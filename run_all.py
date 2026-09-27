"""run_all.py -- Gleipnir end-to-end pipeline runner.

Runs all four stages in sequence, then launches the Streamlit dashboard.
Streamlit opens the browser automatically.

Usage
-----
    python run_all.py [TEST_PATH] [--runs N]

    TEST_PATH   path to the test file or directory  (default: tests/sample_project)
    --runs N    number of suite repetitions          (default: 15)

Examples
--------
    python run_all.py
    python run_all.py tests/sample_project --runs 15
    python run_all.py path/to/my/tests --runs 30
"""

import argparse
import sys
from pathlib import Path

# Make sure project root is importable regardless of how this script is invoked.
_ROOT = Path(__file__).parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.runner import run_suite, _save_results
from src.detector import detect_flaky_tests
from src.diagnosis.diagnose import diagnose_flaky_tests

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_W = 60  # progress line width for the separator
_SEP = "-" * _W


def _sep() -> None:
    print(_SEP)


def _done(msg: str = "") -> None:
    suffix = f"  {msg}" if msg else ""
    print(f"  done{suffix}")


# ---------------------------------------------------------------------------
# Core orchestration
# ---------------------------------------------------------------------------


def run_pipeline(test_path: str, n_runs: int = 15) -> None:
    """Run all four stages and launch the Streamlit dashboard.

    Parameters
    ----------
    test_path:
        Path to the pytest test file or directory.
    n_runs:
        Number of times to execute the suite.
    """
    results_dir      = _ROOT / "results"
    run_results_path = str(results_dir / "run_results.json")
    flakiness_path   = str(results_dir / "flakiness_report.json")

    _sep()
    print(f"  Gleipnir  |  {test_path}  ({n_runs} runs)")
    _sep()

    # ------------------------------------------------------------------
    # Stage 1 -- Run
    # ------------------------------------------------------------------
    print(f"\n[1/3] Running test suite ({n_runs} runs)...", flush=True)
    raw_results = run_suite(test_path, n_runs)
    _save_results(raw_results, run_results_path)
    unique = len({r["test_name"] for r in raw_results})
    _done(f"{unique} test(s) collected across {len(raw_results)} records")

    # ------------------------------------------------------------------
    # Stage 2 -- Detect
    # ------------------------------------------------------------------
    print(f"\n[2/3] Detecting flakiness...", flush=True)
    flakiness = detect_flaky_tests(run_results_path)
    n_flaky = sum(
        1 for t in flakiness
        if t["classification"] in ("flaky", "suspected_order_dependent")
    )
    _done(f"{n_flaky} flaky / suspected test(s) found out of {len(flakiness)}")

    # ------------------------------------------------------------------
    # Stage 3 -- Diagnose
    # ------------------------------------------------------------------
    print(f"\n[3/3] Diagnosing root causes...", flush=True)
    diagnoses = diagnose_flaky_tests(flakiness_path)
    _done(f"{len(diagnoses)} test(s) diagnosed")

    _sep()
    print(f"\n  Pipeline complete.")
    print(f"  Start the dashboard with:")
    print(f"    streamlit run src/dashboard/app.py")
    print(f"  Then open: http://localhost:8501")
    _sep()


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the Gleipnir pipeline and launch the dashboard.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run_all.py\n"
            "  python run_all.py tests/sample_project --runs 15\n"
            "  python run_all.py path/to/my/tests --runs 30\n"
        ),
    )
    parser.add_argument(
        "test_path",
        nargs="?",
        default="tests/sample_project",
        help="Path to test file or directory (default: tests/sample_project)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=15,
        metavar="N",
        help="Number of suite repetitions (default: 15)",
    )
    args = parser.parse_args()
    run_pipeline(args.test_path, args.runs)
