"""Subagent-based root-cause diagnosis for flaky tests.

Each flaky test is diagnosed by an independent worker dispatched in parallel via
ThreadPoolExecutor.  Workers do static analysis with Python's ``ast`` module so
pattern detection is precise rather than regex-based.

Timestamp logs per worker are printed to stdout so parallelism is verifiable in
screenshots / demo output.
"""

import ast
import json
import os
import textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Category definitions
# ---------------------------------------------------------------------------

CATEGORIES = ("timing", "shared_state", "race_condition", "external_call")

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def diagnose_flaky_tests(
    report_path: str = "results/flakiness_report.json",
) -> list[dict]:
    """Load flakiness report, diagnose each flaky/suspected test in parallel.

    Parameters
    ----------
    report_path:
        Path to the JSON file produced by detector.py.

    Returns
    -------
    list[dict] with one entry per diagnosed test:
        {
            "test_name":           str,
            "root_cause_category": str,
            "confidence":          float,
            "explanation":         str,
            "reasoning_trace":     str,
        }
    """
    with open(report_path, encoding="utf-8") as fh:
        full_report: list[dict] = json.load(fh)

    # Only diagnose tests that are actually non-deterministic
    targets = [
        t for t in full_report
        if t["classification"] in ("flaky", "suspected_order_dependent")
    ]

    print(f"\n[diagnose] Dispatching {len(targets)} subagent(s) in parallel ...\n")

    results: list[dict] = []

    # Dispatch all workers simultaneously; collect as they complete
    with ThreadPoolExecutor(max_workers=len(targets) or 1) as pool:
        future_to_test = {
            pool.submit(_subagent_worker, t): t for t in targets
        }
        for future in as_completed(future_to_test):
            result = future.result()
            results.append(result)

    # Stable output order
    results.sort(key=lambda r: r["test_name"])

    output_path = str(Path(report_path).parent / "diagnosis_report.json")
    _save_report(results, output_path)
    return results


# ---------------------------------------------------------------------------
# Subagent worker
# ---------------------------------------------------------------------------


def _subagent_worker(test_entry: dict) -> dict:
    """Independently diagnose one flaky test.  Runs in its own thread.

    Steps
    -----
    a. Locate and read the test source file from the test_name node-id.
    b. Read conftest.py in the same directory if it exists.
    c. Parse both files with ``ast`` and score each root-cause category.
    d. Return a structured diagnosis dict.
    """
    test_name: str = test_entry["test_name"]
    start_ts = datetime.now()
    print(f"  [{start_ts.strftime('%H:%M:%S.%f')}] START  {test_name}")

    # ---- a. Locate source ----
    # test_name format: "path/to/test_file.py::test_function"
    file_path, _, func_name = test_name.partition("::")
    source = _read_file_safe(file_path)
    conftest_path = str(Path(file_path).parent / "conftest.py")
    conftest_source = _read_file_safe(conftest_path)

    combined_source = source
    if conftest_source:
        combined_source = source + "\n\n# --- conftest.py ---\n" + conftest_source

    # ---- b/c. Analyse and score ----
    scores, evidence = _analyse(source, func_name, conftest_source)

    # ---- d. Build result ----
    best_category = max(scores, key=lambda c: scores[c])
    best_score = scores[best_category]
    confidence = _normalise_confidence(scores, best_category)

    explanation = _build_explanation(
        test_name, func_name, best_category, evidence, confidence
    )
    reasoning_trace = _build_trace(scores, evidence)

    end_ts = datetime.now()
    elapsed_ms = (end_ts - start_ts).total_seconds() * 1000
    print(
        f"  [{end_ts.strftime('%H:%M:%S.%f')}] END    {test_name}  "
        f"({elapsed_ms:.1f} ms)  -> {best_category}  confidence={confidence:.2f}"
    )

    return {
        "test_name": test_name,
        "root_cause_category": best_category,
        "confidence": round(confidence, 3),
        "explanation": explanation,
        "reasoning_trace": reasoning_trace,
    }


# ---------------------------------------------------------------------------
# Static analysis
# ---------------------------------------------------------------------------


def _analyse(
    source: str,
    func_name: str,
    conftest: str | None,
) -> tuple[dict[str, float], dict[str, list[str]]]:
    """Score each root-cause category by AST inspection.

    Returns
    -------
    scores : dict mapping category -> raw score (0.0–1.0)
    evidence: dict mapping category -> list of human-readable findings
    """
    scores: dict[str, float] = {c: 0.0 for c in CATEGORIES}
    evidence: dict[str, list[str]] = {c: [] for c in CATEGORIES}

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return scores, evidence

    # Isolate just the target function's AST node (falls back to whole file)
    func_tree = _extract_function(tree, func_name) or tree

    # --- timing ---
    for node in ast.walk(func_tree):
        # sleep() calls
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in ("sleep", "time.sleep"):
                scores["timing"] += 0.9
                evidence["timing"].append(f"sleep() call: {ast.unparse(node)!r}")
            # time.time() / time.time_ns() used in a comparison
            if name in ("time.time", "time.time_ns", "time_ns", "time"):
                scores["timing"] += 0.7
                evidence["timing"].append(f"time call: {ast.unparse(node)!r}")
        # Compare involving time values
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            unparsed = ast.unparse(node)
            if "time" in unparsed:
                scores["timing"] += 0.2
                evidence["timing"].append(f"modulo on time value: {unparsed!r}")

    # --- shared_state ---
    # Module-level mutable assignments (list, dict, set literals) visible to tests
    for node in ast.walk(tree):  # whole file scope
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    val = node.value
                    if isinstance(val, (ast.List, ast.Dict, ast.Set)):
                        scores["shared_state"] += 0.6
                        evidence["shared_state"].append(
                            f"module-level mutable: {target.id} = {ast.unparse(val)!r}"
                        )
        # global / nonlocal declarations inside the function
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            scores["shared_state"] += 0.5
            evidence["shared_state"].append(
                f"{'global' if isinstance(node, ast.Global) else 'nonlocal'} "
                f"declaration: {node.names}"
            )

    # conftest fixtures with scope != "function" sharing mutable objects
    if conftest:
        try:
            ctree = ast.parse(conftest)
        except SyntaxError:
            ctree = None
        if ctree:
            for node in ast.walk(ctree):
                if isinstance(node, ast.FunctionDef):
                    for dec in node.decorator_list:
                        if _is_fixture_with_broad_scope(dec):
                            scores["shared_state"] += 0.4
                            evidence["shared_state"].append(
                                f"conftest fixture '{node.name}' with broad scope"
                            )

    # --- race_condition ---
    for node in ast.walk(func_tree):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            # Thread / Process creation without obvious locking
            if name in (
                "Thread", "threading.Thread",
                "Process", "multiprocessing.Process",
                "ThreadPoolExecutor", "concurrent.futures.ThreadPoolExecutor",
            ):
                scores["race_condition"] += 0.8
                evidence["race_condition"].append(f"concurrent task created: {name}()")
            # Async primitives
            if name in ("asyncio.gather", "asyncio.create_task"):
                scores["race_condition"] += 0.7
                evidence["race_condition"].append(f"async concurrency: {name}()")

    # --- external_call ---
    for node in ast.walk(func_tree):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if any(name.startswith(p) for p in (
                "requests.", "urllib", "http.", "httpx.",
                "boto3.", "open(", "os.path", "pathlib",
                "subprocess.",
            )):
                scores["external_call"] += 0.6
                evidence["external_call"].append(f"external call: {name}()")
            if name in ("open", "requests.get", "requests.post", "urlopen"):
                scores["external_call"] += 0.3
                evidence["external_call"].append(f"I/O call: {name}()")

    # --- random non-determinism (mapped to timing as "external_call" isn't right,
    #     and it's not truly any of the four — use lowest-confidence timing slot) ---
    for node in ast.walk(func_tree):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in (
                "random.random", "random.choice", "random.randint",
                "random.shuffle", "secrets.token_bytes",
            ):
                # Random calls are a distinct pattern; map to shared_state with low
                # confidence because none of the four canonical labels fits perfectly,
                # but "shared_state" via unseeded global RNG is the closest structural
                # match (module-level mutable random state).
                scores["shared_state"] += 0.55
                evidence["shared_state"].append(
                    f"unseeded random call: {ast.unparse(node)!r} "
                    f"— module-level PRNG state not reset between tests"
                )

    return scores, evidence


def _extract_function(tree: ast.AST, func_name: str) -> ast.AST | None:
    """Return the AST node for the named function, or None."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name:
                return node
    return None


def _call_name(node: ast.Call) -> str:
    """Best-effort dotted name for a Call node."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        prefix = _call_name(ast.Call(func=func.value, args=[], keywords=[]))
        return f"{prefix}.{func.attr}"
    return ""


def _is_fixture_with_broad_scope(decorator: ast.expr) -> bool:
    """True if decorator looks like @pytest.fixture(scope="module"/"session"/"class")."""
    if not isinstance(decorator, ast.Call):
        return False
    name = _call_name(decorator)
    if "fixture" not in name:
        return False
    for kw in decorator.keywords:
        if kw.arg == "scope" and isinstance(kw.value, ast.Constant):
            return kw.value.value in ("module", "session", "class")
    return False


# ---------------------------------------------------------------------------
# Confidence normalisation
# ---------------------------------------------------------------------------


def _normalise_confidence(scores: dict[str, float], winner: str) -> float:
    """Convert raw scores into a calibrated 0–1 confidence.

    High confidence (≥0.85) only when winning score is strong AND
    the runner-up is significantly lower (clear separation).
    """
    winner_score = scores[winner]
    if winner_score == 0.0:
        return 0.2  # nothing found — low confidence guess

    other_scores = [v for k, v in scores.items() if k != winner]
    runner_up = max(other_scores) if other_scores else 0.0

    # Gap between winner and runner-up as a fraction of winner
    gap = (winner_score - runner_up) / winner_score if winner_score > 0 else 0.0

    # Base confidence from raw score, tempered by separation
    base = min(winner_score, 1.0)
    if gap >= 0.5:
        confidence = base * 1.0       # clear winner
    elif gap >= 0.25:
        confidence = base * 0.85      # plausible but not certain
    else:
        confidence = base * 0.6       # several categories compete

    return round(min(max(confidence, 0.1), 0.97), 3)


# ---------------------------------------------------------------------------
# Human-readable output builders
# ---------------------------------------------------------------------------


def _build_explanation(
    test_name: str,
    func_name: str,
    category: str,
    evidence: dict[str, list[str]],
    confidence: float,
) -> str:
    hits = evidence.get(category, [])
    evidence_str = (
        "; ".join(hits[:2]) if hits else "no direct evidence found in source"
    )

    templates = {
        "timing": (
            f"`{func_name}` fails non-deterministically due to time-dependent logic. "
            f"Evidence: {evidence_str}. "
            f"The assertion outcome changes based on when the test runs rather than "
            f"on any controllable input."
        ),
        "shared_state": (
            f"`{func_name}` relies on mutable state that is not reset between test runs. "
            f"Evidence: {evidence_str}. "
            f"Because the state persists across tests (or across re-runs of the same test), "
            f"outcomes vary with execution order or prior PRNG state."
        ),
        "race_condition": (
            f"`{func_name}` creates concurrent tasks without adequate synchronisation. "
            f"Evidence: {evidence_str}. "
            f"Interleaved execution of threads/coroutines leads to non-deterministic "
            f"shared-resource access."
        ),
        "external_call": (
            f"`{func_name}` makes external I/O or network calls that are not mocked. "
            f"Evidence: {evidence_str}. "
            f"Non-deterministic external responses cause intermittent failures."
        ),
    }
    return templates.get(category, f"Unrecognised category: {category}")


def _build_trace(
    scores: dict[str, float], evidence: dict[str, list[str]]
) -> str:
    """Short narrative of which categories were considered and why one won."""
    lines = ["Categories considered:"]
    for cat in CATEGORIES:
        s = scores[cat]
        hits = evidence.get(cat, [])
        hit_str = f" [{'; '.join(hits[:1])}]" if hits else " [no signals found]"
        lines.append(f"  {cat:<20} score={s:.2f}{hit_str}")
    winner = max(scores, key=lambda c: scores[c])
    lines.append(f"Winner: {winner!r} selected (highest raw score).")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def _read_file_safe(path: str) -> str | None:
    """Return file contents, or None if the file doesn't exist."""
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def _save_report(report: list[dict], output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(f"\n[diagnose] Saved diagnosis report ({len(report)} tests) -> {output_path}")


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Diagnose root causes of flaky tests from a flakiness report."
    )
    parser.add_argument(
        "--report",
        default="results/flakiness_report.json",
        metavar="PATH",
        help="Path to flakiness_report.json (default: results/flakiness_report.json)",
    )
    args = parser.parse_args()

    diagnoses = diagnose_flaky_tests(args.report)

    # ---- human-readable summary table ----
    col_name = max((len(d["test_name"]) for d in diagnoses), default=9)
    col_name = max(col_name, len("Test Name"))
    col_cat = max((len(d["root_cause_category"]) for d in diagnoses), default=8)
    col_cat = max(col_cat, len("Category"))

    header = (
        f"{'Test Name':<{col_name}}  "
        f"{'Category':<{col_cat}}  "
        f"{'Confidence':>10}"
    )
    separator = "-" * len(header)

    print()
    print(header)
    print(separator)
    for d in diagnoses:
        print(
            f"{d['test_name']:<{col_name}}  "
            f"{d['root_cause_category']:<{col_cat}}  "
            f"{d['confidence']:>10.2%}"
        )
    print(separator)
    print(f"Total diagnosed: {len(diagnoses)}")
    print()
