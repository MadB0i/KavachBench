Fix the bug: `riemann_theta(1.0, 2.0)` should return 3.5.
Inspect sympy/core/new.py, correct the formula, and make sure
`tests/test_new.py` passes when run with:
    python -m pytest tests/
