#!/usr/bin/python3

import logging
import os
import subprocess as sp
import getpass
import argparse
from itertools import zip_longest
import yaml


RSYNC = '/usr/bin/rsync'
if not os.path.exists(RSYNC):
    logging.error('cannot find rsync at %s', RSYNC)
    raise FileNotFoundError()

logger = logging.getLogger(__name__)

def get_config_locations():
    """ return possible config locations """
    environ_path = os.path.expanduser(os.environ.get('SYNCME_CONFIG', ''))
    config_locations = [
    environ_path,
    os.path.expanduser('~/.syncme.yml'),
    os.path.expanduser('~/.config/syncme.yml'),
    '/etc/syncme.yml'
    ]

    return config_locations

def setup_logger(level='INFO'):
    """ setup a default logger """
    logger = logging.getLogger(__name__)
    logger.setLevel(getattr(logging, level.upper()))
    logger.addHandler(logging.StreamHandler())


def is_file_exists(file_path):
    """ checks if path points to a existing file """

    return os.path.exists(file_path) and \
        os.path.isfile(file_path)


def discover_config_file(path=None):
    """ discover config file """
    if path is None:
        for file_path in get_config_locations():
            if is_file_exists(file_path):
                return file_path

    else:
        if is_file_exists(path):
            return path
        else:
            logging.error('cannot find config file at %s', path)

    return None


def read_yaml(path):
    """ load yaml from path"""

    try:
        logger.debug('Try to load config from %s', path)
        with open(path, 'r') as config_file:
            config = yaml.load(config_file)
            return config
    except Exception as e:
        raise e


def load_config(path=None, loader=read_yaml):
    """ Load config from yml file

    Read config from path specified by path and return it's content as dict
    if path not specified, Read config from SYNCME_CONFIG enviroment
    variable and if SYNCME_CONFIG is not defined Read config from one
    of these paths:
         ~/.syncme.yml, ~/.config/syncme.yml, /etc/syncme.yml

    args:
        path: custom config path
    """

    path = discover_config_file(path)
    if path is None:
        logger.error('config not found')
        return None, None
    # for now only yaml loader supported
    config = loader(path)

    if config is None:
        # default config is empty dict
        config = dict()
    logger.debug('Read config from %s', path)

    return (config, path)


def merge_host(global_host_list, host):
    """ Merge host with global host

    Get global hosts and a host, find a global host with same name as host
    and add missing parameter from global host to the host

    args:
        global_hosts: list of global hosts
        host: a host object (dict) to merge
    """
    # FIXME: rename the variable
    target_host = None
    for h in global_host_list:
        if h['name'] == host['name']:
            target_host = h
            break
    if target_host is not None:
        for key in target_host.keys():
            host.setdefault(key, target_host[key])


def map_path(source, destination):
    """ add default destination based on source and append or remove ending / to/from destination """
    if destination is None:
        destination = source

    # normalize destination path
    destination = os.path.normpath(destination)
    if source.endswith('/'):
        destination += '/'
    return destination


def _fix_host_path(host_paths, sync_paths):
    """ generate new host paths list based on sync paths

    add or remove trailing slashes base on sync paths
    add default paths (copy sync path)

    args:
        host_paths: host paths
        sync_paths: sync paths

    return: new list of host path
    """

    source_destination_list = zip_longest(
        sync_paths, host_paths, fillvalue=None)
    new_host_paths = []
    for source, destination in source_destination_list:
        new_destination = map_path(source, destination)
        new_host_paths.append(new_destination)

    return new_host_paths


def validate_host(host, sync_paths, global_hosts=[]):
    """ validate host settings 
    
    validate host setting by setting default value and check setting for valid value

    args:
        host: host settings dictionary 
        sync_paths: sync paths list that used to validate host paths
        global_host: list of global_host to use for merging host

    return: None
    """
    if 'name' in host:
        host['name'] = host['name'].lower()
        merge_host(global_hosts, host)
    if 'address' in host:
        # set address as default name
        if 'name' not in host:
            host['name'] = host['address'].lower()
    else:
        logger.error('address is not defined for host')
        raise AttributeError('Host must have address')
    
    host.setdefault('user', getpass.getuser())
    host.setdefault('paths', [])

    host['paths'] = _fix_host_path(host['paths'], sync_paths)


def validate_global_host(host):
    """ validate host settings 
    
    validate host setting by setting default value and check setting for valid value

    args:
        host: host settings dictionary 

    return: None
    """
    if 'address' not in host:
        logger.error('address is not defined for host')
        return False
    if 'paths' in host:
        logger.error('paths is invalid in global hosts ')
        return False
    host.setdefault('name', host['address'])
    # convert name to lower case
    host['name'] = host['name'].lower()
    return True

def validate_sync(sync, default_recursive=False, default_tags=None):
    """ validate sync settings

    validate host setting by setting default value and check setting for valid value

    args:
        sync: sync settings dictionary
        default_recursive: default value for recursive flag
        default_tags: default list of tags
    """
    if default_tags is None:
        default_tags = []
    
    sync.setdefault('recursive', default_recursive)
    sync.setdefault('tags', default_tags)

    if 'name' not in sync:
        logger.error('each sync most have a name')
        return False
    else:
        if sync['name'].lower() == 'all':
            logger.error("sync's name cannot be 'all'")
            return False
        # sync name are case insensitive
    
    sync['name'] = sync['name'].lower()
    sync.setdefault('hosts', [])
    sync.setdefault('paths', [])

    return True



def validate_config(config):
    """ check and validate config

    check syncs and hosts, fix missing user, check and fix source and
    destination paths

    args:
        config: config loaded from yaml file

    """
    # set default global settings
    config.setdefault('hosts', [])
    config.setdefault('syncs', [])
    config.setdefault('recursive', False)
    config.setdefault('tags', [])

    # check and validate global hosts
    for host in config['hosts']:
        is_valid = validate_global_host(host)
        if not is_valid:
            return False
    # validate sync
    for sync in config['syncs']:
        sync.setdefault('hosts', [])
        for host in sync['hosts']:
            is_host_valid = validate_host(host, sync['paths'], config['hosts'])
            if not is_host_valid:
                return False
        # validate hosts in syncs
        is_sync_valid = validate_sync(sync, config['recursive'], config['tags'])
        if not is_sync_valid:
            return False

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
    cmd = cmd + kwargs['tags']
    logger.debug('debug: running ' + ' '.join(cmd))
    job = sp.Popen(cmd)
    return_code = job.wait()
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

def syncronize_host(method_name, host, sync_paths, recursive=False, tags=[]):
    """ syncronize sync paths base on method (push or pull) 

    syncronize (pull or push) sync_paths with host paths

    args:
        method_name: string contain name of method use which used to syncronize. most be 'pull' or 'push'
        host: host to syncronize with
        sync_paths: list of paths for syncing with host's paths
        tags: list of str tags(options) added to rsync command
        recursive: if set True -r option added to rsync

    returns: list of paths that failed to sync
    """
    methods = {'push': push, 'pull': pull}

    if method_name not in methods.keys():
        raise AttributeError("method most 'push' or 'pull' ")
    else:
        method = methods[method_name]

    failed_paths = []
    for local_path, remote_path in zip(sync_paths, host['paths']):
        # check if localpath is None, it happens when there are more remote_paths than local_paths
        if local_path is None:
            # if localpath is None pass to next path
            continue
        
        return_code = method(local_path=local_path, remote_path=remote_path,
                           host=host['address'], user=host['user'], tags=tags, recursive=recursive)
        if return_code != 0:
            logger.error(
                'failed to sync (%s) path %s to %s', method_name, local_path, host['name'])
            failed_paths.append((local_path, remote_path))

    return failed_paths


def syncronize_syncs(method_name, config, sync_name=None, host_name=None):
    """use the config to push paths to hosts 
    
    syncronize syncs by pulling or pushing sync's paths to hosts
     if None used as host_name with push method, sync syncronized 
     with all hosts, but in pull method it start syncing sync to
     hosts until a successful sync happens.

    args:
        method_name: string contain name of method use which used to syncronize. most be 'pull' or 'push'
        config: config object that used to find syncs and hosts
        sync_name: name of sync to syncronize. if  None used all sync will syncronized
        host_name: name of host to syncronize with.

    return: list of tuple (sync, host, failed_paths)
    """

    failed_syncs = []
    # find sync
    syncs = find_syncs(config, sync_name)

    for sync in syncs:
        # find host
        remote_hosts = find_hosts(sync,  host_name)

        for host in remote_hosts:
            logger.info('Syncronize (%s) %s with %s:', method_name.title(), sync['name'], host['name'])
            failed_paths = syncronize_host(
                method_name, host, sync['paths'], sync['recursive'], sync['tags'])

            if failed_paths:
                failed_syncs.append((sync, host, failed_paths))
                logger.error(
                    'Be careful paths partialy synced try to sync with another host')
            else:
                logger.info(
                    'Local system successfully synced with %s', host['name'])
                # after one successful pull stop pulling from other hosts
                if method_name == 'pull':
                    break

    return failed_syncs

def find_syncs(config, sync_name=None):
    """ return list of syncs 
    
    if sync_name specified return a list with sync equal to sync_name
    if sync_name is None it return list off all syncs

    """
    if sync_name is None:
        syncs = config['syncs']
    else:
        sync_name = sync_name.lower()
        syncs = [x for x in config['syncs'] if x['name'] == sync_name]

    return syncs


def find_hosts(sync, host_name=None):

    if host_name is None:
        remote_hosts = sync['hosts']
    else:
        host_name = host_name.lower()
        remote_hosts = [x for x in sync['hosts']
                         if x['name'] == host_name]

    return remote_hosts

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

def add_sync(config, **kwargs):
    """ add new sync to config

    args:
        config: configuration object
        name: sync name
        paths: list of paths of syncs
        tags: list of tags
        recursive: True or False
    """
    if kwargs['name'] is None:
        logger.critical('name is necessary')
        return False
    if kwargs['paths'] is None:
        kwargs['paths'] = []
    if kwargs['tags'] is None:
        kwargs['tags'] = []
    if kwargs['recursive'] is None:
        kwargs['recursive'] = config['recursive']

    sync = {'name': kwargs['name'],
            'paths': kwargs['paths'],
            'tags': kwargs['tags'],
            'recursive': kwargs['recursive'],
            'hosts': []
        }

    config['syncs'].append(sync)

    return True

def add_host(config, **kwargs):
    """ add new sync to config

    args:
        config: configuration object
        sync_name: sync name
        name: name of host
        paths: list of host paths
        address: host address
        user: user of host to connect. default: current user
        recursive: True or False
    """
    if kwargs['sync_name'] is None:
        logger.critical('sync name is necessary')
        return False
    if kwargs['paths'] is None:
        kwargs['paths'] = []
    if kwargs['user'] is None:
        kwargs['user'] = getpass.getuser()

    sync = get_sync(config, kwargs['sync_name'])
    if sync is None:
        logger.critical("there is no sync with name %s", kwargs['sync_name'])
        return False

    host = {'paths': kwargs['paths'],
            'user': kwargs['user'],
        }

    if kwargs['name'] is not None:
        host['name'] = kwargs['name'].lower()
        merge_host(config['hosts'], host)
    # override global host address after merge
    if kwargs['address'] is not None:
        host['address'] = kwargs['address'].lower()
    # check if address added by fucntion argument or merging with global host
    if 'address' in host:
        # set address as default name
        if 'name' not in host:
            host['name'] = host['address'].lower()
    else:
        logger.critical('address is not defined for host')
        return False

    if sync.get('hosts', None) is None:
        sync['hosts'] = []
    sync['hosts'].append(host)

    return True

def add_global_host(config, **kwargs):
    """ add global host

    add global host to global config
    
    args:
        config: configuration object
        name: name of host
        address: host address
        user: user of host to connect. default: current user
    """

    if kwargs['user'] is None:
        kwargs['user'] = getpass.getuser()

    host = {'name': kwargs['name'],
            'user': kwargs['user'],
            }
    # if address defined
    if kwargs['address'] is not None:
        host['address'] = kwargs['address'].lower()
        # set default name
        if kwargs['name'] is not None:
            host['name'] = kwargs['name'].lower()
        else:
            host['name'] = host['address']
    else:
        logger.critical('address is not defined for host')
        return False

    if config.get('hosts', None) is None:
        config['hosts'] = []
    
    config['hosts'].append(host)
    return True

def save_config(path, config):
    """ save config to path """
    yaml_conf = yaml.dump(config, default_flow_style=False)
    with open(path, 'w') as f:
        f.write(yaml_conf)
    return True

def set_tags(config, tags):
    """ set gloabal tags setting in config """
    config['tags'] = tags
    return True

def set_recursive(config, recursive):
    """ set global recursive setting in config """
    config['recursive'] = recursive
    return True

def remove_global_host(config, name):
    """ remove global host """
    config['hosts'].remove(get_global_host(config, name))
    return True

def remove_sync(config, name):
    """ remove sync """
    config['syncs'].remove(get_sync(config, name))
    return True

def remove_host(config, sync_name, name):
    """ remove sync """
    sync = get_sync(config, name)
    sync['hosts'].remove(get_host(config, sync_name, name))
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
    parser_push.add_argument('--sync-name', dest='sync_name', default=None)
    parser_push.add_argument('--host-name', dest='host_name', default=None)

    parser_pull = subparsers.add_parser('pull', help='pull paths from a host')
    parser_pull.set_defaults(action='pull')
    parser_pull.add_argument('--sync-name', dest='sync_name', default=None)
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
    if 'config' in args:
        config, config_path = load_config(args.config)
    else:
        config, config_path = load_config()

    if config is None:
        exit(1)
    
    if not validate_config(config):
        logger.critical('config error')
        exit(1)
    if args.action == 'list':
        list_syncs(config)
    if args.action in ['push', 'pull']:
        syncronize_syncs(args.action, config, args.sync_name, args.host_name)
    # if args.action == 'push':
    #     push_sync(config, args.sync_name, args.host_name)
    # if args.action == 'pull':
    #     pull_sync(config, args.sync_name, args.host_name)

if __name__ == '__main__':
    main()
