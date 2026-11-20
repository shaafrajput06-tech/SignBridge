// Tells LiteRT.js's WebAssembly glue where its .wasm files are, when it runs inside a worker.
//
// Why: inside the ASL module worker, the glue script is loaded through the importScripts shim
// (importscripts_shim.js). Emscripten glue then looks for its .wasm next to the *worker script*
// (assets/), not in the LiteRT runtime folder (litert/). The server answers that wrong address with
// the HTML page, and compiling fails with "expected magic word 00 61 73 6d, found 3c 21 64 6f" (that is
// "<!do..." of "<!doctype html>"). The GitHub Actions run of 2026-11-19 measured exactly this, so the
// model fell back to the page thread. The frozen Inference Baseline v1 build (baseline/v1-site) already
// had this fix (asl_worker bundle, function $t); it is ported here from that build.
//
// What: in a worker, before the runtime loads, set self.Module = { locateFile } so every file the glue
// asks for is resolved inside the runtime folder. Does nothing on the page (document-relative URLs
// work there) or when a Module object is already set up.

export function pointWasmAtRuntimeFolder(wasmPath, scope = globalThis) {
  if (scope.WorkerGlobalScope === undefined || scope.Module) return false;
  const folder = new URL(wasmPath.endsWith("/") ? wasmPath : `${wasmPath}/`, scope.location.href);
  scope.Module = { locateFile: (file) => new URL(file, folder).href };
  return true;
}
