"""
export_to_csv.py — SignalStack: Batch Excel-to-CSV export utility.
==================================================================
Reads each workbook's correct tab and writes clean CSVs into
data/raw/<source>/ for the pipeline to consume.

Usage:
    python export_to_csv.py              # export all sources
    python export_to_csv.py --source ops_pulse

Actual row layout in Dashboard tabs (0-indexed):
    0  Title (merged)
    1  Subtitle (merged)
    2  Spacer null
    3  KPI section header (merged)
    4  KPI labels
    5  KPI values
    6  Spacer null
    7  Trend section header (merged)
    8  Column headers  <-- skip_rows=8
    9+ Data rows
"""

import pandas as pd
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import get_source, SOURCE_REGISTRY

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

EXPORT_MAP = {

    # Sales — tnds-sales-data-template.xlsx, PIPELINE_READY tab
    # Layout: row 0=title, row 1=subtitle, row 2=col headers, rows 3+=data
    "sales": {
        "workbook":  os.path.join(BASE_DIR, "tnds-sales-data-template.xlsx"),
        "sheet":     "PIPELINE_READY",
        "skip_rows": 2,
        "mode":      "standard",
        "keep_cols": ["Date", "Qty", "Sales Price"],
    },

    # Ops Pulse — Dashboard tab, row 8 = headers
    # Headers: Week, Jobs Done, On-Time %, Callback %, Avg Hours, Utilization %, Open WOs, Notes
    "ops_pulse": {
        "workbook":  os.path.join(BASE_DIR, "SignalStack_OpsPulse.xlsx"),
        "sheet":     "Dashboard",
        "skip_rows": 8,
        "mode":      "standard",
        "keep_cols": ["Week", "Jobs Done", "On-Time %", "Callback %",
                      "Avg Hours", "Utilization %", "Open WOs"],
    },

    # Cash Flow Compass — Weekly Position tab, row 8 = headers
    # Note: "Net Change" and "Ending Balance" are Excel formula cells — they export
    # as null. We compute them from the raw columns in export_standard().
    "cash_flow_compass": {
        "workbook":  os.path.join(BASE_DIR, "SignalStack_CashFlowCompass.xlsx"),
        "sheet":     "Weekly Position",
        "skip_rows": 8,
        "mode":      "cash_flow",
        "keep_cols": ["Week Of", "Cash on Hand", "AR Collected", "AP Paid",
                      "Revenue In", "Expenses Out"],
    },

    # Pipeline Pulse — no weekly trend table on Dashboard.
    # Pull from Pipeline Log, aggregate deal count + value by week entered.
    "pipeline_pulse": {
        "workbook":  os.path.join(BASE_DIR, "SignalStack_PipelinePulse.xlsx"),
        "sheet":     "Pipeline Log",
        "skip_rows": 2,
        "mode":      "aggregate_weekly",
        "date_col":  "Date Entered",
        "value_col": "Est. Value",
    },

    # Team Tempo — Dashboard tab, row 8 = headers
    # Headers: Week, Headcount, Billable Hrs, OT Hrs, Utilization %, Turnover, Training Hrs, Notes
    "team_tempo": {
        "workbook":  os.path.join(BASE_DIR, "SignalStack_TeamTempo.xlsx"),
        "sheet":     "Dashboard",
        "skip_rows": 8,
        "mode":      "standard",
        "keep_cols": ["Week", "Headcount", "Billable Hrs", "OT Hrs",
                      "Utilization %", "Turnover", "Training Hrs"],
    },
}


def export_standard(source_name, src, export_cfg):
    """Read sheet at skip_rows, filter to keep_cols, drop blank date rows."""
    wb_path  = export_cfg["workbook"]
    sheet    = export_cfg["sheet"]
    skiprows = export_cfg["skip_rows"]

    df = pd.read_excel(wb_path, sheet_name=sheet, skiprows=skiprows,
                       header=0, engine="openpyxl")
    df = df.dropna(how="all").dropna(axis=1, how="all")

    keep = export_cfg.get("keep_cols")
    if keep:
        present = [c for c in keep if c in df.columns]
        missing = [c for c in keep if c not in df.columns]
        if missing:
            print(f"[export] WARNING: columns not found: {missing}")
            print(f"[export]   Available: {list(df.columns)}")
        df = df[present]

    date_col = src["date_column"]
    if date_col in df.columns:
        df = df.dropna(subset=[date_col])
    else:
        print(f"[export] WARNING: date column '{date_col}' not found.")
        print(f"[export]   Available: {list(df.columns)}")

    return df


def export_cash_flow(source_name, src, export_cfg):
    """
    Cash Flow Compass export.
    Excel formula cells (Net Change, Ending Balance) come through as null.
    Compute both from Revenue In - Expenses Out, and Cash on Hand + Net Change.
    Drop placeholder future rows where Cash on Hand is blank.
    """
    wb_path  = export_cfg["workbook"]
    sheet    = export_cfg["sheet"]
    skiprows = export_cfg["skip_rows"]
    keep     = export_cfg.get("keep_cols", [])

    df = pd.read_excel(wb_path, sheet_name=sheet, skiprows=skiprows,
                       header=0, engine="openpyxl")
    df = df.dropna(how="all").dropna(axis=1, how="all")

    present = [c for c in keep if c in df.columns]
    df = df[present]

    # Drop future placeholder rows (blank Cash on Hand)
    if "Cash on Hand" in df.columns:
        df = df.dropna(subset=["Cash on Hand"])

    # Coerce numerics
    for col in ["Cash on Hand", "AR Collected", "AP Paid", "Revenue In", "Expenses Out"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Compute derived columns (Excel formulas don't export)
    df["Net Change"]     = df["Revenue In"] - df["Expenses Out"]
    df["Ending Balance"] = df["Cash on Hand"] + df["Net Change"]

    date_col = src["date_column"]
    if date_col in df.columns:
        df = df.dropna(subset=[date_col])

    return df


def export_aggregate_weekly(source_name, src, export_cfg):
    """Read Pipeline Log, group by ISO week, sum value + count deals."""
    wb_path  = export_cfg["workbook"]
    sheet    = export_cfg["sheet"]
    skiprows = export_cfg["skip_rows"]
    date_col = export_cfg["date_col"]
    val_col  = export_cfg["value_col"]

    df = pd.read_excel(wb_path, sheet_name=sheet, skiprows=skiprows,
                       header=0, engine="openpyxl")
    df = df.dropna(how="all")

    if date_col not in df.columns:
        print(f"[export] WARNING: '{date_col}' not found. Columns: {list(df.columns)}")
        return pd.DataFrame()

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df[val_col]  = pd.to_numeric(df[val_col], errors="coerce").fillna(0)

    df["Week"] = df[date_col].dt.strftime("%G-W%V")

    result = df.groupby("Week").agg(
        Pipeline_Value=(val_col, "sum"),
        Deal_Count=(date_col, "count"),
    ).reset_index()
    result.columns = ["Week", "Pipeline Value", "Deal Count"]

    return result


def export_source(source_name):
    if source_name not in EXPORT_MAP:
        print(f"[export] Unknown source: '{source_name}'")
        return False

    src        = get_source(source_name)
    export_cfg = EXPORT_MAP[source_name]
    wb_path    = export_cfg["workbook"]
    mode       = export_cfg.get("mode", "standard")

    print(f"\n[export] Source:    {source_name}")
    print(f"[export] Workbook:  {wb_path}")
    print(f"[export] Sheet:     {export_cfg['sheet']}")
    print(f"[export] Mode:      {mode}")

    if not os.path.exists(wb_path):
        print(f"[export] SKIPPED — workbook not found.")
        print(f"[export] Expected: {wb_path}")
        return False

    try:
        if mode == "cash_flow":
            df = export_cash_flow(source_name, src, export_cfg)
        elif mode == "aggregate_weekly":
            df = export_aggregate_weekly(source_name, src, export_cfg)
        else:
            df = export_standard(source_name, src, export_cfg)
    except Exception as e:
        print(f"[export] ERROR: {e}")
        return False

    if df is None or len(df) == 0:
        print(f"[export] WARNING: 0 rows — nothing written.")
        return False

    out_dir  = src["data_raw"]
    out_path = src["file_path"]
    os.makedirs(out_dir, exist_ok=True)
    df.to_csv(out_path, index=False)

    print(f"[export] Columns:       {list(df.columns)}")
    print(f"[export] Rows exported: {len(df)}")
    print(f"[export] CSV written:   {out_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="SignalStack — Export Excel to CSV.")
    parser.add_argument("--source", default="all",
                        help="Source name or 'all'. Default: all")
    args = parser.parse_args()

    if args.source == "all":
        print("\n[export] Exporting all SignalStack sources...\n")
        results = {}
        for name in EXPORT_MAP:
            ok = export_source(name)
            results[name] = "OK" if ok else "SKIPPED"

        print("\n" + "=" * 50)
        print("  EXPORT SUMMARY")
        print("=" * 50)
        for name, status in results.items():
            print(f"  {name:<25} {status}")
        print("=" * 50)
        print("\nNext: python run_pipeline.py --source all\n")
    else:
        if args.source not in EXPORT_MAP:
            print(f"[export] Unknown source: '{args.source}'")
            print(f"[export] Available: {list(EXPORT_MAP.keys())}")
            sys.exit(1)
        export_source(args.source)


if __name__ == "__main__":
    main()
