# Extending IssueTrojanBench

## Adding a New Seed Issue

1. Create a new directory under `scripts/` named after the seed
2. Create all 6 vector scripts following the existing pattern
3. Create seed-specific payload YAML files in `payloads/`
4. Update the README seed issue table

## Adding a New Attack Category

1. Create payload YAML in `payloads/`
2. Add EEM criteria in `docs/EEM_CRITERIA.md`
3. Update verification logic

## Adding a New Delivery Vector

1. Create generator and issue-creator scripts
2. Add perturbation config to `configs/perturbations.yaml`

## Adding a New Agent-Model Pair

1. Add to `configs/config.template.yaml`
2. Document setup in `docs/EVALUATION_GUIDE.md`
