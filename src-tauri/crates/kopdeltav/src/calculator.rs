//! Delta-V calculation engine for KSP celestial bodies.
//!
//! 天体のΔV計算エンジン。低軌道投入、ホーマン遷移、ツィオルコフスキー方程式を提供する。
//!
//! Provides empirical launch-to-orbit estimation, Hohmann transfer computation,
//! Tsiolkovsky rocket equation, geostationary orbit calculation, escape/landing
//! ΔV helpers, and a multi-step route planner.

use serde::Serialize;
use std::f64::consts::PI;

use crate::models::{hermite_interp, CelestialBody, G0, R_GAS};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/// Fraction of orbital velocity attributed to gravity loss, scaled by surface gravity.
/// Calibrated against KSP flight data; accuracy ~10%.
const GRAVITY_LOSS_COEFF: f64 = 0.35;

/// Fraction of orbital velocity attributed to atmospheric drag loss,
/// scaled by surface density relative to Earth.
const DRAG_LOSS_COEFF: f64 = 0.13;

/// Fraction of orbital velocity saved by air-breathing (jet) engines in the lower atmosphere.
/// Capped when density ratio >= 1.0.
const JET_SAVINGS_COEFF: f64 = 0.39;

/// Earth sea-level atmospheric density [kg/m^3], used as reference for empirical scaling.
const EARTH_RHO_SEA_LEVEL: f64 = 1.225;

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

/// Type of a delta-V route segment, used for display coloring.
///
/// ΔVルートセグメントの種別。表示時の色分けに使用。
#[derive(Debug, Clone, Serialize)]
pub enum SegmentType {
    /// Launch from surface to low orbit.
    Launch,
    /// Escape from a celestial body's gravity well.
    Escape,
    /// Interplanetary/interlunar Hohmann transfer.
    Transfer,
    /// Orbit insertion (capture burn) at destination.
    Capture,
    /// Landing on a celestial body.
    Landing,
    /// Escape from the entire star system (third cosmic velocity).
    SystemEscape,
    /// Transfer from a planet's orbit to a moon's orbit.
    MoonTransfer,
    /// Landing on a moon.
    MoonLanding,
}

// ---------------------------------------------------------------------------
// Result structs
// ---------------------------------------------------------------------------

/// Results of a launch-to-orbit delta-V calculation.
///
/// 低軌道投入ΔV計算の結果。
#[derive(Debug, Clone, Serialize)]
pub struct LaunchResult {
    /// Circular velocity at target orbit [m/s].
    pub orbital_velocity: f64,
    /// Estimated gravity loss [m/s].
    pub gravity_loss: f64,
    /// Estimated atmospheric drag loss [m/s].
    pub drag_loss: f64,
    /// Theoretical minimum (= orbital velocity) [m/s].
    pub total_ideal: f64,
    /// Practical rocket delta-V with losses [m/s].
    pub total_rocket: f64,
    /// Delta-V saved if using jet engines in lower atmosphere [m/s].
    pub jet_savings: f64,
    /// total_rocket - jet_savings [m/s].
    pub total_with_jets: f64,
}

/// Results of a Hohmann transfer calculation.
///
/// ホーマン遷移計算の結果。
#[derive(Debug, Clone, Serialize)]
pub struct HohmannResult {
    /// Delta-V for departure burn [m/s].
    pub departure_dv: f64,
    /// Delta-V for arrival/capture burn [m/s].
    pub arrival_dv: f64,
    /// Total delta-V (departure + arrival) [m/s].
    pub total_dv: f64,
    /// Transfer time (half-period of the transfer ellipse) [s].
    pub transfer_time: f64,
    /// True if the transfer is to an inner (lower) orbit.
    pub inward: bool,
}

/// Results of the Tsiolkovsky rocket equation.
///
/// ツィオルコフスキーの式の計算結果。
#[derive(Debug, Clone, Serialize)]
pub struct TsiolkovskyResult {
    /// Wet mass / dry mass ratio.
    pub mass_ratio: f64,
    /// Fraction of total mass that is fuel (1 - 1/mass_ratio).
    pub fuel_fraction: f64,
    /// Dry (empty) mass [kg].
    pub dry_mass: f64,
    /// Fuel mass [kg].
    pub fuel_mass: f64,
}

/// A single step in a delta-V route.
///
/// ΔVルートの1ステップ。
#[derive(Debug, Clone, Serialize)]
pub struct DvStep {
    /// Human-readable description of this maneuver.
    pub label: String,
    /// Delta-V for this step [m/s].
    pub dv: f64,
    /// Running total delta-V from mission start [m/s].
    pub cumulative: f64,
    /// Type of maneuver for display purposes.
    pub segment_type: SegmentType,
    /// Optional supplementary information (e.g. aerobrake alternative).
    pub note: String,
}

// ---------------------------------------------------------------------------
// Orbital mechanics
// ---------------------------------------------------------------------------

/// Estimate a reasonable low orbit altitude for the body.
///
/// 天体の妥当な低軌道高度を推定する。
///
/// For bodies with atmosphere, returns approximately 10% above the atmosphere
/// depth to ensure a stable orbit well outside the atmosphere. For airless
/// bodies, returns 5% of the body radius (minimum 10 000 m).
///
/// # Arguments
/// * `body` - Target celestial body.
///
/// # Returns
/// Estimated low orbit altitude above surface [m].
pub fn low_orbit_altitude(body: &CelestialBody) -> f64 {
    if let Some(ref atmo) = body.atmosphere {
        atmo.atmosphere_depth * 1.1
    } else {
        f64::max(body.radius * 0.05, 10_000.0)
    }
}

/// Circular orbital velocity at given altitude above surface.
///
/// 指定高度での円軌道速度を計算する。
///
/// Uses `v_circular = sqrt(mu / r)` where `r = radius + altitude`.
///
/// # Arguments
/// * `body` - Target celestial body.
/// * `altitude` - Altitude above surface [m].
///
/// # Returns
/// Orbital velocity [m/s].
///
/// # Panics
/// Panics if altitude is negative.
pub fn circular_velocity(body: &CelestialBody, altitude: f64) -> f64 {
    assert!(altitude >= 0.0, "Altitude must be non-negative: {altitude}");
    let r = body.radius + altitude;
    (body.mu / r).sqrt()
}

/// Escape velocity at given altitude above surface.
///
/// 指定高度での脱出速度を計算する。
///
/// Uses `v_escape = sqrt(2 * mu / r) = sqrt(2) * v_circular` at the same altitude.
///
/// # Arguments
/// * `body` - Target celestial body.
/// * `altitude` - Altitude above surface [m].
///
/// # Returns
/// Escape velocity [m/s].
///
/// # Panics
/// Panics if altitude is negative.
pub fn escape_velocity(body: &CelestialBody, altitude: f64) -> f64 {
    assert!(altitude >= 0.0, "Altitude must be non-negative: {altitude}");
    let r = body.radius + altitude;
    (2.0 * body.mu / r).sqrt()
}

// ---------------------------------------------------------------------------
// Atmospheric density
// ---------------------------------------------------------------------------

/// Calculate atmospheric density at altitude using hermite-interpolated curves.
///
/// 高度ごとの大気密度をエルミート補間カーブで計算する。
///
/// Applies the ideal gas law `rho = P * M / (R_gas * T)` where pressure and
/// temperature are obtained from the body's atmosphere curves via cubic
/// Hermite spline interpolation. When curves are empty, falls back to
/// sea-level scalar values (meaningful only at altitude 0).
///
/// **Important**: Pressure in the curves is in kPa; it must be converted to
/// Pa (x1000) before applying the ideal gas law.
///
/// # Arguments
/// * `body` - Target celestial body.
/// * `altitude` - Altitude above surface [m].
///
/// # Returns
/// Atmospheric density [kg/m^3], or `None` if the body has no atmosphere.
/// Returns `0.0` for altitudes at or above the atmosphere depth.
pub fn density_at_altitude(body: &CelestialBody, altitude: f64) -> Option<f64> {
    let atmo = body.atmosphere.as_ref()?;

    if altitude >= atmo.atmosphere_depth {
        return Some(0.0);
    }

    // Pressure [kPa] from curve, falling back to sea-level scalar.
    let pressure_kpa = if !atmo.pressure_curve.is_empty() {
        hermite_interp(&atmo.pressure_curve, altitude).unwrap_or(0.0)
    } else if altitude == 0.0 {
        atmo.pressure_at_sea_level
    } else {
        0.0
    };

    // Temperature [K] from curve, falling back to sea-level scalar.
    let temperature_k = if !atmo.temperature_curve.is_empty() {
        hermite_interp(&atmo.temperature_curve, altitude).unwrap_or(0.0)
    } else if altitude == 0.0 {
        atmo.temperature_at_sea_level
    } else {
        0.0
    };

    if temperature_k <= 0.0 || pressure_kpa <= 0.0 {
        return Some(0.0);
    }

    // kPa -> Pa conversion, then ideal gas law: rho = P * M / (R * T).
    let pressure_pa = pressure_kpa * 1000.0;
    Some(pressure_pa * atmo.molar_mass / (R_GAS * temperature_k))
}

/// Calculate sea-level atmospheric density using the ideal gas law.
///
/// 海面大気密度を理想気体の式で計算する。大気なしの場合は None。
///
/// Delegates to [`density_at_altitude`] at altitude 0, which evaluates
/// the pressure and temperature curves at sea level.
///
/// # Arguments
/// * `body` - Target celestial body.
///
/// # Returns
/// Sea-level atmospheric density [kg/m^3], or `None` if no atmosphere.
pub fn surface_density(body: &CelestialBody) -> Option<f64> {
    density_at_altitude(body, 0.0)
}

// ---------------------------------------------------------------------------
// Launch delta-V
// ---------------------------------------------------------------------------

/// Calculate launch-to-orbit delta-V for a body.
///
/// 天体の低軌道投入ΔVを計算する。
///
/// This is an **empirical** model. All loss and savings values are rough
/// approximations calibrated against KSP flight data. Estimated accuracy
/// is +/-10% for `total_rocket` and +/-15% for `jet_savings`. Actual values
/// depend heavily on vehicle design, thrust-to-weight ratio, and ascent profile.
///
/// Assumptions:
/// - **Gravity loss** ~ 15% of orbital velocity, scaled linearly by `gee_asl`.
/// - **Drag loss** ~ 5% of orbital velocity, scaled by `rho/rho_earth`.
/// - **Jet savings** ~ 44% of orbital velocity, capped at density ratio 1.0.
///
/// # Arguments
/// * `body` - Target celestial body.
/// * `target_altitude` - Target circular orbit altitude above surface [m].
///
/// # Returns
/// [`LaunchResult`] with computed delta-V values.
///
/// # Panics
/// Panics if `target_altitude` is negative.
pub fn calculate_launch(body: &CelestialBody, target_altitude: f64) -> LaunchResult {
    assert!(
        target_altitude >= 0.0,
        "Target altitude must be non-negative: {target_altitude}"
    );

    let v_orbital = circular_velocity(body, target_altitude);

    // Gravity loss: scales with surface gravity.
    let gravity_loss = v_orbital * GRAVITY_LOSS_COEFF * body.gee_asl;

    // Drag loss: scales with atmospheric density relative to Earth.
    let rho = surface_density(body);
    let drag_loss = match rho {
        Some(r) if r > 0.0 => v_orbital * DRAG_LOSS_COEFF * (r / EARTH_RHO_SEA_LEVEL),
        _ => 0.0,
    };

    let total_ideal = v_orbital;
    let total_rocket = v_orbital + gravity_loss + drag_loss;

    // Jet savings: only possible with atmosphere; capped at density ratio 1.0.
    let jet_savings = match rho {
        Some(r) if r > 0.0 => {
            let density_factor = (r / EARTH_RHO_SEA_LEVEL).min(1.0);
            v_orbital * JET_SAVINGS_COEFF * density_factor
        }
        _ => 0.0,
    };

    let total_with_jets = total_rocket - jet_savings;

    LaunchResult {
        orbital_velocity: v_orbital,
        gravity_loss,
        drag_loss,
        total_ideal,
        total_rocket,
        jet_savings,
        total_with_jets,
    }
}

// ---------------------------------------------------------------------------
// Hohmann transfer
// ---------------------------------------------------------------------------

/// Calculate Hohmann transfer from parking orbit to target orbit.
///
/// パーキング軌道からターゲット軌道へのホーマン遷移ΔVを計算する。
///
/// Supports both outward (target > parking) and inward (target < parking)
/// transfers. For inward transfers the vis-viva computation uses the
/// swapped radii internally and the returned departure/arrival delta-Vs are
/// swapped so that `departure_dv` is the burn at the parking orbit and
/// `arrival_dv` is the burn at the target orbit.
///
/// Standard Hohmann transfer equations (outward case):
/// ```text
/// a_transfer = (r1 + r2) / 2
/// v_transfer_peri = sqrt(mu * (2/r1 - 1/a_transfer))
/// departure_dv = v_transfer_peri - v_circular(r1)
/// v_transfer_apo  = sqrt(mu * (2/r2 - 1/a_transfer))
/// arrival_dv = v_circular(r2) - v_transfer_apo
/// transfer_time = pi * sqrt(a_transfer^3 / mu)
/// ```
///
/// # Arguments
/// * `body` - Central body being orbited.
/// * `parking_altitude` - Altitude of circular parking orbit above surface [m].
/// * `target_sma` - Semi-major axis of target orbit [m] (from body center).
///
/// # Returns
/// [`HohmannResult`] with delta-V and transfer time values.
///
/// # Panics
/// Panics if `parking_altitude` is negative or the parking orbit radius
/// and `target_sma` are identical (zero-ΔV transfer).
pub fn calculate_hohmann(
    body: &CelestialBody,
    parking_altitude: f64,
    target_sma: f64,
) -> HohmannResult {
    assert!(
        parking_altitude >= 0.0,
        "Parking altitude must be non-negative: {parking_altitude}"
    );

    let r_parking = body.radius + parking_altitude;
    let r_target = target_sma;

    assert!(
        (r_parking - r_target).abs() / r_parking.max(r_target) > 1e-12,
        "Parking orbit radius ({r_parking} m) and target SMA ({r_target} m) \
         are identical; Hohmann transfer is undefined"
    );

    let inward = r_target < r_parking;

    // For vis-viva, r_inner is the periapsis and r_outer is the apoapsis.
    let r_inner = r_parking.min(r_target);
    let r_outer = r_parking.max(r_target);

    let mu = body.mu;
    let a_transfer = (r_inner + r_outer) / 2.0;

    // Burn at periapsis of the transfer ellipse.
    let v_inner_circular = (mu / r_inner).sqrt();
    let v_transfer_peri = (mu * (2.0 / r_inner - 1.0 / a_transfer)).sqrt();
    let dv_peri = v_transfer_peri - v_inner_circular;

    // Burn at apoapsis of the transfer ellipse.
    let v_outer_circular = (mu / r_outer).sqrt();
    let v_transfer_apo = (mu * (2.0 / r_outer - 1.0 / a_transfer)).sqrt();
    let dv_apo = v_outer_circular - v_transfer_apo;

    // Transfer time: half the period of the transfer ellipse.
    let transfer_time = PI * (a_transfer.powi(3) / mu).sqrt();

    let (departure_dv, arrival_dv) = if inward {
        // Inward: departure is at the outer (parking) orbit, arrival at inner.
        (dv_apo, dv_peri)
    } else {
        // Outward: departure is at the inner (parking) orbit, arrival at outer.
        (dv_peri, dv_apo)
    };

    HohmannResult {
        departure_dv,
        arrival_dv,
        total_dv: departure_dv + arrival_dv,
        transfer_time,
        inward,
    }
}

// ---------------------------------------------------------------------------
// Tsiolkovsky rocket equation
// ---------------------------------------------------------------------------

/// Apply the Tsiolkovsky rocket equation.
///
/// ツィオルコフスキーの式を適用して質量比を計算する。
///
/// ```text
/// dv = Isp * g0 * ln(m_wet / m_dry)
/// mass_ratio = exp(dv / (Isp * g0))
/// ```
///
/// # Arguments
/// * `delta_v` - Required delta-V [m/s].
/// * `isp` - Specific impulse [s].
/// * `wet_mass` - Total (wet) mass [kg].
///
/// # Returns
/// [`TsiolkovskyResult`] with mass ratio and fuel breakdown.
///
/// # Panics
/// Panics if `delta_v` is negative, `isp` is non-positive, or
/// `wet_mass` is non-positive.
pub fn calculate_tsiolkovsky(delta_v: f64, isp: f64, wet_mass: f64) -> TsiolkovskyResult {
    assert!(delta_v >= 0.0, "delta_v must be non-negative: {delta_v}");
    assert!(isp > 0.0, "Isp must be positive: {isp}");
    assert!(wet_mass > 0.0, "wet_mass must be positive: {wet_mass}");

    let ve = isp * G0; // effective exhaust velocity [m/s]
    let mass_ratio = (delta_v / ve).exp();
    let fuel_fraction = 1.0 - 1.0 / mass_ratio;
    let dry_mass = wet_mass / mass_ratio;
    let fuel_mass = wet_mass - dry_mass;

    TsiolkovskyResult {
        mass_ratio,
        fuel_fraction,
        dry_mass,
        fuel_mass,
    }
}

// ---------------------------------------------------------------------------
// Geostationary orbit
// ---------------------------------------------------------------------------

/// Calculate the altitude of a geostationary orbit.
///
/// 静止軌道の高度を計算する。
///
/// Uses the formula:
/// ```text
/// r_geo = (mu * T^2 / (4 * pi^2))^(1/3)
/// altitude = r_geo - radius
/// ```
///
/// where `T` is the sidereal rotation period of the body.
///
/// # Arguments
/// * `body` - Target celestial body.
///
/// # Returns
/// Geostationary orbit altitude above surface [m].
///
/// # Panics
/// Panics if `body.rotational_period` is non-positive.
pub fn geostationary_altitude(body: &CelestialBody) -> f64 {
    assert!(
        body.rotational_period > 0.0,
        "Rotational period must be positive for a geostationary orbit: {}",
        body.rotational_period
    );
    let t = body.rotational_period;
    let r_geo = (body.mu * t * t / (4.0 * PI * PI)).powf(1.0 / 3.0);
    r_geo - body.radius
}

/// Calculate the delta-V for a Hohmann transfer from low orbit to geostationary orbit.
///
/// 低軌道から静止軌道へのホーマン遷移ΔVを計算する。
///
/// # Arguments
/// * `body` - Target celestial body.
///
/// # Returns
/// [`HohmannResult`] for the low orbit -> geostationary transfer.
///
/// # Panics
/// Panics if `body.rotational_period` is non-positive, or if the
/// geostationary orbit is below the low orbit (extremely fast rotators).
pub fn geostationary_dv(body: &CelestialBody) -> HohmannResult {
    let lo_alt = low_orbit_altitude(body);
    let geo_alt = geostationary_altitude(body);
    let geo_sma = body.radius + geo_alt;
    calculate_hohmann(body, lo_alt, geo_sma)
}

// ---------------------------------------------------------------------------
// Escape delta-V from low orbit
// ---------------------------------------------------------------------------

/// Calculate the delta-V needed to escape from low orbit.
///
/// 低軌道から脱出するのに必要なΔVを計算する。
///
/// Computes `v_escape(lo_alt) - v_circular(lo_alt)`, which is the
/// impulsive burn required to reach escape velocity from a circular
/// parking orbit at the standard low orbit altitude.
///
/// # Arguments
/// * `body` - Target celestial body.
///
/// # Returns
/// Escape delta-V from low orbit [m/s]. Always positive.
pub fn escape_dv_from_low_orbit(body: &CelestialBody) -> f64 {
    let lo_alt = low_orbit_altitude(body);
    let v_esc = escape_velocity(body, lo_alt);
    let v_circ = circular_velocity(body, lo_alt);
    v_esc - v_circ
}

// ---------------------------------------------------------------------------
// Landing delta-V
// ---------------------------------------------------------------------------

/// Estimate the delta-V required to land on a body.
///
/// 天体への着陸に必要なΔVを推定する。
///
/// The powered landing delta-V is approximated as the circular orbital velocity
/// at the low orbit altitude -- representing the speed that must be cancelled
/// to descend from orbit to the surface.
///
/// For bodies **with** atmosphere, aerobraking can absorb most of the
/// orbital energy; the aerobrake contribution is returned as `Some(0.0)`.
///
/// For bodies **without** atmosphere, there is no aerobraking option, so
/// the second element is `None`.
///
/// # Arguments
/// * `body` - Target celestial body.
///
/// # Returns
/// A tuple `(powered_dv, aerobrake_dv)` where:
/// - `powered_dv`: delta-V for a fully powered landing [m/s]. Always > 0.
/// - `aerobrake_dv`: `Some(0.0)` if the body has atmosphere; `None` if no atmosphere.
pub fn landing_dv(body: &CelestialBody) -> (f64, Option<f64>) {
    let lo_alt = low_orbit_altitude(body);
    let powered_dv = circular_velocity(body, lo_alt);
    let aerobrake_dv = if body.atmosphere.is_some() {
        Some(0.0)
    } else {
        None
    };
    (powered_dv, aerobrake_dv)
}

// ---------------------------------------------------------------------------
// Delta-V route planner
// ---------------------------------------------------------------------------

/// Compute a delta-V route from the home world to an optional destination.
///
/// ホームワールドから目的地までのΔVルートを計算する。
///
/// Three modes depending on the arguments:
///
/// **Third cosmic velocity** (`destination = None`):
///   1. Launch to low orbit.
///   2. Escape home world.
///   3. Escape star system.
///
/// **Planet flyby / capture** (`destination = Some(planet)`, `moon = None`):
///   1. Launch to low orbit.
///   2. Escape home world.
///   3. Hohmann transfer in parent body's frame.
///   4. Destination orbit insertion (capture burn).
///   5. Landing on destination.
///
/// **Moon mission** (`destination = Some(planet)`, `moon = Some(satellite)`):
///   Steps 1-4 as above.
///   5. Hohmann transfer from destination low orbit to moon SMA.
///   6. Landing on moon.
///
/// # Arguments
/// * `home` - Home world celestial body (must have orbit and parent).
/// * `parent` - Parent star/body that home orbits.
/// * `destination` - Target planet (must orbit the same parent as home). Pass `None` for third cosmic velocity.
/// * `moon` - Target moon orbiting destination. Ignored when destination is `None`.
///
/// # Returns
/// Ordered list of [`DvStep`] objects representing each maneuver.
///
/// # Panics
/// Panics if home has no orbit data, or if destination/moon have no orbit data when provided.
pub fn compute_route(
    home: &CelestialBody,
    parent: &CelestialBody,
    destination: Option<&CelestialBody>,
    moon: Option<&CelestialBody>,
) -> Vec<DvStep> {
    let home_orbit = home
        .orbit
        .as_ref()
        .expect("Home world has no orbital elements; cannot compute interplanetary route.");

    let mut steps: Vec<DvStep> = Vec::new();
    let mut cumulative = 0.0;

    let add_step = |steps: &mut Vec<DvStep>,
                    cumulative: &mut f64,
                    label: String,
                    dv: f64,
                    seg_type: SegmentType,
                    note: String| {
        *cumulative += dv;
        steps.push(DvStep {
            label,
            dv,
            cumulative: *cumulative,
            segment_type: seg_type,
            note,
        });
    };

    // Step 1: Launch to low orbit.
    let lo_alt = low_orbit_altitude(home);
    let launch = calculate_launch(home, lo_alt);
    add_step(
        &mut steps,
        &mut cumulative,
        "Launch to low orbit".to_string(),
        launch.total_rocket,
        SegmentType::Launch,
        String::new(),
    );

    // Step 2: Escape home world.
    let esc_home = escape_dv_from_low_orbit(home);
    add_step(
        &mut steps,
        &mut cumulative,
        format!("Escape {}", home.name),
        esc_home,
        SegmentType::Escape,
        String::new(),
    );

    let destination = match destination {
        Some(d) => d,
        None => {
            // Third cosmic velocity: escape the parent star system from home orbit.
            let home_sma = home_orbit.semi_major_axis;
            let home_orbit_alt = home_sma - parent.radius;
            let v_esc_star = escape_velocity(parent, home_orbit_alt);
            let v_circ_star = circular_velocity(parent, home_orbit_alt);
            let esc_star = v_esc_star - v_circ_star;
            add_step(
                &mut steps,
                &mut cumulative,
                format!("Escape {} system", parent.name),
                esc_star,
                SegmentType::SystemEscape,
                String::new(),
            );
            return steps;
        }
    };

    let dest_orbit = destination
        .orbit
        .as_ref()
        .expect("Destination has no orbital elements.");

    // Step 3: Hohmann transfer in parent's frame.
    let home_sma = home_orbit.semi_major_axis;
    let home_orbit_alt = home_sma - parent.radius;
    let dest_sma = dest_orbit.semi_major_axis;
    let hohmann = calculate_hohmann(parent, home_orbit_alt, dest_sma);
    add_step(
        &mut steps,
        &mut cumulative,
        format!("Transfer to {}", destination.name),
        hohmann.departure_dv,
        SegmentType::Transfer,
        String::new(),
    );

    // Step 4: Capture at destination.
    let esc_dest = escape_dv_from_low_orbit(destination);
    add_step(
        &mut steps,
        &mut cumulative,
        format!("Capture at {}", destination.name),
        esc_dest,
        SegmentType::Capture,
        String::new(),
    );

    match moon {
        None => {
            // Step 5: Land on destination.
            let (powered_dv, aerobrake_dv) = landing_dv(destination);
            let note = match aerobrake_dv {
                Some(v) => format!("aerobrake option: {v} m/s"),
                None => String::new(),
            };
            add_step(
                &mut steps,
                &mut cumulative,
                format!("Land on {}", destination.name),
                powered_dv,
                SegmentType::Landing,
                note,
            );
        }
        Some(moon_body) => {
            let moon_orbit = moon_body
                .orbit
                .as_ref()
                .expect("Moon has no orbital elements.");

            // Step 5: Transfer from destination low orbit to moon SMA.
            let dest_lo_alt = low_orbit_altitude(destination);
            let moon_sma = moon_orbit.semi_major_axis;
            let moon_hohmann = calculate_hohmann(destination, dest_lo_alt, moon_sma);
            add_step(
                &mut steps,
                &mut cumulative,
                format!("Transfer to {}", moon_body.name),
                moon_hohmann.departure_dv,
                SegmentType::MoonTransfer,
                String::new(),
            );

            // Step 6: Land on moon.
            let (powered_dv_moon, aerobrake_dv_moon) = landing_dv(moon_body);
            let note_moon = match aerobrake_dv_moon {
                Some(v) => format!("aerobrake option: {v} m/s"),
                None => String::new(),
            };
            add_step(
                &mut steps,
                &mut cumulative,
                format!("Land on {}", moon_body.name),
                powered_dv_moon,
                SegmentType::MoonLanding,
                note_moon,
            );
        }
    }

    steps
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::*;

    fn make_sanctar() -> CelestialBody {
        let mut body = CelestialBody::new(
            "Kerbin".to_string(),
            670_000.0,
            1.1,
            true,
            Some(Atmosphere {
                atmosphere_depth: 72_000.0,
                pressure_curve: vec![
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
                ],
                temperature_curve: vec![
                    CurveKey {
                        position: 0.0,
                        value: 281.0,
                        in_tangent: 0.0,
                        out_tangent: -0.00536,
                    },
                    CurveKey {
                        position: 72000.0,
                        value: 187.0,
                        in_tangent: 0.0,
                        out_tangent: 0.0,
                    },
                ],
                molar_mass: 0.02897,
                adiabatic_index: 1.4,
                pressure_at_sea_level: 110.444,
                temperature_at_sea_level: 281.0,
            }),
            None,
            90291.8,
            "Sanctar".to_string(),
        );
        body.is_home_world = true;
        body
    }

    fn make_kerbin() -> CelestialBody {
        let mut body = CelestialBody::new(
            "Kerbin".to_string(),
            600_000.0,
            1.0,
            true,
            Some(Atmosphere {
                atmosphere_depth: 70_000.0,
                pressure_curve: vec![
                    CurveKey {
                        position: 0.0,
                        value: 101.325,
                        in_tangent: 0.0,
                        out_tangent: -0.015,
                    },
                    CurveKey {
                        position: 70000.0,
                        value: 0.0,
                        in_tangent: -0.001,
                        out_tangent: 0.0,
                    },
                ],
                temperature_curve: vec![
                    CurveKey {
                        position: 0.0,
                        value: 288.0,
                        in_tangent: 0.0,
                        out_tangent: -0.006,
                    },
                    CurveKey {
                        position: 70000.0,
                        value: 200.0,
                        in_tangent: 0.0,
                        out_tangent: 0.0,
                    },
                ],
                molar_mass: 0.02897,
                adiabatic_index: 1.4,
                pressure_at_sea_level: 101.325,
                temperature_at_sea_level: 288.0,
            }),
            None,
            21549.425,
            "Kerbin".to_string(),
        );
        body.is_home_world = true;
        body
    }

    fn make_airless() -> CelestialBody {
        CelestialBody::new(
            "Mun".to_string(),
            200_000.0,
            0.166,
            false,
            None,
            None,
            0.0,
            "Mun".to_string(),
        )
    }

    #[test]
    fn test_escape_velocity_sanctar() {
        let body = make_sanctar();
        let v = escape_velocity(&body, 0.0);
        assert!(
            (v - 3802.0).abs() / 3802.0 < 0.001,
            "Expected ~3802, got {v}"
        );
    }

    #[test]
    fn test_escape_velocity_kerbin() {
        let body = make_kerbin();
        let v = escape_velocity(&body, 0.0);
        assert!(
            (v - 3431.0).abs() / 3431.0 < 0.002,
            "Expected ~3431, got {v}"
        );
    }

    #[test]
    fn test_circular_velocity_sanctar_low_orbit() {
        let body = make_sanctar();
        let alt = low_orbit_altitude(&body);
        let v = circular_velocity(&body, alt);
        assert!(
            (v - 2541.1).abs() / 2541.1 < 0.01,
            "Expected ~2541.1, got {v}"
        );
    }

    #[test]
    fn test_low_orbit_altitude_with_atmosphere() {
        let body = make_sanctar();
        let alt = low_orbit_altitude(&body);
        assert!(
            (alt - 79200.0).abs() < 100.0,
            "Expected ~79200 (72000 * 1.1), got {alt}"
        );
    }

    #[test]
    fn test_low_orbit_altitude_airless() {
        let body = make_airless();
        let alt = low_orbit_altitude(&body);
        assert!(
            (alt - 10_000.0).abs() < 1.0,
            "Expected ~10000 (max(200000*0.05=10000, 10000)), got {alt}"
        );
    }

    #[test]
    fn test_surface_density_sanctar() {
        let body = make_sanctar();
        let rho = surface_density(&body).unwrap();
        assert!(
            (rho - 1.4096).abs() / 1.4096 < 0.05,
            "Expected ~1.4096, got {rho}"
        );
    }

    #[test]
    fn test_surface_density_airless() {
        let body = make_airless();
        assert!(surface_density(&body).is_none());
    }

    #[test]
    fn test_calculate_launch_sanctar() {
        let body = make_sanctar();
        let alt = low_orbit_altitude(&body);
        let result = calculate_launch(&body, alt);
        assert!(
            (result.total_rocket - 3891.0).abs() / 3891.0 < 0.02,
            "Expected total_rocket ~3891, got {}",
            result.total_rocket
        );
        assert!(
            (result.total_with_jets - 2899.0).abs() / 2899.0 < 0.02,
            "Expected total_with_jets ~2899, got {}",
            result.total_with_jets
        );
    }

    #[test]
    fn test_calculate_hohmann_outward() {
        let body = make_sanctar();
        let result = calculate_hohmann(&body, 80_000.0, 13_116_000_574.0);
        assert!(result.departure_dv > 0.0);
        assert!(result.arrival_dv > 0.0);
        assert!(!result.inward);
    }

    #[test]
    fn test_calculate_hohmann_inward() {
        let body = make_sanctar();
        let result = calculate_hohmann(&body, 80_000.0, 100_000.0);
        assert!(result.inward);
    }

    #[test]
    fn test_calculate_tsiolkovsky() {
        let result = calculate_tsiolkovsky(3100.0, 310.0, 50_000.0);
        assert!(result.mass_ratio > 1.0);
        assert!(result.fuel_fraction > 0.0 && result.fuel_fraction < 1.0);
        assert!(
            (result.dry_mass + result.fuel_mass - 50_000.0).abs() < 1.0,
            "dry + fuel should equal wet mass: {} + {} = {}",
            result.dry_mass,
            result.fuel_mass,
            result.dry_mass + result.fuel_mass
        );
    }

    #[test]
    fn test_geostationary_altitude() {
        let body = make_sanctar();
        let alt = geostationary_altitude(&body);
        assert!(
            alt > 0.0,
            "Geostationary altitude should be positive, got {alt}"
        );
    }

    #[test]
    fn test_landing_dv_with_atmosphere() {
        let body = make_sanctar();
        let (powered, aerobrake) = landing_dv(&body);
        assert!(powered > 0.0);
        assert_eq!(aerobrake, Some(0.0));
    }

    #[test]
    fn test_landing_dv_airless() {
        let body = make_airless();
        let (powered, aerobrake) = landing_dv(&body);
        assert!(powered > 0.0);
        assert!(aerobrake.is_none());
    }

    #[test]
    fn test_escape_dv_from_low_orbit() {
        let body = make_sanctar();
        let dv = escape_dv_from_low_orbit(&body);
        assert!(dv > 0.0, "Escape dv should be positive, got {dv}");
        // Escape dv should be less than escape velocity (since we start from orbit)
        let v_esc = escape_velocity(&body, 0.0);
        assert!(
            dv < v_esc,
            "Escape dv from orbit ({dv}) should be < surface escape ({v_esc})"
        );
    }

    #[test]
    fn test_density_at_altitude_above_atmosphere() {
        let body = make_sanctar();
        let rho = density_at_altitude(&body, 100_000.0).unwrap();
        assert!(
            (rho - 0.0).abs() < 1e-10,
            "Density above atmosphere should be 0, got {rho}"
        );
    }

    #[test]
    fn test_compute_route_third_cosmic() {
        let mut home = make_sanctar();
        home.orbit = Some(OrbitalElements {
            semi_major_axis: 13_116_000_574.0,
            eccentricity: 0.0,
            inclination: 0.0,
            argument_of_periapsis: 0.0,
            longitude_of_ascending_node: 0.0,
            mean_anomaly_at_epoch: 0.0,
            epoch: 0.0,
        });

        let parent = CelestialBody::new(
            "Star".to_string(),
            261_600_000.0,
            1.0,
            false,
            None,
            None,
            0.0,
            "Star".to_string(),
        );

        let steps = compute_route(&home, &parent, None, None);
        assert_eq!(steps.len(), 3, "Third cosmic velocity should have 3 steps");
        assert!(steps[0].dv > 0.0);
        assert!(steps[1].dv > 0.0);
        assert!(steps[2].dv > 0.0);
        assert!(steps[2].cumulative > steps[1].cumulative);
    }
}
