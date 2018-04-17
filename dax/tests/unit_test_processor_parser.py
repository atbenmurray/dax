from unittest import TestCase

import StringIO
import yaml

from dax import processor_parser

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
        types: X2
        select: foreach(scan2)
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
        doc = yaml.load((StringIO.StringIO(scan_gif_parcellation_yaml)))
        processor_parser.generate(doc)
