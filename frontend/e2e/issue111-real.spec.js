import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

test.skip(!process.env.HEN_111_REAL_PASSWORD || !process.env.HEN_111_REAL_METADATA,
  "Requiere datos ficticios y credenciales del PostgreSQL aislado autorizado.");
const datos = process.env.HEN_111_REAL_METADATA
  ? JSON.parse(readFileSync(process.env.HEN_111_REAL_METADATA, "utf8")) : {};

async function autenticar(request, email) {
  const respuesta = await request.post("/api/auth/token/", {
    data: { email, password: process.env.HEN_111_REAL_PASSWORD },
  });
  expect(respuesta.status()).toBe(200);
  const { access } = await respuesta.json();
  return { Authorization: `Bearer ${access}` };
}

async function sesion(page, headers, institucion = datos.central, simulacion = null) {
  await page.addInitScript(({ token, inst, sim }) => {
    sessionStorage.setItem("salud.access", token);
    if (sim) sessionStorage.setItem("salud.simulacion", JSON.stringify(sim));
    if (inst) localStorage.setItem("salud.institucion", JSON.stringify(inst));
  }, { token: headers.Authorization.slice(7), inst: institucion, sim: simulacion });
}

test("comprador inicia sesión, vuelve a Instituciones y reingresa en Central", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel(/Email/).fill("test@salud.local");
  await page.getByLabel(/^Contraseña/).fill(process.env.HEN_111_REAL_PASSWORD);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/\/login/);
  await page.goto("/directorio");
  await page.getByRole("row").filter({ has: page.getByText("Hospital Central", { exact: true }) }).getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page.getByRole("button", { name: "Volver al directorio" })).toBeVisible();
  await page.getByRole("button", { name: "Volver al directorio" }).click();
  await expect(page.getByRole("heading", { name: "Instituciones", exact: true })).toBeVisible();
  await page.getByRole("row").filter({ has: page.getByText("Hospital Central", { exact: true }) }).getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).toHaveURL(/\/inicio/);
});

test("solicitud manual, ficha, aprobación y traza hospitalaria persistidas", async ({ page, request }) => {
  const headers = await autenticar(request, datos.operador);
  const base = `/api/autorizaciones-cobertura/`;
  const entrada = { afiliado: datos.afiliado, institucion: datos.central.id,
    comun: datos.comun, cantidad: 1, justificacion: "Ensayo aislado del issue 111",
    clave: crypto.randomUUID() };
  const crear = await request.post(`${base}manual/?financiador=${datos.financiador}`, { headers, data: entrada });
  expect(crear.status()).toBe(201);
  const solicitud = await crear.json();
  const ficha = await request.get(`/api/financiadores/${datos.financiador}/ficha-afiliado-autorizaciones/?afiliado=${datos.afiliado}`, { headers });
  expect(ficha.status()).toBe(200);
  expect((await ficha.json()).results.some((s) => s.id === solicitud.id && s.prestacion_nombre)).toBe(true);
  await sesion(page, headers);
  await page.goto(`/financiadores/padron/${datos.afiliado}?financiador=${datos.financiador}`);
  await expect(page.getByRole("heading", { name: "Ficha del afiliado", exact: true })).toBeVisible();
  const hoy = new Date().toLocaleDateString("en-CA", { timeZone: "America/Argentina/Buenos_Aires" });
  const resolver = await request.post(`${base}${solicitud.id}/resolver/?financiador=${datos.financiador}`, { headers,
    data: { revision: solicitud.revision, decision: "aprobar", motivo: "Validación administrativa del ensayo",
      evidencia: "Orden ficticia del entorno aislado", cantidad_aprobada: 1,
      vigencia_desde: hoy, vigencia_hasta: hoy, clave: crypto.randomUUID() } });
  expect(resolver.status()).toBe(200);
  const hospital = await autenticar(request, "admin.central@hospital.gob.ar");
  const auditoria = await request.get(`/api/accesos-clinicos/?institucion=${datos.central.id}&recurso=financiadores-ficha-afiliado`, { headers: hospital });
  expect(auditoria.status()).toBe(200);
  expect((await auditoria.json()).results.some((a) => a.objeto_id === String(solicitud.id) && a.documento === datos.documento)).toBe(true);
});

test("perfil simulado conserva menú; paciente fuera del contexto devuelve 404", async ({ page, request }) => {
  const root = await autenticar(request, "admin@salud.local");
  const iniciar = await request.post("/api/simulaciones/", { headers: root,
    data: { ambito: "institucion", rol: "admin", institucion: datos.central.id } });
  expect(iniciar.status()).toBe(201);
  const sim = await iniciar.json();
  await sesion(page, root, datos.central, sim);
  await page.goto("/inicio");
  const direccion = page.getByText("DIRECCIÓN", { exact: true });
  await expect(direccion).toBeVisible();
  expect((await direccion.boundingBox()).y).toBeLessThan((await page.getByText("OPERACIÓN", { exact: true }).boundingBox()).y);
  const extranjera = await request.get(`/api/ciudadanos/${datos.paciente}/?institucion=${datos.otra.id}`, {
    headers: root });
  expect(extranjera.status()).toBe(404);
  await page.evaluate((inst) => {
    sessionStorage.removeItem("salud.simulacion");
    localStorage.setItem("salud.institucion", JSON.stringify(inst));
  }, datos.otra);
  // El script inicial conserva el contexto en las navegaciones de documento.
  await page.addInitScript((inst) => {
    sessionStorage.removeItem("salud.simulacion");
    localStorage.setItem("salud.institucion", JSON.stringify(inst));
  }, datos.otra);
  await page.goto(`/pacientes/${datos.paciente}`);
  await expect(page.getByText("Paciente no disponible en esta institución", { exact: true })).toBeVisible();
});

test("consulta clínica simulada devuelve entradas firmadas y audita al autor real", async ({ request }) => {
  const root = await autenticar(request, "admin@salud.local");
  const inicio = await request.post("/api/simulaciones/", { headers: root,
    data: { ambito: "financiador", rol: "operador", financiador: datos.financiador } });
  expect(inicio.status()).toBe(201);
  const sim = await inicio.json();
  const respuesta = await request.post(`/api/financiadores/${datos.financiador}/ficha-historia-evoluciones/`, {
    headers: { ...root, "X-HEN-Simulacion": sim.id },
    data: { afiliado: datos.afiliadoClinico, caso: datos.casoClinico, motivo: "Auditoría clínica del ensayo aislado" } });
  expect(respuesta.status()).toBe(200);
  expect((await respuesta.json()).length).toBeGreaterThan(0);
  const auditoria = await request.get(`/api/accesos-clinicos/?institucion=${datos.central.id}&recurso=financiadores-evoluciones-caso`, { headers: root });
  expect(auditoria.status()).toBe(200);
  const acceso = (await auditoria.json()).results.find((a) => a.motivo === "Auditoría clínica del ensayo aislado");
  expect(acceso.usuario_email).toBe("admin@salud.local");
});

test("agendas sembradas de 15 y 20 minutos mantienen bloques legibles", async ({ page, request }) => {
  const root = await autenticar(request, "admin@salud.local");
  await sesion(page, root);
  const respuesta = await request.get(`/api/agendas/?institucion=${datos.central.id}&page_size=100`, { headers: root });
  expect(respuesta.status()).toBe(200);
  const agendas = (await respuesta.json()).results.filter((a) => /Vega|Méndez/.test(a.nombre));
  expect(agendas).toHaveLength(2);
  for (const agenda of agendas) {
    await page.goto(`/agenda?agenda=${agenda.id}&fecha=2026-10-05&vista=semana`);
    const bloques = page.locator("[data-horario]");
    await expect(bloques.first()).toBeVisible();
    const cajas = await bloques.evaluateAll((els) => els.map((el) => {
      const r = el.getBoundingClientRect();
      return { x: r.x, top: r.top, bottom: r.bottom, alto: r.height,
        texto: el.querySelector("span").getBoundingClientRect().height };
    }));
    const anteriores = new Map();
    for (const caja of cajas) {
      expect(caja.alto).toBeGreaterThanOrEqual(caja.texto);
      if (anteriores.has(caja.x)) expect(caja.top).toBeGreaterThanOrEqual(anteriores.get(caja.x));
      anteriores.set(caja.x, caja.bottom);
    }
    await bloques.first().click();
    await expect.poll(() => new URL(page.url()).searchParams.get("vista")).toBe("dia");
  }
});

test("repartos informa el latido del worker real", async ({ page, request }) => {
  const root = await autenticar(request, "admin@salud.local");
  const mes = new Date().toLocaleDateString("en-CA", { timeZone: "America/Argentina/Buenos_Aires" }).slice(0, 7);
  const response = await request.get(`/api/procesamiento-finanzas/?institucion=${datos.central.id}&periodo_economico=${mes}-01`, { headers: root });
  expect(response.status()).toBe(200);
  const estado = await response.json();
  expect(estado.worker_activo).toBe(true);
  expect(estado.ultimo_latido).toBeTruthy();
  expect(estado.mensaje).not.toContain("no registra actividad reciente");
  await sesion(page, root);
  await page.goto(`/finanzas?mes=${mes}&tab=resumen`);
  await expect(page.getByLabel("Resumen de finanzas y costos", { exact: true })).toBeVisible();
  await expect(page.getByText(/El servicio de repartos no registra actividad reciente/)).toHaveCount(0);
});

test("Inicio del financiador completa sus lecturas paralelas auditadas", async ({ page, request }) => {
  const headers = await autenticar(request, datos.operador);
  await sesion(page, headers, null);
  const respuestas = [];
  page.on("response", (r) => {
    const path = new URL(r.url()).pathname;
    if (path === "/api/autorizaciones-cobertura/" || path.endsWith("/actividad/")) respuestas.push(r.status());
  });
  await page.goto(`/financiadores/inicio?financiador=${datos.financiador}`);
  await expect.poll(() => respuestas.length).toBeGreaterThanOrEqual(10);
  expect(respuestas.every((status) => status === 200)).toBe(true);
  await expect(page.getByRole("heading", { name: "Prestaciones realizadas por mes", exact: true })).toBeVisible();
});
