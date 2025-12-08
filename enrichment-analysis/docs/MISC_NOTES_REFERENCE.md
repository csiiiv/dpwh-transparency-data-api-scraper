# Misc Notes Reference - Parsing Issues Documentation

This document describes all possible issues that can be tracked in the `misc_notes` field when enriching DPWH project data with PSGC information.

## Field Location

The `misc_notes` field is added to each enriched JSON file at:
```json
{
  "data": {
    ...
    "misc_notes": [
      "ISSUE_CODE: Description of the issue"
    ]
  }
}
```

If no issues are detected, `misc_notes` will be `null`.

## Issue Categories

### 1. Missing Data Issues

#### `MISSING_REGION`
- **Description**: No region specified in the location object
- **Impact**: Low - region can sometimes be inferred from other data
- **Example**: `"MISSING_REGION: No region specified in location object"`

#### `MISSING_PROVINCE`
- **Description**: No province specified in the location object
- **Impact**: Medium - province is important for accurate location matching
- **Example**: `"MISSING_PROVINCE: No province specified in location object"`

#### `MISSING_DESCRIPTION`
- **Description**: No description field found in the project data
- **Impact**: High - description often contains location information
- **Example**: `"MISSING_DESCRIPTION: No description field found"`

#### `MISSING_COORDINATES`
- **Description**: No latitude/longitude found in the project data
- **Impact**: Low - coordinates are optional but useful for verification
- **Example**: `"MISSING_COORDINATES: No latitude/longitude found"`

#### `MISSING_COMPONENTS`
- **Description**: No components array found in the project data
- **Impact**: Low - components may contain additional location details
- **Example**: `"MISSING_COMPONENTS: No components array found"`

#### `MISSING_BIDDERS`
- **Description**: No bidders array found in the project data
- **Impact**: Low - bidders data is not critical for location enrichment
- **Example**: `"MISSING_BIDDERS: No bidders array found"`

### 2. Data Normalization Issues

#### `REGION_NORMALIZED`
- **Description**: Region name was normalized to match PSGC format
- **Impact**: Low - this is expected behavior
- **Example**: `"REGION_NORMALIZED: 'Region XII' -> 'Soccsksargen'"`

#### `REGION_NOT_FOUND`
- **Description**: Could not normalize the region name to a known PSGC region
- **Impact**: Medium - may affect location matching accuracy
- **Example**: `"REGION_NOT_FOUND: Could not normalize region 'Unknown Region'"`

#### `PROVINCE_CLEANED`
- **Description**: Province name had DEO (District Engineering Office) suffix removed
- **Impact**: Low - this is expected cleaning behavior
- **Example**: `"PROVINCE_CLEANED: Removed DEO suffix from 'Cotabato 1st DEO' -> 'Cotabato'"`

### 3. Parsing Issues

#### `DESCRIPTION_PARSE_FAILED`
- **Description**: Could not extract municipality/barangay from the description field
- **Impact**: Medium - may result in less accurate location matching
- **Example**: `"DESCRIPTION_PARSE_FAILED: Could not extract municipality/barangay from description"`

#### `EXTRACTED_BARANGAY`
- **Description**: Successfully extracted barangay name from description
- **Impact**: None - informational note
- **Example**: `"EXTRACTED_BARANGAY: 'Poblacion' from description"`

#### `EXTRACTED_MUNICIPALITY`
- **Description**: Successfully extracted municipality name from description
- **Impact**: None - informational note
- **Example**: `"EXTRACTED_MUNICIPALITY: 'Pikit' from description"`

#### `EXTRACTED_PROVINCE`
- **Description**: Successfully extracted province name from description
- **Impact**: None - informational note
- **Example**: `"EXTRACTED_PROVINCE: 'North Cotabato' from description"`

### 4. Search and Matching Issues

#### `INSUFFICIENT_SEARCH_DATA`
- **Description**: No location data available for search
- **Impact**: High - location cannot be found without search data
- **Example**: `"INSUFFICIENT_SEARCH_DATA: No location data available for search"`

#### `LOW_CONFIDENCE_MATCH`
- **Description**: Match found but with low confidence score (below 70%)
- **Impact**: Medium - match may be incorrect, manual review recommended
- **Example**: `"LOW_CONFIDENCE_MATCH: Match score 63.2% (threshold: 70%)"`

#### `MULTIPLE_MATCHES`
- **Description**: Found multiple potential matches, using the best match
- **Impact**: Low - best match is used, but other matches may be valid
- **Example**: `"MULTIPLE_MATCHES: Found 4 potential matches, using best match"`

#### `MULTIPLE_DIRECT_MATCHES`
- **Description**: Found multiple direct matches in BARANGAY_FLAT
- **Impact**: Medium - may indicate ambiguous location names
- **Example**: `"MULTIPLE_DIRECT_MATCHES: Found 3 direct matches for 'Poblacion'"`

#### `SEARCH_ERROR`
- **Description**: Fuzzy search encountered an error
- **Impact**: High - search failed, may need manual intervention
- **Example**: `"SEARCH_ERROR: Fuzzy search failed - Connection timeout"`

#### `NO_PSGC_ID`
- **Description**: Search result missing PSGC ID
- **Impact**: High - cannot build location hierarchy without PSGC ID
- **Example**: `"NO_PSGC_ID: Search result missing PSGC ID"`

#### `PSGC_NOT_FOUND`
- **Description**: PSGC ID from search result not found in BARANGAY_FLAT
- **Impact**: High - cannot build location hierarchy
- **Example**: `"PSGC_NOT_FOUND: PSGC ID 1204712050 not found in BARANGAY_FLAT"`

#### `DIRECT_LOOKUP_FAILED`
- **Description**: Direct lookup in BARANGAY_FLAT failed
- **Impact**: Medium - location not found via direct name matching
- **Example**: `"DIRECT_LOOKUP_FAILED: No direct match for 'Unknown Location'"`

#### `ALL_SEARCH_STRATEGIES_FAILED`
- **Description**: All search strategies (fuzzy search and direct lookup) failed
- **Impact**: High - location could not be found
- **Example**: `"ALL_SEARCH_STRATEGIES_FAILED: Could not find location using any method"`

#### `LOCATION_NOT_FOUND`
- **Description**: Could not find matching location in barangay database
- **Impact**: High - no PSGC data available for this project
- **Example**: `"LOCATION_NOT_FOUND: Could not find matching location in barangay database"`

#### `MATCH_FOUND`
- **Description**: Successfully found location via fuzzy search
- **Impact**: None - informational note
- **Example**: `"MATCH_FOUND: Found via fuzzy search (PSGC: 1204712050)"`

#### `DIRECT_MATCH_FOUND`
- **Description**: Successfully found location via direct lookup
- **Impact**: None - informational note
- **Example**: `"DIRECT_MATCH_FOUND: Found via direct lookup"`

### 5. Data Mismatch Issues

#### `PROVINCE_MISMATCH`
- **Description**: Province name in DPWH data doesn't match PSGC province name
- **Impact**: Medium - may indicate data quality issue or name variation
- **Example**: `"PROVINCE_MISMATCH: DPWH='Cotabato' vs PSGC='North Cotabato'"`

#### `REGION_MISMATCH`
- **Description**: Region name in DPWH data doesn't match PSGC region name
- **Impact**: High - indicates significant data discrepancy
- **Example**: `"REGION_MISMATCH: DPWH='Soccsksargen' vs PSGC='Bangsamoro Autonomous Region In Muslim Mindanao (BARMM)'"`

## Issue Severity Levels

### High Impact
- `MISSING_DESCRIPTION`
- `INSUFFICIENT_SEARCH_DATA`
- `SEARCH_ERROR`
- `NO_PSGC_ID`
- `PSGC_NOT_FOUND`
- `ALL_SEARCH_STRATEGIES_FAILED`
- `LOCATION_NOT_FOUND`
- `REGION_MISMATCH`

### Medium Impact
- `MISSING_PROVINCE`
- `REGION_NOT_FOUND`
- `DESCRIPTION_PARSE_FAILED`
- `LOW_CONFIDENCE_MATCH`
- `MULTIPLE_DIRECT_MATCHES`
- `DIRECT_LOOKUP_FAILED`
- `PROVINCE_MISMATCH`

### Low Impact
- `MISSING_REGION`
- `MISSING_COORDINATES`
- `MISSING_COMPONENTS`
- `MISSING_BIDDERS`
- `REGION_NORMALIZED`
- `PROVINCE_CLEANED`
- `MULTIPLE_MATCHES`

### Informational
- `EXTRACTED_BARANGAY`
- `EXTRACTED_MUNICIPALITY`
- `EXTRACTED_PROVINCE`
- `MATCH_FOUND`
- `DIRECT_MATCH_FOUND`

## Usage Examples

### Filtering by Issue Type
```python
import json
from pathlib import Path

enriched_dir = Path('projects-data/dpwh-projects-api/enriched')

# Find all files with high-impact issues
high_impact_issues = [
    'MISSING_DESCRIPTION',
    'LOCATION_NOT_FOUND',
    'REGION_MISMATCH',
    'ALL_SEARCH_STRATEGIES_FAILED'
]

for json_file in enriched_dir.glob('*.json'):
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    misc_notes = data.get('data', {}).get('misc_notes', [])
    if misc_notes:
        for note in misc_notes:
            issue_code = note.split(':')[0]
            if issue_code in high_impact_issues:
                print(f"{json_file.name}: {note}")
```

### Statistics
```python
# Count issue types
issue_counts = {}
for json_file in enriched_dir.glob('*.json'):
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    misc_notes = data.get('data', {}).get('misc_notes', [])
    if misc_notes:
        for note in misc_notes:
            issue_code = note.split(':')[0]
            issue_counts[issue_code] = issue_counts.get(issue_code, 0) + 1

# Print sorted by frequency
for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"{issue}: {count}")
```

## Notes

- All issue codes are prefixed with a category identifier (e.g., `MISSING_`, `REGION_`, `PROVINCE_`)
- Issues are logged in the order they are detected during processing
- Multiple issues can be present in a single record
- The absence of `misc_notes` or `null` value indicates no issues were detected

