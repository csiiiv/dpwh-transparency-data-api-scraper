# Contract Data Comparison: 21MD0023

## Overview

This document compares the data structure and fields between:
- **Base Data API** (`base-data/sample.json`) - Paginated listing endpoint
- **Projects Data API** (`projects-data/dpwh-projects-api/samples/21MD0023.json`) - Individual contract detail endpoint

**Contract ID**: 21MD0023  
**Description**: CONCRETING OF G. GOKOTANO STREET, BARANGAY POBLACION, PIKIT, NORTH COTABATO

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Fields in Base Data | 23 |
| Fields in Projects Data | 52 |
| Common Fields (same value) | 21 |
| Common Fields (different value) | 0 |
| Fields Only in Base Data | 2 |
| Fields Only in Projects Data | 31 |

---

## Common Fields (Same Values)

These fields exist in both APIs with identical values:

| Field | Value |
|-------|-------|
| `amountPaid` | `0` |
| `budget` | `1959816.63` |
| `category` | `Roads` |
| `completionDate` | `2021-05-09` |
| `contractId` | `21MD0023` |
| `contractor` | `LLABAN CONSTRUCTION & SUPPLY (FORMERLY: LLABAN CON (29504)` |
| `description` | `CONCRETING OF G. GOKOTANO STREET, BARANGAY POBLACION, PIKIT, NORTH COTABATO` |
| `infraYear` | `2021` |
| `isLive` | `False` |
| `latitude` | `7.0489667` |
| `livestreamDetectedAt` | `None` |
| `livestreamUrl` | `None` |
| `livestreamVideoId` | `None` |
| `location.province` | `Cotabato 1st DEO` |
| `location.region` | `Region XII` |
| `longitude` | `124.6761778` |
| `programName` | `Regular Infra` |
| `progress` | `100` |
| `sourceOfFunds` | `Regular Infra - GAA 2021 LP` |
| `startDate` | `2021-04-07` |
| `status` | `Completed` |

---

## Fields with Different Values

*No fields with different values found.*

---

## Fields Only in Base Data API

| Field | Value |
|-------|-------|
| `componentCategories` | `Roads` |
| `reportCount` | `0` |

---

## Fields Only in Projects Data API

| Field | Value |
|-------|-------|
| `bidders` | `*list* (2 items)` |
| `components` | `*list* (1 items)` |
| `contractEffectivityDate` | `2021-04-07` |
| `coordinates` | `*list* (1 items)` |
| `expiryDate` | `2021-05-07` |
| `imageSummary.hasImages` | `True` |
| `imageSummary.latestImageDate` | `2021-10-13 02:06:05.585999` |
| `imageSummary.totalImages` | `3` |
| `infraType` | `Roads` |
| `isVerifiedByDpwh` | `False` |
| `isVerifiedByPublic` | `False` |
| `links.advertisement` | `https://archive.dpwh.gov.ph/archive/cw/advertisements/21MD0023-Concreting og G. Gokotano Street, Bar...` |
| `links.contractAgreement` | `` |
| `links.engineeringDesign` | `` |
| `links.noticeOfAward` | `https://www.dpwh.gov.ph/dpwh/sites/default/files/webform/civil_works/notice_of_award/21MD0023.pdf` |
| `links.noticeToProceed` | `` |
| `links.programOfWork` | `` |
| `location.coordinates.latitude` | `7.0489667` |
| `location.coordinates.longitude` | `124.6761778` |
| `location.coordinates.verified` | `False` |
| `location.infraType` | `Roads` |
| `nysReason` | `None` |
| `procurement.abc` | `1980000.00` |
| `procurement.advertisementDate` | `2020-11-13 00:00:00.0000000` |
| `procurement.awardAmount` | `1,959,816.63` |
| `procurement.bidSubmissionDeadline` | `2020-12-09 00:00:00.0000000` |
| `procurement.contractName` | `CONCRETING OF G. GOKOTANO STREET, BARANGAY POBLACION, PIKIT, NORTH COTABATO` |
| `procurement.dateOfAward` | `2021-03-30 00:00:00.0000000` |
| `procurement.fundingInstrument` | `GOP-GOVERNMENT OF THE PHILIPPINES` |
| `procurement.status` | `A` |
| `winnerNames` | `LLABAN CONSTRUCTION & SUPPLY (FORMERLY: LLABAN CON` |

---

## Detailed Field Analysis

### Base Data Structure

```json
{
  "contractId": "21MD0023",
  "description": "CONCRETING OF G. GOKOTANO STREET, BARANGAY POBLACION, PIKIT, NORTH COTABATO",
  "category": "Roads",
  "componentCategories": "Roads",
  "status": "Completed",
  "budget": 1959816.63,
  "amountPaid": 0,
  "progress": 100,
  "location": {
    "province": "Cotabato 1st DEO",
    "region": "Region XII"
  },
  "contractor": "LLABAN CONSTRUCTION & SUPPLY (FORMERLY: LLABAN CON (29504)",
  "startDate": "2021-04-07",
  "completionDate": "2021-05-09",
  "infraYear": "2021",
  "programName": "Regular Infra",
  "sourceOfFunds": "Regular Infra - GAA 2021 LP",
  "isLive": false,
  "livestreamUrl": null,
  "livestreamVideoId": null,
  "livestreamDetectedAt": null,
  "latitude": 7.0489667,
  "longitude": 124.6761778,
  "reportCount": 0
}
...
```

### Projects Data Structure

```json
{
  "contractId": "21MD0023",
  "description": "CONCRETING OF G. GOKOTANO STREET, BARANGAY POBLACION, PIKIT, NORTH COTABATO",
  "category": "Roads",
  "status": "Completed",
  "budget": 1959816.63,
  "amountPaid": 0,
  "progress": 100,
  "location": {
    "region": "Region XII",
    "province": "Cotabato 1st DEO",
    "infraType": "Roads",
    "coordinates": {
      "latitude": 7.0489667,
      "longitude": 124.6761778,
      "verified": false
    }
  },
  "infraType": "Roads",
  "contractor": "LLABAN CONSTRUCTION & SUPPLY (FORMERLY: LLABAN CON (29504)",
  "startDate": "2021-04-07",
  "completionDate": "2021-05-09",
  "infraYear": "2021",
  "contractEffectivityDate": "2021-04-07",
  "expiryDate": "2021-05-07",
  "nysReason": null,
  "programName": "Regular Infra",
  "sourceOfFunds": "Regular Infra - GAA 2021 LP",
  "isVerifiedByDpwh": false,
  "isVerifiedByPublic": false,
  "isLive": false,
  "livestreamUrl": null,
  "livestreamVideoId": null,
  "livestreamDetectedAt": null,
  "components": [
    {
      "componentId": "P00551360MN-CW1",
      "description": "Construction of Concrete Road - Concreting of G. Gokotano Street, Barangay Poblacion, Pikit, North Cotabato",
      "infraType": "Roads",
      "typeOfWork": "Construction of Concrete Road",
      "region": "Region XII",
      "province": "COTABATO (NORTH COTABATO)",
      "coordinates": {
        "latitude": 7.0489667,
        "longitude": 124.6761778,
        "source": "infra_track",
        "locationVerified": false
      }
    }
  ],
  "winnerNames": "LLABAN CONSTRUCTION & SUPPLY (FORMERLY: LLABAN CON",
  "bidders": [
    {
      "name": "LLABAN CONSTRUCTION & SUPPLY (FORMERLY: LLABAN CON (29504)",
      "pcabId": "29504",
      "participation": 100,
      "isWinner": true
    },
    {
      "name": "RDEN CONSTRUCTION & SUPPLY (33707)",
      "pcabId": "33707",
      "participation": 100,
      "isWinner": false
    }
  ],
  "procurement": {
    "contractName": "CONCRETING OF G. GOKOTANO STREET, BARANGAY PO
...
```

---

## Key Observations

- **Component Details**: Projects API includes detailed component information with individual coordinates, component IDs, and type of work.
- **Bidding Information**: Projects API includes detailed bidder information (names, PCAB IDs, participation, winner status) and winner names.
- **Procurement Details**: Projects API includes comprehensive procurement information including ABC (Approved Budget for Contract), advertisement dates, bid submission deadlines, date of award, award amounts, funding instruments, and procurement status.
- **Document Links**: Projects API includes links to various procurement documents (advertisements, contract agreements, notices of award, notices to proceed, program of work, engineering designs).
- **Image Metadata**: Projects API includes image summary information (total images, latest image date, hasImages flag).
- **Enhanced Location Data**: Projects API includes detailed coordinate information within the location object with verification status.
- **Contract Dates**: Projects API includes additional contract dates (effectivity date, expiry date) beyond start and completion dates.
- **Verification Status**: Projects API includes verification flags for both DPWH and public verification.
- **Base Data Only**: Base Data API includes `componentCategories` field which is not present in Projects API (though `infraType` serves a similar purpose).
- **Base Data Only**: Base Data API includes `reportCount` field which tracks the number of reports, not available in Projects API.

### Data Completeness

- **Base Data API**: Provides a lightweight summary suitable for listing/browsing contracts. Contains 23 fields focused on core contract information.
- **Projects Data API**: Provides comprehensive detail suitable for individual contract views. Contains 52 fields with extensive additional information about components, bidding, procurement, and documentation.
- **Overlap**: 21 fields are common between both APIs with identical values, ensuring consistency in core contract data.

### Leaf-Based Analysis Insights

- **100% Data Coverage**: All 19 leaf values from Base Data API are present in Projects Data API.
- **Path Variations**: 11 values appear at different or additional paths, while 8 values appear at identical paths in both APIs.
- **Additional Data**: Projects Data API contains 23 additional unique values not present in Base Data API.
- **Data Consistency**: All base values exist in projects data, confirming that Projects Data API is a superset of Base Data API.

### Key Findings: Values at Additional Paths

The leaf-based analysis reveals that several values appear at **additional paths** in Projects Data API:

| Value | Base Data Path | Additional Paths in Projects Data |
|-------|----------------|-----------------------------------|
| `LLABAN CONSTRUCTION & SUPPLY (FORMERLY: LLABAN CON (29504)` | `contractor` | `bidders[0].name` |
| `100` | `progress` | `bidders[0].participation, bidders[1].participation` |
| `124.6761778` | `longitude` | `location.coordinates.longitude, components[0].coordinates.longitude, coordinates[0].longitude` |
| `CONCRETING OF G. GOKOTANO STREET, BARANGAY POBLACION, PIKIT,...` | `description` | `procurement.contractName` |
| `7.0489667` | `latitude` | `location.coordinates.latitude, components[0].coordinates.latitude, coordinates[0].latitude` |
| `false` | `isLive` | `location.coordinates.verified, isVerifiedByDpwh, isVerifiedByPublic` |
| `Region XII` | `location.region` | `components[0].region` |
| `Roads` | `category` | `location.infraType, infraType, components[0].infraType` |
| `2021-04-07` | `startDate` | `contractEffectivityDate` |
| `null` | `livestreamUrl` | `nysReason` |

**Notable Examples:**

- **Latitude/Longitude**: In Base Data API, coordinates appear only at the top level (`latitude`, `longitude`). In Projects Data API, they appear at both the top level AND nested under `location.coordinates` (plus in component arrays), providing multiple access points to the same coordinate data.

- **Contractor Information**: The contractor name appears at the top level in both APIs, but Projects Data API also includes it in the `bidders` array with additional metadata (PCAB ID, participation, winner status).

- **Description**: The contract description appears at the top level in both, but Projects Data API also includes it in the `procurement.contractName` field, linking it to procurement records.

- **Location Data**: Region and province information appears in the `location` object in both APIs, but Projects Data API also includes this in component-level data, allowing for more granular location tracking.


---

## Leaf-Based Comparison (Value-Level Analysis)

This section compares actual data values regardless of their nesting structure.

### Summary

| Metric | Count |
|--------|-------|
| Total Leaf Values in Base Data | 19 |
| Total Leaf Values in Projects Data | 42 |
| Common Values (appear in both) | 19 |
| Same Value, Same Path | 8 |
| Same Value, Different Path (nested differently) | 11 |
| Values Only in Base Data | 0 |
| Values Only in Projects Data | 23 |

### Values at Different/Additional Paths

These values exist in both APIs but appear at different or additional paths:

| Value | Base Data Path(s) | Projects Data Path(s) | Note |
|-------|------------------|---------------------|------|
| `0` | `amountPaid, reportCount` | `amountPaid` | Also appears at additional paths in Base Data |
| `100` | `progress` | `progress, bidders[0].participation (+1 more)` | Also appears at additional paths in Projects Data |
| `124.6761778` | `longitude` | `longitude, location.coordinates.longitude (+2 more)` | Also appears at additional paths in Projects Data |
| `2021-04-07` | `startDate` | `startDate, contractEffectivityDate` | Also appears at additional paths in Projects Data |
| `7.0489667` | `latitude` | `latitude, location.coordinates.latitude (+2 more)` | Also appears at additional paths in Projects Data |
| `CONCRETING OF G. GOKOTANO STREET, BARANG...` | `description` | `description, procurement.contractName` | Also appears at additional paths in Projects Data |
| `LLABAN CONSTRUCTION & SUPPLY (FORMERLY: ...` | `contractor` | `contractor, bidders[0].name` | Also appears at additional paths in Projects Data |
| `Region XII` | `location.region` | `location.region, components[0].region` | Also appears at additional paths in Projects Data |
| `Roads` | `category, componentCategories` | `category, location.infraType (+2 more)` | Also appears at additional paths in Base Data |
| `false` | `isLive` | `isLive, location.coordinates.verified (+5 more)` | Also appears at additional paths in Projects Data |
| `null` | `livestreamUrl, livestreamDetectedAt, livestreamVideoId` | `livestreamUrl, livestreamDetectedAt, livestreamVideoId, nysReason` | Also appears at additional paths in Projects Data |

### Values Only in Projects Data

| Value | Path(s) |
|-------|--------|
| `` | `links.contractAgreement, links.noticeToProceed (+2 more)` |
| `1,959,816.63` | `procurement.awardAmount` |
| `1980000.00` | `procurement.abc` |
| `2020-11-13 00:00:00.0000000` | `procurement.advertisementDate` |
| `2020-12-09 00:00:00.0000000` | `procurement.bidSubmissionDeadline` |
| `2021-03-30 00:00:00.0000000` | `procurement.dateOfAward` |
| `2021-05-07` | `expiryDate` |
| `2021-10-13 02:06:05.585999` | `imageSummary.latestImageDate` |
| `29504` | `bidders[0].pcabId` |
| `3` | `imageSummary.totalImages` |
| `33707` | `bidders[1].pcabId` |
| `A` | `procurement.status` |
| `COTABATO (NORTH COTABATO)` | `components[0].province` |
| `Construction of Concrete Road` | `components[0].typeOfWork` |
| `Construction of Concrete Road - Concreting of G. G...` | `components[0].description, coordinates[0].description` |

*Showing first 15 of 23 unique values.*

---

*Report generated automatically by comparison script.*
