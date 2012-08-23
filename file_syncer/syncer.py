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

import time
import os
import hashlib
import copy
import fnmatch

from StringIO import StringIO
from itertools import chain

try:
    import simplejson as json
except ImportError:
    import json

from gevent import monkey
from gevent.pool import Pool
from libcloud.utils.files import exhaust_iterator
from libcloud.storage.base import Container, Object
from libcloud.storage.types import ContainerDoesNotExistError
from libcloud.storage.types import ObjectDoesNotExistError

monkey.patch_all()

from file_syncer.file_lock import FileLock
from file_syncer.constants import MANIFEST_FILE


class FileSyncer(object):
    def __init__(self, directory, provider_cls, username, api_key,
                 container_name, cache_path, exclude_patterns,
                 logger, concurrency=20):
        self._directory = directory
        self._provider_cls = provider_cls
        self._username = username
        self._api_key = api_key
        self._container_name = container_name
        self._cache_path = cache_path
        self._exclude_patterns = exclude_patterns
        self._logger = logger
        self._concurrency = concurrency

        self._uploaded = []
        self._removed = []

        if not os.path.exists(self._directory):
            raise ValueError('Directory %s doesn\'t exist' %
                             (self._directory))

        self._logger.info('Using provider: %(name)s',
                          {'name': provider_cls.name})

        self._setup_cache_path()
        self._setup_container()

    def _setup_cache_path(self):
        """
        Create a local cache directory, if it doesn't already exist.
        """
        if not os.path.exists(self._cache_path):
            self._logger.debug('Cache directory doesn\'t exist ' +
              '(%(directory)s), creating it...', {'directory': self._cache_path})
            os.makedirs(self._cache_path)

    def _setup_container(self):
        """
        Create a container if it doesn't already exist.
        """
        driver = self._get_driver_instance()

        try:
            container = driver.get_container(container_name=self._container_name)
        except ContainerDoesNotExistError:
            self._logger.debug('Container "%(name)s" doesn\'t exist, ' +
                    'creating it..', {'name': self._container_name})
            container = driver.create_container(container_name=self._container_name)

        self._container = container

    def _get_driver_instance(self):
        driver = self._provider_cls(self._username, self._api_key)
        return driver

    def _include_file(self, file_name):
        """
        Return True if the file should be included, False otherwise.
        """
        for pattern in self._exclude_patterns:
            if fnmatch.fnmatch(file_name, pattern):
                return

        return True

    def sync(self):
        """
        Synchronizes remote directory with a local one.
        """
        digest = hashlib.md5(self._directory).hexdigest()
        lock_file_path = os.path.join(digest)

        pool = Pool(self._concurrency)

        with FileLock(lock_file_path, timeout=None):
            # Ensure that only a single process runs at the same time
            time_start = time.time()
            local_files = self._get_local_files(directory=self._directory)
            self._logger.debug('Found %(count)s local files',
                               {'count': len(local_files)})

            remote_files = self._get_remote_files()
            self._logger.debug('Found %(count)s remote files',
                               {'count': len(remote_files)})

            differences = self._get_differences(local_files=local_files,
                                                remote_files=remote_files)
            actions = self._calculate_actions(differences=differences)

            self._logger.info('To remove: %(to_remove)s, to upload: %(to_upload)s',
                              {'to_remove': len(actions['to_remove']),
                               'to_upload': len(actions['to_upload'])})

            # Synchronization is performed in two steps:
            # 1 - Upload new or changed files and remove deleted ones
            # 2 - Upload manifest

            for item in actions['to_remove']:
                func = lambda item: self._remove_object(item=item)
                pool.spawn(func, item)

            for item in actions['to_upload']:
                func = lambda item: self._upload_object(item=item)
                pool.spawn(func, item)

            pool.join()

            manifest = self._generate_manifest(remote_files=remote_files)
            self._upload_manifest(json.dumps(manifest))

            took = (time.time() - time_start)
            self._logger.info('Synchronization complete, took: %(took)0.2f' +
                              ' seconds', {'took': took})

    def restore(self):
        """
        Restores a remote container to the file system
        """
        digest = hashlib.md5(self._directory).hexdigest()
        lock_file_path = os.path.join(digest)

        pool = Pool(self._concurrency)
        with FileLock(lock_file_path, timeout=None):
            # Ensure that only a single process runs at the same time
            time_start = time.time()

            for item in self._get_remote_files():
                func = lambda item: self._download_remote_file(name=item)
                pool.spawn(func, item)

            pool.join()

            took = (time.time() - time_start)
            self._logger.info('Synchronization complete, took: %(took)0.2f' +
                              ' seconds', {'took': took})

    def _get_item_remote_name(self, name, file_path):
        return file_path.replace(self._directory, '')

    def _generate_manifest(self, remote_files):
        manifest = copy.deepcopy(remote_files)

        for item in self._uploaded:
            manifest[item['remote_name']] = item

        for item in self._removed:
            if item['remote_name'] in manifest:
                del manifest[item['remote_name']]

        return manifest

    def _upload_manifest(self, data):
        driver = self._get_driver_instance()
        name = MANIFEST_FILE
        extra = {'content_type': 'application/json'}
        container = Container(name=self._container_name, extra=extra, driver=driver)
        iterator = StringIO(data)
        driver.upload_object_via_stream(iterator=iterator, container=container,
                                        object_name=name)

    def _remove_object(self, item):
        driver = self._get_driver_instance()
        name = item['remote_name']

        self._logger.debug('Removing object: %(name)s', {'name': name})

        container = Container(name=self._container_name, extra={}, driver=driver)
        obj = Object(name=name, size=None, hash=None, extra=None,
                     meta_data=None, container=container, driver=driver)

        try:
            driver.delete_object(obj=obj)
        except Exception, e:
            self._logger.error('Failed to remove object "%(name)s": %(error)s',
                               {'name': name, 'error': str(e)})
            return

        self._removed.append(item)
        self._logger.debug('Object removed: %(name)s', {'name': name})

    def _upload_object(self, item):
        driver = self._get_driver_instance()
        name = item['remote_name']
        file_path = item['path']

        self._logger.debug('Uploading object: %(name)s', {'name': name})

        extra = {'content_type': 'application/octet-stream'}
        container = Container(name=self._container_name, extra=None, driver=driver)

        try:
            driver.upload_object(file_path=file_path, container=container,
                                 object_name=name, extra=extra)
        except Exception, e:
            self._logger.error('Failed to upload object "%(name)s": %(error)s',
                               {'name': name, 'error': str(e)})
            return

        self._uploaded.append(item)
        self._logger.debug('Object uploaded: %(name)s', {'name': name})

    def _get_local_files(self, directory):
        """
        Recursively find all the files in a directory.

        @rtype C{dict}
        """
        result = {}

        base_path = os.path.abspath(directory)
        for (dirpath, dirnames, filenames) in os.walk(directory):
            for name in filenames:

                file_path = os.path.join(base_path, dirpath, name)
                remote_name = self._get_item_remote_name(name=name,
                                                         file_path=file_path)

                if not self._include_file(remote_name):
                    self._logger.debug('File %(name)s is excluded, skipping it', 
                                       {'name': name})
                    continue

                mtime = os.path.getmtime(file_path)
                md5_hash = None

                item = {'name': name, 'remote_name': remote_name, 'path': file_path,
                        'last_modified': mtime, 'md5_hash': md5_hash}
                result[remote_name] = item

        return result

    def _get_remote_files(self):
        """
        Return a list of files in a container.
        """
        driver = self._get_driver_instance()

        try:
            obj = driver.get_object(container_name=self._container_name,
                                    object_name=MANIFEST_FILE)
        except ObjectDoesNotExistError:
            self._logger.debug('Manifest doesn\'t exist, assuming that ' +
                               'there are no remote files')
            return {}

        iterator = driver.download_object_as_stream(obj=obj)
        data = exhaust_iterator(iterator=iterator)

        try:
            parsed = json.loads(data)
        except Exception, e:
            raise Exception('Corrupted manifest, failed to parse it: ' + str(e))

        return parsed


    def _download_remote_file(self, name):
        """
        Download a remote file given a name.
        """

        self._logger.debug('Downloading object: %(name)s to %(path)s',
                {'name': name, 'path': self._directory})

        # strip the leading slash if it exists in the object_name
        local_filename = name
        if local_filename[0] == '/':
            local_filename = local_filename[1:]

        driver = self._get_driver_instance()
        filepath = os.path.join(self._directory, local_filename)

        try:
            obj = driver.get_object(container_name=self._container_name,
                                    object_name=name)
        except ObjectDoesNotExistError:
            self._logger.debug('Object ' + name + ' doesn\'t exist')
            return

        driver.download_object(obj=obj, destination_path=filepath,
                overwrite_existing=True, delete_on_failure=True)

    def _get_differences(self, local_files, remote_files):
        """
        Return differences between a local and remote copy.

        @rtype C{dict} A dictionary with the following keys:

        added - files which have been added locally.
        removed - files which have been removed.
        modified - files which have been modified.
        """
        result = {'added': {}, 'removed': {}, 'modified': {}}

        for name, local_item in local_files.iteritems():
            remote_item = remote_files.get(name, None)

            if remote_item is None:
                # New file
                result['added'][name] = local_item
            elif local_item['last_modified'] > remote_item['last_modified']:
                # Local file has been modified
                result['modified'][name] = local_item

        for name, remote_item in remote_files.iteritems():
            name = remote_item['remote_name']
            local_item = local_files.get(name, None)

            if not local_item:
                # File has been deleted locally
                result['removed'][name] = remote_item

        return result

    def _calculate_actions(self, differences):
        """
        Return actions which need to be performed to make the remote copy match
        a local one.
        """
        result = {'to_upload': [], 'to_remove': []}

        for item in chain(differences['added'].values(),
                          differences['modified'].values()):
            result['to_upload'].append(item)

        for item in differences['removed'].values():
            result['to_remove'].append(item)

        return result
