import { defineConfig, devices } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Puerto y artefactos propios: otros worktrees también prueban la UI en 5187.
export default defineConfig({
  testDir: "./e2e",
  testMatch: ["issue111-ui.spec.js", "inicio-ui.spec.js", "autorizaciones-ui.spec.js", "pacientes-ui.spec.js", "landing-ui.spec.js", "simulacion-ui.spec.js"],
  workers: 1, reporter: "list", timeout: 30000, expect: { timeout: 7000 },
  outputDir: join(tmpdir(), "hen-issue111-ui"),
  use: { baseURL: "http://127.0.0.1:5199", trace: "retain-on-failure", screenshot: "only-on-failure", locale: "es-AR", timezoneId: "America/Argentina/Buenos_Aires" },
  webServer: { command: "npm run dev -- --host 127.0.0.1 --port 5199 --strictPort", url: "http://127.0.0.1:5199", reuseExistingServer: false, timeout: 30000 },
  projects: ["claro", "oscuro"].map((tema) => ({ name: tema, use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 }, colorScheme: tema === "oscuro" ? "dark" : "light" } })),
});
