#!/usr/bin/env python3
"""
Extract sample contracts for each type of work.
Saves 10 samples per typeOfWork to the samples directory.
"""

import json
import tarfile
from pathlib import Path
from collections import defaultdict

# Paths
ENRICHMENT_ANALYSIS_DIR = Path(__file__).parent.parent
PROJECTS_DATA_DIR = ENRICHMENT_ANALYSIS_DIR.parent / "projects-data"
TAR_FILE = PROJECTS_DATA_DIR / "json" / "projects-json.tar"
SAMPLES_DIR = ENRICHMENT_ANALYSIS_DIR / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


def extract_samples():
    """Extract 10 sample contracts for each type of work."""
    print("="*70)
    print("Extracting Type of Work Samples")
    print("="*70)
    print()
    print(f"Reading from: {TAR_FILE}")
    print(f"Saving samples to: {SAMPLES_DIR}")
    print()
    
    if not TAR_FILE.exists():
        print(f"Error: Tar file not found: {TAR_FILE}")
        return
    
    # Track samples per type of work
    type_of_work_samples = defaultdict(list)
    processed = 0
    
    try:
        with tarfile.open(TAR_FILE, 'r') as tar:
            members = tar.getmembers()
            total_files = len([m for m in members if m.isfile()])
            print(f"Found {total_files} JSON files in archive")
            print()
            
            for member in members:
                if not member.isfile():
                    continue
                
                try:
                    # Extract and parse JSON
                    file_obj = tar.extractfile(member)
                    if file_obj is None:
                        continue
                    
                    content = file_obj.read().decode('utf-8')
                    data = json.loads(content)
                    
                    if "data" not in data:
                        continue
                    
                    contract_data = data["data"]
                    contract_id = contract_data.get("contractId", "Unknown")
                    
                    # Extract typeOfWork from components
                    if "components" in contract_data and contract_data["components"]:
                        for component in contract_data["components"]:
                            if "typeOfWork" in component:
                                tow = component["typeOfWork"]
                                if tow and len(type_of_work_samples[tow]) < 10:
                                    # Store the full contract data
                                    type_of_work_samples[tow].append({
                                        "contractId": contract_id,
                                        "data": contract_data
                                    })
                    
                    processed += 1
                    if processed % 10000 == 0:
                        total_samples = sum(len(samples) for samples in type_of_work_samples.values())
                        print(f"  Processed {processed}/{total_files} files... (collected {total_samples} samples)")
                
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    continue
        
        print(f"\n✓ Processing complete: {processed} files processed")
        print()
        
        # Save samples
        print("Saving samples...")
        total_saved = 0
        
        for tow, samples in sorted(type_of_work_samples.items()):
            # Clean typeOfWork name for filename (remove special chars)
            safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in tow)
            safe_name = safe_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
            safe_name = safe_name[:100]  # Limit length
            
            # Create directory for this type of work
            tow_dir = SAMPLES_DIR / safe_name
            tow_dir.mkdir(exist_ok=True)
            
            # Save each sample
            for i, sample in enumerate(samples, 1):
                contract_id = sample["contractId"]
                output_file = tow_dir / f"{contract_id}.json"
                
                # Create output structure matching original format
                output_data = {
                    "data": sample["data"]
                }
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False)
                
                total_saved += 1
            
            print(f"  ✓ {tow}: {len(samples)} samples saved to {tow_dir.name}/")
        
        print()
        print("="*70)
        print(f"Summary:")
        print(f"  Total typeOfWork types: {len(type_of_work_samples)}")
        print(f"  Total samples saved: {total_saved}")
        print(f"  Samples directory: {SAMPLES_DIR}")
        print("="*70)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    extract_samples()

