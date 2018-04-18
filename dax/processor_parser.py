
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
    return _get_args(statement)


def _register_iteration_references(name, iteration_args, iteration_sources,
                                   iteration_map):
    if iteration_args[0] == 'foreach':
        if len(iteration_args) == 1:
            iteration_sources.add(name)
        else:
            iteration_map[name] = iteration_args[1]


def _register_input_types(input_types, inputs_by_type, name):
    for t in input_types:
        ts = inputs_by_type.get(t, set())
        ts.add(name)
        inputs_by_type[t] = ts


# TODO: BenM/general refactor/update yaml schema so scan name is an explicit
# field
def _input_name(scan):
    candidates = list(filter(lambda v: v[1] is None, scan.iteritems()))
    if len(candidates) != 1:
        raise ValueError(
            "invalid scan entry format; scan name cannot be determined")
    return candidates[0][0]


def parse_inputs(yaml_source):

    inputs_by_type = {}
    iteration_sources = set()
    iteration_map = {}

    # get inputs: pass 1
    inputs = yaml_source['inputs']
    xnat = inputs['xnat']
    print 'xnat =', xnat

    # get scans
    scans = xnat.get('scans', list())
    for s in scans:
        name = _input_name(s)
        select = s.get('select', None)

        _register_iteration_references(name, _parse_select(select),
                                       iteration_sources, iteration_map)

        _register_input_types([_.strip() for _ in s['types'].split(',')],
                              inputs_by_type, name)

    # get assessors
    asrs = xnat.get('assessors', list())
    for a in asrs:
        name = _input_name(a)
        select = a.get('select', None)

        _register_iteration_references(name, _parse_select(select),
                                       iteration_sources, iteration_map)

        _register_input_types([_.strip() for _ in a['proctypes'].split(',')],
                              inputs_by_type, name)

    return inputs_by_type, iteration_sources, iteration_map


def map_artefact_to_inputs(artefact, inputs_by_type, artefacts_by_input):
    artefact_type = artefact.type()
    inputs_of_type = inputs_by_type.get(artefact_type, set())
    if len(inputs_of_type) > 0:
        # this artefact type is relevant to the assessor
        for i in inputs_of_type:
            artefacts = artefacts_by_input.get(i, [])
            artefacts.append(artefact.id())
            artefacts_by_input[i] = artefacts


def map_artefacts_to_inputs(csess, inputs_by_type):

    # a dictionary of input names to artefacts
    artefacts_by_input = {}

    for cscan in csess.scans():
        map_artefact_to_inputs(cscan, inputs_by_type, artefacts_by_input)

    for cassr in csess.assessors():
        map_artefact_to_inputs(cassr, inputs_by_type, artefacts_by_input)

    return artefacts_by_input


def generate_commands(command_template, inputs_by_type, iteration_sources,
                      artefacts_by_type, artefacts_by_input):

    # generate n dimensional input matrix based on iteration sources

    # generate 'zip' of inputs that are all attached to iteration source
