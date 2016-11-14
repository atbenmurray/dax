""" Task object to generate / manage assessors and cluster """
import os
import time
import logging
from datetime import date

from dax.psql import assessor_create_util
import cluster
from cluster import PBS
from dax_settings import DAX_Settings

DAX_SETTINGS = DAX_Settings()

#Logger to print logs
LOGGER = logging.getLogger('dax')

# Job Statuses
NO_DATA = 'NO_DATA'         # assessor that doesn't have data to run (for session assessor): E.G: dtiqa multi but no dti present.
NEED_TO_RUN = 'NEED_TO_RUN' # assessor that is ready to be launch on the cluster (ACCRE). All the input data for the process to run are there.
NEED_INPUTS = 'NEED_INPUTS' # assessor where input data are missing from a scan, multiple scans or other assessor.
JOB_RUNNING = 'JOB_RUNNING' # the job has been submitted on the cluster and is running right now.
JOB_FAILED = 'JOB_FAILED' # the job failed on the cluster.
READY_TO_UPLOAD = 'READY_TO_UPLOAD' # Job done, waiting for the Spider to upload the results
UPLOADING = 'UPLOADING' # in the process of uploading the resources on XNAT.
COMPLETE = 'COMPLETE' # the assessors contains all the files. The upload and the job are done.
READY_TO_COMPLETE = 'READY_TO_COMPLETE' # the job finished and upload is complete
DOES_NOT_EXIST = 'DOES_NOT_EXIST'
OPEN_STATUS_LIST = [NEED_TO_RUN, UPLOADING, JOB_RUNNING, READY_TO_COMPLETE, JOB_FAILED]
JOB_BUILT = 'JOB_BUILT'

# QC Statuses
JOB_PENDING = 'Job Pending' # job is still running, not ready for QA yet
NEEDS_QA = 'Needs QA' # job ready to be QA
GOOD = 'Good'  # QC status set by the Image Analyst after looking at the results.
PASSED_QA = 'Passed' # QC status set by the Image Analyst after looking at the results.
FAILED = 'Failed' # QC status set by the Image Analyst after looking at the results.
BAD = 'Bad' # QC status set by the Image Analyst after looking at the results.
POOR = 'Poor' # QC status set by the Image Analyst after looking at the results.
RERUN = 'Rerun' # will cause spider to delete results and rerun the processing
REPROC = 'Reproc' # will cause spider to zip the current results and put in OLD, and then processing
DONOTRUN = 'Do Not Run' # Do not run this assessor anymore
FAILED_NEEDS_REPROC = 'Failed-needs reprocessing' # FS
PASSED_EDITED_QA = 'Passed with edits' # FS
OPEN_QA_LIST = [RERUN, REPROC]
BAD_QA_STATUS = [FAILED, BAD, POOR, DONOTRUN]

# Other Constants
RESULTS_DIR = DAX_SETTINGS.get_results_dir()
DEFAULT_EMAIL_OPTS = DAX_SETTINGS.get_email_opts()
JOB_EXTENSION_FILE = DAX_SETTINGS.get_job_extension_file()



READY_TO_UPLOAD_FLAG_FILENAME = 'READY_TO_UPLOAD.txt'
OLD_RESOURCE = 'OLD'
EDITS_RESOURCE = 'EDITS'
REPROC_RES_SKIP_LIST = [OLD_RESOURCE, EDITS_RESOURCE]
INPUTS_DIRNAME = 'INPUTS'
BATCH_DIRNAME = 'BATCH'
OUTLOG_DIRNAME = 'OUTLOG'
PBS_DIRNAME = 'PBS'

class PSQLTask(object):
    """ Class Task to generate/manage the assessor with the cluster """
    def __init__(self, processor, assessor, upload_dir, psql_connection, psql_cursor):
        """
        Init of class Task

        :param processor: processor used
        :param assessor: assessor dict ?
        :param upload_dir: upload directory to copy data to after the job finishes.
        :return: None

        """
        self.processor = processor
        self.assessor = assessor
        self.upload_dir = upload_dir
        self.atype = processor.xsitype.lower()
        self.psql_connection = psql_connection
        self.psql_cursor = psql_cursor

        # Create assessor if needed
        if not assessor.exists():
            if self.atype == 'fs:fsdata':
                assessor.create(assessors='fs:fsData', **{'fs:fsData/fsversion':'0'})
            else:
                # assessor.create(assessors=self.atype) # old way
                PSQLTask.create(self)

            # TODO
            self.set_createdate_today()

            atype = self.atype.lower()
            if atype == 'proc:genprocdata':

                # TODO
                assessor.attrs.mset({atype +'/proctype':self.get_processor_name(),
                atype+'/procversion':self.get_processor_version()})

            self.set_proc_and_qc_status(NEED_INPUTS, JOB_PENDING)

        # Cache for convenience
        self.assessor_id = assessor.id()
        self.assessor_label = assessor.label()

    def get_processor_name(self):
        """
        Get the name of the Processor for the Task.

        :return: String of the Processor name.

        """
        return self.processor.name

    def get_processor_version(self):
        """
        Get the version of the Processor.

        :return: String of the Processor version.

        """
        return self.processor.version

    def is_open(self):
        """
        Check to see if a task is still in "Open" status as defined in
         OPEN_STATUS_LIST.

        :return: True if the Task is open. False if it is not open

        """
        astatus = self.get_status()
        return astatus in OPEN_STATUS_LIST

    def get_job_usage(self):
        """
        Get the amount of memory used, the amount of walltime used, the jobid
         of the process, the node the process ran on, and when it started
         from the scheduler.

        :return: List of strings. Memory used, walltime used, jobid, node used,
         and start date

        """
        atype = self.atype
        [memused, walltime, jobid, jobnode, jobstartdate] = self.assessor.attrs.mget(
            [atype+'/memused', atype+'/walltimeused', atype+'/jobid', atype+'/jobnode', atype+'/jobstartdate'])
        return [memused.strip(), walltime.strip(), jobid.strip(), jobnode.strip(), jobstartdate.strip()]

    def check_job_usage(self):
        """
        The task has now finished, get the amount of memory used, the amount of
         walltime used, the jobid of the process, the node the process ran on,
         and when it started from the scheduler. Set these values on XNAT

        :return: None

        """
        [memused, walltime, jobid, jobnode, jobstartdate] = self.get_job_usage()

        if walltime:
            if memused and jobnode:
                LOGGER.debug('memused and walltime already set, skipping')
            else:
                if memused == '':
                    self.set_memused('NotFound')
                if jobnode == '':
                    self.set_jobnode('NotFound')
            return

        # We can't get info from cluster if job too old
        if not cluster.is_traceable_date(jobstartdate):
            self.set_walltime('NotFound')
            self.set_memused('NotFound')
            self.set_jobnode('NotFound')
            return

        # Get usage with tracejob
        jobinfo = cluster.tracejob_info(jobid, jobstartdate)
        if jobinfo['mem_used'].strip():
            self.set_memused(jobinfo['mem_used'])
        else:
            self.set_memused('NotFound')
        if jobinfo['walltime_used'].strip():
            self.set_walltime(jobinfo['walltime_used'])
        else:
            self.set_walltime('NotFound')
        if jobinfo['jobnode'].strip():
            self.set_jobnode(jobinfo['jobnode'])
        else:
            self.set_jobnode('NotFound')

    def get_memused(self):
        """
        Get the amount of memory used for a process

        :return: String of how much memory was used

        """
        memused = self.assessor.attrs.get(self.atype+'/memused')
        return memused.strip()

    def set_memused(self, memused):
        """
        Set the amount of memory used for a process

        :param memused: String denoting the amount of memory used
        :return: None

        """
        self.assessor.attrs.set(self.atype+'/memused', memused)

    def get_walltime(self):
        """
        Get the amount of walltime used for a process

        :return: String of how much walltime was used for a process

        """
        walltime = self.assessor.attrs.get(self.atype+'/walltimeused')
        return walltime.strip()

    def set_walltime(self, walltime):
        """
        Set the value of walltime used for an assessor on XNAT

        :param walltime: String denoting how much time was used running
         the process.
        :return: None

        """
        self.assessor.attrs.set(self.atype+'/walltimeused', walltime)

    def get_jobnode(self):
        """
        Gets the node that a process ran on

        :return: String identifying the node that a job ran on

        """
        jobnode = self.assessor.attrs.get(self.atype+'/jobnode')
        return jobnode.strip()

    def set_jobnode(self, jobnode):
        """
        Set the value of the the node that the process ran on on the grid

        :param jobnode: String identifying the node the job ran on
        :return: None

        """
        self.assessor.attrs.set(self.atype+'/jobnode', jobnode)

    def undo_processing(self):
        """
        Unset the job ID, memory used, walltime, and jobnode information
         for the assessor on XNAT

        :except: pyxnat.core.errors.DatabaseError when attempting to
         delete a resource
        :return: None

        """
        from pyxnat.core.errors import DatabaseError

        self.set_qcstatus(JOB_PENDING)
        self.set_jobid(' ')
        self.set_memused(' ')
        self.set_walltime(' ')
        self.set_jobnode(' ')

        out_resource_list = self.assessor.out_resources()
        for out_resource in out_resource_list:
            if out_resource.label() not in REPROC_RES_SKIP_LIST:
                LOGGER.info('   Removing '+out_resource.label())
                try:
                    out_resource.delete()
                except DatabaseError:
                    LOGGER.error('   ERROR:deleting resource.')

    def reproc_processing(self):
        """
        If the procstatus of an assessor is REPROC on XNAT, rerun the assessor.

        :return: None

        """
        curtime = time.strftime("%Y%m%d-%H%M%S")
        local_dir = self.assessor_label+'_'+curtime
        local_zip = local_dir+'.zip'
        xml_filename = os.path.join(self.upload_dir, local_dir, self.assessor_label+'.xml')

        # Make the temp dir
        mkdirp(os.path.join(self.upload_dir, local_dir))

        # Download the current resources
        out_resource_list = self.assessor.out_resources()
        for out_resource in out_resource_list:
            olabel = out_resource.label()
            if olabel not in REPROC_RES_SKIP_LIST and len(out_resource.files().get()) > 0:
                LOGGER.info('   Downloading:'+olabel)
                out_res = self.assessor.out_resource(olabel)
                out_res.get(os.path.join(self.upload_dir, local_dir), extract=True)

        # Download xml of assessor
        xml = self.assessor.get()
        f = open(xml_filename, 'w')
        f.write(xml+'\n')
        f.close()

        # Zip it all up
        cmd = 'cd '+self.upload_dir + ' && zip -qr '+local_zip+' '+local_dir+'/'
        LOGGER.debug('running cmd:'+cmd)
        os.system(cmd)

        # Upload it to Archive
        self.assessor.out_resource(OLD_RESOURCE).file(local_zip).put(os.path.join(self.upload_dir, local_zip))

        # Run undo
        self.undo_processing()

        # TODO:
        # delete the local copies

    def update_status(self):
        """
        Update the satus of a Task object.

        :return: the "new" status (updated) of the Task.

        """
        old_status, qcstatus, jobid = self.get_statuses()
        new_status = old_status

        if old_status == COMPLETE or old_status == JOB_FAILED:
            if qcstatus == REPROC:
                LOGGER.info('   * qcstatus=REPROC, running reproc_processing...')
                self.reproc_processing()
                new_status = NEED_TO_RUN
            elif qcstatus == RERUN:
                LOGGER.info('   * qcstatus=RERUN, running undo_processing...')
                self.undo_processing()
                new_status = NEED_TO_RUN
            else:
                #self.check_date()
                pass
        elif old_status == NEED_TO_RUN:
            # TODO: anything, not yet???
            pass
        elif old_status == READY_TO_COMPLETE:
            self.check_job_usage()
            new_status = COMPLETE
        elif old_status == NEED_INPUTS:
            # This is now handled by dax_build
            pass
        elif old_status == JOB_RUNNING:
            new_status = self.check_running(jobid)
        elif old_status == READY_TO_UPLOAD:
            # TODO: let upload spider handle it???
            #self.check_date()
            pass
        elif old_status == UPLOADING:
            # TODO: can we see if it's really uploading???
            pass
        elif old_status == NO_DATA:
            pass
        else:
            LOGGER.warn('   * unknown status for '+self.assessor_label+': '+old_status)

        if new_status != old_status:
            LOGGER.info('   * changing status from '+old_status+' to '+new_status)

            # Update QC Status
            if new_status == COMPLETE:
                self.set_proc_and_qc_status(new_status, NEEDS_QA)
            else:
                self.set_status(new_status)

        return new_status

    def get_jobid(self):
        """
        Get the jobid of an assessor as stored on XNAT

        :return: string of the jobid

        """
        jobid = self.assessor.attrs.get(self.atype+'/jobid').strip()
        return jobid

    def get_job_status(self,jobid=None):
        """
        Get the status of a job given its jobid as assigned by the scheduler

        :param jobid: job id assigned by the scheduler
        :return: string from call to cluster.job_status or UNKNOWN.

        """
        jobstatus = 'UNKNOWN'
        if jobid == None:
            jobid = self.get_jobid()

        if jobid != '' and jobid != '0':
            jobstatus = cluster.job_status(jobid)

        return jobstatus

    def launch(self, jobdir, job_email=None, job_email_options=DAX_SETTINGS.get_email_opts(), xnat_host=None, writeonly=False, pbsdir=None):
        """
        Method to launch a job on the grid

        :param jobdir: absolute path to where the data will be stored on the node
        :param job_email: who to email if the job fails
        :param job_email_options: grid-specific job email options (e.g.,
         fails, starts, exits etc)
        :param xnat_host: set the XNAT_HOST in the PBS job
        :param writeonly: write the job files without submitting them
        :param pbsdir: folder to store the pbs file
        :raises: cluster.ClusterLaunchException if the jobid is 0 or empty
         as returned by pbs.submit() method
        :return: True if the job failed

        """
        cmds = self.commands(jobdir)
        pbsfile = self.pbs_path(writeonly, pbsdir)
        outlog = self.outlog_path()
        outlog_dir = os.path.dirname(outlog)
        mkdirp(outlog_dir)
        pbs = PBS(pbsfile, outlog, cmds, self.processor.walltime_str, self.processor.memreq_mb,
                  self.processor.ppn, job_email, job_email_options, xnat_host)
        pbs.write()
        if writeonly:
            mes_format = """   filepath: {path}"""
            LOGGER.info(mes_format.format(path=pbsfile))
            return True
        else:
            jobid = pbs.submit()

            if jobid == '' or jobid == '0':
                LOGGER.error('failed to launch job on cluster')
                raise cluster.ClusterLaunchException
            else:
                self.set_launch(jobid)
                return True

    def check_date(self):
        """
        Sets the job created date if the assessor was not made through
         dax_build

        :return: Returns if get_createdate() is != '', sets date otherwise

        """
        if self.get_createdate() != '':
            return

        jobstartdate = self.get_jobstartdate()
        if jobstartdate != '':
            self.set_createdate(jobstartdate)

    def get_jobstartdate(self):
        """
        Get the date that the job started

        :return: String of the date that the job started in "%Y-%m-%d" format

        """
        self.psql_cursor.execute("""SELECT jobstartdate from proc_genprocdata where label=(%s)""" % (self.assessor_label,))
        result = self.psql_cursor.fetchone()
        return result(0)


    def set_jobstartdate_today(self):
        """
        Set the date that the job started on the grid to today

        :return: call to set_jobstartdate with today's date

        """
        today_str = str(date.today())
        return self.set_jobstartdate(today_str)

    def set_jobstartdate(self, date_str):
        """
        Set the date that the job started on the grid based on user passed
         value

        :param date_str: Datestring in the format "%Y-%m-%d" to set the job
         starte date to
        :return: None

        """
        self.psql_cursor.execute("""UPDATE proc_genprocdata set jobstartdate=(%s) where label=(%s)""" % (date_str, self.assessor_label,))

    def get_createdate(self):
        """
        Get the date an assessor was created

        :return: String of the date the assessor was created in "%Y-%m-%d"
         format

        """
        self.psql_cursor.execute("""SELECT date from proc_genprocdata where label=(%s)""" % (self.assessor_label,))
        result = self.psql_cursor.fetchone()
        return result(0)
        # return self.assessor.attrs.get(self.atype+'/date')

    def set_createdate(self, date_str):
        """
        Set the date of the assessor creation to user passed value

        :param date_str: String of the date in "%Y-%m-%d" format
        :return: String of today's date in "%Y-%m-%d" format

        """
        self.psql_cursor.execute("""UPDATE proc_genprocdata set date=(%s) where label=(%s)""" % (date_str, self.assessor_label,))
        return date_str

    def set_createdate_today(self):
        """
        Set the date of the assessor creation to today

        :return: String of todays date in "%Y-%m-%d" format

        """
        today_str = str(date.today())
        self.psql_cursor.execute("""UPDATE proc_genprocdata set date=(%s) where label=(%s)""" % (today_str, self.assessor_label,))
        # self.set_createdate(today_str)
        return today_str

    def get_status(self, assessor_id):
        """
        Get the procstatus of an assessor

        :return: The string of the procstatus of the assessor.
         DOES_NOT_EXIST if the assessor does not exist

        """
        if not self.assessor.exists():
            xnat_status = DOES_NOT_EXIST
        elif self.atype == 'proc:genprocdata':
            self.psql_cursor.execute("""SELECT procstatus from proc_genprocdata WHERE id=(%s)""", (assessor_id,) )
            result = self.psql_cursor.fetchone()
            xnat_status=result(0)
        elif self.atype == 'fs:fsdata':
            self.psql_cursor.execute("""SELECT procstatus from fs_fsdata WHERE id=(%s)""", (assessor_id,) )
            result = self.psql_cursor.fetchone()
            xnat_status=result(0)
        else:
            xnat_status = 'UNKNOWN_xsiType:'+self.atype
        return xnat_status

    def get_statuses(self, assessor_id, validation_id):
        """
        Get the procstatus, qcstatus, and job id of an assessor

        :return: Serially ordered strings of the assessor procstatus,
         qcstatus, then jobid.
        """
        atype = self.atype
        if not self.exists():
            xnat_status = DOES_NOT_EXIST
            qcstatus = DOES_NOT_EXIST
            jobid = ''
        elif atype == 'proc:genprocdata' or atype == 'fs:fsdata':
            self.psql_cursor.execute("""SELECT procstatus,jobid from proc_genprocdata WHERE id=(%s)""", (assessor_id,) )
            result = self.psql_cursor.fetchall()
            xnat_status = result(0)
            jobid = result(1)

            self.psql_cursor.execute("""SELECT status from xnat_validationdata where xnat_validation_id=(%s)""")
            result =  self.psql_cursor.fetchone()

            qcstatus = result(0)
            # xnat_status, qcstatus, jobid = self.assessor.attrs.mget(
            #     [atype+'/procstatus', atype+'/validation/status', atype+'/jobid'])
        else:
            xnat_status = 'UNKNOWN_xsiType:'+atype
            qcstatus = 'UNKNOWN_xsiType:'+atype
            jobid = ''

        return xnat_status, qcstatus, jobid

    def set_status(self, status):
        """
        Set the procstatus of an assessor on XNAT

        :param status: String to set the procstatus of the assessor to
        :return: None

        """
        self.psql_cursor.execute("""UPDATE procgenprocdata SET procstatus=(%s) WHERE id=(%s)""" % (procstatus, assessor_id,))
        # self.assessor.attrs.set(self.atype+'/procstatus', status)

    def get_qcstatus(self, validation_id):
        """
        Get the qcstatus of the assessor

        :return: A string of the qcstatus for the assessor if it exists.
         If it does not, it returns DOES_NOT_EXIST.
         The else case returns an UNKNOWN xsiType with the xsiType of the
         assessor as stored on XNAT.
        """
        qcstatus = ''
        atype = self.atype

        if not self.exists():
            qcstatus = DOES_NOT_EXIST
        elif atype == 'proc:genprocdata' or atype == 'fs:fsdata':
            self.psql_cursor.execute(""" SELECT status FROM xnat_validationdata WHERE xnat_validation_id=(%s) """ %(validation_id))
            result = self.psql_cursor.fetchone()
            qcstatus = result(0)
        else:
            qcstatus = 'UNKNOWN_xsiType:'+atype

        return qcstatus

    def set_qcstatus(self, qcstatus, validation_id):
        """
        Set the qcstatus of the assessor

        :param qcstatus: String to set the qcstatus to
        :return: None

        """
        self.psql_cursor.execute("""UPDATE xnat_validationdata SET status=(%s) WHERE validation_id=(%s)""" % (qcstatus, validation_id))
        # self.assessor.attrs.mset({self.atype+'/validation/status': qcstatus,
        #                           self.atype+'/validation/validated_by':'NULL',
        #                           self.atype+'/validation/date':'NULL',
        #                           self.atype+'/validation/notes':'NULL',
        #                           self.atype+'/validation/method':'NULL'})

    def set_proc_and_qc_status(self, procstatus, qcstatus, assessor_id, validation_id):
        """
        Set the procstatus and qcstatus of the assessor

        :param procstatus: String to set the procstatus of the assessor to
        :param qcstatus: String to set the qcstatus of the assessor to
        :return: None

        """
        self.psql_cursor.execute("""UPDATE procgenprocdata SET procstatus=(%s) WHERE id=(%s)""" % (procstatus, assessor_id,))
        self.psql_cursor.execute("""UPDATE xnat_validationdata SET status=(%s) WHERE validation_id=(%s)""" % (qcstatus, validation_id))
        # self.assessor.attrs.mset({self.atype+'/procstatus':procstatus,
        #                          self.atype+'/validation/status':qcstatus})

    def set_jobid(self, jobid, assessor_id):
        """
        Set the job ID of the assessor on XNAT

        :param jobid: The ID of the process assigned by the grid scheduler
        :return: None

        """
        self.psql_cursor.execute("""UPDATE proc_genprocdata SET jobid=(%s) WHERE id=(%s)""" % (jobid, assessor_id,))
        # self.assessor.attrs.set(self.atype+'/jobid', jobid)

    def set_launch(self, jobid, assessor_id):
        """
        Set the date that the job started and its associated ID on XNAT.
        Additionally, set the procstatus to JOB_RUNNING

        :param jobid: The ID of the process assigned by the grid scheduler
        :return: None

        """
        today_str = str(date.today())
        # atype = self.atype.lower()
        self.psql_cursor.execute("""UPDATE proc_genprocdata SET (jobstartdate, jobid, procstatus) VALUES (%s,%s,%s); WHERE id=(%s)""" %(today_str, jobid, JOB_RUNNING,assessor_id))
        # self.assessor.attrs.mset({
        #     atype+'/jobstartdate':today_str,
        #     atype+'/jobid':jobid,
        #     atype+'/procstatus':JOB_RUNNING})

    def commands(self, jobdir):
        """
        Call the get_cmds method of the class Processor.

        :param jobdir: Fully qualified path where the job will run on the node.
         Note that this is likely to start with /tmp on most grids.
        :return: A string that makes a command line call to a spider with all
         args.

        """
        return self.processor.get_cmds(self.assessor, os.path.join(jobdir, self.assessor_label))

    def pbs_path(self, writeonly=False, pbsdir=None):
        """
        Method to return the path of the PBS file for the job

        :param writeonly: write the job files without submitting them in TRASH
        :param pbsdir: folder to store the pbs file
        :return: A string that is the absolute path to the PBS file that will
         be submitted to the scheduler for execution.

        """
        if writeonly:
            if pbsdir and os.path.isdir(pbsdir):
                return os.path.join(pbsdir, self.assessor_label+DAX_SETTINGS.get_job_extension_file())
            else:
                return os.path.join(os.path.join(DAX_SETTINGS.get_results_dir(), 'TRASH'), self.assessor_label+DAX_SETTINGS.get_job_extension_file())
        else:
            return os.path.join(os.path.join(DAX_SETTINGS.get_results_dir(), 'PBS'), self.assessor_label+DAX_SETTINGS.get_job_extension_file())

    def outlog_path(self):
        """
        Method to return the path of outlog file for the job

        :return: A string that is the absolute path to the OUTLOG file.
        """
        label = self.assessor_label
        return os.path.join(self.upload_dir, OUTLOG_DIRNAME, label+'.output')

    def ready_flag_exists(self):
        """
        Method to see if the flag file
        <UPLOAD_DIR>/<ASSESSOR_LABEL>/READY_TO_UPLOAD.txt exists

        :return: True if the file exists. False if the file does not exist.

        """
        flagfile = os.path.join(self.upload_dir, self.assessor_label, READY_TO_UPLOAD_FLAG_FILENAME)
        return os.path.isfile(flagfile)

    def check_running(self, jobid=None):
        """
        Check to see if a job specified by the scheduler ID is still running

        :param jobid: The ID of the job in question assigned by the scheduler.
        :return: A String of JOB_RUNNING if the job is running or enqueued and
         JOB_FAILED if the ready flag (see read_flag_exists) does not exist
         in the assessor label folder in the upload directory.

        """
        # Check status on cluster
        jobstatus = self.get_job_status(jobid)

        if not jobstatus or jobstatus == 'R' or jobstatus == 'Q':
            # Still running
            return JOB_RUNNING
        elif not self.ready_flag_exists():
            # Check for a flag file created upon completion, if it's not there then the job failed
            return JOB_FAILED
        else:
            # Let Upload Spider handle the upload
            return JOB_RUNNING

    def create(self):
        """
        Creates the assessor using psycopg2
        :return:
        """
        assessor = self.assessor_label
        xsi_type = self.atype

        assessor_label = assessor
        project_id = assessor_label.split('-x-')[0]
        subject_label = assessor_label.split('-x-')[1]
        experiment_label = assessor_label.split('-x-')[2]
        proctype = assessor_label.split('-x-')[-1]

        # Check that the project, subject, experiment, and assessor label exist
        if not assessor_create_util.check_if_project_exits(self.psql_cursor,
                                                           project_id):
            LOGGER.critical("Project ID %s does not exist. Cannot create "
                            "assessor %s" % (project_id,
                                             assessor_label))

        if not assessor_create_util.check_if_subject_exists(self.psql_cursor,
                                                            project_id,
                                                            subject_label):
            LOGGER.critical("Subject Label %s does not exist for Project ID %s."
                            " Cannot create assessor %s" % (subject_label,
                                                            project_id,
                                                            assessor_label))

        if not assessor_create_util.check_if_experiment_exists(self.psql_cursor,
                                                               project_id,
                                                               experiment_label):
            LOGGER.critical("Experiment Label %s does not exist for "
                            "Project ID %s. Cannot create assessor %s" %
                            (experiment_label, project_id, assessor_label))

        if assessor_create_util.check_if_assessor_exists(self.psql_cursor,
                                                         project_id,
                                                         assessor_label):
            LOGGER.critical("Assessor Label %s already exists for Project"
                            " ID %s. Cannot create." % (assessor_label,
                                                        project_id ))
        if not assessor_create_util.check_if_xsitype_exists(self.psql_cursor,
                                                            xsi_type):
            LOGGER.critical("xsitype %s does not exist. "
                            "Cannot create." % xsi_type)

        # By default set the procstatus to NEED_INPUTS so we can let dax_build handle the rest of the checking.
        procstatus='NEED_INPUTS'

        # Reserve a lot of the (metadata) ids
        experiment_id = assessor_create_util.get_next_experiment_id(self.psql_cursor)
        LOGGER.debug("Experiment ID is %s" % experiment_id)

        xdat_change_info_id = assessor_create_util.get_xdat_change_info_id(self.psql_cursor)
        LOGGER.debug("xdat change info id is %s" % xdat_change_info_id)

        xnat_experimentdata_meta_data_meta_data_id = assessor_create_util.get_experimentdata_meta_data_id(self.psql_cursor)
        LOGGER.debug("xnat_experimentdata_meta_data_meta_data_id is %s" % xnat_experimentdata_meta_data_meta_data_id)

        xnat_deriveddata_meta_data_id = assessor_create_util.get_deriveddata_meta_data_id(self.psql_cursor)
        LOGGER.debug("xnat_deriveddata_meta_data_id is %s " % xnat_deriveddata_meta_data_id)

        xnat_imageassessordata_meta_data_meta_data_id = assessor_create_util.get_imageassesordata_meta_data_id(self.psql_cursor)
        LOGGER.debug("xnat_imageassessordata_meta_data_meta_data_id is %s " % xnat_imageassessordata_meta_data_meta_data_id)

        proc_genprocdata_meta_data_meta_data_id = assessor_create_util.get_procgenprocdata_meta_data_id(self.psql_cursor)
        LOGGER.debug("proc_genprocdata_meta_data_meta_data_id is %s " % proc_genprocdata_meta_data_meta_data_id)

        # experimentdata
        assessor_create_util.insert_xnat_experimentdata_meta_data(self.psql_connection,self.psql_cursor,xdat_change_info_id,xnat_experimentdata_meta_data_meta_data_id)
        LOGGER.debug("Inserted xnat_experimentdata_meta_data")

        assessor_create_util.insert_xnat_experimentdata(self.psql_connection, self.psql_cursor, xnat_experimentdata_meta_data_meta_data_id, assessor_label, project_id, experiment_id)
        LOGGER.debug("Inserted xnat_experimentdata")

        # deriveddata
        assessor_create_util.insert_xnat_deriveddata_meta_data(self.psql_connection,self.psql_cursor,xdat_change_info_id, xnat_deriveddata_meta_data_id)
        LOGGER.debug("Inserted xnatderiveddata_meta_data")

        assessor_create_util.insert_xnat_deriveddata(self.psql_connection, self.psql_cursor, xnat_deriveddata_meta_data_id, experiment_id)
        LOGGER.debug("Inserted xnat_deriveddata")

        # image assessordata
        session_id = assessor_create_util.get_experiment_id_from_label(self.psql_cursor, project_id, experiment_label)
        LOGGER.debug("Session ID for xnat_image_assessor_data is %s" % session_id)

        assessor_create_util.insert_xnat_imageassessordata_meta_data(self.psql_connection, self.psql_cursor, xdat_change_info_id, xnat_imageassessordata_meta_data_meta_data_id)
        LOGGER.debug("Inserted xnat_imageassessordata_meta_data")

        assessor_create_util.insert_xnat_imageassessordata(self.psql_connection, self.psql_cursor, xnat_imageassessordata_meta_data_meta_data_id, experiment_id, session_id[0])
        LOGGER.debug("Inserted xnat_imageassessordata")

        # finally, the assesor type
        assessor_create_util.insert_proc_genprocdata_meta_data(self.psql_connection, self.psql_cursor, xdat_change_info_id, proc_genprocdata_meta_data_meta_data_id)
        LOGGER.debug("Inserted proc_genprocdata_metadata")

        assessor_create_util.insert_proc_genprocdata(self.psql_connection,self.psql_cursor,proc_genprocdata_meta_data_meta_data_id,experiment_id)
        LOGGER.debug("Inserted proc_genprocdata")

        assessor_create_util.insert_need_inputs_status(self.psql_connection,self.psql_cursor,procstatus,proctype, experiment_id)
        LOGGER.debug("Inserted NEED_INPUTS status")

    def exists(self):
        """
        Checks to see if the assessor exists
        :return:
        """
        return assessor_create_util.check_if_assessor_exists(self.psql_cursor,
                                                             self.assessor_label.split('-x-')[0],
                                                             self.assessor_label)
