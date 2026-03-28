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


def grid_search(train_data, src):
    """
    SARIMA parameter grid search using AIC as selection criterion.

    Parameters:
        train_data (pd.Series):  Training data (log-transformed if applicable).
        src (dict):              Source config — provides all SARIMA ranges.

    Returns:
        tuple: (best_order, best_seasonal_order, best_aic)
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

    best_aic      = float("inf")
    best_order    = None
    best_seasonal = None
    tested        = 0
    errors        = 0

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
                if results.aic < best_aic:
                    best_aic      = results.aic
                    best_order    = param
                    best_seasonal = seasonal_param
                    print(
                        f"[model] [{tested}/{total}]  New best: "
                        f"SARIMA{param}x{seasonal_param}  AIC={best_aic:.4f}"
                    )
            except Exception:
                errors += 1
                continue

    print(f"[model] Search complete — Tested: {tested}  Errors: {errors}")
    print(f"[model] Best: SARIMA{best_order}x{best_seasonal}  AIC={best_aic:.4f}")

    # Save best parameters as text
    out_dir    = src["data_output"]
    os.makedirs(out_dir, exist_ok=True)
    params_path = os.path.join(out_dir, "best_sarima_parameters.txt")
    with open(params_path, "w") as f:
        f.write(f"Source:           {src['raw_subdir']}\n")
        f.write(f"Target:           {src['target_column']}\n")
        f.write(f"Best order:       {best_order}\n")
        f.write(f"Best seasonal:    {best_seasonal}\n")
        f.write(f"AIC:              {best_aic}\n")
    print(f"[model] Parameters saved: {params_path}")

    return best_order, best_seasonal, best_aic


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


def train_model(smoothed_series, src):
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

    Returns:
        dict: {
            "model":            fitted SARIMAX model,
            "train":            training pd.Series,
            "validation":       validation pd.Series,
            "order":            (p, d, q),
            "seasonal_order":   (P, D, Q, s),
            "aic":              float,
            "log_transformed":  bool,
            "source":           source name string,
        }
    """
    label = src.get("description", src["raw_subdir"])
    print(f"\n[model] Starting training — {label}")

    train, validation = split_data(smoothed_series, src)

    if src["log_transform"]:
        train_input, _ = apply_log_transform(train, validation)
    else:
        train_input = train

    order, seasonal_order, aic = grid_search(train_input, src)
    fitted = train_final_model(train_input, order, seasonal_order, src)
    save_model(fitted, src)

    return {
        "model":          fitted,
        "train":          train,
        "validation":     validation,
        "order":          order,
        "seasonal_order": seasonal_order,
        "aic":            aic,
        "log_transformed": src["log_transform"],
        "source":         src["raw_subdir"],
    }
