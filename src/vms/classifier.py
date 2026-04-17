"""
VMS Classification Logic (Step 3.3)
Uses IRS Form 990 contractor expense data from ProPublica to estimate whether each
Stage 2 facility is likely using a Vendor Management System (VMS) for physician staffing.

Classification logic:
    contractor_ratio = Part IX contractor fees / total functional expenses

    HIGH   (likely_vms):   ratio >= 0.15  — heavy contractor spend, consistent with VMS
    LOW    (direct_hire):  ratio <  0.05  — minimal contractor spend
    MEDIUM (uncertain):    0.05 <= ratio < 0.15 — ambiguous

Unmatched facilities (no EIN found) → classified as "uncertain"
Matched EIN but no 990 data       → classified as "uncertain"

Output: data/processed/facilities_final.parquet
        docs/vms_methodology.md
"""

import logging
import sys
from pathlib import Path

import pandas as pd

from src.vms.propublica import ProPublicaClient

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DOCS_DIR = PROJECT_ROOT / "docs"

# Contractor ratio thresholds
THRESHOLD_HIGH = 0.15   # >= 15% of expenses on contractors → likely VMS
THRESHOLD_LOW  = 0.05   # <  5% of expenses on contractors → likely direct hire

# Minimum total functional expenses to trust a 990 match.
# Matches below this floor are likely foundations/auxiliaries, not operating hospitals.
# A nonprofit hospital should have at least $2M in annual operating expenses.
MIN_EXPENSE_FLOOR = 2_000_000


def classify_ratio(ratio: float | None) -> str:
    if ratio is None:
        return "uncertain"
    if ratio >= THRESHOLD_HIGH:
        return "likely_vms"
    if ratio < THRESHOLD_LOW:
        return "direct_hire"
    return "uncertain"


def pull_990_data(crosswalk: pd.DataFrame) -> pd.DataFrame:
    """
    For each facility with a matched EIN, fetch 990 expense data from ProPublica.
    Returns dataframe with ein, contractor_ratio, contractor_fees, total_expenses, tax_year.
    """
    client = ProPublicaClient()
    matched = crosswalk[crosswalk["matched_ein"].notna()].copy()
    log.info(f"Pulling 990 data for {len(matched):,} matched facilities...")

    records = []
    for i, row in matched.iterrows():
        ein = row["matched_ein"]
        result = client.get_expenses(ein)

        if result and result.get("has_data"):
            records.append({
                "cms_provider_num": row["cms_provider_num"],
                "matched_ein": ein,
                "tax_year": result.get("tax_year"),
                "form_type": result.get("form_type"),
                "total_functional_expenses": result.get("total_functional_expenses"),
                "contractor_fees": result.get("contractor_fees"),
                "contractor_ratio": result.get("contractor_ratio"),
                "has_990_data": True,
            })
        else:
            records.append({
                "cms_provider_num": row["cms_provider_num"],
                "matched_ein": ein,
                "tax_year": None,
                "form_type": None,
                "total_functional_expenses": None,
                "contractor_fees": None,
                "contractor_ratio": None,
                "has_990_data": False,
            })

        if len(records) % 25 == 0:
            log.info(f"  {len(records)}/{len(matched)} EINs processed...")

    return pd.DataFrame(records)


def classify(crosswalk: pd.DataFrame, expenses_df: pd.DataFrame) -> pd.DataFrame:
    """
    Join 990 expense data back to all facilities and apply VMS classification.
    990 matches with total_functional_expenses < MIN_EXPENSE_FLOOR are treated as
    foundation/auxiliary mismatches and downgraded to uncertain.
    """
    df = crosswalk.merge(
        expenses_df[["cms_provider_num", "tax_year", "form_type",
                     "total_functional_expenses", "contractor_fees",
                     "contractor_ratio", "has_990_data"]],
        on="cms_provider_num",
        how="left",
    )

    df["has_990_data"] = df["has_990_data"].fillna(False)

    # Nullify 990 data for implausibly small expense figures — likely auxiliary/foundation match
    expense_too_small = df["total_functional_expenses"] < MIN_EXPENSE_FLOOR
    anomaly_count = (df["has_990_data"] & expense_too_small).sum()
    if anomaly_count:
        log.info(f"  Downgrading {anomaly_count} low-expense 990 matches to uncertain "
                 f"(total_expenses < ${MIN_EXPENSE_FLOOR:,} — likely auxiliary/foundation match)")
        df.loc[expense_too_small, ["contractor_ratio", "has_990_data"]] = [None, False]

    df["vms_classification"] = df["contractor_ratio"].apply(classify_ratio)

    # Facilities with no EIN match are explicitly marked
    no_ein = df["matched_ein"].isna()
    df.loc[no_ein, "vms_classification"] = "uncertain"

    return df


def validate(df: pd.DataFrame) -> None:
    log.info("\n--- VMS Classification Summary ---")
    log.info(f"Total Stage 2 facilities: {len(df):,}")

    counts = df["vms_classification"].value_counts()
    for label, n in counts.items():
        pct = n / len(df) * 100
        log.info(f"  {label}: {n:,} ({pct:.1f}%)")

    has_data = df["has_990_data"].sum()
    log.info(f"\n  Facilities with 990 data: {has_data:,} of {len(df):,}")
    log.info(f"  EIN matched but no 990:   {(df['matched_ein'].notna() & ~df['has_990_data']).sum():,}")
    log.info(f"  No EIN match:             {df['matched_ein'].isna().sum():,}")

    log.info(f"\nTop 20 direct_hire candidates:")
    top_cols = ["facility_name", "city", "state", "composite_score",
                "contractor_ratio", "total_functional_expenses", "vms_classification"]
    direct = df[df["vms_classification"] == "direct_hire"].sort_values(
        "composite_score", ascending=False
    )
    log.info(direct[top_cols].head(20).to_string(index=False))

    log.info(f"\nTop 10 likely_vms:")
    vms = df[df["vms_classification"] == "likely_vms"].sort_values(
        "composite_score", ascending=False
    )
    if len(vms) > 0:
        log.info(vms[top_cols].head(10).to_string(index=False))
    else:
        log.info("  None identified.")


def write_methodology_doc(df: pd.DataFrame) -> None:
    direct = (df["vms_classification"] == "direct_hire").sum()
    vms = (df["vms_classification"] == "likely_vms").sum()
    uncertain = (df["vms_classification"] == "uncertain").sum()
    has_data = df["has_990_data"].sum()

    lines = [
        "# VMS Classification Methodology",
        "",
        "This document explains how Saile Radar classifies Stage 2 facilities as",
        "likely VMS users vs. direct-hire candidates.",
        "",
        "**Read this alongside `docs/scoring_methodology.md`.**",
        "",
        "---",
        "",
        "## What is a VMS?",
        "",
        "A Vendor Management System (VMS) is a software platform that some hospitals use to",
        "manage temporary physician staffing. When a hospital routes locum tenens hiring",
        "through a VMS, staffing companies like Saile must work through the VMS intermediary",
        "rather than directly with the hospital — increasing friction and reducing margin.",
        "",
        "Saile's highest-value targets are hospitals that hire locum tenens physicians directly,",
        "without a VMS in the middle.",
        "",
        "---",
        "",
        "## Data Source: IRS Form 990",
        "",
        "Nonprofit hospitals are required to file IRS Form 990 annually.",
        "Part IX of the 990 (Statement of Functional Expenses) includes:",
        "",
        "- **Line 11g**: Fees for services — outside contractors",
        "- **Total functional expenses**: All operating costs",
        "",
        "We use the ratio of contractor fees to total expenses as a proxy for VMS usage.",
        "",
        "**Key limitation:** Part IX contractor fees include ALL outside contractors,",
        "not just physician staffing. A hospital with high IT contractor spend or",
        "large construction projects will show a high ratio even if it has no VMS.",
        "This is the primary source of uncertainty in the model.",
        "",
        "---",
        "",
        "## Classification Thresholds",
        "",
        "```",
        f"contractor_ratio = contractor_fees / total_functional_expenses",
        "",
        f"direct_hire  : ratio < {THRESHOLD_LOW:.0%}   (minimal contractor spend)",
        f"uncertain    : {THRESHOLD_LOW:.0%} ≤ ratio < {THRESHOLD_HIGH:.0%}  (ambiguous)",
        f"likely_vms   : ratio ≥ {THRESHOLD_HIGH:.0%}  (heavy contractor spend)",
        "```",
        "",
        "---",
        "",
        "## Coverage and Results",
        "",
        f"| Category | Count |",
        f"|----------|-------|",
        f"| Stage 2 facilities | {len(df):,} |",
        f"| EIN matched | {df['matched_ein'].notna().sum():,} ({df['matched_ein'].notna().sum()/len(df)*100:.1f}%) |",
        f"| 990 data retrieved | {has_data:,} ({has_data/len(df)*100:.1f}%) |",
        f"| direct_hire | {direct:,} ({direct/len(df)*100:.1f}%) |",
        f"| likely_vms | {vms:,} ({vms/len(df)*100:.1f}%) |",
        f"| uncertain | {uncertain:,} ({uncertain/len(df)*100:.1f}%) |",
        "",
        "---",
        "",
        "## Why 63% of Facilities Are 'Uncertain'",
        "",
        "Three structural reasons limit EIN matching coverage:",
        "",
        "1. **Parent system EINs**: Many hospitals file 990s under a parent health system,",
        "   not the individual facility name. The EIN for 'Copper Queen Community Hospital'",
        "   may be registered as 'Copper Queen Community Health Foundation'.",
        "",
        "2. **Government-operated facilities**: Hospitals operated by county or state",
        "   governments do not file 990s — they are not nonprofit organizations.",
        "   These are still scored by the model but cannot be classified via 990 data.",
        "",
        "3. **Name format divergence**: CMS registers facilities under operational names;",
        "   the IRS BMF uses legal entity names. 'St. Joseph's Medical Center' and",
        "   'St Joseph Health System' may be the same organization.",
        "",
        "**Bottom line:** 'Uncertain' does not mean 'skip this facility.'",
        "It means 990 data was not available. A business development rep should",
        "approach uncertain facilities with a direct conversation rather than",
        "assuming VMS usage.",
        "",
        "---",
        "",
        "## Recommended Outreach Priority",
        "",
        "1. **direct_hire + high shortage score** → Highest priority. Most likely to",
        "   accept direct locum tenens engagement.",
        "",
        "2. **uncertain + high shortage score** → High priority. Shortage is real;",
        "   VMS status unknown. Worth a discovery call.",
        "",
        "3. **likely_vms + high shortage score** → Lower priority, but not excluded.",
        "   Some VMS relationships can be worked around; shortage signal is still real.",
        "",
        "---",
        "",
        "## Output File",
        "",
        "`data/processed/facilities_final.parquet` — All Stage 2 facilities with",
        "shortage score, EIN match, 990 expense data, and VMS classification.",
    ]

    out = DOCS_DIR / "vms_methodology.md"
    out.write_text("\n".join(lines))
    log.info(f"VMS methodology doc written to {out}")


def main():
    log.info("Loading EIN crosswalk...")
    crosswalk = pd.read_parquet(PROCESSED_DIR / "facility_ein_crosswalk.parquet")
    log.info(f"  {len(crosswalk):,} Stage 2 facilities")

    expenses_df = pull_990_data(crosswalk)

    has_data = expenses_df["has_990_data"].sum()
    log.info(f"\n990 data retrieved: {has_data:,} of {expenses_df['has_990_data'].notna().sum():,} matched EINs")

    df_final = classify(crosswalk, expenses_df)
    validate(df_final)
    write_methodology_doc(df_final)

    out = PROCESSED_DIR / "facilities_final.parquet"
    df_final.to_parquet(out, index=False)
    log.info(f"\nSaved final classified facilities to {out}")
    log.info(f"Shape: {df_final.shape}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    main()
