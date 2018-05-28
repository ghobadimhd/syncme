# Pysyncme
Syncme is rsync wrapper that use simple yaml config file to trasfer file between hosts
and keep them sync. I write this keep my laptops syncing.

# Installation
## Ubuntu/linuxmint: 
```
# apt update 
# apt install rsync
# pip3 install syncme
```

# Configuration 
## config file location :
Syncme read config file from first path listed below:

* path specified by -c option
* SYNCME_CONFIG enviroment variable
* ~/.syncme.yml
* ~/.config/syncme.yml
* /etc/syncme.yml

## Configuring Syncme 
Configuring Syncme is pretty simple. There are three group of settings: 
### Global settings 
* recursive: if this set True the '-r' option added to rsync command and paths transfered recursively. You can override this in syncs.
* tags: list of default options that most added to rsync command. You can override this in syncs.
example: 
```yaml
---
recursive: True
tags:
  - '-v'
  - '--perms'
```

### Global hosts (optional):
You can define a list of host and refer them in syncs whith *hosts* setting.
each host consists of these settings: 
* name (optional): name of host. this is used in syncs to refer to host and in output. default value is host *address*.
* address (required): address of host. this setting is mandatory.
* user (optional): ssh user that used to connect to host. default is current user.

example:
```yaml
---
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

```
### Syncs
This is most important setting in file. *Syncs* setting is list of Syncs and each Sync mainly consists of a list of local paths and a list of hosts.

* paths (required): Paths in syncs follow same syntax as rsync paths. If a path ends whith '/' the content of the directory will transfered.

* hosts (required): hosts to Sync with. Hosts are same as global hosts except that they may have one extra setting, paths in hosts is a lists of destination paths. If paths not defined in host, local path used for destination. Also syncs hosts can override the global hosts.

Note: Trailing slashed copied to or removed from remote hosts paths.
this couse same content and file transfered to local when we call pull command.

Note: tags and recursive setting may defined in syncs and override global settings.

Example:
```yaml
---
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
```
# Command
## Pushing and Pulling
After configuring Syncme you use *push* subcommand to transfer file to hosts. use --sync-name and --host-name to transfer paths from specific Sync to specific host. default for these options is *all*.
```
syncme push # transfer path from  all Sync's to all hosts
syncme push --sync-name default.
```
Also you can use pull to transfer paths from hosts. If you don't use *--host-name* Syncme try to pull from hosts one by one until a successfull pull. If you don't use *--sync-name* thing happen to all Sync's.
```
syncme pull
```

## list
You can use list subcommand to list current config.
```
syncme list
```
