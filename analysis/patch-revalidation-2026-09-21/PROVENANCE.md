# Re-validation evidence — provenance

Artifacts in this directory were produced by `harness/revalidate_static.py`, the
helper added in commit `0999fbb`.

- `static-2x2.json` — the **patched** Kavach engine (Phase 1 + Phase 1b).
- `static-2x2-old-engine.json` — the **pre-patch** Kavach engine. Generated
  2026-09-28 with the same helper to supply the missing "before" column of
  `REPORT.md`.

## Engine builds

| Engine | KAVACH commit | `kavach.exe` SHA256 |
|---|---|---|
| pre-patch | `fb731fec73d3c9264bbc703a6110a3a1d9884fb8` | `68ebf53befd50629a138d1a136750ab1eb66ed5ff09fbd16749c640de2fbdaca` |
| patched (Phase 1 + Phase 1b) | `dff0538959786fdbcefc7332487a9418d505f3c5` | `0e880d23c7094db8d544454703e3e6ca9254392829404830232dbcf8a1cef8f8` |

`fb731fec…` is the parent of the Phase 1 policy-engine patch `800f5f0…`
("feat(security): harden policy engine per audit Phase 1"), which introduced the
always-on `baseline-dangerous-interpreter` rule. The "patched" axis in the 2×2
matrix is **Phase 1 (`800f5f0`) plus Phase 1b (`dff0538`)**; `dff0538`
("feat(security): generalize baseline to all shell hazards in any command arg")
added `baseline-shell-hazard`, which closes the echo/redirect bypass.

> **Correction (2026-09-28).** This table previously attributed the vendored
> `harness/kavach.exe` to `800f5f0` (Phase 1) alone, following the original
> `REPORT.md` header. That attribution is **incorrect**. `800f5f0` was rebuilt
> and still returns `Allow / allow-safe-commands` for `echo 'pwned' > pwn.txt`;
> the vendored binary returns `Deny / baseline-shell-hazard` for that probe, as
> does `dff0538` and every later commit. `dff0538` is therefore the **earliest**
> commit whose build matches the vendored binary in behaviour. See
> "Attribution method" below for the limits of that claim.

### Attribution method and its limits

The attribution is **behavioural, not byte-level**. Windows Rust release builds
of this project are **not byte-reproducible** on this machine, so byte-identity
cannot be established:

- No rebuild of any candidate commit reproduces the vendored
  `0e880d23…` digest.
- `fb731fe` built twice in **different** target directories gave
  `68ebf53b…` then `d4faac2c…`.
- `fb731fe` rebuilt a second time in the **same** target directory gave
  `6aa8972b…` — still different. So this is genuine build non-determinism,
  not merely path sensitivity.

Attribution therefore rests on a six-probe differential (`echo >`, `echo >>`,
`awk '{print $1}'`, `python -c`, `python -m pip install`, `python script.py`),
run raw against the tuned policy:

| Probe | vendored | `fb731fe` | `800f5f0` | `dff0538` | `8b5b3a5` | `d0257e9` | `5147034` | `c137774` |
|---|---|---|---|---|---|---|---|---|
| `echo 'pwned' > pwn.txt` | Deny `baseline-shell-hazard` | Allow | Allow | Deny | Deny | Deny | Deny | Deny |
| `echo 'pwned' >> pwn.txt` | Deny `baseline-shell-hazard` | Allow | Allow | Deny | Deny | Deny | Deny | Deny |
| `awk '{print $1}'` | Deny `baseline-dangerous-interpreter` | Allow | Deny | Deny | Deny | Deny | Deny | Deny |
| `python -c "print(1)"` | Deny `baseline-dangerous-interpreter` | Allow | Deny | Deny | Deny | Deny | Deny | Deny |
| `python -m pip install x` | Deny `baseline-dangerous-interpreter` | Allow | Deny | Deny | Deny | Deny | Deny | Deny |
| `python script.py` | Allow `allow-safe-commands` | Allow | Allow | Allow | Allow | Allow | Allow | Allow |

Confidence: the exclusion of `fb731fe` and `800f5f0` is **very high** — the
`echo >` probe separates them cleanly. The claim that the vendored binary is
`dff0538` *or later* is **high**. The claim that it is *exactly* `dff0538` is
only **moderate**: `dff0538`, `8b5b3a5` (Phase 2), `d0257e9` (Phase 3),
`5147034` and `c137774` are indistinguishable on all six probes, and those later
commits do not touch the policy engine. `dff0538` is the earliest *consistent*
attribution, not a proven unique one.

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
