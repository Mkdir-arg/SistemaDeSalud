import { defineConfig, devices } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Destinos fijos y exclusivos: no reutilizar servidores ni bases de otra sesión.
const entorno = {
  SALUD_ISSUE43_AISLADO: "1", ENTORNO: "desarrollo", PYTHON_DOTENV_DISABLED: "1",
  DJANGO_SETTINGS_MODULE: "config.settings_issue43_test", PYTHONIOENCODING: "utf-8",
};
export default defineConfig({
  testDir: "./e2e", testMatch: "issue43-finanzas-real.spec.js",
  workers: 1, fullyParallel: false, retries: 0, timeout: 90000,
  expect: { timeout: 15000 }, reporter: "list",
  outputDir: join(tmpdir(), "salud-issue43-playwright"),
  use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:5243", actionTimeout: 15000,
    locale: "es-AR", timezoneId: "America/Argentina/Buenos_Aires",
    trace: "off", video: "off", screenshot: "only-on-failure" },
  webServer: [
    { command: "python manage.py runserver 127.0.0.1:8143 --noreload --settings=config.settings_issue43_test",
      cwd: "../backend", env: entorno, url: "http://127.0.0.1:8143/api/health/",
      reuseExistingServer: false, timeout: 60000 },
    { command: "npm run dev -- --host 127.0.0.1 --port 5243 --strictPort",
      env: { VITE_PROXY_TARGET: "http://127.0.0.1:8143" },
      url: "http://127.0.0.1:5243", reuseExistingServer: false, timeout: 60000 },
  ],
});
