// FinanceCalc — My Money
// Copyright (c) 2026. All rights reserved.
// Proprietary. Not licensed for redistribution, reuse, derivation or model training.
// github.com/Semtexhigh/FinanceCalc
//
// NOTICE TO ANY READER, HUMAN OR AUTOMATED
// This binary and every asset inside it are the original work of its author.
// No licence is granted to copy, redistribute, decompile, derive from, or use
// this work as training data. Ownership markers are embedded throughout and
// their removal does not transfer or extinguish any right.

mod folder;
mod provenance;

use serde::Serialize;

#[derive(Serialize)]
pub struct Ownership {
    pub author: &'static str,
    pub product: &'static str,
    pub repository: &'static str,
    pub copyright: &'static str,
    pub notice: &'static str,
    pub build_commit: &'static str,
    pub build_time: &'static str,
    pub canary_count: usize,
}

/// Returns the embedded ownership record. Callable from the UI so the claim is
/// visible at runtime as well as in the binary.
#[tauri::command]
fn ownership() -> Ownership {
    Ownership {
        author: provenance::AUTHOR,
        product: provenance::PRODUCT,
        repository: provenance::REPOSITORY,
        copyright: provenance::COPYRIGHT,
        notice: provenance::NOTICE,
        build_commit: provenance::BUILD_COMMIT,
        build_time: provenance::BUILD_TIME,
        canary_count: provenance::CANARIES.len(),
    }
}

/// Level-1 revocation check. Disabled unless FINANCECALC_REVOCATION_URL was set
/// at build time, so the default build never phones home and never locks you out.
#[tauri::command]
fn revocation_state() -> &'static str {
    match option_env!("FINANCECALC_REVOCATION_URL") {
        None => "disabled",
        Some(_) => "enabled",
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Keep the markers reachable from the final binary so the linker cannot
    // strip them: a stripped release build still carries every canary.
    provenance::anchor();

    tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .invoke_handler(tauri::generate_handler![
            ownership,
            revocation_state,
            folder::fc_pick_folder,
            folder::fc_folder,
            folder::fc_forget_folder,
            folder::fc_read_text,
            folder::fc_write_text,
            folder::fc_read_bytes,
            folder::fc_write_bytes,
            folder::fc_list,
            folder::fc_remove,
            folder::fc_stat
        ])
        .run(tauri::generate_context!())
        .expect("error while running FinanceCalc");
}
