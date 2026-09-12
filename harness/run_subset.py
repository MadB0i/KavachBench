#!/usr/bin/env python3
"""Run the real-dataset ToolRequest fixtures through the Kavach policy
check path and summarize interception rates by attack category.

The fixtures in fixtures/real/ are already Kavach ToolRequests (built by
map_dataset.py). The runner applies the same command canonicalization as the
PreToolUse hook before invoking the CLI, so it measures adapter behavior while
retaining machine-readable ToolRequest fixtures.

Usage:
    python run_subset.py          # print summary
    python run_subset.py --json   # machine-readable
"""
import argparse
import json
import os
import pathlib
import subprocess
import tempfile

from kavach_hook import _canonicalize_command_parts

HERE = pathlib.Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "real"
KAVACH_BIN = os.environ.get(
    "KAVACH_BIN", r"D:/Projects/KAVACH/target/release/kavach.exe"
)
KAVACH_POLICY = os.environ.get(
    "KAVACH_POLICY", str(HERE / "policy.kavachbench.toml")
)


def run_fixture(path):
    request_path = path
    temp_path = None
    try:
        request = json.loads(path.read_text(encoding="utf-8"))
        command = request.get("resource", {}).get("Command")
        if command:
            executable, arguments = _canonicalize_command_parts(
                command.get("executable", ""), command.get("arguments", [])
            )
            if (
                executable != command.get("executable")
                or arguments != command.get("arguments", [])
            ):
                request["resource"]["Command"] = {
                    "executable": executable,
                    "arguments": arguments,
                }
                with tempfile.NamedTemporaryFile(
                    "w", suffix=".json", delete=False, encoding="utf-8"
                ) as tf:
                    json.dump(request, tf)
                    temp_path = pathlib.Path(tf.name)
                request_path = temp_path

        proc = subprocess.run(
            [
                KAVACH_BIN,
                "policy",
                "check",
                "--policy",
                KAVACH_POLICY,
                "--request",
                str(request_path),
                "--output",
                "json",
            ],
            capture_output=True,
            text=True,
        )
    finally:
        if temp_path:
            try:
                temp_path.unlink()
            except OSError:
                pass
    try:
        data = json.loads(proc.stdout).get("data", {})
        allowed = data.get("allowed")
        effect = data.get("effect")
    except Exception:
        return "error", "unparseable"
    if effect == "Deny" or allowed is False:
        return "deny", effect
    if effect == "RequireApproval":
        return "ask", effect
    if allowed is True:
        return "allow", effect
    return "error", f"allowed={allowed} effect={effect}"


def classify_attack(stem):
    for a in ["supply_chain", "persistence_hook", "policy_bypass", "resource_exhaustion"]:
        if a in stem:
            return a
    return "unknown"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = []
    for path in sorted(FIXTURES.glob("*.json")):
        decision, reason = run_fixture(path)
        stem = path.stem
        results.append({
            "id": stem,
            "attack": classify_attack(stem),
            "decision": decision,
            "reason": reason,
        })

    if args.json:
        print(json.dumps(results, indent=2))
        return

    by_attack = {}
    for r in results:
        by_attack.setdefault(r["attack"], []).append(r)

    total = 0
    total_denied = 0
    for attack in sorted(by_attack):
        items = by_attack[attack]
        denied = sum(1 for r in items if r["decision"] == "deny")
        allow = sum(1 for r in items if r["decision"] == "allow")
        ask = sum(1 for r in items if r["decision"] == "ask")
        total += len(items)
        total_denied += denied
        print(f"\n  {attack:25s}  blocked={denied}/{len(items):<3}  allow={allow}  ask={ask}")
        for r in items:
            tag = "BLOCKED" if r["decision"] == "deny" else ("ASK" if r["decision"] == "ask" else "PASSED")
            print(f"    [{tag:8s}] {r['id']}")

    print(f"\n  SUMMARY: {total_denied}/{total} real-dataset actions blocked "
          f"({100*total_denied/total:.0f}%)")


if __name__ == "__main__":
    main()
