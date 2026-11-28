"""Compare previous and current preflight on identical public synthetic tasks."""
import json
import os
from pathlib import Path
from statistics import median
import subprocess
import sys

TASKS = ("Build a Python API", "Compilar APK Android", "Legendar vídeos ZIP",
         "Pesquisar fontes de segurança", "Criar um site", "Pedido sem categoria explícita")
PROBE = """
import json
from timeit import timeit
from vortex.discipline import prepare_task
import sys
tasks = json.loads(sys.argv[1])
def run():
    return [prepare_task(task) for task in tasks]
sample = run()
elapsed = timeit(run, number=300)
print(json.dumps({"us": elapsed * 1e6 / (300 * len(tasks)),
                  "cases": [{"roles": sorted(p["role"] for p in r["selected_profiles"]),
                             "economy": {k: r["economy"][k] for k in (
                                 "estimated_baseline_tokens", "estimated_selected_tokens",
                                 "estimated_saved_tokens", "task_preserved",
                                 "mandatory_review_roles_preserved")}}
                            for r in sample]}))
"""


def probe(root):
    root = Path(root).resolve()
    env = dict(os.environ, PYTHONPATH=str(root / "src"))
    output = subprocess.run([sys.executable, "-c", PROBE, json.dumps(TASKS)],
                            cwd=root, env=env, check=True, capture_output=True, text=True,
                            timeout=60)
    return json.loads(output.stdout)


def main():
    roots = {"baseline": sys.argv[1], "candidate": sys.argv[2]}
    samples = {name: [] for name in roots}
    cases = {}
    for index in range(5):
        for name in (("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline")):
            result = probe(roots[name])
            samples[name].append(result["us"])
            if name in cases and cases[name] != result["cases"]:
                raise RuntimeError("Nondeterministic preflight")
            cases[name] = result["cases"]
    for before, after in zip(cases["baseline"], cases["candidate"], strict=True):
        if not set(before["roles"]) <= set(after["roles"]):
            raise RuntimeError("Previous selected role lost")
        if not all(after["economy"][field] for field in
                   ("task_preserved", "mandatory_review_roles_preserved")):
            raise RuntimeError("Mandatory preflight preservation failed")
    print("SPECTOR_BENCHMARK " + json.dumps({
        "tasks": TASKS, "all_previous_roles_preserved": True,
        "baseline_median_us": median(samples["baseline"]),
        "candidate_median_us": median(samples["candidate"]),
        "cases": cases, "scope": "local preflight only; token counts are estimates"
    }))


if __name__ == "__main__":
    main()
