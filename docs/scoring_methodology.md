# Saile Radar — Shortage Scoring Methodology

This document defines the composite shortage score used to rank every facility
in the unified dataset. The score is implemented in `src/scoring/model.py`.

**Read this before touching any scoring code.**

---

## Purpose

The composite score answers one question:
*Which nonprofit facilities are most likely to have an urgent, unmet need for
locum tenens physicians that Saile could fill directly (not through a VMS)?*

A higher score = more severe, more persistent, more structurally underserved.

---

## Composite Score Formula

```
composite_score = (0.40 × hpsa_component)
               + (0.30 × density_component)
               + (0.20 × aamc_component)
               + (0.10 × rural_component)
```

**Weights sum to 1.0.**

Each component is normalized to a 0–1 scale before weighting.
A score of 1.0 means maximum shortage. A score of 0.0 means no shortage signal.

---

## Components

### Component 1: HPSA Score (weight: 0.40)

**What it measures:** How severely underserved the facility's county is,
according to the federal government's official shortage designation.

**Data source:** HRSA HPSA designations (county level).
**Field used:** `hpsa_score_max` — the highest HPSA score across primary care,
dental, and mental health for the facility's county.

**Normalization:** Min-max scaling.
```
hpsa_component = hpsa_score_max / 26
```
HPSA scores range from 0 to 26. Dividing by 26 maps them to 0–1.
Facilities in counties with no HPSA designation receive a score of 0.

**Why 40%:** HPSA designation is the most direct, authoritative, and
facility-specific signal available. It is the federal government's own
verdict on where care is lacking. It receives the highest weight.

---

### Component 2: Provider Density — Inverted (weight: 0.30)

**What it measures:** How few healthcare workers are employed in the
facility's metro area relative to the population. Fewer workers per capita
= higher shortage signal.

**Data source:** BLS OES employment (metro level) + Census population.
**Field used:** `provider_density_per_100k`

**Normalization:** Percentile rank, then inverted.
```
rank = percentile_rank(provider_density_per_100k)   # 0 = lowest density, 1 = highest
density_component = 1 - rank                         # invert: low density → high score
```
Facilities where BLS suppressed the data (22.9% of dataset) are imputed
with a score of 0.5 — the median — so they are neither rewarded nor
penalized for missing data.

**Why 30%:** Provider density is a strong market-level signal of structural
shortage. A county can have an HPSA designation AND a low provider density,
making it doubly underserved. Weighted second because 77% of facilities
lack this data due to BLS suppression — full weight would over-index on
the large urban hospitals that do have data.

---

### Component 3: AAMC National Shortage Weight (weight: 0.20)

**What it measures:** How severe the national projected physician shortage
is for the type of facility. Facilities serving specialties with larger
projected national shortfalls receive a higher score.

**Data source:** AAMC Workforce Projections (national level).
**Field used:** `aamc_category_approx` (mapped from CMS provider category)

**Mapping — AAMC category midpoint shortfall by 2036:**

| AAMC Category | Midpoint Shortfall | Normalized |
|---|---|---|
| Primary Care | 30,300 | 1.00 |
| Surgical Specialties | 15,000 | 0.50 |
| Other Specialties (psych, EM, radiology) | 7,600 | 0.25 |
| Medical Specialties | 900 | 0.03 |
| Hospitalist | 0 | 0.00 |

```
aamc_component = aamc_midpoint_shortfall / 30300
```

**Why 20%:** AAMC data is national and category-level — it cannot distinguish
between two hospitals in the same metro area. It adds national context about
specialty demand trends but is not precise enough to carry more weight.

---

### Component 4: Rural Indicator (weight: 0.10)

**What it measures:** Whether the facility is in a rural area.
Rural facilities face structural recruitment disadvantages that compound
the shortage signals above.

**Data source:** CMS POS file.
**Field used:** `urban_rural`

**Normalization:** Binary.
```
rural_component = 1.0 if urban_rural == 'R' else 0.0
```
Facilities with a null urban/rural flag are treated as urban (0.0).

**Why 10%:** Rural status is a meaningful tiebreaker but is already partially
captured by HPSA score (rural counties are more likely to have high HPSA scores).
Keeping it at 10% adds signal without double-counting.

---

## Normalization Levels

| Component | Geographic Level | Coverage |
|-----------|-----------------|----------|
| HPSA Score | County | 95.7% |
| Provider Density | Metro (CBSA) | 22.9% — nulls imputed at 0.5 |
| AAMC Weight | National | 100% (approximated from facility type) |
| Rural Indicator | Facility | ~97% |

---

## What the Score Does NOT Include (and Why)

**Bed count:** Larger hospitals have more resources and are less likely to be
critically underserved. Excluded to avoid penalizing small community hospitals.

**Ownership type:** For-profit facilities are not scored out — they are filtered
out entirely before Stage 2 selection. Scoring them would waste computation.

**Wage data:** BLS OES wage data was not collected (employment only). Wages
would add signal but require a separate data pull; left for a future iteration.

---

## Stage 2 Threshold

After scoring, facilities are ranked by composite score descending.
Only **nonprofit** facilities advance to Stage 2 (for-profit and government
are excluded — Saile's model targets nonprofits that hire locums directly).

**Threshold set:** `composite_score >= 0.8346`
**Stage 2 candidates:** 548 nonprofit facilities
**Score range within Stage 2:** 0.8346 – 0.8884

### How the threshold was chosen

The `set_stage2_threshold()` function in `src/scoring/model.py` selects the
cutoff that places the target number of nonprofits in the Stage 2 list.
Target was the midpoint of the planner range (500 facilities); the function
found that a score of 0.8346 produces 548 facilities — within the 200–800 target.

### Stage 2 geographic distribution (top 10 states)

| State | Facilities |
|-------|-----------|
| CA | 241 |
| TX | 62 |
| OH | 44 |
| NC | 39 |
| MO | 17 |
| NM | 16 |
| IL | 15 |
| MS | 13 |
| WV | 11 |
| IN | 11 |

28 states represented. California's large count reflects the high density of
nonprofit facilities in counties with HPSA designations (Central Valley in
particular has HPSA scores of 24–26).

**Output file:** `data/processed/stage2_candidates.parquet`

Target size: 200–800 facilities (per planner guidance).

---

## Limitations

1. AAMC weights are category-level, not specialty-level. Two hospitals in the
   same category (e.g., a psychiatric hospital and an ER-heavy acute care
   hospital both mapped to "Other Specialties") receive the same AAMC score.

2. BLS density is null for 77% of facilities. Imputing at 0.5 is conservative
   — these facilities are not penalized but also not rewarded for being in
   potentially underserved small markets.

3. The scoring model reflects current and near-term shortage conditions.
   It does not account for facilities that may have recently recruited
   physicians or resolved their shortage since the data was collected.
