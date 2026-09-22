#!/usr/bin/env python3
"""Post-patch re-validation static runs (Phase 1 fixes).

Runs all 42 real-dataset fixtures through `kavach policy check` in a
2x2 matrix: {untuned, tuned} policy x {raw, adapter-canonicalized}
requests. Records effect + matched_rule_ids per fixture as JSON.

Usage:
    python revalidate_static.py --out <results.json>
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "real"
KAVACH_BIN = os.environ.get("KAVACH_BIN", str(HERE / "kavach.exe"))

sys.path.insert(0, str(HERE))
from kavach_hook import _canonicalize_command_parts


def check(policy_path, request_dict):
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as tf:
        json.dump(request_dict, tf)
        tmp = tf.name
    try:
        proc = subprocess.run(
            [KAVACH_BIN, "policy", "check", "--policy", str(policy_path),
             "--request", tmp, "--output", "json"],
            capture_output=True, text=True,
        )
        try:
            data = json.loads(proc.stdout).get("data", {})
            return {
                "effect": data.get("effect"),
                "allowed": data.get("allowed"),
                "matched_rule_ids": data.get("matched_rule_ids", []),
                "explanation": data.get("explanation", ""),
            }
        except Exception:
            return {"effect": "error", "stderr": proc.stderr.strip()[:200]}
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--untuned-policy", required=True)
    parser.add_argument("--tuned-policy", required=True)
    args = parser.parse_args()

    policies = {"untuned": args.untuned_policy, "tuned": args.tuned_policy}
    results = []
    for path in sorted(FIXTURES.glob("*.json")):
        base = json.loads(path.read_text(encoding="utf-8"))
        entry = {"id": path.stem}
        for pname, ppath in policies.items():
            # raw: fixture as-is
            entry[f"{pname}_raw"] = check(ppath, base)
            # canonicalized: adapter rewrite applied
            canon = json.loads(path.read_text(encoding="utf-8"))
            command = canon.get("resource", {}).get("Command")
            if command:
                exe, cargs = _canonicalize_command_parts(
                    command.get("executable", ""), command.get("arguments", [])
                )
                canon["resource"]["Command"] = {
                    "executable": exe, "arguments": cargs}
            entry[f"{pname}_canon"] = check(ppath, canon)
        results.append(entry)

    summary = {}
    for col in ["untuned_raw", "untuned_canon", "tuned_raw", "tuned_canon"]:
        blocked = sum(1 for r in results if r[col].get("effect") == "Deny")
        summary[col] = {"blocked": blocked, "total": len(results)}

    out = {"summary": summary, "fixtures": results}
    pathlib.Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")

    for col, s in summary.items():
        print(f"  {col:15s} blocked={s['blocked']}/{s['total']}")
    # Which fixtures differ between raw and canon on tuned policy?
    print("\n  tuned raw-vs-canon differences (baseline/adapter attribution):")
    for r in results:
        a, b = r["tuned_raw"], r["tuned_canon"]
        if (a.get("effect") != b.get("effect")
                or a.get("matched_rule_ids") != b.get("matched_rule_ids")):
            print(f"    {r['id']}")
            print(f"      raw:   {a.get('effect')} {a.get('matched_rule_ids')}")
            print(f"      canon: {b.get('effect')} {b.get('matched_rule_ids')}")
    print("\n  untuned canon: rules that fired (explicit vs default):")
    from collections import Counter
    c = Counter()
    for r in results:
        for rid in r["untuned_canon"].get("matched_rule_ids", []):
            c[rid] += 1
    if not any(r["untuned_canon"].get("matched_rule_ids") for r in results):
        print("    (all default-deny)")
    for rid, n in c.most_common():
        print(f"    {rid}: {n}")


if __name__ == "__main__":
    main()
