.. _build-config:

Capture Manager Configuration
=============================

Metadata
--------

We adopt elements from `Dublin Core <https://www.dublincore.org/specifications/dublin-core/dces/>`_
to define dataset metadata, below is the defined elements and their description copied from
`Dublin Core <https://www.dublincore.org/specifications/dublin-core/dces/>`_:

.. confval:: title

   :type: str
   :default: ``"Millimeter-wave dataset"``

   The capture dataset name.

.. confval:: creator

   :type: str
   :default: ``"unknown"``

   An entity primarily responsible for making the resource.

.. confval:: subject

   :type: str

   The topic of the resource.

   Typically, the subject will be represented using keywords,
   key phrases, or classification codes.
   Recommended best practice is to use a controlled vocabulary.

   .. note::

      Use comma to separate multiple keywords: ``"mmwave, radar"``

.. confval:: description

   :type: str

   An account of the resource.

   Description may include but is not limited to:
   an abstract, a table of contents, a graphical representation,
   or a free-text account of the resource.

.. confval:: date

   :type: str | datetime.datetime

   Date of the capture recorded. If the value is ``"<today>"``, it will be replace with
   ``datetime.datetime.today()`` automatically by :class:`~mmwavecapture.capture.capture.CaptureManager`.

.. confval:: license

    :type: str
    :default: ``"CC-BY-SA-4.0"``

    A legal document giving official permission to do something with the resource.

    Recommended practice is to identify the license document with a URI.
    If this is not possible or feasible, a literal value that identifies the license may be provided.

    .. note::

       Recommend to use ``Full name`` or ``short identifier``
       from `SPDX License <https://spdx.org/licenses/>`_.
