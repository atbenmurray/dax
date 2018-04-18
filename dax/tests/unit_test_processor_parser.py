from unittest import TestCase

import StringIO
import yaml

from dax import processor_parser


class TestArtefact:

    def __init__(self, id, artefact_type, quality):
        self.id_ = id
        self.artefact_type = artefact_type
        self.quality_ = quality

    def id(self):
        return self.id_

    def type(self):
        return self.artefact_type

    def quality(self):
        return self.quality_


class TestSession:

    def __init__(self, scans, assessors):
        self.scans_ = [TestArtefact(s[0], s[1], s[2]) for s in scans]
        self.assessors_ = [TestArtefact(a[0], a[1], a[2]) for a in assessors]

    def scans(self):
        return self.scans_

    def assessors(self):
        return self.assessors_


xnat_scan_contents = [
    ("1", "T1W", "usable"),
    ("2", "T1w", "usable"),
    ("10", "FLAIR", "usable"),
    ("11", "FLAIR", "usable"),
]


assessor_prefix = "proj1-x-subj1-x-sess1-x-"


xnat_assessor_contents = [
    (assessor_prefix + "1-x-proc1", "proc1", "usable"),
    (assessor_prefix + "2-x-proc1", "proc1", "usable")
]


scan_gif_parcellation_yaml = """
---
inputs:
  default:
    spider_path: /home/dax/Xnat-management/comic100_dax_config/pipelines/GIF_parcellation/v3.0.0/Spider_GIF_Parcellation_v3_0_0.py
    working_dir: /scratch0/dax/
    nipype_exe: perform_gif_propagation.py
    db: /share/apps/cmic/GIF/db/db.xml
  xnat:
    scans:
      - scan1:
        types: T1w,MPRAGE,T1,T1W
        resources:
          - resource: NIFTI
            varname: t1
      - scan2:
        types: X1
        select: foreach
      - scan3:
        types: FLAIR
        select: foreach(scan1)
      - scan4:
        types: X3
        select: one
      - scan5:
        types: X4
        select: some
      - scan6:
        types: X5
        select: some(3)
      - scan7:
        types: X6
        select: all
    assessors:
      - asr1:
        proctypes: gif_thing
        select: foreach(scan1)
        resources:
          - resource: SEG
          - varname: seg
command: python {spider_path} --t1 {t1} --dbt {db} --exe {nipype_exe}
attrs:
  suffix:
  xsitype: proc:genProcData
  walltime: 24:00:00
  memory: 3850
  ppn: 4
  env: /share/apps/cmic/NiftyPipe/v2.0/setup_v2.0.sh
  type: scan
  scan_nb: scan1
"""



class MyTestCase(TestCase):

    def test_processor_parser1(self):
        csess = TestSession(xnat_scan_contents, xnat_assessor_contents)

        doc = yaml.load((StringIO.StringIO(scan_gif_parcellation_yaml)))
        inputs_by_type, iteration_sources, iteration_map =\
            processor_parser.parse_inputs(doc)

        artefacts_by_input =\
            processor_parser.map_artefacts_to_inputs(csess, inputs_by_type)

        print "inputs_by_type =", inputs_by_type
        print "iteration_sources =", iteration_sources
        print "iteration_map =", iteration_map
        print "artefacts_by_input =", artefacts_by_input
