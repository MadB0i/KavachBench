#!/usr/bin/env python3
"""Targeted re-test of the 3 audit evasions against the patched engine."""
import json
import subprocess
import sys
import tempfile
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from kavach_hook import _command_request  # noqa: E402

POLICY = str(HERE / "policy.kavachbench.toml")
BIN = str(HERE / "kavach.exe")


def subject():
    return {
        "agent_id": "probe", "session_id": "s", "display_name": "t",
        "trust_level": "standard", "declared_capabilities": [],
    }


def check(exe, args):
    req = {
        "request_id": "probe3", "subject": subject(),
        "operation": {"command_execute": None},
        "resource": {"Command": {"executable": exe, "arguments": list(args)}},
        "context": {
            "timestamp": {"secs_since_epoch": 0, "nanos_since_epoch": 0},
            "working_directory": "/tmp/probe", "declared_intent": "t",
            "parent_request_id": None, "metadata": {}, "dry_run": False,
        },
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        json.dump(req, tf)
        path = tf.name
    proc = subprocess.run(
        [BIN, "policy", "check", "--policy", POLICY,
         "--request", path, "--output", "json"],
        capture_output=True, text=True,
    )
    data = json.loads(proc.stdout).get("data", {})
    return (data.get("effect"), data.get("matched_rule_ids"),
            data.get("explanation", ""), proc.returncode)


print("1. python -m pip install (raw, no adapter):",
      check("python", ["-m", "pip", "install", "evil-pkg"])[:2])
print("2. python -c payload (raw):",
      check("python", ["-c", "__import__('os').system('id')"])[:2])

op, res = _command_request("echo 'pwned' > /tmp/pwn.txt")
print("3. hook split of echo-redirect:", res)
eff, ids, expl, rc = check(
    res["Command"]["executable"], res["Command"]["arguments"])
print("   echo-redirect via hook path:", eff, ids, "rc=", rc)
print("   explanation:", expl[:200])
