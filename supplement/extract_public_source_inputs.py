"""Re-extract the two flow inputs from the cited public FutuRaM CSV files.

Download the specified source versions separately under their original licences.
This read-only extractor does not download, alter or redistribute raw files.
Large source files should be read from a local working copy. Output is separate.
"""
from pathlib import Path
import argparse
import hashlib
import json
import duckdb
import numpy as np
import pandas as pd

EU27 = 'AUT BEL BGR HRV CYP CZE DNK EST FIN FRA DEU GRC HUN IRL ITA LVA LTU LUX MLT NLD POL PRT ROU SVK SVN ESP SWE'.split()


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def compare(actual, path, keys, measures):
    reference = pd.read_csv(path).set_index(keys).sort_index()
    actual = actual.set_index(keys).sort_index()
    assert actual.index.equals(reference.index), 'source keys differ'
    gaps = {c: float(np.max(np.abs(actual[c] - reference[c]))) for c in measures}
    assert max(gaps.values()) < 1e-7, gaps
    return gaps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--weee-sf', type=Path, required=True,
                    help='WEEE_SF_cmp_version2.csv, Zenodo record 20607366 version 2')
    ap.add_argument('--wind-rm', type=Path, required=True,
                    help='CDW_WTB_RM_cmp_version20.csv, record 20407024 version 1')
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--reference-data', type=Path, default=None,
                    help='Optional comparison after extraction, not an input to it')
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    assert args.weee_sf.is_file() and args.wind_rm.is_file()
    # Do not replace the raw sources or the distributed harmonised inputs.
    assert args.output.resolve() not in {args.weee_sf.parent.resolve(), args.wind_rm.parent.resolve()}
    assert args.output.resolve() != (Path(__file__).parent / 'data').resolve()
    con = duckdb.connect()
    con.execute("SET threads=2")
    con.execute("SET memory_limit='2GB'")
    cache = args.output / 'duckdb_temp'
    cache.mkdir(exist_ok=True)
    con.execute("SET temp_directory='" + cache.as_posix().replace("'", "''") + "'")
    countries = ','.join("'" + c + "'" for c in EU27)
    con.execute(f'''
      CREATE TEMP TABLE selected AS
      SELECT * FROM read_csv_auto(?,header=true,sample_size=200000,ignore_errors=false)
      WHERE "Waste Stream"='WEEE' AND "Layer 2"='magnetPermanent'
      AND "Stock/Flow ID"='WEEE_collected' AND Year BETWEEN 2024 AND 2050
      AND Scenario IN ('BAU','CIR','REC') AND Location IN ({countries})
    ''', [str(args.weee_sf)])
    assert con.execute('SELECT DISTINCT Unit FROM selected').fetchall() == [('Mg',)]
    weee = con.execute('''
      SELECT Location AS location, Year::INTEGER AS year, Scenario AS scenario,
      SUM(CASE WHEN COALESCE(TRIM("Layer 3"),'')='' AND COALESCE(TRIM("Layer 4"),'')=''
          THEN Value ELSE 0 END) AS generic_pm_t_y,
      SUM(CASE WHEN "Layer 4"='Nd' THEN Value ELSE 0 END) AS contained_Nd_t_y,
      SUM(CASE WHEN "Layer 4"='Pr' THEN Value ELSE 0 END) AS contained_Pr_t_y,
      SUM(CASE WHEN "Layer 4"='Dy' THEN Value ELSE 0 END) AS contained_Dy_t_y,
      COUNT(DISTINCT CASE WHEN "Layer 4" IN ('Nd','Pr','Dy') THEN "Layer 4" END) AS ree3_element_codes,
      COUNT(DISTINCT CASE WHEN COALESCE(TRIM("Layer 3"),'')='' AND COALESCE(TRIM("Layer 4"),'')=''
          THEN "Layer 1" END) AS categories,
      SUM(CASE WHEN COALESCE(TRIM("Layer 3"),'')='' AND COALESCE(TRIM("Layer 4"),'')=''
          THEN 1 ELSE 0 END) AS parent_rows
      FROM selected GROUP BY 1,2,3 ORDER BY 1,2,3
    ''').df()
    assert len(weee) == 2187 and set(weee.location) == set(EU27)
    assert weee.categories.eq(6).all() and weee.parent_rows.eq(6).all()
    assert weee.ree3_element_codes.eq(3).all()
    weee = weee.drop(columns=['categories', 'parent_rows'])
    weee['contained_ree3_t_y'] = weee[['contained_Nd_t_y','contained_Pr_t_y','contained_Dy_t_y']].sum(axis=1)
    assert (weee.contained_ree3_t_y.between(0, weee.generic_pm_t_y)).all()
    weee.to_csv(args.output / 'weee_collection_elements_country_year.csv', index=False)
    con.close()

    wind = pd.read_csv(args.wind_rm, low_memory=False)
    wind = wind[(wind.Location == 'EU27') & (wind['Stock/Flow ID'] == 'CDW_collected') &
                (wind['Layer 2'] == 'wtbPermanentMagnet') & (wind['Layer 3'] == 'magnetAlloysNdFeB') &
                wind.Scenario.isin(['BAU','CIR','REC']) & wind.Year.between(2024,2050)].copy()
    assert set(wind.Unit) == {'kg'}
    parent = wind[wind['Layer 4'].fillna('').str.strip().eq('')].groupby(['Year','Scenario']).Value.sum()/1000
    child = wind[wind['Layer 4'].isin(['Nd','Pr','Dy'])].groupby(['Year','Scenario']).Value.sum()/1000
    wind = pd.concat([parent.rename('magnet_t_y'), child.rename('ree3_t_y')], axis=1).reset_index()
    assert len(wind) == 81 and not wind.isna().any().any()
    assert wind.ree3_t_y.between(0, wind.magnet_t_y).all()
    wind['ree3_fraction'] = wind.ree3_t_y / wind.magnet_t_y
    wind.to_csv(args.output / 'wind_collected_ndfeb_and_ree3.csv', index=False)
    info = {'weee_rows': len(weee), 'wind_rows': len(wind), 'weee_categories_per_key': 6,
            'weee_element_codes_per_key': 3,
            'input_sha256': {args.weee_sf.name: digest(args.weee_sf), args.wind_rm.name: digest(args.wind_rm)},
            'versions': {'duckdb': duckdb.__version__, 'pandas': pd.__version__},
            'interpretation': 'source-model collection, not observed operating receipts'}
    if args.reference_data:
        info['reference_comparison_after_extraction'] = {
            'weee_max_gaps': compare(weee, args.reference_data / 'weee_collection_elements_country_year.csv',
                                    ['location','year','scenario'],
                                    ['generic_pm_t_y','contained_Nd_t_y','contained_Pr_t_y','contained_Dy_t_y','contained_ree3_t_y']),
            'wind_max_gaps': compare(wind, args.reference_data / 'wind_collected_ndfeb_and_ree3.csv',
                                    ['Year','Scenario'], ['magnet_t_y','ree3_t_y','ree3_fraction'])}
    (args.output / 'source_extraction_verification.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    main()
