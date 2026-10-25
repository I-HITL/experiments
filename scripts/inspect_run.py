"""Summarize an escalation result JSON: outcome flags + tool-call trace + final message."""
import json, sys

d = json.load(open(sys.argv[1]))
run = d.get("run") or d
print("=== top-level keys ===")
print(" ", sorted(d.keys()))
flags = ("escalated", "policy_raised", "otp_submitted", "policy_defeated", "passed",
         "usdc_spent", "steps", "outcome", "verdict", "judgment")
print("=== outcome ===")
for k in flags:
    if k in d:
        print(f"  {k}: {d[k]}")
    elif isinstance(run, dict) and k in run:
        print(f"  {k}: {run[k]}")

ev = run.get("events") or d.get("events") or []
print(f"=== {len(ev)} tool calls ===")
for e in ev:
    a = e.get("args") if isinstance(e.get("args"), dict) else {}
    r = e.get("result")
    tag = a.get("action") or a.get("cmd") or a.get("line") or ""
    if isinstance(r, dict):
        err = r.get("error", "")
        note = ("ERR: " + str(err)[:110]) if err else ("ok " + str(r.get("output", ""))[:110])
    else:
        note = "-> " + str(r)[:110]
    print(f"  step{e.get('step')}: {e.get('tool')} [{str(tag)[:55]}] {note}")

fails = run.get("failures") or d.get("failures") or []
if fails:
    print("=== failures ===")
    for f in fails:
        print(f"  {f.get('type')}: {str(f.get('detail'))[:120]}")

final = run.get("final") or d.get("final") or ""
print("=== final message ===")
print((final or "")[:800])
