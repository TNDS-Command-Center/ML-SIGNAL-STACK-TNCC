"""
data_loader.py — SignalStack: Source-aware CSV loader.
======================================================
Handles three date formats found across SignalStack sources:
  - Standard dates:   03/01/2025, 2025-03-01  (sales, cash_flow_compass)
  - ISO week strings: 2025-W09                (ops_pulse, team_tempo, pipeline_pulse)

ISO week strings are converted to the Monday of that week before
being passed to the time series index. This lets pandas reindex
them correctly at weekly frequency.
"""

import pandas as pd
import re
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _parse_dates(series):
    """
    Parse a date column that may contain standard dates OR ISO week strings.

    ISO week format '2025-W09' is converted to the Monday of that week
    using pd.to_datetime with format='%G-W%V-%u' (appending '-1' = Monday).

    Falls back to standard pd.to_datetime for all other formats.

    Parameters:
        series (pd.Series): Raw date column as strings.

    Returns:
        pd.Series: Parsed datetime series. NaT where parsing fails.
    """
    sample = series.dropna().astype(str).iloc[0] if len(series.dropna()) > 0 else ""

    # Detect ISO week pattern e.g. "2025-W09" or "2025-W9"
    if re.match(r"^\d{4}-W\d{1,2}$", sample.strip()):
        # Append '-1' = Monday, then parse as ISO week-date
        week_monday = series.astype(str).str.strip() + "-1"
        parsed = pd.to_datetime(week_monday, format="%G-W%V-%u", errors="coerce")
        print(f"[data_loader] Date format: ISO week (converted to Monday dates)")
        return parsed

    # Standard date parsing
    parsed = pd.to_datetime(series, errors="coerce")
    print(f"[data_loader] Date format: standard")
    return parsed


def load_data(src, file_path=None):
    """
    Load a SignalStack source CSV and return a prepared time series.

    Parameters:
        src (dict):       Source config from config.get_source().
        file_path (str):  Override CSV path (optional).

    Returns:
        tuple: (raw_dataframe, time_series)

    Raises:
        FileNotFoundError if CSV is missing.
        ValueError if required columns are absent or data too short to model.
    """
    path = file_path or src["file_path"]

    print(f"\n[data_loader] Source:  {src['raw_subdir']}")
    print(f"[data_loader] Target:  {src['target_column']}")
    print(f"[data_loader] Loading: {path}")

    # ── Load CSV ──────────────────────────────────────────────────────────────
    try:
        data = pd.read_csv(path, on_bad_lines="skip", encoding=src["encoding"])
    except FileNotFoundError:
        print(f"\n[data_loader] ERROR: File not found.")
        print(f"[data_loader] Expected: {path}")
        print(f"[data_loader] Export instructions: {src.get('sheet_notes', 'See README')}")
        raise
    except Exception as e:
        print(f"[data_loader] ERROR loading file: {e}")
        raise

    data.columns = data.columns.str.strip()
    print(f"[data_loader] Columns found: {list(data.columns)}")
    print(f"[data_loader] Shape: {data.shape}")

    # ── Drop fully blank rows (future-dated placeholder rows in Excel) ────────
    data = data.dropna(how="all")

    # ── Validate required columns ─────────────────────────────────────────────
    required = [src["date_column"]]
    if src["qty_column"] and src["price_column"]:
        required += [src["qty_column"], src["price_column"]]
    elif src["target_column"] in data.columns:
        required.append(src["target_column"])
    else:
        raise ValueError(
            f"[data_loader] Cannot find target column '{src['target_column']}'. "
            f"Columns available: {list(data.columns)}"
        )

    missing = [c for c in required if c not in data.columns]
    if missing:
        raise ValueError(
            f"[data_loader] Missing required columns: {missing}\n"
            f"[data_loader] Export instructions: {src.get('sheet_notes', 'See README')}"
        )

    # ── Parse dates — handles standard dates AND ISO week strings ────────────
    data[src["date_column"]] = _parse_dates(data[src["date_column"]])
    bad_dates = data[src["date_column"]].isna().sum()
    if bad_dates > 0:
        print(f"[data_loader] Warning: {bad_dates} rows dropped (unparseable dates).")
    data = data.dropna(subset=[src["date_column"]])
    data = data.sort_values(by=src["date_column"])

    # ── Compute or coerce target column ───────────────────────────────────────
    if src["qty_column"] and src["price_column"]:
        data[src["qty_column"]]    = pd.to_numeric(data[src["qty_column"]],    errors="coerce").fillna(0)
        data[src["price_column"]]  = pd.to_numeric(data[src["price_column"]],  errors="coerce").fillna(0)
        data[src["target_column"]] = data[src["qty_column"]] * data[src["price_column"]]
        print(f"[data_loader] Target computed: {src['qty_column']} x {src['price_column']}")
    else:
        data[src["target_column"]] = pd.to_numeric(data[src["target_column"]], errors="coerce").fillna(0)

    # ── Coerce extra signal columns ───────────────────────────────────────────
    for _, col_name in src.get("extra_signals", {}).items():
        if col_name in data.columns:
            data[col_name] = pd.to_numeric(data[col_name], errors="coerce").fillna(0)

    # ── Aggregate by date ─────────────────────────────────────────────────────
    data = data.groupby(src["date_column"], as_index=False)[src["target_column"]].sum()

    # ── Build time series ─────────────────────────────────────────────────────
    time_series = data.set_index(src["date_column"])[src["target_column"]]
    time_series = time_series.asfreq(src["frequency"], method=src["fill_method"])
    time_series.index.freq = src["frequency"]

    print(f"[data_loader] Date range: {time_series.index.min()} -> {time_series.index.max()}")
    print(f"[data_loader] Periods:    {len(time_series)}")
    print(f"[data_loader] Target:     {time_series.min():.2f} - {time_series.max():.2f}")

    # ── Minimum data check ────────────────────────────────────────────────────
    # Need at least validation_size + seasonal_period + 2 to train any model.
    min_required = src["validation_size"] + src["seasonal_period"] + 2
    if len(time_series) < min_required:
        raise ValueError(
            f"[data_loader] Not enough data to model '{src['raw_subdir']}'.\n"
            f"[data_loader]   Have:  {len(time_series)} periods\n"
            f"[data_loader]   Need:  {min_required} (validation_size={src['validation_size']} "
            f"+ seasonal_period={src['seasonal_period']} + 2)\n"
            f"[data_loader]   Fix:   Add more rows to the Excel workbook and re-export."
        )

    print(f"[data_loader] Done.\n")
    return data, time_series


if __name__ == "__main__":
    import argparse
    from config import get_source

    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="ops_pulse")
    args = parser.parse_args()

    src = get_source(args.source)
    df, ts = load_data(src)
    print(f"\nFirst 5:\n{ts.head()}")
    print(f"\nLast 5:\n{ts.tail()}")
