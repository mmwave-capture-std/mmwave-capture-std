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

import struct

import pytest

import mmwavecapture.dca1000 as dca1000


@pytest.fixture
def dca():
    return dca1000.DCA1000()


def test_dca_config(dca):
    new_dca_ip = "192.168.33.181"
    assert dca.config.dca_ip == "192.168.33.180"
    dca.config.dca_ip = new_dca_ip
    assert dca.config.dca_ip == new_dca_ip

    new_dca_config_port = 4099
    assert dca.config.dca_config_port == 4096
    dca.config.dca_config_port = new_dca_config_port
    assert dca.config.dca_config_port == new_dca_config_port

    new_packet_delay_us = 25
    assert dca.config.packet_delay_us == 5
    dca.config.packet_delay_us = new_packet_delay_us
    assert dca.config.packet_delay_us == new_packet_delay_us


def test_cmd_reset_fpga(dca):
    assert dca.reset_fpga() == True


def test_cmd_reset_radar(dca):
    assert dca.reset_radar() == True


def test_cmd_start_record(dca):
    assert dca.start_record() == True


def test_cmd_stop_record(dca):
    assert dca.stop_record() == True


def test_cmd_config_packet_delay(dca):
    assert dca.config_packet_delay() == True


def test_cmd_config_fpga(dca):
    assert dca.config_fpga() == True


def test_cmd_config_eeprom(dca):
    assert dca.config_eeprom() == True


def test_cmd_system_connection(dca):
    assert dca.system_connection() == True


def test_cmd_system_error_status(dca):
    assert dca.system_error_status() == 0


def test_cmd_read_fpga_version(dca):
    assert dca.read_fpga_version() == (2, 8, False)


@pytest.mark.manual
def test_start_dca_recording(dca):
    assert dca.system_connection() == True
    assert dca.reset_fpga() == True
    assert dca.config_fpga() == True
    assert dca.config_packet_delay() == True
    assert dca.start_record() == True


@pytest.mark.manual
def test_read_data(dca):
    for i in range(10):
        data = dca.read()
        seq_num = struct.unpack("<I", data[0:4])[0]
        dlen = struct.unpack("<Q", data[4:10] + b"\x00\x00")[0]
        print(seq_num, dlen)
    assert data
