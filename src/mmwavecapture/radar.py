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


class Radar:
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
        self._initialized = False
        self._config_port = config_port
        self._config_baudrate = config_baudrate
        self._data_port = data_port
        self._data_baudrate = data_baudrate
        self._timeout = timeout
        self._capture_frames = capture_frames
        self._config_filename = config_filename
        self._config = [
            n.strip()
            for n in open(self._config_filename).readlines()
            if not n.startswith("%")
        ]  # skip comments in config file

        self._config_serial = serial.Serial()
        self._data_serial = serial.Serial()

        if initialize_connection_and_radar:
            self.initialize()

    @property
    def capture_frames(self) -> int:
        return self._capture_frames

    def set_capture_frames(self, capture_frames: int) -> None:
        self._capture_frames = capture_frames

    def _send_command(self, command: str) -> None:
        # Put command "" to `logger.debug`
        log = logger.info if command else logger.debug
        log(f"{self._config_port} - command: {command}")

        self._config_serial.write(f"{command}\n".encode("utf-8"))

    def _send_command_safe(self, command: str) -> None:
        self._send_command(command)
        time.sleep(0.01)  # XXX: Serious? It could be affect by the baudrate

    @logger.catch(reraise=True)
    def _send_command_and_check_output(self, command: str) -> str:
        self._send_command_safe(command)
        self._send_command("")  # Force a `mmwDemo:/>\n` response

        response = self._config_serial.read_until(b"mmwDemo:/>\n")
        logger.debug(f"{self._config_port} - raw resp: {response}")

        if not response:
            raise RuntimeError(
                f"{self._config_port} - No response from radar, try to increase timeout"
            )

        response = re.findall(RADAR_OUTPUT_REGEX, response.decode("utf-8"), re.DOTALL)[
            0
        ].strip()

        logger.info(f"{self._config_port} - response: {response}")
        if "Done" not in response:
            raise RuntimeError(
                f"{self._config_port} - Command `{command}` failed: {response}"
            )
        return response

    def _flush_radar_config_serial_buffer(self) -> None:
        self._send_command("")

        flushed = self._config_serial.read_until(b"mmwDemo:/>\n")
        logger.info(f"{self._config_port} - flush: {flushed}")

    def get_radar_status(self):
        resp = self._send_command_and_check_output("queryDemoStatus")
        state, data_baudrate = re.search(RADAR_STATUS_QUERY_REGEX, resp).groups()
        return RadarStatus(int(state)), int(data_baudrate)

    def initialize(self) -> None:
        self.connect_serials()
        self._flush_radar_config_serial_buffer()
        self._initialized = True

    def connect_serials(self) -> None:
        self._config_serial.port = self._config_port
        self._config_serial.baudrate = self._config_baudrate
        self._config_serial.timeout = self._timeout
        self._config_serial.open()

        self._data_serial.port = self._data_port
        self._data_serial.baudrate = self._data_baudrate
        self._data_serial.timeout = self._timeout
        self._data_serial.open()

    def close_serials(self) -> None:
        self._config_serial.close()
        self._data_serial.close()

    @logger.catch(reraise=True)
    def config(self) -> None:
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
        if not self._initialized:
            raise Exception(f"{self._config_port} - Radar not initialized")

        self._send_command_and_check_output("sensorStart")

    @logger.catch(reraise=True)
    def stop_sensor(self) -> None:
        if not self._initialized:
            raise Exception(f"{self._config_port} - Radar not initialized")

        self._send_command_and_check_output("sensorStop")

    def __del__(self):
        self.close_serials()
