import { defineConfig, devices } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Requiere el backend de pruebas del issue en 8119 y datos ficticios ya sembrados.
export default defineConfig({
  testDir: "./e2e", testMatch: "issue111-real.spec.js", workers: 1,
  timeout: 45000, expect: { timeout: 10000 }, reporter: "list",
  outputDir: join(tmpdir(), "hen-issue111-real"),
  use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:5219",
    locale: "es-AR", timezoneId: "America/Argentina/Buenos_Aires",
    // Evitar capturar credenciales/tokens de sesiones reales en trazas.
    trace: "off", screenshot: "only-on-failure" },
  webServer: { command: "npm run dev -- --host 127.0.0.1 --port 5219 --strictPort",
    url: "http://127.0.0.1:5219", reuseExistingServer: false,
    env: { VITE_PROXY_TARGET: "http://127.0.0.1:8119" } },
});
