// The LiteRT.js glue inside the ASL worker must load its .wasm from the runtime folder (litert/),
// not from next to the worker script (assets/). Ported from Inference Baseline v1 (see wasm_locate.js).
import test from "node:test";
import assert from "node:assert/strict";
import { pointWasmAtRuntimeFolder } from "../src/wasm_locate.js";

const WORKER = "https://signbridge-pk.github.io/assets/asl_worker-abc.js";

function workerScope(href = WORKER) {
  return { WorkerGlobalScope: function WorkerGlobalScope() {}, location: { href } };
}

test("in a worker, every runtime file resolves inside the runtime folder", () => {
  const scope = workerScope();
  assert.equal(pointWasmAtRuntimeFolder("https://signbridge-pk.github.io/litert/", scope), true);
  assert.equal(scope.Module.locateFile("litert_wasm_internal.wasm"), "https://signbridge-pk.github.io/litert/litert_wasm_internal.wasm");
  assert.equal(scope.Module.locateFile("litert_wasm_threaded_internal.wasm"), "https://signbridge-pk.github.io/litert/litert_wasm_threaded_internal.wasm");
});

test("works under a sub-path and with a folder given without the final slash", () => {
  const scope = workerScope("https://u.github.io/SignBridge/assets/asl_worker-abc.js");
  pointWasmAtRuntimeFolder("https://u.github.io/SignBridge/litert", scope);
  assert.equal(scope.Module.locateFile("x.wasm"), "https://u.github.io/SignBridge/litert/x.wasm");
});

test("does nothing on the page or when Module is already set", () => {
  const page = { location: { href: "https://signbridge-pk.github.io/" } };
  assert.equal(pointWasmAtRuntimeFolder("litert/", page), false);
  assert.equal(page.Module, undefined);
  const existing = { locateFile: () => "keep" };
  const scope = { ...workerScope(), Module: existing };
  assert.equal(pointWasmAtRuntimeFolder("litert/", scope), false);
  assert.equal(scope.Module, existing);
});
