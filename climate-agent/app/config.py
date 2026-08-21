"""Central place for paths and constants. No logic lives here."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
PROCESSED_FILE = PROCESSED_DATA_DIR / "sml2010.parquet"

RAW_FILES = [
    RAW_DATA_DIR / "NEW-DATA-1.T15.txt",
    RAW_DATA_DIR / "NEW-DATA-2.T15.txt",
]

DEFAULT_TMIN = 22.0
DEFAULT_TMAX = 25.0
