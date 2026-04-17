# Phase 3 Results — VMS Filter and Final Outreach Tiers

**If you are a business stakeholder, manager, or anyone without a data background, this is your summary of what Phase 3 produced and what it means for outreach.**

---

## What Phase 3 Did

Phase 3 took the 566 hospitals from Phase 2 and tried to answer one more question:

> *Which of these hospitals hire locum tenens physicians directly — and which route their hiring through a Vendor Management System (VMS) that Saile would have to work around?*

A **VMS (Vendor Management System)** is a software platform some hospitals use to manage temporary physician staffing. When a hospital uses a VMS, staffing companies like Saile must submit candidates through the VMS intermediary, increasing friction and reducing Saile's ability to build a direct relationship. Saile's highest-value targets are hospitals that hire physicians directly.

---

## How We Identified VMS Usage

Nonprofit hospitals are required to file annual financial reports with the IRS (called Form 990). Part IX of the 990 reports how much money the hospital spent on **outside contractors** — which includes physician staffing agencies and VMS-routed placements.

We calculated a simple ratio:

> **Contractor spending ÷ Total operating expenses**

- A hospital spending very little on outside contractors (under 5%) likely hires most staff directly.
- A hospital spending a lot on outside contractors (over 15%) may be routing physician hiring through a VMS or heavy third-party staffing.

---

## Phase 3 Results

Of the 566 hospitals:

| Classification | Count | What it means |
|----------------|-------|---------------|
| **Direct hire** | 138 (24%) | Low contractor spend — likely hiring physicians directly |
| **Likely VMS** | 12 (2%) | High contractor spend — may use a VMS or heavy third-party staffing |
| **Uncertain** | 416 (74%) | Could not determine — IRS data not available or not matched |

---

## Why 74% Are "Uncertain" — and Why That's OK

Three structural reasons limit how many hospitals we can classify:

**1. Government-operated hospitals don't file 990s.**
Hospitals run by county or state governments are not nonprofit organizations, so they don't file IRS 990 forms. About a third of our 566 hospitals fall into this category and simply cannot be evaluated this way — even though many are genuine shortage facilities.

**2. Many hospitals file under a parent health system.**
A hospital called "Mercy Hospital Paris" might file its 990 under "Mercy Health System" — a different name entirely. Our matching system found the right organization in about a third of cases (36.7%), but name divergence means many were unmatched.

**3. The IRS database has gaps.**
Some small rural hospitals are not well-indexed in the ProPublica nonprofit database we used, particularly very small critical access hospitals.

**Important:** "Uncertain" does not mean "skip this facility." It means we could not confirm the hiring method from public data. A business development call to an uncertain facility is still warranted — the shortage signal from Phase 2 is real.

---

## The Recommended Outreach Priority Order

**Tier 1 — Direct Hire + High Shortage Score**
138 hospitals. Confirmed low contractor spend and high shortage need. Best candidates for immediate Saile outreach. Most likely to welcome a direct locum tenens engagement.

**Tier 2 — Uncertain + High Shortage Score**
Most of the 416 uncertain hospitals. Shortage is confirmed, VMS status is unknown. A discovery call or direct conversation is the right approach — don't assume VMS usage just because 990 data wasn't available.

**Tier 3 — Likely VMS**
12 hospitals. Shortage is real, but contractor data suggests staffing may be routed through a VMS. Lower priority but not disqualified — some VMS relationships can be navigated, and situations change.

---

## Sample Top Direct-Hire Targets

These hospitals had both high shortage scores and confirmed low contractor spending:

| Hospital | City | State | Shortage Score |
|----------|------|-------|---------------|
| Hospital Menonita Guayama | Guayama | PR | 0.81 |
| Molokai General Hospital | Kaunakakai | HI | 0.80 |
| UCHealth Greeley Hospital | Greeley | CO | 0.79 |
| Loma Linda University Medical Center | Loma Linda | CA | 0.78 |
| Community Hospital of San Bernardino | San Bernardino | CA | 0.78 |
| Mercy Hospital Paris | Paris | AR | 0.77 |
| Mercy Hospital Booneville | Booneville | AR | 0.77 |
| Sky Lakes Medical Center | Klamath Falls | OR | 0.77 |
| Calais Community Hospital | Calais | ME | 0.77 |
| Mount Desert Island Hospital | Bar Harbor | ME | 0.77 |

---

## A Note on the Contractor Ratio Limitation

The IRS 990 contractor expense line covers **all** outside contractors, not just physician staffing. A hospital with a large IT outsourcing contract, a recent construction project, or heavy administrative consulting would show a high contractor ratio even if it has no VMS for physicians.

This means "likely_vms" is a flag for investigation, not a definitive finding. A BD conversation remains the only way to confirm how a specific hospital manages physician staffing.

---

## Files Produced by Phase 3

| File | What it is |
|------|-----------|
| `data/processed/facility_ein_crosswalk.parquet` | All 566 Stage 2 hospitals with their IRS EIN match results |
| `data/processed/facilities_final.parquet` | All 566 hospitals with shortage score + VMS classification — the main output file going into Phase 4 |
| `docs/data_notes/ein_crosswalk_unmatched.md` | List of hospitals that could not be matched to an IRS EIN, for manual review if needed |
| `docs/vms_methodology.md` | Full technical explanation of how VMS classification works |
