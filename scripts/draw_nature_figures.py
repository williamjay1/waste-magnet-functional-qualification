"""Evidence-preserving Nature-inspired vector figures and table artwork.

Style sources: SciencePlots MIT (John Garrett) and K-Dense scientific-visualization
MIT. Only data/visualisation settings are read; third-party code is not executed.
All source numbers are frozen v102 values. No synthetic observations/error bars.
"""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import shutil
import re
from itertools import combinations
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch
from matplotlib.transforms import Bbox
from matplotlib.text import Text
from matplotlib.lines import Line2D
from PIL import Image
import pymupdf

REPO=Path(__file__).resolve().parent.parent
BASE=REPO
OUT=REPO/'artwork'
RAW=REPO/'style_sources'
BLUE='#0072B2';GREEN='#009E73';ORANGE='#D55E00';INK='#202020';GREY='#6E6E6E'
DPI=1200
REPORT=[]
SOURCES={}

def configure():
    styles=OUT/'style_sources';styles.mkdir(parents=True,exist_ok=True)
    for p in RAW.iterdir():
        if p.is_file():
            dest=styles/p.name
            if p.resolve()==dest.resolve():continue
            if not dest.exists():shutil.copy2(p,dest)
            else:assert dest.read_bytes()==p.read_bytes(),p.name
    plt.style.use([str(styles/'scienceplots_science_20261005.mplstyle'),
                   str(styles/'scienceplots_nature_20261005.mplstyle'),
                   str(styles/'k_dense_nature_20261005.mplstyle')])
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','Helvetica','Liberation Sans','DejaVu Sans'],
        'font.size':7,'axes.titlesize':7,'axes.labelsize':7,'xtick.labelsize':6.5,
        'ytick.labelsize':6.5,'legend.fontsize':6.5,'text.usetex':False,
        'mathtext.fontset':'dejavusans','pdf.fonttype':42,'ps.fonttype':42,
        'svg.fonttype':'none','savefig.bbox':None,'savefig.pad_inches':0,
        'axes.spines.top':False,'axes.spines.right':False,
        'xtick.top':False,'ytick.right':False,'xtick.direction':'out','ytick.direction':'out',
        'xtick.minor.visible':False,'ytick.minor.visible':False,
        'axes.unicode_minus':True,'figure.facecolor':'white','savefig.facecolor':'white',
        'savefig.transparent':False,'lines.linewidth':.8})

def source(rel):
    p=BASE/rel;SOURCES[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
    return pd.read_csv(p)

def canvas(height):
    return plt.figure(figsize=(183/25.4,height/25.4),dpi=144)

def panel(fig,x,y,letter,title):
    fig.text(x,y,letter,fontweight='bold',fontsize=8,va='bottom')
    fig.text(x+.027,y,title,fontsize=7,va='bottom')

def export(fig,name,description,lines_to_check=()):
    folder=OUT/'figures';folder.mkdir(parents=True,exist_ok=True)
    # Arial lacks Unicode superscript-minus; use real mathematical superscripts.
    for t in fig.findobj(match=Text):
        value=t.get_text()
        for old,new in [('m⁻³',r'm$^{-3}$'),('m⁻¹',r'm$^{-1}$'),('year⁻¹',r'year$^{-1}$')]:
            value=value.replace(old,new)
        t.set_text(value)
    fig.canvas.draw();renderer=fig.canvas.get_renderer()
    texts=[t for t in fig.findobj(match=Text) if t.get_visible() and t.get_text().strip()]
    # Axis creates invisible alternate tick labels; visible artists only.
    texts=list(dict.fromkeys(texts))
    boxes=[t.get_window_extent(renderer) for t in texts]
    collisions=[]
    for i,j in combinations(range(len(texts)),2):
        a,b=boxes[i],boxes[j]
        if a.overlaps(b) and min(a.x1,b.x1)-max(a.x0,b.x0)>.5 and min(a.y1,b.y1)-max(a.y0,b.y0)>.5:
            collisions.append([texts[i].get_text(),texts[j].get_text()])
    clipped=[t.get_text() for t,b in zip(texts,boxes) if b.x0<-.5 or b.y0<-.5 or b.x1>fig.bbox.width+.5 or b.y1>fig.bbox.height+.5]
    crossings=[]
    # Explicitly test data/guide polylines and connectors, not rectangle boundaries.
    for line in lines_to_check:
        vertices=line.get_transform().transform(line.get_path().vertices)
        for t,b in zip(texts,boxes):
            inset=Bbox.from_extents(b.x0-.8,b.y0-.8,b.x1+.8,b.y1+.8)
            for p,q in zip(vertices[:-1],vertices[1:]):
                if not np.isfinite([*p,*q]).all():continue
                # Liang-Barsky segment/bounding-box intersection.
                delta=q-p;lo,hi=0.,1.
                for dim,mn,mx in [(0,inset.x0,inset.x1),(1,inset.y0,inset.y1)]:
                    if abs(delta[dim])<1e-12:
                        if p[dim]<mn or p[dim]>mx:lo,hi=1.,0.;break
                    else:
                        u,v=(mn-p[dim])/delta[dim],(mx-p[dim])/delta[dim]
                        lo=max(lo,min(u,v));hi=min(hi,max(u,v))
                if lo<=hi:
                    crossings.append(t.get_text());break
    assert not collisions,(name,'text/text',collisions)
    assert not clipped,(name,'clipped',clipped)
    assert not crossings,(name,'text/line',crossings)
    fig.savefig(folder/(name+'.pdf'),metadata={'Title':name,'Creator':'Matplotlib / Nature-inspired scoped style'},bbox_inches=None)
    fig.savefig(folder/(name+'.svg'),bbox_inches=None)
    fig.savefig(folder/(name+'.png'),dpi=DPI,bbox_inches=None)
    # TIFF is written from the native 1200-dpi export, not upsampled.
    with Image.open(folder/(name+'.png')) as im:
        rgb=im.convert('RGB');rgb.save(folder/(name+'.tiff'),dpi=(DPI,DPI),compression='tiff_lzw')
        preview=rgb.copy();preview.thumbnail((1700,1600));preview.save(folder/(name+'_preview.png'))
    pdf=pymupdf.open(folder/(name+'.pdf'))
    assert len(pdf)==1 and not pdf[0].get_images(full=True),(name,'raster inside vector')
    fonts=pdf[0].get_fonts(full=True)
    assert fonts and all(pdf.extract_font(f[0])[3] for f in fonts)
    assert not any(f[2]=='Type3' for f in fonts)
    widths=[pdf[0].rect.width/72*25.4,pdf[0].rect.height/72*25.4]
    assert abs(widths[0]-183)<.01
    with Image.open(folder/(name+'.tiff')) as im:
        assert im.mode=='RGB' and min(im.info['dpi'])>=1199
        assert abs(im.width/1200*25.4-183)<.03
    svg=(folder/(name+'.svg')).read_text(encoding='utf8')
    assert '<image ' not in svg and '<text ' in svg
    REPORT.append({'file':name,'width_mm':widths[0],'height_mm':widths[1],
        'raster_dpi':DPI,'embedded_raster_count':0,'fonts_embedded':True,'SVG_text_editable':True,
        'text_text_collisions':collisions,'tested_text_line_intersections':crossings,
        'clipped_text':clipped,'text_font_pt_min':min(t.get_fontsize() for t in texts),
        'text_font_pt_max':max(t.get_fontsize() for t in texts),'description':description,
        'visual_review':'pending'});
    plt.close(fig)

def workflow():
    fig=canvas(106);ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,183);ax.set_ylim(0,106);ax.axis('off')
    lines=[]
    def block(x,y,w,h,text,face='white',edge='#737373',weight='normal'):
        ax.add_patch(Rectangle((x,y),w,h,facecolor=face,edgecolor=edge,linewidth=.5))
        ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=6.8,fontweight=weight)
    def connector(points,color=GREY):
        line,=ax.plot(*np.asarray(points).T,color=color,lw=.65);lines.append(line)
        p,q=points[-2:];v=np.asarray(q)-p;n=np.linalg.norm(v)
        if n: ax.add_patch(FancyArrowPatch(np.asarray(q)-v/n*2.2,q,arrowstyle='-|>',mutation_scale=6,color=color,lw=.6))
    ax.text(3,99,'Waste identification',fontsize=7,fontweight='bold')
    ax.text(55,99,'Recovery route',fontsize=7,fontweight='bold')
    ax.text(91,99,'Evidence required',fontsize=7,fontweight='bold')
    ax.text(139,99,'Credited endpoint',fontsize=7,fontweight='bold')
    ax.text(3,89,'End-of-life NdFeB feed',fontsize=6.8)
    for y,text in [(68,'Identify source\nand component'),(45,'Assay material\nand contaminants'),(22,'Retain source\nand process record')]:
        block(3,y,38,15,text)
    connector([(22,68),(22,60)])
    connector([(22,45),(22,37)])
    connector([(41,29.5),(47,29.5),(47,76)])
    connector([(47,29.5),(47,24)])
    rows=[(76,'U  Retained body','Geometry, coating\nand intended service','Component function\nand retained mass',BLUE,'#EDF5FA'),
          (50,'P  Powder recycling','Process, contaminants\nand finished properties','New magnet properties\nand finished mass',GREEN,'#EEF7F3'),
          (24,'E  Element recovery','Process compatibility\nand product purity','Separated products\nand element yield',ORANGE,'#FBF1EC')]
    for y,route,gate,end,color,face in rows:
        block(55,y-8,29,16,route,face,edge=color)
        block(91,y-8,41,16,gate)
        block(139,y-8,41,16,end,face)
        connector([(47,y),(55,y)])
        connector([(84,y),(91,y)])
        connector([(132,y),(139,y)])
    ax.text(3,13,'Chemistry alone is insufficient. Allocate feed once; track residuals separately.',fontsize=6.5)
    ax.text(3,5,'Unknown evidence → verification, not a failure label or qualified output.',fontsize=6.5)
    export(fig,'figure1_qualification_workflow','Source–process–endpoint workflow; U/P/E are noninterchangeable outputs.',lines)

def material():
    m=source('supplement/functional_qualification/computed/material_response_results.csv');s=m[m.study=='S2025']
    decisions=source('supplement/functional_qualification/computed/screen_decisions_all_tolerances.csv')
    fig=canvas(83)
    ax=fig.add_axes([.09,.23,.395,.57]);bx=fig.add_axes([.615,.23,.365,.57])
    panel(fig,.02,.91,'a','Source chemistry and magnetic response')
    panel(fig,.545,.91,'b','Finished-material reference')
    lines=[]
    for r in s.itertuples():
        line,=ax.plot([r.source_ree3_wt_pct]*2,[r.before_BHmax_kJ_m3,r.after_BHmax_kJ_m3],c='#989898',lw=.7);lines.append(line)
        ax.plot(r.source_ree3_wt_pct,r.before_BHmax_kJ_m3,'o',mfc='white',mec=GREY,ms=3.7,mew=.7)
        ax.plot(r.source_ree3_wt_pct,r.after_BHmax_kJ_m3,'o',mfc=BLUE,mec=BLUE,ms=3.7,mew=.7)
        dx,dy={'MRI':(-17,-2),'PUMP':(-24,-3),'WIND':(4,-2),'PS':(4,-2),'IM':(-14,-12),'TM':(-14,-5)}[r.lineage]
        ax.annotate(r.lineage,(r.source_ree3_wt_pct,r.after_BHmax_kJ_m3),xytext=(dx,dy),textcoords='offset points',fontsize=6.5)
    lines.append(ax.axvline(30,c=ORANGE,ls=(0,(3,2)),lw=.7))
    ax.set(xlim=(27.5,30.65),ylim=(180,390),xlabel='Source Nd + Pr + Dy (wt%)',ylabel=r'$(BH)_{\max}$ (kJ m$^{-3}$)')
    ax.set_xticks([27.5,28,28.5,29,29.5,30,30.5]);ax.set_yticks([200,250,300,350])
    ax.legend(handles=[Line2D([],[],marker='o',mfc='white',mec=GREY,ls='',label='Original'),
                       Line2D([],[],marker='o',mfc=BLUE,mec=BLUE,ls='',label='Recycled'),
                       Line2D([],[],c=ORANGE,ls='--',label='30% gate')],
              loc='lower left',bbox_to_anchor=(0,1.03),ncol=3,handlelength=1.1,columnspacing=.8,borderaxespad=0)
    devices=['Pedelec','eScooter','Hoverboard'];ids=list(s.lineage)
    bx.set_xlim(-.5,2.5);bx.set_ylim(5.5,-.5)
    bx.set_xticks(range(3),devices);bx.set_yticks(range(6),ids)
    bx.tick_params(length=0,pad=5)
    for spine in bx.spines.values():spine.set_visible(False)
    for i,identity in enumerate(ids):
        for j,device in enumerate(devices):
            row=decisions[(decisions.study=='S2025')&(decisions.lineage==identity)&(decisions.stage=='after')&(decisions.device==device)&(decisions.relaxation_pct==0)].iloc[0]
            ok=bool(row.reference_screen_pass)
            bx.add_patch(Rectangle((j-.46,i-.43),.92,.86,facecolor='#DCECF5' if ok else '#F3F3F3',edgecolor='white',lw=.7))
            bx.text(j,i,'meets' if ok else 'below',ha='center',va='center',fontsize=6.5)
    fig.text(.09,.035,'Six source lineages; points are published values, not replicate means. Reference matches are not service certificates.',fontsize=6)
    export(fig,'figure2_material_function','Six source pairs and all three component-reference screens; no fitted uncertainty.',lines)

def process():
    m=source('supplement/functional_qualification/computed/material_response_results.csv');lm=m[m.study=='L2025']
    evidence=source('supplement/functional_qualification/route_process_evidence.csv')
    fig=canvas(85)
    axes=[fig.add_axes([.09,.28,.235,.49]),fig.add_axes([.42,.28,.23,.49]),fig.add_axes([.75,.28,.23,.49])]
    titles=['Finished energy product','Powder oxygen','Powder hydrogen']
    for x,l,t in zip([.02,.35,.68],'abc',titles):panel(fig,x,.91,l,t)
    a,b,c=axes;x=np.arange(3);cols=[INK,BLUE,GREEN]
    a.bar(x,lm.after_BHmax_kJ_m3,width=.48,color=cols,zorder=2)
    parent=a.axhline(lm.before_BHmax_kJ_m3.iloc[0],ls=(0,(2,2)),c=GREY,lw=.7)
    a.set(ylim=(0,370),ylabel=r'$(BH)_{\max}$ (kJ m$^{-3}$)');a.set_yticks([0,100,200,300])
    vals=lm.after_BHmax_kJ_m3.to_numpy()
    for xx,yy in zip(x,vals):a.text(xx,yy+13,f'{yy:.2f}',ha='center',fontsize=6.5)
    a.text(.0,1.06,'Parent: 327.7 kJ m⁻³',transform=a.transAxes,fontsize=6.5)
    extracted={}
    for key in ['oxygen','hydrogen']:
        rows=evidence[(evidence.study=='L2025')&(evidence.process_field==key)]
        values=np.array([[float(v) for v in re.split(r'\s*\+/-\s*',str(t))] for t in rows.value])
        assert values.shape==(3,2)
        extracted[key]=values
    for axis,key in [(b,'oxygen'),(c,'hydrogen')]:
        vals=extracted[key]
        for k in range(3):
            axis.errorbar(x[k],vals[k,0],yerr=vals[k,1],fmt=['s','o','^'][k],color=cols[k],ms=3.8,lw=.7,capsize=2,zorder=3)
        axis.set(ylabel=key.capitalize()+' (ppm)')
    b.set_ylim(0,5600);b.set_yticks([0,2000,4000])
    c.set_yscale('log');c.set_ylim(10,10000);c.set_yticks([10,100,1000,10000],['10','100','1000','10,000']);c.set_ylabel('Hydrogen (ppm; log scale)')
    for axis in axes:
        axis.set_xlim(-.6,2.6);axis.set_xticks(x,['RM1','RM2','RM3'])
    fig.text(.09,.125,'RM1  No degassing, 20 bar       RM2  Degassed, 20 bar       RM3  Degassed, 3 bar',fontsize=6.5)
    fig.text(.09,.045,'One elevator parent; three processing branches. Powder intervals are reported ± values, not reconstructed confidence intervals.',fontsize=6)
    export(fig,'figure3_independent_process_response','Energy products and measured powder O/H; hydrogen log scale explicit.',[parent])

def frontier():
    data=source('supplement/functional_qualification/computed/functional_retention_frontier.csv')
    bounds=source('supplement/functional_qualification/computed/functional_output_inverse_bounds.csv')
    fig=canvas(87);ax=fig.add_axes([.105,.25,.53,.59]);lines=[]
    ax.axhspan(1,2.6,facecolor='#F2F2F2',zorder=0)
    lines.append(ax.axhline(1,c=GREY,ls=(0,(2,2)),lw=.7))
    for val,col,ls in [(.2,BLUE,'-'),(.3,ORANGE,(0,(4,2)))]:
        t=data[data.content_minimum==val];line,=ax.plot(t.f_weee,t.min_f_wind,c=col,ls=ls,lw=1);lines.append(line)
        ax.plot(t.f_weee.iloc[-1],t.min_f_wind.iloc[-1],marker='o' if val==.2 else 's',ms=3.5,c=col,clip_on=False)
    ax.set(xlim=(0,1),ylim=(0,2.6),xlabel='WEEE qualification × finished retention, fW',
           ylabel='Required wind qualification\n× finished retention, fWi')
    ax.set_xticks(np.arange(0,1.01,.2));ax.set_yticks([0,.5,1,1.5,2,2.5])
    fig.text(.105,.925,'Necessary condition for 250 t year⁻¹ intact-magnet output',fontsize=7)
    for y,val,col,label in [(.75,.2,BLUE,'20% content design'),(.50,.3,ORANGE,'30% content design')]:
        row=bounds[bounds.content_minimum==val].iloc[0]
        fig.add_artist(Line2D([.70,.745],[y+.036,y+.036],transform=fig.transFigure,c=col,ls='-' if val==.2 else (0,(4,2)),lw=1))
        fig.text(.758,y+.02,label,fontsize=7)
        fig.text(.70,y-.04,f'At fW = 1:  fWi ≥ {row.wind_function_retention_min_if_weee_equals_one:.3f}',fontsize=7)
        fig.text(.70,y-.10,'Candidate only' if val==.2 else 'Excluded within this envelope',fontsize=6.5)
    fig.text(.70,.265,'Unit bounds: 0 ≤ fW, fWi ≤ 1\nGrey region: required fWi > 1',fontsize=6.5,linespacing=1.6)
    fig.text(.105,.055,'Fixed public-flow scenarios and declared route shares; qualification and finished yields are not measured.',fontsize=6)
    export(fig,'figure4_functional_output_bounds','Original two design boundaries, including above-unity failure region.',lines)

def trajectories():
    w=source('supplement/data/weee_collection_elements_country_year.csv')
    wi=source('supplement/data/wind_collected_ndfeb_and_ree3.csv')
    grouped=w.groupby(['year','scenario'],as_index=False)[['generic_pm_t_y','contained_ree3_t_y']].sum()
    fig=canvas(76);axs=[fig.add_axes([.09,.25,.22,.57]),fig.add_axes([.42,.25,.22,.57]),fig.add_axes([.75,.25,.22,.57])];lines=[]
    for x,l,t in zip([.02,.35,.68],'abc',['WEEE generic magnets','WEEE contained Nd + Pr + Dy','Wind NdFeB-coded magnets']):panel(fig,x,.91,l,t)
    for s,color,ls,marker in [('BAU',INK,'-','o'),('CIR',BLUE,'--','s'),('REC',GREEN,'-.','^')]:
        ww=grouped[grouped.scenario==s].sort_values('year');vv=wi[wi.Scenario==s].sort_values('Year')
        for axis,xx,yy in [(axs[0],ww.year,ww.generic_pm_t_y/1000),(axs[1],ww.year,ww.contained_ree3_t_y),(axs[2],vv.Year,vv.magnet_t_y/1000)]:
            line,=axis.plot(xx,yy,color=color,ls=ls,marker=marker,markevery=[0,6,16,26],ms=2.3,lw=.85,label=s);lines.append(line)
    for ax in axs:ax.set_xlim(2023,2051);ax.set_xticks([2025,2035,2045]);ax.set_xlabel('Year')
    axs[0].set_ylabel('Parent magnet mass (kt year⁻¹)');axs[1].set_ylabel('Contained elements (t year⁻¹)');axs[2].set_ylabel('NdFeB-coded mass (kt year⁻¹)')
    axs[0].set_ylim(14,29);axs[1].set_ylim(400,650);axs[2].set_ylim(0,8)
    fig.legend(handles=axs[0].get_lines(),labels=['BAU','CIR','REC'],loc='lower center',bbox_to_anchor=(.53,.025),ncol=3,frameon=False,columnspacing=2)
    export(fig,'figure1_typed_material_trajectories','Unchanged model scenarios, not confidence intervals; no fitted interpolation.',lines)

def table_art(name,headers,rows,widths,rowheight,notes,body_fs=7):
    height=29+rowheight*len(rows)+len(notes)*4.5
    fig=canvas(height);ax=fig.add_axes([0,0,1,1]);ax.set_xlim(0,183);ax.set_ylim(0,height);ax.axis('off')
    left=3;edges=np.r_[left,left+np.cumsum(widths)];top=height-4
    ax.plot([3,180],[top,top],c=INK,lw=.7)
    for j,h in enumerate(headers):ax.text(edges[j]+1.2,top-5,h,fontsize=7,fontweight='bold',va='top',linespacing=1.45)
    y=top-15;ax.plot([3,180],[y,y],c=INK,lw=.5)
    for i,row in enumerate(rows):
        for j,v in enumerate(row):ax.text(edges[j]+1.2,y-i*rowheight-rowheight/2,str(v),fontsize=body_fs,va='center',linespacing=1.5)
        if len(rows)<=4 and i<len(rows)-1:ax.plot([3,180],[y-(i+1)*rowheight,y-(i+1)*rowheight],c='#C8C8C8',lw=.3)
    bottom=y-len(rows)*rowheight;ax.plot([3,180],[bottom,bottom],c=INK,lw=.7)
    for i,n in enumerate(notes):ax.text(3,bottom-5-i*4.5,n,fontsize=6,va='top')
    export(fig,name,'Editable standalone table artwork; same values and units as main-text tables.')

def tables():
    table_art('table1_route_evidence',
      ['Route','Waste form','Evidence required','Credited output'],
      [ ['U','Retained magnet\nor component','Geometry, magnetisation direction, coating,\npreparation loss and intended-service function','Reused component,\nnot powder'],
        ['P','Scrap processed\ninto powder','Assay, contaminants, process state and additions;\nfinished properties and full manufacture yield','Newly manufactured\nmagnet'],
        ['E','Chemical-separation\nfeed','Assay, process compatibility, purity and element\nyield; equivalence if substitution is credited','Separated rare-earth\nproduct'] ],
      [14,32,88,43],19,['Bench demonstration is narrower than full service qualification; intermediate recovery is not finished yield.'])
    m=source('supplement/functional_qualification/computed/material_response_results.csv')
    rows=[]
    names=['MRI / HPMS','Pump / HPMS','Wind / HPMS','Production / HPMS','Industrial / HPMS','Traction / HPMS','Elevator / RM1','Elevator / RM2','Elevator / RM3']
    for i,r in enumerate(m.itertuples()):
        br=f'{r.before_remanence_T:.2f} → {r.after_remanence_T:.2f}' if r.study=='S2025' else f'{r.before_remanence_T:.3f} → {r.after_remanence_T:.4f}'
        hc='>1950 → >1950' if r.Hcj_censored else f'{r.before_Hcj_kA_m:g} → {r.after_Hcj_kA_m:g}'
        bh=f'{r.before_BHmax_kJ_m3:g} → {r.after_BHmax_kJ_m3:g}' if r.study=='S2025' else f'{r.before_BHmax_kJ_m3:.1f} → {r.after_BHmax_kJ_m3:.2f}'
        rows.append([names[i],f'{r.source_ree3_wt_pct:.2f}',br,hc,bh])
    table_art('table2_material_properties',
       ['Source / process','NdPrDy\n(wt%)','Br / Mr (T)\noriginal → final','Hcj (kA m⁻¹)\noriginal → final','(BH)max (kJ m⁻³)\noriginal → final'],rows,[38,21,38,40,40],7,
       ['Published point values: Schönfeldt et al. (2025), Tables 5–7; Lagos et al. (2025), Tables 1 and 4.',
        'Six HPMS lineages plus one elevator parent with three branches. Finished mass yields remain unknown.',
        'Elevator remanence is labelled Mr; traction coercivity is censored. Branches are not independent parents.'])
    table_art('table3_screen_discordance',
       ['Chemical gate','Reference\nmatches','Admitted','Screen false\naccepts','Screen false\nrejects'],
       [['NdPrDy ≥ 20%','5','6','1','0'],['NdPrDy ≥ 30%','5','1','0','4'],['TRE ≥ 30%','5','3','0','2']],
       [55,31,23,34,34],8,
       ['Six source lineages, lowest observed component-reference triple (Hoverboard).',
        'Screen discordance is not a European error rate or a device-failure estimate.'])

def main():
    global BASE,OUT,RAW
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,default=BASE)
    ap.add_argument('--output',type=Path,default=OUT)
    ap.add_argument('--styles',type=Path,default=RAW)
    args=ap.parse_args();BASE=args.source.resolve();OUT=args.output.resolve();RAW=args.styles.resolve()
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'qa').mkdir(exist_ok=True)
    configure();workflow();material();process();frontier();trajectories();tables()
    report={'style':'Nature-inspired; actual target remains WM&R','export_dpi':DPI,
        'scienceplots_commit':'b9b16959570bd2fbc9ff5118bacc423c3bddd592',
        'kdense_commit':'154988403bb5a18e9d3c0ce4e6d5e2e4b184a298',
        'input_hashes':SOURCES,'software':{'python':platform.python_version(),'matplotlib':matplotlib.__version__,
         'numpy':np.__version__,'pandas':pd.__version__},'figures':REPORT,
        'scope':'Screening checks plus required visual review, not a journal acceptance or accessibility certification.'}
    (OUT/'qa/figure_export_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
