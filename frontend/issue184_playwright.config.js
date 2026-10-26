import { defineConfig, devices } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Corte integrado #186 + #184. Sólo UI ficticia y API interceptada.
export default defineConfig({
  testDir: "./e2e",
  testMatch: ["issue184_padron.spec.js", "issue184_ficha.spec.js", "padron-tabla.spec.js", "financiadores-ui.spec.js"],
  workers: 1, retries: 0, reporter: "list", timeout: 30000, expect: { timeout: 7000 },
  outputDir: join(tmpdir(), "salud-issue184-ui"),
  use: { baseURL: "http://127.0.0.1:5195", trace: "off", screenshot: "only-on-failure", locale: "es-AR", timezoneId: "America/Argentina/Buenos_Aires" },
  webServer: { command: "npm run dev -- --host 127.0.0.1 --port 5195 --strictPort", url: "http://127.0.0.1:5195", reuseExistingServer: false, timeout: 30000 },
  projects: [{ name: "issue184-integrado", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});
