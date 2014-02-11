import fcntl
import select
import os
import re
import shlex
import tempfile
from contextlib import contextmanager
from subprocess import Popen, PIPE
from pyramid.threadlocal import get_current_registry

from almir.lib.utils import nl2br


CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
JOBS_DEF_RE = re.compile("""
                              \s+name=(?P<name>.+)\s+JobType
                              .+
                              level=(?P<level>\S*)
                              .+
                              Priority=(?P<priority>\d*)
                              .+
                              Client
                              .+
                              FileSet:\s+name=(?P<fileset>.*)\n
                              .+
                              Storage
                              .+
                              Pool
                              """, re.X)  # TODO: where/when


class BConsoleError(Exception):
    pass


class DirectorNotRunning(BConsoleError):
    pass


class BConsole(object):
    """Interface to bconsole binary"""
    # TODO: provide bconsole session through http request to avoid multiple connects in one http request which slow down performance

    def __init__(self, bconsole_command='bconsole -n -c %s', config_file=None):
        default_config_file = os.path.realpath(os.path.join(CURRENT_DIRECTORY, '..', '..', 'bconsole.conf'))
        registry = get_current_registry()
        self.config_file = config_file or registry.settings.get('bconsole_config',
                                                                default_config_file)
        self.bconsole_command = bconsole_command % self.config_file

    @classmethod
    @contextmanager
    def from_temp_config(cls, name, address, port, password):
        """Constructs :class:`BConsole` object with help of passing temporary file for the session.
        """
        with tempfile.NamedTemporaryFile() as f:
            template = os.path.join(CURRENT_DIRECTORY, '..', '..', 'buildout.d', 'templates', 'bconsole.conf.in')
            with open(template) as f2:
                config = f2.read()\
                           .replace('${almir:director_name}', name)\
                           .replace('${almir:director_port}', port)\
                           .replace('${almir:director_password}', password)\
                           .replace('${almir:director_address}', address)
            f.write(config)
            f.flush()
            yield cls(config_file=f.name)

    def start_process(self):
        return Popen(shlex.split(self.bconsole_command), stdout=PIPE, stdin=PIPE, stderr=PIPE)

    def is_running(self):
        try:
            self.get_version()
            return True
        except DirectorNotRunning:
            return False

    def get_version(self):
        p = self.start_process()
        stdout, stderr = p.communicate('version\n')
        version = filter(lambda s: 'Version' in s, stdout.split('\n'))
        if version:
            return version[-1]
        else:
            raise DirectorNotRunning

    def get_jobs_settings(self):
        p = self.start_process()
        stdout, stderr = p.communicate('show job')
        jobs = []
        for job in stdout.split('Job:'):
            jobs.append(JOBS_DEF_RE.find(stdout))
        return jobs

    def make_backup(self, job, level=None, storage=None, fileset=None, client=None, priority=None, pool=None, when=None):
        # TODO: figure out how to preselect options based on job definition (bat does it)
        # TODO: support 'where' for restore
        # TODO: support datetime for when
        # TODO: support parameters as database models instances
        cmd = 'run job=%s' % job

        if level:
            cmd += " level=%s" % level
        if storage:
            cmd += " storage=%s" % storage
        if fileset:
            cmd += " fileset=%s" % fileset
        if client:
            cmd += " client=%s" % client
        if priority:
            cmd += " priority=%s" % priority
        if pool:
            cmd += " pool=%s" % pool
        if when:
            cmd += " when=%s" % when

        p = self.start_process()
        stdout, stderr = p.communicate(cmd + "\nyes\n")
        if True:
            return "jobid"
        else:
            # TODO: stderr why job failed?
            return False

    def get_upcoming_jobs(self, days=1):
        """"""
        p = self.start_process()
        stdout, stderr = p.communicate('.status dir scheduled days=%d\n' % days)

        #if stderr.strip():
        #    pass  # TODO: display flash?

        try:
            unparsed_jobs = stdout.split('===================================================================================\n')[1].split('====\n')[0]
        except IndexError:
            return []
	fields = ('level', 'type', 'priority', 'date', 'time', 'name', 'volume')
        jobs = []
        for line in unparsed_jobs.split('\n'):
            if not line.strip():
                continue

	    jobs.append(dict(zip(fields, line.split())))

        return jobs

    def send_command_by_polling(self, command, process=None):
        """"""
        if command == 'quit':
            return process, {'commands': ['Try harder.']}

        # start bconsole session if it's not initialized
        if process is None:
            process = self.start_process()

        poll = process.poll()
        if poll is not None:
            process = None
            return process, {'error': 'Connection to director terminated with status %d. Refresh to reconnect.' % poll}

        # send bconsole command
        if command:
            process.stdin.write(command.strip().encode('utf-8') + '\n')

        # make stdout fileobject nonblockable
        fp = process.stdout.fileno()
        flags = fcntl.fcntl(fp, fcntl.F_GETFL)
        fcntl.fcntl(fp, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        output = ''

        while 1:
            # wait for data or timeout
            [i, o, e] = select.select([fp], [], [], 1)
            if i:
                # we have more data
                output += process.stdout.read(1000)
            else:
                # we have a timeout
                output = nl2br(output)

                return process, {"commands": [output]}
