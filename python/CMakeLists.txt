# Python bindings for the analytic-SDF scene authoring layer — `peclet.geom`.
#
# THE POINT OF THIS FILE IS WHAT IT DOES NOT DO. It calls no find_package(MPI) and no
# find_package(Kokkos), because geom_bindings.cpp needs neither: its closure is six
# peclet/core/geom/*.hpp headers plus common/{types,portable}.hpp, none of which include
# peclet/core/common/mpi.hpp (suite/docs/CORE_BOUNDARY.md §2.1 makes that the boundary test).
#
# That is the defect this package exists to fix. While these bindings shared a distribution with
# the halo bindings, core/python/CMakeLists.txt's `find_package(MPI REQUIRED)` covered both, so
# `pip install` of a pure-geometry API needed an MPI toolchain — and eleven gallery pages plus
# peclet.dem's scene_particle.build() were unobtainable without one.
#
#   cmake -S python -B python/build && cmake --build python/build -j
#   PYTHONPATH=python/build python -c "from peclet.geom import SceneBuilder"
cmake_minimum_required(VERSION 3.24)
project(peclet_geom_python LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# SuiteNanobind: the umbrella's copy in a suite checkout, the vendored copy otherwise. Same
# arrangement as core, for the same reason (DECISIONS.md: the sdist must be self-contained).
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/../../cmake" "${CMAKE_CURRENT_SOURCE_DIR}/../cmake")
include(SuiteNanobind)
suite_require_nanobind()

# The core headers, from the sibling checkout or vendored at PECLET_CORE_TAG (cmake/PecletDeps.cmake).
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/PecletDeps.cmake)
peclet_sibling_include(peclet-core "${PECLET_CORE_TAG}" "../../core" PECLET_CORE_INCLUDE)

nanobind_add_module(geom_bindings NB_STATIC geom_bindings.cpp)
set_target_properties(geom_bindings PROPERTIES OUTPUT_NAME _geom
                      LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/peclet/geom")
target_include_directories(geom_bindings PRIVATE ${PECLET_CORE_INCLUDE})

# state_hash.py refuses to compare hashes across toolchains, so the module must SAY which one built
# it — otherwise --check skips (exit 77) and the byte gate silently proves nothing.
target_compile_definitions(geom_bindings PRIVATE
  "PECLET_GEOM_BUILD_TOOLCHAIN=\"${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION} ${CMAKE_BUILD_TYPE} ${CMAKE_SYSTEM_PROCESSOR}\"")

# The importable package: peclet/geom/{__init__.py, _geom<abi>.so, _geom.pyi, py.typed}. `peclet`
# itself is a PEP-420 namespace owned by the member packages — it gets no __init__.py here.
set(_pkg "${CMAKE_BINARY_DIR}/peclet/geom")
file(MAKE_DIRECTORY "${_pkg}")
configure_file(packaging/geom_init.py "${_pkg}/__init__.py" COPYONLY)
configure_file(packaging/_geom.pyi    "${_pkg}/_geom.pyi"   COPYONLY)
file(TOUCH "${_pkg}/py.typed")

install(TARGETS geom_bindings LIBRARY DESTINATION peclet/geom)
install(FILES packaging/geom_init.py DESTINATION peclet/geom RENAME __init__.py)
install(FILES packaging/_geom.pyi    DESTINATION peclet/geom)
install(FILES "${_pkg}/py.typed"     DESTINATION peclet/geom)
