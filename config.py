"""
config.py — SignalStack: Central configuration and source registry.
===================================================================
All paths, model defaults, and per-source schema definitions live here.
Each SignalStack data source (sales, ops_pulse, cash_flow_compass,
pipeline_pulse, team_tempo) has its own entry in SOURCE_REGISTRY.

To run the pipeline for a specific source:
    python run_pipeline.py --source sales
    python run_pipeline.py --source ops_pulse --skip-search

To add a new source, add an entry to SOURCE_REGISTRY.
Everything else (preprocessor, model, evaluator, visualizer) is generic.
"""

import os

# ── Paths ────────────────────────────────────────────────────────────────────

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
DATA_RAW       = os.path.join(BASE_DIR, "data", "raw")
DATA_PROCESSED = os.path.join(BASE_DIR, "data", "processed")
DATA_OUTPUT    = os.path.join(BASE_DIR, "data", "output")
MODELS_DIR     = os.path.join(BASE_DIR, "models")
VISUALS_DIR    = os.path.join(BASE_DIR, "visuals")

# ── Model defaults (overridden per source in SOURCE_REGISTRY) ────────────────

ENCODING            = "utf-8"
FILL_METHOD         = "pad"
OUTLIER_METHOD      = "iqr"
IQR_MULTIPLIER      = 1.5
ZSCORE_THRESHOLD    = 3
OUTLIER_REPLACEMENT = "median"
SMOOTHING_SPAN      = 14
VALIDATION_SIZE     = 60
LOG_TRANSFORM       = True
SARIMA_P_RANGE      = range(0, 3)
SARIMA_D_RANGE      = range(0, 2)
SARIMA_Q_RANGE      = range(0, 3)
SARIMA_SEASONAL_P   = range(0, 3)
SARIMA_SEASONAL_D   = range(0, 2)
SARIMA_SEASONAL_Q   = range(0, 3)
SEASONAL_PERIOD     = 12
MAX_ITER_SEARCH     = 100
MAX_ITER_FINAL      = 500
TOLERANCE_SEARCH    = 1e-4
TOLERANCE_FINAL     = 1e-5
FORECAST_HORIZON    = 90

FIGURE_SIZE = (12, 6)
COLORS = {
    "train":    "blue",
    "actual":   "green",
    "forecast": "orange",
    "ci_fill":  "orange",
    "ci_alpha": 0.2,
    "residual": "red",
}

# ── Source Registry ──────────────────────────────────────────────────────────
#
# Each source maps to:
#   raw_subdir      — folder under data/raw/
#   raw_file        — expected CSV filename (exported from Excel)
#   date_column     — column name containing the date/week field
#   target_column   — the metric to forecast
#   qty_column      — multiply with price_column to compute target (or None)
#   price_column    — (or None)
#   frequency       — pandas offset alias: B, W, M, D
#   seasonal_period — s for SARIMA; matches frequency pattern in data
#   validation_size — how many periods to hold out
#   smoothing_span  — EWM span; shorter for weekly (less data)
#   description     — human-readable label used in plot titles and logs
#   sheet_notes     — which Excel sheet/tab this CSV should be exported from

SOURCE_REGISTRY = {

    # ── Sales (QuickBooks export) ────────────────────────────────────────────
    # Export: SignalStack_SalesTemplate.xlsx  →  PIPELINE_READY tab  →  Save as CSV
    "sales": {
        "raw_subdir":      "sales",
        "raw_file":        "sales_pipeline_ready.csv",
        "date_column":     "Date",
        "target_column":   "Total Sales",
        "qty_column":      "Qty",
        "price_column":    "Sales Price",
        "frequency":       "B",
        "seasonal_period": 5,          # weekly pattern in business-day data
        "validation_size": 60,
        "forecast_horizon": 90,
        "sarima_d_range":  range(1, 3),
        "smoothing_span":  14,
        "max_train_periods": 180,     # ~9 months of business days (regime-aware training)
        "description":     "Daily Sales Revenue",
        "sheet_notes":     "SignalStack_SalesTemplate.xlsx → PIPELINE_READY tab",
    },

    # ── Ops Pulse ────────────────────────────────────────────────────────────
    # Export: SignalStack_OpsPulse.xlsx  →  Dashboard tab (Trend table)  →  Save as CSV
    # Required columns in CSV: Week, Jobs Done, On-Time %, Callback %, Utilization %
    "ops_pulse": {
        "raw_subdir":      "ops_pulse",
        "raw_file":        "ops_pulse_weekly.csv",
        "date_column":     "Week",
        "target_column":   "Jobs Done",
        "qty_column":      None,
        "price_column":    None,
        "frequency":       "W",
        "seasonal_period": 4,          # monthly pattern in weekly data
        "validation_size": 16,
        "forecast_horizon": 12,
        "smoothing_span":  4,
        "description":     "Weekly Jobs Completed",
        "sheet_notes":     "SignalStack_OpsPulse.xlsx → Dashboard tab (copy trend table rows)",
        # Additional columns available for multi-signal runs
        "extra_signals": {
            "on_time_rate":   "On-Time %",
            "callback_rate":  "Callback %",
            "utilization":    "Utilization %",
            "open_work_orders": "Open WOs",
        },
    },

    # ── Cash Flow Compass ────────────────────────────────────────────────────
    # Export: SignalStack_CashFlowCompass.xlsx  →  Weekly Position tab  →  Save as CSV
    # Required columns: Week Of, Cash on Hand, Revenue In, Expenses Out, Ending Balance
    "cash_flow_compass": {
        "raw_subdir":      "cash_flow_compass",
        "raw_file":        "cash_flow_weekly.csv",
        "date_column":     "Week Of",
        "target_column":   "Ending Balance",
        "qty_column":      None,
        "price_column":    None,
        "frequency":       "W",
        "seasonal_period": 4,
        "validation_size": 16,
        "forecast_horizon": 12,
        "smoothing_span":  4,
        "description":     "Weekly Ending Cash Balance",
        "sheet_notes":     "SignalStack_CashFlowCompass.xlsx → Weekly Position tab (8-week tracker)",
        "extra_signals": {
            "revenue_in":    "Revenue In",
            "expenses_out":  "Expenses Out",
            "net_change":    "Net Change",
            "cash_on_hand":  "Cash on Hand",
        },
    },

    # ── Pipeline Pulse ───────────────────────────────────────────────────────
    # Export: SignalStack_PipelinePulse.xlsx  →  Dashboard tab (Funnel Metrics)  →  Save as CSV
    # Required columns: Week, Active Prospects, Win Rate MTD, Pipeline Value (est.)
    "pipeline_pulse": {
        "raw_subdir":      "pipeline_pulse",
        "raw_file":        "pipeline_pulse_weekly.csv",
        "date_column":     "Week",
        "target_column":   "Pipeline Value",
        "qty_column":      None,
        "price_column":    None,
        "frequency":       "W",
        "seasonal_period": 4,
        "validation_size": 16,
        "forecast_horizon": 12,
        "smoothing_span":  6,
        "sarima_p_range":  range(0, 2),
        "sarima_q_range":  range(0, 2),
        "sarima_seasonal_p": range(0, 2),
        "sarima_seasonal_q": range(0, 2),
        "ensemble_forecast": True,       # blend SARIMA + WMA for volatile deal-flow signal
        "ensemble_weights":  (0.6, 0.4), # (sarima_weight, wma_weight)
        "description":     "Weekly Estimated Pipeline Value",
        "sheet_notes":     "SignalStack_PipelinePulse.xlsx → Pipeline Log tab (aggregated by week)",
        "extra_signals": {
            "active_prospects": "Active Prospects",
            "close_rate":       "Close Rate",
            "avg_deal_size":    "Avg Deal Size",
        },
    },

    # ── Team Tempo ───────────────────────────────────────────────────────────
    # Export: SignalStack_TeamTempo.xlsx  →  Dashboard tab (Trend table)  →  Save as CSV
    # Required columns: Week, Headcount, Billable Hrs, OT Hrs, Utilization %
    "team_tempo": {
        "raw_subdir":      "team_tempo",
        "raw_file":        "team_tempo_weekly.csv",
        "date_column":     "Week",
        "target_column":   "Billable Hrs",
        "qty_column":      None,
        "price_column":    None,
        "frequency":       "W",
        "seasonal_period": 4,
        "validation_size": 16,
        "forecast_horizon": 12,
        "smoothing_span":  4,
        "description":     "Weekly Billable Hours",
        "sheet_notes":     "SignalStack_TeamTempo.xlsx → Dashboard tab (8-week trend)",
        "extra_signals": {
            "headcount":    "Headcount",
            "ot_hours":     "OT Hrs",
            "utilization":  "Utilization %",
            "turnover":     "Turnover",
        },
    },
}


def get_source(source_name):
    """
    Retrieve a source config dict by name.
    Merges source-level overrides with global defaults.

    Parameters:
        source_name (str): Key from SOURCE_REGISTRY.

    Returns:
        dict: Merged config with all fields needed by the pipeline.

    Raises:
        KeyError if source_name is not registered.
    """
    if source_name not in SOURCE_REGISTRY:
        available = list(SOURCE_REGISTRY.keys())
        raise KeyError(
            f"[config] Unknown source: '{source_name}'. "
            f"Available sources: {available}"
        )

    src = SOURCE_REGISTRY[source_name].copy()

    # Build absolute data paths from raw_subdir
    src["data_raw"]       = os.path.join(DATA_RAW, src["raw_subdir"])
    src["data_processed"] = os.path.join(DATA_PROCESSED, src["raw_subdir"])
    src["data_output"]    = os.path.join(DATA_OUTPUT, src["raw_subdir"])
    src["models_dir"]     = os.path.join(MODELS_DIR, src["raw_subdir"])
    src["visuals_dir"]    = os.path.join(VISUALS_DIR, src["raw_subdir"])

    # Full path to the raw CSV
    src["file_path"] = os.path.join(src["data_raw"], src["raw_file"])

    # Apply global defaults for any field not overridden at source level
    defaults = {
        "encoding":            ENCODING,
        "fill_method":         FILL_METHOD,
        "outlier_method":      OUTLIER_METHOD,
        "iqr_multiplier":      IQR_MULTIPLIER,
        "zscore_threshold":    ZSCORE_THRESHOLD,
        "outlier_replacement": OUTLIER_REPLACEMENT,
        "log_transform":       LOG_TRANSFORM,
        "sarima_p_range":      SARIMA_P_RANGE,
        "sarima_d_range":      SARIMA_D_RANGE,
        "sarima_q_range":      SARIMA_Q_RANGE,
        "sarima_seasonal_p":   SARIMA_SEASONAL_P,
        "sarima_seasonal_d":   SARIMA_SEASONAL_D,
        "sarima_seasonal_q":   SARIMA_SEASONAL_Q,
        "max_iter_search":     MAX_ITER_SEARCH,
        "max_iter_final":      MAX_ITER_FINAL,
        "tolerance_search":    TOLERANCE_SEARCH,
        "tolerance_final":     TOLERANCE_FINAL,
        "forecast_horizon":    FORECAST_HORIZON,
        "max_train_periods":   None,
        "ensemble_forecast":   False,
        "ensemble_weights":    (1.0, 0.0),
        "figure_size":         FIGURE_SIZE,
        "colors":              COLORS,
        "extra_signals":       {},
    }
    for key, default_val in defaults.items():
        if key not in src:
            src[key] = default_val

    return src
