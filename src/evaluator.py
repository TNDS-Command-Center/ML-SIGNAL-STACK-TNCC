"""
evaluator.py — SignalStack: Forecast evaluation and metrics.
============================================================
Generates forecasts over the validation period from a trained SARIMA model,
computes MAE/RMSE/MAPE, saves results to data/output/<source>/.

No logic changes from original — all parameters come from src dict and
model_results dict. Output paths are scoped per source so all five
SignalStack signals can be evaluated independently.

Usage:
    from config import get_source
    from src.evaluator import evaluate

    src = get_source("team_tempo")
    metrics, forecast_df = evaluate(model_results, src)
"""

import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def forecast(fitted_model, steps, log_transformed=True):
    """
    Generate a forecast from a fitted SARIMAX model.

    Parameters:
        fitted_model:        Trained SARIMAXResultsWrapper.
        steps (int):         Periods to forecast.
        log_transformed (bool): Reverse log1p if True.

    Returns:
        tuple: (forecast_series, confidence_interval_df)
    """
    raw_forecast = fitted_model.get_forecast(steps=steps)

    if log_transformed:
        forecast_values = np.expm1(raw_forecast.predicted_mean)
        ci              = np.expm1(raw_forecast.conf_int())
    else:
        forecast_values = raw_forecast.predicted_mean
        ci              = raw_forecast.conf_int()

    return forecast_values, ci


def compute_metrics(actual, predicted):
    """
    Compute standard regression metrics for time series evaluation.

    Parameters:
        actual (pd.Series):    Actual observed values.
        predicted (pd.Series): Model forecast values.

    Returns:
        dict: MAE, MSE, RMSE, MAPE, Average_Actual, MAE_pct_of_avg, RMSE_pct_of_avg
    """
    mae  = mean_absolute_error(actual, predicted)
    mse  = mean_squared_error(actual, predicted)
    rmse = np.sqrt(mse)
    avg  = actual.mean()

    nonzero = actual != 0
    if nonzero.any():
        mape = np.mean(np.abs((actual[nonzero] - predicted[nonzero]) / actual[nonzero])) * 100
    else:
        mape = float("inf")

    return {
        "MAE":              mae,
        "MSE":              mse,
        "RMSE":             rmse,
        "MAPE":             mape,
        "Average_Actual":   avg,
        "MAE_pct_of_avg":   (mae  / avg) * 100 if avg != 0 else float("inf"),
        "RMSE_pct_of_avg":  (rmse / avg) * 100 if avg != 0 else float("inf"),
    }


def evaluate(model_results, src):
    """
    Full evaluation pipeline for a SignalStack source.

    Steps:
        1. Forecast the validation period
        2. Compute error metrics
        3. Build forecast DataFrame (Actual, Forecast, CI bounds, Residuals)
        4. Save forecast CSV and metrics txt to data/output/<source>/

    Parameters:
        model_results (dict):  Output from model.train_model().
        src (dict):            Source config from config.get_source().

    Returns:
        tuple: (metrics_dict, forecast_dataframe)
    """
    label = src.get("description", src["raw_subdir"])
    print(f"\n[evaluator] Starting — {label}")

    fitted         = model_results["model"]
    validation     = model_results["validation"]
    log_transformed = model_results["log_transformed"]

    # ── Forecast validation period ────────────────────────────────────────────
    forecast_values, ci = forecast(
        fitted,
        steps=len(validation),
        log_transformed=log_transformed,
    )

    # ── Compute metrics ───────────────────────────────────────────────────────
    metrics = compute_metrics(validation, forecast_values)

    print(f"[evaluator] Source:          {src['raw_subdir']}")
    print(f"[evaluator] Target:          {src['target_column']}")
    print(f"[evaluator] MAE:             {metrics['MAE']:.2f}")
    print(f"[evaluator] RMSE:            {metrics['RMSE']:.2f}")
    print(f"[evaluator] MAPE:            {metrics['MAPE']:.2f}%")
    print(f"[evaluator] MAE % of avg:    {metrics['MAE_pct_of_avg']:.2f}%")
    print(f"[evaluator] RMSE % of avg:   {metrics['RMSE_pct_of_avg']:.2f}%")

    # ── Build results DataFrame ───────────────────────────────────────────────
    forecast_df = pd.DataFrame({
        "Actual":    validation.values,
        "Forecast":  forecast_values.values,
        "Lower_CI":  ci.iloc[:, 0].values,
        "Upper_CI":  ci.iloc[:, 1].values,
        "Residual":  (validation.values - forecast_values.values),
    }, index=validation.index)

    # ── Save outputs ──────────────────────────────────────────────────────────
    out_dir = src["data_output"]
    os.makedirs(out_dir, exist_ok=True)

    forecast_path = os.path.join(out_dir, "forecast_results.csv")
    forecast_df.to_csv(forecast_path)
    print(f"[evaluator] Forecast saved:  {forecast_path}")

    metrics_path = os.path.join(out_dir, "metrics.txt")
    with open(metrics_path, "w") as f:
        f.write(f"Source:     {src['raw_subdir']}\n")
        f.write(f"Target:     {src['target_column']}\n")
        f.write(f"Frequency:  {src['frequency']}\n")
        f.write(f"Model:      SARIMA{model_results['order']}x{model_results['seasonal_order']}\n")
        f.write(f"AIC:        {model_results['aic']:.4f}\n\n")
        for k, v in metrics.items():
            f.write(f"{k}: {v}\n")
    print(f"[evaluator] Metrics saved:   {metrics_path}")

    print(f"[evaluator] Done.\n")
    return metrics, forecast_df
