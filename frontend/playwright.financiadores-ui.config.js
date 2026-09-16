import { defineConfig, devices } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Servidor local de UI, API totalmente interceptada. Sin hospitales ni datos reales.
export default defineConfig({
  testDir: "./e2e", testMatch: ["financiadores-ui.spec.js", "cobertura-clinica-ui.spec.js", "seguimiento-cobros-ui.spec.js", "padron-cobertura-ui.spec.js", "autorizaciones-ui.spec.js"], workers: 1,
  reporter: "list", timeout: 30000, expect: { timeout: 7000 },
  outputDir: join(tmpdir(), "cauce-financiadores-ui"),
  use: { baseURL: "http://127.0.0.1:5187", trace: "retain-on-failure", screenshot: "only-on-failure", locale: "es-AR", timezoneId: "America/Argentina/Buenos_Aires" },
  webServer: { command: "npm run dev -- --host 127.0.0.1 --port 5187 --strictPort", url: "http://127.0.0.1:5187", reuseExistingServer: false, timeout: 30000 },
  projects: [{ name: "portal-mock", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});
