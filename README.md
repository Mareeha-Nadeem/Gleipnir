# Gleipnir

Detects and diagnoses flaky tests in any pytest suite. Runs entirely on your
machine -- no internet connection, no external service, no API key required.

---

## Table of Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [Quick start](#quick-start)
4. [Running the pipeline](#running-the-pipeline)
   - [One command](#one-command)
   - [Stage 1 -- Run](#stage-1----run)
   - [Stage 2 -- Detect](#stage-2----detect)
   - [Stage 3 -- Diagnose](#stage-3----diagnose)
   - [Stage 4 -- Dashboard](#stage-4----dashboard)
5. [Output files](#output-files)
6. [Using with Bob (MCP)](#using-with-bob-mcp)
7. [Architecture](#architecture)
8. [Project layout](#project-layout)

---

## Requirements

- Python 3.11+
- pip

---

## Installation

```powershell
pip install -r requirements.txt
```

Installs pytest and its plugins, the MCP server library, Streamlit, and pandas.

---

## Quick start

Run the full pipeline against the bundled sample suite and open the dashboard:

```powershell
python run_all.py
```

With a custom path and run count:

```powershell
python run_all.py tests/sample_project --runs 15
python run_all.py path/to/your/tests --runs 30
```

Stages 1-3 run automatically, then Streamlit starts and opens the browser.
Press `Ctrl+C` to stop the dashboard server.

---

## Running the pipeline

### One command

`run_all.py` chains all four stages:

```
[1/4] Running test suite
[2/4] Detecting flakiness
[3/4] Diagnosing root causes
[4/4] Launching dashboard  ->  http://localhost:8501
```

### Stage 1 -- Run

Executes the suite `N` times, alternating between randomised order and
parallel execution, and writes raw per-test records to JSON.

```powershell
python src/runner.py [TEST_PATH] [--runs N] [--output PATH]
```

| Argument | Default | Description |
|---|---|---|
| `TEST_PATH` | `tests/sample_project` | Path to test file or directory |
| `--runs N` | `15` | Number of times to run the suite |
| `--output PATH` | `results/run_results.json` | Where to write the raw records |

Output -- `results/run_results.json`, one record per test per run:

```json
[
  {
    "test_name": "tests/sample_project/test_sample.py::test_foo",
    "run_id": 1,
    "passed": true,
    "duration": 0.003,
    "parallel": false
  }
]
```

### Stage 2 -- Detect

Reads `run_results.json`, computes pass rates, and classifies every test.

```powershell
python src/detector.py [--results PATH]
```

| Classification | Condition |
|---|---|
| `flaky` | Pass rate strictly between 5% and 95% |
| `suspected_order_dependent` | Always fails AND execution context varies |
| `broken` | Always fails with no context variation |
| `stable` | Everything else |

Output -- `results/flakiness_report.json`.

### Stage 3 -- Diagnose

Reads `flakiness_report.json`, dispatches one isolated worker process per
flaky test in parallel, and writes root-cause diagnoses.

```powershell
python -m src.diagnosis.diagnose [--report PATH]
```

| Root-cause category | What the worker looks for |
|---|---|
| `timing` | `time.sleep()`, `time.time()`, `time_ns()`, time-modulo assertions |
| `shared_state` | Module-level mutable objects, unseeded `random.*` calls, broad-scope fixtures |
| `race_condition` | `Thread`, `Process`, `asyncio.gather` without synchronisation |
| `external_call` | Unmocked `requests.*`, `urllib`, `subprocess.*`, filesystem I/O |

Output -- `results/diagnosis_report.json`.

### Stage 4 -- Dashboard

The dashboard is a Streamlit app. Launch it standalone at any time:

```powershell
streamlit run src/dashboard/app.py
```

Or via the module entry point:

```powershell
python -m src.dashboard
```

Opens at `http://localhost:8501`. Shows:

- Summary metrics (total, flaky, stable, diagnosed)
- Live hours-lost calculator with sliders
- Root-cause breakdown bar chart
- Colour-coded test results table with fix hints
- Per-test expandable sections with full explanation and reasoning trace

---

## Output files

| File | Written by | Contents |
|---|---|---|
| `results/run_results.json` | Stage 1 | Raw pass/fail records for every test x every run |
| `results/flakiness_report.json` | Stage 2 | Per-test classification and pass rate |
| `results/diagnosis_report.json` | Stage 3 | Root-cause category, confidence, explanation, reasoning trace |

---

## Using with Bob (MCP)

`mcp_server.py` is an optional add-on. It exposes the pipeline as five MCP
tools so Bob can run the full analysis from a conversation.

### Register the server

Add to `.bob/mcp.json` in your workspace (create it if it does not exist):

```json
{
  "mcpServers": {
    "gleipnir": {
      "command": "C:/path/to/python.exe",
      "args": ["C:/path/to/Gleipnir/mcp_server.py"],
      "cwd": "C:/path/to/Gleipnir"
    }
  }
}
```

Replace the paths with absolute paths on your machine. Bob hot-reloads on save.

### Available MCP tools

| Tool | What it does |
|---|---|
| `run_tests(test_path, n_runs)` | Stage 1 -- runs the suite |
| `detect_flaky(results_path)` | Stage 2 -- classifies tests |
| `diagnose_flaky(report_path)` | Stage 3 -- diagnoses root causes |
| `run_full_pipeline(test_path, n_runs)` | Stages 1-3 chained, headless |
| `run_and_show_dashboard(test_path, n_runs, port)` | Stages 1-3 then launches Streamlit |

Ask Bob: **"run the full pipeline and show me the dashboard"** to trigger
`run_and_show_dashboard`.

---

## Architecture

```
run_all.py  (or run_and_show_dashboard MCP tool)
    |
    |-- [1/4] src/runner.py
    |         Calls pytest N times, alternating:
    |           odd  runs  -> --random-order  (order-dependent failures)
    |           even runs  -> -n auto         (concurrency failures)
    |         Writes: results/run_results.json
    |
    |-- [2/4] src/detector.py
    |         Groups by test name, computes pass rates, classifies.
    |         Band: 5%-95% = flaky. Always-fail + context varies = suspected.
    |         Writes: results/flakiness_report.json
    |
    |-- [3/4] src/diagnosis/diagnose.py
    |         ProcessPoolExecutor -- one OS process per flaky test, all parallel.
    |         Each process independently reads source + conftest, parses AST,
    |         scores 4 categories, returns diagnosis. No shared state.
    |         Writes: results/diagnosis_report.json
    |
    `-- [4/4] src/dashboard/app.py  (Streamlit)
              Loads the three JSON files, renders interactive dashboard.
              Launched via subprocess; Streamlit opens the browser itself.
```

### Why ProcessPoolExecutor

Each worker runs in a separate OS process with its own memory space. No
shared `scores` or `evidence` dicts, no GIL, and genuine CPU-level
parallelism for the AST parsing work.

### Why static AST analysis

AST parsing catches actual code structure -- a `global` declaration inside a
nested function, a `@pytest.fixture(scope="module")` on a function returning
a mutable list -- rather than text patterns, keeping false-positive rates low.

---

## Project layout

```
Gleipnir/
├── run_all.py                 # One-command pipeline runner
├── mcp_server.py              # Optional MCP server (Bob integration)
├── requirements.txt
├── docs/
│   └── architecture.md
├── results/                   # Pipeline output (git-ignored except .gitkeep)
│   ├── run_results.json
│   ├── flakiness_report.json
│   └── diagnosis_report.json
├── src/
│   ├── runner.py              # Stage 1
│   ├── detector.py            # Stage 2
│   ├── diagnosis/
│   │   └── diagnose.py        # Stage 3
│   └── dashboard/
│       ├── app.py             # Stage 4 -- Streamlit app
│       ├── __init__.py        # launch_dashboard() helper
│       └── __main__.py        # python -m src.dashboard entry point
└── tests/
    └── sample_project/
        └── test_sample.py     # Intentionally flaky sample suite
```
