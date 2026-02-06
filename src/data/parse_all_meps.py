"""
MEPS Data Parser - Unified script to parse all MEPS data files.
Supports both:
1. ASCII (.dat) files with SAS programming statements
2. SPSS Transport (.ssp) files (requires pyreadstat)

Usage:
    python src/data/parse_all_meps.py

Configuration:
    RAW_DIR: Directory containing raw .zip/.ssp files
    PROCESSED_DIR: Output directory for .parquet files
"""

import pandas as pd
import re
import zipfile
import os
from pathlib import Path

# Configuration
RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed_v2")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Files we need to process
REQUIRED_FILES = {
    # Panel Longitudinal Files (for Y1→Y2 cost prediction)
    'h172': {'type': 'long', 'panel': 18, 'years': '2013-2014', 'desc': 'Panel 18 Longitudinal'},
    'h183': {'type': 'long', 'panel': 19, 'years': '2014-2015', 'desc': 'Panel 19 Longitudinal'},
    'h193': {'type': 'long', 'panel': 20, 'years': '2015-2016', 'desc': 'Panel 20 Longitudinal'},
    'h202': {'type': 'long', 'panel': 21, 'years': '2016-2017', 'desc': 'Panel 21 Longitudinal'},
    'h210': {'type': 'long', 'panel': 22, 'years': '2017-2018', 'desc': 'Panel 22 Longitudinal'},
    'h217': {'type': 'long', 'panel': 23, 'years': '2018-2019', 'desc': 'Panel 23 Longitudinal'},
    
    # Full Year Consolidated Files (for Y1 expenses when longitudinal is incomplete)
    'h201': {'type': 'fullyear', 'year': 2017, 'desc': '2017 Full Year Consolidated'},
    'h209': {'type': 'fullyear', 'year': 2018, 'desc': '2018 Full Year Consolidated'},
    
    # Medical Conditions Files
    'h162': {'type': 'cond', 'year': 2013, 'desc': '2013 Medical Conditions'},
    'h170': {'type': 'cond', 'year': 2014, 'desc': '2014 Medical Conditions'},
    'h180': {'type': 'cond', 'year': 2015, 'desc': '2015 Medical Conditions'},
    'h190': {'type': 'cond', 'year': 2016, 'desc': '2016 Medical Conditions'},
    'h199': {'type': 'cond', 'year': 2017, 'desc': '2017 Medical Conditions'},
    'h207': {'type': 'cond', 'year': 2018, 'desc': '2018 Medical Conditions'},
    
    # Prescribed Medicines Files
    'h160a': {'type': 'meds', 'year': 2013, 'desc': '2013 Prescribed Medicines'},
    'h168a': {'type': 'meds', 'year': 2014, 'desc': '2014 Prescribed Medicines'},
    'h178a': {'type': 'meds', 'year': 2015, 'desc': '2015 Prescribed Medicines'},
    'h188a': {'type': 'meds', 'year': 2016, 'desc': '2016 Prescribed Medicines'},
    'h197a': {'type': 'meds', 'year': 2017, 'desc': '2017 Prescribed Medicines'},
    'h206a': {'type': 'meds', 'year': 2018, 'desc': '2018 Prescribed Medicines'},
}


def parse_sas_instructions(sas_file_path):
    """Parse SAS programming statements to get column specs."""
    colspecs = []
    names = []
    dtypes = {}
    
    input_pattern = re.compile(r'@(\d+)\s+([A-Z0-9_]+)\s+(\$?)(\d+)\.')
    
    is_input_section = False
    
    with open(sas_file_path, 'r', encoding='latin1') as f:
        for line in f:
            line = line.strip()
            
            if line.startswith('INPUT'):
                is_input_section = True
                continue
            elif line.startswith(';'):
                is_input_section = False
                continue
            
            if is_input_section:
                match = input_pattern.search(line)
                if match:
                    start_sas = int(match.group(1))
                    var_name = match.group(2)
                    is_char = (match.group(3) == '$')
                    length = int(match.group(4))
                    
                    start_py = start_sas - 1
                    end_py = start_py + length
                    
                    colspecs.append((start_py, end_py))
                    names.append(var_name)
                    dtypes[var_name] = 'str' if is_char else 'float32'

    return {'colspecs': colspecs, 'names': names, 'dtypes': dtypes}


def process_dat_file(file_id):
    """Process ASCII .dat file with SAS statements."""
    # Find files (case insensitive) - try multiple naming patterns
    zip_patterns = [
        f"{file_id}dat.zip", f"{file_id.upper()}dat.zip", f"{file_id}DAT.zip",
        f"{file_id}ssp.zip", f"{file_id.upper()}ssp.zip", f"{file_id}SSP.zip"  # Some files use ssp.zip
    ]
    sas_patterns = [
        f"{file_id}sp.txt", f"{file_id}su.txt",  # Common patterns
        f"{file_id}spu.txt", f"{file_id.upper()}sp.txt", 
        f"{file_id}asp.txt", f"{file_id.upper()}su.txt"
    ]
    
    zip_path = None
    sas_path = None
    
    for pattern in zip_patterns:
        p = RAW_DIR / pattern
        if p.exists():
            zip_path = p
            break
    
    for pattern in sas_patterns:
        p = RAW_DIR / pattern
        if p.exists():
            sas_path = p
            break
    
    if not zip_path:
        return None, f"ZIP file not found"
    if not sas_path:
        return None, f"SAS statements not found (need {file_id}sp.txt)"
    
    print(f"  Parsing: {zip_path.name} + {sas_path.name}")
    
    # Parse SAS
    meta = parse_sas_instructions(sas_path)
    
    # Extract and read DAT (or SSP-contained DAT)
    with zipfile.ZipFile(zip_path, 'r') as z:
        # Look for .dat or .DAT file inside
        dat_files = [n for n in z.namelist() if n.lower().endswith('.dat')]
        if not dat_files:
            return None, f"No .dat file in ZIP ({zip_path.name})"
        z.extract(dat_files[0], path=RAW_DIR)
        dat_path = RAW_DIR / dat_files[0]
    
    if not dat_path.exists():
        # Try case-insensitive search
        for f in RAW_DIR.iterdir():
            if f.name.lower() == dat_files[0].lower():
                dat_path = f
                break
    
    try:
        df = pd.read_fwf(dat_path, colspecs=meta['colspecs'], names=meta['names'], dtype=str)
        
        # Convert numeric columns
        for col, dtype in meta['dtypes'].items():
            if dtype == 'float32' and col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df, None
    finally:
        if dat_path.exists():
            os.remove(dat_path)


def process_ssp_file(file_id):
    """Process SPSS Transport (.ssp) file."""
    try:
        import pyreadstat
        HAS_PYREADSTAT = True
    except ImportError:
        HAS_PYREADSTAT = False
    
    # Find SSP file (case insensitive) - check multiple patterns
    ssp_patterns = [
        f"{file_id}.ssp", f"{file_id.upper()}.ssp", f"{file_id}.SSP",
        f"{file_id.upper()}.SSP", f"{file_id.lower()}.ssp"
    ]
    
    ssp_path = None
    for pattern in ssp_patterns:
        p = RAW_DIR / pattern
        if p.exists():
            ssp_path = p
            break
    
    if not ssp_path:
        return None, f"SSP file not found"
    
    if not HAS_PYREADSTAT:
        return None, f"SSP found ({ssp_path.name}) but pyreadstat not installed"
    
    print(f"  Reading: {ssp_path.name}")
    df, meta = pyreadstat.read_xport(str(ssp_path))
    return df, None


def process_file(file_id):
    """Try to process a file using available method."""
    # Try DAT + SAS first (more reliable, SSP V9 format often fails)
    df, err_dat = process_dat_file(file_id)
    if df is not None:
        return df, 'dat'
    
    # Fallback to SSP (transport format)
    df, err_ssp = process_ssp_file(file_id)
    if df is not None:
        return df, 'ssp'
    
    # Return the more informative error
    return None, err_dat if 'SAS statements' not in str(err_dat) else err_ssp


def main():
    print("="*60)
    print("MEPS Data Parser")
    print("="*60)
    print(f"Raw Dir: {RAW_DIR}")
    print(f"Output Dir: {PROCESSED_DIR}")
    print()
    
    results = {'success': [], 'failed': [], 'skipped': []}
    
    for file_id, info in REQUIRED_FILES.items():
        out_path = PROCESSED_DIR / f"{file_id}.parquet"
        
        # Skip if already processed
        if out_path.exists():
            print(f"[SKIP] {file_id}: Already processed")
            results['skipped'].append(file_id)
            continue
        
        print(f"[PROC] {file_id}: {info['desc']}")
        
        df, method = process_file(file_id)
        
        if df is not None:
            df.to_parquet(out_path, index=False)
            print(f"  -> Saved {len(df):,} rows to {out_path.name} (via {method})")
            results['success'].append(file_id)
        else:
            print(f"  -> FAILED: {method}")
            results['failed'].append((file_id, method))
    
    print()
    print("="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Success: {len(results['success'])} files")
    print(f"Skipped: {len(results['skipped'])} files (already exist)")
    print(f"Failed: {len(results['failed'])} files")
    
    if results['failed']:
        print("\nFailed files (need additional downloads):")
        for fid, err in results['failed']:
            print(f"  - {fid}: {err}")


if __name__ == '__main__':
    main()
