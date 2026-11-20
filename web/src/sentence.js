// Glosses -> a readable sentence, offline, with rules only (master-v3 Stage 3, phase-6 task 1).
// The rules may reorder words, add punctuation and turn the gloss NO into "not" inside a clause; they never
// add a content word that is not traceable to a gloss. The raw glosses are always shown with the result.

const QUESTION = new Set(["what", "where", "who", "when", "how", "why", "which"]);
const TIME = new Set(["today", "tomorrow", "yesterday", "time", "now", "later"]);
// Whole expressions: each one is its own sentence.
const EXPRESSIONS = new Set(["hello", "goodbye", "thank_you", "thankyou", "please", "sorry", "welcome", "excuse_me", "excuseme",
  "assalam_o_alaikum", "walaikumassalam", "goodmorning", "goodnight", "goodafternoon", "have_a_good_day", "seeyoulater",
  "welldone", "ihaveacomplaint", "donttouch", "goaway", "comehere", "how_are_you", "i_am_fine", "my_name_is", "i_do_not_understand",
  "speak_slowly", "emergency", "help", "stop", "wait", "yes"]);

function key(entry) {
  return String(entry.gloss ?? entry.id ?? "").replace(/^psl:/, "").toLowerCase();
}

function words(entry, language) {
  return language === "ur" ? (entry.urdu || entry.english) : entry.english;
}

function capitalise(text) {
  return text ? text[0].toUpperCase() + text.slice(1) : text;
}

function clause(items, language) {
  const isQuestion = items.some((item) => QUESTION.has(key(item)));
  let ordered = items;
  if (language === "en") {
    // English: question word first, time words last.
    const question = items.filter((item) => QUESTION.has(key(item)));
    const time = items.filter((item) => TIME.has(key(item)));
    const rest = items.filter((item) => !QUESTION.has(key(item)) && !TIME.has(key(item)));
    ordered = [...question, ...rest, ...time];
  }
  // Urdu, like PSL, keeps time first and the question word in place.
  const parts = ordered.map((item, index) => {
    if (key(item) === "no" && index > 0) return language === "en" ? "not" : words(item, language);
    return words(item, language);
  });
  const text = language === "en" ? capitalise(parts.join(" ").toLowerCase().replace(/\bi\b/g, "I")) : parts.join(" ");
  const end = isQuestion ? (language === "ur" ? "؟" : "?") : (language === "ur" ? "۔" : ".");
  return text + end;
}

// entries: [{ gloss|id, english, urdu }] in signing order. Returns { text, glosses }.
export function buildSentence(entries, language = "en") {
  const sentences = [];
  let run = [];
  const flush = () => { if (run.length) sentences.push(clause(run, language)); run = []; };
  for (const entry of entries) {
    if (EXPRESSIONS.has(key(entry))) {
      flush();
      const text = words(entry, language);
      const end = language === "ur" ? "۔" : (/[.!?]$/.test(text) ? "" : ".");
      sentences.push(language === "en" ? capitalise(text) + end : text + end);
    } else {
      run.push(entry);
    }
  }
  flush();
  return { text: sentences.join(" "), glosses: entries.map((entry) => key(entry).toUpperCase().replace(/_/g, "-")) };
}

// Every content word of the English result comes from a gloss (the phase-6 rule), checked by tests.
export function contentWords(text) {
  return text.toLowerCase().replace(/[.?!،۔؟,]/g, " ").split(/\s+/).filter(Boolean);
}
