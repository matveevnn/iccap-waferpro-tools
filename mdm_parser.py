import pandas as pd
import re


def mdm_inputs(filename):
    """Return list of input variable names from MDM file."""
    inputs = []
    section = None

    with open(filename, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            stripped = line.strip()

            if stripped == "ICCAP_INPUTS":
                section = "inputs"
                continue
            if stripped == "ICCAP_OUTPUTS":
                break

            if section == "inputs" and stripped:
                inputs.append(stripped.split()[0])

    return inputs


def mdm_outputs(filename):
    """Return list of output variable names from MDM file."""
    outputs = []
    section = None

    with open(filename, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            stripped = line.strip()

            if stripped == "ICCAP_OUTPUTS":
                section = "outputs"
                continue
            if stripped == "ICCAP_VALUES":
                break

            if section == "outputs" and stripped:
                outputs.append(stripped.split()[0])

    return outputs


def mdm_values(filename):
    """Return dictionary of metadata values from ICCAP_VALUES section."""
    values = {}
    section = None

    with open(filename, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            stripped = line.strip()

            if stripped == "ICCAP_VALUES":
                section = "values"
                continue
            if stripped == "END_HEADER":
                break

            if section == "values" and stripped:
                # Parse "Key "Value"" format
                match = re.match(r'(\w+)\s+"([^"]*)"', stripped)
                if match:
                    values[match.group(1)] = match.group(2)

    return values


def mdm_to_dataframe(filename):
    """
    Parse all measurement data blocks from MDM file into a single DataFrame.
    
    Each BEGIN_DB/END_DB block is parsed and combined. 
    ICCAP_VAR values are added as columns to identify each sweep condition.
    
    Returns:
        pd.DataFrame: Combined measurement data with all sweeps
    """
    all_data = []
    
    with open(filename, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    # Split into data blocks
    blocks = re.findall(r'BEGIN_DB(.*?)END_DB', content, re.DOTALL)
    
    for block in blocks:
        lines = block.strip().split('\n')
        
        # Extract ICCAP_VAR values for this block
        block_vars = {}
        data_lines = []
        columns = None
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
                
            # Parse ICCAP_VAR lines
            if stripped.startswith('ICCAP_VAR'):
                parts = stripped.split()
                if len(parts) >= 3:
                    var_name = parts[1]
                    var_value = float(parts[2])
                    block_vars[var_name] = var_value
            
            # Parse column header line (starts with #)
            elif stripped.startswith('#'):
                columns = stripped[1:].split()
            
            # Parse data lines (start with number or negative sign)
            elif columns and (stripped[0].isdigit() or stripped[0] == '-'):
                values = stripped.split()
                if len(values) == len(columns):
                    data_lines.append([float(v) for v in values])
        
        # Create DataFrame for this block
        if columns and data_lines:
            block_df = pd.DataFrame(data_lines, columns=columns)
            
            # Add ICCAP_VAR columns
            for var_name, var_value in block_vars.items():
                block_df[var_name] = var_value
            
            all_data.append(block_df)
    
    # Combine all blocks
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    
    return pd.DataFrame()


def mdm_get_block(filename, block_index=0):
    """
    Get a specific data block by index.
    
    Args:
        filename: Path to MDM file
        block_index: Which block to return (0-based)
    
    Returns:
        pd.DataFrame: Single measurement block data
    """
    with open(filename, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    blocks = re.findall(r'BEGIN_DB(.*?)END_DB', content, re.DOTALL)
    
    if block_index >= len(blocks):
        raise IndexError(f"Block index {block_index} out of range. File has {len(blocks)} blocks.")
    
    block = blocks[block_index]
    lines = block.strip().split('\n')
    
    block_vars = {}
    data_lines = []
    columns = None
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
            
        if stripped.startswith('ICCAP_VAR'):
            parts = stripped.split()
            if len(parts) >= 3:
                block_vars[parts[1]] = float(parts[2])
        elif stripped.startswith('#'):
            columns = stripped[1:].split()
        elif columns and (stripped[0].isdigit() or stripped[0] == '-'):
            values = stripped.split()
            if len(values) == len(columns):
                data_lines.append([float(v) for v in values])
    
    if columns and data_lines:
        df = pd.DataFrame(data_lines, columns=columns)
        for var_name, var_value in block_vars.items():
            df[var_name] = var_value
        return df
    
    return pd.DataFrame()

def mdm_block_count(filename):
    """Return the number of data blocks in the MDM file."""
    with open(filename, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    return len(re.findall(r'BEGIN_DB', content))
