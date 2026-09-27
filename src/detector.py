"""Statistically detects flaky tests from run results."""

import json
from collections import defaultdict
from pathlib import Path


def detect_flaky_tests(
    results_path: str = "results/run_results.json",
) -> list[dict]:
    """Load run results and classify each test.

    Classifications
    ---------------
    flaky                    — pass_rate strictly between 0.05 and 0.95
    suspected_order_dependent — pass_rate == 0.0 AND execution context varies
                               (different duration spread or mixed parallel values)
    broken                   — pass_rate == 0.0 with no context variation
    stable                   — everything else (consistently passing or consistently failing
                               outside the flaky band)

    Parameters
    ----------
    results_path:
        Path to the JSON file produced by runner.py.

    Returns
    -------
    list[dict] with one entry per test:
        {
            "test_name":      str,
            "total_runs":     int,
            "pass_rate":      float,
            "avg_duration":   float,
            "classification": "flaky" | "stable" | "suspected_order_dependent" | "broken",
        }
    """
    with open(results_path, encoding="utf-8") as fh:
        raw: list[dict] = json.load(fh)

    # Group records by test name
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in raw:
        grouped[record["test_name"]].append(record)

    report: list[dict] = []

    for test_name, runs in sorted(grouped.items()):
        total_runs = len(runs)
        pass_count = sum(1 for r in runs if r["passed"])
        fail_count = total_runs - pass_count
        pass_rate = pass_count / total_runs
        avg_duration = sum(r["duration"] for r in runs) / total_runs

        classification = _classify(runs, pass_rate)

        report.append(
            {
                "test_name": test_name,
                "total_runs": total_runs,
                "pass_rate": round(pass_rate, 4),
                "avg_duration": round(avg_duration, 6),
                "classification": classification,
            }
        )

    _save_report(report, str(Path(results_path).parent / "flakiness_report.json"))
    return report


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _classify(runs: list[dict], pass_rate: float) -> str:
    """Return a classification string for a single test's run history."""
    if 0.05 < pass_rate < 0.95:
        return "flaky"

    if pass_rate == 0.0:
        # Check whether the failure depends on execution context:
        # varied parallel flag or noticeably spread durations signal
        # a state/order dependency rather than a plain broken test.
        parallel_values = {r["parallel"] for r in runs}
        durations = [r["duration"] for r in runs]
        duration_spread = max(durations) - min(durations) if durations else 0.0
        context_varies = len(parallel_values) > 1 or duration_spread > 0.001
        return "suspected_order_dependent" if context_varies else "broken"

    return "stable"


def _save_report(report: list[dict], output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(f"Saved flakiness report ({len(report)} tests) -> {output_path}")


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Detect flaky tests from run results produced by runner.py."
    )
    parser.add_argument(
        "--results",
        default="results/run_results.json",
        metavar="PATH",
        help="Path to run_results.json (default: results/run_results.json)",
    )
    args = parser.parse_args()

    results = detect_flaky_tests(args.results)

    # ---- human-readable summary table ----
    col_name = max(len(r["test_name"]) for r in results)
    col_name = max(col_name, len("Test Name"))

    header = (
        f"{'Test Name':<{col_name}}  {'Pass Rate':>9}  {'Classification'}"
    )
    separator = "-" * len(header)

    print()
    print(header)
    print(separator)
    for r in results:
        print(
            f"{r['test_name']:<{col_name}}  "
            f"{r['pass_rate']:>9.2%}  "
            f"{r['classification']}"
        )
    print(separator)
    print(f"Total tests analysed: {len(results)}")
    print()
