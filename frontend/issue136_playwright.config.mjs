import { defineConfig } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

const puerto = Number(process.env.ISSUE136_UI_PORT || 5196);

export default defineConfig({
  testDir: "./e2e", testMatch: ["issue136_geografia.spec.js", "issue136_formularios.spec.js"], workers: 1,
  reporter: "list", timeout: 30000,
  outputDir: join(tmpdir(), "salud-issue136-ui"),
  use: { baseURL: `http://127.0.0.1:${puerto}`, browserName: "chromium", locale: "es-AR", screenshot: "only-on-failure" },
  webServer: { command: "node node_modules/vite/bin/vite.js --config issue136_vite.config.mjs", url: `http://127.0.0.1:${puerto}`, reuseExistingServer: false, timeout: 30000 },
});
