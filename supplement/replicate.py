"""Independent, portable replication of the manuscript's design frontiers.

Inputs are licensed harmonised source-model tables, not observed grade receipts.
Networks use exhaustive enumeration, independent of the original MILP solver.
No absolute paths, credentials, commercial data or commercial solver required.
"""
from pathlib import Path
from itertools import combinations, product
import argparse
import hashlib
import json
import platform
import sys
import numpy as np
import pandas as pd
from scipy.optimize import linprog
import scipy

SC = ['BAU', 'CIR', 'REC']
COMP = np.array([[1, 1, 1], [0, 1, 1], [0, 0, 1]], dtype=bool)
MIXES = {'element_only': [0, 0, 1], 'balanced': [1/3]*3,
         'reuse_half': [.5, .25, .25], 'realloy_three_quarters': [0, .75, .25]}


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def enum_network(adjacency, masses, k):
    # For nonnegative masses, an optimum with at most k points also exists
    # with exactly k points (extra points cannot reduce coverage).
    hs = np.array(list(combinations(range(len(adjacency)), k)), dtype=int)
    cv = adjacency[:, hs].any(axis=2).T
    qty = cv @ masses.T
    objective = qty.min(axis=1)
    j = int(objective.argmax())
    return hs[j], cv[j], qty[j], float(objective[j])


def cut_capacity(supply, shares):
    candidates = []
    for mask in range(1, 8):
        routes = [r for r in range(3) if mask & (1 << r)]
        share = sum(shares[r] for r in routes)
        if share:
            supports = COMP[:, routes].any(axis=1)
            candidates.append((float(supply[supports].sum())/share, mask))
    return min(candidates)


def lp_capacity(supply, shares):
    a = np.zeros((6, 10))
    for g in range(3):
        a[g, 3*g:3*(g+1)] = 1
    for r in range(3):
        a[3+r, r:9:3] = -1
        a[3+r, -1] = shares[r]
    fit = linprog(np.r_[np.zeros(9), -1.], A_ub=a,
                  b_ub=np.r_[supply, np.zeros(3)],
                  bounds=[(0, None if COMP[g, r] else 0)
                          for g in range(3) for r in range(3)] + [(0, None)],
                  method='highs')
    if not fit.success:
        raise RuntimeError(fit.message)
    return -fit.fun


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=Path, default=Path(__file__).parent/'data')
    ap.add_argument('--output', type=Path, default=Path(__file__).parent/'replicated')
    a = ap.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    x = pd.read_csv(a.data/'weee_collection_elements_country_year.csv')
    wind = pd.read_csv(a.data/'wind_collected_ndfeb_and_ree3.csv')
    geo = pd.read_csv(a.data/'country_geometry_caps.csv').set_index('location').sort_index()
    codes = list(geo.index)
    d = pd.read_csv(a.data/'anchor_distances_km.csv', index_col=0).loc[codes, codes].to_numpy()
    caps = geo.cap_radius_km.to_numpy()
    metrics = {'possible': np.maximum(0, d-caps[:, None]), 'anchor': d,
               'all_location': np.minimum(np.pi*6371.0088, d+caps[:, None])}
    assert len(x) == 2187 and len(wind) == 81 and len(codes) == 27
    assert not x.duplicated(['location', 'year', 'scenario']).any()
    assert (x.contained_ree3_t_y <= x.generic_pm_t_y).all()
    assert x.ree3_element_codes.eq(3).all()
    assert set(x.location) == set(codes)
    assert np.allclose(d, d.T) and np.allclose(np.diag(d), 0)
    annual = x.groupby(['year','scenario'], as_index=False)[
        ['generic_pm_t_y','contained_Nd_t_y','contained_Pr_t_y',
         'contained_Dy_t_y','contained_ree3_t_y']].sum()
    annual['ree3_in_generic_pm_pct'] = 100*annual.contained_ree3_t_y/annual.generic_pm_t_y
    for c in [.20, .25, .30, .35]:
        annual[f'ndfeb_ceiling_at_cmin_{c}_t_y'] = annual.contained_ree3_t_y/c
    annual.to_csv(a.output/'weee_collection_elements_eu27_annual.csv',index=False)

    def matrix(year, field):
        return np.vstack([x[(x.year==year)&(x.scenario==s)].set_index('location').loc[codes,field] for s in SC])

    net = []
    for year, k, radius, case in product([2030,2040,2050], [1,2,3],
                                       [250,500,750,1000,1500,2000], metrics):
        hubs, cv, vals, objective = enum_network(metrics[case]<=radius,matrix(year,'generic_pm_t_y'),k)
        net.append(dict(year=year,k=k,radius_km=radius,spatial_case=case,
                        hubs=';'.join(codes[h] for h in hubs),covered_countries=int(cv.sum()),
                        worst_covered_generic_pm_t_y=objective,
                        required_eta_500_pct=100*500/objective if objective else np.inf,
                        required_eta_2000_pct=100*2000/objective if objective else np.inf))
    nt = pd.DataFrame(net)
    nt.to_csv(a.output/'robust_network_frontiers.csv',index=False)
    ann = []
    for year, case in product(range(2024,2051), metrics):
        hubs, cv, vals, objective = enum_network(metrics[case]<=750,matrix(year,'generic_pm_t_y'),2)
        ann.append(dict(year=year,spatial_case=case,hubs=';'.join(codes[h] for h in hubs),
                        worst_covered_generic_pm_t_y=objective,required_eta_500_pct=50000/objective))
    pd.DataFrame(ann).to_csv(a.output/'annual_twohub_750km_frontier.csv',index=False)
    en = []
    for year, radius, case, eta, c in product([2030,2040,2050],[750,1000],metrics,[.02,.05,.1],[.2,.3]):
        pm, el = matrix(year,'generic_pm_t_y'),matrix(year,'contained_ree3_t_y')
        hubs, cv, vals, objective = enum_network(metrics[case]<=radius,np.minimum(eta*pm,el/c),2)
        en.append(dict(year=year,k=2,radius_km=radius,spatial_case=case,
                       assumed_union_eligibility=eta,nominated_ree3_minimum=c,
                       candidate_hubs=';'.join(codes[h] for h in hubs),
                       worst_accepted_feed_ceiling_t_y=objective,
                       **{s+'_accepted_ceiling_t_y':float(v) for s,v in zip(SC,vals)}))
    ent = pd.DataFrame(en)
    ent.to_csv(a.output/'element_constrained_network_capacity.csv',index=False)
    joint, checks, lp_gap = [], 0, 0.
    wind = wind.set_index(['Year','Scenario'])
    for row in en:
        for theta, gn, mix in product([0,.5],['same_grade','higher_direct_grade'],MIXES):
            pw = np.array([.25,.5,.25]) if gn=='same_grade' else np.array([.5,.4,.1])
            mixshares = np.array(MIXES[mix])
            worst, pmin, d_amin = np.inf, 0., 0.
            for ws, vs in product(SC,SC):
                qw = row[ws+'_accepted_ceiling_t_y']
                w = wind.loc[(row['year'],vs)]
                qt = min(theta*w.magnet_t_y,w.ree3_t_y/row['nominated_ree3_minimum'])
                supply = qw*np.array([.25,.5,.25])+qt*pw
                capacity, mask = cut_capacity(supply, mixshares)
                worst = min(worst,capacity)
                rem_d = max(0,500*mixshares[0]-.25*qw)
                rem_da = max(0,500*sum(mixshares[:2])-.75*qw)
                pmin = max(pmin,rem_d/qt if qt else (np.inf if rem_d else 0))
                d_amin = max(d_amin,rem_da/qt if qt else (np.inf if rem_da else 0))
                if row['year']==2030 and row['radius_km']==750 and row['spatial_case']=='all_location' and row['assumed_union_eligibility']==.1:
                    lp_gap=max(lp_gap,abs(lp_capacity(supply,mixshares)-capacity))
                    checks+=1
            joint.append({**{k:row[k] for k in ['year','k','radius_km','spatial_case',
                         'assumed_union_eligibility','nominated_ree3_minimum']},
                          'wind_access_acceptance':theta,'wind_grade':gn,'mix':mix,
                          'max_feasible_route_feed_ceiling_t_y':worst,
                          'wind_direct_grade_min_for_500_pct':100*pmin,
                          'wind_direct_alloy_grade_min_for_500_pct':100*d_amin})
    jt = pd.DataFrame(joint)
    jt.to_csv(a.output/'element_quality_network_joint_frontiers.csv',index=False)

    # Compare objectives, not arbitrary optimiser tie-breaking for hub labels.
    comparisons = {}
    for name, new, keys, field in [
        ('robust_network_frontiers.csv',nt,['year','k','radius_km','spatial_case'],'worst_covered_generic_pm_t_y'),
        ('element_constrained_network_capacity.csv',ent,['year','k','radius_km','spatial_case','assumed_union_eligibility','nominated_ree3_minimum'],'worst_accepted_feed_ceiling_t_y'),
        ('element_quality_network_joint_frontiers.csv',jt,['year','k','radius_km','spatial_case','assumed_union_eligibility','nominated_ree3_minimum','wind_access_acceptance','wind_grade','mix'],'max_feasible_route_feed_ceiling_t_y')]:
        reference = pd.read_csv(a.data/'reference_results'/name)
        both = new.merge(reference,on=keys,suffixes=('_new','_reference'),validate='one_to_one')
        assert len(both)==len(new)==len(reference)
        residual=float((both[field+'_new']-both[field+'_reference']).abs().max())
        assert residual<1e-6,(name,residual)
        comparisons[name]={'rows':len(both),'max_absolute_gap_t_y':residual}
    chosen = jt[(jt.year==2030)&(jt.radius_km==750)&(jt.spatial_case=='all_location')&
                (jt.assumed_union_eligibility==.1)&(jt.wind_access_acceptance==.5)&
                (jt.wind_grade=='higher_direct_grade')&(jt.mix=='reuse_half')]
    assert len(chosen)==2
    true_values={.2:(534.830597,41.343081),.3:(460.566435,59.800956)}
    for _,row in chosen.iterrows():
        cap,threshold=true_values[row.nominated_ree3_minimum]
        assert abs(row.max_feasible_route_feed_ceiling_t_y-cap)<1e-5
        assert abs(row.wind_direct_grade_min_for_500_pct-threshold)<1e-5
    assert lp_gap<1e-6 and checks==288
    verification={'status':'pass','independent_network_method':'exhaustive enumeration',
                  'source_rows':len(x),'wind_rows':len(wind),'comparisons':comparisons,
                  'cut_capacity_lp_checks':checks,'max_cut_lp_gap_t_y':lp_gap,
                  'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,
                  'scipy':scipy.__version__,'platform':platform.platform(),
                  'input_sha256':{str(p.relative_to(a.data)):digest(p) for p in a.data.rglob('*.csv')}}
    (a.output/'replication_verification.json').write_text(json.dumps(verification,indent=2),encoding='utf-8')
    print(json.dumps(verification,indent=2))


if __name__=='__main__':
    main()
