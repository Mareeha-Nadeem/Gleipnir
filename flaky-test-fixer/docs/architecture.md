# Architecture

## Overview

Flaky-test-fixer is a three-stage pipeline that **runs** a test suite repeatedly,
**detects** non-deterministic tests statistically, and **diagnoses** root causes
through parallel static analysis.  Every component is a plain Python module with
no external service dependency — the pipeline runs entirely on the developer's
machine.

---

## Core Product — Standalone CLI

The standalone CLI is the primary delivery target.  It works without Bob, without
an internet connection, and without any MCP client installed.  Teams can drop it
into CI/CD, run it locally, or call it from any Python script.

```
flaky-test-fixer/
├── src/
│   ├── runner.py              # Stage 1 — multi-run pytest harness
│   ├── detector.py            # Stage 2 — statistical flakiness classification
│   └── diagnosis/
│       └── diagnose.py        # Stage 3 — parallel static-analysis diagnosis
└── results/
    ├── run_results.json       # Raw per-test run records
    ├── flakiness_report.json  # Per-test classification + pass rates
    └── diagnosis_report.json  # Root-cause category + confidence + explanation
```

### Stage 1 — `runner.py`

`run_suite(test_path, n_runs=15)` executes pytest repeatedly, alternating between
randomised test order (odd runs, via `pytest-random-order`) and parallel execution
(even runs, via `pytest-xdist`).  This intentionally stresses both
order-dependent and concurrency-sensitive failure modes.  Results are written to
`results/run_results.json` as a flat list of per-test records.

```
python src/runner.py [test_path] [--runs N] [--output PATH]
```

### Stage 2 — `detector.py`

`detect_flaky_tests(results_path)` groups run records by test name, computes
pass rates and durations, and classifies each test:

| Classification | Condition |
|---|---|
| `flaky` | pass_rate strictly between 0.05 and 0.95 |
| `suspected_order_dependent` | pass_rate == 0.0 AND execution context varies |
| `broken` | pass_rate == 0.0, no context variation |
| `stable` | everything else |

Results are saved to `results/flakiness_report.json`.

```
python src/detector.py [--results PATH]
```

### Stage 3 — `diagnosis/diagnose.py`

`diagnose_flaky_tests(report_path)` dispatches one static-analysis worker per
flaky test in parallel via `ThreadPoolExecutor`.  Each worker parses the test
source with Python's `ast` module and scores four root-cause categories:

| Category | Signal |
|---|---|
| `timing` | `time.time()`, `time_ns()`, `sleep()`, time-modulo assertions |
| `shared_state` | module-level mutable state, unseeded `random.*` calls, broad-scope fixtures |
| `race_condition` | `Thread`, `Process`, `asyncio.gather` without synchronisation |
| `external_call` | unmocked `requests.*`, `subprocess.*`, filesystem I/O |

Confidence is calibrated honestly: high (≥ 0.85) only when AST evidence is
unambiguous and the winning category separates clearly from all others.

Results are saved to `results/diagnosis_report.json`.

```
python -m src.diagnosis.diagnose [--report PATH]
```

---

## Optional Integration — MCP Server

`mcp_server.py` (project root) is an **optional add-on** for teams already using
Bob 2.0 in their development workflow.  It has no effect on — and no dependency
from — the standalone CLI modules.

### What it is

A [FastMCP](https://github.com/modelcontextprotocol/python-sdk) stdio server that
wraps the three pipeline stages as first-class Bob tools.  Bob spawns the process
on demand and communicates over stdin/stdout using the Model Context Protocol.

### Why it exists

Developers using Bob can trigger a full flaky-test analysis directly from a
conversation — without switching to a terminal, remembering CLI flags, or
copy-pasting paths.  Bob can chain the tools, interpret the results, and suggest
fixes in the same session.

### Tools exposed

| Tool | Wraps | Returns |
|---|---|---|
| `run_tests(test_path, n_runs)` | `runner.run_suite()` | record count, unique test count, output path |
| `detect_flaky(results_path)` | `detector.detect_flaky_tests()` | classification counts, output path |
| `diagnose_flaky(report_path)` | `diagnose.diagnose_flaky_tests()` | full diagnosis list, output path |
| `run_full_pipeline(test_path, n_runs)` | all three, chained | per-stage summaries + full diagnosis |

### Registration

The server is registered as a workspace-scoped stdio MCP server in `.bob/mcp.json`:

```json
{
  "mcpServers": {
    "flaky-test-fixer": {
      "command": "/path/to/python",
      "args": ["/path/to/flaky-test-fixer/mcp_server.py"],
      "cwd": "/path/to/flaky-test-fixer"
    }
  }
}
```

Bob hot-reloads on save.  The server appears in Bob's MCP panel and its four
tools become available in any Bob conversation opened in this workspace.

### Dependency boundary

```
mcp_server.py
    └── imports ──► src/runner.py          (no Bob dependency)
                    src/detector.py         (no Bob dependency)
                    src/diagnosis/diagnose.py  (no Bob dependency)

runner.py / detector.py / diagnose.py
    └── no import of mcp_server.py  (standalone, Bob-free)
```

The arrow is strictly one-way.  Removing or ignoring `mcp_server.py` leaves the
core product fully functional.
