/// @file
/// @brief Input validation of the `peclet.geom` Python binding (python/geom_bindings.cpp only).
///
/// The scene headers (peclet/core/geom/*.hpp, vendored from core) trust their caller: a leaf
/// with too few parameters was zero-filled, a zero or negative scale divided by zero or turned
/// the shape inside out, a zero or NaN quaternion rotated by the identity or by NaN, a NaN or
/// infinite query point evaluated to distance 0, and quadrature orders and segment counts outside
/// the supported set were silently remapped. The binding refuses these as ValueError
/// (std::invalid_argument) before they reach the headers. A valid value takes exactly the path it
/// took before. The message names the call, the parameter, the admissible range with its
/// dimension (lengths are in the caller's consistent length units) and the offending value.
/// Binding-only: no geometry header includes this file.
#pragma once

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

#include "peclet/core/geom/scene.hpp"

namespace geom_checks {

namespace g = peclet::core::geom;

inline std::string num(double v) {
  char b[32];
  std::snprintf(b, sizeof b, "%g", v);
  return b;
}
[[noreturn]] inline void fail(const char* who, const std::string& name, const std::string& rule,
                              double v) {
  throw std::invalid_argument(std::string(who) + ": " + name + " must be " + rule + ", got " +
                              num(v));
}
inline std::string component(const char* name, std::size_t i) {
  return std::string(name) + "[" + std::to_string(i) + "]";
}

/// Each component finite (a coordinate or a velocity: any sign).
template <std::size_t N>
void finiteEach(const char* who, const char* name, const std::array<double, N>& a,
                const char* dim) {
  for (std::size_t i = 0; i < N; ++i) {
    if (!std::isfinite(a[i])) {
      fail(who, component(name, i), std::string("finite (") + dim + ")", a[i]);
    }
  }
}

/// rotation: a unit quaternion (x, y, z, w). rotate() does not normalize: a quaternion of norm
/// |q| scales every rotated vector by |q|^2 (the zero quaternion collapses to the identity), so the
/// shape would be silently resized. Admitted: | |q| - 1 | <= kUnitQuatTol, which accepts a
/// quaternion rounded to four decimals by hand (|q| - 1 ~ 2e-5).
inline constexpr double kUnitQuatTol = 1e-3;
inline void rotation(const char* who, const std::array<double, 4>& q) {
  finiteEach(who, "rotation", q, "a quaternion (x, y, z, w), dimensionless");
  const double norm = std::sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]);
  if (!(std::abs(norm - 1.0) <= kUnitQuatTol)) {
    fail(who, "|rotation|", "1 within 1e-3 (a unit quaternion (x, y, z, w), dimensionless)", norm);
  }
}

/// A conformal transform: a finite translation, a rotation quaternion and an isotropic scale
/// finite and > 0 (the SDF is divided by it; a negative one turns the shape inside out).
inline void transform(const char* who, const std::array<double, 3>& t,
                      const std::array<double, 4>& q, double s) {
  finiteEach(who, "translation", t, "length units");
  rotation(who, q);
  if (!(std::isfinite(s) && s > 0.0)) {
    fail(who, "scale", "finite and > 0 (dimensionless)", s);
  }
}

/// The parameter count of each leaf kind (the add_leaf docstring) and the index of a parameter
/// that is an exponent rather than a length (-1 if none).
struct LeafShape {
  std::size_t count;
  int exponent;
  const char* names;
};
inline LeafShape leafShape(int kind) {
  switch (kind) {
    case g::kSphere:
      return {1, -1, "[r]"};
    case g::kBox:
      return {3, -1, "[hx, hy, hz]"};
    case g::kHollowCylinder:
      return {3, -1, "[rOuter, height, thickness]"};
    case g::kHollowCylinderShell:
      return {3, -1, "[rOuter, rInner, height]"};
    case g::kCapsule:
      return {2, -1, "[r, halfLength]"};
    case g::kTorus:
      return {2, -1, "[R, r]"};
    case g::kCone:
      return {3, -1, "[rBottom, rTop, halfHeight]"};
    case g::kEllipsoid:
      return {3, -1, "[rx, ry, rz]"};
    default:  // g::kSuperquadric: kindFromName admits no other kind
      return {4, 3, "[rx, ry, rz, e]"};
  }
}

/// add_leaf's params: exactly the kind's parameter count; lengths finite and >= 0 (0 is a
/// degenerate but well-defined shape), the superquadric exponent finite and > 0. The leaf's
/// transform is checked by transform().
inline void leafParams(int kind, const std::string& kindName, const std::vector<double>& params) {
  const char* who = "SceneBuilder.add_leaf";
  const LeafShape shape = leafShape(kind);
  if (params.size() != shape.count) {
    throw std::invalid_argument(
        std::string(who) + ": params must be " + std::to_string(shape.count) +
        (shape.count == 1 ? " value " : " values ") + shape.names + " for kind '" + kindName +
        "', got " + std::to_string(params.size()));
  }
  for (std::size_t i = 0; i < params.size(); ++i) {
    const bool exponent = static_cast<int>(i) == shape.exponent;
    const bool ok = std::isfinite(params[i]) && (exponent ? params[i] > 0.0 : params[i] >= 0.0);
    if (!ok) {
      fail(who, component("params", i),
           exponent ? "finite and > 0 (dimensionless)" : "finite and >= 0 (length units)",
           params[i]);
    }
  }
}

/// add_instance's motion: finite velocities, and a centre that is all NaN (the default: it
/// follows the body) or all finite (pinned in world coordinates). The transform is checked by
/// transform().
inline void motion(const std::array<double, 3>& lin, const std::array<double, 3>& ang,
                   const std::array<double, 3>& center) {
  const char* who = "SceneBuilder.add_instance";
  finiteEach(who, "lin_vel", lin, "length/time units");
  finiteEach(who, "ang_vel", ang, "1/time units");
  const bool follows = std::isnan(center[0]) && std::isnan(center[1]) && std::isnan(center[2]);
  if (!follows) {
    finiteEach(who, "center", center, "length units; or all three NaN, the default");
  }
}

/// (N, 3) query points, every coordinate finite (a NaN or Inf point evaluated to distance 0).
template <class Array>
void points(const char* who, const Array& pts) {
  const double* p = pts.data();
  for (std::size_t i = 0; i < pts.size(); ++i) {
    if (!std::isfinite(p[i])) {  // the name is built only on failure: no allocation per element
      fail(who, "points[" + std::to_string(i / 3) + ", " + std::to_string(i % 3) + "]",
           "finite (length units)", p[i]);
    }
  }
}

/// bake: a finite origin, a spacing finite and > 0, and (once dims >= 2, which bake itself checks)
/// a node count that fits in std::size_t (a wrapped product sized the output array wrongly).
inline void lattice(const std::array<double, 3>& origin, const std::array<double, 3>& spacing,
                    const std::array<int, 3>& dims) {
  const char* who = "SceneBuilder.bake";
  finiteEach(who, "origin", origin, "length units");
  for (std::size_t i = 0; i < spacing.size(); ++i) {
    if (!(std::isfinite(spacing[i]) && spacing[i] > 0.0)) {
      fail(who, component("spacing", i), "finite and > 0 (length units)", spacing[i]);
    }
  }
  std::size_t nodes = 1;
  for (std::size_t i = 0; i < dims.size(); ++i) {
    if (dims[i] >= 2 && __builtin_mul_overflow(nodes, static_cast<std::size_t>(dims[i]), &nodes)) {
      fail(who, component("dims", i), "such that the node count fits in 64 bits", dims[i]);
    }
  }
}

/// body_properties / principal_frame: a finite box and a quadrature the headers support (Gauss
/// orders 1-6 and 8; 2-64 initial segments per line). Other values were remapped silently.
inline void quadrature(const char* who, const std::array<double, 3>& lo,
                       const std::array<double, 3>& hi, int order, int nseg) {
  finiteEach(who, "lo", lo, "length units");
  finiteEach(who, "hi", hi, "length units");
  if (order < 1 || order == 7 || order > 8) {
    fail(who, "order", "a Gauss order in {1, 2, 3, 4, 5, 6, 8} (points per axis)", order);
  }
  if (nseg < 2 || nseg > 64) {
    fail(who, "nseg", "an integer in [2, 64] (initial segments per line)", nseg);
  }
}

/// body_properties' density: finite and > 0 (mass/length^3 units).
inline void density(double rho) {
  if (!(std::isfinite(rho) && rho > 0.0)) {
    fail("SceneBuilder.body_properties", "density", "finite and > 0 (mass/length^3 units)", rho);
  }
}

}  // namespace geom_checks
