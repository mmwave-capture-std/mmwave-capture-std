import pytest

import pathlib

import mmwavecapture.radar


@pytest.fixture
def radar_config():
    return pathlib.Path("tests/configs/xwr18xx_profile_2023_01_01T00_00_00_000.cfg")


def test_radar_core_config(radar_config):
    rcc = mmwavecapture.radar.RadarCoreConfig(filename=radar_config)

    assert rcc.frames == 0
    assert rcc.frame_period == 100.0
    assert rcc.chirps == 16
    assert rcc.virtual_antennas == 8
    assert rcc.tx == 2
    assert rcc.rx == 4
    assert rcc.samples == 256
    assert rcc.frame_iq_size == 16 * 2 * 4 * 256
    assert rcc.antenna_shape == (-1, 16, 2, 4, 256)
    assert rcc.virtual_shape == (-1, 16, 8, 256)
