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

import enum
import json
import pathlib
import socket
import struct
import functools

from copy import deepcopy
from typing import Any, Literal, Optional, Union, overload

from loguru import logger


class DCA1000Const:
    """Ref: RF_API/defines.h"""

    MAX_BYTES_PER_PACKET = 1470
    FPGA_CLK_CONVERSION_FACTOR = 1000
    FPGA_CLK_PERIOD_IN_NANO_SEC = 8
    VERSION_BITS_DECODE = 0x7F
    VERSION_NUM_OF_BITS = 7
    PLAYBACK_MODE = 0x4000


class DCA1000MagicNumber(enum.IntEnum):
    MAGIC_HEADER = 0xA55A
    MAGIC_FOOTER = 0xEEAA


class DCA1000Command(enum.IntEnum):
    RESET_FPGA = 1
    RESET_AR_DEV_CMD = 2
    CONFIG_FPGA_GEN = 3
    CONFIG_EEPROM = 4
    RECORD_START = 5
    RECORD_STOP = 6
    PLAYBACK_START = 7  # Not impl
    PLAYBACK_STOP = 8  # Not impl
    SYSTEM_CONNECTION = 9
    SYSTEM_ERROR_STATUS = 0xA
    CONFIG_PACKET_DELAY = 0xB
    CONFIG_DATA_MODE_AR_DEV = 0xC  # Not impl
    INIT_FPGA_PLAYBACK = 0xD  # Not impl
    READ_FPGA_VERSION = 0xE


class DCA1000Config:
    default_config: dict[str, Any] = {
        "dataLoggingMode": "raw",
        "dataTransferMode": "LVDSCapture",
        "dataCaptureMode": "ethernetStream",
        "lvdsMode": 2,
        "dataFormatMode": 3,
        "packetDelay_us": 5,
        "ethernetConfig": {
            "DCA1000IPAddress": "192.168.33.180",
            "DCA1000ConfigPort": 4096,
            "DCA1000DataPort": 4098,
        },
        "ethernetConfigUpdate": {
            "systemIPAddress": "192.168.33.30",
            "DCA1000IPAddress": "192.168.33.180",
            "DCA1000MACAddress": "12-34-56-78-90-12",
            "DCA1000ConfigPort": 4096,
            "DCA1000DataPort": 4098,
        },
    }

    def __init__(self):
        self._config = deepcopy(self.default_config)

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    @property
    def host_ip(self) -> str:
        # This is the IP address of the host computer
        return self._config["ethernetConfigUpdate"]["systemIPAddress"]

    @host_ip.setter
    def host_ip(self, ip: str) -> None:
        self._config["ethernetConfigUpdate"]["systemIPAddress"] = ip

    @property
    def dca_ip(self) -> str:
        return self._config["ethernetConfig"]["DCA1000IPAddress"]

    @dca_ip.setter
    def dca_ip(self, ip: str) -> None:
        self._config["ethernetConfig"]["DCA1000IPAddress"] = ip

    @property
    def dca_config_port(self) -> int:
        return self._config["ethernetConfig"]["DCA1000ConfigPort"]

    @dca_config_port.setter
    def dca_config_port(self, port: int) -> None:
        self._config["ethernetConfig"]["DCA1000ConfigPort"] = port

    @property
    def dca_data_port(self) -> int:
        return self._config["ethernetConfig"]["DCA1000DataPort"]

    @property
    def data_logging_mode(self) -> int:
        return 1 if self._config["dataLoggingMode"] == "raw" else 2

    @property
    def lvds_mode(self) -> int:
        return self._config["lvdsMode"]

    @property
    def data_transfer_mode(self) -> int:
        return 1 if self._config["dataTransferMode"] == "LVDSCapture" else 2

    @property
    def data_capture_mode(self) -> int:
        return 2 if self._config["dataCaptureMode"] == "ethernetStream" else 1

    @property
    def data_format_mode(self) -> int:
        return self._config["dataFormatMode"]

    @property
    def packet_delay_us(self) -> int:
        return self._config["packetDelay_us"]

    @packet_delay_us.setter
    def packet_delay_us(self, delay: int) -> None:
        self._config["packetDelay_us"] = delay


class DCA1000:
    """This class is used to communicate with the DCA1000EVM over ethernet.

    The DCA1000EVM is a data capture card that is used to capture data from the
    Texas Instruments millimeter-wave radar sensor. The DCA1000EVM is connected
    to the host computer via ethernet, and the host computer can send commands
    to the DCA1000EVM to control its behavior.

    This class does not capture data from the DCA1000EVM. Instead, it is used to
    send commands to the DCA1000EVM to control its behavior.

    .. note::
        Currently it does not read config from files. User should eithe config it
        by `CaptureManager` config file or by `DCA1000Config` class.

    """

    @staticmethod
    def log_command(func):
        name = func.__name__

        @functools.wraps(func)
        def wrapped(self, *args, **kwargs):
            logger.trace(f"To DCA {self.config.dca_ip} - sending command: `{name}`")
            res = func(self, *args, **kwargs)
            logger.trace(f"From DCA {self.config.dca_ip} - `{name}` result: {res}")
            return res

        return wrapped

    def __init__(self, config: DCA1000Config = None) -> None:
        self.config = config if config else DCA1000Config()
        self.socks = {}

        self.socks = self._init_sockets()

    def _init_sockets(self) -> dict[str, socket.socket]:
        # Create UDP sockets for each port, and bind them to the host IP
        sockets = {}
        for sock_type, port in self.config.config["ethernetConfig"].items():
            if sock_type.endswith("Port"):
                sock = socket.socket(
                    socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
                )
                sock.bind((self.config.host_ip, port))

                # Convert "DCA1000ConfigPort" to "config"
                sockets[sock_type[7:-4].lower()] = sock

        # It should have {"data": sock, "config": sock}
        return sockets

    def __del__(self):
        for sock in self.socks.values():
            sock.close()

    @overload
    def _send_dca_command(
        self,
        cmd_code: DCA1000Command,
        data: bytes = ...,
        timeout: float = ...,
        return_raw_status: Literal[False] = ...,
    ) -> bool: ...

    @overload
    def _send_dca_command(
        self,
        cmd_code: DCA1000Command,
        data: bytes = ...,
        timeout: float = ...,
        return_raw_status: Literal[True] = ...,
    ) -> int: ...

    def _send_dca_command(
        self,
        cmd_code: DCA1000Command,
        data: bytes = b"",
        timeout: float = 3.0,
        return_raw_status: bool = False,
    ) -> Union[bool, int]:
        # Construct the command header, data, and footer
        cmd_header = struct.pack(
            "<HHH",
            DCA1000MagicNumber.MAGIC_HEADER,
            cmd_code,
            len(data),
        )
        cmd_footer = struct.pack("<H", DCA1000MagicNumber.MAGIC_FOOTER)

        # Combine the header, data, and footer into a single command
        cmd = cmd_header + data + cmd_footer

        # Setup socket timeout
        self.socks["config"].settimeout(timeout)

        # Send the command to the DCA1000
        self.socks["config"].sendto(
            cmd, (self.config.dca_ip, self.config.dca_config_port)
        )

        # Receive the response from the DCA1000
        resp, addr = self.socks["config"].recvfrom(1024)

        # Decode the response
        # Reference: SPRUIJ4A, Table 14, p. 19
        resp_dec = struct.unpack("<HHHH", resp)
        assert resp_dec[0] == DCA1000MagicNumber.MAGIC_HEADER
        assert resp_dec[1] == cmd_code
        assert resp_dec[3] == DCA1000MagicNumber.MAGIC_FOOTER

        if return_raw_status:
            return resp_dec[2]

        # Check if the command was successful
        return resp_dec[2] == 0

    @log_command
    def reset_fpga(self) -> bool:
        """Reset DCA1000EVM FPGA

        Ref: 2.3.3 Reset FPGA, p.40, DCA1000EVM CLI Software Developer Guide, v1.01
        """
        return self._send_dca_command(DCA1000Command.RESET_FPGA)

    @log_command
    def reset_radar(self) -> bool:
        """Reset Radar

        Ref: 2.3.4 Reset Radar, p.42, DCA1000EVM CLI Software Developer Guide, v1.01
        """
        return self._send_dca_command(DCA1000Command.RESET_AR_DEV_CMD)

    @log_command
    def start_record(self) -> bool:
        """Start DCA1000EVM recording

        Ref: 2.3.5 Start Recording, p.45, DCA1000EVM CLI Software Developer Guide, v1.01
        """

        return self._send_dca_command(DCA1000Command.RECORD_START)

    @log_command
    def stop_record(self) -> bool:
        """Stop DCA1000EVM recording

        Ref: 2.3.6 Stop Recording, p.48, DCA1000EVM CLI Software Developer Guide, v1.01
        """
        return self._send_dca_command(DCA1000Command.RECORD_STOP)

    @log_command
    def config_packet_delay(self) -> bool:
        """Set the delay between the config packet and the data packet

        Args:
            delay (int): Delay in microseconds

        Ref: 2.3.7 Configure record delay, p.53, DCA1000EVM CLI Software Developer Guide, v1.01
        """
        # Ref: RF_API.cpp:ConfigureRFDCCard_Record
        #      FPGA_CLK_CONVERSION_FACTOR = 1000
        #      FPGA_CLK_PERIOD_IN_NANO_SEC = 8
        data = struct.pack(
            "<HH",
            *[
                self.config.packet_delay_us
                * DCA1000Const.FPGA_CLK_CONVERSION_FACTOR
                // DCA1000Const.FPGA_CLK_PERIOD_IN_NANO_SEC,
                0,
            ],
        )
        return self._send_dca_command(DCA1000Command.CONFIG_PACKET_DELAY, data)

    @log_command
    def config_fpga(self) -> bool:
        """Configure DCA1000EVM FPGA

        Ref: 2.3.1 Configure FPGA, p.34, DCA1000EVM CLI Software Developer Guide, v1.01
        """
        data = struct.pack(
            "<BBBBBB",
            *[
                self.config.data_logging_mode,
                self.config.lvds_mode,
                self.config.data_transfer_mode,
                self.config.data_capture_mode,
                self.config.data_format_mode,
                30,  # Timer, unconfigurable in pure Python, see 2.3.1-6
            ],
        )
        return self._send_dca_command(DCA1000Command.CONFIG_FPGA_GEN, data)

    @log_command
    def config_eeprom(self) -> bool:
        """Configure DCA1000EVM EEPROM

        Ref: 2.3.2 Configure EEPROM, p.36, DCA1000EVM CLI Software Developer Guide, v1.01
        """
        data = struct.pack(
            "<BBBBBBBBBBBBBBHH",
            *[
                # Host IP
                *map(
                    int,
                    self.config.config["ethernetConfigUpdate"]["systemIPAddress"].split(
                        "."
                    )[::-1],
                ),
                # DCA IP
                *map(
                    int,
                    self.config.config["ethernetConfigUpdate"][
                        "DCA1000IPAddress"
                    ].split(".")[::-1],
                ),
                # DCA MAC
                *map(
                    lambda x: int(x, 16),
                    self.config.config["ethernetConfigUpdate"][
                        "DCA1000MACAddress"
                    ].split("-")[::-1],
                ),
                # DCA config port
                self.config.config["ethernetConfigUpdate"]["DCA1000ConfigPort"],
                # DCA data port
                self.config.config["ethernetConfigUpdate"]["DCA1000DataPort"],
            ],
        )
        return self._send_dca_command(DCA1000Command.CONFIG_EEPROM, data)

    @log_command
    def system_connection(self) -> bool:
        """Check if the DCA1000EVM is connected to the host computer

        Ref: 2.3.11 Query system aliveness status, p.62, DCA1000EVM CLI Software Developer Guide, v1.01
        """
        return self._send_dca_command(DCA1000Command.SYSTEM_CONNECTION)

    @log_command
    def system_error_status(self) -> int:
        """Check DCA1000EVM system error status

        Ref: 2.3.10 Query record process status, p.60, DCA1000EVM CLI Software Developer Guide, v1.01
        """
        # XXX: It will not return anything worth, you can test it as below:
        #        1. Connect the DCA1000 to the host computer
        #        2. Do not start the radar
        #        3. Run `record_start` ($ uv run pytest -k test_record_start)
        #        4. Wait until DCA1000 get LVDS timeout error (about 10 seconds)
        #           you can see a red led of `LVDS_PATH_ERR` is light on your DCA1000 board
        #        5. Run `system_error_status` ($ uv run pytest -k test_system_error_status)
        #        6. You will see it return `0`, but it should be other value
        # Ref: RF_API/configdatarecv.cpp
        return self._send_dca_command(
            DCA1000Command.SYSTEM_ERROR_STATUS, return_raw_status=True
        )

    @log_command
    def read_fpga_version(self) -> tuple[int, int, bool]:
        """Return FPGA version

        Returns:
            tuple[int, int, bool]: (major, minor, playback_mode)
        """
        status = self._send_dca_command(
            DCA1000Command.READ_FPGA_VERSION, return_raw_status=True
        )
        major = status & DCA1000Const.VERSION_BITS_DECODE
        minor = (
            status >> DCA1000Const.VERSION_NUM_OF_BITS
        ) & DCA1000Const.VERSION_BITS_DECODE
        mode = (status & DCA1000Const.PLAYBACK_MODE) == DCA1000Const.PLAYBACK_MODE
        return major, minor, mode

    def read(self):
        """Read DCA1000EVM data from host ip data port

        .. note::
            It is not recommended to use this method.
        """
        return self.socks["data"].recv(DCA1000Const.MAX_BYTES_PER_PACKET)

    def dump_config(self, outfile: pathlib.Path):
        """Dump the current configuration to a JSON file"""
        with open(outfile, "w") as f:
            json.dump(self.config._config, f, indent=4, ensure_ascii=False)
