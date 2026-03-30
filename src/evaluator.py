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


def ensemble_forecast(fitted_model, steps, log_transformed, smoothed_series, weights=(0.6, 0.4)):
    """
    Blend SARIMA forecast with a simple weighted moving average projection.

    For volatile signals like pipeline value, pure SARIMA can overreact to
    recent noise. This blends the SARIMA prediction with a rolling-mean
    baseline to stabilize the forecast.

    Parameters:
        fitted_model:         Trained SARIMAXResultsWrapper.
        steps (int):          Periods to forecast.
        log_transformed (bool): Whether to reverse log1p.
        smoothed_series (pd.Series): The full smoothed time series (pre-split).
        weights (tuple):      (sarima_weight, ma_weight). Must sum to 1.0.

    Returns:
        tuple: (blended_forecast, sarima_ci)  -- CI remains from SARIMA only
    """
    sarima_forecast, sarima_ci = forecast(
        fitted_model,
        steps=steps,
        log_transformed=log_transformed,
    )

    if smoothed_series is None or len(smoothed_series) == 0:
        print("[evaluator] Ensemble fallback: smoothed series missing, using SARIMA only.")
        return sarima_forecast, sarima_ci

    if len(weights) != 2:
        raise ValueError("[evaluator] ensemble_weights must be a 2-item tuple: (sarima_weight, ma_weight)")

    sarima_weight, ma_weight = float(weights[0]), float(weights[1])
    weight_sum = sarima_weight + ma_weight
    if not np.isclose(weight_sum, 1.0):
        raise ValueError("[evaluator] ensemble_weights must sum to 1.0")

    recent = pd.Series(smoothed_series).dropna()
    window = min(8, len(recent))
    if window == 0:
        print("[evaluator] Ensemble fallback: smoothed series empty after dropna, using SARIMA only.")
        return sarima_forecast, sarima_ci

    recent_window = recent.iloc[-window:]
    # Exponential weighting keeps more influence on the latest points.
    exp_weights = np.exp(np.linspace(-1.0, 0.0, window))
    wma_level = float(np.average(recent_window.values, weights=exp_weights))
    ma_baseline = pd.Series([wma_level] * steps, index=sarima_forecast.index)

    blended = (sarima_weight * sarima_forecast) + (ma_weight * ma_baseline)
    blended.index = sarima_forecast.index

    print(
        f"[evaluator] Ensemble forecast: weights={weights} "
        f"| wma_window={window} | wma_level={wma_level:.2f}"
    )
    return blended, sarima_ci


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


def detect_residual_bias(forecast_df, threshold_pct=60):
    """
    Detect systematic residual bias (trend-tracking failure).

    Splits residuals into first-half and second-half of the validation window.
    If the sign of the mean residual flips between halves AND both halves have
    mean absolute residual > threshold_pct of overall MAE, flags it as a
    V-shaped or inverted-V bias pattern.

    Parameters:
        forecast_df (pd.DataFrame): Must contain 'Residual' column.
        threshold_pct (float):      Minimum % of MAE for each half to trigger.
                                    Default 60%.

    Returns:
        dict: {
            "bias_detected": bool,
            "pattern": str,          # "V-shaped" | "inverted-V" | "none"
            "first_half_mean": float,
            "second_half_mean": float,
            "overall_mae": float,
        }
    """
    residuals = forecast_df["Residual"].values
    n = len(residuals)
    if n < 4:
        return {
            "bias_detected": False,
            "pattern": "none",
            "first_half_mean": 0.0,
            "second_half_mean": 0.0,
            "overall_mae": 0.0,
        }

    mid = n // 2
    first_half = residuals[:mid]
    second_half = residuals[mid:]

    fh_mean = float(np.mean(first_half))
    sh_mean = float(np.mean(second_half))
    overall_mae = float(np.mean(np.abs(residuals)))

    threshold = overall_mae * (threshold_pct / 100)
    sign_flip = (fh_mean > 0 and sh_mean < 0) or (fh_mean < 0 and sh_mean > 0)
    both_significant = abs(fh_mean) > threshold and abs(sh_mean) > threshold

    if sign_flip and both_significant:
        pattern = "V-shaped" if fh_mean < 0 else "inverted-V"
        print(
            f"[evaluator] BIAS DETECTED: {pattern} residual pattern. "
            f"First half mean={fh_mean:.1f}, Second half mean={sh_mean:.1f}, "
            f"MAE={overall_mae:.1f}"
        )
        return {
            "bias_detected": True,
            "pattern": pattern,
            "first_half_mean": fh_mean,
            "second_half_mean": sh_mean,
            "overall_mae": overall_mae,
        }

    return {
        "bias_detected": False,
        "pattern": "none",
        "first_half_mean": fh_mean,
        "second_half_mean": sh_mean,
        "overall_mae": overall_mae,
    }


def cross_validate(smoothed_series, src, n_splits=3):
    """
    Rolling-origin cross-validation for SARIMA models.

    Creates n_splits expanding-window train/test splits, trains a model on each,
    and returns the average MAPE across all folds. Uses the best parameters saved
    in data/output/<source>/best_sarima_parameters.txt if available, otherwise
    uses a simple (1,1,1)(0,0,0,s) model.

    Parameters:
        smoothed_series (pd.Series): Full preprocessed time series.
        src (dict):                  Source config.
        n_splits (int):              Number of CV folds. Default 3.

    Returns:
        dict: {"cv_mapes": list[float], "cv_mean_mape": float, "cv_std_mape": float}
    """
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    val_size = src["validation_size"]
    total = len(smoothed_series)
    s = src["seasonal_period"]

    # Try to load best params from output, fallback to simple model
    params_path = os.path.join(src["data_output"], "best_sarima_parameters.txt")
    order = (1, 1, 1)
    seasonal = (0, 0, 0, s)
    if os.path.exists(params_path):
        import re
        text = open(params_path, encoding="utf-8").read()
        order_match = re.search(r"Best order:\s+\((\d+), (\d+), (\d+)\)", text)
        seasonal_match = re.search(r"Best seasonal:\s+\((\d+), (\d+), (\d+), (\d+)\)", text)
        if order_match:
            order = tuple(int(x) for x in order_match.groups())
        if seasonal_match:
            seasonal = tuple(int(x) for x in seasonal_match.groups())

    # Calculate fold boundaries
    min_train = max(2 * s + 10, total - val_size * (n_splits + 1))
    step = max(1, (total - min_train - val_size) // n_splits)

    mapes = []
    for fold in range(n_splits):
        train_end = min_train + fold * step
        test_end = min(train_end + val_size, total)
        if test_end > total:
            break

        train_fold = smoothed_series.iloc[:train_end]
        test_fold = smoothed_series.iloc[train_end:test_end]

        if len(test_fold) < 2:
            continue

        try:
            if src.get("log_transform", True):
                train_input = np.log1p(train_fold.clip(lower=1e-5))
            else:
                train_input = train_fold

            model = SARIMAX(train_input, order=order, seasonal_order=seasonal)
            fitted = model.fit(disp=False, maxiter=src.get("max_iter_search", 100))

            raw_fc = fitted.get_forecast(steps=len(test_fold))
            if src.get("log_transform", True):
                fc_values = np.expm1(raw_fc.predicted_mean)
            else:
                fc_values = raw_fc.predicted_mean

            nonzero = test_fold != 0
            if nonzero.any():
                mask = nonzero.values
                fold_mape = np.mean(
                    np.abs((test_fold.values[mask] - fc_values.values[mask]) / test_fold.values[mask])
                ) * 100
                mapes.append(float(fold_mape))
                print(f"[evaluator] CV fold {fold+1}/{n_splits}: MAPE={fold_mape:.1f}%")
        except Exception as e:
            print(f"[evaluator] CV fold {fold+1}/{n_splits}: FAILED — {e}")
            continue

    if not mapes:
        return {"cv_mapes": [], "cv_mean_mape": float("inf"), "cv_std_mape": float("inf")}

    result = {
        "cv_mapes": mapes,
        "cv_mean_mape": float(np.mean(mapes)),
        "cv_std_mape": float(np.std(mapes)),
    }
    print(f"[evaluator] CV summary: mean MAPE={result['cv_mean_mape']:.1f}% +/- {result['cv_std_mape']:.1f}%")
    return result


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
    smoothed_series = model_results.get("smoothed")

    # ── Forecast validation period ────────────────────────────────────────────
    if src.get("ensemble_forecast"):
        weights = tuple(src.get("ensemble_weights", (0.6, 0.4)))
        forecast_values, ci = ensemble_forecast(
            fitted,
            steps=len(validation),
            log_transformed=log_transformed,
            smoothed_series=smoothed_series,
            weights=weights,
        )
    else:
        forecast_values, ci = forecast(
            fitted,
            steps=len(validation),
            log_transformed=log_transformed,
        )

    # ── Compute metrics ───────────────────────────────────────────────────────
    metrics = compute_metrics(validation, forecast_values)

    # ── Cross-validation ─────────────────────────────────────────────────────
    if smoothed_series is not None and len(smoothed_series) > 0:
        full_series = smoothed_series
    else:
        full_series = pd.concat([model_results["train"], model_results["validation"]])
    cv_results = cross_validate(
        full_series,
        src,
        n_splits=3,
    )
    metrics["CV_Mean_MAPE"] = cv_results["cv_mean_mape"]
    metrics["CV_Std_MAPE"] = cv_results["cv_std_mape"]

    print(f"[evaluator] Source:          {src['raw_subdir']}")
    print(f"[evaluator] Target:          {src['target_column']}")
    print(f"[evaluator] MAE:             {metrics['MAE']:.2f}")
    print(f"[evaluator] RMSE:            {metrics['RMSE']:.2f}")
    print(f"[evaluator] MAPE:            {metrics['MAPE']:.2f}%")
    print(f"[evaluator] CV Mean MAPE:    {metrics['CV_Mean_MAPE']:.2f}%")
    print(f"[evaluator] CV Std MAPE:     {metrics['CV_Std_MAPE']:.2f}%")
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

    # ── Residual bias detection ──────────────────────────────────────────────
    bias = detect_residual_bias(forecast_df)
    metrics["Bias_Detected"] = bias["bias_detected"]
    metrics["Bias_Pattern"] = bias["pattern"]
    if bias["bias_detected"]:
        print(
            f"[evaluator] WARNING: {bias['pattern']} residual bias detected for "
            f"{src['raw_subdir']}. Consider increasing AR order or enabling ensemble."
        )

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
