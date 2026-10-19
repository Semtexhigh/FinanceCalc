#!/usr/bin/env python3
"""Stop the desktop app calling itself a browser, and say what is actually wrong.

In the shell the page has no browser chrome around it, so "This browser can't
reach a camera" is both wrong and unhelpful: it reads as though the user picked
the wrong browser, when the truth is the app had not asked macOS for the camera.
Every host-dependent message now asks what it is running inside first.

Run:  python3 0001_host_wording.py <path-to-app.html>
"""
import sys

p = sys.argv[1]
s = open(p, encoding="utf-8").read()
orig = s


def swap(old, new, count=1):
    global s
    got = s.count(old)
    if got != count:
        raise SystemExit("0001: expected %d of %r, found %d" % (count, old[:60], got))
    s = s.replace(old, new)


# ---- the helper itself, next to the camera switch it is first used by ----
anchor = '  var CAM_KEY="mymoney_cam_off";\n'
helper = '''  /* What are we running inside? The shell gives the page its own origin and
     no browser around it, so every message that says "browser" is wrong there
     - and the fix for the user is different too: in the app the camera is a
     macOS permission, in a browser it is a site permission. */
  function isDesktopApp(){
    try{ return !!(window.__TAURI__ && window.__TAURI__.core); }catch(e){ return false; }
  }
  function hostWord(){ return isDesktopApp() ? "the app" : "this browser"; }
  function hostWordCap(){ return isDesktopApp() ? "The app" : "This browser"; }

'''
swap(anchor, helper + anchor)

# ---- 1. no getUserMedia at all ----
swap(
    '      return Promise.resolve({ok:false, why:"This browser can\'t reach a camera."});',
    '      return Promise.resolve({ok:false, noApi:true, why: isDesktopApp()\n'
    '        ? "The app hasn\'t been given access to the camera. macOS grants it the first time the app asks — if you said No, turn FinanceCalc back on under System Settings › Privacy & Security › Camera."\n'
    '        : "This browser can\'t reach a camera."});',
)

# ---- 2. insecure context ----
swap(
    '      return Promise.resolve({ok:false, why:"Camera access needs https. Opened straight from disk (file://) the browser blocks it."});',
    '      return Promise.resolve({ok:false, why: hostWordCap()+" blocks the camera here because the page isn\'t on a secure origin. Opened straight from disk (file://) that is expected — use the installed app or the website."});',
)

# ---- 3. framed ----
swap(
    '      return Promise.resolve({ok:false, why:"The camera is blocked inside a frame. Open this in its own tab to use face unlock."});',
    '      return Promise.resolve({ok:false, why: isDesktopApp()\n'
    '        ? "The camera is blocked inside an embedded frame."\n'
    '        : "The camera is blocked inside a frame. Open this in its own tab to use face unlock."});',
)

# ---- 4. the modal title: "can't run here" reads terminal when a photo still works ----
swap(
    '        appModal({title:"Face unlock can\'t run here", investigate:true,',
    '        appModal({title: canPhoto ? "Set up face unlock from a photo" : "Face unlock can\'t run here", investigate:true,',
)

# ---- 5. the lock-screen status line ----
swap(
    '      setStatus && setStatus("Face unlock needs the app in its own tab");',
    '      setStatus && setStatus(isDesktopApp() ? "Face unlock can\'t run in an embedded frame" : "Face unlock needs the app in its own tab");',
)

# ---- 6. the iCloud hint also says "browser" inside the shell ----
swap(
    "<b>This browser can’t write to iCloud Drive by itself</b> (only Chrome or Edge on a computer can).",
    "<b>'+(isDesktopApp()?\"The app can’t write to iCloud Drive by itself\":\"This browser can’t write to iCloud Drive by itself\")+'</b>"
    " '+(isDesktopApp()?'(pick a folder inside iCloud Drive instead).':'(only Chrome or Edge on a computer can).')+'",
)

open(p, "w", encoding="utf-8").write(s)
print("0001: host wording applied (%d -> %d bytes)" % (len(orig.encode()), len(s.encode())))
