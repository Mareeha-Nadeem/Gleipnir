from src.dashboard import generate_dashboard, __name__ as _  # noqa: F401
import argparse
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent  # flaky-test-fixer/

parser = argparse.ArgumentParser(description="Generate flaky-test HTML dashboard")
parser.add_argument("--flakiness", default=str(_ROOT / "results/flakiness_report.json"))
parser.add_argument("--diagnosis", default=str(_ROOT / "results/diagnosis_report.json"))
parser.add_argument("--output", default=str(_ROOT / "results/dashboard.html"))
args = parser.parse_args()

out = generate_dashboard(args.flakiness, args.diagnosis, args.output)
print(f"Dashboard written to: {out}")
