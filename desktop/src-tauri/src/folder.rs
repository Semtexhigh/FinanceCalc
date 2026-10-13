// FinanceCalc — native folder storage
// Copyright (c) 2026 Zeeshan Saleem. All rights reserved.
//
// The web app can only ask the browser engine for storage, and WebKit has no
// showDirectoryPicker, so inside the desktop shell the "save to a real folder"
// tier is dark. These commands give the page a way to reach the real filesystem
// through the shell instead: pick a folder once (iCloud Drive, OneDrive, anywhere),
// remember it forever, and read/write files in it.
//
// File I/O lives here rather than going through tauri-plugin-fs on purpose: the
// plugin's scope system would have to be opened wide enough to cover an arbitrary
// user-chosen path, which is a much bigger grant than this needs. Here the only
// reachable location is the one folder the user picked, enforced by resolve().

use std::fs;
use std::path::{Component, Path, PathBuf};
use std::time::UNIX_EPOCH;

use base64::engine::general_purpose::STANDARD as BASE64;
use base64::Engine as _;
use serde::Serialize;
use tauri::{AppHandle, Manager};
use tauri_plugin_dialog::DialogExt;

/// Where the chosen folder's path is remembered between launches.
fn pointer_file(app: &AppHandle) -> Result<PathBuf, String> {
    let dir = app
        .path()
        .app_config_dir()
        .map_err(|e| format!("no config dir: {e}"))?;
    fs::create_dir_all(&dir).map_err(|e| format!("cannot create config dir: {e}"))?;
    Ok(dir.join("data-folder.txt"))
}

fn saved_root(app: &AppHandle) -> Option<PathBuf> {
    let p = pointer_file(app).ok()?;
    let s = fs::read_to_string(p).ok()?;
    let s = s.trim();
    if s.is_empty() {
        return None;
    }
    let path = PathBuf::from(s);
    if path.is_dir() {
        Some(path)
    } else {
        None // folder was moved or deleted; treat as not set rather than erroring
    }
}

/// Join `rel` onto the chosen folder, refusing anything that would escape it.
/// A relative path from the page is untrusted input, so `..`, absolute paths and
/// root/prefix components are all rejected rather than normalised away.
fn resolve(app: &AppHandle, rel: &str) -> Result<PathBuf, String> {
    let root = saved_root(app).ok_or_else(|| "no-folder".to_string())?;
    let rel_path = Path::new(rel);
    for c in rel_path.components() {
        match c {
            Component::Normal(_) => {}
            _ => return Err(format!("bad path: {rel}")),
        }
    }
    Ok(root.join(rel_path))
}

fn mtime_ms(p: &Path) -> u64 {
    fs::metadata(p)
        .and_then(|m| m.modified())
        .ok()
        .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

#[derive(Serialize)]
pub struct Stat {
    pub size: u64,
    pub mtime: u64,
}

#[derive(Serialize)]
pub struct FolderInfo {
    pub path: String,
    pub name: String,
}

fn info(path: PathBuf) -> FolderInfo {
    let name = path
        .file_name()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_else(|| path.to_string_lossy().to_string());
    FolderInfo {
        path: path.to_string_lossy().to_string(),
        name,
    }
}

/// Open the native folder chooser. Unlike the browser, the choice is permanent -
/// there is no per-session re-grant.
#[tauri::command]
pub async fn fc_pick_folder(app: AppHandle) -> Result<Option<FolderInfo>, String> {
    let (tx, rx) = tokio::sync::oneshot::channel();
    app.dialog().file().pick_folder(move |picked| {
        let _ = tx.send(picked);
    });
    let picked = rx.await.map_err(|e| format!("dialog closed: {e}"))?;
    let Some(p) = picked else { return Ok(None) };

    let path: PathBuf = p
        .into_path()
        .map_err(|e| format!("not a real folder: {e}"))?;
    if !path.is_dir() {
        return Err("that is not a folder".into());
    }
    // Fail now, loudly, rather than at the first save.
    let probe = path.join(".financecalc-write-test");
    fs::write(&probe, b"ok").map_err(|e| format!("cannot write to that folder: {e}"))?;
    let _ = fs::remove_file(&probe);

    fs::write(pointer_file(&app)?, path.to_string_lossy().as_bytes())
        .map_err(|e| format!("cannot remember that folder: {e}"))?;
    Ok(Some(info(path)))
}

#[tauri::command]
pub fn fc_folder(app: AppHandle) -> Option<FolderInfo> {
    saved_root(&app).map(info)
}

#[tauri::command]
pub fn fc_forget_folder(app: AppHandle) -> Result<(), String> {
    let p = pointer_file(&app)?;
    if p.exists() {
        fs::remove_file(p).map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
pub fn fc_read_text(app: AppHandle, rel: String) -> Result<Option<String>, String> {
    let p = resolve(&app, &rel)?;
    if !p.exists() {
        return Ok(None);
    }
    fs::read_to_string(&p).map(Some).map_err(|e| e.to_string())
}

/// Writes via a temp file + rename so a crash mid-write cannot leave a truncated
/// ledger behind. Returns the new mtime so the page can detect outside changes.
#[tauri::command]
pub fn fc_write_text(app: AppHandle, rel: String, contents: String) -> Result<u64, String> {
    let p = resolve(&app, &rel)?;
    if let Some(parent) = p.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let tmp = p.with_extension("tmp-fc");
    fs::write(&tmp, contents.as_bytes()).map_err(|e| e.to_string())?;
    fs::rename(&tmp, &p).map_err(|e| e.to_string())?;
    Ok(mtime_ms(&p))
}

// Photos cross the bridge as base64 rather than Vec<u8>. Tauri serialises command
// arguments as JSON, so a byte vector becomes an array of numbers - roughly 4x the
// size and painfully slow once there are a couple of hundred screenshots.

#[tauri::command]
pub fn fc_read_bytes(app: AppHandle, rel: String) -> Result<Option<String>, String> {
    let p = resolve(&app, &rel)?;
    if !p.exists() {
        return Ok(None);
    }
    let raw = fs::read(&p).map_err(|e| e.to_string())?;
    Ok(Some(BASE64.encode(raw)))
}

#[tauri::command]
pub fn fc_write_bytes(app: AppHandle, rel: String, b64: String) -> Result<(), String> {
    let bytes = BASE64.decode(b64.as_bytes()).map_err(|e| e.to_string())?;
    let p = resolve(&app, &rel)?;
    if let Some(parent) = p.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let tmp = p.with_extension("tmp-fc");
    fs::write(&tmp, &bytes).map_err(|e| e.to_string())?;
    fs::rename(&tmp, &p).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn fc_list(app: AppHandle, rel: String) -> Result<Vec<String>, String> {
    let p = resolve(&app, &rel)?;
    if !p.is_dir() {
        return Ok(vec![]);
    }
    let mut out = vec![];
    for entry in fs::read_dir(&p).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        if entry.file_type().map(|t| t.is_file()).unwrap_or(false) {
            let n = entry.file_name().to_string_lossy().to_string();
            // iCloud leaves .icloud placeholders for files it has evicted locally,
            // and macOS drops .DS_Store everywhere. Neither is ours.
            if n.starts_with('.') || n.ends_with(".tmp-fc") {
                continue;
            }
            out.push(n);
        }
    }
    Ok(out)
}

#[tauri::command]
pub fn fc_remove(app: AppHandle, rel: String) -> Result<(), String> {
    let p = resolve(&app, &rel)?;
    if p.exists() {
        fs::remove_file(p).map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
pub fn fc_stat(app: AppHandle, rel: String) -> Result<Option<Stat>, String> {
    let p = resolve(&app, &rel)?;
    if !p.exists() {
        return Ok(None);
    }
    let m = fs::metadata(&p).map_err(|e| e.to_string())?;
    Ok(Some(Stat {
        size: m.len(),
        mtime: mtime_ms(&p),
    }))
}
