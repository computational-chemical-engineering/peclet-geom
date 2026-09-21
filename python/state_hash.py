"""Fixed-seed reference runs of every public entry path of peclet.geom, hashed.

The structural gate of suite/docs/QUALITY_PLAN.md §3.G: a refactor that moves code verbatim must
leave every final state BYTE-IDENTICAL. This script runs one deterministic scenario per public
entry path, hashes the final arrays (SHA-256 of the raw float64/int bytes) and prints them; with
``--save FILE`` it records them as JSON and with ``--check FILE`` it compares against a recording
and exits non-zero on any difference.

    PYTHONPATH=<python build tree> OMP_NUM_THREADS=1 python python/state_hash.py --save pre.json
    PYTHONPATH=<python build tree> OMP_NUM_THREADS=1 mpirun -np 2 python python/state_hash.py --check pre.json

Under ``mpirun -np N`` (N > 1) the distributed paths (ParticleMigrator / ParticleHalo across ranks)
run too; every per-rank array is gathered to rank 0 in
rank order before hashing, so the hash names carry the rank count (``.np2``). Run at
OMP_NUM_THREADS=1: the device reductions are order-dependent at more than one thread.

Only ``geom`` here; the halo entry paths have the same script in peclet-halo (the `core` repo),
and the AMR ones in peclet-amr. Split out of peclet-core 2026-09-21 (suite/docs/CORE_BOUNDARY.md);
the geom hashes must be BYTE-IDENTICAL across that move, which is what proves it was a move.
"""
import argparse
import hashlib
import json
import os
import sys

import numpy as np


def sha(*arrays):
    h = hashlib.sha256()
    flat = []
    for a in arrays:  # a binding may return a tuple of arrays: hash each member in order
        flat += list(a) if isinstance(a, (tuple, list)) and not np.isscalar(a[0]) else [a]
    for a in flat:
        a = np.ascontiguousarray(a)
        h.update(str(a.dtype).encode())
        h.update(str(a.shape).encode())
        h.update(a.tobytes())
    return h.hexdigest()


def gather_rows(comm, a):
    """Concatenate a per-rank (n, k) array over ranks in rank order (rank 0 gets the result)."""
    if comm is None or comm.size == 1:
        return np.ascontiguousarray(a)
    parts = comm.gather(np.ascontiguousarray(a), root=0)
    return np.concatenate(parts, axis=0) if comm.rank == 0 else None


# ---------------------------------------------------------------------------------------------
# peclet.core.geom — a CSG scene evaluated on a grid, baked, and its mass properties.
# ---------------------------------------------------------------------------------------------
def run_geom(out, comm):
    from peclet import geom
    if comm is not None and comm.rank != 0:
        return
    s = geom.SceneBuilder()
    sph = s.add_leaf("sphere", [0.3])
    box = s.add_leaf("box", [0.25, 0.15, 0.2], translation=[0.2, 0.1, 0.0],
                     rotation=[0.0, 0.0, 0.3826834323650898, 0.9238795325112867])
    tor = s.add_leaf("torus", [0.35, 0.08], translation=[-0.1, 0.0, 0.2])
    u = s.add_union(sph, box)
    d = s.add_difference(u, tor)
    s.add_instance(d, translation=[0.5, 0.5, 0.5])
    s.add_instance(sph, translation=[0.15, 0.8, 0.3], scale=0.5)
    n = 24
    g = (np.arange(n) + 0.5) / n
    pts = np.stack(np.meshgrid(g, g, g, indexing="ij"), axis=-1).reshape(-1, 3)
    pts = np.ascontiguousarray(pts, dtype=np.float64)
    out["geom.eval"] = sha(s.eval(pts))
    out["geom.eval_root"] = sha(s.eval_root(d, pts))
    out["geom.eval_root_grad"] = sha(s.eval_root_grad(d, pts))
    baked = s.bake(d, [-0.6, -0.6, -0.6], [0.05, 0.05, 0.05], [24, 24, 24])
    out["geom.bake"] = sha(np.asarray(baked))
    bp = s.body_properties(d, [-0.8, -0.8, -0.8], [0.8, 0.8, 0.8], n=24)
    out["geom.body_properties"] = sha(
        np.array([bp["volume"], bp["mass"]]), np.asarray(bp["com"]), np.asarray(bp["inertia_tensor"]),
        np.asarray(bp["principal"]), np.asarray(bp["rotation"]), np.asarray(bp["quat"]))


# ---------------------------------------------------------------------------------------------
RUNNERS = {"geom": run_geom}


def toolchain():
    """The module's compiler / version / build type. Hashes are only comparable within one."""
    from peclet import geom
    return getattr(geom, "build_toolchain", "unknown")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modules", default="geom,mpi", help="comma-separated subset of geom,mpi")
    ap.add_argument("--save", metavar="FILE", help="write the hashes as JSON")
    ap.add_argument("--check", metavar="FILE", help="compare against a JSON recording")
    args = ap.parse_args()
    if os.environ.get("OMP_NUM_THREADS") != "1":
        sys.stderr.write("state_hash: run with OMP_NUM_THREADS=1 (device reductions are order-dependent)\n")
    comm = None
    try:
        from mpi4py import MPI
        comm = MPI.COMM_WORLD
    except ImportError:
        pass
    rank = comm.rank if comm is not None else 0
    out = {}
    for name in args.modules.split(","):
        name = name.strip()
        if not name:
            continue
        try:
            RUNNERS[name](out, comm)
        except ImportError as e:
            if rank == 0:
                print(f"# {name}: not importable ({e}); skipped")
    if rank != 0:
        return 0
    for k in sorted(out):
        print(f"{k} {out[k]}")
    rc = 0
    if args.check:
        ref = json.load(open(args.check))
        want = ref.pop("toolchain", None)
        have = toolchain()
        if want is not None and want != have:
            print(f"state_hash: reference recorded with toolchain '{want}', this build is '{have}' — "
                  "not comparable; SKIPPED (exit 77). Re-record with --save on this toolchain to gate it.")
            return 77
        # A recording may merge several rank counts; compare only the keys this run can produce
        # (no `.npN` suffix, or the suffix of the current communicator size).
        size = comm.size if comm is not None else 1
        ref = {k: v for k, v in ref.items() if ".np" not in k or k.endswith(f".np{size}")}
        for k in sorted(set(ref) | set(out)):
            if k not in out:
                print(f"MISSING {k}")
                rc = 1
            elif k not in ref:
                print(f"NEW {k}")
            elif ref[k] != out[k]:
                print(f"DIFFER {k}: {ref[k][:16]}... -> {out[k][:16]}...")
                rc = 1
        print("state_hash: " + ("IDENTICAL" if rc == 0 else "DIFFERENCES FOUND"))
    if args.save:
        out["toolchain"] = toolchain()
        with open(args.save, "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
