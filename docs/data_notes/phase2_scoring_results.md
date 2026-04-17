# Phase 2 Results — What the Shortage Scores Tell Us

**If you are a business stakeholder, manager, or anyone without a data background, this is your summary of what Phase 2 produced and what it means.**

---

## What Phase 2 Did

Phase 2 took the 27,244 healthcare facilities from Phase 1 and gave each one a **shortage score** — a single number between 0 and 1 that answers the question:

> *How urgently does this facility need locum tenens physicians that Saile could fill directly?*

A score of **1.0** = maximum shortage signal. A score of **0.0** = no shortage signal.

The score is calculated from four pieces of evidence, weighted by how reliable and relevant each one is:

| Evidence | Weight | What it measures |
|----------|--------|-----------------|
| Federal shortage designation (HPSA) | 40% | Is this county officially designated as underserved by the federal government? |
| Local provider density | 30% | Are there fewer healthcare workers per person in this area than typical? |
| National specialty shortage trend | 20% | Is the type of facility this is (primary care, surgical, etc.) facing a national shortage? |
| Rural location | 10% | Is the facility in a rural area where recruiting is structurally harder? |

See `docs/scoring_methodology.md` for the full technical formula if needed.

---

## What the Scores Look Like

- **Score range across all facilities:** 0.09 to 0.89
- **Average score:** 0.65
- No facility scored above 0.89 — this is healthy. It means the model is not over-rewarding any single factor.

### What a high score looks like

The top-scoring facilities are in **Maui County, Hawaii** — which carries a federal HPSA designation score of 26 (the maximum possible), meaning the federal government has flagged it as one of the most severely underserved areas in the country. These facilities are also nonprofit and serve a geographically isolated community with no alternative care options nearby.

### What a low score looks like

The lowest-scoring facilities are in suburban areas outside **Covington, Louisiana** and **Mequon, Wisconsin** — affluent suburbs of major metro areas, no federal shortage designation, dense provider markets. The model correctly identifies these as low-priority.

---

## The Stage 2 List — 548 Facilities

After scoring, we applied two filters to identify the top candidates for Saile's outreach:

1. **Nonprofit only** — For-profit hospitals are excluded. Saile's locum tenens model works best with nonprofit and government-funded hospitals that hire physicians directly, rather than through a staffing intermediary.
2. **Score threshold of 0.8346 or higher** — This cutoff was chosen to produce a manageable list (200–800 facilities) that a business development team can realistically work through.

**Result: 548 facilities across 28 states advance to Phase 3.**

### Where are the 548 facilities?

The top states by facility count:

| State | Facilities | Why |
|-------|-----------|-----|
| California | 241 | Large state with many nonprofit facilities in high-shortage counties (Central Valley) |
| Texas | 62 | Large rural population, many counties with federal shortage designations |
| Ohio | 44 | Mix of rural and urban underserved nonprofit hospitals |
| North Carolina | 39 | Rural communities and historically underserved counties |
| New Mexico | 16 | Heavily rural, high proportion of federally-designated shortage areas |

---

## What This Does NOT Mean Yet

The 548 facilities on the Stage 2 list are the **most likely to have a genuine physician shortage**. That is not the same as being the most likely Saile target.

Phase 3 will add one more filter: does the facility use a **Vendor Management System (VMS)** for staffing? Facilities that route hiring through a VMS are harder for Saile to reach directly. Phase 3 will use IRS tax filing data (990 forms) to estimate this, so the final recommended list will be shorter.

---

## Files Produced by Phase 2

| File | What it is |
|------|-----------|
| `data/processed/scored_facilities.parquet` | All 27,244 facilities with their shortage scores |
| `data/processed/stage2_candidates.parquet` | The 548 nonprofit facilities advancing to Phase 3 |

---

## How Reliable Are These Scores?

**High confidence:** The federal HPSA designation (40% of the score) is the most authoritative shortage signal available — it is the federal government's own assessment. Facilities with high HPSA scores are genuinely in shortage areas.

**Moderate confidence:** The provider density component (30%) is reliable where BLS data exists, but 77% of facilities had no BLS data available due to federal privacy rules for small areas. Those facilities are scored neutrally on this component — neither penalized nor rewarded.

**Lower confidence:** The AAMC specialty weight (20%) is a national average, not a local measurement. Two hospitals in the same category (e.g., a psychiatric hospital and a rural emergency department) receive the same AAMC score even if their local supply-demand dynamics differ.

**Bottom line:** The model is strongest at the extremes — high scorers are very likely in genuine shortage areas, low scorers are very likely not priority targets. The middle range (0.60–0.80) requires more judgment.
