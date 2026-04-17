# Data Notes for Non-Technical Readers

This document explains every data source used in Saile Radar — what it is, where it came from,
known gaps, and what those gaps mean for interpreting results.

**If you are not a technical reader, start here.**

---

## Step 1.1 — HRSA Shortage Designation Data

**What this data is:**
The Health Resources & Services Administration (HRSA) officially designates geographic areas,
population groups, and specific facilities as "Health Professional Shortage Areas" (HPSAs).
These designations are the federal government's own assessment of where healthcare access is lacking.

**Where it comes from:** Downloaded directly from data.hrsa.gov (April 2026).

**Key facts:**
- 45,393 active HPSA designations covering primary care, dental, and mental health.
- Only **active** designations are included — areas that were once designated but have since
  improved are excluded.
- HPSA scores range from 0 to 25 (primary care/mental health) or 0 to 26 (dental).
  Higher scores indicate more severe shortages.

**Known limitations:** None significant. This is the most authoritative federal shortage dataset available.

---

## Step 1.2 — CMS Hospital Directory

**What this data is:**
The Centers for Medicare & Medicaid Services (CMS) maintains a master list of every
Medicare-certified healthcare facility in the United States, called the Provider of Services (POS) file.

**Where it comes from:** December 2024 snapshot downloaded from NBER's public CMS data mirror.

**Key facts:**
- 27,244 active hospital and hospital-type facilities across all 50 states and U.S. territories.
- Each facility is classified by ownership type: nonprofit, for-profit, or government.
- **For-profit facilities (1,938) are flagged** so they can be deprioritized in outreach.
  Saile's model works best with nonprofit and government hospitals that are more likely
  to hire locum tenens staff directly rather than through a Vendor Management System (VMS).
- This file is used as the master list of facilities — every other data source is joined to it.

**Known limitations:** None significant. The file is updated quarterly by CMS.

---

## Step 1.3 — BLS Healthcare Employment Data

**What this data is:**
Employment counts for healthcare workers (doctors, nurses, and related practitioners)
from the Bureau of Labor Statistics (BLS) Occupational Employment and Wage Statistics (OES) survey.
This tells us how many healthcare workers are employed in each metro area across the country,
which we use to calculate provider density (workers per 100,000 residents).

**Where it comes from:** BLS public API, May 2024 survey data. Population estimates from U.S. Census Bureau, 2023.

**Key facts:**
- Coverage: 196 of 935 metro areas have employment data.
- Density range: 1,118 to 5,774 healthcare practitioners per 100,000 residents.
- High-density areas (e.g., Durham, NC at 5,774) are anchored by major academic medical centers like Duke.
- Low-density areas (e.g., military towns like Hinesville, GA at 1,205) confirm the model is working correctly.

**Known limitation — 739 of 935 metro areas have no data:**
The BLS intentionally withholds employment numbers for small geographic areas.
This is a federal privacy policy — if an area has too few employers reporting,
publishing a number could reveal confidential information about individual businesses.

What this means in practice:
- The 196 metro areas **with** data cover all major cities and most mid-sized markets —
  where the vast majority of hospitals are located.
- The 739 areas **without** data are predominantly small rural communities where BLS suppressed the numbers.
- Facilities in suppressed areas will not receive a BLS density score in the model.
  This does not disqualify them — it means one scoring component will be missing for them.

**Bottom line:** This is a deliberate government policy, not a bug in our process.
It primarily affects small rural areas that are unlikely to be top Saile targets anyway.

---

## Step 1.4 — AAMC Physician Workforce Shortage Projections

**What this data is:**
National projections of physician supply vs. demand by specialty through 2036,
published by the Association of American Medical Colleges (AAMC). This tells us
which specialties are projected to face the largest national shortfalls — used as a
weight in the scoring model to prioritize facilities serving high-shortage specialties.

**Where it comes from:**
*The Complexities of Physician Supply and Demand: Projections From 2021 to 2036*
Published by AAMC, 2023. Available at: https://www.aamc.org/media/75236/download

**Key facts:**
- 31 specialties included, covering all major locum tenens placement areas.
- Projections run to 2036 and are expressed as a range (low estimate to high estimate).
- Positive shortfall = projected shortage (demand exceeds supply). Negative = projected surplus.
- Largest projected shortfalls by 2036: Primary Care (20,200–40,400), Surgical Specialties (10,100–19,900).
- Hospitalists are projected to move toward surplus under optimistic scenarios.

**Known limitation — category-level data only:**
The AAMC report publishes shortfall projections at five broad specialty group levels only
(Primary Care, Medical Specialties, Surgical Specialties, Other Specialties, Hospitalists).
Individual specialty breakdowns (e.g., cardiology vs. gastroenterology as separate numbers)
are presented only as charts in the PDF — not as extractable tables.

As a result, all specialties within the same AAMC category share the same shortfall range.
For example, Cardiology and Gastroenterology are both assigned the Medical Specialties range
(-3,700 to 5,500 by 2036), even though their individual trajectories differ.

**Bottom line:** The category-level shortfall figures are real numbers directly from the AAMC report.
The individual specialty assignments are our best approximation given what AAMC publishes.
The HRSA HPSA data (Step 1.1) provides the facility-level detail that compensates for this limitation.

See also: [docs/aamc_data_source.md](aamc_data_source.md) for full technical source notes.

---

## General Limitation: Data Currency

All datasets are the most recent publicly available versions as of April 2026.
Government datasets are typically updated annually or quarterly.
Scores and rankings should be refreshed when new data becomes available.

| Dataset | Source | Version Used |
|---------|--------|-------------|
| HRSA HPSA | data.hrsa.gov | April 2026 |
| CMS POS | CMS via NBER | December 2024 |
| BLS OES | BLS public API | May 2024 |
| AAMC Workforce | aamc.org | 2023 report (2021–2036 projections) |
