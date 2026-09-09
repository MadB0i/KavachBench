#!/usr/bin/env python3
"""Verify and record Kavach state before a live validation run.

This performs infrastructure checks only. It does not send a tool request to
Kavach and does not execute any benchmark payload.

Usage:
    python validation/live/verify_kavach_state.py --sandbox 1 --state on --run-id r1
    python validation/live/verify_kavach_state.py --sandbox 1 --state off --run-id r1
"""
import argparse
import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone


HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hook_is_enabled(settings_path):
    if not settings_path.exists():
        return False
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    for entry in settings.get("hooks", {}).get("PreToolUse", []):
        for hook in entry.get("hooks", []):
            command = str(hook.get("command", ""))
            if hook.get("type") == "command" and "kavach_hook.py" in command:
                return True
    return False


def verify(state, sandbox, run_id, log_path):
    harness = REPO_ROOT / "harness"
    kavach_bin = harness / "kavach.exe"
    policy = harness / "policy.kavachbench.toml"
    settings = sandbox / ".claude" / "settings.json"
    settings_off = sandbox / ".claude" / "settings.json.off"

    binary_exists = kavach_bin.is_file()
    policy_exists = policy.is_file()
    hook_enabled = hook_is_enabled(settings)
    active_settings_present = settings.exists()

    if state == "on":
        state_ok = binary_exists and policy_exists and hook_enabled
        observed_state = "on" if hook_enabled else "off_or_invalid"
    else:
        state_ok = binary_exists and policy_exists and not active_settings_present
        observed_state = "off" if not active_settings_present else "on_or_invalid"

    result = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "expected_state": state,
        "observed_state": observed_state,
        "ok": state_ok,
        "sandbox": str(sandbox),
        "settings_present": active_settings_present,
        "settings_off_present": settings_off.exists(),
        "hook_enabled": hook_enabled,
        "kavach_binary": str(kavach_bin),
        "kavach_binary_present": binary_exists,
        "kavach_binary_hash": sha256(kavach_bin) if binary_exists else None,
        "policy": str(policy),
        "policy_present": policy_exists,
        "policy_hash": sha256(policy) if policy_exists else None,
    }

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(result, sort_keys=True) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sandbox", required=True, help="Sandbox number or path")
    parser.add_argument("--state", required=True, choices=("on", "off"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--log",
        type=pathlib.Path,
        default=HERE / "kavach-state-log.jsonl",
    )
    args = parser.parse_args()

    sandbox = pathlib.Path(args.sandbox)
    if not sandbox.is_absolute():
        sandbox = HERE / (args.sandbox if args.sandbox.startswith("sandbox-") else f"sandbox-{args.sandbox}")

    result = verify(args.state, sandbox, args.run_id, args.log)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["ok"]:
        print("Kavach state verification failed; do not start the live run.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
