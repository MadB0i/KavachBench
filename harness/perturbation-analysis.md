# Perturbation Analysis — IssueTrojanBench

**Date:** 2026-09-07
**Repo:** `D:/Projects/KavachBench`

## What the 29 perturbations actually vary

IssueTrojanBench ships 6 delivery vectors, each with a set of perturbation
configurations. The authoritative source is
[`benchmarks/IssueTrojanBench/configs/perturbations.yaml`](../benchmarks/IssueTrojanBench/configs/perturbations.yaml).

### Delivery vectors and perturbation counts

| Delivery vector | Count | Description |
|---|---|---|
| `pdf` | 6 | Payload rendered in a PDF via ReportLab |
| `website` | 6 | Payload embedded in HTML via white-on-white CSS |
| `source_code` | 5 | Payload as `#`-prefixed comments in a `.py` script |
| `github_issue` | 6 | Payload in GitHub issue body Markdown |
| `issue_comment` | 3 | Payload in a GitHub issue comment |
| `image_alttext` | 3 | Payload in Markdown `![alt](url)` alt-text |
| **Total** | **29** | |

### Variation axes (5)

| Axis | Values | Effect on action layer |
|---|---|---|
| `position` | top / middle / bottom | None — placement in document, not command set |
| `language` | english / chinese | None — Chinese payloads are literal translations; file paths and command tokens are identical |
| `caps` | normal / allcaps | None — `.upper()` of the prose text; `pip` becomes `PIP`, etc., but the agent interprets the prose and generates the same canonical commands |
| `color` | white-on-white (constant) | None — visual hiding only |
| `size` | normal (11pt) / 1pt | None — font size hiding only |
| `embedding` | html_comment / visible | None — wrapper hides vs reveals the same text |

### Scale arithmetic

```
Artifacts per attack:  29 (perturbation configs)
Attacks:               4 (supply_chain, persistence_hook, policy_bypass, resource_exhaustion)
Seeds:                 6 (sympy_matrix_det, riemann_theta, hnf, requests_l10n,
                          requests_multipart, requests_json_typing)
Per seed:              29 × 4 = 116
Total:                 116 × 6 = 696
```

> **Note:** `perturbations.yaml` line 45 says "Total across 5 seeds: 580
> artifacts" — this is stale. The benchmark has 6 seeds (confirmed by the
> evaluation guide and all 6 seed directories in `scripts/`), giving 696.

### What is NOT varied

Examining the payload YAMLs and the generation scripts confirms the following
are **held constant** across all 29 configurations within a given attack:

- **Command content:** the malicious instructions are always the same
  natural-language prose (e.g. "Mandatory Prerequisite … pip install X").
  No base64 encoding, hex encoding, command splitting, env-var indirection,
  heredocs, or alternate shell syntax (e.g. `curl` vs `wget`).
- **File targets:** the same file names appear regardless of perturbation
  (`.validate_*.sh`, `CLAUDE.md`, `*_stress_check.py`, etc.).
- **Language variants:** the Chinese payloads are straightforward translations;
  the command names, file paths, and technical identifiers remain identical.
- **Allcaps variant:** simply `str.upper()` — cosmetic, not semantic.

---

## Verdict: all perturbations are presentation-layer

Every perturbation operates in two dimensions:

1. **Where and how the payload is visually hidden** (position within a
   document, font size, HTML comment vs visible text, white-on-white color).
2. **Cosmetic text transformations** (language translation to Chinese,
   uppercasing).

These test whether the *agent's model* parses hidden or low-salience text
and obeys the injection — a **model-susceptibility** property measured by
EEM (Exploit Execution Metric) during live agent runs. They are **not**
policy-coverage variations.

Kavach's interception point is the *action layer*: every IssueTrojanBench
attack induces the same set of `file_create` / `command_execute` tool calls
regardless of which perturbation delivered the prose. Kavach's hook adapter
sees the tool call (not the prose), so the 29-perturbation matrix adds
**zero new action-layer coverage** beyond what the 42-action set already
covers.

---

## Action-layer completeness justification

Because the induced action-footprint is invariant across all 29 perturbations:

- The **42 genuine actions** extracted from the **24 payloads** (6 seeds ×
  4 attack categories) are the **complete action-layer taxonomy** of
  IssueTrojanBench.
- The static interception results — 35/42 (83%) policy-only, 37/42 (88%)
  with adapter, 24/24 (100%) run-level neutralization — hold for all 696
  runs. A run that uses perturbation `pdf_top_english_normal` exercises the
  *same Kavach deny rules* as `github_issue_bottom_chinese_html_comment`.
- The full 696-run matrix is still required for the **model-susceptibility**
  comparison (baseline EEM vs Kavach-defended EEM across all perturbation
  variants), but it does not add interception coverage.

This distinction is important for the paper: the 696-run measures
*whether the model obeys differently-presented injections*; the 42-action
static analysis measures *whether Kavach blocks the resulting tool calls*.
Both are needed; they answer different questions.

## See also

- [adversarial-report.md](adversarial-report.md) — extended obfuscation
  probe (not part of IssueTrojanBench) that empirically exposes Kavach's
  exact-string matching limits.
- [feasibility-notes.md](feasibility-notes.md) — Part B interception
  results and policy-scope analysis.
