#!/usr/bin/env python3
"""Kavach Hook Adapter for Claude Code.

Claude Code invokes PreToolUse hooks before every tool call, passing a JSON
payload on stdin. This adapter translates that tool call into a Kavach
ToolRequest, runs `kavach policy check`, and blocks (denies) the tool call when
Kavach's default-deny policy says so.

Returns the Claude Code hook contract:
  - exit 0 + permissionDecision "allow"            -> let the tool call run
  - exit 2 + permissionDecision "deny"             -> block it (fail-closed)
  - exit 0 + permissionDecision "ask"              -> require_approval from Kavach

Env:
  KAVACH_BIN    path to the kavach CLI (default: ../KAVACH/target/release/kavach.exe)
  KAVACH_POLICY path to the policy TOML (default: policy.kavachbench.toml)

Usage (as a Claude Code PreToolUse hook):  kavach_hook.py  <  hook_payload.json
"""
import json
import os
import pathlib
import shlex
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
KAVACH_BIN = os.environ.get(
    "KAVACH_BIN",
    r"D:/Projects/KAVACH/target/release/kavach.exe",
)
KAVACH_POLICY = os.environ.get(
    "KAVACH_POLICY", str(HERE / "policy.kavachbench.toml")
)

# Claude Code Bash tool inputs carry a single `command` string.
_BASH_TOOLS = {"Bash"}

# Claude Code tools that create/overwrite a file at tool_input.file_path.
_WRITE_TOOLS = {"Write", "MultiEdit", "NotebookEdit"}
# Edit tools mutate an existing file.
_EDIT_TOOLS = {"Edit"}
_READ_TOOLS = {"Read"}


def _decision(decision, reason, message):
    """Emit the Claude Code hookSpecificOutput contract."""
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
            "permissionDecisionMessage": message,
        }
    }
    sys.stdout.write(json.dumps(out))


def _run_kavach(operation, resource):
    """Build a ToolRequest and call `kavach policy check`.

    Returns (allowed, effect) where effect is Allow / Deny / RequireApproval.
    """
    request = {
        "request_id": f"kavach-hook-{abs(hash(json.dumps(resource, sort_keys=True)))}",
        "subject": {
            "agent_id": "claude-code-bench",
            "session_id": os.environ.get("CLAUDE_SESSION_ID", "hook-session"),
            "display_name": "Claude Code (Kavach hook)",
            "trust_level": "standard",
            "declared_capabilities": [],
        },
        "operation": operation,
        "resource": resource,
        "context": {
            "timestamp": {"secs_since_epoch": 0, "nanos_since_epoch": 0},
            "working_directory": os.environ.get("CLAUDE_PROJECT_DIR"),
            "declared_intent": "Resolve reported issue (KavachBench)",
            "parent_request_id": None,
            "metadata": {},
            "dry_run": False,
        },
    }
    import tempfile

    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as tf:
        json.dump(request, tf)
        tmp_path = tf.name
    try:
        proc = subprocess.run(
            [
                KAVACH_BIN,
                "policy",
                "check",
                "--policy",
                KAVACH_POLICY,
                "--request",
                tmp_path,
                "--output",
                "json",
            ],
            capture_output=True,
            text=True,
        )
        data = json.loads(proc.stdout).get("data", {})
        return data.get("allowed"), data.get("effect")
    except Exception:
        return None, None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _command_request(command):
    """Split a shell command into executable + arguments for Kavach."""
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    executable = parts[0] if parts else ""
    arguments = parts[1:]
    return (
        {"command_execute": None},
        {"Command": {"executable": executable, "arguments": arguments}},
    )


def _file_request(operation, path):
    payload = None if operation != "file_read" else {}
    return ({operation: payload}, {"File": {"path": path}})


def map_tool_to_kavach(tool_name, tool_input):
    """Translate a Claude Code tool call into a Kavach (operation, resource).

    Returns None when the tool is not security-relevant (pass through).
    """
    if tool_name in _BASH_TOOLS:
        command = (tool_input or {}).get("command", "")
        if not command.strip():
            return None
        return _command_request(command)

    path = (tool_input or {}).get("file_path") or (tool_input or {}).get("path")
    if not path:
        return None

    if tool_name in _WRITE_TOOLS:
        return _file_request("file_create", path)
    if tool_name in _EDIT_TOOLS:
        return _file_request("file_write", path)
    if tool_name in _READ_TOOLS:
        return _file_request("file_read", path)
    return None


def main():
    payload = json.load(sys.stdin)
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    mapped = map_tool_to_kavach(tool_name, tool_input)

    if mapped is None:
        # Not security-relevant (or unparseable) -> allow, but log for audit.
        _decision("allow", "no-policy-subject", f"Tool '{tool_name}' not mapped")
        return 0

    operation, resource = mapped
    allowed, effect = _run_kavach(operation, resource)

    if allowed is None:
        _decision(
            "deny",
            "kavach-error",
            "Kavach policy check failed; failing closed (deny)",
        )
        return 2

    if effect == "Deny":
        _decision(
            "deny",
            "kavach-deny",
            f"Blocked by Kavach policy: {json.dumps(resource)}",
        )
        return 2
    if effect == "RequireApproval":
        _decision(
            "ask",
            "kavach-require-approval",
            "Kavach requires operator approval for this action",
        )
        return 0
    if allowed is True:
        _decision("allow", "kavach-allow", "Allowed by Kavach policy")
        return 0
    # Unrecognized effect / failed check -> fail closed.
    _decision(
        "deny",
        "kavach-error",
        "Kavach policy check failed; failing closed (deny)",
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
