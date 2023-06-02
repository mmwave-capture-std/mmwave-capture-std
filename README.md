Millimeter-wave Capture Standard (mmwave-capture-std)
=====================================================

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![License: BSD 3-Clause-Clear](https://img.shields.io/badge/License-BSD%203--Clause--Clear-green.svg)](https://spdx.org/licenses/BSD-3-Clause-Clear.html)

**mmwave-capture-std** is a *fast*, *reliable*, and *replicable*
Texas Instruments millimeter-wave capture toolkit.

`mmwave-capture-std` focus on data capturing and parsing raw data,
it stands out with three key attributes:

1. Fast: It parse raw data into `np.ndarray[np.complex64]` **7.25** times
   faster than state-of-the-art packages (0.75s v.s. 5.435s).

2. Reliable: It makes user easily indentify and debugging hardware issues, and provides
   fine-grained control over hardwares. It achieves this by comprehensive logging
   (stderr & file) and by separating the hardware setup from data capture code.

3. Replicable: It simplifies the process of replicating recording setup by
   using a toml config file to manage capture hardwares, layout the dataset
   as HDF5-like structure, and provide sensor config files to each capture result.

Prerequisites
-------------

* tcpdump (Please take a look at [How to setup tcpdump capture privileges](#how-to-setup-tcpdump-capture-privileges))
* Poetry

Install
-------

```bash
git clone git@github.com:mmwave-capture-std/mmwave-capture-std.git
cd mmwave-capture-std
poetry install
```

How to capture
--------------

Capture should be *easy*, *reliable*, and *replicable*.

You can run the following command in `mmwave-capture-std/` to caputre
mmwave raw IF signals from IWR1843 + DCA1000EVM:

```bash
$ poetry run mmwavecapture-std examples/capture_iwr1843.toml
2023-06-02 :43.91 | INFO     | ...:...:225 - Capture ID: 0
2023-06-02 :43.91 | INFO     | ...:init_hw:230 - Initializing capture hardware `iwr1843`..
2023-06-02 :49.32 | SUCCESS  | ...:init_hw:245 - Capture hardware `iwr1843` initialized
2023-06-02 :49.32 | SUCCESS  | ...:init_hw:247 - Total of 1 capture hardwares initialized
2023-06-02 :49.32 | INFO     | ...:capture:258 - Adding capture hardware `iwr1843`
2023-06-02 :49.32 | INFO     | ...:capture:121 - Preparing capture hardwares
2023-06-02 :49.32 | INFO     | ...:capture:125 - Starting capture hardwares
2023-06-02 :49.42 | SUCCESS  | ...:capture:128 - Capture started
2023-06-02 :52.49 | INFO     | ...:capture:132 - Capture finished
2023-06-02 :52.49 | INFO     | ...:capture:134 - Dumping capture hardware configurations
2023-06-02 :52.49 | SUCCESS  | ...:capture:270 - Capture finished, all files ...
```

The capture result will be stored in `example_dataset/`,
the layout should looks like:

```bash
☁  mmwave-capture-std [main]  tree example_dataset
example_dataset
└── capture_00000
    ├── capture.log
    ├── config.toml
    └── iwr1843
        ├── dca.json
        ├── dca.pcap
        └── radar.cfg
```

You probably will need to modify the configuration to reflect your
capture hardware setup. Change the following setting in `example/capture_iwr1843.toml`
to your setup: (assume you did not change any setting on DCA1000EVM EEPROM)

```toml
[hardware.iwr1843]
dca_eth_interface = "enp5s0"
radar_config_port = "/dev/ttyACM0"
radar_data_port = "/dev/ttyACM1"
capture_frames = 10
```

How to setup tcpdump capture privileges
---------------------------------------

For detail information about how to setup tcpdump capture privileges,
please refer to [Wireshark: CaptureSetup/CapturePrivileges](https://wiki.wireshark.org/CaptureSetup/CapturePrivileges).

Below is the example of setting up on Linux:

### 1. Limit capture permission to only one group

1. Create a group called `pcap` and add yourself to it:

    ```bash
    sudo groupadd pcap
    sudo usermod -a -G pcap $USER
    ```

1. Re-login to apply the group changes or use `newgrp pcap` as
   the normal user to enter the *pcap* group. (Run the `groups`
   command to verify that you are part of the *pcap* group.
1. Change `/usr/sbin/tcpdump` group and file mode

    ```bash
    sudo chgrp pcap /usr/sbin/tcpdump
    sudo chmod o-rx /usr/sbin/tcpdump
    ```

### 2. Setting network privileges for tcpdump by file capabilities

```bash
sudo setcap cap_net_raw,cap_net_admin+eip /usr/sbin/tcpdump
```

Contribute
----------

Use the following snippet to setup your development environment:

```bash
git clone <repo-url>
cd mmwave-capture-std
poetry install # Prepare env and install deps
poetry run pre-commit install # Install pre-commit hooks
```

LICENSE
-------

```text
The Clear BSD License

Copyright (c) 2023 Louie Lu <louielu@cs.unc.edu>
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted (subject to the limitations in the disclaimer
below) provided that the following conditions are met:

     * Redistributions of source code must retain the above copyright notice,
     this list of conditions and the following disclaimer.

     * Redistributions in binary form must reproduce the above copyright
     notice, this list of conditions and the following disclaimer in the
     documentation and/or other materials provided with the distribution.

     * Neither the name of the copyright holder nor the names of its
     contributors may be used to endorse or promote products derived from this
     software without specific prior written permission.

NO EXPRESS OR IMPLIED LICENSES TO ANY PARTY'S PATENT RIGHTS ARE GRANTED BY
THIS LICENSE. THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND
CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
```
