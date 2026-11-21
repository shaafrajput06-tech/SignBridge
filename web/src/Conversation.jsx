// Conversation tools on the Translate screen (master-v3 Stage 3):
//  - SentenceStrip: the signs the person confirmed, turned into a sentence by rules (sentence.js), with the
//    raw glosses always shown underneath.
//  - ReplyPanel: the hearing person types (or, if they choose, speaks) a reply; it is shown large, and the
//    words SignMate knows play as PSL dictionary videos one after another. A word-by-word aid, not signed
//    translation, and it says so.
//  - QuickPhrases: one tap speaks a common or emergency phrase.
import React, { useMemo, useRef, useState } from "react";
import { assetUrl } from "./paths.js";
import { matchWords, phraseIndex } from "./reply.js";
import { buildSentence } from "./sentence.js";

export function SentenceStrip({ words, language, onSpeak, onUndo, onClear }) {
  if (!words.length) return null;
  const sentence = buildSentence(words, language);
  return <div className="sentence-strip panel" aria-live="polite">
    <div className="panel-heading"><div><span className="section-kicker">SENTENCE · FROM YOUR CONFIRMED SIGNS</span></div>
      <div className="sentence-actions"><button className="button button-primary" onClick={() => onSpeak(sentence.text)}>Speak sentence</button><button className="button button-quiet" onClick={onUndo}>Undo</button><button className="button button-quiet" onClick={onClear}>Clear</button></div></div>
    <p className="sentence-text" dir={language === "ur" ? "rtl" : "auto"}>{sentence.text}</p>
    <p className="sentence-glosses" title="The signs exactly as confirmed">{sentence.glosses.join(" · ")}</p>
    <small>Made by simple rules that only reorder and punctuate; they never add words. Check it against the signs above.</small>
  </div>;
}

function speechRecognition() {
  return typeof window !== "undefined" ? window.SpeechRecognition || window.webkitSpeechRecognition : null;
}

export function ReplyPanel({ entries, clips, language }) {
  const [text, setText] = useState("");
  const [shown, setShown] = useState("");
  const [playing, setPlaying] = useState(-1);
  const [listening, setListening] = useState(false);
  const videoRef = useRef(null);
  const index = useMemo(() => phraseIndex(entries), [entries]);
  const segments = useMemo(() => (shown ? matchWords(shown, index) : []), [shown, index]);
  const playable = segments.map((segment, i) => ({ i, clip: segment.entry && clips.byWord.get(segment.entry.vocabularyId ?? segment.entry.id) })).filter((item) => item.clip);
  const Recognition = speechRecognition();

  const play = (position) => {
    const item = playable[position];
    if (!item) { setPlaying(-1); return; }
    setPlaying(item.i);
    const video = videoRef.current;
    if (video) { video.src = assetUrl(item.clip.file); video.play().catch(() => {}); video.onended = () => play(position + 1); }
  };

  const listen = () => {
    if (!Recognition) return;
    const recognition = new Recognition();
    recognition.lang = language === "ur" ? "ur-PK" : "en-US";
    recognition.interimResults = false;
    recognition.onresult = (event) => { const said = event.results[0][0].transcript; setText(said); setShown(said); };
    recognition.onend = () => setListening(false);
    setListening(true);
    recognition.start();
  };

  return <div className="reply-panel panel">
    <div className="panel-heading"><div><span className="section-kicker">REPLY · FOR THE HEARING PERSON</span><h2>Write back</h2></div><span className="tier-chip">Word-by-word aid · not signed translation</span></div>
    <form className="reply-form" onSubmit={(event) => { event.preventDefault(); setShown(text); setPlaying(-1); }}>
      <textarea value={text} onChange={(event) => setText(event.target.value)} placeholder="Type in English or Urdu, e.g. “Thank you, the doctor is coming”" rows={2} aria-label="Reply text" dir="auto" />
      <div className="reply-buttons">
        <button className="button button-primary" type="submit" disabled={!text.trim()}>Show</button>
        {Recognition && <button className="button button-quiet" type="button" onClick={listen} disabled={listening} title="Uses your browser's speech service, which may send the audio to its maker's servers">{listening ? "Listening…" : "Speak instead"}</button>}
      </div>
    </form>
    {shown && <>
      <p className="reply-big" dir="auto">{shown}</p>
      <div className="reply-words">{segments.map((segment, i) => <span key={`${segment.text}-${i}`} className={`reply-word ${segment.entry ? "known" : ""} ${playing === i ? "playing" : ""}`}>{segment.text}{segment.entry && clips.byWord.has(segment.entry.vocabularyId ?? segment.entry.id) ? " ▶" : ""}</span>)}</div>
      {playable.length ? <div className="reply-player">
        <video ref={videoRef} muted playsInline controls aria-label="PSL dictionary videos for the reply" />
        <button className="button button-outline" onClick={() => play(0)}>Play the {playable.length} {playable.length === 1 ? "video" : "videos"} in order</button>
        <small>Community dictionary videos (SLT, CC BY 4.0), not yet validated by Deaf signers. Words without ▶ have no licensed video yet.</small>
      </div> : <small>None of these words has a licensed PSL video yet. SignMate never makes up how a sign looks.</small>}
    </>}
  </div>;
}

const QUICK = ["hello", "thank_you", "please", "sorry", "yes", "no", "wait", "repeat", "speak_slowly", "i_do_not_understand"];
const EMERGENCY = ["emergency", "help", "pain", "doctor", "hospital", "call", "dangerous", "medicine"];

export function QuickPhrases({ vocabulary, language, onPick }) {
  const byId = new Map(vocabulary.map((item) => [item.id, item]));
  const row = (ids) => ids.map((id) => byId.get(id)).filter(Boolean).map((item) => <button key={item.id} className="quick-phrase" onClick={() => onPick(item)} dir="auto">{language === "ur" ? item.urdu : item.english}</button>);
  if (!vocabulary.length) return null;
  return <div className="quick-phrases panel">
    <div><span className="section-kicker">QUICK PHRASES · TAP TO SPEAK</span><div className="quick-row">{row(QUICK)}</div></div>
    <div className="emergency-row"><span className="section-kicker emergency">EMERGENCY</span><div className="quick-row">{row(EMERGENCY)}</div></div>
  </div>;
}
