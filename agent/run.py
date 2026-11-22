"""CLI entry: `python -m agent.run` runs the workflow once and prints a JSON report."""
import json
import sys

from .workflow import run_workflow

if __name__ == "__main__":
    print(json.dumps(run_workflow(), indent=2, default=str))
    sys.exit(0)
