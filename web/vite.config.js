import { defineConfig, loadEnv } from "vite";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webDir = path.dirname(fileURLToPath(import.meta.url));
const projectDir = path.resolve(webDir, "..");

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, projectDir, "");
  const apiPort = Number(env.SIGNBRIDGE_API_PORT || 8000);
  const webPort = Number(env.SIGNBRIDGE_WEB_PORT || 5173);
  const cert = env.SIGNBRIDGE_TLS_CERT;
  const key = env.SIGNBRIDGE_TLS_KEY;
  const https = cert && key ? { cert: readFileSync(path.resolve(projectDir, cert)), key: readFileSync(path.resolve(projectDir, key)) } : undefined;
  const proxy = { "/api": { target: `http://127.0.0.1:${apiPort}`, changeOrigin: true } };
  return {
    // "./": relative asset URLs, so one build works at a site root and under a sub-path
    // such as https://<user>.github.io/SignBridge/ (see src/paths.js).
    base: "./",
    envDir: projectDir,
    server: { host: "0.0.0.0", port: webPort, strictPort: true, https, proxy },
    preview: { host: "0.0.0.0", port: 4173, https, proxy },
    // bench.html is the capture v2 frame-rate benchmark (Phase 1); asl-selftest.html checks ASL mode (Stage 2).
    build: { rollupOptions: { input: { main: path.resolve(webDir, "index.html"), bench: path.resolve(webDir, "bench.html"), aslSelftest: path.resolve(webDir, "asl-selftest.html") } } },
  };
});
