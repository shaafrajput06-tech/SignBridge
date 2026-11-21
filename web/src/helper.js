// The offline helper's answers (used by HelperChat.jsx; tested in web/tests/helper-chat.test.mjs). It answers only
// from SignMate's own data and never describes or invents a sign.
import { assetUrl } from "./paths.js";

const plain = (text) => String(text).toLowerCase().replace(/[^a-z0-9؀-ۿ ]/g, " ").replace(/\s+/g, " ").trim();
const SIGN_QUESTION = /^(how (do|to|can) (i|you|we) (sign|say)|sign for|what is the sign for|show me|show)\s+/;

export function answer(question, { dictionary = [], vocabulary = [], pslClasses = [] }) {
  const q = plain(question).replace(/\b(in psl|in sign language|please)\b/g, "").trim();
  if (!q) return { text: "Ask me how to sign a word, which signs the camera knows, or about privacy and offline use." };
  if (/\b(which|what) (signs|words)\b|\bwhat can (you|it) (recognise|recognize|understand)\b|\bcamera know/.test(q)) {
    const signs = pslClasses.filter((entry) => entry.tier).map((entry) => entry.english);
    return { text: signs.length ? `The PSL camera suggests ${signs.length} signs, for example: ${signs.slice(0, 12).join(", ")}. The full list with measured accuracy is on "How well it works".` : "The PSL camera is not available on this device." };
  }
  if (/\b(privacy|private|record|recorded|video saved|upload|data)\b/.test(q)) return { text: "The camera picture stays on your device. SignMate works with hand and face points, not video, and saves nothing unless you choose to." };
  if (/\b(offline|internet|airplane)\b/.test(q)) return { text: "After your first visit, \"Save for offline use\" (bottom of the page) stores everything on your device. Dictionary videos marked ⬇ work offline too." };
  if (/\b(accura|how good|how well|trust|wrong|mistake)\b/.test(q)) return { text: "Every PSL answer is a suggestion you confirm, and none is validated by Deaf signers yet. The measured numbers, and how they were measured, are on \"How well it works\"." };
  if (/\b(urdu|english|language|asl)\b/.test(q) && !SIGN_QUESTION.test(q)) return { text: "Choose English or اردو at the top. PSL is the main sign language; ASL is a separate mode with its own model, never mixed with PSL." };
  const word = q.replace(SIGN_QUESTION, "").replace(/^(the|a|an) /, "").trim();
  const key = plain(word).replace(/ /g, "");
  const fromVocabulary = vocabulary.find((item) => [item.english, item.urdu, item.romanUrdu].some((text) => plain(text || "").replace(/ /g, "") === key));
  const fromDictionary = dictionary.find((entry) => plain(entry.label.split(".")[0].replace(/[-_]/g, " ")).replace(/ /g, "") === (fromVocabulary ? plain(fromVocabulary.english).replace(/ /g, "") : key));
  const camera = pslClasses.find((entry) => entry.tier && plain(entry.english).replace(/ /g, "") === key);
  if (fromDictionary) return { text: `Here is “${word}” from the community PSL dictionary (not yet validated by Deaf signers).${camera ? " The PSL camera can also suggest it." : ""}`, video: fromDictionary.file ? assetUrl(fromDictionary.file) : fromDictionary.url };
  if (camera) return { text: `The PSL camera can suggest “${camera.english}”, but there is no licensed video of it to show yet.${camera.dictionary_url ? " The PSL dictionary page the dataset's signers learned from is linked on \"How well it works\"." : ""}` };
  return { text: `I have no licensed PSL video for “${word}” yet, and I never describe or make up a sign. Try the Dictionary page for similar words.` };
}

