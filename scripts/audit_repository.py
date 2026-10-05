"""Audit the staged, bounded repository and record verification evidence."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

ROOT=Path(__file__).resolve().parent.parent
files=subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()
assert files
assert not any(Path(f).suffix.lower() in ['.pdf','.tex','.geojson','.zip','.tiff'] for f in files)
assert not any('recomputed' in f or 'article' in Path(f).name.lower() for f in files)
for name in ['country_geometry_caps.csv','anchor_distances_km.csv']:
    assert not any(Path(f).name==name for f in files),name
for name in files:
    if Path(name).suffix in ['.py','.json','.md','.csv']:
        content=(ROOT/name).read_text(encoding='utf8')
        assert not re.search(r'(?<![A-Za-z])[CDEF]:[\\/]',content),name
        assert not re.search(r'gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}',content),name
report=json.loads((ROOT/'reproduction_report.json').read_text(encoding='utf8'))
regional=json.loads((ROOT/'regional_recomputed/replication_verification.json').read_text(encoding='utf8'))
geometry=json.loads((ROOT/'supplement/data/geometry_reconstruction.json').read_text(encoding='utf8'))
assert report['status']=='PASS' and regional['status']=='pass'
assert geometry['canonical_geometry_matches_frozen_input']
audit={'audit_date':'2026-10-05','status':'PASS',
       'material_table_numeric_and_label_comparisons':len(report['compared_tables']),
       'independent_decimal_checks':report['independent_verification'],
       'regional_reproduction':{k:regional[k] for k in ['comparisons','cut_capacity_lp_checks','max_cut_lp_gap_t_y','numpy','pandas','scipy']},
       'fresh_official_geometry':{k:geometry[k] for k in ['source_url','source_sha256','frozen_raw_sha256','canonical_eu27_geometry_sha256','canonical_geometry_matches_frozen_input']},
       'no_manuscript_or_publisher_fulltext_published':True,'no_geometry_redistributed':True,
       'limitation':'Implementation/arithmetic checks; not independent experiments, EU qualification rates, service certification or journal acceptance.'}
(ROOT/'VALIDATION.json').write_text(json.dumps(audit,indent=2),encoding='utf8')
manifest=[{'path':n,'bytes':(ROOT/n).stat().st_size,'sha256':hashlib.sha256((ROOT/n).read_bytes()).hexdigest()}
          for n in files if n not in ['FILE_MANIFEST.json','VALIDATION.json']]
(ROOT/'FILE_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
print(json.dumps({'status':'PASS','staged_files':len(files),'manifest_entries':len(manifest)},indent=2))
