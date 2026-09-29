import { defineConfig, devices } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

// App clínica de demostración: pública y sin API, alcanza con el servidor de Vite.
export default defineConfig({
  testDir: "./e2e", testMatch: ["app-clinica.spec.js"], workers: 1,
  reporter: "list", timeout: 30000, expect: { timeout: 7000 },
  outputDir: join(tmpdir(), "salud-app-clinica"),
  use: { baseURL: "http://127.0.0.1:5189", trace: "retain-on-failure", screenshot: "only-on-failure", locale: "es-AR", timezoneId: "America/Argentina/Buenos_Aires" },
  webServer: { command: "npm run dev -- --host 127.0.0.1 --port 5189 --strictPort", url: "http://127.0.0.1:5189", reuseExistingServer: false, timeout: 30000 },
  projects: [
    { name: "celular", use: { ...devices["Pixel 7"] } },
    { name: "escritorio", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
  ],
});
