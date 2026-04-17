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

- **Score range across all facilities:** 0.09 to 0.85
- **Average score:** 0.65
- No facility scored above 0.85 — this is healthy. It means the model is not over-rewarding any single factor.

### What a high score looks like

The top-scoring facilities are hospitals in **Monticello, Arkansas** and **Meridian, Mississippi** — counties with federal HPSA scores of 25–26 (the highest possible), meaning the federal government has flagged them as among the most severely underserved areas in the country.

### What a low score looks like

The lowest-scoring facilities are in affluent suburban areas outside major cities — no federal shortage designation, dense provider markets. The model correctly identifies these as low-priority.

---

## Important Correction Made During Phase 3

When we first generated the Stage 2 list, it was dominated by **ICF-IID facilities** — Intermediate Care Facilities for people with Intellectual and Developmental Disabilities. These are small residential group homes that employ direct-care workers, not physicians. They are not locum tenens targets for Saile.

This was caught during Phase 3 work and corrected. Stage 2 was re-filtered to include only **actual hospitals** (acute care, psychiatric, rehabilitation, and chronic disease). The ICF-IID homes and skilled nursing facilities were removed from consideration.

This was the right correction — it made the list more targeted and more actionable for Saile's business development team.

---

## The Stage 2 List — 566 Hospitals

After scoring, we applied two filters to identify the top candidates for Saile's outreach:

1. **Nonprofit hospitals only** — For-profit hospitals and government-run hospitals are excluded. Saile's locum tenens model works best with nonprofit hospitals that hire physicians directly, rather than through a staffing intermediary.
2. **Hospital types only** — The 566 facilities are all actual hospitals (acute care, psychiatric, rehabilitation, or chronic disease). Nursing homes and residential care facilities are excluded.
3. **Score threshold of 0.6895 or higher** — This cutoff was chosen to produce a manageable list within the 200–800 facility target.

**Result: 566 nonprofit hospitals across 44 states advance to Phase 3.**

### What types of hospitals are on the list?

| Hospital Type | Count |
|---|---|
| Acute care hospitals | 468 |
| Chronic disease hospitals | 79 |
| Psychiatric hospitals | 13 |
| Rehabilitation hospitals | 6 |

### Where are the 566 hospitals?

The top states by facility count:

| State | Facilities | Why |
|-------|-----------|-----|
| California | 72 | Large state, many nonprofit hospitals in high-shortage counties |
| Texas | 48 | Large rural population, many counties with federal shortage designations |
| Pennsylvania | 34 | Mix of rural and urban underserved nonprofit hospitals |
| Wisconsin | 24 | Rural communities and shortage areas in the northern part of the state |
| Iowa | 22 | Heavily rural, many small community hospitals in shortage counties |
| Puerto Rico | 19 | Several counties with maximum federal shortage scores (26/26) |

---

## What This Does NOT Mean Yet

The 566 facilities on the Stage 2 list are the **most likely to have a genuine physician shortage**. That is not the same as being the most likely Saile target.

Phase 3 added one more filter: does the facility use a **Vendor Management System (VMS)** for staffing? See `docs/data_notes/phase3_vms_results.md` for those findings.

---

## Files Produced by Phase 2

| File | What it is |
|------|-----------|
| `data/processed/scored_facilities.parquet` | All 27,244 facilities with their shortage scores |
| `data/processed/stage2_candidates.parquet` | The 566 nonprofit hospitals advancing to Phase 3 |

---

## How Reliable Are These Scores?

**High confidence:** The federal HPSA designation (40% of the score) is the most authoritative shortage signal available. Facilities with high HPSA scores are genuinely in shortage areas.

**Moderate confidence:** The provider density component (30%) is reliable where BLS data exists, but 77% of facilities had no BLS data available due to federal privacy rules for small areas. Those facilities are scored neutrally on this component.

**Lower confidence:** The AAMC specialty weight (20%) is a national average, not a local measurement. Two hospitals in the same category receive the same AAMC score even if their local dynamics differ.

**Bottom line:** The model is strongest at the extremes — high scorers are very likely in genuine shortage areas, low scorers are very likely not priority targets.
