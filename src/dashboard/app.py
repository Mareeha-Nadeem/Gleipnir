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
# Custom CSS  — clean, modern, white/light SaaS theme
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        color: #111827;
    }

    /* ---- page background ---- */
    .stApp { background-color: #F4F8FC; }

    /* ---- main content container ---- */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1200px;
    }

    /* ---- header strip ---- */
    .gleipnir-header {
        background: linear-gradient(135deg, #163B70 0%, #1e4d96 100%);
        border-radius: 14px;
        padding: 1.6rem 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(22, 59, 112, 0.18);
    }
    .gleipnir-header h1 {
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        color: #ffffff;
        margin: 0;
    }
    .gleipnir-header p {
        color: #bfdbfe;
        font-size: 0.9rem;
        margin: 0.35rem 0 0;
        letter-spacing: 0.01em;
    }

    /* ---- section headings ---- */
    .section-heading {
        font-size: 0.72rem;
        font-weight: 700;
        color: #2563EB;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        border-bottom: 2px solid #e5e7eb;
        padding-bottom: 0.45rem;
        margin-bottom: 1rem;
    }

    /* ---- hours-lost callout ---- */
    .hours-callout {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-left: 5px solid #2563EB;
        border-radius: 0 12px 12px 0;
        padding: 1.2rem 1.6rem;
        font-size: 2rem;
        font-weight: 800;
        color: #2563EB;
        margin-top: 0.5rem;
        box-shadow: 0 2px 8px rgba(37, 99, 235, 0.08);
    }
    .hours-callout span {
        display: block;
        font-size: 0.75rem;
        font-weight: 500;
        color: #6b7280;
        margin-top: 0.2rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }

    /* ---- metric cards ---- */
    [data-testid="metric-container"] {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 1.1rem 1.4rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }
    [data-testid="metric-container"] label {
        color: #6b7280 !important;
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 0.09em;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        color: #163B70 !important;
        font-size: 2.1rem !important;
        font-weight: 800 !important;
    }

    /* ---- divider ---- */
    hr { border-color: #e5e7eb !important; }

    /* ---- expanders ---- */
    [data-testid="stExpander"] {
        background: #ffffff;
        border: 1px solid #e5e7eb !important;
        border-radius: 10px;
        margin-bottom: 0.5rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }
    [data-testid="stExpander"] summary {
        color: #111827 !important;
        font-weight: 600;
        font-size: 0.9rem;
    }

    /* ---- dataframe ---- */
    [data-testid="stDataFrame"] {
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }

    /* ---- sliders ---- */
    [data-testid="stSlider"] label {
        color: #111827 !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
    }
    [data-testid="stSlider"] [data-testid="stMarkdownContainer"] p {
        color: #111827 !important;
    }
    /* slider track accent */
    [data-testid="stSlider"] [role="slider"] { background: #2563EB !important; }

    /* ---- info boxes ---- */
    .stAlert {
        background: #eff6ff !important;
        border: 1px solid #bfdbfe !important;
        border-radius: 10px !important;
        color: #1e3a8a !important;
    }

    /* ---- captions / small text ---- */
    [data-testid="stCaptionContainer"] p {
        color: #4b5563 !important;
        font-size: 0.8rem !important;
    }

    /* ---- general text elements ---- */
    p, li, label, span, div { color: #111827; }

    /* ---- badge pills ---- */
    .badge {
        display: inline-block;
        padding: 3px 11px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        white-space: nowrap;
    }
    .badge-flaky                     { background: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; }
    .badge-stable                    { background: #dcfce7; color: #15803d; border: 1px solid #86efac; }
    .badge-suspected_order_dependent { background: #fef3c7; color: #b45309; border: 1px solid #fcd34d; }
    .badge-broken                    { background: #ede9fe; color: #6d28d9; border: 1px solid #c4b5fd; }
    .badge-timing                    { background: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; }
    .badge-shared_state              { background: #ede9fe; color: #6d28d9; border: 1px solid #c4b5fd; }
    .badge-race_condition            { background: #fff7ed; color: #c2410c; border: 1px solid #fdba74; }
    .badge-external_call             { background: #ccfbf1; color: #0f766e; border: 1px solid #5eead4; }

    /* ---- chart bar override ---- */
    .vega-embed canvas { border-radius: 8px; }

    /* ---- st.info text ---- */
    .stAlert p { color: #1e3a8a !important; }

    /* ---- markdown inside expanders ---- */
    [data-testid="stExpander"] p,
    [data-testid="stExpander"] li,
    [data-testid="stExpander"] strong {
        color: #111827 !important;
    }

    /* ---- code blocks ---- */
    [data-testid="stCode"] { border-radius: 8px; }
    [data-testid="stCode"] code { color: #ffffff !important; }
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
    st.bar_chart(chart_df, y="count", height=220, color="#2563EB")

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
        return ["background-color: #fff1f1; color: #111827"] * len(row)
    if cls_val == "broken":
        return ["background-color: #f5f0ff; color: #111827"] * len(row)
    return ["color: #111827"] * len(row)

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
    "<p style='text-align:center; color:#6b7280; font-size:0.75rem; margin-top:2rem; "
    "border-top: 1px solid #e5e7eb; padding-top: 1.2rem;'>"
    "Gleipnir &nbsp;&nbsp;|&nbsp;&nbsp; Made with IBM Bob"
    "</p>",
    unsafe_allow_html=True,
)
