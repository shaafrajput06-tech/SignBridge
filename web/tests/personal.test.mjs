// Personal adaptation: same numbers as tools/psl_train/personal.py (tests/test_psl_personal.py checks the
// Python side with the same case), stays bounded, and is dropped when the bundle changes.
import test from "node:test";
import assert from "node:assert/strict";
import { adapt, emptyPersonal, learn, loadPersonal, savePersonal } from "../src/personal.js";

test("one confirmation moves the bias towards the confirmed sign, like the Python version", () => {
  const scores = [Math.log(0.6), Math.log(0.3), Math.log(0.1)];
  const after = learn(emptyPersonal("v1", 3), scores, 1);
  const expected = [-0.06, 0.07, -0.01]; // tools/psl_train/personal.py, same input
  after.bias.forEach((value, i) => assert.ok(Math.abs(value - expected[i]) < 1e-3, `${i}: ${value}`));
  const adapted = adapt(scores, after);
  assert.ok(adapted[1] - adapted[0] > scores[1] - scores[0], "the confirmed sign moved up");
  assert.equal(after.confirmed, 1);
});

test("bias stays within its limit and storage is per bundle", () => {
  let personal = emptyPersonal("v1", 3);
  for (let i = 0; i < 200; i += 1) personal = learn(personal, [0, 0, 0], 2);
  assert.ok(personal.bias.every((value) => Math.abs(value) <= 2 + 1e-9));
  const store = new Map();
  const storage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v), removeItem: (k) => store.delete(k) };
  savePersonal(personal, storage);
  assert.equal(loadPersonal("v1", 3, storage).confirmed, 200);
  assert.equal(loadPersonal("v2", 3, storage).confirmed, 0, "a new bundle starts fresh");
});
