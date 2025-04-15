#
# Copyright (c) 2023 Louie Lu <louielu@cs.unc.edu>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted (subject to the limitations in the disclaimer
# below) provided that the following conditions are met:
#
#      * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#
#      * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#
#      * Neither the name of the copyright holder nor the names of its
#      contributors may be used to endorse or promote products derived from this
#      software without specific prior written permission.
#
# NO EXPRESS OR IMPLIED LICENSES TO ANY PARTY'S PATENT RIGHTS ARE GRANTED BY
# THIS LICENSE. THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND
# CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
# IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#

from __future__ import annotations

import time
import pathlib
import signal
import struct
import subprocess
import threading
from typing import Any, Dict

import netifaces
from loguru import logger

import disspcap
import mmwavecapture.dca1000
import mmwavecapture.radar
from mmwavecapture.capture.capture import CaptureHardware


class ZmqPublisher:
    """
    A class to publish data (metadata + NumPy array) via ZeroMQ PUSH socket.

    Handles sending with copy=False, track=True and ensures the send
    completes before returning from the publish method.
    """

    def __init__(self, zmq_address: str):
        """
        Initializes the ZMQ context and socket.

        Args:
            zmq_address: The address string for ZMQ socket binding (e.g., "tcp://*:5556").
        """
        logger.info(f"Initializing ZmqPublisher for address: {zmq_address}")
        self.zmq_address = zmq_address
        self._context = zmq.Context()
        self._socket = self._context.socket(zmq.PUSH)

        # Set linger to 0 to discard messages on close immediately if needed
        self._socket.setsockopt(zmq.LINGER, 0)

        # Set high water mark (optional)
        self._socket.set_hwm(1000)

        logger.info(f"Binding ZMQ PUSH socket to {self.zmq_address}")
        self._socket.bind(self.zmq_address)

    def publish(self, md: Dict[str, Any], frame: np.ndarray) -> None:
        """
        Publishes metadata and a NumPy frame via ZeroMQ.

        Sends metadata as JSON, then the frame buffer without copying.
        Waits until ZeroMQ is finished with the frame buffer before returning.

        Args:
            md: A dictionary containing metadata (e.g., dtype, shape).
            frame: The NumPy array data to send.
        """
        try:
            # Ensure frame is C-contiguous for zero-copy. Often true, but good practice.
            # If performance is critical and arrays are often non-contiguous,
            # this copy might negate zero-copy benefits. Profile if needed.
            if not frame.flags["C_CONTIGUOUS"]:
                logger.warning(
                    "Frame is not C-contiguous. Making a copy before sending."
                )
                frame = np.ascontiguousarray(frame)  # This forces a copy!

            logger.debug(
                f"ZMQ Publishing: Shape={md.get('shape')}, Dtype={md.get('dtype')}"
            )

            # 1. Send metadata (JSON) - mark as not the last part
            self._socket.send_json(md, flags=zmq.SNDMORE)

            # 2. Send NumPy array data (no copy, track completion) - this IS the last part
            tracker = self._socket.send(frame, copy=False, track=True)

            # 3. Wait for ZMQ to finish using the buffer *within the publisher*
            #    This ensures the buffer is valid until the publisher returns.
            wait_start_time = time.time()
            while not tracker.done:
                time.sleep(0.0001)  # Sleep 100 microseconds to yield CPU

            wait_duration = time.time() - wait_start_time
            if wait_duration > 0.01:  # Log if waiting takes unexpectedly long
                logger.warning(f"ZMQ tracker wait took {wait_duration:.4f} seconds.")
            else:
                logger.debug(f"ZMQ tracker done (waited {wait_duration:.4f} s).")

        except zmq.ZMQError as e:
            logger.error(f"ZMQ Error during publish to {self.zmq_address}: {e}")
            # Optional: Implement reconnect logic or raise the exception
        except Exception as e:
            # Catch other potential errors (e.g., JSON serialization)
            logger.exception(f"Unexpected error during ZMQ publish: {e}")

    def close(self) -> None:
        """Closes the ZMQ socket and terminates the context."""
        logger.info(f"Closing ZMQ publisher socket for {self.zmq_address}")
        if self._socket and not self._socket.closed:
            self._socket.close()
        logger.info(f"Terminating ZMQ context for {self.zmq_address}")
        if self._context and not self._context.closed:
            self._context.term()


class RadarPacketAggregator:
    def __init__(self, radar_frame_iq_size: int, callbacks: Any = None):
        self.data = disspcap.DcaDataStreaming()
        self.radar_frame_iq_size = radar_frame_iq_size
        self.samples_per_packet = 364  # 1456 bytes / 4 bytes per complex sampl
        self.at_most_waiting_packets = (
            self.radar_frame_iq_size + self.samples_per_packet - 1
        ) // self.samples_per_packet
        self.callbacks = callbacks if callbacks else []
        if not isinstance(self.callbacks, list):
            logger.warning("Callbacks should be a list. Converting to list.")
            self.callbacks = [self.callbacks]

        # Initialize tracking variables
        self.synced = False
        self.expected_seq_id = None
        self.next_frame_start_id = None
        self.samples_to_discard = 0

    def find_next_frame_start_id(self, seq_id):
        """
        Calculate the next sequence ID that will start a new frame and
        how many samples to discard from that packet.

        Returns:
            tuple: (next_frame_start_id, samples_to_discard)
        """
        samples_per_packet = 364

        # Calculate total samples up to this sequence
        total_samples_before = (seq_id - 1) * samples_per_packet

        # Calculate position in frame and samples to next boundary
        position_in_frame = total_samples_before % self.radar_frame_iq_size
        samples_to_next_boundary = self.radar_frame_iq_size - position_in_frame

        # Calculate how many packets until the next frame starts
        packets_to_next_boundary = (samples_to_next_boundary - 1) // samples_per_packet

        # The sequence ID that will start the next frame
        next_frame_start_id = seq_id + packets_to_next_boundary

        # Calculate how many samples to discard from the packet at the next frame start
        # This handles packets that cross frame boundaries
        if samples_to_next_boundary < samples_per_packet:
            discard_samples = samples_per_packet - samples_to_next_boundary
        else:
            discard_samples = 0

        return next_frame_start_id, discard_samples

    def push_packet(self, header: bytes, data: bytes):
        packet = disspcap.Packet(header=header, data=data)
        if not packet.dca_raw:
            return

        current_seq_id = packet.dca_raw.seq_id

        # Out of order
        if self.expected_seq_id and self.expected_seq_id != current_seq_id:
            self.synced = False
            self.next_frame_start_id = None
            logger.warning(
                f"Out of order packet: expected {self.expected_seq_id}, got {current_seq_id}"
            )

            self.expected_seq_id = None

        # Handle packet sychronization
        if not self.synced:
            if (
                not self.next_frame_start_id
                or abs(current_seq_id - self.next_frame_start_id)
                > self.at_most_waiting_packets
            ):
                self.next_frame_start_id, self.samples_to_discard = (
                    self.find_next_frame_start_id(current_seq_id)
                )

            # Only process if this is exactly at a frame start
            if self.next_frame_start_id == current_seq_id:
                self.data.clear()
                self.data.add(packet.dca_raw)

                # If we need to discard samples from this packet to align with the frame boundary
                if self.samples_to_discard > 0:
                    self.data.clear(self.samples_to_discard)

                self.synced = True
                self.expected_seq_id = current_seq_id + 1

            return

        # Normal case: We got the packet we expected
        self.expected_seq_id = current_seq_id + 1
        self.data.add(packet.dca_raw)

        # Check if we have a complete frame
        if len(self.data) >= self.radar_frame_iq_size:
            # Extract exactly one frame
            frame = self.data.get_numpy()[: self.radar_frame_iq_size]
            md = {"dtype": "complex64", "shape": frame.shape, "timestamp": time.time()}

            # Process frame with callbacks
            for callback in self.callbacks:
                if callable(callback):
                    callback(md, frame)

            # Remove exactly one frame worth of data
            self.data.clear(self.radar_frame_iq_size)


class TcpdumpCapture:
    def __init__(self, tcpdump_bin: str, interface: str, dca_ip: str):
        self.tcpdump_bin = tcpdump_bin
        self.interface = interface
        self.dca_ip = dca_ip
        self.file_capture_proc = None
        self.stream_capture_proc = None
        self.stream_thread = None
        self.stop_event = threading.Event()

    def start_file_capture(self, outfile: pathlib.Path):
        self.file_capture_proc = subprocess.Popen(
            [
                self.tcpdump_bin,
                "-i",
                self.interface,
                "-qtn",
                f"udp and host {self.dca_ip}",
                "-w",
                str(outfile),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info(f"Started packet capture to file {outfile}")

    def start_stream_capture(self, packet_aggregator):
        self.stream_capture_proc = subprocess.Popen(
            [
                self.tcpdump_bin,
                "-i",
                self.interface,
                "-qtn",
                "-U",
                f"udp and host {self.dca_ip}",
                "-w",
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        pcap_header = self.stream_capture_proc.stdout.read(24)
        if len(pcap_header) < 24:
            raise RuntimeError("Failed to read pcap header from tcpdump")

        magic, v_major, v_minor, *_ = struct.unpack("=IHHiIII", pcap_header)
        logger.debug(f"Pcap header: magic=0x{magic:08x}, version={v_major}.{v_minor}")

        if magic not in (0xA1B2C3D4, 0xD4C3B2A1):
            raise RuntimeError(f"Invalid pcap magic number: 0x{magic:08x}")

        self.stop_event.clear()
        self.stream_thread = threading.Thread(
            target=self._stream_packets,
            args=(self.stream_capture_proc.stdout, packet_aggregator),
            daemon=True,
        )
        self.stream_thread.start()
        logger.info("Started tcpdump stream capture")

    def _stream_packets(self, stdout_pipe, aggregator):
        while not self.stop_event.is_set():
            header = stdout_pipe.read(16)
            if not header or len(header) < 16:
                logger.debug("End of stream or error reading packet header")
                return
            ts_sec, ts_usec, caplen, origlen = struct.unpack("=IIII", header)
            data = stdout_pipe.read(caplen)
            if not data or len(data) < caplen:
                logger.error(
                    f"Incomplete packet data: expected {caplen}, got {len(data)}"
                )
                return
            aggregator.push_packet(header, data)

    def stop(self):
        if self.file_capture_proc:
            self.file_capture_proc.send_signal(signal.SIGUSR2)
            self.file_capture_proc.send_signal(signal.SIGINT)
            self.file_capture_proc.wait()
            logger.info("Stopped file capture")

        if self.stream_capture_proc:
            self.stop_event.set()
            self.stream_capture_proc.send_signal(signal.SIGUSR2)
            self.stream_capture_proc.send_signal(signal.SIGINT)
            self.stream_capture_proc.wait()
            logger.info("Stopped stream capture")

        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join(timeout=3.0)
            logger.info("Stopped stream thread")


class RadarDCA(CaptureHardware):
    TCPDUMP_BIN_PATH = "/usr/sbin/tcpdump"  # XXX: Windows?
    PCAP_OUTPUT_FILENAME = "dca.pcap"
    RADAR_CONFIG_FILENAME = "radar.cfg"
    DCA_CONFIG_FILENAME = "dca.json"

    @logger.catch(reraise=True)
    def __init__(
        self,
        hw_name: str,
        dca_eth_interface: str,
        radar_config_filename: pathlib.Path,
        radar_config_port: str = "/dev/ttyACM0",
        radar_data_port: str = "/dev/ttyACM1",
        dca_ip: str = "192.168.33.180",
        dca_config_port: int = 4096,
        host_ip: str = "192.168.33.30",
        capture_frames: int = 100,
        init_capture_hw: bool = True,
        enable_save_pcap: bool = True,
        enable_zmq_streaming: bool = False,
        zmq_stream_address: str = "tcp://*:5556",
        **kwargs: Dict[str, Any],
    ) -> None:
        self.hw_name = hw_name
        self._radar_config_filename = radar_config_filename
        self._radar_config_port = radar_config_port
        self._radar_data_port = radar_data_port
        self._dca_eth_interface = dca_eth_interface
        self._dca_ip = dca_ip
        self._dca_config_port = dca_config_port
        self._host_ip = host_ip
        self._capture_frames = capture_frames
        self._init_capture_hw = init_capture_hw
        self._enable_save_pcap = enable_save_pcap
        self._enable_zmq_streaming = enable_zmq_streaming
        self._zmq_stream_address = zmq_stream_address

        # Process handles
        self._catcher = None

        # DCA interface & host IP check
        if dca_eth_interface not in netifaces.interfaces():
            raise ValueError(f"Interface {dca_eth_interface} not found")
        if netifaces.AF_INET not in netifaces.ifaddresses(dca_eth_interface):
            raise ValueError(f"Interface {dca_eth_interface} has no IPv4 address")
        if host_ip not in [
            netif["addr"]
            for netif in netifaces.ifaddresses(dca_eth_interface)[netifaces.AF_INET]
        ]:
            raise ValueError(f"Host IP {host_ip} not found in {dca_eth_interface}")

        # DCA1000EVM
        self.dca_config = mmwavecapture.dca1000.DCA1000Config()
        self.dca_config.dca_ip = self._dca_ip
        self.dca_config.dca_config_port = self._dca_config_port
        self.dca = mmwavecapture.dca1000.DCA1000(self.dca_config)

        # Radar
        self.radar = mmwavecapture.radar.Radar(
            config_port=self._radar_config_port,
            config_baudrate=115200,
            data_port=self._radar_data_port,
            data_baudrate=921600,
            config_filename=self._radar_config_filename,
            initialize_connection_and_radar=False,
            capture_frames=self._capture_frames,
        )

        # Radar config
        radar_config = mmwavecapture.radar.RadarCoreConfig(self._radar_config_filename)
        self.radar_frame_iq_size = radar_config.frame_iq_size

        # Tcpdump
        self.tcpdump = TcpdumpCapture(self.TCPDUMP_BIN_PATH, dca_eth_interface, dca_ip)

        # Callbacks
        self.callbacks = []
        if self._enable_zmq_streaming:
            self.zmq_publisher = ZmqPublisher(self._zmq_stream_address)
            self.callbacks.append(self.zmq_publisher.publish)

        self.aggregator = RadarPacketAggregator(
            self.radar_frame_iq_size, self.callbacks
        )

        if init_capture_hw:
            self.init_capture_hw()

    @logger.catch(reraise=True)
    def init_capture_hw(self) -> None:
        # Check DCA1000EVM connection
        if not self.dca.system_connection():
            raise RuntimeError(f"DCA1000EVM connection error at {self._dca_ip}")

        # Initialize DCA1000EVM
        self.dca.reset_radar()
        self.dca.reset_fpga()
        self.dca.config_fpga()
        self.dca.config_packet_delay()

        # Initialize radar
        self.radar.initialize()
        self.radar.config()

        # Set init flag (they could call after class initialization)
        self.init_capture_hw = True

    @logger.catch(reraise=True)
    def prepare_capture(self) -> None:
        if not self._init_capture_hw:
            raise RuntimeError(
                "Capture hardware are not initialized, run `.init_capture_hw()` first"
            )

        if not self.base_path:
            raise ValueError("Base path is not set")

        # Start tcpdump
        if self._enable_save_pcap:
            self.tcpdump.start_file_capture(self.base_path / self.PCAP_OUTPUT_FILENAME)

        # Start streaming
        if self._enable_zmq_streaming:
            self.tcpdump.start_stream_capture(self.aggregator)

        # Start DCA termination catcher
        self._catcher = subprocess.Popen(
            [
                self.TCPDUMP_BIN_PATH,
                "-i",
                self._dca_eth_interface,
                "-s",
                "256",
                "-c",
                "1",
                "-qtn",
                "udp[10:4] == 0x0a000001",  # Match no LVDS data
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait tcpdump to start capture
        time.sleep(0.1)  # XXX: Another constant?

        # Start DCA1000EVM
        self.dca.start_record()

    def start_capture(self) -> None:
        self.radar.start_sensor()

    def stop_capture(self) -> None:
        if self._catcher:
            self._catcher.wait()
        self.tcpdump.stop()

    def dump_config(self) -> None:
        if not self.base_path:
            raise ValueError("Base path is not set")
        self.radar.dump_config(self.base_path / self.RADAR_CONFIG_FILENAME)
        self.dca.dump_config(self.base_path / self.DCA_CONFIG_FILENAME)
