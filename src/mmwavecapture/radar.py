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
import re
import pathlib
import time
from typing import Optional

import serial
from loguru import logger


RADAR_OUTPUT_REGEX = r"\n(.*?)mmwDemo"
RADAR_STATUS_QUERY_REGEX = r"Sensor State:\s(\d+)\n\rData port baud rate:\s(\d+)"


class RadarStatus(enum.IntEnum):
    INIT = 0
    OPENED = 1

    # Started by `sensorStart` command
    STARTED = 2

    # Explicitly stopped by `sensorStop`, hitting number of frames will not cause this
    STOPPED = 3


class RadarCoreConfig:
    def __init__(self, filename: Optional[pathlib.Path] = None):
        #: The radar config
        self._config: dict[str, list[str]] = {}

        # XXX: only support reading from file at this moment
        if filename is not None:
            with open(filename) as f:
                for n in f.readlines():
                    if n.startswith("%") or " " not in n:
                        continue
                    cmd, args = n.strip().split(" ", 1)
                    self._config[cmd] = args.split(" ")

        #: Total number of frames to capture, 0 means infinite
        self.frames: int = int(self._config["frameCfg"][3])

        #: Frame period (ms)
        self.frame_period: float = float(self._config["frameCfg"][4])

        #: Number of chirps per frame
        self.chirps: int = int(self._config["frameCfg"][2])

        #: Total TX antennas
        self.tx: int = bin(int(self._config["channelCfg"][1]))[2:].count("1")

        #: Total RX antennas
        self.rx: int = bin(int(self._config["channelCfg"][0]))[2:].count("1")

        #: Total virtual antennas
        self.virtual_antennas: int = self.tx * self.rx

        #: Number of ADC samples per chirp
        self.samples: int = int(self._config["profileCfg"][9])

        #: Frame I/Q size
        self.frame_iq_size: int = self.chirps * self.tx * self.rx * self.samples

        #: Shape of the raw data considering TX and RX antennas.
        #:
        #: If the number of frames is 0, the first dimension will be -1
        self.antenna_shape: tuple[int, int, int, int, int] = (
            self.frames if self.frames != 0 else -1,
            self.chirps,
            self.tx,
            self.rx,
            self.samples,
        )

        #: Shape of the raw data considering virtual antennas
        #:
        #: If the number of frames is 0, the first dimension will be -1
        self.virtual_shape: tuple[int, int, int, int] = (
            self.frames if self.frames != 0 else -1,
            self.chirps,
            self.virtual_antennas,
            self.samples,
        )


class Radar:
    """This is a Texas Instrumenst xWR16xx/18xx mmwave radar interface.

    The main goal of this class is to provide a simple interface to communicate
    and config the radar to run the sensor for specified number of frames. It does
    not capture TLV data from the radar.

    It force user to provide a radar config file during the
    construction of the class.

    :param config_port: The serial port to radar config UART
    :type config_port: str
    :param config_baudrate: The baudrate of the radar config UART
    :type config_baudrate: int
    :param data_port: The serial port to radar data UART
    :type data_port: str
    :param data_baudrate: The baudrate of the radar data UART
    :type data_baudrate: int
    :param config_filename: The radar config filename, the format should be
        compatible with the mmwave SDK
    :type config_filename: pathlib.Path
    :param timeout: The timeout for serial communication, defaults to 3 seconds
    :type timeout: int, optional
    :param initialize_connection_and_radar: If set to True, the radar will be initialized
        and connected during the construction of the class, defaults to False
    :type initialize_connection_and_radar: bool, optional
    :param capture_frames: The number of frames to capture, defaults to 100 frames
    :type capture_frames: int, optional
    """

    def __init__(
        self,
        config_port: str,
        config_baudrate: int,
        data_port: str,
        data_baudrate: int,
        config_filename: pathlib.Path,
        timeout: int = 3,
        initialize_connection_and_radar: bool = False,
        capture_frames: int = 100,
    ):
        """Constructor method"""
        self._initialized = False
        self._config_port = config_port
        self._config_baudrate = config_baudrate
        self._data_port = data_port
        self._data_baudrate = data_baudrate
        self._timeout = timeout
        self._config_filename = config_filename
        self._config = [
            n.strip()
            for n in open(self._config_filename).readlines()
            if not n.startswith("%")
        ]  # skip comments in config file
        self.capture_frames = capture_frames

        self._config_serial = serial.Serial()
        self._data_serial = serial.Serial()

        if initialize_connection_and_radar:
            self.initialize()

    @property
    def capture_frames(self) -> int:
        """The number of frames to capture

        :getter: Return the number of frames to capture
        :setter: Set the number of frames to capture,
            it will update the `farmeCfg` command in loaded config
        :type: int
        """
        return self._capture_frames

    @capture_frames.setter
    @logger.catch(reraise=True)
    def capture_frames(self, capture_frames: int) -> None:
        self._capture_frames = capture_frames

        # We need to replace frameCfg `number of frames` with `self._capture_frames`
        # Ref: `frameCfg/number of frames`, p.24, MMWAVE SDK User Guide
        for i, command in enumerate(self._config):
            if command.startswith("frameCfg"):
                frame_cfg = command.split(" ")
                frame_cfg[4] = f"{self._capture_frames:d}"
                command = " ".join(frame_cfg)
                self._config[i] = command
                return
        raise RuntimeError(
            f"{self._config_port} - missing `frameCfg` in config file: {self._config_filename}"
        )

    def _send_command(self, command: str) -> None:
        """Send command to radar config UART. It will encode str to bytes
        and append a newline character to the end of the command.

        :param command: The command to send to radar config UART
        :type: str
        """
        logger.trace(f"{self._config_port} - command: {command}")

        self._config_serial.write(f"{command}\n".encode("utf-8"))

    def _send_command_safe(self, command: str) -> None:
        """Safe way to send command to radar config UART.
        Add additional 0.1 seconds sleep after sending command.

        :param command: The command to send to radar config UART
        :type: str
        """
        self._send_command(command)
        time.sleep(0.01)  # XXX: Serious? It could be affect by the baudrate

    @logger.catch(reraise=True)
    def _send_command_and_check_output(self, command: str) -> str:
        """Send command to radar config UART and check the output.

        By forcing a `mmwDemo:/>` response, we can make sure the command
        is finished. Then we can check if `Done` is in the response
        to see if the command is executed successfully.

        :param command: The command to send to radar config UART
        :type: str
        """
        self._send_command_safe(command)
        self._send_command("")  # Force a `mmwDemo:/>\n` response

        response = self._config_serial.read_until(b"mmwDemo:/>\n")
        logger.trace(f"{self._config_port} - raw resp: {response}")

        if not response:
            raise RuntimeError(
                f"{self._config_port} - No response from radar, try to increase timeout"
            )

        response = re.findall(RADAR_OUTPUT_REGEX, response.decode("utf-8"), re.DOTALL)[
            0
        ].strip()

        logger.trace(f"{self._config_port} - response: {response}")
        if "Done" not in response:
            raise RuntimeError(
                f"{self._config_port} - Command `{command}` failed: {response}"
            )
        return response

    def _flush_radar_config_serial_buffer(self) -> None:
        """Flush the radar config serial buffer"""
        self._send_command("")

        flushed = self._config_serial.read_until(b"mmwDemo:/>\n")
        logger.trace(f"{self._config_port} - flush: {flushed}")

    def get_radar_status(self):
        """Get radar status (MMWAVE SDK OOB Demo)

        :return: Radar status and data baudrate
        :rtype: Tuple[RadarStatus, int]1
        """
        resp = self._send_command_and_check_output("queryDemoStatus")
        state, data_baudrate = re.search(RADAR_STATUS_QUERY_REGEX, resp).groups()
        return RadarStatus(int(state)), int(data_baudrate)

    def initialize(self) -> None:
        """Connect to radar and flush the radar config serial buffer"""
        self.connect_serials()
        self._flush_radar_config_serial_buffer()
        self._initialized = True

    def connect_serials(self) -> None:
        """Connect serial ports, setup baudrate and timeout"""
        self._config_serial.port = self._config_port
        self._config_serial.baudrate = self._config_baudrate
        self._config_serial.timeout = self._timeout
        self._config_serial.open()

        self._data_serial.port = self._data_port
        self._data_serial.baudrate = self._data_baudrate
        self._data_serial.timeout = self._timeout
        self._data_serial.open()

    def close_serials(self) -> None:
        """Close serial ports"""
        self._config_serial.close()
        self._data_serial.close()

    @logger.catch(reraise=True)
    def config(self) -> None:
        """Send config commands to radar"""
        if not self._initialized:
            raise Exception(f"{self._config_port} - Radar not initialized")

        for command in self._config:
            # We need to replace frameCfg `number of frames` with `self._capture_frames`
            # Ref: `frameCfg/number of frames`, p.24, MMWAVE SDK User Guide
            if command.startswith("frameCfg"):
                frame_cfg = command.split(" ")
                frame_cfg[4] = f"{self._capture_frames:d}"
                command = " ".join(frame_cfg)

            # Skip `sensorStart` command
            if command.startswith("sensorStart"):
                continue

            self._send_command_and_check_output(command)

    @logger.catch(reraise=True)
    def start_sensor(self) -> None:
        """Send `sensorStart` command to radar"""
        if not self._initialized:
            raise Exception(f"{self._config_port} - Radar not initialized")

        self._send_command_and_check_output("sensorStart")

    @logger.catch(reraise=True)
    def stop_sensor(self) -> None:
        """Send `sensorStop` command to radar"""
        if not self._initialized:
            raise Exception(f"{self._config_port} - Radar not initialized")

        self._send_command_and_check_output("sensorStop")

    def dump_config(self, outfile: pathlib.Path) -> None:
        """Dump current radar config to file"""
        with open(outfile, "w") as f:
            f.write("\n".join(self._config))

    def __del__(self):
        self.close_serials()
