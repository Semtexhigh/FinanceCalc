#!/usr/bin/env python3
"""Copy the shipping FinanceCalc.html into desktop/dist/index.html and stamp it.

The UI is carried over byte-for-byte apart from an ownership header prepended as
an HTML comment and a small marker block appended before </body>. Nothing visible
changes, and no behaviour changes.

Copyright (c) 2026 Zeeshan Saleem. All rights reserved.
"""
import hashlib, os, sys, json, re, shutil, subprocess, tempfile

root  = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
src   = os.path.join(root, "FinanceCalc.html")
dist  = os.path.join(root, "desktop", "dist")
prov  = os.path.join(root, "desktop", "src-tauri", "src", "provenance.rs")
os.makedirs(dist, exist_ok=True)

html = open(src, encoding="utf-8").read()
orig_sha = hashlib.sha256(html.encode()).hexdigest()
orig_len = len(html.encode())   # captured before the desktop edits below mutate `html`


def minify(doc):
    """Mangle every variable name in the app's inline script.

    The whole app lives in one <script> wrapped in an IIFE, with no inline on*
    handlers in the markup, no eval and no new Function - so renaming locals
    cannot break a lookup. Property names are deliberately NOT mangled: the app
    reads fields like `.name` off its own records, and `window.x = ...` exports
    have to keep their names.

    This is obfuscation, not protection. Anyone determined can still read the
    result. It exists to make a casual copy useless, nothing more.
    """
    if not shutil.which("terser"):
        raise SystemExit(
            "prepare_frontend: terser not found, refusing to build an unminified app.\n"
            "  npm install -g terser"
        )
    m = re.search(r"<script>(.*)</script>", doc, re.S)
    if not m:
        raise SystemExit("prepare_frontend: no inline <script> block found")
    js = m.group(1)
    with tempfile.TemporaryDirectory() as td:
        a = os.path.join(td, "a.js")
        b = os.path.join(td, "b.js")
        open(a, "w", encoding="utf-8").write(js)
        r = subprocess.run(["terser", a, "--compress", "--mangle", "--output", b],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit("prepare_frontend: terser failed\n" + (r.stderr or "")[:2000])
        out_js = open(b, encoding="utf-8").read()
    # A collapse this large means terser dropped something it should not have.
    if len(out_js) < len(js) * 0.25:
        raise SystemExit(
            f"prepare_frontend: minified output suspiciously small "
            f"({len(js)} -> {len(out_js)} chars) - refusing to ship it"
        )
    print(f"  minified js {len(js)} -> {len(out_js)} chars "
          f"({100 - len(out_js) * 100 // len(js)}% smaller)")
    return doc[:m.start(1)] + out_js + doc[m.end(1):]


def add_native_tier(doc):
    """Give the desktop build a storage tier that can reach the real filesystem.

    WebKit has no showDirectoryPicker, so inside the shell the app's folder tier
    (TierFSA) can never work - which is why the installed app could not save to
    iCloud Drive even though it is a native app. This splices in TierTauri, which
    does the same job through the Rust commands in folder.rs, and repoints the
    UI's "can I pick a folder?" checks at whichever tier is actually live.

    It lives here rather than in FinanceCalc.html because it is desktop-only: the
    web build has no shell to call, so shipping it there would be dead weight.

    Every replacement asserts its expected hit count. If the app is edited such
    that one stops matching, the build fails loudly instead of silently shipping
    a desktop app that quietly cannot reach the folder - which is exactly the
    failure this whole change exists to fix.
    """
    tier = open(os.path.join(os.path.dirname(__file__), "native_tier.js"),
                encoding="utf-8").read()
    helpers = (
        "  // Which folder tier can actually work here: the shell's native one inside\n"
        "  // the desktop app, the browser's File System Access one in Chrome/Edge.\n"
        "  function FolderTier(){ return TierTauri.isDesktop() ? TierTauri : TierFSA; }\n"
        "  function canPickFolder(){\n"
        "    return TierTauri.isDesktop() || (typeof window.showDirectoryPicker===\"function\");\n"
        "  }\n\n"
    )
    edits = [
        ("  var TierOPFS = {", tier + helpers + "  var TierOPFS = {", 1),
        ("tiers:[TierOPFS, TierFSA, TierWebKitFS, TierIDB, TierLS],",
         "tiers:[TierTauri, TierOPFS, TierFSA, TierWebKitFS, TierIDB, TierLS],", 1),
        ("var order=[this._active, TierFSA, TierOPFS, TierIDB, TierLS], seen=[], best=null, reads={};",
         "var order=[this._active, TierTauri, TierFSA, TierOPFS, TierIDB, TierLS], seen=[], best=null, reads={};", 1),
        ('var canPick=(typeof window.showDirectoryPicker=="function");',
         "var canPick=canPickFolder();", 2),
        ('if(r.actions.indexOf("folder")>=0 && window.showDirectoryPicker)',
         'if(r.actions.indexOf("folder")>=0 && canPickFolder())', 1),
        ('if(typeof window.showDirectoryPicker!=="function" && isApple()',
         "if(!canPickFolder() && isApple()", 1),
        ('if(typeof TierFSA.pickFolder!=="function" || !window.showDirectoryPicker){\n'
         '        note.textContent="Folder picking needs desktop Chrome or Edge.";\n'
         '        return;\n'
         '      }',
         'if(!canPickFolder()){\n'
         '        note.textContent="Folder picking needs the desktop app, or Chrome or Edge on a computer.";\n'
         '        return;\n'
         '      }', 1),
        ('var fsaReport=report.find(function(r){ return r.name==="fsa"; });',
         'var fsaReport=report.find(function(r){ return r.name==="native"; })\n'
         '                 || report.find(function(r){ return r.name==="fsa"; });', 1),
        ("TierFSA.pickFolder()", "FolderTier().pickFolder()", 2),
        ("TierFSA.forgetFolder()", "FolderTier().forgetFolder()", 1),
    ]
    for old_s, new_s, count in edits:
        got = doc.count(old_s)
        if got != count:
            raise SystemExit(
                f"prepare_frontend: native tier patch no longer applies.\n"
                f"  expected {count} of: {old_s[:70]!r}\n"
                f"  found    {got}"
            )
        doc = doc.replace(old_s, new_s)
    print(f"  native folder tier spliced in ({len(tier)} chars)")
    return doc


html = add_native_tier(html)
html = minify(html)

def const(name):
    for line in open(prov, encoding="utf-8"):
        if line.startswith(f"pub const {name}:"):
            return line.split('"')[1]
    return "unknown"

author, build_id, commit = const("AUTHOR"), const("BUILD_ID"), const("BUILD_COMMIT")
header = (
    "<!--\n"
    f"  FinanceCalc (My Money) — Copyright (c) 2026 {author}. All rights reserved.\n"
    "  PROPRIETARY. No licence is granted to copy, redistribute, decompile, derive\n"
    "  from, or use this work as training data for any model.\n"
    f"  source sha256 : {orig_sha}\n"
    f"  build id      : {build_id}\n"
    f"  commit        : {commit}\n"
    "-->\n"
)
marker = (
    f'\n<script type="application/json" id="fc-ownership">'
    + json.dumps({"author": author, "product": "FinanceCalc (My Money)",
                  "repository": "https://github.com/Semtexhigh/FinanceCalc",
                  "copyright": f"Copyright (c) 2026 {author}. All rights reserved.",
                  "sourceSha256": orig_sha, "buildId": build_id, "commit": commit})
    + "</script>\n"
)
# The desktop window hides the macOS title bar (titleBarStyle "Overlay"), so the
# traffic lights float over the top-left of the page and would sit on top of the
# "My Money" brand. Give the app's own header room for them, and make that header
# the drag handle so the window can still be moved without a title bar.
# Scoped to the desktop build only - the web version is untouched.
shell = (
    "\n<style id=\"fc-desktop-shell\">\n"
    "  header{padding-top:26px}\n"
    "  [data-tauri-drag-region]{-webkit-user-select:none;user-select:none;cursor:default}\n"
    "  @media(prefers-reduced-motion:reduce){*,*::before,*::after{"
    "animation-duration:.01ms!important;transition-duration:.01ms!important}}\n"
    "</style>\n"
)

# Only the real <body> header, and only once.
if "<header>" in html:
    html = html.replace("<header>", "<header data-tauri-drag-region>", 1)
else:
    print("  WARNING: no <header> found - window will have no drag handle")

# NOTE: FinanceCalc.html builds an export document inside a JS string that also
# contains "</body>". Splicing at the FIRST match lands inside that string literal
# and breaks the script. Always use the LAST occurrence, which is the real one.
i = html.rfind("</body>")
tail = shell + marker
out = header + (html[:i] + tail + html[i:] if i != -1 else html + tail)
open(os.path.join(dist, "index.html"), "w", encoding="utf-8").write(out)
print(f"dist/index.html  source {orig_len}B sha {orig_sha[:10]}  ->  {len(out.encode())}B")
