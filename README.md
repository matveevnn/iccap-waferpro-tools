# iccap-waferpro-tools
Python tools for parsing **Keysight IC-CAP** MDM files and **Keysight IC-CAP WaferPro** measurement data. Generate interactive HTML reports for analyze semiconductor device measurements and statistics.

[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

## Installation

### Requirements

- Python 3.6+
- pandas >= 1.3.0
- numpy >= 1.20.0

### Install Dependencies

```bash
pip install -r requirements.txt
```
## Quick Start

### Parse MDM File

### Parse WaferPro measurement file

### Generate MDM to HTML Report

### Generate WaferPro HTML Report

## Documentation

### MDM Parser (`mdm_parser.py`)

Functions for parsing IC-CAP MDM files:

- `mdm_inputs(filename)` - Extract input variable names
- `mdm_outputs(filename)` - Extract output variable names
- `mdm_values(filename)` - Extract metadata from ICCAP_VALUES section
- `mdm_to_dataframe(filename)` - Convert MDM file to pandas DataFrame
- `mdm_get_block(filename, block_index)` - Get specific data block
- `mdm_block_count(filename)` - Count data blocks in file

### MDM HTML Report generator (`mdm_to_html.py`)

- `generate_html_viewer(filename, output_html=None, auto_open=True)` - Converts an MDM file into an interactive HTML document.

**Parameters:**
- `filename` - path to the MDM file
- `output_html` - path to save HTML (optional)
- `auto_open` - automatically open in the browser (default: `True`)

## Examples

See the `examples/` directory for more usage examples.

## Search Keywords

This project can be found by searching for:
- `iccap tools`
- `waferpro tools`
- `keysight iccap python`
- `iccap mdm parser`
- `waferpro csv processor`
- `semiconductor measurement tools`
- `mdm file parser`
- `iccap html report`

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

**Matveev Nikita**

Copyright (c) 2025 Matveev Nikita

## Acknowledgments

- Keysight Technologies for IC-CAP and WaferPro software
- The pandas and numpy communities

---

**Keywords:** IC-CAP, WaferPro, Keysight,Agilent, MDM parser, semiconductor measurement, device characterization, measurement data analysis, statistic
