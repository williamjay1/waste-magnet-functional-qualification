"""Published material qualification and bounded regional inverse design.

No raw experimental replicates, EU prevalence estimates, fitted classifier or
finished-yield assumptions. Paths configurable; source work data are read only.
"""
from pathlib import Path
from itertools import combinations, product, permutations
import argparse
import hashlib
import json
import platform
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.optimize import linprog
import scipy

SC = ['BAU', 'CIR', 'REC']

def screen(values, reference, relax=0):
    return bool(np.all(np.asarray(values) >= np.asarray(reference)*(1-relax)-1e-12))

def run(data, legacy, output):
    output.mkdir(parents=True, exist_ok=True)
    figures = output/'figures'
    figures.mkdir(exist_ok=True)
    m = pd.read_csv(data/'material_lineages.csv')
    ref = pd.read_csv(data/'device_reference_points.csv')
    demo = pd.read_csv(data/'device_demonstrations.csv')
    m['source_ree3_wt_pct'] = m[['source_nd_wt_pct','source_pr_wt_pct','source_dy_wt_pct']].sum(axis=1)
    assert len(m) == 9 and m.groupby(['study','lineage']).ngroups == 7
    assert m.finished_mass_yield.isna().all()
    for p in ['remanence_T','Hcj_kA_m','BHmax_kJ_m3']:
        m['retention_'+p] = m['after_'+p]/m['before_'+p]
    m.loc[m.Hcj_censored, 'retention_Hcj_kA_m'] = np.nan
    m.to_csv(output/'material_response_results.csv', index=False)
    props = ['remanence_T', 'Hcj_kA_m', 'BHmax_kJ_m3']
    decisions = []
    for _, row in m.iterrows():
        for _, target in ref.iterrows():
            for stage in ['before','after']:
                for relax in np.arange(16)/100:
                    decision = screen([row[stage+'_'+p] for p in props],target[props],relax)
                    decisions.append(dict(study=row.study,lineage=row.lineage,process=row.process,
                        stage=stage,device=target.device,relaxation_pct=int(round(100*relax)),
                        reference_screen_pass=decision,
                        chemistry20_pass=row.source_ree3_wt_pct>=20,
                        chemistry30_pass=row.source_ree3_wt_pct>=30,
                        total_ree30_pass=row.source_tre_wt_pct>=30))
    dec = pd.DataFrame(decisions)
    dec.to_csv(output/'screen_decisions_all_tolerances.csv',index=False)
    rows = []
    for study, stage, device, tol in product(['S2025','L2025'], ['before','after'],ref.device,range(16)):
        d = dec[(dec.study==study)&(dec.stage==stage)&(dec.device==device)&(dec.relaxation_pct==tol)]
        for chemical in ['chemistry20_pass','chemistry30_pass','total_ree30_pass']:
            rows.append(dict(study=study,stage=stage,device=device,relaxation_pct=tol,gate=chemical,
                             n_process_rows=len(d),n_independent_lineages=d.lineage.nunique(),
                             reference_passes=int(d.reference_screen_pass.sum()),
                             chemical_accepts=int(d[chemical].sum()),
                             screen_false_accepts=int((d[chemical]&~d.reference_screen_pass).sum()),
                             screen_false_rejects=int((~d[chemical]&d.reference_screen_pass).sum())))
    counts = pd.DataFrame(rows)
    counts.to_csv(output/'screen_discordance_counts.csv',index=False)
    # Exploratory best-case threshold diagnostic; not a new trained classifier.
    # A cutoff that interpolates the six development sources is frozen before
    # examining the independent-study response. The held-out branches remain one
    # parent source, and the comparison is a counterexample, not error-rate inference.
    target = ref[ref.device=='Hoverboard'].iloc[0]
    dev = m[m.study=='S2025'].copy()
    ydev = np.array([screen(r[['after_'+p for p in props]],target[props]) for _,r in dev.iterrows()])
    positives = dev.loc[ydev,'source_ree3_wt_pct']
    negatives = dev.loc[~ydev,'source_ree3_wt_pct']
    lower,upper = negatives.max(),positives.min()
    assert lower < upper
    frozen_cut = (lower+upper)/2
    held = m[m.study=='L2025']
    held_accept = held.source_ree3_wt_pct >= frozen_cut
    held_pass = np.array([screen(r[['after_'+p for p in props]],target[props]) for _,r in held.iterrows()])
    threshold_diagnostic = dict(exploratory=True,reference='Hoverboard point triple',
        development_source_lineages=6,development_perfect_cutoff_lower_exclusive_wt_pct=float(lower),
        development_perfect_cutoff_upper_inclusive_wt_pct=float(upper),
        frozen_midpoint_cutoff_wt_pct=float(frozen_cut),independent_parent_lineages=1,
        independent_process_branches=3,held_out_chemical_accepts=int(held_accept.sum()),
        held_out_reference_passes=int(held_pass.sum()),
        inference='out-of-study chemical-sufficiency counterexample; not population predictive accuracy')
    (output/'exploratory_chemical_threshold_diagnostic.json').write_text(json.dumps(threshold_diagnostic,indent=2),encoding='utf8')
    breakpoint_rows=[]
    for _,r in m.iterrows():
        for _,t in ref.iterrows():
            weakest=min(float(r['after_'+p])/float(t[p]) for p in props)
            breakpoint_rows.append(dict(study=r.study,lineage=r.lineage,process=r.process,device=t.device,
                joint_reference_relaxation_needed_pct=100*max(0,1-weakest),
                endpoint='point specification sensitivity not statistical confidence'))
    pd.DataFrame(breakpoint_rows).to_csv(output/'reference_relaxation_breakpoints.csv',index=False)
    de = []
    for _, d in demo.iterrows():
        r = m[(m.study==d.study)&(m.lineage==d.lineage)].iloc[0]
        t = ref[ref.device==d.target_device].iloc[0]
        stage = 'before' if d.route=='U' else 'after'
        de.append({**d.to_dict(), 'component_reference_screen_pass':screen([r[stage+'_'+p] for p in props],t[props]),
                   'screen_stage':stage, 'independent_sample_n': 'not inferable from magnet piece count'})
    pd.DataFrame(de).to_csv(output/'device_screen_discordance.csv',index=False)
    # Normalised source-candidate allocation: one source slot per development
    # lineage, not observed inventory, material tonnage or a yield estimate.
    # Requirements are DIFFERENT recorded endpoints, not interchangeable output.
    sm0=m[m.study=='S2025'].set_index('lineage')
    source_ids=list(sm0.index)
    targets=['U_Pedelec_EMF_evidence','P_eScooter_EMF_evidence','P_Hoverboard_material_reference']
    observed={targets[0]:{'MRI'},targets[1]:{'PUMP'},targets[2]:set()}
    for label,r in sm0.iterrows():
        if screen(r[['after_'+p for p in props]],ref[ref.device=='Hoverboard'].iloc[0][props]):
            observed[targets[2]].add(label)
    material={targets[0]:set(),targets[1]:set(),targets[2]:observed[targets[2]]}
    for label,r in sm0.iterrows():
        if screen(r[['before_'+p for p in props]],ref[ref.device=='Pedelec'].iloc[0][props]):
            material[targets[0]].add(label)
        if screen(r[['after_'+p for p in props]],ref[ref.device=='eScooter'].iloc[0][props]):
            material[targets[1]].add(label)
    assignment_rows=[]
    for labels in permutations(source_ids,3):
        assignment_rows.append(dict(zip(targets,labels))|dict(
            chemistry20_admitted=all(sm0.loc[l,'source_ree3_wt_pct']>=20 for l in labels),
            chemistry30_admitted=all(sm0.loc[l,'source_ree3_wt_pct']>=30 for l in labels),
            total_ree30_admitted=all(sm0.loc[l,'source_tre_wt_pct']>=30 for l in labels),
            component_reference_supported=all(l in material[t] for l,t in zip(labels,targets)),
            recorded_endpoint_supported=all(l in observed[t] for l,t in zip(labels,targets))))
    assignments=pd.DataFrame(assignment_rows)
    assignments.to_csv(output/'normalised_source_candidate_allocations.csv',index=False)
    # Select a subset of endpoint requirements with no repeated lineage; maximise
    # number of supported endpoints. This exhaustive bipartite matching is not a
    # proposed novel solver or a certified device-production network.
    def matched_count(graph,allowed):
        best=0
        for n in range(1,4):
            for tset in combinations(targets,n):
                for labels in permutations(allowed,n):
                    if all(l in graph[t] for l,t in zip(labels,tset)):
                        best=max(best,n)
        return best
    allocation_diagnostic=dict(
        source_slots=len(source_ids),required_endpoints=targets,
        chemistry20_only_uncertified_assignments=int(assignments.chemistry20_admitted.sum()),
        full_component_reference_assignments=int(assignments.component_reference_supported.sum()),
        full_recorded_endpoint_assignments=int(assignments.recorded_endpoint_supported.sum()),
        full_endpoint_assignments_with_chemistry30=int((assignments.recorded_endpoint_supported&assignments.chemistry30_admitted).sum()),
        full_endpoint_assignments_with_tre30=int((assignments.recorded_endpoint_supported&assignments.total_ree30_admitted).sum()),
        maximum_reference_supported_endpoints=matched_count(material,source_ids),
        maximum_recorded_evidence_endpoints=matched_count(observed,source_ids),
        units='normalised source-candidate slots; not actual inventories or finished mass',
        meaning='uncertified assignments are unsupported, not measured failures; EMF is not complete service')
    (output/'normalised_allocation_diagnostic.json').write_text(json.dumps(allocation_diagnostic,indent=2),encoding='utf8')

    # Independently enumerate the inherited country-location and element model.
    w = pd.read_csv(legacy/'weee_collection_elements_country_year.csv')
    wind = pd.read_csv(legacy/'wind_collected_ndfeb_and_ree3.csv').set_index(['Year','Scenario'])
    geo = pd.read_csv(legacy/'country_geometry_caps.csv').set_index('location').sort_index()
    codes = list(geo.index)
    dist = pd.read_csv(legacy/'anchor_distances_km.csv',index_col=0).loc[codes,codes].to_numpy()
    adj = dist + geo.cap_radius_km.to_numpy()[:,None] <=750
    hubs = np.array(list(combinations(range(27),2)))
    cov = adj[:,hubs].any(axis=2).T
    pm = np.vstack([w[(w.year==2030)&(w.scenario==s)].set_index('location').loc[codes,'generic_pm_t_y'] for s in SC])
    el = np.vstack([w[(w.year==2030)&(w.scenario==s)].set_index('location').loc[codes,'contained_ree3_t_y'] for s in SC])
    net, frontier, lp_gap = [], [], 0.
    for c in [.20,.30]:
        qt = cov @ np.minimum(.1*pm,el/c).T
        best = int(qt.min(axis=1).argmax())
        qw = qt[best]
        qwind = np.array([min(.5*wind.loc[(2030,s),'magnet_t_y'],wind.loc[(2030,s),'ree3_t_y']/c) for s in SC])
        qw_min, wi_min = qw.min(), qwind.min()
        fw_required = (250-.5*wi_min)/(.25*qw_min)
        fi_required = (250-.25*qw_min)/(.5*wi_min)
        net.append(dict(content_minimum=c,year=2030,k=2,radius_km=750,
                        spatial_case='whole_cap',hubs=';'.join(codes[i] for i in hubs[best]),
                        weee_input_ceiling_t_y=float(qw_min),wind_input_ceiling_t_y=float(wi_min),
                        declared_weee_intact_fraction=.25,declared_wind_intact_fraction=.50,
                        target_intact_output_t_y=250,
                        wind_function_retention_min_if_weee_equals_one=float(fi_required),
                        weee_function_retention_min_if_wind_equals_one=float(fw_required),
                        all_upper_intact_output_t_y=float(.25*qw_min+.50*wi_min)))
        for fw in np.linspace(0,1,101):
            required = max(max(0,250-.25*q*fw)/(.5*v) for q,v in product(qw,qwind))
            frontier.append(dict(content_minimum=c,f_weee=fw,min_f_wind=required,
                                 feasible_within_unit_bounds=required<=1+1e-12))
        # An independent LP maximises intact output from all source pairs for a
        # specification grid; this checks, rather than fits, the closed form.
        for fw,fi in product(np.linspace(0,1,6),repeat=2):
            for q,v in product(qw,qwind):
                result = linprog([-fw,-fi], A_ub=np.eye(2),b_ub=[.25*q,.5*v],bounds=[(0,None)]*2,method='highs')
                assert result.success
                lp_gap=max(lp_gap,abs(-result.fun-(.25*q*fw+.5*v*fi)))
    nt = pd.DataFrame(net)
    nt.to_csv(output/'functional_output_inverse_bounds.csv',index=False)
    pd.DataFrame(frontier).to_csv(output/'functional_retention_frontier.csv',index=False)
    legacy_ref = pd.read_csv(legacy/'reference_results'/'element_constrained_network_capacity.csv')
    match = legacy_ref[(legacy_ref.year==2030)&(legacy_ref.radius_km==750)&(legacy_ref.spatial_case=='all_location')&(legacy_ref.assumed_union_eligibility==.1)]
    gap = max(abs(nt.set_index('content_minimum').loc[r.nominated_ree3_minimum,'weee_input_ceiling_t_y']-r.worst_accepted_feed_ceiling_t_y) for r in match.itertuples())
    assert gap < 1e-8 and lp_gap < 1e-8

    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
    sm=m[m.study=='S2025'].copy()
    fig,ax=plt.subplots(1,2,figsize=(10.4,4.1),gridspec_kw={'width_ratios':[1.1,1]})
    for i, r in enumerate(sm.itertuples()):
        ax[0].plot([r.source_ree3_wt_pct]*2,[r.before_BHmax_kJ_m3,r.after_BHmax_kJ_m3],c='#a0a0a0',lw=1.2)
        ax[0].scatter(r.source_ree3_wt_pct,r.before_BHmax_kJ_m3,marker='o',facecolors='none',edgecolors='#555',s=45)
        ax[0].scatter(r.source_ree3_wt_pct,r.after_BHmax_kJ_m3,c='#007a87',s=42)
        ax[0].annotate(r.lineage,(r.source_ree3_wt_pct,r.after_BHmax_kJ_m3),xytext=(4,-10 if r.lineage=='IM' else 5),textcoords='offset points',fontsize=8)
    ax[0].axvline(30,c='#bd5146',ls='--',lw=1)
    ax[0].set(xlabel='Source Nd+Pr+Dy (wt%)',ylabel='(BH)max (kJ/m³)',title='(a) Content does not fix magnetic response',xlim=(27.3,30.8))
    heat=np.array([[screen(r[["after_"+p for p in props]],t[props]) for _,t in ref.iterrows()] for _,r in sm.iterrows()],int)
    from matplotlib.colors import ListedColormap
    ax[1].imshow(heat,cmap=ListedColormap(['#efe9df','#007a87']),vmin=0,vmax=1,aspect='auto')
    ax[1].set_xticks(range(3),ref.device);ax[1].set_yticks(range(6),sm.lineage)
    for i in range(6):
        for j in range(3): ax[1].text(j,i,'meets' if heat[i,j] else 'below',ha='center',va='center',color='white' if heat[i,j] else '#333',fontsize=9)
    ax[1].set_title('(b) Three-property output reference screen')
    fig.tight_layout();fig.savefig(figures/'figure2_material_function.pdf');fig.savefig(figures/'figure2_material_function.png',dpi=200);plt.close(fig)

    lm=m[m.study=='L2025']
    fig,ax=plt.subplots(1,2,figsize=(10.4,3.9))
    names=['No degassing','Degassed 20 bar','Degassed 3 bar']
    ax[0].bar(names,lm.after_BHmax_kJ_m3,color=['#bd5146','#007a87','#7dab9b'])
    ax[0].axhline(lm.before_BHmax_kJ_m3.iloc[0],c='#444',ls=':',label='Parent magnet')
    ax[0].set(ylabel='(BH)max (kJ/m³)',title='(a) One parent material, three process branches')
    ax[0].legend(frameon=False,fontsize=8);ax[0].tick_params(axis='x',labelsize=8)
    ax[1].plot([0,1,2],[4700,1870,1950],'o-',label='Oxygen (powder)',c='#007a87')
    ax[1].plot([0,1,2],[5000,24,28],'s--',label='Hydrogen (powder)',c='#bd5146')
    ax[1].set_xticks(range(3),names,fontsize=8)
    ax[1].set(ylabel='Reported powder concentration (ppm)',title='(b) Observable state before FAST sintering')
    ax[1].legend(frameon=False,fontsize=8)
    fig.tight_layout();fig.savefig(figures/'figure3_independent_process_response.pdf');fig.savefig(figures/'figure3_independent_process_response.png',dpi=200);plt.close(fig)

    fig,ax=plt.subplots(figsize=(7.4,4.8))
    fr=pd.DataFrame(frontier)
    for c,col in [(.2,'#007a87'),(.3,'#bd5146')]:
        t=fr[fr.content_minimum==c];ax.plot(t.f_weee,t.min_f_wind,c=col,label=f'Nd+Pr+Dy minimum {int(c*100)}%')
    ax.axhline(1,c='#555',ls='--',lw=1)
    ax.fill_between([0,1],1,2.6,color='#eee',label='Exceeds wind unit bound')
    ax.set(xlim=(0,1),ylim=(0,2.6),xlabel='WEEE application qualification × finished retention (fW)',
           ylabel='Required wind qualification × finished retention',title='Necessary intact-output cut: 250 t/year')
    ax.legend(frameon=False,fontsize=9,loc='upper right')
    fig.tight_layout();fig.savefig(figures/'figure4_functional_output_bounds.pdf');fig.savefig(figures/'figure4_functional_output_bounds.png',dpi=200);plt.close(fig)

    report={'source_process_rows':len(m),'source_lineages':m.groupby(['study','lineage']).ngroups,
            'independent_publications':m.study.nunique(),'censored_Hcj_ratios_missing':int(m.retention_Hcj_kA_m.isna().sum()),
            'finished_mass_yields_known':int(m.finished_mass_yield.notna().sum()),
            'regional_legacy_recompute_max_abs_t_y':gap,'independent_lp_cases':2*36*9,
            'lp_max_abs_t_y':lp_gap,'inputs_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in data.glob('*.csv')},
            'software':{'python':sys.version,'platform':platform.platform(),'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__,'matplotlib':matplotlib.__version__},
            'scope':'published point screens and conditional bounds; no EU qualification prevalence or uncertainty distribution'}
    (output/'analysis_run.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2))
    print(counts[(counts.study=='S2025')&(counts.stage=='after')&(counts.relaxation_pct==0)].to_string(index=False))
    print(nt.to_string(index=False))

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    base=Path(__file__).resolve().parent
    ap.add_argument('--data',type=Path,default=base/'functional_qualification')
    ap.add_argument('--legacy',type=Path,default=base/'data')
    ap.add_argument('--output',type=Path,default=base/'functional_qualification'/'recomputed')
    a=ap.parse_args();run(a.data,a.legacy,a.output)
