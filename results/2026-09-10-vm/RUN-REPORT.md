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
