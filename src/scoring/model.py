"""
Shortage Scoring Engine (Step 2.2)
Implements the composite shortage score defined in docs/scoring_methodology.md.

Formula:
    composite_score = (0.40 × hpsa_component)
                    + (0.30 × density_component)
                    + (0.20 × aamc_component)
                    + (0.10 × rural_component)

Input:  data/processed/unified_facilities.parquet
Output: data/processed/scored_facilities.parquet
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

# Weights — must sum to 1.0
W_HPSA    = 0.40
W_DENSITY = 0.30
W_AAMC    = 0.20
W_RURAL   = 0.10

# AAMC category → normalized shortfall score (midpoint / 30300)
# See docs/scoring_methodology.md Component 3 for derivation
AAMC_NORMALIZED = {
    "Primary Care":         30300 / 30300,  # 1.00
    "Surgical Specialties": 15000 / 30300,  # 0.50
    "Other Specialties":     7600 / 30300,  # 0.25
    "Medical Specialties":    900 / 30300,  # 0.03
    "Hospitalist":              0 / 30300,  # 0.00
    # Mixed/unknown categories — use median across five buckets
    "Primary Care / Surgical / Other": (30300 + 15000 + 7600) / 3 / 30300,
    "Unknown": 0.0,
}

HPSA_MAX = 26.0  # HPSA scores range 0–26


def compute_hpsa_component(df: pd.DataFrame) -> pd.Series:
    """Min-max normalization: hpsa_score_max / 26. Null → 0."""
    return (df["hpsa_score_max"].fillna(0) / HPSA_MAX).clip(0, 1)


def compute_density_component(df: pd.DataFrame) -> pd.Series:
    """
    Percentile rank of provider_density_per_100k, then inverted.
    Low density → high shortage score.
    Null (BLS-suppressed) → 0.5 (neutral imputation, neither rewarded nor penalized).
    """
    density = df["provider_density_per_100k"].copy()

    # Rank only non-null values
    has_data = density.notna()
    rank = pd.Series(0.5, index=df.index)  # default for null rows

    if has_data.sum() > 0:
        rank[has_data] = density[has_data].rank(pct=True)

    return (1 - rank).clip(0, 1)


def compute_aamc_component(df: pd.DataFrame) -> pd.Series:
    """Map aamc_category_approx to normalized shortfall weight. Unknown → 0."""
    return df["aamc_category_approx"].map(AAMC_NORMALIZED).fillna(0.0)


def compute_rural_component(df: pd.DataFrame) -> pd.Series:
    """Binary: R=1.0, U or null=0.0."""
    return (df["urban_rural"].fillna("U") == "R").astype(float)


def score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["hpsa_component"]    = compute_hpsa_component(df)
    df["density_component"] = compute_density_component(df)
    df["aamc_component"]    = compute_aamc_component(df)
    df["rural_component"]   = compute_rural_component(df)

    df["composite_score"] = (
        W_HPSA    * df["hpsa_component"]
        + W_DENSITY * df["density_component"]
        + W_AAMC    * df["aamc_component"]
        + W_RURAL   * df["rural_component"]
    ).round(4)

    df = df.sort_values("composite_score", ascending=False).reset_index(drop=True)
    df["score_rank"] = df.index + 1

    return df


def validate(df: pd.DataFrame) -> None:
    log.info("\n--- Scoring Validation ---")
    log.info(f"Total facilities scored: {len(df):,}")

    score_range = df["composite_score"]
    log.info(f"Score range: {score_range.min():.4f} – {score_range.max():.4f}")
    log.info(f"Score mean:  {score_range.mean():.4f}")
    log.info(f"Score median:{score_range.median():.4f}")

    log.info(f"\nComponent means:")
    for col in ["hpsa_component", "density_component", "aamc_component", "rural_component"]:
        log.info(f"  {col}: {df[col].mean():.4f}")

    log.info(f"\nTop 10 facilities:")
    top_cols = ["score_rank", "facility_name", "city", "state", "composite_score",
                "hpsa_score_max", "ownership_type", "urban_rural"]
    log.info(df[top_cols].head(10).to_string(index=False))

    # Score distribution
    thresholds = [0.90, 0.80, 0.70, 0.60, 0.50]
    log.info(f"\nFacilities by composite score threshold (all ownership types):")
    for t in thresholds:
        n = (df["composite_score"] >= t).sum()
        log.info(f"  >= {t:.2f}: {n:,}")

    # Nonprofit-only view (for Stage 2 planning)
    nonprofit = df[df["ownership_type"] == "nonprofit"]
    log.info(f"\nNonprofit facilities only ({len(nonprofit):,} total):")
    for t in thresholds:
        n = (nonprofit["composite_score"] >= t).sum()
        log.info(f"  >= {t:.2f}: {n:,}")


def set_stage2_threshold(df: pd.DataFrame, target_low: int = 200, target_high: int = 800) -> float:
    """
    Find the composite_score threshold that yields target_low–target_high
    nonprofit facilities for Stage 2. Returns the threshold.
    """
    nonprofit = df[df["ownership_type"] == "nonprofit"].copy()
    nonprofit_sorted = nonprofit.sort_values("composite_score", ascending=False)

    # Binary search for a threshold that puts count in [target_low, target_high]
    # Use midpoint of the range as the target
    target = (target_low + target_high) // 2  # 500

    if len(nonprofit_sorted) <= target_high:
        threshold = nonprofit_sorted["composite_score"].min()
        log.info(f"All {len(nonprofit_sorted):,} nonprofits fit within Stage 2 target range — threshold = {threshold:.4f}")
        return threshold

    cutoff_score = nonprofit_sorted.iloc[target - 1]["composite_score"]
    actual_count = (nonprofit["composite_score"] >= cutoff_score).sum()
    log.info(f"\nStage 2 threshold: composite_score >= {cutoff_score:.4f}")
    log.info(f"  Targets {target:,} nonprofits; actual count at threshold: {actual_count:,}")
    log.info(f"  (Target range was {target_low:,}–{target_high:,})")
    return cutoff_score


def main():
    input_path = PROCESSED_DIR / "unified_facilities.parquet"
    if not input_path.exists():
        log.error(f"Input not found: {input_path}")
        log.error("Run src/ingest/unify.py first.")
        sys.exit(1)

    log.info(f"Loading {input_path} ...")
    df = pd.read_parquet(input_path)
    log.info(f"  Loaded: {len(df):,} facilities")

    log.info("Computing shortage scores...")
    df_scored = score(df)

    validate(df_scored)

    threshold = set_stage2_threshold(df_scored)
    df_scored["is_stage2_candidate"] = (
        (df_scored["composite_score"] >= threshold)
        & (df_scored["ownership_type"] == "nonprofit")
    )
    stage2_count = df_scored["is_stage2_candidate"].sum()
    log.info(f"\nStage 2 candidates flagged: {stage2_count:,}")

    out_path = PROCESSED_DIR / "scored_facilities.parquet"
    df_scored.to_parquet(out_path, index=False)
    log.info(f"\nSaved scored facilities to {out_path}")
    log.info(f"Final shape: {df_scored.shape}")


if __name__ == "__main__":
    main()
