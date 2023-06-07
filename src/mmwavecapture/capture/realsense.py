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

import json
import threading
import pathlib
from typing import Optional, Tuple, Any, Dict, NamedTuple, BinaryIO

import cv2
import pyrealsense2 as rs
import numpy as np
import zstandard as zstd
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


class CameraIntrinsics:
    """Camera intrinsics

    Ref: https://intelrealsense.github.io/librealsense/python_docs/_generated/pyrealsense2.intrinsics.html
    """

    def __init__(self, intrinsics: rs.pyrealsense2.intrinsics) -> None:
        self.width: int = intrinsics.width
        self.height: int = intrinsics.height

        #: Focal length of the image plane, as a multiple of pixel width
        self.fx: float = intrinsics.fx

        #: Focal length of the image plane, as a multiple of pixel height
        self.fy: float = intrinsics.fy

        #: Horizontal coordinate of the principal point of the image, as a pixel offset from the left edge
        self.ppx: float = intrinsics.ppx

        #: Vertical coordinate of the principal point of the image, as a pixel offset from the top edge
        self.ppy: float = intrinsics.ppy

        #: Distortion model of the image
        self.model: str = intrinsics.model.name

        #: Distortion coefficients
        self.coeffs: list[float] = intrinsics.coeffs[:]


class ColorMetadata(NamedTuple):
    frame_num: int
    timestamp: float
    stamp_frame_num: int
    time_of_arrival: float
    backend_timestamp: float
    frame_timestamp: float
    actual_fps: int


class ColorConfig:
    def __init__(self, intrinsics: CameraIntrinsics, fps: int) -> None:
        #: Camera intrinsics
        self.intrinsics: CameraIntrinsics = intrinsics

        #: Frame per second
        self.fps: int = fps


class DepthMetadata(NamedTuple):
    frame_num: int
    timestamp: float
    stamp_frame_num: int
    time_of_arrival: float
    backend_timestamp: float
    frame_timestamp: float
    actual_fps: int


class DepthConfig:
    def __init__(
        self, intrinsics: CameraIntrinsics, depth_units: float, fps: int
    ) -> None:
        #: Camera intrinsics
        self.intrinsics: CameraIntrinsics = intrinsics

        #: Depth units
        self.depth_units: float = depth_units

        #: Frame per second
        self.fps: int = fps


class Realsense(CaptureHardware):
    COLOR_OUTPUT_FILENAME = "color.avi"
    COLOR_CONFIG_FILENAME = "color_config.json"
    COLOR_METADATA_FILENAME = "color_metadata.json"
    DEPTH_OUTPUT_FILENAME = "depth.zst"
    DEPTH_CONFIG_FILENAME = "depth_config.json"
    DEPTH_METADATA_FILENAME = "depth_metadata.json"

    def __init__(
        self,
        hw_name: str,
        fps: int = 30,
        resolution: Tuple[int, int] = (1920, 1080),
        depth_resolution: Tuple[int, int] = (1280, 720),
        capture_frames: int = 150,
        rotate: bool = False,
        latency_skip_frames: int = 3,
        **kwargs: Dict[str, Any],
    ) -> None:
        self.hw_name = hw_name
        self._fps = fps
        self._resolution = resolution
        self._depth_resolution = depth_resolution
        self._capture_frames = capture_frames
        self._rotate = rotate
        self._latency_skip_frames = latency_skip_frames

        # Capture thread
        self._capture_thread: Optional[threading.Thread] = None
        self._capture_start_event = threading.Event()

        # Realsense HW
        self._pipeline = rs.pipeline()
        self._config = rs.config()

        # Output video file
        self._colorwriter: Optional[cv2.VideoWriter] = None

        # Output depth file
        self._depthcctx = zstd.ZstdCompressor(level=3)
        self._depthfh: Optional[BinaryIO] = None
        self._depthwriter: Optional[zstd.ZstdCompressionWriter] = None

        # Metadata
        self._color_config: Optional[ColorConfig] = None
        self._depth_config: Optional[DepthConfig] = None
        self._color_metadata: list[dict] = []
        self._depth_metadata: list[dict] = []

        self.init_capture_hw()

    def init_capture_hw(self) -> None:
        self._config.enable_stream(
            rs.stream.color,
            self._resolution[0],
            self._resolution[1],
            rs.format.bgr8,
            self._fps,
        )
        self._config.enable_stream(
            rs.stream.depth,
            self._depth_resolution[0],
            self._depth_resolution[1],
            rs.format.z16,
            self._fps,
        )
        profile = self._pipeline.start(self._config)

        # Setup camera configs
        depth_sensor = profile.get_device().first_depth_sensor()
        depth_profile = rs.video_stream_profile(profile.get_stream(rs.stream.depth))
        depth_intrinsics = depth_profile.get_intrinsics()
        self._depth_config = DepthConfig(
            intrinsics=CameraIntrinsics(depth_intrinsics),
            depth_units=float(depth_sensor.get_option(rs.option.depth_units)),
            fps=self._fps,
        )

        color_sensor = profile.get_device().first_color_sensor()
        color_profile = rs.video_stream_profile(profile.get_stream(rs.stream.color))
        color_intrinsics = color_profile.get_intrinsics()
        self._color_config = ColorConfig(
            intrinsics=CameraIntrinsics(color_intrinsics),
            fps=self._fps,
        )

        # There is a huge latency when starting the camera
        # to wait the frames, so start it earlier.
        # This add additional overhead when init the hardware,
        # but it's fine.
        #
        #  Line #      Hits         Time  Per Hit   % Time  Line Contents
        #  ==============================================================
        #      17         1      21155.3  21155.3      1.3      pp.start(config)
        #      19         1     493007.5 493007.5     30.5      frames = pp.wait_for_frames()
        #                       ^^^^^^^^----- This is a huge latency spike
        #
        #      25         1      30578.7  30578.7      1.9      frames = pp.wait_for_frames()
        #
        self._pipeline.wait_for_frames(10000)

    def prepare_capture(self) -> None:
        if not self.base_path:
            raise ValueError("Base path not set")

        self._colorwriter = cv2.VideoWriter(
            str(self.base_path / self.COLOR_OUTPUT_FILENAME),
            cv2.VideoWriter_fourcc(*"XVID"),
            self._fps,
            self._resolution if not self._rotate else self._resolution[::-1],
            1,
        )  # type: ignore

        self._depthfh = open(self.base_path / self.DEPTH_OUTPUT_FILENAME, "wb")
        self._depthwriter = self._depthcctx.stream_writer(self._depthfh)

        self._capture_thread = threading.Thread(target=self._capture)

        # We start the camera and queue the frame, because of the
        # camera latency
        #
        # Ref: https://dev.intelrealsense.com/docs/rs-latency-tool
        # Mine is 90ms, set to 3 (90ms / 30 fps)
        self._capture_thread.start()

    def _capture(self) -> None:
        if not self._colorwriter:
            raise ValueError("Color writer not initialized")
        if not self._depthwriter:
            raise ValueError("Depth writer not initialized")

        current_frame = 0
        while current_frame != self._capture_frames + self._latency_skip_frames:
            frames = self._pipeline.wait_for_frames()
            color_frame = frames.get_color_frame()
            depth_frame = frames.get_depth_frame()

            if not color_frame or not depth_frame:
                continue

            # Convert color frame to color image
            color_image = np.asanyarray(color_frame.get_data())

            # Convert depth frame to depth image
            depth_image = np.asanyarray(depth_frame.get_data())

            # Wait for the capture to start
            if not self._capture_start_event.is_set():
                continue

            # Increment frame number
            current_frame += 1

            # Skip latency frames
            if current_frame - 1 < self._latency_skip_frames:
                continue

            # Write to file
            if self._rotate:
                color_image = cv2.rotate(color_image, cv2.ROTATE_90_CLOCKWISE)
                depth_image = cv2.rotate(depth_image, cv2.ROTATE_90_CLOCKWISE)

            stamp_frame_num = current_frame - self._latency_skip_frames - 1
            color_image = stamp_framenum(color_image, stamp_frame_num)
            self._colorwriter.write(color_image)
            self._depthwriter.write(depth_image.tobytes())

            # Record metadata
            color_meta = ColorMetadata(
                frame_num=frames.frame_number,
                timestamp=frames.timestamp,
                stamp_frame_num=stamp_frame_num,
                time_of_arrival=color_frame.get_frame_metadata(
                    rs.frame_metadata_value.time_of_arrival
                ),
                backend_timestamp=color_frame.get_frame_metadata(
                    rs.frame_metadata_value.backend_timestamp
                ),
                frame_timestamp=color_frame.get_frame_metadata(
                    rs.frame_metadata_value.frame_timestamp
                ),
                actual_fps=color_frame.get_frame_metadata(
                    rs.frame_metadata_value.actual_fps
                ),
            )
            depth_meta = DepthMetadata(
                frame_num=frames.frame_number,
                timestamp=frames.timestamp,
                stamp_frame_num=stamp_frame_num,
                time_of_arrival=color_frame.get_frame_metadata(
                    rs.frame_metadata_value.time_of_arrival
                ),
                backend_timestamp=color_frame.get_frame_metadata(
                    rs.frame_metadata_value.backend_timestamp
                ),
                frame_timestamp=color_frame.get_frame_metadata(
                    rs.frame_metadata_value.frame_timestamp
                ),
                actual_fps=color_frame.get_frame_metadata(
                    rs.frame_metadata_value.actual_fps
                ),
            )

            # XXX: Sad not to preserve `ColorMetadata` type,
            #      but I don't want to spend time on this
            self._color_metadata.append(color_meta._asdict())
            self._depth_metadata.append(depth_meta._asdict())

    def start_capture(self) -> None:
        if not self._colorwriter:
            raise ValueError("Color writer not initialized")
        if not self._depthwriter:
            raise ValueError("Depth writer not initialized")
        if not self._capture_thread:
            raise ValueError("Capture thread not initialized")

        self._capture_start_event.set()

    def stop_capture(self) -> None:
        if self._capture_thread:
            self._capture_thread.join()
        if self._colorwriter:
            self._colorwriter.release()
        if self._depthwriter:
            self._depthwriter.close()
        if self._depthfh:
            self._depthfh.close()
        self._pipeline.stop()

    def dump_config(self) -> None:
        if not self.base_path:
            raise ValueError("Base path not set")
        with open(self.base_path / self.COLOR_METADATA_FILENAME, "w") as f:
            json.dump(self._color_metadata, f, indent=4)
        with open(self.base_path / self.DEPTH_METADATA_FILENAME, "w") as f:
            json.dump(self._depth_metadata, f, indent=4)
        with open(self.base_path / self.COLOR_CONFIG_FILENAME, "w") as f:
            json.dump(self._color_config, f, indent=4, default=vars)
        with open(self.base_path / self.DEPTH_CONFIG_FILENAME, "w") as f:
            json.dump(self._depth_config, f, indent=4, default=vars)
