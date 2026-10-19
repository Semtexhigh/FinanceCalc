// FinanceCalc — desktop shell
// Copyright (c) 2026 Semtexhigh. All rights reserved.
// Proprietary. Not licensed for redistribution, reuse, derivation or training.
//
// Touch ID, for unlocking the app.
//
// The web view cannot reach the sensor: WebAuthn needs an https origin and the
// shell serves the page from its own scheme, so the browser route is refused
// before a prompt is ever shown. macOS exposes the sensor to the process
// instead, through LocalAuthentication, which is what this asks.
//
// It is a gate and nothing more: no key is derived from it and the vault is not
// bound to it. The PIN stays underneath as the fallback, exactly as it is for
// face unlock. Both commands answer `false` rather than failing, so a Mac with
// no sensor, a cancelled prompt and a refused prompt all look the same to the
// page: the offer is simply not made, or not accepted.

#[cfg(target_os = "macos")]
mod imp {
    use block2::RcBlock;
    use objc2_foundation::NSString;
    use objc2_local_authentication::{LAContext, LAPolicy};
    use std::sync::mpsc;
    use std::time::Duration;

    // Biometrics only. DeviceOwnerAuthentication would fall back to the login
    // password, which is not what "fingerprint" means to anyone reading it.
    const POLICY: LAPolicy = LAPolicy::DeviceOwnerAuthenticationWithBiometrics;

    pub fn available() -> bool {
        unsafe {
            let ctx = LAContext::new();
            ctx.canEvaluatePolicy_error(POLICY).is_ok()
        }
    }

    pub fn prompt(reason: &str) -> bool {
        unsafe {
            let ctx = LAContext::new();
            if ctx.canEvaluatePolicy_error(POLICY).is_err() {
                return false;
            }
            let (tx, rx) = mpsc::channel::<bool>();
            let block = RcBlock::new(move |ok: objc2::runtime::Bool, _err: *mut objc2_foundation::NSError| {
                // A send failure just means we already timed out and gave up.
                let _ = tx.send(ok.as_bool());
            });
            ctx.evaluatePolicy_localizedReason_reply(POLICY, &NSString::from_str(reason), &block);
            // The sheet is modal to the app, but never block forever on it.
            rx.recv_timeout(Duration::from_secs(120)).unwrap_or(false)
        }
    }
}

#[cfg(not(target_os = "macos"))]
mod imp {
    pub fn available() -> bool {
        false
    }
    pub fn prompt(_reason: &str) -> bool {
        false
    }
}

#[tauri::command]
pub async fn fc_touchid_available() -> Result<bool, String> {
    Ok(tauri::async_runtime::spawn_blocking(imp::available)
        .await
        .unwrap_or(false))
}

#[tauri::command]
pub async fn fc_touchid(reason: String) -> Result<bool, String> {
    Ok(
        tauri::async_runtime::spawn_blocking(move || imp::prompt(&reason))
            .await
            .unwrap_or(false),
    )
}
