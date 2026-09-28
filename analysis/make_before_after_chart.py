#!/usr/bin/env python3
"""Render docs/screenshots/02-before-after-chart.png from the re-validation
evidence.

Every plotted value is read from the per-run evidence files; nothing is typed
in by hand:

    analysis/patch-revalidation-2026-09-21/static-2x2.json             patched engine
    analysis/patch-revalidation-2026-09-21/static-2x2-old-engine.json  pre-patch engine

Usage:
    python analysis/make_before_after_chart.py
"""
import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE / "patch-revalidation-2026-09-21"
OUT = HERE.parent / "docs" / "screenshots" / "02-before-after-chart.png"

CELLS = ["untuned_raw", "untuned_canon", "tuned_raw", "tuned_canon"]
LABELS = ["untuned\nraw", "untuned\n+ adapter", "tuned\nraw", "tuned\n+ adapter"]
SERIES = [
    ("pre-patch engine", EVIDENCE / "static-2x2-old-engine.json", "#8d99ae"),
    ("patched engine", EVIDENCE / "static-2x2.json", "#2f7fbf"),
]


def load(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    summary = data["summary"]
    totals = {summary[c]["total"] for c in CELLS}
    assert len(totals) == 1, f"inconsistent totals in {path.name}: {totals}"
    return [summary[c]["blocked"] for c in CELLS], totals.pop()


def main():
    loaded = [(name, *load(path)) for name, path, _ in SERIES]
    total = loaded[0][2]
    assert all(vals[2] == total for vals in loaded), "total differs between engines"

    x = range(len(CELLS))
    width = 0.36

    fig, ax = plt.subplots(figsize=(12, 7.5), dpi=150)
    for i, (name, values, _) in enumerate(loaded):
        offset = (i - (len(loaded) - 1) / 2) * width
        pos = [p + offset for p in x]
        bars = ax.bar(pos, values, width, label=name, color=SERIES[i][2],
                      edgecolor="black", linewidth=1.1, zorder=3)
        for bar, v in zip(bars, values):
            ax.annotate(f"{v}/{total}\n({v / total:.0%})",
                        (bar.get_x() + bar.get_width() / 2, v),
                        textcoords="offset points", xytext=(0, 4),
                        ha="center", va="bottom", fontsize=11, zorder=4)

    ax.set_title("KavachBench: real attack actions blocked, by policy × adapter × engine",
                 fontsize=15, pad=46)
    ax.set_ylabel(f"Attack actions blocked (out of {total})", fontsize=12)
    ax.set_xlabel("Policy configuration and adapter canonicalization", fontsize=12)
    ax.set_xticks(list(x))
    ax.set_xticklabels(LABELS, fontsize=11)
    ax.set_ylim(0, total + 6)
    ax.set_yticks(range(0, total + 1, 5))
    ax.grid(axis="y", linestyle="--", alpha=0.55, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(frameon=False, fontsize=11, loc="lower center",
              bbox_to_anchor=(0.5, 1.005), ncol=len(loaded))

    fig.text(0.5, 0.015,
             f"All values read from {EVIDENCE.name}/static-2x2.json and "
             f"static-2x2-old-engine.json ({total} fixtures).",
             ha="center", fontsize=8.5, color="#444444")
    fig.tight_layout(rect=(0, 0.035, 1, 1))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT)
    print(f"wrote {OUT}")
    for name, values, _ in loaded:
        print(f"  {name:18} " + "  ".join(f"{c}={v}" for c, v in zip(CELLS, values)))


if __name__ == "__main__":
    main()
