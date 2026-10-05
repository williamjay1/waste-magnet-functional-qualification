# Waste magnet functional qualification

Reproducible secondary analysis for *From rare-earth content to functional
recovery: qualification of waste NdFeB magnets for reuse and recycling*.
This repository publishes **code, attributed data and verification records**,
not the unpublished manuscript, publisher PDFs or confidential measurements.

## What the analysis establishes

Source rare-earth content and a finished-material reference screen answer
different questions. Six matched source lineages provide screen-disagreement
counterexamples; an independent elevator parent with three process branches
tests the chemical-sufficiency interpretation. Seven parents are not a European
sample. Three allocation requirements have distinct endpoints and do not form
a common functional unit. Fixed FutuRaM scenarios support conditional planning
bounds, not actual qualified deliveries, net environmental benefits or minimum
profitable plant size.

Unreported finished yields, raw replicates and service acceptance rules are not
filled in. Traction coercivity remains censored. A reference mismatch or missing
record is not a measured device failure. All 0–15% reference perturbations,
unfavourable process branches and above-unity feasibility requirements remain.

## Inputs and rights

Read [DATA_SOURCES.json](DATA_SOURCES.json) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Original software is MIT;
the published tables and FutuRaM adaptations retain CC BY 4.0/source attribution.
GISCO geometry/cap/distance files are not redistributed or assigned MIT.
They are regenerated locally after explicit acceptance of the separate
noncommercial-use terms. No paid database, proprietary solver or laboratory
access is needed for the supplied secondary analysis.

## Reproduce

Python 3.12 was used; dependency versions are recorded in requirements.txt.
Create an isolated environment and install those requirements. From this clone:

```bash
python -m pip install -r requirements.txt
python run_reproduction.py --raw-dir ../external_raw --accept-gisco-noncommercial
```

The second command downloads the small official GISCO input into a new versioned
read-only file, records its raw SHA-256, checks the canonical EU27 geometry hash
and rebuilds diagnostics. Alternatively
use an existing official download:

```bash
python run_reproduction.py --geometry-file /path/to/NUTS_RG_01M_2024_4326_LEVL_0.geojson --accept-gisco-noncommercial
```

Review [the GISCO terms](https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units)
first. Local paths in examples are placeholders, not data locations. If the official
geometry changes, the hash check stops instead of silently mixing source versions.
Changes to JSON formatting or unused properties do not change the input geometry;
both the original byte hash and the canonical geometry hash are documented.
Raw files are never overwritten. Choose an appropriate raw repository and work
directory; generated results go to this working clone.

Outputs: `supplement/functional_qualification/recomputed/` and
`reproduction_report.json`. The decimal verifier is independent of the floating-
point implementation. The runner compares every computed CSV with the frozen
snapshot. To reproduce all inherited supplementary regional grids, add
`--regional-grid`; to export artwork, add `--figures`. Plotting fails on detected
text collisions/clipping; it does not replace manual visual review.

```bash
python run_reproduction.py --raw-dir ../external_raw --accept-gisco-noncommercial --regional-grid --figures
```

Figures are also reproducible from the frozen, verified CSVs without a geometry
download:

```bash
python scripts/draw_nature_figures.py
```

The 5 figures and 3 standalone table artworks are native PDF/SVG plus 1200 dpi
PNG/TIFF in `artwork/`. Tables in the manuscript remain editable, not raster
screenshots. See [STYLE_PROVENANCE.md](STYLE_PROVENANCE.md). Original source
values are preserved; no smoothing, invented points or synthetic uncertainty.

The harmonised model input CSVs are bundled; no multi-GB download is needed for
ordinary reproduction. To re-extract them from the original, versioned FutuRaM
downloads, install requirements-extraction.txt and run:

```bash
python supplement/extract_public_source_inputs.py --weee-sf /path/to/WEEE_SF_cmp_version2.csv --wind-rm /path/to/CDW_WTB_RM_cmp_version20.csv --output extracted --reference-data supplement/data
```

Exact node, hierarchy, unit and EU27 filters are executable in that extractor.
`provenance_source_extraction_verification.json` records earlier original-to-table
checks. These are model scenario inputs, not observed material qualification.

## Scientific transparency and DOI handoff

The fixed/exploratory history is in
`supplement/functional_qualification/ANALYSIS_PROTOCOL.md`. Exploration is not
mislabelled as preregistration. AI-assisted tools supported discovery, extraction,
coding, verification, analysis, visualisation and drafting; source claims and
numbers were checked separately. No new experiment or human-participant study
was conducted. Do not infer that automated checks validate population claims.

The repository name/account identify the maintainer, not the complete manuscript
author list, funding or competing interests. Submitting authors must confirm
those declarations and the target journal's current exact-ISSN coverage/guidance.

No Zenodo DOI is reserved, generated or invented by this package. The owner will
personally connect GitHub to Zenodo, archive the selected release and verify the
DOI and licence metadata. Before doing so, confirm the creator list and preserve
the per-file rights distinctions; do not select one blanket licence for all inputs.
Add the real version DOI and concept DOI only after the deposit is verified.
For now cite the immutable Git commit and the original versioned source DOIs.
