# DPWH Data Enrichment Documentation

## Overview

This document describes how the `enrich_with_barangay.py` script extracts and enriches DPWH project data with Philippine Standard Geographic Code (PSGC) information using the [barangay package](https://github.com/bendlikeabamboo/barangay/).

## Purpose

The enrichment process adds the following fields to DPWH project JSON files:

1. **PSGC Data**: Barangay, municipality, province, region names, and PSGC codes
2. **Project Description (Cleaned)**: Project description with location information removed
3. **Misc Notes**: Tracking of parsing issues and data quality concerns

## Data Flow

```
┌─────────────┐
│  Input JSON │
│   (DPWH)    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────┐
│  Extract Location Info  │
│  - Region normalization │
│  - Description parsing  │
│  - Province cleaning    │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  Search Barangay DB     │
│  - Fuzzy search         │
│  - Direct lookup        │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  Build Hierarchy        │
│  - Trace parent chain   │
│  - Fill missing levels  │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  Extract Project       │
│  Details               │
│  - Remove location      │
│  - Clean description    │
└──────┬──────────────────┘
       │
       ▼
┌─────────────────────────┐
│  Track Issues          │
│  - Add misc_notes       │
│  - Log problems         │
└──────┬──────────────────┘
       │
       ▼
┌─────────────┐
│ Output JSON │
│ (Enriched)  │
└─────────────┘
```

## Step-by-Step Process

### 1. Input Data Structure

The script processes DPWH project JSON files with the following structure:

```json
{
  "status": 200,
  "code": "SUCCESS",
  "data": {
    "contractId": "21MD0023",
    "description": "CONCRETING OF G. GOKOTANO STREET, BARANGAY POBLACION, PIKIT, NORTH COTABATO",
    "location": {
      "region": "Region XII",
      "province": "Cotabato 1st DEO",
      "coordinates": {
        "latitude": 7.0489667,
        "longitude": 124.6761778
      }
    },
    "components": [
      {
        "description": "...",
        "province": "COTABATO (NORTH COTABATO)",
        "region": "Region XII"
      }
    ]
  }
}
```

### 2. Location Information Extraction

#### 2.1 Region Normalization

**Function**: `normalize_region_name(region: str) -> str`

The script normalizes DPWH region names to match PSGC format:

**Mapping Table**:
- `"Region I"` → `"Ilocos Region"`
- `"Region II"` → `"Cagayan Valley"`
- `"Region III"` → `"Central Luzon"`
- `"Region IV-A"` → `"CALABARZON"`
- `"Region IV-B"` → `"MIMAROPA Region"`
- `"Region V"` → `"Bicol Region"`
- `"Region VI"` → `"Western Visayas"`
- `"Region VII"` → `"Central Visayas"`
- `"Region VIII"` → `"Eastern Visayas"`
- `"Region IX"` → `"Zamboanga Peninsula"`
- `"Region X"` → `"Northern Mindanao"`
- `"Region XI"` → `"Davao Region"`
- `"Region XII"` → `"Soccsksargen"`
- `"Region XIII"` → `"Caraga"`
- `"CAR"` → `"Cordillera Administrative Region (CAR)"`
- `"NCR"` → `"National Capital Region (NCR)"`
- `"BARMM"` → `"Bangsamoro Autonomous Region in Muslim Mindanao (BARMM)"`

**Process**:
1. Check for exact match in mapping table
2. Try partial match if exact match fails
3. Search in `BARANGAY_FLAT` for region type entries
4. Return normalized name or original if not found

**Example**:
```python
normalize_region_name("Region XII")  # Returns: "Soccsksargen"
normalize_region_name("Region X")    # Returns: "Northern Mindanao"
```

#### 2.2 Description Parsing

**Function**: `extract_location_from_description(description: str) -> Dict[str, Optional[str]]`

Extracts location information from project descriptions using regex patterns.

**Patterns Used**:

1. **Barangay Pattern**:
   ```regex
   BARANGAY\s+([A-Z][A-Z\s]+?)(?:,|$)
   ```
   - Matches: `"BARANGAY POBLACION"`, `"BARANGAY SANTA ANA"`
   - Example: `"CONCRETING OF STREET, BARANGAY POBLACION, PIKIT"` → `{"barangay": "POBLACION"}`

2. **Municipality/City Pattern**:
   ```regex
   (?:MUNICIPALITY OF|CITY OF|MUNICIPALITY|CITY)\s+([A-Z][A-Z\s]+?)(?:,|$)
   ```
   - Matches: `"CITY OF MANILA"`, `"MUNICIPALITY OF PIKIT"`
   - Falls back to second-to-last comma-separated part if no explicit pattern

3. **Province Pattern**:
   ```regex
   ([A-Z][A-Z\s]+?)\s+(?:PROVINCE|PROV)
   ```
   - Matches: `"NORTH COTABATO PROVINCE"`
   - Falls back to last comma-separated part if contains common province names

**Extraction Strategy**:
1. Split description by commas
2. Check each part against regex patterns
3. Identify location components based on position and patterns
4. Return dictionary with extracted values

**Example**:
```python
description = "CONCRETING OF G. GOKOTANO STREET, BARANGAY POBLACION, PIKIT, NORTH COTABATO"
extract_location_from_description(description)
# Returns: {
#   "barangay": "POBLACION",
#   "municipality": "PIKIT",
#   "province": "NORTH COTABATO"
# }
```

#### 2.3 Province Name Cleaning

**Process**: Removes DEO (District Engineering Office) suffixes from province names.

**Patterns**:
- `\s+\d+(st|nd|rd|th)\s+DEO.*$` - Matches "1st DEO", "2nd DEO", etc.
- `\s*\([^)]*DEO[^)]*\)` - Matches "(Cotabato 1st DEO)"

**Example**:
```python
"Cotabato 1st DEO" → "Cotabato"
"Bukidnon 2nd DEO" → "Bukidnon"
```

### 3. Location Search in Barangay Database

**Function**: `find_location_in_barangay(...) -> Tuple[Optional[Dict], List[str]]`

Searches for location in the barangay database using multiple strategies.

#### 3.1 Strategy 1: Fuzzy Search

**Process**:
1. Build search query from available location components:
   - Format: `"{barangay}, {municipality}, {province}, {region}"`
2. Use `barangay.search()` function with:
   - `match_hooks=["barangay", "municipality", "province"]`
   - `threshold=60.0` (60% similarity minimum)
   - `n=5` (return top 5 matches)
3. Extract PSGC ID from best match
4. Look up full location data in `BARANGAY_FLAT` using PSGC ID
5. Build location hierarchy

**Match Quality Assessment**:
- Check `f_0pmb_ratio_score` (full match score)
- If score < 70%, add `LOW_CONFIDENCE_MATCH` note
- If multiple matches found, add `MULTIPLE_MATCHES` note

**Example**:
```python
search("Poblacion, Pikit, Cotabato, Soccsksargen")
# Returns list of matches with scores
# Best match: {"psgc_id": "1204712050", "f_0pmb_ratio_score": 88.9}
```

#### 3.2 Strategy 2: Direct Lookup

**Process**:
1. If fuzzy search fails or no search query available
2. Search `BARANGAY_FLAT` directly by name
3. Match against barangay or municipality name
4. Case-insensitive matching

**Example**:
```python
# Direct lookup for "Poblacion"
for loc in BARANGAY_FLAT:
    if loc["name"].upper() == "POBLACION":
        return build_location_hierarchy(loc)
```

#### 3.3 Location Hierarchy Building

**Function**: `build_location_hierarchy(location: Dict) -> Dict`

Builds complete administrative hierarchy from a location entry.

**Process**:
1. Identify location type (barangay, municipality, province, region)
2. Set corresponding field in hierarchy
3. Trace parent hierarchy using `parent_psgc_id`:
   - Start with current location
   - Find parent using `parent_psgc_id`
   - Continue until root (region) or max depth reached
4. Fill in missing hierarchy levels from parent chain

**Example**:
```python
# Input: Barangay entry
{
  "name": "Poblacion",
  "type": "barangay",
  "psgc_id": "1204712050",
  "parent_psgc_id": "1204700000"  # Municipality
}

# Output: Complete hierarchy
{
  "barangay_name": "Poblacion",
  "municipality_name": "Pikit",      # From parent
  "province_name": "Cotabato",        # From grandparent
  "region_name": "Region XII (SOCCSKSARGEN)",  # From great-grandparent
  "psgc_code": "1204712050",
  "location_type": "barangay"
}
```

### 4. Project Description Cleaning

**Function**: `extract_project_details_from_description(description: str, location_info: Dict) -> str`

Removes location information from description to extract actual project details.

**Strategy**: Work backwards from the end, removing location parts

**Process**:
1. Split description by commas into parts
2. Identify location parts:
   - **Last part**: Usually province (check against extracted province or common province names)
   - **Second-to-last part**: Usually municipality (check against extracted municipality)
   - **Any part**: Check for "BARANGAY {name}" pattern
3. Remove identified location parts
4. Reconstruct description from remaining parts
5. Clean up: remove trailing "NORTH", "SOUTH", etc., multiple commas, leading/trailing whitespace

**Example**:
```python
description = "CONCRETING OF G. GOKOTANO STREET, BARANGAY POBLACION, PIKIT, NORTH COTABATO"
location_info = {"barangay": "POBLACION", "municipality": "PIKIT", "province": "NORTH COTABATO"}

# Split: ["CONCRETING OF G. GOKOTANO STREET", "BARANGAY POBLACION", "PIKIT", "NORTH COTABATO"]
# Remove: parts[-1] (NORTH COTABATO), parts[-2] (PIKIT), parts with "BARANGAY POBLACION"
# Result: "CONCRETING OF G. GOKOTANO STREET"
```

**Edge Cases Handled**:
- Descriptions without clear location markers
- Duplicate location information
- Location names that might be part of project name
- Conservative approach: if result too short (< 10 chars), return original

### 5. Data Enrichment Process

**Function**: `enrich_project_data(project_data: Dict) -> Dict`

Main function that orchestrates the enrichment process.

#### 5.1 Data Extraction Phase

1. **Extract from location object**:
   - Region: `data.location.region`
   - Province: `data.location.province`
   - Coordinates: `data.location.coordinates`

2. **Extract from components** (if available):
   - Component province: `data.components[0].province`
   - Component description: `data.components[0].description`
   - Extract location from component description

3. **Extract from main description**:
   - Parse description for location information
   - Extract barangay, municipality, province

4. **Clean province name**:
   - Remove DEO suffixes
   - Normalize format

#### 5.2 Location Search Phase

1. **Normalize region name**:
   - Convert DPWH format to PSGC format

2. **Build search query**:
   - Combine: barangay, municipality, province, region

3. **Execute search strategies**:
   - Try fuzzy search first
   - Fall back to direct lookup if needed
   - Collect notes about search process

#### 5.3 Data Addition Phase

1. **Add PSGC data**:
   ```json
   "psgc": {
     "barangay_name": "Poblacion",
     "municipality_name": "Pikit",
     "province_name": "Cotabato",
     "region_name": "Region XII (SOCCSKSARGEN)",
     "psgc_code": "1204712050",
     "location_type": "barangay"
   }
   ```

2. **Add cleaned project description**:
   ```json
   "project_description_clean": "CONCRETING OF G. GOKOTANO STREET"
   ```

3. **Add misc notes**:
   ```json
   "misc_notes": [
     "PROJECT_DETAILS_EXTRACTED: Removed location info from description",
     "REGION_NORMALIZED: 'Region XII' -> 'Soccsksargen'",
     "LOW_CONFIDENCE_MATCH: Match score 63.2% (threshold: 70%)",
     "MULTIPLE_MATCHES: Found 4 potential matches, using best match",
     "MATCH_FOUND: Found via fuzzy search (PSGC: 1204712050)"
   ]
   ```

#### 5.4 Issue Tracking

The script tracks various issues during processing:

**Missing Data Issues**:
- `MISSING_REGION`: No region in location object
- `MISSING_PROVINCE`: No province in location object
- `MISSING_DESCRIPTION`: No description field
- `MISSING_COORDINATES`: No latitude/longitude
- `MISSING_COMPONENTS`: No components array
- `MISSING_BIDDERS`: No bidders array

**Normalization Issues**:
- `REGION_NORMALIZED`: Region name was normalized
- `REGION_NOT_FOUND`: Could not normalize region
- `PROVINCE_CLEANED`: DEO suffix removed from province

**Parsing Issues**:
- `DESCRIPTION_PARSE_FAILED`: Could not extract location from description
- `EXTRACTED_BARANGAY`: Successfully extracted barangay
- `EXTRACTED_MUNICIPALITY`: Successfully extracted municipality
- `EXTRACTED_PROVINCE`: Successfully extracted province

**Search Issues**:
- `INSUFFICIENT_SEARCH_DATA`: No data for search
- `LOW_CONFIDENCE_MATCH`: Match score below threshold
- `MULTIPLE_MATCHES`: Multiple potential matches found
- `SEARCH_ERROR`: Fuzzy search failed
- `LOCATION_NOT_FOUND`: Could not find location
- `MATCH_FOUND`: Successfully found location

**Data Mismatch Issues**:
- `PROVINCE_MISMATCH`: DPWH province doesn't match PSGC province
- `REGION_MISMATCH`: DPWH region doesn't match PSGC region

## Code Structure

### Main Functions

1. **`normalize_region_name(region: str) -> str`**
   - Normalizes DPWH region names to PSGC format

2. **`extract_location_from_description(description: str) -> Dict`**
   - Extracts location components from description text

3. **`extract_project_details_from_description(description: str, location_info: Dict) -> str`**
   - Removes location information to get clean project description

4. **`find_location_in_barangay(...) -> Tuple[Optional[Dict], List[str]]`**
   - Searches for location in barangay database
   - Returns location data and notes

5. **`build_location_hierarchy(location: Dict) -> Dict`**
   - Builds complete administrative hierarchy from location entry

6. **`enrich_project_data(project_data: Dict) -> Dict`**
   - Main enrichment function

7. **`process_json_file(input_file: Path, output_file: Path)`**
   - Processes a single JSON file

8. **`main()`**
   - Main entry point, processes all files in samples directory

## Example: Complete Processing Flow

### Input
```json
{
  "status": 200,
  "code": "SUCCESS",
  "data": {
    "contractId": "21MD0023",
    "description": "CONCRETING OF G. GOKOTANO STREET, BARANGAY POBLACION, PIKIT, NORTH COTABATO",
    "location": {
      "region": "Region XII",
      "province": "Cotabato 1st DEO"
    }
  }
}
```

### Processing Steps

1. **Extract location info**:
   - Region: "Region XII" → Normalize → "Soccsksargen"
   - Province: "Cotabato 1st DEO" → Clean → "Cotabato"
   - From description: Extract "POBLACION" (barangay), "PIKIT" (municipality)

2. **Search barangay database**:
   - Query: "POBLACION, PIKIT, Cotabato, Soccsksargen"
   - Fuzzy search finds match with PSGC: "1204712050"
   - Build hierarchy: Poblacion → Pikit → Cotabato → Region XII

3. **Extract project details**:
   - Remove: "BARANGAY POBLACION, PIKIT, NORTH COTABATO"
   - Result: "CONCRETING OF G. GOKOTANO STREET"

4. **Track issues**:
   - Region normalized
   - Low confidence match (63.2%)
   - Multiple matches found
   - Match found successfully

### Output
```json
{
  "status": 200,
  "code": "SUCCESS",
  "data": {
    "contractId": "21MD0023",
    "description": "CONCRETING OF G. GOKOTANO STREET, BARANGAY POBLACION, PIKIT, NORTH COTABATO",
    "project_description_clean": "CONCRETING OF G. GOKOTANO STREET",
    "psgc": {
      "barangay_name": "Poblacion",
      "municipality_name": "Pikit",
      "province_name": "Cotabato",
      "region_name": "Region XII (SOCCSKSARGEN)",
      "psgc_code": "1204712050",
      "location_type": "barangay"
    },
    "misc_notes": [
      "PROJECT_DETAILS_EXTRACTED: Removed location info from description",
      "REGION_NORMALIZED: 'Region XII' -> 'Soccsksargen'",
      "LOW_CONFIDENCE_MATCH: Match score 63.2% (threshold: 70%)",
      "MULTIPLE_MATCHES: Found 4 potential matches, using best match",
      "MATCH_FOUND: Found via fuzzy search (PSGC: 1204712050)"
    ]
  }
}
```

## Dependencies

### Required Packages

1. **barangay** (https://github.com/bendlikeabamboo/barangay/)
   - Provides PSGC data and fuzzy search functionality
   - Installation: `pip install barangay`

2. **Standard Library**:
   - `json`: JSON file handling
   - `re`: Regular expressions for pattern matching
   - `pathlib`: File path operations
   - `typing`: Type hints

## Error Handling

The script includes comprehensive error handling:

1. **File Operations**:
   - Checks if files exist before processing
   - Handles JSON parsing errors gracefully
   - Creates output directory if it doesn't exist

2. **Search Operations**:
   - Catches exceptions from fuzzy search
   - Falls back to alternative strategies
   - Logs errors in misc_notes

3. **Data Validation**:
   - Checks for required fields before processing
   - Validates data structure
   - Handles missing or null values

## Performance Considerations

1. **Barangay Database Loading**:
   - `BARANGAY_FLAT` is loaded once at import time
   - Contains ~42,000+ location entries
   - In-memory lookups are fast

2. **Fuzzy Search**:
   - Uses optimized search algorithm from barangay package
   - Threshold of 60% balances accuracy and recall
   - Returns top 5 matches for best result selection

3. **Hierarchy Building**:
   - Maximum depth limit (10 levels) prevents infinite loops
   - Parent lookup is O(n) but acceptable for small dataset

## Limitations

1. **Description Format Variations**:
   - Some descriptions don't follow standard format
   - Location extraction may fail for non-standard formats
   - Example: Road names with coordinates (18KA0002)

2. **Name Variations**:
   - Province/municipality names may vary between DPWH and PSGC
   - Fuzzy search helps but may not catch all variations
   - Manual review needed for mismatches

3. **Multiple Locations**:
   - Some projects span multiple locations
   - Script only extracts primary location
   - Component-level locations may differ

4. **Confidence Thresholds**:
   - Low confidence matches (< 70%) may be incorrect
   - Manual verification recommended for low-confidence matches

## Best Practices

1. **Review misc_notes**:
   - Check for high-impact issues (LOCATION_NOT_FOUND, REGION_MISMATCH)
   - Review low-confidence matches
   - Verify province/region mismatches

2. **Validate PSGC Codes**:
   - Cross-reference with official PSGC database
   - Verify hierarchy completeness
   - Check for missing levels

3. **Handle Edge Cases**:
   - Descriptions without clear location markers
   - Projects spanning multiple locations
   - Historical name changes

## Future Improvements

1. **Coordinate-based Lookup**:
   - Use latitude/longitude for reverse geocoding
   - Verify location matches using coordinates
   - Handle projects with multiple coordinate sets

2. **Enhanced Pattern Matching**:
   - Machine learning for description parsing
   - Support for more description formats
   - Better handling of abbreviations

3. **Batch Processing**:
   - Process multiple files in parallel
   - Progress tracking for large datasets
   - Resume capability for interrupted runs

4. **Data Quality Metrics**:
   - Confidence scores for all extractions
   - Validation against known good data
   - Automated quality reports

## Algorithm Details

### Regex Patterns Used

#### Barangay Extraction
```python
r'BARANGAY\s+([A-Z][A-Z\s]+?)(?:,|$)'
```
- Matches: "BARANGAY POBLACION", "BARANGAY SANTA ANA"
- Captures: Barangay name (non-greedy match until comma or end)

#### Municipality/City Extraction
```python
r'(?:MUNICIPALITY OF|CITY OF|MUNICIPALITY|CITY)\s+([A-Z][A-Z\s]+?)(?:,|$)'
```
- Matches: "CITY OF MANILA", "MUNICIPALITY OF PIKIT"
- Falls back to second-to-last comma part if no explicit pattern

#### Province Extraction
```python
r'([A-Z][A-Z\s]+?)\s+(?:PROVINCE|PROV)'
```
- Matches: "NORTH COTABATO PROVINCE"
- Also checks last comma part for common province names

#### DEO Suffix Removal
```python
r'\s+\d+(st|nd|rd|th)\s+DEO.*$'
r'\s*\([^)]*DEO[^)]*\)'
```
- Removes: "1st DEO", "2nd DEO", "(Cotabato 1st DEO)"

### Search Query Construction

The search query is built in priority order:
1. Barangay (if available)
2. Municipality (if available)
3. Province (if available)
4. Region (if available)

Format: `"{barangay}, {municipality}, {province}, {region}"`

**Example**:
```python
# Input:
barangay = "Poblacion"
municipality = "Pikit"
province = "Cotabato"
region = "Soccsksargen"

# Query:
"Poblacion, Pikit, Cotabato, Soccsksargen"
```

### Hierarchy Building Algorithm

```python
def build_hierarchy(location):
    hierarchy = initialize_empty_hierarchy()
    current = location
    
    # Set current level
    set_current_level(hierarchy, current)
    
    # Trace parents
    while current has parent:
        parent = find_parent_by_psgc_id(current.parent_psgc_id)
        if not parent:
            break
        
        # Fill missing levels from parent
        fill_missing_levels(hierarchy, parent)
        current = parent
    
    return hierarchy
```

**Example Trace**:
```
Barangay "Poblacion" (PSGC: 1204712050)
  ↓ parent_psgc_id: 1204700000
Municipality "Pikit" (PSGC: 1204700000)
  ↓ parent_psgc_id: 1200000000
Province "Cotabato" (PSGC: 1200000000)
  ↓ parent_psgc_id: 1200000000 (root)
Region "Region XII" (PSGC: 1200000000)
```

## Testing

### Test Cases

1. **Standard Format**:
   - Input: `"CONCRETING OF STREET, BARANGAY POBLACION, PIKIT, NORTH COTABATO"`
   - Expected: Extract all location components, find PSGC, clean description

2. **Missing Components**:
   - Input: Description without "BARANGAY" keyword
   - Expected: Fall back to component description or location object

3. **Non-standard Format**:
   - Input: Road names with coordinates
   - Expected: May fail to extract, logged in misc_notes

4. **Multiple Matches**:
   - Input: Common barangay name like "Poblacion"
   - Expected: Use best match, log multiple matches

### Validation

After enrichment, validate:
- PSGC code format (10 digits)
- Hierarchy completeness (all levels present)
- Description cleaning (location removed)
- Notes accuracy (issues properly logged)

## Troubleshooting

### Common Issues

1. **Location Not Found**:
   - Check if description format is standard
   - Verify region/province names are correct
   - Try manual search in barangay package

2. **Low Confidence Matches**:
   - Review match score in misc_notes
   - Verify extracted location components
   - Consider manual correction

3. **Province/Region Mismatch**:
   - Check if DPWH uses different naming
   - Verify region normalization worked
   - May indicate data quality issue

4. **Description Not Cleaned**:
   - Check if location was extracted correctly
   - Verify location parts were identified
   - May need manual review

## References

- [Barangay Package](https://github.com/bendlikeabamboo/barangay/)
- [PSGC Official Website](https://psa.gov.ph/classification/psgc/)
- [DPWH Transparency Portal](https://transparency.dpwh.gov.ph/)

