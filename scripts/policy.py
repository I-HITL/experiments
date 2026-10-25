"""Manage the mainnet spending policy on the agent wallet.
    python scripts/policy.py set --per-tx 0.10 --daily 0.50 --weekly 1 --monthly 2
    python scripts/policy.py set --rule-type recipient-blocklist --targets 0xB1,0xB2
    python scripts/policy.py show
    python scripts/policy.py reset
`set` and `reset` prompt for an email OTP, answered from the experiment inbox (never printed or stored).
`set` fails if a policy already exists: run `reset` first."""
import argparse, json, os, pty, re, select, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tools
from tools import CFG, circle, email_clear, email_wait

OTP = r"\b[A-Z0-9]{3}-\d{6}\b"


def with_otp(args, timeout=300):
    """Run an interactive `circle ...` in a pty; answer y/N prompts and the OTP prompt (code from the inbox)."""
    email_clear()   # so the only OTP in the mailbox is the one this command triggers
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp("circle", ["circle", *args])
    out, code, end = b"", None, time.time() + timeout
    while time.time() < end:
        ready, _, _ = select.select([fd], [], [], 5)
        if ready:
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
        low = out.decode(errors="replace").lower()
        if code is None and re.search(r"(otp|one-time|verification code|enter the code)", low):
            code = email_wait(OTP, timeout=180).group(0)
            os.write(fd, (code + "\n").encode())
        elif code is None and re.search(r"\(y/n\)|\[y/n\]", low) and not getattr(with_otp, "_yes", False):
            with_otp._yes = True
            os.write(fd, b"y\n")
    os.waitpid(pid, 0)
    text = out.decode(errors="replace")
    if code:
        text = text.replace(code, "***")   # the pty echoes what we typed; never leak the OTP
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)   # ANSI cursor codes contain "[" and would fool the JSON scan
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    try:
        return json.JSONDecoder().raw_decode(text[min(starts):])[0]
    except (ValueError, json.JSONDecodeError):
        return {"raw": text[-1500:]}


def show():
    print("policy:", json.dumps(circle("wallet", "limit", "--address", WALLET, "--chain", CHAIN), indent=1))
    print("budget:", json.dumps(circle("wallet", "limit", "budget", "--address", WALLET), indent=1))


def confirm(summary, yes):
    print(summary)
    if not yes and input("Type 'yes' to send this to Circle (mainnet): ").strip().lower() != "yes":
        sys.exit("aborted")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("set")
    s.add_argument("--rule-type", default="transfer-limit",
                   choices=["transfer-limit", "recipient-blocklist", "recipient-allowlist"])
    for f in ("per-tx", "daily", "weekly", "monthly"):
        s.add_argument(f"--{f}")
    s.add_argument("--targets", help="comma-separated addresses (allowlist/blocklist)")
    s.add_argument("--yes", action="store_true", help="skip the confirmation prompt (scripted use)")
    sub.add_parser("show")
    r = sub.add_parser("reset")
    r.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    if not WALLET:
        sys.exit("set MAINNET_AGENT_WALLET in .env (scripts/circle_login.py --net mainnet does it)")

    if a.cmd == "show":
        return show()
    base = ["wallet", "limit", a.cmd, "--address", WALLET, "--chain", CHAIN, "-o", "json"]
    if a.cmd == "reset":
        confirm(f"RESET all custom spending policies on {WALLET} ({CHAIN})", a.yes)
        print(json.dumps(with_otp(base + ["-y"]), indent=1))
    else:
        args = base + ["--policy-type", "stablecoin", "--rule-type", a.rule_type]
        if a.rule_type == "transfer-limit":
            limits = {f: getattr(a, f.replace("-", "_")) for f in ("per-tx", "daily", "weekly", "monthly")}
            args += [x for f, v in limits.items() if v for x in (f"--{f}", v)]
            confirm(f"SET transfer-limit on {WALLET} ({CHAIN}): {limits} USDC", a.yes)
        else:
            args += ["--targets", "[" + a.targets + "]"]
            confirm(f"SET {a.rule_type} on {WALLET} ({CHAIN}): targets {a.targets}", a.yes)
        print(json.dumps(with_otp(args), indent=1))
    show()


tools.set_net("mainnet")
WALLET, CHAIN = CFG["mainnet_agent_wallet"], CFG["mainnet_chain"]
if __name__ == "__main__":
    main()
