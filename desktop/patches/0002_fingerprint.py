#!/usr/bin/env python3
"""Fingerprint / Touch ID unlock, beside the PIN and face unlock.

Two ways in, picked at runtime:
  · In the desktop app, the Rust side asks macOS directly (LocalAuthentication),
    which is the real Touch ID prompt.
  · In a browser, a WebAuthn platform authenticator does the same job.

It is a gate, exactly like the PIN: the vault is not keyed to it, and the PIN
is always still there underneath. The row never appears on a machine with no
sensor, so nobody is offered an unlock they cannot use.

Run:  python3 0002_fingerprint.py <path-to-app.html>
"""
import sys

p = sys.argv[1]
s = open(p, encoding="utf-8").read()
orig = s


def swap(old, new, count=1):
    global s
    got = s.count(old)
    if got != count:
        raise SystemExit("0002: expected %d of %r, found %d" % (count, old[:70], got))
    s = s.replace(old, new)


# ------------------------------------------------------------------ module
anchor = '  /* ---- 1. is there a camera at all? ---- */\n'
module = r'''  /* ============================================================
     FINGERPRINT / TOUCH ID

     A second way past the lock screen, sitting on the PIN the same way
     face unlock does. Nothing is encrypted with it: it proves the person
     at the machine is the owner, and the PIN remains the fallback.

     Desktop app  -> fc_touchid, a Rust command that calls macOS
                     LocalAuthentication. That is the system prompt.
     Browser      -> WebAuthn with a platform authenticator, which on a Mac
                     is the same Touch ID sensor.

     If neither is available the row is not shown at all.
     ============================================================ */
  var BIO_KEY="mymoney_bio_v1";
  var bioCfg={ on:false, cred:"", kind:"" };
  function loadBio(){
    try{ var r=localStorage.getItem(BIO_KEY); if(r) bioCfg=Object.assign(bioCfg, JSON.parse(r)); }catch(e){}
  }
  function saveBio(){ try{ localStorage.setItem(BIO_KEY, JSON.stringify(bioCfg)); }catch(e){} }
  loadBio();

  var AUTOBIO_KEY="mymoney_autobio";
  function autoBioOn(){ try{ return localStorage.getItem(AUTOBIO_KEY)!=="0"; }catch(e){ return true; } }
  function setAutoBio(on){
    try{ on ? localStorage.removeItem(AUTOBIO_KEY) : localStorage.setItem(AUTOBIO_KEY,"0"); }catch(e){}
  }

  function bioNative(){
    try{ return isDesktopApp() && window.__TAURI__.core && typeof window.__TAURI__.core.invoke==="function"; }
    catch(e){ return false; }
  }
  /* Is there a sensor? Answered once and remembered for the session, because
     both routes are a real system call and the settings screen asks often. */
  var _bioAvail=null;
  function bioAvailable(){
    if(_bioAvail) return _bioAvail;
    _bioAvail = new Promise(function(res){
      if(bioNative()){
        window.__TAURI__.core.invoke("fc_touchid_available")
          .then(function(ok){ res(!!ok); })
          .catch(function(){ res(false); });
        return;
      }
      if(!(window.PublicKeyCredential &&
           PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable)){ res(false); return; }
      PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable()
        .then(function(ok){ res(!!ok); })
        .catch(function(){ res(false); });
    });
    return _bioAvail;
  }
  function bioLabel(){ return isApple&&isApple() ? "Touch ID" : "Fingerprint"; }

  function _b64(buf){
    var b=new Uint8Array(buf), out="";
    for(var i=0;i<b.length;i++) out+=String.fromCharCode(b[i]);
    return btoa(out);
  }
  function _unb64(str){
    var raw=atob(str), out=new Uint8Array(raw.length);
    for(var i=0;i<raw.length;i++) out[i]=raw.charCodeAt(i);
    return out;
  }
  function _chal(){
    var a=new Uint8Array(32);
    (window.crypto||{}).getRandomValues ? crypto.getRandomValues(a)
      : a.forEach(function(_,i){ a[i]=Math.floor(Math.random()*256); });
    return a;
  }

  /* Enrol. Resolves true when the device has bound a credential to this app. */
  function bioEnrol(){
    return bioAvailable().then(function(ok){
      if(!ok) return false;
      if(bioNative()){
        return window.__TAURI__.core.invoke("fc_touchid", {reason:"set up "+bioLabel()+" for FinanceCalc"})
          .then(function(ok2){
            if(!ok2) return false;
            bioCfg.on=true; bioCfg.kind="native"; bioCfg.cred=""; saveBio();
            return true;
          }).catch(function(){ return false; });
      }
      var id=new Uint8Array(16); crypto.getRandomValues(id);
      return navigator.credentials.create({publicKey:{
        challenge:_chal(),
        rp:{name:"FinanceCalc"},
        user:{id:id, name:"my-money", displayName:"My Money"},
        pubKeyCredParams:[{type:"public-key",alg:-7},{type:"public-key",alg:-257}],
        authenticatorSelection:{authenticatorAttachment:"platform", userVerification:"required", residentKey:"preferred"},
        timeout:60000, attestation:"none"
      }}).then(function(c){
        if(!c) return false;
        bioCfg.on=true; bioCfg.kind="webauthn"; bioCfg.cred=_b64(c.rawId); saveBio();
        return true;
      }).catch(function(){ return false; });
    });
  }

  /* Ask. Resolves true only on a real success - never on a cancel or error,
     so a refusal silently leaves the PIN pad exactly where it was. */
  function bioVerify(){
    if(!bioCfg.on) return Promise.resolve(false);
    if(bioCfg.kind==="native" || bioNative()){
      return window.__TAURI__.core.invoke("fc_touchid", {reason:"unlock FinanceCalc"})
        .then(function(ok){ return !!ok; }).catch(function(){ return false; });
    }
    if(!(window.PublicKeyCredential && navigator.credentials)) return Promise.resolve(false);
    var allow=[];
    if(bioCfg.cred) allow.push({type:"public-key", id:_unb64(bioCfg.cred), transports:["internal"]});
    return navigator.credentials.get({publicKey:{
      challenge:_chal(), allowCredentials:allow, userVerification:"required", timeout:60000
    }}).then(function(a){ return !!a; }).catch(function(){ return false; });
  }
  function bioDisable(){ bioCfg.on=false; bioCfg.cred=""; bioCfg.kind=""; saveBio(); }

'''
swap(anchor, module + anchor)

# ------------------------------------------------- lock screen: ask on open
swap(
    '    startAutoFace(ov, unlock, faceSay);\n',
    '    startAutoFace(ov, unlock, faceSay);\n'
    '\n'
    '    /* Fingerprint sits on its own line under the face line. It asks once\n'
    '       when the screen opens, and after that only when tapped - a prompt\n'
    '       that reappears on its own is a prompt people learn to dismiss. */\n'
    '    if(bioCfg.on){\n'
    '      var bioLine=document.createElement("button");\n'
    '      bioLine.type="button"; bioLine.className="kp-link"; bioLine.id="lkBio";\n'
    '      bioLine.textContent="Unlock with "+bioLabel();\n'
    '      ov.querySelector(".lk-box").appendChild(bioLine);\n'
    '      var asking=false;\n'
    '      var askBio=function(){\n'
    '        if(asking || !document.getElementById("lockScreen")) return;\n'
    '        asking=true; bioLine.disabled=true;\n'
    '        bioVerify().then(function(ok){\n'
    '          asking=false; bioLine.disabled=false;\n'
    '          if(!document.getElementById("lockScreen")) return;\n'
    '          if(ok){ unlock(); return; }\n'
    '          recordFailedAttempt && recordFailedAttempt("bio");\n'
    '          bioLine.textContent="Try "+bioLabel()+" again";\n'
    '        });\n'
    '      };\n'
    '      bioLine.addEventListener("click", askBio);\n'
    '      if(autoBioOn()) setTimeout(askBio, 260);\n'
    '    }\n',
)

# ------------------------------------------------------- settings: the row
swap(
    '''    <div class="sec-item">
      <div class="si-main"><div class="si-t">Unlock automatically</div>''',
    '''    <div class="sec-item" id="bioRow" style="display:none">
      <div class="si-main"><div class="si-t" id="bioRowT">Fingerprint</div>
        <div class="si-d" id="bioFpNote">Unlock with the sensor on this machine. Your PIN still works.</div></div>
      <button type="button" class="btn ghost sm" id="bioFpBtn">Set up</button>
    </div>
    <div class="sec-item">
      <div class="si-main"><div class="si-t">Unlock automatically</div>''',
)

# --------------------------------------------------- settings: the wiring
swap(
    '    var faceBtn=document.getElementById("faceBtn");\n',
    '''    var bioFpBtn=document.getElementById("bioFpBtn");
    if(bioFpBtn && !bioFpBtn._bound){
      bioFpBtn._bound=true;
      bioFpBtn.addEventListener("click", function(){
        if(!lockIsOn()){
          appModal({title:"Set a PIN first",
            message:bioLabel()+" sits on top of the PIN \\u2014 the PIN is the fallback whenever the sensor can't read you.",
            confirmText:"OK"});
          return;
        }
        if(bioCfg.on){
          appModal({title:"Remove "+bioLabel()+"?", message:"You'll unlock with your PIN only.",
            confirmText:"Remove", cancelText:"Keep",
            onConfirm:function(){ bioDisable(); refreshSecUI(); flashSaved(bioLabel()+" removed"); }});
          return;
        }
        bioFpBtn.disabled=true;
        bioEnrol().then(function(ok){
          bioFpBtn.disabled=false;
          if(ok){ refreshSecUI(); flashSaved(bioLabel()+" on"); }
          else appModal({title:bioLabel()+" wasn't set up",
            message:"The sensor didn't confirm it was you, or the request was cancelled. Nothing has changed.",
            confirmText:"OK"});
        });
      });
    }
    var faceBtn=document.getElementById("faceBtn");
''',
)

swap(
    '    var fb=document.getElementById("faceBtn");\n',
    '''    var bioRow=document.getElementById("bioRow");
    if(bioRow) bioAvailable().then(function(has){
      /* No sensor, no row: an unlock you cannot use is worse than no offer. */
      bioRow.style.display = has ? "" : "none";
      if(!has) return;
      var t=document.getElementById("bioRowT");
      var n=document.getElementById("bioFpNote");
      var b=document.getElementById("bioFpBtn");
      if(t) t.textContent=bioLabel();
      if(b) b.textContent = bioCfg.on ? "Remove" : "Set up";
      if(n){
        n.textContent = !lockIsOn()
          ? "Set a PIN first \\u2014 " + bioLabel() + " sits on top of it."
          : bioCfg.on
            ? "On \\u2014 " + bioLabel() + " unlocks the app. Your PIN still works."
            : "Unlock with the sensor on this machine. Your PIN still works.";
        n.style.color = bioCfg.on ? "var(--up)" : "";
      }
    });
    var fb=document.getElementById("faceBtn");
''',
)

open(p, "w", encoding="utf-8").write(s)
print("0002: fingerprint unlock added (%d -> %d bytes)" % (len(orig.encode()), len(s.encode())))
