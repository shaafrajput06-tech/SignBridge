// The offline helper answers from SignBridge's own data and never invents a sign.
import test from "node:test";
import assert from "node:assert/strict";
import { answer } from "../src/helper.js";

const data = {
  dictionary: [{ label: "doctor.physician", url: "https://example.org/doctor.mp4" }, { label: "water", url: "https://example.org/water.mp4", file: "clips/psl/water.mp4" }],
  vocabulary: [{ id: "doctor", english: "Doctor", urdu: "ڈاکٹر", romanUrdu: "Doctor" }],
  pslClasses: [{ english: "Hello", tier: "B" }, { english: "Water", tier: "B" }, { english: "Not a sign", tier: null }],
};

test("a word with a dictionary video gets the video, labelled not validated", () => {
  const reply = answer("How do I sign doctor?", data);
  assert.equal(reply.video, "https://example.org/doctor.mp4");
  assert.match(reply.text, /not yet validated/);
  assert.match(answer("ڈاکٹر", data).text, /doctor|ڈاکٹر/i);
});

test("no video means a plain no, never a description", () => {
  const reply = answer("how do i sign elephant", data);
  assert.equal(reply.video, undefined);
  assert.match(reply.text, /no licensed PSL video/);
  const camera = answer("sign for hello", data);
  assert.match(camera.text, /camera can suggest/);
  assert.equal(camera.video, undefined);
});

test("questions about the camera, privacy and offline use", () => {
  assert.match(answer("which signs does the camera know?", data).text, /2 signs/);
  assert.match(answer("is my video recorded?", data).text, /stays on your device/);
  assert.match(answer("does it work offline", data).text, /offline/);
});
