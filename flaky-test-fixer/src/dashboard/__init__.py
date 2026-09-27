"""Dashboard — generate an HTML report from flaky-test pipeline results.

Usage (CLI):
    python -m src.dashboard [--flakiness PATH] [--diagnosis PATH] [--output PATH]

Usage (Python):
    from src.dashboard import generate_dashboard
    html_path = generate_dashboard(flakiness_path, diagnosis_path, output_path)
"""

from __future__ import annotations

import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_dashboard(
    flakiness_path: str | Path = "results/flakiness_report.json",
    diagnosis_path: str | Path = "results/diagnosis_report.json",
    output_path: str | Path = "results/dashboard.html",
) -> str:
    """Render an HTML dashboard from pipeline result files.

    Returns the path to the written HTML file.
    """
    flakiness_path = Path(flakiness_path)
    diagnosis_path = Path(diagnosis_path)
    output_path = Path(output_path)

    flakiness: list[dict] = json.loads(flakiness_path.read_text(encoding="utf-8"))
    diagnosis: list[dict] = json.loads(diagnosis_path.read_text(encoding="utf-8"))

    html = _render(flakiness, diagnosis)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render(flakiness: list[dict], diagnosis: list[dict]) -> str:
    diagnosis_by_name = {d["test_name"]: d for d in diagnosis}

    total = len(flakiness)
    flaky_count = sum(1 for t in flakiness if t["classification"] not in ("stable",))
    stable_count = total - flaky_count

    # Category breakdown for diagnosed tests
    category_counts: dict[str, int] = {}
    for d in diagnosis:
        cat = d.get("root_cause_category", "unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    rows_html = _build_rows(flakiness, diagnosis_by_name)
    category_bars_html = _build_category_bars(category_counts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Flaky-Test Dashboard</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
    font-size: 14px;
    line-height: 1.6;
    color: #1f2328;
    background: #ffffff;
    padding: 32px 16px 64px;
  }}
  .page {{ max-width: 820px; margin: 0 auto; }}
  h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
  h2 {{ font-size: 15px; font-weight: 600; margin-bottom: 12px; color: #1f2328; }}
  .subtitle {{ color: #57606a; font-size: 13px; margin-bottom: 32px; }}

  /* Summary cards */
  .cards {{ display: flex; gap: 16px; margin-bottom: 32px; flex-wrap: wrap; }}
  .card {{
    flex: 1; min-width: 140px;
    background: #f7f8fa;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 16px 20px;
  }}
  .card .label {{ font-size: 12px; color: #57606a; text-transform: uppercase; letter-spacing: 0.04em; }}
  .card .value {{ font-size: 28px; font-weight: 700; margin-top: 2px; }}
  .card .value.red {{ color: #cf222e; }}
  .card .value.green {{ color: #1a7f37; }}
  .card .value.blue {{ color: #3b82d4; }}

  /* Hours-lost calculator */
  .calculator {{
    background: #f7f8fa;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 12px;
  }}
  .calc-grid {{ display: flex; gap: 20px; flex-wrap: wrap; align-items: flex-end; margin-bottom: 14px; }}
  .calc-field {{ display: flex; flex-direction: column; gap: 4px; }}
  .calc-field label {{ font-size: 12px; color: #57606a; }}
  .calc-field input[type=number] {{
    width: 80px; padding: 5px 8px;
    border: 1px solid #e5e7eb; border-radius: 5px;
    font-size: 14px; background: #fff;
  }}
  .calc-field input[type=range] {{ width: 160px; accent-color: #3b82d4; cursor: pointer; }}
  .slider-row {{ display: flex; align-items: center; gap: 10px; }}
  .slider-label {{ font-size: 13px; min-width: 52px; color: #1f2328; font-weight: 600; }}
  .result-line {{
    font-size: 20px; font-weight: 700; color: #3b82d4; margin-top: 4px;
  }}
  .result-line span {{ font-size: 13px; font-weight: 400; color: #57606a; margin-left: 8px; }}
  .footnote {{
    font-size: 11.5px; color: #57606a; margin-top: 8px;
    border-top: 1px solid #e5e7eb; padding-top: 8px;
    line-height: 1.55;
  }}

  /* Info box */
  .infobox {{
    background: #f7f8fa;
    border-left: 3px solid #3b82d4;
    border-radius: 0 8px 8px 0;
    padding: 16px 20px;
    margin-bottom: 32px;
    font-size: 13px;
    color: #1f2328;
  }}
  .infobox h3 {{ font-size: 13px; font-weight: 600; margin-bottom: 6px; }}
  .infobox ul {{ padding-left: 18px; }}
  .infobox li {{ margin-bottom: 4px; }}
  .infobox .muted {{ color: #57606a; font-size: 12px; margin-top: 8px; }}

  /* Category breakdown */
  .section {{ margin-bottom: 32px; }}
  .bar-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }}
  .bar-label {{ width: 140px; font-size: 13px; color: #1f2328; text-align: right; flex-shrink: 0; }}
  .bar-track {{ flex: 1; background: #e5e7eb; border-radius: 4px; height: 14px; }}
  .bar-fill {{ height: 14px; border-radius: 4px; background: #3b82d4; }}
  .bar-fill.timing {{ background: #cf222e; }}
  .bar-fill.shared_state {{ background: #7c5cd8; }}
  .bar-fill.race_condition {{ background: #e36209; }}
  .bar-fill.external_call {{ background: #1a7f37; }}
  .bar-count {{ width: 32px; font-size: 12px; color: #57606a; }}

  /* Test table */
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  thead th {{
    text-align: left; padding: 8px 10px;
    background: #f7f8fa; border-bottom: 1px solid #e5e7eb;
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; color: #57606a;
  }}
  tbody tr:hover {{ background: #f7f8fa; }}
  td {{ padding: 9px 10px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }}
  .badge {{
    display: inline-block; padding: 2px 8px; border-radius: 10px;
    font-size: 11px; font-weight: 600; white-space: nowrap;
  }}
  .badge.flaky {{ background: #ffebe9; color: #cf222e; }}
  .badge.stable {{ background: #dafbe1; color: #1a7f37; }}
  .badge.suspected_order_dependent {{ background: #fff8c5; color: #7d4e00; }}
  .badge.broken {{ background: #f3e8ff; color: #7c5cd8; }}
  .cat-badge {{
    display: inline-block; padding: 2px 7px; border-radius: 10px;
    font-size: 11px; font-weight: 500; background: #e5e7eb; color: #1f2328;
    white-space: nowrap;
  }}
  .cat-badge.timing {{ background: #ffebe9; color: #cf222e; }}
  .cat-badge.shared_state {{ background: #f3e8ff; color: #7c5cd8; }}
  .cat-badge.race_condition {{ background: #fff3e0; color: #e36209; }}
  .cat-badge.external_call {{ background: #dafbe1; color: #1a7f37; }}
  .pass-bar {{ display: flex; align-items: center; gap: 6px; }}
  .pass-track {{ width: 60px; height: 6px; background: #e5e7eb; border-radius: 3px; }}
  .pass-fill {{ height: 6px; border-radius: 3px; background: #1a7f37; }}
  .confidence {{ font-size: 11px; color: #57606a; }}

  footer {{
    margin-top: 48px; border-top: 1px solid #e5e7eb; padding-top: 12px;
    text-align: center; font-size: 12px; color: #57606a;
  }}
</style>
</head>
<body>
<div class="page">

  <h1>Flaky-Test Dashboard</h1>
  <p class="subtitle">Pipeline results — {total} tests analysed</p>

  <!-- Summary cards -->
  <div class="cards">
    <div class="card">
      <div class="label">Total Tests</div>
      <div class="value blue">{total}</div>
    </div>
    <div class="card">
      <div class="label">Flaky / Suspected</div>
      <div class="value red">{flaky_count}</div>
    </div>
    <div class="card">
      <div class="label">Stable</div>
      <div class="value green">{stable_count}</div>
    </div>
    <div class="card">
      <div class="label">Diagnosed</div>
      <div class="value blue">{len(diagnosis)}</div>
    </div>
  </div>

  <!-- Hours-lost calculator -->
  <div class="section">
    <h2>Hours Lost per Week</h2>
    <div class="calculator">
      <div class="calc-grid">
        <div class="calc-field">
          <label for="inp-flaky">Flaky tests</label>
          <input type="number" id="inp-flaky" min="0" value="{flaky_count}">
        </div>
        <div class="calc-field">
          <label for="inp-ci">CI runs / day</label>
          <input type="number" id="inp-ci" min="1" value="10">
        </div>
        <div class="calc-field">
          <label>Investigation time</label>
          <div class="slider-row">
            <input type="range" id="inp-inv" min="10" max="30" value="20"
                   oninput="document.getElementById('inv-val').textContent=this.value+' min';recalc()">
            <span class="slider-label" id="inv-val">20 min</span>
          </div>
        </div>
      </div>
      <div class="result-line" id="hours-result">&#8212;</div>
      <p class="footnote">
        <strong>Formula:</strong>
        hours_lost_per_week = flaky_tests &times; ci_runs_per_day &times; 7 &times; (investigation_minutes &divide; 60)<br>
        <strong>Research basis:</strong>
        Estimate based on published industry research showing flaky-test investigation
        time averages 15&ndash;30 minutes per failure, and that flaky tests consume roughly
        2.5% of total engineering time in studied organisations
        (Leinen&nbsp;et&nbsp;al., <em>ICST&nbsp;2024</em>).
        The default 20-minute midpoint sits between the 15&ndash;23&nbsp;min range
        reported across multiple studies and the 30-minute figure from practitioner
        surveys. Adjust the slider to match your team&rsquo;s experience.
      </p>
    </div>
  </div>

  <!-- Research info box -->
  <div class="infobox">
    <h3>How Our Diagnosis Categories Map to Real-World Research</h3>
    <ul>
      <li><strong>Timing &amp; concurrency issues</strong> are consistently the single
          largest root-cause category in large-scale studies of flaky tests in
          production CI systems — prominently reported in Google&rsquo;s CI research
          and subsequent academic replications. These tests fail non-deterministically
          because their assertions depend on wall-clock time, execution order, or
          thread scheduling that cannot be controlled by the test author.</li>
      <li><strong>Shared-state &amp; order-dependency issues</strong> are the second
          most common category. They arise when module-level mutable state, unseeded
          random number generators, or improperly scoped fixtures bleed between test
          runs, making results dependent on which tests ran previously.</li>
    </ul>
    <p class="muted">
      Together, timing/concurrency and shared-state/order-dependency account for the
      majority of flaky failures observed in large open-source and industrial test
      suites. This is precisely why this tool targets those two categories first,
      alongside race conditions and unmocked external calls.
    </p>
  </div>

  <!-- Root-cause breakdown -->
  <div class="section">
    <h2>Root-Cause Breakdown</h2>
    {category_bars_html}
  </div>

  <!-- Test results table -->
  <div class="section">
    <h2>Test Results</h2>
    <table>
      <thead>
        <tr>
          <th>Test</th>
          <th>Status</th>
          <th>Pass Rate</th>
          <th>Root Cause</th>
          <th>Confidence</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>

</div>

<script>
function recalc() {{
  var f = parseFloat(document.getElementById('inp-flaky').value) || 0;
  var c = parseFloat(document.getElementById('inp-ci').value) || 0;
  var m = parseFloat(document.getElementById('inp-inv').value) || 20;
  var h = f * c * 7 * (m / 60);
  var el = document.getElementById('hours-result');
  el.innerHTML = h.toFixed(1) + ' hrs / week <span>across team</span>';
}}
document.getElementById('inp-flaky').addEventListener('input', recalc);
document.getElementById('inp-ci').addEventListener('input', recalc);
recalc();
</script>

<footer>Made with IBM Bob</footer>
</body>
</html>"""


def _build_rows(flakiness: list[dict], diagnosis_by_name: dict[str, dict]) -> str:
    parts = []
    for t in sorted(flakiness, key=lambda x: (x["classification"] == "stable", x["test_name"])):
        name = t["test_name"]
        short_name = name.split("::")[-1] if "::" in name else name
        cls = t["classification"]
        pass_rate = t.get("pass_rate", 1.0)
        pct = int(pass_rate * 100)
        diag = diagnosis_by_name.get(name)
        if diag:
            cat = diag.get("root_cause_category", "—")
            conf = diag.get("confidence", 0.0)
            cat_cell = f'<span class="cat-badge {cat}">{cat.replace("_", " ")}</span>'
            conf_cell = f'<span class="confidence">{int(conf * 100)}%</span>'
        else:
            cat_cell = '<span style="color:#57606a">—</span>'
            conf_cell = '<span style="color:#57606a">—</span>'

        parts.append(f"""
        <tr>
          <td style="font-family:monospace;font-size:12px">{short_name}</td>
          <td><span class="badge {cls}">{cls.replace("_", " ")}</span></td>
          <td>
            <div class="pass-bar">
              <div class="pass-track"><div class="pass-fill" style="width:{pct}%"></div></div>
              <span style="font-size:12px;color:#57606a">{pct}%</span>
            </div>
          </td>
          <td>{cat_cell}</td>
          <td>{conf_cell}</td>
        </tr>""")
    return "\n".join(parts)


def _build_category_bars(category_counts: dict[str, int]) -> str:
    if not category_counts:
        return '<p style="color:#57606a;font-size:13px">No diagnoses available.</p>'
    max_count = max(category_counts.values())
    all_cats = ["timing", "shared_state", "race_condition", "external_call"]
    parts = []
    for cat in all_cats:
        count = category_counts.get(cat, 0)
        width_pct = int(count / max_count * 100) if max_count else 0
        label = cat.replace("_", " ").title()
        parts.append(f"""
    <div class="bar-row">
      <div class="bar-label">{label}</div>
      <div class="bar-track"><div class="bar-fill {cat}" style="width:{width_pct}%"></div></div>
      <div class="bar-count">{count}</div>
    </div>""")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    _ROOT = Path(__file__).parent.parent.parent  # flaky-test-fixer/

    parser = argparse.ArgumentParser(description="Generate flaky-test HTML dashboard")
    parser.add_argument("--flakiness", default=str(_ROOT / "results/flakiness_report.json"))
    parser.add_argument("--diagnosis", default=str(_ROOT / "results/diagnosis_report.json"))
    parser.add_argument("--output", default=str(_ROOT / "results/dashboard.html"))
    args = parser.parse_args()

    out = generate_dashboard(args.flakiness, args.diagnosis, args.output)
    print(f"Dashboard written to: {out}")
