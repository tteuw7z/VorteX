"""Compare common tasks using two source trees and the same interpreter/runner."""
import argparse
import json
import os
from pathlib import Path
from statistics import median
import subprocess
import sys

TASKS = (
    "Legendar os vídeos do ZIP",
    "Add captions to videos from a ZIP",
    "Audit Android security",
    "Build a Python workflow",
    "Obrigado pela ajuda",
)
PROBE = """
import json
from timeit import timeit
from vortex.core import plan
tasks = json.loads(__import__('sys').argv[1])
def run():
    return [plan(task, agent_limit=2) for task in tasks]
sample = run()
elapsed = timeit(run, number=2000)
print(json.dumps({"median_input_us": elapsed * 1e6 / (2000 * len(tasks)),
                  "plans": sample}))
"""

def sample(root: Path) -> dict:
    env = dict(os.environ, PYTHONPATH=str(root.resolve() / "src"))
    result = subprocess.run([sys.executable, "-c", PROBE, json.dumps(TASKS)],
                            cwd=root, env=env, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    roots = {"baseline": args.baseline.resolve(), "candidate": args.candidate.resolve()}
    values = {label: [] for label in roots}
    expected = None
    for i in range(5):
        for label in (("baseline", "candidate") if i % 2 == 0 else ("candidate", "baseline")):
            result = sample(roots[label])
            if expected is None:
                expected = result["plans"]
            elif result["plans"] != expected:
                raise RuntimeError("Common task plan changed; comparison rejected")
            values[label].append(result["median_input_us"])
    before, after = median(values["baseline"]), median(values["candidate"])
    print(json.dumps({"tasks": TASKS, "plans_equal": True, "samples_us_per_task": values,
                      "baseline_median_us": before, "candidate_median_us": after,
                      "candidate_over_baseline": after / before}, indent=2))

if __name__ == "__main__":
    main()
