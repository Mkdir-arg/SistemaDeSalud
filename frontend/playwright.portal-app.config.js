import { defineConfig, devices } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";

// App del paciente (#122) contra el backend REAL: nada se intercepta.
//
// Antes hay que cargar la base (desde `backend/`):
//   python manage.py migrate
//   python manage.py seed_guardia
//   python manage.py seed_portal_e2e --salida <archivo>.json
// y pasar ese archivo en PORTAL_E2E_ESCENARIO. Las pruebas confirman y cancelan
// turnos: para repetirlas, volvé a correr seed_portal_e2e (no duplica nada).
//
// Levanta su propio backend y su Vite. Con PORTAL_E2E_URL usa uno ya levantado.
//
// Límite de ingreso: cada corrida ingresa varias veces con la misma cuenta y el
// backend corta a las 10 por hora (portal_ingreso_email_ip, en settings.py); los
// contadores viven en la base (cache `portal`), así que sobreviven entre corridas.
// Por eso el backend que levanta esta config, y sólo ése, arranca con las tasas de
// ingreso altas (TASAS_E2E). No se limpian los contadores desde seed_portal_e2e
// porque eso no sirve con PORTAL_E2E_URL. Con PORTAL_E2E_URL, el backend externo
// tiene que arrancar con esas mismas variables si se va a repetir en la hora;
// nunca en un entorno real.
const API = Number(process.env.PORTAL_E2E_API_PORT || 8191);
const WEB = Number(process.env.PORTAL_E2E_WEB_PORT || 5192);
const externo = Boolean(process.env.PORTAL_E2E_URL);
const TASAS_E2E = {
  PORTAL_TASA_PORTAL_INGRESO_IP: "1000/hour",
  PORTAL_TASA_PORTAL_INGRESO_EMAIL_IP: "1000/hour",
  PORTAL_TASA_PORTAL_INGRESO_EMAIL: "1000/hour",
};

export default defineConfig({
  testDir: "./e2e", testMatch: ["portal-app.spec.js", "portal-contraste.spec.js"], workers: 1,
  reporter: "list", timeout: 45000, expect: { timeout: 7000 },
  outputDir: join(tmpdir(), "salud-portal-app"),
  use: {
    baseURL: process.env.PORTAL_E2E_URL || `http://127.0.0.1:${WEB}`,
    trace: "retain-on-failure", screenshot: "only-on-failure",
    locale: "es-AR", timezoneId: "America/Argentina/Buenos_Aires",
  },
  webServer: externo ? undefined : [
    {
      command: `python manage.py runserver 127.0.0.1:${API} --noreload`, cwd: "../backend", env: TASAS_E2E,
      url: `http://127.0.0.1:${API}/api/health/`, reuseExistingServer: false, timeout: 60000,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${WEB} --strictPort`,
      env: { VITE_PROXY_TARGET: `http://127.0.0.1:${API}` },
      url: `http://127.0.0.1:${WEB}`, reuseExistingServer: false, timeout: 30000,
    },
  ],
  projects: [
    // Las pruebas que modifican datos (@modifica) corren una sola vez, en el celular.
    { name: "celular", use: { ...devices["Pixel 7"], viewport: { width: 375, height: 740 } } },
    { name: "escritorio", grepInvert: /@modifica/, use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
  ],
});
