#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os.path
from collections import OrderedDict

from fabric.api import env, task, cd
from fabric.contrib.files import uncomment, sed, upload_template

from niteoweb.fabfile.server import *

# the remote dir you want install almir to
# PLEASE DO NOT CHANGE (it will break the fabric method)
env.dir = '/home/almir/almir'

# where do you want to install the almir project
# env.host_string = '192.168.42.118'

# this are the settings that will be rendered into the almir buildout.cfg file

env.tmp_context = {
    'db': {
        'username': 'bacula',
        'password': 'secret',
        'host': 'localhost',
        'name': 'bacula'
        },
    'timezone': 'CET',
    'almir': {
        'listen_ip': '0.0.0.0',
        'port': '8080',
        'dir_name': 'bacula_dir',
        'dir_port': '9101',
        'dir_address': 'localhost',
        # bacula director password
        'bc_password': 'secret'
    }
}

@task
def install_almir():
    """Installation of almir (bacula web interface)."""

    # Enforce the usage of utf-8 when client reads
    sed('/etc/postgresql/8.4/main/postgresql.conf',
        "#client_encoding = sql_ascii",
        "client_encoding = utf8",
        use_sudo=True)

    # Install git (install deps) and bacula console (deps)
    sudo('apt-get -yq install '
        'git '
        'bacula-console ')
    # !! WARNING !! new group will be created
    sudo('groupadd projects || true')
    # !! WARNING !! new user will be created
    create_project_user("almir")
    sudo('mkdir -p %s' % env.dir, user='almir')
    with cd(env.dir):
        #sudo('', user='almir')
        sudo('ls')
        sudo('git clone https://github.com/iElectric/almir.git -b latests .', user='almir')
        sudo(r'echo -e "[buildout]\nextends = buildout.d/production.cfg" > buildout.cfg', user='almir')
        sudo('python bootstrap.py', user='almir')
        upload_template('almir_buildout.cfg.jinja2', 'buildout.cfg', env.tmp_context, True, use_sudo=True)
        # export PYTHON_EGG_CACHE is necessary because sudo does not push the env variables
        # there is not a nicer way to push them with fabric
        # but there is a open feature request https://github.com/fabric/fabric/issues/263
        # python wants to set it to the home of the user running bin/fab
        # (doesn't matter if the user doesn't exist on the remote)
        sudo('export PYTHON_EGG_CACHE="/home/almir/.python-eggs"; bin/buildout', user='almir')
        sudo('export PYTHON_EGG_CACHE="/home/almir/.python-eggs"; bin/supervisord', user='almir')

