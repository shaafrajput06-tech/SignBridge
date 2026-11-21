// Text -> PSL word-by-word aid (master-v3 Stage 3, phase-6 task 3): finds the words of a typed or spoken
// reply that SignBridge knows (vocabulary phrases and PSL glosses, in English, Urdu or Roman Urdu), longest
// phrase first. It is a word-by-word aid, not signed translation: PSL grammar is not applied.

export function normalise(text) {
  return String(text).toLowerCase().normalize("NFC").replace(/[^\p{L}\p{N}\s']/gu, " ").replace(/\s+/g, " ").trim();
}

// entries: [{ id, english, urdu, romanUrdu }] -> Map(normalised phrase -> entry); earlier entries win.
export function phraseIndex(entries) {
  const index = new Map();
  for (const entry of entries) {
    for (const text of [entry.english, entry.urdu, entry.romanUrdu, ...(entry.aliases || [])]) {
      const phrase = normalise(text || "");
      if (phrase && !index.has(phrase)) index.set(phrase, entry);
    }
  }
  return index;
}

// -> [{ text, entry }] in reading order; entry is null for words SignBridge does not know.
export function matchWords(text, index, longest = 5) {
  const tokens = normalise(text).split(" ").filter(Boolean);
  const out = [];
  for (let i = 0; i < tokens.length;) {
    let found = null;
    for (let n = Math.min(longest, tokens.length - i); n >= 1 && !found; n -= 1) {
      const phrase = tokens.slice(i, i + n).join(" ");
      if (index.has(phrase)) found = { text: phrase, entry: index.get(phrase), size: n };
    }
    if (found) { out.push({ text: found.text, entry: found.entry }); i += found.size; }
    else { out.push({ text: tokens[i], entry: null }); i += 1; }
  }
  return out;
}
