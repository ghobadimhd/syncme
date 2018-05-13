#!/usr/bin/python3

import logging
import os
import subprocess as sp
import getpass
from itertools import zip_longest
import yaml


# global variables
SYNCME_CONFIG = os.path.expanduser(os.environ.get('SYNCME_CONFIG', ''))
CONFIG_LOCATIONS = [SYNCME_CONFIG, os.path.expanduser('~/.syncme.yml'), os.path.expanduser('~/.config/syncme.yml'), '/etc/syncme.yml']
RSYNC = '/usr/bin/rsync'
if not os.path.exists(RSYNC):
    logging.error('cannot find rsync at %s', RSYNC)
    raise FileNotFoundError()

def setup_logger(level=logging.INFO):
    """ setup a default logger """
    logger = logging.getLogger('default')
    logger.setLevel(level)
    logger.addHandler(logging.StreamHandler())

def load_config(config_path=None):
    """ Load config from yml file """
    logger = logging.getLogger('default')
    if config_path is not None:
        
        if os.path.exists(config_path) and os.path.isfile(config_path):
            try:
                logger.debug('loading config from %s', config_path)
                with open(config_path, 'r') as config_file:
                    return yaml.load(config_file)
            except Exception as e:
                raise e
    else:
        for config_path in CONFIG_LOCATIONS:
            
            if os.path.exists(config_path) and os.path.isfile(config_path):
                try:
                    logger.debug('loading config from %s', config_path)
                    with open(config_path, 'r') as config_file:
                        return yaml.load(config_file)
                except Exception as e:
                    raise e
    logger.error('config not found')
    return None

def validate_config(config:dict):
    logger = logging.getLogger('default')
    config.setdefault('hosts', [])
    config.setdefault('syncs', [])
    config.setdefault('recursive', False)

    for sync in config.get('syncs'):
        sync.setdefault('recursive', config.get('recursive'))
        sync.setdefault('tags', [])

        if 'name' not in sync:
            logger.error('each sync most have a name')
            return False
        if 'hosts' not in sync:
            logger.error('%s: no host defined', sync['name'])
            return False
        if 'paths' not in sync:
            logger.error('%s: paths not defined', sync['name'])
            return False
        
        for host in sync['hosts']:
            if 'address' not in host:
                logger.error('address is not defined for host')
                return False

            # set address as default name
            host.setdefault('name', host['address'])
            host.setdefault('user', getpass.getuser())
            host.setdefault('paths', [])

            zipped_path = zip_longest(sync['paths'], host['paths'], fillvalue=None)
            new_host_paths = []
            for path_pair in zipped_path:
                if path_pair[1] is None:
                    new_host_paths.append(path_pair[0])
                else:
                    if path_pair[0][-1] == '/' and path_pair[1][-1] != '/':
                        new_host_paths.append(path_pair[1] + '/')
                    elif path_pair[0][-1] != '/' and path_pair[1][-1] == '/':
                        new_host_paths.append(path_pair[1][:-1] )
                    else:
                        new_host_paths.append(path_pair[1])

            host['paths'] = new_host_paths

    return True

def push(**kwargs):
    """
    transfer file from local to remote
    """

    return_code = rsync(source_path=kwargs.get('local_path'), dest_path=kwargs.get('remote_path'),
                        dest_host=kwargs.get('host'), dest_user=kwargs.get('user'),
                        tags=kwargs.get('tags', []), recursive=kwargs.get('recursive', False))

    return return_code

def pull(**kwargs):
    """
    transfer file from remote to local
    """
    return_code = rsync(dest_path=kwargs.get('local_path'), source_path=kwargs.get('remote_path'),
                        source_host=kwargs.get('host'), source_user=kwargs.get('user'),
                        tags=kwargs.get('tags', []), recursive=kwargs.get('recursive', False))
    return return_code

def rsync(**kwargs):
    """
    transfer file from remote to local
    """
    logger = logging.getLogger('default')
    kwargs.setdefault('source_path', '.')
    kwargs.setdefault('soruce_user', getpass.getuser())
    kwargs.setdefault('dest_path', '.')
    kwargs.setdefault('dest_user', getpass.getuser())
    kwargs.setdefault('tags', [])
    kwargs.setdefault('recursive', False)

    if kwargs.get('source_host', None) is None:
        cmd = [RSYNC, '{0}'.format(kwargs['source_path']),
               '{0}@{1}:{2}'.format(kwargs['dest_user'], kwargs['dest_host'],
               kwargs['dest_path'])]
    elif kwargs.get('dest_host', None) is None:
        cmd = [RSYNC, '{0}@{1}:{2}'.format(kwargs['source_user'],
               kwargs['source_host'], kwargs['source_path']),
               '{0}'.format(kwargs['dest_path'])]
    else:
        logger.critical('Both source and destination cannot be remote hosts')
        return 1

    # add recursive tag to command
    if kwargs['recursive']:
        cmd.append('-r')
    # add tags
    cmd + kwargs['tags']
    logger.debug('debug: running ' + ' '.join(cmd))
    return_code, output = sp.getstatusoutput(' '.join(cmd))
    logger.debug(output)
    return return_code

def list_syncs(config):
    """list syncs """
    for sync in config['syncs']:
        print('{}:'.format(sync['name']))
        print('\tpaths:')
        for path in sync['paths']:
            print('\t\t{}'.format(path))
        print('\thosts:')
        for host in sync['hosts']:
            print('\t\tname: {}'.format(host['name']))
            print('\t\taddress: {}'.format(host['address']))
            print('\t\tuser: {}'.format(host['user']))
            print('\t\tpaths:')
            for path in host['paths']:
                print('\t\t\t{}'.format(path))
        print('\ttags:')
        for tag in sync['tags']:
            print('\t\t{}'.format(tag))
        print('')

def push_sync(config, sync_name='all', host_name='all'):
    """use the config to push paths to hosts """
    logger = logging.getLogger('default')
    failed_hosts = []
    sync_name = sync_name.lower()
    host_name = host_name.lower()
    # find sync
    if sync_name == 'all':
            syncs = config['syncs']
    else:
        syncs = [x for x in config['syncs'] if x['name'] == sync_name]
    
    for sync in syncs:
        # find host
        if host_name == 'all':
            remote_hosts = sync['hosts']
        else:
            remote_hosts = [x for x in sync['hosts']
                            if x['name'] == host_name]

        for host in remote_hosts:
            logger.info('Push from %s to %s:', sync['name'], host['name'])
            for local_path, remote_path in zip(sync['paths'], host['paths']):
                return_code = push(local_path=local_path, remote_path=remote_path,
                               host=host['address'], user=host['user'], tags=sync['tags'], recursive=sync['recursive'])
                if return_code != 0:
                    logger.error('failed to transfer path %s to %s', local_path, host['name'])
                    failed_hosts.append((host['name'], local_path))

    return failed_hosts

def pull_sync(config, sync_name='all', host_name=None):
    """use the config to pull paths from hosts"""
    logger = logging.getLogger('default')
    failed_hosts = []
    sync_name = sync_name.lower()
    if host_name is not None:
        host_name = host_name.lower()

    # find sync
    if sync_name == 'all':
            syncs = config['syncs']
    else:
        syncs = [x for x in config['syncs'] if x['name'] == sync_name]

    for sync in syncs:
        # find host
        if host_name is None:
            remote_hosts = sync['hosts']
        else:
            remote_hosts = [x for x in sync['hosts']
                            if x['name'] == host_name]

        for host in remote_hosts:
            logger.info('Pull from %s to %s', host['name'], sync['name'])
            for local_path, remote_path in zip(sync['paths'], host['paths']):
                return_code = push(local_path=local_path, remote_path=remote_path,
                                   host=host['address'], user=host['user'], tags=sync['tags'], recursive=sync['recursive'])
                if return_code != 0:
                    logger.debug('Failed to transfer path %s to local system',
                                 remote_path)
                    failed_hosts.append((host['name'], local_path))
            if host['name'] not in [x[0] for x in failed_hosts]:
                logger.info('Local system successfully synced with %s', host['name'])
                break
            else:
                logger.error('paths partialy synced try to sync with another host')

    return failed_hosts
