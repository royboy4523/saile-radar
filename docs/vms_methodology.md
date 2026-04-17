# VMS Classification Methodology

This document explains how Saile Radar classifies Stage 2 facilities as
likely VMS users vs. direct-hire candidates.

**Read this alongside `docs/scoring_methodology.md`.**

---

## What is a VMS?

A Vendor Management System (VMS) is a software platform that some hospitals use to
manage temporary physician staffing. When a hospital routes locum tenens hiring
through a VMS, staffing companies like Saile must work through the VMS intermediary
rather than directly with the hospital — increasing friction and reducing margin.

Saile's highest-value targets are hospitals that hire locum tenens physicians directly,
without a VMS in the middle.

---

## Data Source: IRS Form 990

Nonprofit hospitals are required to file IRS Form 990 annually.
Part IX of the 990 (Statement of Functional Expenses) includes:

- **Line 11g**: Fees for services — outside contractors
- **Total functional expenses**: All operating costs

We use the ratio of contractor fees to total expenses as a proxy for VMS usage.

**Key limitation:** Part IX contractor fees include ALL outside contractors,
not just physician staffing. A hospital with high IT contractor spend or
large construction projects will show a high ratio even if it has no VMS.
This is the primary source of uncertainty in the model.

---

## Classification Thresholds

```
contractor_ratio = contractor_fees / total_functional_expenses

direct_hire  : ratio < 5%   (minimal contractor spend)
uncertain    : 5% ≤ ratio < 15%  (ambiguous)
likely_vms   : ratio ≥ 15%  (heavy contractor spend)
```

---

## Coverage and Results

| Category | Count |
|----------|-------|
| Stage 2 facilities | 566 |
| EIN matched | 208 (36.7%) |
| 990 data retrieved | 170 (30.0%) |
| direct_hire | 138 (24.4%) |
| likely_vms | 12 (2.1%) |
| uncertain | 416 (73.5%) |

---

## Why 63% of Facilities Are 'Uncertain'

Three structural reasons limit EIN matching coverage:

1. **Parent system EINs**: Many hospitals file 990s under a parent health system,
   not the individual facility name. The EIN for 'Copper Queen Community Hospital'
   may be registered as 'Copper Queen Community Health Foundation'.

2. **Government-operated facilities**: Hospitals operated by county or state
   governments do not file 990s — they are not nonprofit organizations.
   These are still scored by the model but cannot be classified via 990 data.

3. **Name format divergence**: CMS registers facilities under operational names;
   the IRS BMF uses legal entity names. 'St. Joseph's Medical Center' and
   'St Joseph Health System' may be the same organization.

**Bottom line:** 'Uncertain' does not mean 'skip this facility.'
It means 990 data was not available. A business development rep should
approach uncertain facilities with a direct conversation rather than
assuming VMS usage.

---

## Recommended Outreach Priority

1. **direct_hire + high shortage score** → Highest priority. Most likely to
   accept direct locum tenens engagement.

2. **uncertain + high shortage score** → High priority. Shortage is real;
   VMS status unknown. Worth a discovery call.

3. **likely_vms + high shortage score** → Lower priority, but not excluded.
   Some VMS relationships can be worked around; shortage signal is still real.

---

## Output File

`data/processed/facilities_final.parquet` — All Stage 2 facilities with
shortage score, EIN match, 990 expense data, and VMS classification.