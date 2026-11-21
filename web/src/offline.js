// Registers the service worker (public/sw.js) on secure pages of the built site, and lets the page ask it
// to save every file for offline use. Development builds never register it.
export function registerServiceWorker() {
  if (!import.meta.env?.PROD || typeof navigator === "undefined" || !("serviceWorker" in navigator) || !window.isSecureContext) return null;
  return navigator.serviceWorker.register(new URL("sw.js", document.baseURI), { scope: "./" }).catch(() => null);
}

// onUpdate({ type: "progress" | "cached" | "error", ... })
export async function saveForOffline(onUpdate) {
  const registration = await navigator.serviceWorker?.ready;
  if (!registration?.active) throw new Error("offline saving is not available in this browser");
  const listener = (event) => { if (event.data?.source === "signbridge-sw") { onUpdate(event.data); if (event.data.type !== "progress") navigator.serviceWorker.removeEventListener("message", listener); } };
  navigator.serviceWorker.addEventListener("message", listener);
  registration.active.postMessage({ type: "cache-all" });
}

export async function offlineSize() {
  try {
    const response = await fetch(new URL("precache.json", document.baseURI), { cache: "no-store" });
    return response.ok ? (await response.json()).total_bytes : null;
  } catch { return null; }
}
