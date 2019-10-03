import os
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch, mock_open
from copy import copy

import syncme


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

        self.default_config_content = """
recursive: True
tags:
  - '-v'
  - '--perms'

hosts:
  - name: example
    address: example.com
    user: ghobadimhd
  - name: netbook
    address: 192.168.1.15
    user: mamad

syncs:
  - name: default
    paths:
      - '/home/ghobadimhd'
      - '~/projects/'
      - '/var/cache/apt-cacher-ng/'
    tags: ['-v']
    hosts:
      - name: netbook
        user: netbook

      - name: example
        paths:
          - '/home'
          - '/var/projects'
"""
        self.default_config = {
            'hosts': [{'address': 'example.com', 'name': 'example', 'user': 'ghobadimhd'},
                              {'address': '192.168.1.15', 'name': 'netbook', 'user': 'mamad'}],
                               'recursive': True,
                               'syncs': [{'hosts': [{'name': 'netbook', 'user': 'netbook'},
                                                    {'name': 'example', 'paths': ['/home', '/var/projects']}],
                                          'name': 'default',
                                          'paths': ['/home/ghobadimhd',
                                                    '~/projects/',
                                                    '/var/cache/apt-cacher-ng/'],
                                          'tags': ['-v']}],
                               'tags': ['-v', '--perms']}


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
