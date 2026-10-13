import { defineConfig, devices } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Solo harness ficticio; no setup/seed ni conexión a API/backend/demo.
export default defineConfig({
  testDir: "./e2e", testMatch: "padron-tabla.spec.js", workers: 1, retries: 0,
  reporter: "list", timeout: 30000, expect: { timeout: 7000 },
  outputDir: join(tmpdir(), "salud-padron-tabla-ui"),
  use: { baseURL: "http://127.0.0.1:5193", trace: "off", screenshot: "only-on-failure", locale: "es-AR" },
  webServer: { command: "npm run dev -- --host 127.0.0.1 --port 5193 --strictPort", url: "http://127.0.0.1:5193", reuseExistingServer: false, timeout: 30000 },
  projects: [{ name: "componente-ficticio", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});
