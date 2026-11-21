// The full PSL dictionary (master-v3 Stage 7 list A): every sign of the SLT community PSL dictionary
// (CC BY 4.0), which Stage 1 learned as Tier B. Each entry shows the dictionary's own video: the 31 vocabulary
// videos are stored with the site (work offline); the others play from the dataset's GitHub release when the
// visitor presses play (internet needed, and GitHub sees that request). No video is ever made up.
import React, { useEffect, useMemo, useState } from "react";
import { assetUrl } from "./paths.js";

function readable(label) {
  const [head, ...rest] = label.split(".");
  const word = head.replace(/[-_]/g, " ");
  return rest.length ? `${word} (${rest.join(", ").replace(/[-_]/g, " ")})` : word;
}

const plain = (text) => text.toLowerCase().replace(/[^a-z0-9]/g, "");

export default function Dictionary({ pslClasses = [] }) {
  const [data, setData] = useState(null);
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState(null);
  useEffect(() => {
    let alive = true;
    fetch(assetUrl("psl_dictionary.json")).then((r) => (r.ok ? r.json() : null)).then((value) => { if (alive) setData(value || { entries: [], note: "The dictionary list is not in this copy of SignMate." }); })
      .catch(() => { if (alive) setData({ entries: [], note: "The dictionary list could not be loaded." }); });
    return () => { alive = false; };
  }, []);
  const camera = useMemo(() => new Set(pslClasses.filter((entry) => entry.tier).map((entry) => plain(entry.english))), [pslClasses]);
  const entries = data?.entries || [];
  const shown = useMemo(() => {
    const q = plain(query);
    return q ? entries.filter((entry) => plain(entry.label).includes(q)) : entries;
  }, [entries, query]);

  if (!data) return <p role="status">Loading the dictionary…</p>;
  const pickedWord = picked && readable(picked.label);
  return <section className="content-section dictionary">
    <div className="section-intro"><div><span className="section-kicker">{entries.length} PSL SIGNS · COMMUNITY DICTIONARY · TIER B</span><h1>PSL dictionary</h1>
      <p>Every sign of the SLT community PSL dictionary, signed by one real signer. SignMate learned their hand movements in Stage 1 as suggestions (Tier B). <b>Not yet validated by Deaf signers.</b> Videos marked ⬇ are stored with SignMate and work offline; the others play from the dictionary's GitHub page and need internet.</p></div></div>
    {data.note && <p className="inline-warning">{data.note}</p>}
    <div className="dictionary-layout">
      <div className="panel dictionary-list">
        <input className="dictionary-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search, e.g. water, doctor, school" aria-label="Search the PSL dictionary" />
        <p className="dictionary-count">{shown.length} of {entries.length}</p>
        <div className="dictionary-words">{shown.slice(0, 400).map((entry) => <button key={entry.label} className={picked?.label === entry.label ? "dictionary-word active" : "dictionary-word"} onClick={() => setPicked(entry)}>{readable(entry.label)}{entry.file ? " ⬇" : ""}</button>)}</div>
        {shown.length > 400 && <p className="dictionary-count">Type to narrow the list ({shown.length - 400} more).</p>}
      </div>
      <div className="panel dictionary-view">
        {picked ? <figure className="sign-clip">
          <h2>{pickedWord}</h2>
          <video key={picked.label} src={picked.file ? assetUrl(picked.file) : picked.url} controls loop muted playsInline autoPlay preload="metadata" aria-label={`PSL dictionary video: ${pickedWord}`} />
          <figcaption>
            <b>Community dictionary video · not yet validated by Deaf signers</b>
            <span>{picked.file ? "Stored with SignMate (works offline)." : "Plays from the dictionary's GitHub release (internet needed)."}{camera.has(plain(picked.label.split(".")[0])) ? " The PSL camera can also suggest this sign." : ""}</span>
            <small>{data.attribution}</small>
          </figcaption>
        </figure> : <p>Choose a sign to see how it is signed.</p>}
      </div>
    </div>
  </section>;
}
