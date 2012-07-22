import time
import os
import hashlib

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


class FileSyncer(object):
    def __init__(self, directory, provider_cls, username, api_key,
                 container_name, cache_path, logger, concurrency=20):
        self._directory = directory
        self._provider_cls = provider_cls
        self._username = username
        self._api_key = api_key
        self._container_name = container_name
        self._cache_path = cache_path
        self._logger = logger
        self._concurrency = concurrency

        if not os.path.exists(self._directory):
            raise ValueError('Directory %s doesn\'t exist' %
                             (self._directory))

        self._logger.info('Using provider: %(name)s', {'name': provider_cls.name})

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

            # Synchronization is performed in three steps:
            # 1 - Remove removed or changed files
            # 2 - Upload new or changed files
            # 3 - Upload manifest

            for item in actions['to_remove']:
                func = lambda name: self._remove_object(name=name)
                pool.spawn(func, item['remote_name'])

            pool.join()

            for item in actions['to_upload']:
                func = lambda file_path, name: self._upload_object(file_path=file_path,
                                                   name=name)
                pool.spawn(func, item['path'], item['remote_name'])

            pool.join()

            # TODO: Only add successfully uploaded files.
            self._upload_manifest(json.dumps(local_files))

            took = time.time() - time_start
            self._logger.info('Synchronization complete, took: %(took)0.2f' +
                              ' seconds', {'took': took})

    def _get_item_remote_name(self, name, file_path):
        return file_path.replace(self._directory, '')

    def _upload_manifest(self, data):
        driver = self._get_driver_instance()
        name = 'manifest.json'
        manifest_path = os.path.join(self._cache_path, name)

        with open(manifest_path, 'w') as fp:
            fp.write(data)

        container = Container(name=self._container_name, extra={}, driver=driver)
        driver.upload_object(file_path=manifest_path, container=container,
                             object_name=name)

    def _remove_object(self, name):
        driver = self._get_driver_instance()
        container = Container(name=self._container_name, extra={}, driver=driver)
        obj = Object(name=name, size=None, hash=None, extra=None,
                     meta_data=None, container=container, driver=driver)
        driver.delete_object(obj=obj)
        self._logger.debug('Object removed: %(name)s', {'name': name})

    def _upload_object(self, file_path, name):
        driver = self._get_driver_instance()
        self._logger.debug('Uploading object: %(name)s', {'name': name})
        container = Container(name=self._container_name, extra={}, driver=driver)
        driver.upload_object(file_path=file_path, container=container,
                             object_name=name, extra=None)
        self._logger.debug('Object uploaded: %(name)s', {'name': name})

    def _get_local_files(self, directory):
        """
        Recursively find all the files in a directory.
        @rtype C{dict}
        """
        results = []

        base_path = os.path.abspath(directory)
        for (dirpath, dirnames, filenames) in os.walk(directory):
            for name in filenames:
                file_path = os.path.join(base_path, dirpath, name)
                remote_name = self._get_item_remote_name(name=name,
                                                         file_path=file_path)
                mtime = os.path.getmtime(file_path)
                md5_hash = None

                item = {'name': name, 'remote_name': remote_name, 'path': file_path,
                        'last_modified': mtime, 'md5_hash': md5_hash}
                results.append(item)

        return results

    def _get_remote_files(self):
        """
        Return a list of files in a container.
        """
        driver = self._get_driver_instance()

        try:
            obj = driver.get_object(container_name=self._container_name,
                                    object_name='manifest.json')
        except ObjectDoesNotExistError:
            self._logger.debug('Manifest doesn\'t exist, assuming that ' +
                               'there are no remote files')
            return []

        iterator = driver.download_object_as_stream(obj=obj)
        data = exhaust_iterator(iterator=iterator)

        try:
            parsed = json.loads(data)
        except Exception, e:
            raise Exception('Corrupted manifest, failed to parse it: ' + str(e))

        return parsed

    def _get_item(self, item_path, items):
        for item in items:
            if item['path'] == item_path:
                return item

        return None

    def _get_differences(self, local_files, remote_files):
        """
        Return differences between a local and remote copy.

        @rtype C{dict} A dictionary with the following keys:

        added - a list of files which have been added local.
        removed - a list of local files which have been removed.
        changed - a list of local files which have changed.
        """
        result = {'added': [], 'removed': [], 'changed': []}

        # TODO: Make search more efficient
        for local_item in local_files:
            remote_item = self._get_item(item_path=local_item['path'],
                                         items=remote_files)

            if not remote_item:
                # New file
                result['added'].append(local_item)
            elif local_item['last_modified'] > remote_item['last_modified']:
                # Local file has been changed
                result['changed'].append(local_item)

        for remote_item in remote_files:
            local_item = self._get_item(item_path=remote_item['path'],
                                        items=local_files)

            if not local_item:
                # File has been deleted locally
                result['removed'].append(remote_item)

        return result

    def _calculate_actions(self, differences):
        """
        Return actions which need to be performed to make the remote copy match
        a local one.
        """
        result = {'to_upload': [], 'to_remove': []}

        for item in differences['added']:
            result['to_upload'].append(item)

        for item in differences['changed']:
            result['to_upload'].append(item)

        for item in differences['removed']:
            result['to_remove'].append(item)

        return result
