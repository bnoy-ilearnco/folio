use serde::Deserialize;

#[derive(Deserialize)]
pub struct PageSettings {
    size: String,
    orientation: String,
    top: f64,
    right: f64,
    bottom: f64,
    left: f64,
}

#[tauri::command]
pub async fn export_pdf(
    window: tauri::WebviewWindow,
    name: String,
    page: PageSettings,
) -> Result<Option<String>, String> {
    if ![page.top, page.right, page.bottom, page.left]
        .iter()
        .all(|v| v.is_finite() && *v >= 0.0 && *v <= 100.0)
        || !["A4", "Letter"].contains(&page.size.as_str())
        || !["portrait", "landscape"].contains(&page.orientation.as_str())
    {
        return Err("Invalid PDF page settings.".into());
    }
    let safe_name: String = name
        .chars()
        .filter(|c| !"<>:\"/\\|?*".contains(*c) && !c.is_control())
        .take(100)
        .collect();
    let file = rfd::AsyncFileDialog::new()
        .set_title("Export PDF")
        .set_file_name(format!(
            "{}.pdf",
            if safe_name.trim().is_empty() {
                "Untitled"
            } else {
                safe_name.trim()
            }
        ))
        .add_filter("PDF", &["pdf"])
        .save_file()
        .await;
    let Some(file) = file else { return Ok(None) };
    let path = file.path().to_path_buf();
    if !path
        .extension()
        .and_then(|e| e.to_str())
        .is_some_and(|e| e.eq_ignore_ascii_case("pdf"))
    {
        return Err("Choose a .pdf filename.".into());
    }
    let parent = path.parent().ok_or("Invalid PDF destination")?;
    let temporary = tempfile::tempdir_in(parent)
        .map_err(|e| format!("Cannot create PDF staging folder: {e}"))?;
    let staged = temporary.path().join("document.pdf");
    #[cfg(windows)]
    {
        use std::sync::{Arc, Mutex};
        use webview2_com::{Microsoft::Web::WebView2::Win32::*, PrintToPdfCompletedHandler};
        use windows::core::{Interface, HSTRING};
        let (tx, rx) = tokio::sync::oneshot::channel::<Result<(), String>>();
        let sender = Arc::new(Mutex::new(Some(tx)));
        let destination = staged.to_string_lossy().into_owned();
        window
            .with_webview(move |view| {
                let callback_sender = sender.clone();
                let started = (|| unsafe {
                    let core: ICoreWebView2_7 = view.controller().CoreWebView2()?.cast()?;
                    let environment: ICoreWebView2Environment6 = view.environment().cast()?;
                    let settings = environment.CreatePrintSettings()?;
                    let (w, h) = if page.size == "A4" {
                        (210.0, 297.0)
                    } else {
                        (215.9, 279.4)
                    };
                    settings.SetOrientation(if page.orientation == "landscape" {
                        COREWEBVIEW2_PRINT_ORIENTATION_LANDSCAPE
                    } else {
                        COREWEBVIEW2_PRINT_ORIENTATION_PORTRAIT
                    })?;
                    settings.SetPageWidth(w / 25.4)?;
                    settings.SetPageHeight(h / 25.4)?;
                    settings.SetMarginTop(page.top / 25.4)?;
                    settings.SetMarginBottom(page.bottom / 25.4)?;
                    settings.SetMarginLeft(page.left / 25.4)?;
                    settings.SetMarginRight(page.right / 25.4)?;
                    settings.SetShouldPrintBackgrounds(true)?;
                    settings.SetShouldPrintHeaderAndFooter(false)?;
                    core.PrintToPdf(
                        &HSTRING::from(destination),
                        &settings,
                        &PrintToPdfCompletedHandler::create(Box::new(move |error, success| {
                            let result = error
                                .map_err(|e| format!("PDF export failed: {e}"))
                                .and_then(|_| {
                                    if success {
                                        Ok(())
                                    } else {
                                        Err("Windows could not generate the PDF.".into())
                                    }
                                });
                            if let Some(tx) = callback_sender.lock().unwrap().take() {
                                let _ = tx.send(result);
                            }
                            Ok(())
                        })),
                    )
                })();
                if let Err(error) = started {
                    if let Some(tx) = sender.lock().unwrap().take() {
                        let _ = tx.send(Err(format!("Cannot start PDF export: {error}")));
                    }
                }
            })
            .map_err(|e| e.to_string())?;
        tokio::time::timeout(std::time::Duration::from_secs(90), rx)
            .await
            .map_err(|_| "PDF export timed out")?
            .map_err(|_| "PDF export was interrupted")??;
    }
    #[cfg(not(windows))]
    {
        let _ = (window, page);
        return Err("Direct PDF export currently requires Windows.".into());
    }
    let bytes = std::fs::read(&staged).map_err(|e| format!("Cannot read generated PDF: {e}"))?;
    if !bytes.starts_with(b"%PDF") {
        return Err("Windows returned an invalid PDF.".into());
    }
    let mut output = tempfile::NamedTempFile::new_in(parent).map_err(|e| e.to_string())?;
    use std::io::Write;
    output.write_all(&bytes).map_err(|e| e.to_string())?;
    output.as_file().sync_all().map_err(|e| e.to_string())?;
    output.persist(&path).map_err(|e| {
        format!(
            "Cannot save PDF: {}. The original file was preserved.",
            e.error
        )
    })?;
    Ok(Some(path.to_string_lossy().into_owned()))
}
