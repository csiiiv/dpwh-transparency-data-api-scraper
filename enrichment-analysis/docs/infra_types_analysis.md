# Infrastructure Types and Type of Work Analysis - Insights

## Executive Summary

This document provides analysis and insights from the infrastructure types and type of work data extracted from DPWH projects.

**Data Source**: `projects-data/json/projects-json.tar`  
**Analysis Date**: 1765209451.298551

---

## Key Findings

### Data Coverage

- **Total Contracts**: 246,148
- **infraType Coverage**: 100.0% (246,058 contracts)
- **typeOfWork Coverage**: 97.5% (239,917 contracts)
- **Components Available**: 239,980 contracts (97.5%)

### Infrastructure Type Distribution

The data shows 7 unique infrastructure types:

**Top Infrastructure Types:**

| Rank | infraType | Count | Percentage |
|------|----------|-------|------------|
| 1 | `Roads` | 94,167 | 38.27% |
| 2 | `Buildings and Facilities` | 93,451 | 37.98% |
| 3 | `Flood Control and Drainage` | 35,578 | 14.46% |
| 4 | `Bridges` | 13,624 | 5.54% |
| 5 | `Water Provision and Storage` | 6,919 | 2.81% |
| 6 | `Buildings` | 2,314 | 0.94% |
| 7 | `Septage and Sewerage Plants` | 5 | 0.00% |

### Type of Work Distribution

The data shows **121** unique types of work.

**Top Types of Work:**

| Rank | typeOfWork | Count | Percentage |
|------|------------|-------|------------|
| 1 | `Construction of Multi Purpose Building` | 56,811 | 20.13% |
| 2 | `Construction of Concrete Road` | 50,205 | 17.79% |
| 3 | `Construction of Classrooms` | 26,047 | 9.23% |
| 4 | `Construction of Rain Water Collector` | 25,051 | 8.88% |
| 5 | `Construction of Flood Mitigation Structure` | 21,481 | 7.61% |
| 6 | `Construction of Road Slope Protection Structure` | 9,109 | 3.23% |
| 7 | `Rehabilitation / Major Repair of Multi Purpose Building` | 7,213 | 2.56% |
| 8 | `Preventive Maintenance of Road: Asphalt Overlay` | 7,132 | 2.53% |
| 9 | `Road Widening` | 6,385 | 2.26% |
| 10 | `Construction of Water Supply Systems` | 4,262 | 1.51% |
| 11 | `Rehabilitation of Paved Road` | 4,115 | 1.46% |
| 12 | `Rehabilitation of Concrete Road` | 4,082 | 1.45% |
| 13 | `Construction of Drainage Structure along Road` | 4,051 | 1.44% |
| 14 | `Construction of Revetment` | 3,677 | 1.30% |
| 15 | `Rehabilitation / Major Repair of Bridge` | 3,312 | 1.17% |

---

## Analysis

### 1. Data Completeness

- **infraType**: Excellent coverage (100.0% present). Most contracts have this field.
- **typeOfWork**: Excellent coverage (97.5% present). Most components have this field.

### 2. Infrastructure Type Insights

- **Most Common Types**: `Roads`, `Buildings and Facilities`, `Flood Control and Drainage`
- **Diversity**: 7 distinct infrastructure types identified
- **Concentration**: Moderate concentration - top type represents 38.3% of all contracts

### 3. Type of Work Insights

- **Total Unique Types**: 121 distinct types of work
- **Top 5 Types**: `Construction of Multi Purpose Building`, `Construction of Concrete Road`, `Construction of Classrooms`, `Construction of Rain Water Collector`, `Construction of Flood Mitigation Structure`
- **Granularity**: High granularity - many specific work types (121 unique types)

### 4. Relationship Analysis

**infraType and typeOfWork Relationships:**

| infraType | typeOfWork | Count |
|-----------|------------|-------|
| `Buildings and Facilities` | `Construction of Multi Purpose Building` | 56,808 |
| `Roads` | `Construction of Concrete Road` | 49,987 |
| `Buildings and Facilities` | `Construction of Classrooms` | 26,043 |
| `Water Provision and Storage` | `Construction of Rain Water Collector` | 25,051 |
| `Flood Control and Drainage` | `Construction of Flood Mitigation Structure` | 21,375 |
| `Roads` | `Construction of Road Slope Protection Structure` | 9,045 |
| `Buildings and Facilities` | `Rehabilitation / Major Repair of Multi Purpose Building` | 7,210 |
| `Roads` | `Preventive Maintenance of Road: Asphalt Overlay` | 7,127 |
| `Roads` | `Road Widening` | 6,367 |
| `Water Provision and Storage` | `Construction of Water Supply Systems` | 4,247 |
| `Roads` | `Rehabilitation of Paved Road` | 4,112 |
| `Roads` | `Rehabilitation of Concrete Road` | 4,076 |
| `Roads` | `Construction of Drainage Structure along Road` | 4,036 |
| `Flood Control and Drainage` | `Construction of Revetment` | 3,659 |
| `Bridges` | `Rehabilitation / Major Repair of Bridge` | 3,290 |
| `Bridges` | `Widening of Bridge` | 3,228 |
| `Roads` | `Reconstruction to Concrete Pavement` | 3,180 |
| `Flood Control and Drainage` | `Rehabilitation / Major Repair of Flood Control Structure` | 2,860 |
| `Flood Control and Drainage` | `Construction of Drainage Structure` | 2,791 |
| `Bridges` | `Retrofitting / Strengthening of Bridge` | 2,693 |

**Observations:**
- 212 unique infraType-typeOfWork combinations found
- 6 infrastructure types have associated typeOfWork values

### 5. Location Distribution Analysis

- **Total Unique Regions**: 18 distinct regions
- **Top 5 Regions**: `Region III`, `Region IV-A`, `Region I`, `National Capital Region`, `Region V`
- **Regional Concentration**: Well distributed - top region represents 10.2% of all contracts
- **Total Unique Provinces**: 220 distinct provinces
- **Top 5 Provinces**: `Metro Manila 1st DEO`, `Bulacan 1st DEO`, `Batangas 4th DEO`, `Ilocos Norte 1st DEO`, `Region X`
- **Region Data Quality**: Excellent - 100.0% of contracts have region data

### 6. Yearly Distribution Analysis

- **Year Range**: 2016 - 2025 (10 years)
- **Total Unique Years**: 10 distinct years
- **Peak Year**: `2024` with 30,325 contracts (12.3%)
- **Recent Trend**: increasing - from 21,861 in 2020 to 25,072 in 2025
- **Year Data Quality**: Excellent - 100.0% of contracts have year data

**Year-Infrastructure Type Trends:**

| Year | Top infraType | Count |
|------|----------------|-------|
| `2016` | `Buildings and Facilities` | 11,382 |
| `2017` | `Buildings and Facilities` | 16,935 |
| `2018` | `Buildings and Facilities` | 12,769 |
| `2019` | `Buildings and Facilities` | 10,324 |
| `2020` | `Roads` | 9,585 |
| `2021` | `Buildings and Facilities` | 10,112 |
| `2022` | `Roads` | 11,618 |
| `2023` | `Roads` | 11,730 |
| `2024` | `Roads` | 13,078 |
| `2025` | `Roads` | 10,644 |

**Detailed Year-Infrastructure Type Analysis:**

This table shows the complete breakdown of infrastructure types for each year.

| Year | Roads | Buildings & Facilities | Flood Control | Bridges | Water | Buildings | Septage |
|------|-------|----------------------|---------------|---------|-------|-----------|----------|
| `2016` | 8,072 | 11,382 | 2,038 | 1,447 | 3,694 | 0 | 0 |
| `2017` | 7,437 | 16,935 | 2,680 | 2,028 | 3,334 | 0 | 0 |
| `2018` | 10,078 | 12,769 | 3,949 | 1,756 | 3,423 | 0 | 0 |
| `2019` | 9,334 | 10,324 | 3,031 | 1,401 | 3,851 | 0 | 0 |
| `2020` | 9,585 | 8,506 | 3,019 | 1,348 | 3,669 | 0 | 1 |
| `2021` | 10,055 | 10,112 | 2,733 | 1,077 | 3,250 | 0 | 1 |
| `2022` | 11,618 | 6,581 | 4,023 | 1,377 | 2,273 | 0 | 2 |
| `2023` | 11,730 | 8,419 | 4,568 | 1,318 | 2,781 | 0 | 0 |
| `2024` | 13,078 | 9,864 | 5,329 | 1,319 | 1,950 | 0 | 0 |
| `2025` | 10,644 | 6,152 | 4,072 | 1,338 | 1,506 | 0 | 0 |

**Regional Infrastructure Type Preferences:**

This table shows which infrastructure types are most common in each region.

| Region | Top infraType | Count | % of Region |
|--------|---------------|-------|-------------|
| `Central Office` | `Flood Control and Drainage` | 186 | 63.1% |
| `Cordillera Administrative Region` | `Roads` | 5,141 | 52.3% |
| `National Capital Region` | `Buildings and Facilities` | 6,836 | 40.7% |
| `Negros Island Region` | `Buildings and Facilities` | 4,413 | 44.9% |
| `Region I` | `Roads` | 6,687 | 37.7% |
| `Region II` | `Roads` | 5,648 | 40.4% |
| `Region III` | `Roads` | 9,102 | 36.1% |
| `Region IV-A` | `Roads` | 9,695 | 38.8% |
| `Region IV-B` | `Roads` | 4,260 | 39.0% |
| `Region IX` | `Roads` | 3,674 | 39.8% |
| `Region V` | `Roads` | 6,174 | 38.1% |
| `Region VI` | `Buildings and Facilities` | 5,996 | 46.3% |
| `Region VII` | `Roads` | 5,587 | 40.6% |
| `Region VIII` | `Roads` | 6,308 | 41.2% |
| `Region X` | `Buildings and Facilities` | 6,104 | 39.4% |
| `Region XI` | `Buildings and Facilities` | 5,897 | 42.0% |
| `Region XII` | `Buildings and Facilities` | 4,978 | 48.3% |
| `Region XIII` | `Buildings and Facilities` | 3,795 | 41.6% |

**Regional Activity Trends:**

This analysis shows which regions had the most activity in recent years.

| Region | Peak Year | Contracts in Peak Year | % of Region Total |
|--------|-----------|------------------------|-------------------|
| `Central Office` | `2019` | 47 | 15.9% |
| `Cordillera Administrative Region` | `2022` | 1,278 | 13.0% |
| `National Capital Region` | `2024` | 2,009 | 11.9% |
| `Negros Island Region` | `2018` | 1,153 | 11.7% |
| `Region I` | `2024` | 2,338 | 13.2% |
| `Region II` | `2024` | 1,969 | 14.1% |
| `Region III` | `2024` | 3,669 | 14.5% |
| `Region IV-A` | `2024` | 3,211 | 12.9% |
| `Region IV-B` | `2018` | 1,431 | 13.1% |
| `Region IX` | `2017` | 1,227 | 13.3% |
| `Region V` | `2018` | 2,151 | 13.3% |
| `Region VI` | `2024` | 1,628 | 12.6% |
| `Region VII` | `2024` | 1,854 | 13.5% |
| `Region VIII` | `2024` | 1,946 | 12.7% |
| `Region X` | `2017` | 1,881 | 12.1% |
| `Region XI` | `2017` | 2,084 | 14.8% |
| `Region XII` | `2018` | 1,263 | 12.2% |
| `Region XIII` | `2017` | 1,191 | 13.0% |

---

## Recommendations

1. **Improve infraType Coverage**: Consider backfilling missing infraType values from category or description fields.

2. **Improve typeOfWork Coverage**: Some components are missing typeOfWork. Review data extraction process.

3. **Standardize typeOfWork**: High number of unique types suggests need for standardization or categorization.

6. **Data Quality**: Use these insights to validate data quality and identify areas for improvement.


### 7. PSGC Enrichment Analysis

- **PSGC Enrichment**: No PSGC data found in analyzed files.
- **Recommendation**: Run the enrichment script (`enrich_with_barangay.py`) to add PSGC data before analysis.
- **Benefits**: PSGC enrichment provides standardized location names and codes, enabling better geographic analysis.


---

*Analysis generated automatically from infrastructure types data.*
