//! Application state shared across Tauri commands.
//!
//! Tauri コマンド間で共有するアプリケーション状態。

use std::collections::HashMap;
use std::sync::Mutex;

use kopdeltav::models::CelestialBody;
use kopdeltav::system::CelestialSystem;

/// Central application state holding parsed celestial bodies and the built system tree.
///
/// パース済み天体とシステムツリーを保持する中央アプリケーション状態。
pub struct AppState {
    /// All loaded celestial bodies indexed by internal name.
    pub bodies: HashMap<String, CelestialBody>,
    /// The fully linked celestial system tree, built after loading bodies.
    pub system: Option<CelestialSystem>,
}

impl AppState {
    /// Create a new empty state with no bodies loaded.
    pub fn new() -> Self {
        Self {
            bodies: HashMap::new(),
            system: None,
        }
    }
}

/// Thread-safe wrapper around `AppState` for Tauri managed state.
pub type ManagedState = Mutex<AppState>;
