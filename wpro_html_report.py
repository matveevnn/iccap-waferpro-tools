"""
WaferPro CSV Measurement Report Generator

Generates a complete HTML report with:
- Main index page with measurement overview and statistics
- Individual HTML pages for each MDM file (using mdm_to_html)
- Navigation between all pages
"""

import re
import json
import webbrowser
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime
from collections import defaultdict

# Import the MDM viewer generator
from mdm_to_html import generate_html_viewer


class WProReportGenerator:
    """Generator for HTML measurement reports from WaferPro CSV files."""
    
    def __init__(self, filepath: str):
        """
        Initialize the report generator with a WPro.csv file.
        
        Args:
            filepath: Path to the WPro.csv file
        """
        self.filepath = Path(filepath)
        self.header_info: Dict[str, str] = {}
        self.meas_conditions: Dict[str, str] = {}
        self._df: Optional[pd.DataFrame] = None
        self._parse_file()
    
    def _parse_file(self):
        """Parse the CSV file header and data."""
        with open(self.filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        in_meas_condition = False
        meas_condition_header = []
        skip_rows = 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            if not stripped.startswith('*'):
                skip_rows = i
                break
            
            content = re.sub(r'^\*[,\s]*', '', stripped).strip()
            
            if content.startswith('Start Meas Condition Description'):
                in_meas_condition = True
                continue
            elif content.startswith('End Meas Condition Description'):
                in_meas_condition = False
                continue
            elif content == 'HEADER_START' or content == 'HEADER_END':
                continue
            
            if in_meas_condition:
                if not meas_condition_header:
                    meas_condition_header = [h.strip() for h in content.split(',') if h.strip()]
                else:
                    values = [v.strip() for v in content.split(',') if v.strip()]
                    if values and meas_condition_header:
                        for j, val in enumerate(values):
                            if j < len(meas_condition_header):
                                self.meas_conditions[meas_condition_header[j]] = val
            else:
                if ',' in content:
                    parts = content.split(',', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        if key and value:
                            self.header_info[key] = value
        
        self._df = pd.read_csv(self.filepath, skiprows=skip_rows)
    
    @property
    def dataframe(self) -> pd.DataFrame:
        return self._df
    
    @property
    def lot_name(self) -> str:
        return self.header_info.get('Lot', 'Unknown')
    
    def get_result_columns(self) -> List[str]:
        columns = self._df.columns.tolist()
        try:
            start_idx = columns.index('$')
            end_idx = columns.index('ResultRead')
            return columns[start_idx + 1:end_idx]
        except ValueError:
            return []
    
    def get_wafer_summary(self) -> List[Dict[str, Any]]:
        summary = []
        for wafer in self._df['Wafer'].unique():
            wafer_data = self._df[self._df['Wafer'] == wafer]
            summary.append({
                'wafer': str(wafer),  # Convert to string to avoid numpy type issues
                'die_count': wafer_data['Die'].nunique(),
                'temperatures': sorted(wafer_data['Temperature (C)'].unique().tolist()),
                'blocks': wafer_data['Block'].unique().tolist(),
                'subsites': wafer_data['Subsite'].unique().tolist()
            })
        return summary
    
    def get_temperature_summary(self) -> Dict[Any, int]:
        result = {}
        for temp in sorted(self._df['Temperature (C)'].unique()):
            result[temp] = self._df[self._df['Temperature (C)'] == temp]['Die'].nunique()
        return result
    
    def get_parameter_statistics(self) -> Dict[str, Dict[str, float]]:
        result_columns = self.get_result_columns()
        stats = {}
        
        for col in result_columns:
            if col in self._df.columns:
                data = pd.to_numeric(self._df[col], errors='coerce').dropna()
                if len(data) > 0:
                    stats[col] = {
                        'count': len(data),
                        'mean': float(data.mean()),
                        'std': float(data.std()) if len(data) > 1 else 0,
                        'min': float(data.min()),
                        'max': float(data.max()),
                        'median': float(data.median()),
                        'cv': float(data.std() / data.mean() * 100) if data.mean() != 0 else 0
                    }
        return stats
    
    def get_measurements_table(self) -> Dict[str, Any]:
        """
        Get pivot table structure with Wafer, Temperature, Device, Parameter as rows
        and Die values as columns with parameter values.
        Returns: {
            'dies': [list of die names],
            'rows': [{
                'Wafer': ...,
                'Temperature': ...,
                'Device': ...,
                'Parameter': ...,
                'values': {die_name: value}
            }]
        }
        """
        result_columns = self.get_result_columns()
        
        # Get all unique dies
        all_dies = sorted(self._df['Die'].unique().tolist())
        
        # Dictionary to store rows: key is (Wafer, Temperature, Device, Parameter)
        rows_dict = {}
        
        for idx, row in self._df.iterrows():
            wafer = str(row.get('Wafer', '') or '')
            temperature = str(row.get('Temperature (C)', '') or '')
            die = str(row.get('Die', '') or '')
            name = str(row.get('Name', '') or '')
            
            # For each parameter column
            for param in result_columns:
                if param in row:
                    value = row[param]
                    # Skip if value is NaN or empty
                    if pd.isna(value) or value == '':
                        continue
                    
                    # Parameter is just the parameter name (without Name)
                    parameter = param
                    
                    # Create unique key for this row
                    row_key = (wafer, str(temperature), name, parameter)
                    
                    # Initialize row if doesn't exist
                    if row_key not in rows_dict:
                        rows_dict[row_key] = {
                            'Wafer': wafer,
                            'Temperature': temperature,
                            'Device': name,
                            'Parameter': parameter,
                            'values': {}
                        }
                    
                    # Store value for this die
                    rows_dict[row_key]['values'][die] = value
        
        # Convert to list of rows and calculate statistics
        rows = []
        for row_data in rows_dict.values():
            values = row_data['values']
            # Extract numeric values
            numeric_values = []
            for die, val in values.items():
                try:
                    num_val = float(val)
                    if not pd.isna(num_val):
                        numeric_values.append(num_val)
                except (ValueError, TypeError):
                    pass
            
            # Calculate statistics
            if numeric_values:
                stats = {
                    'Min': float(min(numeric_values)),
                    'Max': float(max(numeric_values)),
                    'Average': float(np.mean(numeric_values)),
                    'Median': float(np.median(numeric_values)),
                    'StdDev': float(np.std(numeric_values)) if len(numeric_values) > 1 else 0.0
                }
            else:
                stats = {
                    'Min': None,
                    'Max': None,
                    'Average': None,
                    'Median': None,
                    'StdDev': None
                }
            
            row_data['stats'] = stats
            rows.append(row_data)
        
        return {
            'dies': all_dies,
            'rows': rows
        }


def format_number(num: float) -> str:
    """Format a number for display."""
    if num == 0:
        return '0'
    abs_val = abs(num)
    if abs_val < 1e-12 or abs_val >= 1e6:
        return f'{num:.4e}'
    if abs_val < 0.001:
        return f'{num:.4e}'
    return f'{num:.6g}'


def find_mdm_files(lot_folder: Path) -> List[Path]:
    """Find all MDM files in the lot folder."""
    return list(lot_folder.rglob('*.mdm'))


def organize_mdm_files(mdm_files: List[Path], lot_folder: Path) -> Dict:
    """
    Organize MDM files into a hierarchical structure.
    Returns: {wafer: {temperature: {die: {meas_group: [files]}}}}
    """
    structure = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    
    for mdm_path in mdm_files:
        # Get relative path from lot folder
        rel_path = mdm_path.relative_to(lot_folder)
        parts = rel_path.parts
        
        # Expected structure: Wafer_1/T27/WholeDie/N/X0-Y0/MeasGroup/file.mdm
        if len(parts) >= 6:
            wafer = parts[0]  # Wafer_1
            temp = parts[1]   # T27
            die = parts[4]    # X0-Y0
            meas_group = parts[5]  # WPro_MOSFET_DC~WX_DC_MeasGroup1
            
            structure[wafer][temp][die][meas_group].append(mdm_path)
    
    return structure


def generate_mdm_html_files(mdm_files: List[Path], lot_folder: Path, report_folder: Path) -> Dict[Path, Path]:
    """
    Generate HTML files for all MDM files, maintaining folder structure.
    Returns a mapping of MDM path to HTML path.
    """
    mdm_to_html = {}
    
    for mdm_path in mdm_files:
        # Get relative path from lot folder
        rel_path = mdm_path.relative_to(lot_folder)
        
        # Create corresponding path in report folder
        html_rel_path = rel_path.with_suffix('.html')
        html_path = report_folder / html_rel_path
        
        # Create parent directories
        html_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Generate HTML using mdm_to_html
            generate_html_viewer(str(mdm_path), str(html_path), auto_open=False)
            mdm_to_html[mdm_path] = html_path
            print(f"  Generated: {html_rel_path}")
        except Exception as e:
            print(f"  Error generating {rel_path}: {e}")
    
    return mdm_to_html


def generate_main_report(generator: WProReportGenerator, 
                         report_folder: Path,
                         mdm_structure: Dict,
                         mdm_to_html: Dict[Path, Path],
                         lot_folder: Path,
                         mdm_files_count: int = 0) -> Path:
    """Generate the main index.html report page."""
    
    header_info = generator.header_info
    wafer_summary = generator.get_wafer_summary()
    temp_summary = generator.get_temperature_summary()
    
    total_dies = generator.dataframe['Die'].nunique()
    
    # Build navigation tree
    nav_html = build_navigation_tree(mdm_structure, mdm_to_html, lot_folder, report_folder)
    
    # Build stat cards
    wafer_list = ', '.join([str(w['wafer']) for w in wafer_summary])  # Ensure string conversion
    temp_list = ', '.join([str(t) + '°C' for t in temp_summary.keys()])
    
    # Get measurements table data (pivot structure)
    measurements_data = generator.get_measurements_table()
    all_dies = measurements_data['dies']
    table_rows_data = measurements_data['rows']
    
    # Get unique values for filters (ensure string conversion to avoid numpy type issues)
    unique_wafers = sorted(set([str(row['Wafer']) for row in table_rows_data]))
    unique_temperatures = sorted(set([str(row['Temperature']) for row in table_rows_data]))
    unique_devices = sorted(set([str(row['Device']) for row in table_rows_data if row.get('Device')]))
    unique_params = sorted(set([str(row['Parameter']) for row in table_rows_data]))
    
    # Build filter checkboxes
    wafer_checkboxes = ''.join([f'<label class="checkbox-item"><input type="checkbox" value="{w}"><span>{w}</span></label>' for w in unique_wafers])
    temp_checkboxes = ''.join([f'<label class="checkbox-item"><input type="checkbox" value="{t}"><span>{t}</span></label>' for t in unique_temperatures])
    device_checkboxes = ''.join([f'<label class="checkbox-item"><input type="checkbox" value="{d}"><span>{d}</span></label>' for d in unique_devices])
    param_checkboxes = ''.join([f'<label class="checkbox-item"><input type="checkbox" value="{p}"><span>{p}</span></label>' for p in unique_params])
    
    # Build table header with Die columns and statistics columns
    die_columns = ''.join([f'<th class="mono">{die}</th>' for die in all_dies])
    
    # Build measurements table rows with statistics
    table_rows = ''
    for row_data in table_rows_data:
        wafer = row_data['Wafer']
        temperature = row_data['Temperature']
        device = row_data.get('Device', '')
        parameter = row_data.get('Parameter', '')
        values = row_data['values']
        stats = row_data['stats']
        
        # Build value cells for each die
        die_cells = ''
        for die in all_dies:
            value = values.get(die, '')
            if value != '':
                try:
                    formatted_value = format_number(float(value)) if isinstance(value, (int, float)) else str(value)
                except (ValueError, TypeError):
                    formatted_value = str(value)
                die_cells += f'<td class="mono">{formatted_value}</td>'
            else:
                die_cells += '<td class="mono" style="color: var(--text-muted);">—</td>'
        
        # Build statistics cells
        stat_cells = ''
        for stat_name in ['Min', 'Max', 'Average', 'Median', 'StdDev']:
            stat_value = stats.get(stat_name)
            if stat_value is not None:
                stat_cells += f'<td class="mono">{format_number(stat_value)}</td>'
            else:
                stat_cells += '<td class="mono" style="color: var(--text-muted);">—</td>'
        
        table_rows += f'''
        <tr data-wafer="{wafer}" data-temperature="{temperature}" data-device="{device}" data-parameter="{parameter}">
            <td class="mono">{wafer}</td>
            <td class="mono">{temperature}</td>
            <td class="mono">{device}</td>
            <td class="mono">{parameter}</td>
            {stat_cells}
            {die_cells}
        </tr>
        '''
    
    # Get header values
    lot_name = header_info.get('Lot', 'Unknown')
    device_type = header_info.get('Device Type', 'Device')
    routine = header_info.get('Routine', '')
    meas_condition = header_info.get('Meas Condition', '')
    date_val = header_info.get('Date', 'N/A')
    operator_val = header_info.get('Operator', '') or 'N/A'
    
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{lot_name} - Measurement Report</title>
    <style>
        :root {{
            --bg-primary: #ffffff;
            --bg-secondary: #fafafa;
            --bg-tertiary: #f5f5f5;
            --bg-card: #ffffff;
            --border-color: #eeeeee;
            --text-primary: #333333;
            --text-secondary: #666666;
            --text-muted: #999999;
            --accent-blue: #0066cc;
            --accent-green: #22863a;
            --accent-orange: #e36209;
            --accent-red: #cb2431;
            --font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: var(--font-family);
            background: var(--bg-primary);
            min-height: 100vh;
            color: var(--text-primary);
            line-height: 1.6;
            font-size: 14px;
        }}
        
        .layout {{
            display: flex;
            min-height: 100vh;
        }}
        
        /* Sidebar */
        .sidebar {{
            background: var(--bg-secondary);
            border-right: 1px solid var(--border-color);
            height: 100vh;
            position: sticky;
            top: 0;
            overflow-y: auto;
            padding: 1.5rem;
            flex-shrink: 0;
            width: 280px;
            min-width: 200px;
            max-width: 600px;
        }}
        
        /* Resizer */
        .resizer {{
            width: 4px;
            background: var(--border-color);
            cursor: col-resize;
            flex-shrink: 0;
            position: relative;
            transition: background 0.2s;
        }}
        
        .resizer:hover {{
            background: var(--accent-blue);
        }}
        
        .resizer.active {{
            background: var(--accent-blue);
        }}
        
        .sidebar-header {{
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border-color);
        }}
        
        .sidebar-title {{
            font-size: 0.7rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 0.5rem;
        }}
        
        .sidebar-lot {{
            font-size: 1rem;
            font-weight: 500;
            color: var(--text-primary);
        }}
        
        /* Navigation Tree */
        .nav-tree {{
            font-size: 0.8rem;
        }}
        
        .nav-section {{
            margin-bottom: 0.5rem;
        }}
        
        .nav-section-header {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.4rem 0.5rem;
            cursor: pointer;
            border-radius: 4px;
            font-weight: 500;
            color: var(--text-secondary);
            transition: background 0.15s;
        }}
        
        .nav-section-header:hover {{
            background: var(--bg-tertiary);
        }}
        
        .nav-section-header .icon {{
            width: 16px;
            height: 16px;
            transition: transform 0.2s;
        }}
        
        .nav-section.collapsed .nav-section-header .icon {{
            transform: rotate(-90deg);
        }}
        
        .nav-section.collapsed .nav-children {{
            display: none;
        }}
        
        .nav-children {{
            margin-left: 1.25rem;
            border-left: 1px solid var(--border-color);
            padding-left: 0.75rem;
        }}
        
        .nav-item {{
            display: block;
            padding: 0.3rem 0.5rem;
            color: var(--text-secondary);
            text-decoration: none;
            border-radius: 4px;
            font-size: 0.75rem;
            font-family: monospace;
            transition: all 0.15s;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .nav-item:hover {{
            background: var(--bg-tertiary);
            color: var(--accent-blue);
        }}
        
        .nav-label {{
            font-size: 0.7rem;
            color: var(--text-muted);
            padding: 0.25rem 0.5rem;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 1.5rem 2rem;
        }}
        
        /* Main Content */
        .main {{
            padding: 0;
            flex: 1;
            min-width: 0;
            overflow-x: auto;
        }}
        
        /* Header */
        header {{
            text-align: left;
            padding: 1rem 0 1.5rem;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 1.5rem;
        }}
        
        header h1 {{
            font-size: 1.25rem;
            font-weight: 500;
            color: var(--text-primary);
            margin-bottom: 0.5rem;
        }}
        
        .header-subtitle {{
            color: var(--text-secondary);
            font-size: 0.875rem;
        }}
        
        .header-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 1.5rem;
            margin-top: 1rem;
        }}
        
        .meta-item {{
            display: flex;
            gap: 0.5rem;
            align-items: baseline;
        }}
        
        .meta-label {{
            font-size: 12px;
            color: var(--text-muted);
        }}
        
        .meta-value {{
            color: var(--text-primary);
            font-size: 13px;
        }}
        
        /* Stats Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        
        .stat-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.25rem;
        }}
        
        .stat-label {{
            font-size: 0.7rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.3px;
            margin-bottom: 0.25rem;
        }}
        
        .stat-value {{
            font-size: 1.75rem;
            font-weight: 600;
            font-family: 'IBM Plex Mono', monospace;
        }}
        
        .stat-value.blue {{ color: var(--accent-blue); }}
        .stat-value.green {{ color: var(--accent-green); }}
        .stat-value.orange {{ color: var(--accent-orange); }}
        .stat-value.purple {{ color: var(--accent-purple); }}
        
        .stat-detail {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-top: 0.25rem;
        }}
        
        /* Section */
        .section {{
            margin-bottom: 2rem;
        }}
        
        .section-title {{
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--text-muted);
            margin-bottom: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        /* Parameter Cards */
        .param-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 0.75rem;
        }}
        
        .param-card {{
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            overflow: hidden;
        }}
        
        .param-header {{
            padding: 0.75rem 1rem;
            background: var(--bg-tertiary);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .param-name {{
            font-family: 'IBM Plex Mono', monospace;
            font-weight: 500;
            font-size: 0.85rem;
            color: var(--accent-cyan);
        }}
        
        .param-count {{
            font-size: 0.7rem;
            color: var(--text-muted);
        }}
        
        .param-body {{
            padding: 0.75rem 1rem;
        }}
        
        .param-stat-row {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.5rem;
            margin-bottom: 0.5rem;
        }}
        
        .param-stat-row:last-child {{
            margin-bottom: 0;
        }}
        
        .param-stat {{
            text-align: center;
        }}
        
        .param-stat-label {{
            display: block;
            font-size: 0.6rem;
            color: var(--text-muted);
            text-transform: uppercase;
            margin-bottom: 0.1rem;
        }}
        
        .param-stat-value {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 0.8rem;
            font-weight: 500;
        }}
        
        /* Summary Statistics */
        .summary-stats {{
            display: flex;
            gap: 2rem;
            margin-bottom: 1rem;
            padding: 1rem;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
        }}
        
        .summary-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .summary-label {{
            font-size: 13px;
            color: var(--text-secondary);
        }}
        
        .summary-value {{
            font-size: 16px;
            font-weight: 600;
            color: var(--text-primary);
        }}
        
        .summary-detail {{
            font-size: 12px;
            font-weight: 400;
            color: var(--text-muted);
            margin-left: 0.5rem;
        }}
        
        /* Data Table */
        .table-container {{
            overflow-x: auto;
            overflow-y: auto;
            max-height: 600px;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            position: relative;
            -webkit-overflow-scrolling: touch;
        }}
        
        .table-container::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        
        .table-container::-webkit-scrollbar-track {{
            background: var(--bg-secondary);
            border-radius: 4px;
        }}
        
        .table-container::-webkit-scrollbar-thumb {{
            background: var(--text-muted);
            border-radius: 4px;
        }}
        
        .table-container::-webkit-scrollbar-thumb:hover {{
            background: var(--text-secondary);
        }}
        
        .data-table {{
            width: 100%;
            min-width: max-content;
            border-collapse: separate;
            border-spacing: 0;
            font-size: 12px;
            table-layout: auto;
        }}
        
        .data-table thead {{
            background: linear-gradient(to bottom, #f8f9fa, #f0f1f2);
        }}
        
        .data-table th {{
            color: var(--text-primary);
            font-weight: 600;
            padding: 0.75rem 1rem;
            text-align: center;
            border-bottom: 2px solid var(--border-color);
            border-right: 1px solid var(--border-color);
            position: sticky;
            top: 0;
            z-index: 10;
            font-size: 11px;
            white-space: nowrap;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            background: linear-gradient(to bottom, #f8f9fa, #f0f1f2);
        }}
        
        .data-table th:last-child {{
            border-right: none;
        }}
        
        .data-table th:not(:first-child):not(:nth-child(2)):not(:nth-child(3)):not(:nth-child(4)) {{
            min-width: 80px;
        }}
        
        .data-table td:not(:first-child):not(:nth-child(2)):not(:nth-child(3)):not(:nth-child(4)) {{
            min-width: 80px;
        }}
        
        /* Filters Container */
        .filters-container {{
            display: flex;
            flex-wrap: wrap;
            gap: 1.5rem;
            margin-bottom: 1rem;
            padding: 1rem;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
        }}
        
        .filter-group {{
            position: relative;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .filter-label {{
            font-size: 12px;
            color: var(--text-secondary);
            font-weight: 500;
        }}
        
        .filter-btn {{
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            cursor: pointer;
            padding: 0.4rem 0.75rem;
            font-size: 12px;
            line-height: 1;
            transition: all 0.15s;
            border-radius: 4px;
            min-width: 150px;
            text-align: left;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        
        .filter-btn:hover {{
            border-color: var(--accent-blue);
            background: var(--bg-primary);
        }}
        
        .filter-btn.active {{
            border-color: var(--accent-blue);
            color: var(--accent-blue);
            background: var(--bg-primary);
        }}
        
        .filter-dropdown {{
            display: none;
            position: absolute;
            top: 100%;
            left: 0;
            margin-top: 4px;
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 1000;
            min-width: 250px;
            max-width: 350px;
            max-height: 400px;
        }}
        
        .filter-dropdown.show {{
            display: block;
        }}
        
        .filter-dropdown .checkbox-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            cursor: pointer;
            padding: 0.25rem 0;
        }}
        
        .filter-dropdown .checkbox-item input {{
            cursor: pointer;
            accent-color: #000000;
        }}
        
        .filter-dropdown .checkbox-item span {{
            cursor: pointer;
            font-size: 13px;
            color: var(--text-muted);
            transition: color 0.15s;
        }}
        
        .filter-dropdown .checkbox-item input:checked + span {{
            color: #000000;
            font-weight: 500;
        }}
        
        .filter-apply-btn {{
            width: 100%;
            padding: 0.5rem;
            border: none;
            border-top: 1px solid var(--border-color);
            background: #000000;
            color: white;
            cursor: pointer;
            font-size: 12px;
            font-family: var(--font-family);
            font-weight: 500;
            transition: background 0.15s;
        }}
        
        .filter-apply-btn:hover {{
            background: #333333;
        }}
        
        .filter-dropdown .filter-checkboxes {{
            max-height: 280px;
            overflow-y: auto;
            padding: 0.5rem;
        }}
        
        .filter-dropdown .filter-checkboxes::-webkit-scrollbar {{
            width: 6px;
        }}
        
        .filter-dropdown .filter-checkboxes::-webkit-scrollbar-track {{
            background: var(--bg-secondary);
        }}
        
        .filter-dropdown .filter-checkboxes::-webkit-scrollbar-thumb {{
            background: var(--text-muted);
            border-radius: 3px;
        }}
        
        /* Sticky columns */
        .data-table th:first-child,
        .data-table th:nth-child(2),
        .data-table th:nth-child(3),
        .data-table th:nth-child(4) {{
            position: sticky;
            left: 0;
            z-index: 12;
            background: linear-gradient(to bottom, #f8f9fa, #f0f1f2) !important;
        }}
        
        .data-table th:first-child {{
            min-width: 100px;
            width: 100px;
        }}
        
        .data-table th:nth-child(2) {{
            left: 100px;
            min-width: 120px;
            width: 120px;
        }}
        
        .data-table th:nth-child(3) {{
            left: 220px;
            min-width: 150px;
            width: 150px;
        }}
        
        .data-table th:nth-child(4) {{
            left: 370px;
            min-width: 200px;
            width: 200px;
        }}
        
        
        .data-table td {{
            padding: 0.6rem 1rem;
            border-bottom: 1px solid #e8e9ea;
            border-right: 1px solid #e8e9ea;
            text-align: center;
            color: var(--text-primary);
            white-space: nowrap;
            background: var(--bg-primary);
        }}
        
        .data-table td:last-child {{
            border-right: none;
        }}
        
        .data-table tbody tr:nth-child(even) td {{
            background: #fafbfc;
        }}
        
        .data-table tbody tr:nth-child(odd) td {{
            background: var(--bg-primary);
        }}
        
        .data-table td:first-child {{
            position: sticky;
            left: 0;
            z-index: 5;
            min-width: 100px;
            width: 100px;
            background: var(--bg-primary);
        }}
        
        .data-table td:nth-child(2) {{
            position: sticky;
            left: 100px;
            z-index: 5;
            min-width: 120px;
            width: 120px;
            background: var(--bg-primary);
        }}
        
        .data-table td:nth-child(3) {{
            position: sticky;
            left: 220px;
            z-index: 5;
            min-width: 150px;
            width: 150px;
            background: var(--bg-primary);
        }}
        
        .data-table td:nth-child(4) {{
            position: sticky;
            left: 370px;
            z-index: 5;
            min-width: 200px;
            width: 200px;
            background: var(--bg-primary);
        }}
        
        .data-table tbody tr:nth-child(even) td:first-child,
        .data-table tbody tr:nth-child(even) td:nth-child(2),
        .data-table tbody tr:nth-child(even) td:nth-child(3),
        .data-table tbody tr:nth-child(even) td:nth-child(4) {{
            background: #fafbfc !important;
        }}
        
        .data-table tbody tr:nth-child(odd) td:first-child,
        .data-table tbody tr:nth-child(odd) td:nth-child(2),
        .data-table tbody tr:nth-child(odd) td:nth-child(3),
        .data-table tbody tr:nth-child(odd) td:nth-child(4) {{
            background: var(--bg-primary) !important;
        }}
        
        .data-table tbody tr:hover td {{
            background: #e8f4f8 !important;
        }}
        
        .data-table tbody tr:hover td:first-child,
        .data-table tbody tr:hover td:nth-child(2),
        .data-table tbody tr:hover td:nth-child(3),
        .data-table tbody tr:hover td:nth-child(4) {{
            background: #e8f4f8 !important;
            z-index: 6;
        }}
        
        .data-table .mono {{
            font-family: monospace;
            font-size: 12px;
        }}
        
        .data-table tbody tr:last-child td {{
            border-bottom: none;
        }}
        
        
        .copy-btn, .reset-btn {{
            font-family: var(--font-family);
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            padding: 0.4rem 0.75rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            white-space: nowrap;
            min-width: 120px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .copy-btn:hover, .reset-btn:hover {{
            border-color: var(--text-muted);
            color: var(--text-primary);
        }}
        
        .copy-btn.success {{
            background: var(--accent-green);
            color: white;
            border-color: var(--accent-green);
        }}
        
        .data-table tbody tr.hidden {{
            display: none;
        }}
        
        /* Footer */
        .footer {{
            margin-top: 3rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border-color);
            font-size: 0.75rem;
            color: var(--text-muted);
        }}
        
        @media (max-width: 1024px) {{
            .sidebar {{
                display: none;
            }}
            .resizer {{
                display: none;
            }}
            .stats-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
    </style>
</head>
<body>
    <div class="layout">
        <!-- Sidebar Navigation -->
        <aside class="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-title">Measurement Data</div>
            </div>
            <nav class="nav-tree">
                {nav_html}
            </nav>
        </aside>
        
        <!-- Resizer -->
        <div class="resizer" id="sidebar-resizer"></div>
        
        <!-- Main Content -->
        <main class="main">
            <div class="container">
            <header>
                <h1>{lot_name}</h1>
                <p class="header-subtitle">{device_type} • {routine} • {meas_condition}</p>
                <div class="header-meta">
                    <div class="meta-item">
                        <span class="meta-label">Date</span>
                        <span class="meta-value">{date_val}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">Operator</span>
                        <span class="meta-value">{operator_val}</span>
                    </div>
                </div>
            </header>
            
            <!-- Measurements Table -->
            <section class="section">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                    <h2 class="section-title" style="margin-bottom: 0;">Measurement Statistics</h2>
                    <button id="copy-table-btn" class="copy-btn">Copy Table</button>
                </div>
                
                <!-- Summary Statistics -->
                <div class="summary-stats">
                    <div class="summary-item">
                        <span class="summary-label">Wafers:</span>
                        <span class="summary-value">{len(unique_wafers)} <span class="summary-detail">({wafer_list})</span></span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-label">Temperatures:</span>
                        <span class="summary-value">{len(unique_temperatures)} <span class="summary-detail">({temp_list})</span></span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-label">Devices:</span>
                        <span class="summary-value">{len(unique_devices)}</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-label">Measurements:</span>
                        <span class="summary-value">{mdm_files_count}</span>
                    </div>
                </div>
                
                <!-- Filters above table -->
                <div class="filters-container">
                    <div class="filter-group">
                        <label class="filter-label">Wafer:</label>
                        <button class="filter-btn" data-filter="wafer">Wafer ▼</button>
                        <div class="filter-dropdown" id="filter-wafer-dropdown">
                            <div class="filter-checkboxes">
                                <label class="checkbox-item">
                                    <input type="checkbox" value="" checked>
                                    <span>All</span>
                                </label>
                                {wafer_checkboxes}
                            </div>
                            <button class="filter-apply-btn">Apply</button>
                        </div>
                    </div>
                    <div class="filter-group">
                        <label class="filter-label">Temperature:</label>
                        <button class="filter-btn" data-filter="temperature">Temperature ▼</button>
                        <div class="filter-dropdown" id="filter-temperature-dropdown">
                            <div class="filter-checkboxes">
                                <label class="checkbox-item">
                                    <input type="checkbox" value="" checked>
                                    <span>All</span>
                                </label>
                                {temp_checkboxes}
                            </div>
                            <button class="filter-apply-btn">Apply</button>
                        </div>
                    </div>
                    <div class="filter-group">
                        <label class="filter-label">Device:</label>
                        <button class="filter-btn" data-filter="device">Device ▼</button>
                        <div class="filter-dropdown" id="filter-device-dropdown">
                            <div class="filter-checkboxes">
                                <label class="checkbox-item">
                                    <input type="checkbox" value="" checked>
                                    <span>All</span>
                                </label>
                                {device_checkboxes}
                            </div>
                            <button class="filter-apply-btn">Apply</button>
                        </div>
                    </div>
                    <div class="filter-group">
                        <label class="filter-label">Parameter:</label>
                        <button class="filter-btn" data-filter="testparam">Parameter ▼</button>
                        <div class="filter-dropdown" id="filter-testparam-dropdown">
                            <div class="filter-checkboxes">
                                <label class="checkbox-item">
                                    <input type="checkbox" value="" checked>
                                    <span>All</span>
                                </label>
                                {param_checkboxes}
                            </div>
                            <button class="filter-apply-btn">Apply</button>
                        </div>
                    </div>
                </div>
                
                <div class="table-container">
                    <table id="measurements-table" class="data-table">
                        <thead>
                            <tr>
                                <th>Wafer</th>
                                <th>Temperature</th>
                                <th>Device</th>
                                <th>Parameter</th>
                                <th>Min</th>
                                <th>Max</th>
                                <th>Average</th>
                                <th>Median</th>
                                <th>StdDev</th>
                                {die_columns}
                            </tr>
                        </thead>
                        <tbody id="table-body">
                            {table_rows}
                        </tbody>
                    </table>
                </div>
            </section>
            
            <footer class="footer">
                <p>Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>Source: {generator.filepath.name}</p>
            </footer>
            </div>
        </main>
    </div>
    
    <script>
        // Sidebar resizer functionality
        const sidebar = document.querySelector('.sidebar');
        const resizer = document.getElementById('sidebar-resizer');
        let isResizing = false;
        let startX = 0;
        let startWidth = 0;
        
        // Load saved width from localStorage
        const savedWidth = localStorage.getItem('sidebar-width');
        if (savedWidth) {{
            sidebar.style.width = savedWidth + 'px';
        }}
        
        resizer.addEventListener('mousedown', (e) => {{
            isResizing = true;
            startX = e.clientX;
            startWidth = sidebar.offsetWidth;
            resizer.classList.add('active');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            e.preventDefault();
        }});
        
        document.addEventListener('mousemove', (e) => {{
            if (!isResizing) return;
            
            const diff = e.clientX - startX;
            const newWidth = startWidth + diff;
            const minWidth = 200;
            const maxWidth = 600;
            
            if (newWidth >= minWidth && newWidth <= maxWidth) {{
                sidebar.style.width = newWidth + 'px';
            }}
        }});
        
        document.addEventListener('mouseup', () => {{
            if (isResizing) {{
                isResizing = false;
                resizer.classList.remove('active');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
                // Save width to localStorage
                localStorage.setItem('sidebar-width', sidebar.offsetWidth);
            }}
        }});
        
        // Toggle navigation sections
        document.querySelectorAll('.nav-section-header').forEach(header => {{
            header.addEventListener('click', () => {{
                header.parentElement.classList.toggle('collapsed');
            }});
        }});
        
        // Table filtering with header filters
        const tableBody = document.getElementById('table-body');
        const filterWaferDropdown = document.getElementById('filter-wafer-dropdown');
        const filterTemperatureDropdown = document.getElementById('filter-temperature-dropdown');
        const filterDeviceDropdown = document.getElementById('filter-device-dropdown');
        const filterTestParamDropdown = document.getElementById('filter-testparam-dropdown');
        
        // Store current filter values
        let currentWaferFilters = [];
        let currentTempFilters = [];
        let currentDeviceFilters = [];
        let currentParamFilters = [];
        
        function getSelectedValues(container) {{
            const checked = Array.from(container.querySelectorAll('input:checked')).map(cb => cb.value);
            if (checked.includes('') || checked.length === 0) {{
                return [];
            }}
            return checked;
        }}
        
        function applyFilters() {{
            const rows = tableBody.querySelectorAll('tr');
            
            rows.forEach(row => {{
                const wafer = row.getAttribute('data-wafer');
                const temperature = row.getAttribute('data-temperature');
                const device = row.getAttribute('data-device');
                const parameter = row.getAttribute('data-parameter');
                
                const matchesWafer = currentWaferFilters.length === 0 || currentWaferFilters.includes(wafer);
                const matchesTemp = currentTempFilters.length === 0 || currentTempFilters.includes(temperature);
                const matchesDevice = currentDeviceFilters.length === 0 || currentDeviceFilters.includes(device);
                const matchesParam = currentParamFilters.length === 0 || currentParamFilters.includes(parameter);
                
                if (matchesWafer && matchesTemp && matchesDevice && matchesParam) {{
                    row.classList.remove('hidden');
                }} else {{
                    row.classList.add('hidden');
                }}
            }});
        }}
        
        // Handle "All" checkbox logic
        function handleAllCheckbox(container, allCheckbox) {{
            if (allCheckbox.checked) {{
                container.querySelectorAll('input:not([value=""])').forEach(cb => cb.checked = false);
            }} else {{
                const otherChecked = container.querySelectorAll('input:not([value=""]):checked');
                if (otherChecked.length === 0) {{
                    allCheckbox.checked = true;
                }}
            }}
        }}
        
        function handleItemCheckbox(container, allCheckbox) {{
            const otherChecked = container.querySelectorAll('input:not([value=""]):checked');
            if (otherChecked.length > 0) {{
                allCheckbox.checked = false;
            }} else {{
                allCheckbox.checked = true;
            }}
        }}
        
        // Setup filter dropdowns
        function setupFilterDropdown(dropdown, filterType) {{
            const allCheckbox = dropdown.querySelector('input[value=""]');
            const applyBtn = dropdown.querySelector('.filter-apply-btn');
            const checkboxesContainer = dropdown.querySelector('.filter-checkboxes');
            
            // Prevent dropdown from closing when clicking inside
            dropdown.addEventListener('click', (e) => {{
                e.stopPropagation();
            }});
            
            // Function to apply filter
            function applyFilter() {{
                const selected = getSelectedValues(checkboxesContainer);
                if (filterType === 'wafer') {{
                    currentWaferFilters = selected;
                }} else if (filterType === 'temperature') {{
                    currentTempFilters = selected;
                }} else if (filterType === 'device') {{
                    currentDeviceFilters = selected;
                }} else if (filterType === 'testparam') {{
                    currentParamFilters = selected;
                }}
                applyFilters();
                updateFilterButtonText(filterType, selected);
            }}
            
            // Handle checkbox changes
            checkboxesContainer.querySelectorAll('input').forEach(cb => {{
                cb.addEventListener('change', (e) => {{
                    e.stopPropagation();
                    if (cb === allCheckbox) {{
                        handleAllCheckbox(checkboxesContainer, allCheckbox);
                    }} else {{
                        handleItemCheckbox(checkboxesContainer, allCheckbox);
                    }}
                }});
            }});
            
            // Apply button
            applyBtn.addEventListener('click', (e) => {{
                e.stopPropagation();
                applyFilter();
                // Don't close dropdown automatically - let user continue selecting
            }});
        }}
        
        setupFilterDropdown(filterWaferDropdown, 'wafer');
        setupFilterDropdown(filterTemperatureDropdown, 'temperature');
        setupFilterDropdown(filterDeviceDropdown, 'device');
        setupFilterDropdown(filterTestParamDropdown, 'testparam');
        
        // Toggle dropdowns
        document.querySelectorAll('.filter-btn').forEach(btn => {{
            btn.addEventListener('click', (e) => {{
                e.stopPropagation();
                const filterType = btn.getAttribute('data-filter');
                const dropdown = document.getElementById(`filter-${{filterType}}-dropdown`);
                const isOpen = dropdown.classList.contains('show');
                
                // Close all dropdowns
                closeAllDropdowns();
                
                // Toggle current dropdown
                if (!isOpen) {{
                    dropdown.classList.add('show');
                    btn.classList.add('active');
                    
                    // Restore checkbox states based on current filters
                    const checkboxesContainer = dropdown.querySelector('.filter-checkboxes');
                    const allCheckbox = checkboxesContainer.querySelector('input[value=""]');
                    let currentFilters = [];
                    if (filterType === 'wafer') {{
                        currentFilters = currentWaferFilters;
                    }} else if (filterType === 'temperature') {{
                        currentFilters = currentTempFilters;
                    }} else if (filterType === 'device') {{
                        currentFilters = currentDeviceFilters;
                    }} else if (filterType === 'testparam') {{
                        currentFilters = currentParamFilters;
                    }}
                    
                    if (currentFilters.length === 0) {{
                        allCheckbox.checked = true;
                        checkboxesContainer.querySelectorAll('input:not([value=""])').forEach(cb => cb.checked = false);
                    }} else {{
                        allCheckbox.checked = false;
                        checkboxesContainer.querySelectorAll('input').forEach(cb => {{
                            cb.checked = currentFilters.includes(cb.value);
                        }});
                    }}
                }}
            }});
        }});
        
        function closeAllDropdowns() {{
            document.querySelectorAll('.filter-dropdown').forEach(dd => dd.classList.remove('show'));
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
        }}
        
        // Close dropdowns when clicking outside
        document.addEventListener('click', (e) => {{
            const isInsideFilter = e.target.closest('.filter-group') || e.target.closest('.filter-dropdown');
            if (!isInsideFilter) {{
                closeAllDropdowns();
            }}
        }});
        
        // Copy table to clipboard
        const copyBtn = document.getElementById('copy-table-btn');
        copyBtn.addEventListener('click', async () => {{
            const table = document.getElementById('measurements-table');
            const rows = tableBody.querySelectorAll('tr:not(.hidden)');
            
            if (rows.length === 0) {{
                alert('No rows to copy. Please clear filters.');
                return;
            }}
            
            let text = '';
            
            // Copy header
            const headerRow = table.querySelector('thead tr');
            const headerCells = headerRow.querySelectorAll('th');
            text += Array.from(headerCells).map(th => th.textContent.trim()).join('\\t') + '\\n';
            
            // Copy visible rows
            rows.forEach(row => {{
                const cells = row.querySelectorAll('td');
                text += Array.from(cells).map(td => td.textContent.trim()).join('\\t') + '\\n';
            }});
            
            try {{
                await navigator.clipboard.writeText(text);
                const originalText = copyBtn.textContent;
                copyBtn.textContent = 'Copied!';
                copyBtn.style.background = 'var(--accent-green)';
                setTimeout(() => {{
                    copyBtn.textContent = originalText;
                    copyBtn.style.background = '';
                }}, 2000);
            }} catch (err) {{
                console.error('Failed to copy:', err);
                alert('Failed to copy table. Please try selecting and copying manually.');
            }}
        }});
        
        // Initialize filter button texts
        function updateFilterButtonText(filterType, selected) {{
            const btn = document.querySelector(`.filter-btn[data-filter="${{filterType}}"]`);
            if (btn && selected.length > 0) {{
                if (selected.length <= 3) {{
                    btn.textContent = selected.join(', ') + ' ▼';
                }} else {{
                    btn.textContent = `${{selected.length}} selected ▼`;
                }}
                btn.classList.add('active');
            }} else if (btn) {{
                const labels = {{
                    'wafer': 'Wafer',
                    'temperature': 'Temperature',
                    'device': 'Device',
                    'testparam': 'Parameter'
                }};
                btn.textContent = labels[filterType] + ' ▼';
                btn.classList.remove('active');
            }}
        }}
        
        // Initial filter application (shows all rows)
        applyFilters();
        updateFilterButtonText('wafer', currentWaferFilters);
        updateFilterButtonText('temperature', currentTempFilters);
        updateFilterButtonText('device', currentDeviceFilters);
        updateFilterButtonText('testparam', currentParamFilters);
        
        // Wafer Map functionality
        const waferMapSvg = document.getElementById('wafer-map-svg');
        const waferSelect = document.getElementById('wafer-map-wafer-select');
        const temperatureSelect = document.getElementById('wafer-map-temperature-select');
        const deviceSelect = document.getElementById('wafer-map-device-select');
        const parameterSelect = document.getElementById('wafer-map-parameter-select');
        const heatmapToggle = document.getElementById('wafer-map-heatmap-toggle');
        const legendDiv = document.getElementById('wafer-map-legend');
        
        function parseDieCoordinate(dieStr) {{
            const match = dieStr.match(/X(-?\\d+)-Y(-?\\d+)/);
            if (match) {{
                return {{ x: parseInt(match[1]), y: parseInt(match[2]) }};
            }}
            return null;
        }}
        
        function getWaferMapData() {{
            const wafer = waferSelect.value;
            const temperature = temperatureSelect.value;
            const device = deviceSelect.value;
            const parameter = parameterSelect.value;
            
            if (!wafer || !parameter) {{
                return null;
            }}
            
            const rows = tableBody.querySelectorAll('tr');
            const dieMap = {{}};
            
            rows.forEach(row => {{
                const rowWafer = row.getAttribute('data-wafer');
                const rowTemp = row.getAttribute('data-temperature');
                const rowDevice = row.getAttribute('data-device');
                const rowParam = row.getAttribute('data-parameter');
                
                if (rowWafer !== wafer || rowParam !== parameter) {{
                    return;
                }}
                if (temperature && rowTemp !== temperature) {{
                    return;
                }}
                if (device && rowDevice !== device) {{
                    return;
                }}
                
                // Get all die cells
                const cells = row.querySelectorAll('td');
                // Skip first 9 cells (Wafer, Temperature, Device, Parameter, Min, Max, Average, Median, StdDev)
                for (let i = 9; i < cells.length; i++) {{
                    const dieHeader = document.querySelector(`#measurements-table thead th:nth-child(${{i + 1}})`);
                    if (!dieHeader) continue;
                    
                    const dieStr = dieHeader.textContent.trim();
                    const coord = parseDieCoordinate(dieStr);
                    if (!coord) continue;
                    
                    const cellValue = cells[i].textContent.trim();
                    if (cellValue && cellValue !== '—') {{
                        const numValue = parseFloat(cellValue);
                        if (!isNaN(numValue)) {{
                            const key = `${{coord.x}},${{coord.y}}`;
                            // If multiple values for same die, take the last one
                            dieMap[key] = {{
                                x: coord.x,
                                y: coord.y,
                                value: numValue,
                                dieStr: dieStr
                            }};
                        }}
                    }}
                }}
            }});
            
            return Object.values(dieMap);
        }}
        
        function interpolateColor(value, min, max) {{
            if (max === min) return 'rgb(200, 200, 200)';
            const ratio = (value - min) / (max - min);
            // Blue to red gradient
            const r = Math.round(255 * ratio);
            const b = Math.round(255 * (1 - ratio));
            return `rgb(${{r}}, 100, ${{b}})`;
        }}
        
        function renderWaferMap() {{
            const data = getWaferMapData();
            
            // Clear SVG
            waferMapSvg.innerHTML = '';
            legendDiv.style.display = 'none';
            
            if (!data || data.length === 0) {{
                const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                text.setAttribute('x', '400');
                text.setAttribute('y', '300');
                text.setAttribute('text-anchor', 'middle');
                text.setAttribute('fill', 'var(--text-muted)');
                text.textContent = 'Select wafer and parameter to display map';
                waferMapSvg.appendChild(text);
                return;
            }}
            
            // Find bounds
            const xCoords = data.map(d => d.x);
            const yCoords = data.map(d => d.y);
            const values = data.map(d => d.value);
            
            const minX = Math.min(...xCoords);
            const maxX = Math.max(...xCoords);
            const minY = Math.min(...yCoords);
            const maxY = Math.max(...yCoords);
            
            const minValue = Math.min(...values);
            const maxValue = Math.max(...values);
            
            // Calculate grid dimensions
            const width = maxX - minX + 1;
            const height = maxY - minY + 1;
            
            // Die size (pixels)
            const dieSize = 40;
            const padding = 60;
            
            // Calculate SVG dimensions
            const svgWidth = Math.max(800, width * dieSize + padding * 2);
            const svgHeight = Math.max(600, height * dieSize + padding * 2);
            waferMapSvg.setAttribute('width', svgWidth);
            waferMapSvg.setAttribute('height', svgHeight);
            
            // Create a map for quick lookup
            const dataMap = {{}};
            data.forEach(d => {{
                const key = `${{d.x}},${{d.y}}`;
                dataMap[key] = d;
            }});
            
            // Draw grid (Y from bottom to top, X from left to right)
            // X0-Y0 should be in the center
            const centerX = 0;
            const centerY = 0;
            
            // Calculate offset to center X0-Y0
            const offsetX = (svgWidth / 2) - (centerX - minX) * dieSize - dieSize / 2;
            const offsetY = (svgHeight / 2) - (maxY - centerY) * dieSize - dieSize / 2;
            
            // Draw all dies in the grid
            for (let y = maxY; y >= minY; y--) {{
                for (let x = minX; x <= maxX; x++) {{
                    const key = `${{x}},${{y}}`;
                    const dieData = dataMap[key];
                    
                    const xPos = offsetX + (x - minX) * dieSize;
                    const yPos = offsetY + (maxY - y) * dieSize;
                    
                    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                    rect.setAttribute('x', xPos);
                    rect.setAttribute('y', yPos);
                    rect.setAttribute('width', dieSize - 2);
                    rect.setAttribute('height', dieSize - 2);
                    rect.setAttribute('class', 'wafer-map-die');
                    
                    if (dieData) {{
                        if (heatmapToggle.checked) {{
                            const color = interpolateColor(dieData.value, minValue, maxValue);
                            rect.setAttribute('fill', color);
                        }} else {{
                            rect.setAttribute('fill', 'var(--bg-primary)');
                        }}
                        
                        // Add value text
                        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                        text.setAttribute('x', xPos + dieSize / 2);
                        text.setAttribute('y', yPos + dieSize / 2);
                        text.setAttribute('class', 'wafer-map-die-text');
                        // Format number for display
                        let formattedValue;
                        const absValue = Math.abs(dieData.value);
                        if (absValue === 0) {{
                            formattedValue = '0';
                        }} else if (absValue < 0.001 || absValue >= 1e6) {{
                            formattedValue = dieData.value.toExponential(2);
                        }} else {{
                            formattedValue = dieData.value.toPrecision(4);
                        }}
                        text.textContent = formattedValue;
                        waferMapSvg.appendChild(text);
                    }} else {{
                        rect.setAttribute('fill', 'var(--bg-tertiary)');
                        rect.setAttribute('opacity', '0.3');
                    }}
                    
                    waferMapSvg.appendChild(rect);
                }}
            }}
            
            // Draw axes labels
            // X axis (left to right)
            const xAxisLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            xAxisLabel.setAttribute('x', svgWidth - 30);
            xAxisLabel.setAttribute('y', svgHeight - 20);
            xAxisLabel.setAttribute('class', 'wafer-map-axis-label');
            xAxisLabel.textContent = 'X →';
            waferMapSvg.appendChild(xAxisLabel);
            
            // Y axis (bottom to top)
            const yAxisLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            yAxisLabel.setAttribute('x', 20);
            yAxisLabel.setAttribute('y', 30);
            yAxisLabel.setAttribute('class', 'wafer-map-axis-label');
            yAxisLabel.textContent = '↑ Y';
            waferMapSvg.appendChild(yAxisLabel);
            
            // Draw center marker (X0-Y0)
            const centerXPos = offsetX + (centerX - minX) * dieSize;
            const centerYPos = offsetY + (maxY - centerY) * dieSize;
            const centerCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
            centerCircle.setAttribute('cx', centerXPos + dieSize / 2);
            centerCircle.setAttribute('cy', centerYPos + dieSize / 2);
            centerCircle.setAttribute('r', 3);
            centerCircle.setAttribute('fill', 'var(--accent-red)');
            waferMapSvg.appendChild(centerCircle);
            
            // Show legend if heatmap is enabled
            if (heatmapToggle.checked) {{
                legendDiv.style.display = 'flex';
                document.getElementById('wafer-map-legend-min').style.background = interpolateColor(minValue, minValue, maxValue);
                document.getElementById('wafer-map-legend-max').style.background = interpolateColor(maxValue, minValue, maxValue);
                
                // Format legend values
                function formatLegendValue(val) {{
                    const absVal = Math.abs(val);
                    if (absVal === 0) return '0';
                    if (absVal < 0.001 || absVal >= 1e6) return val.toExponential(3);
                    return val.toPrecision(4);
                }}
                
                document.getElementById('wafer-map-legend-min-value').textContent = `Min: ${{formatLegendValue(minValue)}}`;
                document.getElementById('wafer-map-legend-max-value').textContent = `Max: ${{formatLegendValue(maxValue)}}`;
            }}
        }}
        
        // Event listeners for wafer map controls
        waferSelect.addEventListener('change', renderWaferMap);
        temperatureSelect.addEventListener('change', renderWaferMap);
        deviceSelect.addEventListener('change', renderWaferMap);
        parameterSelect.addEventListener('change', renderWaferMap);
        heatmapToggle.addEventListener('change', renderWaferMap);
        
        // Initial render
        renderWaferMap();
    </script>
</body>
</html>
'''
    
    # Write main report
    index_path = report_folder / 'index.html'
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return index_path


def build_navigation_tree(mdm_structure: Dict, mdm_to_html: Dict[Path, Path], 
                          lot_folder: Path, report_folder: Path) -> str:
    """Build HTML navigation tree from MDM structure."""
    html_parts = []
    
    for wafer in sorted(mdm_structure.keys()):
        temps = mdm_structure[wafer]
        
        wafer_html = f'''
        <div class="nav-section">
            <div class="nav-section-header">
                <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
                {wafer}
            </div>
            <div class="nav-children">
        '''
        
        for temp in sorted(temps.keys()):
            dies = temps[temp]
            
            wafer_html += f'''
            <div class="nav-section collapsed">
                <div class="nav-section-header">
                    <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="6 9 12 15 18 9"></polyline>
                    </svg>
                    {temp}
                </div>
                <div class="nav-children">
            '''
            
            for die in sorted(dies.keys()):
                meas_groups = dies[die]
                
                wafer_html += f'''
                <div class="nav-section collapsed">
                    <div class="nav-section-header">
                        <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                        {die}
                    </div>
                    <div class="nav-children">
                '''
                
                for meas_group in sorted(meas_groups.keys()):
                    files = meas_groups[meas_group]
                    
                    # Short name for meas group
                    short_group = meas_group.split('~')[-1] if '~' in meas_group else meas_group
                    
                    wafer_html += f'<div class="nav-label">{short_group}</div>'
                    
                    for mdm_path in sorted(files, key=lambda x: x.name):
                        if mdm_path in mdm_to_html:
                            html_path = mdm_to_html[mdm_path]
                            rel_link = html_path.relative_to(report_folder)
                            # Use full HTML filename without .html extension
                            html_filename = html_path.stem  # This removes the .html extension
                            wafer_html += f'<a class="nav-item" href="{rel_link}" target="_blank">{html_filename}</a>'
                
                wafer_html += '</div></div>'  # Close die
            
            wafer_html += '</div></div>'  # Close temp
        
        wafer_html += '</div></div>'  # Close wafer
        html_parts.append(wafer_html)
    
    return '\n'.join(html_parts)


def generate_wpro_html_report(csv_filepath: str, auto_open: bool = True) -> Path:
    """
    Generate a complete HTML measurement report from a WaferPro CSV file.
    
    This will:
    1. Parse the CSV file and extract the Lot name
    2. Find the Lot folder in the same directory as the CSV
    3. Create a Report folder inside the Lot folder
    4. Generate HTML pages for all MDM files
    5. Create a main index.html with navigation
    
    Args:
        csv_filepath: Path to the WPro.csv file
        auto_open: Whether to automatically open the report in browser
    
    Returns:
        Path to the generated index.html
    """
    csv_path = Path(csv_filepath)
    print(f"Processing: {csv_path.name}")
    
    # Parse CSV
    generator = WProReportGenerator(csv_filepath)
    lot_name = generator.lot_name
    print(f"Lot: {lot_name}")
    
    # Find lot folder (same directory as CSV, folder named as Lot)
    csv_dir = csv_path.parent
    lot_folder = csv_dir / lot_name if (csv_dir / lot_name).exists() else csv_dir
    
    # Check if lot folder is actually the parent
    if csv_dir.name == lot_name:
        lot_folder = csv_dir
    
    print(f"Lot folder: {lot_folder}")
    
    # Create Report folder
    report_folder = lot_folder / 'Report'
    report_folder.mkdir(exist_ok=True)
    print(f"Report folder: {report_folder}")
    
    # Find all MDM files
    print("Finding MDM files...")
    mdm_files = find_mdm_files(lot_folder)
    # Exclude Report folder
    mdm_files = [f for f in mdm_files if 'Report' not in f.parts]
    print(f"Found {len(mdm_files)} MDM files")
    
    # Generate HTML for each MDM file
    print("Generating HTML pages for MDM files...")
    mdm_to_html = generate_mdm_html_files(mdm_files, lot_folder, report_folder)
    print(f"Generated {len(mdm_to_html)} HTML pages")
    
    # Organize structure for navigation
    mdm_structure = organize_mdm_files(mdm_files, lot_folder)
    
    # Generate main report
    print("Generating main report...")
    index_path = generate_main_report(generator, report_folder, mdm_structure, mdm_to_html, lot_folder, len(mdm_files))
    print(f"Main report: {index_path}")
    
    # Open in browser
    if auto_open:
        webbrowser.open(f'file://{index_path.resolve()}')
    
    return index_path

generate_wpro_html_report("MyLotA_02/WX-ABench~Simu~MOSFET~WPro_MOSFET_DC~WX_DC_MeasGroup1.csv")