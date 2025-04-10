.. Millimeter-wave Capture Standard (mmwave-capture-std) documentation master file, created by
   sphinx-quickstart on Fri Jun  2 20:04:11 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. rst-class:: hide-header

Welcome to Millimeter-wave Capture Standard (mmwave-capture-std)'s documentation!
=================================================================================

**mmwave-capture-std** is a *fast*, *reliable*, and *replicable* Texas Instruments millimeter-wave capture toolkit, focus on data capturing and raw data parsing.

It stands out with three key attributes:

#. **Fast**: It parses raw data into ``np.ndarray[np.complex64]`` 2.09 times faster than state-of-the-art packages (0.593s v.s. 1.239s).

#. **Reliable**: It makes users easily identify and debug hardware issues, and provides fine-grained control over different hardware. It achieves this by comprehensive logging (stderr & file) and by separating the hardware setup from the data capture code.

#. **Replicable**: It simplifies the process of replicating the recording setup by using a toml config file to manage capture hardware, layout the dataset as HDF5-like structure, and provide sensor config files to each capture result.

Here is an example of using ``mmwave-capture-std`` to capture mmwave data from IWR1483BOOST and DCA1000EVM:

.. code-block:: bash

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


Nice and easy! Your capture result will be stored like this with HDF5-like structure :

.. code-block:: bash

   ☁  mmwave-capture-std [main]  tree example_dataset
   example_dataset
    └── capture_00000
        ├── capture.log
        ├── config.toml
        └── iwr1843
            ├── dca.json
            ├── dca.pcap
            └── radar.cfg

You probably will need to modify the configuration to reflect your capture hardware setup.
Change the following setting in ``example/capture_iwr1843.toml`` to your setup:
(assume you did not change any setting on DCA1000EVM EEPROM)

.. code-block:: toml

   [hardware.iwr1843]
   dca_eth_interface = "enp5s0"
   radar_config_port = "/dev/ttyACM0"
   radar_data_port = "/dev/ttyACM1"
   capture_frames = 10


Where to start?
---------------

First, setup your environment (hardware, software, and network): :doc:`Setup <setup>`.

Then, read our quickstart to get familiar with how ``mmwave-capture-std`` works: :doc:`Quickstart <quickstart>`.



Contribute
----------

Use the following snippet to setup your development environment:

.. code-block:: bash

   git clone <repo-url>
   cd mmwave-capture-std
   uv sync # Prepare env and install deps
   uv run pre-commit install # Install pre-commit hooks

License
-------

This project is licensed under the `BSD 3-Clause Clear License <https://github.com/mmwave-capture-std/mmwave-capture-std/blob/main/LICENSE>`_.


.. toctree::
   :caption: User's Guide
   :maxdepth: 2
   :hidden:

   setup
   quickstart
   configs/index

.. toctree::
   :caption: Development
   :hidden:

   api/api

.. toctree::
   :caption: Links
   :hidden:

   Homepage <https://cs.unc.edu/~louielu/p/mmwave-capture-std>
   Documentation <https://mmwave-capture-std.readthedocs.io/en/latest/>
   Source Code <https://github.com/mmwave-capture-std/mmwave-capture-std>
   License <https://github.com/mmwave-capture-std/mmwave-capture-std/blob/main/LICENSE>

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
