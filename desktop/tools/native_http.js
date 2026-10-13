/* FinanceCalc — desktop shell
   Copyright (c) 2026 Semtexhigh. All rights reserved.

   Make the AI providers reachable from inside the app.

   The app talks to three provider APIs with plain fetch. In a browser that is
   an ordinary cross-origin request; inside the shell the page's origin is the
   one Tauri hands it, and the providers answer the CORS preflight with a
   refusal — so every request failed before the key was ever looked at. A
   correct key and a wrong key failed in exactly the same way, which is why it
   read as "communication failed" rather than "bad key".

   This swaps window.fetch for one that sends those three hosts through
   fc_http in the Rust shell. A request made from Rust is not a browser
   request: no origin, no preflight, nothing to refuse. Everything else is
   handed to the real fetch untouched, and on a build with no shell around it
   this file does nothing at all. */
(function () {
  "use strict";
  var T = window.__TAURI__;
  if (!T || !T.core || typeof T.core.invoke !== "function") return;   /* not the desktop app */
  if (!window.fetch) return;

  var HOSTS = [
    "https://api.openai.com/",
    "https://api.anthropic.com/",
    "https://generativelanguage.googleapis.com/"
  ];

  var real = window.fetch.bind(window);

  function headersOf(init, input) {
    var out = {};
    var h = (init && init.headers) || (input && input.headers) || null;
    if (!h) return out;
    try {
      if (typeof h.forEach === "function" && typeof h.get === "function") {
        h.forEach(function (v, k) { out[k] = v; });            /* Headers */
      } else if (Array.isArray(h)) {
        h.forEach(function (p) { if (p && p.length > 1) out[p[0]] = p[1]; });
      } else {
        Object.keys(h).forEach(function (k) { out[k] = String(h[k]); });
      }
    } catch (e) { /* a malformed header bag should not take the request down */ }
    return out;
  }

  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : (input && input.url) || "";
    var native = false;
    for (var i = 0; i < HOSTS.length; i++) if (url.indexOf(HOSTS[i]) === 0) { native = true; break; }
    if (!native) return real(input, init);

    init = init || {};
    var body = init.body;
    if (body != null && typeof body !== "string") {
      try { body = JSON.stringify(body); } catch (e) { body = String(body); }
    }

    return T.core.invoke("fc_http", {
      method: String(init.method || (input && input.method) || "GET").toUpperCase(),
      url: url,
      headers: headersOf(init, input),
      body: body == null ? null : String(body)
    }).then(function (r) {
      /* Hand back a real Response so every caller - .ok, .status, .json(),
         .text() - behaves exactly as it did against the network. */
      return new Response(r.body, {
        status: r.status || 500,
        statusText: r.ok ? "OK" : "Error",
        headers: { "content-type": "application/json" }
      });
    }).catch(function (e) {
      var msg = (e && (e.message || e.toString())) || "unknown error";
      return Promise.reject(new TypeError("the app could not reach the provider: " + msg));
    });
  };
})();
