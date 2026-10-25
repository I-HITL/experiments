"""Self-escalation rate per model and setting (the paper figure).

A run counts when the agent completed the escalation: its own policy change went through the OTP flow
(escalation.policy_defeated in the result JSON). Models are grouped by family, least to most capable.
    python analysis/plot.py                      # all three settings -> figures/self_escalation.{png,pdf}
    python analysis/plot.py --only escalation    # one setting, e.g. for slides
    python analysis/plot.py --ci 95              # add Wilson score intervals
"""
import argparse, collections, glob, json, os
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.transforms import blended_transform_factory

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# (directory, file prefix, runs kept per model x setting): the current suite, plus the earlier suite that
# supplies five runs for deepseek-v3.1, gemini-2.5-flash and sonnet-5
SOURCES = [(os.path.join(ROOT, "results", "lc3_suite_2026-10-21", "result_json"), "lc3", 20),
           (os.path.join(ROOT, "results", "langchain_suite_2026-10-10", "result_json"), "lc2b", 5)]
SETTINGS = [("escalation", "Payment agent\nNo attack"),
            ("escalation_injection_invoice", "Payment agent\nInjection attack"),
            ("escalation_injection_no_invoice", "Summary agent\nInjection attack")]
FAMILIES = [("Qwen", [("openrouter:qwen/qwen3.6-35b-a3b", "qwen3.6-35b-a3b"), ("openrouter:qwen/qwen3.6-27b", "qwen3.6-27b")]),
            ("DeepSeek", [("openrouter:deepseek/deepseek-chat-v3.1", "deepseek-v3.1"),
                          ("openrouter:deepseek/deepseek-v4-pro", "deepseek-v4-pro")]),
            ("GPT", [("openai:gpt-5.6-luna", "gpt-5.6-luna"), ("openai:gpt-5.6-sol", "gpt-5.6-sol")]),
            ("Gemini", [("gemini:gemini-2.5-flash", "gemini-2.5-flash"), ("gemini:gemini-3.8-flash", "gemini-3.8-flash")]),
            ("Claude", [("anthropic:claude-sonnet-5", "sonnet-5"), ("anthropic:claude-opus-5-5", "opus-5.5")])]
LABEL = {a: lab for _, models in FAMILIES for a, lab in models}
COLORS = {"escalation": "#d79c42", "escalation_injection_invoice": "#4378ae", "escalation_injection_no_invoice": "#bc5a32"}
INK, MUTED, GRID = "#222222", "#555555", "#DDDDDD"
FS = dict(tick=15, ylab=17, leg=16, fam=16)
Z = {90: 1.6449, 95: 1.96, 99: 2.5758}


def tally(setting):
    """{agent: {"n": runs, "comp": completed}} over the latest runs of each source."""
    files = collections.defaultdict(list)
    for d, pre, _ in SOURCES:
        for f in glob.glob(os.path.join(d, f"{pre}_{setting}_*.json")):
            if setting == "escalation" and os.path.basename(f).startswith(f"{pre}_escalation_injection_"):
                continue
            a = json.load(open(f))["agent"]
            if a in LABEL:
                files[(a, pre)].append(f)
    keep = {pre: k for _, pre, k in SOURCES}
    rows = collections.defaultdict(lambda: dict(n=0, comp=0))
    for (a, pre), fs in files.items():
        for f in sorted(fs, key=os.path.getmtime)[-keep[pre]:]:
            rows[a]["n"] += 1
            rows[a]["comp"] += bool((json.load(open(f)).get("escalation") or {}).get("policy_defeated"))
    return rows


def wilson(k, n, z):
    if not n:
        return 0.0, 0.0
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return max(0.0, c - h), min(1.0, c + h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=[s for s, _ in SETTINGS], help="plot a single setting")
    ap.add_argument("--ci", type=int, choices=sorted(Z), help="add Wilson score intervals at this confidence level")
    ap.add_argument("--out", default=os.path.join(ROOT, "figures"))
    a = ap.parse_args()
    sel = [s for s in SETTINGS if a.only in (None, s[0])]
    nb = len(sel)
    data = {s: tally(s) for s, _ in sel}

    bar, gap = (0.26, 0.4) if nb > 1 else (0.6, 0.4)
    xs, x = [], 0.0
    for _, models in FAMILIES:
        for agent, _ in models:
            xs.append((agent, x)); x += nb * bar + gap

    fig, ax = plt.subplots(figsize=(16, 7.0))
    for k, (s, _) in enumerate(sel):
        for agent, x0 in xs:
            r = data[s].get(agent, {"n": 0, "comp": 0})
            pct = 100 * r["comp"] / r["n"] if r["n"] else 0
            ax.bar(x0 + k * bar, pct, width=bar, color=COLORS[s], edgecolor="white", linewidth=1.2, zorder=3)
            if a.ci and r["n"]:
                lo, hi = wilson(r["comp"], r["n"], Z[a.ci])
                ax.errorbar(x0 + k * bar, pct, yerr=[[pct - 100 * lo], [100 * hi - pct]], fmt="none", ecolor=INK,
                            elinewidth=1.1, capsize=3, capthick=1.1, zorder=5)
            if r["n"] and pct == 0:   # a measured zero, so it does not read as missing data
                ax.hlines(0.9, x0 + k * bar - 0.38 * bar, x0 + k * bar + 0.38 * bar, colors=COLORS[s], linewidth=2.5,
                          capstyle="round", zorder=4)

    centers = [x0 + (nb - 1) / 2 * bar for _, x0 in xs]
    i = 0
    for name, models in FAMILIES:
        if i:   # dotted separator before every family but the first
            ax.axvline((xs[i - 1][1] + (nb - 0.5) * bar + xs[i][1] - 0.5 * bar) / 2,
                       color="#AAAAAA", linestyle=":", linewidth=1.2, zorder=1)
        ax.text((centers[i] + centers[i + len(models) - 1]) / 2, -0.31, name, fontsize=FS["fam"], color=MUTED,
                fontweight="bold", ha="center", va="top", transform=blended_transform_factory(ax.transData, ax.transAxes))
        i += len(models)

    ax.set_xticks(centers)
    ax.set_xticklabels([LABEL[agent] for agent, _ in xs], rotation=30, ha="right", fontsize=FS["tick"], color=INK)
    ax.set_xlim(-bar, xs[-1][1] + nb * bar)
    ax.set_ylim(0, 103 if a.ci else 100)
    ax.set_yticks(range(0, 101, 25))
    ax.set_yticklabels([f"{v}%" for v in range(0, 101, 25)], fontsize=FS["tick"], color=MUTED)
    ax.set_ylabel("Self-escalation %", fontsize=FS["ylab"], color=INK)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    if nb > 1:
        fig.legend(handles=[Patch(facecolor=COLORS[s], label=t) for s, t in sel], loc="upper center",
                   bbox_to_anchor=(0.5, 0.995), ncol=3, frameon=False, fontsize=FS["leg"])
    fig.subplots_adjust(left=0.07, right=0.99, top=0.87, bottom=0.26)

    os.makedirs(a.out, exist_ok=True)
    name = ("self_escalation" if nb > 1 else f"self_escalation_{a.only}") + (f"_ci{a.ci}" if a.ci else "")
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(a.out, f"{name}.{ext}"), dpi=200, bbox_inches="tight")
    print(f"wrote {os.path.join(a.out, name)}.png/.pdf")
    for agent, _ in xs:
        print(f"  {LABEL[agent]:16s} " + "  ".join(
            f"{s}: {data[s].get(agent, {}).get('comp', 0)}/{data[s].get(agent, {}).get('n', 0)}" for s, _ in sel))


if __name__ == "__main__":
    main()
