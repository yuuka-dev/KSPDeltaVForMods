#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;
use tauri_plugin_shell::ShellExt;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let shell = app.shell();
            let (mut rx, _child) = shell
                .command("python")
                .args(["api.py"])
                .spawn()
                .expect("Failed to spawn Python API server");

            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        tauri_plugin_shell::process::CommandEvent::Stdout(line) => {
                            println!("[python:stdout] {}", String::from_utf8_lossy(&line));
                        }
                        tauri_plugin_shell::process::CommandEvent::Stderr(line) => {
                            eprintln!("[python:stderr] {}", String::from_utf8_lossy(&line));
                        }
                        tauri_plugin_shell::process::CommandEvent::Terminated(status) => {
                            eprintln!("[python] Process terminated: {:?}", status);
                        }
                        _ => {}
                    }
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
