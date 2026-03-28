"""
preprocessor.py — SignalStack: Outlier detection, cleaning, and smoothing.
==========================================================================
Takes a raw time series and source config dict. Detects outliers using
the method configured per source (IQR or Z-score), handles them, applies
EWM smoothing, and saves intermediate outputs to data/processed/<source>/.

All parameters (multiplier, span, method) come from the source config —
no hardcoded values. The same logic works for daily sales data and
weekly ops data because frequency-appropriate defaults are set in
config.SOURCE_REGISTRY.

Usage:
    from config import get_source
    from src.preprocessor import preprocess

    src = get_source("ops_pulse")
    cleaned, smoothed = preprocess(time_series, src)
"""

import pandas as pd
import numpy as np
from scipy.stats import zscore
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def detect_outliers_iqr(series, multiplier):
    """
    Detect outliers using Interquartile Range method.

    Parameters:
        series (pd.Series):  Input time series.
        multiplier (float):  IQR multiplier threshold.

    Returns:
        pd.Series: Boolean mask — True = outlier.
    """
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr

    mask = (series < lower) | (series > upper)
    print(f"[preprocessor] IQR bounds: [{lower:.2f}, {upper:.2f}]  |  Outliers: {mask.sum()} of {len(series)} ({mask.mean()*100:.1f}%)")
    return mask


def detect_outliers_zscore(series, threshold):
    """
    Detect outliers using Z-score method.

    Parameters:
        series (pd.Series):  Input time series.
        threshold (float):   Z-score threshold (typically 3).

    Returns:
        pd.Series: Boolean mask — True = outlier.
    """
    z = np.abs(zscore(series.dropna()))
    mask = pd.Series(False, index=series.index)
    mask.loc[series.dropna().index] = z > threshold

    print(f"[preprocessor] Z-score threshold: {threshold}  |  Outliers: {mask.sum()} of {len(series)} ({mask.mean()*100:.1f}%)")
    return mask


def handle_outliers(series, mask, method, iqr_multiplier):
    """
    Replace or remove detected outliers.

    Parameters:
        series (pd.Series):   Original time series.
        mask (pd.Series):     Boolean outlier mask.
        method (str):         "median" | "cap" | "remove"
        iqr_multiplier (float): Used for cap method bounds.

    Returns:
        pd.Series: Cleaned series.
    """
    cleaned = series.copy()

    if method == "median":
        median_val = series.median()
        cleaned[mask] = median_val
        print(f"[preprocessor] Replaced {mask.sum()} outliers with median ({median_val:.2f})")

    elif method == "cap":
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        lo = q1 - iqr_multiplier * iqr
        hi = q3 + iqr_multiplier * iqr
        cleaned = series.clip(lower=lo, upper=hi)
        print(f"[preprocessor] Capped {mask.sum()} outliers to [{lo:.2f}, {hi:.2f}]")

    elif method == "remove":
        cleaned = series[~mask]
        print(f"[preprocessor] Removed {mask.sum()} outlier rows. New length: {len(cleaned)}")

    else:
        raise ValueError(f"[preprocessor] Unknown outlier method: '{method}'. Use: median | cap | remove")

    return cleaned


def smooth(series, span):
    """
    Apply Exponential Weighted Moving Average smoothing.

    Parameters:
        series (pd.Series):  Cleaned time series.
        span (int):          EWM span. Shorter for weekly data (4), longer for daily (14).

    Returns:
        pd.Series: Smoothed series.
    """
    smoothed = series.ewm(span=span).mean()
    print(f"[preprocessor] EWM smoothing applied (span={span})")
    return smoothed


def preprocess(time_series, src, save=True):
    """
    Full preprocessing pipeline for a SignalStack source.

    Steps:
        1. Detect outliers (IQR or Z-score per source config)
        2. Handle outliers (median replace, cap, or remove)
        3. Apply EWM smoothing
        4. Save cleaned and smoothed CSVs to data/processed/<source>/

    Parameters:
        time_series (pd.Series):  Raw time series from data_loader.
        src (dict):               Source config from config.get_source().
        save (bool):              Write intermediate CSVs (default True).

    Returns:
        tuple: (cleaned_series, smoothed_series)
    """
    label = src.get("description", src["raw_subdir"])
    print(f"[preprocessor] Starting — {label}")
    print(f"[preprocessor] Input length: {len(time_series)} periods")

    # ── Detect outliers ───────────────────────────────────────────────────────
    method = src["outlier_method"]
    if method == "iqr":
        outlier_mask = detect_outliers_iqr(time_series, src["iqr_multiplier"])
    elif method == "zscore":
        outlier_mask = detect_outliers_zscore(time_series, src["zscore_threshold"])
    else:
        raise ValueError(f"[preprocessor] Unknown outlier_method: '{method}'. Use: iqr | zscore")

    # ── Handle outliers ───────────────────────────────────────────────────────
    cleaned = handle_outliers(
        time_series,
        outlier_mask,
        method=src["outlier_replacement"],
        iqr_multiplier=src["iqr_multiplier"],
    )

    # ── Smooth ────────────────────────────────────────────────────────────────
    smoothed = smooth(cleaned, span=src["smoothing_span"])

    # ── Save intermediates ────────────────────────────────────────────────────
    if save:
        out_dir = src["data_processed"]
        os.makedirs(out_dir, exist_ok=True)

        cleaned_path  = os.path.join(out_dir, "cleaned_time_series.csv")
        smoothed_path = os.path.join(out_dir, "cleaned_smoothed_time_series.csv")
        cleaned.to_csv(cleaned_path)
        smoothed.to_csv(smoothed_path)
        print(f"[preprocessor] Saved: {cleaned_path}")
        print(f"[preprocessor] Saved: {smoothed_path}")

    print(f"[preprocessor] Done.\n")
    return cleaned, smoothed


if __name__ == "__main__":
    import argparse
    from config import get_source
    from src.data_loader import load_data

    parser = argparse.ArgumentParser(description="Test preprocessor for a source.")
    parser.add_argument("--source", default="sales", help="Source name from SOURCE_REGISTRY")
    args = parser.parse_args()

    src = get_source(args.source)
    _, ts = load_data(src)
    cleaned, smoothed = preprocess(ts, src)

    print(f"\nCleaned:\n{cleaned.describe()}")
    print(f"\nSmoothed:\n{smoothed.describe()}")
