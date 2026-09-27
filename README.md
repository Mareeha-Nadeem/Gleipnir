# flaky-test-fixer

A three-stage pipeline that detects and diagnoses flaky tests in any pytest
suite.  Runs entirely on your machine — no internet connection, no external
service, no AI API key required.

---

## Table of Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [Quick start](#quick-start)
4. [Running each stage manually](#running-each-stage-manually)
   - [Stage 1 — Run](#stage-1--run)
   - [Stage 2 — Detect](#stage-2--detect)
   - [Stage 3 — Diagnose](#stage-3--diagnose)
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
# from the flaky-test-fixer directory
pip install -r requirements.txt
```

This installs pytest and the four pytest plugins the runner needs
(`pytest-json-report`, `pytest-random-order`, `pytest-xdist`) plus the MCP
server library (`mcp[cli]`).

---

## Quick start

Run the full three-stage pipeline against the bundled sample suite:

```powershell
# from the flaky-test-fixer directory
python -c "
import sys; sys.path.insert(0, '.')
from mcp_server import run_full_pipeline
import json
result = run_full_pipeline('tests/sample_project', n_runs=15)
print(json.dumps(result, indent=2))
"
```

Or call each stage from the CLI (see below) — the CLI is the primary interface
and works without importing the MCP server at all.

---

## Running each stage manually

All CLI commands must be run from inside the `flaky-test-fixer/` directory.

### Stage 1 — Run

Executes the suite `N` times, alternating between randomised order and
parallel execution, and writes raw per-test records to JSON.

```powershell
python src/runner.py [TEST_PATH] [--runs N] [--output PATH]
```

| Argument | Default | Description |
|---|---|---|
| `TEST_PATH` | `tests/sample_project` | Path to your test file or directory |
| `--runs N` | `15` | Number of times to run the suite |
| `--output PATH` | `results/run_results.json` | Where to write the raw records |

**Example — run your own suite 20 times:**
```powershell
python src/runner.py path/to/your/tests --runs 20
```

**Output:** `results/run_results.json` — a flat JSON array, one record per
test per run:
```json
[
  {
    "test_name": "tests/sample_project/test_sample.py::test_foo",
    "run_id": 1,
    "passed": true,
    "duration": 0.003,
    "parallel": false
  },
  ...
]
```

---

### Stage 2 — Detect

Reads `run_results.json`, computes pass rates, and classifies every test.

```powershell
python src/detector.py [--results PATH]
```

| Argument | Default | Description |
|---|---|---|
| `--results PATH` | `results/run_results.json` | Path to Stage 1 output |

**Example:**
```powershell
python src/detector.py --results results/run_results.json
```

Prints a summary table and writes `results/flakiness_report.json`.

**Classifications:**

| Label | Condition |
|---|---|
| `flaky` | Pass rate strictly between 5 % and 95 % |
| `suspected_order_dependent` | Always fails AND execution context varies (mixed parallel/serial runs, spread durations) |
| `broken` | Always fails with no context variation |
| `stable` | Everything else |

---

### Stage 3 — Diagnose

Reads `flakiness_report.json`, dispatches one isolated worker process per
flaky or suspected test in parallel, and writes root-cause diagnoses.

```powershell
python -m src.diagnosis.diagnose [--report PATH]
```

| Argument | Default | Description |
|---|---|---|
| `--report PATH` | `results/flakiness_report.json` | Path to Stage 2 output |

**Example:**
```powershell
python -m src.diagnosis.diagnose --report results/flakiness_report.json
```

Prints a timestamped per-worker log (so you can see parallelism) and a
summary table, then writes `results/diagnosis_report.json`.

**Root-cause categories:**

| Category | What the worker looks for |
|---|---|
| `timing` | `time.sleep()`, `time.time()`, `time_ns()`, time-modulo assertions |
| `shared_state` | Module-level mutable objects (`list`/`dict`/`set`), `global`/`nonlocal` declarations, unseeded `random.*` calls, broad-scope pytest fixtures |
| `race_condition` | `Thread`, `Process`, `asyncio.gather`, `asyncio.create_task` without synchronisation |
| `external_call` | Unmocked `requests.*`, `urllib`, `httpx`, `subprocess.*`, filesystem I/O |

---

## Output files

All output lands in `results/` by default.

| File | Written by | Contents |
|---|---|---|
| `run_results.json` | Stage 1 | Raw pass/fail records for every test × every run |
| `flakiness_report.json` | Stage 2 | Per-test classification and pass rate |
| `diagnosis_report.json` | Stage 3 | Root-cause category, confidence score, explanation, and reasoning trace per flaky test |

---

## Using with Bob (MCP)

`mcp_server.py` is an **optional** add-on.  It wraps the three stages as MCP
tools so Bob can call them directly from a conversation.  The standalone CLI
above works without it.

### Register the server

Add this to your workspace `.bob/mcp.json` (create the file if it doesn't
exist):

```json
{
  "mcpServers": {
    "flaky-test-fixer": {
      "command": "C:/path/to/python.exe",
      "args": ["C:/path/to/flaky-test-fixer/mcp_server.py"],
      "cwd": "C:/path/to/flaky-test-fixer"
    }
  }
}
```

Replace the paths with absolute paths on your machine.  Bob hot-reloads on
save — the four tools appear in Bob's MCP panel immediately.

### Available MCP tools

| Tool | What it does |
|---|---|
| `run_tests(test_path, n_runs)` | Stage 1 — runs the suite |
| `detect_flaky(results_path)` | Stage 2 — classifies tests |
| `diagnose_flaky(report_path)` | Stage 3 — diagnoses root causes |
| `run_full_pipeline(test_path, n_runs)` | All three stages chained, returns a single result dict with `stage_1_run`, `stage_2_detect`, `stage_3_diagnose` |

---

## Architecture

```
                        ┌─────────────────────────────────────────┐
                        │           run_full_pipeline()            │
                        │  (mcp_server.py — optional MCP wrapper)  │
                        └──────┬──────────┬──────────┬────────────┘
                               │          │          │
                    ┌──────────▼──┐  ┌────▼──────┐  ┌▼──────────────────┐
                    │  runner.py  │  │detector.py│  │  diagnose.py       │
                    │  Stage 1    │  │  Stage 2  │  │  Stage 3           │
                    └──────┬──────┘  └────┬──────┘  └──────┬────────────┘
                           │              │                 │
              Runs pytest   │    Reads     │    Reads        │  Spawns N
              N times with  │    run_      │    flakiness_   │  worker processes
              --random-order│    results   │    report       │  in parallel
              and -n auto   │    .json     │    .json        │  (one per flaky
                           │              │                 │   test)
                           ▼              ▼                 ▼
                    run_results     flakiness_report   diagnosis_report
                    .json           .json              .json
```

### Stage 1 — `src/runner.py`

**What it does:** Calls pytest as a subprocess `N` times. Odd-numbered runs
use `--random-order` (stresses test-order dependencies). Even-numbered runs
use `-n auto` (parallel via xdist, stresses concurrency and shared-state
bugs). Results are captured via `pytest-json-report` into a temp file per
run, then merged into a single flat list.

**Why both modes:** A test that only fails in a specific order won't show up
in parallel runs and vice versa. Alternating maximises detection surface.

**Output shape:** One JSON object per test per run with `test_name`,
`run_id`, `passed`, `duration`, `parallel`.

---

### Stage 2 — `src/detector.py`

**What it does:** Groups records by `test_name`, computes pass rate across
all runs, and applies the classification rules below.

**Why the 5 %–95 % band:** Tests that fail less than 5 % or more than 95 %
of the time are treated as stable or broken respectively — the band is wide
enough to catch real flakiness without false-positiving on rare environment
noise.

**`suspected_order_dependent`:** A test that _always_ fails but shows
varying durations or was run in both serial and parallel contexts is more
likely failing due to state pollution from a prior test than being genuinely
broken. This distinction matters for triage.

---

### Stage 3 — `src/diagnosis/diagnose.py`

**What it does:** For each test classified as `flaky` or
`suspected_order_dependent`, spawns an isolated OS-level worker process
(`ProcessPoolExecutor`, `max_workers=N` so all start simultaneously). Each
worker:

1. Reads the test source file itself from the `test_name` node-id path.
2. Reads `conftest.py` from the same directory if it exists.
3. Parses both files with Python's `ast` module independently.
4. Scores four root-cause categories by walking the AST.
5. Picks the highest-scoring category as the diagnosis.
6. Computes a calibrated confidence: high (≥ 0.85) only when AST evidence
   is strong _and_ the winning category is clearly separated from all
   others.

**Why `ProcessPoolExecutor` not `ThreadPoolExecutor`:** Each worker process
has its own memory space — no shared `scores` or `evidence` dicts, no GIL
contention, and genuine CPU-level parallelism for the AST parsing work.

**Why static analysis, not heuristics:** AST parsing catches the actual
structure of the code (e.g. a `global` declaration inside a nested function,
a `@pytest.fixture(scope="module")` on a function that returns a mutable
list) rather than just string patterns, so false-positive rates are lower.

---

## Project layout

```
flaky-test-fixer/
├── mcp_server.py              # Optional MCP server (Bob integration)
├── requirements.txt
├── docs/
│   └── architecture.md        # Detailed architecture reference
├── results/                   # All pipeline output (git-ignored except .gitkeep)
│   ├── run_results.json
│   ├── flakiness_report.json
│   └── diagnosis_report.json
├── src/
│   ├── runner.py              # Stage 1
│   ├── detector.py            # Stage 2
│   └── diagnosis/
│       └── diagnose.py        # Stage 3
└── tests/
    └── sample_project/
        └── test_sample.py     # Intentionally flaky sample suite for testing
```
