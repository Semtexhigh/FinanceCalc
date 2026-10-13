#!/usr/bin/env python3
"""
vaultkey - change who can open a vault, without touching the payloads.

The payloads are encrypted under one random data key.  The manifest carries
that key wrapped once per password.  So changing, adding or revoking a
password rewrites about a hundred bytes of JSON; the ciphertext is never
re-encrypted and never re-uploaded.

    # what opens it now
    python3 tools/vaultkey.py vault/manifest.json --list

    # add a password (needs one that already works, to get the key out)
    python3 tools/vaultkey.py vault/manifest.json --open CURRENT --add laptop=NEW

    # revoke one
    python3 tools/vaultkey.py vault/manifest.json --open CURRENT --drop laptop

    # throw them all away and use a single strong passphrase
    python3 tools/vaultkey.py vault/manifest.json --open CURRENT \\
        --only owner="correct horse battery staple"

A short password is the weak link in all of this: the ciphertext is public,
so anyone holding it can guess offline at whatever rate their hardware
allows.  310,000 PBKDF2 iterations slow that down, they do not stop it.
Length is what stops it.
"""
import argparse, base64, json, os, sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

b64e = lambda b: base64.b64encode(b).decode("ascii")
b64d = base64.b64decode


def derive(password, salt, iterations):
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                      salt=salt, iterations=iterations).derive(password.encode("utf-8"))


def unwrap(manifest, password):
    """Return (slot name, data key) for whichever slot this password opens."""
    iters = int(manifest.get("iterations", 310000))
    for name, slot in manifest.get("slots", {}).items():
        try:
            key = derive(password, b64d(slot["salt"]), iters)
            return name, AESGCM(key).decrypt(b64d(slot["iv"]), b64d(slot["ct"]), None)
        except Exception:
            continue
    return None, None


def wrap(data_key, password, iterations):
    salt, iv = os.urandom(16), os.urandom(12)
    ct = AESGCM(derive(password, salt, iterations)).encrypt(iv, data_key, None)
    return {"salt": b64e(salt), "iv": b64e(iv), "ct": b64e(ct)}


def main():
    ap = argparse.ArgumentParser(description="add, drop or replace vault passwords")
    ap.add_argument("manifest")
    ap.add_argument("--list", action="store_true", help="show the slot names and stop")
    ap.add_argument("--open", dest="current", help="a password that works today")
    ap.add_argument("--add", action="append", default=[], metavar="NAME=PASSWORD")
    ap.add_argument("--drop", action="append", default=[], metavar="NAME")
    ap.add_argument("--only", action="append", default=[], metavar="NAME=PASSWORD",
                    help="replace every slot with these")
    a = ap.parse_args()

    man = json.load(open(a.manifest))
    iters = int(man.get("iterations", 310000))
    slots = man.setdefault("slots", {})

    if a.list:
        print("%s: %d payloads, %d iterations" % (a.manifest, len(man.get("items", [])), iters))
        for name in slots:
            print("  slot:", name)
        return

    if not (a.add or a.drop or a.only):
        sys.exit("nothing to do: pass --list, --add, --drop or --only")
    if not a.current:
        sys.exit("--open needs a password that currently works, to recover the data key")

    opened, data_key = unwrap(man, a.current)
    if data_key is None:
        sys.exit("that password does not open this vault, so the data key cannot be recovered")
    print("opened via slot:", opened)

    def split(pair):
        if "=" not in pair:
            sys.exit("expected NAME=PASSWORD, got: " + pair)
        return pair.split("=", 1)

    written = {}
    if a.only:
        slots.clear()
        for name, pw in map(split, a.only):
            slots[name] = wrap(data_key, pw, iters)
            written[name] = pw
            print("  set   ", name)
    for name, pw in map(split, a.add):
        slots[name] = wrap(data_key, pw, iters)
        written[name] = pw
        print("  added ", name)
    for name in a.drop:
        if slots.pop(name, None) is None:
            print("  (no slot called %s)" % name)
        else:
            print("  dropped", name)

    if not slots:
        sys.exit("refusing to leave the vault with no way in")

    # every slot written in this run must hand back the same data key, or the
    # manifest is not touched at all
    for name, pw in written.items():
        _, got = unwrap({"iterations": iters, "slots": {name: slots[name]}}, pw)
        if got != data_key:
            sys.exit("slot %s did not round-trip - nothing written" % name)
    print("  verified", len(written), "new slot(s)")

    man["slots"] = slots
    with open(a.manifest, "w") as fh:
        json.dump(man, fh, separators=(",", ":"))
    print("%s now opens with: %s" % (a.manifest, ", ".join(slots)))


if __name__ == "__main__":
    main()
