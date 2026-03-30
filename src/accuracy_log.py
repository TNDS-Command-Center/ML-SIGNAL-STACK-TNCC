"""
accuracy_log.py — SignalStack: Persistent accuracy tracking across runs.
========================================================================
Appends each pipeline run's key metrics to a CSV log file so you can
track model improvement over time. One row per source per run.

Usage:
    from src.accuracy_log import log_run
    log_run(source_name, model_results, metrics, src)
"""

import os
import csv
import datetime


LOG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "output",
    "accuracy_log.csv",
)

COLUMNS = [
    "timestamp", "iso_week", "source", "model", "aic",
    "mape", "mae", "rmse", "cv_mean_mape", "cv_std_mape",
    "train_size", "validation_size", "forecast_horizon",
]


def log_run(source_name, model_results, metrics, src):
    """Append one row to the accuracy log CSV."""
    exists = os.path.exists(LOG_FILE)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    now = datetime.datetime.now()
    row = {
        "timestamp":       now.isoformat(timespec="seconds"),
        "iso_week":        now.strftime("%G-W%V"),
        "source":          source_name,
        "model":           f"SARIMA{model_results['order']}x{model_results['seasonal_order']}",
        "aic":             f"{model_results['aic']:.4f}",
        "mape":            f"{metrics['MAPE']:.2f}",
        "mae":             f"{metrics['MAE']:.2f}",
        "rmse":            f"{metrics['RMSE']:.2f}",
        "cv_mean_mape":    f"{metrics.get('CV_Mean_MAPE', '')}" if metrics.get("CV_Mean_MAPE") else "",
        "cv_std_mape":     f"{metrics.get('CV_Std_MAPE', '')}" if metrics.get("CV_Std_MAPE") else "",
        "train_size":      len(model_results.get("train", [])),
        "validation_size": src["validation_size"],
        "forecast_horizon": src["forecast_horizon"],
    }

    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)

    print(f"[accuracy_log] Logged: {source_name} | MAPE={metrics['MAPE']:.1f}% | {LOG_FILE}")
