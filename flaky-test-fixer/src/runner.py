"""Runs pytest suite N times under varied conditions and collects per-test results."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def run_suite(test_path: str, n_runs: int = 15) -> list[dict]:
    """Run the pytest suite at *test_path* n_runs times.

    Alternates between:
      - odd  runs  (1, 3, 5 …): randomised test order via pytest-random-order
      - even runs  (2, 4, 6 …): parallel execution via pytest-xdist

    Returns a flat list of per-test result dicts:
      {
        "test_name": str,
        "run_id":    int,   # 1-based
        "passed":    bool,
        "duration":  float, # seconds
        "parallel":  bool,
      }
    """
    all_results: list[dict] = []

    for run_id in range(1, n_runs + 1):
        parallel = (run_id % 2 == 0)
        records = _single_run(test_path, run_id, parallel)
        all_results.extend(records)

    return all_results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _single_run(test_path: str, run_id: int, parallel: bool) -> list[dict]:
    """Execute one pytest run and return per-test result dicts."""
    with tempfile.NamedTemporaryFile(
        suffix=".json", delete=False, mode="w"
    ) as tmp:
        report_path = tmp.name

    try:
        cmd = [
            sys.executable, "-m", "pytest",
            test_path,
            "--json-report",
            f"--json-report-file={report_path}",
            "--json-report-indent=2",
            "-q",          # less noise on stdout
            "--tb=no",     # no tracebacks — we only need pass/fail
        ]

        if parallel:
            cmd += ["-n", "auto"]
        else:
            cmd += ["--random-order"]

        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,   # non-zero exit when tests fail — that's fine
        )

        return _parse_report(report_path, run_id, parallel)
    finally:
        try:
            os.unlink(report_path)
        except OSError:
            pass


def _parse_report(report_path: str, run_id: int, parallel: bool) -> list[dict]:
    """Parse a pytest-json-report file into a list of result dicts."""
    try:
        with open(report_path, encoding="utf-8") as fh:
            report = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return []

    results = []
    for test in report.get("tests", []):
        outcome = test.get("outcome", "")
        # pytest-json-report uses "passed", "failed", "error", "skipped"
        passed = outcome == "passed"
        # Duration lives under the "call" phase; fall back to 0.0 when absent
        # (e.g. xdist parallel runs don't always populate it)
        call_phase = test.get("call") or {}
        duration = float(call_phase.get("duration", 0.0))
        # node id looks like "tests/sample_project/test_sample.py::test_foo"
        test_name = test.get("nodeid", "unknown")

        results.append(
            {
                "test_name": test_name,
                "run_id": run_id,
                "passed": passed,
                "duration": round(duration, 6),
                "parallel": parallel,
            }
        )

    return results


def _save_results(results: list[dict], output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"Saved {len(results)} records -> {output_path}")


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run a pytest suite N times and collect per-test results."
    )
    parser.add_argument(
        "test_path",
        nargs="?",
        default="tests/sample_project",
        help="Path to the test directory or file (default: tests/sample_project)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=15,
        metavar="N",
        help="Number of runs (default: 15)",
    )
    parser.add_argument(
        "--output",
        default="results/run_results.json",
        help="Output JSON path (default: results/run_results.json)",
    )
    args = parser.parse_args()

    print(f"Running {args.runs} suite(s) against '{args.test_path}' ...")
    results = run_suite(args.test_path, args.runs)
    _save_results(results, args.output)
