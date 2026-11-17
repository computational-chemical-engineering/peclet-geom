# peclet.geom playbook: user-facing round (WO-35, 2026-11-17; deltas from core's, pnm's, dem's)
- **Scope**: python/ and CI only; the peclet/core/geom/*.hpp headers are core's (vendored), never edited here.
  Gate: config.toml here, `--behaviour-only --base b8f8331`; core's headers pinned with `PECLET_SIBLING_PECLET_CORE`.
- **Checks**: `python/geom_bindings_checks.hpp` (`geom_checks`, alias `chk`), one or two `chk::` lines per lambda.
  Keep each helper at <= 5 parameters: a six-parameter leaf()/instance() raised the touched-file debt 6.0 -> 8.0.
- **Found**: 62 silent + 1 crash of 127. Short leaf params zero-filled (empty kept radius 1); scale <= 0 divided by
  zero or inverted the shape; the zero quaternion was the identity and a non-unit one resized the shape by |q|^2;
  NaN/Inf query points evaluated to distance 0; a lattice node count wrapping size_t: SIGSEGV; Gauss order outside
  {1..6, 8} and nseg outside [2, 64] remapped silently; a partly-NaN centre stored as given. Table: `probes_wo35.tsv`.
- **Judgment calls**: unit quaternion within 1e-3 (own commit, ea06a50; admits 4-decimal hand rounding); lengths >= 0
  (0 = degenerate shape); exact param count per kind (all 96 literal add_leaf calls in suite/gallery/papers match).
- **Valid input kept**: all-NaN centre (default, follows the body), negative material ids (opaque; -1 = none),
  large n (n = 2**20 times out: cost n^3 * order^2 lines, not a bug), empty point sets.
- **Traps**: geom has no clang-format standard (geom_bindings.cpp is unformatted under every style in the tree): new
  python/*.hpp only, core's style. No ctests: CI's 'Python tests' step runs python/test_*.py on the installed wheel.
  The shipped stub had drifted (docstrings and build_toolchain missing); regenerated with core's post-processing.
- **Wall clock (TRS2)**: build 6 s; gate --behaviour-only 29 s; probes 127 cases about 1.5 min (two 40 s timeouts).
