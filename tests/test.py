import os
from copy import copy
from unittest import TestCase
from unittest.mock import MagicMock, Mock, mock_open, patch

import syncme
from sample_config import SAMPLE_PARSED_CONFIG


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

        self.default_config = SAMPLE_PARSED_CONFIG

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
                    mock_os.path.exists.side_effect = lambda p: True if p == path else False
                    result = syncme.load_config()
                    self.assertDictEqual(result[0], self.default_config)
                    self.assertEqual(result[1], path)

            mock_os.path.exists.side_effect = lambda p: p == sample_path

            result = syncme.load_config(sample_path)
            self.assertDictEqual(result[0], self.default_config)
            self.assertEqual(result[1], sample_path)

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
