import os
import random
import hashlib
import pkg_resources

from pyramid_beaker import BeakerSessionFactoryConfig
from pyramid.config import Configurator
from pyramid.events import BeforeRender
from pyramid.httpexceptions import HTTPError
from sqlalchemy.dialects import sqlite
from sqlalchemy.types import INTEGER

from almir.meta import initialize_sql


try:
    __version__ = pkg_resources.get_distribution("almir").version
except:
    __version__ = ''


def navigation_tree(event):
    """Generate navigation data"""
    request = event['request']
    if not request:
        # debugger does not provide request
        return  # PRAGMA: no cover
    event['navigation_tree'] = [
        dict(name="Dashboard", url=request.route_url('dashboard')),
        dict(name="Clients", url=request.route_url('client_list')),
        # TODO: add later dict(name="FileSets", url=request.route_url('fileset_list')),
        dict(name="Jobs", url=request.route_url('job_list')),
        dict(name="Volumes", url=request.route_url('volume_list')),
        dict(name="Pools", url=request.route_url('pool_list')),
        dict(name="Storages", url=request.route_url('storage_list')),
        dict(name="Logs", url=request.route_url('log')),
        dict(name="Console", url=request.route_url('console')),
    ]

    try:
        event['current_url'] = request.current_route_url()
    except ValueError:
        event['current_url'] = ''


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application. """
    # provide aliases for sqlite types
    # to silence warnings
    sqlite.base.ischema_names['TINYINT'] = INTEGER
    sqlite.base.ischema_names['BIGINT'] = INTEGER

    initialize_sql(settings)

    config = Configurator(settings=settings)
    config.include('pyramid_jinja2')
    config.include('pyramid_tm')
    config.include('pyramid_beaker')
    config.include('deform_bootstrap')

    # setup beaker
    beaker_dict = dict(
                   type="memory",
                   lock_dir=os.path.join(global_config.get('here', '.'), 'session_lock'),
                   secret=hashlib.sha1(str(random.getrandbits(100))).hexdigest(),
                   )
    config.set_session_factory(BeakerSessionFactoryConfig(**beaker_dict))

    # events
    config.add_subscriber(navigation_tree, BeforeRender)

    # static
    config.add_static_view('static', 'almir:static', cache_max_age=3600)
    config.add_static_view('static_deform', 'deform:static')

    # routes
    config.add_route('dashboard', '/')
    config.add_view('almir.views.dashboard',
                    route_name='dashboard',
                    renderer='templates/dashboard.jinja2')
    config.add_route('about', '/about/')
    config.add_view('almir.views.about',
                    route_name='about',
                    renderer='templates/about.jinja2')
    config.add_route('log', '/log/')
    config.add_view('almir.views.LogView',
                    attr="list",
                    route_name='log',
                    renderer='templates/log.jinja2')
    config.add_route('console', '/console/')
    config.add_view('almir.views.console',
                    route_name='console',
                    renderer='templates/console.jinja2')
    config.add_route('console_ajax', '/console/input/')
    config.add_view('almir.views.ajax_console_input',
                    route_name='console_ajax',
                    renderer='json',
                    request_method='POST')
    config.add_route('datatables', '/datatables/')
    config.add_view('almir.views.datatables',
                    route_name='datatables',
                    renderer='json',
                    request_method='GET')

    config.add_route('modify_storage', '/storage/modify')
    config.add_view('almir.views.modify_storage',
                    route_name='modify_storage',
                    request_method='POST')

    # exception handling views
    config.add_view('almir.views.httpexception',
                    context=HTTPError,
                    renderer='templates/httpexception.jinja2')
    config.add_notfound_view('almir.views.httpexception',
                             renderer='templates/httpexception.jinja2',
                             append_slash=True)

    # RESTful resources
    for name in ['job', 'client', 'storage', 'volume', 'pool']:
        for action, url in [('list', '/%s/' % name), ('detail', '/%s/{id:\d+}/' % name)]:
            config.add_route('%s_%s' % (name, action), url)
            config.add_view(
                'almir.views.%sView' % name.title(),
                route_name='%s_%s' % (name, action),
                attr=action,
                renderer='templates/%s_%s.jinja2' % (name, action),
            )

    return config.make_wsgi_app()
