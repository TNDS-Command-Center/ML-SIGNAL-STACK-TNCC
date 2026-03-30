# SignalStack User Manual
## True North Data Strategies
### For Business Owners — No Data Science Background Required

**Version 1.2 (Updated March 29, 2026) | Jacob Johnston | jacob@truenorthstrategyops.com | 719-204-6365**
**Colorado Springs, CO | SDVOSB**

---

## Table of Contents

1. What Is SignalStack?
2. What You Get Each Week
3. Folder Structure
4. Your Five Business Signals
5. The Weekly Workflow — Three Commands
6. Updating Your Excel Workbooks
7. Reading Your Reports
8. Reading the Charts
9. Fine-Tuning the System (config.py)
10. Fine-Tuning Model Parameters (run_pipeline.py)
11. Adding a New Data Source
12. Troubleshooting
13. Glossary of Terms

---

## 1. What Is SignalStack?

SignalStack is a business intelligence forecasting system. It reads five sets of your business data every week, runs a statistical forecasting model on each one, and produces a Word document report showing where each metric is headed.

**Plain English:** You update five Excel files with your weekly numbers. SignalStack reads them, finds the pattern, and tells you what the next several weeks will likely look like — along with how confident it is in that projection.

**What it does NOT do:**
- Connect to the internet or QuickBooks automatically
- Make decisions for you
- Replace your judgment — it informs it

**What makes it different from a spreadsheet dashboard:**
A dashboard shows where you've been. SignalStack shows where you're going, with a confidence band so you know how much to trust the projection.


---

## 2. What You Get Each Week

After running the three commands, you get:

**A Word document report** in the `reports/` folder, automatically named by ISO week (e.g., `SignalStack_Report_YYYY-Www.docx`). It contains:
- An Executive Summary table — all five signals at a glance, color-coded by accuracy
- A detail section per signal — metrics scorecard + embedded forecast chart
- A Glossary — every term in plain English

**Six diagnostic charts per signal** as PNG image files in `visuals/` (`01` through `06`), including the extended forecast chart.

**Five metrics files** in `data/output/` — MAE, RMSE, MAPE, CV_Mean_MAPE, CV_Std_MAPE, model selected.

**One persistent accuracy log** in `data/output/accuracy_log.csv` — appends one row per source per run so you can track improvement over time.

**Five trained model files** in `models/` — reused each week so the run takes seconds.

### Current Testing Baseline (March 29, 2026)

The workbook history was expanded by an additional full year of rows for ML testing.

| Source | Workbook Tab | Exported Rows | Current End Date |
|---|---|---:|---|
| Sales | `RAW_INPUT` | 441 | 2026-07-21 |
| Ops Pulse | `Weekly Log` (aggregated to weekly) | 85 | 2026-W27 |
| Cash Flow Compass | `Weekly Position` tracker | 85 | 2026-05-18 |
| Pipeline Pulse | `Pipeline Log` (weekly aggregate output) | 89 | 2026-W23 |
| Team Tempo | `Hours Log` (aggregated to weekly) | 85 | 2026-W27 |

This gives you enough history for model testing and backtesting. Continue adding new rows weekly; do not replace old rows.

---

## 3. Folder Structure — Where Everything Lives

```
ML-SIGNAL-STACK-TNCC/
  config.py                        Master settings. Change parameters here.
  run_pipeline.py                  Run the forecasting engine.
  export_to_csv.py                 Export Excel data to CSVs the engine reads.
  generate_report.py               Generate the Word document report.
  requirements.txt                 Python packages required.

  SignalStack_OpsPulse.xlsx        Update weekly (Ops data)
  SignalStack_CashFlowCompass.xlsx Update weekly (Cash data)
  SignalStack_PipelinePulse.xlsx   Update weekly (Sales pipeline)
  SignalStack_TeamTempo.xlsx       Update weekly (Team hours)
  tnds-sales-data-template.xlsx   Update weekly (Transaction data)

  data/
    raw/          Auto-populated by export_to_csv.py. Do not edit manually.
    processed/    Auto-generated intermediate files. Ignore.
    output/       Auto-generated metrics, forecast CSVs, and accuracy_log.csv.
  models/         Saved trained models. Do not delete.
  visuals/        Saved forecast charts (PNG).
  reports/        Word document reports land here.
  docs/           This manual and other documentation.
```

---

## 4. Your Five Business Signals

### Signal 1: Sales (Daily Sales Revenue)
**File:** `tnds-sales-data-template.xlsx` → tab: `RAW_INPUT`
**Forecasts:** Daily revenue (Qty × Price per transaction)
**Minimum history:** 67 business days (~3.5 months)

One row per transaction. Three columns:
| Column | Format | Example |
|---|---|---|
| Date | MM/DD/YYYY | 03/28/2026 |
| Qty | Number | 500 |
| Sales Price | Dollar per unit | 3.85 |

**Best data source:** QuickBooks → Sales by Customer Detail → export as Excel → copy Date, Qty, Rate columns into the RAW_INPUT tab.

If you only have a total (no qty/price split), put `1` in Qty and the full dollar amount in Sales Price.


### Signal 2: Ops Pulse (Weekly Jobs Completed)
**File:** `SignalStack_OpsPulse.xlsx` → tab: `Weekly Log` (detail input)
**Forecasts:** Jobs completed per week
**Minimum history:** 22 weeks

Add one row per job in Weekly Log. `export_to_csv.py` aggregates jobs to ISO week rows.
| Column | Format | Example |
|---|---|---|
| Date | MM/DD/YYYY | 03/24/2026 |
| Jobs Completed | Whole number | 1 |
| Scheduled Time (h) | Hours | 2.5 |
| Actual Time (h) | Hours | 2.3 |
| On Time? (Y/N) | Text | Y |
| Callback? (Y/N) | Text | N |
| Open WOs (optional) | Whole number | 8 |

**ISO week format:** The week number of the year, always starting Monday. Week 1 of 2026 = `2026-W01`. You can look up current ISO week at any time by typing `python -c "import datetime; print(datetime.date.today().strftime('%G-W%V'))"` in your terminal.

---

### Signal 3: Cash Flow Compass (Weekly Ending Cash Balance)
**File:** `SignalStack_CashFlowCompass.xlsx` → tab: `Weekly Position`
**Forecasts:** Ending cash balance per week
**Minimum history:** 22 weeks

Add one row per week. Net Change and Ending Balance are auto-calculated.
| Column | Format | Example |
|---|---|---|
| Week Of | MM/DD/YYYY (Monday) | 03/23/2026 |
| Cash on Hand | Dollar | 48500 |
| AR Collected | Dollar | 22400 |
| AP Paid | Dollar | 14200 |
| Revenue In | Dollar | 24000 |
| Expenses Out | Dollar | 17500 |

---

### Signal 4: Pipeline Pulse (Weekly Pipeline Value)
**File:** `SignalStack_PipelinePulse.xlsx` → tab: `Pipeline Log`
**Forecasts:** Total estimated pipeline value, grouped by week entered
**Minimum history:** 22 weeks of deal activity

Add one row per prospect. The system groups deals by the week they were entered.
| Column | Format | Example |
|---|---|---|
| Prospect | Text | Acme Petroleum |
| Industry | Text | Energy |
| Est. Value | Dollar | 35000 |
| Current Stage | Text | Map |
| Date Entered | MM/DD/YYYY | 01/15/2026 |
| Owner | Text | Jacob |
| Win Prob % | Decimal | 0.65 |

Stages follow the Direction Protocol: Identify → Assess → Map → Chart → Launch → Closed Lost

---

### Signal 5: Team Tempo (Weekly Billable Hours)
**File:** `SignalStack_TeamTempo.xlsx` → tabs: `Hours Log` + `Roster`
**Forecasts:** Billable hours per week
**Minimum history:** 22 weeks

Add one row per employee per week in Hours Log. Keep Roster current for employee status.
| Column | Format | Example |
|---|---|---|
| Week Of | MM/DD/YYYY | 03/23/2026 |
| Employee | Text | Mike Rodriguez |
| Regular Hrs | Hours | 36 |
| OT Hrs | Hours | 22 |
| Training Hrs | Hours | 2 |
| PTO Hrs | Hours | 0 |


---

## 5. The Weekly Workflow — Three Commands

Every week after updating your Excel files, open PowerShell, navigate to your project folder, activate the virtual environment, and run three commands in order.

### Step 1: Activate the environment (if not already active)
```powershell
cd "C:\Users\truenorth\Desktop\00 PIPLINE PUNKS GIT\00-FLEET-COMPLIANCE-SENTINEL\tooling\ML-SIGNAL-STACK-TNCC"
.\venv_tnds-signal-engine\Scripts\Activate.ps1
```
You'll know it's active when you see `(venv_tnds-signal-engine)` at the start of the prompt.

### Step 2: Export Excel data to CSV
```powershell
python export_to_csv.py
```
This reads all five Excel workbooks and writes clean data files the pipeline can read.
Expected output: `OK` for each source in the summary at the bottom.

### Step 3: Run the forecasting pipeline
```powershell
python run_pipeline.py --source all --skip-search
```
The `--skip-search` flag reuses previously found model parameters so this runs in seconds instead of minutes. Remove it only when you want to re-run a full parameter search (after adding significant new data).

### Step 4: Generate the Word report
```powershell
python generate_report.py
```
Report saves to `reports/SignalStack_Report_YYYY-Www.docx` automatically named for the current week.

---

### Running a single source only

If you only updated one workbook:
```powershell
python export_to_csv.py --source ops_pulse
python run_pipeline.py --source ops_pulse --skip-search
python generate_report.py --source ops_pulse
```

Available source names: `sales`, `ops_pulse`, `cash_flow_compass`, `pipeline_pulse`, `team_tempo`

---

### Saving the report with a custom name
```powershell
python generate_report.py --out "reports\ChiefPetroleum_Weekly_YYYY-Www.docx"
```

---

## 6. Updating Your Excel Workbooks

**The golden rule:** Always add rows, never delete old ones. The model needs history — removing rows reduces accuracy.

**For Ops Pulse:**
- Open `SignalStack_OpsPulse.xlsx`
- Go to `Weekly Log`
- Add one row per completed job (Date + job inputs)
- Save and run `python export_to_csv.py --source ops_pulse`

**For Team Tempo:**
- Open `SignalStack_TeamTempo.xlsx`
- Go to `Hours Log` and add one row per employee per week
- Keep `Roster` up to date for active employees/status
- Save and run `python export_to_csv.py --source team_tempo`

**For Cash Flow Compass:**
- Open `SignalStack_CashFlowCompass.xlsx`
- Go to `Weekly Position`
- Add one row for the week
- Save and run `python export_to_csv.py --source cash_flow_compass`

**For the Pipeline Log (Pipeline Pulse):**
- Open `SignalStack_PipelinePulse.xlsx`
- Go to the Pipeline Log tab
- Add new prospects as new rows at the bottom
- Update the `Current Stage` on existing prospects as they move forward
- Save before running export

**For Sales:**
- Ideally export directly from QuickBooks each week and paste new rows into the RAW_INPUT tab
- Sort by date ascending (oldest to newest)
- Do not delete or reformat existing rows

**Important baseline note:**
- The current workbooks already include one full added year of synthetic testing history through mid-2026.
- Keep those rows for testing continuity. Append new real rows after the existing last row.


---

## 7. Reading Your Reports

Open any file in `reports/` with Microsoft Word. The report has three sections:

### Executive Summary Table
Five rows, one per signal. Columns:
- **Signal** — the business metric being forecast
- **Model** — the SARIMA parameter combination selected (technical; ignore the numbers)
- **MAPE** — your primary accuracy score. Color coded:
  - Green (under 10%) — high confidence. Use for planning.
  - Amber (10–20%) — directionally accurate. Verify weekly.
  - Red (over 20%) — developing. Use for trend direction only.
- **MAE** — average error in the signal's native unit (dollars or hours)
- **Accuracy Assessment** — plain-English interpretation

### Signal Detail Sections
One section per signal. Each contains:
- A **metrics stats bar** showing model, MAPE, MAE, and RMSE
- An **accuracy statement** in plain English (italic, color-coded)
- The **forecast vs actual chart** (see Section 8 for how to read it)

### Glossary
Definitions for every technical term in the report.

---

## 8. Reading the Charts

Each forecast chart has three elements:

**Blue line — Training Data**
This is the historical data the model learned from. Everything to the left of where the green line starts.

**Green line — Actual (Validation)**
This is real data the model had never seen. The gap between the green line and the orange line is the forecast error — how wrong the model was during testing.

**Orange line — Forecast**
The model's projection. For weekly sources this is typically flat or gently trending because we have limited history. As you add more weekly data, this line will develop more shape.

**Orange shaded band — 95% Confidence Interval**
There's a 95% probability the actual value will land inside this band. Wider band = more uncertainty. Narrower band = tighter prediction.

**What good looks like:** The green (actual) line stays close to the orange (forecast) line and mostly inside the shaded band. Cash Flow Compass at about 0.6% MAPE is what an excellent model looks like — the lines are nearly on top of each other.

**What moderate looks like:** Pipeline Pulse at about 18% MAPE — directional signal is useful, but individual week values can still vary materially. Use this signal for trend direction and planning ranges, not exact dollar commitments.

---

## 9. Fine-Tuning the System (config.py)

`config.py` is the master control file. You should not need to edit it often, but here are the settings you might adjust as your business evolves.

### Changing the minimum history requirement

The validation size controls how many periods are held out for testing. If you consistently have trouble meeting the minimum data requirement, reduce this:

**For weekly sources (ops_pulse, cash_flow_compass, pipeline_pulse, team_tempo):**
Find this block in `config.py`:
```python
"ops_pulse": {
    ...
    "validation_size": 16,   # ← Weekly default (about 4 months holdout)
    ...
}
```

**For sales:**
```python
"sales": {
    ...
    "validation_size": 60,   # ← Daily default (about 3 months holdout)
    ...
}
```
**Rule of thumb:** Validation size should be about 20-25% of your total history. If you have 20 weeks of data, use validation_size = 4 or 5.

### Changing the smoothing level

Smoothing reduces noise before the model trains. Lower = less smoothing (more sensitive to recent changes). Higher = more smoothing (more stable, slower to react).

```python
"ops_pulse": {
    ...
    "smoothing_span": 4,     # ← 2 = very reactive, 8 = very smooth
    ...
}
```
For weekly data: 2-6 is the useful range (Pipeline Pulse currently uses 6; other weekly sources use 4).
For daily sales data: 7–21 is the useful range.

### Changing the seasonal period

This tells the model how long one "season" is in your data.
```python
"ops_pulse": {
    ...
    "seasonal_period": 4,    # ← 4 = monthly pattern in weekly data
    ...
}
```
- Weekly data with monthly pattern: `4`
- Weekly data with quarterly pattern: `13`
- Daily data with weekly pattern: `5` (business days)
- Daily data with monthly pattern: `21`


### Changing outlier handling

When the model detects unusual values (a slow holiday week, a one-time large deal), it handles them using this setting:

```python
OUTLIER_REPLACEMENT = "median"   # Options: "median", "cap", "remove"
```
- `"median"` — replaces outliers with the median value. Best for most cases.
- `"cap"` — clips extreme values to the IQR boundary instead of replacing.
- `"remove"` — removes outlier rows entirely. Risk: breaks time series continuity.

**Recommended:** Keep `"median"` unless you have a specific reason to change it.

### Changing the outlier detection threshold

```python
IQR_MULTIPLIER = 1.5    # Lower = catches more outliers. Higher = catches fewer.
```
- `1.5` — standard setting, catches clear outliers
- `2.0` — more lenient, only catches extreme outliers
- `1.0` — aggressive, may flag normal variation as outliers

---

## 10. Fine-Tuning Model Parameters (run_pipeline.py)

After your first full pipeline run (without `--skip-search`), the best SARIMA parameters are saved to `data/output/<source>/best_sarima_parameters.txt`. Update `MANUAL_PARAMS` in `run_pipeline.py` with these values to make future runs faster.

### Reading best_sarima_parameters.txt

Open any file in `data/output/<source>/best_sarima_parameters.txt`. It looks like:
```
Source:           ops_pulse
Target:           Jobs Done
Best order:       (0, 1, 1)
Best seasonal:    (0, 0, 0, 4)
AIC:              -291.1149
Adjusted AIC:     -291.1149
Convergence:      True
Total params:     2
```

### Updating MANUAL_PARAMS

Open `run_pipeline.py` and find this block near the top:
```python
MANUAL_PARAMS = {
    "sales": {
        "order":    (1, 1, 1),      # ← Replace with Best order from txt file
        "seasonal": (2, 0, 2, 5),   # ← Replace with Best seasonal from txt file
    },
    "ops_pulse": {
        "order":    (0, 1, 1),
        "seasonal": (0, 0, 0, 4),
    },
    "cash_flow_compass": {
        "order":    (2, 1, 0),
        "seasonal": (2, 0, 0, 4),
    },
    "pipeline_pulse": {
        "order":    (0, 1, 1),
        "seasonal": (0, 0, 0, 4),
    },
    "team_tempo": {
        "order":    (2, 1, 2),
        "seasonal": (0, 0, 0, 4),
    },
}
```

For example, after seeing `Best order: (0, 1, 1)` and `Best seasonal: (0, 0, 0, 4)` for ops_pulse, update it to:
```python
"ops_pulse": {
    "order":    (0, 1, 1),    # updated from best_sarima_parameters.txt
    "seasonal": (0, 0, 0, 4), # updated from best_sarima_parameters.txt
},
```

**When to re-run grid search (remove --skip-search):**
- After adding 4+ weeks of new data to any source
- After a major business change (new service line, new pricing, new market)
- If MAPE gets significantly worse over several weeks
- Quarterly is a good rhythm for re-searching

**Grid search takes:** Usually 5-15 minutes per source depending on search ranges. Current defaults are wider than 64 combinations for most sources, while `pipeline_pulse` is capped smaller to reduce overfitting risk.


---

## 11. Adding a New Data Source

To add a sixth signal (for example, tracking customer satisfaction scores weekly):

### Step 1 — Add to SOURCE_REGISTRY in config.py

Open `config.py` and add a new entry at the bottom of `SOURCE_REGISTRY`:

```python
"customer_sat": {
    "raw_subdir":      "customer_sat",
    "raw_file":        "customer_sat_weekly.csv",
    "date_column":     "Week",
    "target_column":   "Avg Score",
    "qty_column":      None,
    "price_column":    None,
    "frequency":       "W",
    "seasonal_period": 4,
    "validation_size": 16,
    "smoothing_span":  4,
    "description":     "Weekly Customer Satisfaction Score",
    "sheet_notes":     "CustomerSat.xlsx → Scores tab",
},
```

### Step 2 — Add to EXPORT_MAP in export_to_csv.py

Open `export_to_csv.py` and add to the `EXPORT_MAP` dictionary:

```python
"customer_sat": {
    "workbook":  os.path.join(BASE_DIR, "CustomerSat.xlsx"),
    "sheet":     "Scores",
    "skip_rows": 1,         # adjust based on how many header rows your Excel has
    "mode":      "standard",
    "keep_cols": ["Week", "Avg Score", "Responses"],
},
```

### Step 3 — Add to SOURCE_META in generate_report.py

Open `generate_report.py` and add to the `SOURCE_META` dictionary:

```python
"customer_sat": {
    "label": "Weekly Customer Satisfaction",
    "unit":  "score",
    "target": "Avg Score"
},
```

Also add `"customer_sat"` to the `SOURCES` list at the top of `generate_report.py`.

### Step 4 — Create the data folder

```powershell
mkdir "data\raw\customer_sat"
```

### Step 5 — Drop the Excel file in the project root and run

```powershell
python export_to_csv.py --source customer_sat
python run_pipeline.py --source customer_sat
python generate_report.py
```

---

## 12. Troubleshooting

### "Not enough data to model"

```
[data_loader] Not enough data to model 'ops_pulse'.
Have: 7 periods | Need: 14
```

**Fix:** Add more rows to the Excel workbook and re-run `export_to_csv.py`. You need at least `validation_size + seasonal_period + 2` rows. For weekly sources with current defaults, that's 22 weeks minimum.

Alternatively, reduce `validation_size` in `config.py` temporarily while building history:
```python
"ops_pulse": {
    "validation_size": 4,   # temporarily reduced
    ...
}
```

---

### "Module not found" error

```
ModuleNotFoundError: No module named 'docx'
```

**Fix:** Install the missing package inside your virtual environment:
```powershell
pip install python-docx
```

For other missing modules:
```powershell
pip install -r requirements.txt
```

---

### Export shows WARNING: columns not found

```
[export] WARNING: columns not found: ['Ending Balance']
```

**Fix:** The column name in your Excel file doesn't exactly match what the script expects. Check for extra spaces, different capitalization, or a slightly different name. Open the CSV in `data/raw/<source>/` to see what column names actually exported, then either fix the Excel column header or update `keep_cols` in `export_to_csv.py`.

---

### "SKIPPED — workbook not found"

```
[export] SKIPPED — workbook not found.
Expected: C:\...\SignalStack_OpsPulse.xlsx
```

**Fix:** The Excel file is not in the project root folder. Move or copy it to the same folder as `export_to_csv.py`.

---

### Pipeline runs but MAPE gets worse each week

This usually means one of three things:
1. **Business changed** — run a full grid search (remove `--skip-search`) to find new best parameters
2. **Not enough history for the seasonal period** — reduce `seasonal_period` in config.py
3. **Outliers skewing the model** — try `OUTLIER_METHOD = "zscore"` instead of `"iqr"` in config.py

---

### Report shows "[Chart not found]" instead of image

**Fix:** Run the pipeline before generating the report. Charts are only created by `run_pipeline.py`. The report generator embeds `visuals/<source>/04_forecast_vs_actual.png`; the additional client-facing projection chart is `visuals/<source>/06_extended_forecast.png`.

---

### How to get the current ISO week number

```powershell
python -c "import datetime; print(datetime.date.today().strftime('%G-W%V'))"
```


---

## 13. Glossary of Terms

**AIC (Akaike Information Criterion)**
A model quality score. Lower is better. SignalStack compares models with an adjusted-AIC selection step to discourage overfitting on short series, while still recording the raw AIC in outputs.

**Business Day (B)**
A frequency setting meaning the model runs on weekdays only (Monday–Friday). Used for the Sales signal since transactions happen on business days.

**Callback Rate**
The percentage of completed jobs that required a return visit due to incomplete or incorrect work. A key quality indicator in Ops Pulse.

**Confidence Interval (95% CI)**
The shaded orange band on forecast charts. There is a 95% probability the actual future value will land inside this band. A wider band means more uncertainty. As you add more history, the band typically narrows.

**CSV (Comma-Separated Values)**
A simple text file where each row is a record and columns are separated by commas. SignalStack uses CSVs as the bridge between your Excel workbooks and the forecasting engine. You never need to open or edit these — `export_to_csv.py` creates them automatically.

**accuracy_log.csv**
A persistent run history file in `data/output/` with one row per source per run (timestamp, model, AIC, MAPE, CV metrics, train size, validation size, forecast horizon). Use it to track model improvement over time.

**EWM Smoothing (Exponential Weighted Moving Average)**
Applied before modeling to reduce week-to-week noise while preserving the overall trend. Think of it like a moving average that gives more weight to recent data. Controlled by `smoothing_span` in config.py.

**Forecast**
The model's projection of future values based on historical patterns. Shown as the orange line on charts.

**Forecast Horizon**
How many periods beyond the validation window the model projects. Current defaults are source-specific: `sales=90` business days, and all weekly sources (`ops_pulse`, `cash_flow_compass`, `pipeline_pulse`, `team_tempo`) use `12` weeks.

**Grid Search**
The process of testing SARIMA parameter combinations and selecting the best model. SignalStack rejects non-converged fits, applies an over-parameterization penalty during selection, and includes a validation MAPE guardrail fallback for unstable results. Runtime varies by source and configured search ranges.

**Cross-Validation (CV)**
Rolling-origin backtesting across multiple folds to estimate stability, not just one split. Saved as `CV_Mean_MAPE` and `CV_Std_MAPE` in each source `metrics.txt`.

**Convergence**
A status from statsmodels indicating whether optimizer fitting completed successfully. Non-converged candidates are rejected during grid search.

**IQR (Interquartile Range)**
A statistical measure used to detect outliers. Values that fall far outside the middle 50% of your data are flagged as outliers and handled per your `OUTLIER_REPLACEMENT` setting.

**ISO Week**
A standardized week numbering system where weeks start on Monday. Format: `YYYY-Www`. Example: `2026-W13` = the 13th week of 2026, starting March 23, 2026. Used as the date format for all weekly SignalStack sources.

**MAE (Mean Absolute Error)**
The average difference between what the model predicted and what actually happened, in the signal's native unit. If MAE = $307 for Sales, the model is off by an average of $307 per day. If MAE = 2.6 for Ops Pulse, the model is off by 2.6 jobs per week on average.

**MAPE (Mean Absolute Percentage Error)**
The average error expressed as a percentage of the actual value. This is your primary accuracy metric. Under 10% is strong for small-business data. 10–20% is moderate. Over 20% means use for trend direction only.

**Model**
In SignalStack context, the trained SARIMA statistical model for a given signal. Stored as a `.pkl` file in the `models/` folder. Reloaded on each `--skip-search` run.

**Ops Pulse**
SignalStack's operational health signal. Tracks jobs completed, on-time rate, callback rate, crew utilization, and open work orders per week.

**Outlier**
A data point that falls significantly outside the normal range. Examples: a holiday week with unusually low jobs, a one-time large deal that spikes pipeline value. SignalStack detects and handles these automatically before modeling.

**Pipeline Pulse**
SignalStack's sales pipeline signal. Aggregates the estimated value of prospects entered each week, tracking direction and velocity of new business.

**RMSE (Root Mean Square Error)**
Similar to MAE but penalizes large misses more heavily. If RMSE is significantly higher than MAE, it means the model occasionally makes big misses even if the average error is acceptable.

**SARIMA**
Seasonal AutoRegressive Integrated Moving Average. The statistical model used by SignalStack to learn patterns in time series data and project them forward. The "Seasonal" part means it can detect repeating patterns (weekly, monthly, quarterly rhythms) in your data.

**Seasonal Period**
How long one "season" is in your data. For weekly data with a monthly pattern, seasonal_period = 4 (four weeks per month). For daily business data with a weekly pattern, seasonal_period = 5 (five business days per week).

**Signal**
In SignalStack, a "signal" is one tracked business metric — sales revenue, jobs completed, cash balance, pipeline value, or billable hours. Each signal has its own model, data, and output.

**Skip-Search**
A command flag (`--skip-search`) that tells the pipeline to skip the slow SARIMA grid search and use the parameters already saved in `MANUAL_PARAMS` in `run_pipeline.py`. Use this every week after your first full run.

**Team Tempo**
SignalStack's workforce signal. Tracks headcount, billable hours, overtime hours, utilization rate, turnover, and training hours per week.

**Training Data**
The historical periods the SARIMA model learned from. Shown as the blue line on forecast charts. More training data = better model accuracy.

**Validation Period**
The most recent portion of your history held back from training and used to test how accurate the model is. Shown as the green line on forecast charts. The difference between green and orange is your error rate.

**Virtual Environment (venv)**
A self-contained Python installation specific to this project. Keeps SignalStack's dependencies isolated from other software on your computer. Activated by running `.\venv_tnds-signal-engine\Scripts\Activate.ps1`.

---

## Quick Reference Card

### Weekly Commands
```powershell
# Activate environment
.\venv_tnds-signal-engine\Scripts\Activate.ps1

# Update Excel files first, then:
python export_to_csv.py
python run_pipeline.py --source all --skip-search
python generate_report.py
```

### Run grid search (quarterly or after major data additions)
```powershell
python run_pipeline.py --source all
```

### Single source
```powershell
python export_to_csv.py --source ops_pulse
python run_pipeline.py --source ops_pulse --skip-search
python generate_report.py --source ops_pulse
```

### Custom report filename
```powershell
python generate_report.py --out "reports\ClientName_YYYY-Www.docx"
```

### Check current ISO week
```powershell
python -c "import datetime; print(datetime.date.today().strftime('%G-W%V'))"
```

### Accuracy rating guide
| MAPE | Rating | Use For |
|---|---|---|
| Under 5% | Excellent | Operational decisions |
| 5–10% | Good | Planning and projections |
| 10–20% | Moderate | Directional guidance |
| 20–35% | Fair | Trend direction only |
| Over 35% | Developing | Add more data |

---

*SignalStack — Turning Data into Direction*
*True North Data Strategies | jacob@truenorthstrategyops.com | 719-204-6365 | SDVOSB*
