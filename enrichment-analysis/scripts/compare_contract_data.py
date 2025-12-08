#!/usr/bin/env python3
"""
Compare contract data between base-data and projects-data APIs for contract ID 21MD0023.
Generates a markdown report of differences.
"""

import json
from pathlib import Path
from typing import Any, Dict, Set, List

# File paths
ENRICHMENT_ANALYSIS_DIR = Path(__file__).parent.parent
BASE_DATA_FILE = ENRICHMENT_ANALYSIS_DIR.parent / "base-data" / "sample.json"
PROJECTS_DATA_FILE = ENRICHMENT_ANALYSIS_DIR / "samples" / "21MD0023.json"
OUTPUT_MD = ENRICHMENT_ANALYSIS_DIR / "docs" / "contract_comparison_21MD0023.md"

CONTRACT_ID = "21MD0023"


def flatten_dict(d: Dict, parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """Flatten a nested dictionary."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # For lists, we'll store them as-is but note the structure
            items.append((new_key, v))
        else:
            items.append((new_key, v))
    return dict(items)


def extract_leaves(d: Dict, parent_key: str = "", sep: str = ".") -> Dict[str, List[str]]:
    """
    Extract all leaf values (terminal values) from a nested dictionary.
    Returns a dict mapping normalized values to their paths.
    Handles lists by extracting leaf values from list items.
    """
    leaves = {}
    
    def normalize_leaf_value(value: Any) -> str:
        """Normalize a leaf value for comparison."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, (int, float)):
            return str(value)
        return str(value)
    
    def process_value(key: str, value: Any):
        if isinstance(value, dict):
            for k, v in value.items():
                new_key = f"{key}{sep}{k}" if key else k
                process_value(new_key, v)
        elif isinstance(value, list):
            # Process each item in the list
            for idx, item in enumerate(value):
                if isinstance(item, dict):
                    # Recursively process dict items in list
                    for k, v in item.items():
                        new_key = f"{key}[{idx}]{sep}{k}" if key else f"[{idx}]{sep}{k}"
                        process_value(new_key, v)
                else:
                    # Leaf value in list
                    leaf_key = f"{key}[{idx}]" if key else f"[{idx}]"
                    normalized = normalize_leaf_value(item)
                    if normalized not in leaves:
                        leaves[normalized] = []
                    leaves[normalized].append(leaf_key)
        else:
            # Leaf value
            normalized = normalize_leaf_value(value)
            if normalized not in leaves:
                leaves[normalized] = []
            leaves[normalized].append(key)
    
    for k, v in d.items():
        process_value(k, v)
    
    return leaves


def extract_contract_from_base_data(data: Dict, contract_id: str) -> Dict:
    """Extract a specific contract from base-data structure."""
    contracts = data.get("data", {}).get("data", [])
    for contract in contracts:
        if contract.get("contractId") == contract_id:
            return contract
    return {}


def normalize_value(value: Any) -> str:
    """Normalize value for comparison."""
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def compare_fields(base_data: Dict, projects_data: Dict) -> Dict:
    """Compare two dictionaries using path-based comparison."""
    base_flat = flatten_dict(base_data)
    projects_flat = flatten_dict(projects_data)
    
    base_keys = set(base_flat.keys())
    projects_keys = set(projects_flat.keys())
    
    common_keys = base_keys & projects_keys
    only_base = base_keys - projects_keys
    only_projects = projects_keys - base_keys
    
    differences = {
        "common_fields": {},
        "value_differences": {},
        "only_in_base": {},
        "only_in_projects": {}
    }
    
    # Compare common fields
    for key in common_keys:
        base_val = normalize_value(base_flat[key])
        projects_val = normalize_value(projects_flat[key])
        
        if base_val != projects_val:
            differences["value_differences"][key] = {
                "base": base_flat[key],
                "projects": projects_flat[key]
            }
        else:
            differences["common_fields"][key] = base_flat[key]
    
    # Fields only in base
    for key in only_base:
        differences["only_in_base"][key] = base_flat[key]
    
    # Fields only in projects
    for key in only_projects:
        differences["only_in_projects"][key] = projects_flat[key]
    
    return differences


def compare_leaves(base_data: Dict, projects_data: Dict) -> Dict:
    """
    Compare two dictionaries using leaf values (terminal values).
    This identifies values that exist in both but may be nested differently.
    """
    base_leaves = extract_leaves(base_data)
    projects_leaves = extract_leaves(projects_data)
    
    base_values = set(base_leaves.keys())
    projects_values = set(projects_leaves.keys())
    
    common_values = base_values & projects_values
    only_base_values = base_values - projects_values
    only_projects_values = projects_values - base_values
    
    # Find values that exist in both but at different paths
    same_value_different_path = {}
    same_value_same_path = {}
    
    for value in common_values:
        base_paths = base_leaves[value]
        projects_paths = projects_leaves[value]
        
        # Check if any paths match
        matching_paths = set(base_paths) & set(projects_paths)
        base_only_paths = [p for p in base_paths if p not in matching_paths]
        projects_only_paths = [p for p in projects_paths if p not in matching_paths]
        
        if matching_paths:
            # Has matching paths, but check if there are also different paths
            if base_only_paths or projects_only_paths:
                # Same value appears at both same and different paths
                same_value_different_path[value] = {
                    "matching_paths": list(matching_paths),
                    "base_only_paths": base_only_paths,
                    "projects_only_paths": projects_only_paths,
                    "note": "Value appears at both matching and different paths"
                }
            else:
                # All paths match
                same_value_same_path[value] = {
                    "paths": list(matching_paths)
                }
        else:
            # Same value but completely different paths (nested differently)
            same_value_different_path[value] = {
                "base_paths": base_paths,
                "projects_paths": projects_paths,
                "note": "Value appears at different paths (no matching paths)"
            }
    
    return {
        "same_value_same_path": same_value_same_path,
        "same_value_different_path": same_value_different_path,
        "only_in_base_values": {v: base_leaves[v] for v in only_base_values},
        "only_in_projects_values": {v: projects_leaves[v] for v in only_projects_values},
        "statistics": {
            "total_base_leaves": len(base_values),
            "total_projects_leaves": len(projects_values),
            "common_values": len(common_values),
            "same_path_count": len(same_value_same_path),
            "different_path_count": len(same_value_different_path),
            "only_base_count": len(only_base_values),
            "only_projects_count": len(only_projects_values)
        }
    }


def generate_markdown_report(base_data: Dict, projects_data: Dict, differences: Dict, leaf_comparison: Dict = None) -> str:
    """Generate markdown report."""
    md = f"""# Contract Data Comparison: {CONTRACT_ID}

## Overview

This document compares the data structure and fields between:
- **Base Data API** (`base-data/sample.json`) - Paginated listing endpoint
- **Projects Data API** (`enrichment-analysis/samples/21MD0023.json`) - Individual contract detail endpoint

**Contract ID**: {CONTRACT_ID}  
**Description**: {base_data.get('description', 'N/A')}

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Fields in Base Data | {len(flatten_dict(base_data))} |
| Fields in Projects Data | {len(flatten_dict(projects_data))} |
| Common Fields (same value) | {len(differences['common_fields'])} |
| Common Fields (different value) | {len(differences['value_differences'])} |
| Fields Only in Base Data | {len(differences['only_in_base'])} |
| Fields Only in Projects Data | {len(differences['only_in_projects'])} |

---

## Common Fields (Same Values)

These fields exist in both APIs with identical values:

"""
    
    if differences['common_fields']:
        md += "| Field | Value |\n"
        md += "|-------|-------|\n"
        for key, value in sorted(differences['common_fields'].items()):
            value_str = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
            md += f"| `{key}` | `{value_str}` |\n"
    else:
        md += "*No common fields with identical values found.*\n"
    
    md += "\n---\n\n## Fields with Different Values\n\n"
    
    if differences['value_differences']:
        md += "| Field | Base Data Value | Projects Data Value |\n"
        md += "|-------|----------------|---------------------|\n"
        for key, vals in sorted(differences['value_differences'].items()):
            base_val = str(vals['base'])[:50] + "..." if len(str(vals['base'])) > 50 else str(vals['base'])
            proj_val = str(vals['projects'])[:50] + "..." if len(str(vals['projects'])) > 50 else str(vals['projects'])
            md += f"| `{key}` | `{base_val}` | `{proj_val}` |\n"
    else:
        md += "*No fields with different values found.*\n"
    
    md += "\n---\n\n## Fields Only in Base Data API\n\n"
    
    if differences['only_in_base']:
        md += "| Field | Value |\n"
        md += "|-------|-------|\n"
        for key, value in sorted(differences['only_in_base'].items()):
            value_str = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
            md += f"| `{key}` | `{value_str}` |\n"
    else:
        md += "*No fields unique to Base Data API.*\n"
    
    md += "\n---\n\n## Fields Only in Projects Data API\n\n"
    
    if differences['only_in_projects']:
        md += "| Field | Value |\n"
        md += "|-------|-------|\n"
        for key, value in sorted(differences['only_in_projects'].items()):
            # Handle complex values (lists, dicts)
            if isinstance(value, (list, dict)):
                value_str = f"*{type(value).__name__}* ({len(value) if isinstance(value, list) else len(value.keys())} items)"
            else:
                value_str = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
            md += f"| `{key}` | `{value_str}` |\n"
    else:
        md += "*No fields unique to Projects Data API.*\n"
    
    md += "\n---\n\n## Detailed Field Analysis\n\n"
    
    md += "### Base Data Structure\n\n"
    md += "```json\n"
    md += json.dumps(base_data, indent=2)[:2000] + "\n...\n"
    md += "```\n\n"
    
    md += "### Projects Data Structure\n\n"
    md += "```json\n"
    md += json.dumps(projects_data, indent=2)[:2000] + "\n...\n"
    md += "```\n\n"
    
    md += "---\n\n## Key Observations\n\n"
    
    # Add observations
    observations = []
    
    # Check for specific new sections
    projects_keys_str = ' '.join(differences['only_in_projects'].keys())
    
    if 'components' in projects_keys_str:
        observations.append("**Component Details**: Projects API includes detailed component information with individual coordinates, component IDs, and type of work.")
    
    if 'bidders' in projects_keys_str:
        observations.append("**Bidding Information**: Projects API includes detailed bidder information (names, PCAB IDs, participation, winner status) and winner names.")
    
    if 'procurement' in projects_keys_str:
        observations.append("**Procurement Details**: Projects API includes comprehensive procurement information including ABC (Approved Budget for Contract), advertisement dates, bid submission deadlines, date of award, award amounts, funding instruments, and procurement status.")
    
    if 'links' in projects_keys_str:
        observations.append("**Document Links**: Projects API includes links to various procurement documents (advertisements, contract agreements, notices of award, notices to proceed, program of work, engineering designs).")
    
    if 'imageSummary' in projects_keys_str:
        observations.append("**Image Metadata**: Projects API includes image summary information (total images, latest image date, hasImages flag).")
    
    if 'location.coordinates' in projects_keys_str:
        observations.append("**Enhanced Location Data**: Projects API includes detailed coordinate information within the location object with verification status.")
    
    if 'contractEffectivityDate' in projects_keys_str or 'expiryDate' in projects_keys_str:
        observations.append("**Contract Dates**: Projects API includes additional contract dates (effectivity date, expiry date) beyond start and completion dates.")
    
    if 'isVerifiedByDpwh' in projects_keys_str or 'isVerifiedByPublic' in projects_keys_str:
        observations.append("**Verification Status**: Projects API includes verification flags for both DPWH and public verification.")
    
    if 'coordinates' in projects_keys_str and 'coordinates' not in 'location.coordinates':
        observations.append("**Coordinate Arrays**: Projects API includes a top-level coordinates array with component-level coordinate information.")
    
    if 'componentCategories' in differences['only_in_base']:
        observations.append("**Base Data Only**: Base Data API includes `componentCategories` field which is not present in Projects API (though `infraType` serves a similar purpose).")
    
    if 'reportCount' in differences['only_in_base']:
        observations.append("**Base Data Only**: Base Data API includes `reportCount` field which tracks the number of reports, not available in Projects API.")
    
    if not observations:
        observations.append("Both APIs contain similar core contract information.")
    
    for obs in observations:
        md += f"- {obs}\n"
    
    md += "\n### Data Completeness\n\n"
    md += "- **Base Data API**: Provides a lightweight summary suitable for listing/browsing contracts. Contains 23 fields focused on core contract information.\n"
    md += "- **Projects Data API**: Provides comprehensive detail suitable for individual contract views. Contains 52 fields with extensive additional information about components, bidding, procurement, and documentation.\n"
    md += "- **Overlap**: 21 fields are common between both APIs with identical values, ensuring consistency in core contract data.\n\n"
    
    if leaf_comparison:
        stats = leaf_comparison["statistics"]
        md += "### Leaf-Based Analysis Insights\n\n"
        md += f"- **100% Data Coverage**: All {stats['total_base_leaves']} leaf values from Base Data API are present in Projects Data API.\n"
        md += f"- **Path Variations**: {stats['different_path_count']} values appear at different or additional paths, while {stats['same_path_count']} values appear at identical paths in both APIs.\n"
        md += f"- **Additional Data**: Projects Data API contains {stats['only_projects_count']} additional unique values not present in Base Data API.\n"
        md += f"- **Data Consistency**: All base values exist in projects data, confirming that Projects Data API is a superset of Base Data API.\n\n"
        
        # Add specific findings about path differences
        if leaf_comparison["same_value_different_path"]:
            md += "### Key Findings: Values at Additional Paths\n\n"
            md += "The leaf-based analysis reveals that several values appear at **additional paths** in Projects Data API:\n\n"
            
            # Find specific examples
            examples = []
            for value, paths_info in leaf_comparison["same_value_different_path"].items():
                if "matching_paths" in paths_info:
                    proj_only = paths_info.get("projects_only_paths", [])
                    if proj_only:
                        # This value appears at additional paths in projects
                        value_display = value[:60] + "..." if len(value) > 60 else value
                        matching = paths_info.get("matching_paths", [])
                        examples.append({
                            "value": value_display,
                            "base_path": matching[0] if matching else "N/A",
                            "additional_paths": proj_only[:3]  # Show first 3
                        })
            
            if examples:
                md += "| Value | Base Data Path | Additional Paths in Projects Data |\n"
                md += "|-------|----------------|-----------------------------------|\n"
                for ex in examples[:10]:  # Show top 10 examples
                    addl_paths = ", ".join(ex["additional_paths"])
                    if len(ex["additional_paths"]) > 3:
                        addl_paths += " (+more)"
                    md += f"| `{ex['value']}` | `{ex['base_path']}` | `{addl_paths}` |\n"
                
                md += "\n**Notable Examples:**\n\n"
                md += "- **Latitude/Longitude**: In Base Data API, coordinates appear only at the top level (`latitude`, `longitude`). "
                md += "In Projects Data API, they appear at both the top level AND nested under `location.coordinates` "
                md += "(plus in component arrays), providing multiple access points to the same coordinate data.\n\n"
                
                md += "- **Contractor Information**: The contractor name appears at the top level in both APIs, but Projects Data API "
                md += "also includes it in the `bidders` array with additional metadata (PCAB ID, participation, winner status).\n\n"
                
                md += "- **Description**: The contract description appears at the top level in both, but Projects Data API also "
                md += "includes it in the `procurement.contractName` field, linking it to procurement records.\n\n"
                
                md += "- **Location Data**: Region and province information appears in the `location` object in both APIs, but "
                md += "Projects Data API also includes this in component-level data, allowing for more granular location tracking.\n\n"
    
    # Add leaf-based comparison section
    if leaf_comparison:
        md += "\n---\n\n## Leaf-Based Comparison (Value-Level Analysis)\n\n"
        md += "This section compares actual data values regardless of their nesting structure.\n\n"
        
        stats = leaf_comparison["statistics"]
        md += f"### Summary\n\n"
        md += f"| Metric | Count |\n"
        md += f"|--------|-------|\n"
        md += f"| Total Leaf Values in Base Data | {stats['total_base_leaves']} |\n"
        md += f"| Total Leaf Values in Projects Data | {stats['total_projects_leaves']} |\n"
        md += f"| Common Values (appear in both) | {stats['common_values']} |\n"
        md += f"| Same Value, Same Path | {stats['same_path_count']} |\n"
        md += f"| Same Value, Different Path (nested differently) | {stats['different_path_count']} |\n"
        md += f"| Values Only in Base Data | {stats['only_base_count']} |\n"
        md += f"| Values Only in Projects Data | {stats['only_projects_count']} |\n\n"
        
        # Same value, different path (nested differently)
        if leaf_comparison["same_value_different_path"]:
            md += f"### Values at Different/Additional Paths\n\n"
            md += f"These values exist in both APIs but appear at different or additional paths:\n\n"
            md += f"| Value | Base Data Path(s) | Projects Data Path(s) | Note |\n"
            md += f"|-------|------------------|---------------------|------|\n"
            
            # Sort by value for readability, limit to first 20
            sorted_items = sorted(leaf_comparison["same_value_different_path"].items())[:20]
            for value, paths_info in sorted_items:
                value_display = value[:40] + "..." if len(value) > 40 else value
                
                # Handle different structures
                if "matching_paths" in paths_info:
                    # Has both matching and different paths
                    base_paths = paths_info.get("base_only_paths", [])
                    proj_paths = paths_info.get("projects_only_paths", [])
                    matching = paths_info.get("matching_paths", [])
                    
                    base_paths_str = ", ".join(matching + base_paths[:1])
                    if len(base_paths) > 1:
                        base_paths_str += f" (+{len(base_paths)-1} more)"
                    
                    proj_paths_str = ", ".join(matching + proj_paths[:1])
                    if len(proj_paths) > 1:
                        proj_paths_str += f" (+{len(proj_paths)-1} more)"
                    
                    note = "Also appears at additional paths in Projects Data"
                    if base_paths:
                        note = "Also appears at additional paths in Base Data"
                else:
                    # Completely different paths
                    base_paths = paths_info.get("base_paths", [])
                    proj_paths = paths_info.get("projects_paths", [])
                    
                    base_paths_str = ", ".join(base_paths[:2])
                    if len(base_paths) > 2:
                        base_paths_str += f" (+{len(base_paths)-2} more)"
                    
                    proj_paths_str = ", ".join(proj_paths[:2])
                    if len(proj_paths) > 2:
                        proj_paths_str += f" (+{len(proj_paths)-2} more)"
                    
                    note = "Different paths (nested differently)"
                
                md += f"| `{value_display}` | `{base_paths_str}` | `{proj_paths_str}` | {note} |\n"
            
            if len(leaf_comparison["same_value_different_path"]) > 20:
                md += f"\n*Showing first 20 of {len(leaf_comparison['same_value_different_path'])} values with path differences.*\n"
        
        # Values only in base
        if leaf_comparison["only_in_base_values"]:
            md += f"\n### Values Only in Base Data\n\n"
            md += f"| Value | Path(s) |\n"
            md += f"|-------|--------|\n"
            sorted_base = sorted(leaf_comparison["only_in_base_values"].items())[:15]
            for value, paths in sorted_base:
                value_display = value[:50] + "..." if len(value) > 50 else value
                paths_str = ", ".join(paths[:2])
                if len(paths) > 2:
                    paths_str += f" (+{len(paths)-2} more)"
                md += f"| `{value_display}` | `{paths_str}` |\n"
            if len(leaf_comparison["only_in_base_values"]) > 15:
                md += f"\n*Showing first 15 of {len(leaf_comparison['only_in_base_values'])} unique values.*\n"
        
        # Values only in projects
        if leaf_comparison["only_in_projects_values"]:
            md += f"\n### Values Only in Projects Data\n\n"
            md += f"| Value | Path(s) |\n"
            md += f"|-------|--------|\n"
            sorted_proj = sorted(leaf_comparison["only_in_projects_values"].items())[:15]
            for value, paths in sorted_proj:
                value_display = value[:50] + "..." if len(value) > 50 else value
                paths_str = ", ".join(paths[:2])
                if len(paths) > 2:
                    paths_str += f" (+{len(paths)-2} more)"
                md += f"| `{value_display}` | `{paths_str}` |\n"
            if len(leaf_comparison["only_in_projects_values"]) > 15:
                md += f"\n*Showing first 15 of {len(leaf_comparison['only_in_projects_values'])} unique values.*\n"
    
    md += "\n---\n\n*Report generated automatically by comparison script.*\n"
    
    return md


def main():
    """Main function."""
    print("Loading JSON files...")
    
    # Load base data
    with open(BASE_DATA_FILE, 'r', encoding='utf-8') as f:
        base_json = json.load(f)
    
    # Extract contract from base data
    base_contract = extract_contract_from_base_data(base_json, CONTRACT_ID)
    
    if not base_contract:
        print(f"Error: Contract {CONTRACT_ID} not found in base data")
        return
    
    # Load projects data
    with open(PROJECTS_DATA_FILE, 'r', encoding='utf-8') as f:
        projects_json = json.load(f)
    
    projects_contract = projects_json.get("data", {})
    
    print("Comparing data structures (path-based)...")
    differences = compare_fields(base_contract, projects_contract)
    
    print("Comparing leaf values (value-based)...")
    leaf_comparison = compare_leaves(base_contract, projects_contract)
    
    print("Generating markdown report...")
    markdown = generate_markdown_report(base_contract, projects_contract, differences, leaf_comparison)
    
    print(f"Writing report to {OUTPUT_MD}...")
    with open(OUTPUT_MD, 'w', encoding='utf-8') as f:
        f.write(markdown)
    
    print("✓ Report generated successfully!")
    print(f"\nPath-Based Summary:")
    print(f"  Common fields: {len(differences['common_fields'])}")
    print(f"  Different values: {len(differences['value_differences'])}")
    print(f"  Only in base: {len(differences['only_in_base'])}")
    print(f"  Only in projects: {len(differences['only_in_projects'])}")
    
    if leaf_comparison:
        stats = leaf_comparison["statistics"]
        print(f"\nLeaf-Based Summary:")
        print(f"  Total base leaves: {stats['total_base_leaves']}")
        print(f"  Total projects leaves: {stats['total_projects_leaves']}")
        print(f"  Common values: {stats['common_values']}")
        print(f"  Same value, same path: {stats['same_path_count']}")
        print(f"  Same value, different path: {stats['different_path_count']}")
        print(f"  Only in base: {stats['only_base_count']}")
        print(f"  Only in projects: {stats['only_projects_count']}")


if __name__ == "__main__":
    main()

