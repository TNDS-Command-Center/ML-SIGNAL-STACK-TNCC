# SignalStack — Business Intelligence Forecasting Engine
**True North Data Strategies | tnds-signal-engine**

SARIMA time series forecasting pipeline for five SignalStack business metrics.
One codebase. Five signals. Each source runs independently with its own data,
outputs, models, and visuals.

---

## Sources

| Source | Workbook | Target Column | Frequency |
|---|---|---|---|
| `sales` | SignalStack_SalesTemplate.xlsx | Total Sales | Business Day |
| `ops_pulse` | SignalStack_OpsPulse.xlsx | Jobs Done | Weekly |
| `cash_flow_compass` | SignalStack_CashFlowCompass.xlsx | Ending Balance | Weekly |
| `pipeline_pulse` | SignalStack_PipelinePulse.xlsx | Pipeline Value | Weekly |
| `team_tempo` | SignalStack_TeamTempo.xlsx | Billable Hrs | Weekly |

---

## Quick Start

```bash
# 1. Set up environment
bash setup.sh

# 2. Activate
source venv_tnds-signal-engine/bin/activate

# 3. Export Excel workbooks to CSV (place .xlsx files in project root first)
python export_to_csv.py

# 4. Run pipeline for one source
python run_pipeline.py --source sales
python run_pipeline.py --source ops_pulse

# 5. Run all five sources
python run_pipeline.py --source all

# 6. Skip grid search after first run (use saved params)
python run_pipeline.py --source sales --skip-search
```

---

## Folder Structure

```
tnds-signal-engine/
  config.py               # Source registry + all parameters
  run_pipeline.py         # Single entry point — pass --source
  export_to_csv.py        # Batch Excel → CSV export utility
  requirements.txt
  setup.sh
  src/
    data_loader.py        # Source-aware CSV loading
    preprocessor.py       # Outlier detection + EWM smoothing
    model.py              # SARIMA grid search + training
    evaluator.py          # Forecast + metrics (MAE/RMSE/MAPE)
    visualizer.py         # 5 standard plots per source
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
  visuals/                # Auto-generated: 5 PNGs per source
```

---

## Export Instructions (per source)

### Sales
1. Open `SignalStack_SalesTemplate.xlsx`
2. Go to **PIPELINE_READY** tab
3. File → Save As → CSV
4. Save as `data/raw/sales/sales_pipeline_ready.csv`

### Ops Pulse
1. Open `SignalStack_OpsPulse.xlsx`
2. Go to **Dashboard** tab
3. Copy the **8-week trend table** rows (Week, Jobs Done, On-Time %, etc.)
4. Paste into a new sheet, save as `data/raw/ops_pulse/ops_pulse_weekly.csv`
   — OR — run `python export_to_csv.py --source ops_pulse`

### Cash Flow Compass
1. Open `SignalStack_CashFlowCompass.xlsx`
2. Go to **Weekly Position** tab
3. Copy the 8-week tracker rows
4. Save as `data/raw/cash_flow_compass/cash_flow_weekly.csv`

### Pipeline Pulse
1. Open `SignalStack_PipelinePulse.xlsx`
2. Go to **Dashboard** tab
3. Copy the funnel metrics trend rows (requires adding a weekly tracking table)
4. Save as `data/raw/pipeline_pulse/pipeline_pulse_weekly.csv`

### Team Tempo
1. Open `SignalStack_TeamTempo.xlsx`
2. Go to **Dashboard** tab
3. Copy the 8-week trend table rows
4. Save as `data/raw/team_tempo/team_tempo_weekly.csv`

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
  metrics.txt                 # MAE, RMSE, MAPE, model params
  best_sarima_parameters.txt  # Best order from grid search

models/<source>/
  sarima_model.pkl            # Trained model (reload with --skip-search)

visuals/<source>/
  01_raw_time_series.png
  02_decomposition.png
  03_preprocessing.png
  04_forecast_vs_actual.png
  05_residuals.png
```

---

## After First Grid Search

Update `MANUAL_PARAMS` in `run_pipeline.py` with the best parameters
from `data/output/<source>/best_sarima_parameters.txt`, then use
`--skip-search` for all future runs to skip the slow grid search.

---

Jacob Johnston | 719-204-6365 | jacob@truenorthstrategyops.com
True North Data Strategies | Colorado Springs, CO | SDVOSB
