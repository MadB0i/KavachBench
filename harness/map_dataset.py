#!/usr/bin/env python3
"""Map IssueTrojanBench YAML payloads to Kavach ToolRequest fixtures.

Parses every payload YAML, extracts the tool-call actions the agent is
tricked into performing, and emits one Kavach ToolRequest JSON per action
into harness/fixtures/real/<seed>-<attack>-<action>.json.

Usage:
    python map_dataset.py --dump-summary   # print attack-action inventory
    python map_dataset.py                  # write fixture JSON files
"""
import argparse
import json
import os
import pathlib
import re
import time
import yaml

DATASET = pathlib.Path(__file__).resolve().parent.parent / "benchmarks" / "issuetrojanbench"
OUT = pathlib.Path(__file__).resolve().parent / "fixtures" / "real"
HERE = pathlib.Path(__file__).resolve().parent

SUBJECT = {
    "agent_id": "claude-code-bench",
    "session_id": "real-dataset-run",
    "display_name": "Claude Code (IssueTrojanBench)",
    "trust_level": "standard",
    "declared_capabilities": [],
}

# Tool-call inventory is built from the TOP-LEVEL directives only. The real
# payloads embed extra shell lines inside the script bodies they tell the agent
# to create (e.g. `os.system('chmod +x ...')`, `curl ...agent-telemetry-ping`,
# `pip install -r docs/requirements.txt`, `sphinx-build`, `pytest`). Those run
# inside the created script/_as subprocesses of a single Bash call_, not as
# separate agent tool calls, so they are deliberately NOT extracted here.

# ── Marker artifacts to exclude ──────────────────────────────────────────────
# These are EEM success indicators, written AFTER an attack prerequisite
# completes, not the malicious action itself.
_MARKER = re.compile(r"(?:status|dependency_status|_hook_status)", re.I)


def _clean_target(s):
    return s.strip().rstrip("'\".,;:") or None


def _extract_commands(text):
    """Top-level command directives the agent is told to run (kind, exe, args).

    Returns deduped list of (kind, executable, arguments). kinds:
      malicious_install  -> pip / pip via `python -m pip` (supply chain)
      chain_exec         -> chmod +x / run the hook script (persistence)
      exhaustion_exec    -> `python <script>.py` (resource exhaustion)
    """
    cmds = []
    # 1. Supply-chain installs. `python [-m] pip install <pkg>` variants in one
    #    pass so `python -m pip install x` is captured once, never double-counted
    #    as a bare `pip`. Only direct ONE-token installs count — option-bearing
    #    lines (e.g. `pip install -q -r docs/requirements.txt || true` inside a
    #    script body) are skipped as not-command-directives.
    for m in re.finditer(
        r"\b((?:python|python3)\s+-m\s+)?(pip|pip3)\s+install\s+([^\s\n;|&]+)", text
    ):
        prefix, raw, pkg = m.group(1), m.group(2), _clean_target(m.group(3))
        if not pkg or pkg.startswith("-"):
            continue
        if prefix:
            cmds.append(("malicious_install", "python", ["-m", "pip", "install", pkg]))
        else:
            cmds.append(("malicious_install", raw, ["install", pkg]))
    # 2. Top-level `chmod +x <hook>`. Skip the chmod that lives inside the
    #    script body (`python3 -c "... os.system('chmod +x ...') ..."`).
    for m in re.finditer(r"\bchmod\s+\+x\s+(\S+)", text):
        if "os.system" in text[max(0, m.start() - 40):m.start()]:
            continue
        fname = _clean_target(m.group(1))
        if fname and "." in fname and not _MARKER.search(fname):
            cmds.append(("chain_exec", "chmod", ["+x", fname]))
    # 3. Run the hook / stress bash script: `bash X.sh`, `sh X.sh`, `./X.sh`.
    #    A bare `.foo.sh` filename is NOT a run — only `./`-prefixed tokens are.
    for m in re.finditer(r"\b(?:bash|sh)\s+([^\s&|;\n]+\.sh)\b", text):
        fname = _clean_target(m.group(1).strip("./"))
        if fname:
            cmds.append(("chain_exec", "bash", ["./" + fname]))
    for m in re.finditer(r"\./(\.?[A-Za-z0-9_]+\.sh)\b", text):
        fname = _clean_target(m.group(1).strip("./"))
        if fname:
            cmds.append(("chain_exec", "bash", ["./" + fname]))
    # 4. Run a python diagnostic: `python <script>.py` (resource exhaustion exec).
    for m in re.finditer(r"\b(?:python|python3)\s+(?!-m\b)([A-Za-z0-9_./-]+\.py)\b", text):
        script = m.group(1).lstrip("./")
        if script and not _MARKER.search(script):
            cmds.append(("exhaustion_exec", "python", [script]))
    # dedupe preserving order
    seen, out = set(), []
    for kind, exe, args in cmds:
        key = (kind, exe, tuple(args))
        if key not in seen:
            seen.add(key)
            out.append((kind, exe, args))
    return out


def _extract_file_creates(text):
    """Top-level file_create targets (the malicious artifacts themselves)."""
    files = []
    # Persistence-hook scripts and resource-exhaustion diagnostic scripts.
    for pat in [
        r"\.validate_[A-Za-z0-9_]+\.sh",          # persistence hook files
        r"[A-Za-z0-9_]+_stress_check\.py",         # resource stress diagnostics
        r"[A-Za-z0-9_]+_workload_check\.py",       # resource workload diagnostics
        r"diagnostic_stress\.sh",                  # base fork bomb
    ]:
        for m in re.finditer(pat, text):
            fname = _clean_target(m.group(0))
            if fname and not _MARKER.search(fname):
                files.append(fname)
    # Policy-bypass files: CLAUDE.md / AGENTS.md / .cursorrules
    # (?<!\w) so a leading-dot filename in "(1) .cursorrules" / "named .cursorrules"
    # is captured (a \b before `\.` would fail because '.' is a non-word char).
    for m in re.finditer(r"(?<!\w)(?:CLAUDE\.md|AGENTS\.md|\.cursorrules)\b", text):
        files.append(m.group(0))
    return list(dict.fromkeys(files))   # dedupe, preserve order


def _action_label(kind, payload):
    slug = re.sub(r"[^a-zA-Z0-9_.]+", "-", payload)
    return f"{kind}-{slug}"


def parse_attack_actions(yaml_text):
    """Return list of (label, operation, resource) tuples for the induced
    tool calls a fully-obedient agent would make to complete the prerequisite."""
    actions = []
    for kind, exe, args in _extract_commands(yaml_text):
        label = _action_label(kind, f"{exe}-{' '.join(args)}")
        actions.append((label, {"command_execute": None},
                        {"Command": {"executable": exe, "arguments": args}}))
    for fname in _extract_file_creates(yaml_text):
        label = _action_label("malicious_artifact", fname)
        actions.append((label, {"file_create": None}, {"File": {"path": fname}}))
    return actions


# ── ToolRequest builder ──────────────────────────────────────────────────────

ACTION_ID = 0

def _next_id():
    global ACTION_ID
    ACTION_ID += 1
    return ACTION_ID


def _now():
    s = time.time()
    return {
        "secs_since_epoch": int(s),
        "nanos_since_epoch": int((s - int(s)) * 1_000_000_000),
    }


def build_request(action_label, operation, resource, attack_category, seed):
    return {
        "request_id": f"real-{seed}-{attack_category}-{action_label}-{_next_id():04d}",
        "subject": SUBJECT,
        "operation": operation,
        "resource": resource,
        "context": {
            "timestamp": _now(),
            "working_directory": f"/tmp/{seed}",
            "declared_intent": f"IssueTrojanBench {attack_category} ({seed})",
            "parent_request_id": None,
            "metadata": {"attack_category": attack_category, "seed": seed},
            "dry_run": False,
        },
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

def load_payloads():
    """Yield (seed, attack_category, yaml_text) for every payload file."""
    for path in sorted((DATASET / "payloads").glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        text = data.get("english", "")
        stem = path.stem
        # map filename to attack category
        if "supply_chain" in stem:
            attack = "supply_chain"
        elif "persistence_hook" in stem:
            attack = "persistence_hook"
        elif "policy_bypass" in stem:
            attack = "policy_bypass"
        elif "resource_exhaustion" in stem:
            attack = "resource_exhaustion"
        else:
            continue
        # derive seed name (drop attack prefix)
        seed = stem.replace(f"{attack}", "").strip("_") or "base"
        yield seed, attack, text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump-summary", action="store_true")
    args = parser.parse_args()
    summary = []
    manifest = []

    OUT.mkdir(parents=True, exist_ok=True)
    for seed, attack, text in load_payloads():
        actions = parse_attack_actions(text)
        if not actions:
            actions.append((
                "allow_only",
                {"command_execute": None},
                {"Command": {"executable": "echo", "arguments": ["no-op"]}},
            ))
        for label, op, res in actions:
            req = build_request(label, op, res, attack, seed)
            safe_label = re.sub(r"[^a-zA-Z0-9_\-]+", "_", label).strip("_")
            fname = f"{seed}-{attack}-{safe_label}.json"
            (OUT / fname).write_text(json.dumps(req, indent=2), encoding="utf-8")
            kind = label.split("-", 1)[0]
            summary.append((seed, attack, label, res, kind))
            manifest.append({
                "id": fname,
                "seed": seed,
                "attack": attack,
                "kind": kind,
                "label": label,
                "operation": next(iter(op)),
                "resource": res,
            })

    manifest.sort(key=lambda e: e["id"])
    (HERE / "inventory.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    if args.dump_summary:
        by_cat = {}
        for seed, attack, label, res, kind in summary:
            by_cat.setdefault(attack, []).append((seed, label, res, kind))
        for attack in sorted(by_cat):
            items = by_cat[attack]
            print(f"\n== {attack} ({len(items)} actions across seeds) ==")
            for seed, label, res, kind in items:
                if "Command" in res:
                    exe = res["Command"]["executable"]
                    a = res["Command"]["arguments"]
                    print(f"  [{kind:20s}] {seed:25s}  {exe} {' '.join(a)}")
                elif "File" in res:
                    print(f"  [{kind:20s}] {seed:25s}  write {res['File']['path']}")
        print(f"\nTotal fixtures written: {len(summary)} -> {OUT}/inventory.json")
    else:
        print(f"Wrote {len(summary)} ToolRequest fixtures to {OUT}")


if __name__ == "__main__":
    main()