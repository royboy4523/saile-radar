"""
Data Unification (Step 1.5)
Joins all four cleaned datasets into a single facility-level dataframe:
  - CMS (base): one row per facility
  - HRSA: county-level HPSA scores joined via county_fips
  - BLS: metro-level provider density joined via cbsa_code
  - AAMC: national shortage weights stored as a reference column

Output: data/processed/unified_facilities.parquet
        docs/data_notes/data_dictionary.md
"""

import logging
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
EXTERNAL_DIR = PROJECT_ROOT / "data" / "external"
DOCS_DIR = PROJECT_ROOT / "docs" / "data_notes"

# AAMC category → shortfall midpoint (used as a national weight reference)
# Midpoint of (shortfall_low + shortfall_high) / 2, floored at 0 for surpluses
AAMC_WEIGHT = {
    "Primary Care": 30300,       # midpoint of 20200–40400
    "Surgical Specialties": 15000,  # midpoint of 10100–19900
    "Other Specialties": 7600,   # midpoint of -4300–19500 (broad range, use midpoint)
    "Medical Specialties": 900,  # midpoint of -3700–5500
    "Hospitalist": 0,            # midpoint of -4900–1300 → near zero
}


def load_datasets() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    log.info("Loading CMS facilities...")
    cms = pd.read_parquet(PROCESSED_DIR / "cms_pos_clean.parquet")
    log.info(f"  CMS: {len(cms):,} facilities")

    log.info("Loading HRSA HPSA designations...")
    hrsa = pd.read_parquet(PROCESSED_DIR / "hrsa_hpsa_clean.parquet")
    log.info(f"  HRSA: {len(hrsa):,} designations")

    log.info("Loading BLS employment data...")
    bls = pd.read_parquet(PROCESSED_DIR / "bls_oes_clean.parquet")
    log.info(f"  BLS: {len(bls):,} metro areas ({bls['healthcare_employment'].notna().sum()} with employment data)")

    log.info("Loading AAMC specialty shortages...")
    aamc = pd.read_csv(EXTERNAL_DIR / "aamc_specialty_shortages.csv")
    log.info(f"  AAMC: {len(aamc):,} specialties")

    return cms, hrsa, bls, aamc


def aggregate_hrsa(hrsa: pd.DataFrame) -> pd.DataFrame:
    """Aggregate HRSA to one row per county: max HPSA score per specialty category."""
    log.info("Aggregating HRSA to county level (max score per specialty)...")

    agg = (
        hrsa.groupby(["county_fips", "specialty_category"])["hpsa_score"]
        .max()
        .unstack(fill_value=None)
        .reset_index()
    )

    # Rename columns
    rename = {}
    for col in agg.columns:
        if col != "county_fips":
            rename[col] = f"hpsa_score_{col}"
    agg = agg.rename(columns=rename)

    # Boolean flags
    for specialty in ["primary_care", "dental", "mental_health"]:
        score_col = f"hpsa_score_{specialty}"
        if score_col in agg.columns:
            agg[f"has_hpsa_{specialty}"] = agg[score_col].notna()

    # Overall max score and designation flag
    score_cols = [c for c in agg.columns if c.startswith("hpsa_score_")]
    agg["hpsa_score_max"] = agg[score_cols].max(axis=1)
    agg["has_hpsa_any"] = agg["has_hpsa_primary_care"] | agg["has_hpsa_dental"] | agg["has_hpsa_mental_health"]

    log.info(f"  HRSA aggregated: {len(agg):,} unique counties")
    return agg


def join_hrsa(cms: pd.DataFrame, hrsa_county: pd.DataFrame) -> pd.DataFrame:
    log.info("Joining CMS → HRSA (via county_fips)...")
    df = cms.merge(hrsa_county, on="county_fips", how="left")

    # Fill boolean flags to False where no HPSA exists
    bool_cols = [c for c in df.columns if c.startswith("has_hpsa_")]
    df[bool_cols] = df[bool_cols].fillna(False)

    matched = df["has_hpsa_any"].sum()
    pct = matched / len(df) * 100
    log.info(f"  {matched:,} of {len(df):,} facilities ({pct:.1f}%) in a county with at least one HPSA designation")
    return df


def join_bls(df: pd.DataFrame, bls: pd.DataFrame) -> pd.DataFrame:
    log.info("Joining CMS → BLS (via cbsa_code)...")
    bls_slim = bls[["cbsa_code", "cbsa_name", "population", "healthcare_employment", "provider_density_per_100k"]]
    df = df.merge(bls_slim, on="cbsa_code", how="left")

    matched = df["provider_density_per_100k"].notna().sum()
    pct = matched / len(df) * 100
    log.info(f"  {matched:,} of {len(df):,} facilities ({pct:.1f}%) matched to BLS metro employment data")
    return df


def add_aamc_weights(df: pd.DataFrame) -> pd.DataFrame:
    """
    AAMC data is national-level — no per-facility join key exists.
    We store the category weights as a reference; Phase 2 scoring will apply them
    based on the specialty mix of facilities in each area.
    For now, flag urban vs rural and primary care HPSA as proxies.
    """
    log.info("Adding AAMC national shortage weight reference...")
    # Map provider_category to AAMC specialty group as best approximation
    # Category 01 = acute care → mixed specialties; 03 = psychiatric → mental health
    category_to_aamc = {
        "01": "Primary Care / Surgical / Other",   # general acute care — mixed
        "02": "Primary Care",                       # long-term care
        "03": "Other Specialties",                  # psychiatric (psychiatry is Other)
        "04": "Other Specialties",                  # rehabilitation (PM&R)
        "05": "Primary Care",                       # children's
        "06": "Primary Care",                       # chronic disease
        "11": "Primary Care",                       # critical access (rural primary care)
    }
    df["aamc_category_approx"] = df["provider_category"].map(category_to_aamc).fillna("Unknown")
    log.info("  AAMC category approximation added based on CMS provider category code")
    return df


def validate(df: pd.DataFrame) -> None:
    log.info("\n--- Validation ---")
    log.info(f"Total facilities: {len(df):,}")
    log.info(f"Duplicate provider numbers: {df['cms_provider_num'].duplicated().sum()}")

    hrsa_pct = df["has_hpsa_any"].sum() / len(df) * 100
    bls_pct = df["provider_density_per_100k"].notna().sum() / len(df) * 100
    log.info(f"HPSA coverage: {hrsa_pct:.1f}% (target >80%): {'PASS' if hrsa_pct > 80 else 'WARN'}")
    log.info(f"BLS coverage:  {bls_pct:.1f}% (informational — BLS suppresses small areas)")

    log.info(f"\nOwnership breakdown:\n{df['ownership_type'].value_counts().to_string()}")
    log.info(f"\nHPSA designation breakdown:")
    log.info(f"  Primary care HPSA:  {df['has_hpsa_primary_care'].sum():,}")
    log.info(f"  Dental HPSA:        {df['has_hpsa_dental'].sum():,}")
    log.info(f"  Mental health HPSA: {df['has_hpsa_mental_health'].sum():,}")
    log.info(f"  Any HPSA:           {df['has_hpsa_any'].sum():,}")


def write_data_dictionary(df: pd.DataFrame) -> None:
    lines = [
        "# Data Dictionary — unified_facilities.parquet",
        "",
        "One row per CMS-certified facility. Generated by `src/ingest/unify.py`.",
        "",
        "| Column | Type | Source | Description |",
        "|--------|------|--------|-------------|",
    ]

    schema = {
        "cms_provider_num":          ("str",   "CMS POS",  "CMS Certification Number (unique facility ID)"),
        "facility_name":             ("str",   "CMS POS",  "Facility name"),
        "address":                   ("str",   "CMS POS",  "Street address"),
        "city":                      ("str",   "CMS POS",  "City"),
        "state":                     ("str",   "CMS POS",  "State abbreviation"),
        "zip":                       ("str",   "CMS POS",  "5-digit ZIP code"),
        "county_fips":               ("str",   "CMS POS",  "5-digit county FIPS code"),
        "bed_count":                 ("int",   "CMS POS",  "Total licensed bed count"),
        "ownership_type":            ("str",   "CMS POS",  "nonprofit / for_profit / government / other"),
        "is_for_profit":             ("bool",  "CMS POS",  "True if for-profit facility"),
        "provider_category":         ("str",   "CMS POS",  "CMS facility category code (01=acute, 03=psych, 11=CAH, etc.)"),
        "provider_subtype":          ("str",   "CMS POS",  "CMS facility sub-category code"),
        "cbsa_code":                 ("str",   "CMS POS",  "Core-Based Statistical Area code (metro area)"),
        "urban_rural":               ("str",   "CMS POS",  "U=urban, R=rural (CBSA classification)"),
        "hpsa_score_primary_care":   ("float", "HRSA",     "Max primary care HPSA score in this county (0–25; higher = more severe shortage)"),
        "hpsa_score_dental":         ("float", "HRSA",     "Max dental HPSA score in this county (0–26)"),
        "hpsa_score_mental_health":  ("float", "HRSA",     "Max mental health HPSA score in this county (0–25)"),
        "hpsa_score_max":            ("float", "HRSA",     "Highest HPSA score across all three specialty categories for this county"),
        "has_hpsa_primary_care":     ("bool",  "HRSA",     "True if county has an active primary care HPSA designation"),
        "has_hpsa_dental":           ("bool",  "HRSA",     "True if county has an active dental HPSA designation"),
        "has_hpsa_mental_health":    ("bool",  "HRSA",     "True if county has an active mental health HPSA designation"),
        "has_hpsa_any":              ("bool",  "HRSA",     "True if county has any active HPSA designation"),
        "cbsa_name":                 ("str",   "BLS/Census","Metro area name"),
        "population":                ("int",   "Census",   "2023 metro area population estimate"),
        "healthcare_employment":     ("float", "BLS OES",  "Total healthcare practitioners employed in metro area (SOC 29-0000); null if BLS-suppressed"),
        "provider_density_per_100k": ("float", "BLS OES",  "Healthcare practitioners per 100,000 residents; null if BLS-suppressed"),
        "aamc_category_approx":      ("str",   "AAMC",     "Approximate AAMC specialty category based on CMS provider category code"),
        "fips_state_cd":             ("str",   "CMS POS",  "FIPS state code (2-digit)"),
        "fips_cnty_cd":              ("str",   "CMS POS",  "FIPS county code (3-digit)"),
        "gnrl_cntl_type_cd":         ("str",   "CMS POS",  "Raw CMS ownership/control type code"),
        "pgm_prtcptn_cd":            ("str",   "CMS POS",  "Medicare/Medicaid participation code"),
        "pgm_trmntn_cd":             ("str",   "CMS POS",  "Termination code (00 = active)"),
    }

    for col in df.columns:
        if col in schema:
            dtype, source, desc = schema[col]
        else:
            dtype, source, desc = (str(df[col].dtype), "derived", "")
        lines.append(f"| `{col}` | {dtype} | {source} | {desc} |")

    lines += [
        "",
        "## Notes",
        "",
        "- **HPSA scores** are aggregated to the county level (max score across all designations).",
        "  A facility in a county with a score of 25 is in an area with the most severe shortage.",
        "- **BLS employment and density** are null for facilities in metro areas where BLS suppresses",
        "  data due to small sample sizes. See `docs/data_notes/overview.md` for details.",
        "- **AAMC category** is an approximation based on CMS provider category code.",
        "  The scoring model (Phase 2) applies AAMC national shortage weights at scoring time.",
        "- **is_for_profit** facilities are kept in this dataset but should be filtered out",
        "  before final target selection.",
    ]

    out_path = DOCS_DIR / "data_dictionary.md"
    out_path.write_text("\n".join(lines))
    log.info(f"Data dictionary written to {out_path}")


def main():
    cms, hrsa, bls, aamc = load_datasets()

    hrsa_county = aggregate_hrsa(hrsa)
    df = join_hrsa(cms, hrsa_county)
    df = join_bls(df, bls)
    df = add_aamc_weights(df)

    validate(df)

    out_path = PROCESSED_DIR / "unified_facilities.parquet"
    df.to_parquet(out_path, index=False)
    log.info(f"\nSaved unified dataframe to {out_path}")
    log.info(f"Final shape: {df.shape}")

    write_data_dictionary(df)


if __name__ == "__main__":
    main()
