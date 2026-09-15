import { defineConfig, devices } from "@playwright/test";

// Recorrido de lectura para la demo aislada de Finanzas; no requiere ni siembra
// el escenario clínico de volumen usado por la suite general.
export default defineConfig({
  testDir: "./e2e", testMatch: "finanzas-feedback.spec.js", workers: 1,
  reporter: "list", timeout: 45_000, expect: { timeout: 10_000 },
  use: { baseURL: process.env.CAUCE_URL || "http://localhost:8090", trace: "retain-on-failure", screenshot: "only-on-failure", locale: "es-AR", timezoneId: "America/Argentina/Buenos_Aires" },
  projects: [{ name: "escritorio", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});
