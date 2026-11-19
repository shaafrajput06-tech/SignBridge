// ASL mode: a separate, clearly labelled language mode (CLAUDE.md 8.2). It never shows, mixes or
// describes ASL signs as PSL. Uses capture v2 (both hands, pose, face), cuts the stream into single
// signs and runs the Google Isolated Sign Language Recognition 1st-place model (250 ASL signs).
import React, { useEffect, useRef, useState } from "react";
import { createCaptureV2, loadFeatureSpecV2 } from "./capture_v2.js";
import { handCounts, islrFrame, loadAslSpec, SignSegmenter } from "./asl_islr.js";
import { createAslRecognizer, loadAslLabels } from "./asl_client.js";

const HAND_LINKS = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16], [13, 17], [17, 18], [18, 19], [19, 20], [0, 17]];
export const HAND_COLOURS = { left: "#f0c876", right: "#83d7b8" };
const HANDS_TEXT = { both: "Both hands seen", one: "Only one hand seen", none: "No hands seen" };

function drawHands(canvas, video, frame) {
  if (!canvas || !video) return;
  const width = video.videoWidth || 640;
  const height = video.videoHeight || 480;
  if (canvas.width !== width) canvas.width = width;
  if (canvas.height !== height) canvas.height = height;
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, width, height);
  for (const side of ["left", "right"]) {
    const points = frame?.[`${side}_hand`];
    if (!points) continue;
    context.strokeStyle = HAND_COLOURS[side];
    context.fillStyle = HAND_COLOURS[side];
    context.lineWidth = Math.max(2, width / 320);
    for (const [a, b] of HAND_LINKS) {
      context.beginPath();
      context.moveTo(points[a][0] * width, points[a][1] * height);
      context.lineTo(points[b][0] * width, points[b][1] * height);
      context.stroke();
    }
    for (const point of points) {
      context.beginPath();
      context.arc(point[0] * width, point[1] * height, Math.max(3, width / 220), 0, Math.PI * 2);
      context.fill();
    }
  }
}

function speak(text) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = 0.92;
  window.speechSynthesis.speak(utterance);
}

function friendly(error) {
  const text = String(error?.message || error);
  if (error?.name === "NotAllowedError") return "Camera permission was declined. Allow the camera in your browser settings and try again.";
  if (/pose_landmarker|face_landmarker|Feature spec|model file was not found|class list/i.test(text)) return `${text} Start the website once with internet (start_web.bat) so it can download the models.`;
  return text;
}

export default function AslMode({ requestCamera, voiceEnabled }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const voiceRef = useRef(voiceEnabled);
  voiceRef.current = voiceEnabled;
  const [cameraOn, setCameraOn] = useState(false);
  const [phase, setPhase] = useState("idle");
  const [message, setMessage] = useState("");
  const [runtime, setRuntime] = useState(null);
  const [hands, setHands] = useState("none");
  const [signing, setSigning] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    if (!cameraOn) return undefined;
    let active = true;
    let stream;
    let capture;
    let recogniser;
    let raf = 0;
    let busy = false;
    let pending = null;
    let lastSeen = "";
    let lastActive = false;

    function classify(sign, aslSpec) {
      if (busy) { pending = sign; return; }
      busy = true;
      const twoHandFrames = sign.filter((row) => handCounts(row, aslSpec).every(Boolean)).length;
      recogniser.predict(sign).then((answer) => {
        if (!active) return;
        setResult({ ...answer, twoHandFrames });
        setHistory((items) => [{ ...answer.top[0], band: answer.band, at: Date.now() }, ...items].slice(0, 5));
        if (answer.band === "sure" && voiceRef.current) speak(answer.top[0].display);
      }).catch((error) => {
        if (active) setMessage(`The ASL model stopped: ${error.message || error}`);
      }).finally(() => {
        busy = false;
        if (pending && active) { const next = pending; pending = null; classify(next, aslSpec); }
      });
    }

    (async () => {
      setPhase("loading");
      setMessage("Loading the ASL model…");
      const [featureSpec, aslSpec] = await Promise.all([loadFeatureSpecV2(), loadAslSpec()]);
      const labels = await loadAslLabels(aslSpec);
      recogniser = await createAslRecognizer({ aslSpec, labels });
      if (!active) { recogniser.close(); return; }
      setRuntime(recogniser.info);
      setMessage("Starting the camera…");
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
      if (!active) { stream.getTracks().forEach((track) => track.stop()); return; }
      const video = videoRef.current;
      video.srcObject = stream;
      await video.play();
      capture = await createCaptureV2({ spec: featureSpec });
      if (!active) { capture.close(); return; }
      const segmenter = new SignSegmenter(aslSpec);
      setPhase("ready");
      setMessage("");
      const loop = () => {
        if (!active) return;
        try {
          if (video.readyState >= 2) {
            // Browser camera frames are unmirrored; only the display is mirrored (CSS).
            const out = capture.processVideoFrame(video, performance.now(), { inputMirrored: false });
            if (out) {
              drawHands(canvasRef.current, video, out.frame);
              const seen = out.frame.left_hand && out.frame.right_hand ? "both" : out.frame.left_hand || out.frame.right_hand ? "one" : "none";
              if (seen !== lastSeen) { lastSeen = seen; setHands(seen); }
              const sign = segmenter.push(islrFrame(out.raw, featureSpec, aslSpec));
              if (segmenter.active !== lastActive) { lastActive = segmenter.active; setSigning(lastActive); }
              if (sign) classify(sign, aslSpec);
            }
          }
        } catch (error) {
          setMessage(`Tracking paused: ${error.message || error}`);
        }
        raf = requestAnimationFrame(loop);
      };
      loop();
    })().catch((error) => {
      if (active) { setPhase("error"); setMessage(friendly(error)); }
    });

    return () => {
      active = false;
      cancelAnimationFrame(raf);
      capture?.close();
      recogniser?.close();
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, [cameraOn]);

  const best = result?.top?.[0];
  return <section className="asl-mode">
    <div className="asl-banner panel" role="note">
      <span className="asl-tag">ASL</span>
      <div><strong>American Sign Language mode</strong><p>This is <b>not</b> Pakistan Sign Language. It recognises 250 everyday ASL words with a ready-made model. PSL stays the main language of SignBridge.</p></div>
    </div>
    <section className="translator-grid">
      <div className="camera-card panel">
        <div className="panel-heading">
          <div><span className="section-kicker">LIVE CAMERA · ASL</span><h2>Sign one word, then lower your hands</h2></div>
          <div className="camera-indicator"><i className={phase === "ready" ? "live" : ""} />{phase === "ready" ? "Camera on" : "Camera off"}</div>
        </div>
        <div className="camera-stage">
          <video ref={videoRef} className={phase === "ready" ? "camera-video visible mirrored" : "camera-video mirrored"} muted playsInline aria-label="Local camera preview" />
          <canvas ref={canvasRef} className="landmark-canvas mirrored" aria-hidden="true" />
          {phase !== "ready" && <div className="camera-placeholder">
            <strong>{phase === "error" ? "ASL mode needs attention" : phase === "loading" ? "Getting ready" : "Your camera stays on this device"}</strong>
            <p>{message || "Both hands, your shoulders and your face should be in view. Nothing is recorded."}</p>
            {phase !== "loading" && <button className="button button-primary" onClick={() => { setMessage(""); setPhase("idle"); setCameraOn(false); requestCamera(() => setCameraOn(true)); }}>Start ASL camera</button>}
          </div>}
          {phase === "ready" && <div className="camera-overlay-top">
            <span className={`hands-chip ${hands}`} role="status">{HANDS_TEXT[hands]}</span>
            {signing && <span className="signing-chip">Watching your sign…</span>}
          </div>}
          {phase === "ready" && <button className="camera-stop" onClick={() => { setCameraOn(false); setPhase("idle"); }}>Stop camera</button>}
        </div>
        <div className="camera-caption hand-legend">
          <span><i style={{ background: HAND_COLOURS.left }} /> Your left hand</span>
          <span><i style={{ background: HAND_COLOURS.right }} /> Your right hand</span>
          {message && phase === "ready" && <span className="inline-warning">{message}</span>}
        </div>
      </div>

      <div className="result-column">
        <div className="result-card panel">
          <div className="panel-heading result-heading"><div><span className="section-kicker">ASL RESULT</span><h2>What I saw</h2></div><span className="asl-tag small">ASL</span></div>
          {!result && <div className="translation-output"><div className="translation-main">Sign one ASL word</div><div className="translation-helper">Then lower your hands so I know you finished.</div></div>}
          {result?.band === "sure" && <div className="translation-output has-result"><div className="asl-confidence sure">Pretty sure</div><div className="translation-main">{best.display}</div></div>}
          {result?.band === "unsure" && <div className="translation-output"><div className="asl-confidence unsure">Not sure. Is it one of these?</div><div className="asl-choices">{result.top.slice(0, 3).map((item) => <span key={item.label} className="asl-choice">{item.display}</span>)}</div></div>}
          {result?.band === "none" && <div className="translation-output"><div className="asl-confidence none">I'm not sure. Try once more.</div><div className="translation-helper">Keep both hands and your face in view, and sign a little slower.</div></div>}
          {result && <p className="asl-details">{result.frames} frames · {result.twoHandFrames} with both hands · {Math.round(result.ms)} ms · {result.runtime === "server" ? "ran on the SignBridge server on this computer" : "ran in this browser"}</p>}
          {history.length > 1 && <div className="asl-history"><span className="section-kicker">EARLIER</span>{history.slice(1).map((item) => <span key={item.at} className={`asl-history-item ${item.band}`}>{item.band === "sure" ? item.display : `${item.display}?`}</span>)}</div>}
          <p className="asl-credit">Runs {runtime ? (runtime.frames ? `in this browser (LiteRT.js, ${runtime.frames}-frame input)` : `on ${runtime.runtime}`) : "on this device"}. Model: 1st place of Google's Isolated Sign Language Recognition competition by Hoyeol Sohn (MIT licence), trained on signs by Deaf signers from the Deaf Professional Arts Network and Georgia Tech (CC BY 4.0). Results are spoken only when it is pretty sure.</p>
        </div>
      </div>
    </section>
  </section>;
}
