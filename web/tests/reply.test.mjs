// Text -> word-by-word PSL aid: longest phrase first, English / Urdu / Roman Urdu, unknown words kept.
import test from "node:test";
import assert from "node:assert/strict";
import { matchWords, normalise, phraseIndex } from "../src/reply.js";

const entries = [
  { id: "thank_you", english: "Thank you", urdu: "شکریہ", romanUrdu: "Shukriya" },
  { id: "doctor", english: "Doctor", urdu: "ڈاکٹر", romanUrdu: "Doctor" },
  { id: "how_are_you", english: "How are you?", urdu: "آپ کیسے ہیں؟", romanUrdu: "Aap kaise hain?" },
  { id: "you", english: "You", urdu: "آپ", romanUrdu: "Aap" },
];

test("longest phrase first, punctuation ignored", () => {
  const index = phraseIndex(entries);
  const out = matchWords("Thank you! How are you, doctor?", index);
  assert.deepEqual(out.map((item) => item.entry?.id ?? null), ["thank_you", "how_are_you", "doctor"]);
});

test("Urdu and Roman Urdu, and unknown words stay as text", () => {
  const index = phraseIndex(entries);
  assert.deepEqual(matchWords("شکریہ ڈاکٹر صاحب", index).map((item) => [item.text, item.entry?.id ?? null]), [["شکریہ", "thank_you"], ["ڈاکٹر", "doctor"], ["صاحب", null]]);
  assert.equal(matchWords("aap kaise hain", index)[0].entry.id, "how_are_you");
  assert.equal(normalise("  Hello,   WORLD! "), "hello world");
});
