//! Kopernicus ConfigNode parser for KSP `.cfg` files.
//!
//! Two-layer design:
//! 1. **Low-level**: `ConfigNode` tree parsed from raw text.
//! 2. **High-level**: `parse_bodies` extracts `CelestialBody` instances from the tree.
//!
//! KSP ConfigNodeパーサー（2層構成）。

use crate::models::{Atmosphere, CelestialBody, CurveKey, OrbitalElements};

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/// Characters used as ModuleManager modifier prefixes on node names.
const MODIFIER_CHARS: &[char] = &['@', '!', '+', '-', '%'];

// ---------------------------------------------------------------------------
// ConfigNode
// ---------------------------------------------------------------------------

/// A node in the KSP ConfigNode tree.
///
/// KSP ConfigNodeツリーのノード。
#[derive(Debug, Clone)]
pub struct ConfigNode {
    /// Node name (modifiers stripped).
    pub name: String,
    /// Key-value pairs declared directly in this node.
    pub values: Vec<(String, String)>,
    /// Child nodes.
    pub children: Vec<ConfigNode>,
}

impl ConfigNode {
    /// Create a new empty ConfigNode with the given name.
    fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            values: Vec::new(),
            children: Vec::new(),
        }
    }

    /// Get the first value for a given key, or `None` if not found.
    ///
    /// 指定キーの最初の値を返す。
    pub fn get_value(&self, key: &str) -> Option<&str> {
        self.values
            .iter()
            .find(|(k, _)| k == key)
            .map(|(_, v)| v.as_str())
    }

    /// Get all values for a given key.
    ///
    /// 指定キーの全値を返す。
    pub fn get_values(&self, key: &str) -> Vec<&str> {
        self.values
            .iter()
            .filter(|(k, _)| k == key)
            .map(|(_, v)| v.as_str())
            .collect()
    }

    /// Get the first child node with the given name, or `None`.
    ///
    /// 指定名の最初の子ノードを返す。
    pub fn get_child(&self, name: &str) -> Option<&ConfigNode> {
        self.children.iter().find(|c| c.name == name)
    }
}

// ---------------------------------------------------------------------------
// Low-level parser
// ---------------------------------------------------------------------------

/// Strip `//` comments from a line and trim whitespace.
fn strip_comments(line: &str) -> &str {
    match line.find("//") {
        Some(idx) => line[..idx].trim(),
        None => line.trim(),
    }
}

/// Remove ModuleManager modifier prefixes, colon annotations, and bracket
/// expressions from a raw node name.
fn clean_node_name(raw: &str) -> String {
    let mut s = raw.trim();

    // Strip leading modifier chars
    while let Some(first) = s.chars().next() {
        if MODIFIER_CHARS.contains(&first) {
            s = &s[first.len_utf8()..];
        } else {
            break;
        }
    }

    // Strip :AFTER[...] etc.
    if let Some(colon_idx) = s.find(':') {
        s = &s[..colon_idx];
    }

    // Strip [Name] bracket expressions
    if let Some(bracket_idx) = s.find('[') {
        s = &s[..bracket_idx];
    }

    s.trim().to_string()
}

/// Returns true if the line is a delete directive like `!Body[Kerbin]{}`.
fn is_delete_directive(line: &str) -> bool {
    if !line.starts_with('!') {
        return false;
    }
    // Pattern: !Word[...]{ optional whitespace }
    // Match: starts with !, has word chars, brackets, then { } with optional whitespace
    let rest = &line[1..];
    let Some(bracket_start) = rest.find('[') else {
        return false;
    };
    // Must have word chars before bracket
    if bracket_start == 0
        || !rest[..bracket_start]
            .chars()
            .all(|c| c.is_alphanumeric() || c == '_')
    {
        return false;
    }
    let Some(bracket_end) = rest.find(']') else {
        return false;
    };
    if bracket_end <= bracket_start {
        return false;
    }
    let after_bracket = rest[bracket_end + 1..].trim();
    // Must end with {}
    if after_bracket == "{}" {
        return true;
    }
    // Or { } with whitespace
    if after_bracket.starts_with('{') && after_bracket.ends_with('}') {
        let inner = &after_bracket[1..after_bracket.len() - 1];
        return inner.trim().is_empty();
    }
    false
}

/// Close the top node on the stack, attaching it to its parent or to top-level.
fn close_node(stack: &mut Vec<ConfigNode>, top_level: &mut Vec<ConfigNode>) {
    if let Some(closed) = stack.pop() {
        if let Some(parent) = stack.last_mut() {
            parent.children.push(closed);
        } else {
            top_level.push(closed);
        }
    }
}

/// Process a single logical line fragment (after comment stripping).
///
/// This is factored out so that content remaining after an opening `{`
/// on the same physical line can be recursively processed.
fn process_fragment(
    line: &str,
    stack: &mut Vec<ConfigNode>,
    top_level: &mut Vec<ConfigNode>,
    pending_name: &mut Option<String>,
) {
    let line = line.trim();
    if line.is_empty() {
        return;
    }

    // Inline delete directive
    if is_delete_directive(line) {
        return;
    }

    // Closing brace
    if line == "}" {
        if stack.is_empty() {
            eprintln!("parser warning: unmatched closing brace, ignoring");
            return;
        }
        close_node(stack, top_level);
        return;
    }

    // Opening brace alone
    if line == "{" {
        let name = pending_name.take().unwrap_or_default();
        stack.push(ConfigNode::new(name));
        return;
    }

    // Line contains `{`
    if line.contains('{') {
        let brace_idx = line.find('{').unwrap();
        let before = line[..brace_idx].trim();
        let node_name = if before.is_empty() {
            pending_name.take().unwrap_or_default()
        } else {
            *pending_name = None;
            clean_node_name(before)
        };
        let node = ConfigNode::new(node_name);
        let after = line[brace_idx + 1..].trim();
        if after.starts_with('}') {
            // Empty inline node like `Node {}`
            if let Some(parent) = stack.last_mut() {
                parent.children.push(node);
            } else {
                top_level.push(node);
            }
            return;
        }
        stack.push(node);
        // Process remaining content after `{` on the same line
        if !after.is_empty() {
            process_fragment(after, stack, top_level, pending_name);
        }
        return;
    }

    // Check for trailing `}` on a key=value line or bare line
    if line.contains('=') {
        if pending_name.is_some() {
            eprintln!("parser warning: discarding pending name before key=value line");
            *pending_name = None;
        }

        // Check if line ends with `}` (inline close after key=value)
        let (kv_part, has_close) = if let Some(stripped) = line.strip_suffix('}') {
            (stripped, true)
        } else {
            (line, false)
        };

        let eq_idx = kv_part.find('=').unwrap();
        let key = kv_part[..eq_idx].trim().to_string();
        let value = kv_part[eq_idx + 1..].trim().to_string();
        if let Some(current) = stack.last_mut() {
            current.values.push((key, value));
        }

        if has_close {
            close_node(stack, top_level);
        }
        return;
    }

    // Check if a bare token ends with `}` (edge case)
    if let Some(stripped) = line.strip_suffix('}') {
        let before = stripped.trim();
        if !before.is_empty() {
            if pending_name.is_some() {
                eprintln!("parser warning: discarding previous pending name");
            }
            *pending_name = Some(clean_node_name(before));
        }
        close_node(stack, top_level);
        return;
    }

    // Bare identifier (potential node name for next `{`)
    if pending_name.is_some() {
        eprintln!("parser warning: discarding previous pending name");
    }
    *pending_name = Some(clean_node_name(line));
}

/// Parse raw KSP ConfigNode text into a list of top-level nodes.
///
/// Handles comments, modifiers, delete directives, nested braces,
/// and auto-closes unclosed nodes at EOF with a warning.
///
/// KSP ConfigNodeテキストをパースしてノードツリーを返す。
pub fn parse_config_text(source: &str) -> Vec<ConfigNode> {
    let mut top_level: Vec<ConfigNode> = Vec::new();
    let mut stack: Vec<ConfigNode> = Vec::new();
    let mut pending_name: Option<String> = None;

    for raw_line in source.lines() {
        let line = strip_comments(raw_line);
        if line.is_empty() {
            continue;
        }
        process_fragment(line, &mut stack, &mut top_level, &mut pending_name);
    }

    // Auto-close unclosed nodes
    if !stack.is_empty() {
        eprintln!(
            "parser warning: {} unclosed node(s) at EOF, auto-closing",
            stack.len()
        );
        while !stack.is_empty() {
            close_node(&mut stack, &mut top_level);
        }
    }

    top_level
}

// ---------------------------------------------------------------------------
// Helper parsers
// ---------------------------------------------------------------------------

/// Parse a float from a string, returning `default` on `None` or parse failure.
fn parse_float(value: Option<&str>, default: f64) -> f64 {
    match value {
        Some(s) => s.trim().parse::<f64>().unwrap_or(default),
        None => default,
    }
}

/// Parse a boolean from a string ("true" / "True" / "TRUE"), returning `default`
/// on `None` or unrecognized input.
fn parse_bool(value: Option<&str>, default: bool) -> bool {
    match value {
        Some(s) => s.trim().eq_ignore_ascii_case("true"),
        None => default,
    }
}

/// Parse a single curve key line: `position value [inTangent [outTangent]]`.
///
/// outTangent defaults to inTangent when omitted; both default to 0.
fn parse_curve_key(raw_value: &str) -> Option<CurveKey> {
    let parts: Vec<&str> = raw_value.split_whitespace().collect();
    if parts.len() < 2 {
        return None;
    }
    let position = parts[0].parse::<f64>().ok()?;
    let value = parts[1].parse::<f64>().ok()?;
    let in_tangent = if parts.len() >= 3 {
        parts[2].parse::<f64>().unwrap_or(0.0)
    } else {
        0.0
    };
    let out_tangent = if parts.len() >= 4 {
        parts[3].parse::<f64>().unwrap_or(in_tangent)
    } else {
        in_tangent
    };
    Some(CurveKey {
        position,
        value,
        in_tangent,
        out_tangent,
    })
}

/// Extract sorted curve keys from a node's `key` values.
fn extract_curve_keys(node: &ConfigNode) -> Vec<CurveKey> {
    let mut keys: Vec<CurveKey> = node
        .get_values("key")
        .iter()
        .filter_map(|raw| parse_curve_key(raw))
        .collect();
    keys.sort_by(|a, b| {
        a.position
            .partial_cmp(&b.position)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    keys
}

// ---------------------------------------------------------------------------
// Body extraction
// ---------------------------------------------------------------------------

/// Extract an `Atmosphere` from a body node, if present and enabled.
fn extract_atmosphere(body_node: &ConfigNode) -> Option<Atmosphere> {
    let atmo_node = body_node.get_child("Atmosphere")?;
    let enabled = parse_bool(atmo_node.get_value("enabled"), false);
    if !enabled {
        return None;
    }

    let altitude = parse_float(atmo_node.get_value("altitude"), 0.0);
    let adiabatic_index = parse_float(atmo_node.get_value("adiabaticIndex"), 1.4);
    let molar_mass = parse_float(atmo_node.get_value("atmosphereMolarMass"), 0.02897);
    let temperature_sea_level = parse_float(atmo_node.get_value("temperatureSeaLevel"), 0.0);
    let pressure_sea_level = parse_float(atmo_node.get_value("staticPressureASL"), 0.0);

    let temperature_curve = atmo_node
        .get_child("temperatureCurve")
        .map(extract_curve_keys)
        .unwrap_or_default();
    let pressure_curve = atmo_node
        .get_child("pressureCurve")
        .map(extract_curve_keys)
        .unwrap_or_default();

    Some(Atmosphere {
        atmosphere_depth: altitude,
        pressure_curve,
        temperature_curve,
        molar_mass,
        adiabatic_index,
        pressure_at_sea_level: pressure_sea_level,
        temperature_at_sea_level: temperature_sea_level,
    })
}

/// Extract `OrbitalElements` from a body node, if present.
fn extract_orbit(body_node: &ConfigNode) -> Option<OrbitalElements> {
    let orbit_node = body_node.get_child("Orbit")?;
    Some(OrbitalElements {
        semi_major_axis: parse_float(orbit_node.get_value("semiMajorAxis"), 0.0),
        eccentricity: parse_float(orbit_node.get_value("eccentricity"), 0.0),
        inclination: parse_float(orbit_node.get_value("inclination"), 0.0),
        argument_of_periapsis: parse_float(orbit_node.get_value("argumentOfPeriapsis"), 0.0),
        longitude_of_ascending_node: parse_float(
            orbit_node.get_value("longitudeOfAscendingNode"),
            0.0,
        ),
        mean_anomaly_at_epoch: parse_float(orbit_node.get_value("meanAnomalyAtEpoch"), 0.0),
        epoch: parse_float(orbit_node.get_value("epoch"), 0.0),
    })
}

/// Check if an Ocean child node exists and has `ocean = True`.
fn extract_has_ocean(body_node: &ConfigNode) -> bool {
    match body_node.get_child("Ocean") {
        Some(ocean_node) => parse_bool(ocean_node.get_value("ocean"), false),
        None => false,
    }
}

/// Resolve display name: prefer Properties/displayName unless it starts with
/// `#LOC_`, in which case fall back to source_filename then body name.
fn resolve_display_name(
    properties: Option<&ConfigNode>,
    body_name: &str,
    source_filename: &str,
) -> String {
    let fallback = || -> String {
        if source_filename.is_empty() {
            body_name.to_string()
        } else {
            source_filename.to_string()
        }
    };

    let Some(props) = properties else {
        return fallback();
    };

    match props.get_value("displayName") {
        Some(dn) if !dn.starts_with("#LOC_") => dn.to_string(),
        _ => fallback(),
    }
}

/// Extract a single `CelestialBody` from a Body ConfigNode.
fn extract_body(body_node: &ConfigNode, source_filename: &str) -> Option<CelestialBody> {
    let name = body_node.get_value("name")?;
    let properties = body_node.get_child("Properties");

    let radius = parse_float(properties.and_then(|p| p.get_value("radius")), 600_000.0);
    let gee_asl = parse_float(properties.and_then(|p| p.get_value("geeASL")), 1.0);
    let rotational_period =
        parse_float(properties.and_then(|p| p.get_value("rotationPeriod")), 0.0);
    let display_name = resolve_display_name(properties, name, source_filename);
    let is_home_world = parse_bool(properties.and_then(|p| p.get_value("isHomeWorld")), false);

    let reference_body_name = body_node
        .get_child("Orbit")
        .and_then(|o| o.get_value("referenceBody"))
        .map(|s| s.trim().to_string())
        .unwrap_or_default();

    let atmosphere = extract_atmosphere(body_node);
    let orbit = extract_orbit(body_node);
    let has_ocean = extract_has_ocean(body_node);

    let mut body = CelestialBody::new(
        name.to_string(),
        radius,
        gee_asl,
        has_ocean,
        atmosphere,
        orbit,
        rotational_period,
        display_name,
    );
    body.is_home_world = is_home_world;
    body.reference_body_name = reference_body_name;

    Some(body)
}

/// Recursively walk nodes looking for `Body` children and extract them.
fn walk_bodies(nodes: &[ConfigNode], source_filename: &str, bodies: &mut Vec<CelestialBody>) {
    for node in nodes {
        if node.name == "Body" {
            if let Some(body) = extract_body(node, source_filename) {
                bodies.push(body);
            }
        } else {
            walk_bodies(&node.children, source_filename, bodies);
        }
    }
}

/// Parse KSP ConfigNode source text and extract all `CelestialBody` instances.
///
/// This is the main entry point for the parser.
///
/// メインエントリーポイント。天体を抽出して返す。
pub fn parse_bodies(source: &str) -> Vec<CelestialBody> {
    parse_bodies_with_filename(source, "")
}

/// Parse bodies with a source filename used as display name fallback.
///
/// ファイル名付きでパースする。
pub fn parse_bodies_with_filename(source: &str, filename: &str) -> Vec<CelestialBody> {
    let top_nodes = parse_config_text(source);
    let mut bodies = Vec::new();
    walk_bodies(&top_nodes, filename, &mut bodies);
    bodies
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // -----------------------------------------------------------------------
    // ConfigNode low-level tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_empty_input() {
        assert!(parse_config_text("").is_empty());
    }

    #[test]
    fn test_simple_key_value() {
        let nodes = parse_config_text("Node\n{\n    name = Kerbin\n    radius = 600000\n}");
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].name, "Node");
        assert_eq!(nodes[0].get_value("name"), Some("Kerbin"));
        assert_eq!(nodes[0].get_value("radius"), Some("600000"));
    }

    #[test]
    fn test_nested_nodes() {
        let nodes = parse_config_text(
            "Outer\n{\n    key = val\n    Inner\n    {\n        key = val2\n    }\n}",
        );
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].children.len(), 1);
        assert_eq!(nodes[0].children[0].name, "Inner");
    }

    #[test]
    fn test_comment_removal() {
        let nodes = parse_config_text("Node\n{\n    key = val // comment\n}");
        assert_eq!(nodes[0].get_value("key"), Some("val"));
    }

    #[test]
    fn test_modifier_stripping() {
        for prefix in ["@", "!", "+", "-", "%"] {
            let source = format!("{}Node\n{{\n    key = val\n}}", prefix);
            let nodes = parse_config_text(&source);
            assert_eq!(nodes[0].name, "Node", "failed for prefix {}", prefix);
        }
    }

    #[test]
    fn test_delete_directive_skipped() {
        let nodes = parse_config_text("!Body[Kerbin]{}\nNode\n{\n    key = val\n}");
        assert!(nodes.iter().any(|n| n.name == "Node"));
        // The delete directive should not produce a node
        assert!(!nodes.iter().any(|n| n.name == "Body"));
    }

    #[test]
    fn test_unclosed_brace_no_crash() {
        let result = parse_config_text("Node\n{\n    key = val\n");
        assert!(!result.is_empty());
        assert_eq!(result[0].get_value("key"), Some("val"));
    }

    #[test]
    fn test_values_with_spaces() {
        let nodes = parse_config_text("Node\n{\n    name = North Pole\n}");
        assert_eq!(nodes[0].get_value("name"), Some("North Pole"));
    }

    #[test]
    fn test_inline_node_opening() {
        // Node name on the same line as the opening brace
        let nodes = parse_config_text("Properties {\n    radius = 100000\n}");
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].name, "Properties");
        assert_eq!(nodes[0].get_value("radius"), Some("100000"));
    }

    #[test]
    fn test_mm_annotation_stripped() {
        let nodes = parse_config_text("@Kopernicus:AFTER[Kopernicus]\n{\n    key = val\n}");
        assert_eq!(nodes[0].name, "Kopernicus");
    }

    #[test]
    fn test_get_values_multiple() {
        let nodes =
            parse_config_text("Curve\n{\n    key = 0 100\n    key = 1 200\n    key = 2 300\n}");
        let vals = nodes[0].get_values("key");
        assert_eq!(vals.len(), 3);
    }

    #[test]
    fn test_get_child_not_found() {
        let nodes = parse_config_text("Node\n{\n    key = val\n}");
        assert!(nodes[0].get_child("Missing").is_none());
    }

    // -----------------------------------------------------------------------
    // Curve key parsing
    // -----------------------------------------------------------------------

    #[test]
    fn test_curve_key_full() {
        let ck = parse_curve_key("0 101.325 -0.005 -0.01").unwrap();
        assert!((ck.position - 0.0).abs() < 1e-6);
        assert!((ck.value - 101.325).abs() < 1e-6);
        assert!((ck.in_tangent - (-0.005)).abs() < 1e-6);
        assert!((ck.out_tangent - (-0.01)).abs() < 1e-6);
    }

    #[test]
    fn test_curve_key_out_tangent_defaults_to_in() {
        let ck = parse_curve_key("0 101.325 -0.005").unwrap();
        assert!((ck.out_tangent - (-0.005)).abs() < 1e-6);
    }

    #[test]
    fn test_curve_key_tangents_default_to_zero() {
        let ck = parse_curve_key("0 101.325").unwrap();
        assert!((ck.in_tangent - 0.0).abs() < 1e-6);
        assert!((ck.out_tangent - 0.0).abs() < 1e-6);
    }

    #[test]
    fn test_curve_key_too_few_parts() {
        assert!(parse_curve_key("0").is_none());
        assert!(parse_curve_key("").is_none());
    }

    // -----------------------------------------------------------------------
    // Body extraction tests
    // -----------------------------------------------------------------------

    #[test]
    fn test_parse_simple_body() {
        let cfg = r#"
        @Kopernicus:AFTER[Kopernicus]
        {
            Body
            {
                name = Kerbin
                Properties
                {
                    radius = 600000
                    geeASL = 1.0
                    rotationPeriod = 21549.425
                    isHomeWorld = True
                }
            }
        }
        "#;
        let bodies = parse_bodies(cfg);
        assert_eq!(bodies.len(), 1);
        assert_eq!(bodies[0].name, "Kerbin");
        assert!((bodies[0].radius - 600_000.0).abs() < 1.0);
        assert!((bodies[0].gee_asl - 1.0).abs() < 0.001);
        assert!(bodies[0].is_home_world);
    }

    #[test]
    fn test_parse_sanctar_cfg() {
        let cfg = std::fs::read_to_string("../../../sample_configs/Sanctar.cfg").unwrap();
        let bodies = parse_bodies(&cfg);
        assert!(!bodies.is_empty());
        let body = &bodies[0];

        // Basic properties
        assert!((body.radius - 670_000.0).abs() < 1.0);
        assert!((body.gee_asl - 1.1).abs() < 0.001);

        // Atmosphere
        assert!(body.atmosphere.is_some());
        let atmo = body.atmosphere.as_ref().unwrap();
        assert!((atmo.atmosphere_depth - 72_000.0).abs() < 1.0);
        assert_eq!(atmo.pressure_curve.len(), 26);
        assert_eq!(atmo.temperature_curve.len(), 26);
        assert!((atmo.pressure_at_sea_level - 110.444).abs() / 110.444 < 0.001);
        assert!((atmo.temperature_at_sea_level - 281.0).abs() < 0.1);
        assert!((atmo.molar_mass - 0.02897).abs() < 0.0001);
        assert!((atmo.adiabatic_index - 1.4).abs() < 0.001);

        // Orbit
        assert!(body.orbit.is_some());
        let orbit = body.orbit.as_ref().unwrap();
        assert!((orbit.semi_major_axis - 13_116_000_574.0).abs() / 13_116_000_574.0 < 0.001);
        assert!((orbit.eccentricity - 0.0254528).abs() < 0.001);
        assert!((orbit.inclination - 1.38).abs() < 0.01);

        // Other
        assert!(body.is_home_world);
        assert_eq!(body.reference_body_name, "Sun");
        assert!(body.has_ocean);
    }

    #[test]
    fn test_curve_key_out_tangent_defaults_to_in_body() {
        let cfg = r#"
        Body
        {
            name = Test
            Properties { radius = 100000 }
            Atmosphere
            {
                enabled = True
                altitude = 50000
                adiabaticIndex = 1.4
                atmosphereMolarMass = 0.029
                temperatureSeaLevel = 288
                staticPressureASL = 101.325
                pressureCurve
                {
                    key = 0 101.325 -0.005
                }
                temperatureCurve
                {
                    key = 0 288 0 0
                }
            }
        }
        "#;
        let bodies = parse_bodies(cfg);
        let atmo = bodies[0].atmosphere.as_ref().unwrap();
        assert!((atmo.pressure_curve[0].out_tangent - (-0.005)).abs() < 1e-6);
    }

    #[test]
    fn test_atmosphere_disabled_is_none() {
        let cfg = "Body\n{\n    name = Test\n    Properties\n    {\n        radius = 100000\n        geeASL = 1.0\n    }\n    Atmosphere\n    {\n        enabled = False\n        altitude = 70000\n    }\n}";
        let bodies = parse_bodies(cfg);
        assert!(bodies[0].atmosphere.is_none());
    }

    #[test]
    fn test_no_orbit_is_none() {
        let cfg = "Body\n{\n    name = Test\n    Properties\n    {\n        radius = 100000\n        geeASL = 1.0\n    }\n}";
        let bodies = parse_bodies(cfg);
        assert!(bodies[0].orbit.is_none());
    }

    #[test]
    fn test_reference_body_from_orbit() {
        let cfg = "Body\n{\n    name = Test\n    Properties\n    {\n        radius = 100000\n        geeASL = 1.0\n    }\n    Orbit\n    {\n        semiMajorAxis = 1000000\n        referenceBody = Sun\n    }\n}";
        let bodies = parse_bodies(cfg);
        assert_eq!(bodies[0].reference_body_name, "Sun");
    }

    #[test]
    fn test_multiple_bodies() {
        let cfg = "Body\n{\n    name = A\n    Properties { radius = 100000\n geeASL = 1.0 }\n}\nBody\n{\n    name = B\n    Properties { radius = 200000\n geeASL = 0.8 }\n}";
        let bodies = parse_bodies(cfg);
        assert_eq!(bodies.len(), 2);
    }

    #[test]
    fn test_display_name_loc_fallback() {
        let cfg = r#"
        Body
        {
            name = Kerbin
            Properties
            {
                displayName = #LOC_Kerbin
                radius = 600000
            }
        }
        "#;
        // Without filename, falls back to body name
        let bodies = parse_bodies(cfg);
        assert_eq!(bodies[0].display_name, "Kerbin");

        // With filename, falls back to filename
        let bodies = parse_bodies_with_filename(cfg, "MyPlanet");
        assert_eq!(bodies[0].display_name, "MyPlanet");
    }

    #[test]
    fn test_display_name_real_value() {
        let cfg = r#"
        Body
        {
            name = Kerbin
            Properties
            {
                displayName = Earth
                radius = 600000
            }
        }
        "#;
        let bodies = parse_bodies(cfg);
        assert_eq!(bodies[0].display_name, "Earth");
    }

    #[test]
    fn test_no_properties_defaults() {
        let cfg = "Body\n{\n    name = Test\n}";
        let bodies = parse_bodies(cfg);
        assert_eq!(bodies.len(), 1);
        assert!((bodies[0].radius - 600_000.0).abs() < 1.0);
        assert!((bodies[0].gee_asl - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_body_without_name_skipped() {
        let cfg = "Body\n{\n    Properties { radius = 100000 }\n}";
        let bodies = parse_bodies(cfg);
        assert!(bodies.is_empty());
    }

    #[test]
    fn test_unmatched_closing_brace() {
        // Should not crash
        let nodes = parse_config_text("}\nNode\n{\n    key = val\n}");
        assert_eq!(nodes.len(), 1);
        assert_eq!(nodes[0].name, "Node");
    }

    #[test]
    fn test_delete_directive_with_spaces() {
        let nodes = parse_config_text("!Body[Kerbin]{ }\nNode\n{\n    key = val\n}");
        assert!(nodes.iter().any(|n| n.name == "Node"));
        assert!(!nodes.iter().any(|n| n.name == "Body"));
    }
}
