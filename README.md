# SignalStack — Business Intelligence Forecasting Engine
**True North Data Strategies | tnds-signal-engine**

SARIMA time series forecasting pipeline for five SignalStack business metrics.
One codebase. Five signals. Each source runs independently with its own data,
outputs, models, visuals, and client-facing report narration.

---

## Sources

| Source | Workbook | Target Column | Frequency |
|---|---|---|---|
| `sales` | tnds-sales-data-template.xlsx | Total Sales | Business Day |
| `ops_pulse` | SignalStack_OpsPulse.xlsx | Jobs Done | Weekly |
| `cash_flow_compass` | SignalStack_CashFlowCompass.xlsx | Ending Balance | Weekly |
| `pipeline_pulse` | SignalStack_PipelinePulse.xlsx | Pipeline Value | Weekly |
| `team_tempo` | SignalStack_TeamTempo.xlsx | Billable Hrs | Weekly |

Current forecast/validation defaults:
- `sales`: forecast horizon `90` business days, validation size `60`
- Weekly sources: forecast horizon `12` weeks, validation size `16`

---

## Current Data Baseline (Updated March 30, 2026)

The workbooks were expanded for ML testing with an additional full year of synthetic historical rows.

| Source | Workbook Tab | Rows Exported | Current End Date |
|---|---|---:|---|
| `sales` | `RAW_INPUT` | 441 | 2026-07-21 |
| `ops_pulse` | `Weekly Log` (aggregated to weekly) | 85 | 2026-W27 |
| `cash_flow_compass` | `Weekly Position` tracker | 85 | 2026-05-18 |
| `pipeline_pulse` | `Pipeline Log` (aggregated weekly) | 89 (weekly agg) | 2026-W23 |
| `team_tempo` | `Hours Log` (aggregated to weekly) | 85 | 2026-W27 |

Rebuild raw CSVs any time workbook data changes (auto-runs root workbook integrity fixes first):

```bash
python export_to_csv.py
```

If you need to bypass the integrity pass:
```bash
python export_to_csv.py --skip-root-fix
```

Run the integrity pass by itself (no CSV export):
```bash
python fix_root_workbooks.py
```

---

## Quick Start

```bash
# 1. Set up environment
bash setup.sh

# 2. Activate
source venv_tnds-signal-engine/bin/activate

# 3. Export Excel workbooks to CSV (place .xlsx files in project root first)
python export_to_csv.py        # auto-runs root workbook integrity fixes first

# 4. Run pipeline for one source
python run_pipeline.py --source sales
python run_pipeline.py --source ops_pulse

# 5. Run all five sources
python run_pipeline.py --source all

# 6. Skip grid search after first run (use saved params)
python run_pipeline.py --source sales --skip-search

# 7. Generate report + delivery package
python generate_report.py
python package_output.py
```

---

## Folder Structure

```
tnds-signal-engine/
  config.py               # Source registry + all parameters
  run_pipeline.py         # Single entry point — pass --source
  export_to_csv.py        # Batch Excel → CSV export utility
  fix_root_workbooks.py   # Root workbook type normalizer (date/number text fixes)
  generate_report.py      # Word report builder (Signal Profile + glossary)
  package_output.py       # Delivery ZIP builder with standalone HTML report
  fix_ar_aging.py         # CashFlowCompass AR/AP formula repair utility
  requirements.txt
  setup.sh
  src/
    data_loader.py        # Source-aware CSV loading
    preprocessor.py       # Outlier detection + EWM smoothing
    accuracy_log.py       # Persistent run-by-run accuracy tracking CSV
    model.py              # Convergence-aware SARIMA grid search + training
    evaluator.py          # Forecast + metrics (MAE/RMSE/MAPE + CV + bias detection)
    visualizer.py         # 6 standard plots per source
  data/
    raw/
      sales/              # Drop: sales_pipeline_ready.csv
      ops_pulse/          # Drop: ops_pulse_weekly.csv
      cash_flow_compass/  # Drop: cash_flow_weekly.csv
      pipeline_pulse/     # Drop: pipeline_pulse_weekly.csv
      team_tempo/         # Drop: team_tempo_weekly.csv
    processed/            # Auto-generated: cleaned + smoothed CSVs
    output/               # Auto-generated: forecast results + metrics
  models/                 # Auto-generated: sarima_model.pkl per source
  visuals/                # Auto-generated: 6 PNGs per source
```

---

## Export Instructions (per source)

### Sales
1. Open `tnds-sales-data-template.xlsx`
2. Go to **RAW_INPUT** tab
3. Add transaction rows with `Date`, `Qty`, and `Sales Price` (or `Total Sales`)
4. Keep the **Analysis** tab intact; it feeds the report's sales Signal Profile narration.
5. Run `python export_to_csv.py --source sales` (script writes `data/raw/sales/sales_pipeline_ready.csv`)

### Ops Pulse
1. Open `SignalStack_OpsPulse.xlsx`
2. Go to **Weekly Log** tab
3. Add per-job rows (`Date`, `Jobs Completed`, `Scheduled Time`, `Actual Time`, `On Time?`, `Callback?`)
4. Run `python export_to_csv.py --source ops_pulse` (script aggregates to weekly CSV)

### Cash Flow Compass
1. Open `SignalStack_CashFlowCompass.xlsx`
2. Go to **Weekly Position** tab
3. Copy/paste the latest weekly tracker rows into the tab
4. Run `python export_to_csv.py --source cash_flow_compass` (script exports weekly CSV)

### Pipeline Pulse
1. Open `SignalStack_PipelinePulse.xlsx`
2. Go to **Pipeline Log** tab
3. Ensure `Date Entered` and `Est. Value` are populated for active rows
4. Run `python export_to_csv.py --source pipeline_pulse` (script aggregates weekly CSV)

### Team Tempo
1. Open `SignalStack_TeamTempo.xlsx`
2. Go to **Hours Log** tab and add per-employee weekly rows
3. Keep **Roster** tab up to date for active employees/status
4. Run `python export_to_csv.py --source team_tempo` (script aggregates to weekly CSV)

**Shortcut:** Place all .xlsx files in the project root and run:
```bash
python export_to_csv.py
```

---

## Adding a New Source

1. Add a new entry to `SOURCE_REGISTRY` in `config.py`
2. Add matching entry to `EXPORT_MAP` in `export_to_csv.py`
3. Drop the CSV in `data/raw/<new_source>/`
4. Run: `python run_pipeline.py --source <new_source>`

No other files need to change.

---

## Output Files (per source run)

```
data/output/<source>/
  forecast_results.csv        # Actual vs Forecast vs CI vs Residuals
  metrics.txt                 # MAE, RMSE, MAPE, CV metrics, Bias_Detected, Bias_Pattern
  best_sarima_parameters.txt  # Best order + AIC + adjusted AIC + convergence

data/output/
  accuracy_log.csv            # One row per source per run (persistent history)

models/<source>/
  sarima_model.pkl            # Trained model (reload with --skip-search)

visuals/<source>/
  01_raw_time_series.png
  02_decomposition.png
  03_preprocessing.png
  04_forecast_vs_actual.png
  05_residuals.png
  06_extended_forecast.png

reports/
  SignalStack_Report_<YYYY-Www>.docx   # Word report with glossary + Signal Profile

Desktop/
  SignalStack_Delivery_<YYYY-Www>.zip  # Delivery ZIP containing DOCX, HTML, charts, Excel
```

---

## After First Grid Search

Update `MANUAL_PARAMS` in `run_pipeline.py` with the best parameters
from `data/output/<source>/best_sarima_parameters.txt`, then use
`--skip-search` for all future runs to skip the slow grid search.

Grid search now filters non-converged fits, uses an adjusted-AIC selection
score to discourage over-parameterization on short series, and applies a
MAPE guardrail fallback when a best-AIC model performs poorly on validation.

---

Jacob Johnston | 719-204-6365 | jacob@truenorthstrategyops.com
True North Data Strategies | Colorado Springs, CO | SDVOSB
