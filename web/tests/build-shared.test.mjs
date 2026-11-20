// npm run build:shared packages the offline shared copy. Here: package a tiny made-up site with
// --from and check the zip (names, contents, launcher files) without building the real website.
// (Packaging the frozen baseline site gives the baseline's own 66-file list; see reports/v3_stage0_baseline.md.)
import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { inflateRawSync } from "node:zlib";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { REQUIRED, zipFiles } from "../scripts/build-shared.mjs";

const web = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function readZip(buffer) {
  const end = buffer.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  const count = buffer.readUInt16LE(end + 10);
  let at = buffer.readUInt32LE(end + 16);
  const files = new Map();
  for (let i = 0; i < count; i += 1) {
    assert.equal(buffer.readUInt32LE(at), 0x02014b50);
    const method = buffer.readUInt16LE(at + 10);
    const size = buffer.readUInt32LE(at + 20);
    const nameLength = buffer.readUInt16LE(at + 28);
    const extraLength = buffer.readUInt16LE(at + 30);
    const commentLength = buffer.readUInt16LE(at + 32);
    const local = buffer.readUInt32LE(at + 42);
    const name = buffer.subarray(at + 46, at + 46 + nameLength).toString("utf8");
    const dataStart = local + 30 + buffer.readUInt16LE(local + 26) + buffer.readUInt16LE(local + 28);
    const body = buffer.subarray(dataStart, dataStart + size);
    files.set(name, method === 8 ? inflateRawSync(body) : Buffer.from(body));
    at += 46 + nameLength + extraLength + commentLength;
  }
  return files;
}

test("zipFiles writes a standard zip that reads back byte for byte", () => {
  const entries = [{ name: "a.txt", data: Buffer.from("hello hello hello hello") }, { name: "dir/ü.bin", data: Buffer.from([0, 1, 2, 3]) }];
  const files = readZip(zipFiles(entries));
  assert.deepEqual([...files.keys()], ["a.txt", "dir/ü.bin"]);
  assert.equal(files.get("a.txt").toString(), "hello hello hello hello");
  assert.deepEqual([...files.get("dir/ü.bin")], [0, 1, 2, 3]);
});

test("build:shared --from packages a site with the Windows launcher, and leaves CI results out", () => {
  const root = mkdtempSync(path.join(tmpdir(), "signbridge-shared-"));
  const site = path.join(root, "site");
  for (const relative of [...REQUIRED, "assets/app.js", "ci/status.json"]) {
    mkdirSync(path.dirname(path.join(site, relative)), { recursive: true });
    writeFileSync(path.join(site, relative), `file ${relative}`);
  }
  const out = path.join(root, "out");
  execFileSync(process.execPath, [path.join(web, "scripts", "build-shared.mjs"), "--from", site, "--out", out], { stdio: "pipe" });
  const files = readZip(readFileSync(path.join(out, "SignBridge-shared-copy.zip")));
  for (const name of ["SignBridge/Start SignBridge.bat", "SignBridge/serve.ps1", "SignBridge/README.txt", "SignBridge/site/index.html", "SignBridge/site/assets/app.js", "SignBridge/site/models/asl/model.tflite"]) {
    assert.ok(files.has(name), name);
  }
  assert.ok(![...files.keys()].some((name) => name.includes("/ci/")), "CI results are not shipped");
  assert.match(files.get("SignBridge/Start SignBridge.bat").toString(), /serve\.ps1/);
  assert.ok(files.get("SignBridge/Start SignBridge.bat").includes(Buffer.from("\r\n")), "the .bat keeps Windows line endings");
});

test("build:shared refuses a site without the models", () => {
  const root = mkdtempSync(path.join(tmpdir(), "signbridge-shared-"));
  mkdirSync(path.join(root, "site"), { recursive: true });
  writeFileSync(path.join(root, "site", "index.html"), "<!doctype html>");
  assert.throws(() => execFileSync(process.execPath, [path.join(web, "scripts", "build-shared.mjs"), "--from", path.join(root, "site"), "--out", path.join(root, "out")], { stdio: "pipe" }), /missing files/);
});
