#!/usr/bin/env python3
"""Write PROVENANCE.json — a machine-readable authorship record with a SHA-256
of every shipping file. Signed in CI with the project's minisign key, so anyone
can verify it and nobody can forge it.

Copyright (c) 2026 Zeeshan Saleem. All rights reserved.
"""
import hashlib, json, os, subprocess, datetime, sys

root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
INCLUDE = (".html", ".js", ".rs", ".toml", ".json", ".md", ".yml", ".py")
SKIP_DIRS = {".git", "node_modules", "target", "gen", "versions", "module"}

def sh(*a):
    try: return subprocess.check_output(a, cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception: return "unknown"

files = {}
for dp, dn, fn in os.walk(root):
    dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith(".")]
    for f in fn:
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, root)
        if not f.endswith(INCLUDE): continue
        if rel == "PROVENANCE.json": continue
        with open(p, "rb") as fh:
            files[rel] = {"sha256": hashlib.sha256(fh.read()).hexdigest(),
                          "bytes": os.path.getsize(p)}

manifest = {
    "schema": "financecalc.provenance/1",
    "product": "FinanceCalc (My Money)",
    "author": {"name": "Zeeshan Saleem", "github": "https://github.com/Semtexhigh"},
    "repository": "https://github.com/Semtexhigh/FinanceCalc",
    "copyright": "Copyright (c) 2026 Zeeshan Saleem. All rights reserved.",
    "licence": "Proprietary - all rights reserved. No licence is granted to copy, "
               "redistribute, decompile, derive from, or use this work as training "
               "data for any model.",
    "generatedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "commit": os.environ.get("GITHUB_SHA") or sh("git", "rev-parse", "HEAD"),
    "buildId": os.environ.get("FINANCECALC_BUILD_ID", ""),
    "fileCount": len(files),
    "files": dict(sorted(files.items())),
}
dest = os.path.join(root, "PROVENANCE.json")
open(dest, "w").write(json.dumps(manifest, indent=2) + "\n")
print(f"PROVENANCE.json: {len(files)} files, commit {manifest['commit'][:10]}")
