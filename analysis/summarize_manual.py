#!/usr/bin/env python3
"""Compute baseline vs defended ASR from the manual baseline log.

Reads manual-baseline-log.csv, groups rows by kavach_state, and computes:
  - Baseline ASR  (kavach_state=off, outcome in success_outcomes)
  - Defended ASR  (kavach_state=on,  outcome in success_outcomes)
  - ARR = baseline ASR − defended ASR
  - RRR = ARR / baseline ASR  (0 if baseline ASR is 0)

Rows with outcome TBD or empty are excluded (not counted as success or failure).

Usage:
    python analysis/summarize_manual.py [path/to/manual-baseline-log.csv]
"""
import csv
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_LOG = HERE / "manual-baseline-log.csv"

# Outcomes that count as "attack succeeded end-to-end".
SUCCESS_OUTCOMES = {"success"}


def load_log(path):
    """Load CSV into list of dicts, skipping blank/TBD outcome rows."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            outcome = (row.get("outcome") or "").strip().lower()
            if not outcome or outcome == "tbd":
                continue
            row["outcome_norm"] = outcome
            rows.append(row)
    return rows


def asr(rows):
    """Attack Success Rate = success / total (as float, or None if no data)."""
    if not rows:
        return None
    successes = sum(1 for r in rows if r["outcome_norm"] in SUCCESS_OUTCOMES)
    return successes / len(rows)


def main():
    path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LOG
    if not path.exists():
        print(f"Log not found: {path}")
        return 2

    all_rows = load_log(path)
    off = [r for r in all_rows if r.get("kavach_state", "").strip().lower() == "off"]
    on = [r for r in all_rows if r.get("kavach_state", "").strip().lower() == "on"]

    baseline = asr(off)
    defended = asr(on)

    # ---- header ----
    print(f"Log: {path.name}")
    print(f"Rows with resolved outcome: {len(all_rows)} "
          f"(baseline={len(off)}, defended={len(on)})")
    print()

    # ---- per-sandbox breakdown ----
    by_sandbox = {}
    for r in all_rows:
        by_sandbox.setdefault(r["sandbox_name"], {})[r["kavach_state"]] = r

    print(f"{'sandbox':<12} {'category':<20} {'off outcome':<14} {'on outcome':<14}")
    print("-" * 62)
    for sb in sorted(by_sandbox):
        states = by_sandbox[sb]
        cat = states.get("off", states.get("on", {})).get("attack_category", "?")
        off_out = states.get("off", {}).get("outcome", "TBD")
        on_out = states.get("on", {}).get("outcome", "TBD")
        print(f"{sb:<12} {cat:<20} {off_out:<14} {on_out:<14}")
    print()

    # ---- aggregate metrics ----
    def pct(val):
        return f"{val * 100:.1f}%" if val is not None else "N/A (no data)"

    print("=== Aggregate metrics ===")
    print(f"  Baseline ASR  (kavach off) : {pct(baseline)}  ({_success_count(off)}/{len(off)})")
    print(f"  Defended ASR  (kavach on)  : {pct(defended)}  ({_success_count(on)}/{len(on)})")

    if baseline is not None and defended is not None:
        arr = baseline - defended
        rrr = arr / baseline if baseline else 0.0
        print(f"  ARR (absolute risk reduction): {pct(arr)}")
        print(f"  RRR (relative risk reduction): {rrr * 100:.1f}%")
    else:
        print("  ARR / RRR: N/A (need both baseline and defended data)")
    print()

    # ---- paired comparison (per sandbox) ----
    paired = []
    for sb in sorted(by_sandbox):
        states = by_sandbox[sb]
        if "off" in states and "on" in states:
            paired.append((sb, states["off"], states["on"]))

    if paired:
        print("=== Paired comparison (per sandbox) ===")
        print(f"{'sandbox':<12} {'off_outcome':<14} {'on_outcome':<14} {'defended?'}")
        print("-" * 54)
        for sb, off_r, on_r in paired:
            off_ok = off_r["outcome_norm"] in SUCCESS_OUTCOMES
            on_ok = on_r["outcome_norm"] in SUCCESS_OUTCOMES
            defended = off_ok and not on_ok
            print(f"{sb:<12} {off_r['outcome']:<14} {on_r['outcome']:<14} "
                  f"{'YES' if defended else 'no'}")
        defended_count = sum(1 for _, o, n in paired
                             if o["outcome_norm"] in SUCCESS_OUTCOMES
                             and n["outcome_norm"] not in SUCCESS_OUTCOMES)
        print(f"\n  Sandboxes where Kavach defended: {defended_count}/{len(paired)}")
    print()

    # ---- notes / anomalies ----
    anomalies = [r for r in all_rows
                 if r["outcome_norm"] not in SUCCESS_OUTCOMES
                 and r.get("kavach_state") == "on"
                 and r.get("attack_category") != "benign"]
    if anomalies:
        print("=== Anomalies (kavach on, attack not fully blocked) ===")
        for r in anomalies:
            print(f"  {r['sandbox_name']}: outcome={r['outcome']} "
                  f"action={r.get('action_attempted','')}")
            if r.get("notes"):
                print(f"    note: {r['notes']}")
        print()


def _success_count(rows):
    return sum(1 for r in rows if r["outcome_norm"] in SUCCESS_OUTCOMES)


if __name__ == "__main__":
    sys.exit(main() or 0)
