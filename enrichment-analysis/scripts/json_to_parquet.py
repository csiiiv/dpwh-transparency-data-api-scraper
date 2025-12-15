#!/usr/bin/env python3
"""
Convert enriched DPWH JSON files to Parquet format.
Handles nested objects using multiple strategies:
1. Flatten nested structures (location.region -> location_region)
2. Convert nested objects to JSON strings
3. Use Parquet STRUCT types for complex nested objects
"""

import json
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd


def flatten_dict(d: Dict, parent_key: str = "", sep: str = "_") -> Dict:
    """
    Flatten a nested dictionary.
    Example: {"location": {"region": "XII"}} -> {"location_region": "XII"}
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # For lists, convert to JSON string or handle specially
            items.append((new_key, json.dumps(v) if v else None))
        else:
            items.append((new_key, v))
    return dict(items)


def extract_contract_data(project_data: Dict) -> Dict:
    """Extract and flatten contract data from project JSON."""
    if "data" not in project_data:
        return {}
    
    data = project_data["data"]
    
    # Start with top-level fields
    flat_data = {}
    
    # Simple fields (non-nested, non-list)
    simple_fields = [
        "contractId", "description", "category", "status", "budget",
        "amountPaid", "progress", "contractor", "startDate", "completionDate",
        "infraYear", "programName", "sourceOfFunds", "isLive",
        "livestreamUrl", "livestreamVideoId", "livestreamDetectedAt",
        "latitude", "longitude", "infraType", "contractEffectivityDate",
        "expiryDate", "nysReason", "isVerifiedByDpwh", "isVerifiedByPublic",
        "winnerNames"
    ]
    
    for field in simple_fields:
        if field in data:
            flat_data[field] = data[field]
    
    # Flatten location object
    if "location" in data:
        location = data["location"]
        flat_data["location_region"] = location.get("region")
        flat_data["location_province"] = location.get("province")
        flat_data["location_infraType"] = location.get("infraType")
        
        if "coordinates" in location:
            coords = location["coordinates"]
            flat_data["location_coordinates_latitude"] = coords.get("latitude")
            flat_data["location_coordinates_longitude"] = coords.get("longitude")
            flat_data["location_coordinates_verified"] = coords.get("verified")
    
    # Flatten PSGC data
    if "psgc" in data:
        psgc = data["psgc"]
        flat_data["psgc_barangay_name"] = psgc.get("barangay_name")
        flat_data["psgc_municipality_name"] = psgc.get("municipality_name")
        flat_data["psgc_province_name"] = psgc.get("province_name")
        flat_data["psgc_region_name"] = psgc.get("region_name")
        flat_data["psgc_code"] = psgc.get("psgc_code")
        flat_data["psgc_location_type"] = psgc.get("location_type")
    
    # Handle nested objects as JSON strings
    nested_objects = ["procurement", "links", "imageSummary"]
    for obj_key in nested_objects:
        if obj_key in data:
            flat_data[f"{obj_key}_json"] = json.dumps(data[obj_key]) if data[obj_key] else None
    
    # Handle arrays - convert to JSON strings or extract summary info
    if "components" in data and data["components"]:
        # Store as JSON string
        flat_data["components_json"] = json.dumps(data["components"])
        # Also extract first component summary
        first_comp = data["components"][0]
        flat_data["component_id"] = first_comp.get("componentId")
        flat_data["component_description"] = first_comp.get("description")
        flat_data["component_typeOfWork"] = first_comp.get("typeOfWork")
        flat_data["component_region"] = first_comp.get("region")
        flat_data["component_province"] = first_comp.get("province")
        flat_data["components_count"] = len(data["components"])
    else:
        flat_data["components_json"] = None
        flat_data["components_count"] = 0
    
    if "bidders" in data and data["bidders"]:
        flat_data["bidders_json"] = json.dumps(data["bidders"])
        flat_data["bidders_count"] = len(data["bidders"])
        # Extract winner info
        winner = next((b for b in data["bidders"] if b.get("isWinner")), None)
        if winner:
            flat_data["winner_name"] = winner.get("name")
            flat_data["winner_pcabId"] = winner.get("pcabId")
    else:
        flat_data["bidders_json"] = None
        flat_data["bidders_count"] = 0
    
    if "coordinates" in data and data["coordinates"]:
        flat_data["coordinates_json"] = json.dumps(data["coordinates"])
        flat_data["coordinates_count"] = len(data["coordinates"])
    else:
        flat_data["coordinates_json"] = None
        flat_data["coordinates_count"] = 0
    
    return flat_data


def convert_json_to_parquet_flat(input_dir: Path, output_file: Path):
    """
    Convert JSON files to Parquet using flattened structure.
    This is the simplest approach - all nested data is flattened or converted to JSON strings.
    """
    print("Converting JSON files to Parquet (flattened structure)...")
    
    json_files = list(input_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {input_dir}")
        return
    
    print(f"Found {len(json_files)} JSON files")
    
    all_records = []
    
    for json_file in sorted(json_files):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            flat_record = extract_contract_data(data)
            if flat_record:
                all_records.append(flat_record)
        except Exception as e:
            print(f"  Error processing {json_file.name}: {e}")
    
    if not all_records:
        print("No valid records found")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(all_records)
    
    # Write to Parquet
    table = pa.Table.from_pandas(df)
    pq.write_table(table, output_file)
    
    print(f"\n✓ Parquet file created: {output_file}")
    print(f"  Records: {len(all_records)}")
    print(f"  Columns: {len(df.columns)}")
    print(f"  File size: {output_file.stat().st_size / 1024:.2f} KB")


def convert_json_to_parquet_nested(input_dir: Path, output_file: Path):
    """
    Convert JSON files to Parquet using nested STRUCT types.
    This preserves the original structure better but is more complex.
    """
    print("Converting JSON files to Parquet (nested STRUCT types)...")
    
    json_files = list(input_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {input_dir}")
        return
    
    print(f"Found {len(json_files)} JSON files")
    
    # Define schema with nested structures
    schema = pa.schema([
        ("contractId", pa.string()),
        ("description", pa.string()),
        ("category", pa.string()),
        ("status", pa.string()),
        ("budget", pa.float64()),
        ("amountPaid", pa.float64()),
        ("progress", pa.int64()),
        ("contractor", pa.string()),
        ("startDate", pa.string()),
        ("completionDate", pa.string()),
        ("infraYear", pa.string()),
        ("programName", pa.string()),
        ("sourceOfFunds", pa.string()),
        ("isLive", pa.bool_()),
        ("latitude", pa.float64()),
        ("longitude", pa.float64()),
        # Nested location struct
        ("location", pa.struct([
            ("region", pa.string()),
            ("province", pa.string()),
            ("infraType", pa.string()),
            ("coordinates", pa.struct([
                ("latitude", pa.float64()),
                ("longitude", pa.float64()),
                ("verified", pa.bool_())
            ]))
        ])),
        # Nested PSGC struct
        ("psgc", pa.struct([
            ("barangay_name", pa.string()),
            ("municipality_name", pa.string()),
            ("province_name", pa.string()),
            ("region_name", pa.string()),
            ("psgc_code", pa.string()),
            ("location_type", pa.string())
        ])),
        # Arrays stored as JSON strings (Parquet LIST of STRUCT is complex)
        ("components_json", pa.string()),
        ("bidders_json", pa.string()),
        ("procurement_json", pa.string()),
        ("links_json", pa.string()),
        ("coordinates_json", pa.string()),
        ("imageSummary_json", pa.string()),
    ])
    
    all_data = []
    
    for json_file in sorted(json_files):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            
            if "data" not in project_data:
                continue
            
            data = project_data["data"]
            
            # Build location struct
            location_data = data.get("location", {})
            coords_data = location_data.get("coordinates", {})
            location_struct = {
                "region": location_data.get("region"),
                "province": location_data.get("province"),
                "infraType": location_data.get("infraType"),
                "coordinates": {
                    "latitude": coords_data.get("latitude"),
                    "longitude": coords_data.get("longitude"),
                    "verified": coords_data.get("verified", False)
                }
            }
            
            # Build PSGC struct
            psgc_data = data.get("psgc", {})
            psgc_struct = {
                "barangay_name": psgc_data.get("barangay_name"),
                "municipality_name": psgc_data.get("municipality_name"),
                "province_name": psgc_data.get("province_name"),
                "region_name": psgc_data.get("region_name"),
                "psgc_code": psgc_data.get("psgc_code"),
                "location_type": psgc_data.get("location_type")
            }
            
            record = {
                "contractId": data.get("contractId"),
                "description": data.get("description"),
                "category": data.get("category"),
                "status": data.get("status"),
                "budget": data.get("budget"),
                "amountPaid": data.get("amountPaid"),
                "progress": data.get("progress"),
                "contractor": data.get("contractor"),
                "startDate": data.get("startDate"),
                "completionDate": data.get("completionDate"),
                "infraYear": data.get("infraYear"),
                "programName": data.get("programName"),
                "sourceOfFunds": data.get("sourceOfFunds"),
                "isLive": data.get("isLive", False),
                "latitude": data.get("latitude"),
                "longitude": data.get("longitude"),
                "location": location_struct,
                "psgc": psgc_struct,
                "components_json": json.dumps(data.get("components", [])) if data.get("components") else None,
                "bidders_json": json.dumps(data.get("bidders", [])) if data.get("bidders") else None,
                "procurement_json": json.dumps(data.get("procurement", {})) if data.get("procurement") else None,
                "links_json": json.dumps(data.get("links", {})) if data.get("links") else None,
                "coordinates_json": json.dumps(data.get("coordinates", [])) if data.get("coordinates") else None,
                "imageSummary_json": json.dumps(data.get("imageSummary", {})) if data.get("imageSummary") else None,
            }
            
            all_data.append(record)
        except Exception as e:
            print(f"  Error processing {json_file.name}: {e}")
    
    if not all_data:
        print("No valid records found")
        return
    
    # Create Arrow table
    table = pa.Table.from_pylist(all_data, schema=schema)
    
    # Write to Parquet
    pq.write_table(table, output_file)
    
    print(f"\n✓ Parquet file created: {output_file}")
    print(f"  Records: {len(all_data)}")
    print(f"  File size: {output_file.stat().st_size / 1024:.2f} KB")


def main():
    """Main function."""
    print("="*70)
    print("DPWH JSON to Parquet Converter")
    print("="*70)
    print()
    
    # Paths
    ENRICHMENT_ANALYSIS_DIR = Path(__file__).parent.parent
    enriched_dir = ENRICHMENT_ANALYSIS_DIR / "enriched"
    output_dir = ENRICHMENT_ANALYSIS_DIR / "parquet"
    output_dir.mkdir(exist_ok=True)
    
    if not enriched_dir.exists():
        print(f"Enriched directory not found: {enriched_dir}")
        print("Please run enrich_with_barangay.py first")
        return
    
    # Option 1: Flattened structure (recommended for most use cases)
    print("Strategy 1: Flattened Structure")
    print("-" * 70)
    flat_output = output_dir / "dpwh_projects_enriched_flat.parquet"
    convert_json_to_parquet_flat(enriched_dir, flat_output)
    
    print("\n" + "="*70)
    print()
    
    # Option 2: Nested STRUCT types
    print("Strategy 2: Nested STRUCT Types")
    print("-" * 70)
    nested_output = output_dir / "dpwh_projects_enriched_nested.parquet"
    convert_json_to_parquet_nested(enriched_dir, nested_output)
    
    print("\n" + "="*70)
    print("\nComparison:")
    print("  - Flattened: Easier to query, all columns at top level")
    print("  - Nested: Preserves structure, better for complex nested data")
    print("  - Both: Arrays stored as JSON strings (can be parsed when needed)")
    print("="*70)


if __name__ == "__main__":
    main()

