#!/usr/bin/env python3
"""
vaultpack - build a password-protected payload set for the owner vault.

Every payload is gzipped, then encrypted with AES-256-GCM under one random
data key.  The data key itself is wrapped once per accepted password, so a
password can be added, changed or revoked by rewriting a 100-byte slot
instead of re-encrypting the payloads.

    python3 tools/vaultpack.py spec.json

spec.json:
{
  "out":       "vault/b",            # where the .enc blobs go
  "url_dir":   "b",                  # how the page addresses them
  "manifest":  "vault/manifest.json",
  "iterations": 310000,
  "part_max":  3000000,              # split anything larger than this
  "passwords": {"owner": "...", "alt": "..."},
  "items": [{"id":"b001","kind":"build","name":"v1.0","src":"versions/001 ....html",
             "meta":{"seq":"001"}}]
}

The manifest holds no secret: the slots are useless without a password and
the blobs are useless without the data key.
"""
import base64, gzip, hashlib, json, os, sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

b64 = lambda b: base64.b64encode(b).decode("ascii")


def derive(password: str, salt: bytes, iterations: int) -> bytes:
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                      salt=salt, iterations=iterations).derive(password.encode("utf-8"))


def wrap(data_key: bytes, password: str, iterations: int) -> dict:
    """One password slot: PBKDF2 -> AES-GCM over the data key."""
    salt = os.urandom(16)
    iv = os.urandom(12)
    ct = AESGCM(derive(password, salt, iterations)).encrypt(iv, data_key, None)
    return {"salt": b64(salt), "iv": b64(iv), "ct": b64(ct)}


def pack(spec: dict, root: str = ".") -> dict:
    iters = int(spec.get("iterations", 310000))
    out_dir = os.path.join(root, spec["out"])
    os.makedirs(out_dir, exist_ok=True)

    data_key = os.urandom(32)
    aes = AESGCM(data_key)

    slots = {name: wrap(data_key, pw, iters) for name, pw in spec["passwords"].items()}

    items, total_in, total_out = [], 0, 0
    for it in spec["items"]:
        src = os.path.join(root, it["src"])
        raw = open(src, "rb").read()
        gz = gzip.compress(raw, 9, mtime=0)                  # mtime=0 -> reproducible
        iv = os.urandom(12)
        ct = aes.encrypt(iv, gz, it["id"].encode("ascii"))   # id is bound in as AAD
        blob = os.path.join(out_dir, it["id"] + ".enc")
        part_max = int(spec.get("part_max", 0))
        parts = 0
        if part_max and len(ct) > part_max:
            parts = (len(ct) + part_max - 1) // part_max
            for n in range(parts):
                with open("%s.%d" % (blob, n), "wb") as fh:
                    fh.write(ct[n*part_max:(n+1)*part_max])
        else:
            with open(blob, "wb") as fh:
                fh.write(ct)
        total_in += len(raw)
        total_out += len(ct)
        rec = {"id": it["id"], "kind": it["kind"], "name": it["name"],
               "file": it.get("file") or os.path.basename(it["src"]),
               "iv": b64(iv), "gz": True,
               **({"parts": parts} if parts else {}),
               "bytes": len(raw), "enc": len(ct),
               "sha256": hashlib.sha256(raw).hexdigest()}
        rec.update(it.get("meta") or {})
        items.append(rec)

    manifest = {"v": 1, "alg": "AES-GCM-256", "kdf": "PBKDF2-SHA256",
                "iterations": iters, "wrap": "aes-gcm-256",
                "slots": slots, "dir": spec.get("url_dir", spec["out"]), "items": items}
    mpath = os.path.join(root, spec["manifest"])
    os.makedirs(os.path.dirname(mpath) or ".", exist_ok=True)
    with open(mpath, "w") as fh:
        json.dump(manifest, fh, separators=(",", ":"))
    return {"items": len(items), "plain": total_in, "cipher": total_out,
            "manifest": mpath, "manifest_bytes": os.path.getsize(mpath)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: vaultpack.py spec.json [repo-root]")
    spec = json.load(open(sys.argv[1]))
    root = sys.argv[2] if len(sys.argv) > 2 else "."
    r = pack(spec, root)
    print("packed {items} items  {plain} -> {cipher} bytes"
          "  manifest {manifest} ({manifest_bytes} bytes)".format(**r))
