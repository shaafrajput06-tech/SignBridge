// importScripts() for the ASL module worker.
//
// Why: LiteRT.js loads its WebAssembly glue with importScripts() when it runs inside a worker. The ASL
// worker is a module worker (it uses `import`, which Vite bundles), and module workers throw on
// importScripts(). The first GitHub Actions run measured exactly that ("Module scripts don't support
// importScripts()"), so the model fell back to the page thread, where it can make the camera view stutter.
//
// What: inside the worker only, importScripts(url) is replaced by what it does in a classic worker:
// fetch the script synchronously and run it in the worker's global scope. It is limited to files on the
// page's own origin under one folder (the bundled LiteRT runtime, public/litert/), so it can never run
// code from another site. It does nothing in a classic worker, where importScripts already works.

export function moduleWorkerBlocksImportScripts(scope = globalThis) {
  if (typeof scope.importScripts !== "function") return false;
  try {
    scope.importScripts(); // no URLs: a no-op in a classic worker, a TypeError in a module worker
    return false;
  } catch {
    return true;
  }
}

// allowedPrefix: absolute URL of the only folder scripts may come from (must end with "/").
// Returns true when the shim was installed.
export function installImportScriptsShim({ scope = globalThis, allowedPrefix, Request = scope.XMLHttpRequest, run = (code) => (0, eval)(code) } = {}) {
  if (!moduleWorkerBlocksImportScripts(scope)) return false;
  if (typeof Request !== "function") return false;
  const base = scope.location?.href;
  const prefix = new URL(allowedPrefix, base).href;
  if (!prefix.endsWith("/")) throw new Error("allowedPrefix must be a folder URL ending with /");
  const origin = new URL(base).origin;
  scope.importScripts = (...urls) => {
    for (const url of urls) {
      const absolute = new URL(String(url), base);
      if (absolute.origin !== origin || !absolute.href.startsWith(prefix)) {
        throw new Error(`importScripts refused ${absolute.href}: only the bundled LiteRT runtime (${prefix}) may be loaded`);
      }
      const request = new Request();
      request.open("GET", absolute.href, false); // synchronous, as importScripts is; allowed in workers
      request.send(null);
      if (request.status !== 200) throw new Error(`importScripts could not load ${absolute.href} (HTTP ${request.status})`);
      run(`${request.responseText}\n//# sourceURL=${absolute.href}`);
    }
  };
  return true;
}
