Welcome to File Syncer documentation!
=====================================

File Syncer is a Python program which synchronized files from a local directory
to one of the cloud object storage providers supported by Apache Libcloud.

Besides local <-> remote synchronization it also supports restoring files from
the remote server to a local directory.

For more information and background, please see blog post titled
`Hosting APT repository on Rackspace CloudFiles`_.

Features
========

* Synchronize files from a local directory to one of the supported providers
 * User can specify a list of filename patterns which are excluded
 * User can specify to delete files in the container that do not exist locally
* Restore files from the remote server to a local directory
* All the operations (deletes, uploads and downloads) happen in parallel

Installation
============

Latest stable version can be installed from PyPi using pip:

.. sourcecode:: bash
    pip install file-syncer

If you want to install latest development version, you can install it from this
Git repository:

.. sourcecode:: bash

    pip install -e https://github.com/Kami/python-file-syncer.git@master#egg=file_syncer

Usage
=====

.. sourcecode:: bash

    file-syncer --help

Synchronizing files from a local directory to a remote server
-------------------------------------------------------------

.. sourcecode:: bash

    file-syncer --username=<api username> --key=<api key or password> \
                --provider=<libcloud provider constant - e.g. CLOUDFILES_US> \
                --container-name=<target container name>  \
                --directory=<path to directory used to synchronize> \
                --delete

Restoring files from the remote server to a local directory
-----------------------------------------------------------

.. sourcecode:: bash

    file-syncer --username=<api username> --key=<api key or password> \
                --restore \
                --provider=<libcloud provider constant - e.g. CLOUDFILES_US> \
                --container-name=<remote container name>  \
                --directory=<path to directory where the files will be restored to>

Specifying a region with a CloudFiles provider
----------------------------------------------

.. sourcecode:: bash

    file-syncer --username=<api username> --key=<api key or password> \
                --provider=CLOUDFILES_US \
                --region=ord  \
                --container-name=<target container name>  \
                --directory=<path to directory used to synchronize> \
                --delete

Changelog
=========

For changelog, please see the `CHANGES file`_.

License
=======

File syncer is distributed under the `Apache 2.0 license`_.

.. _`Hosting APT repository on Rackspace CloudFiles`: http://www.tomaz.me/2012/07/22/hosting-apt-repository-on-rackspace-cloud-files.html
.. _`CHANGES file`: https://github.com/Kami/python-file-syncer/blob/master/CHANGES.rst
.. _`Apache 2.0 license`: https://www.apache.org/licenses/LICENSE-2.0.html
