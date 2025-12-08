import pandas as pd
from typing import List

class WProProcessor:
    """Processor for WPro.csv measurement result files."""
    
    def __init__(self, filepath: str):
        """
        Initialize the processor with a WPro.csv file.
        
        Args:
            filepath: Path to the WPro.csv file
        """
        self.filepath = filepath
        self._df = None
        self._load_data()
    
    def _load_data(self):
        """Load the CSV file, skipping header comment lines."""
        # Read file and find where actual data starts (skip lines starting with *)
        with open(self.filepath, 'r') as f:
            lines = f.readlines()
        
        # Find the header row (first line not starting with *)
        skip_rows = 0
        for i, line in enumerate(lines):
            if not line.strip().startswith('*'):
                skip_rows = i
                break
        
        self._df = pd.read_csv(self.filepath, skiprows=skip_rows)
    
    @property
    def dataframe(self) -> pd.DataFrame:
        """Return the loaded DataFrame."""
        return self._df
    
    def get_unique_wafer(self) -> List[str]:
        """Return unique Wafer values."""
        return self._df['Wafer'].unique().tolist()
    
    def get_unique_die(self) -> List[str]:
        """Return unique Die values."""
        return self._df['Die'].unique().tolist()
    
    def get_unique_temperature(self) -> List:
        """Return unique Temperature values."""
        return self._df['Temperature (C)'].unique().tolist()
    
    def get_unique_block(self) -> List[str]:
        """Return unique Block values."""
        return self._df['Block'].unique().tolist()
    
    def get_unique_subsite(self) -> List[str]:
        """Return unique Subsite values."""
        return self._df['Subsite'].unique().tolist()
    
    def get_unique_name(self) -> List[str]:
        """Return unique Name values."""
        return self._df['Name'].unique().tolist()
    
    def get_result_columns(self) -> List[str]:
        """
        Return column names between '$' and 'ResultRead' (exclusive).
        These are the measurement result columns.
        """
        columns = self._df.columns.tolist()
        
        try:
            start_idx = columns.index('$')
            end_idx = columns.index('ResultRead')
            # Exclude '$' (start_idx + 1) and 'ResultRead' (end_idx)
            return columns[start_idx + 1:end_idx]
        except ValueError:
            # If columns not found, return empty list
            return []


# Convenience functions for standalone usage
def load_wpro(filepath: str) -> WProProcessor:
    """Load a WPro.csv file and return a processor instance."""
    return WProProcessor(filepath)


def get_unique_wafer(filepath: str) -> List[str]:
    """Return unique Wafer values from a WPro.csv file."""
    return WProProcessor(filepath).get_unique_wafer()


def get_unique_die(filepath: str) -> List[str]:
    """Return unique Die values from a WPro.csv file."""
    return WProProcessor(filepath).get_unique_die()


def get_unique_temperature(filepath: str) -> List:
    """Return unique Temperature values from a WPro.csv file."""
    return WProProcessor(filepath).get_unique_temperature()


def get_unique_block(filepath: str) -> List[str]:
    """Return unique Block values from a WPro.csv file."""
    return WProProcessor(filepath).get_unique_block()


def get_unique_subsite(filepath: str) -> List[str]:
    """Return unique Subsite values from a WPro.csv file."""
    return WProProcessor(filepath).get_unique_subsite()


def get_unique_name(filepath: str) -> List[str]:
    """Return unique Name values from a WPro.csv file."""
    return WProProcessor(filepath).get_unique_name()


def get_result_columns(filepath: str) -> List[str]:
    """Return column names from '$' to 'ResultRead' from a WPro.csv file."""
    return WProProcessor(filepath).get_result_columns()

if __name__ == "__main__":

    processor = load_wpro("/Users/sorrymusic/VScode/Projects/mdm library/WPro.csv")
    
    print("Unique Wafers:", processor.get_unique_wafer())
    print("Unique Dies:", processor.get_unique_die())
    print("Unique Temperatures:", processor.get_unique_temperature())
    print("Unique Blocks:", processor.get_unique_block())
    print("Unique Subsites:", processor.get_unique_subsite())
    print("Unique Names:", processor.get_unique_name())
    print("Result Columns:", processor.get_result_columns())

