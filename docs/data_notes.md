# Data Notes for Non-Technical Readers

This document explains important facts about the data sources used in Saile Radar —
including known gaps, limitations, and what they mean for how the results should be interpreted.

---

## BLS Healthcare Employment Data (Step 1.3)

**What this data is:**
We pulled employment counts for healthcare workers (doctors, nurses, and related practitioners)
from the Bureau of Labor Statistics (BLS) Occupational Employment and Wage Statistics (OES) survey.
This tells us how many healthcare workers are employed in each metro area across the country.

**The gap: 739 out of 935 metro areas have no data.**

The BLS intentionally withholds employment numbers for small geographic areas.
This is a federal privacy policy — if an area has too few employers reporting data,
publishing a number could reveal confidential information about individual businesses.

What this means in practice:
- The **196 metro areas with data** cover all major cities and most mid-sized markets —
  these are the areas where the vast majority of hospitals are located.
- The **739 areas without data** are predominantly small rural communities and
  micropolitan areas (think: Hinesville, GA or Gettysburg, PA) where BLS suppressed
  the numbers.
- For our scoring model, facilities in suppressed areas will simply not receive a
  BLS density score. This is noted as a limitation and does not disqualify those
  facilities from appearing in the final output — it just means one scoring component
  will be missing for them.

**Bottom line:** The missing data is not a bug or error in our process.
It is a deliberate government policy, and it primarily affects small rural areas
that are unlikely to be top targets anyway. The data we do have is complete and reliable
for the markets Saile cares most about.

---

## HRSA Shortage Designation Data (Step 1.1)

**What this data is:**
The Health Resources & Services Administration (HRSA) officially designates geographic
areas, population groups, and specific facilities as "Health Professional Shortage Areas"
(HPSAs). These designations are the federal government's own assessment of where
healthcare access is lacking.

**Key facts:**
- We pulled 45,393 active HPSA designations covering primary care, dental, and mental health.
- Only **active** designations are included — areas that were once designated but have since
  improved are excluded.
- HPSA scores range from 0 to 25 (primary care/mental health) or 0 to 26 (dental).
  Higher scores indicate more severe shortages.

---

## CMS Hospital Directory (Step 1.2)

**What this data is:**
The Centers for Medicare & Medicaid Services (CMS) maintains a master list of every
Medicare-certified healthcare facility in the United States — the Provider of Services (POS) file.

**Key facts:**
- We pulled 27,244 active hospital and hospital-type facilities.
- Each facility is classified by ownership type: nonprofit, for-profit, or government.
- **For-profit facilities (1,938) are flagged** so they can be deprioritized in outreach.
  Saile's model works best with nonprofit and government hospitals that are more likely
  to hire locum tenens staff directly rather than through a VMS.
- The dataset covers all 50 states plus U.S. territories (58 jurisdictions total).

---

## General Limitation: Data Currency

All datasets used in this project are the most recent publicly available versions
as of April 2026. Government datasets are typically updated annually or quarterly.
Scores and rankings should be refreshed when new data becomes available.
