
session_namespace = {
    'foreach': {'args': [{'optional': True, 'type': str}]},
    'one': {'args': []},
    'some': {'args': [{'optional': False, 'type': int}]},
    'all': {'args': []}
}


def _get_args(statement):
    leftindex = statement.find('(')
    rightindex = statement.find(')')
    if leftindex == -1 and rightindex == -1:
        return [statement]
    elif leftindex != -1 and rightindex != -1:
        return [statement[:leftindex]] +\
               [s.strip() for s in statement[leftindex+1:rightindex].split(',')]
    else:
        raise ValueError('statement is malformed')


def _parse_select(statement):
    if statement is None:
        statement = 'foreach'
    statement = statement.strip()
    print _get_args(statement)


# TODO: BenM/general refactor/update yaml schema so scan name is an explicit
# field
def _scan_name(scan):
    print 'scan =', scan
    candidates = list(filter(lambda v: v[1] is None, scan.iteritems()))
    if len(candidates) != 1:
        raise ValueError(
            "invalid scan entry format; scan name cannot be determined")
    return candidates[0][0]


def generate(yaml_source):

    scans_by_type = {}

    # get scans
    inputs = yaml_source['inputs']
    xnat = inputs['xnat']
    print 'xnat =', xnat

    scans = xnat.get('scans', list())
    for s in scans:
        name = _scan_name(s)
        select = s.get('select', None)
        print 'select =', select
        _parse_select(select)
        types = [_.strip() for _ in s['types'].split(',')]
        for t in types:
            ts = scans_by_type.get(t, set())
            print s
            ts.add(name)
            scans_by_type[t] = ts

    print 'scans_by_type =', scans_by_type


    # get assessors
    asrs = xnat.get('assessors', list())
    for a in asrs:
        select = a.get('select', None)
        print 'select =', select
