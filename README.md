# Saile Radar

Healthcare Workforce Intelligence Dashboard — identifying high-priority facility acquisition targets for Saile's business development team.

Built by Rajeev as a summer project during Operations Internship at Saile.

---

## For Non-Technical Readers

If you are a business stakeholder, manager, or anyone without a technical background:

- **[docs/data_notes/overview.md](docs/data_notes/overview.md)** — Start here. Plain-English explanations of every data source used, known gaps, and what they mean for interpreting results.
- **[docs/data_notes/phase2_scoring_results.md](docs/data_notes/phase2_scoring_results.md)** — What the shortage scores mean, what the Stage 2 list of 548 facilities looks like, and how to interpret the results.
- **[docs/data_notes/aamc_data_source.md](docs/data_notes/aamc_data_source.md)** — Detailed source notes for the AAMC physician shortage projections.
- **[docs/how_to_update.md](docs/how_to_update.md)** — How to refresh the data and re-run the pipeline when new government data is published.

All data collection notes, workarounds, and limitations live in **[docs/data_notes/](docs/data_notes/)**.

---

## For Technical Readers

### Setup
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Project Structure
```
data/
  raw/          Raw downloaded files (excluded from git)
  processed/    Cleaned parquet files (excluded from git)
  external/     Hand-curated reference data (committed to git)
src/
  ingest/       Data download and cleaning scripts
  scoring/      Shortage scoring model
  crosswalk/    EIN and facility matching logic
  vms/          VMS classification (ProPublica 990 data)
  dashboard/    Interactive Plotly/Dash app
docs/           Documentation and methodology notes
notebooks/      Exploratory analysis
tests/          Unit tests
```

### Running the Data Pipeline
Run scripts in order to regenerate all processed data:
```
python src/ingest/hrsa.py       # Step 1.1 — HRSA HPSA data
python src/ingest/cms.py        # Step 1.2 — CMS hospital directory
python src/ingest/bls.py        # Step 1.3 — BLS employment data
python src/ingest/unify.py      # Step 1.5 — Unified facility dataframe
python src/scoring/model.py     # Phase 2  — Shortage scoring → 548 Stage 2 candidates
python src/dashboard/app.py     # Phase 4  — Launch dashboard (coming soon)
```

To refresh data or adjust scoring weights, see **[docs/how_to_update.md](docs/how_to_update.md)**.

See CLAUDE.md for full technical details and architecture notes.
