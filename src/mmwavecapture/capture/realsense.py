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

import threading
import pathlib
from typing import Optional, Tuple, Any, Dict

import cv2
import pyrealsense2 as rs
import numpy as np
from loguru import logger

from mmwavecapture.capture.capture import CaptureHardware


FONT_FACE = cv2.FONT_HERSHEY_SIMPLEX
FONT_PLACEMENT = (540, 40)
FONT_SCALE = 1
FONT_COLOR = (0, 0, 0)
FONT_THIKNESS = 2
FONT_LINETYPE = 2

TEXT_RECTS, BASELINE = cv2.getTextSize(
    "0000",
    FONT_FACE,
    FONT_SCALE,
    FONT_THIKNESS,
)

RECTS = (
    (FONT_PLACEMENT[0], FONT_PLACEMENT[1] + BASELINE // 2),
    (
        FONT_PLACEMENT[0] + TEXT_RECTS[0],
        FONT_PLACEMENT[1] - TEXT_RECTS[1] - BASELINE,
    ),
    (255, 255, 255),
    -1,
)


def stamp_framenum(img: np.ndarray, frame: int) -> np.ndarray:
    text = f"{frame:04d}"

    img = cv2.rectangle(img, *RECTS)

    img = cv2.putText(
        img,
        f"{frame:04d}",
        FONT_PLACEMENT,
        FONT_FACE,
        FONT_SCALE,
        FONT_COLOR,
        FONT_THIKNESS,
        FONT_LINETYPE,
    )

    return img


class Realsense(CaptureHardware):
    COLOR_OUTPUT_FILENAME = "color.avi"

    def __init__(
        self,
        hw_name: str,
        fps: int = 30,
        resolution: Tuple[int, int] = (1920, 1080),
        capture_frames: int = 150,
        rotate: bool = False,
        **kwargs: Dict[str, Any],
    ) -> None:
        self.hw_name = hw_name
        self._fps = fps
        self._resolution = resolution
        self._capture_frames = capture_frames
        self._capture_thread: Optional[threading.Thread] = None
        self._rotate = rotate

        # Realsense HW
        self._pipeline = rs.pipeline()
        self._config = rs.config()

        # Output video file
        self._colorwriter: Optional[cv2.ViedoWriter] = None

        self.init_capture_hw()

    def init_capture_hw(self) -> None:
        self._config.enable_stream(
            rs.stream.color,
            self._resolution[0],
            self._resolution[1],
            rs.format.bgr8,
            self._fps,
        )
        self._pipeline.start(self._config)

    def prepare_capture(self) -> None:
        if not self.base_path:
            raise ValueError("Base path not set")

        self._colorwriter = cv2.VideoWriter(
            str(self.base_path / self.COLOR_OUTPUT_FILENAME),
            cv2.VideoWriter_fourcc(*"XVID"),
            self._fps,
            self._resolution if not self._rotate else self._resolution[::-1],
            1,
        )

        self._capture_thread = threading.Thread(target=self._capture)

    def _capture(self) -> None:
        if not self._colorwriter:
            raise ValueError("Color writer not initialized")

        # https://dev.intelrealsense.com/docs/rs-latency-tool
        # Mine is 90ms, set to 3 (90ms / 30 fps)
        LATENCY_SKIP = 3
        current_frame = 0
        while current_frame != self._capture_frames + LATENCY_SKIP:
            frames = self._pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()
            if not color_frame:
                continue

            current_frame += 1

            # Skip latency packet
            if current_frame - 1 < LATENCY_SKIP:
                continue

            # Write to file
            color_image = np.asanyarray(color_frame.get_data())
            if self._rotate:
                color_image = cv2.rotate(color_image, cv2.ROTATE_90_CLOCKWISE)
            color_image = stamp_framenum(color_image, current_frame - LATENCY_SKIP)
            self._colorwriter.write(color_image)

    def start_capture(self) -> None:
        if not self._colorwriter:
            raise ValueError("Color writer not initialized")
        if not self._capture_thread:
            raise ValueError("Capture thread not initialized")
        self._capture_thread.start()

    def stop_capture(self) -> None:
        if not self._colorwriter:
            raise ValueError("Color writer not initialized")
        if not self._capture_thread:
            raise ValueError("Capture thread not initialized")

        self._capture_thread.join()
        self._colorwriter.release()
        self._pipeline.stop()

    def dump_config(self) -> None:
        pass