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

import disspcap


class Raw:
    def __init__(self, packet: disspcap.Packet):
        buf = packet.udp.payload

        self.ts = packet.ts
        self.seq_id, self.byte_count = struct.unpack("<IQ", buf[:10] + b"\x00\x00")
        self.data = buf[10:]

    def __lt__(self, other):
        return self.seq_id < other.seq_id

    def __le__(self, other):
        return self.seq_id <= other.seq_id

    def __eq__(self, other):
        return self.seq_id == other.seq_id

    def __ne__(self, other):
        return self.seq_id != other.seq_id

    def __gt__(self, other):
        return self.seq_id > other.seq_id

    def __ge__(self, other):
        return self.seq_id >= other.seq_id


class Config:
    def __init__(self, packet: disspcap.Packet):
        buf = packet.udp.payload

        self.ts = packet.ts
        self.header, self.cmd = struct.unpack("<HH", buf[:4])
        self.status = struct.unpack(">H", buf[4:6])[0]
        self.footer = struct.unpack("<H", buf[-2:])[0]

    def __lt__(self, other):
        return self.ts < other.ts

    def __le__(self, other):
        return self.ts <= other.ts

    def __eq__(self, other):
        return self.ts == other.ts

    def __ne__(self, other):
        return self.ts != other.ts

    def __gt__(self, other):
        return self.ts > other.ts

    def __ge__(self, other):
        return self.ts >= other.ts
