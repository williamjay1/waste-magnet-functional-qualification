"""Arithmetic and scope audit independent of the analysis implementation."""
from pathlib import Path
from decimal import Decimal as D
import csv
import json
import argparse

def main(data, result):
    rows=list(csv.DictReader((data/'material_lineages.csv').open(encoding='utf-8-sig')))
    refs=list(csv.DictReader((data/'device_reference_points.csv').open(encoding='utf-8-sig')))
    checks=[]
    for row in rows:
        # Preserve the published dash treatment as a sum convention, not detection.
        total=sum(D(row[k]) for k in ['source_nd_wt_pct','source_pr_wt_pct','source_dy_wt_pct'])
        for ref in refs:
            values=[D(row['after_'+k]) for k in ['remanence_T','Hcj_kA_m','BHmax_kJ_m3']]
            targets=[D(ref[k]) for k in ['remanence_T','Hcj_kA_m','BHmax_kJ_m3']]
            checks.append(dict(study=row['study'],lineage=row['lineage'],process=row['process'],
                device=ref['device'],passed=all(a>=b for a,b in zip(values,targets)),
                chemistry20=total>=D(20),chemistry30=total>=D(30)))
    found=list(csv.DictReader((result/'screen_decisions_all_tolerances.csv').open(encoding='utf-8-sig')))
    for c in checks:
        f=[r for r in found if all(r[k]==c[k] for k in ['study','lineage','process','device']) and r['stage']=='after' and r['relaxation_pct']=='0']
        assert len(f)==1 and (f[0]['reference_screen_pass']=='True')==c['passed']
        assert (f[0]['chemistry20_pass']=='True')==c['chemistry20']
        assert (f[0]['chemistry30_pass']=='True')==c['chemistry30']
    regional=list(csv.DictReader((result/'functional_output_inverse_bounds.csv').open(encoding='utf-8-sig')))
    residual=[]
    for r in regional:
        qw,qi=D(r['weee_input_ceiling_t_y']),D(r['wind_input_ceiling_t_y'])
        needed=(D(250)-D('.25')*qw)/(D('.5')*qi)
        residual.append(float(abs(needed-D(r['wind_function_retention_min_if_weee_equals_one']))))
        assert residual[-1]<1e-12
    response=list(csv.DictReader((result/'material_response_results.csv').open(encoding='utf-8-sig')))
    assert len(rows)==9 and len({(r['study'],r['lineage']) for r in rows})==7
    assert all(r['finished_mass_yield']=='' for r in rows)
    assert next(r for r in response if r['lineage']=='TM')['retention_Hcj_kA_m']==''
    assert len({r['lineage'] for r in rows if r['study']=='L2025'})==1
    # These fixed expected comparisons have been checked against source tables.
    sm=[c for c in checks if c['study']=='S2025' and c['device']=='Hoverboard']
    assert sum(c['passed'] for c in sm)==5
    assert sum(c['chemistry30'] and not c['passed'] for c in sm)==0
    assert sum(not c['chemistry30'] and c['passed'] for c in sm)==4
    assert sum(c['chemistry20'] and not c['passed'] for c in sm)==1
    independent=[c for c in checks if c['study']=='L2025' and c['device']=='Hoverboard']
    assert len(independent)==3 and not any(c['passed'] for c in independent)
    diagnostics=json.loads((result/'exploratory_chemical_threshold_diagnostic.json').read_text())
    assert abs(diagnostics['frozen_midpoint_cutoff_wt_pct']-28.05)<1e-12
    assert diagnostics['held_out_chemical_accepts']==3 and diagnostics['held_out_reference_passes']==0
    allocation=json.loads((result/'normalised_allocation_diagnostic.json').read_text())
    # U evidence fixes MRI, P eScooter fixes pump; the third non-repeated matched
    # material can be wind, production waste or industrial motor: three choices.
    assert allocation['full_recorded_endpoint_assignments']==3
    assert allocation['full_component_reference_assignments']==0
    assert allocation['chemistry20_only_uncertified_assignments']==6*5*4
    assert allocation['maximum_reference_supported_endpoints']==2
    assert allocation['maximum_recorded_evidence_endpoints']==3
    assert allocation['full_endpoint_assignments_with_chemistry30']==0
    report={'status':'PASS','independent_decimal_reference_checks':len(checks),
            'regional_equation_residual_max':max(residual),
            'nonduplicating_candidate_allocation_checks':'PASS: 120 uncertified / 0 strict reference / 3 recorded endpoint combinations',
            'published_table_scope_checks':'7 parent lineages / 2 publications; no finished yields; traction censor retained',
            'meaning':'implementation and extraction arithmetic verified, not population or service validation'}
    (result/'independent_verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    base=Path(__file__).resolve().parent
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,default=base/'functional_qualification')
    p.add_argument('--result',type=Path,default=base/'functional_qualification'/'recomputed')
    a=p.parse_args();main(a.data,a.result)
