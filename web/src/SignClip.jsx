// "How it is signed": a real PSL signer's video from a community dictionary (SLT, CC BY 4.0), carried over
// from Inference Baseline v1. Shown only when a licensed video exists; SignBridge never makes up how a sign
// looks (CLAUDE.md 3), and the caption says the video is not yet validated by Deaf signers.
import React, { useEffect, useState } from "react";
import { assetUrl } from "./paths.js";

let loading = null;
export function loadClips() {
  loading ??= fetch(assetUrl("psl_clips.json"))
    .then((response) => (response.ok ? response.json() : { clips: [], attribution: "" }))
    .then((data) => ({ attribution: data.attribution || "", byWord: new Map((data.clips || []).map((clip) => [clip.word, clip])) }))
    .catch(() => ({ attribution: "", byWord: new Map() }));
  return loading;
}

export function useClips() {
  const [clips, setClips] = useState({ attribution: "", byWord: new Map() });
  useEffect(() => {
    let alive = true;
    loadClips().then((value) => { if (alive) setClips(value); });
    return () => { alive = false; };
  }, []);
  return clips;
}

// "close.shut" -> "close (shut)"
function labelText(label) {
  const [head, ...rest] = label.split(".");
  return rest.length ? `${head} (${rest.join(", ")})` : head;
}

export default function SignClip({ word, title, compact = false, showMissing = false }) {
  const { byWord, attribution } = useClips();
  const clip = byWord.get(word);
  if (!clip) return showMissing ? <p className="sign-clip-missing">No licensed PSL video for “{title}” yet. SignBridge never makes up how a sign looks.</p> : null;
  const different = clip.label.split(".")[0].replace(/[-_]/g, " ").toLowerCase() !== String(title).replace(/[?.!]/g, "").trim().toLowerCase();
  return <figure className={`sign-clip ${compact ? "compact" : ""}`}>
    <video src={assetUrl(clip.file)} controls loop muted playsInline preload="metadata" aria-label={`PSL video for ${title}`} />
    <figcaption>
      <b>How it is signed{different ? `: dictionary entry “${labelText(clip.label)}”` : ""}</b>
      <span>Community dictionary video · not yet validated by Deaf signers.</span>
      {!compact && <small>{attribution}</small>}
    </figcaption>
  </figure>;
}
