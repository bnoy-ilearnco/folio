#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
mod library;
mod pdf;
use std::{io::Write, path::PathBuf, sync::Mutex};

#[derive(Default)]
struct DocumentPath(Mutex<Option<PathBuf>>);

#[derive(Serialize)]
struct OpenedDocument {
    name: String,
    path: String,
    bytes: Vec<u8>,
}

#[tauri::command]
async fn open_document(
    state: tauri::State<'_, DocumentPath>,
) -> Result<Option<OpenedDocument>, String> {
    let file = rfd::AsyncFileDialog::new()
        .set_title("Open document")
        .add_filter("Documents", &["odt", "docx", "dwd"])
        .pick_file()
        .await;
    let Some(file) = file else {
        return Ok(None);
    };
    let path = file.path().to_path_buf();
    let extension = path
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    if extension != "odt" && extension != "docx" && extension != "dwd" {
        return Err("Choose an ODT, DOCX or DavkaWriter DWD document.".into());
    }
    let metadata = std::fs::metadata(&path).map_err(|e| format!("Cannot read document: {e}"))?;
    if metadata.len() > 30 * 1024 * 1024 {
        return Err("This version opens files up to 30 MB.".into());
    }
    let bytes = std::fs::read(&path).map_err(|e| format!("Cannot read document: {e}"))?;
    // Retain the prior save target until the frontend has parsed the new document.
    *state
        .0
        .lock()
        .map_err(|_| "Document state is unavailable")? = None;
    Ok(Some(OpenedDocument {
        name: path
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .into_owned(),
        path: path.to_string_lossy().into_owned(),
        bytes,
    }))
}

#[tauri::command]
fn reset_document(state: tauri::State<'_, DocumentPath>) -> Result<(), String> {
    *state
        .0
        .lock()
        .map_err(|_| "Document state is unavailable")? = None;
    Ok(())
}

#[tauri::command]
async fn save_document(
    bytes: Vec<u8>,
    name: String,
    format: String,
    save_as: bool,
    state: tauri::State<'_, DocumentPath>,
) -> Result<Option<String>, String> {
    if !["odt", "docx", "pdf"].contains(&format.as_str()) {
        return Err("Unsupported export format.".into());
    }
    if bytes.len() > 100 * 1024 * 1024 {
        return Err("Document exceeds the save size limit.".into());
    }
    let existing = if format == "odt" && !save_as {
        state
            .0
            .lock()
            .map_err(|_| "Document state is unavailable")?
            .clone()
    } else {
        None
    };
    let path = if let Some(path) = existing {
        path
    } else {
        let safe_name: String = name
            .chars()
            .filter(|c| !"<>:\"/\\|?*".contains(*c) && !c.is_control())
            .take(100)
            .collect();
        let safe_name = if safe_name.trim().is_empty() {
            "Untitled"
        } else {
            safe_name.trim()
        };
        let file = rfd::AsyncFileDialog::new()
            .set_title(if format == "odt" {
                "Save document"
            } else {
                "Export document"
            })
            .set_file_name(format!("{safe_name}.{format}"))
            .add_filter(format.to_uppercase(), &[format.as_str()])
            .save_file()
            .await;
        let Some(file) = file else {
            return Ok(None);
        };
        let mut path = file.path().to_path_buf();
        // Do not silently redirect to another filename after the overwrite dialog.
        if path
            .extension()
            .and_then(|s| s.to_str())
            .map(|s| !s.eq_ignore_ascii_case(&format))
            .unwrap_or(true)
        {
            return Err(format!(
                "Use a .{format} filename. Choose Save As to try again."
            ));
        }
        path.set_extension(&format);
        path
    };
    let parent = path.parent().ok_or("Invalid destination folder")?;
    let mut temporary = tempfile::NamedTempFile::new_in(parent)
        .map_err(|e| format!("Cannot create save file: {e}"))?;
    temporary
        .write_all(&bytes)
        .map_err(|e| format!("Cannot write document: {e}"))?;
    temporary
        .as_file()
        .sync_all()
        .map_err(|e| format!("Cannot finish writing document: {e}"))?;
    temporary.persist(&path).map_err(|e| {
        format!(
            "Cannot replace destination: {}. The previous file was preserved.",
            e.error
        )
    })?;
    if format == "odt" {
        *state
            .0
            .lock()
            .map_err(|_| "Document state is unavailable")? = Some(path.clone());
    }
    Ok(Some(path.to_string_lossy().into_owned()))
}

#[tauri::command]
async fn print_document(window: tauri::WebviewWindow) -> Result<(), String> {
    window
        .print()
        .map_err(|e| format!("Cannot open print dialog: {e}"))
}

fn main() {
    tauri::Builder::default()
        .manage(DocumentPath::default())
        .invoke_handler(tauri::generate_handler![
            open_document,
            reset_document,
            save_document,
            print_document,
            library::library_catalog,
            library::library_sections,
            library::library_read,
            library::library_search,
            pdf::export_pdf
        ])
        .run(tauri::generate_context!())
        .expect("Folio could not start");
}
