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
import shutil
import signal
import subprocess
from typing import Any, Dict

import grpc
from loguru import logger

import cascadedradar_pb2  # type: ignore[import]
import cascadedradar_pb2_grpc  # type: ignore[import]
from mmwavecapture.capture.capture import CaptureHardware


class CascadedGrpc(CaptureHardware):
    CASCADED_RADAR_CONFIG_FILENAME = "mmwaveconfig.txt"

    @logger.catch(reraise=True)
    def __init__(
        self,
        hw_name: str,
        radar_config_filename: pathlib.Path,
        tda_ip: str = "192.168.33.180",
        tda_port: int = 5001,
        grpc_server_ip: str = "localhost",
        grpc_server_port: int = 50051,
        capture_frames: int = 100,
        init_capture_hw: bool = True,
        **kwargs: Dict[str, Any],
    ) -> None:
        self.hw_name = hw_name
        self._radar_config_filename = pathlib.Path(radar_config_filename)
        self._tda_ip = tda_ip
        self._tda_port = tda_port
        self._grpc_server_ip = grpc_server_ip
        self._grpc_server_port = grpc_server_port
        self._capture_frames = capture_frames
        self._init_capture_hw = init_capture_hw

        # Init gRPC channel
        self._grpc_channel = grpc.insecure_channel(
            f"{self._grpc_server_ip}:{self._grpc_server_port}"
        )
        self._grpc_stub = cascadedradar_pb2_grpc.CascadedRadarStub(self._grpc_channel)

        if init_capture_hw:
            self.init_capture_hw()
        else:
            # Skip the init process
            self._init_capture_hw = True

    @logger.catch(reraise=True)
    def init_capture_hw(self) -> None:
        # Init Cascaded Radar
        req = cascadedradar_pb2.SetConfigFilenameRequest(
            filename=self._radar_config_filename.resolve().as_posix()
        )
        res = self._grpc_stub.SetConfigFilename(req)
        if res.ret_val != 0:
            raise RuntimeError(f"Failed to set radar config filename: {res.ret_val}")

        # Connect to TDA
        req = cascadedradar_pb2.ConnectTdaRequest(ip=self._tda_ip, port=self._tda_port)
        res = self._grpc_stub.ConnectTda(req)
        if res.ret_val != 0:
            raise RuntimeError(f"Failed to connect to TDA: {res.ret_val}")

        # Init radar
        req = cascadedradar_pb2.EmptyRequest()
        res = self._grpc_stub.InitDevices(req)
        if res.ret_val != 0:
            raise RuntimeError(f"Failed to init radar: {res.ret_val}")

        # Config radar
        req = cascadedradar_pb2.EmptyRequest()
        res = self._grpc_stub.ConfigDevices(req)
        if res.ret_val != 0:
            raise RuntimeError(f"Failed to config radar: {res.ret_val}")

        # Set init flag (they could call after class initialization)
        self._init_capture_hw = True

    @logger.catch(reraise=True)
    def prepare_capture(self) -> None:
        if not self._init_capture_hw:
            raise RuntimeError(
                "Capture hardware are not initialized, run `.init_capture_hw()` first"
            )

        if not self.base_path:
            raise ValueError("Base path is not set")

        # Setup TDA capture directory
        req = cascadedradar_pb2.SetCaptureDirectoryRequest(
            directory=self.base_path.as_posix().replace("/", "-")
        )
        res = self._grpc_stub.SetCaptureDirectory(req)
        if res.ret_val != 0:
            raise RuntimeError(f"Failed to set capture directory: {res.ret_val}")

        # Setup expect total capture frames
        req = cascadedradar_pb2.SetCaptureFramesRequest(frames=self._capture_frames)
        res = self._grpc_stub.SetCaptureFrames(req)
        if res.ret_val != 0:
            raise RuntimeError(f"Failed to set capture frames: {res.ret_val}")

        # Prepare capture
        req = cascadedradar_pb2.EmptyRequest()
        res = self._grpc_stub.PrepareCapture(req)
        if res.ret_val != 0:
            raise RuntimeError(f"Failed to prepare capture: {res.ret_val}")

    def start_capture(self) -> None:
        req = cascadedradar_pb2.EmptyRequest()
        res = self._grpc_stub.StartCapture(req)
        if res.ret_val != 0:
            raise RuntimeError(f"Failed to start capture: {res.ret_val}")

    def stop_capture(self) -> None:
        # XXX: But why?
        time.sleep(1)

        req = cascadedradar_pb2.EmptyRequest()
        res = self._grpc_stub.StopCapture(req)
        if res.ret_val != 0:
            raise RuntimeError(f"Failed to stop capture: {res.ret_val}")

    def dump_config(self) -> None:
        if not self.base_path:
            raise ValueError("Base path is not set")

        shutil.copy(
            self._radar_config_filename,
            self.base_path / self.CASCADED_RADAR_CONFIG_FILENAME,
        )
