# AAMC Specialty Shortage Data — Source Notes

## Source Document

**Title:** The Complexities of Physician Supply and Demand: Projections From 2021 to 2036
**Publisher:** Association of American Medical Colleges (AAMC)
**Published:** 2023
**URL:** https://www.aamc.org/media/75236/download

## What the Numbers Mean

The shortfall figures represent the projected gap between physician supply and demand by 2036.
- **Positive numbers** = projected shortage (demand exceeds supply)
- **Negative numbers** = projected surplus (supply exceeds demand)
- **shortfall_low** = 25th percentile scenario (more optimistic — more GME growth, later retirements)
- **shortfall_high** = 75th percentile scenario (more pessimistic — earlier retirements, less GME growth)

## Important Limitation: Category-Level Data Only

The AAMC report publishes shortfall projections at five broad specialty group levels:
1. Primary Care
2. Medical Specialties (internal medicine and pediatric subspecialties)
3. Surgical Specialties
4. Other Specialties
5. Hospitalists (primary-care-trained only)

**Individual specialty breakdowns** (e.g., cardiology vs. gastroenterology separately) are
presented only as charts and graphs in the PDF — they are not published as extractable tables.

As a result, `aamc_specialty_shortages.csv` maps each individual specialty to its AAMC
category and assigns the **category-level shortfall** to all specialties within that group.
This means, for example, that Cardiology and Gastroenterology share the same shortfall
range (Medical Specialties: -3,700 to 5,500 by 2036), even though their individual
trajectories differ.

## How This Data Is Used in Scoring

In the Saile Radar scoring model, the AAMC specialty shortage data provides a **national
weight** for each specialty category. Facilities serving specialties with larger projected
shortfalls receive a higher shortage weight in the composite score.

Given that individual specialty data isn't available in extractable form, the category-level
weights are a reasonable approximation. The HRSA HPSA data (Step 1.1) provides more
granular, facility-level shortage information that complements this national picture.

## Specialties Included

31 specialties across 5 AAMC categories, covering all major locum tenens placement areas:
primary care, hospitalist, medical subspecialties, surgical subspecialties, and other specialties
(psychiatry, radiology, anesthesiology, emergency medicine, dermatology, pathology, PM&R).
