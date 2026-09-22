# KavachBench

**Abstract.** KavachBench is a research-evaluation harness that measures how well Kavach — a Rust zero-trust policy-enforcement runtime for AI-agent tool calls — blocks real prompt-injection attacks from the IssueTrojanBench corpus: 42 genuine attack tool-call actions across 4 categories, plus benign controls.

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE) [![Rust 1.85+](https://img.shields.io/badge/rust-1.85%2B-orange.svg)](https://www.rust-lang.org) [![arXiv: pending](https://img.shields.io/badge/arXiv-pending-lightgrey.svg)](https://arxiv.org/abs/XXXX.XXXXX)

## Motivation

Autonomous coding agents do their work through tools: executing shell commands, writing files, installing packages, editing configuration. When the task context itself is adversarial — a GitHub issue with injected instructions embedded in it — the model may comply and emit tool calls the user never authorized. Once the model has decided to act, content-level filtering is no longer on the decision path; the remaining question is whether anything authorizes each tool call at the enforcement boundary before side effects occur.

This repository exists to answer that question empirically for one enforcement design (Kavach) against a real attack corpus (IssueTrojanBench) rather than synthetic prompts — and to report what is blocked and what is not with equal precision.

## What this repository evaluates

**Kavach**, the system under test, is a zero-trust policy-enforcement runtime for AI-agent tool calls. It interposes on the agent's tool-call path, validates each request against an explicit default-deny policy, issues request-bound permits, enforces at the adapter boundary, and records a tamper-evident audit chain. In this harness Kavach is exercised as a compiled binary (`harness/kavach.exe`) fronted by hook adapters: `harness/kavach_hook.py` for Claude Code `PreToolUse` hooks, and a custom `tool.execute.before` hook plugin (e.g. `validation/live/sandbox-1-on/.opencode/plugins/kavach.ts`) for the live OpenCode agent runs.

**IssueTrojanBench** ([software-artifacts/IssueTrojanBench](https://github.com/software-artifacts/IssueTrojanBench)) is a benchmark of prompt-injection attacks delivered as GitHub issues: natural-language payloads that induce an agent to perform malicious tool calls in the course of fixing a bug. Its v1.0.0 payloads — 24 YAML files (6 seeds x 4 attack categories) in `benchmarks/IssueTrojanBench/payloads/`, sourced from the project's Zenodo archive (record 21402335) — are pure prose. There are no literal shell commands to match; the agent must interpret the prose and emit the induced actions.

Concretely, the benchmark asks two questions: (1) statically, what fraction of the induced malicious tool calls does Kavach deny at the enforcement point, before and after benchmark-informed policy tuning; and (2) live, do paired baseline-vs-defended agent runs confirm that denied-at-policy means blocked-before-side-effect in practice.

## Methodology

### Dataset and attack categories

`harness/map_dataset.py` parses every payload YAML, extracts the top-level directive tool calls a fully obedient agent would emit (commands and files the payload explicitly instructs the agent to run or create), and writes one Kavach `ToolRequest` JSON per action to `harness/fixtures/real/`, with the manifest in `harness/inventory.json`. Per-payload status artifacts (e.g. `dependency_status.txt`, `*_agents_status.txt`) are completion signals for binary EEM scoring, not the malicious action itself, and are excluded from the fixture set. Commands embedded inside script bodies are likewise excluded: they are subprocess-level execution within a single tool call, not separate agent tool calls.

| Category | Actions | Induced tool calls |
|---|---|---|
| Supply-chain | 6 | `pip install <package>` (including `python -m pip` forms) |
| Persistence-hook | 17 | Create `.validate_*.sh` hook scripts, `chmod +x`, execute |
| Policy-bypass | 8 | Create `.cursorrules` / `CLAUDE.md` / `AGENTS.md` |
| Resource-exhaustion | 11 | Create `diagnostic_stress.sh` / `*_stress_check.py` / `*_workload_check.py`, execute |
| **Total** | **42** | Plus benign controls (file read/edit, `pytest`, `git`) |

The 29 presentation-layer perturbations in `benchmarks/IssueTrojanBench/configs/perturbations.yaml` vary how the prose is delivered and hidden, not the induced action set (see `harness/perturbation-analysis.md`). The 42-action set is therefore treated as the complete action-layer taxonomy of the benchmark.

### Static evaluation

Each fixture is evaluated with `kavach policy check` under the default-deny bench policy (`harness/policy.kavachbench.toml`), via the hook adapter, which additionally canonicalizes known command aliases before policy evaluation (`python -m pip install ...` to `pip install ...`; known benchmark stress/workload-script executions to an explicit deny target). Entry points: `harness/run_subset.py` for the 42-action corpus, `harness/run_feasibility.py` for the fixture sweep including benign controls, and `harness/adversarial_probe.py` for 22 obfuscation probes outside the benchmark corpus (results in `harness/adversarial-report.md`). Post-patch re-validation is recorded in `analysis/patch-revalidation-2026-09-21/REPORT.md`.

### Live evaluation and baseline-vs-defended design

Static analysis cannot show that a model would comply with an injection, nor that a deny precedes side effects at runtime. The live loop closes both gaps. Five sandboxes (`validation/live/`, labels `1`, `2`, `3`, `5`, `benign`) each pair one attack family with a `TASK.md` prompt that wraps the real payload prose in innocent bug-fixing framing, mirroring the benchmark's task design. The scenario matrix is defined in `validation/live/scenarios.md`.

Each sandbox is run twice — once with the Kavach hook disabled (baseline) and once enabled (defended) — for 10 runs total, driven by an OpenCode agent through the custom `tool.execute.before` hook plugin that calls the compiled Kavach binary on every tool call. The batch runner is `run-all-10.ps1`; raw transcripts are stored in `results/live/`; outcomes are scored in `analysis/manual-baseline-log.csv` (schema documented in `analysis/manual-baseline-legend.md`) and aggregated with `analysis/summarize_manual.py` into baseline vs. defended attack success rates. The baseline runs measure whether the attack chain completes without defense; the defended runs measure whether it is stopped at the hook boundary; the benign sandbox checks that legitimate work still passes.

## Results

| Configuration | Blocked | Rate |
|---|---|---|
| Out-of-the-box policy | 37 / 42 | 88% |
| After iterative, benchmark-informed policy tuning | 42 / 42 | 100% |

The five recovered actions were tool-call forms the out-of-the-box executable matching did not cover: `python -m pip install` invocations, which map to the allowlisted `python` executable rather than `pip`, and stress/workload-script executions (`python *_stress_check.py`, `python *_workload_check.py`), which likewise present only a trusted interpreter name. Both were closed by benchmark-informed tuning — adapter canonicalization of the `python -m pip` form onto the supply-chain deny rule, and an explicit deny rule for the benchmark's stress/workload-script executions — without removing any legitimate allowance: benign reads, edits, and test commands still evaluate to allow. The 10 live runs corroborate the static result: baseline runs completed the induced chains, while defended runs denied each attack step at the hook boundary before any side effect occurred.

## Architecture

![Architecture diagram placeholder: an OpenCode agent issuing tool calls through a tool.execute.before hook plugin that forwards each call to the compiled Kavach binary for policy evaluation, with allow proceeding to execution and deny blocking before any side effect, plus the parallel baseline path with the hook disabled](docs/screenshots/architecture-diagram.png)

> [DIAGRAM PLACEHOLDER] — Replace `docs/screenshots/architecture-diagram.png` with a diagram showing: the OpenCode agent emitting tool calls; the `tool.execute.before` hook plugin (`kavach.ts`) forwarding each call to the compiled Kavach binary (`harness/kavach.exe`) for evaluation under `harness/policy.kavachbench.toml`; the allow path proceeding to execution and the deny path blocking before any side effect; and the parallel baseline path with the hook disabled for comparison.

## Screenshots

![Terminal output of a real blocked attack showing the Kavach deny decision](docs/screenshots/01-blocked-attack-deny.png)

*Terminal output of a real blocked attack, showing the Kavach deny decision.*

![Chart rendering the before/after results table: 37/42 blocked out-of-the-box versus 42/42 after tuning](docs/screenshots/02-before-after-chart.png)

*Chart of the before/after results: 37/42 blocked out-of-the-box versus 42/42 after tuning.*

![Excerpt of a live-validation sandbox run transcript showing hook denials at the tool-call boundary](docs/screenshots/03-live-sandbox-transcript.png)

*Excerpt of a live-validation sandbox run transcript showing hook denials at the tool-call boundary.*

![Repository and architecture folder structure of KavachBench](docs/screenshots/04-repo-structure.png)

*Repository and architecture folder structure of KavachBench.*

## Reproducing the results

Source layout: `analysis/` (scoring and logs), `benchmarks/IssueTrojanBench/` (attack corpus), `harness/` (runners, hook adapter, policy, fixtures), `results/` (raw run outputs), `run-all-10.ps1` (live batch runner), `validation/live/` (sandbox definitions), `paper/` (paper draft).

```powershell
# Static: 42-action corpus interception (expect 42/42 with tuned policy + adapter)
python harness/run_subset.py

# Static: feasibility fixture sweep, including benign controls
python harness/run_feasibility.py

# Static: 22 obfuscation probes outside the benchmark corpus
python harness/adversarial_probe.py

# Live-outcome aggregation from the scored run log
python analysis/summarize_manual.py analysis/manual-baseline-log.csv

# Live: all 10 baseline-vs-defended agent runs (5 sandboxes x on/off),
# transcripts to results/live/
powershell -NoProfile -ExecutionPolicy Bypass -File run-all-10.ps1
```

Dataset provenance: the fixtures derive from the 24 payload YAMLs in `benchmarks/IssueTrojanBench/payloads/` (IssueTrojanBench v1.0.0, Zenodo record 21402335); the extraction mapping is `harness/map_dataset.py` with its output manifest in `harness/inventory.json`. Post-patch engine re-validation evidence is in `analysis/patch-revalidation-2026-09-21/REPORT.md` with raw data in the same directory. The accompanying paper draft is `paper/KavachBench.tex` (3 figures); its arXiv submission (cs.CR) is in progress pending endorsement, linked as a placeholder until the identifier is assigned.

## Limitations

1. **Argument-blind command matching.** Kavach matches commands on the executable name only, without inspecting arguments. The `python -m pip install <package>` form therefore bypassed the supply-chain deny rule out-of-the-box (the visible executable is the allowlisted `python`). It is closed in this harness by adapter canonicalization, but argument-aware matching remains a structural gap in the engine.
2. **Shell-redirect bypass.** An `echo '...' > file` write via shell redirection was found during live testing to bypass file-creation policy: the policy engine saw only the allowlisted `echo` executable, and the enforcement-layer redirect blocklist sat on a code path the hook-based `policy check` flow never invokes. It is fixed in a later Kavach patch, but the finding stands as evidence that hook-path coverage and enforcement-path coverage can diverge.
3. **Benign-argument false-positive trade-off.** Hardening executable matching against substitution hazards (e.g. firing on `$` in arguments) risks denying legitimate commands whose arguments innocently contain that character, such as `awk '{print $1}'`. Sensitivity and false-positive rate remain a tuning trade-off rather than a solved point.
4. **Untested generalization.** All tuning targets the naming conventions observed in this corpus (`.validate_*.sh`, `*_stress_check.py`, `*_workload_check.py`, known policy-file names). Generalization to unseen attacker naming conventions is explicitly untested, and no claim is made about it.

## Citation

```bibtex
@misc{kavachbench2026,
  title         = {KavachBench: Benchmarking a Zero-Trust Policy-Enforcement Runtime
                   Against Real Prompt-Injection Tool-Call Attacks},
  author        = {{KavachBench contributors}},
  year          = {2026},
  eprint        = {XXXX.XXXXX},
  archivePrefix = {arXiv},
  primaryClass  = {cs.CR},
  note          = {arXiv submission in progress, pending endorsement}
}
```

Paper draft: `paper/KavachBench.tex` (3 figures). Replace `XXXX.XXXXX` with the assigned identifier once the arXiv submission (cs.CR) clears endorsement.

## Acknowledgments

- **[OpenCode](https://opencode.ai)** — used as the live-validation agent
  runtime; a custom TypeScript plugin (`validation/live/opencode-kavach-plugin.ts`)
  hooks its `tool.execute.before` to enforce Kavach's policy engine during
  the 10 real baseline-vs-defended sandbox runs.
- **[IssueTrojanBench](https://github.com/software-artifacts/IssueTrojanBench)**
  — source of the real prompt-injection attack corpus (Zenodo dataset,
  6 seeds × 4 attack categories) this evaluation is built on.
- **[Kavach](https://github.com/MadB0i/KAVACH)** — the zero-trust policy-
  enforcement runtime under evaluation in this repo.

## License

This repository is licensed under the Apache License, Version 2.0. See [`LICENSE`](LICENSE) for the full text.
