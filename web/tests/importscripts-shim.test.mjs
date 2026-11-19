// The ASL worker's importScripts() replacement (src/importscripts_shim.js), with a stand-in worker scope.
import test from "node:test";
import assert from "node:assert/strict";
import { installImportScriptsShim, moduleWorkerBlocksImportScripts } from "../src/importscripts_shim.js";

const PAGE = "https://example.github.io/SignBridge/assets/asl_worker-abc.js";
const RUNTIME = "https://example.github.io/SignBridge/litert/";

function moduleWorkerScope() {
  return {
    location: { href: PAGE },
    importScripts() { throw new TypeError("Module scripts don't support importScripts()."); },
  };
}

function fakeRequestClass(files, log) {
  return class {
    open(method, url, async) { this.url = url; log.push({ method, url, async }); }
    send() {
      if (this.url in files) { this.status = 200; this.responseText = files[this.url]; } else { this.status = 404; this.responseText = ""; }
    }
  };
}

test("module worker detection", () => {
  assert.equal(moduleWorkerBlocksImportScripts(moduleWorkerScope()), true);
  assert.equal(moduleWorkerBlocksImportScripts({ importScripts() {} }), false, "classic worker: no-op");
  assert.equal(moduleWorkerBlocksImportScripts({}), false, "page: no importScripts at all");
});

test("loads same-origin runtime files synchronously and runs them in order", () => {
  const scope = moduleWorkerScope();
  const log = [];
  const ran = [];
  const files = { [`${RUNTIME}litert_wasm_internal.js`]: "var A = 1;", [`${RUNTIME}extra.js`]: "var B = 2;" };
  const installed = installImportScriptsShim({ scope, allowedPrefix: RUNTIME, Request: fakeRequestClass(files, log), run: (code) => ran.push(code) });
  assert.equal(installed, true);
  scope.importScripts("../litert/litert_wasm_internal.js", `${RUNTIME}extra.js`);
  assert.deepEqual(log.map((entry) => [entry.method, entry.url, entry.async]), [
    ["GET", `${RUNTIME}litert_wasm_internal.js`, false],
    ["GET", `${RUNTIME}extra.js`, false],
  ]);
  assert.equal(ran.length, 2);
  assert.ok(ran[0].startsWith("var A = 1;"));
  assert.ok(ran[0].endsWith(`//# sourceURL=${RUNTIME}litert_wasm_internal.js`));
});

test("refuses other sites, other folders and missing files", () => {
  const scope = moduleWorkerScope();
  const ran = [];
  installImportScriptsShim({ scope, allowedPrefix: RUNTIME, Request: fakeRequestClass({}, []), run: (code) => ran.push(code) });
  assert.throws(() => scope.importScripts("https://cdn.jsdelivr.net/npm/@litertjs/core/wasm/x.js"), /refused/);
  assert.throws(() => scope.importScripts("https://example.github.io/SignBridge/assets/other.js"), /refused/);
  assert.throws(() => scope.importScripts("https://example.github.io/SignBridgeEvil/litert/x.js"), /refused/);
  assert.throws(() => scope.importScripts(`${RUNTIME}missing.js`), /HTTP 404/);
  assert.equal(ran.length, 0);
});

test("leaves classic workers and pages alone", () => {
  const classic = { location: { href: PAGE }, importScripts() {} };
  const original = classic.importScripts;
  assert.equal(installImportScriptsShim({ scope: classic, allowedPrefix: RUNTIME, Request: fakeRequestClass({}, []) }), false);
  assert.equal(classic.importScripts, original);
  assert.equal(installImportScriptsShim({ scope: { location: { href: PAGE } }, allowedPrefix: RUNTIME, Request: fakeRequestClass({}, []) }), false);
});

test("the runtime folder must be a folder", () => {
  assert.throws(() => installImportScriptsShim({ scope: moduleWorkerScope(), allowedPrefix: `${RUNTIME}litert.js`, Request: fakeRequestClass({}, []) }), /folder/);
});

test("default runner evaluates in the global scope, like importScripts", () => {
  const scope = moduleWorkerScope();
  const name = `__shimTest${Date.now()}`;
  installImportScriptsShim({ scope, allowedPrefix: RUNTIME, Request: fakeRequestClass({ [`${RUNTIME}g.js`]: `var ${name} = 42;` }, []) });
  scope.importScripts(`${RUNTIME}g.js`);
  assert.equal(globalThis[name], 42);
  delete globalThis[name];
});
