import { defineConfig, devices } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Sólo el proyecto aislado previamente autorizado, preparado y servido.
// Sin globalSetup, mocks, servidor automático ni selección por otros suites.
export default defineConfig({
  testDir: "./e2e", testMatch: "issue130-padron-real.spec.js",
  workers: 1, fullyParallel: false, retries: 0,
  timeout: 60000, expect: { timeout: 10000 }, reporter: "list",
  outputDir: join(tmpdir(), "salud-padron130-real"),
  use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:8230",
    locale: "es-AR", timezoneId: "America/Argentina/Buenos_Aires",
    trace: "off", video: "off", screenshot: "only-on-failure" },
});
