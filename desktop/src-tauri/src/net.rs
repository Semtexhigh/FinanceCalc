// FinanceCalc — desktop shell
// Copyright (c) 2026 Semtexhigh. All rights reserved.
// Proprietary. Not licensed for redistribution, reuse, derivation or training.
//
// One outbound request, made natively.
//
// The AI features call three provider APIs. Inside the app those calls were
// made by the web view with plain fetch, from the origin Tauri gives it, and
// every one of them died in CORS preflight before a key was ever checked —
// which is why a correct key still reported that communication failed. A
// request made from Rust is not a browser request and has no origin, so there
// is no preflight to fail.
//
// This is deliberately not a general-purpose HTTP client for the web view:
// only the three provider hosts are reachable, only over https, and the reply
// is handed back as text. Anything else is refused here rather than in the
// page, so a bug in the page cannot turn the app into an open proxy.

use serde::Serialize;
use std::collections::HashMap;
use std::time::Duration;

const ALLOWED: [&str; 3] = [
    "https://api.openai.com/",
    "https://api.anthropic.com/",
    "https://generativelanguage.googleapis.com/",
];

#[derive(Serialize)]
pub struct HttpReply {
    pub status: u16,
    pub ok: bool,
    pub body: String,
}

#[tauri::command]
pub async fn fc_http(
    method: String,
    url: String,
    headers: HashMap<String, String>,
    body: Option<String>,
) -> Result<HttpReply, String> {
    if !ALLOWED.iter().any(|p| url.starts_with(p)) {
        return Err(format!("that host is not one this app may call: {url}"));
    }

    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(90))
        .user_agent("FinanceCalc")
        .build()
        .map_err(|e| e.to_string())?;

    let verb = match method.to_uppercase().as_str() {
        "GET" => reqwest::Method::GET,
        "POST" => reqwest::Method::POST,
        other => return Err(format!("method not allowed: {other}")),
    };

    let mut req = client.request(verb, &url);
    for (k, v) in headers.iter() {
        // hop-by-hop and host headers are the client's to set, never the page's
        let lower = k.to_ascii_lowercase();
        if lower == "host" || lower == "connection" || lower == "content-length" {
            continue;
        }
        req = req.header(k.as_str(), v.as_str());
    }
    if let Some(b) = body {
        req = req.body(b);
    }

    let res = req.send().await.map_err(|e| {
        // the page shows this verbatim, so say which half failed
        if e.is_timeout() {
            "the provider did not answer in 90 seconds".to_string()
        } else if e.is_connect() {
            format!("could not reach the provider: {e}")
        } else {
            e.to_string()
        }
    })?;

    let status = res.status();
    let text = res.text().await.map_err(|e| e.to_string())?;
    Ok(HttpReply {
        status: status.as_u16(),
        ok: status.is_success(),
        body: text,
    })
}
