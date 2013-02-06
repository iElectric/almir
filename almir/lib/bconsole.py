import fcntl
import select
import os
import re
import shlex
import tempfile
from contextlib import contextmanager
from subprocess import Popen, PIPE

#from almir.lib.utils import nl2br
from utils import nl2br

import logging
log = logging.getLogger(__name__) 


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
        self.config_file = config_file or default_config_file
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

    def send_command(self, cmd):
        log.debug('Sending command to bconsole: %s' % cmd)
        p = self.start_process()
        stdout, stderr = p.communicate(cmd)
        log.debug('Command output by bconsole:')
        log.debug(stdout)
        # cleaning stdout from connection info
        # removing firsts four lines
#        for i in range(3):
#            stdout = stdout[:stdout.find('\n')] 

        # removinf you have messages. msg
        stdout = stdout.replace('You have messages.\n','') 
        return stdout

    def is_running(self):
        try:
            self.get_version()
            return True
        except DirectorNotRunning:
            return False

    def get_version(self):
        stdout = self.send_command('version\n')

        version = filter(lambda s: 'Version' in s, stdout.split('\n'))
        if version:
            return version[-1]
        else:
            raise DirectorNotRunning

    def get_jobs_settings(self):
        stdout = self.send_command('show job\n')

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

        stdout =  self.send_command(cmd + "\nyes\n")

        if True:
            return "jobid"
        else:
            # TODO: stderr why job failed?
            return False

    def get_disabled_jobs(self):
        # get the list of disabled jobs
        stdout = self.send_command('show disabled\n')

#        example of header: 
#        Disabled Jobs:
#        BackupCatalog
#


        try:
            unparsed_jobs = stdout.split('Disabled Jobs:\n')[1]
        except IndexError:
            return []

        disabled=[x.strip() for x in unparsed_jobs.split('\n') if len(x)>1] 

        jobs = []

        for job in disabled:
            jobs.append({'name': job,
            })

        return jobs
        
    def get_upcoming_jobs(self, days=1):
        """"""

        stdout = self.send_command('.status dir scheduled days=%d\n' % days)

        #if stderr.strip():
        #    pass  # TODO: display flash?

        try:
            unparsed_jobs = stdout.split('===================================================================================\n')[1].split('====\n')[0]
        except IndexError:
            return []

        jobs = []

        for line in unparsed_jobs.split('\n'):
            if not line.strip():
                continue

            jobs.append({
                         'level': line[:14].strip(),
                         'type': line[14:23].strip(),
                         'priority': line[23:28].strip(),
                         'date': line[28:38].strip(),
                         'time': line[38:44].strip(),
                         'name': line[47:67].strip(),
                         'volume': line[67:].strip(),
            })

        return jobs


    def mount_storage(self, storage, slot):
        """Mounts the volume contained in the slot *slot* on the storage *storage*"""

        cmd = 'mount=%s slot=%d\n' % (storage,slot)
        stdout = self.send_command(cmd)

        is_ok = stdout.find('is mounted')

        return is_ok != -1


    def unmount_storage(self, storage):
        """Unmounts the storage *storage*"""
        cmd = 'unmount=%s \n' % storage
        stdout = self.send_command(cmd)

        is_ok = stdout.find('unmounted')

        return is_ok != -1 


    def delete(self, volume=None, jobid=None):
        """Deletes an object"""

        if not volume and not jobid:
            return False # what you want to delete?

        if volume:
            cmd = ' volume=%s\nyes' % (volume)
        if jobid:
            cmd = ' jobid=%d ' % (jobid)

        cmd = 'delete %s \n' % cmd

        stdout = self.send_command(cmd)

        is_ok = stdout.find('deleted')

        return is_ok != -1 

    def create_label(self, pool, storage='', label = None, barcode = False ):
        """Create a new label"""

        if not label and not barcode:
            return False # we need or manual label or barcode

        cmd = 'label pool=%s storage=%s' % (pool,storage)
     
        if barcode:
            cmd += ( " barcode\n" )
        else:
            cmd += ( "\n%s\n" % label )

        stdout = self.send_command(cmd)

        is_ok = stdout.find('successfully created')

        return is_ok != -1 


    def enable_job(self, jobname ):
        """Enables job named as passed by argument"""

        cmd = 'enable job=%s\n' % jobname
        stdout = self.send_command(cmd)

        is_ok = stdout.find('enabled')

        return is_ok != -1 


    def disable_job(self, jobname):
        """Disables job named as passed by argument"""

        cmd = 'disable job=%s\n' % jobname
        stdout = self.send_command(cmd)

        is_ok = stdout.find('disabled')

        return is_ok != -1 


    def estimate_job(self, jobname ):
        """Estimates a job returns -1,-1 if something goes wrong"""

        cmd = 'estimate job=%s\n' % jobname
        stdout = self.send_command(cmd)

        try:
            retcode, files, bytes = re.findall('\\d+',stdout.replace(',',''))
        except ValueError:
            retcode = -1

        if int(retcode) != 2000:
            return -1,-1
        else:
            return int(files), int(bytes)


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

