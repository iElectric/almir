import logging
import collections

from deform import Form, ValidationFailure
from pyramid.interfaces import IRoutesMapper
from pyramid.settings import asbool
from pyramid.view import view_config
from pyramid.httpexceptions import HTTPMovedPermanently, HTTPFound

from sqlalchemy import String, LargeBinary
from sqlalchemy.sql.expression import desc, or_
from sqlalchemy.sql.functions import sum, count
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import InstrumentedAttribute

from almir.meta import DBSession, get_database_size
from almir.models import Job, Client, Log, Media, Storage, Pool, Status, File, Path, Filename
from almir.forms import JobSchema, MediaSchema, LogSchema
from almir.lib.console_commands import CONSOLE_COMMANDS
from almir.lib.bconsole import BConsole, DirectorNotRunning
from almir.lib.utils import render_rst_section, get_jinja_macro


log = logging.getLogger(__name__)


def dashboard(request):
    dbsession = DBSession()

    jobs = Job.get_last()
    running_jobs = Job.get_running()
    upcoming_jobs = Job.get_upcoming()
    try:
        director_version = '<span title="Connected to" class="label label-success">%s</span>' % BConsole().get_version()
    except DirectorNotRunning:
        director_version = '<span class="label label-important">Director not running!</span>'

    # statistics
    num_clients = dbsession.query(count(Client.clientid)).scalar()
    num_jobs = dbsession.query(count(Job.jobid)).scalar()
    num_volumes = dbsession.query(count(Media.mediaid)).scalar()
    sum_volumes = Media.format_byte_size(dbsession.query(sum(Media.volbytes)).scalar() or 0)
    database_size = get_database_size(DBSession.bind)

    return locals()


def about(request):
    changelog = render_rst_section('changelog.rst')
    about = render_rst_section('about.rst')
    return locals()


def console(request):
    command_array = ','.join(['"%s"' % name for name in CONSOLE_COMMANDS.keys()])
    console_commands = CONSOLE_COMMANDS
    return locals()


# restful generic view
class MixinView(object):
    model = None
    schema = None

    def __init__(self, request):
        self.request = request
        self.context = {
                        'appstruct': {},
        }

    def get_form(self):
        """Deals everything regarding forms for a request."""
        if not self.schema:
            return

        schema = self.schema()

        form = Form(schema.bind(**self.context),
                    buttons=[],
                    bootstrap_form_style='form-vertical')

        if self.request.query_string:
            controls = self.request.GET.items()

            try:
                self.context['appstruct'] = form.validate(controls)
                self.request.session[self.schema.__name__] = self.context['appstruct']
                self.request.session.save()
            except ValidationFailure, e:
                return e

        appstruct = self.request.session.get(self.schema.__name__, None)
        if appstruct:
            return form.render(appstruct)
        else:
            return form.render()

    def list(self):
        self.context['form'] = self.get_form()
        self.context['objects'] = self.model.get_list(appstruct=self.context['appstruct'])
        return self.context

    def detail(self):
        id_ = self.request.matchdict['id']
        self.context['object'] = self.model.get_one(id_)
        return self.context


class JobView(MixinView):
    model = Job
    schema = JobSchema

    def list(self):
        # TODO: cache this
        self.context['status_values'] = [('', '---')] + Status.get_values()
        return super(JobView, self).list()

    def detail(self):
        id_ = self.request.matchdict['id']
        self.context['files'] = File.query.filter(File.jobid == int(id_))\
                                          .options(joinedload('path'), joinedload('filename'))\
                                          .join('path').join('filename')
        return super(JobView, self).detail()

class ClientView(MixinView):
    model = Client

    def detail(self):
        # TODO: get jobs as join/subquery on client
        super(ClientView, self).detail()
        id_ = self.request.matchdict['id']
        jobs = Job.query.filter(Job.clientid == int(id_))
        self.context['jobs'] = jobs.options(joinedload(Job.status))\
                                   .order_by(desc(Job.schedtime))\
                                   .limit(50)  # TODO: dynamic datatables
        self.context['job_statistics'] = jobs.with_entities(count().label('num_jobs'), sum(Job.jobbytes).label('total_size_backups')).first(),
        self.context['last_successful_job'] = jobs.filter(Job.jobstatus == 'T').order_by(desc(Job.starttime)).first(),
        return self.context


class StorageView(MixinView):
    model = Storage


class VolumeView(MixinView):
    model = Media
    schema = MediaSchema

    def list(self):
        # UPSTREAM: we need to convert id to string, look at https://github.com/Pylons/deform/issues/81
        # TODO: cache
        self.context['storage_values'] = [('', '---')] + map(lambda x: (str(x[0]), x[1]), Storage.get_values())
        self.context['pool_values'] = [('', '---')] + map(lambda x: (str(x[0]), x[1]), Pool.get_values())
        return super(VolumeView, self).list()


class PoolView(MixinView):
    model = Pool


class LogView(MixinView):
    model = Log
    schema = LogSchema


bconsole_session = None
command_cache = collections.deque(maxlen=10)


def ajax_console_input(request):
    global bconsole_session
    # TODO: if status for client is requested, it might timeout after few seconds, but not 0.5
    # TODO: thread locking
    # TODO: implement session based on cookie
    # TODO: stderr?

    if not request.POST['bconsole_command'] and bconsole_session is not None:
        return {"commands": list(command_cache)}

    b = BConsole()
    bconsole_session, response = b.send_command_by_polling(request.POST['bconsole_command'], bconsole_session)

    if 'error' in response:
        command_cache.clear()

    if 'commands' in response:
        command_cache.extend(response['commands'])
    return response


def httpexception(context, request):
    request.response.status_int = context.code
    return {'context': context}


def datatables(request):
    """Implements server side interface for datatables.

    For field reference look at http://www.datatables.net/usage/server-side

    """
    link = get_jinja_macro('link')

    q = request.GET
    iDisplayStart = int(q.get('iDisplayStart'))
    iDisplayLength = int(q.get('iDisplayLength'))
    iColumns = int(q.get('iColumns'))
    sColumns = q.get('sColumns').split(',')
    sSearch = q.get('sSearch')
    #bRegex = q.get('bRegex')
    #iSortingCols = int(q.get('iSortingCols'))
    sEcho = int(q.get('sEcho'))

    # get view from referrer url
    for route in request.registry.getUtility(IRoutesMapper).routelist:
        match = route.match(q.get('referrer'))
        if match is not None:
            break

    for intro in request.registry.introspector.get_category('views'):
        if intro['introspectable']['route_name'] == route.name:
            break

    view = intro['introspectable']['callable'](request)
    # TODO: views will do form filtering, meaning total_records will give false information
    if intro['introspectable']['attr'] == 'list':
        query = view.list()[q.get('context', 'objects')]
    else:
        request.matchdict = match
        query = view.detail()[q.get('context', 'object')]

    # get model from query entity
    model = query._entities[0].mapper.class_

    total_records = query.count()
    search_filter = []

    for i in range(iColumns):
        mDataProp = q.get('mDataProp_%d' % i)
        try:
            field = sColumns[i] or mDataProp
        except IndexError:
            # no information about columns
            field = mDataProp

        # handle search
        bSearchable = asbool(q.get('bSearchable_%d' % i))
        if bSearchable:
            # TODO: handle regex
            # TODO: column specific search: col_sSearch = q.get('sSearch_%d' % i)
            # TODO refactor to models to provide generic search and edge cases for specific models
            if sSearch:
                if field == 'path.path;filename.name':
                    search_filter.append((Path.path + Filename.name).ilike('%' + sSearch + '%'))
                else:
                    column = getattr(model, field)
                    if isinstance(column.property.columns[0].type, (String, LargeBinary)):
                        search_filter.append(column.ilike('%' + sSearch + '%'))
                    # TODO: support more type searches

        # handle sorting
        iSortCol = q.get('iSortCol_%d' % i)
        bSortable = asbool(q.get('bSortable_%d' % i))
        if iSortCol and bSortable:
            # TODO refactor to models to provide generic ordering and edge cases for specific models
            for prop in field.split(';'):
                # get colum for sorting
                order_column = model
                for attr in prop.split('.'):
                    if isinstance(order_column, InstrumentedAttribute):
                        # handle relations
                        order_column = order_column.property.mapper.class_
                    order_column = getattr(order_column, attr)

                # sort
                if q.get('sSortDir_%d' % i) == 'desc':
                    query = query.order_by(desc(order_column))
                else:
                    query = query.order_by(order_column)

    query = query.filter(or_(*search_filter))
    total_display_records = query.count()

    aaData = []

    for result in query[iDisplayStart:iDisplayStart + iDisplayLength]:
        obj = {}
        for i in range(iColumns):
            mDataProp = q.get('mDataProp_%d' % i)
            options = getattr(result, 'render_%s' % mDataProp)(request) or {}
            obj[mDataProp] = link(options)
            if options.get('cssclass'):
                obj['DT_RowClass'] = options['cssclass']
        aaData.append(obj)

    return {
            'sEcho': sEcho,
            'iTotalDisplayRecords': total_display_records,
            'iTotalRecords': total_records,
            'aaData': aaData,
    }


def modify_storage(request):
    bc = BConsole()

    enderer='templates/storage_list.jinja2',

    storages = ['File',]

    log.debug('###################################')
    log.debug(request.params)
    log.debug('###################################')
    
    command = request.POST.get('command')
    if command == 'unmount':
        ret = {'okmsg':'Storage unmounted correctly'}
        for storage in storages:
            if not bc.unmount_storage(storage):
                msg = 'Error unmounting storage: %s' % storage
                log.info(msg)
                ret = {'errormsg':msg}
                break
    else:
        ret = {'okmsg':'Storage mounted correctly'}
        for storage in storages:
            if not bc.mount_storage(storage):
                msg = 'Error mounting storage: %s' % storage
                log.info(msg)
                ret = {'errormsg':msg}                
                break
    
    redirect_url = request.route_url('storage_list', _query=ret)
    response = HTTPFound(location=redirect_url)
    
    return response


