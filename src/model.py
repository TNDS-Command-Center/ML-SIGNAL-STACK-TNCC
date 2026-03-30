"""
model.py — SignalStack: SARIMA grid search, training, and model persistence.
============================================================================
All SARIMA parameters (ranges, seasonal period, iterations) come from the
source config dict — not hardcoded. Each source gets its own model file
saved under models/<source>/sarima_model.pkl so you can run and compare
all five SignalStack signals without overwriting each other.

The internal logic is identical to the original; the only change is that
config values are read from src dict instead of the global config module.

Usage:
    from config import get_source
    from src.model import train_model, load_model

    src = get_source("cash_flow_compass")
    results = train_model(smoothed_series, src)
    model = load_model(src)
"""

import pandas as pd
import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX
import itertools
import joblib
import warnings
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

warnings.filterwarnings("ignore")


def split_data(series, src):
    """
    Split time series into training and validation sets.

    Parameters:
        series (pd.Series):  Preprocessed time series.
        src (dict):          Source config. Uses src["validation_size"].

    Returns:
        tuple: (train, validation)
    """
    n = src["validation_size"]
    train      = series[:-n]
    validation = series[-n:]

    max_train = src.get("max_train_periods")
    if max_train and len(train) > max_train:
        discarded = len(train) - max_train
        train = train.iloc[-max_train:]
        print(f"[model] Training window capped: using last {max_train} of {max_train + discarded} periods")

    print(f"[model] Train: {len(train)} periods  |  Validation: {len(validation)} periods")
    return train, validation


def apply_log_transform(train, validation):
    """
    Apply log1p transform. Floors zero/negative values to avoid log(0).

    Returns:
        tuple: (train_log, validation_log)
    """
    train_safe = train.copy()
    train_safe[train_safe <= 0] = 1e-5
    print(f"[model] Log transform applied.")
    return np.log1p(train_safe), np.log1p(validation)


def _validation_mape(fitted_model, validation, log_transformed):
    """
    Compute validation MAPE for a fitted model over a given validation window.
    """
    if validation is None or len(validation) == 0:
        return float("inf")

    raw_forecast = fitted_model.get_forecast(steps=len(validation))
    if log_transformed:
        forecast_values = np.expm1(raw_forecast.predicted_mean)
    else:
        forecast_values = raw_forecast.predicted_mean

    nonzero = validation != 0
    if not nonzero.any():
        return float("inf")

    mask = nonzero.values
    return float(
        np.mean(
            np.abs(
                (validation.values[mask] - forecast_values.values[mask])
                / validation.values[mask]
            )
        ) * 100
    )


def grid_search(train_data, src, validation=None, log_transformed=True):
    """
    SARIMA parameter grid search using AIC as selection criterion.

    Parameters:
        train_data (pd.Series):  Training data (log-transformed if applicable).
        src (dict):              Source config — provides all SARIMA ranges.

    Returns:
        tuple: (best_order, best_seasonal_order, best_raw_aic)
    """
    pdq = list(itertools.product(
        src["sarima_p_range"],
        src["sarima_d_range"],
        src["sarima_q_range"],
    ))
    seasonal_pdq = list(itertools.product(
        src["sarima_seasonal_p"],
        src["sarima_seasonal_d"],
        src["sarima_seasonal_q"],
        [src["seasonal_period"]],
    ))

    total = len(pdq) * len(seasonal_pdq)
    label = src.get("description", src["raw_subdir"])
    print(f"[model] Grid search — {label}: {total} combinations")

    best_raw_aic      = float("inf")
    best_adjusted_aic = float("inf")
    best_order        = None
    best_seasonal     = None
    best_converged    = False
    best_total_params = 0
    tested            = 0
    errors            = 0
    convergence_failures = 0

    for param in pdq:
        for seasonal_param in seasonal_pdq:
            tested += 1
            try:
                model = SARIMAX(
                    train_data,
                    order=param,
                    seasonal_order=seasonal_param,
                )
                results = model.fit(
                    disp=False,
                    maxiter=src["max_iter_search"],
                    tol=src["tolerance_search"],
                )
                # Check convergence -- reject models that didn't converge
                mle_retvals = getattr(results, "mle_retvals", {}) or {}
                converged = bool(mle_retvals.get("converged", True))
                if not converged:
                    errors += 1
                    convergence_failures += 1
                    continue

                total_params = sum(param) + sum(seasonal_param[:3])
                n_train = len(train_data)
                # Penalize over-parameterized models on short series
                adjusted_aic = results.aic
                if total_params > 0 and n_train / total_params < 10:
                    adjusted_aic += 50 * (total_params - n_train / 10)

                if adjusted_aic < best_adjusted_aic:
                    best_adjusted_aic = adjusted_aic
                    best_raw_aic      = results.aic
                    best_order        = param
                    best_seasonal     = seasonal_param
                    best_converged    = converged
                    best_total_params = total_params
                    print(
                        f"[model] [{tested}/{total}]  New best: "
                        f"SARIMA{param}x{seasonal_param}  "
                        f"AIC={best_raw_aic:.4f}  Adjusted={best_adjusted_aic:.4f}"
                    )
            except Exception:
                errors += 1
                continue

    if best_order is None or best_seasonal is None:
        raise RuntimeError("[model] Grid search failed — no valid converged model found.")

    print(
        f"[model] Search complete — Tested: {tested}  "
        f"Errors: {errors}  Convergence failures: {convergence_failures}"
    )
    print(
        f"[model] Best: SARIMA{best_order}x{best_seasonal}  "
        f"AIC={best_raw_aic:.4f}  Adjusted={best_adjusted_aic:.4f}"
    )

    # MAPE guardrail for short/noisy series: fallback to simpler model when needed
    if validation is not None and len(validation) > 0:
        try:
            best_model = SARIMAX(
                train_data,
                order=best_order,
                seasonal_order=best_seasonal,
            ).fit(
                disp=False,
                maxiter=src["max_iter_search"],
                tol=src["tolerance_search"],
            )
            best_mape = _validation_mape(best_model, validation, log_transformed)

            if best_mape > 25:
                print(
                    f"[model] MAPE guardrail triggered: best AIC model "
                    f"MAPE={best_mape:.1f}% > 25%. Testing simple fallback..."
                )
                fallback_order = (0, 1, 1)
                fallback_seasonal = (0, 0, 0, src["seasonal_period"])
                fallback_model = SARIMAX(
                    train_data,
                    order=fallback_order,
                    seasonal_order=fallback_seasonal,
                ).fit(
                    disp=False,
                    maxiter=src["max_iter_search"],
                    tol=src["tolerance_search"],
                )

                fallback_retvals = getattr(fallback_model, "mle_retvals", {}) or {}
                if not bool(fallback_retvals.get("converged", True)):
                    print("[model] Fallback model failed convergence. Keeping best AIC model.")
                else:
                    fallback_mape = _validation_mape(fallback_model, validation, log_transformed)
                    print(
                        f"[model] Guardrail compare — "
                        f"AIC model MAPE={best_mape:.1f}% vs "
                        f"fallback MAPE={fallback_mape:.1f}%"
                    )
                    if fallback_mape < best_mape:
                        best_order = fallback_order
                        best_seasonal = fallback_seasonal
                        best_raw_aic = fallback_model.aic
                        best_adjusted_aic = fallback_model.aic
                        best_converged = True
                        best_total_params = sum(fallback_order) + sum(fallback_seasonal[:3])
                        print(
                            "[model] Guardrail applied — using simple fallback "
                            f"SARIMA{best_order}x{best_seasonal}"
                        )
        except Exception as e:
            print(f"[model] MAPE guardrail skipped due to error: {e}")

    # Save best parameters as text
    out_dir    = src["data_output"]
    os.makedirs(out_dir, exist_ok=True)
    params_path = os.path.join(out_dir, "best_sarima_parameters.txt")
    with open(params_path, "w") as f:
        f.write(f"Source:           {src['raw_subdir']}\n")
        f.write(f"Target:           {src['target_column']}\n")
        f.write(f"Best order:       {best_order}\n")
        f.write(f"Best seasonal:    {best_seasonal}\n")
        f.write(f"AIC:              {best_raw_aic}\n")
        f.write(f"Adjusted AIC:     {best_adjusted_aic}\n")
        f.write(f"Convergence:      {best_converged}\n")
        f.write(f"Total params:     {best_total_params}\n")
    print(f"[model] Parameters saved: {params_path}")

    return best_order, best_seasonal, best_raw_aic


def train_final_model(train_data, order, seasonal_order, src):
    """
    Train the final SARIMA model with the best parameters.

    Parameters:
        train_data (pd.Series):         Training data.
        order (tuple):                  (p, d, q)
        seasonal_order (tuple):         (P, D, Q, s)
        src (dict):                     Source config (for max_iter, tolerance).

    Returns:
        SARIMAXResultsWrapper: Fitted model.
    """
    print(f"[model] Training final model: SARIMA{order}x{seasonal_order}")
    model  = SARIMAX(train_data, order=order, seasonal_order=seasonal_order)
    fitted = model.fit(
        disp=False,
        maxiter=src["max_iter_final"],
        tol=src["tolerance_final"],
    )
    print(f"[model] Final AIC: {fitted.aic:.4f}")
    return fitted


def save_model(fitted_model, src, filename="sarima_model.pkl"):
    """
    Save fitted model to models/<source>/.

    Parameters:
        fitted_model:   Trained SARIMAXResultsWrapper.
        src (dict):     Source config — provides models_dir.
        filename (str): Output filename.

    Returns:
        str: Full path to saved model.
    """
    models_dir = src["models_dir"]
    os.makedirs(models_dir, exist_ok=True)
    path = os.path.join(models_dir, filename)
    joblib.dump(fitted_model, path)
    print(f"[model] Model saved: {path}")
    return path


def load_model(src, filename="sarima_model.pkl"):
    """
    Load a previously saved model for this source.

    Parameters:
        src (dict):     Source config — provides models_dir.
        filename (str): Model filename.

    Returns:
        SARIMAXResultsWrapper: Loaded model.
    """
    path = os.path.join(src["models_dir"], filename)
    model = joblib.load(path)
    print(f"[model] Model loaded: {path}")
    return model


def train_model(smoothed_series, src, smoothed_series_full=None):
    """
    Full training pipeline for a SignalStack source.

    Steps:
        1. Split train/validation
        2. Optionally apply log transform
        3. SARIMA grid search
        4. Train final model with best params
        5. Save model to models/<source>/

    Parameters:
        smoothed_series (pd.Series):  Preprocessed time series from preprocessor.
        src (dict):                   Source config from config.get_source().
        smoothed_series_full (pd.Series | None):
            Optional full smoothed series to carry through model_results.
            If None, uses smoothed_series.

    Returns:
        dict: {
            "model":            fitted SARIMAX model,
            "train":            training pd.Series,
            "validation":       validation pd.Series,
            "smoothed":         full smoothed pd.Series,
            "order":            (p, d, q),
            "seasonal_order":   (P, D, Q, s),
            "aic":              float,
            "log_transformed":  bool,
            "source":           source name string,
        }
    """
    label = src.get("description", src["raw_subdir"])
    print(f"\n[model] Starting training — {label}")
    smoothed_for_results = smoothed_series_full if smoothed_series_full is not None else smoothed_series

    train, validation = split_data(smoothed_series, src)

    if src["log_transform"]:
        train_input, _ = apply_log_transform(train, validation)
    else:
        train_input = train

    order, seasonal_order, aic = grid_search(
        train_input,
        src,
        validation=validation,
        log_transformed=src["log_transform"],
    )
    fitted = train_final_model(train_input, order, seasonal_order, src)
    save_model(fitted, src)

    return {
        "model":          fitted,
        "train":          train,
        "validation":     validation,
        "smoothed":       smoothed_for_results,
        "order":          order,
        "seasonal_order": seasonal_order,
        "aic":            aic,
        "log_transformed": src["log_transform"],
        "source":         src["raw_subdir"],
    }
