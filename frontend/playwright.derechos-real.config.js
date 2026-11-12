import { defineConfig, devices } from "@playwright/test";
import { join } from "node:path";
import { tmpdir } from "node:os";

const aislado = process.env.SALUD_DERECHOS_E2E_AISLADO === "1";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "novedades-real.spec.js",
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 120000,
  expect: { timeout: 15000 },
  reporter: "list",
  outputDir: join(tmpdir(), "salud-derechos-real-resultados"),
  use: {
    baseURL: "http://127.0.0.1:5179",
    locale: "es-AR",
    timezoneId: "America/Argentina/Buenos_Aires",
    trace: "off",
    video: "off",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-chromium", use: { ...devices["Pixel 7"] } },
  ],
  webServer: aislado ? [
    {
      command: "python -B manage.py runserver 127.0.0.1:8231 --noreload",
      cwd: "../backend",
      env: {
        DJANGO_SETTINGS_MODULE: "config.settings_financiadores_postgres_test",
        DJANGO_DEBUG: "true",
        PYTHON_DOTENV_DISABLED: "1",
      },
      url: "http://127.0.0.1:8231/api/health/",
      reuseExistingServer: false,
      timeout: 60000,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5179 --strictPort",
      env: { VITE_PROXY_TARGET: "http://127.0.0.1:8231" },
      url: "http://127.0.0.1:5179",
      reuseExistingServer: false,
      timeout: 60000,
    },
  ] : undefined,
});
