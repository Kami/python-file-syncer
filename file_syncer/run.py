# Licensed to Tomaz Muraus under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# Tomaz muraus licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import logging

from optparse import OptionParser

from libcloud.storage.providers import get_driver
from libcloud.storage.types import Provider

from file_syncer.log import get_logger
from file_syncer.constants import VALID_LOG_LEVELS
from file_syncer.syncer import FileSyncer

SUPPORTED_PROVIDERS = [p for p in Provider.__dict__.keys() if not
                       p.startswith('__')]
PROVIDER_MAP = dict([(k, v) for k, v in Provider.__dict__.iteritems()
                     if not k.startswith('__')])
REQUIRED_OPTIONS = [('username', 'api_username'), ('key', 'api_key'),
                    ('container-name', 'container_name'),
                    ('directory', 'directory')]


def run():
    usage = 'usage: %prog --username=<api username> --key=<api key> [options]'
    parser = OptionParser(usage=usage)
    parser.add_option('--provider', dest='provider', default='CLOUDFILES_US',
                      help='Provider to use')
    parser.add_option('--region', dest='region', default=None,
                      help='Region to use if a Libcloud driver supports \
                        multiple regions (e.g. ORD for CloudFiles provider)')
    parser.add_option('--username', dest='api_username',
                      help='API username')
    parser.add_option('--key', dest='api_key',
                      help='API key')
    parser.add_option('--restore', dest='restore', action="store_true",
                      help='Restore from')
    parser.add_option('--container-name', dest='container_name',
                      default='file_syncer',
                      help='Name of the container storing the files')
    parser.add_option('--directory', dest='directory',
                      help='Local directory to sync')
    parser.add_option('--cache-path', dest='cache_path',
                      default=os.path.expanduser('~/.file_syncer'),
                      help='Directory where a settings and cached manifest ' +
                           'files are stored')
    parser.add_option('--concurrency', dest='concurrency', default=10,
                      help='File upload concurrency')
    parser.add_option('--exclude', dest='exclude',
                      help='Comma separated list of file name patterns to ' +
                           'exclude')
    parser.add_option('--log-level', dest='log_level', default='INFO',
                      help='Log level')
    parser.add_option('--delete', dest='delete', action='store_true',
                      help='delete extraneous files from dest containers',
                      default=False)
    parser.add_option('--no-content-type', dest='no_content_type',
                      default=False, action='store_true',
                      help='Don\'t automatically specify \'application/' +
                           'octet-stream\' content-type for every file. Use ' +
                           'automatic file type detection based on the file ' +
                           'extension')
    parser.add_option('--follow_symlinks', dest='follow_symlinks',
                      default=False, action='store_true',
                      help='Visit directories pointed to by symlinks, ' +
                           'on systems that support them')

    (options, args) = parser.parse_args()

    for option_name, key in REQUIRED_OPTIONS:
        if not getattr(options, key, None):
            raise ValueError('Missing required argument: ' + option_name)

    # Set up provider
    if options.provider not in SUPPORTED_PROVIDERS:
        raise ValueError('Invalid provider: %s. Valid providers are: %s' %
                         (options.provider, ', '.join(SUPPORTED_PROVIDERS)))

    provider = PROVIDER_MAP[options.provider]

    # Set up logger
    log_level = options.log_level.upper()

    if log_level not in VALID_LOG_LEVELS:
        valid_levels = [value.lower() for value in VALID_LOG_LEVELS]
        raise ValueError('Invalid log level: %s. Valid log levels are: %s' %
                         (options.log_level, ', ' .join(valid_levels)))

    level = getattr(logging, log_level, 'INFO')
    logger = get_logger(handler=logging.StreamHandler(), level=level)

    directory = os.path.expanduser(options.directory)
    exclude_patterns = options.exclude or ''
    exclude_patterns = exclude_patterns.split(',')

    syncer = FileSyncer(directory=directory,
                        provider_cls=get_driver(provider),
                        provider=provider,
                        region=options.region,
                        username=options.api_username,
                        api_key=options.api_key,
                        container_name=options.container_name,
                        cache_path=options.cache_path,
                        exclude_patterns=exclude_patterns,
                        logger=logger,
                        concurrency=int(options.concurrency),
                        no_content_type=options.no_content_type,
                        follow_symlinks=options.follow_symlinks)
    if options.restore:
        syncer.restore()
    else:
        syncer.sync(options.delete)
