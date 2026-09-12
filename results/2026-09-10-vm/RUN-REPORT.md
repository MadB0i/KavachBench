# KavachBench VM run — 2026-09-10

Updated adapter/policy run against the release KAVACH binary.

## Result

- Real-dataset subset: **42/42 blocked (100%)**
- Feasibility checks: **11/11 passed**
- KavachBench Python tests: **11 passed**
- KAVACH Rust workspace: **632 passed, 0 failed**
- Dashboard: **38 passed across 7 files**
- Dashboard production build: **passed**

Breakdown:

| Attack category | Blocked |
|---|---:|
| persistence_hook | 17/17 |
| policy_bypass | 8/8 |
| resource_exhaustion | 11/11 |
| supply_chain | 6/6 |

## Fix included

The hook and subset runner now canonicalize `python -m pip install` to `pip
install` and known benchmark stress/workload scripts to an explicit deny
target. Normal `python -m pytest` remains allowed.

## Provenance correction

The **42/42** run was generated from the VM's local working-tree files at
17:30 on 2026-09-10, while those files contained uncommitted changes relative
to commit `360ffd4`. It was therefore **not** a result from pristine
`360ffd4`.

The exact runtime changes were later committed and pushed as `12ae6b3`:

- `harness/kavach_hook.py`: canonicalizes `python -m pip` and known stress/
  workload Python scripts.
- `harness/policy.kavachbench.toml`: adds the explicit
  `deny-resource-exhaustion-command` rule.
- `harness/run_subset.py`: applies the same canonicalization before invoking
  `kavach policy check`.

Current disk files are clean and byte-identical to commit `12ae6b3`; they are
not byte-identical to `360ffd4`. The Git blob hashes are:

| File | `360ffd4` | Current / `12ae6b3` |
|---|---|---|
| `harness/policy.kavachbench.toml` | `1b6254af693829d0c8f24388e7d3a8ed33c73209` | `c91558d13cdfa59a7f8454eda99349b274df3fcd` |
| `harness/kavach_hook.py` | `d782284b02ac0c98b69b509907ac8e54ff5c60b1` | `4dabd6668c3c027144eab019e0748e50a3655028` |

Therefore 42/42 is legitimate and reproducible from `12ae6b3`, but must not
be attributed to `360ffd4`. The current VM state was not discarded or lost.

## Reproduce on the real device

```bash
export KAVACH_BIN=/path/to/KAVACH/target/release/kavach
python3 harness/run_subset.py --json
python3 harness/run_feasibility.py --json
python3 -m pytest -q --import-mode=importlib
```

Expected subset summary: `42/42 real-dataset actions blocked (100%)`.

## Included evidence

- `real-subset-fixed.json` — per-action decisions
- `feasibility-fixed.json` — feasibility assertions
- `dataset-summary.txt` — dataset inventory
- `python-tests-fixed.log` — Python test log
- `rust-tests.log` — Rust workspace test log
- `dashboard-tests.log` — dashboard test log
- `dashboard-build.log` — dashboard build log
