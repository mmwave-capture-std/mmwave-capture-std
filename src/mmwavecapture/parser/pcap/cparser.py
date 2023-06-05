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

import pathlib
from typing import Dict

import numpy as np

import disspcap


class PcapCparser:
    """DCA1000EVM pcap c++ parser
    Assumption for DCA1000EVM: LVDS 2 Channels
    """

    def __init__(
        self,
        pcap_file: pathlib.Path,
        data_ports: list[int] = [4098],
        lsb_quadrature: bool = True,
        preprocessing: bool = True,
    ):
        self.pcap_file = pcap_file
        self.pcap = disspcap.Pcap(str(pcap_file))
        self.data_ports = data_ports
        self.lsb_quadrature = lsb_quadrature
        self.dca_data: Dict[int, disspcap.DcaData] = {}

        if preprocessing:
            self.preprocessing()

    def preprocessing(self):
        self.pcap.dca_fetch_packets(self.data_ports)
        for port in self.data_ports:
            dd = self.pcap.get_dca_data(port)
            dd.convert_complex(True)
            self.dca_data[port] = dd

    def validate_dca_data(self, port: int):
        dd = self.dca_data[port]
        return not dd.is_out_of_order and dd.dca_report_tx_bytes == dd.received_rx_bytes

    def get_complex(self, port: int):
        dd = self.dca_data[port]
        return np.array(dd, copy=False)
