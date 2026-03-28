"""
run_pipeline.py — SignalStack: Source-selectable pipeline entry point.
======================================================================
Single entry point for all five SignalStack data sources.
Pass --source to select which signal to run. Defaults to "sales".

Usage:
    python run_pipeline.py --source sales
    python run_pipeline.py --source ops_pulse
    python run_pipeline.py --source cash_flow_compass
    python run_pipeline.py --source pipeline_pulse
    python run_pipeline.py --source team_tempo

    # Skip slow grid search after first run (use saved/manual params):
    python run_pipeline.py --source sales --skip-search

    # Run all five sources sequentially:
    python run_pipeline.py --source all

Available sources: sales, ops_pulse, cash_flow_compass, pipeline_pulse, team_tempo
Each source reads its own CSV from data/raw/<source>/
Each source writes outputs to:
    data/processed/<source>/
    data/output/<source>/
    models/<source>/
    visuals/<source>/
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_source, SOURCE_REGISTRY
from src.data_loader  import load_data
from src.preprocessor import preprocess
from src.model        import train_model, split_data, apply_log_transform, train_final_model, save_model
from src.evaluator    import evaluate
from src.visualizer   import plot_all


# ── Manual override params — fill these in after your first grid search ──────
# These are used when --skip-search is passed.
# Update per source after your first successful run.
MANUAL_PARAMS = {
    "sales": {
        "order":    (1, 1, 1),
        "seasonal": (0, 0, 0, 5),
    },
    "ops_pulse": {
        "order":    (1, 1, 1),
        "seasonal": (0, 0, 0, 4),
    },
    "cash_flow_compass": {
        "order":    (1, 1, 1),
        "seasonal": (0, 0, 0, 4),
    },
    "pipeline_pulse": {
        "order":    (1, 1, 1),
        "seasonal": (0, 0, 0, 4),
    },
    "team_tempo": {
        "order":    (1, 1, 1),
        "seasonal": (0, 0, 0, 4),
    },
}


def run_source(source_name, skip_search=False):
    """
    Execute the full pipeline for one SignalStack source.

    Parameters:
        source_name (str):  Key from SOURCE_REGISTRY.
        skip_search (bool): If True, use MANUAL_PARAMS instead of grid search.
    """
    src = get_source(source_name)
    label = src.get("description", source_name)

    print("\n" + "=" * 64)
    print(f"  SIGNALSTACK PIPELINE — {label.upper()}")
    print(f"  Source:    {source_name}")
    print(f"  Target:    {src['target_column']}")
    print(f"  Frequency: {src['frequency']}")
    print(f"  CSV:       {src['file_path']}")
    print("=" * 64)

    # ── Step 1: Load ──────────────────────────────────────────────────────────
    raw_df, time_series = load_data(src)

    # ── Step 2: Preprocess ───────────────────────────────────────────────────
    cleaned, smoothed = preprocess(time_series, src)

    # ── Step 3: Train ────────────────────────────────────────────────────────
    if skip_search:
        params = MANUAL_PARAMS.get(source_name, {})
        order    = params.get("order",    (1, 1, 1))
        seasonal = params.get("seasonal", (0, 0, 0, src["seasonal_period"]))

        print(f"\n[pipeline] Skip-search mode — using manual params for {source_name}")
        print(f"[pipeline]   order={order}  seasonal={seasonal}")

        train, validation = split_data(smoothed, src)
        if src["log_transform"]:
            train_input, _ = apply_log_transform(train, validation)
        else:
            train_input = train

        fitted = train_final_model(train_input, order, seasonal, src)
        save_model(fitted, src)

        model_results = {
            "model":          fitted,
            "train":          train,
            "validation":     validation,
            "order":          order,
            "seasonal_order": seasonal,
            "aic":            fitted.aic,
            "log_transformed": src["log_transform"],
            "source":         source_name,
        }
    else:
        model_results = train_model(smoothed, src)

    # ── Step 4: Evaluate ─────────────────────────────────────────────────────
    metrics, forecast_df = evaluate(model_results, src)

    # ── Step 5: Visualize ────────────────────────────────────────────────────
    plot_all(time_series, cleaned, smoothed, model_results, forecast_df, src)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 64)
    print(f"  PIPELINE COMPLETE — {label.upper()}")
    print("=" * 64)
    print(f"  Model:     SARIMA{model_results['order']}x{model_results['seasonal_order']}")
    print(f"  AIC:       {model_results['aic']:.4f}")
    print(f"  MAE:       {metrics['MAE']:.2f}")
    print(f"  RMSE:      {metrics['RMSE']:.2f}")
    print(f"  MAPE:      {metrics['MAPE']:.2f}%")
    print(f"  Output:    {src['data_output']}/")
    print(f"  Visuals:   {src['visuals_dir']}/")
    print(f"  Model:     {src['models_dir']}/")
    print("=" * 64 + "\n")

    return metrics, model_results


def main():
    parser = argparse.ArgumentParser(
        description="SignalStack — SARIMA forecasting pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Sources available:
  sales                — Daily revenue (QuickBooks export)
  ops_pulse            — Weekly jobs completed / utilization
  cash_flow_compass    — Weekly cash position / ending balance
  pipeline_pulse       — Weekly pipeline value / close rate
  team_tempo           — Weekly billable hours / OT tracking
  all                  — Run all five sources sequentially

Examples:
  python run_pipeline.py --source sales
  python run_pipeline.py --source ops_pulse --skip-search
  python run_pipeline.py --source all
        """,
    )
    parser.add_argument(
        "--source",
        default="sales",
        help="Source name to run (or 'all' for all sources). Default: sales",
    )
    parser.add_argument(
        "--skip-search",
        action="store_true",
        help="Skip SARIMA grid search. Uses MANUAL_PARAMS in run_pipeline.py.",
    )
    args = parser.parse_args()

    if args.source == "all":
        print("\n[pipeline] Running all SignalStack sources...\n")
        results = {}
        for source_name in SOURCE_REGISTRY:
            try:
                metrics, model_results = run_source(source_name, skip_search=args.skip_search)
                results[source_name] = {"status": "OK", "mape": metrics["MAPE"]}
            except FileNotFoundError as e:
                print(f"\n[pipeline] SKIPPED {source_name} — CSV not found. Drop the export in data/raw/{source_name}/\n")
                results[source_name] = {"status": "SKIPPED — CSV missing"}
            except Exception as e:
                print(f"\n[pipeline] ERROR {source_name}: {e}\n")
                results[source_name] = {"status": f"ERROR: {e}"}

        print("\n" + "=" * 64)
        print("  SIGNALSTACK — ALL SOURCES SUMMARY")
        print("=" * 64)
        for name, res in results.items():
            status = res["status"]
            mape_str = f"  MAPE: {res['mape']:.1f}%" if "mape" in res else ""
            print(f"  {name:<25} {status}{mape_str}")
        print("=" * 64 + "\n")

    else:
        run_source(args.source, skip_search=args.skip_search)


if __name__ == "__main__":
    main()
