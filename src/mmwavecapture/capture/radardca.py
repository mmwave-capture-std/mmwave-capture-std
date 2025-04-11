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

import mmwavecapture.dca1000
import mmwavecapture.radar
from mmwavecapture.capture.capture import CaptureHardware


class TcpdumpCapture:
    def __init__(self, tcpdump_bin: str, interface: str, dca_ip: str):
        self.tcpdump_bin = tcpdump_bin
        self.interface = interface
        self.dca_ip = dca_ip
        self.file_capture_proc = None
        self.stream_capture_proc = None
        self.stream_thread = None
        self.stop_event = threading.Event()

    def start_file_capture(self, outfile: Path):
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
        self.dca = mmwavecapture.dca1000.DCA1000()
        self.dca.config.dca_ip = self._dca_ip
        self.dca.config.dca_config_port = self._dca_config_port

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

        # Tcpdump
        self.tcpdump = TcpdumpCapture(self.TCPDUMP_BIN_PATH, dca_eth_interface, dca_ip)

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
        self.tcpdump.start_file_capture(self.base_path / self.PCAP_OUTPUT_FILENAME)

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
