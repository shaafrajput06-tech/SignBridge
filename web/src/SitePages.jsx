// "How well it works", "Credits and licences" and "What's new" (master-v3 Stage 7). They show only what
// tools/site_pages.py read from the committed reports (shared_data/site_pages.json); nothing is typed here.
import React, { useEffect, useState } from "react";
import { assetUrl } from "./paths.js";

let loading = null;
function usePages() {
  const [pages, setPages] = useState(null);
  useEffect(() => {
    let alive = true;
    loading ??= fetch(assetUrl("site_pages.json")).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    loading.then((value) => { if (alive) setPages(value || {}); });
    return () => { alive = false; };
  }, []);
  return pages;
}

const pct = (v) => (v == null ? "—" : `${(v * 100).toFixed(1)} %`);

function Stat({ value, label }) {
  return <div className="report-stat"><strong>{value}</strong><small>{label}</small></div>;
}

export function HowWellItWorks() {
  const pages = usePages();
  if (!pages) return <p role="status">Loading…</p>;
  const { psl, asl, web_learn: web, performance } = pages;
  return <>
    <div className="section-intro"><div><span className="section-kicker">EVERY NUMBER IS MEASURED · FROM THE PROJECT'S REPORTS</span><h1>How well it works</h1>
      <p>Each number says what it was measured on, how and when. "Weaker" means the test could include people the model learned from. Read this before trusting an answer.</p></div></div>

    {psl ? <div className="panel report-body">
      <div className="report-summary"><div><span className="section-kicker">PSL CAMERA · {psl.bundle}</span><h2>{psl.signs} PSL signs · {psl.tiers.A} Tier A · {psl.tiers.B} Tier B · {psl.badge}</h2>
        <p>Trained {psl.trained} on {psl.samples} recordings from the SignSpeak dataset ({Object.entries(psl.devices).map(([k, v]) => `${v} ${k}`).join(", ")}). Test: {psl.device_held_out.protocol}{psl.device_held_out.fair_test ? `; ${psl.device_held_out.fair_test.samples} phone recordings (${psl.device_held_out.fair_test.rule})` : ""}.</p></div>
        <Stat value={pct(psl.device_held_out.top1)} label="top-1 on phone recordings it never saw (weaker)" /><Stat value={pct(psl.device_held_out.top5)} label="top-5" /></div>
      <ul className="report-facts">
        <li>One-handed signs: {pct(psl.device_held_out.one_handed.top1)} ({psl.device_held_out.one_handed.samples} tests). Two-handed signs: {pct(psl.device_held_out.two_handed.top1)} ({psl.device_held_out.two_handed.samples} tests).</li>
        {psl.device_held_out.left_right && <li>Left-handed signing (the same tests mirrored): {pct(psl.device_held_out.left_right.left_top1)}; right-handed: {pct(psl.device_held_out.left_right.right_top1)}.</li>}
        {psl.device_held_out.top1_all_phone != null && <li>All phone recordings, including signs this test cannot learn: {pct(psl.device_held_out.top1_all_phone)}.</li>}
        {psl.device_held_out.not_measured?.length > 0 && <li>Not measured (only phone recordings exist): {psl.device_held_out.not_measured.join(", ")}.</li>}
        {psl.device_held_out.label_conflicts?.map((c) => <li key={c.signs.join()}>Data problem: in the dataset's phone recordings, {c.signs.join(" and ")} are labelled the other way round. SignMate learned them from the computer-camera recordings only.</li>)}
        <li>A simpler model (GRU) scored {pct(psl.device_held_out.gru_top1)} on the same test; the better one ships.</li>
        {psl.independent_signer ? <li>One new signer (the SLT dictionary's, never in the training data), {psl.independent_signer.samples} signs: top-1 {pct(psl.independent_signer.top1)}, top-5 {pct(psl.independent_signer.top5)}. A miss can also be a regional variant of the sign.</li> : <li>A test on new signers has not been possible: the dataset has no signer names. That is why no sign is Tier A.</li>}
        {psl.personal_adaptation?.runs > 0 && <li>After 20 confirmations by the same person (simulated with phone recordings): {pct(psl.personal_adaptation.top1_before)} → {pct(psl.personal_adaptation.top1_after)}.</li>}
        <li>Model: {psl.model.architecture}, {psl.model.parameters.toLocaleString()} parameters, {(psl.model.bytes / 1e6).toFixed(1)} MB ({psl.model.precision}). Source: <code>{psl.source_report}</code>.</li>
      </ul>
      <table className="report-table"><thead><tr><th>Sign</th><th>اردو</th><th>Hands</th><th>Tests</th><th>Top-1</th><th>Top-5</th></tr></thead>
        <tbody>{psl.per_sign.map((s) => <tr key={s.english} title={s.note}><td>{s.dictionary_url ? <a href={s.dictionary_url} target="_blank" rel="noreferrer">{s.english}</a> : s.english}{s.note ? " *" : ""}</td><td dir="rtl">{s.urdu}</td><td>{s.hands}</td><td>{s.tested}</td><td>{pct(s.top1)}</td><td>{pct(s.top5)}</td></tr>)}</tbody></table>
      <p className="asl-credit">* see the data note (hover). Sign names link to the PSL dictionary page the dataset's signers learned from.</p>
    </div> : <div className="panel report-body"><h2>PSL camera</h2><p>No PSL model in this copy of SignMate.</p></div>}

    {asl && <div className="panel report-body"><div className="report-summary"><div><span className="section-kicker">ASL MODE · A SEPARATE LANGUAGE</span><h2>250 ASL words · ready-made model</h2>
      <p>{asl.dataset}: {asl.samples.toLocaleString()} signs by signers the model never saw, measured {asl.measured_on} ({asl.where}).</p></div>
      <Stat value={pct(asl.browser_top1)} label={`top-1 in the browser (${asl.browser_frames} frames)`} /><Stat value={pct(asl.top5)} label="top-5 (full sign)" /></div>
      <ul className="report-facts"><li>Full-length sign: top-1 {pct(asl.top1)}.</li><li>Left-handed signers {pct(asl.left_dominant_top1)}, right-handed {pct(asl.right_dominant_top1)}.</li>
        <li>Spoken aloud only at {Math.round(asl.speak_at * 100)} % or more: that covered {pct(asl.spoken_share)} of signs, and {pct(asl.wrong_when_spoken)} of those were wrong ({pct(asl.wrong_at_pretty_sure)} at 60 %).</li>
        <li>Two-handed signs: only {asl.two_handed.samples} in the test set, so no reliable number. Source: <code>{asl.source_report}</code>.</li></ul></div>}

    {web && <div className="panel report-body"><span className="section-kicker">LEARNING FROM LICENSED VIDEOS</span><h2>{web.kept} dictionary videos learned · {web.vocabulary_covered} of {web.vocabulary_total} phrases covered</h2>
      <p>{web.kept} of {web.dictionary_labels} SLT dictionary videos passed the checks ({web.rejected} rejected: hands not visible). {web.outside_vocabulary} of them are signs outside the 64 phrases (Dictionary page). All are Tier B. Source: <code>{web.source_report}</code>.</p></div>}

    {performance?.measurements?.length > 0 && <div className="panel report-body"><span className="section-kicker">SPEED</span><h2>Measured speed</h2>
      <table className="report-table"><thead><tr><th>What</th><th>Result</th><th>Where</th><th>When</th></tr></thead>
        <tbody>{performance.measurements.map((m) => <tr key={m.what + m.where}><td>{m.what}</td><td>{m.result}</td><td>{m.where}</td><td>{m.date}</td></tr>)}</tbody></table>
      <p className="asl-credit">Source: <code>reports/performance_v3.json</code>. {performance.note || ""}</p></div>}
  </>;
}

export function Credits() {
  const pages = usePages();
  if (!pages) return <p role="status">Loading…</p>;
  const credits = pages.credits || { assets: [], software: [] };
  return <>
    <div className="section-intro"><div><span className="section-kicker">FROM data/LICENSES.yaml</span><h1>Credits and licences</h1><p>SignMate is built on other people's work. Every dataset, model and video it uses is listed here with the credit its licence asks for.</p></div></div>
    <div className="panel report-body"><h2>Data, models and videos</h2>
      <table className="report-table"><thead><tr><th>What</th><th>Used for</th><th>Licence</th><th>Credit</th></tr></thead>
        <tbody>{credits.assets.map((a) => <tr key={a.id}><td>{a.source_url?.startsWith("http") ? <a href={a.source_url} target="_blank" rel="noreferrer">{a.name}</a> : a.name}</td><td>{a.used_for}</td><td>{a.licence}</td><td>{a.attribution}</td></tr>)}</tbody></table></div>
    <div className="panel report-body"><h2>Software</h2>
      <table className="report-table"><thead><tr><th>Package</th><th>Version</th><th>Licence</th></tr></thead>
        <tbody>{credits.software.map((s) => <tr key={s.name}><td>{s.name}</td><td>{s.version}</td><td>{s.licence}</td></tr>)}</tbody></table></div>
  </>;
}

export function WhatsNew() {
  const pages = usePages();
  if (!pages) return <p role="status">Loading…</p>;
  return <>
    <div className="section-intro"><div><span className="section-kicker">SIGNBRIDGE 3.0</span><h1>What's new</h1><p>What changed since the previous version of this website.</p></div></div>
    {(pages.whats_new || []).map((section) => <div className="panel report-body" key={section.title}><h2>{section.title}</h2><ul className="report-facts">{section.items.map((item) => <li key={item}>{item}</li>)}</ul></div>)}
  </>;
}
