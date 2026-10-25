"""Drain each testnet recipient wallet's USDC back to the agent wallet so every scenario starts from a known
balance. Recipients are extra agent wallets under the same Circle login, which is what makes this possible.
(Mainnet recipients are the operator's own wallets, so run.py never drains on mainnet.)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import CFG, agent_wallet, chain, circle, find, usdc_token


def usdc_balance(address):
    """ERC-20 USDC only — ARC-TESTNET's native gas token is also called USDC, so match on the contract address.
    Use Circle's server-side --token filter: a wallet holding many tokens (e.g. airdrop spam) otherwise paginates
    USDC out of the default balance page, silently returning 0."""
    bals = find(circle("wallet", "balance", "--address", address, "--chain", chain(), "--token", usdc_token()), "balances") or []
    for b in bals:
        if str(find(b, "tokenAddress")).lower() == str(usdc_token()).lower():
            return float(find(b, "amount") or 0)
    return 0.0


def drain():
    if not CFG.get("agent_wallet"):
        return
    for r in CFG["recipients"].values():
        amt = usdc_balance(r["address"]) if r["address"] else 0.0
        if amt > 0:
            circle("wallet", "transfer", agent_wallet(), "--amount", amt, "--token", usdc_token(),
                   "--address", r["address"], "--chain", chain())
            print(f"reset: drained {amt} USDC from {r['label']}")


if __name__ == "__main__":
    drain()
