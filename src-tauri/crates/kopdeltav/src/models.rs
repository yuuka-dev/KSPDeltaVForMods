//! Core domain models for KSP celestial body physics.
//!
//! Provides data structures for celestial bodies, atmospheres, orbital elements,
//! and animation curve interpolation (Cubic Hermite Spline) compatible with
//! KSP's AnimationCurve format.

use serde::Serialize;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/// Standard gravitational acceleration at sea level [m/s^2].
pub const G0: f64 = 9.80665;

/// Universal gas constant [J/(mol*K)].
pub const R_GAS: f64 = 8.314_462_618;

// ---------------------------------------------------------------------------
// Functions
// ---------------------------------------------------------------------------

/// Compute the standard gravitational parameter (mu) for a celestial body.
///
/// mu = gee_asl * G0 * radius^2
///
/// # Arguments
/// * `gee_asl` - Surface gravity in multiples of g0.
/// * `radius` - Equatorial radius [m].
///
/// # Returns
/// Gravitational parameter mu [m^3/s^2].
pub fn compute_mu(gee_asl: f64, radius: f64) -> f64 {
    gee_asl * G0 * radius * radius
}

// ---------------------------------------------------------------------------
// Structs
// ---------------------------------------------------------------------------

/// A single keyframe in a KSP AnimationCurve.
///
/// KSPのAnimationCurveキーフレーム。
#[derive(Debug, Clone, Serialize)]
pub struct CurveKey {
    /// Curve position (x-axis value, e.g. altitude).
    pub position: f64,
    /// Curve value at this position (y-axis value).
    pub value: f64,
    /// Incoming tangent (slope on the left side of the key).
    pub in_tangent: f64,
    /// Outgoing tangent (slope on the right side of the key).
    pub out_tangent: f64,
}

/// Atmospheric model for a celestial body.
///
/// 天体の大気モデル。
#[derive(Debug, Clone, Serialize)]
pub struct Atmosphere {
    /// Height of the atmosphere above the surface [m].
    pub atmosphere_depth: f64,
    /// Pressure curve keyframes (altitude -> pressure in kPa).
    pub pressure_curve: Vec<CurveKey>,
    /// Temperature curve keyframes (altitude -> temperature in K).
    pub temperature_curve: Vec<CurveKey>,
    /// Molar mass of the atmosphere [kg/mol].
    pub molar_mass: f64,
    /// Adiabatic index (ratio of specific heats, Cp/Cv).
    pub adiabatic_index: f64,
    /// Sea-level pressure [kPa].
    pub pressure_at_sea_level: f64,
    /// Sea-level temperature [K].
    pub temperature_at_sea_level: f64,
}

/// Keplerian orbital elements for a celestial body.
///
/// 天体のケプラー軌道要素。
#[derive(Debug, Clone, Serialize)]
pub struct OrbitalElements {
    /// Semi-major axis [m].
    pub semi_major_axis: f64,
    /// Orbital eccentricity (0 = circular, <1 = elliptical).
    pub eccentricity: f64,
    /// Orbital inclination [degrees].
    pub inclination: f64,
    /// Argument of periapsis [degrees].
    pub argument_of_periapsis: f64,
    /// Longitude of ascending node [degrees].
    pub longitude_of_ascending_node: f64,
    /// Mean anomaly at epoch [radians].
    pub mean_anomaly_at_epoch: f64,
    /// Reference epoch [s].
    pub epoch: f64,
}

/// A celestial body in the KSP system with physical and orbital properties.
///
/// KSPの天体（物理・軌道パラメータ付き）。
///
/// Not `Serialize` because parent/children references form a graph
/// that is resolved externally by name.
#[derive(Debug, Clone)]
pub struct CelestialBody {
    /// Internal name (e.g. "Kerbin").
    pub name: String,
    /// Equatorial radius [m].
    pub radius: f64,
    /// Surface gravity in multiples of g0.
    pub gee_asl: f64,
    /// Whether the body has an ocean.
    pub has_ocean: bool,
    /// Atmospheric model, if present.
    pub atmosphere: Option<Atmosphere>,
    /// Orbital elements, if the body orbits another body.
    pub orbit: Option<OrbitalElements>,
    /// Sidereal rotational period [s].
    pub rotational_period: f64,
    /// Display name (may differ from internal name).
    pub display_name: String,
    /// Sphere of influence radius [m].
    pub soi: f64,
    /// Whether this is the home world (e.g. Kerbin).
    pub is_home_world: bool,
    /// Name of the parent body this body orbits.
    pub reference_body_name: String,
    /// Standard gravitational parameter mu [m^3/s^2] (auto-computed).
    pub mu: f64,
    /// Parent body name for tree construction.
    pub parent_name: Option<String>,
    /// Child body names for tree construction.
    pub children_names: Vec<String>,
}

impl CelestialBody {
    /// Create a new celestial body with auto-computed mu.
    ///
    /// 天体を生成し、muを自動計算する。
    ///
    /// # Arguments
    /// * `name` - Internal name.
    /// * `radius` - Equatorial radius [m].
    /// * `gee_asl` - Surface gravity in multiples of g0.
    /// * `has_ocean` - Whether the body has an ocean.
    /// * `atmosphere` - Atmospheric model, if any.
    /// * `orbit` - Orbital elements, if any.
    /// * `rotational_period` - Sidereal rotational period [s].
    /// * `display_name` - Display name for UI.
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        name: String,
        radius: f64,
        gee_asl: f64,
        has_ocean: bool,
        atmosphere: Option<Atmosphere>,
        orbit: Option<OrbitalElements>,
        rotational_period: f64,
        display_name: String,
    ) -> Self {
        let mu = compute_mu(gee_asl, radius);
        Self {
            name,
            radius,
            gee_asl,
            has_ocean,
            atmosphere,
            orbit,
            rotational_period,
            display_name,
            soi: 0.0,
            is_home_world: false,
            reference_body_name: String::new(),
            mu,
            parent_name: None,
            children_names: Vec::new(),
        }
    }

    /// Returns true if the body has an atmosphere.
    ///
    /// 大気を持つかどうかを返す。
    pub fn has_atmosphere(&self) -> bool {
        self.atmosphere.is_some()
    }
}

// ---------------------------------------------------------------------------
// Hermite interpolation
// ---------------------------------------------------------------------------

/// Evaluate a Cubic Hermite Spline at position `x`, compatible with KSP AnimationCurve.
///
/// KSP AnimationCurve互換のCubic Hermite Spline補間。
///
/// Values outside the curve range are clamped to the nearest endpoint value.
///
/// # Arguments
/// * `keys` - Sorted keyframes defining the curve.
/// * `x` - Position to evaluate at.
///
/// # Returns
/// Interpolated value, or an error if `keys` is empty.
///
/// # Errors
/// Returns `Err` if the keys slice is empty.
pub fn hermite_interp(keys: &[CurveKey], x: f64) -> Result<f64, String> {
    if keys.is_empty() {
        return Err("Cannot interpolate with empty keys list".to_string());
    }
    if keys.len() == 1 {
        return Ok(keys[0].value);
    }
    if x <= keys[0].position {
        return Ok(keys[0].value);
    }
    if x >= keys[keys.len() - 1].position {
        return Ok(keys[keys.len() - 1].value);
    }

    // Find the segment containing x
    let mut i = 0;
    for (j, key) in keys.iter().enumerate().skip(1) {
        if key.position >= x {
            i = j - 1;
            break;
        }
    }

    let k0 = &keys[i];
    let k1 = &keys[i + 1];
    let dx = k1.position - k0.position;
    let t = (x - k0.position) / dx;

    let t2 = t * t;
    let t3 = t2 * t;
    let h00 = 2.0 * t3 - 3.0 * t2 + 1.0;
    let h10 = t3 - 2.0 * t2 + t;
    let h01 = -2.0 * t3 + 3.0 * t2;
    let h11 = t3 - t2;

    Ok(h00 * k0.value + h10 * dx * k0.out_tangent + h01 * k1.value + h11 * dx * k1.in_tangent)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // Constants
    #[test]
    fn test_g0_constant() {
        assert!((G0 - 9.80665).abs() < 1e-10);
    }

    // compute_mu
    #[test]
    fn test_compute_mu_sanctar() {
        let mu = compute_mu(1.1, 670_000.0);
        let expected = 4.8424e12;
        assert!((mu - expected).abs() / expected < 0.001);
    }

    #[test]
    fn test_compute_mu_kerbin() {
        let mu = compute_mu(1.0, 600_000.0);
        let expected = 3.5316e12;
        assert!((mu - expected).abs() / expected < 0.001);
    }

    // CurveKey
    #[test]
    fn test_curve_key_creation() {
        let key = CurveKey {
            position: 0.0,
            value: 110.444,
            in_tangent: 0.0,
            out_tangent: -0.01793,
        };
        assert!((key.value - 110.444).abs() < 1e-6);
    }

    // Hermite interpolation
    #[test]
    fn test_hermite_interp_at_key_position() {
        let keys = vec![
            CurveKey {
                position: 0.0,
                value: 110.444,
                in_tangent: 0.0,
                out_tangent: -0.01793,
            },
            CurveKey {
                position: 3547.0,
                value: 62.1074,
                in_tangent: -0.01093,
                out_tangent: -0.01093,
            },
        ];
        let result = hermite_interp(&keys, 0.0).unwrap();
        assert!((result - 110.444).abs() < 1e-6);
    }

    #[test]
    fn test_hermite_interp_midpoint() {
        let keys = vec![
            CurveKey {
                position: 0.0,
                value: 110.444,
                in_tangent: 0.0,
                out_tangent: -0.01793,
            },
            CurveKey {
                position: 3547.0,
                value: 62.1074,
                in_tangent: -0.01093,
                out_tangent: -0.01093,
            },
        ];
        let result = hermite_interp(&keys, 1773.5).unwrap();
        assert!(result > 62.0 && result < 111.0);
    }

    #[test]
    fn test_hermite_interp_clamps_below() {
        let keys = vec![
            CurveKey {
                position: 0.0,
                value: 110.444,
                in_tangent: 0.0,
                out_tangent: -0.01793,
            },
            CurveKey {
                position: 3547.0,
                value: 62.1074,
                in_tangent: -0.01093,
                out_tangent: -0.01093,
            },
        ];
        let result = hermite_interp(&keys, -100.0).unwrap();
        assert!((result - 110.444).abs() < 1e-6);
    }

    #[test]
    fn test_hermite_interp_clamps_above() {
        let keys = vec![
            CurveKey {
                position: 0.0,
                value: 110.444,
                in_tangent: 0.0,
                out_tangent: -0.01793,
            },
            CurveKey {
                position: 3547.0,
                value: 62.1074,
                in_tangent: -0.01093,
                out_tangent: -0.01093,
            },
        ];
        let result = hermite_interp(&keys, 5000.0).unwrap();
        assert!((result - 62.1074).abs() < 1e-6);
    }

    #[test]
    fn test_hermite_interp_empty_keys() {
        let keys: Vec<CurveKey> = vec![];
        assert!(hermite_interp(&keys, 0.0).is_err());
    }

    // CelestialBody
    #[test]
    fn test_celestial_body_mu() {
        let body = CelestialBody::new(
            "Kerbin".to_string(),
            670_000.0,
            1.1,
            true,
            None,
            None,
            90291.8,
            "Sanctar".to_string(),
        );
        let expected = 4.8424e12;
        assert!((body.mu - expected).abs() / expected < 0.001);
    }

    #[test]
    fn test_celestial_body_has_atmosphere() {
        let body_no_atmo = CelestialBody::new(
            "Moon".to_string(),
            200_000.0,
            0.166,
            false,
            None,
            None,
            0.0,
            "Moon".to_string(),
        );
        assert!(!body_no_atmo.has_atmosphere());
    }
}
