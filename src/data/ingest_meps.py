"""
MEPS Data Ingestion Script for Group 5 (Panels 18-22, Years 2013-2018).
Downloads ASCII (.dat) data files and SAS Programming Statements (.txt) from AHRQ.
"""

import requests
import os
import zipfile
import time
from pathlib import Path

# --- Configuration for Group 5 ---
# MEPS Base URL patterns
# NOTE: MEPS has two main storage locations. We must try both.
BASE_URL_1 = "https://meps.ahrq.gov/data_files/pufs"
BASE_URL_2 = "https://meps.ahrq.gov/data_stats/download_data/pufs"

# File Mappings
FILES_TO_DOWNLOAD = {
    # Longitudinal Files (The Core: 2-year tracking)
    "longitudinal": [
        {"id": "h172", "label": "Panel 18 (2013-2014)"},
        {"id": "h183", "label": "Panel 19 (2014-2015)"},
        {"id": "h193", "label": "Panel 20 (2015-2016)"},
        {"id": "h202", "label": "Panel 21 (2016-2017)"},
        {"id": "h209", "label": "Panel 22 (2017-2018)"}
    ],
    # Event Files (Needed for Opioid & Mental Health Specifics)
    # We download the corresponding years for the panels above.
    "events": [
        # Medical Conditions
        {"id": "h162", "type": "cond", "year": 2013},
        {"id": "h170", "type": "cond", "year": 2014},
        {"id": "h180", "type": "cond", "year": 2015},
        {"id": "h190", "type": "cond", "year": 2016},
        {"id": "h199", "type": "cond", "year": 2017},
        {"id": "h207", "type": "cond", "year": 2018},
        
        # Prescribed Medicines
        {"id": "h160a", "type": "meds", "year": 2013},
        {"id": "h168a", "type": "meds", "year": 2014},
        {"id": "h178a", "type": "meds", "year": 2015},
        {"id": "h188a", "type": "meds", "year": 2016},
        {"id": "h197a", "type": "meds", "year": 2017},
        {"id": "h206a", "type": "meds", "year": 2018}
    ]
}

RAW_DIR = Path("data/raw")

def download_url(url, dest_path):
    if dest_path.exists():
        print(f"Skipping {dest_path.name}, already exists.")
        return True
    
    print(f"Downloading {url}...")
    try:
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Saved to {dest_path}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to download {url}: {e}")
        return False

def ingest_group_data():
    """Main ingestion logic."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    
    all_files = FILES_TO_DOWNLOAD["longitudinal"] + FILES_TO_DOWNLOAD["events"]
    
    for file_info in all_files:
        fid = file_info["id"]
        
        # 1. Download ASCII Data Zip
        # Try both base URLs and common naming patterns
        # Pattern 1: /hXXXdat.zip (Old style)
        # Pattern 2: /hXXX/hXXXdat.zip (New style, inside folder)
        zip_patterns = [
            f"{BASE_URL_1}/{fid}dat.zip",
            f"{BASE_URL_2}/{fid}/{fid}dat.zip",
            f"{BASE_URL_1}/{fid}/{fid}dat.zip"
        ]
        
        zip_downloaded = False
        zip_dest = RAW_DIR / f"{fid}dat.zip"
        
        for url in zip_patterns:
            if download_url(url, zip_dest):
                zip_downloaded = True
                break
        
        if not zip_downloaded:
            print(f"ERROR: Could not find DATA ZIP for {fid}")
            continue # If no data, no point downloading SAS statements

        # 2. Download SAS Programming Statements (The "Decoder Ring" for ASCII)
        # Try multiple patterns because MEPS naming is inconsistent
        # Priority 1: standard 'sp.txt' 
        # Priority 2: 'su.txt' (older style)
        # Priority 3: 'ssp' (sometimes no extension)
        
        success = False
        
        # New robust logic: Check both Base URLs + Check Inside Subfolder + Check All Extensions
        sas_patterns = []
        extensions = ["sp.txt", "su.txt", ".ssp", ".sas", "stu.txt"]
        
        for ext in extensions:
            # Root level
            sas_patterns.append(f"{BASE_URL_1}/{fid}{ext}")
            # Inside subfolder (Base 2 is usually structured /pufs/hXXX/hXXXsp.txt)
            sas_patterns.append(f"{BASE_URL_2}/{fid}/{fid}{ext}")
            sas_patterns.append(f"{BASE_URL_1}/{fid}/{fid}{ext}")
        
        for url in sas_patterns:
            # Always save as sp.txt locally for consistency so parser knows what to read
            sas_dest = RAW_DIR / f"{fid}sp.txt" 
            
            if download_url(url, sas_dest):
                success = True
                break
        
        if not success:
            print(f"WARNING: Could not find SAS statements for {fid}")
        
        # Small delay to be polite to the server
        time.sleep(1)

if __name__ == "__main__":
    print(f"Starting ingestion for Group 5 (Panels 18-22)...")
    ingest_group_data()
    print("Done! Check data/raw/ folder.")
