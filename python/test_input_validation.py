"""Contract: SceneBuilder refuses a malformed leaf, transform, instance, query point, lattice or quadrature.

Validation lives in the binding (python/geom_bindings_checks.hpp, used from python/geom_bindings.cpp);
the ValueError names the call, the parameter, the admissible range with its dimension and the
offending value. Each validated argument is covered twice: every bad value raises ValueError naming
the parameter, and a valid call still runs.

Run: PYTHONPATH=<python build tree> python -m pytest -q python/test_input_validation.py
"""
import math
import re

import numpy as np
import pytest
from peclet import geom

NAN, INF = math.nan, math.inf
LO, HI = [-0.6] * 3, [0.6] * 3


def _scene():
    s = geom.SceneBuilder()
    a = s.add_leaf("sphere", [0.5])
    b = s.add_leaf("box", [0.3, 0.2, 0.4])
    return s, a, b


def _raises(call, text):
    with pytest.raises(ValueError, match=re.escape(text)):
        call()


# --- add_leaf ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind, params, text", [
    ("sphere", [], "params must be 1 value [r] for kind 'sphere', got 0"),
    ("sphere", [0.5, 1.0], "params must be 1 value [r] for kind 'sphere', got 2"),
    ("sphere", [0.5] * 9, "params must be 1 value [r]"),
    ("box", [0.3], "params must be 3 values [hx, hy, hz] for kind 'box', got 1"),
    ("superquadric", [1, 1, 1], "params must be 4 values [rx, ry, rz, e]"),
    ("sphere", [NAN], "params[0] must be finite and >= 0 (length units)"),
    ("sphere", [INF], "params[0] must be finite and >= 0"),
    ("box", [0.3, -0.2, 0.4], "params[1] must be finite and >= 0 (length units), got -0.2"),
    ("superquadric", [1, 1, 1, 0], "params[3] must be finite and > 0 (dimensionless), got 0"),
    ("superquadric", [1, 1, 1, -2], "params[3] must be finite and > 0"),
])
def test_add_leaf_params_refused(kind, params, text):
    _raises(lambda: geom.SceneBuilder().add_leaf(kind, params), f"SceneBuilder.add_leaf: {text}")


@pytest.mark.parametrize("kind, params", [
    ("sphere", [0.5]), ("sphere", [0.0]), ("box", [0.3, 0.2, 0.4]),
    ("hollow_cylinder", [1.0, 2.0, 0.1]), ("hollow_cylinder_shell", [1.0, 0.8, 2.0]),
    ("capsule", [0.2, 0.0]), ("torus", [1.0, 0.2]), ("cone", [0.5, 0.0, 1.0]),
    ("ellipsoid", [1.0, 0.5, 0.25]), ("superquadric", [1.0, 1.0, 1.0, 0.3])])
def test_add_leaf_params_accepted(kind, params):
    assert geom.SceneBuilder().add_leaf(kind, params) == 0


# Bad transforms, shared by every call that takes one.
BAD_TRANSFORM = [
    ({"translation": [NAN, 0, 0]}, "translation[0] must be finite (length units)"),
    ({"translation": [0, -INF, 0]}, "translation[1] must be finite"),
    ({"rotation": [0, 0, 0, 0]}, "|rotation| must be 1 within 1e-3"),
    ({"rotation": [0, 0, 0, 2]}, "|rotation| must be 1 within 1e-3"),
    ({"rotation": [NAN, 0, 0, 1]}, "rotation[0] must be finite"),
    ({"rotation": [0, 0, INF, 1]}, "rotation[2] must be finite"),
    ({"scale": 0.0}, "scale must be finite and > 0 (dimensionless), got 0"),
    ({"scale": -1.0}, "scale must be finite and > 0"),
    ({"scale": NAN}, "scale must be finite and > 0"),
    ({"scale": INF}, "scale must be finite and > 0"),
]
GOOD_TRANSFORM = {"translation": [1.0, -2.0, 3.0], "rotation": [0.0, 0.0, 0.7071, 0.7071], "scale": 2.5}


def _with_transform(s, a, b, call, kw):
    if call == "add_leaf":
        return s.add_leaf("sphere", [0.5], **kw)
    if call == "add_reframed":
        return s.add_reframed(a, **kw)
    if call == "add_instance":
        return s.add_instance(a, **kw)
    return getattr(s, call)(a, b, **kw)


TRANSFORM_CALLS = ["add_leaf", "add_union", "add_intersection", "add_difference", "add_reframed",
                   "add_instance"]


@pytest.mark.parametrize("call", TRANSFORM_CALLS)
@pytest.mark.parametrize("kw, text", BAD_TRANSFORM)
def test_transform_refused(call, kw, text):
    s, a, b = _scene()
    _raises(lambda: _with_transform(s, a, b, call, kw), f"SceneBuilder.{call}: {text}")


@pytest.mark.parametrize("call", TRANSFORM_CALLS)
def test_transform_accepted(call):
    s, a, b = _scene()
    assert _with_transform(s, a, b, call, GOOD_TRANSFORM) >= 0


# --- add_instance -----------------------------------------------------------------------------------

@pytest.mark.parametrize("kw, text", [
    ({"lin_vel": [NAN, 0, 0]}, "lin_vel[0] must be finite (length/time units)"),
    ({"ang_vel": [0, INF, 0]}, "ang_vel[1] must be finite (1/time units)"),
    ({"center": [INF, 0, 0]}, "center[0] must be finite (length units; or all three NaN"),
    ({"center": [NAN, 0, 0]}, "center[0] must be finite"),
    ({"center": [0, 0, NAN]}, "center[2] must be finite"),
])
def test_add_instance_refused(kw, text):
    s, a, _ = _scene()
    _raises(lambda: s.add_instance(a, **kw), f"SceneBuilder.add_instance: {text}")


@pytest.mark.parametrize("kw", [{}, {"center": [0.0, 0.0, 0.0]}, {"center": [NAN] * 3},
                                {"lin_vel": [1, 0, 0], "ang_vel": [0, 2, 0], "material": -3}])
def test_add_instance_accepted(kw):
    s, a, _ = _scene()
    assert s.add_instance(a, **kw) == 0


# --- eval / eval_root / eval_root_grad -------------------------------------------------------------

def _evaluate(call, s, a, pts):
    if call == "eval":
        s.add_instance(a)
        return s.eval(pts)
    return getattr(s, call)(a, pts)


@pytest.mark.parametrize("call", ["eval", "eval_root", "eval_root_grad"])
@pytest.mark.parametrize("bad, where", [(NAN, "points[1, 0]"), (INF, "points[1, 0]"), (-INF, "points[1, 0]")])
def test_points_refused(call, bad, where):
    s, a, _ = _scene()
    pts = np.zeros((3, 3))
    pts[1, 0] = bad
    _raises(lambda: _evaluate(call, s, a, pts), f"SceneBuilder.{call}: {where} must be finite (length units)")


@pytest.mark.parametrize("call", ["eval", "eval_root", "eval_root_grad"])
@pytest.mark.parametrize("n", [0, 4])
def test_points_accepted(call, n):
    s, a, _ = _scene()
    out = _evaluate(call, s, a, np.full((n, 3), 0.1))
    assert (out[0] if isinstance(out, tuple) else out).shape == (n,)


# --- bake ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("origin, spacing, dims, text", [
    ([NAN, 0, 0], [0.1] * 3, [4] * 3, "origin[0] must be finite (length units)"),
    ([0, -INF, 0], [0.1] * 3, [4] * 3, "origin[1] must be finite"),
    ([0, 0, 0], [0.0, 0.1, 0.1], [4] * 3, "spacing[0] must be finite and > 0 (length units)"),
    ([0, 0, 0], [0.1, -0.1, 0.1], [4] * 3, "spacing[1] must be finite and > 0"),
    ([0, 0, 0], [0.1, 0.1, NAN], [4] * 3, "spacing[2] must be finite and > 0"),
    ([0, 0, 0], [INF, 0.1, 0.1], [4] * 3, "spacing[0] must be finite and > 0"),
    ([0, 0, 0], [0.1] * 3, [2**21, 2**21, 2**22], "dims[2] must be such that the node count fits"),
])
def test_bake_refused(origin, spacing, dims, text):
    s, a, _ = _scene()
    _raises(lambda: s.bake(a, origin, spacing, dims), f"SceneBuilder.bake: {text}")


def test_bake_accepted():
    s, a, _ = _scene()
    assert s.bake(a, [-1.0, -1.0, -1.0], [0.1, 0.2, 0.4], [21, 11, 6]).shape == (21 * 11 * 6,)


# --- body_properties / principal_frame ------------------------------------------------------------

BAD_QUADRATURE = [
    ({"lo": [NAN, -0.6, -0.6]}, "lo[0] must be finite (length units)"),
    ({"lo": [-INF, -0.6, -0.6]}, "lo[0] must be finite"),
    ({"hi": [0.6, INF, 0.6]}, "hi[1] must be finite (length units)"),
    ({"order": 0}, "order must be a Gauss order in {1, 2, 3, 4, 5, 6, 8}"),
    ({"order": -1}, "order must be a Gauss order"),
    ({"order": 7}, "order must be a Gauss order"),
    ({"order": 99}, "order must be a Gauss order"),
    ({"nseg": 0}, "nseg must be an integer in [2, 64]"),
    ({"nseg": 1}, "nseg must be an integer in [2, 64]"),
    ({"nseg": 65}, "nseg must be an integer in [2, 64]"),
]


def _quad(call, s, a, kw):
    args = {"lo": LO, "hi": HI, "n": 6}
    args.update(kw)
    return getattr(s, call)(a, **args)


@pytest.mark.parametrize("call", ["body_properties", "principal_frame"])
@pytest.mark.parametrize("kw, text", BAD_QUADRATURE)
def test_quadrature_refused(call, kw, text):
    s, a, _ = _scene()
    _raises(lambda: _quad(call, s, a, kw), f"SceneBuilder.{call}: {text}")


@pytest.mark.parametrize("call", ["body_properties", "principal_frame"])
@pytest.mark.parametrize("kw", [{}, {"order": 1}, {"order": 8}, {"nseg": 2}, {"nseg": 64}])
def test_quadrature_accepted(call, kw):
    s, a, _ = _scene()
    _quad(call, s, a, kw)


@pytest.mark.parametrize("rho", [0.0, -1.0, NAN, INF])
def test_density_refused(rho):
    s, a, _ = _scene()
    _raises(lambda: _quad("body_properties", s, a, {"density": rho}),
            "SceneBuilder.body_properties: density must be finite and > 0 (mass/length^3 units)")


def test_density_accepted():
    s, a, _ = _scene()
    props = _quad("body_properties", s, a, {"density": 2.0})
    assert props["mass"] == pytest.approx(2.0 * props["volume"])
