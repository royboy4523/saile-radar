"""
EIN Crosswalk (Step 3.2)
Matches CMS facility names to IRS EINs using a two-stage approach:
  1. ProPublica Nonprofit Explorer search API (primary — text-indexed, finds parent systems)
  2. IRS BMF fuzzy name match (fallback — covers organizations not yet in ProPublica)

Stage 2 candidates are predominantly ICF-DD homes, CAH hospitals, and skilled nursing
facilities — many of which file 990s under a parent nonprofit EIN, not the facility name.
ProPublica's search handles this better than raw name matching.

Input:  data/processed/stage2_candidates.parquet
        IRS BMF (downloaded from IRS, cached to data/raw/irs_bmf/)
Output: data/processed/facility_ein_crosswalk.parquet
        docs/data_notes/ein_crosswalk_unmatched.md
"""

import json
import logging
import re
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd
import requests
from rapidfuzz import fuzz, process

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "irs_bmf"
CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "propublica_search"
DOCS_DIR = PROJECT_ROOT / "docs" / "data_notes"
RAW_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

PROPUBLICA_SEARCH = "https://projects.propublica.org/nonprofits/api/v2/search.json"
IRS_BMF_BASE = "https://www.irs.gov/pub/irs-soi/eo"
IRS_BMF_FILES = {
    "eo1": f"{IRS_BMF_BASE}1.csv",
    "eo2": f"{IRS_BMF_BASE}2.csv",
    "eo3": f"{IRS_BMF_BASE}3.csv",
    "eo4": f"{IRS_BMF_BASE}4.csv",
}

RATE_LIMIT_SECONDS = 1.0
FUZZY_ACCEPT = 82   # minimum score to accept a ProPublica search result
BMF_ACCEPT = 85     # minimum score for BMF fallback match


def normalize(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for suffix in [" inc", " llc", " corp", " ltd", " lp"]:
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
    return text


_last_call = 0.0


def _rate_limit():
    global _last_call
    elapsed = time.time() - _last_call
    if elapsed < RATE_LIMIT_SECONDS:
        time.sleep(RATE_LIMIT_SECONDS - elapsed)
    _last_call = time.time()


def _search_cache_path(cms_num: str) -> Path:
    return CACHE_DIR / f"{cms_num}_search.json"


def propublica_search(facility_name: str, city: str, state: str, cms_num: str) -> list[dict]:
    """
    Query ProPublica Nonprofit Explorer search for a facility.
    Returns list of candidate organizations (name, ein, city, state).
    Responses are cached by CMS provider number.
    """
    cache = _search_cache_path(cms_num)
    if cache.exists():
        with open(cache) as f:
            return json.load(f)

    # Use facility name only — adding city to query causes 404s on ProPublica's API.
    # State filter still applied to narrow results.
    query = facility_name
    _rate_limit()
    try:
        resp = requests.get(
            PROPUBLICA_SEARCH,
            params={"q": query, "state[id]": state},
            timeout=15,
        )
        if resp.status_code == 404:
            orgs = []
        else:
            resp.raise_for_status()
            orgs = resp.json().get("organizations", [])
    except requests.RequestException as e:
        log.warning(f"ProPublica search failed for {facility_name}: {e}")
        orgs = []

    with open(cache, "w") as f:
        json.dump(orgs, f, indent=2)
    return orgs


def match_via_propublica(facility_name: str, city: str, state: str, cms_num: str) -> dict | None:
    """
    Search ProPublica and pick the best match using fuzzy name comparison.
    Returns match dict or None if no match above threshold.
    """
    candidates = propublica_search(facility_name, city, state, cms_num)
    if not candidates:
        return None

    fac_norm = normalize(facility_name)

    best_score = 0
    best = None
    for org in candidates[:5]:  # only check top 5 results
        org_norm = normalize(org.get("name", ""))
        score = fuzz.token_sort_ratio(fac_norm, org_norm)
        if score > best_score:
            best_score = score
            best = org

    if best and best_score >= FUZZY_ACCEPT:
        return {
            "matched_ein": best["ein"],
            "match_score": best_score,
            "match_name": best.get("name"),
            "match_confidence": "high" if best_score >= 90 else "medium",
            "match_method": "propublica_search",
        }
    return None


# ── BMF fallback ──────────────────────────────────────────────────────────────

def download_bmf() -> pd.DataFrame:
    frames = []
    for name, url in IRS_BMF_FILES.items():
        cache_path = RAW_DIR / f"{name}.csv"
        if cache_path.exists():
            log.info(f"  {name}: loading from cache")
        else:
            log.info(f"  {name}: downloading from IRS...")
            resp = requests.get(url, timeout=120, stream=True)
            resp.raise_for_status()
            with open(cache_path, "wb") as f:
                for chunk in resp.iter_content(65536):
                    f.write(chunk)
        try:
            df = pd.read_csv(
                cache_path, dtype=str,
                usecols=["EIN", "NAME", "CITY", "STATE", "NTEE_CD"],
                encoding="latin-1",
            )
            frames.append(df)
            log.info(f"  {name}: {len(df):,} records")
        except Exception as e:
            log.warning(f"  {name}: {e}")

    if not frames:
        log.error("No BMF files loaded.")
        sys.exit(1)

    bmf = pd.concat(frames, ignore_index=True)
    ntee = bmf["NTEE_CD"].fillna("")
    bmf = bmf[ntee.str.startswith(("E", "F", "P")) | (ntee == "")].copy()
    log.info(f"BMF loaded: {len(bmf):,} healthcare/human-services records")
    return bmf


def match_via_bmf(facility_name: str, city: str, state: str, bmf: pd.DataFrame) -> dict | None:
    """BMF fuzzy fallback for facilities not found via ProPublica search."""
    state_bmf = bmf[bmf["STATE"].str.lower().str.strip() == state.lower().strip()]
    if state_bmf.empty:
        return None

    fac_key = f"{normalize(facility_name)} {normalize(city)}"
    state_keys = (state_bmf["NAME"].apply(normalize) + " " + state_bmf["CITY"].apply(normalize)).tolist()

    match = process.extractOne(fac_key, state_keys, scorer=fuzz.token_sort_ratio, score_cutoff=0)
    if not match:
        return None
    _, score, idx = match

    if score >= BMF_ACCEPT:
        return {
            "matched_ein": state_bmf.iloc[idx]["EIN"],
            "match_score": score,
            "match_name": state_bmf.iloc[idx]["NAME"],
            "match_confidence": "medium",
            "match_method": "bmf_fuzzy",
        }
    return None


# ── Main matching loop ────────────────────────────────────────────────────────

def match_facilities(facilities: pd.DataFrame, bmf: pd.DataFrame) -> pd.DataFrame:
    results = []
    n = len(facilities)

    for i, row in facilities.iterrows():
        name = row["facility_name"]
        city = row["city"]
        state = row["state"]
        cms_num = row["cms_provider_num"]

        # Stage 1: ProPublica search
        result = match_via_propublica(name, city, state, cms_num)

        # Stage 2: BMF fuzzy fallback
        if result is None:
            result = match_via_bmf(name, city, state, bmf)

        if result is None:
            result = {
                "matched_ein": None,
                "match_score": 0,
                "match_name": None,
                "match_confidence": "unmatched",
                "match_method": "none",
            }

        result["cms_provider_num"] = cms_num
        results.append(result)

        if (len(results) % 50) == 0:
            log.info(f"  {len(results)}/{n} facilities processed...")

    return pd.DataFrame(results)


def write_unmatched_report(crosswalk: pd.DataFrame) -> None:
    low = crosswalk[crosswalk["match_confidence"].isin(["unmatched", "low"])]
    lines = [
        "# EIN Crosswalk — Unmatched Facilities",
        "",
        f"{len(low):,} facilities could not be matched to an IRS EIN.",
        "These will be classified as 'uncertain' in the VMS model.",
        "",
        "| CMS # | Facility | City | State | Best Candidate | Score |",
        "|-------|----------|------|-------|----------------|-------|",
    ]
    for _, r in low.iterrows():
        lines.append(
            f"| {r['cms_provider_num']} | {r['facility_name']} | {r['city']} | {r['state']} "
            f"| {r.get('match_name') or 'n/a'} | {r['match_score']} |"
        )
    (DOCS_DIR / "ein_crosswalk_unmatched.md").write_text("\n".join(lines))
    log.info(f"Unmatched report written to {DOCS_DIR / 'ein_crosswalk_unmatched.md'}")


def main():
    log.info("Loading Stage 2 candidates...")
    facilities = pd.read_parquet(PROCESSED_DIR / "stage2_candidates.parquet")
    log.info(f"  {len(facilities):,} facilities")

    log.info("Loading IRS BMF (fallback)...")
    bmf = download_bmf()

    log.info("Matching facilities (ProPublica search → BMF fallback)...")
    match_df = match_facilities(facilities, bmf)

    crosswalk = facilities.merge(match_df, on="cms_provider_num", how="left")

    high = crosswalk["match_confidence"].isin(["high", "medium"]).sum()
    unmatched = crosswalk["matched_ein"].isna().sum()
    log.info(f"\n--- EIN Match Summary ---")
    log.info(f"Matched (high/medium confidence): {high:,} ({high/len(crosswalk)*100:.1f}%)")
    log.info(f"Unmatched:                        {unmatched:,} ({unmatched/len(crosswalk)*100:.1f}%)")
    log.info(f"\nBy method:")
    log.info(crosswalk["match_method"].value_counts().to_string())

    # matched_ein contains EIN strings and None — use pandas StringDtype to avoid
    # pyarrow inferring int64 from numeric-looking EIN strings like "951914489"
    crosswalk["matched_ein"] = crosswalk["matched_ein"].astype(pd.StringDtype())

    out = PROCESSED_DIR / "facility_ein_crosswalk.parquet"
    crosswalk.to_parquet(out, index=False)
    log.info(f"\nSaved crosswalk to {out}")

    write_unmatched_report(crosswalk)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    main()
