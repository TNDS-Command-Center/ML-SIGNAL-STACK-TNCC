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
from fix_root_workbooks import run_root_workbook_fixes

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

EXPORT_MAP = {

    # Sales — tnds-sales-data-template.xlsx, RAW_INPUT tab
    # Layout: row 0=title, row 1=subtitle, row 2=col headers, rows 3+=data
    "sales": {
        "workbook":  os.path.join(BASE_DIR, "tnds-sales-data-template.xlsx"),
        "sheet":     "RAW_INPUT",
        "skip_rows": 2,
        "mode":      "sales_from_raw",
        "keep_cols": ["Date", "Qty", "Sales Price"],
    },

    # Ops Pulse — Weekly Log tab, row 2=headers, row 3 includes auto-calc label row, row 4+=data
    "ops_pulse": {
        "workbook":  os.path.join(BASE_DIR, "SignalStack_OpsPulse.xlsx"),
        "sheet":     "Weekly Log",
        "skip_rows": 2,
        "mode":      "ops_from_log",
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

    # Team Tempo — aggregate from Hours Log (+ Roster fallback for headcount)
    "team_tempo": {
        "workbook":  os.path.join(BASE_DIR, "SignalStack_TeamTempo.xlsx"),
        "sheet":     "Hours Log",
        "roster_sheet": "Roster",
        "skip_rows": 2,
        "mode":      "tempo_from_log",
        "keep_cols": ["Week", "Headcount", "Billable Hrs", "OT Hrs",
                      "Utilization %", "Turnover", "Training Hrs"],
    },
}


def _norm_col(col):
    """Normalize header names for resilient matching (handles newlines/spaces/case)."""
    return " ".join(str(col).replace("\n", " ").replace("\r", " ").strip().lower().split())


def _find_col(df, aliases, required=True):
    """
    Find a column by one of several aliases using normalized matching.
    Returns the actual dataframe column name or None.
    """
    alias_norm = {_norm_col(a) for a in aliases}
    for col in df.columns:
        if _norm_col(col) in alias_norm:
            return col

    if required:
        print(f"[export] WARNING: missing required column aliases: {aliases}")
        print(f"[export]   Available: {list(df.columns)}")
    return None


def _parse_dates_flexible(series):
    """
    Parse dates with a fast fixed-format pass first, then fallback parse for stragglers.
    Avoids noisy infer-format warnings on mixed cells.
    """
    parsed = pd.to_datetime(series, format="%m/%d/%Y", errors="coerce")
    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(series.loc[missing], errors="coerce")
    return parsed


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


def export_sales_from_raw(source_name, src, export_cfg):
    """
    Sales export from RAW_INPUT tab.
    Keeps Date, Qty, Sales Price (transaction-level rows, no aggregation).
    """
    wb_path = export_cfg["workbook"]
    sheet = export_cfg["sheet"]
    skiprows = export_cfg["skip_rows"]

    df = pd.read_excel(wb_path, sheet_name=sheet, skiprows=skiprows,
                       header=0, engine="openpyxl")
    df = df.dropna(how="all").dropna(axis=1, how="all")
    if df.empty:
        print(f"[export] WARNING: RAW_INPUT tab is empty.")
        return pd.DataFrame()

    date_col = _find_col(df, ["Date"])
    qty_col = _find_col(df, ["Qty", "Quantity"])
    price_col = _find_col(df, ["Sales Price", "Rate", "Price"])
    total_col = _find_col(df, ["Total Sales", "Amount"], required=False)

    if not all([date_col, qty_col, price_col]):
        return pd.DataFrame()

    df["__date"] = _parse_dates_flexible(df[date_col])
    df = df.dropna(subset=["__date"])
    if df.empty:
        print(f"[export] WARNING: no valid sales rows after date parsing.")
        return pd.DataFrame()

    qty = pd.to_numeric(df[qty_col], errors="coerce")
    price = pd.to_numeric(df[price_col], errors="coerce")

    # If Qty/Price are missing but Total Sales exists, backfill as Qty=1, Price=Total.
    if total_col and total_col in df.columns:
        total = pd.to_numeric(df[total_col], errors="coerce")
        mask_total_only = qty.isna() & price.isna() & total.notna()
        qty.loc[mask_total_only] = 1
        price.loc[mask_total_only] = total.loc[mask_total_only]

    result = pd.DataFrame({
        "Date": df["__date"].dt.strftime("%m/%d/%Y"),
        "Qty": qty.fillna(0),
        "Sales Price": price.fillna(0),
    })

    result = result.dropna(subset=["Date"])
    return result


def export_ops_from_log(source_name, src, export_cfg):
    """
    Ops Pulse export from Weekly Log (per-job rows) aggregated to ISO week.
    Output columns:
      Week, Jobs Done, On-Time %, Callback %, Avg Hours, Utilization %, Open WOs
    """
    wb_path = export_cfg["workbook"]
    sheet = export_cfg["sheet"]
    skiprows = export_cfg["skip_rows"]

    df = pd.read_excel(wb_path, sheet_name=sheet, skiprows=skiprows,
                       header=0, engine="openpyxl")
    df = df.dropna(how="all").dropna(axis=1, how="all")
    if df.empty:
        print(f"[export] WARNING: Weekly Log tab is empty.")
        return pd.DataFrame()

    date_col = _find_col(df, ["Date"])
    jobs_col = _find_col(df, ["Jobs Completed", "Jobs"])
    sched_col = _find_col(df, ["Scheduled Time (h)", "Scheduled Time"])
    actual_col = _find_col(df, ["Actual Time (h)", "Actual Time"])
    ontime_col = _find_col(df, ["On Time? (Y/N)", "On Time"])
    callback_col = _find_col(df, ["Callback? (Y/N)", "Callback"])
    open_wos_col = _find_col(df, ["Open WOs", "Open WOs"], required=False)

    if not all([date_col, jobs_col, sched_col, actual_col, ontime_col, callback_col]):
        return pd.DataFrame()

    df["__date"] = _parse_dates_flexible(df[date_col])
    df = df.dropna(subset=["__date"])
    if df.empty:
        print(f"[export] WARNING: no valid ops rows after date parsing.")
        return pd.DataFrame()

    df["__week"] = df["__date"].dt.strftime("%G-W%V")
    df["__jobs"] = pd.to_numeric(df[jobs_col], errors="coerce").fillna(0)
    df["__sched"] = pd.to_numeric(df[sched_col], errors="coerce").fillna(0)
    df["__actual"] = pd.to_numeric(df[actual_col], errors="coerce").fillna(0)
    df["__on_time"] = df[ontime_col].astype(str).str.strip().str.upper().eq("Y").astype(int)
    df["__callback"] = df[callback_col].astype(str).str.strip().str.upper().eq("Y").astype(int)

    if open_wos_col and open_wos_col in df.columns:
        df["__open_wos"] = pd.to_numeric(df[open_wos_col], errors="coerce")
    else:
        print(f"[export] INFO: Open WOs column missing in Weekly Log; defaulting to 0.")
        df["__open_wos"] = 0

    grouped = df.groupby("__week", as_index=False).agg(
        Jobs_Done=("__jobs", "sum"),
        On_Time_Rate=("__on_time", "mean"),
        Callback_Rate=("__callback", "mean"),
        Avg_Hours=("__actual", "mean"),
        Actual_Sum=("__actual", "sum"),
        Scheduled_Sum=("__sched", "sum"),
        Open_WOs=("__open_wos", "last"),
    )

    grouped["Utilization_Pct"] = grouped.apply(
        lambda r: (r["Actual_Sum"] / r["Scheduled_Sum"]) if r["Scheduled_Sum"] > 0 else 0,
        axis=1,
    )
    grouped["Open_WOs"] = pd.to_numeric(grouped["Open_WOs"], errors="coerce").fillna(0)

    # Stable weekly ordering
    grouped["__week_date"] = pd.to_datetime(
        grouped["__week"] + "-1", format="%G-W%V-%u", errors="coerce"
    )
    grouped = grouped.sort_values("__week_date")

    result = grouped[[
        "__week", "Jobs_Done", "On_Time_Rate", "Callback_Rate",
        "Avg_Hours", "Utilization_Pct", "Open_WOs"
    ]].copy()
    result.columns = ["Week", "Jobs Done", "On-Time %", "Callback %",
                      "Avg Hours", "Utilization %", "Open WOs"]
    return result


def export_tempo_from_log(source_name, src, export_cfg):
    """
    Team Tempo export from Hours Log, with Roster fallback for headcount.
    Output columns:
      Week, Headcount, Billable Hrs, OT Hrs, Utilization %, Turnover, Training Hrs
    """
    wb_path = export_cfg["workbook"]
    sheet = export_cfg["sheet"]
    roster_sheet = export_cfg.get("roster_sheet", "Roster")
    skiprows = export_cfg["skip_rows"]

    hours = pd.read_excel(wb_path, sheet_name=sheet, skiprows=skiprows,
                          header=0, engine="openpyxl")
    hours = hours.dropna(how="all").dropna(axis=1, how="all")
    if hours.empty:
        print(f"[export] WARNING: Hours Log tab is empty.")
        return pd.DataFrame()

    roster = pd.read_excel(wb_path, sheet_name=roster_sheet, skiprows=skiprows,
                           header=0, engine="openpyxl")
    roster = roster.dropna(how="all").dropna(axis=1, how="all")

    week_col = _find_col(hours, ["Week Of", "Week"])
    employee_col = _find_col(hours, ["Employee"])
    regular_col = _find_col(hours, ["Regular Hrs", "Regular Hours"])
    ot_col = _find_col(hours, ["OT Hrs", "Overtime Hrs"])
    training_col = _find_col(hours, ["Training Hrs", "Training Hours"])
    if not all([week_col, employee_col, regular_col, ot_col, training_col]):
        return pd.DataFrame()

    hours["__week_date"] = _parse_dates_flexible(hours[week_col])
    hours = hours.dropna(subset=["__week_date"])
    if hours.empty:
        print(f"[export] WARNING: no valid team tempo rows after date parsing.")
        return pd.DataFrame()

    hours["__week"] = hours["__week_date"].dt.strftime("%G-W%V")
    hours["__employee"] = hours[employee_col].astype(str).str.strip()
    hours["__regular"] = pd.to_numeric(hours[regular_col], errors="coerce").fillna(0)
    hours["__ot"] = pd.to_numeric(hours[ot_col], errors="coerce").fillna(0)
    hours["__training"] = pd.to_numeric(hours[training_col], errors="coerce").fillna(0)
    hours["__billable"] = hours["__regular"] + hours["__ot"]

    grouped = hours.groupby("__week", as_index=False).agg(
        Headcount=("__employee", "nunique"),
        Billable_Hrs=("__billable", "sum"),
        OT_Hrs=("__ot", "sum"),
        Training_Hrs=("__training", "sum"),
    )

    # Roster fallback for sparse hours logs
    active_count = 0
    if not roster.empty:
        r_status_col = _find_col(roster, ["Status"], required=False)
        r_employee_col = _find_col(roster, ["Employee"], required=False)
        if r_employee_col:
            if r_status_col:
                active_mask = roster[r_status_col].astype(str).str.strip().str.lower().eq("active")
                active_count = roster.loc[active_mask, r_employee_col].astype(str).str.strip().nunique()
            else:
                active_count = roster[r_employee_col].astype(str).str.strip().nunique()

    if active_count > 0:
        grouped["Headcount"] = grouped["Headcount"].replace(0, active_count)

    grouped["Utilization_Pct"] = grouped.apply(
        lambda r: (r["Billable_Hrs"] / (r["Headcount"] * 40)) if r["Headcount"] > 0 else 0,
        axis=1,
    )

    # Default turnover (status-change tracking requires roster snapshots over time).
    grouped["Turnover"] = 0

    # Stable weekly ordering
    grouped["__week_date"] = pd.to_datetime(
        grouped["__week"] + "-1", format="%G-W%V-%u", errors="coerce"
    )
    grouped = grouped.sort_values("__week_date")

    result = grouped[[
        "__week", "Headcount", "Billable_Hrs", "OT_Hrs",
        "Utilization_Pct", "Turnover", "Training_Hrs"
    ]].copy()
    result.columns = ["Week", "Headcount", "Billable Hrs", "OT Hrs",
                      "Utilization %", "Turnover", "Training Hrs"]
    return result


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
        if mode == "sales_from_raw":
            df = export_sales_from_raw(source_name, src, export_cfg)
        elif mode == "ops_from_log":
            df = export_ops_from_log(source_name, src, export_cfg)
        elif mode == "tempo_from_log":
            df = export_tempo_from_log(source_name, src, export_cfg)
        elif mode == "cash_flow":
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


def run_pre_export_integrity_pass():
    """
    Normalize root workbook data types and known formula compatibility issues
    before any CSV export.
    """
    print("\n[export] Running root workbook integrity pass...\n")
    try:
        summary = run_root_workbook_fixes()
        print(
            "\n[export] Root workbook integrity pass complete. "
            f"Files updated: {summary.get('changed_files', 0)}"
        )
        if summary.get("errors"):
            print(f"[export] WARNING: integrity pass errors: {summary['errors']}")
    except Exception as e:
        print(f"[export] WARNING: integrity pass failed, continuing export. Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="SignalStack — Export Excel to CSV.")
    parser.add_argument("--source", default="all",
                        help="Source name or 'all'. Default: all")
    parser.add_argument("--skip-root-fix", action="store_true",
                        help="Skip root workbook integrity pass before export.")
    args = parser.parse_args()

    if not args.skip_root_fix:
        run_pre_export_integrity_pass()

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
