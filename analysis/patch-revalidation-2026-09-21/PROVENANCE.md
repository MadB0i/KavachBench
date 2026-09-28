# Re-validation evidence — provenance

Artifacts in this directory were produced by `harness/revalidate_static.py`, the
helper added in commit `0999fbb`.

- `static-2x2.json` — the **patched** Kavach engine.
- `static-2x2-old-engine.json` — the **pre-patch** Kavach engine. Generated
  2026-09-28 with the same helper to supply the missing "before" column of
  `REPORT.md`.

## Engine builds

| Engine | KAVACH commit | `kavach.exe` SHA256 |
|---|---|---|
| pre-patch | `fb731fec73d3c9264bbc703a6110a3a1d9884fb8` | `68ebf53befd50629a138d1a136750ab1eb66ed5ff09fbd16749c640de2fbdaca` |
| patched | `800f5f092d886fd9fa4b2819cf5006fa6d50190c` | `0e880d23c7094db8d544454703e3e6ca9254392829404830232dbcf8a1cef8f8` |

`fb731fec…` is the parent of the Phase 1 policy-engine patch `800f5f0…`
("feat(security): harden policy engine per audit Phase 1"), which introduced the
always-on `baseline-dangerous-interpreter` rule.

The pre-patch binary was produced without modifying the KAVACH checkout: the
repository was cloned to a temporary directory, detached at `fb731fec…`, and
built with an external `--target-dir`.

## Policies

Both policy files are read from **KavachBench** git, not from KAVACH:

| Cell suffix | Policy | SHA256 |
|---|---|---|
| `untuned` | `12ae6b3^:harness/policy.kavachbench.toml` (before `deny-resource-exhaustion-command`) | `de8c16d03c9192cf779c7937362e608dbcb400b08956b6bb5aaf4dba71794bc2` |
| `tuned` | `HEAD:harness/policy.kavachbench.toml` | `496d387397f55c81934bf2aca03798bcd9ebcaa524397c0e8db20433fd8dfdef` |

`_raw` sends the committed fixture unmodified; `_canon` first applies
`harness/kavach_hook.py:_canonicalize_command_parts`.

## Reproducing

```powershell
# materialise the two policies
git show 12ae6b3^:harness/policy.kavachbench.toml > untuned.toml
git show HEAD:harness/policy.kavachbench.toml        > tuned.toml

# pre-patch engine (clone KAVACH elsewhere, detach at fb731fec, build)
$env:KAVACH_BIN = '<old>/kavach.exe'
python harness/revalidate_static.py `
  --out analysis/patch-revalidation-2026-09-21/static-2x2-old-engine.json `
  --untuned-policy untuned.toml --tuned-policy tuned.toml

# patched engine (the committed default)
$env:KAVACH_BIN = 'harness/kavach.exe'
python harness/revalidate_static.py --out <somewhere>.json `
  --untuned-policy untuned.toml --tuned-policy tuned.toml
```

Running the patched configuration reproduces the committed `static-2x2.json`
(37/42, 42/42, 37/42, 42/42).
