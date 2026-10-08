import { defineConfig, devices } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Portal del paciente (#120): la API `/api/mi/*` se intercepta en cada prueba,
// así que alcanza con el servidor de Vite.
export default defineConfig({
  testDir: "./e2e", testMatch: ["portal-cuenta.spec.js"], workers: 1,
  reporter: "list", timeout: 30000, expect: { timeout: 7000 },
  outputDir: join(tmpdir(), "salud-portal"),
  use: { baseURL: "http://127.0.0.1:5191", trace: "retain-on-failure", screenshot: "only-on-failure", locale: "es-AR", timezoneId: "America/Argentina/Buenos_Aires" },
  webServer: { command: "npm run dev -- --host 127.0.0.1 --port 5191 --strictPort", url: "http://127.0.0.1:5191", reuseExistingServer: false, timeout: 30000 },
  projects: [
    // Móvil primero: el ancho más angosto que se soporta.
    { name: "celular", use: { ...devices["Pixel 7"], viewport: { width: 375, height: 740 } } },
    { name: "escritorio", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
  ],
});
