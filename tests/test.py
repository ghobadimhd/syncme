import os
from copy import copy
from unittest import TestCase
from unittest.mock import MagicMock, Mock, mock_open, patch

import syncme
import sample_config


class TestSyncme(TestCase):

    """ Test Syncme """

    def setUp(self):
        SYNCME_CONFIG = os.path.expanduser(os.environ.get('SYNCME_CONFIG', ''))
        self.default_config_files = [
            SYNCME_CONFIG,
            os.path.expanduser('~/.syncme.yml'),
            os.path.expanduser('~/.config/syncme.yml'),
            '/etc/syncme.yml'
        ]

        with open('tests/sample_config.yml') as f:
            self.default_config_content = f.read()

        self.default_config = sample_config.SAMPLE_PARSED_CONFIG

    def test_get_config_locations(self):


        result = syncme.get_config_locations()
        self.assertListEqual(result, self.default_config_files)

    @patch('syncme.os')
    def test_load_config(self, mock_os):

        sample_path = '/sample/path'

        # test method if file does not exists
        mock_os.path.exists.return_value = False
        result = syncme.load_config()
        self.assertTupleEqual(result, (None, None))
        # test load_config with given parameter
        result = syncme.load_config(sample_path)
        self.assertTupleEqual(result, (None, None))

        # if path exists but it's not a file
        mock_os.path.exists.return_value = True
        mock_os.path.isfile.return_value = False
        expected_resault = (None, None)
        result = syncme.load_config()
        self.assertTupleEqual(result, (None, None))

        result = syncme.load_config(sample_path)
        self.assertTupleEqual(result, (None, None))

        # test if it can discover files properly
        # FIXME: it's too imperative and complicated
        mock_os.path.isfile.return_value = True
        with patch('syncme.open', mock_open(
                   read_data=self.default_config_content)):
            for path in self.default_config_files:
                with self.subTest(file=path):
                    mock_os.path.exists.side_effect = \
                        lambda p: True if p == path else False
                    result = syncme.load_config()
                    self.assertDictEqual(result[0], self.default_config)
                    self.assertEqual(result[1], path)

            mock_os.path.exists.side_effect = lambda p: p == sample_path

            result = syncme.load_config(sample_path)
            self.assertDictEqual(result[0], self.default_config)
            self.assertEqual(result[1], sample_path)

            # test if function work with given argument
            with patch('syncme.open', mock_open(
                    read_data='')):
                result = syncme.load_config(sample_path)
                self.assertDictEqual(result[0], dict())
                self.assertEqual(result[1], sample_path)

    def test_merge_host(self):
        """ test merge_host function """

        sample_host = copy(self.default_config['syncs'][0]['hosts'][1])
        sample_global_host = self.default_config['hosts']

        expected_result = {'name': 'example',
                           'address': 'example.com',
                           'user': 'ghobadimhd',
                           'paths': ['/home', '/var/projects']}

        syncme.merge_host(sample_global_host, sample_host)
        self.assertDictEqual(sample_host, expected_result)

    def test_fix_host_path(self):
        """ test _fix_host_path function """

        sample_path_list1 = [
            '/home/ghobadimhd',
            '~/projects/',
            '/var/cache/apt-cacher-ng',
            '/var/backups/'
        ]
        sample_path_list2 = [
            '/remote/sergey/',
            '/var/projects',
            '/var/cache/apt-cacher-ng',
        ]
        expected_path_list = [
            '/remote/sergey',
            '/var/projects/',
            '/var/cache/apt-cacher-ng',
            '/var/backups/',
        ]

        result = syncme._fix_host_path(sample_path_list2, sample_path_list1)
        self.assertListEqual(result, expected_path_list)

    def test_validate_global_host(self):
        """ test valiate_global_host function """

        sample_host1 = {
            'address': 'example.com',
        }

        expected_result = {
            'name': 'example.com',
            'address': 'example.com',
        }

        return_value = syncme.validate_global_host(sample_host1)
        self.assertDictEqual(sample_host1, expected_result)

        # it should return True if everything goes OK
        # FIXME: it better for function to return host in normal and throw
        # exception if anything goes wrong
        self.assertTrue(return_value)

        sample_host2 = {
            'name': 'example.com',
        }

        return_value = syncme.validate_global_host(sample_host2)

        # must return False if address missing
        # FIXME: it's better to throw exception instead of returning False
        self.assertFalse(return_value)

        sample_host3 = {
            'name': 'example.com',
            'paths': ['/some/where', '/path1/file']
        }

        return_value = syncme.validate_global_host(sample_host3)

        # must return false if path defined in host
        # FIXME: it's better to throw exception instead of returning False
        self.assertFalse(return_value)

    def test_validate_host(self):
        """ test validate_host function """

        sample_global_host_list = [
            {
                'name': 'example.com',
                'address': 'example.com',
                'user': 'user1',
                'password': 'password123',
            }
        ]

        sample_host1 = {
            'name': 'example.com',
        }

        sample_path1 = [
            '/home/ghobadimhd',
            '~/projects/',
            '/var/cache/apt-cacher-ng',
            '/var/backups/'
        ]

        expected_result = {
            'name': 'example.com',
            'address': 'example.com',
            'user': 'user1',
            'password': 'password123',
            'paths': [
                '/home/ghobadimhd',
                '~/projects/',
                '/var/cache/apt-cacher-ng',
                '/var/backups/'
            ]
        }
        # FIXME: it's better that original function return host than changing
        # it and in
        syncme.validate_host(sample_host1, sample_path1,
                             sample_global_host_list)
        self.assertDictEqual(sample_host1, expected_result)

        sample_host2 = {}

        with self.assertRaises(AttributeError):
            syncme.validate_host(sample_host2, sample_path1,
                                 sample_global_host_list)

    def test_validate_sync(self):
        """ test validate_sync_function """

        # if sync is empty it must return false
        # FIXME: it's better to orginal function Raise a exception
        sample_sync = {}

        result = syncme.validate_sync(sample_sync)
        self.assertFalse(result)

        # sync with reserved name 'all' is not allowed
        sample_sync = {'name': 'all'}
        result = syncme.validate_sync(sample_sync)
        self.assertFalse(result)

        sample_sync = {
            'name': 'test',
            'paths': [
                '/home/ghobadimhd/',
                '~/projects',
                '/var/cache/apt-cacher-ng',
                '/var/backups/'
            ],

        }

        expected_sync = {
            'name': 'test',
            'recursive': False,
            'tags': [],
            'paths': [
                '/home/ghobadimhd/',
                '~/projects',
                '/var/cache/apt-cacher-ng',
                '/var/backups/'
            ],
            'hosts': []
        }

        self.maxDiff = None
        result = syncme.validate_sync(sample_sync)
        print(sample_sync)
        self.assertTrue(result)
        self.assertDictEqual(sample_sync, expected_sync)

    def test_validate_config_empty_config(self):
        """ test validate_config with empty config """

        sample_config = {}

        expected_config = {
            'hosts': [],
            'syncs': [],
            'recursive': False,
            'tags': [],
        }

        result = syncme.validate_config(sample_config)
        self.assertTrue(result)
        self.assertDictEqual(sample_config, expected_config)

    def test_validate_config_invalid_config(self):
        """ test validate_config function with invalid configuration """

        sample_config = {
            'syncs': [
                {
                    'name': 'all'
                }
            ]
        }

        result = syncme.validate_config(sample_config)
        # FIXME: it's better to raise exception when something goes wrong
        self.assertFalse(result, 'syncs with name "all" are not allowed')

        sample_config = {
            'hosts': [
                {
                    # global host without address field is invalid
                    'name': 'global_host'
                }
            ]
        }
        is_valid = syncme.validate_config(sample_config)
        self.assertFalse(is_valid)

        sample_config = {
            'hosts': [
                {
                    # a global host at least need to define a name and address
                    'name': 'global_host',
                    'address': 'example.com'
                }
            ]
        }
        is_valid = syncme.validate_config(sample_config)
        self.assertTrue(is_valid)

        sample_config = {
            'hosts': [
                {
                    # global host with paths field is invalid
                    'name': 'global_host',
                    'address': 'example.com',
                    'paths': [
                        '/some/path',
                    ]
                }
            ]
        }
        is_valid = syncme.validate_config(sample_config)
        self.assertFalse(is_valid)

        sample_config = {
            'hosts': [
                {
                    'name': 'global_host',
                    'address': 'example.com',
                    'user': 'user1',
                    'password': '123'
                }
            ],
            'syncs': [
                {
                    # sync without a name is invalid
                    'paths': [
                        '/some/path',
                        '/another/path'
                    ]
                }
            ]
        }
        is_valid = syncme.validate_config(sample_config)
        self.assertFalse(is_valid)

        # host is defined without address
        sample_config = {
            'hosts': [
                {
                    'name': 'backup_server',
                }
            ],
            'syncs': [
                {
                    'name': 'backups',
                    'paths': [
                        '/some/path',
                        '/another/path'
                    ],
                    'hosts': [
                        {
                            'name': 'backup_server',
                        }
                    ]

                }
            ]
        }
        is_valid = syncme.validate_config(sample_config)
        self.assertFalse(is_valid)

    @patch('syncme.os')
    def test_valid_config(self, mock_os):

        sample_path = '/sample/path'
        mock_os.path.isfile.return_value = True
        with patch('syncme.open', mock_open(
                   read_data=self.default_config_content)):

            # if just given path exists
            mock_os.path.exists.side_effect = lambda p: p == sample_path
            # test if function work with given argument
            result = syncme.load_config(sample_path)
            self.assertDictEqual(result[0], self.default_config)
            self.assertEqual(result[1], sample_path)

        # test if function work with given argument and empty content
        with patch('syncme.open', mock_open(
                read_data='')):
            result = syncme.load_config(sample_path)
            self.assertDictEqual(result[0], dict())
            self.assertEqual(result[1], sample_path)
