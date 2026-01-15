"""
ASCII Parser for MEPS Data.
Parses SAS Programming Statements (.txt) to extract column specifications (names, start/end positions, labels).
Reads fixed-width .dat files and processes them into optimized Parquet format.
"""

import pandas as pd
import re
import zipfile
import os
from pathlib import Path

def parse_sas_instructions(sas_file_path):
    """
    Parses a SAS input statement file to extract column names, widths/positions, and labels.
    Args:
        sas_file_path (Path): Path to the .txt file containing SAS commands.
        
    Returns:
        dict: containing:
            'colspecs': list of (start, end) tuples for pd.read_fwf (0-based)
            'names': list of column names
            'dtypes': dictionary of {col_name: type_str}
            'labels': dictionary of {col_name: description}
    """
    colspecs = []
    names = []
    dtypes = {}
    labels = {}
    
    # Regex patterns
    # Matches: @1 DUPERSID $8.  or  @9 AGE13X 2.
    # Group 1: Start Pos, Group 2: Var Name, Group 3: '$' (if char), Group 4: Length
    input_pattern = re.compile(r'@(\d+)\s+([A-Z0-9_]+)\s+(\$?)(\d+)\.')
    
    # Matches: DUPERSID = "PERSON ID (DUID + PID)"
    label_pattern = re.compile(r'([A-Z0-9_]+)\s*=\s*"(.*)"')
    
    is_input_section = False
    is_label_section = False
    
    with open(sas_file_path, 'r', encoding='latin1') as f:
        for line in f:
            line = line.strip()
            
            # Detect Sections
            if line.startswith('INPUT'):
                is_input_section = True
                is_label_section = False
                continue
            elif line.startswith('LABEL'):
                is_label_section = True
                is_input_section = False
                continue
            elif line.startswith(';'):
                is_input_section = False
                is_label_section = False
                continue
            
            # Parse INPUT section
            if is_input_section:
                match = input_pattern.search(line)
                if match:
                    start_sas = int(match.group(1))
                    var_name = match.group(2)
                    is_char = (match.group(3) == '$')
                    length = int(match.group(4))
                    
                    # Convert SAS 1-based start to Python 0-based start
                    start_py = start_sas - 1
                    end_py = start_py + length
                    
                    colspecs.append((start_py, end_py))
                    names.append(var_name)
                    
                    # Store dtype preference
                    if is_char:
                        dtypes[var_name] = 'str'
                    else:
                        # We'll read as float first to handle NaNs, then downcast later if needed
                        dtypes[var_name] = 'float32' 

            # Parse LABEL section
            if is_label_section:
                match = label_pattern.search(line)
                if match:
                    var_name = match.group(1)
                    desc = match.group(2)
                    labels[var_name] = desc

    return {
        'colspecs': colspecs,
        'names': names,
        'dtypes': dtypes,
        'labels': labels
    }

def process_ascii_file(zip_path, sas_path, output_dir):
    """
    Full pipeline: Unzip .dat -> Parse SAS -> Read FWF -> Save Parquet -> Cleanup.
    """
    zip_path = Path(zip_path)
    sas_path = Path(sas_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    file_id = sas_path.stem.replace('sp', '') # e.g. h172sp -> h172
    
    print(f"Processing {file_id}...")
    
    # 1. Parse Metadata
    print(f"  - Parsing SAS instructions from {sas_path.name}...")
    meta = parse_sas_instructions(sas_path)
    
    # 2. Extract .dat file from zip
    with zipfile.ZipFile(zip_path, 'r') as z:
        # Assuming only one .dat file inside, or finding the .dat
        dat_filename = [n for n in z.namelist() if n.endswith('.dat') or n.endswith('.DAT')][0]
        print(f"  - Extracting {dat_filename}...")
        z.extract(dat_filename, path=zip_path.parent)
        dat_path = zip_path.parent / dat_filename
        
    # 3. Read Fixed Width File (Chunks to convert to consistent types)
    print(f"  - Reading ASCII data (this may take a while)...")
    try:
        # Read as string first to avoid parsing errors, then convert
        df = pd.read_fwf(
            dat_path, 
            colspecs=meta['colspecs'], 
            names=meta['names'],
            header=None,
            dtype=str  # Read all as string first to be safe
        )
        
        # Convert numeric columns
        for col, dtype in meta['dtypes'].items():
            if dtype == 'float32':
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        print(f"  - Loaded {len(df)} rows, {len(df.columns)} columns.")

        # 4. Save to Parquet (Preserve Schema)
        out_file = output_dir / f"{file_id}.parquet"
        
        # Store column labels in metadata (custom attribute is tricky in parquet, 
        # so we often save a separate json or just rely on the codebook)
        # Here we just save the data.
        df.to_parquet(out_file, index=False)
        print(f"  - Saved to {out_file}")
        
    finally:
        # 5. Cleanup huge .dat file
        if dat_path.exists():
            os.remove(dat_path)
            print(f"  - Cleaned up raw .dat file.")

def run_batch_processing():
    """
    Finds all matching pairs (zip + txt) in data/raw and processes them.
    """
    raw_dir = Path("data/raw")
    processed_dir = Path("data/processed")
    
    # Identify all .txt SAS files (the anchors)
    sas_files = list(raw_dir.glob("*sp.txt"))
    
    print(f"Found {len(sas_files)} datasets to process.")
    
    for sas_file in sas_files:
        # Construct corresponding zip filename (e.g., h172sp.txt -> h172dat.zip)
        # Note: Sometimes pattern is slightly different (h172.dat or h172dat.zip)
        # We assume the standard download pattern from our ingest script: {id}dat.zip
        file_id = sas_file.stem.replace('sp', '')  # h172
        zip_file = raw_dir / f"{file_id}dat.zip"
        
        if not zip_file.exists():
            print(f"Warning: Data zip for {file_id} not found at {zip_file}. Skipping.")
            continue
            
        print(f"\n>>> Processing Batch: {file_id}")
        try:
            process_ascii_file(zip_file, sas_file, processed_dir)
        except Exception as e:
            print(f"ERROR processing {file_id}: {e}")

if __name__ == '__main__':
    run_batch_processing()
