# PecletDeps.cmake — dependency provisioning for peclet-geom.
#
# peclet-geom has exactly ONE dependency: the header-only peclet-core geom headers. No Kokkos, no
# MPI, no morton (suite/docs/CORE_BOUNDARY.md §1.2) — which is what lets this package ship wheels
# while peclet-halo stays an sdist.
#
# Two ways to build, selected automatically:
#   * DEV / suite build — the sibling ../../core/include is used directly.
#   * SELF-CONTAINED sdist (pip install peclet-geom) — the siblings are ABSENT, so the core headers
#     are FetchContent-fetched at PECLET_CORE_TAG below.
# Force the fetch with -DPECLET_VENDOR_DEPS=ON. Keep PECLET_CORE_TAG in lockstep with the other
# packages' PecletDeps.cmake; the release pre-flight (tools/release/check_release_state.sh) checks it.
#
# The PECLET_SIBLING_PECLET_CORE override below is how concurrent work stays out of each other's
# way: point a build at a core WORKTREE without touching the shared ../../core checkout.
include_guard(GLOBAL)
include(FetchContent)

set(PECLET_CORE_TAG "v1.0.2" CACHE STRING "Vendored core git tag (headers)")
option(PECLET_VENDOR_DEPS "Force FetchContent-fetch of the core headers (self-contained sdist)" OFF)

function(peclet_sibling_include repo tag sibling_reldir outvar)
  # Dev override for a sibling checked out somewhere else than `../<repo>` -- in particular a git
  # WORKTREE, which is how the suite runs concurrent agents (`git worktree add ../core-w0`). Pass
  # the repo ROOT (`/include` is appended):
  #   -DPECLET_SIBLING_PECLET_CORE=/path/to/suite/core-w0
  # Unset (the default) it resolves exactly as before, so every existing build is unchanged.
  string(TOUPPER "${repo}" _ovr)
  string(REPLACE "-" "_" _ovr "${_ovr}")
  if(PECLET_SIBLING_${_ovr})
    set(${outvar} "${PECLET_SIBLING_${_ovr}}/include" PARENT_SCOPE)
    message(STATUS "[peclet] ${repo} headers from PECLET_SIBLING_${_ovr} -> ${PECLET_SIBLING_${_ovr}}/include")
    return()
  endif()
  set(_local "${CMAKE_CURRENT_SOURCE_DIR}/${sibling_reldir}/include")
  if(EXISTS "${_local}" AND NOT PECLET_VENDOR_DEPS)
    set(${outvar} "${_local}" PARENT_SCOPE)
    return()
  endif()
  string(TOLOWER "peclet_sib_${repo}" _name)
  FetchContent_Declare(${_name}
    GIT_REPOSITORY "https://github.com/computational-chemical-engineering/${repo}.git"
    GIT_TAG ${tag} GIT_SHALLOW TRUE)
  FetchContent_GetProperties(${_name})
  if(NOT ${_name}_POPULATED)
    FetchContent_Populate(${_name})
  endif()
  set(${outvar} "${${_name}_SOURCE_DIR}/include" PARENT_SCOPE)
  message(STATUS "[peclet] vendored ${repo} headers -> ${${_name}_SOURCE_DIR}/include")
endfunction()
