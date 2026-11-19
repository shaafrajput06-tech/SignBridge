# Phase 7 — Clients: offline, on-device, accessible

OBJECTIVE
The same recogniser, tiers and translation run fully on each device, fast, offline and accessible.

TASKS
1. Web: installable PWA; self-host all WASM and models; MediaPipe telemetry off or disclosed and
   opt-in (F9); onnxruntime-web with WebGPU and WASM fallback; inference in a Web Worker.
2. Flutter: on-device MediaPipe + LiteRT; no server needed for recognition; the local-server mode
   stays as an option. Build and test in CI on Android; iOS where a Mac runner exists.
3. Desktop: replace the OpenCV window with the web UI served locally (one UI to maintain), or keep
   OpenCV as a fallback; decide and record why.
4. UX for Deaf-first use: large captions, high contrast, Urdu RTL, haptic and visual (not audio) cues,
   signing-space guide overlay, lighting and framing coach, confidence shown in plain words.
5. Performance budgets enforced in CI with recorded device profiles.

ACCEPTANCE GATE
- Recognition works in airplane mode on web (installed PWA), Android and desktop.
- >= 24 fps landmarking and <= 300 ms sign-to-text on a mid-range Android phone (name the device).
- WCAG 2.2 AA checks pass on the web UI; screen-reader labels on all controls.
- Same input clip gives the same top-1 gloss on Python, web and Flutter (parity on 200 clips).
