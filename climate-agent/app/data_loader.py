"""
Loads the SML2010 dataset (NEW-DATA-1.T15.txt / NEW-DATA-2.T15.txt) into a
clean, chronologically-sorted pandas DataFrame, with a parquet cache so the
raw whitespace-delimited text files only get re-parsed when they change.

Usage:
    from app.data_loader import load_and_cache, agent_view

    df = load_and_cache()          # full dataset, all 24 columns
    slim = agent_view(df)          # just what the agent needs to run
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.config import PROCESSED_FILE, RAW_FILES

# Column order exactly as documented in the dataset's header comment line.
RAW_COLUMNS = [
    "Date",
    "Time",
    "Temperature_Comedor_Sensor",
    "Temperature_Habitacion_Sensor",
    "Weather_Temperature",
    "CO2_Comedor_Sensor",
    "CO2_Habitacion_Sensor",
    "Humedad_Comedor_Sensor",
    "Humedad_Habitacion_Sensor",
    "Lighting_Comedor_Sensor",
    "Lighting_Habitacion_Sensor",
    "Precipitacion",
    "Meteo_Exterior_Crepusculo",
    "Meteo_Exterior_Viento",
    "Meteo_Exterior_Sol_Oest",
    "Meteo_Exterior_Sol_Est",
    "Meteo_Exterior_Sol_Sud",
    "Meteo_Exterior_Piranometro",
    "Exterior_Entalpic_1",
    "Exterior_Entalpic_2",
    "Exterior_Entalpic_turbo",
    "Temperature_Exterior_Sensor",
    "Humedad_Exterior_Sensor",
    "Day_Of_Week",
]


def _parse_raw_file(path: Path) -> pd.DataFrame:
    """Parse a single NEW-DATA-*.T15.txt file into a typed DataFrame."""
    if not path.exists():
        raise FileNotFoundError(f"SML2010 raw file not found: {path}")

    df = pd.read_csv(
        path,
        sep=r"\s+",
        comment="#",
        header=None,
        names=RAW_COLUMNS,
        engine="python",
    )

    df["timestamp"] = pd.to_datetime(
        df["Date"] + " " + df["Time"], format="%d/%m/%Y %H:%M"
    )
    df = df.drop(columns=["Date", "Time"])

    cols = ["timestamp"] + [c for c in df.columns if c != "timestamp"]
    return df[cols]


def load_raw(paths: list[Path] = RAW_FILES) -> pd.DataFrame:
    """Parse and concatenate all raw SML2010 chunks into one sorted DataFrame."""
    frames = [_parse_raw_file(p) for p in paths]
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset="timestamp", keep="first")
    combined = combined.sort_values("timestamp").reset_index(drop=True)
    return combined


def load_and_cache(force_refresh: bool = False) -> pd.DataFrame:
    """
    Return the full parsed dataset, using a parquet cache to skip re-parsing
    the raw text files on every startup. Pass force_refresh=True after the
    raw files change.
    """
    if PROCESSED_FILE.exists() and not force_refresh:
        return pd.read_parquet(PROCESSED_FILE)

    df = load_raw()
    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PROCESSED_FILE, index=False)
    return df


def agent_view(df: pd.DataFrame) -> pd.DataFrame:
    """
    Slim projection with only what the temperature agent needs to run,
    renamed to plain English so agent.py / simulator.py don't touch
    dataset-specific column names.
    """
    return df[
        ["timestamp", "Temperature_Habitacion_Sensor", "Temperature_Exterior_Sensor"]
    ].rename(
        columns={
            "Temperature_Habitacion_Sensor": "room_temp",
            "Temperature_Exterior_Sensor": "outdoor_temp",
        }
    )


if __name__ == "__main__":
    # Quick manual sanity check: python -m app.data_loader
    full = load_and_cache(force_refresh=True)
    print(f"Loaded {len(full)} rows, {full['timestamp'].min()} -> {full['timestamp'].max()}")
    print(full.dtypes)
    print()
    print(agent_view(full).head())
