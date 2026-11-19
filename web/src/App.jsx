import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { classifyGesture, createHandDetector, drawLandmarks, normalizeLandmarks, releaseHandDetector } from "./vision.js";
import AslMode from "./AslMode.jsx";
import { API_BASE, HAS_SERVER, assetUrl } from "./paths.js";

const API = API_BASE;
const HOLD_FRAMES = 8;
const LOST_MS = 900;
const localHost = ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);

async function request(path, options = {}) {
  if (!HAS_SERVER) throw new Error("This website version has no SignBridge server.");
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) },
  });
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `Request failed (${response.status})`);
  return response.headers.get("content-type")?.includes("application/json") ? response.json() : response.text();
}

function speakItem(item, language, enabled) {
  if (!enabled || !item || !("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(language === "ur" ? item.urdu : item.english);
  utterance.lang = language === "ur" ? "ur-PK" : "en-US";
  utterance.rate = 0.92;
  window.speechSynthesis.speak(utterance);
}

function Icon({ children }) { return <span className="icon" aria-hidden="true">{children}</span>; }

export default function App() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const modeRef = useRef("demo");
  const languageRef = useRef("en");
  const backendRef = useRef(false);
  const modelRef = useRef(false);
  const busyPredictRef = useRef(false);
  const sampleRef = useRef(null);
  const lastAcceptedRef = useRef("");
  const vocabularyRef = useRef([]);
  const acceptWordRef = useRef(() => {});

  const [vocabulary, setVocabulary] = useState([]);
  const [connection, setConnection] = useState("checking");
  const [modelInfo, setModelInfo] = useState({ available: false, mode: "AI Demo Mode" });
  const [view, setView] = useState("translate");
  const [language, setLanguage] = useState("en");
  const [romanUrdu, setRomanUrdu] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [dark, setDark] = useState(true);
  const [cameraOn, setCameraOn] = useState(false);
  const [metricsConsent, setMetricsConsent] = useState(() => {
    try { return localStorage.getItem("signbridge_mediapipe_metrics_consent") === "yes"; } catch { return false; }
  });
  const [metricsNoticeOpen, setMetricsNoticeOpen] = useState(false);
  const [metricsNoticeChecked, setMetricsNoticeChecked] = useState(false);
  const [facing, setFacing] = useState("user");
  const [cameraError, setCameraError] = useState("");
  const [mode, setMode] = useState("demo");
  const [status, setStatus] = useState("Show a sign to the camera");
  const [current, setCurrent] = useState(null);
  const [lastFeatures, setLastFeatures] = useState(null);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All categories");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const [exhibition, setExhibition] = useState(false);
  const [participant, setParticipant] = useState("");
  const [consent, setConsent] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [counts, setCounts] = useState({});
  const [report, setReport] = useState("");
  // Which sign language is active. PSL is the main language; ASL is a separate, clearly labelled mode (CLAUDE.md 8.2).
  const [signLanguage, setSignLanguage] = useState(() => {
    try { return localStorage.getItem("signbridge_sign_language") === "ASL" ? "ASL" : "PSL"; } catch { return "PSL"; }
  });
  const pendingCameraStartRef = useRef(null);

  const currentMode = mode === "trained" ? "AI Trained Mode" : "AI Demo Mode";
  modeRef.current = mode;
  languageRef.current = language;
  backendRef.current = connection === "online";
  modelRef.current = modelInfo.available;

  const requestCameraStart = () => {
    setCameraError("");
    if (metricsConsent) setCameraOn(true);
    else { setMetricsNoticeChecked(false); setMetricsNoticeOpen(true); }
  };

  const acceptMetricsNotice = () => {
    try { localStorage.setItem("signbridge_mediapipe_metrics_consent", "yes"); } catch { /* Ask again after reload if storage is unavailable. */ }
    setMetricsConsent(true);
    setMetricsNoticeOpen(false);
    const pending = pendingCameraStartRef.current;
    pendingCameraStartRef.current = null;
    if (pending) pending(); else setCameraOn(true);
  };

  // ASL mode asks for the camera through the same MediaPipe notice as PSL mode.
  const requestAslCamera = (start) => {
    if (metricsConsent) start();
    else { pendingCameraStartRef.current = start; setMetricsNoticeChecked(false); setMetricsNoticeOpen(true); }
  };

  function changeSignLanguage(next) {
    setSignLanguage(next);
    setCameraOn(false);
    setCurrent(null);
    try { localStorage.setItem("signbridge_sign_language", next); } catch { /* the choice lasts for this visit only */ }
  }

  useEffect(() => {
    let active = true;
    fetch(`${API}/vocabulary?page_size=128`).then((response) => response.ok ? response.json() : Promise.reject()).then((data) => {
      if (active) setVocabulary(data.items || []);
    }).catch(async () => {
      try {
        const response = await fetch(assetUrl("vocabulary.json"));
        if (active && response.ok) setVocabulary(await response.json());
      } catch { if (active) setVocabulary([]); }
    });
    return () => { active = false; };
  }, []);

  const refreshConnection = useCallback(async () => {
    try {
      const [health, model] = await Promise.all([request("/health"), request("/model-status")]);
      setConnection("online");
      setModelInfo(model);
      if (!model.available) setMode("demo");
      if (health.model_available !== model.available) setStatus("Backend and model status are updating");
    } catch {
      setConnection("offline");
      setModelInfo({ available: false, mode: "AI Demo Mode" });
      setMode("demo");
    }
  }, []);

  useEffect(() => {
    refreshConnection();
    const timer = window.setInterval(refreshConnection, 12000);
    return () => window.clearInterval(timer);
  }, [refreshConnection]);

  useEffect(() => {
    let alive = true;
    request("/settings").then((saved) => {
      if (!alive) return;
      setLanguage(saved.language === "ur" ? "ur" : "en");
      setRomanUrdu(Boolean(saved.roman_urdu));
      setVoiceEnabled(saved.voice_enabled !== false);
    }).catch(() => {});
    return () => { alive = false; };
  }, []);

  const persistSettings = useCallback((patch) => {
    request("/settings", { method: "PUT", body: JSON.stringify(patch) }).catch(() => {});
  }, []);

  const acceptWord = useCallback((item, source, nextStatus) => {
    if (!item) return;
    setCurrent(item);
    setSelected(item);
    setStatus(nextStatus || (item.demoAvailable ? "Rule-based match" : "Vocabulary Mode — training data required for camera recognition"));
    if (source !== "camera" || lastAcceptedRef.current !== item.id) {
      lastAcceptedRef.current = item.id;
      speakItem(item, languageRef.current, voiceEnabled);
      request("/history", { method: "POST", body: JSON.stringify({ vocabulary_id: item.id, language: languageRef.current, source }) }).catch(() => {});
    }
  }, [voiceEnabled]);
  // The camera loop reads these through refs so that loading the vocabulary or toggling voice
  // does not tear down and restart the camera.
  vocabularyRef.current = vocabulary;
  acceptWordRef.current = acceptWord;

  useEffect(() => {
    if (!cameraOn) return undefined;
    let active = true;
    let stream;
    let detector;
    let raf = 0;
    let recent = [];
    let lastHandAt = 0;
    let frameNumber = 0;
    let lastStatus = "";

    async function start() {
      if (!window.isSecureContext && !localHost) {
        setCameraError("Phone and tablet browsers require HTTPS before they allow camera access. Use the mobile app or open the site through a trusted HTTPS address.");
        return;
      }
      if (!navigator.mediaDevices?.getUserMedia) {
        setCameraError("This browser does not provide camera access. Use a recent browser or browse the vocabulary without a camera.");
        return;
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: facing }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
        if (!active) { stream.getTracks().forEach((track) => track.stop()); return; }
        setCameraError("");
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        detector = await createHandDetector();
        if (!active) return;

        const loop = () => {
          if (!active || !videoRef.current || videoRef.current.readyState < 2) {
            raf = requestAnimationFrame(loop);
            return;
          }
          try {
            const result = detector.detectForVideo(videoRef.current, performance.now());
            const points = result.landmarks?.[0] || null;
            drawLandmarks(canvasRef.current, videoRef.current, points);
            frameNumber += 1;
            if (points) {
              lastHandAt = performance.now();
              const handedness = result.handedness?.[0]?.[0]?.categoryName || "Right";
              let features = null;
              try { features = normalizeLandmarks(points, handedness); } catch { features = null; }
              if (features && frameNumber % 6 === 0) {
                sampleRef.current = features;
                setLastFeatures(features);
              }
              let guess = classifyGesture(points);
              if (modeRef.current === "trained" && modelRef.current && backendRef.current) {
                if (features && frameNumber % 6 === 0 && !busyPredictRef.current) {
                  busyPredictRef.current = true;
                  request("/predict", { method: "POST", body: JSON.stringify({ features }) })
                    .then((prediction) => {
                      const item = vocabularyRef.current.find((entry) => entry.id === prediction.vocabulary_id);
                      const id = item?.id || null;
                      recent = [...recent, id].slice(-HOLD_FRAMES);
                      if (id && recent.length === HOLD_FRAMES && recent.every((entry) => entry === id) && lastAcceptedRef.current !== id) acceptWordRef.current(item, "camera", "Trained model prediction");
                      if (id) setStatus("Trained model prediction");
                    })
                    .catch(() => setStatus("Trained model is unavailable; switch to AI Demo Mode"))
                    .finally(() => { busyPredictRef.current = false; });
                }
              } else {
                const item = vocabularyRef.current.find((entry) => entry.gestureId === guess);
                const id = item?.id || null;
                recent = [...recent, id].slice(-HOLD_FRAMES);
                const newStatus = id ? (modeRef.current === "trained" ? "Trained model prediction" : "Rule-based match") : "Hold sign steady";
                if (newStatus !== lastStatus) { lastStatus = newStatus; setStatus(newStatus); }
                if (id && recent.length === HOLD_FRAMES && recent.every((entry) => entry === id) && lastAcceptedRef.current !== id) {
                  acceptWordRef.current(item, "camera", newStatus);
                }
              }
            } else {
              recent = [];
              if (performance.now() - lastHandAt > LOST_MS) {
                lastAcceptedRef.current = "";
                setCurrent(null);
                if (lastStatus !== "Show a sign to the camera") { lastStatus = "Show a sign to the camera"; setStatus(lastStatus); }
              }
              drawLandmarks(canvasRef.current, videoRef.current, null);
            }
          } catch (error) {
            setCameraError(`Camera recognition paused: ${error.message || "hand tracking error"}`);
          }
          raf = requestAnimationFrame(loop);
        };
        loop();
      } catch (error) {
        setCameraError(error.name === "NotAllowedError" ? "Camera permission was declined. Allow camera access in your browser settings and try again." : error.message || "The camera could not start.");
      }
    }
    start();
    return () => {
      active = false;
      cancelAnimationFrame(raf);
      releaseHandDetector();
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, [cameraOn, facing]);

  useEffect(() => {
    const handleKey = (event) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement || event.target?.isContentEditable) return;
      if (view === "vocabulary" && ["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft"].includes(event.key)) {
        const cards = [...document.querySelectorAll(".vocab-card")];
        if (cards.length) {
          const currentIndex = cards.indexOf(document.activeElement);
          const forward = event.key === "ArrowDown" || event.key === "ArrowRight";
          const nextIndex = currentIndex < 0 ? (forward ? 0 : cards.length - 1) : Math.max(0, Math.min(cards.length - 1, currentIndex + (forward ? 1 : -1)));
          cards[nextIndex].focus();
          event.preventDefault();
          return;
        }
      }
      const key = event.key.toLowerCase();
      if (key === "e") { setLanguage("en"); persistSettings({ language: "en" }); }
      else if (key === "u") { setLanguage("ur"); persistSettings({ language: "ur" }); }
      else if (key === "l") { setLanguage((previous) => { const next = previous === "en" ? "ur" : "en"; persistSettings({ language: next }); return next; }); }
      else if (key === "r" && current) speakItem(current, language, voiceEnabled);
      else if (key === "v") { setVoiceEnabled((value) => { persistSettings({ voice_enabled: !value }); return !value; }); }
      else if (key === "m" && modelInfo.available) setMode((value) => value === "demo" ? "trained" : "demo");
      else if (key === "b") setView((value) => value === "vocabulary" ? "translate" : "vocabulary");
      else if (key === "h") setHelpOpen((value) => !value);
      else if (key === "q") setCameraOn(false);
      else if (key === "escape") { setHelpOpen(false); setExhibition(false); }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [current, language, voiceEnabled, modelInfo.available, persistSettings, view]);

  useEffect(() => {
    if (connection !== "online" || view !== "training") return;
    request("/training-counts").then(setCounts).catch(() => {});
  }, [connection, view]);

  useEffect(() => {
    if (connection === "online" && view === "report") request("/training-report").then(setReport).catch((error) => setReport(error.message));
  }, [connection, view]);

  const categories = useMemo(() => ["All categories", ...new Set(vocabulary.map((item) => item.category))], [vocabulary]);
  const filtered = useMemo(() => vocabulary.filter((item) => (category === "All categories" || item.category === category) && (!search.trim() || `${item.english} ${item.urdu} ${item.romanUrdu} ${item.category}`.toLowerCase().includes(search.trim().toLowerCase()))), [vocabulary, category, search]);
  const pageSize = 12;
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const visibleItems = filtered.slice(page * pageSize, (page + 1) * pageSize);

  function changeLanguage(next) {
    setLanguage(next);
    persistSettings({ language: next });
  }

  async function saveExample() {
    if (!consent) { setSaveMessage("Check the consent box before saving landmarks."); return; }
    const features = sampleRef.current;
    if (!features) { setSaveMessage("Show a hand to the camera first."); return; }
    if (!selected) { setSaveMessage("Choose a vocabulary item to label this example."); return; }
    try {
      const response = await request("/recordings", { method: "POST", body: JSON.stringify({ consent: true, examples: [{ vocabulary_id: selected.id, participant: participant || "anonymous", session_id: `web-${Date.now()}`, features, frame_width: videoRef.current?.videoWidth || 0, frame_height: videoRef.current?.videoHeight || 0 }] }) });
      setSaveMessage(`${response.saved} landmark example saved on this computer. Camera images were not saved.`);
      setCounts((value) => ({ ...value, [selected.id]: (value[selected.id] || 0) + response.saved }));
    } catch (error) { setSaveMessage(error.message); }
  }

  async function openReport() {
    setView("report");
    if (connection === "online") request("/training-report").then(setReport).catch((error) => setReport(error.message));
  }

  const selectedText = current ? (language === "ur" ? (romanUrdu ? current.romanUrdu : current.urdu) : current.english) : "Show a sign to the camera";
  const helperText = current ? (language === "ur" ? current.english : (romanUrdu ? current.romanUrdu : current.urdu)) : "Your result appears here";

  return <div className={`app-shell ${dark ? "theme-dark" : "theme-light"} ${exhibition ? "exhibition" : ""}`}>
    {!exhibition && <header className="topbar">
      <a className="brand" href="#home" onClick={(event) => { event.preventDefault(); setView("translate"); }} aria-label="SignBridge home"><span className="brand-mark">S</span><span><strong>SignBridge</strong><small>Words that connect</small></span></a>
      <nav className="main-nav" aria-label="Main navigation">
        {[ ["translate", "Translate"], ["vocabulary", "Vocabulary"], ["training", "Training"], ["report", "Model report"] ].map(([id, label]) => <button key={id} className={view === id ? "nav-link active" : "nav-link"} onClick={() => setView(id)}>{label}</button>)}
      </nav>
      <div className="top-actions">
        <div className="sign-language-switch" role="group" aria-label="Sign language">
          <span>Sign language</span>
          <button className={signLanguage === "PSL" ? "selected" : ""} aria-pressed={signLanguage === "PSL"} onClick={() => changeSignLanguage("PSL")} title="Pakistan Sign Language (main)">PSL</button>
          <button className={signLanguage === "ASL" ? "selected asl" : "asl"} aria-pressed={signLanguage === "ASL"} onClick={() => changeSignLanguage("ASL")} title="American Sign Language (separate mode, not PSL)">ASL</button>
        </div>
        <span className={`connection-pill ${connection}`}><i />{connection === "online" ? "Backend connected" : connection === "offline" ? (HAS_SERVER ? "Offline demo" : "Website version") : "Connecting"}</span>
        <button className="icon-button" title="Switch theme" aria-label="Switch theme" onClick={() => setDark((value) => !value)}>{dark ? "☼" : "◐"}</button>
        <button className="help-button" onClick={() => setHelpOpen(true)}><span>?</span> Help</button>
      </div>
    </header>}

    <main className="page-wrap">
      {(view === "translate" || exhibition) && signLanguage === "ASL" && <AslMode requestCamera={requestAslCamera} voiceEnabled={voiceEnabled} />}
      {(view === "translate" || exhibition) && signLanguage === "PSL" && <>
        {!exhibition && <section className="welcome-row">
          <div><div className="eyebrow"><span className="pulse-dot" /> LOCAL-FIRST ACCESSIBILITY PROTOTYPE</div><h1>Every hand has <em>something to say.</em></h1><p>Show a supported pose, explore the phrasebook, and choose how SignBridge speaks.</p></div>
          <div className="mode-control"><span>Recognition mode</span><button className={`mode-switch ${mode === "trained" ? "on" : ""}`} disabled={!modelInfo.available} onClick={() => setMode((value) => value === "demo" ? "trained" : "demo")}><i />{currentMode}<small>{modelInfo.available ? "Tap to switch" : "Trained mode appears after you collect and train data"}</small></button></div>
        </section>}

        <section className="translator-grid">
          <div className="camera-card panel">
            <div className="panel-heading">
              <div><span className="section-kicker">LIVE CAMERA</span><h2>Show a sign</h2></div>
              <div className="camera-indicator"><i className={cameraOn && !cameraError ? "live" : ""} />{cameraOn && !cameraError ? "Camera on" : "Camera off"}</div>
            </div>
            <div className="camera-stage">
              <video ref={videoRef} className={cameraOn && !cameraError ? "camera-video visible" : "camera-video"} muted playsInline aria-label="Local camera preview" />
              <canvas ref={canvasRef} className="landmark-canvas" aria-hidden="true" />
              {(!cameraOn || cameraError) && <div className="camera-placeholder"><div className="camera-orb"><Icon>⌖</Icon></div><strong>{cameraError ? "Camera needs attention" : "Your camera stays on this device"}</strong><p>{cameraError || "Turn on the camera to see hand tracking. Nothing is recorded by default."}</p><button className="button button-primary" onClick={requestCameraStart}><Icon>◉</Icon> Enable camera</button></div>}
              {cameraOn && !cameraError && <div className="camera-overlay-top"><span className="mini-live"><i /> LIVE</span><span className="overlay-mode">{currentMode}</span></div>}
              {cameraOn && <button className="camera-switch" aria-label="Switch front or rear camera" title="Switch camera" onClick={() => setFacing((value) => value === "user" ? "environment" : "user")}>↺</button>}
              {cameraOn && <button className="camera-stop" aria-label="Stop camera" onClick={() => { setCameraOn(false); setCurrent(null); setStatus("Camera stopped"); }}>Stop camera</button>}
            </div>
            <div className="camera-caption"><span><b>●</b> MediaPipe hand tracking runs locally in this browser.</span><button className="text-button" onClick={() => setHelpOpen(true)}>How it works <span>↗</span></button></div>
          </div>

          <div className="result-column">
            <div className="result-card panel">
              <div className="panel-heading result-heading"><div><span className="section-kicker">TRANSLATION</span><h2>Recognized phrase</h2></div><span className={`mode-badge ${mode}`}>{currentMode}</span></div>
              <div className="language-switch" role="group" aria-label="Output language"><button className={language === "en" ? "selected" : ""} onClick={() => changeLanguage("en")}>English</button><button className={language === "ur" ? "selected" : ""} onClick={() => changeLanguage("ur")}>اردو</button><button className="cycle-button" title="Switch language" onClick={() => changeLanguage(language === "en" ? "ur" : "en")}>↔</button></div>
              <div className={`translation-output ${current ? "has-result" : ""}`}>
                <div className="translation-main" dir={language === "ur" && !romanUrdu ? "rtl" : "auto"}>{selectedText}</div>
                <div className="translation-helper" dir={language === "en" && !romanUrdu ? "rtl" : "auto"}>{helperText}</div>
              </div>
              <div className="recognition-status"><span className={current ? "status-check" : "status-wait"}>{current ? "✓" : "…"}</span><span>{status}</span><span className="rule-label">{current ? (mode === "trained" ? "Model result" : "Rule-based match") : "Waiting"}</span></div>
              {current && <div className="gesture-hint"><span className="hint-icon">✳</span><span><b>Gesture hint</b>{current.handSignHint || "No demo gesture is assigned to this phrase."}</span></div>}
              <div className="result-actions"><button className="button button-primary" onClick={() => current && speakItem(current, language, voiceEnabled)} disabled={!current}><Icon>◖</Icon> Speak</button><button className={`button button-quiet ${voiceEnabled ? "voice-on" : ""}`} onClick={() => { setVoiceEnabled((value) => { persistSettings({ voice_enabled: !value }); return !value; }); }}><Icon>{voiceEnabled ? "♪" : "∅"}</Icon>{voiceEnabled ? "Voice on" : "Voice off"}</button><button className={`button button-quiet ${romanUrdu ? "voice-on" : ""}`} onClick={() => { setRomanUrdu((value) => { persistSettings({ roman_urdu: !value }); return !value; }); }}>Roman Urdu</button></div>
            </div>
            <div className="demo-guide panel">
              <div className="guide-title"><span className="guide-star">✳</span><div><span className="section-kicker">QUICK DEMO</span><h3>How to demonstrate</h3></div></div>
              <div className="guide-steps"><div><span>01</span><p>Frame one hand in the camera.</p></div><div><span>02</span><p>Hold a supported pose steady.</p></div><div><span>03</span><p>Switch language or open vocabulary.</p></div></div>
              <button className="text-button" onClick={() => setHelpOpen(true)}>See the gesture guide <span>→</span></button>
            </div>
          </div>
        </section>
        {!exhibition && <section className="feature-row"><article><span className="feature-icon mint">◌</span><div><b>On-device AI hand tracking</b><small>21 landmarks detected locally</small></div></article><article><span className="feature-icon gold">Aa</span><div><b>English + Urdu</b><small>Urdu script and Roman fallback</small></div></article><article><span className="feature-icon violet">♪</span><div><b>Speech support</b><small>Uses voices available on your device</small></div></article><button className="button button-outline" onClick={() => { if (!document.fullscreenElement) document.documentElement.requestFullscreen?.(); setExhibition(true); }}>⛶ Exhibition view</button></section>}
      </>}

      {view === "vocabulary" && !exhibition && <section className="content-section">
        <div className="section-intro"><div><span className="section-kicker">64 PHRASES · 7 CATEGORIES</span><h1>Vocabulary browser</h1><p>Browse every phrase. Demo tags show which items have an immediate geometry rule.</p></div><button className="button button-outline" onClick={() => setView("translate")}>Back to translator</button></div>
        <div className="vocab-tools"><label className="search-box"><span>⌕</span><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} placeholder="Search English, Urdu, Roman Urdu…" aria-label="Search vocabulary" /></label><select value={category} onChange={(event) => { setCategory(event.target.value); setPage(0); }} aria-label="Filter by category">{categories.map((name) => <option key={name}>{name}</option>)}</select><span className="result-count">{filtered.length} phrases</span></div>
        <div className="vocab-grid">{visibleItems.map((item) => <button key={item.id} className={`vocab-card panel ${selected?.id === item.id ? "chosen" : ""}`} onClick={() => { setSelected(item); acceptWord(item, "vocabulary", item.demoAvailable ? "Vocabulary selected · camera demo supported" : "Vocabulary Mode — training data required for camera recognition"); }}><span className="vocab-category">{item.category}</span><strong>{item.english}</strong><span className="vocab-urdu" dir="rtl">{item.urdu}</span><small>{item.romanUrdu}</small><span className={item.demoAvailable ? "availability demo" : "availability training"}>{item.demoAvailable ? "● Demo gesture" : "Training data required for camera recognition"}</span><span className="card-speak">♪</span></button>)}</div>
        <div className="pagination"><button disabled={page === 0} onClick={() => setPage((value) => Math.max(0, value - 1))}>← Previous</button><span>Page {page + 1} of {pageCount}</span><button disabled={page + 1 >= pageCount} onClick={() => setPage((value) => Math.min(pageCount - 1, value + 1))}>Next →</button></div>
      </section>}

      {view === "training" && !exhibition && <section className="content-section">
        <div className="section-intro"><div><span className="section-kicker">BUILD FROM REAL EXAMPLES</span><h1>Training data</h1><p>Collect normalized hand landmarks for any vocabulary item. SignBridge saves nothing until you confirm a sample.</p></div><span className="privacy-pill">⌑ Local storage · no camera images</span></div>
        <div className="training-layout"><div className="panel training-card"><h2>Save one landmark sample</h2><p>Start the camera on the Translate screen, choose a phrase, show its sign, then save a frame here.</p><label>Vocabulary item<select value={selected?.id || ""} onChange={(event) => setSelected(vocabulary.find((item) => item.id === event.target.value) || null)}><option value="">Choose a phrase</option>{vocabulary.map((item) => <option key={item.id} value={item.id}>{item.english} · {item.category}</option>)}</select></label><label>Participant name <span className="optional">optional</span><input value={participant} onChange={(event) => setParticipant(event.target.value)} placeholder="Anonymous if left blank" /></label><label className="consent-row"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} /><span>I agree to save this landmark sample to the local SignBridge training dataset. No image or video is saved.</span></label><button className="button button-primary" onClick={saveExample} disabled={connection !== "online"}>Save current hand sample</button><div className="inline-message" role="status">{saveMessage || (connection === "online" ? (lastFeatures ? "A hand sample is ready." : "Turn on the camera and show a hand first.") : "Connect the local backend to save training data.")}</div></div><div className="panel training-card"><span className="section-kicker">MODEL STATUS</span><h2>{modelInfo.available ? "Trained model available" : "Demo recognition active"}</h2><p>{modelInfo.available ? `${modelInfo.model_name || "Classifier"} · ${modelInfo.examples || 0} examples · ${modelInfo.classes?.length || 0} classes` : "The camera demo uses rules. A learned model appears after enough collected examples are trained."}</p><div className="count-list">{vocabulary.slice(0, 8).map((item) => <div key={item.id}><span>{item.english}</span><b>{counts[item.id] || 0}</b></div>)}</div><button className="button button-outline" onClick={() => setView("report")}>View training report</button></div></div>
      </section>}

      {view === "report" && !exhibition && <section className="content-section">
        <div className="section-intro"><div><span className="section-kicker">TRANSPARENT EVALUATION</span><h1>Model report</h1><p>Recognition results are reported only after training and validation on real collected examples.</p></div><button className="button button-outline" onClick={() => { window.location.href = `${API}/confusion-matrix.csv`; }}>Download confusion matrix</button></div>
        <div className="report-summary panel"><div><span className="section-kicker">CURRENT MODE</span><h2>{modelInfo.available ? "AI Trained Mode" : "AI Demo Mode"}</h2><p>{modelInfo.available ? `Selected: ${modelInfo.model_name || "trained classifier"}` : "MediaPipe tracks the hand; geometry rules map a small pose set. No custom model is currently available."}</p></div><div className="report-stat"><strong>{modelInfo.accuracy == null ? "—" : `${(modelInfo.accuracy * 100).toFixed(1)}%`}</strong><small>{modelInfo.accuracy == null ? "No measured score" : "Measured validation accuracy"}</small></div><div className="report-stat"><strong>{modelInfo.examples || 0}</strong><small>training examples used</small></div></div>
        <div className="panel report-body"><div className="panel-heading"><div><span className="section-kicker">EVALUATION DETAILS</span><h2>Training report</h2></div><a className="text-button" href={`${API}/training-data.csv`}>Download training CSV →</a></div>{report ? <pre>{report}</pre> : <div className="empty-report">{connection === "online" ? "No trained model report exists yet. Use Training and run the training command when enough real data has been collected." : "The backend is offline. Demo recognition and the vocabulary remain available on this device."}</div>}</div>
      </section>}

      {!exhibition && <footer className="page-footer"><span>SignBridge · Local-first demonstration prototype</span><span>Camera frames are not saved. Training samples require explicit consent.</span><button onClick={() => setHelpOpen(true)}>Privacy & help</button></footer>}
    </main>

    {helpOpen && <div className="modal-scrim" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setHelpOpen(false); }}><section className="help-modal panel" role="dialog" aria-modal="true" aria-labelledby="help-title"><button className="modal-close" onClick={() => setHelpOpen(false)} aria-label="Close help">×</button><span className="section-kicker">A QUICK GUIDE</span><h2 id="help-title">How to use SignBridge</h2><div className="help-columns"><div><h3>Demo gestures</h3><ul><li>Open, spread palm → Hello</li><li>Flat, close fingers → Stop</li><li>Fist → No · thumbs up/down → Yes/Bad</li><li>V sign → Please · index up → Wait</li><li>OK → Good · call-me pose → Phone</li><li>Three fingers → Thank you · four → Water</li><li>Five close fingers → Emergency</li><li>Horizontal point → Help</li></ul></div><div><h3>Keyboard</h3><ul><li>E English · U Urdu · L switch</li><li>R repeat · V voice on/off</li><li>M switch available recognition mode</li><li>B opens vocabulary · H help · Q quit</li><li>In vocabulary, type to search; Escape closes it</li></ul><h3>Privacy</h3><p>Browser hand images are processed here and are not sent to Google or saved. MediaPipe Tasks may send aggregate performance and usage metrics to Google. Training landmarks are saved only after you check consent and press Save.</p></div></div><button className="button button-primary" onClick={() => setHelpOpen(false)}>Got it</button></section></div>}
    {metricsNoticeOpen && <div className="modal-scrim" role="presentation"><section className="help-modal panel" role="dialog" aria-modal="true" aria-labelledby="metrics-title"><span className="section-kicker">CAMERA PRIVACY</span><h2 id="metrics-title">Before enabling hand tracking</h2><p>Hand images are processed in this browser and are not sent to Google. MediaPipe Tasks may send aggregate performance and usage metrics to Google while online. SignBridge does not save camera images or video.</p><label className="consent-row"><input type="checkbox" checked={metricsNoticeChecked} onChange={(event) => setMetricsNoticeChecked(event.target.checked)} /><span>I understand and agree to use MediaPipe hand tracking with these metrics.</span></label><div className="result-actions"><button className="button button-quiet" onClick={() => setMetricsNoticeOpen(false)}>Not now</button><button className="button button-primary" disabled={!metricsNoticeChecked} onClick={acceptMetricsNotice}>Agree and enable camera</button></div></section></div>}
    {exhibition && <button className="exit-exhibition" onClick={() => { setExhibition(false); if (document.fullscreenElement) document.exitFullscreen?.(); }}>Exit exhibition view · Esc</button>}
  </div>;
}
