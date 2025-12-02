"""
MDM File HTML Viewer Generator

Generates an interactive HTML page displaying:
- Measurement regimes (ICCAP_INPUTS and ICCAP_OUTPUTS)
- Interactive graph with selectable output data
- Measurement results table
"""

import re
import json
import webbrowser
from pathlib import Path


def parse_mdm_header(filename):
    """Parse the ICCAP_INPUTS and ICCAP_OUTPUTS sections from MDM file."""
    inputs = []
    outputs = []
    values = {}
    section = None
    
    with open(filename, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            stripped = line.strip()
            
            if stripped == "ICCAP_INPUTS":
                section = "inputs"
                continue
            elif stripped == "ICCAP_OUTPUTS":
                section = "outputs"
                continue
            elif stripped == "ICCAP_VALUES":
                section = "values"
                continue
            elif stripped == "END_HEADER":
                break
            
            if section == "inputs" and stripped:
                inputs.append(stripped)
            elif section == "outputs" and stripped:
                outputs.append(stripped)
            elif section == "values" and stripped:
                match = re.match(r'(\w+)\s+"([^"]*)"', stripped)
                if match:
                    values[match.group(1)] = match.group(2)
    
    return inputs, outputs, values


def parse_mdm_data(filename):
    """Parse all measurement data blocks from MDM file."""
    all_blocks = []
    
    with open(filename, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    blocks = re.findall(r'BEGIN_DB(.*?)END_DB', content, re.DOTALL)
    
    for block_idx, block in enumerate(blocks):
        lines = block.strip().split('\n')
        
        block_vars = {}
        data = []
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
                    row = {col: float(val) for col, val in zip(columns, values)}
                    data.append(row)
        
        if columns and data:
            all_blocks.append({
                'index': block_idx,
                'vars': block_vars,
                'columns': columns,
                'data': data
            })
    
    return all_blocks


def generate_html_viewer(filename, output_html=None, auto_open=True):
    """
    Generate an interactive HTML page from an MDM file.
    
    Args:
        filename: Path to the MDM file
        output_html: Output HTML file path (default: same as input with .html extension)
        auto_open: Whether to automatically open the HTML file in browser
    
    Returns:
        Path to the generated HTML file
    """
    filename = Path(filename)
    
    if output_html is None:
        output_html = filename.with_suffix('.html')
    else:
        output_html = Path(output_html)
    
    # Parse MDM file
    inputs, outputs, values = parse_mdm_header(filename)
    blocks = parse_mdm_data(filename)
    
    if not blocks:
        raise ValueError("No data blocks found in MDM file")
    
    # Extract column names (inputs and outputs for graphing)
    columns = blocks[0]['columns']
    
    # Prepare data for JavaScript
    js_data = json.dumps(blocks, indent=2)
    js_inputs = json.dumps(inputs)
    js_outputs = json.dumps(outputs)
    js_values = json.dumps(values)
    js_columns = json.dumps(columns)
    
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{filename.name}</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
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
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 1.5rem 2rem;
        }}
        
        header {{
            text-align: left;
            padding: 1rem 0 1.5rem;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 1.5rem;
        }}
        
        h1 {{
            font-size: 1.25rem;
            font-weight: 500;
            color: var(--text-primary);
        }}
        
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
            margin-bottom: 1.5rem;
        }}
        
        @media (max-width: 1200px) {{
            .grid {{
                grid-template-columns: 1fr;
            }}
        }}
        
        .card {{
            background: var(--bg-card);
            padding: 0;
        }}
        
        .card-title {{
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--text-muted);
            margin-bottom: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .regime-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        
        .regime-table th {{
            color: var(--text-muted);
            font-weight: 500;
            padding: 0.5rem 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
            font-size: 12px;
        }}
        
        .regime-table td {{
            padding: 0.5rem 0.75rem;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-primary);
        }}
        
        .regime-table tr:last-child td {{
            border-bottom: none;
        }}
        
        .var-name {{
            color: var(--text-primary);
            font-weight: 500;
        }}
        
        .var-unit {{
            color: var(--text-muted);
        }}
        
        .var-node {{
            color: var(--text-primary);
        }}
        
        .var-smu {{
            color: var(--text-secondary);
        }}
        
        .var-sweep {{
            color: var(--text-secondary);
        }}
        
        .metadata-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 1.5rem;
        }}
        
        .metadata-item {{
            display: flex;
            gap: 0.5rem;
            align-items: baseline;
        }}
        
        .metadata-label {{
            font-size: 12px;
            color: var(--text-muted);
        }}
        
        .metadata-value {{
            color: var(--text-primary);
            font-size: 13px;
        }}
        
        .graph-section {{
            margin: 1.5rem 0;
            padding-top: 1.5rem;
            border-top: 1px solid var(--border-color);
        }}
        
        .graph-card {{
            background: var(--bg-card);
        }}
        
        .graph-controls {{
            padding: 0 0 1rem 0;
            display: flex;
            flex-wrap: wrap;
            gap: 1.5rem;
            align-items: flex-start;
        }}
        
        .control-group {{
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }}
        
        .control-label {{
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}
        
        select {{
            font-family: var(--font-family);
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 0.4rem 0.6rem;
            border-radius: 4px;
            font-size: 13px;
            cursor: pointer;
            min-width: 120px;
        }}
        
        select:hover {{
            border-color: var(--text-muted);
        }}
        
        select:focus {{
            outline: none;
            border-color: var(--accent-blue);
        }}
        
        .checkbox-group {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }}
        
        .checkbox-item {{
            display: flex;
            align-items: center;
            gap: 0.25rem;
            cursor: pointer;
        }}
        
        .checkbox-item input {{
            cursor: pointer;
            accent-color: #000000;
        }}
        
        .checkbox-item label {{
            cursor: pointer;
            font-size: 13px;
            color: var(--text-muted);
            transition: color 0.15s;
        }}
        
        .checkbox-item input:checked + label {{
            color: #000000;
            font-weight: 500;
        }}
        
        #plot {{
            width: 100%;
            height: 600px;
        }}
        
        .data-table-section {{
            margin-top: 1.5rem;
            padding-top: 1.5rem;
            border-top: 1px solid var(--border-color);
        }}
        
        .data-table-card {{
            background: var(--bg-card);
        }}
        
        .table-header {{
            padding: 0 0 1rem 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }}
        
        .table-title {{
            font-size: 12px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }}
        
        .table-container {{
            overflow-x: auto;
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid var(--border-color);
        }}
        
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}
        
        .data-table th {{
            background: var(--bg-secondary);
            color: var(--text-muted);
            font-weight: 500;
            padding: 0.5rem 0.75rem;
            text-align: right;
            border-bottom: 1px solid var(--border-color);
            position: sticky;
            top: 0;
            z-index: 10;
            font-size: 11px;
        }}
        
        .data-table th:first-child {{
            text-align: center;
        }}
        
        .data-table td {{
            padding: 0.35rem 0.75rem;
            border-bottom: 1px solid var(--border-color);
            text-align: right;
            color: var(--text-primary);
        }}
        
        .data-table td:first-child {{
            text-align: center;
            color: var(--text-muted);
        }}
        
        .data-table tr:last-child td {{
            border-bottom: none;
        }}
        
        .plot-type-btns {{
            display: flex;
            gap: 2px;
        }}
        
        .plot-type-btn {{
            font-family: var(--font-family);
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            padding: 0.4rem 0.6rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }}
        
        .plot-type-btn:hover {{
            border-color: var(--text-muted);
        }}
        
        .plot-type-btn.active {{
            background: var(--text-primary);
            color: var(--bg-primary);
            border-color: var(--text-primary);
        }}
        
        .action-btn {{
            font-family: var(--font-family);
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            padding: 0.4rem 0.75rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }}
        
        .action-btn:hover {{
            border-color: var(--text-muted);
            color: var(--text-primary);
        }}
        
        .action-btn.success {{
            background: var(--accent-green);
            color: white;
            border-color: var(--accent-green);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{filename.name}</h1>
        </header>
        
        <div class="grid">
            <div class="card">
                <h2 class="card-title">INPUTS</h2>
                <table class="regime-table">
                    <thead>
                        <tr>
                            <th>Variable</th>
                            <th>Unit</th>
                            <th>Node</th>
                            <th>SMU</th>
                            <th>Sweep</th>
                            <th>Option</th>
                        </tr>
                    </thead>
                    <tbody id="inputs-table"></tbody>
                </table>
            </div>
            
            <div class="card">
                <h2 class="card-title">OUTPUTS</h2>
                <table class="regime-table">
                    <thead>
                        <tr>
                            <th>Variable</th>
                            <th>Unit</th>
                            <th>Node</th>
                            <th>SMU</th>
                            <th>Option</th>
                        </tr>
                    </thead>
                    <tbody id="outputs-table"></tbody>
                </table>
            </div>
        </div>
        
        <div class="card" style="margin-bottom: 1.5rem;">
            <h2 class="card-title">MEASUREMENT INFO</h2>
            <div class="metadata-grid" id="metadata-grid"></div>
        </div>
        
        <section class="graph-section">
            <div class="graph-card">
                <div class="graph-controls">
                    <div class="control-group">
                        <span class="control-label">X-Axis</span>
                        <select id="x-axis-select"></select>
                    </div>
                    <div class="control-group">
                        <span class="control-label">Y-Axis</span>
                        <div class="checkbox-group" id="y-axis-checkboxes"></div>
                    </div>
                    <div class="control-group">
                        <span class="control-label">X Scale</span>
                        <div class="plot-type-btns" id="x-scale-btns">
                            <button class="plot-type-btn active" data-scale="linear">Linear</button>
                            <button class="plot-type-btn" data-scale="log">Log</button>
                        </div>
                    </div>
                    <div class="control-group">
                        <span class="control-label">Y Scale</span>
                        <div class="plot-type-btns" id="y-scale-btns">
                            <button class="plot-type-btn active" data-scale="linear">Linear</button>
                            <button class="plot-type-btn" data-scale="log">Log</button>
                        </div>
                    </div>
                    <div class="control-group">
                        <span class="control-label">Sweep</span>
                        <select id="block-select">
                            <option value="all">All</option>
                        </select>
                    </div>
                    <div class="control-group" style="margin-left: auto;">
                        <button class="action-btn" id="save-plot-btn">Save PNG</button>
                    </div>
                </div>
                <div id="plot"></div>
            </div>
        </section>
        
        <section class="data-table-section">
            <div class="data-table-card">
                <div class="table-header">
                    <h2 class="table-title">Measurement Data</h2>
                    <div style="display: flex; align-items: center; gap: 1rem;">
                        <div class="control-group">
                            <select id="table-block-select">
                                <option value="all">All</option>
                            </select>
                        </div>
                        <button class="action-btn" id="copy-table-btn">Copy Data</button>
                    </div>
                </div>
                <div class="table-container">
                    <table class="data-table">
                        <thead id="table-head"></thead>
                        <tbody id="table-body"></tbody>
                    </table>
                </div>
            </div>
        </section>
        
        <section class="data-table-section">
            <div class="data-table-card">
                <div class="table-header" style="flex-direction: column; align-items: flex-start; gap: 0.5rem;">
                    <h2 class="table-title">Link to mdm file</h2>
                    <a href="file://{filename.resolve()}" style="color: var(--accent-blue); text-decoration: none; font-size: 0.875rem;">{filename.resolve()}</a>
                </div>
            </div>
        </section>
    </div>
    
    <script>
        // Data from MDM file
        const mdmData = {js_data};
        const inputs = {js_inputs};
        const outputs = {js_outputs};
        const values = {js_values};
        const columns = {js_columns};
        const mdmFilename = '{filename.stem}';
        
        // Color palette for plots
        const colors = [
            '#1a73e8', '#34a853', '#ea4335', '#ea8600', 
            '#9334e6', '#e91e63', '#00acc1', '#43a047'
        ];
        
        // Initialize the page
        document.addEventListener('DOMContentLoaded', function() {{
            populateInputsTable();
            populateOutputsTable();
            populateMetadata();
            setupControls();
            updatePlot();
            updateDataTable('all');
        }});
        
        function parseInputLine(line) {{
            const parts = line.trim().split(/\\s+/);
            return {{
                name: parts[0] || '',
                unit: parts[1] || '',
                terminal: parts[2] || '',
                ground: parts[3] || '',
                source: parts[4] || '',
                compliance: parts[5] || '',
                sweepType: parts[6] || '',
                param1: parts[7] || '',
                param2: parts[8] || '',
                param3: parts[9] || '',
                param4: parts[10] || '',
                param5: parts[11] || ''
            }};
        }}
        
        function parseOutputLine(line) {{
            const parts = line.trim().split(/\\s+/);
            return {{
                name: parts[0] || '',
                unit: parts[1] || '',
                terminal: parts[2] || '',
                ground: parts[3] || '',
                source: parts[4] || '',
                type: parts[5] || ''
            }};
        }}
        
        function parseInputWithOrder(line) {{
            const input = parseInputLine(line);
            let sweepOrder = Infinity; // CON goes to end
            let sweepLabel = '';
            let sweepOption = '';
            
            if (input.sweepType === 'CON') {{
                sweepLabel = 'CON';
                sweepOption = input.param1;
            }} else if (input.sweepType) {{
                // For LIN, LOG, etc. - param1 is the sweep order
                sweepOrder = parseInt(input.param1) || Infinity;
                sweepLabel = `VAR${{input.param1}}`;
                sweepOption = `${{input.sweepType}}: ${{input.param2}} → ${{input.param3}} (${{input.param4}} pts, step ${{input.param5}})`;
            }}
            
            return {{ ...input, sweepOrder, sweepLabel, sweepOption, originalLine: line }};
        }}
        
        // Parse and sort inputs by sweep order
        const parsedInputs = inputs.map(parseInputWithOrder).sort((a, b) => a.sweepOrder - b.sweepOrder);
        
        function populateInputsTable() {{
            const tbody = document.getElementById('inputs-table');
            parsedInputs.forEach(input => {{
                tbody.innerHTML += `
                    <tr>
                        <td><span class="var-name">${{input.name}}</span></td>
                        <td><span class="var-unit">${{input.unit}}</span></td>
                        <td><span class="var-node">${{input.terminal}}</span></td>
                        <td><span class="var-smu">${{input.source}}</span></td>
                        <td><span class="var-sweep">${{input.sweepLabel}}</span></td>
                        <td><span class="var-sweep">${{input.sweepOption}}</span></td>
                    </tr>
                `;
            }});
        }}
        
        function populateOutputsTable() {{
            const tbody = document.getElementById('outputs-table');
            
            // Get node order from sorted inputs
            const nodeOrder = parsedInputs.map(inp => inp.terminal);
            
            // Parse and sort outputs by node order (same as inputs)
            const parsedOutputs = outputs.map(line => parseOutputLine(line));
            parsedOutputs.sort((a, b) => {{
                const orderA = nodeOrder.indexOf(a.terminal);
                const orderB = nodeOrder.indexOf(b.terminal);
                // If node not found in inputs, put at end
                return (orderA === -1 ? 999 : orderA) - (orderB === -1 ? 999 : orderB);
            }});
            
            parsedOutputs.forEach(output => {{
                tbody.innerHTML += `
                    <tr>
                        <td><span class="var-name">${{output.name}}</span></td>
                        <td><span class="var-unit">${{output.unit}}</span></td>
                        <td><span class="var-node">${{output.terminal}}</span></td>
                        <td><span class="var-smu">${{output.source}}</span></td>
                        <td><span class="var-sweep">${{output.type || '—'}}</span></td>
                    </tr>
                `;
            }});
        }}
        
        function populateMetadata() {{
            const grid = document.getElementById('metadata-grid');
            const displayKeys = ['Date', 'Lot', 'Wafer', 'Die', 'Subsite', 'DeviceName', 
                                 'DevTechno', 'DevPolarity', 'Setup', 'W', 'L', 'Temperature'];
            
            displayKeys.forEach(key => {{
                if (values[key]) {{
                    grid.innerHTML += `
                        <div class="metadata-item">
                            <span class="metadata-label">${{key}}:</span>
                            <span class="metadata-value">${{values[key]}}</span>
                        </div>
                    `;
                }}
            }});
        }}
        
        function setupControls() {{
            // X-axis selector
            const xSelect = document.getElementById('x-axis-select');
            columns.forEach(col => {{
                const option = document.createElement('option');
                option.value = col;
                option.textContent = col;
                xSelect.appendChild(option);
            }});
            xSelect.addEventListener('change', updatePlot);
            
            // Y-axis checkboxes (outputs)
            const yCheckboxes = document.getElementById('y-axis-checkboxes');
            const outputNames = outputs.map(line => parseOutputLine(line).name);
            
            outputNames.forEach((name, idx) => {{
                const div = document.createElement('div');
                div.className = 'checkbox-item';
                div.innerHTML = `
                    <input type="checkbox" id="y-${{name}}" value="${{name}}" ${{idx === 0 ? 'checked' : ''}}>
                    <label for="y-${{name}}">${{name}}</label>
                `;
                yCheckboxes.appendChild(div);
            }});
            yCheckboxes.querySelectorAll('input').forEach(cb => {{
                cb.addEventListener('change', updatePlot);
            }});
            
            // Block selector for plot
            const blockSelect = document.getElementById('block-select');
            mdmData.forEach((block, idx) => {{
                const vars = Object.entries(block.vars).map(([k, v]) => `${{k}}=${{v}}`).join(', ');
                const option = document.createElement('option');
                option.value = idx;
                option.textContent = vars;
                blockSelect.appendChild(option);
            }});
            blockSelect.addEventListener('change', updatePlot);
            
            // Table block selector
            const tableBlockSelect = document.getElementById('table-block-select');
            tableBlockSelect.innerHTML = '<option value="all">All</option>';
            mdmData.forEach((block, idx) => {{
                const vars = Object.entries(block.vars).map(([k, v]) => `${{k}}=${{v}}`).join(', ');
                const option = document.createElement('option');
                option.value = idx;
                option.textContent = vars;
                tableBlockSelect.appendChild(option);
            }});
            tableBlockSelect.addEventListener('change', (e) => updateDataTable(e.target.value));
            
            // X scale buttons
            document.querySelectorAll('#x-scale-btns .plot-type-btn').forEach(btn => {{
                btn.addEventListener('click', function() {{
                    document.querySelectorAll('#x-scale-btns .plot-type-btn').forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                    updatePlot();
                }});
            }});
            
            // Y scale buttons
            document.querySelectorAll('#y-scale-btns .plot-type-btn').forEach(btn => {{
                btn.addEventListener('click', function() {{
                    document.querySelectorAll('#y-scale-btns .plot-type-btn').forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                    updatePlot();
                }});
            }});
            
            // Save plot button
            document.getElementById('save-plot-btn').addEventListener('click', savePlotAsPNG);
            
            // Copy table button
            document.getElementById('copy-table-btn').addEventListener('click', () => copyTableToClipboard('table-head', 'table-body'));
        }}
        
        function updatePlot() {{
            const xAxis = document.getElementById('x-axis-select').value;
            const yAxes = Array.from(document.querySelectorAll('#y-axis-checkboxes input:checked')).map(cb => cb.value);
            const blockValue = document.getElementById('block-select').value;
            const xScale = document.querySelector('#x-scale-btns .plot-type-btn.active').dataset.scale;
            const yScale = document.querySelector('#y-scale-btns .plot-type-btn.active').dataset.scale;
            
            const traces = [];
            let colorIdx = 0;
            
            const blocksToPlot = blockValue === 'all' ? mdmData : [mdmData[parseInt(blockValue)]];
            
            blocksToPlot.forEach((block, blockIdx) => {{
                const varLabel = Object.entries(block.vars).map(([k, v]) => `${{k}}=${{v}}`).join(', ');
                
                yAxes.forEach(yAxis => {{
                    let xData = block.data.map(row => row[xAxis]);
                    let yData = block.data.map(row => row[yAxis]);
                    
                    // Handle negative values for log scale
                    if (xScale === 'log') {{
                        xData = xData.map(v => Math.abs(v));
                    }}
                    if (yScale === 'log') {{
                        yData = yData.map(v => Math.abs(v));
                    }}
                    
                    traces.push({{
                        x: xData,
                        y: yData,
                        mode: 'lines+markers',
                        name: blockValue === 'all' ? `${{yAxis}} (${{varLabel}})` : yAxis,
                        line: {{ color: colors[colorIdx % colors.length], width: 2 }},
                        marker: {{ size: 4 }}
                    }});
                    colorIdx++;
                }});
            }});
            
            // Format axis labels based on scale
            const xAxisLabel = xScale === 'log' ? `log10(${{xAxis}})` : xAxis;
            const yAxisLabel = yScale === 'log' ? yAxes.map(y => `log10(${{y}})`).join(', ') : yAxes.join(', ');
            
            // Calculate min/max for axes to ensure max values are shown
            let allX = [];
            let allY = [];
            traces.forEach(trace => {{
                allX = allX.concat(trace.x);
                allY = allY.concat(trace.y);
            }});
            
            // For linear scale, use actual min/max; for log scale, let Plotly auto-scale
            let xRange, yRange;
            if (xScale === 'linear') {{
                const xMin = Math.min(...allX);
                const xMax = Math.max(...allX);
                xRange = [xMin, xMax];
            }} else {{
                // Log scale: use log10 of positive values for range
                const positiveX = allX.filter(v => v > 0);
                if (positiveX.length > 0) {{
                    xRange = [Math.log10(Math.min(...positiveX)), Math.log10(Math.max(...positiveX))];
                }} else {{
                    xRange = undefined;
                }}
            }}
            
            if (yScale === 'linear') {{
                const yMin = Math.min(...allY);
                const yMax = Math.max(...allY);
                yRange = [yMin, yMax];
            }} else {{
                // Log scale: use log10 of positive values for range
                const positiveY = allY.filter(v => v > 0);
                if (positiveY.length > 0) {{
                    yRange = [Math.log10(Math.min(...positiveY)), Math.log10(Math.max(...positiveY))];
                }} else {{
                    yRange = undefined;
                }}
            }}
            
            const layout = {{
                title: {{
                    text: mdmFilename,
                    font: {{ size: 16, color: '#202124' }},
                    x: 0.01,
                    xanchor: 'left'
                }},
                paper_bgcolor: '#ffffff',
                plot_bgcolor: '#ffffff',
                font: {{ family: 'Inter, Segoe UI, system-ui, sans-serif', color: '#333333', size: 12 }},
                xaxis: {{
                    title: xAxisLabel,
                    type: xScale,
                    gridcolor: '#eeeeee',
                    zerolinecolor: '#eeeeee',
                    showline: false,
                    minor: {{
                        showgrid: true,
                        gridcolor: '#f5f5f5'
                    }},
                    exponentformat: 'e',
                    automargin: true,
                    tickmode: 'auto',
                    nticks: 10,
                    showticklabels: true,
                    range: xRange,
                    autorange: xRange === undefined
                }},
                yaxis: {{
                    title: yAxisLabel,
                    type: yScale,
                    gridcolor: '#eeeeee',
                    zerolinecolor: '#eeeeee',
                    showline: false,
                    minor: {{
                        showgrid: true,
                        gridcolor: '#f5f5f5'
                    }},
                    exponentformat: 'e',
                    automargin: true,
                    tickmode: 'auto',
                    nticks: 10,
                    showticklabels: true,
                    range: yRange,
                    autorange: yRange === undefined
                }},
                legend: {{
                    bgcolor: 'rgba(255,255,255,0)',
                    borderwidth: 0
                }},
                margin: {{ t: 60, r: 40, b: 60, l: 80 }},
                hovermode: 'closest'
            }};
            
            const config = {{
                responsive: true,
                displayModeBar: true,
                modeBarButtonsToRemove: ['lasso2d', 'select2d'],
                displaylogo: false
            }};
            
            Plotly.newPlot('plot', traces, layout, config);
        }}
        
        // Helper to get sweep order for a variable name
        function getSweepOrder(varName) {{
            const input = parsedInputs.find(inp => inp.name === varName);
            return input ? input.sweepOrder : Infinity;
        }}
        
        // Check if a column is an input variable
        function isInputVar(varName) {{
            return parsedInputs.some(inp => inp.name === varName);
        }}
        
        // Get output variable names
        const outputNames = outputs.map(line => parseOutputLine(line).name);
        
        function updateDataTable(blockValue) {{
            const thead = document.getElementById('table-head');
            const tbody = document.getElementById('table-body');
            
            if (blockValue === 'all') {{
                // Show all data combined
                if (mdmData.length === 0) return;
                
                // Get all column names
                const sweepVars = Object.keys(mdmData[0].vars);
                const dataColumns = mdmData[0].columns;
                
                // Combine all columns and separate inputs from outputs
                const allColumns = [...sweepVars, ...dataColumns];
                const inputColumns = allColumns.filter(col => isInputVar(col));
                const outputColumns = allColumns.filter(col => !isInputVar(col));
                
                // Sort input columns by sweep order (ascending, CON at end)
                inputColumns.sort((a, b) => getSweepOrder(a) - getSweepOrder(b));
                
                // Final column order: sorted inputs, then outputs
                const orderedColumns = [...inputColumns, ...outputColumns];
                
                // Header
                thead.innerHTML = '<tr><th>#</th>' + 
                    orderedColumns.map(col => `<th>${{col}}</th>`).join('') + '</tr>';
                
                // Body: combine all blocks
                let rowNum = 1;
                let rows = '';
                mdmData.forEach(block => {{
                    block.data.forEach(row => {{
                        const cells = orderedColumns.map(col => {{
                            // Check if column is from block.vars or row data
                            const val = block.vars[col] !== undefined ? block.vars[col] : row[col];
                            return `<td>${{formatNumber(val)}}</td>`;
                        }}).join('');
                        rows += `<tr><td>${{rowNum++}}</td>${{cells}}</tr>`;
                    }});
                }});
                tbody.innerHTML = rows;
            }} else {{
                // Show single block
                const blockIdx = parseInt(blockValue);
                const block = mdmData[blockIdx];
                
                // Get all column names (sweep vars + data columns)
                const sweepVars = Object.keys(block.vars);
                const dataColumns = block.columns;
                
                // Combine all columns and separate inputs from outputs
                const allColumns = [...sweepVars, ...dataColumns];
                const inputColumns = allColumns.filter(col => isInputVar(col));
                const outputColumns = allColumns.filter(col => !isInputVar(col));
                
                // Sort input columns by sweep order
                inputColumns.sort((a, b) => getSweepOrder(a) - getSweepOrder(b));
                
                // Final column order: sorted inputs, then outputs
                const orderedColumns = [...inputColumns, ...outputColumns];
                
                // Header
                thead.innerHTML = '<tr><th>#</th>' + orderedColumns.map(col => `<th>${{col}}</th>`).join('') + '</tr>';
                
                // Body
                tbody.innerHTML = block.data.map((row, idx) => {{
                    const cells = orderedColumns.map(col => {{
                        // Check if column is from block.vars or row data
                        const val = block.vars[col] !== undefined ? block.vars[col] : row[col];
                        return `<td>${{formatNumber(val)}}</td>`;
                    }}).join('');
                    return `<tr><td>${{idx + 1}}</td>${{cells}}</tr>`;
                }}).join('');
            }}
        }}
        
        function formatNumber(num) {{
            if (num === 0) return '0';
            const abs = Math.abs(num);
            if (abs < 1e-12 || abs >= 1e6) {{
                return num.toExponential(6);
            }}
            return num.toPrecision(6);
        }}
        
        function savePlotAsPNG() {{
            Plotly.downloadImage('plot', {{
                format: 'png',
                width: 1200,
                height: 600,
                filename: mdmFilename
            }});
        }}
        
        function copyTableToClipboard(theadId, tbodyId) {{
            const thead = document.getElementById(theadId);
            const tbody = document.getElementById(tbodyId);
            
            let text = '';
            
            // Header
            const headerCells = thead.querySelectorAll('th');
            text += Array.from(headerCells).map(th => th.textContent).join('\\t') + '\\n';
            
            // Body
            const rows = tbody.querySelectorAll('tr');
            rows.forEach(row => {{
                const cells = row.querySelectorAll('td');
                text += Array.from(cells).map(td => td.textContent).join('\\t') + '\\n';
            }});
            
            navigator.clipboard.writeText(text).then(() => {{
                // Find the button that was clicked
                const btn = event.target;
                const originalText = btn.textContent;
                btn.textContent = 'Copied!';
                btn.classList.add('success');
                setTimeout(() => {{
                    btn.textContent = originalText;
                    btn.classList.remove('success');
                }}, 1500);
            }});
        }}
    </script>
</body>
</html>
'''
    
    # Write HTML file
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"HTML viewer generated: {output_html}")
    
    # Auto-open in browser
    if auto_open:
        webbrowser.open(f'file://{output_html.resolve()}')
    
    return output_html

