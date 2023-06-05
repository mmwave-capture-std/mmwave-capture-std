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

import abc
import importlib
import pathlib
import sys
from typing import Optional, Dict, Any

import toml
from loguru import logger


class CaptureHardware(abc.ABC):
    """CaptureHardware is the abstract class for all capture hardware.


    For each capture hardware, there are 5 stages of capture process:

    1. Initialize capture hardware

        This stage should initialize and config the capture hardware,
        and make sure the capture hardware is ready to capture data.

        .. note:: Do not create any output files in this stage.

    2. Prepare capture environment and output files

        This stage should setup the capture environment and create
        output files for the capture hardware. You should also setup
        thread/processes for capturing data at this stage, but not start them.

        .. warning:: The output files should be created under `base_path`

        If you are using `Capture` class, the hardware `base_path` will
        be setup after calling `Capture.add_capture_hardware()`.
        If you are using `CaptureManager` class, the hardware `base_path`
        will be setup during `CaptureManager.capture()`.
        It not using any of the above classes, you should setup the
        `base_path` by yourself before calling `CaptureHardware.prepare_capture()`.

    3. Start capture

        This stage should start the capture process/thread.

    4. Stop capture

        This stage should stop the capture process/thread and close
        the output files.

    5. Dump configuration

        This stage should dump the configuration of the capture hardware
        to `base_path/<config_name>` for future reference.
    """

    _hw_name: str = ""
    _base_path: Optional[pathlib.Path] = None

    @property
    def hw_name(self) -> str:
        return self._hw_name

    @hw_name.setter
    def hw_name(self, hw_name: str) -> None:
        self._hw_name = hw_name

    @property
    def base_path(self) -> Optional[pathlib.Path]:
        """The base path for the capture hardware

        The base path will be set by `Capture` class or `CaptureManager` class.
        Or by yourself if you are not using any of the above classes.

        If set it by `CaptureManager`, the base path should be
        `<dataset_path>/<capture_path>/<hw_name>/`.

        :setter: Set the base path for the capture hardware
        :getter: Get the base path for the capture hardware
        """
        return self._base_path

    @base_path.setter
    def base_path(self, base_path: pathlib.Path) -> None:
        if not base_path.exists():
            raise ValueError(f"Base path `{base_path}/` does not exist")
        if not base_path.is_dir():
            raise ValueError(f"Base path `{base_path}/` is not a directory")

        self._base_path = base_path

    @abc.abstractmethod
    def init_capture_hw(self) -> None:
        """Initialize the capture hardware"""
        raise NotImplementedError

    @abc.abstractmethod
    def prepare_capture(self) -> None:
        """Prepare the capture environment and output files

        Output filename should be `self.base_path`/<sensor>.*
        """
        raise NotImplementedError

    @abc.abstractmethod
    def start_capture(self) -> None:
        """Start the sensor to capture data"""
        raise NotImplementedError

    @abc.abstractmethod
    def stop_capture(self) -> None:
        """Stop the sensor and capture output files"""
        raise NotImplementedError

    @abc.abstractmethod
    def dump_config(self) -> None:
        """Dump the configuration of the capture hardware to `base_path`"""
        raise NotImplementedError


class Capture:
    def __init__(self, base_path: pathlib.Path):
        self._cap_hw: list[CaptureHardware] = []
        self._base_path: pathlib.Path = base_path

        # Create directory for `Capture`
        self._base_path.mkdir(exist_ok=True)
        logger.debug(f"Capture directory created at `{self._base_path}/`")

    def add_capture_hardware(self, hw: CaptureHardware) -> None:
        # Creat directory for capture hardware
        hardware_base_path = self._base_path / hw.hw_name
        hardware_base_path.mkdir(exist_ok=True)
        logger.debug(f"Capture hardware directory created at `{hardware_base_path}/`")

        hw.base_path = hardware_base_path

        self._cap_hw.append(hw)

    @logger.catch(reraise=True)
    def capture(self) -> None:
        logger.info("Preparing capture hardware")
        for hw in self._cap_hw:
            hw.prepare_capture()

        logger.info("Starting capture hardware")
        for hw in self._cap_hw:
            hw.start_capture()
        logger.success("Capture started")

        for hw in self._cap_hw:
            hw.stop_capture()
        logger.info("Capture finished")

        logger.info("Dumping capture hardware configurations")
        for hw in self._cap_hw:
            hw.dump_config()


class CaptureManager:
    """Capture Manager manages HDF5-like dataset directory structure
    and handle capture hardware initialization and capture process.

    The layout of dataset directory is as follows::

        dataset_path/           # Create when initalizing `CaptureManager`
        ├── capture_00000/      # Create when calling `CaptureManager.capture()`
        │   ├── config.toml     # Capture configuration
        │   ├── iwr1843_vert/   # Capture hardware name
        │   │   ├── dca.pcap    # DCA1000EVM capture pcap
        │   │   ├── radar.cfg   # Radar configuration
        │   │   ├── dca.json    # DCA1000EVM configuration
        │   ├── realsense/         # Another capture hardware name
        │   │   ├── color.avi      # Color video
        ├── capture_00001/
        │   ├── config.toml
        │   ├── iwr1843_vert/
        │   │   ├── dca.pcap
        ...

    The calling sequence of `CaptureManager` is as follows:

    1. Initialize `CaptureManager` with `config.toml` path
    2. Initialize capture hardware with `CaptureManager.init_hw()`
    3. Start capture by calling `CaptureManager.capture()`
    """

    CAPTURE_LOG_FILENAME = "capture.log"
    CAPTURE_MANAGER_CONFIG_OUTPUT_FILENAME = "config.toml"
    CAPTURE_DIR_PREFIX = "capture_"
    CAPTURE_DIR_FORMAT = CAPTURE_DIR_PREFIX + "{:05d}"  # XXX: fixed to 5 digits?

    def __init__(self, config_filename: pathlib.Path):
        self._hw: list[CaptureHardware] = []
        self._config_filename: pathlib.Path = config_filename
        self._config: Dict[str, Any] = {}

        # Load config and create dataset directory
        self._load_config(self._config_filename)
        self._dataset_dir = pathlib.Path(self._config["dataset_dir"])
        self._dataset_dir.mkdir(exist_ok=True)

        # Create capture directory
        self._capture_dir = self._get_next_capture_dir()
        self._capture_dir.mkdir(exist_ok=True)

        # Init logging
        logger.remove()

        # Add stderr logger
        if self._config["logging"]["stderr"]["enable"]:
            logger.add(sys.stderr, level=self._config["logging"]["stderr"]["level"])

        # Add logfile logger
        if self._config["logging"]["logfile"]["enable"]:
            logger.add(
                self._capture_dir / self.CAPTURE_LOG_FILENAME,
                level=self._config["logging"]["logfile"]["level"],
                serialize=self._config["logging"]["logfile"]["serialize"],
            )

        # Unfotunately, we will need to log them here
        logger.debug(f"Dataset directory created at `{self._dataset_dir}/`")
        logger.debug(f"Capture directory created at `{self._capture_dir}/`")

    def _load_config(self, path: pathlib.Path) -> None:
        with open(path) as f:
            self._config = toml.load(f)

        # Validate configuration
        if "dataset_dir" not in self._config:
            raise RuntimeError("`dataset_dir` is not specified in config")

    def _get_next_capture_dir(self) -> pathlib.Path:
        dir_names = [
            i.name.split(self.CAPTURE_DIR_PREFIX)[-1]
            for i in self._dataset_dir.glob(f"{self.CAPTURE_DIR_PREFIX}*")
        ]

        next_id = 0
        if dir_names:
            next_id = max(map(int, dir_names)) + 1

        logger.info(f"Capture ID: {next_id}")
        return self._dataset_dir / self.CAPTURE_DIR_FORMAT.format(next_id)

    def init_hw(self) -> None:
        for hw in self._config["hardware"]:
            logger.info(
                f"Initializing capture hardware `{hw}` from "
                f"`{self._config['hardware'][hw]['hw_def_class']}`"
            )
            # Get capture hardware class by `hw_def_class`
            module_name, class_name = self._config["hardware"][hw][
                "hw_def_class"
            ].rsplit(".", 1)
            module = importlib.import_module(module_name)
            hw_class = getattr(module, class_name)

            # Create capture hardware instance
            hw_config = self._config["hardware"][hw]
            hw_obj = hw_class(hw_name=hw, **hw_config)
            self._hw.append(hw_obj)
            logger.success(f"Capture hardware `{hw}` initialized")

        logger.success(
            f"Total of {len(self._config['hardware'])} capture hardware initialized"
        )

    def capture(self) -> None:
        if not self._hw:
            raise RuntimeError("Capture hardware is not initialized")

        # Initialize capture hardware and setup capture
        capture = Capture(self._capture_dir)
        for hw in self._hw:
            logger.info(f"Adding capture hardware `{hw.hw_name}`")
            capture.add_capture_hardware(hw)

        # Start capture
        capture.capture()

        # After finishing capture, dump capture config into capture dir
        with open(
            capture._base_path / self.CAPTURE_MANAGER_CONFIG_OUTPUT_FILENAME, "w"
        ) as f:
            toml.dump(self._config, f)

        logger.success(f"Capture finished, all files output to `{capture._base_path}/`")
