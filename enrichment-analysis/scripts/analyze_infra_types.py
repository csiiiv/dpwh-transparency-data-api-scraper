#!/usr/bin/env python3
"""
Analyze infraType and typeOfWork from projects-data JSON files.
Processes files from tar archive without extracting them.
Includes PSGC enrichment analysis using barangay package.
"""

import json
import tarfile
import re
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Set, Optional, Tuple

# Try to import barangay package for enrichment
try:
    from barangay import search, BARANGAY_FLAT, BARANGAY_EXTENDED
    BARANGAY_AVAILABLE = True
except ImportError:
    BARANGAY_AVAILABLE = False
    print("Warning: barangay package not available. PSGC enrichment will be skipped.")


# Enrichment functions (from enrich_with_barangay.py)
def normalize_region_name(region: str) -> str:
    """Normalize region names to match PSGC format."""
    if not region or not BARANGAY_AVAILABLE:
        return region or ""
    
    region = region.strip()
    region_mapping = {
        "Region I": "Ilocos Region",
        "Region II": "Cagayan Valley",
        "Region III": "Central Luzon",
        "Region IV-A": "CALABARZON",
        "Region IV-B": "MIMAROPA Region",
        "Region V": "Bicol Region",
        "Region VI": "Western Visayas",
        "Region VII": "Central Visayas",
        "Region VIII": "Eastern Visayas",
        "Region IX": "Zamboanga Peninsula",
        "Region X": "Northern Mindanao",
        "Region XI": "Davao Region",
        "Region XII": "Soccsksargen",
        "Region XIII": "Caraga",
        "CAR": "Cordillera Administrative Region (CAR)",
        "NCR": "National Capital Region (NCR)",
        "BARMM": "Bangsamoro Autonomous Region in Muslim Mindanao (BARMM)",
    }
    
    if region in region_mapping:
        return region_mapping[region]
    
    for key, value in region_mapping.items():
        if key in region or region in key:
            return value
    
    return region


def extract_location_from_description(description: str) -> Dict[str, Optional[str]]:
    """Extract location information from project description."""
    if not description:
        return {}
    
    location_info = {}
    
    # Extract barangay
    brgy_match = re.search(r'BARANGAY\s+([A-Z][A-Z\s]+?)(?:,|$)', description, re.IGNORECASE)
    if brgy_match:
        location_info["barangay"] = brgy_match.group(1).strip()
    
    # Extract municipality/city
    mun_match = re.search(r'(?:MUNICIPALITY OF|CITY OF|MUNICIPALITY|CITY)\s+([A-Z][A-Z\s]+?)(?:,|$)', description, re.IGNORECASE)
    if mun_match:
        location_info["municipality"] = mun_match.group(1).strip()
    else:
        parts = description.split(',')
        if len(parts) >= 2:
            potential_mun = parts[-2].strip()
            if potential_mun and not any(word in potential_mun.upper() for word in ['PROVINCE', 'REGION', 'NORTH', 'SOUTH', 'EAST', 'WEST']):
                location_info["municipality"] = potential_mun
    
    # Extract province
    prov_match = re.search(r'([A-Z][A-Z\s]+?)\s+(?:PROVINCE|PROV)', description, re.IGNORECASE)
    if prov_match:
        location_info["province"] = prov_match.group(1).strip()
    else:
        parts = description.split(',')
        if len(parts) >= 1:
            last_part = parts[-1].strip()
            if any(word in last_part.upper() for word in ['COTABATO', 'MINDORO', 'LEYTE', 'CEBU', 'PALAWAN']):
                location_info["province"] = last_part
    
    return location_info


def build_location_hierarchy(location: Dict) -> Dict:
    """Build full location hierarchy from a location entry."""
    return build_location_hierarchy_fixed(location)


def find_location_in_barangay(
    region: Optional[str] = None,
    province: Optional[str] = None,
    municipality: Optional[str] = None,
    barangay: Optional[str] = None,
    description: Optional[str] = None
) -> Tuple[Optional[Dict], List[str]]:
    """Find location in barangay database using fuzzy search."""
    if not BARANGAY_AVAILABLE:
        return None, ["BARANGAY_PACKAGE_UNAVAILABLE"]
    
    notes = []
    search_parts = []
    
    if barangay:
        search_parts.append(barangay)
    if municipality:
        search_parts.append(municipality)
    if province:
        search_parts.append(province)
    if region:
        search_parts.append(region)
    
    if description and not any([barangay, municipality, province]):
        extracted = extract_location_from_description(description)
        if extracted.get("barangay"):
            search_parts.insert(0, extracted["barangay"])
        if extracted.get("municipality"):
            search_parts.insert(0, extracted["municipality"])
        if extracted.get("province"):
            search_parts.append(extracted["province"])
    
    if not search_parts:
        return None, ["INSUFFICIENT_SEARCH_DATA"]
    
    search_query = ", ".join(search_parts)
    
    # Strategy 1: Fuzzy search
    try:
        results = search(search_query, n=3, match_hooks=["barangay", "municipality", "province"], threshold=60.0)
        
        if results:
            best_match = results[0]
            psgc_id = best_match.get("psgc_id")
            if psgc_id:
                for loc in BARANGAY_FLAT:
                    if loc.get("psgc_id") == psgc_id:
                        return build_location_hierarchy(loc), ["MATCH_FOUND"]
    except Exception:
        pass
    
    # Strategy 2: Direct lookup
    if municipality or barangay:
        search_name = (barangay or municipality).upper()
        for loc in BARANGAY_FLAT:
            if loc["name"].upper() == search_name or search_name in loc["name"].upper():
                return build_location_hierarchy(loc), ["DIRECT_MATCH_FOUND"]
    
    return None, ["ALL_SEARCH_STRATEGIES_FAILED"]


def build_location_hierarchy_fixed(location: Dict) -> Dict:
    """Build full location hierarchy from a location entry (fixed version)."""
    if not BARANGAY_AVAILABLE:
        return {}
    
    hierarchy = {
        "barangay_name": None,
        "municipality_name": None,
        "province_name": None,
        "region_name": None,
        "psgc_code": location.get("psgc_id", ""),
        "location_type": location.get("type", "")
    }
    
    # Set the current level
    loc_type = location.get("type", "").lower()
    if loc_type == "barangay":
        hierarchy["barangay_name"] = location.get("name")
    elif loc_type == "municipality" or loc_type == "city":
        hierarchy["municipality_name"] = location.get("name")
    elif loc_type == "province":
        hierarchy["province_name"] = location.get("name")
    elif loc_type == "region":
        hierarchy["region_name"] = location.get("name")
    
    # Trace parent hierarchy using parent_psgc_id
    current = location
    max_depth = 10
    depth = 0
    
    while current and depth < max_depth:
        parent_id = current.get("parent_psgc_id")
        if not parent_id or parent_id == "0" * len(str(parent_id)):
            break
        
        # Find parent
        parent = None
        for loc in BARANGAY_FLAT:
            if loc.get("psgc_id") == parent_id:
                parent = loc
                break
        
        if not parent:
            break
        
        # Set hierarchy based on parent type
        parent_type = parent.get("type", "").lower()
        if parent_type == "barangay" and not hierarchy["barangay_name"]:
            hierarchy["barangay_name"] = parent.get("name")
        elif (parent_type == "municipality" or parent_type == "city") and not hierarchy["municipality_name"]:
            hierarchy["municipality_name"] = parent.get("name")
        elif parent_type == "province" and not hierarchy["province_name"]:
            hierarchy["province_name"] = parent.get("name")
        elif parent_type == "region" and not hierarchy["region_name"]:
            hierarchy["region_name"] = parent.get("name")
        
        current = parent
        depth += 1
    
    return hierarchy

# Paths
ENRICHMENT_ANALYSIS_DIR = Path(__file__).parent.parent
PROJECTS_DATA_DIR = ENRICHMENT_ANALYSIS_DIR.parent / "projects-data"
TAR_FILE = PROJECTS_DATA_DIR / "json" / "projects-json.tar"
OUTPUT_DIR = ENRICHMENT_ANALYSIS_DIR / "docs"
RESULTS_MD = OUTPUT_DIR / "infra_types_results.md"
ANALYSIS_MD = OUTPUT_DIR / "infra_types_analysis.md"


def analyze_tar_archive(tar_path: Path) -> Dict:
    """
    Analyze infraType and typeOfWork from all JSON files in tar archive.
    Returns statistics and data.
    """
    print("Analyzing projects-data JSON files from tar archive...")
    print(f"Reading: {tar_path}")
    if BARANGAY_AVAILABLE:
        print("PSGC enrichment: ENABLED (will enrich on-the-fly)")
    else:
        print("PSGC enrichment: DISABLED (barangay package not available)")
    
    infra_types = Counter()
    type_of_work = Counter()
    infra_type_work_combinations = defaultdict(Counter)
    contracts_with_infra_type = 0
    contracts_with_type_of_work = 0
    contracts_with_components = 0
    total_contracts = 0
    missing_infra_type = 0
    missing_type_of_work = 0
    
    # Location tracking
    regions = Counter()
    provinces = Counter()
    region_province_combinations = defaultdict(Counter)
    region_infra_combinations = defaultdict(Counter)
    region_year_combinations = defaultdict(Counter)
    province_year_combinations = defaultdict(Counter)
    missing_region = 0
    missing_province = 0
    
    # PSGC enrichment tracking
    psgc_barangays = Counter()
    psgc_municipalities = Counter()
    psgc_provinces_psgc = Counter()  # PSGC province names (may differ from DPWH)
    psgc_regions_psgc = Counter()  # PSGC region names (may differ from DPWH)
    psgc_location_types = Counter()  # barangay, municipality, province, etc.
    contracts_with_psgc = 0
    contracts_with_barangay = 0
    contracts_with_municipality = 0
    contracts_with_psgc_code = 0
    psgc_region_infra_combinations = defaultdict(Counter)
    psgc_region_year_combinations = defaultdict(Counter)
    
    # Yearly tracking
    years = Counter()
    year_infra_combinations = defaultdict(Counter)
    year_type_of_work_combinations = defaultdict(Counter)
    missing_year = 0
    
    # Track unique values
    unique_infra_types = set()
    unique_type_of_work = set()
    unique_regions = set()
    unique_provinces = set()
    unique_years = set()
    
    # Sample contracts for each type
    infra_type_samples = defaultdict(list)
    type_of_work_samples = defaultdict(list)
    region_samples = defaultdict(list)
    year_samples = defaultdict(list)
    
    try:
        with tarfile.open(tar_path, 'r') as tar:
            members = tar.getmembers()
            total_files = len([m for m in members if m.isfile()])
            print(f"Found {total_files} JSON files in archive")
            
            processed = 0
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
                    total_contracts += 1
                    
                    # Extract location data
                    location = contract_data.get("location", {})
                    region = location.get("region", "") if isinstance(location, dict) else ""
                    province = location.get("province", "") if isinstance(location, dict) else ""
                    
                    # Extract or enrich PSGC data
                    psgc_data = contract_data.get("psgc", {})
                    psgc_enriched = False
                    
                    # Check if PSGC data already exists
                    if isinstance(psgc_data, dict) and psgc_data and any(psgc_data.values()):
                        psgc_enriched = True
                    elif BARANGAY_AVAILABLE:
                        # Perform enrichment on-the-fly
                        description = contract_data.get("description", "")
                        normalized_region = normalize_region_name(region) if region else None
                        
                        # Extract location from description
                        extracted_location = extract_location_from_description(description)
                        
                        # Try to find location in barangay database
                        location_data, _ = find_location_in_barangay(
                            region=normalized_region,
                            province=province,
                            municipality=extracted_location.get("municipality"),
                            barangay=extracted_location.get("barangay"),
                            description=description
                        )
                        
                        if location_data:
                            psgc_data = location_data
                            psgc_enriched = True
                    
                    # Track PSGC data
                    if psgc_enriched and psgc_data:
                        contracts_with_psgc += 1
                        
                        psgc_barangay = psgc_data.get("barangay_name")
                        psgc_municipality = psgc_data.get("municipality_name")
                        psgc_province = psgc_data.get("province_name")
                        psgc_region = psgc_data.get("region_name")
                        psgc_code = psgc_data.get("psgc_code")
                        location_type = psgc_data.get("location_type")
                        
                        if psgc_barangay:
                            contracts_with_barangay += 1
                            psgc_barangays[psgc_barangay] += 1
                        
                        if psgc_municipality:
                            contracts_with_municipality += 1
                            psgc_municipalities[psgc_municipality] += 1
                        
                        if psgc_province:
                            psgc_provinces_psgc[psgc_province] += 1
                        
                        if psgc_region:
                            psgc_regions_psgc[psgc_region] += 1
                            
                            # Track PSGC region combinations
                            if infra_type:
                                psgc_region_infra_combinations[psgc_region][infra_type] += 1
                            if year_str:
                                psgc_region_year_combinations[psgc_region][year_str] += 1
                        
                        if psgc_code:
                            contracts_with_psgc_code += 1
                        
                        if location_type:
                            psgc_location_types[location_type] += 1
                        
                        # Use PSGC data as fallback if DPWH location is missing
                        if not region and psgc_region:
                            region = psgc_region
                        if not province and psgc_province:
                            province = psgc_province
                    
                    if region:
                        regions[region] += 1
                        unique_regions.add(region)
                        if len(region_samples[region]) < 3:
                            region_samples[region].append({
                                "contractId": contract_id,
                                "description": contract_data.get("description", "")[:100]
                            })
                    else:
                        missing_region += 1
                    
                    if province:
                        provinces[province] += 1
                        unique_provinces.add(province)
                        if region and province:
                            region_province_combinations[region][province] += 1
                    else:
                        missing_province += 1
                    
                    # Extract year data
                    infra_year = contract_data.get("infraYear")
                    year_str = None
                    if infra_year:
                        year_str = str(infra_year)
                        years[year_str] += 1
                        unique_years.add(year_str)
                        if len(year_samples[year_str]) < 3:
                            year_samples[year_str].append({
                                "contractId": contract_id,
                                "description": contract_data.get("description", "")[:100]
                            })
                        
                        # Track region-year combinations
                        if region:
                            region_year_combinations[region][year_str] += 1
                        
                        # Track province-year combinations
                        if province:
                            province_year_combinations[province][year_str] += 1
                    else:
                        missing_year += 1
                    
                    # Extract infraType
                    infra_type = None
                    if "infraType" in contract_data:
                        infra_type = contract_data["infraType"]
                        if infra_type:  # Only count non-None values
                            contracts_with_infra_type += 1
                            infra_types[infra_type] += 1
                            unique_infra_types.add(infra_type)
                            
                            # Store sample (keep first 3)
                            if len(infra_type_samples[infra_type]) < 3:
                                infra_type_samples[infra_type].append({
                                    "contractId": contract_id,
                                    "description": contract_data.get("description", "")[:100]
                                })
                            
                            # Track region-infraType combinations
                            if region:
                                region_infra_combinations[region][infra_type] += 1
                        else:
                            missing_infra_type += 1
                    else:
                        missing_infra_type += 1
                    
                    # Extract typeOfWork from components
                    if "components" in contract_data and contract_data["components"]:
                        contracts_with_components += 1
                        found_type_of_work = False
                        
                        for component in contract_data["components"]:
                            if "typeOfWork" in component:
                                tow = component["typeOfWork"]
                                if tow:  # Only count non-None values
                                    type_of_work[tow] += 1
                                    unique_type_of_work.add(tow)
                                    found_type_of_work = True
                                    
                                    # Track combination
                                    if infra_type:
                                        infra_type_work_combinations[infra_type][tow] += 1
                                    
                                    # Track year-infraType combination
                                    if infra_year and infra_type:
                                        year_infra_combinations[str(infra_year)][infra_type] += 1
                                    
                                    # Track year-typeOfWork combination
                                    if infra_year:
                                        year_type_of_work_combinations[str(infra_year)][tow] += 1
                                    
                                    # Store sample (keep first 3)
                                    if len(type_of_work_samples[tow]) < 3:
                                        type_of_work_samples[tow].append({
                                            "contractId": contract_id,
                                            "description": contract_data.get("description", "")[:100],
                                            "componentId": component.get("componentId", "")
                                        })
                        
                        if found_type_of_work:
                            contracts_with_type_of_work += 1
                        else:
                            missing_type_of_work += 1
                    else:
                        missing_type_of_work += 1
                    
                    processed += 1
                    if processed % 10000 == 0:
                        psgc_pct = (contracts_with_psgc / max(processed, 1)) * 100
                        print(f"  Processed {processed}/{total_files} files... (PSGC enriched: {contracts_with_psgc:,} ({psgc_pct:.1f}%))")
                
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    # Skip problematic files
                    continue
        
        print(f"\n✓ Analysis complete: {processed} files processed")
        
        return {
            "total_contracts": total_contracts,
            "contracts_with_infra_type": contracts_with_infra_type,
            "contracts_with_type_of_work": contracts_with_type_of_work,
            "contracts_with_components": contracts_with_components,
            "missing_infra_type": missing_infra_type,
            "missing_type_of_work": missing_type_of_work,
            "infra_types": infra_types,
            "type_of_work": type_of_work,
            "infra_type_work_combinations": infra_type_work_combinations,
            "unique_infra_types": unique_infra_types,
            "unique_type_of_work": unique_type_of_work,
            "infra_type_samples": infra_type_samples,
            "type_of_work_samples": type_of_work_samples,
            "regions": regions,
            "provinces": provinces,
            "region_province_combinations": region_province_combinations,
            "region_infra_combinations": region_infra_combinations,
            "region_year_combinations": region_year_combinations,
            "province_year_combinations": province_year_combinations,
            "missing_region": missing_region,
            "missing_province": missing_province,
            "unique_regions": unique_regions,
            "unique_provinces": unique_provinces,
            "years": years,
            "year_infra_combinations": year_infra_combinations,
            "year_type_of_work_combinations": year_type_of_work_combinations,
            "missing_year": missing_year,
            "unique_years": unique_years,
            "region_samples": region_samples,
            "year_samples": year_samples,
            "psgc_barangays": psgc_barangays,
            "psgc_municipalities": psgc_municipalities,
            "psgc_provinces_psgc": psgc_provinces_psgc,
            "psgc_regions_psgc": psgc_regions_psgc,
            "psgc_location_types": psgc_location_types,
            "contracts_with_psgc": contracts_with_psgc,
            "contracts_with_barangay": contracts_with_barangay,
            "contracts_with_municipality": contracts_with_municipality,
            "contracts_with_psgc_code": contracts_with_psgc_code,
            "psgc_region_infra_combinations": psgc_region_infra_combinations,
            "psgc_region_year_combinations": psgc_region_year_combinations
        }
    
    except Exception as e:
        print(f"Error analyzing tar archive: {e}")
        return {}


def generate_results_markdown(stats: Dict) -> str:
    """Generate results markdown file."""
    md = """# Infrastructure Types and Type of Work Analysis - Results

## Overview

This document contains the raw results of analyzing `infraType` and `typeOfWork` fields from DPWH projects data.

**Data Source**: `projects-data/json/projects-json.tar`  
**Total Contracts Analyzed**: {total_contracts}

---

## Summary Statistics

| Metric | Count | Percentage |
|--------|-------|------------|
| Total Contracts | {total_contracts} | 100% |
| Contracts with infraType | {contracts_with_infra_type} | {infra_type_pct:.1f}% |
| Contracts with typeOfWork | {contracts_with_type_of_work} | {type_of_work_pct:.1f}% |
| Contracts with Components | {contracts_with_components} | {components_pct:.1f}% |
| Missing infraType | {missing_infra_type} | {missing_infra_pct:.1f}% |
| Missing typeOfWork | {missing_type_of_work} | {missing_type_of_work_pct:.1f}% |

---

## Infrastructure Types (infraType)

### Count by infraType

| infraType | Count | Percentage |
|-----------|-------|------------|
""".format(
        total_contracts=stats.get("total_contracts", 0),
        contracts_with_infra_type=stats.get("contracts_with_infra_type", 0),
        contracts_with_type_of_work=stats.get("contracts_with_type_of_work", 0),
        contracts_with_components=stats.get("contracts_with_components", 0),
        missing_infra_type=stats.get("missing_infra_type", 0),
        missing_type_of_work=stats.get("missing_type_of_work", 0),
        infra_type_pct=(stats.get("contracts_with_infra_type", 0) / max(stats.get("total_contracts", 1), 1)) * 100,
        type_of_work_pct=(stats.get("contracts_with_type_of_work", 0) / max(stats.get("total_contracts", 1), 1)) * 100,
        components_pct=(stats.get("contracts_with_components", 0) / max(stats.get("total_contracts", 1), 1)) * 100,
        missing_infra_pct=(stats.get("missing_infra_type", 0) / max(stats.get("total_contracts", 1), 1)) * 100,
        missing_type_of_work_pct=(stats.get("missing_type_of_work", 0) / max(stats.get("total_contracts", 1), 1)) * 100
    )
    
    # Add infraType counts
    total_infra = sum(stats.get("infra_types", {}).values())
    for infra_type, count in stats.get("infra_types", {}).most_common():
        pct = (count / max(total_infra, 1)) * 100
        md += f"| `{infra_type}` | {count:,} | {pct:.2f}% |\n"
    
    md += "\n### Sample Contracts by infraType\n\n"
    for infra_type, samples in sorted(stats.get("infra_type_samples", {}).items(), key=lambda x: (x[0] is None, str(x[0]) if x[0] else "")):
        infra_type_display = infra_type if infra_type else "None/Missing"
        md += f"#### {infra_type_display}\n\n"
        for i, sample in enumerate(samples, 1):
            md += f"{i}. **{sample['contractId']}**: {sample['description']}...\n"
        md += "\n"
    
    md += "\n---\n\n## Type of Work (typeOfWork)\n\n"
    md += "### Count by typeOfWork\n\n"
    md += "| typeOfWork | Count | Percentage |\n"
    md += "|------------|-------|------------|\n"
    
    total_tow = sum(stats.get("type_of_work", {}).values())
    for tow, count in stats.get("type_of_work", {}).most_common():
        pct = (count / max(total_tow, 1)) * 100
        md += f"| `{tow}` | {count:,} | {pct:.2f}% |\n"
    
    md += "\n### Sample Contracts by typeOfWork\n\n"
    for tow, samples in sorted(stats.get("type_of_work_samples", {}).items(), key=lambda x: (x[0] is None, str(x[0]) if x[0] else "")):
        tow_display = tow if tow else "None/Missing"
        md += f"#### {tow_display}\n\n"
        for i, sample in enumerate(samples, 1):
            md += f"{i}. **{sample['contractId']}** (Component: {sample.get('componentId', 'N/A')}): {sample['description']}...\n"
        md += "\n"
    
    md += "\n---\n\n## infraType and typeOfWork Combinations\n\n"
    md += "This section shows which typeOfWork values appear with each infraType.\n\n"
    
    for infra_type in sorted(stats.get("infra_type_work_combinations", {}).keys()):
        md += f"### {infra_type}\n\n"
        md += "| typeOfWork | Count |\n"
        md += "|------------|-------|\n"
        
        combinations = stats["infra_type_work_combinations"][infra_type]
        for tow, count in combinations.most_common():
            md += f"| `{tow}` | {count:,} |\n"
        md += "\n"
    
    md += "\n---\n\n## Location Distribution\n\n"
    md += "### Distribution by Region\n\n"
    md += "| Region | Count | Percentage |\n"
    md += "|--------|-------|------------|\n"
    
    total_regions = sum(stats.get("regions", {}).values())
    for region, count in stats.get("regions", {}).most_common():
        pct = (count / max(total_regions, 1)) * 100
        md += f"| `{region}` | {count:,} | {pct:.2f}% |\n"
    
    md += f"\n**Missing Region Data**: {stats.get('missing_region', 0):,} contracts ({stats.get('missing_region', 0) / max(stats.get('total_contracts', 1), 1) * 100:.2f}%)\n\n"
    
    md += "### Distribution by Province\n\n"
    md += "| Province | Count | Percentage |\n"
    md += "|----------|-------|------------|\n"
    
    total_provinces = sum(stats.get("provinces", {}).values())
    for province, count in stats.get("provinces", {}).most_common(50):  # Top 50 provinces
        pct = (count / max(total_provinces, 1)) * 100
        md += f"| `{province}` | {count:,} | {pct:.2f}% |\n"
    
    if len(stats.get("provinces", {})) > 50:
        md += f"\n*Showing top 50 provinces. Total unique provinces: {len(stats.get('provinces', {}))}*\n"
    
    md += f"\n**Missing Province Data**: {stats.get('missing_province', 0):,} contracts ({stats.get('missing_province', 0) / max(stats.get('total_contracts', 1), 1) * 100:.2f}%)\n\n"
    
    md += "### Provinces by Region\n\n"
    md += "This section shows the breakdown of provinces within each region.\n\n"
    
    for region in sorted(stats.get("region_province_combinations", {}).keys()):
        md += f"#### {region}\n\n"
        md += "| Province | Count | Percentage of Region |\n"
        md += "|----------|-------|----------------------|\n"
        
        province_counts = stats["region_province_combinations"][region]
        region_total = sum(province_counts.values())
        
        for province, count in province_counts.most_common(20):  # Top 20 provinces per region
            pct = (count / max(region_total, 1)) * 100
            md += f"| `{province}` | {count:,} | {pct:.2f}% |\n"
        
        if len(province_counts) > 20:
            md += f"\n*Showing top 20 provinces. Total provinces in {region}: {len(province_counts)}*\n"
        md += "\n"
    
    md += "### Infrastructure Types by Region\n\n"
    md += "This section shows the distribution of infrastructure types within each region.\n\n"
    
    for region in sorted(stats.get("region_infra_combinations", {}).keys()):
        md += f"#### {region}\n\n"
        md += "| infraType | Count | Percentage of Region |\n"
        md += "|-----------|-------|----------------------|\n"
        
        infra_counts = stats["region_infra_combinations"][region]
        region_total = sum(infra_counts.values())
        
        for infra_type, count in infra_counts.most_common():
            pct = (count / max(region_total, 1)) * 100
            md += f"| `{infra_type}` | {count:,} | {pct:.2f}% |\n"
        md += "\n"
    
    md += "### Yearly Distribution by Region\n\n"
    md += "This section shows the distribution of contracts across years for each region.\n\n"
    
    for region in sorted(stats.get("region_year_combinations", {}).keys()):
        md += f"#### {region}\n\n"
        md += "| Year | Count | Percentage of Region |\n"
        md += "|------|-------|----------------------|\n"
        
        year_counts = stats["region_year_combinations"][region]
        region_total = sum(year_counts.values())
        
        for year in sorted(year_counts.keys(), key=lambda x: int(x) if x.isdigit() else 0):
            count = year_counts[year]
            pct = (count / max(region_total, 1)) * 100
            md += f"| `{year}` | {count:,} | {pct:.2f}% |\n"
        md += "\n"
    
    md += "### Sample Contracts by Region\n\n"
    for region, samples in sorted(stats.get("region_samples", {}).items(), key=lambda x: (x[0] is None, str(x[0]) if x[0] else ""))[:20]:  # Top 20 regions
        region_display = region if region else "None/Missing"
        md += f"#### {region_display}\n\n"
        for i, sample in enumerate(samples, 1):
            md += f"{i}. **{sample['contractId']}**: {sample['description']}...\n"
        md += "\n"
    
    md += "\n---\n\n## Yearly Distribution\n\n"
    md += "### Distribution by Year (infraYear)\n\n"
    md += "| Year | Count | Percentage |\n"
    md += "|------|-------|------------|\n"
    
    total_years = sum(stats.get("years", {}).values())
    for year in sorted(stats.get("years", {}).keys(), key=lambda x: int(x) if x.isdigit() else 0):
        count = stats.get("years", {}).get(year, 0)
        pct = (count / max(total_years, 1)) * 100
        md += f"| `{year}` | {count:,} | {pct:.2f}% |\n"
    
    md += f"\n**Missing Year Data**: {stats.get('missing_year', 0):,} contracts ({stats.get('missing_year', 0) / max(stats.get('total_contracts', 1), 1) * 100:.2f}%)\n\n"
    
    md += "### Infrastructure Types by Year\n\n"
    md += "This section shows the distribution of infrastructure types for each year.\n\n"
    
    for year in sorted(stats.get("year_infra_combinations", {}).keys(), key=lambda x: int(x) if x.isdigit() else 0):
        md += f"#### {year}\n\n"
        md += "| infraType | Count | Percentage of Year |\n"
        md += "|-----------|-------|-------------------|\n"
        
        infra_counts = stats["year_infra_combinations"][year]
        year_total = sum(infra_counts.values())
        
        for infra_type, count in infra_counts.most_common():
            pct = (count / max(year_total, 1)) * 100
            md += f"| `{infra_type}` | {count:,} | {pct:.2f}% |\n"
        md += "\n"
    
    md += "### Type of Work by Year\n\n"
    md += "This section shows the distribution of types of work for each year.\n\n"
    
    for year in sorted(stats.get("year_type_of_work_combinations", {}).keys(), key=lambda x: int(x) if x.isdigit() else 0):
        md += f"#### {year}\n\n"
        md += "| typeOfWork | Count | Percentage of Year |\n"
        md += "|------------|-------|-------------------|\n"
        
        tow_counts = stats["year_type_of_work_combinations"][year]
        year_total = sum(tow_counts.values())
        
        for tow, count in tow_counts.most_common(15):  # Top 15 per year
            pct = (count / max(year_total, 1)) * 100
            md += f"| `{tow}` | {count:,} | {pct:.2f}% |\n"
        
        if len(tow_counts) > 15:
            md += f"\n*Showing top 15 types of work. Total unique types in {year}: {len(tow_counts)}*\n"
        md += "\n"
    
    md += "### Regional Distribution by Year\n\n"
    md += "This section shows the distribution of contracts across regions for each year.\n\n"
    
    # Reverse the region_year_combinations to show by year
    year_region_combinations = defaultdict(Counter)
    for region, year_counts in stats.get("region_year_combinations", {}).items():
        for year, count in year_counts.items():
            year_region_combinations[year][region] += count
    
    for year in sorted(year_region_combinations.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        md += f"#### {year}\n\n"
        md += "| Region | Count | Percentage of Year |\n"
        md += "|--------|-------|-------------------|\n"
        
        region_counts = year_region_combinations[year]
        year_total = sum(region_counts.values())
        
        for region, count in region_counts.most_common():
            pct = (count / max(year_total, 1)) * 100
            md += f"| `{region}` | {count:,} | {pct:.2f}% |\n"
        md += "\n"
    
    md += "### Top Provinces by Year\n\n"
    md += "This section shows the top provinces for each year.\n\n"
    
    # Reverse the province_year_combinations to show by year
    year_province_combinations = defaultdict(Counter)
    for province, year_counts in stats.get("province_year_combinations", {}).items():
        for year, count in year_counts.items():
            year_province_combinations[year][province] += count
    
    for year in sorted(year_province_combinations.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        md += f"#### {year}\n\n"
        md += "| Province | Count | Percentage of Year |\n"
        md += "|----------|-------|-------------------|\n"
        
        province_counts = year_province_combinations[year]
        year_total = sum(province_counts.values())
        
        for province, count in province_counts.most_common(10):  # Top 10 provinces per year
            pct = (count / max(year_total, 1)) * 100
            md += f"| `{province}` | {count:,} | {pct:.2f}% |\n"
        
        if len(province_counts) > 10:
            md += f"\n*Showing top 10 provinces. Total unique provinces in {year}: {len(province_counts)}*\n"
        md += "\n"
    
    md += "### Sample Contracts by Year\n\n"
    for year in sorted(stats.get("year_samples", {}).keys(), key=lambda x: int(x) if x.isdigit() else 0):
        md += f"#### {year}\n\n"
        samples = stats.get("year_samples", {}).get(year, [])
        for i, sample in enumerate(samples, 1):
            md += f"{i}. **{sample['contractId']}**: {sample['description']}...\n"
        md += "\n"
    
    md += "\n---\n\n## PSGC Enrichment Data Distribution\n\n"
    
    psgc_coverage = (stats.get("contracts_with_psgc", 0) / max(stats.get("total_contracts", 1), 1)) * 100
    
    if stats.get("contracts_with_psgc", 0) > 0:
        md += f"**PSGC Data Coverage**: {stats.get('contracts_with_psgc', 0):,} contracts ({psgc_coverage:.2f}%)\n\n"
        
        md += "### Distribution by Barangay (PSGC)\n\n"
        md += "| Barangay | Count | Percentage |\n"
        md += "|----------|-------|------------|\n"
        
        total_barangays = sum(stats.get("psgc_barangays", {}).values())
        for barangay, count in stats.get("psgc_barangays", {}).most_common(50):  # Top 50 barangays
            pct = (count / max(total_barangays, 1)) * 100
            md += f"| `{barangay}` | {count:,} | {pct:.2f}% |\n"
        
        if len(stats.get("psgc_barangays", {})) > 50:
            md += f"\n*Showing top 50 barangays. Total unique barangays: {len(stats.get('psgc_barangays', {}))}*\n"
        
        md += f"\n**Contracts with Barangay Data**: {stats.get('contracts_with_barangay', 0):,} ({stats.get('contracts_with_barangay', 0) / max(stats.get('contracts_with_psgc', 1), 1) * 100:.2f}% of enriched)\n\n"
        
        md += "### Distribution by Municipality (PSGC)\n\n"
        md += "| Municipality | Count | Percentage |\n"
        md += "|--------------|-------|------------|\n"
        
        total_municipalities = sum(stats.get("psgc_municipalities", {}).values())
        for municipality, count in stats.get("psgc_municipalities", {}).most_common(50):  # Top 50 municipalities
            pct = (count / max(total_municipalities, 1)) * 100
            md += f"| `{municipality}` | {count:,} | {pct:.2f}% |\n"
        
        if len(stats.get("psgc_municipalities", {})) > 50:
            md += f"\n*Showing top 50 municipalities. Total unique municipalities: {len(stats.get('psgc_municipalities', {}))}*\n"
        
        md += f"\n**Contracts with Municipality Data**: {stats.get('contracts_with_municipality', 0):,} ({stats.get('contracts_with_municipality', 0) / max(stats.get('contracts_with_psgc', 1), 1) * 100:.2f}% of enriched)\n\n"
        
        md += "### Distribution by Province (PSGC Standard Names)\n\n"
        md += "| Province (PSGC) | Count | Percentage |\n"
        md += "|----------------|-------|------------|\n"
        
        total_psgc_provinces = sum(stats.get("psgc_provinces_psgc", {}).values())
        for province, count in stats.get("psgc_provinces_psgc", {}).most_common(30):  # Top 30 provinces
            pct = (count / max(total_psgc_provinces, 1)) * 100
            md += f"| `{province}` | {count:,} | {pct:.2f}% |\n"
        
        if len(stats.get("psgc_provinces_psgc", {})) > 30:
            md += f"\n*Showing top 30 provinces. Total unique provinces: {len(stats.get('psgc_provinces_psgc', {}))}*\n"
        
        md += "### Distribution by Region (PSGC Standard Names)\n\n"
        md += "| Region (PSGC) | Count | Percentage |\n"
        md += "|--------------|-------|------------|\n"
        
        total_psgc_regions = sum(stats.get("psgc_regions_psgc", {}).values())
        for region, count in stats.get("psgc_regions_psgc", {}).most_common():
            pct = (count / max(total_psgc_regions, 1)) * 100
            md += f"| `{region}` | {count:,} | {pct:.2f}% |\n"
        
        md += "### Location Type Distribution\n\n"
        md += "This shows the granularity level at which locations were matched.\n\n"
        md += "| Location Type | Count | Percentage |\n"
        md += "|---------------|-------|------------|\n"
        
        total_location_types = sum(stats.get("psgc_location_types", {}).values())
        for loc_type, count in stats.get("psgc_location_types", {}).most_common():
            pct = (count / max(total_location_types, 1)) * 100
            md += f"| `{loc_type}` | {count:,} | {pct:.2f}% |\n"
        
        md += f"\n**Contracts with PSGC Code**: {stats.get('contracts_with_psgc_code', 0):,} ({stats.get('contracts_with_psgc_code', 0) / max(stats.get('contracts_with_psgc', 1), 1) * 100:.2f}% of enriched)\n\n"
    else:
        md += "**Note**: No PSGC enrichment data found in the analyzed files.\n"
        md += "To include PSGC analysis, run the enrichment script first to add barangay/municipality/province/region data.\n\n"
    
    md += "\n---\n\n*Report generated automatically from projects-data analysis.*\n"
    
    return md


def generate_analysis_markdown(stats: Dict) -> str:
    """Generate analysis markdown file with insights."""
    md = """# Infrastructure Types and Type of Work Analysis - Insights

## Executive Summary

This document provides analysis and insights from the infrastructure types and type of work data extracted from DPWH projects.

**Data Source**: `projects-data/json/projects-json.tar`  
**Analysis Date**: {analysis_date}

---

## Key Findings

### Data Coverage

- **Total Contracts**: {total_contracts:,}
- **infraType Coverage**: {infra_type_coverage:.1f}% ({contracts_with_infra_type:,} contracts)
- **typeOfWork Coverage**: {type_of_work_coverage:.1f}% ({contracts_with_type_of_work:,} contracts)
- **Components Available**: {contracts_with_components:,} contracts ({components_coverage:.1f}%)

### Infrastructure Type Distribution

The data shows {unique_infra_types} unique infrastructure types:

""".format(
        analysis_date=Path(__file__).stat().st_mtime,
        total_contracts=stats.get("total_contracts", 0),
        contracts_with_infra_type=stats.get("contracts_with_infra_type", 0),
        contracts_with_type_of_work=stats.get("contracts_with_type_of_work", 0),
        contracts_with_components=stats.get("contracts_with_components", 0),
        infra_type_coverage=(stats.get("contracts_with_infra_type", 0) / max(stats.get("total_contracts", 1), 1)) * 100,
        type_of_work_coverage=(stats.get("contracts_with_type_of_work", 0) / max(stats.get("total_contracts", 1), 1)) * 100,
        components_coverage=(stats.get("contracts_with_components", 0) / max(stats.get("total_contracts", 1), 1)) * 100,
        unique_infra_types=len(stats.get("unique_infra_types", set()))
    )
    
    # Top infraTypes
    infra_types = stats.get("infra_types", {})
    if infra_types:
        md += "**Top Infrastructure Types:**\n\n"
        md += "| Rank | infraType | Count | Percentage |\n"
        md += "|------|----------|-------|------------|\n"
        for rank, (infra_type, count) in enumerate(infra_types.most_common(10), 1):
            total = sum(infra_types.values())
            pct = (count / max(total, 1)) * 100
            md += f"| {rank} | `{infra_type}` | {count:,} | {pct:.2f}% |\n"
    
    md += "\n### Type of Work Distribution\n\n"
    type_of_work = stats.get("type_of_work", {})
    if type_of_work:
        md += f"The data shows **{len(stats.get('unique_type_of_work', set()))}** unique types of work.\n\n"
        md += "**Top Types of Work:**\n\n"
        md += "| Rank | typeOfWork | Count | Percentage |\n"
        md += "|------|------------|-------|------------|\n"
        for rank, (tow, count) in enumerate(type_of_work.most_common(15), 1):
            total = sum(type_of_work.values())
            pct = (count / max(total, 1)) * 100
            md += f"| {rank} | `{tow}` | {count:,} | {pct:.2f}% |\n"
    
    md += "\n---\n\n## Analysis\n\n"
    
    # Analysis points
    md += "### 1. Data Completeness\n\n"
    missing_infra_pct = (stats.get("missing_infra_type", 0) / max(stats.get("total_contracts", 1), 1)) * 100
    missing_tow_pct = (stats.get("missing_type_of_work", 0) / max(stats.get("total_contracts", 1), 1)) * 100
    
    if missing_infra_pct < 5:
        md += f"- **infraType**: Excellent coverage ({100-missing_infra_pct:.1f}% present). Most contracts have this field.\n"
    elif missing_infra_pct < 20:
        md += f"- **infraType**: Good coverage ({100-missing_infra_pct:.1f}% present). Some contracts missing this field.\n"
    else:
        md += f"- **infraType**: Limited coverage ({100-missing_infra_pct:.1f}% present). Many contracts missing this field.\n"
    
    if missing_tow_pct < 5:
        md += f"- **typeOfWork**: Excellent coverage ({100-missing_tow_pct:.1f}% present). Most components have this field.\n"
    elif missing_tow_pct < 20:
        md += f"- **typeOfWork**: Good coverage ({100-missing_tow_pct:.1f}% present). Some components missing this field.\n"
    else:
        md += f"- **typeOfWork**: Limited coverage ({100-missing_tow_pct:.1f}% present). Many components missing this field.\n"
    
    md += "\n### 2. Infrastructure Type Insights\n\n"
    
    # Check for common types
    infra_types = stats.get("infra_types", {})
    if infra_types:
        top_3 = [item[0] for item in infra_types.most_common(3)]
        md += f"- **Most Common Types**: {', '.join(f'`{t}`' for t in top_3)}\n"
        md += f"- **Diversity**: {len(infra_types)} distinct infrastructure types identified\n"
        
        # Check distribution
        top_count = infra_types.most_common(1)[0][1] if infra_types else 0
        total = sum(infra_types.values())
        top_pct = (top_count / max(total, 1)) * 100
        
        if top_pct > 50:
            md += f"- **Concentration**: High concentration - top type represents {top_pct:.1f}% of all contracts\n"
        elif top_pct > 30:
            md += f"- **Concentration**: Moderate concentration - top type represents {top_pct:.1f}% of all contracts\n"
        else:
            md += f"- **Concentration**: Well distributed - top type represents {top_pct:.1f}% of all contracts\n"
    
    md += "\n### 3. Type of Work Insights\n\n"
    
    type_of_work = stats.get("type_of_work", {})
    if type_of_work:
        md += f"- **Total Unique Types**: {len(type_of_work)} distinct types of work\n"
        
        # Check for common patterns
        top_5 = [item[0] for item in type_of_work.most_common(5)]
        md += f"- **Top 5 Types**: {', '.join(f'`{t}`' for t in top_5)}\n"
        
        # Check if there are many unique types
        if len(type_of_work) > 50:
            md += f"- **Granularity**: High granularity - many specific work types ({len(type_of_work)} unique types)\n"
        elif len(type_of_work) > 20:
            md += f"- **Granularity**: Moderate granularity - several work type categories ({len(type_of_work)} unique types)\n"
        else:
            md += f"- **Granularity**: Low granularity - few broad work type categories ({len(type_of_work)} unique types)\n"
    
    md += "\n### 4. Relationship Analysis\n\n"
    
    combinations = stats.get("infra_type_work_combinations", {})
    if combinations:
        md += "**infraType and typeOfWork Relationships:**\n\n"
        
        # Find most common combinations
        all_combinations = []
        for infra_type, tows in combinations.items():
            for tow, count in tows.items():
                all_combinations.append((infra_type, tow, count))
        
        all_combinations.sort(key=lambda x: x[2], reverse=True)
        
        md += "| infraType | typeOfWork | Count |\n"
        md += "|-----------|------------|-------|\n"
        for infra_type, tow, count in all_combinations[:20]:  # Top 20 combinations
            md += f"| `{infra_type}` | `{tow}` | {count:,} |\n"
        
        md += "\n**Observations:**\n"
        md += f"- {len(all_combinations)} unique infraType-typeOfWork combinations found\n"
        
        # Check if types are well-mapped
        infra_types_with_work = len([k for k, v in combinations.items() if v])
        md += f"- {infra_types_with_work} infrastructure types have associated typeOfWork values\n"
    
    md += "\n### 5. Location Distribution Analysis\n\n"
    
    regions = stats.get("regions", {})
    provinces = stats.get("provinces", {})
    
    if regions:
        md += f"- **Total Unique Regions**: {len(regions)} distinct regions\n"
        top_5_regions = [item[0] for item in regions.most_common(5)]
        md += f"- **Top 5 Regions**: {', '.join(f'`{r}`' for r in top_5_regions)}\n"
        
        # Check distribution
        top_region_count = regions.most_common(1)[0][1] if regions else 0
        total_regions = sum(regions.values())
        top_region_pct = (top_region_count / max(total_regions, 1)) * 100
        
        if top_region_pct > 30:
            md += f"- **Regional Concentration**: High concentration - top region represents {top_region_pct:.1f}% of all contracts\n"
        elif top_region_pct > 15:
            md += f"- **Regional Concentration**: Moderate concentration - top region represents {top_region_pct:.1f}% of all contracts\n"
        else:
            md += f"- **Regional Concentration**: Well distributed - top region represents {top_region_pct:.1f}% of all contracts\n"
    
    if provinces:
        md += f"- **Total Unique Provinces**: {len(provinces)} distinct provinces\n"
        top_5_provinces = [item[0] for item in provinces.most_common(5)]
        md += f"- **Top 5 Provinces**: {', '.join(f'`{p}`' for p in top_5_provinces)}\n"
    
    missing_region_pct = (stats.get("missing_region", 0) / max(stats.get("total_contracts", 1), 1)) * 100
    if missing_region_pct < 5:
        md += f"- **Region Data Quality**: Excellent - {100-missing_region_pct:.1f}% of contracts have region data\n"
    elif missing_region_pct < 20:
        md += f"- **Region Data Quality**: Good - {100-missing_region_pct:.1f}% of contracts have region data\n"
    else:
        md += f"- **Region Data Quality**: Needs improvement - {100-missing_region_pct:.1f}% of contracts have region data\n"
    
    md += "\n### 6. Yearly Distribution Analysis\n\n"
    
    years = stats.get("years", {})
    if years:
        year_list = sorted([int(y) for y in years.keys() if y.isdigit()])
        if year_list:
            md += f"- **Year Range**: {min(year_list)} - {max(year_list)} ({max(year_list) - min(year_list) + 1} years)\n"
            md += f"- **Total Unique Years**: {len(years)} distinct years\n"
            
            # Find peak year
            peak_year = max(years.items(), key=lambda x: x[1])
            md += f"- **Peak Year**: `{peak_year[0]}` with {peak_year[1]:,} contracts ({peak_year[1] / max(sum(years.values()), 1) * 100:.1f}%)\n"
            
            # Check for trends
            recent_years = [y for y in year_list if y >= max(year_list) - 5]
            if recent_years:
                recent_counts = [years.get(str(y), 0) for y in recent_years]
                if len(recent_counts) >= 2:
                    trend = "increasing" if recent_counts[-1] > recent_counts[0] else "decreasing"
                    md += f"- **Recent Trend**: {trend} - from {recent_counts[0]:,} in {recent_years[0]} to {recent_counts[-1]:,} in {recent_years[-1]}\n"
    
    missing_year_pct = (stats.get("missing_year", 0) / max(stats.get("total_contracts", 1), 1)) * 100
    if missing_year_pct < 5:
        md += f"- **Year Data Quality**: Excellent - {100-missing_year_pct:.1f}% of contracts have year data\n"
    elif missing_year_pct < 20:
        md += f"- **Year Data Quality**: Good - {100-missing_year_pct:.1f}% of contracts have year data\n"
    else:
        md += f"- **Year Data Quality**: Needs improvement - {100-missing_year_pct:.1f}% of contracts have year data\n"
    
    # Year-InfraType combinations
    year_infra = stats.get("year_infra_combinations", {})
    if year_infra:
        md += "\n**Year-Infrastructure Type Trends:**\n\n"
        md += "| Year | Top infraType | Count |\n"
        md += "|------|----------------|-------|\n"
        
        for year in sorted(year_infra.keys(), key=lambda x: int(x) if x.isdigit() else 0)[-10:]:  # Last 10 years
            infra_counts = year_infra[year]
            if infra_counts:
                top_infra = infra_counts.most_common(1)[0]
                md += f"| `{year}` | `{top_infra[0]}` | {top_infra[1]:,} |\n"
        
        md += "\n**Detailed Year-Infrastructure Type Analysis:**\n\n"
        md += "This table shows the complete breakdown of infrastructure types for each year.\n\n"
        md += "| Year | Roads | Buildings & Facilities | Flood Control | Bridges | Water | Buildings | Septage |\n"
        md += "|------|-------|----------------------|---------------|---------|-------|-----------|----------|\n"
        
        infra_type_names = ["Roads", "Buildings and Facilities", "Flood Control and Drainage", "Bridges", 
                           "Water Provision and Storage", "Buildings", "Septage and Sewerage Plants"]
        
        for year in sorted(year_infra.keys(), key=lambda x: int(x) if x.isdigit() else 0):
            infra_counts = year_infra[year]
            row = f"| `{year}` |"
            for infra_name in infra_type_names:
                count = infra_counts.get(infra_name, 0)
                row += f" {count:,} |"
            md += row + "\n"
    
    # Region-InfraType analysis
    region_infra = stats.get("region_infra_combinations", {})
    if region_infra:
        md += "\n**Regional Infrastructure Type Preferences:**\n\n"
        md += "This table shows which infrastructure types are most common in each region.\n\n"
        md += "| Region | Top infraType | Count | % of Region |\n"
        md += "|--------|---------------|-------|-------------|\n"
        
        for region in sorted(region_infra.keys()):
            infra_counts = region_infra[region]
            if infra_counts:
                top_infra = infra_counts.most_common(1)[0]
                region_total = sum(infra_counts.values())
                pct = (top_infra[1] / max(region_total, 1)) * 100
                md += f"| `{region}` | `{top_infra[0]}` | {top_infra[1]:,} | {pct:.1f}% |\n"
    
    # Region-Year analysis
    region_year = stats.get("region_year_combinations", {})
    if region_year:
        md += "\n**Regional Activity Trends:**\n\n"
        md += "This analysis shows which regions had the most activity in recent years.\n\n"
        
        # Find peak year for each region
        md += "| Region | Peak Year | Contracts in Peak Year | % of Region Total |\n"
        md += "|--------|-----------|------------------------|-------------------|\n"
        
        for region in sorted(region_year.keys()):
            year_counts = region_year[region]
            if year_counts:
                peak_year = max(year_counts.items(), key=lambda x: x[1])
                region_total = sum(year_counts.values())
                pct = (peak_year[1] / max(region_total, 1)) * 100
                md += f"| `{region}` | `{peak_year[0]}` | {peak_year[1]:,} | {pct:.1f}% |\n"
    
    md += "\n---\n\n## Recommendations\n\n"
    
    # Generate recommendations based on data
    if stats.get("missing_infra_type", 0) > 0:
        md += "1. **Improve infraType Coverage**: Consider backfilling missing infraType values from category or description fields.\n\n"
    
    if stats.get("missing_type_of_work", 0) > 0:
        md += "2. **Improve typeOfWork Coverage**: Some components are missing typeOfWork. Review data extraction process.\n\n"
    
    if len(stats.get("unique_type_of_work", set())) > 100:
        md += "3. **Standardize typeOfWork**: High number of unique types suggests need for standardization or categorization.\n\n"
    
    if stats.get("missing_region", 0) > stats.get("total_contracts", 1) * 0.1:
        md += "4. **Improve Location Data**: Significant number of contracts missing region data. Consider enrichment from description or other sources.\n\n"
    
    if stats.get("missing_year", 0) > stats.get("total_contracts", 1) * 0.1:
        md += "5. **Improve Year Data**: Significant number of contracts missing year data. Consider extracting from contract dates or other fields.\n\n"
    
    md += "6. **Data Quality**: Use these insights to validate data quality and identify areas for improvement.\n\n"
    
    md += "\n### 7. PSGC Enrichment Analysis\n\n"
    
    psgc_coverage = (stats.get("contracts_with_psgc", 0) / max(stats.get("total_contracts", 1), 1)) * 100
    
    if stats.get("contracts_with_psgc", 0) > 0:
        md += f"- **PSGC Data Coverage**: {psgc_coverage:.1f}% ({stats.get('contracts_with_psgc', 0):,} contracts enriched)\n"
        md += f"- **Barangay-Level Data**: {stats.get('contracts_with_barangay', 0):,} contracts ({stats.get('contracts_with_barangay', 0) / max(stats.get('contracts_with_psgc', 1), 1) * 100:.1f}% of enriched)\n"
        md += f"- **Municipality-Level Data**: {stats.get('contracts_with_municipality', 0):,} contracts ({stats.get('contracts_with_municipality', 0) / max(stats.get('contracts_with_psgc', 1), 1) * 100:.1f}% of enriched)\n"
        md += f"- **PSGC Code Coverage**: {stats.get('contracts_with_psgc_code', 0):,} contracts ({stats.get('contracts_with_psgc_code', 0) / max(stats.get('contracts_with_psgc', 1), 1) * 100:.1f}% of enriched)\n"
        md += f"- **Unique Barangays**: {len(stats.get('psgc_barangays', {}))} distinct barangays identified\n"
        md += f"- **Unique Municipalities**: {len(stats.get('psgc_municipalities', {}))} distinct municipalities identified\n"
        md += f"- **Unique Provinces (PSGC)**: {len(stats.get('psgc_provinces_psgc', {}))} distinct provinces (using PSGC standard names)\n"
        md += f"- **Unique Regions (PSGC)**: {len(stats.get('psgc_regions_psgc', {}))} distinct regions (using PSGC standard names)\n\n"
        
        # Location type analysis
        location_types = stats.get("psgc_location_types", {})
        if location_types:
            md += "**Location Granularity:**\n\n"
            md += "| Location Type | Count | % of Enriched |\n"
            md += "|---------------|-------|---------------|\n"
            total_enriched = sum(location_types.values())
            for loc_type, count in location_types.most_common():
                pct = (count / max(total_enriched, 1)) * 100
                md += f"| `{loc_type}` | {count:,} | {pct:.2f}% |\n"
            md += "\n"
        
        # Top barangays
        top_barangays = [item[0] for item in stats.get("psgc_barangays", {}).most_common(5)]
        if top_barangays:
            md += f"- **Top 5 Barangays**: {', '.join(f'`{b}`' for b in top_barangays)}\n"
        
        # Top municipalities
        top_municipalities = [item[0] for item in stats.get("psgc_municipalities", {}).most_common(5)]
        if top_municipalities:
            md += f"- **Top 5 Municipalities**: {', '.join(f'`{m}`' for m in top_municipalities)}\n"
        
        # PSGC Region analysis
        psgc_regions = stats.get("psgc_regions_psgc", {})
        if psgc_regions:
            md += "\n**PSGC Region Distribution:**\n\n"
            md += "| Region (PSGC) | Count | % of Enriched |\n"
            md += "|---------------|-------|---------------|\n"
            total_psgc = sum(psgc_regions.values())
            for region, count in psgc_regions.most_common():
                pct = (count / max(total_psgc, 1)) * 100
                md += f"| `{region}` | {count:,} | {pct:.2f}% |\n"
    else:
        md += "- **PSGC Enrichment**: No PSGC data found in analyzed files.\n"
        md += "- **Recommendation**: Run the enrichment script (`enrich_with_barangay.py`) to add PSGC data before analysis.\n"
        md += "- **Benefits**: PSGC enrichment provides standardized location names and codes, enabling better geographic analysis.\n\n"
    
    md += "\n---\n\n*Analysis generated automatically from infrastructure types data.*\n"
    
    return md


def main():
    """Main function."""
    print("="*70)
    print("Infrastructure Types and Type of Work Analysis")
    print("="*70)
    print()
    
    if not TAR_FILE.exists():
        print(f"Error: Tar file not found: {TAR_FILE}")
        return
    
    # Analyze tar archive
    stats = analyze_tar_archive(TAR_FILE)
    
    if not stats:
        print("Error: No data extracted from tar archive")
        return
    
    # Generate markdown files
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    print(f"\nGenerating results markdown...")
    results_md = generate_results_markdown(stats)
    with open(RESULTS_MD, 'w', encoding='utf-8') as f:
        f.write(results_md)
    print(f"✓ Results saved to: {RESULTS_MD}")
    
    print(f"Generating analysis markdown...")
    analysis_md = generate_analysis_markdown(stats)
    with open(ANALYSIS_MD, 'w', encoding='utf-8') as f:
        f.write(analysis_md)
    print(f"✓ Analysis saved to: {ANALYSIS_MD}")
    
    # Print summary
    print("\n" + "="*70)
    print("Summary:")
    print(f"  Total contracts: {stats.get('total_contracts', 0):,}")
    print(f"  Unique infraTypes: {len(stats.get('unique_infra_types', set()))}")
    print(f"  Unique typeOfWork: {len(stats.get('unique_type_of_work', set()))}")
    print(f"  Unique regions: {len(stats.get('unique_regions', set()))}")
    print(f"  Unique provinces: {len(stats.get('unique_provinces', set()))}")
    print(f"  Unique years: {len(stats.get('unique_years', set()))}")
    if stats.get("contracts_with_psgc", 0) > 0:
        print(f"  Contracts with PSGC data: {stats.get('contracts_with_psgc', 0):,}")
        print(f"  Unique PSGC barangays: {len(stats.get('psgc_barangays', {}))}")
        print(f"  Unique PSGC municipalities: {len(stats.get('psgc_municipalities', {}))}")
    print("="*70)


if __name__ == "__main__":
    main()

