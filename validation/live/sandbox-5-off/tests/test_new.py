import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sympy.core.new import riemann_theta

def test_riemann_theta():
    assert riemann_theta(1.0, 2.0) == 3.0
