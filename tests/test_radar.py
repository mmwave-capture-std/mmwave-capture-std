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

import pytest

import time
import pathlib

import mmwavecapture.radar


@pytest.fixture
def radar_config():
    return pathlib.Path("tests/configs/xwr18xx_profile_2023_01_01T00_00_00_000.cfg")


@pytest.fixture
def radar_uninit(radar_config):
    return mmwavecapture.radar.Radar(
        config_port="/dev/ttyACM0",
        config_baudrate=115200,
        data_port="/dev/ttyACM1",
        data_baudrate=921600,
        config_filename=radar_config,
        timeout=1,
        initialize_connection_and_radar=False,
        capture_frames=10,
    )


@pytest.fixture
def radar(radar_config):
    return mmwavecapture.radar.Radar(
        config_port="/dev/ttyACM0",
        config_baudrate=115200,
        data_port="/dev/ttyACM1",
        data_baudrate=921600,
        config_filename=radar_config,
        timeout=1,
        initialize_connection_and_radar=True,
        capture_frames=10,
    )


def test_radar_setter(rada_uninit):
    new_capture_frames = 20
    assert rada_uninit.capture_frames == 10
    rada_uninit.capture_frames = new_capture_frames
    assert rada_uninit.capture_frames == new_capture_frames


def test_radar_uninit(radar_uninit):
    assert radar_uninit._initialized == False
    assert radar_uninit._config_serial.is_open == False
    assert radar_uninit._data_serial.is_open == False

    with pytest.raises(Exception):
        radar_uninit.config()


def test_radar_uninit_then_init_and_config(radar_uninit):
    radar_uninit.initialize()
    radar_uninit.config()

    assert radar_uninit._initialized == True
    assert radar_uninit._config_serial.is_open == True
    assert radar_uninit._data_serial.is_open == True


def test_radar_init_then_config(radar):
    radar.config()

    assert radar._initialized == True
    assert radar._config_serial.is_open == True
    assert radar._data_serial.is_open == True

    radar_status, data_baudrate = radar.get_radar_status()
    assert radar_status != mmwavecapture.radar.RadarStatus.STARTED
    assert data_baudrate == radar._data_baudrate


def test_radar_init_config_and_start(radar):
    radar.config()
    assert radar._initialized == True
    assert radar._config_serial.is_open == True
    assert radar._data_serial.is_open == True

    radar.start_sensor()
    radar_status, data_baudrate = radar.get_radar_status()
    assert radar_status == mmwavecapture.radar.RadarStatus.STARTED

    time.sleep(2)  # 2 seconds should be enough for 10 frames for 10 Hz (that is 1 sec)
    radar.stop_sensor()


def test_radar_init_failed_command(radar):
    with pytest.raises(Exception):
        radar._send_command_and_check_output("Embedded Intellgence Lab @ UNC-CH")
