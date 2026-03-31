#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Command, Stdio};
use std::sync::Mutex;
use tauri::Manager;

struct PythonProcess(Mutex<Option<std::process::Child>>);

fn find_python() -> Option<String> {
    for cmd in ["python", "py", "python3"] {
        if Command::new(cmd)
            .arg("--version")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .is_ok()
        {
            return Some(cmd.to_string());
        }
    }
    None
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let resource_dir = app
                .path()
                .resource_dir()
                .expect("Failed to resolve resource directory");

            let resources = resource_dir.join("resources");
            let launcher_path = resources.join("launcher.py");

            let python = find_python().expect(
                "Python not found. Install Python 3.10+ and ensure it is on PATH.",
            );

            eprintln!("[tauri] Python: {}", python);
            eprintln!("[tauri] Launcher: {}", launcher_path.display());

            // Use Stdio::null — launcher.py writes its own log file.
            // IMPORTANT: Do NOT use Stdio::piped() without reading,
            // as a full pipe buffer will block the child process.
            let child = Command::new(&python)
                .arg(&launcher_path)
                .current_dir(&resources)
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn();

            match child {
                Ok(proc) => {
                    app.manage(PythonProcess(Mutex::new(Some(proc))));
                }
                Err(e) => {
                    eprintln!("[tauri] Failed to spawn Python: {}", e);
                    app.manage(PythonProcess(Mutex::new(None)));
                }
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app: &tauri::AppHandle, event: tauri::RunEvent| {
            if let tauri::RunEvent::Exit = event {
                if let Some(state) = app.try_state::<PythonProcess>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(proc) = guard.as_mut() {
                            let _ = proc.kill();
                        }
                    }
                }
            }
        });
}
