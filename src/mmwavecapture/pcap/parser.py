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
from collections import defaultdict
from typing import Callable, Dict, Optional, Union

import disspcap
from mmwavecapture.pcap.layer7 import Raw, Config


class _PcapIterWrapper:
    """Wrapper around disspcap.Pcap to make it iterable.

    This does not guarantee that the packets are in order,
    and it returns the `disspcap.Packet` object.
    """

    def __init__(self, filename: pathlib.Path) -> None:
        self.filename = str(filename)
        self.pcap = disspcap.Pcap(self.filename)

    def __iter__(self) -> _PcapIterWrapper:
        return self

    def __next__(self) -> disspcap.Packet:
        p = self.pcap.next_packet()
        if not p:
            raise StopIteration
        return p


class _PcapOrderedWrapper:
    def __init__(
        self,
        filename: pathlib.Path,
        config_ports: list[int] = [4096],
        data_ports: list[int] = [4098],
    ) -> None:
        self.filename = filename
        self.pcap = _PcapIterWrapper(self.filename)
        self.config_ports = config_ports
        self.data_ports = data_ports

        # Initialize all the packest, it takes time
        self.packets: defaultdict[int, list[Union[Raw, Config]]] = defaultdict(list)
        for p in self.pcap:
            if not p.udp:
                continue
            if p.udp.destination_port in self.data_ports:
                self.packets[p.udp.destination_port].append(Raw(p))
            elif p.udp.destination_port in self.config_ports:
                self.packets[p.udp.destination_port].append(Config(p))

        # Sort the packets
        for port in self.packets:
            self.packets[port].sort()


def get_raw_bytes_from_pcap(
    filename: pathlib.Path,
    data_port: int = 4098,
):
    """Get raw bytes from a pcap file by a specific data port.

    This will return the raw bytes from the data port.

    Note: This is not guaranteed to be in order.
    """
    pcap = _PcapIterWrapper(filename)

    raw_data = []
    for p in pcap:
        if not p.udp:
            continue
        if p.udp.destination_port != data_port:
            continue
        raw_data.append(Raw(p).data)

    return b"".join(raw_data)
