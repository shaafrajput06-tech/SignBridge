import test from "node:test";
import assert from "node:assert/strict";
import { cameraAdvice, createCameraCheck } from "../src/camera_check.js";

const hand = (height) => Array.from({ length: 21 }, (_, i) => [0.5, 0.4 + (height * i) / 20, 0]);

test("good light, face in view and a normal hand size: all fine", () => {
  const check = createCameraCheck({ frames: 10 });
  for (let i = 0; i < 12; i += 1) check.add({ face: [[0, 0, 0]], pose: [[0, 0, 0]], left_hand: null, right_hand: hand(0.2) }, 0.5);
  assert.equal(check.done, true);
  assert.equal(check.stats.seen, 10);
  assert.ok(cameraAdvice(check.stats).every((item) => item.ok));
});

test("dark, no face and tiny hands each get plain advice", () => {
  const check = createCameraCheck({ frames: 5 });
  for (let i = 0; i < 5; i += 1) check.add({ face: null, right_hand: hand(0.03) }, 0.05);
  const advice = Object.fromEntries(cameraAdvice(check.stats).map((item) => [item.id, item]));
  assert.equal(advice.light.ok, false);
  assert.equal(advice.framing.ok, false);
  assert.equal(advice.distance.ok, false);
  assert.match(advice.distance.text, /closer/);
});
