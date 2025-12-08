#!/usr/bin/env python3
"""
Enrich DPWH project data with barangay, municipality, province, region names, and PSGC codes
using the barangay package (https://github.com/bendlikeabamboo/barangay/).
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from barangay import search, BARANGAY_FLAT, BARANGAY_EXTENDED

# Input/Output paths
ENRICHMENT_ANALYSIS_DIR = Path(__file__).parent.parent
SAMPLES_DIR = ENRICHMENT_ANALYSIS_DIR / "samples"
OUTPUT_DIR = ENRICHMENT_ANALYSIS_DIR / "enriched"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def normalize_region_name(region: str) -> str:
    """Normalize region names to match PSGC format."""
    if not region:
        return ""
    
    # Remove common prefixes/suffixes
    region = region.strip()
    
    # Map DPWH region names to PSGC format
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
    
    # Try exact match first
    if region in region_mapping:
        return region_mapping[region]
    
    # Try partial match
    for key, value in region_mapping.items():
        if key in region or region in key:
            return value
    
    # Try to find in BARANGAY_FLAT
    for loc in BARANGAY_FLAT:
        if loc["type"] == "Region" and (key.lower() in loc["name"].lower() or loc["name"].lower() in region.lower()):
            return loc["name"]
    
    return region


def extract_location_from_description(description: str) -> Dict[str, Optional[str]]:
    """Extract location information from project description."""
    if not description:
        return {}
    
    # Common patterns in DPWH descriptions
    # Example: "CONCRETING OF G. GOKOTANO STREET, BARANGAY POBLACION, PIKIT, NORTH COTABATO"
    location_info = {}
    
    # Try to extract barangay
    brgy_match = re.search(r'BARANGAY\s+([A-Z][A-Z\s]+?)(?:,|$)', description, re.IGNORECASE)
    if brgy_match:
        location_info["barangay"] = brgy_match.group(1).strip()
    
    # Try to extract municipality/city
    # Look for patterns like "PIKIT" or "CITY OF MANILA"
    mun_match = re.search(r'(?:MUNICIPALITY OF|CITY OF|MUNICIPALITY|CITY)\s+([A-Z][A-Z\s]+?)(?:,|$)', description, re.IGNORECASE)
    if mun_match:
        location_info["municipality"] = mun_match.group(1).strip()
    else:
        # Try to find municipality name before province
        parts = description.split(',')
        if len(parts) >= 2:
            # Second to last part might be municipality
            potential_mun = parts[-2].strip()
            if potential_mun and not any(word in potential_mun.upper() for word in ['PROVINCE', 'REGION', 'NORTH', 'SOUTH', 'EAST', 'WEST']):
                location_info["municipality"] = potential_mun
    
    # Try to extract province
    prov_match = re.search(r'([A-Z][A-Z\s]+?)\s+(?:PROVINCE|PROV)', description, re.IGNORECASE)
    if prov_match:
        location_info["province"] = prov_match.group(1).strip()
    else:
        # Look for common province patterns
        parts = description.split(',')
        if len(parts) >= 1:
            last_part = parts[-1].strip()
            if any(word in last_part.upper() for word in ['COTABATO', 'MINDORO', 'LEYTE', 'CEBU', 'PALAWAN']):
                location_info["province"] = last_part
    
    return location_info


def extract_project_details_from_description(description: str, location_info: Dict[str, Optional[str]]) -> str:
    """
    Extract project details (actual work description) by removing location information.
    Returns cleaned project description without location parts.
    
    Strategy: Remove location parts from the end of the description, as they typically
    appear at the end in format: [PROJECT], [BARANGAY], [MUNICIPALITY], [PROVINCE]
    """
    if not description:
        return ""
    
    # Start with original description
    project_desc = description
    
    # Strategy: Work backwards from the end, removing location parts
    # Split by comma to get parts
    parts = [p.strip() for p in description.split(',')]
    
    if len(parts) <= 1:
        # No commas, likely no location info to remove
        return description
    
    # Identify which parts are location-related
    location_parts_to_remove = []
    
    # Check last part (usually province)
    if parts:
        last_part = parts[-1].upper()
        # Check if it's a province
        if location_info.get("province"):
            prov_upper = location_info["province"].upper()
            if prov_upper in last_part or last_part in prov_upper:
                location_parts_to_remove.append(len(parts) - 1)
            # Also check for "NORTH COTABATO", "SOUTH COTABATO" patterns
            elif any(word in last_part for word in ['NORTH', 'SOUTH', 'EAST', 'WEST']) and \
                 any(prov_word in last_part for prov_word in prov_upper.split()):
                location_parts_to_remove.append(len(parts) - 1)
        # Check for common province indicators
        elif any(word in last_part for word in ['PROVINCE', 'PROV']) or \
             any(prov in last_part for prov in ['COTABATO', 'MINDORO', 'LEYTE', 'CEBU', 'PALAWAN']):
            location_parts_to_remove.append(len(parts) - 1)
    
    # Check second-to-last part (usually municipality)
    if len(parts) >= 2:
        second_last = parts[-2].upper()
        if location_info.get("municipality"):
            mun_upper = location_info["municipality"].upper()
            if mun_upper in second_last or second_last in mun_upper:
                location_parts_to_remove.append(len(parts) - 2)
        # Check for municipality indicators
        elif any(word in second_last for word in ['MUNICIPALITY', 'CITY']):
            location_parts_to_remove.append(len(parts) - 2)
    
    # Check for BARANGAY pattern (can be anywhere but often before municipality)
    for i, part in enumerate(parts):
        part_upper = part.upper()
        # Check for "BARANGAY {name}" pattern
        if part_upper.startswith('BARANGAY'):
            location_parts_to_remove.append(i)
        # Check if part matches extracted barangay name
        elif location_info.get("barangay"):
            brgy_upper = location_info["barangay"].upper()
            if brgy_upper in part_upper and i not in location_parts_to_remove:
                # Only remove if it's clearly a location part (not part of project name)
                if i >= len(parts) - 3:  # Likely in location section
                    location_parts_to_remove.append(i)
    
    # Remove identified location parts (in reverse order to maintain indices)
    for idx in sorted(location_parts_to_remove, reverse=True):
        if 0 <= idx < len(parts):
            parts.pop(idx)
    
    # Reconstruct description
    project_desc = ', '.join(parts)
    
    # Clean up: remove trailing/leading whitespace, handle edge cases
    project_desc = project_desc.strip()
    
    # Remove any remaining location indicators that might have been missed
    # Remove standalone "NORTH", "SOUTH", etc. at the end
    project_desc = re.sub(r'\s+(NORTH|SOUTH|EAST|WEST)$', '', project_desc, flags=re.IGNORECASE)
    
    # If result is empty or too short, return original
    if len(project_desc) < 10:
        return description
    
    return project_desc


def find_location_in_barangay(
    region: Optional[str] = None,
    province: Optional[str] = None,
    municipality: Optional[str] = None,
    barangay: Optional[str] = None,
    description: Optional[str] = None
) -> Tuple[Optional[Dict], List[str]]:
    """
    Find location in barangay database using fuzzy search.
    Returns tuple: (location data with PSGC code and hierarchy, list of notes)
    """
    notes = []
    
    # Build search query
    search_parts = []
    
    if barangay:
        search_parts.append(barangay)
    if municipality:
        search_parts.append(municipality)
    if province:
        search_parts.append(province)
    if region:
        search_parts.append(region)
    
    # If we have description but no specific location, try to extract from description
    if description and not any([barangay, municipality, province]):
        extracted = extract_location_from_description(description)
        if extracted.get("barangay"):
            search_parts.insert(0, extracted["barangay"])
            notes.append(f"EXTRACTED_BARANGAY: '{extracted['barangay']}' from description")
        if extracted.get("municipality"):
            search_parts.insert(0, extracted["municipality"])
            notes.append(f"EXTRACTED_MUNICIPALITY: '{extracted['municipality']}' from description")
        if extracted.get("province"):
            search_parts.append(extracted["province"])
            notes.append(f"EXTRACTED_PROVINCE: '{extracted['province']}' from description")
    
    # Store extracted location info for project details extraction
    # (This will be used in the calling function)
    
    if not search_parts:
        notes.append("INSUFFICIENT_SEARCH_DATA: No location data available for search")
        return None, notes
    
    # Try different search strategies
    search_query = ", ".join(search_parts)
    
    # Strategy 1: Try fuzzy search with barangay
    try:
        results = search(
            search_query,
            n=5,
            match_hooks=["barangay", "municipality", "province"],
            threshold=60.0
        )
        
        if results:
            # Get the best match (first result)
            best_match = results[0]
            
            # Check match quality
            match_score = best_match.get("f_0pmb_ratio_score", 0)
            if match_score < 70.0:
                notes.append(f"LOW_CONFIDENCE_MATCH: Match score {match_score:.1f}% (threshold: 70%)")
            
            # Check if multiple matches
            if len(results) > 1:
                notes.append(f"MULTIPLE_MATCHES: Found {len(results)} potential matches, using best match")
            
            # Extract PSGC ID from search result
            psgc_id = best_match.get("psgc_id")
            if psgc_id:
                # Find full location data in BARANGAY_FLAT using PSGC ID
                matched_location = None
                for loc in BARANGAY_FLAT:
                    if loc.get("psgc_id") == psgc_id:
                        matched_location = loc
                        break
                
                if matched_location:
                    notes.append(f"MATCH_FOUND: Found via fuzzy search (PSGC: {psgc_id})")
                    return build_location_hierarchy(matched_location), notes
                else:
                    notes.append(f"PSGC_NOT_FOUND: PSGC ID {psgc_id} not found in BARANGAY_FLAT")
            else:
                notes.append("NO_PSGC_ID: Search result missing PSGC ID")
    except Exception as e:
        notes.append(f"SEARCH_ERROR: Fuzzy search failed - {str(e)}")
    
    # Strategy 2: Direct lookup in BARANGAY_FLAT
    if municipality or barangay:
        search_name = (barangay or municipality).upper()
        matches = []
        for loc in BARANGAY_FLAT:
            if loc["name"].upper() == search_name or search_name in loc["name"].upper():
                matches.append(loc)
        
        if matches:
            if len(matches) > 1:
                notes.append(f"MULTIPLE_DIRECT_MATCHES: Found {len(matches)} direct matches for '{search_name}'")
            notes.append(f"DIRECT_MATCH_FOUND: Found via direct lookup")
            return build_location_hierarchy(matches[0]), notes
        else:
            notes.append(f"DIRECT_LOOKUP_FAILED: No direct match for '{search_name}'")
    
    notes.append("ALL_SEARCH_STRATEGIES_FAILED: Could not find location using any method")
    return None, notes


def build_location_hierarchy(location: Dict) -> Dict:
    """Build full location hierarchy from a location entry."""
    hierarchy = {
        "barangay_name": None,
        "municipality_name": None,
        "province_name": None,
        "region_name": None,
        "psgc_code": location.get("psgc_id", ""),
        "location_type": location.get("type", ""),
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
    max_depth = 10  # Prevent infinite loops
    depth = 0
    
    while current and depth < max_depth:
        parent_id = current.get("parent_psgc_id")
        if not parent_id or parent_id == "0" * len(parent_id):
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


def enrich_project_data(project_data: Dict) -> Dict:
    """Enrich a single project record with barangay data."""
    if "data" not in project_data:
        return project_data
    
    data = project_data["data"]
    enriched_data = data.copy()
    
    # Initialize misc_notes to track parsing issues
    misc_notes = []
    
    # Extract location information
    location = data.get("location", {})
    region = normalize_region_name(location.get("region", ""))
    province = location.get("province", "")
    description = data.get("description", "")
    
    # Check for missing location data
    if not location.get("region"):
        misc_notes.append("MISSING_REGION: No region specified in location object")
    if not location.get("province"):
        misc_notes.append("MISSING_PROVINCE: No province specified in location object")
    if not description:
        misc_notes.append("MISSING_DESCRIPTION: No description field found")
    
    # Try to get municipality from components if available
    municipality = None
    barangay = None
    
    if "components" in data and data["components"]:
        component = data["components"][0]
        if "province" in component:
            province = component.get("province", province)
        if "description" in component:
            # Try to extract from component description
            comp_desc = component.get("description", "")
            extracted = extract_location_from_description(comp_desc)
            if extracted.get("municipality"):
                municipality = extracted["municipality"]
            if extracted.get("barangay"):
                barangay = extracted["barangay"]
    
    # Also try to extract from main description
    extracted_from_desc = extract_location_from_description(description)
    if not municipality and extracted_from_desc.get("municipality"):
        municipality = extracted_from_desc["municipality"]
    if not barangay and extracted_from_desc.get("barangay"):
        barangay = extracted_from_desc["barangay"]
    
    # Extract project details (description minus location)
    project_details = extract_project_details_from_description(description, extracted_from_desc)
    if project_details and project_details != description:
        enriched_data["project_description_clean"] = project_details
        misc_notes.append(f"PROJECT_DETAILS_EXTRACTED: Removed location info from description")
    elif description:
        # If extraction didn't change anything, store original
        enriched_data["project_description_clean"] = description
    
    # Clean province name (remove DEO suffixes, etc.)
    original_province = province
    if province:
        province = re.sub(r'\s+\d+(st|nd|rd|th)\s+DEO.*$', '', province, flags=re.IGNORECASE).strip()
        province = re.sub(r'\s*\([^)]*DEO[^)]*\)', '', province, flags=re.IGNORECASE).strip()
        if province != original_province:
            misc_notes.append(f"PROVINCE_CLEANED: Removed DEO suffix from '{original_province}' -> '{province}'")
    
    # Check for region name normalization issues
    original_region = location.get("region", "")
    if original_region and region != original_region:
        misc_notes.append(f"REGION_NORMALIZED: '{original_region}' -> '{region}'")
    if original_region and not region:
        misc_notes.append(f"REGION_NOT_FOUND: Could not normalize region '{original_region}'")
    
    # Check for missing coordinates
    if not data.get("latitude") and not location.get("coordinates", {}).get("latitude"):
        misc_notes.append("MISSING_COORDINATES: No latitude/longitude found")
    
    # Check for description parsing issues
    if description and not any([municipality, barangay]):
        misc_notes.append("DESCRIPTION_PARSE_FAILED: Could not extract municipality/barangay from description")
    
    # Find location in barangay database
    location_data, search_notes = find_location_in_barangay(
        region=region,
        province=province,
        municipality=municipality,
        barangay=barangay,
        description=description
    )
    
    # Add search-related notes
    misc_notes.extend(search_notes)
    
    # Add enriched fields
    if location_data:
        enriched_data["psgc"] = {
            "barangay_name": location_data.get("barangay_name"),
            "municipality_name": location_data.get("municipality_name"),
            "province_name": location_data.get("province_name"),
            "region_name": location_data.get("region_name"),
            "psgc_code": location_data.get("psgc_code"),
            "location_type": location_data.get("location_type"),
        }
        
        # Check for mismatches between DPWH data and PSGC data
        if province and location_data.get("province_name"):
            if province.upper() not in location_data.get("province_name", "").upper() and \
               location_data.get("province_name", "").upper() not in province.upper():
                misc_notes.append(f"PROVINCE_MISMATCH: DPWH='{province}' vs PSGC='{location_data.get('province_name')}'")
        
        if region and location_data.get("region_name"):
            if region.upper() not in location_data.get("region_name", "").upper() and \
               location_data.get("region_name", "").upper() not in region.upper():
                misc_notes.append(f"REGION_MISMATCH: DPWH='{region}' vs PSGC='{location_data.get('region_name')}'")
    else:
        # Add empty structure if not found
        enriched_data["psgc"] = {
            "barangay_name": None,
            "municipality_name": None,
            "province_name": None,
            "region_name": None,
            "psgc_code": None,
            "location_type": None,
        }
        misc_notes.append("LOCATION_NOT_FOUND: Could not find matching location in barangay database")
    
    # Check for missing components
    if "components" not in data or not data.get("components"):
        misc_notes.append("MISSING_COMPONENTS: No components array found")
    
    # Check for missing bidders
    if "bidders" not in data or not data.get("bidders"):
        misc_notes.append("MISSING_BIDDERS: No bidders array found")
    
    # Add misc_notes field
    enriched_data["misc_notes"] = misc_notes if misc_notes else None
    
    return {
        **project_data,
        "data": enriched_data
    }


def process_json_file(input_file: Path, output_file: Path):
    """Process a single JSON file and enrich it."""
    print(f"Processing: {input_file.name}")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        enriched = enrich_project_data(data)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(enriched, f, indent=2, ensure_ascii=False)
        
        # Print summary
        psgc_data = enriched.get("data", {}).get("psgc", {})
        if psgc_data.get("psgc_code"):
            print(f"  ✓ Enriched: {psgc_data.get('barangay_name') or psgc_data.get('municipality_name') or 'Unknown'}")
            print(f"    PSGC Code: {psgc_data.get('psgc_code')}")
        else:
            print(f"  ⚠ Could not find location match")
        
    except Exception as e:
        print(f"  ✗ Error processing {input_file.name}: {e}")


def main():
    """Main function."""
    print("="*60)
    print("DPWH Data Enrichment with Barangay PSGC Data")
    print("="*60)
    print(f"Using barangay package: https://github.com/bendlikeabamboo/barangay/")
    print()
    
    # Process all sample files (recursively find all JSON files in samples directory)
    if not SAMPLES_DIR.exists():
        print(f"Samples directory not found: {SAMPLES_DIR}")
        return
    
    json_files = list(SAMPLES_DIR.rglob("*.json"))
    if not json_files:
        print(f"No JSON files found in: {SAMPLES_DIR}")
        return
    
    print(f"Found {len(json_files)} sample files to process\n")
    
    success_count = 0
    error_count = 0
    
    for json_file in sorted(json_files):
        # Preserve directory structure in output
        relative_path = json_file.relative_to(SAMPLES_DIR)
        output_file = OUTPUT_DIR / relative_path
        output_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            process_json_file(json_file, output_file)
            success_count += 1
        except Exception as e:
            print(f"  ✗ Error: {e}")
            error_count += 1
        print()
    
    print("="*60)
    print(f"Summary: {success_count} files processed successfully, {error_count} errors")
    print(f"Enriched files saved to: {OUTPUT_DIR}")
    print("="*60)


if __name__ == "__main__":
    main()

