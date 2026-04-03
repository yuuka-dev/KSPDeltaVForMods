//! Tauri command handlers that bridge the frontend to the kopdeltav crate.
//!
//! Each command locks the shared `ManagedState`, delegates to kopdeltav functions,
//! and returns `Result<T, String>` for Tauri IPC compatibility.
//!
//! Tauri コマンドハンドラ。フロントエンドと kopdeltav クレートの橋渡し。

use serde::Serialize;
use std::collections::HashMap;

use kopdeltav::calculator::{
    calculate_hohmann, calculate_launch, calculate_tsiolkovsky, circular_velocity, compute_route,
    density_at_altitude, escape_dv_from_low_orbit, geostationary_altitude, geostationary_dv,
    landing_dv, low_orbit_altitude, surface_density,
};
use kopdeltav::models::{hermite_interp, CelestialBody};
use kopdeltav::parser::parse_bodies;
use kopdeltav::system::{build_tree, scan_configs, sort_by_transfer_dv};

use crate::state::ManagedState;

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

/// Summary representation of a celestial body for list views.
#[derive(Serialize)]
pub struct BodySummary {
    pub name: String,
    pub display_name: String,
    pub radius: f64,
    pub gee_asl: f64,
    pub has_atmosphere: bool,
    pub has_ocean: bool,
}

/// Orbital elements response matching TypeScript interfaces.
#[derive(Serialize)]
pub struct OrbitResponse {
    pub semi_major_axis: f64,
    pub eccentricity: f64,
    pub inclination: f64,
    pub argument_of_periapsis: f64,
    pub longitude_of_ascending_node: f64,
    pub mean_anomaly_at_epoch: f64,
    pub epoch: f64,
}

/// Atmosphere summary response.
#[derive(Serialize)]
pub struct AtmosphereResponse {
    pub atmosphere_depth: f64,
    pub pressure_at_sea_level: f64,
    pub temperature_at_sea_level: f64,
    pub molar_mass: f64,
    pub adiabatic_index: f64,
    pub sea_level_density: Option<f64>,
}

/// Detailed celestial body response.
#[derive(Serialize)]
pub struct BodyDetail {
    pub name: String,
    pub display_name: String,
    pub radius: f64,
    pub gee_asl: f64,
    pub mu: f64,
    pub has_ocean: bool,
    pub rotational_period: f64,
    pub soi: f64,
    pub atmosphere: Option<AtmosphereResponse>,
    pub orbit: Option<OrbitResponse>,
}

/// Launch-to-orbit calculation response.
#[derive(Serialize)]
pub struct LaunchResponse {
    pub orbital_velocity: f64,
    pub gravity_loss: f64,
    pub drag_loss: f64,
    pub total_ideal: f64,
    pub total_rocket: f64,
    pub jet_savings: f64,
    pub total_with_jets: f64,
}

/// Hohmann transfer calculation response.
#[derive(Serialize)]
pub struct HohmannResponse {
    pub departure_dv: f64,
    pub arrival_dv: f64,
    pub total_dv: f64,
    pub transfer_time: f64,
    pub inward: bool,
}

/// Tsiolkovsky equation response.
#[derive(Serialize)]
pub struct TsiolkovskyResponse {
    pub mass_ratio: f64,
    pub fuel_fraction: f64,
    pub dry_mass: f64,
    pub fuel_mass: f64,
}

/// Config upload/scan result.
#[derive(Serialize)]
pub struct UploadResponse {
    pub bodies_added: Vec<String>,
    pub count: usize,
}

/// A node in the celestial body tree for hierarchical display.
#[derive(Serialize)]
pub struct BodyTreeNode {
    pub name: String,
    pub display_name: String,
    pub children: Vec<BodyTreeNode>,
}

/// Full celestial system response.
#[derive(Serialize)]
pub struct SystemResponse {
    pub root: BodySummary,
    pub home_world: BodyDetail,
    pub body_count: usize,
    pub tree: Vec<BodyTreeNode>,
}

/// A destination body with its transfer delta-V.
#[derive(Serialize)]
pub struct DestinationEntry {
    pub body: BodySummary,
    pub transfer_dv: f64,
}

/// A single step in a delta-V route.
#[derive(Serialize)]
pub struct DvStepResponse {
    pub label: String,
    pub dv: f64,
    pub cumulative: f64,
    pub note: String,
}

/// Full route response.
#[derive(Serialize)]
pub struct RouteResponse {
    pub steps: Vec<DvStepResponse>,
    pub total_powered: f64,
    pub total_aerobrake: Option<f64>,
}

/// Atmosphere profile sampled at regular altitude intervals.
#[derive(Serialize)]
pub struct AtmoProfileResponse {
    pub altitude: Vec<f64>,
    pub pressure: Vec<f64>,
    pub temperature: Vec<f64>,
    pub density: Vec<f64>,
}

// ---------------------------------------------------------------------------
// Conversion helpers
// ---------------------------------------------------------------------------

/// Convert a `CelestialBody` to a `BodySummary`.
fn body_to_summary(body: &CelestialBody) -> BodySummary {
    BodySummary {
        name: body.name.clone(),
        display_name: body.display_name.clone(),
        radius: body.radius,
        gee_asl: body.gee_asl,
        has_atmosphere: body.has_atmosphere(),
        has_ocean: body.has_ocean,
    }
}

/// Convert a `CelestialBody` to a `BodyDetail`.
fn body_to_detail(body: &CelestialBody) -> BodyDetail {
    let atmosphere = body.atmosphere.as_ref().map(|atmo| {
        let sea_level_density = surface_density(body);
        AtmosphereResponse {
            atmosphere_depth: atmo.atmosphere_depth,
            pressure_at_sea_level: atmo.pressure_at_sea_level,
            temperature_at_sea_level: atmo.temperature_at_sea_level,
            molar_mass: atmo.molar_mass,
            adiabatic_index: atmo.adiabatic_index,
            sea_level_density,
        }
    });

    let orbit = body.orbit.as_ref().map(|o| OrbitResponse {
        semi_major_axis: o.semi_major_axis,
        eccentricity: o.eccentricity,
        inclination: o.inclination,
        argument_of_periapsis: o.argument_of_periapsis,
        longitude_of_ascending_node: o.longitude_of_ascending_node,
        mean_anomaly_at_epoch: o.mean_anomaly_at_epoch,
        epoch: o.epoch,
    });

    BodyDetail {
        name: body.name.clone(),
        display_name: body.display_name.clone(),
        radius: body.radius,
        gee_asl: body.gee_asl,
        mu: body.mu,
        has_ocean: body.has_ocean,
        rotational_period: body.rotational_period,
        soi: body.soi,
        atmosphere,
        orbit,
    }
}

/// Build a tree node recursively from the body map.
fn build_tree_node(name: &str, bodies: &HashMap<String, CelestialBody>) -> Option<BodyTreeNode> {
    let body = bodies.get(name)?;
    let children = body
        .children_names
        .iter()
        .filter_map(|child_name| build_tree_node(child_name, bodies))
        .collect();
    Some(BodyTreeNode {
        name: body.name.clone(),
        display_name: body.display_name.clone(),
        children,
    })
}

/// Try to rebuild the system tree from current bodies and store it in state.
/// Returns the list of body names added.
fn rebuild_system(
    bodies: &HashMap<String, CelestialBody>,
) -> Option<kopdeltav::system::CelestialSystem> {
    if bodies.is_empty() {
        return None;
    }
    let body_list: Vec<CelestialBody> = bodies.values().cloned().collect();
    build_tree(body_list).ok()
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

/// Health check endpoint.
#[tauri::command]
pub fn health() -> serde_json::Value {
    serde_json::json!({"status": "ok"})
}

/// Upload and parse a Kopernicus config string, adding bodies to state.
#[tauri::command]
pub fn upload_config(
    file_content: String,
    state: tauri::State<'_, ManagedState>,
) -> Result<UploadResponse, String> {
    let mut app = state.lock().map_err(|e| e.to_string())?;
    let parsed = parse_bodies(&file_content);
    if parsed.is_empty() {
        return Err("No celestial bodies found in config".to_string());
    }

    let mut added: Vec<String> = Vec::new();
    for body in parsed {
        added.push(body.name.clone());
        app.bodies.insert(body.name.clone(), body);
    }

    // Try rebuilding the system tree
    app.system = rebuild_system(&app.bodies);

    let count = added.len();
    Ok(UploadResponse {
        bodies_added: added,
        count,
    })
}

/// Scan a GameData directory for Kopernicus configs and replace state entirely.
#[tauri::command]
pub fn scan_gamedata(
    path: String,
    exclude: Vec<String>,
    state: tauri::State<'_, ManagedState>,
) -> Result<UploadResponse, String> {
    let system = scan_configs(&path, &exclude)?;

    let added: Vec<String> = system.bodies.keys().cloned().collect();
    let count = added.len();

    let mut app = state.lock().map_err(|e| e.to_string())?;
    app.bodies = system.bodies.clone();
    app.system = Some(system);

    Ok(UploadResponse {
        bodies_added: added,
        count,
    })
}

/// List all loaded celestial bodies as summaries.
#[tauri::command]
pub fn list_bodies(
    _lang: Option<String>,
    state: tauri::State<'_, ManagedState>,
) -> Result<Vec<BodySummary>, String> {
    let app = state.lock().map_err(|e| e.to_string())?;
    let mut summaries: Vec<BodySummary> = app.bodies.values().map(body_to_summary).collect();
    summaries.sort_by(|a, b| a.name.cmp(&b.name));
    Ok(summaries)
}

/// Get detailed information for a specific celestial body.
#[tauri::command]
pub fn get_body(
    name: String,
    _lang: Option<String>,
    state: tauri::State<'_, ManagedState>,
) -> Result<BodyDetail, String> {
    let app = state.lock().map_err(|e| e.to_string())?;
    let body = app
        .bodies
        .get(&name)
        .ok_or_else(|| format!("Body not found: {}", name))?;
    Ok(body_to_detail(body))
}

/// Calculate launch-to-orbit delta-V for a body.
#[tauri::command]
pub fn calc_launch(
    body_name: String,
    target_altitude: f64,
    state: tauri::State<'_, ManagedState>,
) -> Result<LaunchResponse, String> {
    let app = state.lock().map_err(|e| e.to_string())?;
    let body = app
        .bodies
        .get(&body_name)
        .ok_or_else(|| format!("Body not found: {}", body_name))?;

    if target_altitude < 0.0 {
        return Err("Target altitude must be non-negative".to_string());
    }

    let result = calculate_launch(body, target_altitude);
    Ok(LaunchResponse {
        orbital_velocity: result.orbital_velocity,
        gravity_loss: result.gravity_loss,
        drag_loss: result.drag_loss,
        total_ideal: result.total_ideal,
        total_rocket: result.total_rocket,
        jet_savings: result.jet_savings,
        total_with_jets: result.total_with_jets,
    })
}

/// Calculate Hohmann transfer delta-V.
#[tauri::command]
pub fn calc_hohmann(
    body_name: String,
    parking_alt: f64,
    target_sma: f64,
    state: tauri::State<'_, ManagedState>,
) -> Result<HohmannResponse, String> {
    let app = state.lock().map_err(|e| e.to_string())?;
    let body = app
        .bodies
        .get(&body_name)
        .ok_or_else(|| format!("Body not found: {}", body_name))?;

    if parking_alt < 0.0 {
        return Err("Parking altitude must be non-negative".to_string());
    }

    let r_parking = body.radius + parking_alt;
    if (r_parking - target_sma).abs() / r_parking.max(target_sma) < 1e-12 {
        return Err("Parking orbit and target SMA are identical".to_string());
    }

    let result = calculate_hohmann(body, parking_alt, target_sma);
    Ok(HohmannResponse {
        departure_dv: result.departure_dv,
        arrival_dv: result.arrival_dv,
        total_dv: result.total_dv,
        transfer_time: result.transfer_time,
        inward: result.inward,
    })
}

/// Apply the Tsiolkovsky rocket equation.
#[tauri::command]
pub fn calc_tsiolkovsky(
    delta_v: f64,
    isp: f64,
    wet_mass: f64,
) -> Result<TsiolkovskyResponse, String> {
    if delta_v < 0.0 {
        return Err("delta_v must be non-negative".to_string());
    }
    if isp <= 0.0 {
        return Err("Isp must be positive".to_string());
    }
    if wet_mass <= 0.0 {
        return Err("Wet mass must be positive".to_string());
    }

    let result = calculate_tsiolkovsky(delta_v, isp, wet_mass);
    Ok(TsiolkovskyResponse {
        mass_ratio: result.mass_ratio,
        fuel_fraction: result.fuel_fraction,
        dry_mass: result.dry_mass,
        fuel_mass: result.fuel_mass,
    })
}

/// Get the full celestial system tree.
#[tauri::command]
pub fn get_system(
    state: tauri::State<'_, ManagedState>,
) -> Result<SystemResponse, String> {
    let app = state.lock().map_err(|e| e.to_string())?;
    let system = app
        .system
        .as_ref()
        .ok_or_else(|| "No system loaded. Upload a config or scan GameData first.".to_string())?;

    let root_body = system
        .bodies
        .get(&system.root_name)
        .ok_or_else(|| format!("Root body '{}' not found in system", system.root_name))?;

    let home_body = system
        .bodies
        .get(&system.home_world_name)
        .ok_or_else(|| {
            format!(
                "Home world '{}' not found in system",
                system.home_world_name
            )
        })?;

    let tree = root_body
        .children_names
        .iter()
        .filter_map(|child_name| build_tree_node(child_name, &system.bodies))
        .collect();

    Ok(SystemResponse {
        root: body_to_summary(root_body),
        home_world: body_to_detail(home_body),
        body_count: system.bodies.len(),
        tree,
    })
}

/// Get sibling bodies sorted by transfer delta-V from the home world.
#[tauri::command]
pub fn get_destinations(
    state: tauri::State<'_, ManagedState>,
) -> Result<Vec<DestinationEntry>, String> {
    let app = state.lock().map_err(|e| e.to_string())?;
    let system = app
        .system
        .as_ref()
        .ok_or_else(|| "No system loaded".to_string())?;

    let sorted = sort_by_transfer_dv(&system.home_world_name, &system.bodies);

    let entries = sorted
        .into_iter()
        .filter_map(|(name, dv)| {
            let body = system.bodies.get(&name)?;
            Some(DestinationEntry {
                body: body_to_summary(body),
                transfer_dv: dv,
            })
        })
        .collect();

    Ok(entries)
}

/// Compute a delta-V route from home to an optional destination and moon.
#[tauri::command]
pub fn calc_route(
    destination: Option<String>,
    moon: Option<String>,
    state: tauri::State<'_, ManagedState>,
) -> Result<RouteResponse, String> {
    let app = state.lock().map_err(|e| e.to_string())?;
    let system = app
        .system
        .as_ref()
        .ok_or_else(|| "No system loaded".to_string())?;

    let home = system
        .bodies
        .get(&system.home_world_name)
        .ok_or_else(|| "Home world not found in system".to_string())?;

    let parent_name = home
        .parent_name
        .as_ref()
        .ok_or_else(|| "Home world has no parent body".to_string())?;

    let parent = system
        .bodies
        .get(parent_name)
        .ok_or_else(|| format!("Parent body '{}' not found", parent_name))?;

    let dest_body = match &destination {
        Some(name) => Some(
            system
                .bodies
                .get(name)
                .ok_or_else(|| format!("Destination body '{}' not found", name))?,
        ),
        None => None,
    };

    let moon_body = match &moon {
        Some(name) => Some(
            system
                .bodies
                .get(name)
                .ok_or_else(|| format!("Moon '{}' not found", name))?,
        ),
        None => None,
    };

    let steps = compute_route(home, parent, dest_body, moon_body);

    let total_powered = steps.last().map(|s| s.cumulative).unwrap_or(0.0);

    // Check if any step has an aerobrake note
    let has_aerobrake = steps.iter().any(|s| s.note.contains("aerobrake"));
    let total_aerobrake = if has_aerobrake {
        // Aerobrake landing replaces the last powered landing step
        let last_landing_dv = steps
            .iter()
            .rev()
            .find(|s| s.note.contains("aerobrake"))
            .map(|s| s.dv)
            .unwrap_or(0.0);
        Some(total_powered - last_landing_dv)
    } else {
        None
    };

    let step_responses = steps
        .into_iter()
        .map(|s| DvStepResponse {
            label: s.label,
            dv: s.dv,
            cumulative: s.cumulative,
            note: s.note,
        })
        .collect();

    Ok(RouteResponse {
        steps: step_responses,
        total_powered,
        total_aerobrake,
    })
}

/// Get an atmosphere profile sampled at regular altitude intervals.
#[tauri::command]
pub fn get_atmo_profile(
    name: String,
    steps: Option<u32>,
    state: tauri::State<'_, ManagedState>,
) -> Result<AtmoProfileResponse, String> {
    let app = state.lock().map_err(|e| e.to_string())?;
    let body = app
        .bodies
        .get(&name)
        .ok_or_else(|| format!("Body not found: {}", name))?;

    let atmo = body
        .atmosphere
        .as_ref()
        .ok_or_else(|| format!("Body '{}' has no atmosphere", name))?;

    let n_steps = steps.unwrap_or(100) as usize;
    if n_steps == 0 {
        return Err("Steps must be positive".to_string());
    }

    let depth = atmo.atmosphere_depth;
    let step_size = depth / n_steps as f64;

    let mut altitudes = Vec::with_capacity(n_steps + 1);
    let mut pressures = Vec::with_capacity(n_steps + 1);
    let mut temperatures = Vec::with_capacity(n_steps + 1);
    let mut densities = Vec::with_capacity(n_steps + 1);

    for i in 0..=n_steps {
        let alt = step_size * i as f64;
        altitudes.push(alt);

        let pressure = if !atmo.pressure_curve.is_empty() {
            hermite_interp(&atmo.pressure_curve, alt).unwrap_or(0.0)
        } else if alt == 0.0 {
            atmo.pressure_at_sea_level
        } else {
            0.0
        };
        pressures.push(pressure);

        let temperature = if !atmo.temperature_curve.is_empty() {
            hermite_interp(&atmo.temperature_curve, alt).unwrap_or(0.0)
        } else if alt == 0.0 {
            atmo.temperature_at_sea_level
        } else {
            0.0
        };
        temperatures.push(temperature);

        let density = density_at_altitude(body, alt).unwrap_or(0.0);
        densities.push(density);
    }

    Ok(AtmoProfileResponse {
        altitude: altitudes,
        pressure: pressures,
        temperature: temperatures,
        density: densities,
    })
}

/// Get moons of a body sorted by transfer delta-V.
#[tauri::command]
pub fn get_body_moons(
    name: String,
    state: tauri::State<'_, ManagedState>,
) -> Result<Vec<DestinationEntry>, String> {
    let app = state.lock().map_err(|e| e.to_string())?;
    let system = app
        .system
        .as_ref()
        .ok_or_else(|| "No system loaded".to_string())?;

    let body = system
        .bodies
        .get(&name)
        .ok_or_else(|| format!("Body not found: {}", name))?;

    if body.children_names.is_empty() {
        return Ok(Vec::new());
    }

    // Use sort_by_transfer_dv from the home world perspective if
    // this body is a planet. For moons, we look at children of this body
    // and compute transfers from the body's low orbit.
    let lo_alt = low_orbit_altitude(body);

    let mut entries: Vec<DestinationEntry> = Vec::new();
    for child_name in &body.children_names {
        let child = match system.bodies.get(child_name) {
            Some(c) => c,
            None => continue,
        };
        let child_orbit = match &child.orbit {
            Some(o) => o,
            None => continue,
        };
        let target_sma = child_orbit.semi_major_axis;
        let r_parking = body.radius + lo_alt;

        // Skip if radii are too close (would panic in calculate_hohmann)
        if (r_parking - target_sma).abs() / r_parking.max(target_sma) < 1e-12 {
            continue;
        }

        let hohmann = calculate_hohmann(body, lo_alt, target_sma);
        entries.push(DestinationEntry {
            body: body_to_summary(child),
            transfer_dv: hohmann.total_dv,
        });
    }

    entries.sort_by(|a, b| {
        a.transfer_dv
            .partial_cmp(&b.transfer_dv)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    Ok(entries)
}
