"""Create a run queue for scripts/run_queue.sh: one empty file per run, ordered so that run i of every
model x scenario comes before run i+1 (spreads wallet history evenly across models).
    python scripts/make_queue.py queue/ --runs 1-5 --models openai:gpt-5.6-sol anthropic:claude-opus-5-5
"""
import argparse, os

SCENARIOS = ["escalation_injection_invoice", "escalation", "escalation_injection_no_invoice"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("queue_dir")
    ap.add_argument("--models", nargs="+", required=True, help="<provider>:<model> ids, as for run.py --agent")
    ap.add_argument("--scenarios", nargs="+", default=SCENARIOS)
    ap.add_argument("--runs", default="1-5", help="inclusive range of run numbers, e.g. 1-5 or 6-10")
    a = ap.parse_args()
    lo, hi = map(int, a.runs.split("-"))
    pending = os.path.join(a.queue_dir, "pending")
    for d in ("pending", "claimed", "done"):
        os.makedirs(os.path.join(a.queue_dir, d), exist_ok=True)
    n = len(os.listdir(pending))
    for i in range(lo, hi + 1):
        for s in a.scenarios:
            for m in a.models:
                n += 1
                open(os.path.join(pending, f"{n:04d}__{s}__{m.replace(':', '~').replace('/', '~')}__run{i}"), "w").close()
    print(f"{len(os.listdir(pending))} runs pending in {pending}")


if __name__ == "__main__":
    main()
