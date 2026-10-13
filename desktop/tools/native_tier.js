  /* ---- Tier 0: the desktop shell's own filesystem. Only exists inside the macOS
     app. WebKit has no showDirectoryPicker, so the browser folder tier below can
     never work there — this replaces it by asking the Rust shell to do the file I/O.
     The folder is chosen once through a native dialog and remembered permanently:
     no per-session re-grant, because that limitation is the browser's, not the
     operating system's. Same layout on disk as the browser folder tier, so a folder
     written by Chrome and one written by the app are interchangeable. ---- */
  var TierTauri = {
    name:"native", priority:0, _folder:null, _lastMod:null, _baseStamp:null, _force:false,
    CORE:"my-money-data/core.json", PHOTOS:"my-money-data/photos",
    isDesktop:function(){
      try{ var t=window.__TAURI__; return !!(t && t.core && typeof t.core.invoke==="function"); }
      catch(e){ return false; }
    },
    _invoke:function(cmd,args){
      if(!this.isDesktop()) return Promise.reject(new Error("not running in the desktop app"));
      return window.__TAURI__.core.invoke(cmd, args||{});
    },
    async available(){
      if(!this.isDesktop()) return false;
      if(this._folder) return true;
      try{ this._folder=await this._invoke("fc_folder"); }catch(e){ this._folder=null; }
      return !!this._folder;
    },
    folderName(){ return (this._folder && this._folder.name) || "your folder"; },
    folderPath(){ return (this._folder && this._folder.path) || ""; },
    // No user-gesture requirement here — that is a browser rule, not an OS one.
    async pickFolder(){
      var f=await this._invoke("fc_pick_folder");
      if(!f) return null;                      // user cancelled the dialog
      this._folder=f; this._lastMod=null; this._baseStamp=null;
      return f;
    },
    async forgetFolder(){
      try{ await this._invoke("fc_forget_folder"); }catch(e){}
      this._folder=null; this._lastMod=null; this._baseStamp=null;
    },
    async read(){
      try{
        if(!(await this.available())) return null;
        var txt=await this._invoke("fc_read_text",{rel:this.CORE});
        if(txt==null) return null;
        var core=JSON.parse(txt);
        var st=null; try{ st=await this._invoke("fc_stat",{rel:this.CORE}); }catch(e){}
        var sy=0; try{ sy=+localStorage.getItem("mymoney_folder_synced")||0; }catch(e){}
        this._baseStamp = sy || ((core&&core.savedAt)||0);
        this._lastMod = st ? st.mtime : null;
        return {core:core, photoIds:await this.listPhotos()};
      }catch(e){ return null; }
    },
    async write(core){
      var force=this._force;
      if(!(await this.available())){
        this._force=false;
        var ne=new Error("No folder selected"); ne.needsFolder=true; throw ne;
      }
      if(!force){
        // iCloud may have pulled down a newer copy from another device since this one
        // last touched the file. Never overwrite that: keep ours in history and ask.
        try{
          var st=await this._invoke("fc_stat",{rel:this.CORE});
          if(st && st.size && this._lastMod!=null && st.mtime!==this._lastMod){
            var txt=await this._invoke("fc_read_text",{rel:this.CORE});
            var cur=txt?JSON.parse(txt):null, cs=(cur&&cur.savedAt)||0;
            if(cs!==core.savedAt && cs>(this._baseStamp||0)){
              try{ await SaveHistory.toFolder(JSON.stringify(core),"not-written-conflict"); }catch(e){}
              if(typeof StorageManager.onFolderConflict==="function") StorageManager.onFolderConflict(cur);
              var ce=new Error("The folder has newer changes from another device"); ce.conflict=true; throw ce;
            }
          }
        }catch(e){ if(e && e.conflict) throw e; }
      }
      this._force=false;
      var mt=await this._invoke("fc_write_text",{rel:this.CORE, contents:JSON.stringify(core)});
      this._lastMod=mt||null;
      this._baseStamp=core.savedAt||Date.now();
      try{ localStorage.setItem("mymoney_folder_synced", String(this._baseStamp)); }catch(e){}
    },
    async readPhoto(id,ext){
      try{
        var b64=await this._invoke("fc_read_bytes",{rel:this.PHOTOS+"/"+id+"."+ext});
        if(b64==null) return null;
        var bin=atob(b64), n=bin.length, arr=new Uint8Array(n);
        for(var i=0;i<n;i++) arr[i]=bin.charCodeAt(i);
        return new Blob([arr]);
      }catch(e){ return null; }
    },
    async writePhoto(id,ext,blob){
      var buf=await blob.arrayBuffer(), arr=new Uint8Array(buf), s="";
      // chunked so a large screenshot cannot blow the argument limit of apply()
      for(var i=0;i<arr.length;i+=0x8000) s+=String.fromCharCode.apply(null,arr.subarray(i,i+0x8000));
      await this._invoke("fc_write_bytes",{rel:this.PHOTOS+"/"+id+"."+ext, b64:btoa(s)});
    },
    async deletePhoto(id,ext){
      try{ await this._invoke("fc_remove",{rel:this.PHOTOS+"/"+id+"."+ext}); }catch(e){}
    },
    async listPhotos(){
      try{ return (await this._invoke("fc_list",{rel:this.PHOTOS}))||[]; }catch(e){ return []; }
    },
    async health(){
      try{
        if(!this.isDesktop()) return {ok:false, space:0, detail:"Desktop app only"};
        if(!(await this.available())) return {ok:false, space:0, detail:"No folder selected", needsFolder:true};
        return {ok:true, space:null, detail:"Connected: "+this.folderName()};
      }catch(e){ return {ok:false, space:0, detail:String((e&&e.message)||e)}; }
    }
  };

