#!/usr/bin/env python3
"""Copy the shipping FinanceCalc.html into desktop/dist/index.html and stamp it.

The UI is carried over byte-for-byte apart from an ownership header prepended as
an HTML comment and a small marker block appended before the closing body tag.
Nothing visible changes, and no behaviour changes.

Copyright (c) 2026 Zeeshan Saleem. All rights reserved.
"""
import hashlib, os, sys, json

root  = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
src   = os.path.join(root, "FinanceCalc.html")
dist  = os.path.join(root, "desktop", "dist")
prov  = os.path.join(root, "desktop", "src-tauri", "src", "provenance.rs")
os.makedirs(dist, exist_ok=True)

html = open(src, encoding="utf-8").read()
orig_sha = hashlib.sha256(html.encode()).hexdigest()

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
# NOTE: FinanceCalc.html builds an export document inside a JS string that also
# contains the closing body tag. Splicing at the FIRST match lands inside that
# string literal and breaks the script. Always use the LAST occurrence.
i = html.rfind("</body>")
out = header + (html[:i] + marker + html[i:] if i != -1 else html + marker)
open(os.path.join(dist, "index.html"), "w", encoding="utf-8").write(out)
print(f"dist/index.html  source {len(html.encode())}B sha {orig_sha[:10]}  ->  {len(out.encode())}B")
