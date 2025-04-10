Millimeter-wave Capture Standard (mmwave-capture-std)
=====================================================

[![Documentation Status](https://readthedocs.org/projects/mmwave-capture-std/badge/?version=latest)](https://mmwave-capture-std.readthedocs.io/en/latest/?badge=latest)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![License: BSD 3-Clause-Clear](https://img.shields.io/badge/License-BSD%203--Clause--Clear-green.svg)](https://spdx.org/licenses/BSD-3-Clause-Clear.html)

**mmwave-capture-std** is a *fast*, *reliable*, and *replicable*
Texas Instruments millimeter-wave capture toolkit,
focus on data capturing and raw data parsing.

It stands out with three key attributes:

1. Fast: It parses raw data into `np.ndarray[np.complex64]` **2.09** times
   faster than state-of-the-art packages (0.59s v.s. 1.239s).

2. Reliable: It makes users easily identify and debug hardware issues,
   and provides fine-grained control over different hardware.
   It achieves this by comprehensive logging (stderr & file) and by separating
   the hardware setup from the data capture code.

3. Replicable: It simplifies the process of replicating the recording setup
   by using a toml config file to manage capture hardware, layout the dataset
   as HDF5-like structure, and provide sensor config files to each capture result.

Capture Millimeter-wave Raw Data is Easy
----------------------------------------

Here is an example of using `mmwave-capture-std` to capture mmwave data
from IWR1483BOOST and DCA1000EVM:

```bash
$ uv run mmwavecapture-std examples/capture_iwr1843.toml
2023-06-02 :43.91 | INFO     | ...:...:225 - Capture ID: 0
2023-06-02 :43.91 | INFO     | ...:init_hw:230 - Initializing capture hardware `iwr1843`..
2023-06-02 :49.32 | SUCCESS  | ...:init_hw:245 - Capture hardware `iwr1843` initialized
2023-06-02 :49.32 | SUCCESS  | ...:init_hw:247 - Total of 1 capture hardware initialized
2023-06-02 :49.32 | INFO     | ...:capture:258 - Adding capture hardware `iwr1843`
2023-06-02 :49.32 | INFO     | ...:capture:121 - Preparing capture hardware
2023-06-02 :49.32 | INFO     | ...:capture:125 - Starting capture hardware
2023-06-02 :49.42 | SUCCESS  | ...:capture:128 - Capture started
2023-06-02 :52.49 | INFO     | ...:capture:132 - Capture finished
2023-06-02 :52.49 | INFO     | ...:capture:134 - Dumping capture hardware configurations
2023-06-02 :52.49 | SUCCESS  | ...:capture:270 - Capture finished, all files ...
```

Nice and easy! Your capture result will be stored like this with HDF5-like structure:

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

Where to start?
---------------

First, setup your environment (hardware, software, and network):
[Setup](https://mmwave-capture-std.readthedocs.io/en/latest/setup.html).

Then, read our quickstart to get familiar with how mmwave-capture-std works:
[Quickstart](https://mmwave-capture-std.readthedocs.io/en/latest/quickstart.html).

See the full documentation:
[mmwave-capture-std Documentation](https://mmwave-capture-std.readthedocs.io/en/latest/index.html)
for more information.

Links
-----

* Homepage: <https://www.cs.unc.edu/~louielu/p/mmwave-capture-std/>
* Documentation: [mmwave-capture-std Documentation](https://mmwave-capture-std.readthedocs.io/en/latest/)
* Source Code: [mmwave-capture-std/mmwave-capture-std](https://github.com/mmwave-capture-std/mmwave-capture-std/)
* License: [BSD 3-Clause Clear License](https://github.com/mmwave-capture-std/mmwave-capture-std/blob/main/LICENSE)

Contribute
----------

Use the following snippet to setup your development environment:

```bash
git clone <repo-url>
cd mmwave-capture-std
uv install # Prepare env and install deps
uv run pre-commit install # Install pre-commit hooks
```

Related Publications
--------------------

* mmCounter: Static People Counting in Dense Indoor Scenarios using mmWave Radar
  - Tarik Reza Toha, Shao-Jung (Louie) Lu, and Shahriar Nirjon
  - The 22nd International Conference on Embedded Wireless Systems and Networks (EWSN '25)

* mmDefender: A mmWave System for On-Body Localization of Concealed Threats in Moving Persons
  - Shao-Jung (Louie) Lu, Mahathir Monjur, Sirajum Munir, and Shahriar Nirjon
  - The 22nd International Conference on Embedded Wireless Systems and Networks (EWSN '25)

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
