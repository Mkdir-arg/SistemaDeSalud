import { defineConfig, devices } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Manual: API/PostgreSQL y Vite ya iniciados. CI: gestiona sólo los servidores
// del escenario explícitamente aislado, sin reutilizar procesos de otra sesión.
const aislado = process.env.SALUD_IMPORTACION_E2E_AISLADO === "1";
export default defineConfig({
  testDir: "./e2e", testMatch: "importacion-real.spec.js", workers: 1,
  fullyParallel: false, retries: 0, timeout: 120000,
  expect: { timeout: 15000 }, reporter: "list",
  outputDir: join(tmpdir(), "salud-importacion182-resultados"),
  use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:5189",
    locale: "es-AR", timezoneId: "America/Argentina/Buenos_Aires",
    trace: "off", video: "off", screenshot: "only-on-failure" },
  webServer: aislado ? [
    { command: "python tests/importacion_real.py servidor", cwd: "../backend",
      url: "http://127.0.0.1:8232/api/health/", reuseExistingServer: false, timeout: 60000 },
    { command: "npm run dev -- --host 127.0.0.1 --port 5189 --strictPort",
      env: { VITE_PROXY_TARGET: "http://127.0.0.1:8232" },
      url: "http://127.0.0.1:5189", reuseExistingServer: false, timeout: 60000 },
  ] : undefined,
});
