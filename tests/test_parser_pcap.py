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

import pathlib

import pytest


from mmwavecapture.parser.pcap import PcapCparser
from mmwavecapture.parser.pcap import parser


@pytest.fixture
def cmd_pcap_filename():
    return pathlib.Path("tests/pcaps/test_cmd.pcap")


@pytest.fixture
def one_frame_pcap_filename():
    return pathlib.Path("tests/pcaps/test_one_frame.pcap")


@pytest.fixture
def large_pcap():
    return pathlib.Path("wireshark/test_600_frames.pcap")


def test_pcap_iter_wrapper(cmd_pcap_filename):
    for p in parser._PcapIterWrapper(cmd_pcap_filename):
        assert p.udp.destination_port == 4096


def test_cmd_dissec(cmd_pcap_filename):
    for p in parser._PcapIterWrapper(cmd_pcap_filename):
        assert p.udp.destination_port == 4096

        config = mmwavecapture.pcap.layer7.Config(p)
        assert config.header == 0xA55A
        assert config.footer == 0xEEAA
        assert config.cmd >= 0
        assert config.status >= 0


def test_raw_dissec(one_frame_pcap_filename):
    current_total_bytes = 0
    next_expected_seq_id = 1
    for p in parser._PcapIterWrapper(one_frame_pcap_filename):
        if p.udp.destination_port == 4098:
            raw = mmwavecapture.pcap.layer7.Raw(p)
            assert raw.seq_id == next_expected_seq_id
            assert raw.byte_count == current_total_bytes
            assert len(raw.data)

            next_expected_seq_id += 1
            current_total_bytes += len(raw.data)


def test_get_raw_bytes_from_pcap(one_frame_pcap_filename):
    raw_bytes = parser.get_raw_bytes_from_pcap(one_frame_pcap_filename, data_port=4098)
    assert len(raw_bytes) == 16384


def test_cparser_get_complex(one_frame_pcap_filename):
    data_ports = [4098]
    pcap = PcapCparser(
        one_frame_pcap_filename,
        data_ports=data_ports,
        lsb_quadrature=True,
        preprocessing=True,
    )

    for port in data_ports:
        assert pcap.validate_dca_data(port) == True

        sig = pcap.get_complex(port)
        assert sig.shape == (4096,)
        assert sig[4065] == (223 + 120j)
        assert sig[3293] == (-90 - 615j)
        assert sig[415] == (-88 + 193j)
        assert sig[1255] == (366 - 21j)
        assert sig[671] == (-55 + 205j)
        assert sig[1736] == (-127 - 238j)
        assert sig[3474] == (268 - 48j)
        assert sig[2394] == (745 - 301j)
        assert sig[1262] == (582 + 30j)


@pytest.mark.manual
def test_cparser_large_file_get_complex(large_pcap):
    data_ports = [4098]
    pcap = PcapCparser(
        large_pcap,
        data_ports=data_ports,
        lsb_quadrature=True,
        preprocessing=True,
    )

    for port in data_ports:
        assert pcap.validate_dca_data(port) == True
        assert pcap.get_complex(port).shape == (117964800,)
