// The PSL answer card. Every PSL sign in this version is Tier B: a suggestion the person confirms, with
// the "Community dataset — not yet validated" badge always visible (CLAUDE.md 1, 8.3). Nothing is spoken
// until the person taps "Yes"; "Not a sign" is never offered as an answer.
import React from "react";

function word(entry, language) {
  return language === "ur" && entry.urdu ? entry.urdu : entry.english;
}

export default function PslSuggestion({ result, signing, language, badge, onConfirm, onDismiss }) {
  if (signing) return <div className="psl-suggestion watching" role="status"><span className="signing-chip">Watching your sign…</span><small>Lower your hands when you finish the sign.</small></div>;
  if (!result) return <div className="psl-suggestion idle"><b>Sign one PSL word, then lower your hands.</b><small>SignBridge suggests what it saw; you confirm it.</small></div>;
  const choices = result.top.filter((entry) => !entry.unknown).slice(0, 3);
  const best = choices[0];
  const dir = language === "ur" ? "rtl" : "auto";
  return <div className={`psl-suggestion ${result.band}`} role="status" aria-live="polite">
    <div className="psl-suggestion-head">
      <span className="tier-chip">Tier B · Suggested — please confirm</span>
      <span className="validation-badge">{badge}</span>
    </div>
    {result.band === "sure" && best && <>
      <div className="psl-word" dir={dir}>{word(best, language)}</div>
      <div className="psl-actions">
        <button className="button button-primary" onClick={() => onConfirm(best)}>Yes, that's it</button>
        <button className="button button-quiet" onClick={onDismiss}>No</button>
      </div>
      {choices.length > 1 && <div className="psl-alternatives"><small>Or did you sign:</small>{choices.slice(1).map((entry) => <button key={entry.gloss} className="asl-choice" onClick={() => onConfirm(entry)} dir={dir}>{word(entry, language)}</button>)}</div>}
    </>}
    {result.band === "unsure" && <>
      <div className="asl-confidence unsure">Not sure. Is it one of these?</div>
      <div className="asl-choices">{choices.map((entry) => <button key={entry.gloss} className="asl-choice" onClick={() => onConfirm(entry)} dir={dir}>{word(entry, language)}</button>)}</div>
      <button className="text-button" onClick={onDismiss}>None of these</button>
    </>}
    {result.band === "none" && <>
      <div className="asl-confidence none">I'm not sure. Try once more.</div>
      <small>Keep both hands in view and sign at a steady speed.</small>
    </>}
    <p className="asl-details">{result.frames} frames · {Math.round(result.ms)} ms · ran in this browser{best ? ` · ${Math.round(best.probability * 100)} % sure of “${best.english}”` : ""}</p>
  </div>;
}
