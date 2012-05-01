#!/usr/bin/env python
# -*- coding: utf-8 -*-

from fabric.api import env, task, cd
from fabric.contrib.files import uncomment, sed, upload_template
from fabric.operations import prompt
from fabric.utils import abort
from fabric.colors import *

from niteoweb.fabfile.server import create_project_user

###
#Settings
###

# run almir as? (must be nonexisting user) (will be created)
# the whole home will be deleted if you run remove_almir !!
env.almir_user = 'almir'

# the remote dir you want install almir to (must be empty) (will be created)
env.dir = '/home/%s/almir' % env.almir_user

# where do you want to install the almir project
env.host_string = '192.168.42.118'

# select the sql type  !! WARNING !! this script was only tested with psql
# env.db = "psql" OR "mysql" OR "sqlite"
env.db = 'psql'

# this are the settings that will be rendered into the almir buildout.cfg file
env.tmp_context = {
    'db': {
        # just for MySQL and psql
        'username': 'bacula',
        'password': 'secret',
        'host': 'localhost',
        'name': 'bacula',
        # just for SQL
        'abs_path': '/var/db/bacula.db'
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

###
# Support functions
###


def legal_note():
    """Check if user agrees that we were drunk when writing this (docstring).
    If he does return None, else raise an abort exception.
    """

    print """
    This fabric script is just an example script, you should only use it as a reference.
    It was only tested on a Ubuntu 10.04.3 LTS with psql and it DOES NOT work on distributions other than Ubuntu.
    We are not responsable if this script, kills your server.
    You have read the script and you know the basics of Fabric project?
    """
    ans = prompt("(y,n,yes,no)", default='yes', validate='(y|Y|n|yes|no)')
    if ans in ('y', 'yes', 'Y'):
        return
    else:
        abort('You do not agree.')


def is_ubuntu():
    """Return True if distribution is Ubuntu,
    else raise abort exception.
    """

    distribution = sudo('lsb_release -is')
    print blue("checking distribution ...")
    if 'Ubuntu' == distribution:
        print green("OK ... distribution is %s" % distribution)
        return True
    else:
        print red("FAIL ... distribution is %s" % distribution)
        abort("Your distribution is not Ubuntu.")


def configure_for_psql():
    """Make changes needed psql to work."""

    # Enforce the usage of utf-8 when client reads
    sed('/etc/postgresql/8.4/main/postgresql.conf',
        "#client_encoding = sql_ascii",
        "client_encoding = utf8",
        use_sudo=True)
    with cd(env.dir):
        uncomment('buildout.cfg', 'postgresql')


def configure_for_sqlite():
    """Make changes needed sqlite to work."""

    with cd(env.dir):
        uncomment('buildout.cfg', 'sqlite')


def configure_for_mysql():
    """Make changes needed mysql to work."""

    with cd(env.dir):
        uncomment('buildout.cfg', 'mysql')

# map configure functions to dict
configure_fun = {
    'psql': configure_for_psql,
    'mysql': configure_for_mysql,
    'sqlite': configure_for_sqlite
}

###
# Tasks
###


@task
def install_almir():
    """Install almir (bacula web interface)"""

    legal_note()
    is_ubuntu()

    print blue('Install git and bconsole ... ')
    # Install git (install deps) and bacula console (deps)
    sudo('apt-get -yq install '
        'git '
        'bacula-console ')

    print blue('Create user ... ')
    # !! WARNING !! new group will be created
    sudo('groupadd projects || true')
    # !! WARNING !! new user will be created
    if sudo('grep -E %s /etc/passwd || true' % env.almir_user):
        abort('You must set a non existing user for almir project to run.')

    create_project_user(env.almir_user)

    print blue('Git clone last version ... ')
    sudo('mkdir -p %s' % env.dir, user=env.almir_user)
    with cd(env.dir):
        sudo('git clone https://github.com/iElectric/almir.git -b latests .', user=env.almir_user)
        sudo(r'echo -e "[buildout]\nextends = buildout.d/production.cfg" > buildout.cfg', user=env.almir_user)
        sudo('python bootstrap.py', user=env.almir_user)
        upload_template('almir_buildout.cfg.jinja2', 'buildout.cfg', env.tmp_context, True, use_sudo=True)

    print blue('Configure db settings ... ')
    configure_fun[env.db]()

    print blue('Install almir and deps ... ')
    with cd(env.dir):
        # export PYTHON_EGG_CACHE is necessary because sudo does not push the env variables
        # there is not a nicer way to push them with fabric
        # but there is a open feature request https://github.com/fabric/fabric/issues/263
        # python wants to set it to the home of the user running bin/fab
        # (doesn't matter if the user doesn't exist on the remote)
        sudo('export PYTHON_EGG_CACHE="/home/almir/.python-eggs"; bin/buildout', user=env.almir_user)
        sudo('export PYTHON_EGG_CACHE="/home/almir/.python-eggs"; bin/supervisord', user=env.almir_user)

    print blue('Almir installed !')


@task
def remove_almir():
    """Remove almir (bacula web interface)"""
    print blue('Remove almir and user: %s ... ' % env.almir_user)

    ans = prompt(red("This will delete the user and his home !!! (y,n,yes,no)"),
        default='yes', validate='(y|Y|n|yes|no)'
    )
    if ans in ('y', 'yes', 'Y'):
        pass
    else:
        abort('You do not agree.')

    # kill all almir processes
    sudo("pkill -u %s || true" % env.almir_user)

    # !! WARNING !! user will be deleted
    sudo("deluser --remove-home %s || true" % env.almir_user)
    # TODO: check if projects group is empty, if so then delete it

    print blue("Almir removed !")
