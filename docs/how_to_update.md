# How to Update Saile Radar — Living Algorithm Guide

This document explains how to refresh Saile Radar when new data becomes available,
how to adjust the scoring model, and how to re-run the full pipeline from scratch.

**Saile Radar is designed to be re-run.** Every script reads from files and writes
to files. Running them in order always produces an up-to-date result.

---

## When Should You Update?

| Data Source | Update Frequency | What Triggers a Refresh |
|-------------|-----------------|------------------------|
| HRSA HPSA designations | Quarterly | New federal shortage designations published at data.hrsa.gov |
| CMS Provider of Services | Quarterly | New hospitals added, ownership changes, facility closures |
| BLS OES employment | Annually (May release) | New employment survey data released each May |
| AAMC workforce projections | Every 1–2 years | AAMC publishes updated workforce projections report |

---

## How to Run a Full Refresh

Run these scripts in order from the project root. Each one overwrites its output file.

```bash
cd ~/Projects/saile-radar
source venv/bin/activate

python src/ingest/hrsa.py        # Step 1.1 — re-downloads HRSA HPSA data
python src/ingest/cms.py         # Step 1.2 — re-downloads CMS facility list
python src/ingest/bls.py         # Step 1.3 — re-downloads BLS employment data
python src/ingest/unify.py       # Step 1.5 — rebuilds unified facility dataframe
python src/scoring/model.py      # Phase 2  — re-scores all facilities, re-sets threshold
```

After running, check the log output from each script for:
- Row counts (should be similar to previous run, or higher if new facilities added)
- HPSA coverage percentage (should stay above 80%)
- Number of Stage 2 candidates (should stay in the 200–800 range)

---

## How to Adjust the Scoring Weights

The scoring formula is defined in `src/scoring/model.py`. The weights are at the top
of the file and are easy to change:

```python
# Weights — must sum to 1.0
W_HPSA    = 0.40
W_DENSITY = 0.30
W_AAMC    = 0.20
W_RURAL   = 0.10
```

**Rules:**
- All four weights must add up to exactly 1.0
- After changing weights, re-run `python src/scoring/model.py` to regenerate scores
- Document any weight changes in `docs/scoring_methodology.md` with the reason

---

## How to Adjust the Stage 2 Target Size

The number of Stage 2 candidates (currently 548) is controlled by the target range
in `src/scoring/model.py`:

```python
threshold = set_stage2_threshold(df_scored, target_low=200, target_high=800)
```

To get more candidates (e.g., 800–1500), change the parameters:
```python
threshold = set_stage2_threshold(df_scored, target_low=800, target_high=1500)
```

The function automatically finds the score cutoff that produces a count in that range.

---

## How to Update AAMC Specialty Weights

When AAMC publishes a new workforce projections report:

1. Open the PDF and find the exhibit showing physician shortage projections by specialty group (currently Exhibit 35 in the 2023 report).
2. Update the shortfall numbers in `data/external/aamc_specialty_shortages.csv`.
3. Update the `AAMC_WEIGHT` dictionary in `src/ingest/unify.py` and the
   `AAMC_NORMALIZED` dictionary in `src/scoring/model.py` if the category midpoints change.
4. Re-run the pipeline from `src/ingest/unify.py` onward.
5. Update the table in `docs/scoring_methodology.md` with the new figures.

---

## How to Update HRSA Data Manually

If the HRSA download script stops working (e.g., the URL changes):

1. Go to data.hrsa.gov
2. Search for "HPSA" and download the three CSVs: Primary Care, Dental, Mental Health
3. Save them to `data/raw/` with the naming pattern `hrsa_hpsa_primary_care_YYYY-MM-DD.csv`
4. The cleaning logic in `src/ingest/hrsa.py` will handle the rest

---

## What Each Script Does (Plain English)

| Script | What it does | Output |
|--------|-------------|--------|
| `src/ingest/hrsa.py` | Downloads federal shortage area data. Cleans and standardizes it. | `data/processed/hrsa_hpsa_clean.parquet` |
| `src/ingest/cms.py` | Downloads the master list of all US hospitals. Flags ownership type. | `data/processed/cms_pos_clean.parquet` |
| `src/ingest/bls.py` | Downloads healthcare employment data by metro area. Calculates density. | `data/processed/bls_oes_clean.parquet` |
| `src/ingest/unify.py` | Joins all four datasets into one table (one row per hospital). | `data/processed/unified_facilities.parquet` |
| `src/scoring/model.py` | Scores every facility. Identifies Stage 2 candidates. | `data/processed/scored_facilities.parquet`, `data/processed/stage2_candidates.parquet` |

---

## Data That Must Be Updated Manually (Not Automated)

**AAMC specialty shortages** (`data/external/aamc_specialty_shortages.csv`) — this file
is hand-curated from the AAMC PDF report because AAMC does not publish the data in
machine-readable form. It must be updated by hand when AAMC publishes a new report.
See `docs/data_notes/aamc_data_source.md` for the source details.

---

## Notes on Data Storage

- `data/raw/` — downloaded source files. Excluded from git (too large). Re-generated by running the ingest scripts.
- `data/processed/` — cleaned and scored output files. Excluded from git. Re-generated by running the full pipeline.
- `data/external/` — hand-curated reference files (AAMC CSV). **Committed to git.** Do not delete.

---

## Troubleshooting

**Script fails with "file not found":** Run the scripts in order — each one depends on the previous step's output.

**HPSA coverage drops below 80%:** The HRSA or CMS data format may have changed. Check the column names in both files and compare to the `COLUMNS_KEEP` dict in `src/ingest/hrsa.py`.

**Stage 2 count is unexpectedly high or low:** A data source may have changed significantly. Check the HPSA score distribution — if the average dropped, re-download the HRSA file.

**BLS API returns errors:** The BLS API has rate limits. The script already includes 1-second pauses between batches. If errors persist, try running again the next day — BLS API is sometimes throttled during high-traffic periods.
