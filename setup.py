import os
import sys

from setuptools import setup
from setuptools import Command
from subprocess import call


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
    version='0.1.0',
    scripts=[os.path.join(os.getcwd(), 'bin/file-syncer')],
    packages=[
        'file_syncer'
    ],
    package_dir={
        'file_syncer': 'file_syncer'
    },
    install_requires=[
        'apache-libcloud>=0.10.1',
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
    }
)
