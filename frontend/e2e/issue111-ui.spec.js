import { expect, test } from "@playwright/test";

const lista = (results = []) => ({ count: results.length, next: null, previous: null, results });
const instituciones = [{ id: 1, nombre: "Hospital Central", activa: true, estado: "activa" }, { id: 2, nombre: "Hospital Norte", activa: true }];
const caps = ["turnos", "padron_admision", "historia_clinica", "auditoria", "supervision", "config_institucional", "casos_operar", "filas"];
const agenda = { id: 10, nombre: "Dr. Vega · Traumatología", tipo: "profesional", area_nombre: "Traumatología", activa: true, institucion: 1, duracion_min: 15, disponibilidades: [{ dia_semana: 1, activa: true }] };
const medica = { ...agenda, id: 11, nombre: "Dra. Méndez · Cardiología", area_nombre: "Cardiología", duracion_min: 20, disponibilidades: [{ dia_semana: 0, activa: true }] };
const solicitud = { id: 91, financiador: 21, institucion: 1, institucion_nombre: "Hospital Central", afiliado_nombre: "Ana", afiliado_numero: "001", prestacion_nombre: "Consulta", origen: "manual", estado: "pendiente", revision: 1, cantidad_solicitada: 2, cantidad_aprobada: 0, puede_resolver: true, creado: "2026-10-05T12:00:00Z", historial: [] };

async function preparar(page, opciones = {}) {
  const pedidos = [];
  await page.addInitScript((inst) => {
    sessionStorage.setItem("salud.access", "token-ficticio-111");
    localStorage.setItem("salud.institucion", JSON.stringify(inst));
    localStorage.removeItem("salud.menu");
    localStorage.removeItem("salud.tema");
  }, instituciones[0]);
  await page.route("**/api/**", (route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const path = url.pathname.slice(4);
    pedidos.push({ path, method: route.request().method() });
    const responder = (json) => route.fulfill({ json });
    if (path === "/usuarios/me/") return responder({ id: 7, email: "persona@example.test", is_superuser: !!opciones.superadmin,
      nombre_completo: "Persona de prueba", capacidades_por_institucion: { 1: [...caps, ...(opciones.plataforma ? ["gobierno_plataforma"] : [])], 2: caps },
      roles_por_institucion: { 1: ["admin"], 2: ["admin"] }, financiadores: opciones.financiador ? [{ id: 21, nombre: "Mutual", rol: "admin" }] : [],
      simulacion: opciones.simulada ? { id: "11111111-1111-4111-8111-111111111111", ambito: "institucion", rol: "admin", etiqueta: "Administrador", institucion: instituciones[0], cuenta: { id: 7, nombre: "Referencia" } } : null });
    if (path === "/instituciones/") return responder(lista(instituciones));
    if (path === "/instituciones/tablero-plataforma/") return responder({ instituciones: 2, activas: 2, en_alta: 0, atendidos: 0, ocupacion: 0, personal_activo: 0, serie: [], alertas: [], indicadores: [] });
    if (path.endsWith("/metricas/")) return responder({ staff: 12, areas: 4, boxes: 8, flujos: 2 });
    if (path.endsWith("/puesta-en-marcha/")) return responder({ areas: true, usuarios: true, asignaciones: true, agenda_profesional: true, agenda_recurso: true, flujo_operativo: false });
    if (path.endsWith("/tablero/")) return responder({ resumen: {}, serie: [], ingresos_por_dia: [] });
    if (path === "/notificaciones/resumen/") return responder({ no_leidas: 0, items: [] });
    if (path === "/concesiones-financieras/mias/") return responder({ superusuario: false, concesiones: [] });
    if (path === "/mis-tareas/") return responder({ tareas: [], filas: [], esperando: [], puestos: [], iniciar: [] });
    if (path === "/membresias/") return responder(lista([{ id: 1, usuario: 7, institucion: 1, areas: [3], areas_nombres: { 3: "Guardia" } }]));
    if (path === "/areas/") return responder(lista([{ id: 3, nombre: "Guardia", institucion: 1 }]));
    if (path === "/boxes/") return responder(lista([{ id: 4, nombre: "Box 1", area: 3 }]));
    if (path === "/items-fila/") return responder(lista([{ id: 5, caso: 41, ciudadano_nombre: "Ana", area: 3, area_nombre: "Guardia", rango: 1, ticket: "G001", ingreso: "2026-10-05T12:00:00Z", box: null }]));
    if (path === "/agendas/") return responder(lista([agenda, medica]));
    if (/\/agendas\/\d+\/semana\/$/.test(path)) {
      const minutos = path.includes("/11/") ? 20 : 15;
      const horarios = Array.from({ length: 4 }, (_, i) => ({ inicio: `2026-10-05T${String(9 + Math.floor(i * minutos / 60)).padStart(2, "0")}:${String(i * minutos % 60).padStart(2, "0")}:00-03:00`, duracion_min: minutos, libres: 1, cupos: 1 }));
      return responder({ dias: [{ fecha: "2026-10-05", horarios }] });
    }
    if (/\/agendas\/\d+\/dia\/$/.test(path)) return responder({ horarios: [] });
    if (path === "/ciudadanos/7/") return route.fulfill({ status: opciones.errorPaciente || 404, json: { detail: "No disponible" } });
    if (path === "/accesos-clinicos/") return responder(lista([{ id: 1, tipo: "financiador", tipo_display: "Consulta de un financiador", usuario_nombre: "Auditor", institucion: 1, institucion_nombre: "Hospital Central", momento: "2026-10-05T12:00:00Z", recurso: "financiadores-evoluciones-caso", detalle: "entradas=12,13", motivo: "Auditoría médica del convenio; entradas=1,2,3", ciudadano: null, resultados: 2 }]));
    if (path === "/financiadores/") return responder(lista([{ id: 21, nombre: "Mutual", rol: "admin", consulta_historia_clinica: true }]));
    if (path === "/autorizaciones-cobertura/") return responder(lista([solicitud]));
    if (path === "/autorizaciones-cobertura/91/") return responder(solicitud);
    if (path.endsWith("/ficha-afiliado/")) return responder({ ...lista(), afiliado: { id: 7, nombre: "Ana", estado: "vigente" }, resumen: {}, cupos: [], historial: [] });
    if (path.endsWith("/ficha-historia-casos/")) return responder(lista([
      { id: 41, institucion: instituciones[0], estado: "recibido", creado: "2026-10-05T12:00:00Z", evoluciones_firmadas: 0 },
      { id: 42, institucion: instituciones[0], estado: "cerrado", creado: "2026-10-04T12:00:00Z", evoluciones_firmadas: 1 },
    ]));
    return responder(lista());
  });
  return pedidos;
}

test("selector legible y DIRECCIÓN antes de OPERACIÓN", async ({ page }) => {
  await preparar(page);
  await page.goto("/inicio");
  await page.getByRole("button", { name: /Hospital Central/ }).click();
  await expect(page.getByText("CAMBIAR DE INSTITUCIÓN", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Hospital Central/ }).first().click();
  const direccion = await page.getByText("DIRECCIÓN", { exact: true }).boundingBox();
  const operacion = await page.getByText("OPERACIÓN", { exact: true }).boundingBox();
  expect(direccion.y).toBeLessThan(operacion.y);
});

for (const ancho of [1440, 390]) {
  test(`ayuda completa dentro del viewport ${ancho}`, async ({ page }) => {
    await page.setViewportSize({ width: ancho, height: 900 });
    await preparar(page);
    await page.goto("/inicio");
    await page.getByRole("button", { name: "Ayuda sobre Requiere atención" }).click();
    const caja = await page.getByRole("tooltip").boundingBox();
    expect(caja.x).toBeGreaterThanOrEqual(0);
    expect(caja.x + caja.width).toBeLessThanOrEqual(ancho);
    await page.keyboard.press("Escape");
    await expect(page.getByRole("tooltip")).toHaveCount(0);
  });
}

for (const id of [10, 11]) {
  test(`agenda ${id}: horarios legibles sin superposición y clic al día`, async ({ page }) => {
    await preparar(page);
    await page.goto(`/agenda?agenda=${id}&fecha=2026-10-05&vista=semana`);
    const bloques = page.locator("[data-horario]");
    await expect(bloques).toHaveCount(4);
    const cajas = await bloques.evaluateAll((elements) => elements.map((el) => {
      const r = el.getBoundingClientRect(); const texto = el.querySelector("span").getBoundingClientRect();
      return { top: r.top, bottom: r.bottom, height: r.height, texto: texto.height };
    }));
    for (let i = 0; i < cajas.length; i++) {
      expect(cajas[i].height).toBeGreaterThanOrEqual(cajas[i].texto);
      if (i) expect(cajas[i].top).toBeGreaterThanOrEqual(cajas[i - 1].bottom);
    }
    await bloques.first().click();
    await expect.poll(() => new URL(page.url()).searchParams.get("vista")).toBe("dia");
    await page.getByRole("combobox", { name: "Profesional o recurso" }).click();
    await expect(page.getByRole("option", { name: "Dra. Méndez · Cardiología", exact: true })).toBeVisible();
  });
}

test("agenda inicial elige una disponibilidad del lunes sin alterar selección explícita", async ({ page }) => {
  await preparar(page);
  await page.goto("/agenda?fecha=2026-10-05&vista=semana");
  await expect(page.getByRole("combobox", { name: "Profesional o recurso" })).toHaveValue(medica.nombre);
});

test("comprador autorizado vuelve a Instituciones", async ({ page }) => {
  await preparar(page, { plataforma: true });
  await page.goto("/inicio");
  await page.getByRole("button", { name: "Volver al directorio" }).click();
  await expect(page).toHaveURL(/\/directorio/);
  await expect(page.getByRole("heading", { name: "Instituciones", exact: true })).toBeVisible();
});

test("paciente no disponible tiene mensaje contextual", async ({ page }) => {
  await preparar(page);
  await page.goto("/pacientes/7");
  await expect(page.getByText("Paciente no disponible en esta institución", { exact: true })).toBeVisible();
});

test("motivo completo no se interpreta como ids de auditoría", async ({ page }) => {
  await preparar(page);
  await page.goto("/accesos");
  await expect(page.getByText("Motivo: Auditoría médica del convenio; entradas=1,2,3", { exact: true })).toBeVisible();
});

test("ficha: estados y singular legibles, cero evoluciones sin pedir motivo", async ({ page }) => {
  const pedidos = await preparar(page, { financiador: true });
  await page.goto("/financiadores/padron/7?financiador=21");
  await expect(page.getByText(/Recibido · 0 evoluciones firmadas/)).toBeVisible();
  await expect(page.getByText(/Cerrado · 1 evolución firmada/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Ver evoluciones" })).toHaveCount(1);
  await expect(page.getByRole("textbox", { name: "Motivo de consulta" })).toHaveCount(0);
  expect(pedidos.some((p) => p.path.endsWith("/ficha-historia-evoluciones/"))).toBe(false);
});

test("miniatura de app supera contraste 4,5:1", async ({ page }) => {
  await page.goto("/presentacion");
  const textos = page.getByText("Próximo turno", { exact: true });
  await expect(textos).toBeVisible();
  const contraste = await textos.evaluate((el) => {
    const rgb = (color) => {
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 1;
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = color;
      ctx.fillRect(0, 0, 1, 1);
      return [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3);
    };
    const luminancia = (c) => rgb(c).map((v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }).reduce((s, v, i) => s + v * [0.2126, 0.7152, 0.0722][i], 0);
    const estilo = getComputedStyle(el.parentElement);
    const a = luminancia(estilo.color), b = luminancia(estilo.backgroundColor);
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  });
  expect(contraste).toBeGreaterThanOrEqual(4.5);
});

test("aprobar explica fechas obligatorias y bloquea rangos invertidos", async ({ page }) => {
  await preparar(page, { financiador: true });
  await page.goto("/financiadores/autorizaciones?financiador=21");
  await page.getByRole("button", { name: "Revisar", exact: true }).click();
  await page.getByRole("button", { name: "Resolver solicitud", exact: true }).click();
  await page.getByRole("combobox", { name: "Decisión", exact: true }).selectOption("aprobar");
  await page.getByLabel("Motivo de la decisión", { exact: true }).fill("Revisión administrativa conforme");
  await page.getByLabel("Evidencia de la decisión", { exact: false }).fill("Acta interna ficticia");
  const registrar = page.getByRole("button", { name: "Registrar decisión", exact: true });
  await expect(registrar).toBeDisabled();
  await expect(page.getByRole("status")).toContainText("ambas fechas de vigencia");
  await page.getByLabel("Válida desde", { exact: true }).fill("2026-10-30");
  await page.getByLabel("Válida hasta", { exact: true }).fill("2026-10-16");
  await expect(registrar).toBeDisabled();
  await page.getByLabel("Válida hasta", { exact: true }).fill("2026-10-30");
  await expect(registrar).toBeEnabled();
});

test("fila muestra prioridad alta y superusuario no ofrece llamar", async ({ page }) => {
  await preparar(page, { superadmin: true });
  await page.goto("/filas");
  await expect(page.getByText("Prioridad alta", { exact: true })).toBeVisible();
  const llamar = page.getByRole("button", { name: /Llamar/ });
  await expect(llamar).toHaveCount(1);
  await expect(llamar).toBeDisabled();
});

test("DIRECCIÓN precede a OPERACIÓN también con administrador simulado", async ({ page }) => {
  await preparar(page, { simulada: true });
  await page.goto("/inicio");
  const direccion = page.getByText("DIRECCIÓN", { exact: true });
  await expect(direccion).toBeVisible();
  const operacion = await page.getByText("OPERACIÓN", { exact: true }).boundingBox();
  expect((await direccion.boundingBox()).y).toBeLessThan(operacion.y);
});

test("fechas de calendario mantienen día y mes en zona argentina", async ({ page }) => {
  await page.goto("/presentacion");
  const valores = await page.evaluate(async () => {
    const { fechaCalendario, periodoCalendario } = await import("/src/lib/format.js");
    return [fechaCalendario("2026-10-01"), fechaCalendario("2027-01-01"), periodoCalendario("2026-10"), periodoCalendario("2027-01"), fechaCalendario(null)];
  });
  expect(valores).toEqual(["01/10/2026", "01/01/2027", "octubre de 2026", "enero de 2027", "—"]);
});
