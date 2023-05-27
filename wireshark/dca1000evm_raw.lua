--- Wireshark TI MMWave DCA1000EVM packet protocol dissector
---
--- Copyright (c) 2023 Louie Lu <louielu@cs.unc.edu>
--- All rights reserved.
---
--- Redistribution and use in source and binary forms, with or without
--- modification, are permitted (subject to the limitations in the disclaimer
--- below) provided that the following conditions are met:
---
---      * Redistributions of source code must retain the above copyright notice,
---      this list of conditions and the following disclaimer.
---
---      * Redistributions in binary form must reproduce the above copyright
---      notice, this list of conditions and the following disclaimer in the
---      documentation and/or other materials provided with the distribution.
---
---      * Neither the name of the copyright holder nor the names of its
---      contributors may be used to endorse or promote products derived from this
---      software without specific prior written permission.
---
--- NO EXPRESS OR IMPLIED LICENSES TO ANY PARTY'S PATENT RIGHTS ARE GRANTED BY
--- THIS LICENSE. THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND
--- CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
--- LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
--- PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
--- CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
--- EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
--- PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
--- BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
--- IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
--- ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
--- POSSIBILITY OF SUCH DAMAGE.
---
---
--- Description
---
---    This is a wireshark dissector for DCA1000EVM Raw data mode and Config protocol
---
--- How to use it
---
---    $ wireshark -X lua_script:dca1000evm_raw.lua <your-pcap-file>
---
---    P.S. If you want to capture DCA1000EVM packets, you can use `tcpdump`
---
---        $ tcpdump -i <your-eth-interface> "src 192.168.33.180" -w out.pcap
---
---        Change the filter IP address (192.168.33.180) to your own DCA1000EVM IP address
---
--- Parameters
---
---     Change the port number if you have modified
---
--- Author
---
---    Louie Lu <louielu@cs.unc.edu>
---
--- This program is part of the mmwave-capture-std kit
---

---
--- Parameters
---
local CONFIG_PORT = 4096
local RAW_DATA_PORT = 4098

---
--- RAW Mode
---
local p_ti_mmwave_raw = Proto("raw_dca", "TIMmwaveRaw")

local f_seq_id = ProtoField.uint32("ti_mmwave_raw.seq_id", "SeqId", base.DEC)
local f_bytes_count = ProtoField.uint64("ti_mmwave_raw.bytes_count", "BytesCount", base.DEC)
local f_data = ProtoField.bytes("ti_mmwave_raw.data", "Raw I/Q data")

p_ti_mmwave_raw.fields = { f_seq_id, f_bytes_count, f_data }

function p_ti_mmwave_raw.dissector(buf, pkt, tree)
	length = buf:len()
	if length == 0 then
		return
	end

	pkt.cols.protocol = p_ti_mmwave_raw.name
	local subtree = tree:add(p_ti_mmwave_raw, buf(), "TI DCA1000EVM Raw-frame Protocol Data")

	subtree:add_le(f_seq_id, buf(0, 4))
	subtree:add_le(f_bytes_count, buf(4, 6))
	local st_data = subtree:add(f_data, buf(10, -1))
    st_data:set_text(string.format("DCA Raw payload (%d bytes)", length - 10))

end

local udp_encap_table = DissectorTable.get("udp.port")
udp_encap_table:add(RAW_DATA_PORT, p_ti_mmwave_raw)

---
--- Config
---
local p_ti_mmwave_config = Proto("cfg_dca", "TIMmwaveCfg")

local cmd_code_enum = {
	[1] = "Reset FPGA",
	[2] = "Reset radar",
	[3] = "Config FPGA",
	[4] = "Config EEPROM",
	[5] = "Start record",
	[6] = "Stop record",
	[7] = "Start playback",
	[8] = "Stop playback",
	[9] = "System aliveness",
	[10] = "System status",
	[11] = "Config packet delay",
	[12] = "Config radar",
	[13] = "Init FPGA playback",
	[14] = "Read FPGA version",
}

local command_status_enum = {
	[0] = "Success",
	[1] = "Failure",
}

local system_status_enum = {
	[0x0] = "No Error",
	[0x1] = "No LVDS data",
	[0x2] = "No header",
	[0x4] = "EEPROM failure",
	[0x8] = "SD card detected",
	[0x10] = "SD card removed",
	[0x20] = "SD card full",
	[0x40] = "Mode config failure",
	[0x80] = "DDR full",
	[0x100] = "Rec completed",
	[0x200] = "LVDS buffer full",
	[0x400] = "Playback completed",
	[0x800] = "Playback out of seq",
}

local set_not_set_enum = {
	[0] = "Not set",
	[1] = "Set",
}

local f_header = ProtoField.uint16("ti_mmwave_cfg.header", "Header", base.HEX)
local f_cmd_code = ProtoField.uint16("ti_mmwave_cfg.cmd_code", "CmdCode", base.DEC, cmd_code_enum, 0xF)
local f_system_status =
	ProtoField.uint16("ti_mmwave_cfg.system_status", "SystemStatus", base.DEC, command_status_enum, 0x1)
local f_footer = ProtoField.uint16("ti_mmwave_cfg.footer", "Footer", base.HEX)

p_ti_mmwave_config.fields = { f_header, f_cmd_code, f_system_status, f_footer }

function p_ti_mmwave_config.dissector(buf, pkt, tree)
	length = buf:len()
	if length == 0 then
		return
	end

	pkt.cols.protocol = p_ti_mmwave_config.name
	local subtree = tree:add(p_ti_mmwave_config, buf(), "TI DCA1000EVM Config-frame Protocol Data")

	local cmd_code = buf(2, 2):le_uint()
	subtree:add_le(f_header, buf(0, 2))
	subtree:add_le(f_cmd_code, buf(2, 2), cmd_code)

	local sys_status = buf(4, 2):uint()
	local status_tree = subtree:add_le(f_system_status, buf(4, 2), sys_status)

	if cmd_code == 0xA then
		local flag1 = bit.band(sys_status, 0x1)
		local flag2 = bit.band(sys_status, 0x2)
		local flag3 = bit.band(sys_status, 0x4)
		local flag4 = bit.band(sys_status, 0x8)
		local flag5 = bit.band(sys_status, 0x10)
		local flag6 = bit.band(sys_status, 0x20)
		local flag7 = bit.band(sys_status, 0x40)
		local flag8 = bit.band(sys_status, 0x80)
		local flag9 = bit.band(sys_status, 0x100)
		local flag10 = bit.band(sys_status, 0x200)
		local flag11 = bit.band(sys_status, 0x400)
		local flag12 = bit.band(sys_status, 0x800)

		status_tree:set_text(
			string.format(
				".... %d%d%d%d %d%d%d%d %d%d%d%d = SystemStatus: 0x%X, %s",
				flag12,
				flag11,
				flag10,
				flag9,
				flag8,
				flag7,
				flag6,
				flag5,
				flag4,
				flag3,
				flag2,
				flag1,
				sys_status,
				system_status_enum[sys_status]
			)
		)
		status_tree:add(string.format(".... .... .... ...%d = No LVDS data: %s", flag1, set_not_set_enum[flag1]))
		status_tree:add(string.format(".... .... .... ..%d. = No header: %s", flag2, set_not_set_enum[flag2]))
		status_tree:add(string.format(".... .... .... .%d.. = EEPROM failure: %s", flag3, set_not_set_enum[flag3]))
		status_tree:add(string.format(".... .... .... %d... = SD card detected: %s", flag4, set_not_set_enum[flag4]))
		status_tree:add(string.format(".... .... ...%d .... = SD card removed: %s", flag5, set_not_set_enum[flag5]))
		status_tree:add(string.format(".... .... ..%d. .... = SD card full: %s", flag6, set_not_set_enum[flag6]))
		status_tree:add(string.format(".... .... .%d.. .... = Mode config failure: %s", flag7, set_not_set_enum[flag7]))
		status_tree:add(string.format(".... .... %d... .... = DDR full: %s", flag8, set_not_set_enum[flag8]))
		status_tree:add(string.format(".... ...%d .... .... = Rec completed: %s", flag9, set_not_set_enum[flag9]))
		status_tree:add(string.format(".... ..%d. .... .... = LVDS buffer full: %s", flag10, set_not_set_enum[flag10]))
		status_tree:add(
			string.format(".... .%d.. .... .... = Playback completed: %s", flag11, set_not_set_enum[flag11])
		)
		status_tree:add(
			string.format(".... %d... .... .... = Playback out of seq: %s", flag12, set_not_set_enum[flag12])
		)
	elseif cmd_code == 0xE then
		local fpga_version = buf(4, 2):le_uint()
		local major = bit.band(fpga_version, 0x7F)
		local minor = bit.band(bit.rshift(fpga_version, 7), 0x7F)
		local playback = bit.band(bit.rshift(fpga_version, 14), 0x1)
		status_tree:set_text(string.format("FPGA version: %d.%d (Playback: %d)", major, minor, playback))
	end

	subtree:add_le(f_footer, buf(6, 2))
end

udp_encap_table:add(CONFIG_PORT, p_ti_mmwave_config)
