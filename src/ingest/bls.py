"""
BLS OES + Census Population Ingest
Fetches healthcare practitioner employment (SOC 29-0000) for every metro
and nonmetro area via the BLS public API, joins to Census 2023 population
estimates, computes provider density per 100k residents, and saves to
data/processed/bls_oes_clean.parquet.
"""

import logging
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
CENSUS_URL = "https://api.census.gov/data/2023/pep/charv"

# SOC 29-0000 = Healthcare Practitioners and Technical Occupations
# BLS OES series: OEU + M + area_code(7) + 000000(industry) + 290000(SOC) + 01(employment)
SOC_CODE = "290000"
DATATYPE_EMPLOYMENT = "01"
BLS_BATCH_SIZE = 50  # max series per API call without registration key


def fetch_cbsa_population() -> pd.DataFrame:
    """Fetch 2023 population for all CBSAs from Census PEP API."""
    log.info("Fetching CBSA population estimates from Census API...")
    r = requests.get(
        CENSUS_URL,
        params={
            "get": "NAME,POP,GEO_ID,YEAR",
            "for": "metropolitan statistical area/micropolitan statistical area:*",
        },
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    df = df.rename(columns={
        "metropolitan statistical area/micropolitan statistical area": "cbsa_code",
        "POP": "population",
        "YEAR": "year",
    })
    df["population"] = pd.to_numeric(df["population"], errors="coerce")
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    # Keep most recent year per CBSA (deduplicate)
    df = df.sort_values("year", ascending=False).drop_duplicates("cbsa_code")
    df = df[["cbsa_code", "NAME", "population"]].rename(columns={"NAME": "cbsa_name"})
    log.info(f"Census: {len(df):,} CBSAs with population data")
    return df.reset_index(drop=True)


def build_series_id(cbsa_code: str) -> str:
    """Build BLS OES series ID for total healthcare employment in a CBSA."""
    area = cbsa_code.zfill(7)
    return f"OEUM{area}000000{SOC_CODE}{DATATYPE_EMPLOYMENT}"


def fetch_bls_employment(cbsa_codes: list[str]) -> pd.DataFrame:
    """Query BLS API in batches for SOC 29-0000 employment by CBSA."""
    series_to_cbsa = {build_series_id(c): c for c in cbsa_codes}
    all_series = list(series_to_cbsa.keys())
    results = []

    log.info(f"Querying BLS API for {len(all_series)} metro areas in batches of {BLS_BATCH_SIZE}...")
    for i in range(0, len(all_series), BLS_BATCH_SIZE):
        batch = all_series[i: i + BLS_BATCH_SIZE]
        log.info(f"  Batch {i // BLS_BATCH_SIZE + 1}/{-(-len(all_series) // BLS_BATCH_SIZE)}: {len(batch)} series")
        r = requests.post(
            BLS_API_URL,
            json={"seriesid": batch, "startyear": "2024", "endyear": "2024"},
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()

        for series in data.get("Results", {}).get("series", []):
            sid = series["seriesID"]
            cbsa = series_to_cbsa.get(sid)
            rows = series.get("data", [])
            if rows:
                val = rows[0]["value"]
                results.append({"cbsa_code": cbsa, "healthcare_employment": val})

        time.sleep(0.5)  # be polite to BLS API

    df = pd.DataFrame(results)
    df["healthcare_employment"] = pd.to_numeric(df["healthcare_employment"], errors="coerce")
    log.info(f"BLS: received employment data for {len(df):,} of {len(cbsa_codes):,} CBSAs")
    return df


def main():
    today = date.today().isoformat()

    pop_path = RAW_DIR / f"census_cbsa_pop_{today}.csv"
    bls_path = RAW_DIR / f"bls_oes_{today}.csv"

    # --- Census Population ---
    if pop_path.exists():
        log.info(f"Loading cached population data: {pop_path.name}")
        pop_df = pd.read_csv(pop_path, dtype=str)
        pop_df["population"] = pd.to_numeric(pop_df["population"], errors="coerce")
    else:
        pop_df = fetch_cbsa_population()
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        pop_df.to_csv(pop_path, index=False)
        log.info(f"Saved population data to {pop_path.name}")

    cbsa_codes = pop_df["cbsa_code"].tolist()

    # --- BLS Employment ---
    if bls_path.exists():
        log.info(f"Loading cached BLS data: {bls_path.name}")
        bls_df = pd.read_csv(bls_path, dtype=str)
        bls_df["healthcare_employment"] = pd.to_numeric(bls_df["healthcare_employment"], errors="coerce")
    else:
        bls_df = fetch_bls_employment(cbsa_codes)
        bls_df.to_csv(bls_path, index=False)
        log.info(f"Saved BLS data to {bls_path.name}")

    # --- Join and compute density ---
    df = pop_df.merge(bls_df, on="cbsa_code", how="left")
    df["provider_density_per_100k"] = (
        df["healthcare_employment"] / df["population"] * 100_000
    ).round(1)

    missing_emp = df["healthcare_employment"].isna().sum()
    log.info(f"CBSAs missing BLS employment data: {missing_emp:,} (suppressed by BLS for small areas)")

    log.info(f"\nFinal shape: {df.shape}")
    log.info(f"Employment range: {df['healthcare_employment'].min():.0f} – {df['healthcare_employment'].max():.0f}")
    log.info(f"Density range: {df['provider_density_per_100k'].min():.1f} – {df['provider_density_per_100k'].max():.1f} per 100k")
    log.info(f"\nTop 5 highest density:\n{df.nlargest(5, 'provider_density_per_100k')[['cbsa_name','provider_density_per_100k']].to_string()}")
    log.info(f"\nBottom 5 lowest density (with data):\n{df.dropna(subset=['healthcare_employment']).nsmallest(5, 'provider_density_per_100k')[['cbsa_name','provider_density_per_100k']].to_string()}")

    out_path = PROCESSED_DIR / "bls_oes_clean.parquet"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    log.info(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
