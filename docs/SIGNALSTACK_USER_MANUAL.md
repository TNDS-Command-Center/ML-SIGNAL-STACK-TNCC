# SignalStack User Manual
## True North Data Strategies
### For Business Owners — No Data Science Background Required

**Version 1.0 | Jacob Johnston | jacob@truenorthstrategyops.com | 719-204-6365**
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

**A Word document report** in the `reports/` folder, automatically named by ISO week (e.g., `SignalStack_Report_2026-W14.docx`). It contains:
- An Executive Summary table — all five signals at a glance, color-coded by accuracy
- A detail section per signal — metrics scorecard + embedded forecast chart
- A Glossary — every term in plain English

**Five forecast charts** as PNG image files in `visuals/` — one per signal.

**Five metrics files** in `data/output/` — MAE, RMSE, MAPE, model selected.

**Five trained model files** in `models/` — reused each week so the run takes seconds.

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
    output/       Auto-generated metrics and forecast CSVs.
  models/         Saved trained models. Do not delete.
  visuals/        Saved forecast charts (PNG).
  reports/        Word document reports land here.
  docs/           This manual and other documentation.
```

---

## 4. Your Five Business Signals

### Signal 1: Sales (Daily Sales Revenue)
**File:** `tnds-sales-data-template.xlsx` → tab: `PIPELINE_READY`
**Forecasts:** Daily revenue (Qty × Price per transaction)
**Minimum history:** 67 business days (~3.5 months)

One row per transaction. Three columns:
| Column | Format | Example |
|---|---|---|
| Date | MM/DD/YYYY | 03/28/2026 |
| Qty | Number | 500 |
| Sales Price | Dollar per unit | 3.85 |

**Best data source:** QuickBooks → Sales by Customer Detail → export as Excel → copy Date, Qty, Rate columns into PIPELINE_READY tab.

If you only have a total (no qty/price split), put `1` in Qty and the full dollar amount in Sales Price.

