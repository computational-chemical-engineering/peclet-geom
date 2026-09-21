# peclet-geom

`peclet.geom` — analytic-SDF scene authoring for the [peclet](https://github.com/computational-chemical-engineering/peclet)
suite: CSG trees over signed-distance primitives, batch evaluation, lattice baking, and rigid-body
mass properties (mass, centre of mass, the full inertia tensor, and the principal frame as three
moments plus a quaternion).

```bash
pip install peclet-geom        # or just `pip install peclet` — it is part of the family
```

```python
from peclet import geom

s = geom.SceneBuilder()
head   = s.add_leaf("torus", ...)
handle = s.add_leaf("capsule", ...)
body   = s.add_union([head, handle])
m, com, inertia, quat = s.body_properties(body, lo, hi)
racket = s.principal_frame(body, lo, hi)     # re-expressed exactly, no resampling
```

## Why this is its own package

It is **host-only**: no MPI, no Kokkos, no GPU — its closure is six `peclet/core/geom/*.hpp`
headers plus two common ones, and it depends on nothing but numpy at runtime. That is what lets it
ship as wheels and be part of a plain `pip install peclet`.

Until peclet 1.2.0 this code was `peclet.core.geom` inside the `peclet-core` distribution, whose
build requires an MPI toolchain because it also builds the halo bindings. A pure-geometry API was
therefore unobtainable without MPI — which broke eleven gallery pages and `peclet.dem`'s
`scene_particle.build()`. The boundary rule and the migration ladder are in
[suite/docs/CORE_BOUNDARY.md](https://github.com/computational-chemical-engineering/peclet/blob/main/docs/CORE_BOUNDARY.md).

`peclet.core.geom` still works and is the *same object* — `peclet.core.geom.SceneBuilder is
peclet.geom.SceneBuilder` — it gains a `DeprecationWarning` in 1.3.0 and is removed in 2.0.0.

## Build from source

```bash
cmake -S python -B python/build -DCMAKE_BUILD_TYPE=Release
cmake --build python/build -j
PYTHONPATH=python/build python -c "from peclet import geom; print(geom.SceneBuilder())"
```

The core headers come from a sibling `../core` checkout if present, else are fetched at
`PECLET_CORE_TAG` (`cmake/PecletDeps.cmake`). Point at a core worktree with
`-DPECLET_SIBLING_PECLET_CORE=/path/to/core-worktree`.

## Faithfulness gate

`python/state_hash.py` hashes every public entry path. The recorded reference is byte-identical to
what `peclet-core` 1.0.2 produced before the split — a changed digit is a bug in the move:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=python/build python python/state_hash.py --check python/state_hash_reference.json
```

## License

MIT — see [LICENSE](LICENSE).
