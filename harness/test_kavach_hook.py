#!/usr/bin/env python3
"""Regression tests for the Claude Code adapter.

These tests exercise request translation and hook decisions only. They do not
execute shell commands, install packages, or run benchmark payloads.
"""
import io
import json
import pathlib
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import kavach_hook  # noqa: E402


class KavachHookRegressionTests(unittest.TestCase):
    def run_hook(self, payload):
        output = io.StringIO()
        with patch.object(sys, "stdin", io.StringIO(json.dumps(payload))), \
                redirect_stdout(output):
            return kavach_hook.main(), json.loads(output.getvalue())

    def test_unmapped_tool_fails_closed(self):
        rc, result = self.run_hook(
            {"tool_name": "FutureTool", "tool_input": {"operation": "side-effect"}}
        )
        self.assertEqual(rc, 2)
        self.assertEqual(
            result["hookSpecificOutput"]["permissionDecision"], "deny"
        )
        self.assertEqual(
            result["hookSpecificOutput"]["permissionDecisionReason"],
            "unmapped-tool",
        )

    def test_powershell_is_mapped_to_command_policy(self):
        with patch.object(
            kavach_hook, "_run_kavach", return_value=(False, "Deny")
        ) as check:
            rc, result = self.run_hook(
                {"tool_name": "PowerShell", "tool_input": {"command": "Get-ChildItem"}}
            )
        self.assertEqual(rc, 2)
        check.assert_called_once()
        operation, resource = check.call_args.args
        self.assertEqual(operation, {"command_execute": None})
        self.assertEqual(resource["Command"]["executable"], "Get-ChildItem")
        self.assertEqual(
            result["hookSpecificOutput"]["permissionDecision"], "deny"
        )

    def test_windows_backslash_path_is_normalized_before_evaluation(self):
        with patch.object(
            kavach_hook, "_run_kavach", return_value=(True, "Allow")
        ):
            rc, result = self.run_hook(
                {
                    "tool_name": "Read",
                    "tool_input": {
                        "file_path": r"C:\KavachBench\sandbox-1\sympy\core\new.py"
                    },
                }
            )
        self.assertEqual(rc, 0)
        self.assertEqual(
            result["hookSpecificOutput"]["permissionDecision"], "allow"
        )

        with patch.object(
            kavach_hook, "_run_kavach", return_value=(True, "Allow")
        ) as check:
            self.run_hook(
                {
                    "tool_name": "Read",
                    "tool_input": {
                        "file_path": r"C:\KavachBench\sandbox-1\sympy\core\new.py"
                    },
                }
            )
        _, resource = check.call_args.args
        self.assertEqual(
            resource["File"]["path"],
            "C:/KavachBench/sandbox-1/sympy/core/new.py",
        )

    def test_python_module_pip_is_canonicalized_to_denied_pip(self):
        with patch.object(
            kavach_hook, "_run_kavach", return_value=(False, "Deny")
        ) as check:
            rc, result = self.run_hook(
                {
                    "tool_name": "Bash",
                    "tool_input": {
                        "command": "python -m pip install example-package"
                    },
                }
            )
        self.assertEqual(rc, 2)
        _, resource = check.call_args.args
        self.assertEqual(resource["Command"]["executable"], "pip")
        self.assertEqual(
            resource["Command"]["arguments"], ["install", "example-package"]
        )
        self.assertEqual(
            result["hookSpecificOutput"]["permissionDecision"], "deny"
        )


if __name__ == "__main__":
    unittest.main()
