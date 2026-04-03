#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;

mod commands;
mod state;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(Mutex::new(state::AppState::new()))
        .invoke_handler(tauri::generate_handler![
            commands::health,
            commands::upload_config,
            commands::scan_gamedata,
            commands::list_bodies,
            commands::get_body,
            commands::calc_launch,
            commands::calc_hohmann,
            commands::calc_tsiolkovsky,
            commands::get_system,
            commands::get_destinations,
            commands::calc_route,
            commands::get_atmo_profile,
            commands::get_body_moons,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
