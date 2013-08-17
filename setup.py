import os
import sys

from os.path import join as pjoin

from setuptools import setup
from setuptools import Command
from subprocess import call


def read_version_string():
    version = None
    sys.path.insert(0, pjoin(os.getcwd()))
    from file_syncer import __version__
    version = __version__
    sys.path.pop(0)
    return version


class Pep8Command(Command):
    description = 'run pep8 script'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        try:
            import pep8

            pep8
        except ImportError:
            print ('Missing "pep8" library. You can install it using pip: '
                   'pip install pep8')
            sys.exit(1)

        cwd = os.getcwd()
        retcode = call(('pep8 %s/file_syncer' % (cwd)).split(' '))
        sys.exit(retcode)

setup(
    name='file_syncer',
    version=read_version_string(),
    long_description=open('README.rst').read() + '\n\n' +
    open('CHANGES.rst').read(),
    scripts=[os.path.join(os.getcwd(), 'bin/file-syncer')],
    packages=[
        'file_syncer'
    ],
    package_dir={
        'file_syncer': 'file_syncer'
    },
    install_requires=[
        'apache-libcloud>=0.13.0',
        'gevent'
    ],
    url='https://github.com/Kami/python-file-syncer/',
    license='Apache License (2.0)',
    author='Tomaz Muraus',
    author_email='tomaz+pypi@tomaz.me',
    description='Python program which synchronizes files from a local ' +
                 'directory to one of the storage providers supported by ' +
                 'Libcloud.',
    cmdclass={
        'pep8': Pep8Command
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Operating System :: OS Independent',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
