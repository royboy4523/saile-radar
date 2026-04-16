"""
HRSA HPSA Ingest
Downloads all three HPSA designation files (primary care, dental, mental health),
cleans and standardizes columns, and saves a combined parquet to data/processed/.
"""

import logging
import sys
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

HPSA_FILES = {
    "primary_care": "https://data.hrsa.gov/DataDownload/DD_Files/BCD_HPSA_FCT_DET_PC.csv",
    "dental": "https://data.hrsa.gov/DataDownload/DD_Files/BCD_HPSA_FCT_DET_DH.csv",
    "mental_health": "https://data.hrsa.gov/DataDownload/DD_Files/BCD_HPSA_FCT_DET_MH.csv",
}

COLUMNS_KEEP = {
    "HPSA ID": "hpsa_id",
    "HPSA Name": "hpsa_name",
    "Designation Type": "designation_type",
    "HPSA Score": "hpsa_score",
    "HPSA Status": "hpsa_status",
    "State Abbreviation": "state",
    "State and County Federal Information Processing Standard Code": "county_fips",
    "Common State County FIPS Code": "county_fips",  # alternate column name in some files
    "Designation Last Update Date": "last_update_date",
    "HPSA Formal Ratio": "hpsa_formal_ratio",
    "Primary State Name": "state_name",
}


def download(url: str, dest: Path) -> Path:
    log.info(f"Downloading {url}")
    resp = requests.get(url, stream=True, timeout=120)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1 << 20):
            f.write(chunk)
    log.info(f"Saved {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


def clean(df: pd.DataFrame, specialty: str) -> pd.DataFrame:
    # Normalize column names for lookup
    rename = {}
    for raw_col, clean_col in COLUMNS_KEEP.items():
        if raw_col in df.columns and clean_col not in rename.values():
            rename[raw_col] = clean_col
    df = df.rename(columns=rename)

    keep = [c for c in COLUMNS_KEEP.values() if c in df.columns]
    # Deduplicate in case both county_fips aliases matched
    keep = list(dict.fromkeys(keep))
    df = df[keep].copy()

    df["specialty_category"] = specialty

    # Keep only active designations
    if "hpsa_status" in df.columns:
        before = len(df)
        df = df[df["hpsa_status"].str.strip().str.upper() == "DESIGNATED"]
        log.info(f"  {specialty}: dropped {before - len(df)} non-active rows, kept {len(df)}")

    # HPSA score to numeric, drop rows with missing score
    df["hpsa_score"] = pd.to_numeric(df["hpsa_score"], errors="coerce")
    null_scores = df["hpsa_score"].isna().sum()
    if null_scores:
        log.warning(f"  {specialty}: dropping {null_scores} rows with null HPSA score")
    df = df.dropna(subset=["hpsa_score"])
    df["hpsa_score"] = df["hpsa_score"].astype(int)

    # Standardize county FIPS to 5-digit zero-padded string
    if "county_fips" in df.columns:
        df["county_fips"] = (
            df["county_fips"]
            .astype(str)
            .str.strip()
            .str.replace(r"\.0$", "", regex=True)
            .str.zfill(5)
        )
        df.loc[df["county_fips"] == "00000", "county_fips"] = None

    if "state" in df.columns:
        df["state"] = df["state"].str.strip().str.upper()

    return df.reset_index(drop=True)


def main():
    today = date.today().isoformat()
    frames = []

    for specialty, url in HPSA_FILES.items():
        raw_path = RAW_DIR / f"hrsa_hpsa_{specialty}_{today}.csv"

        if not raw_path.exists():
            download(url, raw_path)
        else:
            log.info(f"Raw file already exists, skipping download: {raw_path.name}")

        log.info(f"Loading {raw_path.name}")
        df = pd.read_csv(raw_path, dtype=str, low_memory=False)
        log.info(f"  {specialty}: {len(df):,} rows, {len(df.columns)} columns")

        df = clean(df, specialty)
        log.info(f"  {specialty}: {len(df):,} rows after cleaning")
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    log.info(f"Combined: {len(combined):,} total HPSA designations")

    out_path = PROCESSED_DIR / "hrsa_hpsa_clean.parquet"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(out_path, index=False)
    log.info(f"Saved cleaned data to {out_path}")

    log.info("\nColumn summary:")
    log.info(combined.dtypes.to_string())
    log.info(f"\nScore range: {combined['hpsa_score'].min()} – {combined['hpsa_score'].max()}")
    log.info(f"Specialty breakdown:\n{combined['specialty_category'].value_counts().to_string()}")
    if "designation_type" in combined.columns:
        log.info(f"Designation types:\n{combined['designation_type'].value_counts().to_string()}")
    else:
        log.warning("designation_type column not found — check source column name in raw CSV")


if __name__ == "__main__":
    main()
