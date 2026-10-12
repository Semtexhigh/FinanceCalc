# FinanceCalc — macOS desktop

The same app, wrapped in a Tauri 2 shell: a Rust binary with the UI compiled in.
Nothing about the interface changes.

## What you get

| | |
|---|---|
| Bundle | `FinanceCalc.app` inside a `.dmg`, universal (Apple Silicon + Intel) |
| Storage | real files in `~/Library/Application Support/com.semtexhigh.financecalc/` — no OPFS, nothing lost to "clear website data" |
| Auto-update | built in. The app checks `desktop/latest.json`, verifies an Ed25519 signature, installs on restart |
| Ownership | 256 markers compiled into the binary, a signed `PROVENANCE.json`, headers on every file |
| Revocation | level-1 kill switch, **off** unless built with `FINANCECALC_REVOCATION_URL` |

## Releasing a build

1. `git tag desktop-v0.1.0`
2. `git push origin desktop-v0.1.0`
3. Actions runs `desktop-release` on a macOS runner (~10 min)
4. The `.dmg` appears on the Releases page

Or: Actions → desktop-release → Run workflow, for a build without a tag.

## Required secret

`TAURI_SIGNING_PRIVATE_KEY` — the updater key. Without it the app still builds,
but updates cannot be signed, so auto-update will refuse them.

## Optional secrets (Apple signing)

Add all five and the build is signed and notarised; the `.dmg` then opens on a
double-click with no warning. Leave them out and macOS warns on first open.

`APPLE_CERTIFICATE` (base64 .p12) · `APPLE_CERTIFICATE_PASSWORD` ·
`APPLE_SIGNING_IDENTITY` · `APPLE_ID` · `APPLE_PASSWORD` · `APPLE_TEAM_ID`

## Building locally (needs a Mac with Xcode CLT and Rust)

1. `npm install -g @tauri-apps/cli@^2`
2. `python3 desktop/tools/gen_provenance.py`
3. `python3 desktop/tools/prepare_frontend.py`
4. `cd desktop && tauri build --target universal-apple-darwin`

## Layout

```
desktop/
  dist/index.html        generated from ../FinanceCalc.html — never edit directly
  src-tauri/
    src/main.rs          entry point
    src/lib.rs           app setup, ownership + revocation commands
    src/provenance.rs    generated — 256 ownership markers
    tauri.conf.json      window, bundle and updater config
  tools/
    gen_provenance.py    regenerates provenance.rs with a fresh build id
    prepare_frontend.py  stamps FinanceCalc.html into dist/index.html
    gen_manifest.py      writes PROVENANCE.json
```
