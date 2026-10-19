#!/usr/bin/env python3
"""A denied camera looks identical to no camera, so say both.

macOS answers enumerateDevices with an empty list when permission has been
refused, so "No camera found on this device" was shown to people who do have a
camera and had simply said No once. In the app that is the likeliest reason, so
the message points at the setting that fixes it.

Run:  python3 0003_no_camera_found.py <path-to-app.html>
"""
import sys

p = sys.argv[1]
s = open(p, encoding="utf-8").read()
old = '        : {ok:false, why:"No camera found on this device."};'
new = ('        : {ok:false, why: isDesktopApp()\n'
       '            ? "No camera is available. If this Mac has one, FinanceCalc may have been refused it — check System Settings › Privacy & Security › Camera."\n'
       '            : "No camera found on this device."};')
if s.count(old) != 1:
    raise SystemExit("0003: anchor not found exactly once (%d)" % s.count(old))
open(p, "w", encoding="utf-8").write(s.replace(old, new))
print("0003: no-camera message now names the likely cause")
