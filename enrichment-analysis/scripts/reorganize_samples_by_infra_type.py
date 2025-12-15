#!/usr/bin/env python3
"""
Reorganize samples by infrastructure type, then by type of work.
Structure: samples/InfraType/TypeOfWork/contractId.json
"""

import json
import shutil
from pathlib import Path
from collections import defaultdict

# Paths
ENRICHMENT_ANALYSIS_DIR = Path(__file__).parent.parent
SAMPLES_DIR = ENRICHMENT_ANALYSIS_DIR / "samples"


def get_infra_type_mapping():
    """Analyze samples to determine which infraType each typeOfWork belongs to."""
    print("Analyzing typeOfWork to infraType mapping...")
    
    type_of_work_to_infra_type = defaultdict(set)
    
    # Scan all sample directories
    for tow_dir in SAMPLES_DIR.iterdir():
        if not tow_dir.is_dir():
            continue
        
        # Read a sample file from this directory to get infraType
        json_files = list(tow_dir.glob("*.json"))
        if not json_files:
            continue
        
        # Read first file to determine infraType
        try:
            with open(json_files[0], 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if "data" in data:
                contract_data = data["data"]
                infra_type = contract_data.get("infraType")
                
                if infra_type:
                    # Get the typeOfWork from the directory name or from components
                    tow_dir_name = tow_dir.name
                    
                    # Also check components to get actual typeOfWork
                    if "components" in contract_data and contract_data["components"]:
                        for component in contract_data["components"]:
                            if "typeOfWork" in component:
                                tow = component["typeOfWork"]
                                type_of_work_to_infra_type[tow].add(infra_type)
                else:
                    print(f"  Warning: No infraType found in {tow_dir.name}")
        except Exception as e:
            print(f"  Error reading {tow_dir.name}: {e}")
    
    return type_of_work_to_infra_type


def reorganize_samples():
    """Reorganize samples by infraType, then by typeOfWork."""
    print("="*70)
    print("Reorganizing Samples by Infrastructure Type")
    print("="*70)
    print()
    
    if not SAMPLES_DIR.exists():
        print(f"Error: Samples directory not found: {SAMPLES_DIR}")
        return
    
    # Get mapping of typeOfWork to infraType
    type_of_work_to_infra_type = get_infra_type_mapping()
    
    print(f"\nFound {len(type_of_work_to_infra_type)} typeOfWork types")
    print()
    
    # Create a backup/old structure
    old_samples_dir = SAMPLES_DIR.parent / "samples_old_structure"
    
    # Reorganize
    moved_count = 0
    skipped_count = 0
    
    for tow_dir in sorted(SAMPLES_DIR.iterdir()):
        if not tow_dir.is_dir():
            continue
        
        tow_dir_name = tow_dir.name
        
        # Find the infraType(s) for this typeOfWork
        # Try to match by directory name first
        infra_types = type_of_work_to_infra_type.get(tow_dir_name, set())
        
        # If not found, try to read a sample to determine
        if not infra_types:
            json_files = list(tow_dir.glob("*.json"))
            if json_files:
                try:
                    with open(json_files[0], 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if "data" in data:
                        infra_type = data["data"].get("infraType")
                        if infra_type:
                            infra_types.add(infra_type)
                except Exception:
                    pass
        
        if not infra_types:
            print(f"  ⚠ Skipping {tow_dir_name}: No infraType found")
            skipped_count += 1
            continue
        
        # For each infraType, move the directory
        for infra_type in infra_types:
            # Clean infraType name for directory
            safe_infra_type = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in infra_type)
            safe_infra_type = safe_infra_type.replace(' ', '_').replace('/', '_').replace('\\', '_')
            
            # Create infraType directory
            infra_type_dir = SAMPLES_DIR / safe_infra_type
            infra_type_dir.mkdir(exist_ok=True)
            
            # Destination for this typeOfWork
            dest_dir = infra_type_dir / tow_dir_name
            
            # If multiple infraTypes, we need to handle this carefully
            if len(infra_types) > 1:
                # Create a subdirectory with infraType suffix
                dest_dir = infra_type_dir / f"{tow_dir_name}_{safe_infra_type}"
            
            # Move the directory
            if dest_dir.exists():
                print(f"  ⚠ {tow_dir_name} -> {safe_infra_type}/{dest_dir.name}: Already exists, skipping")
                skipped_count += 1
            else:
                try:
                    shutil.move(str(tow_dir), str(dest_dir))
                    print(f"  ✓ {tow_dir_name} -> {safe_infra_type}/{dest_dir.name}")
                    moved_count += 1
                    break  # Only move once if multiple infraTypes
                except Exception as e:
                    print(f"  ✗ Error moving {tow_dir_name}: {e}")
                    skipped_count += 1
    
    print()
    print("="*70)
    print(f"Summary:")
    print(f"  Moved: {moved_count} directories")
    print(f"  Skipped: {skipped_count} directories")
    print(f"  New structure: samples/InfraType/TypeOfWork/")
    print("="*70)


if __name__ == "__main__":
    reorganize_samples()

