//! Celestial system tree construction and GameData config scanning.
//!
//! Builds parent/children relationships from a flat list of parsed bodies,
//! identifies root star and home world, computes SOI, and provides
//! transfer-DV sorting and GameData directory scanning.
//!
//! 天体ツリーの構築と GameData/ の .cfg ファイルスキャンを提供する。

use std::collections::HashMap;
use std::path::Path;

use crate::calculator::calculate_hohmann;
use crate::models::CelestialBody;
use crate::parser::parse_bodies_with_filename;

// ---------------------------------------------------------------------------
// CelestialSystem
// ---------------------------------------------------------------------------

/// A fully linked tree of celestial bodies parsed from Kopernicus configs.
///
/// Kopernicus 設定からパースされた天体の完全なツリー構造。
pub struct CelestialSystem {
    /// Internal name of the root star (top of the hierarchy).
    pub root_name: String,
    /// Flat name -> body lookup for O(1) access.
    pub bodies: HashMap<String, CelestialBody>,
    /// Internal name of the home world body.
    pub home_world_name: String,
}

// ---------------------------------------------------------------------------
// Barycenter detection
// ---------------------------------------------------------------------------

/// Heuristic: detect if a body is likely a system barycenter.
///
/// 天体がバリセンタ(重心)かどうかをヒューリスティクスで判定する。
///
/// A body is treated as a barycenter when it has children and its
/// radius is smaller than the smallest child's radius.
///
/// # Arguments
/// * `body` - The body to check.
/// * `bodies` - All bodies in the system, for child lookup.
///
/// # Returns
/// `true` if the body is likely a barycenter.
pub fn is_barycenter(body: &CelestialBody, bodies: &HashMap<String, CelestialBody>) -> bool {
    if body.children_names.is_empty() {
        return false;
    }
    let min_child_radius = body
        .children_names
        .iter()
        .filter_map(|name| bodies.get(name))
        .map(|c| c.radius)
        .fold(f64::INFINITY, f64::min);

    if min_child_radius == f64::INFINITY {
        // No children resolved in the map
        return false;
    }
    body.radius < min_child_radius
}

// ---------------------------------------------------------------------------
// Body completeness scoring (deduplication)
// ---------------------------------------------------------------------------

/// Score how complete a body's data is, for deduplication priority.
///
/// 天体データの完全度をスコア化する(重複排除の優先度判定用)。
fn body_completeness(body: &CelestialBody) -> i32 {
    let mut score = 0;
    if body.is_home_world {
        score += 100;
    }
    if body.orbit.is_some() {
        score += 10;
    }
    if !body.reference_body_name.is_empty() {
        score += 5;
    }
    if body.atmosphere.is_some() {
        score += 3;
    }
    if body.radius > 0.0 {
        score += 1;
    }
    score
}

// ---------------------------------------------------------------------------
// Tree construction
// ---------------------------------------------------------------------------

/// Build a parent/children tree from a flat list of bodies.
///
/// フラットな天体リストから親子関係ツリーを構築する。
///
/// Steps:
/// 1. Deduplicate by name (prefer more complete: is_home_world > has orbit > has reference_body_name).
/// 2. Link parent_name / children_names using reference_body_name.
/// 3. Find root (no orbit, no reference_body_name, has children).
/// 4. Find home world (is_home_world=true; fallback: Kerbin-like > has ocean > has atmosphere).
/// 5. Compute SOI where soi == 0: `soi = a * (mu_body / mu_parent)^0.4`.
///
/// # Arguments
/// * `bodies` - Flat list of `CelestialBody` objects (e.g. from `parse_bodies`).
///
/// # Returns
/// A fully linked `CelestialSystem`, or an error if the list is empty or no root found.
///
/// # Errors
/// Returns `Err` if `bodies` is empty.
pub fn build_tree(bodies: Vec<CelestialBody>) -> Result<CelestialSystem, String> {
    if bodies.is_empty() {
        return Err("Cannot build tree from an empty body list".to_string());
    }

    // Step 1: deduplicate by name, preferring the most complete version.
    let mut index: HashMap<String, CelestialBody> = HashMap::new();
    for body in bodies {
        let name = body.name.clone();
        if let Some(existing) = index.get(&name) {
            if body_completeness(&body) > body_completeness(existing) {
                index.insert(name, body);
            }
        } else {
            index.insert(name, body);
        }
    }

    // Reset parent/children to avoid stale links.
    for body in index.values_mut() {
        body.parent_name = None;
        body.children_names.clear();
    }

    // Step 2: link parent/children using reference_body_name.
    // Collect linkage info first to satisfy borrow checker.
    let links: Vec<(String, String)> = index
        .values()
        .filter(|b| !b.reference_body_name.is_empty())
        .map(|b| (b.name.clone(), b.reference_body_name.clone()))
        .collect();

    for (child_name, parent_name) in &links {
        if !index.contains_key(parent_name) {
            eprintln!(
                "system warning: body '{}' references unknown referenceBody '{}'",
                child_name, parent_name
            );
            continue;
        }
        // Set parent_name on child
        if let Some(child) = index.get_mut(child_name) {
            child.parent_name = Some(parent_name.clone());
        }
        // Add child to parent's children_names
        if let Some(parent) = index.get_mut(parent_name) {
            if !parent.children_names.contains(child_name) {
                parent.children_names.push(child_name.clone());
            }
        }
    }

    // Step 3: find root.
    // Primary: body with no orbit AND no reference_body_name AND has children.
    let mut root_name: Option<String> = None;

    let candidates: Vec<String> = index
        .values()
        .filter(|b| b.orbit.is_none() && b.reference_body_name.is_empty())
        .map(|b| b.name.clone())
        .collect();

    if !candidates.is_empty() {
        let with_children: Vec<&String> = candidates
            .iter()
            .filter(|name| {
                index
                    .get(name.as_str())
                    .is_some_and(|b| !b.children_names.is_empty())
            })
            .collect();
        root_name = Some(if !with_children.is_empty() {
            with_children[0].clone()
        } else {
            candidates[0].clone()
        });
    }

    // Fallback: body with no parent link after tree construction, that has children.
    if root_name.is_none() {
        let orphans: Vec<String> = index
            .values()
            .filter(|b| b.parent_name.is_none() && !b.children_names.is_empty())
            .map(|b| b.name.clone())
            .collect();
        if !orphans.is_empty() {
            root_name = Some(orphans[0].clone());
        }
    }

    // Last resort: first body in the map
    let root_name = root_name.unwrap_or_else(|| {
        let first = index.keys().next().expect("index is non-empty");
        eprintln!(
            "system warning: cannot determine root; defaulting to '{}'",
            first
        );
        first.clone()
    });

    // Step 4: home world.
    let mut home_world_name: Option<String> = None;
    for body in index.values() {
        if body.is_home_world {
            home_world_name = Some(body.name.clone());
            break;
        }
    }

    if home_world_name.is_none() {
        // Fallback: pick the best candidate using a heuristic score.
        let best = index
            .values()
            .max_by_key(|b| {
                let mut score: i32 = 0;
                if b.name.trim().eq_ignore_ascii_case("kerbin") {
                    score += 100;
                }
                if b.has_ocean {
                    score += 50;
                }
                if b.atmosphere.is_some() {
                    score += 30;
                }
                if b.rotational_period > 0.0 {
                    score += 10;
                }
                if b.orbit.is_some() {
                    score += 5;
                }
                if b.parent_name.is_some() {
                    score += 2;
                }
                score
            })
            .expect("index is non-empty");

        home_world_name = Some(best.name.clone());
        eprintln!(
            "system warning: no body declares isHomeWorld=true; falling back to '{}' as home world",
            best.name
        );

        // Mark it as home world
        if let Some(body) = index.get_mut(&home_world_name.clone().unwrap()) {
            body.is_home_world = true;
        }
    }

    let home_world_name = home_world_name.expect("home world resolved above");

    // Step 5: compute SOI where soi == 0.
    // Collect (name, soi) pairs to assign, to satisfy borrow checker.
    let soi_updates: Vec<(String, f64)> = index
        .values()
        .filter_map(|body| {
            if body.soi != 0.0 || body.parent_name.is_none() || body.orbit.is_none() {
                return None;
            }
            let parent_name = body.parent_name.as_ref()?;
            let parent = index.get(parent_name)?;
            let a = body.orbit.as_ref()?.semi_major_axis;
            let mu_body = body.mu;
            let mu_parent = parent.mu;
            if mu_parent > 0.0 && a > 0.0 {
                let soi = a * (mu_body / mu_parent).powf(0.4);
                Some((body.name.clone(), soi))
            } else {
                None
            }
        })
        .collect();

    for (name, soi) in soi_updates {
        if let Some(body) = index.get_mut(&name) {
            body.soi = soi;
        }
    }

    Ok(CelestialSystem {
        root_name,
        bodies: index,
        home_world_name,
    })
}

// ---------------------------------------------------------------------------
// Transfer DV sorting
// ---------------------------------------------------------------------------

/// Sort sibling bodies by Hohmann transfer DV from origin, ascending.
///
/// origin からのホーマン遷移 DV 昇順でターゲット天体をソートする。
///
/// The origin must orbit a parent body. Siblings of origin (other children of the
/// same parent) are sorted by their Hohmann transfer DV.
///
/// # Arguments
/// * `origin_name` - Name of the departure body.
/// * `bodies` - All bodies in the system.
///
/// # Returns
/// List of `(target_name, total_dv)` tuples sorted ascending by total_dv.
/// Bodies that cannot be evaluated are omitted.
pub fn sort_by_transfer_dv(
    origin_name: &str,
    bodies: &HashMap<String, CelestialBody>,
) -> Vec<(String, f64)> {
    let origin = match bodies.get(origin_name) {
        Some(b) => b,
        None => return Vec::new(),
    };

    let origin_orbit = match &origin.orbit {
        Some(o) => o,
        None => return Vec::new(),
    };

    let parent_name = match &origin.parent_name {
        Some(n) => n.clone(),
        None => return Vec::new(),
    };

    let parent = match bodies.get(&parent_name) {
        Some(p) => p,
        None => return Vec::new(),
    };

    // Collect siblings (other children of the same parent)
    let siblings: Vec<String> = parent
        .children_names
        .iter()
        .filter(|n| n.as_str() != origin_name)
        .cloned()
        .collect();

    let origin_sma = origin_orbit.semi_major_axis;

    let mut results: Vec<(String, f64)> = Vec::new();
    for sibling_name in &siblings {
        let sibling = match bodies.get(sibling_name) {
            Some(s) => s,
            None => continue,
        };
        let target_sma = match &sibling.orbit {
            Some(o) => o.semi_major_axis,
            None => continue,
        };

        let parking_altitude = origin_sma - parent.radius;
        if parking_altitude < 0.0 {
            continue;
        }

        let hohmann = calculate_hohmann(parent, parking_altitude, target_sma);
        results.push((sibling_name.clone(), hohmann.total_dv));
    }

    results.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal));
    results
}

// ---------------------------------------------------------------------------
// GameData config scanner
// ---------------------------------------------------------------------------

/// Recursively scan a GameData directory for Kopernicus `.cfg` files and build a tree.
///
/// GameData/ ディレクトリを再帰スキャンし、Kopernicus 設定から天体ツリーを構築する。
///
/// All `.cfg` files are read. Directories whose lowercase names appear in
/// `exclude_dirs` are skipped entirely (default: `["kopernicus"]`).
///
/// # Arguments
/// * `gamedata_path` - Path to the `GameData/` directory.
/// * `exclude_dirs` - Directory names (lowercase) to skip during scan.
///
/// # Returns
/// A `CelestialSystem` built from all bodies found, or an error.
///
/// # Errors
/// Returns `Err` if the path is not a directory, no bodies are found, or tree construction fails.
pub fn scan_configs(
    gamedata_path: &str,
    exclude_dirs: &[String],
) -> Result<CelestialSystem, String> {
    let path = Path::new(gamedata_path);
    if !path.is_dir() {
        return Err(format!(
            "gamedata_path is not an existing directory: {}",
            gamedata_path
        ));
    }

    let cfg_files = iter_cfgs(path, exclude_dirs);
    let mut all_bodies: Vec<CelestialBody> = Vec::new();

    for cfg_path in &cfg_files {
        let source = match std::fs::read_to_string(cfg_path) {
            Ok(s) => s,
            Err(e) => {
                eprintln!("system warning: cannot read '{}': {}", cfg_path.display(), e);
                continue;
            }
        };

        let filename = cfg_path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("");
        let bodies = parse_bodies_with_filename(&source, filename);
        if bodies.is_empty() {
            continue;
        }

        all_bodies.extend(bodies);
    }

    if all_bodies.is_empty() {
        return Err(format!(
            "No celestial bodies found under '{}'",
            gamedata_path
        ));
    }

    build_tree(all_bodies)
}

/// Recursively collect .cfg files under a directory, skipping excluded dirs.
///
/// ディレクトリ以下の .cfg ファイルを再帰的に収集する。
fn iter_cfgs(directory: &Path, exclude_dirs: &[String]) -> Vec<std::path::PathBuf> {
    let mut results = Vec::new();

    let entries = match std::fs::read_dir(directory) {
        Ok(e) => e,
        Err(e) => {
            eprintln!(
                "system warning: cannot list directory '{}': {}",
                directory.display(),
                e
            );
            return results;
        }
    };

    let mut sorted_entries: Vec<std::path::PathBuf> = entries
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .collect();
    sorted_entries.sort();

    for entry in &sorted_entries {
        if entry.is_dir() {
            let dir_name = entry
                .file_name()
                .and_then(|s| s.to_str())
                .unwrap_or("")
                .to_lowercase();
            if exclude_dirs.iter().any(|ex| ex.to_lowercase() == dir_name) {
                continue;
            }
            results.extend(iter_cfgs(entry, exclude_dirs));
        } else if entry.is_file() {
            let ext = entry
                .extension()
                .and_then(|s| s.to_str())
                .unwrap_or("")
                .to_lowercase();
            if ext == "cfg" {
                results.push(entry.clone());
            }
        }
    }

    results
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::*;

    fn make_star() -> CelestialBody {
        CelestialBody::new(
            "Sun".to_string(),
            261_600_000.0,
            1.75,
            false,
            None,
            None,
            0.0,
            "Sun".to_string(),
        )
    }

    fn make_planet(name: &str, ref_body: &str) -> CelestialBody {
        let mut body = CelestialBody::new(
            name.to_string(),
            600_000.0,
            1.0,
            true,
            None,
            Some(OrbitalElements {
                semi_major_axis: 13_599_840_256.0,
                eccentricity: 0.0,
                inclination: 0.0,
                argument_of_periapsis: 0.0,
                longitude_of_ascending_node: 0.0,
                mean_anomaly_at_epoch: 0.0,
                epoch: 0.0,
            }),
            21549.0,
            name.to_string(),
        );
        body.reference_body_name = ref_body.to_string();
        body
    }

    #[test]
    fn test_build_tree_basic() {
        let star = make_star();
        let mut planet = make_planet("Kerbin", "Sun");
        planet.is_home_world = true;
        let system = build_tree(vec![star, planet]).unwrap();
        assert_eq!(system.root_name, "Sun");
        assert_eq!(system.home_world_name, "Kerbin");
        let kerbin = &system.bodies["Kerbin"];
        assert_eq!(kerbin.parent_name, Some("Sun".to_string()));
        let sun = &system.bodies["Sun"];
        assert!(sun.children_names.contains(&"Kerbin".to_string()));
    }

    #[test]
    fn test_build_tree_empty_fails() {
        assert!(build_tree(vec![]).is_err());
    }

    #[test]
    fn test_build_tree_soi_computation() {
        let star = make_star();
        let mut planet = make_planet("Kerbin", "Sun");
        planet.is_home_world = true;
        let system = build_tree(vec![star, planet]).unwrap();
        let kerbin = &system.bodies["Kerbin"];
        assert!(kerbin.soi > 0.0);
    }

    #[test]
    fn test_build_tree_dedup() {
        let star = make_star();
        let p1 = make_planet("Kerbin", "Sun");
        let mut p2 = make_planet("Kerbin", "Sun");
        p2.is_home_world = true;
        let system = build_tree(vec![star, p1, p2]).unwrap();
        // p2 should win (is_home_world = true)
        assert_eq!(system.home_world_name, "Kerbin");
    }

    #[test]
    fn test_is_barycenter() {
        let mut parent = make_star();
        parent.radius = 100.0; // tiny
        parent.name = "Tiny".to_string();
        parent.children_names = vec!["Big".to_string()];
        let mut child = make_planet("Big", "Tiny");
        child.radius = 600_000.0;
        let mut bodies = HashMap::new();
        bodies.insert("Tiny".to_string(), parent);
        bodies.insert("Big".to_string(), child);
        assert!(is_barycenter(&bodies["Tiny"], &bodies));
        assert!(!is_barycenter(&bodies["Big"], &bodies));
    }

    #[test]
    fn test_home_world_fallback() {
        // No body has is_home_world = true; the one with ocean/atmosphere should win.
        let star = make_star();
        let mut planet = make_planet("Kerbin", "Sun");
        // Don't set is_home_world; the heuristic should still pick Kerbin by name.
        planet.is_home_world = false;
        let system = build_tree(vec![star, planet]).unwrap();
        assert_eq!(system.home_world_name, "Kerbin");
        assert!(system.bodies["Kerbin"].is_home_world);
    }

    #[test]
    fn test_sort_by_transfer_dv_basic() {
        let mut star = make_star();
        star.children_names = vec!["Inner".to_string(), "Outer".to_string()];

        let mut inner = make_planet("Inner", "Sun");
        inner.is_home_world = true;
        inner.orbit = Some(OrbitalElements {
            semi_major_axis: 10_000_000_000.0,
            eccentricity: 0.0,
            inclination: 0.0,
            argument_of_periapsis: 0.0,
            longitude_of_ascending_node: 0.0,
            mean_anomaly_at_epoch: 0.0,
            epoch: 0.0,
        });
        inner.parent_name = Some("Sun".to_string());

        let mut outer = make_planet("Outer", "Sun");
        outer.orbit = Some(OrbitalElements {
            semi_major_axis: 20_000_000_000.0,
            eccentricity: 0.0,
            inclination: 0.0,
            argument_of_periapsis: 0.0,
            longitude_of_ascending_node: 0.0,
            mean_anomaly_at_epoch: 0.0,
            epoch: 0.0,
        });
        outer.parent_name = Some("Sun".to_string());

        let mut bodies = HashMap::new();
        bodies.insert("Sun".to_string(), star);
        bodies.insert("Inner".to_string(), inner);
        bodies.insert("Outer".to_string(), outer);

        let result = sort_by_transfer_dv("Inner", &bodies);
        assert_eq!(result.len(), 1);
        assert_eq!(result[0].0, "Outer");
        assert!(result[0].1 > 0.0);
    }

    #[test]
    fn test_sort_by_transfer_dv_no_orbit() {
        let bodies: HashMap<String, CelestialBody> = HashMap::new();
        let result = sort_by_transfer_dv("Missing", &bodies);
        assert!(result.is_empty());
    }
}
