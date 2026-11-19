// Where the website finds its own files and the SignBridge server.
//
// The same build must work at a site root (http://localhost:5173/) and under a sub-path
// (https://<user>.github.io/SignBridge/), so files are never fetched from "/..." directly.
// vite.config.js builds with base "./"; assetUrl() turns "models/x.task" into an absolute URL
// next to the current page. Workers get absolute URLs from the page, never relative ones.
//
// VITE_API_BASE: "/api" (default) when the local server runs next to the website; "none" for the
// static website on GitHub Pages, which has no server (the app then runs fully in the browser).

export function assetUrl(path, baseUrl = import.meta.env?.BASE_URL ?? "/", pageUrl = globalThis.location?.href ?? "http://localhost/") {
  const relative = String(path).replace(/^\/+/, "");
  return new URL(relative, new URL(baseUrl, pageUrl)).href;
}

export const API_BASE = import.meta.env?.VITE_API_BASE ?? "/api";
export const HAS_SERVER = API_BASE !== "none" && API_BASE !== "";
