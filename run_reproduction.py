"""Reproduce material checks and the fixed regional illustration from this clone.

No paid solver, private measurements or unreported finished yield is needed.
Regional calculations require a local GISCO file under its separate terms.
"""
from pathlib import Path
import argparse
import subprocess
import sys
import json
import hashlib
import pandas as pd

ROOT=Path(__file__).resolve().parent

def command(*args):
    subprocess.run([sys.executable,*map(str,args)],cwd=ROOT,check=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--geometry-file',type=Path)
    p.add_argument('--raw-dir',type=Path)
    p.add_argument('--accept-gisco-noncommercial',action='store_true')
    p.add_argument('--regional-grid',action='store_true',help='Also run inherited full regional supplementary grids.')
    p.add_argument('--figures',action='store_true',help='Export native vector and 1200 dpi artwork after arithmetic checks.')
    a=p.parse_args()
    data=ROOT/'supplement/data';fq=ROOT/'supplement/functional_qualification';result=fq/'recomputed'
    params=['--output',data]
    if a.geometry_file:params += ['--geometry-file',a.geometry_file.resolve()]
    if a.raw_dir:params += ['--raw-dir',a.raw_dir.resolve()]
    if a.accept_gisco_noncommercial:params+=['--accept-gisco-noncommercial']
    command(ROOT/'scripts/prepare_geometry.py',*params)
    command(ROOT/'supplement/functional_qualification_v101.py','--data',fq,'--legacy',data,'--output',result)
    command(ROOT/'supplement/verify_functional_qualification_v101.py','--data',fq,'--result',result)
    comparisons={}
    for path in (fq/'computed').glob('*.csv'):
        newer=result/path.name
        pd.testing.assert_frame_equal(pd.read_csv(path),pd.read_csv(newer),check_exact=False,rtol=1e-10,atol=1e-10)
        comparisons[path.name]={'numeric_and_label_equality':'PASS','frozen_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    if a.regional_grid:command(ROOT/'supplement/replicate.py','--data',data,'--output',ROOT/'regional_recomputed')
    if a.figures:command(ROOT/'scripts/draw_nature_figures.py','--source',ROOT,'--output',ROOT/'artwork','--styles',ROOT/'style_sources')
    verification=json.loads((result/'independent_verification.json').read_text(encoding='utf8'))
    report={'status':'PASS','compared_tables':comparisons,'independent_verification':verification,
            'scope':'Arithmetic and implementation verification, not new experimental validation or EU qualification inference.'}
    (ROOT/'reproduction_report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({'status':'PASS','compared_tables':len(comparisons),'independent_verification':verification},indent=2))

if __name__=='__main__':main()
