/* FinanceCalc service worker - tombstone.

   The in-browser build is gone; the app ships as a macOS .dmg now. An older
   root-scoped worker is still registered in any browser that opened the web
   version, so deleting this file would leave it serving a cached copy of a
   site that no longer exists. This replacement unregisters it, drops its
   caches and reloads the page once onto the live site. */
self.addEventListener("install", function(){ self.skipWaiting(); });
self.addEventListener("activate", function(e){
  e.waitUntil((async function(){
    try { for (const k of await caches.keys()) await caches.delete(k); } catch (err) {}
    try { await self.registration.unregister(); } catch (err) {}
    try { for (const c of await self.clients.matchAll({type:"window"})) c.navigate(c.url); } catch (err) {}
  })());
});
