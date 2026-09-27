"""Gleipnir -- Streamlit dashboard.

Run with:
    streamlit run src/dashboard/app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent.parent.resolve()
_RESULTS = _ROOT / "results"

_RUN_PATH       = _RESULTS / "run_results.json"
_FLAKINESS_PATH = _RESULTS / "flakiness_report.json"
_DIAGNOSIS_PATH = _RESULTS / "diagnosis_report.json"

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Gleipnir",
    page_icon=":chains:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Minimal custom CSS  (no em-dashes, no generic branding)
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }

    /* page background */
    .stApp { background-color: #0f1117; }

    /* tighten the default Streamlit top padding */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1200px;
    }

    /* ---- header strip ---- */
    .gleipnir-header {
        background: linear-gradient(135deg, #1a1d27 0%, #161922 100%);
        border: 1px solid #2a2d3a;
        border-left: 4px solid #4f8ef7;
        border-radius: 0 10px 10px 0;
        padding: 1.2rem 1.5rem;
        margin-bottom: 2rem;
    }
    .gleipnir-header h1 {
        font-size: 1.9rem;
        font-weight: 700;
        letter-spacing: -0.03em;
        color: #e8eaf0;
        margin: 0;
    }
    .gleipnir-header p {
        color: #8b92a8;
        font-size: 0.85rem;
        margin: 0.3rem 0 0;
        letter-spacing: 0.01em;
    }

    /* ---- section headings ---- */
    .section-heading {
        font-size: 0.78rem;
        font-weight: 600;
        color: #4f8ef7;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        border-bottom: 1px solid #2a2d3a;
        padding-bottom: 0.4rem;
        margin-bottom: 1rem;
    }

    /* ---- hours-lost callout ---- */
    .hours-callout {
        background: #1a1d27;
        border: 1px solid #2a2d3a;
        border-left: 4px solid #4f8ef7;
        border-radius: 0 10px 10px 0;
        padding: 1rem 1.4rem;
        font-size: 1.75rem;
        font-weight: 700;
        color: #4f8ef7;
        margin-top: 0.5rem;
    }
    .hours-callout span {
        display: block;
        font-size: 0.78rem;
        font-weight: 400;
        color: #8b92a8;
        margin-top: 0.15rem;
        letter-spacing: 0.02em;
        text-transform: uppercase;
    }

    /* ---- metric cards ---- */
    [data-testid="metric-container"] {
        background: #1a1d27;
        border: 1px solid #2a2d3a;
        border-radius: 10px;
        padding: 1rem 1.25rem;
    }
    [data-testid="metric-container"] label {
        color: #8b92a8 !important;
        font-size: 0.78rem !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #e8eaf0 !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
    }

    /* ---- divider ---- */
    hr { border-color: #2a2d3a !important; }

    /* ---- expanders ---- */
    [data-testid="stExpander"] {
        background: #1a1d27;
        border: 1px solid #2a2d3a !important;
        border-radius: 8px;
        margin-bottom: 0.5rem;
    }
    [data-testid="stExpander"] summary {
        color: #c9cdd8 !important;
        font-weight: 500;
        font-size: 0.9rem;
    }

    /* ---- dataframe ---- */
    [data-testid="stDataFrame"] {
        border: 1px solid #2a2d3a;
        border-radius: 8px;
        overflow: hidden;
    }

    /* ---- sliders ---- */
    [data-testid="stSlider"] label { color: #c9cdd8 !important; font-size: 0.85rem !important; }

    /* ---- info boxes ---- */
    .stAlert { background: #1a1d27 !important; border: 1px solid #2a2d3a !important; border-radius: 8px !important; }

    /* ---- badge pills ---- */
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.03em;
        white-space: nowrap;
    }
    .badge-flaky                     { background: #2d1a1e; color: #f87171; border: 1px solid #7f1d1d; }
    .badge-stable                    { background: #1a2d1e; color: #4ade80; border: 1px solid #14532d; }
    .badge-suspected_order_dependent { background: #2d2a1a; color: #fbbf24; border: 1px solid #78350f; }
    .badge-broken                    { background: #251a2d; color: #c084fc; border: 1px solid #581c87; }
    .badge-timing                    { background: #2d1a1e; color: #f87171; border: 1px solid #7f1d1d; }
    .badge-shared_state              { background: #251a2d; color: #c084fc; border: 1px solid #581c87; }
    .badge-race_condition            { background: #2d221a; color: #fb923c; border: 1px solid #7c2d12; }
    .badge-external_call             { background: #1a2d1e; color: #4ade80; border: 1px solid #14532d; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


flakiness  = _load(_FLAKINESS_PATH)
diagnosis  = _load(_DIAGNOSIS_PATH)
run_records = _load(_RUN_PATH)

diag_by_name: dict[str, dict] = {d["test_name"]: d for d in diagnosis}

total       = len(flakiness)
flaky_count = sum(1 for t in flakiness if t["classification"] != "stable")
stable_count = total - flaky_count
diag_count  = len(diagnosis)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    f"""
    <div class="gleipnir-header">
        <h1>Gleipnir</h1>
        <p>Flaky test detection and root-cause diagnosis &nbsp;|&nbsp; {total} tests analysed</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Tests",      total)
c2.metric("Flaky / Suspected", flaky_count,  delta=None)
c3.metric("Stable",           stable_count, delta=None)
c4.metric("Diagnosed",        diag_count,   delta=None)

st.divider()

# ---------------------------------------------------------------------------
# Hours-lost calculator
# ---------------------------------------------------------------------------

st.markdown('<div class="section-heading">Hours Lost per Week</div>', unsafe_allow_html=True)

col_sliders, col_result = st.columns([2, 1], gap="large")

with col_sliders:
    ci_runs = st.slider(
        "CI runs per day",
        min_value=5, max_value=30, value=10, step=1,
    )
    inv_min = st.slider(
        "Investigation time per failure (minutes)",
        min_value=10, max_value=30, value=20, step=1,
    )

hours_lost = flaky_count * ci_runs * 7 * (inv_min / 60)

with col_result:
    st.markdown(
        f'<div class="hours-callout">'
        f'{hours_lost:.1f} hrs / week'
        f'<span>estimated across team</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.caption(
    "**Formula:** hours = flaky_tests x ci_runs_per_day x 7 x (investigation_min / 60)  |  "
    "**Research basis:** Flaky-test investigation averages 15-30 min per failure; "
    "flaky tests consume roughly 2.5% of total engineering time in studied organisations "
    "(Leinen et al., ICST 2024). The 20-minute default is the midpoint of the "
    "15-23 min range reported across multiple studies. Adjust the slider to match your team."
)

st.divider()

# ---------------------------------------------------------------------------
# Root-cause breakdown bar chart
# ---------------------------------------------------------------------------

if diagnosis:
    st.markdown('<div class="section-heading">Root-Cause Breakdown</div>', unsafe_allow_html=True)

    all_cats = ["timing", "shared_state", "race_condition", "external_call"]
    cat_counts = {c: 0 for c in all_cats}
    for d in diagnosis:
        cat = d.get("root_cause_category", "")
        if cat in cat_counts:
            cat_counts[cat] += 1

    chart_df = pd.DataFrame(
        {"count": list(cat_counts.values())},
        index=[c.replace("_", " ").title() for c in cat_counts],
    )
    st.bar_chart(chart_df, y="count", height=220)

    st.divider()

# ---------------------------------------------------------------------------
# Test results table
# ---------------------------------------------------------------------------

st.markdown('<div class="section-heading">Test Results</div>', unsafe_allow_html=True)

_FIX_SUGGESTIONS: dict[str, str] = {
    "timing":       "Replace wall-clock assertions with deterministic mocks (freezegun, unittest.mock.patch).",
    "shared_state": "Reset module-level state in a fixture with autouse=True, or seed the PRNG explicitly.",
    "race_condition": "Add synchronisation (threading.Event, asyncio.Lock) or mock concurrent primitives.",
    "external_call": "Mock external calls with pytest-httpx, responses, or unittest.mock.",
}

rows = []
for t in sorted(flakiness, key=lambda x: (x["classification"] == "stable", x["test_name"])):
    name = t["test_name"]
    short = name.split("::")[-1] if "::" in name else name
    cls   = t["classification"]
    rate  = t.get("pass_rate", 1.0)
    d     = diag_by_name.get(name)
    cat   = d["root_cause_category"] if d else ""
    conf  = f'{int(d["confidence"] * 100)}%' if d else ""
    fix   = _FIX_SUGGESTIONS.get(cat, "") if d else ""
    rows.append({
        "Test":        short,
        "Status":      cls,
        "Pass Rate":   f"{int(rate * 100)}%",
        "Root Cause":  cat.replace("_", " ") if cat else "",
        "Confidence":  conf,
        "Fix Hint":    fix,
    })

df = pd.DataFrame(rows)

# Color-code rows: flaky rows get a light red background via pandas Styler
def _row_style(row: pd.Series):
    cls_val = row["Status"]
    if cls_val in ("flaky", "suspected_order_dependent"):
        return ["background-color: #fff5f5"] * len(row)
    if cls_val == "broken":
        return ["background-color: #faf0ff"] * len(row)
    return [""] * len(row)

styled = (
    df.style
    .apply(_row_style, axis=1)
    .set_properties(**{"font-size": "0.82rem"})
    .hide(axis="index")
)

st.dataframe(styled, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Per-test expandable detail
# ---------------------------------------------------------------------------

flaky_tests = [t for t in flakiness if t["classification"] != "stable"]

if flaky_tests:
    st.markdown('<div class="section-heading">Per-Test Diagnosis Detail</div>', unsafe_allow_html=True)

    for t in sorted(flaky_tests, key=lambda x: x["test_name"]):
        name  = t["test_name"]
        short = name.split("::")[-1] if "::" in name else name
        cls   = t["classification"]
        d     = diag_by_name.get(name)

        label = f"{short}  [{cls.replace('_', ' ')}]"
        with st.expander(label, expanded=False):
            meta_col, fix_col = st.columns([1, 1], gap="medium")
            with meta_col:
                st.markdown(f"**Full test ID:** `{name}`")
                st.markdown(f"**Classification:** `{cls}`")
                st.markdown(f"**Pass rate:** {int(t.get('pass_rate', 1.0) * 100)}%")
                if d:
                    cat  = d.get("root_cause_category", "")
                    conf = d.get("confidence", 0.0)
                    st.markdown(f"**Root cause:** `{cat}`")
                    st.markdown(f"**Confidence:** {int(conf * 100)}%")
            with fix_col:
                if d:
                    cat = d.get("root_cause_category", "")
                    fix = _FIX_SUGGESTIONS.get(cat, "")
                    if fix:
                        st.info(f"**Fix hint:** {fix}")

            if d:
                st.markdown("**Explanation**")
                st.markdown(d.get("explanation", ""))
                st.markdown("**Reasoning trace**")
                st.code(d.get("reasoning_trace", ""), language=None)

st.divider()

# ---------------------------------------------------------------------------
# Research context
# ---------------------------------------------------------------------------

with st.expander("How the diagnosis categories map to real-world research", expanded=False):
    st.markdown(
        """
**Timing and concurrency** are consistently the single largest root-cause category
in large-scale studies of flaky tests in production CI systems, prominently
reported in Google's CI research and subsequent academic replications.
These tests fail non-deterministically because their assertions depend on
wall-clock time, execution order, or thread scheduling that the test author
cannot control.

**Shared state and order dependency** is the second most common category.
It arises when module-level mutable state, unseeded random number generators,
or improperly scoped fixtures bleed between test runs, making results depend
on which tests ran previously.

Together these two categories account for the majority of flaky failures
observed in large open-source and industrial test suites. That is why Gleipnir
targets them first, alongside race conditions and unmocked external calls.
        """
    )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown(
    "<p style='text-align:center; color:#57606a; font-size:0.75rem; margin-top:2rem;'>"
    "Gleipnir &nbsp;|&nbsp; Made with IBM Bob"
    "</p>",
    unsafe_allow_html=True,
)
