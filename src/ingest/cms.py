"""
CMS Provider of Services (POS) Ingest
Downloads the hospital/non-hospital POS file from NBER's CMS mirror,
filters to hospitals, cleans key fields, flags for-profit facilities,
and saves to data/processed/ as parquet.
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

POS_URL = "https://data.nber.org/cms/pos/csv/2024/posotherdec2024.csv"

# prvdr_ctgry_cd values that represent hospitals
# 01 = short-term acute care, 02 = long-term, 03 = psychiatric,
# 04 = rehabilitation, 05 = children's, 06 = chronic disease,
# 11 = critical access hospital
HOSPITAL_CATEGORY_CODES = {"01", "02", "03", "04", "05", "06", "11"}

# gnrl_cntl_type_cd actual CMS coding:
# 01 = Voluntary Nonprofit - Church
# 02 = Voluntary Nonprofit - Private
# 03 = Voluntary Nonprofit - Other
# 04 = Proprietary (for-profit)
# 05 = Government - Federal
# 06 = Government - State
# 07 = Government - Local
# 08 = Government - City-County / Special District
# 09 = Government - County
# 10 = Government - City
# 11 = Government - Hospital District
# 12 = Government - Other
# 13 = Other
NONPROFIT_CODES = {"01", "02", "03"}
FOR_PROFIT_CODES = {"04"}
GOVERNMENT_CODES = {"05", "06", "07", "08", "09", "10", "11", "12"}

OWNERSHIP_LABEL = {
    **{c: "nonprofit" for c in NONPROFIT_CODES},
    **{c: "for_profit" for c in FOR_PROFIT_CODES},
    **{c: "government" for c in GOVERNMENT_CODES},
    "13": "other",
}

COLUMNS_KEEP = [
    "prvdr_num",          # CMS certification number
    "fac_name",           # facility name
    "st_adr",             # street address
    "city_name",          # city
    "state_cd",           # state abbreviation
    "zip_cd",             # ZIP code
    "fips_state_cd",      # FIPS state code
    "fips_cnty_cd",       # FIPS county code
    "bed_cnt",            # total bed count
    "gnrl_cntl_type_cd",  # ownership/control type
    "prvdr_ctgry_cd",     # provider category
    "prvdr_ctgry_sbtyp_cd",  # provider sub-category
    "pgm_prtcptn_cd",     # Medicare/Medicaid participation
    "pgm_trmntn_cd",      # termination code (00 = active)
    "cbsa_cd",            # CBSA/metro area code
    "cbsa_urbn_rrl_ind",  # urban/rural indicator
]


def download(url: str, dest: Path) -> Path:
    log.info(f"Downloading {url}")
    resp = requests.get(url, stream=True, timeout=300)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1 << 20):
            f.write(chunk)
            downloaded += len(chunk)
            if downloaded % (10 << 20) == 0:
                log.info(f"  {downloaded / 1e6:.0f} MB downloaded...")
    log.info(f"Saved {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


def build_county_fips(df: pd.DataFrame) -> pd.Series:
    state = df["fips_state_cd"].astype(str).str.strip().str.zfill(2)
    county = df["fips_cnty_cd"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True).str.zfill(3)
    fips = state + county
    # Null out placeholder values
    fips = fips.where(fips != "00000", None)
    return fips


def main():
    today = date.today().isoformat()
    raw_path = RAW_DIR / f"cms_pos_{today}.csv"

    if not raw_path.exists():
        download(POS_URL, raw_path)
    else:
        log.info(f"Raw file already exists, skipping download: {raw_path.name}")

    log.info(f"Loading {raw_path.name} (this may take a moment)...")
    df = pd.read_csv(raw_path, dtype=str, low_memory=False)
    log.info(f"Loaded: {len(df):,} rows, {len(df.columns)} columns")

    # Keep only needed columns (ignore any missing ones)
    cols = [c for c in COLUMNS_KEEP if c in df.columns]
    missing = set(COLUMNS_KEEP) - set(cols)
    if missing:
        log.warning(f"Columns not found in source, skipping: {missing}")
    df = df[cols].copy()

    # Filter: active facilities only (pgm_trmntn_cd == '00')
    before = len(df)
    df = df[df["pgm_trmntn_cd"].str.strip() == "00"]
    log.info(f"Active facilities: {len(df):,} (dropped {before - len(df):,} terminated)")

    # Filter: hospitals only
    df["prvdr_ctgry_cd"] = df["prvdr_ctgry_cd"].str.strip().str.zfill(2)
    before = len(df)
    df = df[df["prvdr_ctgry_cd"].isin(HOSPITAL_CATEGORY_CODES)]
    log.info(f"Hospitals only: {len(df):,} (dropped {before - len(df):,} non-hospital facilities)")

    # Build standardized county FIPS
    df["county_fips"] = build_county_fips(df)

    # Ownership type
    df["gnrl_cntl_type_cd"] = df["gnrl_cntl_type_cd"].str.strip().str.zfill(2)
    df["ownership_type"] = df["gnrl_cntl_type_cd"].map(OWNERSHIP_LABEL).fillna("unknown")
    df["is_for_profit"] = df["ownership_type"] == "for_profit"

    # Bed count to numeric
    df["bed_cnt"] = pd.to_numeric(df["bed_cnt"], errors="coerce").astype("Int64")

    # Clean string fields
    for col in ["fac_name", "city_name", "st_adr"]:
        if col in df.columns:
            df[col] = df[col].str.strip().str.title()

    df["state_cd"] = df["state_cd"].str.strip().str.upper()
    df["zip_cd"] = df["zip_cd"].astype(str).str.strip().str[:5].str.zfill(5)
    df["cbsa_cd"] = df["cbsa_cd"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)

    # Rename for clarity
    df = df.rename(columns={
        "prvdr_num": "cms_provider_num",
        "fac_name": "facility_name",
        "st_adr": "address",
        "city_name": "city",
        "state_cd": "state",
        "zip_cd": "zip",
        "bed_cnt": "bed_count",
        "cbsa_cd": "cbsa_code",
        "cbsa_urbn_rrl_ind": "urban_rural",
        "prvdr_ctgry_cd": "provider_category",
        "prvdr_ctgry_sbtyp_cd": "provider_subtype",
    })

    df = df.reset_index(drop=True)

    # Summary stats
    log.info(f"\nFinal shape: {df.shape}")
    log.info(f"Ownership breakdown:\n{df['ownership_type'].value_counts().to_string()}")
    log.info(f"For-profit count: {df['is_for_profit'].sum():,}")
    log.info(f"Missing county FIPS: {df['county_fips'].isna().sum():,}")
    log.info(f"Bed count — median: {df['bed_count'].median()}, max: {df['bed_count'].max()}")
    log.info(f"States: {df['state'].nunique()}")

    out_path = PROCESSED_DIR / "cms_pos_clean.parquet"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    log.info(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
