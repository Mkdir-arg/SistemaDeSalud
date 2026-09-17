import { defineConfig, devices } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Contratos HTTP simulados: nunca crea usuarios, pacientes ni gastos en la demo.
export default defineConfig({
  testDir: "./e2e", testMatch: ["finanzas-ui.spec.js", "finanzas-dinero.spec.js", "finanzas-*-demo.spec.js"], workers: 1,
  reporter: "list", timeout: 30000, expect: { timeout: 7000 },
  outputDir: join(tmpdir(), "sistemadesalud-finanzas-ui-20260914"),
  use: { baseURL: process.env.SALUD_URL || "http://localhost:8090", trace: "retain-on-failure", screenshot: "only-on-failure", locale: "es-AR", timezoneId: "America/Argentina/Buenos_Aires" },
  projects: [{ name: "contratos-ui", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
});
