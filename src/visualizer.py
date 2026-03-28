"""
visualizer.py — SignalStack: Plot generation for all pipeline stages.
=====================================================================
Produces 5 standard plots per source run:
    01_raw_time_series.png
    02_decomposition.png
    03_preprocessing.png
    04_forecast_vs_actual.png
    05_residuals.png

All plot titles and axis labels use the source's description and
target_column fields. All output paths are scoped to visuals/<source>/
so plots from different SignalStack signals don't overwrite each other.

Usage:
    from config import get_source
    from src.visualizer import plot_all

    src = get_source("pipeline_pulse")
    plot_all(time_series, cleaned, smoothed, model_results, forecast_df, src)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.tsa.seasonal import seasonal_decompose
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _save_fig(fig, filename, src):
    """Save figure to visuals/<source>/ directory."""
    visuals_dir = src["visuals_dir"]
    os.makedirs(visuals_dir, exist_ok=True)
    path = os.path.join(visuals_dir, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"[visualizer] Saved: {path}")
    plt.close(fig)


def plot_raw_series(time_series, src):
    """
    Plot the raw time series for initial EDA.
    Title includes source description and target column.
    """
    label  = src.get("description", src["raw_subdir"])
    target = src["target_column"]
    colors = src["colors"]
    fig_sz = src["figure_size"]

    fig, ax = plt.subplots(figsize=fig_sz)
    ax.plot(time_series, label=target, color=colors["train"])
    ax.set_title(f"Raw Time Series — {label}")
    ax.set_xlabel("Date")
    ax.set_ylabel(target)
    ax.legend()
    ax.grid(True)
    _save_fig(fig, "01_raw_time_series.png", src)


def plot_decomposition(time_series, src):
    """
    Plot seasonal decomposition: trend, seasonal component, residual.
    Uses seasonal_period from source config.
    """
    label  = src.get("description", src["raw_subdir"])
    period = src["seasonal_period"]
    fig_sz = src["figure_size"]

    try:
        decomp = seasonal_decompose(time_series.dropna(), model="additive", period=period)
    except ValueError as e:
        print(f"[visualizer] Decomposition skipped (not enough data for period={period}): {e}")
        return

    fig, axes = plt.subplots(4, 1, figsize=(fig_sz[0], 12))
    axes[0].plot(time_series,    color="blue");   axes[0].set_title("Original")
    axes[1].plot(decomp.trend,   color="orange"); axes[1].set_title("Trend")
    axes[2].plot(decomp.seasonal,color="green");  axes[2].set_title("Seasonal")
    axes[3].plot(decomp.resid,   color="red");    axes[3].set_title("Residual")

    for ax in axes:
        ax.grid(True)
    fig.suptitle(f"Seasonal Decomposition — {label}", y=1.01)
    fig.tight_layout()
    _save_fig(fig, "02_decomposition.png", src)


def plot_preprocessing(raw, cleaned, smoothed, src):
    """
    Compare raw vs cleaned vs smoothed series.
    Shows the effect of outlier handling and EWM smoothing.
    """
    label  = src.get("description", src["raw_subdir"])
    target = src["target_column"]
    fig_sz = src["figure_size"]

    fig, ax = plt.subplots(figsize=fig_sz)
    ax.plot(raw,      label="Raw",                     alpha=0.4, color="gray")
    ax.plot(cleaned,  label="Cleaned (outliers fixed)", alpha=0.7, color="blue")
    ax.plot(smoothed, label=f"Smoothed (EWM span={src['smoothing_span']})", color="green")
    ax.set_title(f"Preprocessing Pipeline — {label}")
    ax.set_xlabel("Date")
    ax.set_ylabel(target)
    ax.legend()
    ax.grid(True)
    _save_fig(fig, "03_preprocessing.png", src)


def plot_forecast_vs_actual(train, validation, forecast_values, ci_df, src):
    """
    Plot training history, actual validation period, and SARIMA forecast
    with confidence interval band.
    """
    label  = src.get("description", src["raw_subdir"])
    target = src["target_column"]
    colors = src["colors"]
    fig_sz = src["figure_size"]

    fig, ax = plt.subplots(figsize=fig_sz)
    ax.plot(train,           label="Training Data",      color=colors["train"])
    ax.plot(validation,      label="Actual (Validation)", color=colors["actual"])
    ax.plot(forecast_values, label="Forecast",            color=colors["forecast"])
    ax.fill_between(
        forecast_values.index,
        ci_df.iloc[:, 0],
        ci_df.iloc[:, 1],
        color=colors["ci_fill"],
        alpha=colors["ci_alpha"],
        label="95% CI",
    )
    ax.set_title(f"SARIMA Forecast vs Actual — {label}")
    ax.set_xlabel("Date")
    ax.set_ylabel(target)
    ax.legend()
    ax.grid(True)
    _save_fig(fig, "04_forecast_vs_actual.png", src)


def plot_residuals(forecast_df, src):
    """
    Plot residuals over time and their distribution histogram.
    Used to visually check for systematic bias in the model.
    """
    label  = src.get("description", src["raw_subdir"])
    colors = src["colors"]
    fig_sz = src["figure_size"]

    fig, axes = plt.subplots(1, 2, figsize=(fig_sz[0] * 1.5, fig_sz[1]))

    axes[0].plot(forecast_df["Residual"], color=colors["residual"])
    axes[0].axhline(y=0, color="black", linestyle="--", alpha=0.5)
    axes[0].set_title(f"Residuals Over Time — {label}")
    axes[0].set_xlabel("Date")
    axes[0].grid(True)

    axes[1].hist(forecast_df["Residual"], bins=20, color=colors["residual"], alpha=0.7)
    axes[1].set_title("Residual Distribution")
    axes[1].set_xlabel("Residual Value")

    fig.tight_layout()
    _save_fig(fig, "05_residuals.png", src)


def plot_all(time_series, cleaned, smoothed, model_results, forecast_df, src):
    """
    Generate all 5 standard SignalStack plots for one source run.

    Parameters:
        time_series (pd.Series):    Raw time series from data_loader.
        cleaned (pd.Series):        After outlier handling.
        smoothed (pd.Series):       After EWM smoothing.
        model_results (dict):       From model.train_model().
        forecast_df (pd.DataFrame): From evaluator.evaluate().
        src (dict):                 Source config from config.get_source().
    """
    label = src.get("description", src["raw_subdir"])
    print(f"\n[visualizer] Generating plots — {label}")

    plot_raw_series(time_series, src)
    plot_decomposition(time_series, src)
    plot_preprocessing(time_series, cleaned, smoothed, src)

    # Reconstruct forecast series for the forecast vs actual plot
    from src.evaluator import forecast as run_forecast
    forecast_values, ci = run_forecast(
        model_results["model"],
        steps=len(model_results["validation"]),
        log_transformed=model_results["log_transformed"],
    )
    plot_forecast_vs_actual(
        model_results["train"],
        model_results["validation"],
        forecast_values,
        ci,
        src,
    )
    plot_residuals(forecast_df, src)

    print(f"[visualizer] All plots saved to: {src['visuals_dir']}/\n")
