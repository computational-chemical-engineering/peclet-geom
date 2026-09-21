"""peclet.geom — analytic-SDF scene authoring: CSG trees, batch evaluation, lattice baking,
and rigid-body mass properties (mass, centre of mass, inertia tensor, principal frame).

Host-only and dependency-light by design: no MPI, no Kokkos, no Kokkos-backed solver. That is
why it ships as wheels and is part of a plain ``pip install peclet``.

Until peclet 1.2.0 this was ``peclet.core.geom`` in the ``peclet-core`` distribution, which could
not be installed without an MPI toolchain. ``peclet.core.geom`` still works and is the same object
(``peclet.core.geom.SceneBuilder is peclet.geom.SceneBuilder``); it warns from 1.3.0 and is removed
in 2.0.0. See suite/docs/CORE_BOUNDARY.md.
"""
from ._geom import *  # noqa: F401,F403
from . import _geom as _ext

__all__ = [n for n in dir(_ext) if not n.startswith("_")]
