import { defineConfig, devices } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Requiere API/PostgreSQL y Vite aislados ya iniciados. No levanta servicios,
// carga datos ni acepta una URL remota desde variables del entorno.
export default defineConfig({
  testDir: "./e2e", testMatch: "importacion-real.spec.js", workers: 1,
  fullyParallel: false, retries: 0, timeout: 120000,
  expect: { timeout: 15000 }, reporter: "list",
  outputDir: join(tmpdir(), "salud-importacion182-resultados"),
  use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:5189",
    locale: "es-AR", timezoneId: "America/Argentina/Buenos_Aires",
    trace: "off", video: "off", screenshot: "only-on-failure" },
});
