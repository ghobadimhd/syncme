#!/usr/bin/python3

import logging
import os
import subprocess as sp
import getpass
import argparse
from itertools import zip_longest
import yaml


# global variables
SYNCME_CONFIG = os.path.expanduser(os.environ.get('SYNCME_CONFIG', ''))
CONFIG_LOCATIONS = [
    SYNCME_CONFIG,
    os.path.expanduser('~/.syncme.yml'),
    os.path.expanduser('~/.config/syncme.yml'),
    '/etc/syncme.yml'
    ]
RSYNC = '/usr/bin/rsync'
if not os.path.exists(RSYNC):
    logging.error('cannot find rsync at %s', RSYNC)
    raise FileNotFoundError()

logger = logging.getLogger(__name__)

def setup_logger(level='INFO'):
    """ setup a default logger """
    logger = logging.getLogger(__name__)
    logger.setLevel(getattr(logging, level.upper()))
    logger.addHandler(logging.StreamHandler())

def load_config(path=None):
    """ Load config from yml file

    Read config from path specified by path and return it's content as dict
    if path not specified, Read config from SYNCME_CONFIG enviroment
    variable and if SYNCME_CONFIG is not defined Read config from one
    of these paths:
         ~/.syncme.yml, ~/.config/syncme.yml, /etc/syncme.yml

    args:
        path: custom config path
    """
    if path is not None:
        paths = [path]
    else:
        paths = CONFIG_LOCATIONS
    # Check paths and read first path that exists
    for config_path in paths:
        print(config_path)
        if os.path.exists(config_path) and os.path.isfile(config_path):
            try:
                logger.debug('loading config from %s', config_path)
                with open(config_path, 'r') as config_file:
                    config = yaml.load(config_file)
                    # config config (file) is empty
                    if config is None:
                        config = dict()
                    return config
            except Exception as e:
                raise e
    logger.error('config not found')
    return None

def merge_host(global_hosts, host):
    """ Merge host with global host
    
    Get global hosts and a host, find a global host with same name as host
    and add missing parameter from global host to the host

    args:
        global_hosts: list of global hosts
        host: a host object (dict) to merge 
    """
    global_host = None
    for h in global_hosts:
        if h['name'] == host['name']:
            global_host = h
            break
    if global_host is not None:
        for key in global_host.keys():
            host.setdefault(key, global_host[key])

def validate_config(config):
    """ check and validate config

    check syncs and hosts, fix missing user, check and fix source and
    destination paths

    args:
        config: config loaded from yaml file

    """

    config.setdefault('hosts', [])
    config.setdefault('syncs', [])
    config.setdefault('recursive', False)
    config.setdefault('tags', [])

    # check and validate global hosts
    for host in config['hosts']:
        if 'address' not in host:
            logger.error('address is not defined for host')
            return False
        if 'paths' in host:
            logger.error('paths is invalid in global hosts ')
            return False

        host.setdefault('name', host['address'])
        host['name'] = host['name'].lower()

    for sync in config.get('syncs'):
        sync.setdefault('recursive', config.get('recursive'))
        sync.setdefault('tags', config['tags'])

        if 'name' not in sync:
            logger.error('each sync most have a name')
            return False
        else:
            if sync['name'] == 'all':
                logger.error("sync's name cannot be 'all'")
                return False
            # sync name are case insensitive
            sync['name'] = sync['name'].lower()

        sync.setdefault('hosts', [])
        sync.setdefault('paths', [])
        
        for host in sync['hosts']:
            if 'name' in host:
                host['name'] = host['name'].lower()
                merge_host(config['hosts'], host)
            if 'address' in host:
                # set address as default name
                if 'name' not in host:
                host['name'] = host['address'].lower()
            else:
                logger.error('address is not defined for host')
                return False

            host.setdefault('user', getpass.getuser())
            host.setdefault('paths', [])

            zipped_path = zip_longest(sync['paths'], host['paths'], fillvalue=None)
            new_host_paths = []
            for path_pair in zipped_path:
                if path_pair[0] is not None:
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
    """ transfer file from local to remote

    args:
        local_path: path of source file to transfer
        remote_path: path of destination file
        host: remote host address
        user: user of remote host
        recursive: if set True path trasfered recursively
        tags: list of str tags(options) added to rsync command
    """
    return_code = rsync(
        source_path=kwargs.get('local_path'), dest_path=kwargs.get('remote_path'),
            dest_host=kwargs.get('host'), dest_user=kwargs.get('user'),
            tags=kwargs.get('tags', []), recursive=kwargs.get('recursive', False))

    return return_code

def pull(**kwargs):
    """ transfer file from remote to local

    args:
        local_path: path of source file (destination)
        remote_path: path of remote file
        host: remote host address
        user: user of remote host
        recursive: if set True path trasfered recursively
        tags: list of str tags(options) added to rsync command
    """
    return_code = rsync(
        dest_path=kwargs.get('local_path'), source_path=kwargs.get('remote_path'),
            source_host=kwargs.get('host'), source_user=kwargs.get('user'),
            tags=kwargs.get('tags', []), recursive=kwargs.get('recursive', False))
    return return_code

def rsync(**kwargs):
    """ this is wrapper around rsync command

    args:
        source_path: path of source file
        dest_path: path of destination file
        source_host: address of source host
        dest_host: address of destination host
        source_user: source host username
        dest_user: destination host username
        tags: list of str tags(options) added to rsync command
        recursive: if set True -r option added to rsync
    """

    # set default user for source and destination
    if kwargs.get('source_user') is None:
        kwargs['source_user'] = getpass.getuser()
    if kwargs.get('dest_user') is None:
        kwargs['dest_user'] = getpass.getuser()

    kwargs.setdefault('source_path', '.')
    kwargs.setdefault('dest_path', '.')
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
            logger.info('Push %s to %s:', sync['name'], host['name'])
            for local_path, remote_path in zip(sync['paths'], host['paths']):
                # check if localpath is None, it happens when there are more remote_paths than local_paths
                if local_path is not None:
                    return_code = push(local_path=local_path, remote_path=remote_path,
                                   host=host['address'], user=host['user'], tags=sync['tags'], recursive=sync['recursive'])
                    if return_code != 0:
                        logger.error('failed to transfer path %s to %s', local_path, host['name'])
                        failed_hosts.append((host['name'], local_path))

    return failed_hosts

def pull_sync(config, sync_name='all', host_name=None):
    """use the config to pull paths from hosts"""

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
                # check if localpath is None, it happens when there are more remote_paths than local_paths
                if local_path is not None:
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

def get_sync(config, name):
    """ find sync in config and return it """

    for sync in config['syncs']:
        if sync['name'] == name:
            return sync
    return None

def get_host(config, sync_name, name):
    """ find host in sync and return it  """
    sync = get_sync(config, sync_name)

    for host in sync['hosts']:
        if host['name'] == name:
            return host
    return None

def get_global_host(config, name):
    """ find global host in config with its name and return it """

    for host in config['hosts']:
        if host['name'] == name:
            return host
    return None

def add_sync(config, name, paths=None, tags=None, recursive=None):
    """ add new sync to config

    args:
        config: configuration object
        name: sync name
        paths: list of paths of syncs
        tags: list of tags
        recursive: True or False
    """
    if name is None:
        logger.critical('name is necessary')
        return False
    if paths is None:
        paths = []
    if tags is None:
        tags = []
    if recursive is None:
        recursive = config['recursive']

    sync = {'name': name,
            'paths': paths,
            'tags': tags,
            'recursive': recursive,
            'hosts': []
        }

    config['syncs'].append(sync)

    return True

def setup_argparse():
    parser = argparse.ArgumentParser(prog='syncme')
    parser.add_argument('-v', action='store_true', help='verbose mode')
    parser.add_argument('-c', '--config', help='load config from file specified by CONFIG')
    subparsers = parser.add_subparsers()

    parser_list = subparsers.add_parser('list')
    parser_list.set_defaults(action='list')

    parser_push = subparsers.add_parser('push', help='push paths to hosts')
    parser_push.set_defaults(action='push')
    parser_push.add_argument('--sync-name', dest='sync_name', default='all')
    parser_push.add_argument('--host-name', dest='host_name', default='all')

    parser_pull = subparsers.add_parser('pull', help='pull paths from a host')
    parser_pull.set_defaults(action='pull')
    parser_pull.add_argument('--sync-name', dest='sync_name', default='all')
    parser_pull.add_argument('--host-name', dest='host_name', default=None)

    return parser

def main():
    parser = setup_argparse()
    args = parser.parse_args()
    if 'action' not in args:
        parser.print_help()
        exit(1)

    if args.v:
        setup_logger('DEBUG')
    else:
        setup_logger()
    if 'c' in args:
        config = load_config(args.c)
    else:
        config = load_config()

    if config is None:
        exit(1)
    
    if not validate_config(config):
        logger.critical('config error')
        exit(1)
    if args.action == 'list':
        list_syncs(config)
    if args.action == 'push':
        push_sync(config, args.sync_name, args.host_name)
    if args.action == 'pull':
        pull_sync(config, args.sync_name, args.host_name)

if __name__ == '__main__':
    main()
