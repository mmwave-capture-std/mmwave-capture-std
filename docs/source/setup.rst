Setup
=====

Software (``mmwave-capture-std`` and dependencies)
--------------------------------------------------

System requirements
```````````````````

- **Python 3.7+**
    - **Recommendation**: `pyenv <https://github.com/pyenv/pyenv>`_ for Python version management (if you are using macOS, or your distribution does not provide Python 3.7+)
    - `Python Installation <https://www.python.org/downloads/>`_
- git
    - `git Installation <https://git-scm.com/download/linux>`_


Dependencies Installation
`````````````````````````

- uv: `uv Installation <https://docs.astral.sh/uv/getting-started/installation/>`_
- tcpdump:
    - `tcpdump latest releases <https://www.tcpdump.org/#latest-releases>`_
    - For Linux and UNIX systems, check the package name for your distribution from here:
      `tcpdump package <https://pkgs.org/download/tcpdump>`_, e.g.:

      .. code-block:: bash

         - ``apt-get install tcpdump`` for Debian/Ubuntu
         - ``pacman -S tcpdump`` for Arch Linux
         - ``yum install tcpdump`` for CentOS
         - ``dnf install tcpdump`` for Fedora

- libpcap:
    - `libpcap latest releases <https://www.tcpdump.org/#latest-releases>`_
    - For Linux and UNIX systems, check the package name for your distribution from here:
      `libpcap package <https://pkgs.org/download/libpcap>`_, e.g.:

      .. code-block:: bash

         - ``apt-get install libpcap-dev`` for Debian/Ubuntu
         - ``pacman -S libpcap`` for Arch Linux
         - ``yum install libpcap-devel`` for CentOS
         - ``dnf install libpcap-devel`` for Fedora

``mmwave-capture-std`` Installation
````````````````````````````````````

.. code-block:: bash

   git clone git@github.com:mmwave-capture-std/mmwave-capture-std.git
   cd mmwave-capture-std
   uv sync

Hardware
--------

IWR1843BOOST
````````````

- Firmware: Out-of-box demo: 3.6.0
- `MMWAVE SDK User Guide Product Release 3.6 LTS <https://dr-download.ti.com/software-development/software-development-kit-sdk/MD-PIrUeCYr3X/03.06.00.00-LTS/mmwave_sdk_user_guide.pdf>`_


DCA1000EVM
``````````

- FPGA firmware: 2.8
- `DCA1000EVM Quick Start Guide <https://www.ti.com/lit/ml/spruik7/spruik7.pdf>`_
- `DCA1000EVM User's Guide <https://www.ti.com/lit/ug/spruij4a/spruij4a.pdf>`_

Network Setup
-------------

tcpdump capture privileges
```````````````````````````

.. warning::

   ``mmwave-capture-std`` relies on ``tcpdump`` to capture DCA1000EVM data,
   so make sure you read and setup ``tcpdump`` capture privileges correctly.

For detail information about how to setup tcpdump capture privileges,
please refer to `Wireshark: CaptureSetup/CapturePrivileges <https://wiki.wireshark.org/CaptureSetup/CapturePrivileges>`_.

Below is the example of setting up on Linux:

1. Limit capture permission to only one group
'''''''''''''''''''''''''''''''''''''''''''''

1. Create a group called ``pcap`` and add yourself to it:

   .. code-block:: bash

      sudo groupadd pcap
      sudo usermod -a -G pcap $USER

2. Re-login to apply the group changes or use ``newgrp pcap`` as
   the normal user to enter the *pcap* group. (Run the ``groups``
   command to verify that you are part of the *pcap* group.

3. Change ``/usr/sbin/tcpdump`` group and file mode

   .. code-block:: bash

      sudo chgrp pcap /usr/sbin/tcpdump
      sudo chmod o-rx /usr/sbin/tcpdump


2. Setting network privileges for tcpdump by file capabilities
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

.. code-block:: bash

   sudo setcap cap_net_raw,cap_net_admin+eip /usr/sbin/tcpdump


DCA1000EVM network setup
````````````````````````

Assume your host machine has two network interfaces:

- ``enp1s0``: Host ip ``192.168.33.30``, DCA1000EVM ip ``192.168.33.180``.
- ``enp2s0``: Host ip ``192.168.33.31``, DCA1000EVM ip ``192.168.33.181``.

First, you will need to change the state of the device to **UP**:

.. code-block:: bash

    sudo ip link set enp1s0 up
    sudo ip link set enp2s0 up


One DCA1000EVM (one radar)
''''''''''''''''''''''''''

It is easy to setup one radar. Just add an IP address to the network interface connected to the radar. For example:

.. code-block:: bash

    # On the host machine
    sudo ip addr add 192.168.33.30/24 dev enp1s0

Two or more DCA1000EVM (two or more radars)
'''''''''''''''''''''''''''''''''''''''''''

For two or more radars, we need to setup routing rules additionally. For example:

.. code-block:: bash

    # On the host machine
    sudo ip addr add 192.168.33.30/24 dev enp1s0
    sudo ip addr add 192.168.33.31/24 dev enp2s0

    # Setup routing rules
    sudo ip route add 192.168.33.180 dev enp1s0
    sudo ip route add 192.168.33.181 dev enp2s0

Increase the memory dedicated to the network interfaces
```````````````````````````````````````````````````````

.. note:: These settings probably are not necessary for most of the cases.

If you observe packet loss from ``tcpdump``, you may need to increase the memory dedicated to the network interfaces. Please refer to `Increase the memory dedicated to the network interfaces - Archlinux Wiki <https://wiki.archlinux.org/title/sysctl#Increase_the_memory_dedicated_to_the_network_interfaces>`_.
