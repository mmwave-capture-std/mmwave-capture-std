--- Wireshark TI MMWave radar interface control packet protocol dissector
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
---    This is a wireshark dissector for TI radar interface control
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
local CONFIG_PORT = 5001
local RAW_DATA_PORT = 5000

---
--- Config
---
local tcp_encap_table = DissectorTable.get("tcp.port")
local f_tcp_srcport    = Field.new("tcp.srcport")
local f_tcp_dstport    = Field.new("tcp.dstport")

local p_ti_mmwave_config = Proto("cfg_csr", "TIMmwaveCascadeCfg")
local p_ti_mmwave_tda_cmd_header = Proto("tda_cmd_header", "TIMmwaveCascadeTdaCmdHeader")

local packet_formation_enum = {
   [0xa5c8] = "TX Sync",
   [0x8c5a] = "RX Sync",
}

local cmd_code_enum = {
   [0x10] = "CAPTURE_CONFIG_CONNECT",
   [0x11] = "CAPTURE_CONFIG_DISCONNECT",
   [0x12] = "CAPTURE_CONFIG_PING",
   [0x13] = "CAPTURE_CONFIG_VERSION_GET",
   [0x14] = "CAPTURE_CONFIG_CONFIG_SET",
   [0x15] = "CAPTURE_CONFIG_CONFIG_GET",
   [0x16] = "CAPTURE_CONFIG_TRACE_START",
   [0x17] = "CAPTURE_CONFIG_TRACE_RETREIVE",
   [0x18] = "CAPTURE_CONFIG_CREATE_APPLICATION",
   [0x19] = "CAPTURE_CONFIG_START_LOGGING_STATS",
   [0x1A] = "CAPTURE_CONFIG_DEVICE_MAP",
   [0x20] = "SENSOR_CONFIG_DEVICE_RESET",
   [0x21] = "SENSOR_CONFIG_SET_SOP",
   [0x22] = "SENSOR_CONFIG_GET_SOP",
   [0x23] = "SENSOR_CONFIG_SPI_WRITE",
   [0x24] = "SENSOR_CONFIG_SPI_READ",
   [0x25] = "SENSOR_CONFIG_GPIO_CONFIG",
   [0x26] = "SENSOR_CONFIG_GPIO_SET",
   [0x27] = "SENSOR_CONFIG_GPIO_GET",
   [0x31] = "CAPTURE_DATA_START_RECORD",
   [0x32] = "CAPTURE_DATA_STOP_RECORD",
   [0x35] = "CAPTURE_DATA_FRAME_PERIODICITY",
   [0x36] = "CAPTURE_DATA_NUM_ALLOCATED_FILES",
   [0x37] = "CAPTURE_DATA_ENABLE_DATA_PACKAGING",
   [0x38] = "CAPTURE_DATA_SESSION_DIRECTORY",
   [0x39] = "CAPTURE_DATA_NUM_FRAMES",
   [0x81] = "CAPTURE_RESPONSE_ACK",
   [0x82] = "CAPTURE_RESPONSE_NACK",
   [0x83] = "CAPTURE_RESPONSE_VERSION_INFO",
   [0x84] = "CAPTURE_RESPONSE_CONFIG_INFO",
   [0x85] = "CAPTURE_RESPONSE_TRACE_DATA",
   [0x86] = "CAPTURE_RESPONSE_GPIO_DATA",
   [0x87] = "CAPTURE_RESPONSE_PLAYBACK_DATA",
   [0x88] = "CAPTURE_RESPONSE_HOST_IRQ",
   [0x89] = "SENSOR_RESPONSE_SPI_DATA",
   [0x8A] = "SENSOR_RESPONSE_SOP_INFO",
   [0x8D] = "CAPTURE_RESPONSE_NETWORK_ERROR",
}

local command_status_enum = {
	[0] = "Success",
	[1] = "Failure",
}

local ack_type_enum = {
	[0x01] = "ACK on process",
	[0x10] = "ACK on receive",
	[0x11] = "No ACK required",
}

local f_sync_byte = ProtoField.uint16("ti_mmwave_cfg.sync_byte", "Sync", base.HEX, packet_formation_enum)
local f_cmd_code = ProtoField.uint16("ti_mmwave_cfg.cmd_code", "CmdCode", base.HEX, cmd_code_enum)
local f_ack_code = ProtoField.uint16("ti_mmwave_cfg.ack_code", "AckCode", base.HEX)
local f_data_length = ProtoField.uint16("ti_mmwave_cfg.data_length", "DataLength", base.DEC)
local f_dev_selection = ProtoField.uint8("ti_mmwave_cfg.dev_selection", "DevSelection", base.HEX)
local f_ack_type = ProtoField.uint8("ti_mmwave_cfg.ack_type", "AckType", base.HEX, ack_type_enum)
local f_data = ProtoField.string("ti_mmwave_cfg.data", "Data")
local f_parm_length = ProtoField.uint32("ti_mmwave_cfg.parm_length", "ParmLength", base.DEC)


--- SPI
local spi_direction_enum = {
   [0x00] = "Invalid",
   [0x01] = "Communication between Host to BSS",
   [0x02] = "Communication between BSS to Host",
   [0x03] = "Communication between Host to DSS",
   [0x04] = "Communication between DSS to Host",
   [0x05] = "Communication between Host to Master",
   [0x06] = "Communication between Master to Host",
   [0x07] = "Communication between BSS to Master",
   [0x08] = "Communication between Master to BSS",
   [0x09] = "Communication between BSS to DSS",
   [0x0A] = "Communication between DSS to BSS",
   [0x0B] = "Communication between Master to DSS",
   [0x0C] = "Communication between DSS to Master",
   [0x0D] = "RESERVED",
   [0x0E] = "RESERVED",
   [0x0F] = "RESERVED",
}

local spi_msg_type_enum = {
   [0x00] = "COMMAND",
   [0x01] = "RESPONSE (ACK or ERROR)",
   [0x02] = "NACK",
   [0x03] = "ASYNC",
}

local spi_sync_enum = {
   [0x43211234] = "Master to Slave (New command)" ,
   [0x87655678] = "External Host to Device - CNYS (Host ready to receive msg from device)",
   [0xABCDDCBA] = "Slave to Master",
}

local spi_msg_id_enum = {
   [0x00] = "AWR_ERROR_MSG",
   [0x01] = "RESERVED",
   [0x02] = "RESERVED",
   [0x03] = "RESERVED",
   [0x04] = "AWR RF STATIC CONF SET MSG",
   [0x05] = "AWR RF STATIC CONF GET MSG",
   [0x06] = "AWR RF INIT MSG",
   [0x07] = "RESERVED",
   [0x08] = "AWR RF DYNAMIC CONF SET MSG",
   [0x09] = "AWR RF DYNAMIC CONF GET MSG",
   [0x0A] = "AWR RF FRAME TRIG MSG",
   [0x0B] = "RESERVED",
   [0x0C] = "AWR RF ADVANCED FEATURES CONF SET MSG",
   [0x0D] = "RESERVED",
   [0x0E] = "AWR RF MONITORING CONF SET MSG",
   [0x0F] = "RESERVED",
   [0x10] = "RESERVED",
   [0x11] = "AWR RF STATUS GET MSG",
   [0x12] = "RESERVED",
   [0x13] = "AWR RF MONITORING REPORT GET MSG",
   [0x14] = "RESERVED",
   [0x15] = "RESERVED",
   [0x16] = "AWR RF MISC CONF SET MSG",
   [0x17] = "AWR RF MISC CONF GET MSG",
   [0x18] = "RESERVED",
   [0x19] = "RESERVED",
   [0x80] = "AWR RF ASYNC EVENT MSG1",
   [0x81] = "AWR RF ASYNC EVENT MSG2",
   [0x200] = "AWR DEV RFPOWERUP MSG",
   [0x201] = "RESERVED",
   [0x202] = "AWR DEV CONF SET MSG",
   [0x203] = "AWR DEV CONF GET MSG",
   [0x204] = "AWR DEV FILE DOWNLOAD MSG",
   [0x205] = "RESERVED",
   [0x206] = "AWR DEV FRAME CONFIG APPLY MSG",
   [0x207] = "AWR DEV STATUS GET MSG",
   [0x208] = "RESERVED",
   [0x209] = "RESERVED",
   [0x20A] = "RESERVED",
   [0x20B] = "RESERVED",
   [0x20C] = "RESERVED",
   [0x20D] = "RESERVED",
   [0x280] = "AWR DEV ASYNC EVENT MSG",
}

local f_spi_sync = ProtoField.uint32("ti_mmwave_cfg.spi.sync", "Sync", base.HEX, spi_sync_enum)
local f_spi_direction = ProtoField.uint8("ti_mmwave_cfg.spi.direction", "Direction", base.HEX, spi_direction_enum)
local f_spi_msg_type = ProtoField.uint8("ti_mmwave_cfg.spi.msg_type", "MsgType", base.HEX, spi_msg_type_enum)
local f_spi_msg_id = ProtoField.uint16("ti_mmwave_cfg.spi.msg_id", "MsgId", base.HEX, spi_msg_id_enum)
local f_spi_len = ProtoField.uint16("ti_mmwave_cfg.spi.len", "Len", base.DEC)
local f_spi_flags = ProtoField.uint16("ti_mmwave_cfg.spi.flags", "Flags", base.HEX)
local f_spi_sblkid = ProtoField.uint16("ti_mmwave_cfg.spi.sblkid", "SblkId", base.HEX)
local f_spi_sblklen = ProtoField.uint16("ti_mmwave_cfg.spi.sblklen", "SblkLen", base.DEC)
local f_spi_sblkdata = ProtoField.string("ti_mmwave_cfg.spi.sblkdata", "SblkData")

p_ti_mmwave_config.fields = { f_sync_byte, f_cmd_code, f_ack_code, f_data_length,
                              f_dev_selection, f_ack_type, f_data, f_parm_length,
                              f_spi_sync, f_spi_direction, f_spi_msg_type,
                              f_spi_msg_id, f_spi_len, f_spi_flags,
                              f_spi_sblkid, f_spi_sblklen, f_spi_sblkdata }


local f_parm_length = ProtoField.uint32("ti_mmwave_tda_cmd_header.parm_length", "ParmLength", base.DEC)
p_ti_mmwave_tda_cmd_header.fields = { f_parm_length }

function p_ti_mmwave_tda_cmd_header.dissector(buf, pkt, tree)
    if length == 4 then
    end
end


function p_ti_mmwave_config.dissector(buf, pkt, tree)
	length = buf:len()
	if length == 0 then
		return
	end

	local subtree = tree:add(p_ti_mmwave_config, buf(), "TI Cascade EVM Config-frame Protocol Data")


    if length == 4 then
       --- Network TDA Command Header
       pkt.cols.protocol = "TDA_HDR"

       subtree:add_le(f_parm_length, buf(0, 4))
       return
    end

    if f_tcp_dstport().value == CONFIG_PORT then
       pkt.cols.protocol = "CFG_CSR"
    elseif f_tcp_srcport().value == CONFIG_PORT then
       pkt.cols.protocol = "ACK_CSR"
    end

    local cmd_code = buf(2, 2):le_uint()
    subtree:add_le(f_sync_byte, buf(0, 2))
    subtree:add_le(f_cmd_code, buf(2, 2), cmd_code)
    subtree:add_le(f_ack_code, buf(4, 2))
    subtree:add_le(f_data_length, buf(6, 2))
    subtree:add_le(f_dev_selection, buf(8, 1))
    subtree:add_le(f_ack_type, buf(9, 1))

    if cmd_code == 0x23 then
       --- SPI
       local spi_subtree = subtree:add(p_ti_mmwave_config, buf(14, buf:len() - 14), "SPI")
       local msg_direction = bit.band(buf(18, 2):le_uint(), 0xF)
       local msg_type = bit.rshift(bit.band(buf(18, 2):le_uint(), 0x30), 2)
       local msg_id = bit.rshift(bit.band(buf(18, 2):le_uint(), 0xFFC0), 6)
       spi_subtree:add_le(f_spi_sync, buf(14, 4))
       spi_subtree:add_le(f_spi_direction, buf(18, 1), msg_direction)
       spi_subtree:add_le(f_spi_msg_type,  buf(18, 1), msg_type)
       spi_subtree:add_le(f_spi_msg_id, buf(18, 2), msg_id)
       spi_subtree:add_le(f_spi_len, buf(20, 2))
       spi_subtree:add_le(f_spi_flags, buf(22, 2))

       spi_subtree:add_le(f_spi_sblkid, buf(30, 2))
       spi_subtree:add_le(f_spi_sblklen, buf(32, 2))
       spi_subtree:add_le(f_spi_sblkdata, buf(34, buf(32,2):le_uint() - 4))
    else
       subtree:add_le(f_data, buf(14, buf:len() - 16))
    end
end

tcp_encap_table:add(CONFIG_PORT, p_ti_mmwave_config)


---
--- ACK
---

local p_ti_mmwave_config_ack = Proto("cfg_ack", "TIMmwaveCascadeCfgAck")
