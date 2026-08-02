import { defineConfig, devices } from "@playwright/test";

/**
 * Suite end-to-end de Cauce.
 *
 * Es la red de seguridad de la migración: quedan ~28 pantallas por pasar a la
 * fundación nueva y estos recorridos son lo que avisa si una de esas migraciones
 * rompe algo que ya funcionaba.
 *
 * Requiere los dos servidores levantados y la demo sembrada:
 *   backend/  python manage.py seed_volumen --rehacer && python manage.py runserver
 *   frontend/ npm run dev
 *
 * Se corre con `npm run e2e`.
 */
export default defineConfig({
  testDir: "./e2e",
  // Los tests operan sobre la MISMA base de datos: llamar a un paciente cambia
  // la fila que ve otro test. Se corren en serie a propósito.
  workers: 1,
  fullyParallel: false,
  reporter: [["list"]],
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: process.env.CAUCE_URL || "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    locale: "es-AR",
    timezoneId: "America/Argentina/Buenos_Aires",
  },
  projects: [
    { name: "escritorio", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
  ],
  globalSetup: "./e2e/setup.js",
});
