"""Rebuild geometry diagnostics locally; do not redistribute GISCO boundaries.

GISCO-specific terms apply, not this repository's MIT licence. Explicitly accept
the noncommercial research-use terms, and retain EuroGeographics attribution.
"""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import urllib.request
import numpy as np
import pandas as pd
from shapely.geometry import shape
import shapely

URL='https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_01M_2024_4326_LEVL_0.geojson'
TERMS='https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units'
EXPECTED_SHA='bfb21033b246f8d22104ec736396a656594a6a9780208e311b911d0afcc5a4d0'
EXPECTED_GEOMETRY_SHA='f8fd6115d0ac7125525c567f12c4dcfc157fcb0b5aba87839e399c06c60d21e6'
MAP=dict(zip('AT BE BG HR CY CZ DK EE FI FR DE EL HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE'.split(),
             'AUT BEL BGR HRV CYP CZE DNK EST FIN FRA DEU GRC HUN IRL ITA LVA LTU LUX MLT NLD POL PRT ROU SVK SVN ESP SWE'.split()))
EARTH=6371.0088

def distances(a,b):
    a,b=np.radians(a),np.radians(b)
    da=a[:,0,None]-b[None,:,0];db=a[:,1,None]-b[None,:,1]
    h=np.sin(da/2)**2+np.cos(a[:,0,None])*np.cos(b[None,:,0])*np.sin(db/2)**2
    return 2*EARTH*np.arcsin(np.sqrt(np.clip(h,0,1)))

def rectangle_cap(lat,lon,bbox):
    lo,bottom,hi,top=np.radians(bbox);la,ln=np.radians([lat,lon])
    dl=max(abs(math.atan2(math.sin(x-ln),math.cos(x-ln))) for x in [lo,hi])
    for x in [ln-math.pi,ln+math.pi]:
        if lo<=x<=hi:dl=math.pi
    A,B=math.sin(la),math.cos(la)*math.cos(dl)
    phis=[bottom,top];v=math.atan2(A,B)
    phis += [v+n*math.pi for n in range(-2,3) if bottom<=v+n*math.pi<=top]
    dot=min(A*math.sin(p)+B*math.cos(p) for p in phis)
    return EARTH*math.acos(max(-1,min(1,dot)))+1e-6

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--geometry-file',type=Path,help='Read an existing official download without modifying it.')
    p.add_argument('--raw-dir',type=Path,help='New download directory, required if no geometry-file is given.')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--accept-gisco-noncommercial',action='store_true')
    a=p.parse_args()
    if not a.accept_gisco_noncommercial:p.error('Review '+TERMS+' then pass --accept-gisco-noncommercial for permitted noncommercial use.')
    accessed=datetime.now(timezone.utc).isoformat()
    if a.geometry_file:
        source=a.geometry_file;raw=source.read_bytes();downloaded=False
    else:
        if not a.raw_dir:p.error('--raw-dir is required for a new official download.')
        a.raw_dir.mkdir(parents=True,exist_ok=True)
        request=urllib.request.Request(URL,headers={'User-Agent':'project38-research-reproduction/1.0'})
        with urllib.request.urlopen(request,timeout=60) as response:raw=response.read()
        source=a.raw_dir/('GISCO_NUTS0_2024_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.geojson')
        with source.open('xb') as stream:stream.write(raw)
        source.chmod(0o444);downloaded=True
    digest=hashlib.sha256(raw).hexdigest()
    geo=json.loads(raw)
    geometries={f['properties'].get('CNTR_CODE'):f['geometry'] for f in geo['features'] if f['properties'].get('CNTR_CODE') in MAP}
    semantic=hashlib.sha256(json.dumps(geometries,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if semantic!=EXPECTED_GEOMETRY_SHA:
        raise RuntimeError('EU27 geometry differs from the frozen study input. Preserve the new file but do not silently mix versions: '+semantic)
    points={}
    for f in geo['features']:
        code=f['properties'].get('CNTR_CODE')
        if code in MAP:
            polygon=shape(f['geometry']);point=polygon.representative_point()
            points[MAP[code]]=dict(location=MAP[code],gisco_code=code,lat=point.y,lon=point.x,
                cap_radius_km=rectangle_cap(point.y,point.x,polygon.bounds),
                bbox_west=polygon.bounds[0],bbox_south=polygon.bounds[1],bbox_east=polygon.bounds[2],bbox_north=polygon.bounds[3])
    assert set(points)==set(MAP.values())
    codes=sorted(points);coordinates=np.array([[points[c]['lat'],points[c]['lon']] for c in codes])
    a.output.mkdir(parents=True,exist_ok=True)
    pd.DataFrame([points[c] for c in codes]).to_csv(a.output/'country_geometry_caps.csv',index=False)
    pd.DataFrame(distances(coordinates,coordinates),index=codes,columns=codes).to_csv(a.output/'anchor_distances_km.csv')
    receipt={'source_url':URL,'source_sha256':digest,'frozen_raw_sha256':EXPECTED_SHA,
             'raw_byte_equal_to_old_download':digest==EXPECTED_SHA,'canonical_eu27_geometry_sha256':semantic,
             'canonical_geometry_matches_frozen_input':True,'processed_utc':accessed,'new_download':downloaded,
             'terms_url':TERMS,'copyright':'Administrative boundaries: copyright EuroGeographics.',
             'use':'noncommercial research; complete geometry, including outlying territories',
             'redistribution':'Geometry/cap/distance files are ignored by Git and are not relicensed.',
             'shapely':shapely.__version__,'countries':len(points)}
    (a.output/'geometry_reconstruction.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
