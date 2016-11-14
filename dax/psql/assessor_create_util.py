__author__ = 'damons'
import psycopg2
import sys
import re
import datetime


def get_connection(dbname='xnat', user='xnat', password='', host=''):
    """

    :param dbname: The postgres database name
    :param user: The postgres username
    :param password: The associated password with the postgres user
    :return: psycopg2 connection object
    """
    try:
     conn = psycopg2.connect(dbname=dbname,
                             password=password, user=user,
                             host=host)
    except psycopg2.OperationalError:

     print "FATAL: Caught an OperationalError. Please check your dbname, " \
           "host ip address, username, and password"
     sys.exit(1)
    return conn

def get_cursor(connection):
    """

    :param connection: psycopg2 Connection object
    :return: Re
    """

    return connection.cursor()

def get_user_id_by_name(cursor, name):
    """

    :param cursor:
    :param name:
    :return:
    """

    cursor.execute("""SELECT xdat_user_id from xdat_user where login=%s""", name)
    result = cursor.fetchone()
    return result[0]

def get_xdat_change_info_id(cursor):
    """

    :param cursor:
    :return:
    """
    cursor.execute("""SELECT nextval('public.xdat_change_info_xdat_change_info_id_seq') AS xdat_change_info_id""")
    result = cursor.fetchall()
    return result[0]

def get_experimentdata_meta_data_id(cursor):
    """

    :param cursor:
    :return:
    """
    cursor.execute("""SELECT nextval('public.xnat_experimentdata_meta_data_meta_data_id_seq') AS meta_data_id""")
    result = cursor.fetchall()
    return result[0]

def get_deriveddata_meta_data_id(cursor):
    """

    :param cursor:
    :return:
    """
    cursor.execute("""SELECT nextval('public.xnat_deriveddata_meta_data_meta_data_id_seq') AS meta_data_id""")
    result = cursor.fetchall()
    return result[0]

def get_imageassesordata_meta_data_id(cursor):
    """

    :param cursor:
    :return:
    """
    cursor.execute("""SELECT nextval('public.xnat_imageassessordata_meta_data_meta_data_id_seq') AS meta_data_id""")
    result = cursor.fetchall()
    return result[0]

def get_procgenprocdata_meta_data_id(cursor):
    """

    :param cursor:
    :return:
    """
    cursor.execute("""SELECT nextval('public.proc_genprocdata_meta_data_meta_data_id_seq') AS meta_data_id""")
    result = cursor.fetchall()
    return result[0]

def insert_xnat_experimentdata_meta_data(conn, cursor, xft_version, meta_data_id):
    """

    :param cursor:
    :param xft_version:
    :param activation_date:
    :param row_last_modified:
    :param insert_date:
    :param meta_data_id:
    :return:
    """

    activation_date = get_timestamp()
    row_last_modified = activation_date
    insert_date = activation_date
    cmd = """INSERT INTO xnat_experimentData_meta_data (xft_version,status,activation_user_xdat_user_id,activation_date,row_last_modified,insert_date,modified,insert_user_xdat_user_id,meta_data_id,shareable) VALUES ((%s),'active',1,(%s),(%s),(%s),0,1,(%s),1)"""
    cursor.execute(cmd, (xft_version, activation_date, row_last_modified, insert_date, meta_data_id))
    conn.commit()

def insert_xnat_experimentdata(conn, cursor, experimentdata_info, label, project, id):
    """

    :param cursor:
    :return:
    """
    cmd="""INSERT INTO xnat_experimentData (experimentdata_info,label,project,extension,id) VALUES ((%s),(%s),(%s),586,(%s))"""
    cursor.execute(cmd,(str(experimentdata_info[0].__int__()),
                         label,
                         project,
                         id))
    conn.commit()

def insert_xnat_deriveddata_meta_data(conn, cursor, xft_version, meta_data_id):
    """

    :param conn:
    :param cursor:
    :param xft_version:
    :param meta_data_id:
    :return:
    """
    activation_date = get_timestamp()
    row_last_modified = activation_date
    insert_date = activation_date
    cmd="""INSERT INTO xnat_derivedData_meta_data (xft_version,status,activation_user_xdat_user_id,activation_date,row_last_modified,insert_date,modified,insert_user_xdat_user_id,meta_data_id,shareable) VALUES ((%s),'active',1,(%s),(%s),(%s),0,1,(%s),1)"""
    cursor.execute(cmd, (xft_version, activation_date, row_last_modified, insert_date, meta_data_id))
    conn.commit()

def insert_xnat_deriveddata(conn, cursor, deriveddata_info,experiment_id):
    """

    :param cursor:
    :return:
    """
    cmd="""INSERT INTO xnat_derivedData (deriveddata_info,id) VALUES ((%s),(%s))"""
    cursor.execute(cmd, (deriveddata_info, experiment_id))
    conn.commit()

def insert_xnat_imageassessordata_meta_data(conn,cursor, xft_version, meta_data_id):
    """
    :param cursor:
    :return:
    """
    activation_date = get_timestamp()
    row_last_modified = activation_date
    insert_date = activation_date
    cmd = """INSERT INTO xnat_imageAssessorData_meta_data (xft_version,status,activation_user_xdat_user_id,activation_date,row_last_modified,insert_date,modified,insert_user_xdat_user_id,meta_data_id,shareable) VALUES ((%s),'active',1,(%s),(%s),(%s),0,1,(%s),1)"""
    cursor.execute(cmd, (xft_version, activation_date, row_last_modified, insert_date, meta_data_id))
    conn.commit()

def insert_xnat_imageassessordata(conn, cursor, meta_data_id, assessor_id, session_id):
    """

    :param cusor:
    :return:
    """
    cmd = """INSERT INTO xnat_imageAssessorData (imageassessordata_info,id,imagesession_id) VALUES ((%s),(%s),(%s))"""
    cursor.execute(cmd, (meta_data_id, assessor_id, session_id))
    conn.commit()

def insert_proc_genprocdata_meta_data(conn,cursor, xft_version, meta_data_id):
    """
    :param cursor:
    :return:
    """
    activation_date = get_timestamp()
    row_last_modified = activation_date
    insert_date = activation_date
    cmd = """INSERT INTO proc_genProcData_meta_data (xft_version,status,activation_user_xdat_user_id,activation_date,row_last_modified,insert_date,modified,insert_user_xdat_user_id,meta_data_id,shareable) VALUES ((%s),'active',1,(%s),(%s),(%s),0,1,(%s),1)"""
    cursor.execute(cmd, (xft_version, activation_date, row_last_modified, insert_date, meta_data_id))
    conn.commit()

def insert_proc_genprocdata(conn, cursor, meta_data_id, experiment_id):
    """

    :param cursor:
    :return:
    """
    cmd = """INSERT INTO proc_genProcData (genprocdata_info,id) VALUES ((%s),(%s))"""
    cursor.execute(cmd, (meta_data_id, experiment_id))
    conn.commit()

def insert_need_inputs_status(conn,cursor,procstatus,proctype, experiment_id):
    """

    :param conn:
    :param cursor:
    :param experiment_id:
    :param proctype:
    :return:
    """
    cmd = """UPDATE proc_genProcData SET procstatus=(%s), proctype=(%s) WHERE id=(%s)"""
    cursor.execute(cmd, (procstatus, proctype, experiment_id))
    conn.commit()

def get_next_experiment_id(cursor):
    """
    These IDs should really be some sort of serial8 or something of the like,
    but this sorts the tuple to get the max value and then adds
    :param cursor:
    :param subject_ids:
    :return: the new ID (in a tuple)
    """
    cmd = """SELECT DISTINCT id FROM (SELECT id FROM xnat_experimentData WHERE id LIKE 'DEV_VUIISXNAT99_E%' UNION SELECT DISTINCT id FROM xnat_experimentData_history WHERE id LIKE 'DEV_VUIISXNAT99_E%') SRCHA"""
    cursor.execute(cmd)
    experiment_ids = cursor.fetchall()
    # Sort here rather than using postgres to mimic XNAT
    experiment_ids.sort()
    try:
        last_id = experiment_ids[len(experiment_ids)-1]
    except IndexError:
        last_id=('DEV_VUIISXNAT99_E00000',)

    # I don't know if numbers are OK in the XNAT instance name. Thus, split the
    #  '_' and take the last element
    tail_of_id = last_id[0].split('_')
    last_id_digits = re.findall(r'\d+', tail_of_id[len(tail_of_id)-1])

    # pop the last element of the tail_of_id to reconstruct the XNAT instance name
    tail_of_id.pop(len(tail_of_id)-1)

    # I don't know if the zeropadding is a hard limit. This mimics the current install
    new_id = "%s_E%05d" % ('_'.join(tail_of_id), int(last_id_digits[0])+1)
    return (new_id,)


def get_timestamp():
    """
    :return: timestamp
    """
    return datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

def get_timestamp_from_datetime_object(obj):
    """

    :param obj:
    :return:
    """
    return obj.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

def check_if_project_exits(cursor, project_id):
    """

    :param cursor:
    :param project_id:
    :return:
    """
    cmd = """SELECT id from xnat_projectdata WHERE id=(%s)"""
    cursor.execute(cmd, (project_id,))
    res = cursor.fetchall()
    if res:
        return True
    else:
        return False


def check_if_subject_exists(cursor, project_id, subject_label):
    """

    :param cursor:
    :param project_id:
    :param subject_label:
    :return:
    """
    cmd = """SELECT id from xnat_subjectdata where project=(%s) AND label=(%s)"""
    cursor.execute(cmd, (project_id, subject_label,))
    res = cursor.fetchall()
    if res:
        return True
    else:
        return False

def check_if_experiment_exists(cursor, project_id,experiment_label):
    """

    :param cursor:
    :param project_id:
    :param experiment_label:
    :return:
    """
    cmd = """SELECT id from xnat_experimentdata where project=(%s) AND label=(%s)"""
    cursor.execute(cmd, (project_id, experiment_label,))
    res = cursor.fetchall()
    if res:
        return True
    else:
        return False

def check_if_assessor_exists(cursor, project_id, assessor_label):
    """

    :param cursor:
    :param project_id:
    :param assessor_label:
    :return:
    """
    cmd = """SELECT id from xnat_experimentdata where project=(%s) AND label=(%s)"""
    cursor.execute(cmd, (project_id, assessor_label,))
    res = cursor.fetchall()
    if res:
        return True
    else:
        return False

def check_if_xsitype_exists(cursor, xsitype):
    """

    :param cursor:
    :param xsitype:
    :return:
    """
    # bad idea to pass in table names. So we have them hard coded
    cmd = get_statement_from_xsitype(xsitype)
    if cmd is None:
        return False
    else:
        try:
            cursor.execute(cmd)
            return True
        except psycopg2.ProgrammingError:
            return False

def get_experiment_id_from_label(cursor, project_id, experiment_label):
    """

    :param cursor:
    :param project_id:
    :param experiment_label:
    :return:
    """
    cmd = """SELECT id FROM xnat_experimentdata where project=(%s) and label=(%s)"""
    cursor.execute(cmd, (project_id, experiment_label,))
    result = cursor.fetchone()
    return result

def execute_wrapper(cursor, template, values):
    """
    Wrap the execution of a statement and catch the base class error.

    :param cursor: psycopg2
    :param template: string template of a SQL statement
    :param values: tuple of values to insert into the SQL template
    :return: None
    """
    try:
        cursor.execute(template,values)
    except psycopg2.Error as e:
        sys.stderr.write('[ERROR]: Caught psycopg2 error code %s\n' % e.pgcode)
        sys.stderr.write('[ERROR]: Message is %s\n' % e.pgerror)
        # TODO
        # Should we cache everything that is done so we can "undo" it on exception?
        sys.exit(1)


def get_statement_from_xsitype(xsitype):
    """
    Map between the xsitype and the statement to see if the table exists. Can't
    insert table name dynamically so these are hard coded
    :param xsitype:
    :return:
    """
    mp = {'proc:genProcData': """SELECT 1 from proc_genprocdata""",
          'fs:fsData': """SELECT 1 from fs_fsdata"""}
    if xsitype not in mp.keys():
        return None
    else:
        return mp[xsitype]

