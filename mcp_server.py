"""MCP server for Gleipnir.

Exposes five tools that wrap the pipeline modules so Bob (or any MCP client)
can trigger flaky-test analysis from a conversation.

The standalone modules (runner.py, detector.py, src/diagnosis/diagnose.py)
have zero dependency on this file and continue to work without Bob installed.

Run directly for a quick smoke-test:
    python mcp_server.py
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path so src.* imports resolve when the server
# is spawned by Bob from an arbitrary working directory.
_ROOT = Path(__file__).parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# mcp 2.x: FastMCP was renamed to MCPServer
from mcp.server.mcpserver import MCPServer

from src.runner import run_suite, _save_results
from src.detector import detect_flaky_tests
from src.diagnosis.diagnose import diagnose_flaky_tests
from src.dashboard import launch_dashboard

mcp = MCPServer(
    "gleipnir",
    instructions=(
        "Gleipnir: flaky test detection and root-cause diagnosis. "
        "Use run_and_show_dashboard for the full pipeline with Streamlit dashboard, "
        "run_full_pipeline for a headless analysis, or call "
        "run_tests -> detect_flaky -> diagnose_flaky individually."
    ),
)

# ---------------------------------------------------------------------------
# Tool: run_tests
# ---------------------------------------------------------------------------

@mcp.tool()
def run_tests(
    test_path: str = "tests/sample_project",
    n_runs: int = 15,
) -> dict:
    """Run a pytest suite N times under varied conditions and save raw results.

    Alternates between randomised-order (odd runs) and parallel xdist (even
    runs) to surface order-dependent and concurrency-sensitive failures.

    Args:
        test_path: Path to the test file or directory to run.
        n_runs:    Number of times to execute the suite (default 15).

    Returns:
        Summary dict with total_tests, total_records, and output_path.
    """
    import os
    # Resolve relative paths against the project root so the server works
    # regardless of the CWD Bob uses when spawning it.
    if not Path(test_path).is_absolute():
        test_path = str(_ROOT / test_path)

    results = run_suite(test_path, n_runs)

    output_path = str(_ROOT / "results" / "run_results.json")
    _save_results(results, output_path)

    unique_tests = len({r["test_name"] for r in results})
    return {
        "total_tests": unique_tests,
        "total_records": len(results),
        "n_runs": n_runs,
        "output_path": output_path,
    }


# ---------------------------------------------------------------------------
# Tool: detect_flaky
# ---------------------------------------------------------------------------

@mcp.tool()
def detect_flaky(
    results_path: str = "results/run_results.json",
) -> dict:
    """Analyse run results and classify each test by flakiness.

    Args:
        results_path: Path to run_results.json produced by run_tests.

    Returns:
        Summary counts by classification plus path to the saved report.
    """
    if not Path(results_path).is_absolute():
        results_path = str(_ROOT / results_path)

    report = detect_flaky_tests(results_path)

    counts: dict[str, int] = {}
    for entry in report:
        c = entry["classification"]
        counts[c] = counts.get(c, 0) + 1

    output_path = str(Path(results_path).parent / "flakiness_report.json")
    return {
        "total_tests": len(report),
        "counts_by_classification": counts,
        "output_path": output_path,
    }


# ---------------------------------------------------------------------------
# Tool: diagnose_flaky
# ---------------------------------------------------------------------------

@mcp.tool()
def diagnose_flaky(
    report_path: str = "results/flakiness_report.json",
) -> dict:
    """Run root-cause diagnosis on all flaky/suspected tests in parallel.

    Dispatches one static-analysis worker per test simultaneously, then
    saves a structured diagnosis report.

    Args:
        report_path: Path to flakiness_report.json produced by detect_flaky.

    Returns:
        Full list of per-test diagnoses and path to the saved report.
    """
    if not Path(report_path).is_absolute():
        report_path = str(_ROOT / report_path)

    diagnoses = diagnose_flaky_tests(report_path)

    output_path = str(Path(report_path).parent / "diagnosis_report.json")
    return {
        "total_diagnosed": len(diagnoses),
        "diagnoses": diagnoses,
        "output_path": output_path,
    }


# ---------------------------------------------------------------------------
# Tool: run_full_pipeline
# ---------------------------------------------------------------------------

@mcp.tool()
def run_full_pipeline(
    test_path: str = "tests/sample_project",
    n_runs: int = 15,
) -> dict:
    """Run the complete flaky-test pipeline end-to-end.

    Chains: run_tests -> detect_flaky -> diagnose_flaky

    Args:
        test_path: Path to the test file or directory to run.
        n_runs:    Number of suite repetitions (default 15).

    Returns:
        Combined result with a summary of each stage and the full diagnosis.
    """
    # Stage 1: run
    run_summary = run_tests(test_path, n_runs)

    # Stage 2: detect
    flaky_summary = detect_flaky(run_summary["output_path"])

    # Stage 3: diagnose
    diagnosis_result = diagnose_flaky(flaky_summary["output_path"])

    return {
        "stage_1_run": run_summary,
        "stage_2_detect": flaky_summary,
        "stage_3_diagnose": {
            "total_diagnosed": diagnosis_result["total_diagnosed"],
            "output_path": diagnosis_result["output_path"],
            "diagnoses": diagnosis_result["diagnoses"],
        },
    }


# ---------------------------------------------------------------------------
# Tool: run_and_show_dashboard  (tool 5)
# ---------------------------------------------------------------------------

@mcp.tool()
def run_and_show_dashboard(
    test_path: str = "tests/sample_project",
    n_runs: int = 15,
    port: int = 8501,
) -> dict:
    """Run the full pipeline and launch the Streamlit dashboard.

    Chains: run_tests -> detect_flaky -> diagnose_flaky, then starts
    `streamlit run src/dashboard/app.py` in a subprocess. Streamlit opens
    the browser automatically on http://localhost:<port>.

    Ask Bob: "run the full pipeline and show me the dashboard."

    Args:
        test_path: Path to the test file or directory (default: tests/sample_project).
        n_runs:    Number of suite repetitions (default: 15).
        port:      Streamlit server port (default: 8501).

    Returns:
        Per-stage summaries plus dashboard launch info.
    """
    # Resolve path relative to project root
    if not Path(test_path).is_absolute():
        test_path = str(_ROOT / test_path)

    # Stage 1
    run_summary = run_tests(test_path, n_runs)

    # Stage 2
    flaky_summary = detect_flaky(run_summary["output_path"])

    # Stage 3
    diagnosis_result = diagnose_flaky(flaky_summary["output_path"])

    # Stage 4 -- launch Streamlit (non-blocking; server stays alive)
    launch_dashboard(port=port, block=False)

    return {
        "stage_1_run": run_summary,
        "stage_2_detect": flaky_summary,
        "stage_3_diagnose": {
            "total_diagnosed": diagnosis_result["total_diagnosed"],
            "output_path": diagnosis_result["output_path"],
            "diagnoses": diagnosis_result["diagnoses"],
        },
        "stage_4_dashboard": {
            "url": f"http://localhost:{port}",
            "streamlit_launched": True,
        },
    }


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # stdio transport — Bob spawns this process and communicates over stdin/stdout.
    # All logging must go to stderr to avoid corrupting the MCP protocol stream.
    import sys
    print("Gleipnir MCP server starting on stdio ...", file=sys.stderr)
    mcp.run(transport="stdio")
