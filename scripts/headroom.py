"""Reset the policy before each run so it leaves 0.01 USDC of room.

Circle's caps are rolling windows over past spend, which a policy reset does not clear. This sets per-tx 0.01,
daily = 24h spend + 0.01, weekly = 7d spend + 0.30, monthly = 30d spend + 1, so every run can pay exactly one
0.01 invoice before it hits the cap.
    python scripts/headroom.py          # apply, then verify (exit 1 on failure)
    python scripts/headroom.py --check  # verify only
"""
import os, subprocess, sys, time
from decimal import Decimal as D

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tools

tools.set_net("mainnet")
POLICY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "policy.py")


def budget():
    b = tools.circle("wallet", "limit", "budget", "--address", tools.agent_wallet(), "--chain", tools.chain(), "-o", "json")
    return tools.find(b, "STABLECOIN_TRANSFER") or {}


def spent(p, w):
    return D(str(p[f"{w}_limit"])) - D(str(p[f"{w}_remaining"]))


def ok(p):
    return (p.get("origin") == "CUSTOM" and D(str(p["per_tx_limit"])) == D("0.01")
            and D(str(p["daily_remaining"])) >= D("0.01"))   # tools.py caps the run at 0.01 regardless


def apply():
    p = budget()
    clamped = p.get("daily_limit") and any(D(str(p[f"{w}_remaining"])) <= 0 for w in ("daily", "weekly", "monthly"))
    if not p.get("daily_limit") or clamped:
        # no policy, or a cap below past spend (remaining clamps at 0): install a wide one to measure spend
        if clamped:
            subprocess.run([sys.executable, POLICY, "reset", "--yes"], capture_output=True, text=True, timeout=250)
            time.sleep(4)
        subprocess.run([sys.executable, POLICY, "set", "--per-tx", "0.01", "--daily", "100", "--weekly", "100",
                        "--monthly", "100", "--yes"], capture_output=True, text=True, timeout=250)
        time.sleep(8)
        p = budget()
        if not p.get("daily_limit"):
            sys.exit("could not install a custom policy to measure spend against")
    sd, sw, sm = spent(p, "daily"), spent(p, "weekly"), spent(p, "monthly")
    lim = [D("0.01"), sd + D("0.01"), sw + D("0.30"), sm + D("1")]
    subprocess.run([sys.executable, POLICY, "reset", "--yes"], capture_output=True, text=True, timeout=250)
    time.sleep(4)
    subprocess.run([sys.executable, POLICY, "set", "--per-tx", str(lim[0]), "--daily", str(lim[1]),
                    "--weekly", str(lim[2]), "--monthly", str(lim[3]), "--yes"], capture_output=True, text=True, timeout=250)
    time.sleep(8)


if __name__ == "__main__":
    if "--check" not in sys.argv:
        apply()
    p = budget()
    print(f"per_tx {p.get('per_tx_limit')} daily {p.get('daily_limit')} (room {p.get('daily_remaining')}) "
          f"weekly {p.get('weekly_limit')} (room {p.get('weekly_remaining')}) monthly {p.get('monthly_limit')} "
          f"(room {p.get('monthly_remaining')}) origin {p.get('origin')}")
    sys.exit(0 if p and ok(p) else 1)
