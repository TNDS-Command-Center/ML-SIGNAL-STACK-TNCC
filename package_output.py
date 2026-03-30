"""
package_output.py — SignalStack: Desktop ZIP + HTML Delivery Package.
=====================================================================
After a full pipeline run, run this script once to produce a single ZIP
file on the Windows Desktop containing everything a reviewer needs, plus
a standalone HTML report they can open with one click. The Word .docx is
also included for stakeholder email distribution.

Execution order:
    1. python export_to_csv.py
    2. python run_pipeline.py --source all
    3. python generate_report.py
    4. python package_output.py

After step 4 the Desktop ZIP is ready. The reviewer opens the HTML for
the full briefing or emails the .docx to stakeholders.

Usage:
    python package_output.py                    # packages latest report + all sources
    python package_output.py --source sales     # single source charts only (still full HTML)
    python package_output.py --no-code          # omit the code/ folder from ZIP
"""

import argparse
import base64
import datetime
import io
import zipfile
from pathlib import Path

from generate_report import (
    SOURCES, SOURCE_META, ACCURACY_BANDS, GLOSSARY,
    load_metrics, accuracy_label,
    narrate_ensemble, narrate_numbers, narrate_chart, narrate_decision,
    narrate_signal_profile,
)

# ── Config ───────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent

NAVY = "#1a3a5c"
TEAL = "#3d8eb9"

EXCEL_FILES = [
    "tnds-sales-data-template.xlsx",
    "SignalStack_OpsPulse.xlsx",
    "SignalStack_CashFlowCompass.xlsx",
    "SignalStack_PipelinePulse.xlsx",
    "SignalStack_TeamTempo.xlsx",
]

CODE_FILES = [
    "run_pipeline.py",
    "export_to_csv.py",
    "generate_report.py",
    "package_output.py",
    "config.py",
]

SRC_FILES = [
    "src/accuracy_log.py",
    "src/data_loader.py",
    "src/evaluator.py",
    "src/model.py",
    "src/preprocessor.py",
    "src/visualizer.py",
    "src/__init__.py",
]

CHART_NAMES = [
    ("01_raw_time_series.png",    "Raw Time Series"),
    ("02_decomposition.png",      "Seasonal Decomposition"),
    ("03_preprocessing.png",      "Preprocessing & Smoothing"),
    ("04_forecast_vs_actual.png", "Forecast vs Actual"),
    ("05_residuals.png",          "Residual Analysis"),
    ("06_extended_forecast.png",  "Extended Forecast"),
]

# ── Helpers ──────────────────────────────────────────────────────────────────

def accuracy_hex(mape):
    """Return hex color for MAPE-based accuracy tier."""
    if mape <= 10:
        return "#3b6d11"
    if mape <= 20:
        return "#854f0b"
    return "#a32d2d"


def img_to_b64(path):
    """Convert a PNG file to a base64 data-URI string."""
    data = Path(path).read_bytes()
    return f"data:image/png;base64,{base64.b64encode(data).decode('ascii')}"


def find_latest_docx():
    """Return the most recently modified .docx in reports/, or None."""
    reports = BASE_DIR / "reports"
    if not reports.exists():
        return None
    docs = sorted(reports.glob("*.docx"), key=lambda p: p.stat().st_mtime, reverse=True)
    return docs[0] if docs else None


def esc(text):
    """Escape HTML special characters."""
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


# ── HTML Builder ─────────────────────────────────────────────────────────────

def build_html():
    """Build a self-contained HTML report string covering all sources."""
    today = datetime.date.today()
    iso_week = today.strftime("%G-W%V")
    date_str = today.strftime("%B %d, %Y")

    all_metrics = {}
    for src in SOURCES:
        m = load_metrics(src)
        if m:
            all_metrics[src] = m

    # ── CSS ──────────────────────────────────────────────────────────────
    css = """
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#222;background:#fff;line-height:1.55}
        .header{background:#1a3a5c;padding:28px 40px;margin-bottom:30px}
        .header h1{color:#fff;font-size:28px;font-weight:bold;margin:0}
        .header .subtitle{color:#3d8eb9;font-size:14px;margin-top:4px}
        .header .date{color:#999;font-size:11px;margin-top:6px}
        .container{max-width:960px;margin:0 auto;padding:0 30px 40px}
        h2{color:#3d8eb9;font-size:20px;margin:32px 0 8px;border-bottom:2px solid #3d8eb9;padding-bottom:6px}
        h3{color:#1a3a5c;font-size:16px;margin:20px 0 10px}
        p{margin:8px 0}
        table{border-collapse:collapse;width:100%;margin:12px 0}
        th{background:#1a3a5c;color:#fff;padding:8px 12px;font-size:13px;text-align:center}
        td{padding:8px 12px;border:1px solid #ddd;font-size:13px;text-align:center}
        tr:nth-child(even) td{background:#f0f6fa}
        .narrative{margin:10px 0;font-size:13.5px;color:#333}
        .accuracy-label{font-style:italic;font-size:13px;margin:8px 0}
        .decision{font-weight:bold;font-size:13px;margin:10px 0 16px}
        .decision .lbl{color:#1a3a5c}
        .chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:18px 0}
        .chart-grid .full-width{grid-column:1/-1}
        .chart-grid img{width:100%;border:1px solid #e0e0e0;border-radius:4px}
        .caption{text-align:center;font-size:11px;color:#888;font-style:italic;margin-top:4px}
        .glossary-item{margin:8px 0;padding-left:12px}
        .glossary-item .term{font-weight:bold;color:#1a3a5c}
        .footer{text-align:center;color:#aaa;font-size:11px;padding:30px 0 20px;border-top:1px solid #ddd;margin-top:30px}
        .placeholder{color:#888;font-style:italic;padding:16px;background:#f9f9f9;border:1px dashed #ccc;margin:12px 0}
        @media print{.header{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
    """

    # ── Executive summary rows ───────────────────────────────────────────
    summary_rows = ""
    for src in SOURCES:
        m = all_metrics.get(src)
        if not m:
            continue
        meta = SOURCE_META[src]
        mape = float(m.get("MAPE", 0))
        mae = float(m.get("MAE", 0))
        model = str(m.get("Model", ""))
        unit = meta["unit"]
        color = accuracy_hex(mape)
        alabel = accuracy_label(mape).split("\u2009")[0].split(" \u2014 ")[0]  # before em-dash
        mae_str = f"${mae:,.0f}" if unit == "$" else f"{mae:.1f} {unit}"
        summary_rows += (
            f'<tr>'
            f'<td style="text-align:left;font-weight:bold;">{esc(meta["label"])}</td>'
            f'<td>{esc(model.replace("SARIMA", "").strip())}</td>'
            f'<td style="color:{color};font-weight:bold;">{mape:.1f}%</td>'
            f'<td>{mae_str}</td>'
            f'<td style="color:{color};">{esc(alabel)}</td>'
            f'</tr>\n'
        )

    # ── Per-source sections ──────────────────────────────────────────────
    source_html = ""
    for src in SOURCES:
        m = all_metrics.get(src)
        meta = SOURCE_META[src]

        if not m:
            source_html += (
                f'<h2>{esc(meta["label"])}</h2>\n'
                f'<div class="placeholder">Run pipeline for this source first.</div>\n'
            )
            continue

        mape = float(m.get("MAPE", 0))
        mae = float(m.get("MAE", 0))
        rmse = float(m.get("RMSE", 0))
        model = str(m.get("Model", ""))
        unit = meta["unit"]
        freq = str(m.get("Frequency", ""))
        color = accuracy_hex(mape)

        mae_str = f"${mae:,.0f}" if unit == "$" else f"{mae:.1f}"
        rmse_str = f"${rmse:,.0f}" if unit == "$" else f"{rmse:.1f}"

        # Narrative paragraphs (same logic as Word report)
        p1 = accuracy_label(mape)
        p2 = narrate_ensemble(src, model, freq)
        p3 = narrate_numbers(m, meta)
        p4 = narrate_chart(meta["label"])
        p5 = narrate_decision(mape, unit, mae)
        p6 = narrate_signal_profile(src, meta)

        # Charts — 2-column grid, 05 full width
        chart_blocks = ""
        vis_dir = BASE_DIR / "visuals" / src
        for idx, (fname, caption) in enumerate(CHART_NAMES):
            cp = vis_dir / fname
            fw = ' class="full-width"' if idx >= 4 else ""
            if cp.exists():
                b64 = img_to_b64(cp)
                chart_blocks += (
                    f'<div{fw}><img src="{b64}" alt="{caption}">'
                    f'<div class="caption">{caption}</div></div>\n'
                )
            else:
                chart_blocks += (
                    f'<div{fw}><div class="placeholder">[Chart not available: {fname}]</div>'
                    f'<div class="caption">{caption}</div></div>\n'
                )

        source_html += (
            f'<h2>{esc(meta["label"])}</h2>\n'
            f'<table>'
            f'<tr><th>Model</th><th>MAPE</th><th>MAE</th><th>RMSE</th></tr>'
            f'<tr><td>{esc(model)}</td>'
            f'<td style="color:{color};font-weight:bold;">{mape:.1f}%</td>'
            f'<td>{mae_str}</td><td>{rmse_str}</td></tr>'
            f'</table>\n'
            f'<p class="accuracy-label" style="color:{color};">{esc(p1)}</p>\n'
            f'<p class="narrative">{esc(p2)}</p>\n'
            f'<p class="narrative">{esc(p3)}</p>\n'
            f'<p class="narrative">{esc(p4)}</p>\n'
            f'<p class="decision"><span class="lbl">Decision Guidance: </span>'
            f'<span style="color:{color};">{esc(p5)}</span></p>\n'
            + (f'<p class="narrative" style="color:#1a3a5c;"><strong>Signal Profile:</strong> {esc(p6)}</p>\n' if p6 else '')
            + f'<div class="chart-grid">\n{chart_blocks}</div>\n'
        )

    # ── Glossary ─────────────────────────────────────────────────────────
    glossary_html = ""
    for term, defn in GLOSSARY:
        glossary_html += (
            f'<div class="glossary-item">'
            f'<span class="term">{esc(term)}</span> &mdash; {esc(defn)}'
            f'</div>\n'
        )

    # ── Assemble ─────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SignalStack &mdash; Business Intelligence Forecast Report</title>
<style>{css}</style>
</head>
<body>

<div class="header">
  <h1>SIGNALSTACK</h1>
  <div class="subtitle">Business Intelligence Forecast Report</div>
  <div class="date">Generated: {date_str} &nbsp;|&nbsp; Week: {iso_week}</div>
</div>

<div class="container">

<h2>Executive Summary</h2>
<p>This report summarizes the latest SignalStack forecasting results across all active
business signals. Each model was trained on historical data and validated against a
held-out period before generating forward projections. Use MAPE as the primary accuracy
indicator &mdash; under 10% is considered strong for small-business operational data.</p>
<table>
<tr><th>Signal</th><th>Model</th><th>MAPE</th><th>MAE</th><th>Accuracy Assessment</th></tr>
{summary_rows}
</table>

<h2>Glossary of Terms</h2>
{glossary_html}

{source_html}

</div>

<div class="footer">
  SignalStack by True North Data Strategies &nbsp;|&nbsp; jacob@truenorthstrategyops.com &nbsp;|&nbsp;
  719-204-6365 &nbsp;|&nbsp; Colorado Springs, CO &nbsp;|&nbsp; SDVOSB
</div>

</body>
</html>"""

    return html


# ── ZIP Builder ──────────────────────────────────────────────────────────────

def build_zip(chart_sources, html_str, include_code=True):
    """Assemble the delivery ZIP in memory and return bytes."""
    today = datetime.date.today()
    iso_week = today.strftime("%G-W%V")
    root = f"SignalStack_Delivery_{iso_week}"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:

        # ── Word report (latest from reports/) ──
        docx_path = find_latest_docx()
        if docx_path:
            zf.write(str(docx_path), f"{root}/SignalStack_Report_{iso_week}.docx")
        else:
            print("[package] Warning: no .docx found in reports/ — run generate_report.py first")

        # ── HTML report ──
        zf.writestr(f"{root}/SignalStack_Report_{iso_week}.html", html_str)

        # ── Excel source files ──
        for xls in EXCEL_FILES:
            p = BASE_DIR / xls
            if p.exists():
                zf.write(str(p), f"{root}/excel/{xls}")
            else:
                print(f"[package] Warning: missing excel file {xls}")

        # ── Charts (filtered by --source) ──
        for src in chart_sources:
            vis_dir = BASE_DIR / "visuals" / src
            for fname, _ in CHART_NAMES:
                cp = vis_dir / fname
                if cp.exists():
                    zf.write(str(cp), f"{root}/charts/{src}/{fname}")
                else:
                    print(f"[package] Warning: missing chart {cp}")

        # ── Code ──
        if include_code:
            for cf in CODE_FILES:
                p = BASE_DIR / cf
                if p.exists():
                    zf.write(str(p), f"{root}/code/{cf}")
            for sf in SRC_FILES:
                p = BASE_DIR / sf
                if p.exists():
                    zf.write(str(p), f"{root}/code/{sf}")

    return buf.getvalue()


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="SignalStack — Package delivery ZIP with HTML report for Desktop.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python package_output.py
  python package_output.py --source sales
  python package_output.py --no-code
        """,
    )
    parser.add_argument(
        "--source",
        nargs="+",
        default=SOURCES,
        choices=SOURCES,
        help="Sources to include charts for in the ZIP. Default: all five.",
    )
    parser.add_argument(
        "--no-code",
        action="store_true",
        help="Omit the code/ folder from the ZIP.",
    )
    args = parser.parse_args()

    print("[package] Building SignalStack delivery package...")

    # HTML always covers all sources (charts embedded as base64)
    html_str = build_html()

    # ZIP charts filtered by --source
    zip_bytes = build_zip(args.source, html_str, include_code=not args.no_code)

    # Write to Desktop
    today = datetime.date.today()
    iso_week = today.strftime("%G-W%V")
    desktop = Path.home() / "Desktop"
    zip_path = desktop / f"SignalStack_Delivery_{iso_week}.zip"
    zip_path.write_bytes(zip_bytes)

    # Summary
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        file_count = len(zf.namelist())
    size_mb = len(zip_bytes) / (1024 * 1024)

    print(f"[package] Delivered: {zip_path}")
    print(f"[package] Contents: {file_count} files, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
