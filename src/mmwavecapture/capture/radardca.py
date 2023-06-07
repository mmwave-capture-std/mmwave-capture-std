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
import subprocess
from typing import Any, Dict

import netifaces
from loguru import logger

import mmwavecapture.dca1000
import mmwavecapture.radar
from mmwavecapture.capture.capture import CaptureHardware


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

        # tcpdump
        self._cap_tcpdump = None
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

    def start_tcpdump_capture(self, outfile: pathlib.Path) -> None:
        self._cap_tcpdump = subprocess.Popen(
            [
                self.TCPDUMP_BIN_PATH,
                "-i",
                self._dca_eth_interface,
                "-qtn",
                f"udp and host {self._dca_ip}",
                "-w",
                outfile,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def stop_tcpdump_capture(self) -> None:
        if not self._cap_tcpdump:
            return

        self._cap_tcpdump.send_signal(signal.SIGUSR2)  # Flush buffer
        self._cap_tcpdump.send_signal(signal.SIGINT)  # Stop capturing
        self._cap_tcpdump.wait()  # Wait for tcpdump

    @logger.catch(reraise=True)
    def prepare_capture(self) -> None:
        if not self._init_capture_hw:
            raise RuntimeError(
                "Capture hardware are not initialized, run `.init_capture_hw()` first"
            )

        if not self.base_path:
            raise ValueError("Base path is not set")

        # Start DCA tcpdump
        self.start_tcpdump_capture(outfile=self.base_path / self.PCAP_OUTPUT_FILENAME)

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
        self.stop_tcpdump_capture()

    def dump_config(self) -> None:
        if not self.base_path:
            raise ValueError("Base path is not set")
        self.radar.dump_config(self.base_path / self.RADAR_CONFIG_FILENAME)
        self.dca.dump_config(self.base_path / self.DCA_CONFIG_FILENAME)
