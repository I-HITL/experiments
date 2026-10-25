"""Log the agent into Circle (OTP read from the experiment inbox, never printed), save its wallet address to .env and
the USDC contract to config/experiment2.json. On testnet it also creates recipient wallets and requests faucet USDC.
    python scripts/circle_login.py                # testnet
    python scripts/circle_login.py --net mainnet"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tools
from tools import CFG, ENV, ROOT, circle, email_clear, email_wait, find, save_env

OTP = r"\b[A-Z0-9]{3}-\d{6}\b"                       # Circle codes look like B1X-123456
REQUEST = re.compile(r"--request\s+([0-9a-f-]{36})")  # --init returns the id inside a message string
ADDR = re.compile(r"0x[0-9a-fA-F]{40}")


def addresses(out):
    return list(dict.fromkeys(ADDR.findall(json.dumps(out))))


def login():
    email_clear()   # so the only OTP in the mailbox is the one this --init sends
    init = circle("wallet", "login", ENV["MAIL_ADDRESS"], "--type", "agent", "--init")
    m = REQUEST.search(json.dumps(init))
    req = find(init, "requestId") or (m and m.group(1))
    if not req:
        sys.exit(f"login --init failed: {init}")
    done = circle("wallet", "login", "--request", req, "--otp", email_wait(OTP).group(0))
    if "error" in done:
        sys.exit(f"login failed: {done}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", choices=["testnet", "mainnet"], default="testnet")
    net = ap.parse_args().net
    tools.set_net(net)
    if find(find(circle("wallet", "status", "--type", "agent"), net) or {}, "tokenStatus") != "VALID":
        login()
    wallets = addresses(circle("wallet", "list", "--chain", tools.chain(), "--type", "agent"))
    if not wallets:
        sys.exit(f"no agent wallet on {tools.chain()} after login")
    wkey, tkey = ("mainnet_agent_wallet", "mainnet_usdc_token") if net == "mainnet" else ("agent_wallet", "usdc_token")
    CFG[wkey] = CFG[wkey] if CFG[wkey] in wallets else wallets[0]
    CFG[tkey] = find(circle("contract", "address", "usdc", "--chain", tools.chain()), "address")
    save_env({wkey.upper(): CFG[wkey]})
    print(f"{net} agent wallet on {tools.chain()}: {CFG[wkey]} (saved to .env) | usdc: {CFG[tkey]}")

    if net == "testnet":
        need = 1 + len(CFG["recipients"])
        for _ in range(5):   # agent-wallet creation is capped at 5 in total
            if len(wallets) >= need:
                break
            out = circle("wallet", "create")
            if "error" in out:
                print("wallet create stopped:", str(out["error"])[:200])
                break
            wallets = addresses(circle("wallet", "list", "--chain", tools.chain(), "--type", "agent"))
        for (k, r), a in zip(CFG["recipients"].items(), [w for w in wallets if w != CFG[wkey]]):
            r["address"] = a
            save_env({f"RECIPIENT_{k.upper()}": a})
        fund = circle("wallet", "fund", "--address", CFG[wkey], "--chain", tools.chain())
        print("recipients:", {r["label"]: r["address"] for r in CFG["recipients"].values()})
        print("faucet:", "requested" if "error" not in fund else f"FAILED ({str(fund['error'])[:160]}) — try https://faucet.circle.com")
    else:
        print("mainnet: fund this address with USDC on BASE yourself, and set MAINNET_RECIPIENT_A in .env")
    path = os.path.join(ROOT, "config", "experiment2.json")
    saved = json.load(open(path))   # write back only the public token contract; addresses stay in .env
    saved[tkey] = CFG[tkey]
    json.dump(saved, open(path, "w"), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
