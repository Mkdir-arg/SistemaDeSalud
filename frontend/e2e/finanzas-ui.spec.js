import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { inflateSync } from "node:zlib";
test.beforeEach(async ({ page }) => { page.on("pageerror", (error) => { console.error("Error de página:", error.message); }); });

async function escenarioAjusteCosto(page, { aprobar = true, sensible = false, alcanceSensible = true, areaAprobacion = 3 } = {}) {
  await escenario(page, { permisos: ["ver_costos", ...(aprobar ? ["aprobar_costos"] : [])] });
  const escrituras = [];
  let lecturas = 0;
  const ajuste = { id: 77, importe: "10.00", motivo: "Corrección manual", estado: "pendiente_aprobacion", aprobado: false,
    area: 3, sensible, registrado_por: 7, registrado: "2026-09-14T12:00:00Z" };
  await page.route("**/api/concesiones-financieras/mias/", (route) => route.fulfill({ json: { superusuario: false, concesiones: [
    { institucion: 2, accion: "ver_costos", todas_las_areas: true, areas: [], permite_sensibles: true },
    ...(aprobar ? [{ institucion: 2, accion: "aprobar_costos", todas_las_areas: false, areas: [areaAprobacion], permite_sensibles: alcanceSensible }] : []),
  ] } }));
  await page.route("**/api/hechos-costo/**", (route) => {
    lecturas += 1;
    return route.fulfill({ json: lista([{ id: 17, institucion: 2, area: 3, caso: 21, ocurrida_en: "2026-09-14T10:00:00Z",
      total_conocido: ajuste.estado === "aprobado" ? "110.00" : "100.00", total_compartido_conocido: "0.00", total_directo_es_completo: true,
      imputaciones: [{ componente: 1, componente_nombre: "Materiales", importe: "100.00", ajustes: [ajuste] }],
      repartos_compartidos: [], faltantes: [], limite: "Componentes directos configurados.", actualizado_en: "2026-09-14T12:00:00Z" }]) });
  });
  await page.route("**/api/ajustes-costo/77/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    const body = route.request().postDataJSON(); escrituras.push({ path, body });
    ajuste.estado = path.endsWith("/aprobar/") ? "aprobado" : "rechazado";
    ajuste.aprobado = ajuste.estado === "aprobado";
    return route.fulfill({ json: ajuste });
  });
  return { escrituras, lecturas: () => lecturas };
}

for (const rechazar of [false, true]) {
  test(`ajuste de costo se ${rechazar ? "rechaza con motivo" : "aprueba"} desde su composición y refresca el costo`, async ({ page }) => {
    const escenarioCosto = await escenarioAjusteCosto(page);
    await page.goto("/finanzas?tab=costos&mes=2026-09");
    await page.getByRole("button", { name: "Ver composición", exact: true }).click();
    await page.getByRole("button", { name: rechazar ? "Rechazar ajuste de costo" : "Aprobar ajuste de costo", exact: true }).click();
    if (rechazar) {
      await expect(page.getByRole("button", { name: "Confirmar rechazo", exact: true })).toBeDisabled();
      await page.getByLabel("Motivo del rechazo").fill("El valor no corresponde");
    }
    await page.getByRole("button", { name: rechazar ? "Confirmar rechazo" : "Confirmar aprobación", exact: true }).click();
    await expect.poll(() => escenarioCosto.escrituras.length).toBe(1);
    expect(escenarioCosto.escrituras[0]).toEqual({ path: `/api/ajustes-costo/77/${rechazar ? "rechazar" : "aprobar"}/`, body: rechazar ? { motivo: "El valor no corresponde" } : {} });
    await expect.poll(escenarioCosto.lecturas).toBeGreaterThan(1);
    await expect(page.getByRole("dialog").getByText(rechazar ? "Rechazado" : "Aprobado", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Aprobar ajuste de costo", exact: true })).toHaveCount(0);
  });
}

for (const [nombre, permisos] of [
  ["sin permiso", { aprobar: false }],
  ["sin alcance sensible", { sensible: true, alcanceSensible: false }],
  ["en otra área", { areaAprobacion: 4 }],
]) {
  test(`ajuste de costo no ofrece decisiones ${nombre}`, async ({ page }) => {
    await escenarioAjusteCosto(page, permisos);
    await page.goto("/finanzas?tab=costos&mes=2026-09");
    await page.getByRole("button", { name: "Ver composición", exact: true }).click();
    await expect(page.getByRole("dialog").getByText("Pendiente de aprobación", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Aprobar ajuste de costo", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Rechazar ajuste de costo", exact: true })).toHaveCount(0);
  });
}

const inst = { id: 2, nombre: "Hospital Escuela" };
const area = { id: 3, nombre: "Consultorios Escuela", institucion: 2 };
const lista = (results) => ({ count: results.length, results, next: null, previous: null });
// El resumen dibuja barras de gastos, de dinero y de costos: siempre se indica cuál.
const barrasDeGastos = (page) => page.getByRole("region", { name: "Gráfico de barras por área y concepto" }).locator(".recharts-bar-rectangle");
const acciones = ["ver_gastos", "ver_costos", "registrar_gastos", "aprobar_gastos", "configurar_componentes", "configurar_gastos_esperados", "configurar_repartos"];
const calendario = { id: 1, institucion: 2, concepto: 1, concepto_nombre: "Electricidad", area: 3, area_nombre: area.nombre, sensible: false, estado_carga: "falta_cargar", gastos_pendientes: 1, gastos_aprobados: 1, monto_referencia: "12000.00", importe_aprobado: "10000.01", diferencia_referencia: "1999.99", vigente_desde: "2026-09-01", vigente_hasta: null };
const reporte = { aprobados: "10000.01", pendientes_aprobacion: "500.00", distribuido: "10000.01", sin_distribuir: "0.00", moneda: "ARS", actualizando: false, alcance: "Gastos registrados visibles según tus permisos; no equivale al costo total del hospital", agrupaciones: [{ area: 3, area_nombre: area.nombre, concepto: 1, concepto_nombre: "Electricidad", aprobados: "10000.01", pendientes_aprobacion: "500.00", distribuido: "10000.01", sin_distribuir: "0.00", actualizando: false }] };
const resumenCostos = { institucion: 2, area: null, periodo_economico: "2026-09-01", moneda: "ARS", atenciones: 2, atenciones_incompletas: 1, ajustes_pendientes: 0, reparto_actualizando: false, directo_conocido: "10000.00", compartido_conocido: "3333.34", alcance: "Costos conocidos de las atenciones del mes.", agrupaciones: {
  area: [{ area: 3, nombre: area.nombre, atenciones: 2, incompletas: 1, directo_conocido: "10000.00", compartido_conocido: "3333.34" }],
  prestacion: [{ prestacion: 4, nombre: "Consulta médica", atenciones: 1, incompletas: 0, directo_conocido: "10000.00", compartido_conocido: "3333.34" }, { prestacion: null, nombre: "Sin prestación configurada", atenciones: 1, incompletas: 1, directo_conocido: "0.00", compartido_conocido: "0.00" }],
} };
const resumenDinero = { cobros_brutos: "200.00", pagos_brutos: "40.00", reintegros_cobros: "10.00", reintegros_pagos: "5.00", cobros_netos: "190.00", pagos_netos: "35.00", diferencia: "155.00", cantidad_movimientos: 3, fecha_desde: "2026-09-01", fecha_hasta: "2026-09-30", moneda: "ARS", por_aprobar: { pagos: "15.00", cobros: "0.00", reintegros_pagos: "0.00", reintegros_cobros: "0.00", cantidad: 1 }, agrupaciones: [{ area: 3, area_nombre: area.nombre, cobros_netos: "190.00", pagos_netos: "35.00", diferencia: "155.00", cantidad_movimientos: 3, por_aprobar: { cantidad: 1 } }] };

async function escenarioEjecutivo(page, { permisos = [...acciones, "ver_dinero"], vacio = false, error = false, transformar = (datos) => datos } = {}) {
  const base = await escenario(page, { permisos });
  const peticiones = [];
  page.on("request", (r) => { if (r.url().includes("/api/")) peticiones.push(new URL(r.url())); });
  await page.route(/\/api\/reportes-(finanzas|dinero)\/comparativa\//, async (route) => {
    if (error) return route.fulfill({ status: 403, json: { detail: "Sin acceso a este alcance" } });
    const url = new URL(route.request().url());
    const esDinero = url.pathname.includes("reportes-dinero");
    const anterior = url.searchParams.get("comparar") === "anio_anterior" ? "2025-09-01" : "2026-08-01";
    const nombres = ["Electricidad", "Materiales de atención", "Mantenimiento", "Limpieza"];
    const grupos = vacio ? [] : nombres.map((nombre, i) => ({ area: i < 2 ? 3 : 4, area_nombre: i < 2 ? area.nombre : "Guardia", concepto: i + 1, concepto_nombre: nombre,
      actual: { aprobados: ["480000.01", "320000.00", "140000.00", "60000.00"][i] }, anterior: { aprobados: ["400000.00", "250000.00", "100000.00", "50000.00"][i] },
      variacion: { importe: ["80000.01", "70000.00", "40000.00", "10000.00"][i], porcentaje: "20.00" } }));
    const gasto = (periodo, actual = true) => ({ periodo_economico: periodo, aprobados: vacio ? "0.00" : actual ? "1000000.01" : "800000.00", pendientes_aprobacion: vacio ? "0.00" : "25000.00", cantidad_registros: vacio ? 0 : 4, controles: vacio ? 0 : 3, controles_sin_completar: vacio ? 0 : actual ? 1 : 2, provisional: !vacio, actualizando: false, ajustes_pendientes: 0, mes_abierto: periodo === "2026-09-01" });
    const money = (periodo, actual = true) => ({ periodo_economico: periodo, fecha_desde: periodo, fecha_hasta: periodo.slice(0, 8) + (periodo.slice(5, 7) === "09" ? "30" : "31"), cobros_netos: vacio ? "0.00" : actual ? "720000.00" : "600000.00", pagos_netos: vacio ? "0.00" : "540000.00", diferencia: vacio ? "0.00" : actual ? "180000.00" : "60000.00", cantidad_movimientos: vacio ? 0 : 9, por_aprobar: { cantidad: vacio ? 0 : 2 }, mes_abierto: periodo === "2026-09-01" });
    const meses = Number(url.searchParams.get("meses"));
    const serie = Array.from({ length: meses }, (_, i) => {
      const fecha = new Date(Date.UTC(2026, 9 - meses + i, 1)).toISOString().slice(0, 10);
      const fila = esDinero ? money(fecha) : gasto(fecha);
      if (!vacio && i < meses - 1) {
        if (esDinero) { fila.cobros_netos = String(420000 + i * 36000); fila.pagos_netos = String(380000 + i * 23000); }
        else fila.aprobados = String(620000 + i * 45000);
      }
      return fila;
    });
    const variacion = { importe: vacio ? null : "200000.01", porcentaje: vacio ? null : "25.00", motivo: vacio ? "Sin registros comparables" : null };
    const desglose = vacio ? [] : [{ area_nombre: area.nombre, concepto_nombre: "Consulta médica", pagador_nombre: "Mutual del Litoral", cobros_netos: "720000.00", pagos_netos: "0.00", cantidad_movimientos: 9, por_aprobar: { cantidad: 2 }, filtros: { area: 3, tipo_cuenta: "cobrar", reporte_financiador: "9", reporte_prestacion: "4", reporte_concepto: "null", reporte_pagador: "financiador" } }];
    await route.fulfill({ json: transformar({ actual: esDinero ? money("2026-09-01") : gasto("2026-09-01"), anterior: esDinero ? money(anterior, false) : gasto(anterior, false), serie,
      variaciones: Object.fromEntries((esDinero ? ["cobros_netos", "pagos_netos", "diferencia"] : ["aprobados", "pendientes_aprobacion"]).map((c) => [c, vacio ? variacion : c === "aprobados" ? variacion : { importe: c === "pagos_netos" || c === "pendientes_aprobacion" ? "0.00" : "120000.00", porcentaje: c === "pagos_netos" || c === "pendientes_aprobacion" ? "0.00" : c === "diferencia" ? "200.00" : "20.00" }])), agrupaciones: esDinero ? desglose : grupos,
      calculado_en: "2026-09-16T15:30:00Z", moneda: "ARS", alcance: "Fuentes registradas y visibles; no certifica carga completa." }, esDinero) });
  });
  return { ...base, peticiones };
}

test("comparaciones colorean aumentos y bajas sin confundir cero ni falta de base", async ({ page }) => {
  await escenarioEjecutivo(page, { transformar: (datos, esDinero) => {
    if (esDinero) return datos;
    datos.actual.aprobados = "600000.00";
    datos.variaciones.aprobados = { importe: "-200000.00", porcentaje: "-25.00" };
    datos.agrupaciones[0].actual.aprobados = "320000.00";
    datos.agrupaciones[0].variacion = { importe: "-80000.00", porcentaje: "-20.00" };
    datos.agrupaciones[1].variacion = { importe: "70000.00", porcentaje: null };
    datos.agrupaciones[2].anterior = null;
    datos.agrupaciones[2].variacion = { importe: null, porcentaje: null };
    return datos;
  } });
  await page.goto("/finanzas?tab=reportes&mes=2026-09");
  const cambios = page.locator(".finance-report-change");
  await expect(cambios.first().locator("strong")).toHaveText("ARS -200.000,00");
  for (const oscuro of [false, true]) {
    if (oscuro) await page.getByRole("button", { name: "Cambiar a tema oscuro", exact: true }).click();
    for (const [texto, clase] of [["-25% nominal", "text-badge-error-fg"], ["-20% nominal", "text-badge-error-fg"], ["+20% nominal", "text-badge-green-fg"], ["0% nominal", "text-texto-debil"], ["Sin base porcentual", "text-texto-debil"]]) {
      const elementos = cambios.getByText(texto, { exact: true });
      for (const elemento of await elementos.all()) {
        await expect(elemento).toHaveClass(new RegExp(clase));
        // Detecta reglas CSS más específicas que anulen el token de color.
        expect(await elemento.evaluate((el, token) => {
          const referencia = document.createElement("span");
          referencia.className = token;
          document.body.append(referencia);
          const coincide = getComputedStyle(el).color === getComputedStyle(referencia).color;
          referencia.remove();
          return coincide;
        }, clase)).toBe(true);
      }
    }
    await expect(cambios.first().locator("strong")).toHaveClass(/text-badge-error-fg/);
    await expect(page.getByText("Sin base comparable", { exact: true })).toHaveClass(/text-texto-debil/);
  }
});

async function descargarPdf(page, testInfo) {
  const descarga = page.waitForEvent("download");
  await page.getByRole("button", { name: "Descargar PDF", exact: true }).click();
  const archivo = await descarga;
  expect(archivo.suggestedFilename()).toBe("reporte-finanzas-2026-09.pdf");
  const ruta = testInfo.outputPath("reporte.pdf");
  await archivo.saveAs(ruta);
  await testInfo.attach("reporte-pdf", { path: ruta, contentType: "application/pdf" });
  const pdf = (await readFile(ruta)).toString("latin1");
  expect(pdf).toMatch(/^%PDF-/);
  // Inspeccionar los flujos de texto emitidos por jsPDF, además de comprobar
  // la descarga. La revisión visual usa un lector PDF independiente.
  const contenido = [...pdf.matchAll(/stream\r?\n([\s\S]*?)\r?\nendstream/g)].map((m) => {
    try { return inflateSync(Buffer.from(m[1], "latin1")).toString("latin1"); } catch { return m[1]; }
  }).join("\n");
  return { pdf, contenido };
}

test("PDF descarga gráficos y todas las filas filtradas en su orden, con períodos y fuentes", async ({ page }, testInfo) => {
  const { peticiones } = await escenarioEjecutivo(page, { transformar: (datos, esDinero) => {
    if (!esDinero) datos.agrupaciones = Array.from({ length: 32 }, (_, i) => ({ ...datos.agrupaciones[0],
      concepto: i + 1, area_nombre: "AreaPDF", concepto_nombre: i === 31 ? "Excluido" : `Incluido ${String(i + 1).padStart(3, "0")}`,
      actual: { aprobados: `${1000 + i}.01` }, anterior: { aprobados: "900.00" }, variacion: { importe: `${100 + i}.01`, porcentaje: "11.11" },
    }));
    return datos;
  } });
  await page.goto("/finanzas?tab=reportes&mes=2026-09&area=3&reporte_grupos_gastos_f_area_concepto=Incluido&reporte_grupos_gastos_ord=-actual&reporte_grupos_gastos_pag=2");
  await page.getByLabel("Comparar período", { exact: true }).selectOption("anio_anterior");
  await page.getByLabel("Trayectoria", { exact: true }).selectOption("12");
  await page.getByRole("textbox", { name: "Buscar en desglose", exact: true }).fill("Litoral");
  await expect(page.locator("[data-reporte-grafico] .recharts-wrapper > svg.recharts-surface")).toHaveCount(3);
  await expect(page.getByRole("button", { name: "Descargar PDF", exact: true })).toBeEnabled();
  const consultasAntes = peticiones.filter((p) => p.pathname.includes("/comparativa/")).length;
  const { pdf, contenido } = await descargarPdf(page, testInfo);
  expect(pdf.match(/\/Subtype \/Image/g)?.length).toBeGreaterThanOrEqual(3);
  for (const dato of ["Hospital Escuela", "2025-09", "2026-09", "Consultorios Escuela", "Trayectoria: 12 meses", "Fuente consultada", "registros vigentes", "Incluido 031", "Incluido 001", "Filas: 31.", "Búsqueda: Litoral", "Mutual del Litoral"]) expect(contenido).toContain(dato);
  // El gráfico conserva sus grupos aunque la tabla esté filtrada, y el PDF
  // identifica cada barra con área y concepto porque no tiene tooltips.
  expect(contenido).toContain("1. AreaPDF · Excluido");
  const tablaGastos = contenido.slice(contenido.indexOf("Comparación exacta de gastos"));
  expect(tablaGastos).not.toContain("Excluido");
  expect(tablaGastos.indexOf("Incluido 031")).toBeLessThan(tablaGastos.indexOf("Incluido 001"));
  expect(peticiones.filter((p) => p.pathname.includes("/comparativa/")).length).toBe(consultasAntes);
  await expect(page).toHaveURL(/reporte_grupos_gastos_pag=2/);
});

test("PDF conserva restricciones y ausencia de registros sin dibujar ceros", async ({ page }, testInfo) => {
  const { peticiones } = await escenarioEjecutivo(page, { permisos: ["ver_dinero"], vacio: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/finanzas?tab=reportes&mes=2026-09");
  await expect(page.getByRole("button", { name: "Descargar PDF", exact: true })).toBeEnabled();
  const { pdf, contenido } = await descargarPdf(page, testInfo);
  expect(contenido).toContain("No incluidos en tu acceso");
  expect(contenido).toContain("Sin base comparable");
  expect(contenido).not.toContain("ARS 0,00");
  expect(pdf).not.toContain("/Subtype /Image");
  expect(peticiones.some((p) => p.pathname.includes("/reportes-finanzas/"))).toBe(false);
});

test("PDF bloquea consultas fallidas y filtros numéricos inválidos", async ({ page }) => {
  await escenarioEjecutivo(page, { error: true });
  await page.goto("/finanzas?tab=reportes&mes=2026-09");
  await expect(page.getByText("No tenés permiso para ver esto", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Descargar PDF", exact: true })).toBeDisabled();
  await escenarioEjecutivo(page);
  await page.goto("/finanzas?tab=reportes&mes=2026-09&reporte_grupos_gastos_f_actual_min=1e3");
  await page.getByRole("button", { name: "Descargar PDF", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Corregí los filtros de importe" })).toBeVisible();
});

test("PDF exporta gráficos desde móvil oscuro y conserva las bajas", async ({ page }, testInfo) => {
  await escenarioEjecutivo(page, { transformar: (datos, esDinero) => {
    if (!esDinero) {
      datos.actual.aprobados = "600000.00";
      datos.variaciones.aprobados = { importe: "-200000.00", porcentaje: "-25.00" };
    }
    return datos;
  } });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/finanzas?tab=reportes&mes=2026-09");
  await page.getByRole("button", { name: "Cambiar a tema oscuro", exact: true }).click();
  await expect(page.locator("[data-reporte-grafico] .recharts-wrapper > svg.recharts-surface")).toHaveCount(3);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  const { pdf, contenido } = await descargarPdf(page, testInfo);
  expect(contenido).toContain("ARS -200.000,00");
  expect(contenido).toContain("-25%");
  expect(pdf.match(/\/Subtype \/Image/g)?.length).toBeGreaterThanOrEqual(3);
  await page.screenshot({ path: testInfo.outputPath("pdf-movil-oscuro.png") });
});

test("PDF espera las consultas y muestra un error recuperable si falla la generación", async ({ page }, testInfo) => {
  await escenarioEjecutivo(page, { vacio: true });
  let liberar;
  const espera = new Promise((resolve) => { liberar = resolve; });
  await page.route(/\/api\/reportes-(finanzas|dinero)\/comparativa\//, async (route) => { await espera; await route.fallback(); });
  await page.goto("/finanzas?tab=reportes&mes=2026-09");
  await expect(page.getByRole("button", { name: "Descargar PDF", exact: true })).toBeDisabled();
  liberar();
  await expect(page.getByRole("button", { name: "Descargar PDF", exact: true })).toBeEnabled();
  await page.route("**/src/pages/finanzas/reportePdf.js*", (route) => route.abort());
  await page.getByRole("button", { name: "Descargar PDF", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "No se pudo generar el PDF" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Descargar PDF", exact: true })).toBeEnabled();
  await expect(page.locator(".finance-report-metric")).toHaveCount(5);
  await page.unroute("**/src/pages/finanzas/reportePdf.js*");
  // Los navegadores conservan un import() fallido durante esta navegación.
  // Se sigue la recuperación indicada en el mensaje, sin perder filtros URL.
  await page.reload();
  await descargarPdf(page, testInfo);
  await expect(page.getByRole("alert").filter({ hasText: "No se pudo generar el PDF" })).toHaveCount(0);
});

test("reporte ejecutivo compara períodos y abre gastos anteriores sin imponer control mensual", async ({ page }, testInfo) => {
  const { peticiones } = await escenarioEjecutivo(page);
  await page.goto("/finanzas?tab=reportes&mes=2026-09");
  await expect(page.getByRole("heading", { name: "Comparación de períodos" })).toBeVisible();
  const ayuda = page.getByRole("button", { name: "Cómo leer los reportes", exact: true });
  await expect(page.getByText(/Los importes están en pesos argentinos/)).toHaveCount(0);
  await ayuda.focus();
  await expect(page.getByRole("dialog", { name: "Cómo leer los reportes", exact: true })).toContainText("base anterior es positiva");
  await page.keyboard.press("Escape");
  await expect(ayuda).toBeFocused();
  await expect(page.getByRole("dialog", { name: "Cómo leer los reportes", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Ver gastos aprobados de 2026-09", exact: true })).toHaveText("ARS 1.000.000,01");
  await expect(page.getByRole("region", { name: "Informe de gastos", exact: true }).getByText("+25% nominal", { exact: true }).first()).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await expect(page.getByRole("img", { name: "Tendencia mensual; importes y navegación disponibles en la tabla" }).first()).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("reportes-ejecutivos-escritorio.png"), animations: "disabled" });
  await page.locator(".finance-report-charts").scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("reportes-ejecutivos-graficos.png"), animations: "disabled" });
  await page.getByLabel("Comparar período").selectOption("anio_anterior");
  await page.getByRole("combobox", { name: "Trayectoria", exact: true }).selectOption("12");
  await expect.poll(() => peticiones.some((u) => u.pathname === "/api/reportes-finanzas/comparativa/" && u.searchParams.get("comparar") === "anio_anterior" && u.searchParams.get("meses") === "12")).toBe(true);
  await page.getByRole("button", { name: "Ver gastos aprobados de 2025-09", exact: true }).click();
  await expect.poll(() => peticiones.some((u) => u.pathname === "/api/gastos/" && u.searchParams.get("periodo_economico") === "2025-09-01" && u.searchParams.get("estado_operativo") === "aprobado" && !u.searchParams.has("control_mensual"))).toBe(true);
});

test("reporte ejecutivo conserva área concepto y mes del desglose de gastos", async ({ page }) => {
  const { peticiones } = await escenarioEjecutivo(page);
  await page.goto("/finanzas?tab=reportes&mes=2026-09");
  const fila = page.getByRole("table", { name: "Comparación exacta de gastos" }).getByRole("row").filter({ hasText: "Mantenimiento" });
  await fila.getByRole("button", { name: "ARS 140.000,00", exact: true }).click();
  await expect.poll(() => peticiones.some((u) => u.pathname === "/api/gastos/" && u.searchParams.get("area") === "4" && u.searchParams.get("concepto") === "3" && u.searchParams.get("periodo_economico") === "2026-09-01" && !u.searchParams.has("control_mensual"))).toBe(true);
});

test("reporte ejecutivo muestra cargas pendientes de ambos períodos y abre sus controles", async ({ page }) => {
  const { peticiones } = await escenarioEjecutivo(page);
  await page.goto("/finanzas?tab=reportes&mes=2026-09&area=3");
  await expect(page.getByRole("button", { name: "1 control pendiente de carga · revisar", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "2 controles pendientes de carga · revisar", exact: true }).click();
  await expect.poll(() => peticiones.some((u) => u.pathname === "/api/expectativas-gasto/calendario/" && u.searchParams.get("periodo_economico") === "2026-08-01" && u.searchParams.get("area") === "3" && u.searchParams.get("estado_carga") === "falta_cargar")).toBe(true);
});

test("reporte ejecutivo traza financiador prestación y estado hasta movimientos", async ({ page }) => {
  const { peticiones } = await escenarioEjecutivo(page);
  await page.route("**/api/movimientos-dinero/**", (route) => route.fulfill({ json: lista([{ id: 81, obligacion: 62, importe: "720000.00", estado: "aprobado", tipo: "cobro", obligacion_tipo: "cobrar", contraparte_nombre: "Mutual del Litoral", fecha: "2026-09-10", periodo_economico: "2026-08-01" }]) }));
  await page.route("**/api/obligaciones-financieras/62/", (route) => route.fulfill({ json: { id: 62, tipo: "cobrar", hecho: 71, area: 3, sensible: false, contraparte_nombre: "Mutual del Litoral", periodo_economico: "2026-08-01", importe_original: "720000.00", obligacion_actual: "720000.00", registrado_neto: "720000.00", pendiente: "0.00", disponible_registro: "0.00", disponible_reducir: "0.00", saldo_a_devolver: "0.00", por_aprobar: "0.00", reintegros_por_aprobar: "0.00", ajustes_por_aprobar: "0.00", movimientos: [], ajustes: [] } }));
  await page.goto("/finanzas?tab=reportes&mes=2026-09&movimientos_dinero_pag=2");
  const tabla = page.getByRole("table", { name: "Desglose de dinero por área, concepto y financiador" });
  await tabla.getByRole("button", { name: "ARS 720.000,00", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Mutual del Litoral");
  await expect(page).not.toHaveURL(/movimientos_dinero_pag=2/);
  await expect.poll(() => peticiones.some((u) => u.pathname === "/api/movimientos-dinero/" && u.searchParams.get("page") === "1" && u.searchParams.get("reporte_financiador") === "9" && u.searchParams.get("reporte_prestacion") === "4" && u.searchParams.get("reporte_concepto") === "null" && u.searchParams.get("area") === "3" && u.searchParams.get("estado") === "aprobado" && u.searchParams.get("fecha_desde") === "2026-09-01" && u.searchParams.get("fecha_hasta") === "2026-09-30")).toBe(true);
  await page.getByRole("button", { name: "Ver cuenta #62", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Cuenta #62", exact: true })).toContainText("Atención de origen #71");
});

test("reporte ejecutivo consulta pendientes fuera de los importes confirmados", async ({ page }) => {
  const { peticiones } = await escenarioEjecutivo(page);
  await page.goto("/finanzas?tab=reportes&mes=2026-09");
  await page.getByRole("table", { name: "Desglose de dinero por área, concepto y financiador" }).getByRole("button", { name: "2 registros", exact: true }).click();
  await expect.poll(() => peticiones.some((u) => u.pathname === "/api/movimientos-dinero/" && u.searchParams.get("estado") === "pendiente_aprobacion" && u.searchParams.get("reporte_financiador") === "9")).toBe(true);
});

test("reporte ejecutivo es legible en móvil y permite filtrar el desglose", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await escenarioEjecutivo(page);
  await page.goto("/finanzas?tab=reportes&mes=2026-09");
  await expect(page.getByRole("heading", { name: "Comparación de períodos" })).toBeVisible();
  await page.getByRole("button", { name: "Importes y pendientes de gastos", exact: true }).click();
  const ayuda = page.getByRole("dialog", { name: "Importes y pendientes de gastos", exact: true });
  await expect(ayuda).toContainText("Los ajustes por aprobar no modifican ese importe");
  const limites = await ayuda.boundingBox();
  expect(limites.x).toBeGreaterThanOrEqual(0);
  expect(limites.x + limites.width).toBeLessThanOrEqual(390);
  await ayuda.getByRole("button", { name: "Cerrar Importes y pendientes de gastos", exact: true }).click();
  await page.evaluate(() => document.fonts.ready);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("reportes-ejecutivos-movil.png"), animations: "disabled" });
  await page.locator(".finance-report-trend").first().scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("reportes-ejecutivos-grafico-movil.png"), animations: "disabled" });
  await page.getByRole("textbox", { name: "Buscar en desglose", exact: true }).fill("inexistente");
  await expect(page.getByText("Sin movimientos para este desglose", { exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: "Buscar en desglose", exact: true }).fill("Litoral");
  await expect(page.getByRole("table", { name: "Desglose de dinero por área, concepto y financiador" })).toContainText("Mutual del Litoral");
});

test("reporte ejecutivo sin registros no dibuja ceros ni una variación ficticia", async ({ page }) => {
  await escenarioEjecutivo(page, { vacio: true });
  await page.goto("/finanzas?tab=reportes&mes=2026-09");
  await expect(page.getByRole("button", { name: "Ver gastos aprobados de 2026-09", exact: true })).toHaveText("Sin registros");
  await expect(page.getByText("Sin base comparable", { exact: true }).first()).toBeVisible();
  await expect(page.locator(".finance-report .recharts-line")).toHaveCount(0);
  await expect(page.locator(".finance-report").getByText("ARS 0,00", { exact: true })).toHaveCount(0);
});

test("reporte ejecutivo no consulta gastos sin permiso y muestra restricción en lugar de cero", async ({ page }) => {
  const { peticiones } = await escenarioEjecutivo(page, { permisos: ["ver_dinero"] });
  await page.goto("/finanzas?tab=reportes&mes=2026-09");
  await expect(page.getByText("Los gastos no están incluidos en tu acceso. No se representan como cero.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Ver cobros netos de 2026-09", exact: true })).toBeVisible();
  expect(peticiones.some((u) => u.pathname.startsWith("/api/reportes-finanzas/"))).toBe(false);
});

test("reporte ejecutivo informa rechazo de acceso sin exponer cifras", async ({ page }) => {
  await escenarioEjecutivo(page, { error: true });
  await page.goto("/finanzas?tab=reportes&mes=2026-09");
  await expect(page.getByText("No tenés permiso para ver esto", { exact: true }).first()).toBeVisible();
  await expect(page.locator(".finance-report-metric")).toHaveCount(0);
});

test("ajustes pendientes se distinguen en resumen, control y evolución sin cambiar el aprobado", async ({ page }, testInfo) => {
  const { db, peticiones } = await escenario(page);
  db.reporte.aprobados = "100.00";
  db.reporte.pendientes_aprobacion = "0.00";
  db.reporte.ajustes_pendientes = 1;
  db.reporte.distribuido = "100.00";
  Object.assign(db.reporte.agrupaciones[0], { aprobados: "100.00", pendientes_aprobacion: "0.00", distribuido: "100.00", ajustes_pendientes: 1 });
  db.evolucion = { conceptos: [{ id: 1, nombre: "Electricidad" }], concepto: 1, moneda: "ARS", meses: [{
    periodo_economico: "2026-08-01", importe_aprobado: "100.00", estado: "incompleto", controles: 1,
    gastos_pendientes: 0, gastos_aprobados: 1, ajustes_pendientes: 1, monto_referencia: null,
  }] };
  await page.route("**/api/expectativas-gasto/calendario/**", (route) => route.fulfill({ json: lista([
    { ...calendario, estado_carga: "carga_completa", gastos_pendientes: 0, ajustes_pendientes: 1, importe_aprobado: "100.00" },
  ]) }));
  await page.goto("/finanzas?mes=2026-08");
  const resumen = page.getByRole("region", { name: "Resumen de gastos", exact: true });
  await expect(resumen.getByText("1 ajuste por aprobar", { exact: false })).toBeVisible();
  await expect(resumen.getByRole("button", { name: "Revisar gastos con ajustes", exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("ajustes-resumen.png"), animations: "disabled" });
  await page.getByRole("button", { name: "Evolución mensual", exact: true }).click();
  const evolucion = page.getByRole("region", { name: "Evolución de gastos mensuales", exact: true });
  await expect(evolucion.getByText("1 ajuste por aprobar", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Ver importes mensuales", exact: true }).click();
  await expect(evolucion.getByText("1 configuraciones incluidas · Carga o aprobación incompleta", { exact: true })).toBeVisible();
  await expect(evolucion.getByText("Ajustes por aprobar: 1", { exact: true })).toBeVisible();
  await expect(evolucion.getByRole("list", { name: "Importes mensuales", exact: true }).getByRole("button", { name: "Ver gastos aprobados de 2026-08 · Electricidad", exact: true })).toHaveText("ARS 100,00");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await evolucion.getByText("1 ajuste por aprobar", { exact: false }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("ajustes-evolucion-movil.png"), animations: "disabled" });
  await page.getByRole("tab", { name: "Gastos mensuales", exact: true }).click();
  await expect(page.getByRole("button", { name: "1 ajuste por aprobar", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "1 ajuste por aprobar", exact: true }).click();
  await expect.poll(() => peticiones.some((url) => url.pathname === "/api/gastos/"
    && url.searchParams.get("concepto") === "1" && url.searchParams.get("area") === "3"
    && url.searchParams.get("periodo_economico") === "2026-08-01"
    && url.searchParams.get("estado_operativo") === "aprobado")).toBe(true);
});

async function escenario(page, { permisos = acciones, pendientes = false, concesiones = [], clinico = false } = {}) {
  const peticiones = [];
  const escrituras = [];
  const db = { prestaciones: [], componentes: [], valores: [], concesiones: [...concesiones], pendientes, reporte: structuredClone(reporte), evolucion: { conceptos: [], concepto: null, meses: [], moneda: "ARS" }, costos: structuredClone(resumenCostos), dinero: structuredClone(resumenDinero) };
  await page.addInitScript((institucion) => { localStorage.setItem("salud.access", "credencial-ficticia-solo-mock"); localStorage.setItem("salud.institucion", JSON.stringify(institucion)); }, inst);
  await page.route("**/api/**", async (route) => {
    const req = route.request(); const url = new URL(req.url()); const path = url.pathname.replace(/^\/api/, "");
    if (!url.pathname.startsWith("/api/")) return route.continue();
    peticiones.push(url);
    let data = lista([]);
    if (req.method() !== "GET") {
      const body = req.postDataJSON(); escrituras.push({ path, body });
      const coleccion = { "/prestaciones-costo/": "prestaciones", "/componentes-costo/": "componentes", "/valores-componentes/": "valores" }[path];
      if (coleccion) { data = { id: db[coleccion].length + 1, ...body }; db[coleccion].push(data); }
      else if (path === "/concesiones-financieras/editar-membresia/") { db.concesiones = body.concesiones.map((c, n) => ({ ...c, membresia: 8, id: 20 + n })); data = { membresia: 8, activo: true, concesiones: db.concesiones, heredadas: [], otras_membresias: [], version_esperada: "b".repeat(64) }; }
      else if (path === "/expectativas-gasto/") data = { id: 2, ...body };
      else return route.fulfill({ status: 400, json: { detail: "Escritura no prevista bloqueada por la prueba" } });
      return route.fulfill({ status: 201, json: data });
    }
    if (path === "/usuarios/me/") data = { id: 7, nombre: "Administración Escuela", email: "admin@mock.local", is_superuser: false, capacidades_por_institucion: { 2: ["config_institucional", ...(clinico ? ["casos_operar"] : [])] }, roles_por_institucion: { 2: ["admin"] } };
    if (path === "/usuarios/8/") data = { id: 8, nombre: "Contabilidad", apellido: "Escuela", email: "contador@mock.local", is_active: true };
    if (path === "/instituciones/") data = lista([inst]);
    if (path === "/areas/") data = lista([area]);
    if (path === "/notificaciones/resumen/") data = { no_leidas: 0, recientes: [] };
    if (path === "/concesiones-financieras/mias/") data = { superusuario: false, concesiones: permisos.map((accion) => ({ institucion: 2, accion, todas_las_areas: true, areas: [], permite_sensibles: true, administrativa: true })) };
    if (path === "/concesiones-financieras/") data = lista(db.concesiones);
    if (path === "/concesiones-financieras/editar-membresia/") data = { membresia: 8, activo: true, concesiones: db.concesiones, heredadas: [], otras_membresias: [], version_esperada: "a".repeat(64) };
    if (path === "/membresias/") data = lista([{ id: 8, usuario: 8, usuario_nombre: "Contabilidad Escuela", usuario_email: "contador@mock.local", institucion: 2, rol: "administrativo", activo: true, areas: [] }]);
    if (path === "/conceptos-gasto/") data = lista([{ id: 1, institucion: 2, nombre: "Electricidad", codigo: "ELEC", activo: true, sensible: false }]);
    if (path === "/expectativas-gasto/calendario/") data = lista([calendario]);
    if (path === "/expectativas-gasto/") data = lista([calendario]);
    if (path === "/reportes-finanzas/") data = db.pendientes ? { ...db.reporte, actualizando: true, distribuido: null, sin_distribuir: null, agrupaciones: [{ ...db.reporte.agrupaciones[0], distribuido: null, sin_distribuir: null, actualizando: true }] } : db.reporte;
    if (path === "/reportes-finanzas/evolucion/") data = { ...db.evolucion, series: db.evolucion.series ?? db.evolucion.conceptos.map((c) => ({ ...c, meses: db.evolucion.meses })) };
    if (path === "/reportes-costos/") data = db.pendientes ? { ...db.costos, reparto_actualizando: true } : db.costos;
    if (path === "/reportes-dinero/") data = db.dinero;
    if (path === "/procesamiento-finanzas/") data = { estado: db.pendientes ? "pendiente" : "actualizado", pendientes: db.pendientes ? 1 : 0, worker_activo: !db.pendientes, ultimo_exito: db.pendientes ? null : "2026-09-14T12:00:00Z", mensaje: db.pendientes ? "El proceso está detenido; el trabajo se conserva." : "Sin cambios pendientes." };
    if (path === "/prestaciones-costo/atenciones-disponibles/") data = [{ id: 44, titulo: "Consulta médica", flujo_nombre: "Ingreso Escuela", version_numero: 1, area: 3, area_nombre: area.nombre }];
    if (path === "/prestaciones-costo/") data = lista(db.prestaciones);
    if (path === "/componentes-costo/") data = lista(db.componentes);
    if (path === "/valores-componentes/") data = lista(db.valores);
    if (path === "/hechos-costo/") data = lista([{ id: 17, institucion: 2, area: 3, caso: 21, ocurrida_en: "2026-09-14T10:00:00Z", actualizado_en: "2026-09-14T10:00:01Z", total_conocido: "10000.00", total_compartido_conocido: "3333.34", total_directo_es_completo: true, total_es_completo: false, reparto_actualizando: db.pendientes, imputaciones: [{ componente: 1, componente_nombre: "Materiales", importe: "10000.00", ajustes: [] }], repartos_compartidos: [{ reparto: 1, gasto: 1, concepto: "Electricidad", periodo_economico: "2026-09-01", version: 1, importe: "3333.34" }], faltantes: [{ motivo: "otras_fuentes", motivo_display: "Otras fuentes aún no integradas" }], limite: "Componentes directos configurados y atribuciones visibles; no equivale a costo total del paciente." }]);
    if (path === "/hechos-costo/" && db.ocultarHechos) data = lista([]);
    return route.fulfill({ status: 200, json: data });
  });
  return { db, peticiones, escrituras };
}

test("evolución distingue faltantes, referencia e incompletos y abre sólo gastos esperados", async ({ page }, testInfo) => {
  const { db, peticiones, escrituras } = await escenario(page);
  db.evolucion = { conceptos: [{ id: 1, nombre: "Electricidad" }], concepto: 1, moneda: "ARS", meses: [
    { periodo_economico: "2026-04-01", importe_aprobado: "100.01", monto_referencia: "120.00", estado: "completo" },
    { periodo_economico: "2026-05-01", importe_aprobado: "110.01", monto_referencia: "120.00", estado: "completo" },
    { periodo_economico: "2026-06-01", importe_aprobado: null, monto_referencia: null, estado: "sin_control" },
    { periodo_economico: "2026-07-01", importe_aprobado: "0.00", monto_referencia: "125.00", estado: "sin_carga" },
    { periodo_economico: "2026-08-01", importe_aprobado: "80.01", monto_referencia: "125.00", estado: "incompleto" },
    { periodo_economico: "2026-09-01", importe_aprobado: "120.01", monto_referencia: "125.00", estado: "mes_abierto" },
  ] };
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/finanzas?mes=2026-09&area=3");
  const grafico = page.getByRole("region", { name: "Gráfico de evolución de gastos mensuales" });
  await expect(grafico).toHaveCount(0);
  expect(peticiones.some((u) => u.pathname === "/api/reportes-finanzas/evolucion/")).toBe(false);
  await page.getByRole("button", { name: "Evolución mensual", exact: true }).click();
  await expect(grafico.getByRole("button")).toHaveCount(4);
  await expect(grafico.getByRole("button", { name: "Ver gastos aprobados de 2026-07" })).toHaveCount(0);
  await expect(grafico.locator(".recharts-line")).toHaveCount(2);
  await page.getByRole("button", { name: "Comparar con referencias", exact: true }).click();
  await expect(grafico.locator(".recharts-line")).toHaveCount(3);
  await page.getByText("Ver importes mensuales", { exact: true }).click();
  await expect(page.getByRole("list", { name: "Importes mensuales" }).getByText(/Sin configuración mensual vigente/)).toBeVisible();
  await expect(page.getByText("Aprobado registrado: ARS 0,00 · carga pendiente", { exact: true })).toBeVisible();
  await page.getByRole("combobox", { name: "Período de evolución" }).selectOption("6");
  await expect.poll(() => peticiones.some((u) => u.pathname === "/api/reportes-finanzas/evolucion/" && u.searchParams.get("meses") === "6")).toBe(true);
  await grafico.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("evolucion.png"), animations: "disabled" });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => grafico.evaluate((e) => e.scrollWidth <= e.clientWidth)).toBe(true);
  await grafico.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("evolucion-movil.png"), animations: "disabled" });
  await grafico.getByRole("button", { name: "Ver gastos aprobados de 2026-08 · Electricidad" }).click();
  await expect(page).toHaveURL(/mes=2026-08/);
  await expect(page).toHaveURL(/area=3/);
  await expect(page).toHaveURL(/gastos_f_control_mensual=true/);
  await expect(page).toHaveURL(/gastos_f_concepto=1/);
  await expect.poll(() => peticiones.some((u) => u.pathname === "/api/gastos/" && u.searchParams.get("control_mensual") === "true" && u.searchParams.get("periodo_economico") === "2026-08-01")).toBe(true);
  await expect(page.getByRole("button", { name: "Quitar filtro Gastos mensuales", exact: true })).toBeVisible();
  expect(escrituras).toHaveLength(0);
});

test("dos niveles mantienen el parentesco de sectores y los filtros de cada nivel", async ({ page }, testInfo) => {
  const { db, escrituras } = await escenario(page);
  db.reporte.agrupaciones = [
    { ...reporte.agrupaciones[0], aprobados: "80.01", pendientes_aprobacion: "20.00" },
    { ...reporte.agrupaciones[0], concepto: 2, concepto_nombre: "Limpieza", aprobados: "50.00", pendientes_aprobacion: "50.01" },
  ];
  Object.assign(db.reporte, { aprobados: "130.01", pendientes_aprobacion: "70.01", distribuido: "0.00", sin_distribuir: "130.01" });
  db.reporte.agrupaciones.forEach((g) => { g.distribuido = "0.00"; g.sin_distribuir = g.aprobados; });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/finanzas?mes=2026-09&area=3");
  await page.getByRole("button", { name: "Dos niveles", exact: true }).click();
  const niveles = page.locator(".recharts-pie");
  await expect(niveles).toHaveCount(2);
  await expect(niveles.first().locator(".recharts-pie-sector")).toHaveCount(2);
  await expect(niveles.nth(1).locator(".recharts-pie-sector")).toHaveCount(4);
  const grafico = page.getByRole("region", { name: "Gráfico de dos niveles por área, concepto y estado" });
  await expect(grafico.locator("svg text")).toHaveCount(0);
  expect((await grafico.boundingBox()).height).toBeLessThan(500);
  expect((await grafico.boundingBox()).height).toBeGreaterThanOrEqual(220);
  const colores = await niveles.evaluateAll((anillos) => anillos.map((a) => [...a.querySelectorAll("path.recharts-sector")].map((p) => p.getAttribute("fill"))));
  expect(colores[0].every((color) => !colores[1].includes(color))).toBe(true);
  expect(colores[0][0]).toBe(colores[0][1]); // Igual participación, igual color.
  // Un sector interior termina en el centro: no conserva el hueco de dona.
  expect(await niveles.first().locator("path.recharts-sector").first().getAttribute("d")).toMatch(/L\s*[\d.]+,[\d.]+\s*Z/i);
  // Los dos conceptos tienen igual peso (100,01): cada mitad interior debe
  // terminar en el mismo eje que su par de sectores exteriores.
  const inicios = await page.locator(".recharts-pie").evaluateAll((anillos) => anillos.map((anillo) => [...anillo.querySelectorAll("path.recharts-sector")].map((path) => {
    const punto = path.getPointAtLength(0);
    const marco = path.ownerSVGElement.viewBox.baseVal;
    const x = punto.x - marco.width / 2, y = punto.y - marco.height / 2;
    const radio = Math.hypot(x, y);
    return { x: x / radio, y: y / radio };
  })));
  for (const [padre, hijo] of [[0, 0], [1, 2]]) {
    expect(Math.hypot(inicios[0][padre].x - inicios[1][hijo].x, inicios[0][padre].y - inicios[1][hijo].y)).toBeLessThan(0.001);
  }
  const listado = page.getByRole("list", { name: "Importes del gráfico de dos niveles" });
  await expect(listado.getByText("Aprobado: ARS 80,01", { exact: false })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("dos-niveles.png"), animations: "disabled", fullPage: true });
  await listado.getByRole("button", { name: "Por aprobar: ARS 20,00", exact: true }).click();
  await expect(page).toHaveURL(/gastos_f_estado_operativo=pendiente_aprobacion/);
  await expect(page).toHaveURL(/gastos_f_concepto=1/);
  await page.getByRole("tab", { name: "Resumen", exact: true }).click();
  await page.getByRole("button", { name: "Dos niveles", exact: true }).click();
  const interior = page.locator(".recharts-pie").first().locator(".recharts-pie-sector").first();
  const marcoInterior = await interior.boundingBox();
  await interior.click({ position: { x: marcoInterior.width / 2, y: marcoInterior.height / 2 } });
  await expect(page).toHaveURL(/tab=gastos/);
  await expect(page).toHaveURL(/gastos_f_concepto=1/);
  await expect(page).not.toHaveURL(/gastos_f_estado_operativo/);
  await expect(page).not.toHaveURL(/undefined/);
  expect(escrituras).toHaveLength(0);
});

test("evolución sigue accesible sin gastos del mes y ocupa una sola vista", async ({ page }) => {
  const { db, peticiones } = await escenario(page);
  db.reporte.agrupaciones = [];
  db.evolucion = { conceptos: [{ id: 1, nombre: "Electricidad" }], concepto: 1, meses: [{ periodo_economico: "2026-08-01", importe_aprobado: "123.45", estado: "completo", monto_referencia: null }] };
  await page.goto("/finanzas?mes=2026-09");
  await expect(page.getByText("Todavía no hay gastos para estos filtros", { exact: true })).toBeVisible();
  expect(peticiones.some((u) => u.pathname === "/api/reportes-finanzas/evolucion/")).toBe(false);
  await page.getByRole("button", { name: "Evolución mensual", exact: true }).click();
  await expect(page.getByRole("region", { name: "Gráfico de evolución de gastos mensuales" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Comparar", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Listado", exact: true }).click();
  await expect(page.getByRole("region", { name: "Evolución de gastos mensuales", exact: true })).toHaveCount(0);
});

test("participación ordena azul a rojo, resalta ambos niveles y no reinicia el llenado", async ({ page }, testInfo) => {
  const { db } = await escenario(page);
  db.reporte.agrupaciones = [60, 30, 10].map((importe, i) => ({
    ...reporte.agrupaciones[0], concepto: i + 1, concepto_nombre: `Concepto ${i + 1}`,
    aprobados: String(importe), pendientes_aprobacion: "0.00",
  }));
  await page.goto("/finanzas?mes=2026-09");
  await page.getByRole("button", { name: "Dos niveles", exact: true }).click();
  const sectores = page.locator(".recharts-pie").first().locator("path.recharts-sector");
  await expect(sectores).toHaveCount(3);
  const matices = await sectores.evaluateAll((items) => items.map((e) => Number(e.getAttribute("fill").match(/hsl\(([^ ]+)/)[1])));
  expect(matices[0]).toBe(0);
  expect(matices[2]).toBe(225);
  expect(matices[1]).toBeGreaterThan(240);
  expect(matices[1]).toBeLessThan(360);
  const conceptos = page.getByRole("list", { name: "Importes del gráfico de dos niveles" });
  const elegido = conceptos.getByRole("button", { name: /Concepto 2/ });
  await elegido.focus();
  await expect(sectores.nth(0)).toHaveCSS("fill-opacity", "0.3");
  await expect(sectores.nth(1)).toHaveCSS("fill-opacity", "1");
  await expect(page.locator(".recharts-pie").nth(1).locator('path.recharts-sector[name*="Concepto 2"]').first()).toHaveCSS("fill-opacity", "1");
  // Espera acotada sólo para comprobar que el dibujo no vuelve a empezar al enfocar.
  await page.waitForTimeout(450);
  const antes = await sectores.evaluateAll((items) => items.map((e) => e.getAttribute("d")));
  await conceptos.getByRole("button", { name: /Concepto 3/ }).focus();
  expect(await sectores.evaluateAll((items) => items.map((e) => e.getAttribute("d")))).toEqual(antes);
  await page.getByRole("button", { name: "Dos niveles", exact: true }).focus();
  await expect(sectores.nth(0)).toHaveCSS("fill-opacity", "1");
  const graficoCircular = page.getByRole("region", { name: "Gráfico de dos niveles por área, concepto y estado" });
  await graficoCircular.screenshot({ path: testInfo.outputPath("participacion-desktop.png"), animations: "disabled" });
  await conceptos.screenshot({ path: testInfo.outputPath("conceptos-desktop.png"), animations: "disabled" });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => conceptos.evaluate((e) => e.scrollWidth <= e.clientWidth && e.scrollHeight <= e.clientHeight)).toBe(true);
  await graficoCircular.screenshot({ path: testInfo.outputPath("participacion-movil.png"), animations: "disabled" });
  await conceptos.screenshot({ path: testInfo.outputPath("conceptos-movil.png"), animations: "disabled" });
});

test("gráficos aprovechan el alto restante sin crecer por el viewport ni por el scroll", async ({ page }, testInfo) => {
  const { db, escrituras } = await escenario(page);
  db.reporte.agrupaciones = [60, 30, 10].map((valor, i) => ({ ...reporte.agrupaciones[0], concepto: i + 1, concepto_nombre: `Concepto ${i + 1}`, aprobados: `${valor}.00`, pendientes_aprobacion: "0.00" }));
  db.evolucion = { conceptos: [{ id: 1, nombre: "Electricidad" }], concepto: 1, meses: ["04", "05", "06", "07", "08", "09"].map((mes, i) => ({ periodo_economico: `2026-${mes}-01`, importe_aprobado: `${100 + i}.00`, monto_referencia: "120.00", estado: "completo" })) };
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/finanzas?mes=2026-09");
  for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080], [390, 844]]) {
    await page.setViewportSize({ width, height });
    for (const vista of ["Barras", "Dos niveles", "Evolución mensual"]) {
      await page.getByRole("button", { name: vista, exact: true }).click();
      const canvas = page.getByRole("region", { name: "Resumen de gastos", exact: true }).locator(".finance-chart-canvas");
      await expect(canvas.locator("svg.recharts-surface")).toBeVisible();
      await expect.poll(() => page.locator("main > .overflow-auto").evaluate((e) => e.scrollWidth <= e.clientWidth)).toBe(true);
      const dimensiones = await page.locator("main > .overflow-auto").evaluate((e) => ({ visible: e.clientHeight, total: e.scrollHeight }));
      console.log("Espacio gráfico", width, height, vista, dimensiones);
      // El resumen reúne gastos, dinero y costos: la página se desplaza, pero el
      // dibujo de gastos no puede colapsar ni crecer con el alto del viewport.
      if (width >= 1440) expect((await canvas.boundingBox()).height).toBeLessThanOrEqual(dimensiones.visible);
      if (vista === "Dos niveles" && width >= 1366) {
        const leyenda = await page.getByRole("list", { name: "Importes del gráfico de dos niveles" }).boundingBox();
        const dibujo = await canvas.boundingBox();
        expect(leyenda.x + leyenda.width).toBeLessThan(dibujo.x);
      }
      const altura = (await canvas.boundingBox()).height;
      await page.locator("main > .overflow-auto").evaluate((e) => { e.scrollTop = e.scrollHeight; });
      expect((await canvas.boundingBox()).height).toBeCloseTo(altura, 0);
      await page.locator("main > .overflow-auto").evaluate((e) => { e.scrollTop = 0; });
      await page.screenshot({ path: testInfo.outputPath(`espacio-${width}-${vista}.png`), animations: "disabled" });
    }
  }
  expect(escrituras).toHaveLength(0);
});

test("barras ordenan por la suma exacta de la comparación y dos niveles ordenan sus categorías", async ({ page }) => {
  const { db, escrituras } = await escenario(page);
  db.reporte.agrupaciones = [
    { ...reporte.agrupaciones[0], concepto: 1, concepto_nombre: "Menor aprobado", aprobados: "30.00", pendientes_aprobacion: "90.00", distribuido: "29.00", sin_distribuir: "1.00" },
    { ...reporte.agrupaciones[0], concepto: 2, concepto_nombre: "Mayor aprobado", aprobados: "100.00", pendientes_aprobacion: "0.00", distribuido: "10.00", sin_distribuir: "90.00" },
    { ...reporte.agrupaciones[0], concepto: 3, concepto_nombre: "Intermedio", aprobados: "70.00", pendientes_aprobacion: "10.00", distribuido: "0.00", sin_distribuir: "70.00" },
  ];
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/finanzas?mes=2026-09");
  const nombres = page.getByRole("region", { name: "Gráfico de barras por área y concepto" }).locator(".recharts-yAxis-tick-labels text");
  await expect(nombres).toHaveText([/Menor aprobado/, /Mayor aprobado/, /Intermedio/]);
  await page.getByRole("combobox", { name: "Ordenar", exact: true }).selectOption("menor");
  await expect(nombres).toHaveText([/Intermedio/, /Mayor aprobado/, /Menor aprobado/]);
  await page.getByRole("combobox", { name: "Comparar", exact: true }).selectOption("distribucion");
  await expect(nombres).toHaveText([/Menor aprobado/, /Intermedio/, /Mayor aprobado/]);
  await page.getByRole("combobox", { name: "Ordenar", exact: true }).selectOption("mayor");
  await expect(nombres).toHaveText([/Mayor aprobado/, /Intermedio/, /Menor aprobado/]);
  await page.getByRole("button", { name: "Dos niveles", exact: true }).click();
  const categorias = page.getByRole("list", { name: "Importes del gráfico de dos niveles" }).getByRole("listitem");
  await expect(categorias).toHaveText([/Mayor aprobado/, /Intermedio/, /Menor aprobado/]);
  const externos = page.locator(".recharts-pie").nth(1).locator("path.recharts-sector");
  const rellenos = await externos.evaluateAll((items) => items.map((e) => e.getAttribute("fill")));
  expect(rellenos.some((v) => v.startsWith("url(#"))).toBe(true);
  expect(rellenos.every((v) => v.startsWith("url(#") || v === "var(--color-texto-debil)")).toBe(true);
  expect(escrituras).toHaveLength(0);
});

test("gastos simplificados conservan detalle y filtros guardados; diferencias distinguen ausencia y signo", async ({ page }, testInfo) => {
  const { escrituras } = await escenario(page);
  const gasto = { id: 1, concepto_nombre: "Electricidad", area_nombre: area.nombre, periodo_economico: "2026-09-01", estado_operativo: "aprobado", estado: "aprobado", importe: "100.01", total_ajustes: "-20.00", importe_resultante: "80.01", registrado: "2026-09-14T12:00:00Z", ajustes: [{ id: 1, estado: "aprobado", aprobado: true, importe: "-20.00", motivo: "Corrección de factura", registrado: "2026-09-14T12:10:00Z" }], reemplazado_por: null };
  await page.route("**/api/gastos/**", (route) => route.fulfill({ json: lista([gasto]) }));
  await page.route("**/api/expectativas-gasto/calendario/**", (route) => route.fulfill({ json: lista(["1.00", "-1.00", "0.00", null].map((valor, i) => ({ ...calendario, id: i + 1, concepto_nombre: `Control ${i}`, importe_aprobado: ["99.00", "101.00", "100.00", "50.00"][i], diferencia_referencia: valor, monto_referencia: valor == null ? null : "100.00" }))) }));
  await page.goto("/finanzas?mes=2026-09&tab=gastos&gastos_ord=-total_ajustes&gastos_f_importe_min=20");
  const tabla = page.locator(".finance-table-content");
  await expect(tabla.getByRole("button", { name: "Ordenar por Importe original", exact: true })).toHaveCount(0);
  await expect(tabla.getByRole("button", { name: "Ordenar por Ajustes", exact: true })).toHaveCount(0);
  await expect(tabla.getByText("ARS 80,01", { exact: true })).toBeVisible();
  await expect(page.getByText("Orden guardado: ajustes (mayor a menor)", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Quitar filtro Importe original (ARS) desde", exact: true }).click();
  await expect(page).not.toHaveURL(/gastos_f_importe_min/);
  await page.getByRole("button", { name: "Ordenar por importe vigente", exact: true }).click();
  await expect(page).toHaveURL(/gastos_ord=importe_resultante/);
  await page.screenshot({ path: testInfo.outputPath("gastos-simplificados.png"), animations: "disabled" });
  await page.getByRole("button", { name: "Detalle", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("ARS 100,01");
  await expect(page.getByRole("dialog")).toContainText("ARS -20,00");
  await expect(page.getByRole("dialog")).toContainText("Corrección de factura");
  await page.getByRole("button", { name: "Cerrar detalle", exact: true }).click();
  await page.getByRole("tab", { name: "Gastos mensuales", exact: true }).click();
  const diferencias = tabla.locator('td[data-label="Diferencia"]');
  await expect(diferencias).toHaveText(["ARS +1,00", "ARS -1,00", "ARS 0,00", "-"]);
  await expect(diferencias.nth(0).locator("span")).toHaveClass(/text-badge-green-fg/);
  await expect(diferencias.nth(1).locator("span")).toHaveClass(/text-badge-error-fg/);
  await expect(diferencias.nth(2).locator("span")).toHaveClass(/text-texto-debil/);
  await expect(diferencias.nth(3).locator("span")).toHaveAttribute("aria-label", "Sin referencia");
  await page.screenshot({ path: testInfo.outputPath("control-diferencias.png"), animations: "disabled" });
  expect(escrituras).toHaveLength(0);
});

test("control mensual conserva columnas y permite desplazarlas sin romper encabezados", async ({ page }, testInfo) => {
  const { escrituras } = await escenario(page);
  await page.route("**/api/gastos/**", (route) => route.fulfill({ json: lista([{ id: 1, concepto_nombre: "Electricidad", area_nombre: area.nombre, periodo_economico: "2026-09-01", estado_operativo: "aprobado", importe: "100.00", importe_resultante: "100.00", registrado: "2026-09-14T12:00:00Z", reemplazado_por: null }]) }));
  await page.goto("/finanzas?mes=2026-09&tab=calendario");
  const contenido = page.locator(".finance-table-content");
  for (const width of [1366, 1440, 1578, 1734, 1738, 1920, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(contenido.locator("thead")).toBeVisible();
    const ordenar = page.getByRole("button", { name: /^Ordenar por Referencia mensual/ });
    await expect(ordenar).toBeVisible();
    // Una palabra del encabezado nunca debería partirse en dos líneas.
    expect(await contenido.locator('thead button[title^="Ordenar por"]').evaluateAll((elementos) => {
      for (const elemento of elementos) {
        const nodos = document.createTreeWalker(elemento, NodeFilter.SHOW_TEXT);
        for (let nodo = nodos.nextNode(); nodo; nodo = nodos.nextNode()) {
          for (const coincidencia of nodo.textContent.matchAll(/\S+/g)) {
            const rango = document.createRange();
            rango.setStart(nodo, coincidencia.index); rango.setEnd(nodo, coincidencia.index + coincidencia[0].length);
            if (rango.getClientRects().length > 1) return false;
          }
        }
      }
      return true;
    })).toBe(true);
    if (width === 1440) {
      await ordenar.click();
      await expect(page).toHaveURL(/calendario_ord=monto_referencia/);
    }
    await page.getByRole("button", { name: "Filtrar Referencia mensual", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "Filtrar Referencia mensual", exact: true })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(contenido.locator('td[data-label="Referencia mensual"]')).toHaveText("ARS 12.000,00");
    await expect(contenido.locator('td[data-label="Diferencia"]')).toHaveText("ARS +1.999,99");
    await expect.poll(() => contenido.evaluate((e) => getComputedStyle(e).overflowX === "auto" && e.getBoundingClientRect().right <= innerWidth + 1)).toBe(true);
    await contenido.scrollIntoViewIfNeeded();
    await page.screenshot({ path: testInfo.outputPath(`control-adaptado-${width}.png`), animations: "disabled" });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Administrar Electricidad", exact: false }).click();
  await expect(page.getByRole("dialog")).toContainText("Consultar historial");
  await page.getByRole("button", { name: "Cerrar detalle", exact: true }).click();
  await page.getByRole("tab", { name: "Gastos registrados", exact: true }).click();
  await expect(contenido.locator("thead")).toBeVisible();
  await expect(contenido.locator('td[data-label="Importe vigente"]')).toHaveText("ARS 100,00");
  expect(escrituras).toHaveLength(0);
});

test("orden por centavos distingue montos grandes, empates y negativos sin modificar la fuente", async ({ page }) => {
  const { db, escrituras } = await escenario(page);
  const valores = [["B", "999999999999999.98"], ["A", "999999999999999.99"], ["C", "999999999999999.98"], ["D", "-0.01"]];
  db.reporte.agrupaciones = valores.map(([nombre, monto], i) => ({ ...reporte.agrupaciones[0], concepto: i + 1, concepto_nombre: nombre, aprobados: monto, pendientes_aprobacion: "0.00" }));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/finanzas?mes=2026-09");
  const etiquetas = page.getByRole("region", { name: "Gráfico de barras por área y concepto" }).locator(".recharts-yAxis-tick-labels text");
  await expect(etiquetas).toHaveText([/·\s*A$/, /·\s*B$/, /·\s*C$/, /·\s*D$/]);
  await page.getByRole("combobox", { name: "Ordenar", exact: true }).selectOption("menor");
  await expect(etiquetas).toHaveText([/·\s*D$/, /·\s*B$/, /·\s*C$/, /·\s*A$/]);
  await page.getByRole("combobox", { name: "Ordenar", exact: true }).selectOption("nombre");
  await expect(etiquetas).toHaveText([/·\s*A$/, /·\s*B$/, /·\s*C$/, /·\s*D$/]);
  await page.getByRole("button", { name: "Dos niveles", exact: true }).click();
  await expect(page.getByRole("status")).toContainText(["Repartos actualizados", "Hay importes negativos"]);
  expect(db.reporte.agrupaciones.map((g) => [g.concepto_nombre, g.aprobados])).toEqual(valores);
  expect(escrituras).toHaveLength(0);
});

for (const cantidad of [2, 8, 24]) {
  test(`dos niveles conservan ${cantidad} categorías completas sin scroll interno`, async ({ page }, testInfo) => {
    const { db } = await escenario(page);
    db.reporte.agrupaciones = Array.from({ length: cantidad }, (_, i) => ({ ...reporte.agrupaciones[0], concepto: i + 1, concepto_nombre: `Concepto ${String(i + 1).padStart(2, "0")}`, aprobados: `${i + 1}.00`, pendientes_aprobacion: "0.50" }));
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/finanzas?mes=2026-09");
    await page.getByRole("button", { name: "Dos niveles", exact: true }).click();
    const categorias = page.getByRole("list", { name: "Importes del gráfico de dos niveles" });
    await expect(categorias.getByRole("listitem")).toHaveCount(cantidad);
    await expect(categorias.getByRole("listitem").first()).toContainText(`Concepto ${String(cantidad).padStart(2, "0")}`);
    await expect.poll(() => categorias.evaluate((e) => e.scrollHeight <= e.clientHeight && e.scrollWidth <= e.clientWidth)).toBe(true);
    const colores = await page.locator(".recharts-pie").first().locator("path.recharts-sector").evaluateAll((es) => es.map((e) => e.getAttribute("fill")));
    expect(new Set(colores).size).toBe(cantidad);
    const dibujo = page.getByRole("region", { name: "Gráfico de dos niveles por área, concepto y estado" });
    expect((await dibujo.boundingBox()).height).toBeLessThan(650);
    await page.getByRole("button", { name: "Cambiar a tema oscuro", exact: true }).click();
    await dibujo.scrollIntoViewIfNeeded();
    await page.screenshot({ path: testInfo.outputPath(`categorias-${cantidad}-oscuro.png`), animations: "disabled" });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect.poll(() => categorias.evaluate((e) => e.scrollHeight <= e.clientHeight && e.scrollWidth <= e.clientWidth)).toBe(true);
    await dibujo.scrollIntoViewIfNeeded();
    await page.screenshot({ path: testInfo.outputPath(`categorias-${cantidad}-movil.png`), animations: "disabled" });
  });
}

test("evolución conserva selección múltiple al cambiar rango y señala ausentes sin reemplazarlos", async ({ page }) => {
  const { peticiones, escrituras } = await escenario(page);
  await page.route("**/api/reportes-finanzas/evolucion/**", (route) => {
    const url = new URL(route.request().url()); peticiones.push(url);
    const conceptos = [{ id: 1, nombre: "Electricidad" }, ...(url.searchParams.get("meses") === "12" ? [{ id: 2, nombre: "Mantenimiento" }] : [])];
    return route.fulfill({ json: { conceptos, series: conceptos.map((c) => ({ ...c, meses: [{ periodo_economico: "2026-08-01", importe_aprobado: "12.01", estado: "completo" }] })), moneda: "ARS" } });
  });
  await page.goto("/finanzas?mes=2026-09");
  await page.getByRole("button", { name: "Evolución mensual", exact: true }).click();
  const conceptos = page.getByRole("list", { name: "Conceptos comparados" });
  await expect(conceptos.getByRole("listitem")).toHaveCount(2);
  await page.getByRole("button", { name: "Quitar concepto Electricidad", exact: true }).click();
  await expect(conceptos.getByRole("listitem")).toHaveCount(1);
  await page.getByRole("combobox", { name: "Período de evolución" }).selectOption("6");
  await expect(page.getByText("Hay 1 conceptos seleccionados sin configuración mensual visible", { exact: false })).toBeVisible();
  await expect(page.getByRole("region", { name: "Gráfico de evolución de gastos mensuales" })).toHaveCount(0);
  await page.getByRole("combobox", { name: "Período de evolución" }).selectOption("12");
  await expect(conceptos.getByRole("listitem")).toHaveCount(1);
  await expect(conceptos.getByRole("button", { name: "Destacar Mantenimiento" })).toBeVisible();
  expect(peticiones.filter((u) => u.pathname.endsWith("/evolucion/")).every((u) => !u.searchParams.has("concepto"))).toBe(true);
  expect(escrituras).toHaveLength(0);
});

test("evolución muestra todas, filtra localmente, destaca sin cambiar colores y compara todas las referencias", async ({ page }, testInfo) => {
  const { db, peticiones, escrituras } = await escenario(page);
  db.evolucion.conceptos = [{ id: 1, nombre: "Electricidad" }, { id: 2, nombre: "Limpieza" }, { id: 3, nombre: "Mantenimiento" }];
  db.evolucion.series = db.evolucion.conceptos.map((c, i) => ({ ...c, meses: ["04", "05", "06", "07", "08", "09"].map((mes, m) => ({
    periodo_economico: `2026-${mes}-01`, importe_aprobado: `${(i + 1) * 100 + m * (i + 1) * 10}.01`, monto_referencia: i === 2 ? null : `${(i + 1) * 120}.00`,
    controles: 1, estado: m === 5 ? "mes_abierto" : "completo",
  })) }));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/finanzas?mes=2026-09&area=3");
  await page.getByRole("button", { name: "Evolución mensual", exact: true }).click();
  const leyenda = page.getByRole("list", { name: "Conceptos comparados" });
  const grafico = page.getByRole("region", { name: "Gráfico de evolución de gastos mensuales" });
  await expect(leyenda.getByRole("listitem")).toHaveCount(3);
  await expect(grafico.locator(".recharts-line")).toHaveCount(6);
  const punto = grafico.getByRole("button", { name: "Ver gastos aprobados de 2026-08 · Limpieza", exact: true });
  const color = await punto.getAttribute("stroke");
  await page.getByRole("button", { name: "Destacar Limpieza", exact: true }).click();
  await expect(page.getByRole("button", { name: "Destacar Limpieza", exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(grafico.getByRole("button", { name: "Ver gastos aprobados de 2026-08 · Electricidad", exact: true })).toHaveAttribute("opacity", "0.2");
  await punto.hover();
  const tooltip = page.getByRole("tooltip");
  await expect(tooltip).toContainText("Electricidad");
  await expect(tooltip).toContainText("Limpieza");
  await expect(tooltip).toContainText("Mantenimiento");
  await expect(tooltip).toContainText("ARS 280,01");
  const ayuda = await page.getByRole("tooltip").boundingBox();
  expect(ayuda.y).toBeGreaterThanOrEqual(0);
  expect(ayuda.y + ayuda.height).toBeLessThanOrEqual(900);
  expect(ayuda.x + ayuda.width).toBeLessThanOrEqual(1440);
  await page.screenshot({ path: testInfo.outputPath("evolucion-ayuda-completa.png"), animations: "disabled" });
  await page.keyboard.press("Escape");
  await expect(page.getByRole("tooltip")).toBeHidden();
  await page.getByRole("button", { name: "Comparar con referencias", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "Concepto de referencia" })).toHaveCount(0);
  await expect(grafico.locator(".recharts-line")).toHaveCount(8);
  await page.getByRole("button", { name: "Quitar concepto Electricidad", exact: true }).click();
  await expect(punto).toHaveAttribute("stroke", color);
  await expect(leyenda.getByRole("listitem")).toHaveCount(2);
  await page.getByRole("button", { name: "Elegir conceptos de evolución" }).click();
  const selector = page.getByRole("dialog", { name: "Elegir conceptos de evolución" });
  await selector.getByRole("textbox").fill("Limp");
  await expect(selector.getByRole("checkbox")).toHaveCount(1);
  await selector.getByRole("checkbox", { name: "Limpieza" }).uncheck();
  await selector.getByRole("textbox").fill("");
  await selector.getByRole("button", { name: "Quitar todos", exact: true }).click();
  await page.keyboard.press("Escape");
  await expect(page.getByText("No hay conceptos seleccionados disponibles para comparar.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Mostrar todos los conceptos", exact: true }).click();
  await expect(leyenda.getByRole("listitem")).toHaveCount(3);
  await expect(punto).toHaveAttribute("stroke", color);
  await page.screenshot({ path: testInfo.outputPath("evolucion-multiple.png"), animations: "disabled" });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.locator(".finance-page").evaluate((e) => e.scrollWidth <= e.clientWidth)).toBe(true);
  await grafico.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("evolucion-multiple-movil.png"), animations: "disabled" });
  // Teclado abre la categoría exacta, no la primera ni el total.
  await punto.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/mes=2026-08/);
  await expect(page).toHaveURL(/area=3/);
  await expect(page).toHaveURL(/gastos_f_concepto=2/);
  await expect(page).toHaveURL(/gastos_f_control_mensual=true/);
  expect(peticiones.filter((u) => u.pathname.endsWith("/evolucion/"))).toHaveLength(1);
  expect(escrituras).toHaveLength(0);
});

test("evolución muestra 24 conceptos sin recorte de selección y deja consultar todos los importes", async ({ page }, testInfo) => {
  const { db } = await escenario(page);
  db.evolucion.conceptos = Array.from({ length: 24 }, (_, i) => ({ id: i + 1, nombre: `Concepto mensual ${String(i + 1).padStart(2, "0")}` }));
  db.evolucion.series = db.evolucion.conceptos.map((c) => ({ ...c, meses: ["07", "08", "09"].map((m) => ({ periodo_economico: `2026-${m}-01`, controles: 1, importe_aprobado: `${c.id * 100}.01`, estado: "completo", monto_referencia: null })) }));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/finanzas?mes=2026-09");
  await page.getByRole("button", { name: "Evolución mensual", exact: true }).click();
  const leyenda = page.getByRole("list", { name: "Conceptos comparados" });
  await expect(leyenda.getByRole("listitem")).toHaveCount(24);
  await expect(page.getByRole("button", { name: "Elegir conceptos de evolución" })).toContainText("24/24");
  const grafico = page.getByRole("region", { name: "Gráfico de evolución de gastos mensuales" });
  await expect(grafico.locator(".recharts-line")).toHaveCount(48);
  await grafico.getByRole("button", { name: "Ver gastos aprobados de 2026-08 · Concepto mensual 24", exact: true }).hover();
  const ayuda = page.getByRole("tooltip");
  await expect(ayuda).toContainText("Concepto mensual 24");
  await ayuda.hover();
  await page.mouse.wheel(0, 2400);
  await expect(ayuda).toBeVisible();
  await expect.poll(() => ayuda.evaluate((e) => e.scrollTop)).toBeGreaterThan(0);
  await page.keyboard.press("Escape");
  await expect(ayuda).toBeHidden();
  await grafico.getByRole("button", { name: "Ver gastos aprobados de 2026-07 · Concepto mensual 24", exact: true }).hover();
  await expect(ayuda).toBeVisible();
  await expect(ayuda).toContainText("2026-07");
  await page.getByRole("button", { name: "Evolución mensual", exact: true }).hover();
  await expect(ayuda).toBeHidden();
  await page.getByRole("button", { name: "Ver importes mensuales", exact: true }).click();
  await expect(page.getByRole("list", { name: "Importes mensuales" }).getByRole("button")).toHaveCount(72);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.locator(".finance-page").evaluate((e) => e.scrollWidth <= e.clientWidth)).toBe(true);
  await expect.poll(() => leyenda.evaluate((e) => e.scrollHeight <= e.clientHeight)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("evolucion-24-conceptos-movil.png"), animations: "disabled" });
});

test("evolución filtra estados por concepto y conserva referencias completas, parciales y cero", async ({ page }, testInfo) => {
  const { db, peticiones, escrituras } = await escenario(page);
  const fila = (mes, importe, estado, referencia) => ({ periodo_economico: `2026-${mes}-01`, controles: 1, importe_aprobado: importe, estado, monto_referencia: referencia });
  db.evolucion.series = [
    { id: 1, nombre: "Electricidad", meses: [fila("07", "101.01", "completo", "120.00"), fila("08", "111.01", "incompleto", "130.00"), fila("09", "121.01", "mes_abierto", "140.00")] },
    { id: 2, nombre: "Limpieza", meses: [fila("07", "202.02", "incompleto", null), fila("08", "212.02", "completo", "0.00"), fila("09", "0.00", "sin_carga", null)] },
    { id: 3, nombre: "Mantenimiento", meses: [fila("07", null, "sin_control", null), fila("08", "303.03", "completo", null), fila("09", "313.03", "mes_abierto", null)] },
  ];
  db.evolucion.conceptos = db.evolucion.series.map(({ id, nombre }) => ({ id, nombre }));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/finanzas?mes=2026-09&area=3");
  await page.getByRole("button", { name: "Evolución mensual", exact: true }).click();
  const grafico = page.getByRole("region", { name: "Gráfico de evolución de gastos mensuales" });
  const filtro = page.getByRole("combobox", { name: "Estado de los meses" });
  await expect(filtro).toHaveValue("ambos");
  await expect(grafico.getByRole("button")).toHaveCount(7);
  await page.getByRole("button", { name: "Comparar con referencias", exact: true }).click();
  const colorLuz = await grafico.getByRole("button", { name: "Ver gastos aprobados de 2026-07 · Electricidad", exact: true }).getAttribute("stroke");
  const colorLimpieza = await grafico.getByRole("button", { name: "Ver gastos aprobados de 2026-08 · Limpieza", exact: true }).getAttribute("stroke");
  const refLuz = grafico.locator(`circle.recharts-line-dot[stroke="${colorLuz}"]`);
  const refLimpieza = grafico.locator(`circle.recharts-line-dot[stroke="${colorLimpieza}"]`);
  // La referencia aislada en cero debe tener un punto aunque no forme un segmento.
  await expect(refLuz).toHaveCount(3);
  await expect(refLimpieza).toHaveCount(1);
  await expect(grafico.locator(".recharts-line")).toHaveCount(8);
  await filtro.selectOption("completo");
  await expect(grafico.getByRole("button")).toHaveCount(3);
  await expect(grafico.getByRole("button", { name: "Ver gastos aprobados de 2026-08 · Electricidad", exact: true })).toHaveCount(0);
  await expect(grafico.getByRole("button", { name: "Ver gastos aprobados de 2026-08 · Limpieza", exact: true })).toHaveCount(1);
  await expect(refLuz).toHaveCount(3);
  await expect(refLimpieza).toHaveCount(1);
  await grafico.getByRole("button", { name: "Ver gastos aprobados de 2026-08 · Limpieza", exact: true }).hover();
  const ayuda = page.getByRole("tooltip");
  await expect(ayuda).toContainText("Referencia: ARS 130,00");
  await expect(ayuda).toContainText("Referencia: ARS 0,00");
  await expect(ayuda).not.toContainText("111,01");
  await expect(ayuda).toContainText("212,02");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Ver importes mensuales", exact: true }).click();
  const listaMeses = page.getByRole("list", { name: "Importes mensuales" });
  await expect(listaMeses.getByRole("button")).toHaveCount(3);
  await expect(listaMeses).not.toContainText("111,01");
  await expect(listaMeses).toContainText("Referencia: ARS 140,00");
  await filtro.selectOption("provisional");
  await expect(grafico.getByRole("button")).toHaveCount(4);
  await expect(listaMeses.getByRole("button")).toHaveCount(4);
  await expect(listaMeses).not.toContainText("212,02");
  await expect(listaMeses).toContainText("Referencia: ARS 0,00");
  await expect(refLuz).toHaveCount(3);
  await page.getByRole("button", { name: "Ocultar importes mensuales", exact: true }).click();
  await page.screenshot({ path: testInfo.outputPath("evolucion-estados-referencias.png"), animations: "disabled" });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.locator(".finance-page").evaluate((e) => e.scrollWidth <= e.clientWidth)).toBe(true);
  await grafico.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("evolucion-estados-referencias-movil.png"), animations: "disabled" });
  await page.getByRole("button", { name: "Quitar concepto Electricidad", exact: true }).click();
  await page.getByRole("button", { name: "Quitar concepto Limpieza", exact: true }).click();
  await expect(page.getByRole("button", { name: "Comparar con referencias", exact: true })).toBeDisabled();
  await expect(grafico.locator(".recharts-line")).toHaveCount(2);
  await page.getByRole("button", { name: "Elegir conceptos de evolución" }).click();
  const selector = page.getByRole("dialog", { name: "Elegir conceptos de evolución" });
  await selector.getByRole("checkbox", { name: "Limpieza", exact: true }).check();
  await selector.getByRole("checkbox", { name: "Mantenimiento", exact: true }).uncheck();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Ocultar referencias", exact: true })).toBeEnabled();
  await expect(grafico.locator(".recharts-line")).toHaveCount(3);
  expect(peticiones.filter((u) => u.pathname.endsWith("/evolucion/"))).toHaveLength(1);
  db.evolucion.series[1].meses[0].estado = "completo";
  await page.getByRole("combobox", { name: "Período de evolución" }).selectOption("6");
  await expect(page.getByText("No hay importes aprobados para graficar con este filtro. Se mantienen las referencias de todo el período.", { exact: true })).toBeVisible();
  await expect(grafico.getByRole("button")).toHaveCount(0);
  await expect(refLimpieza).toHaveCount(1);
  expect(escrituras).toHaveLength(0);
});

test("sin distribuir abre sólo fuentes con saldo y conserva filtros territoriales", async ({ page }) => {
  const { db, peticiones, escrituras } = await escenario(page);
  Object.assign(db.reporte.agrupaciones[0], { aprobados: "150.00", distribuido: "100.00", sin_distribuir: "50.00" });
  await page.goto("/finanzas?mes=2026-09&area=3");
  await page.getByRole("button", { name: "Dos niveles", exact: true }).click();
  await page.getByRole("combobox", { name: "Comparar", exact: true }).selectOption("distribucion");
  await page.getByRole("button", { name: "Sin distribuir: ARS 50,00", exact: true }).click();
  await expect(page).toHaveURL(/repartos_f_sin_distribuir=true/);
  await expect(page).toHaveURL(/area=3/);
  await expect(page).toHaveURL(/repartos_f_gasto__concepto=1/);
  await expect.poll(() => peticiones.some((u) => u.pathname.endsWith("/repartos-gasto/") && u.searchParams.get("sin_distribuir") === "true" && u.searchParams.get("gasto__periodo_economico") === "2026-09-01")).toBe(true);
  await page.getByRole("button", { name: "Quitar filtro Saldo sin distribuir", exact: true }).click();
  await expect(page).not.toHaveURL(/repartos_f_sin_distribuir/);
  expect(escrituras).toHaveLength(0);
});

test("evolución retira importes al perder acceso", async ({ page }) => {
  const { db } = await escenario(page);
  db.evolucion = { conceptos: [{ id: 1, nombre: "Electricidad" }], concepto: 1, meses: [{ periodo_economico: "2026-08-01", importe_aprobado: "123.45", estado: "completo", monto_referencia: null }] };
  await page.goto("/finanzas?mes=2026-09");
  await page.getByRole("button", { name: "Evolución mensual", exact: true }).click();
  await page.getByText("Ver importes mensuales", { exact: true }).click();
  await expect(page.getByText("ARS 123,45", { exact: true })).toBeVisible();
  await page.route("**/api/reportes-finanzas/evolucion/**", (route) => route.fulfill({ status: 403, json: { detail: "Sin acceso" } }));
  await page.getByRole("combobox", { name: "Período de evolución" }).selectOption("6");
  await expect(page.getByRole("alert").getByText("No tenés permiso para ver esto", { exact: true })).toBeVisible();
  await expect(page.getByText("ARS 123,45", { exact: true })).toHaveCount(0);
});

test("estado actualizado deja texto y fecha dentro de su ayuda", async ({ page }) => {
  await escenario(page);
  await page.goto("/finanzas?mes=2026-09");
  await expect(page.getByText("Repartos actualizados", { exact: true })).toBeVisible();
  await expect(page.getByText("Sin cambios pendientes.", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Última ejecución correcta:", { exact: false })).toHaveCount(0);
  await page.getByRole("button", { name: "Cuándo se actualizan los repartos", exact: true }).click();
  const ayuda = page.getByRole("dialog", { name: "Cuándo se actualizan los repartos", exact: true });
  await expect(ayuda).toContainText("Sin cambios pendientes.");
  await expect(ayuda).toContainText("Última ejecución correcta:");
});

test("listas financieras con scroll horizontal conservan importes, filtros y acciones", async ({ page }, testInfo) => {
  await escenario(page);
  await page.route("**/api/gastos/**", (route) => route.fulfill({ json: lista([{ id: 1, concepto_nombre: "Electricidad de edificios y consultorios del hospital", area_nombre: area.nombre, periodo_economico: "2026-09-01", estado_operativo: "aprobado", estado: "aprobado", importe: "999999999999999.99", total_ajustes: "-10.00", importe_resultante: "999999999999989.99", registrado: "2026-09-14T12:00:00Z", ajustes: [], reemplazado_por: null }]) }));
  await page.route("**/api/repartos-gasto/**", (route) => route.fulfill({ json: lista([{ id: 1, gasto: 1, concepto_nombre: "Electricidad", area_nombre: area.nombre, periodo_economico: "2026-09-01", estado: "distribuido", saldo_centavos: 10001, saldo_no_atribuido_centavos: 0, atribuciones: 0, vigente: true, version: 1 }]) }));
  await page.goto("/finanzas?mes=2026-09");
  for (const ancho of [1440, 1024, 390]) {
    await page.setViewportSize({ width: ancho, height: 1100 });
    for (const tab of ["Gastos mensuales", "Gastos registrados", "Repartos", "Costos por atención", "Resumen"]) {
      await page.getByRole("tab", { name: tab, exact: true }).click();
      if (tab === "Resumen") await page.getByRole("button", { name: "Listado", exact: true }).click();
      await expect(page.locator(".finance-table-content")).toHaveCount(1);
      await expect.poll(() => page.locator(".finance-table-content").evaluateAll((nodos) => nodos.every((e) => getComputedStyle(e).overflowX === "auto" && e.getBoundingClientRect().right <= innerWidth + 1))).toBe(true);
      await expect(page.locator(".finance-table-content table")).toHaveCSS("display", "table");
      await expect(page.locator(".finance-table-content thead")).toBeVisible();
    }
  }
  await page.getByRole("tab", { name: "Gastos mensuales", exact: true }).click();
  await page.getByRole("button", { name: "Ordenar por Importe aprobado", exact: true }).click();
  await expect(page).toHaveURL(/calendario_ord=importe_aprobado/);
  await page.getByRole("button", { name: "Filtrar Referencia mensual", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Filtrar Referencia mensual", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.locator(".finance-table").scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("control-sin-scroll-movil.png"), animations: "disabled" });
  await page.getByRole("button", { name: "Administrar Electricidad", exact: false }).click();
  await expect(page.getByRole("dialog")).toContainText("ARS 1.999,99");
  await page.getByRole("button", { name: "Historial de configuración", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Historial de configuración · Electricidad" })).toBeVisible();
  await expect.poll(() => page.getByRole("dialog").locator(".finance-table-content").evaluate((e) => getComputedStyle(e).overflowX === "auto" && e.getBoundingClientRect().right <= innerWidth + 1)).toBe(true);
  await page.route("**/api/expectativas-gasto/1/indicaciones/**", (route) => route.fulfill({ json: lista([{ id: 1, periodo_economico: "2026-09-01", estado: "carga_completa", registrado: "2026-09-14T12:00:00Z" }]) }));
  await page.getByRole("button", { name: "Historial de carga", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Historial · Electricidad" })).toBeVisible();
  await expect(page.getByRole("dialog").getByText("Carga completa", { exact: true })).toBeVisible();
  await expect.poll(() => page.getByRole("dialog").locator(".finance-table-content").evaluate((e) => getComputedStyle(e).overflowX === "auto" && e.getBoundingClientRect().right <= innerWidth + 1)).toBe(true);
});

test("filtros y tabs comparten fila, cabecera estable y límite explicado en ayuda", async ({ page }, testInfo) => {
  await escenario(page);
  await page.goto("/finanzas?mes=2026-09&area=3");
  const grupo = page.getByRole("group", { name: "Filtros y secciones de finanzas" });
  await expect(grupo.getByRole("tablist")).toBeVisible();
  // Comparar vistas con la misma fuente, no fallback contra Inter recién cargada.
  await page.evaluate(() => document.fonts.ready);
  const filtro = await grupo.getByRole("combobox", { name: "Área", exact: true }).boundingBox();
  const tabs = await grupo.getByRole("tablist").boundingBox();
  expect(Math.abs(tabs.y + tabs.height - filtro.y - filtro.height)).toBeLessThan(3);
  await page.getByRole("button", { name: "Qué información incluye Finanzas", exact: true }).click();
  await expect(page.getByText("No existe todavía un cálculo integral", { exact: false })).toBeVisible();
  await page.keyboard.press("Escape");
  const controles = page.getByRole("group", { name: "Controles del resumen" });
  const inicial = await controles.boundingBox();
  const botones = await controles.getByRole("group").boundingBox();
  for (const vista of ["Dos niveles", "Listado", "Barras"]) {
    await controles.getByRole("button", { name: vista, exact: true }).click();
    const actual = await controles.boundingBox();
    const posicion = await controles.getByRole("group").boundingBox();
    expect(Math.abs(actual.height - inicial.height)).toBeLessThan(2);
    expect(Math.abs(posicion.x - botones.x)).toBeLessThan(2);
    expect(Math.abs(posicion.y - botones.y)).toBeLessThan(2);
  }
  await barrasDeGastos(page).first().hover();
  await page.mouse.move(0, 0);
  await page.screenshot({ path: testInfo.outputPath("resumen-compacto.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("filtros-movil.png") });
});

async function abrirEditorPermisos(page) {
  await page.goto("/administracion");
  await page.getByRole("row").filter({ hasText: "Contabilidad Escuela" }).click();
  await page.getByRole("region", { name: "Permisos financieros", exact: true }).locator("summary").filter({ hasText: /^Permisos financieros$/ }).click();
}

test("permiso existente aparece marcado sin modificar su alcance", async ({ page }, testInfo) => {
  const { escrituras } = await escenario(page, { concesiones: [{ id: 1, membresia: 8, accion: "ver_gastos", areas: [3], todas_las_areas: false, permite_sensibles: false }] });
  await abrirEditorPermisos(page);
  const check = page.getByRole("checkbox", { name: "Ver gastos", exact: true });
  await expect(check).toBeEnabled();
  await expect(check).toBeChecked();
  await page.getByText("Alcance de Ver gastos", { exact: true }).click();
  await expect(page.getByLabel("Consultorios Escuela · Ver gastos", { exact: true })).toBeChecked();
  await expect(page.getByLabel("Incluir información sensible · Ver gastos", { exact: true })).not.toBeChecked();
  expect(escrituras).toHaveLength(0);
  await page.screenshot({ path: testInfo.outputPath("permisos-checklist.png"), fullPage: true, animations: "disabled" });
});

test("detalles separan importes, contexto e historial sin cambiar cálculos", async ({ page }, testInfo) => {
  const { escrituras } = await escenario(page);
  const gasto = { id: 1, concepto_nombre: "Electricidad", area_nombre: area.nombre, periodo_economico: "2026-09-01", estado_operativo: "aprobado", estado: "aprobado", importe: "100.01", total_ajustes: "-20.00", importe_resultante: "80.01", registrado: "2026-09-14T12:00:00Z", aprobado_en: "2026-09-14T12:05:00Z", ajustes: [{ id: 1, estado: "aprobado", aprobado: true, importe: "-20.00", motivo: "Corrección de factura", registrado: "2026-09-14T12:10:00Z" }], reemplazado_por: null };
  await page.route("**/api/gastos/**", (route) => route.fulfill({ json: lista([gasto]) }));
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto("/finanzas?mes=2026-09&tab=gastos");
  await page.getByRole("button", { name: "Detalle", exact: true }).click();
  const modal = page.getByRole("dialog");
  await expect(modal.getByRole("region", { name: "Importe del gasto" })).toContainText("ARS 80,01");
  await expect(modal.getByText("ARS 80,01", { exact: true })).toHaveCSS("font-size", "22px");
  await expect(modal.getByRole("heading", { name: "Registro y seguimiento" })).toBeVisible();
  await expect(modal.getByText("Corrección de factura", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("detalle-gasto.png"), fullPage: true, animations: "disabled" });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => modal.evaluate((e) => e.scrollWidth <= e.clientWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("detalle-gasto-movil.png"), animations: "disabled" });
  await page.getByRole("button", { name: "Cerrar detalle", exact: true }).click();
  await page.getByRole("tab", { name: "Gastos mensuales", exact: true }).click();
  await page.getByRole("button", { name: "Administrar Electricidad · Consultorios Escuela", exact: true }).click();
  await expect(modal.getByRole("region", { name: "Importes de gastos mensuales" })).toContainText("ARS 1.999,99");
  await expect(modal.getByRole("heading", { name: "Consultar historial" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("detalle-control-movil.png"), animations: "disabled" });
  await page.getByRole("button", { name: "Cerrar detalle", exact: true }).click();
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.getByRole("tab", { name: "Costos por atención", exact: true }).click();
  await page.getByRole("button", { name: "Ver composición", exact: true }).click();
  await expect(modal.getByRole("region", { name: "Importes conocidos de la atención" })).toContainText("ARS 10.000,00");
  await expect(modal.getByRole("heading", { name: "Componentes directos" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("detalle-costo.png"), fullPage: true, animations: "disabled" });
  expect(escrituras).toHaveLength(0);
});

for (const movimiento of ["no-preference", "reduce"]) {
  test(`llenado de barras respeta movimiento y no se reinicia por sondeos (${movimiento})`, async ({ page }) => {
    const { peticiones } = await escenario(page);
    let refrescar = false;
    await page.route("**/api/procesamiento-finanzas/**", (route) => route.fulfill({ json: { estado: "actualizado", worker_activo: true, mensaje: "Sin pendientes", ultimo_exito: refrescar ? "2026-09-14T12:00:01Z" : "2026-09-14T12:00:00Z" } }));
    await page.emulateMedia({ reducedMotion: movimiento });
    await page.addInitScript(() => {
      window.anchosGrafico = new Set();
      new MutationObserver(() => {
        const barra = document.querySelector(".recharts-bar-rectangle path");
        if (barra) { const ancho = barra.getBBox().width; if (ancho > 0) window.anchosGrafico.add(Math.round(ancho * 10)); }
      }).observe(document, { subtree: true, attributes: true, childList: true });
    });
    await page.goto("/finanzas?mes=2026-09");
    await barrasDeGastos(page).first().hover();
    const cantidad = await page.evaluate(() => window.anchosGrafico.size);
    expect(cantidad).toBeGreaterThan(0);
    if (movimiento === "reduce") expect(cantidad).toBeLessThanOrEqual(2);
    else expect(cantidad).toBeGreaterThan(2);
    await page.evaluate(() => window.anchosGrafico.clear());
    refrescar = true;
    await expect.poll(() => peticiones.filter((u) => u.pathname === "/api/reportes-finanzas/").length).toBeGreaterThanOrEqual(2);
    expect(await page.evaluate(() => window.anchosGrafico.size)).toBeLessThanOrEqual(1);
  });
}

test("resumen enlaza gastos conservando mes, área, concepto y aprobación", async ({ page }, testInfo) => {
  const { peticiones } = await escenario(page);
  await page.goto("/finanzas?mes=2026-09&area=3");
  await expect(page.getByRole("region", { name: "Resumen de gastos", exact: true })).toBeVisible();
  await expect(page.getByText("Del gasto a su distribución", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Gastos registrados visibles según tus permisos", { exact: false })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("resumen.png"), fullPage: true });
  await page.getByRole("button", { name: "Listado", exact: true }).click();
  await page.getByRole("row").filter({ hasText: "Electricidad" }).getByRole("button", { name: "ARS 500,00" }).click();
  await expect(page).toHaveURL(/mes=2026-09/); await expect(page).toHaveURL(/area=3/);
  await expect(page).toHaveURL(/gastos_f_concepto=1/); await expect(page).toHaveURL(/gastos_f_estado_operativo=pendiente_aprobacion/);
  await expect.poll(() => peticiones.some((u) => u.pathname === "/api/gastos/" && u.searchParams.get("estado_operativo") === "pendiente_aprobacion")).toBe(true);
});

test("barras por defecto con importe exacto y clic que conserva filtros", async ({ page }, testInfo) => {
  await escenario(page);
  await page.goto("/finanzas?mes=2026-09&area=3");
  await expect(page.getByRole("button", { name: "Barras", exact: true })).toHaveAttribute("aria-pressed", "true");
  const barras = barrasDeGastos(page);
  await expect(barras).toHaveCount(2);
  await barras.first().hover();
  await expect(page.getByText("Aprobado: ARS 10.000,01", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("barras.png"), fullPage: true });
  await barras.nth(1).click();
  await expect(page).toHaveURL(/gastos_f_estado_operativo=pendiente_aprobacion/);
  await expect(page).toHaveURL(/gastos_f_concepto=1/);
  await expect(page).toHaveURL(/area=3/);
  await expect(page).toHaveURL(/mes=2026-09/);
});

test("dos niveles comparan distribución y abren su reparto, sin doble suma", async ({ page }, testInfo) => {
  await escenario(page);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/finanzas?mes=2026-09&area=3");
  await page.getByRole("button", { name: "Dos niveles", exact: true }).click();
  await page.getByRole("combobox", { name: "Comparar", exact: true }).selectOption("distribucion");
  await expect(page.locator(".recharts-pie")).toHaveCount(2);
  await page.screenshot({ path: testInfo.outputPath("dona.png"), fullPage: true });
  const porcion = page.locator(".recharts-pie").nth(1).locator(".recharts-pie-sector").first();
  // Con movimiento reducido, esperar un dibujo medible sin imponerle el
  // diámetro viejo: ahora se adapta al alto que queda en la pantalla.
  await expect.poll(async () => (await porcion.boundingBox())?.width || 0).toBeGreaterThan(0);
  await expect.poll(async () => (await porcion.boundingBox())?.height || 0).toBeGreaterThan(0);
  const caja = await porcion.boundingBox();
  // Pulsar el estado exterior, no el centro que ahora abre el concepto completo.
  await porcion.click({ position: { x: caja.width * 0.9, y: caja.height / 2 } });
  await expect(page).toHaveURL(/tab=repartos/);
  await expect(page).toHaveURL(/repartos_f_estado=distribuido/);
  await expect(page).toHaveURL(/repartos_f_gasto__concepto=1/);
});

test("negativos y montos grandes conservan decimales; la dona no inventa porcentajes", async ({ page }) => {
  const { db } = await escenario(page);
  db.reporte.aprobados = "-900719925474099.91";
  db.reporte.agrupaciones[0].aprobados = db.reporte.aprobados;
  await page.goto("/finanzas?mes=2026-09");
  await expect(barrasDeGastos(page)).toHaveCount(2);
  await barrasDeGastos(page).first().hover();
  await expect(page.getByText("Aprobado: ARS -900.719.925.474.099,91", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Dos niveles", exact: true }).click();
  await expect(page.getByText("Hay importes negativos:", { exact: false })).toBeVisible();
  await expect(page.locator(".recharts-pie-sector")).toHaveCount(0);
  await page.getByRole("button", { name: "Listado", exact: true }).click();
  await expect(page.getByRole("table").getByText("ARS -900.719.925.474.099,91", { exact: true })).toBeVisible();
});

test("distribución pendiente no se grafica como cero y listado sigue disponible", async ({ page }) => {
  await escenario(page, { pendientes: true });
  await page.goto("/finanzas?mes=2026-09");
  await page.getByRole("combobox", { name: "Comparar", exact: true }).selectOption("distribucion");
  await expect(page.getByText("todavía no hay una distribución completa", { exact: false })).toBeVisible();
  await expect(barrasDeGastos(page)).toHaveCount(0);
  await page.getByRole("button", { name: "Listado", exact: true }).click();
  await expect(page.getByRole("table").getByText("Actualización pendiente", { exact: true })).toHaveCount(2);
});

test("fallo al cargar gráfico conserva acceso al listado", async ({ page }) => {
  await escenario(page);
  await page.route("**/GraficoFinanzas.jsx*", (route) => route.abort());
  await page.goto("/finanzas?mes=2026-09");
  await expect(page.getByText("No se pudo mostrar el gráfico.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Listado", exact: true }).click();
  await expect(page.getByRole("table").getByText("Electricidad", { exact: true })).toBeVisible();
});

for (const movimiento of ["no-preference", "reduce"]) {
  test(`atribuciones abren caso autorizado, conservan filtros y cierran sin foco oculto (${movimiento})`, async ({ page }, testInfo) => {
    const { peticiones } = await escenario(page, { clinico: true });
    await page.emulateMedia({ reducedMotion: movimiento });
    await page.route("**/api/repartos-gasto/**", async (route) => {
      const detalle = new URL(route.request().url()).pathname.includes("atribuciones");
      const filas = detalle ? [
        { id: 1, referencia_atencion: 501, caso_navegable: 21, caso_descripcion: "Consulta kinesiológica", area_nombre: area.nombre, importe_centavos: 5001, ocurrida_en: "2026-09-14T12:00:00Z" },
        { id: 2, referencia_atencion: 502, caso_navegable: null, area_nombre: area.nombre, importe_centavos: 5000, ocurrida_en: "2026-09-14T12:00:00Z" },
      ] : [{ id: 11, gasto: 1, concepto_nombre: "Electricidad", area_nombre: area.nombre, periodo_economico: "2026-09-01", estado: "distribuido", motivo: "", saldo_centavos: 10001, saldo_no_atribuido_centavos: 0, atribuciones: 2, vigente: true, version: 1, actualizando: false }];
      await route.fulfill({ json: { ...lista(filas), saldo_centavos: 10001, importe_atribuido_centavos: 10001, saldo_no_atribuido_centavos: 0 } });
    });
    // Se prueba navegación, no se fabrica una historia clínica para el caso.
    await page.route("**/api/casos/21/**", (route) => route.fulfill({ status: 403, json: { detail: "Caso fuera del escenario de interfaz" } }));
    await page.goto("/finanzas?mes=2026-09&area=3&tab=repartos&repartos_f_gasto__concepto=1");
    const urlFinanzas = page.url();
    const abrir = page.getByRole("button", { name: "Ver 2 atenciones", exact: false });
    await expect(abrir).toBeVisible();
    expect(peticiones.some((u) => u.pathname.includes("atribuciones"))).toBe(false);
    await abrir.click();
    const enlace = page.getByRole("link", { name: "Consulta kinesiológica" });
    await expect(enlace).toBeVisible();
    const desplegable = page.locator('div[aria-hidden="false"]').filter({ has: enlace });
    await expect(desplegable).toHaveCSS("opacity", "1");
    if (movimiento === "reduce") await expect(desplegable).toHaveCSS("transition-property", "none");
    else await expect(desplegable).toHaveCSS("transition-duration", "0.2s");
    await expect(page.getByText("Sin enlace", { exact: false })).toBeVisible();
    await expect(page.getByRole("link", { name: "Consulta kinesiológica" })).toHaveCount(1);
    await page.setViewportSize({ width: 390, height: 844 });
    await expect.poll(() => page.locator(".finance-table-content").evaluateAll((listas) => listas.every((e) => getComputedStyle(e).overflowX === "auto" && (e.parentElement.closest(".finance-table-content") || e.getBoundingClientRect().right <= innerWidth + 1)))).toBe(true);
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page.screenshot({ path: testInfo.outputPath("atribuciones.png"), fullPage: true });
    await enlace.click();
    await expect(page).toHaveURL(/\/casos\/21$/);
    await expect(page.getByRole("alert").getByText("No tenés permiso para ver esto", { exact: true })).toBeVisible();
    await page.goBack();
    await expect(page).toHaveURL(urlFinanzas);
    await page.getByRole("button", { name: "Ver 2 atenciones", exact: false }).click();
    const cerrar = page.getByRole("button", { name: "Ocultar 2 atenciones", exact: false });
    await expect(enlace).toBeVisible();
    await cerrar.click();
    await expect(page.getByRole("link", { name: "Consulta kinesiológica" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Ver 2 atenciones", exact: false })).toBeFocused();
    await expect(page.locator('a[href="/casos/21"]')).toHaveCount(0);
  });
}

test("gráficos con muchas áreas, tema oscuro y móvil mantienen todos los importes", async ({ page }, testInfo) => {
  const { db } = await escenario(page);
  db.reporte.agrupaciones = Array.from({ length: 24 }, (_, i) => ({ ...reporte.agrupaciones[0], area: i + 1, area_nombre: `Área ${i + 1}`, concepto_nombre: `Concepto de prueba ${i + 1}` }));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/finanzas?mes=2026-09");
  const grafico = page.getByRole("region", { name: "Gráfico de barras por área y concepto" });
  await expect(barrasDeGastos(page)).toHaveCount(48);
  await expect.poll(() => grafico.evaluate((e) => e.clientHeight > 480 && e.scrollHeight <= e.clientHeight)).toBe(true);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await grafico.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("barras-movil.png") });
  await page.getByRole("button", { name: "Dos niveles", exact: true }).click();
  await expect(page.getByRole("list", { name: "Importes del gráfico de dos niveles" }).getByRole("listitem")).toHaveCount(24);
  await expect.poll(() => page.getByRole("list", { name: "Importes del gráfico de dos niveles" }).evaluate((e) => e.scrollHeight <= e.clientHeight && e.scrollWidth <= e.clientWidth)).toBe(true);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.setViewportSize({ width: 1440, height: 1200 });
  await page.getByRole("button", { name: "Cambiar a tema oscuro", exact: true }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.getByRole("region", { name: "Gráfico de dos niveles por área, concepto y estado" }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("dona-oscuro.png") });
});

test("el resumen reúne gastos, dinero y costos con sus tres gráficos y sin sumarlos", async ({ page }, testInfo) => {
  const { db, peticiones, escrituras } = await escenario(page, { permisos: [...acciones, "ver_dinero"] });
  db.costos.ajustes_pendientes = 2;
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/finanzas?mes=2026-09");
  const gastos = page.getByRole("region", { name: "Resumen de gastos", exact: true });
  const dinero = page.getByRole("region", { name: "Resumen de pagos y cobros", exact: true });
  const costos = page.getByRole("region", { name: "Resumen de costos por atención", exact: true });
  await expect(gastos.getByRole("region", { name: "Gráfico de barras por área y concepto" })).toBeVisible();
  await expect(dinero.getByRole("region", { name: "Gráfico de cobros y pagos netos por área" })).toBeVisible();
  await expect(costos.getByRole("region", { name: "Gráfico de costo conocido por área" })).toBeVisible();
  await expect(dinero.getByText("ARS 190,00", { exact: true })).toBeVisible();
  await expect(dinero.getByText("ARS 155,00", { exact: true })).toBeVisible();
  await expect(dinero.getByText("Fecha efectiva · 2026-09-01 al 2026-09-30", { exact: true })).toBeVisible();
  await expect(costos.getByText("ARS 10.000,00", { exact: true })).toBeVisible();
  await expect(costos.getByText("ARS 3.333,34", { exact: true })).toBeVisible();
  await expect(costos.getByText("2 ajustes de costo por aprobar", { exact: false })).toBeVisible();
  // Cada bloque conserva su magnitud: el resumen nunca publica un total común.
  await expect(page.getByText("ARS 23.333,34", { exact: false })).toHaveCount(0);
  await expect.poll(() => peticiones.filter((u) => u.pathname === "/api/reportes-costos/" && u.searchParams.get("periodo_economico") === "2026-09-01").length).toBeGreaterThan(0);
  await expect.poll(() => peticiones.some((u) => u.pathname === "/api/reportes-dinero/" && u.searchParams.get("fecha_desde") === "2026-09-01" && u.searchParams.get("fecha_hasta") === "2026-09-30")).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("resumen-panorama.png"), animations: "disabled", fullPage: true });
  await costos.getByRole("combobox", { name: "Agrupar costos" }).selectOption("prestacion");
  await expect(costos.getByRole("region", { name: "Gráfico de costo conocido por prestación" })).toBeVisible();
  await expect(costos.getByText("Sin prestación configurada", { exact: false })).toBeVisible();
  expect(escrituras).toHaveLength(0);
});

test("el resumen lleva cada bloque a su pestaña con el área elegida", async ({ page }) => {
  await escenario(page, { permisos: [...acciones, "ver_dinero"] });
  await page.goto("/finanzas?mes=2026-09");
  const costos = page.getByRole("region", { name: "Resumen de costos por atención", exact: true });
  await costos.getByRole("button", { name: "Ver atenciones costeadas" }).click();
  await expect(page.getByRole("tab", { name: "Costos por atención" })).toHaveAttribute("aria-selected", "true");
  expect(new URL(page.url()).searchParams.get("area")).toBe(null);
  await page.goto("/finanzas?mes=2026-09");
  await page.getByRole("region", { name: "Resumen de pagos y cobros", exact: true }).getByRole("button", { name: "Ver cobros netos" }).click();
  await expect(page.getByRole("tab", { name: "Pagos y cobros" })).toHaveAttribute("aria-selected", "true");
});

test("el resumen informa restricciones y fallos por bloque sin ocultar los demás", async ({ page }) => {
  const { db } = await escenario(page, { permisos: [...acciones, "ver_dinero"] });
  await page.route("**/api/reportes-costos/**", (route) => route.fulfill({ status: 503, json: { detail: "Servicio no disponible" } }));
  await page.goto("/finanzas?mes=2026-09");
  await expect(page.getByText("No se pudo consultar los costos por atención", { exact: false })).toBeVisible();
  await expect(page.getByRole("region", { name: "Resumen de pagos y cobros", exact: true }).getByText("ARS 190,00", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Gráfico de barras por área y concepto" })).toBeVisible();
  // El bloque que falló no publica cifras propias ni una versión degradada.
  await expect(page.getByRole("region", { name: "Resumen de costos por atención", exact: true })).toHaveCount(0);
  await expect(page.getByText("ARS 10.000,00", { exact: true })).toHaveCount(0);
  expect(db.costos.atenciones).toBe(2);
});

test("el resumen no consulta dinero sin permiso y lo declara en lugar de mostrar cero", async ({ page }) => {
  const { peticiones } = await escenario(page);
  await page.goto("/finanzas?mes=2026-09");
  await expect(page.getByText("Los pagos y cobros no están incluidos en tu acceso. No se representan como cero.", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Resumen de costos por atención", exact: true })).toBeVisible();
  expect(peticiones.some((u) => u.pathname === "/api/reportes-dinero/")).toBe(false);
});

test("procesamiento detenido no convierte distribución desconocida en cero y se recupera", async ({ page }) => {
  const { db } = await escenario(page, { pendientes: true });
  await page.goto("/finanzas?mes=2026-09");
  await expect(page.getByText("El proceso está detenido", { exact: false })).toBeVisible();
  await expect(page.getByText("Actualización pendiente", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("ARS 0,00", { exact: true })).toHaveCount(0);
  db.pendientes = false;
  await expect(page.getByText("Repartos actualizados", { exact: true })).toBeVisible();
  await expect(page.getByText("ARS 0,00", { exact: true }).first()).toBeVisible();
});

test("control mensual agrupa acciones en modal y referencia no declara carga completa", async ({ page }) => {
  const { escrituras } = await escenario(page);
  await page.goto("/finanzas?mes=2026-09&tab=calendario");
  await expect(page.getByRole("tab", { name: "Gastos mensuales" })).toBeVisible();
  await expect(page.getByText("ARS +1.999,99", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Historial de configuración", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Administrar Electricidad" }).click();
  await expect(page.getByRole("button", { name: "Historial de configuración", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Modificar configuración y vigencia" }).click();
  await page.getByLabel("Aplicar el cambio desde").fill("2026-10");
  await page.getByLabel("Monto de referencia mensual en ARS (opcional)").fill("15000.01");
  await page.getByLabel("Motivo", { exact: true }).fill("Nueva referencia mensual");
  await page.getByRole("button", { name: "Confirmar", exact: true }).click();
  await expect.poll(() => escrituras.length).toBe(1);
  expect(escrituras[0].body.monto_referencia).toBe("15000.01");
  expect(escrituras[0].body).not.toHaveProperty("estado_carga");
});

test("contable recibe múltiples acciones y sensible en una sola operación", async ({ page }, testInfo) => {
  const { escrituras } = await escenario(page);
  await abrirEditorPermisos(page);
  await page.getByLabel("Ver gastos", { exact: true }).check();
  await page.getByLabel("Aprobar gastos", { exact: true }).check();
  for (const accion of ["Ver gastos", "Aprobar gastos"]) {
    await page.getByLabel(`Consultorios Escuela · ${accion}`, { exact: true }).check();
    await page.getByLabel(`Incluir información sensible · ${accion}`, { exact: true }).check();
  }
  await page.screenshot({ path: testInfo.outputPath("permisos.png"), fullPage: true });
  await page.getByRole("button", { name: "Guardar permisos financieros", exact: true }).click();
  await expect.poll(() => escrituras.length).toBe(1);
  expect(escrituras[0]).toEqual({ path: "/concesiones-financieras/editar-membresia/", body: { membresia: 8, version_esperada: "a".repeat(64), concesiones: ["ver_gastos", "aprobar_gastos"].map((accion) => ({ accion, areas: [3], todas_las_areas: false, permite_sensibles: true })) } });
});

test("checklist reúne las acciones existentes y conserva sus alcances separados", async ({ page }) => {
  await escenario(page, { concesiones: acciones.map((accion, n) => ({ id: n + 1, membresia: 8, accion, areas: [3], todas_las_areas: false, permite_sensibles: true })) });
  await abrirEditorPermisos(page);
  await expect(page.getByRole("checkbox", { name: "Ver gastos", exact: true })).toBeChecked();
  await expect(page.getByRole("checkbox", { name: "Aprobar gastos", exact: true })).toBeChecked();
  await page.getByText("Alcance de Ver gastos", { exact: true }).click();
  await expect(page.getByLabel("Consultorios Escuela · Ver gastos", { exact: true })).toBeChecked();
  await expect(page.getByLabel("Incluir información sensible · Ver gastos", { exact: true })).toBeChecked();
  await expect(page.getByRole("button", { name: "Revocar", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Guardar permisos financieros", exact: true })).toBeVisible();
});

test("solo ver costos permite entrar sin consultar gastos ni configuración", async ({ page }) => {
  const { peticiones, db } = await escenario(page, { permisos: ["ver_costos"], pendientes: true });
  await page.goto("/finanzas?mes=2026-09");
  await expect(page.getByRole("tab", { name: "Costos por atención" })).toBeVisible();
  await expect(page.getByText("Actualizando reparto", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Ver composición" }).click();
  await expect(page.getByRole("heading", { name: "Componentes directos" })).toBeVisible();
  await expect(page.getByText("ARS 3.333,34", { exact: true })).toHaveCount(0);
  db.pendientes = false;
  await expect(page.getByRole("region", { name: "Importes conocidos de la atención" }).getByText("ARS 3.333,34", { exact: true })).toBeVisible();
  expect(peticiones.some((u) => /\/(gastos|reportes-finanzas|procesamiento-finanzas|prestaciones-costo)\//.test(u.pathname))).toBe(false);
});

test("el detalle se retira cuando el servidor deja de devolver una atención", async ({ page }) => {
  const { db } = await escenario(page, { permisos: ["ver_costos"] });
  await page.goto("/finanzas?mes=2026-09");
  await page.getByRole("button", { name: "Ver composición" }).click();
  await expect(page.getByRole("dialog", { name: "Costo de atención · Caso #21" })).toBeVisible();
  db.ocultarHechos = true;
  await expect(page.getByText("Sin atenciones financieras visibles para estos filtros", { exact: true })).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Costo de atención · Caso #21" })).toHaveCount(0);
});

test("configuración completa prestación componente y valor desde pantallas", async ({ page }) => {
  const { escrituras } = await escenario(page);
  await page.goto("/finanzas?mes=2026-09&tab=costos");
  await page.getByRole("button", { name: "Configurar costos por atención", exact: true }).click();
  await page.getByRole("button", { name: "Configurar otra atención" }).click();
  await page.getByLabel("Atención del flujo publicado").selectOption("44");
  await page.getByRole("button", { name: "Guardar este paso" }).click();
  await page.getByRole("button", { name: "Agregar componente", exact: true }).click();
  await page.getByLabel("Nombre", { exact: true }).fill("Materiales");
  await page.getByRole("button", { name: "Guardar este paso" }).click();
  await expect(page.getByText("Falta el valor de este componente", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Agregar intervalo de valor" }).click();
  await page.getByLabel("Importe por atención en ARS").fill("1500.01");
  await page.getByLabel("Vigente desde", { exact: false }).fill("2026-09-14T10:00");
  await page.getByRole("button", { name: "Guardar este paso" }).click();
  await expect(page.getByText("ARS 1.500,01", { exact: true })).toBeVisible();
  expect(escrituras.map((e) => e.path)).toEqual(["/prestaciones-costo/", "/componentes-costo/", "/valores-componentes/"]);
  expect(escrituras[2].body.vigente_desde).toBe("2026-09-14T13:00:00.000Z");
});

test("resumen y control mensual no desbordan el ancho móvil", async ({ page }) => {
  await escenario(page); await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/finanzas?mes=2026-09");
  for (const tab of ["Resumen", "Gastos mensuales", "Costos por atención"]) {
    await page.getByRole("tab", { name: tab, exact: true }).click();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  }
});

for (const status of [403, 503]) {
  test(`detalle relacionado retira importes anteriores después de error ${status}`, async ({ page }) => {
    await escenario(page);
    let error = false;
    const gasto = { id: 1, concepto_nombre: "Electricidad", area_nombre: area.nombre,
      periodo_economico: "2026-09-01", estado_operativo: "reemplazado", estado: "rechazado",
      importe: "100.00", total_ajustes: "0.00", importe_resultante: "100.00",
      registrado: "2026-09-14T12:00:00Z", ajustes: [], reemplazado_por: 2 };
    await page.route("**/api/gastos/**", async (route) => {
      if (new URL(route.request().url()).pathname.endsWith("/2/")) {
        return route.fulfill({ status: error ? status : 200, json: error
          ? { detail: "No se puede consultar el gasto" }
          : { ...gasto, id: 2, importe: "9876.54", importe_resultante: "9876.54", reemplazado_por: null } });
      }
      return route.fulfill({ json: lista([gasto]) });
    });
    await page.route("**/api/procesamiento-finanzas/**", (route) => route.fulfill({ json: {
      estado: "actualizado", pendientes: 0, worker_activo: true, mensaje: "Sin pendientes",
      ultimo_exito: error ? "2026-09-14T12:00:01Z" : "2026-09-14T12:00:00Z",
    } }));
    await page.goto("/finanzas?mes=2026-09&tab=gastos");
    await page.getByRole("button", { name: "Reemplazado por #2", exact: true }).click();
    await expect(page.getByRole("dialog")).toContainText("9.876,54");
    error = true;
    await expect(page.getByRole("dialog")).toContainText(status === 403
      ? "No tenés permiso para ver esto" : "No se pudo consultar el gasto relacionado", { timeout: 15000 });
    await expect(page.getByRole("dialog")).not.toContainText("9.876,54");
  });
}

test("configurador sin lectura registra una regla sin consultar importes", async ({ page }) => {
  const { peticiones } = await escenario(page, { permisos: ["configurar_repartos"] });
  let guardado = false;
  await page.route("**/api/coberturas-actividad/verificacion/**", (route) => route.fulfill({ json: {
    integridad_tecnica: true, incluye_importes: false, atenciones_contrastables: 1,
    atenciones_registradas: 1, diferencias: 0, cobertura_operativa_confirmada: true,
    importe_total_centavos: null, importe_pendiente_centavos: null, importe_estimado_por_atencion_centavos: null,
  } }));
  await page.route("**/api/reglas-reparto/", (route) => {
    if (route.request().method() === "POST") {
      guardado = true;
      return route.fulfill({ status: 201, json: { id: 9, ...route.request().postDataJSON() } });
    }
    return route.fulfill({ json: lista([]) });
  });
  await page.goto("/finanzas?mes=2026-09");
  await page.getByRole("button", { name: "Configurar repartos", exact: true }).click();
  await page.getByRole("button", { name: "Agregar regla", exact: true }).click();
  const modal = page.getByRole("dialog");
  await modal.getByRole("combobox", { name: "Área", exact: true }).selectOption("3");
  const verificacion = page.waitForRequest((req) => req.url().includes("/verificacion/"));
  await modal.getByRole("combobox", { name: "Concepto de gasto", exact: true }).selectOption("1");
  expect(new URL((await verificacion).url()).searchParams.get("incluir_importes")).toBe("false");
  await expect(modal).toContainText("Podés configurar el reparto sin consultar importes");
  await expect(modal.getByText("Importe aprobado visible", { exact: true })).toHaveCount(0);
  await modal.getByRole("button", { name: "Registrar regla", exact: true }).click();
  await expect.poll(() => guardado).toBe(true);
  expect(peticiones.some((url) => /\/(gastos|reportes-finanzas|procesamiento-finanzas)\//.test(url.pathname))).toBe(false);
});


test("reporte ejecutivo mantiene columnas independientes y no genera scroll invisible", async ({ page }) => {
  await escenarioEjecutivo(page);
  await page.goto("/finanzas?tab=reportes&mes=2026-09");
  const gastos = page.getByRole("region", { name: "Informe de gastos", exact: true });
  const dinero = page.getByRole("region", { name: "Informe de dinero", exact: true });
  await expect(gastos.getByRole("heading", { name: "Detalle por área y concepto" })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  const posicion = () => dinero.getByRole("heading", { name: "Detalle de pagos y cobros" }).evaluate((e) => e.getBoundingClientRect().top + e.closest("main > div:last-child").scrollTop);
  const antes = await posicion();
  await gastos.getByText("Ver importes y fuentes de cada mes", { exact: true }).click();
  expect(Math.abs(await posicion() - antes)).toBeLessThan(2);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollHeight <= innerHeight)).toBe(true);
  const controles = page.locator(".finance-report-table-heading .finance-report-tools");
  const select = await controles.locator("select").boundingBox();
  const input = await controles.locator("input").boundingBox();
  expect(Math.abs(select.y - input.y)).toBeLessThan(2);
  const estado = await page.getByText("Repartos actualizados", { exact: true }).boundingBox();
  const contexto = await page.locator(".finance-page-context > div").first().boundingBox();
  expect(Math.abs(estado.y + estado.height / 2 - contexto.y - contexto.height / 2)).toBeLessThan(8);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollHeight <= innerHeight && document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("reporte ejecutivo ordena importes y filtra sin cambiar las cifras ni los gráficos", async ({ page }) => {
  await escenarioEjecutivo(page);
  await page.goto("/finanzas?tab=reportes&mes=2026-09");
  const tabla = page.getByRole("table", { name: "Comparación exacta de gastos" });
  const contenedor = tabla.locator("xpath=ancestor::div[contains(@class,'finance-table') and not(contains(@class,'finance-table-content'))][1]");
  await tabla.getByRole("button", { name: /^Ordenar por 2026-09/ }).click();
  await expect(tabla.locator("tbody tr").first()).toContainText("Limpieza");
  await tabla.getByRole("button", { name: /^Ordenar por 2026-09/ }).click();
  await expect(tabla.locator("tbody tr").first()).toContainText("Electricidad");
  await tabla.getByRole("button", { name: "Filtrar 2026-09", exact: true }).click();
  await page.getByRole("spinbutton", { name: "2026-09 desde", exact: true }).fill("480000.01");
  await page.keyboard.press("Escape");
  await expect(tabla.locator("tbody tr")).toHaveCount(1);
  await expect(tabla.locator("tbody tr")).toContainText("Electricidad");
  await expect(page.getByRole("button", { name: "Ver gastos aprobados de 2026-09", exact: true })).toHaveText("ARS 1.000.000,01");
  await contenedor.getByRole("button", { name: "Quitar filtro 2026-09 desde", exact: true }).click();
  await expect(tabla.locator("tbody tr")).toHaveCount(4);
  await tabla.getByRole("button", { name: "Filtrar Área / concepto", exact: true }).click();
  await page.getByRole("textbox", { name: "Área / concepto", exact: true }).fill("ausente");
  await page.keyboard.press("Escape");
  await contenedor.getByRole("button", { name: "Limpiar filtros", exact: true }).click();
  await expect(tabla.locator("tbody tr")).toHaveCount(4);
});


test("listado agregado conserva centavos grandes y no filtra desconocidos como cero", async ({ page }) => {
  const { db } = await escenario(page);
  db.reporte.agrupaciones = [
    ["Mayor", "900719925474099.92"], ["Menor", "900719925474099.91"], ["Desconocido", null], ["Cero", "0.00"],
  ].map(([nombre, importe], i) => ({ ...reporte.agrupaciones[0], concepto: i + 1, concepto_nombre: nombre, distribuido: importe }));
  await page.goto("/finanzas?mes=2026-09&resumen_grupos_tam=-5&resumen_grupos_pag=100");
  await page.getByRole("button", { name: "Listado", exact: true }).click();
  const tabla = page.getByRole("table", { name: "Gastos por área y concepto · ARS" });
  await tabla.getByRole("button", { name: "Ordenar por Distribuido", exact: true }).click();
  await expect(tabla.locator("tbody tr").first()).toContainText("Cero");
  await expect(tabla.locator("tbody tr").last()).toContainText("Desconocido");
  await tabla.getByRole("button", { name: "Ordenar por Distribuido (ascendente)", exact: true }).click();
  await expect(tabla.locator("tbody tr").first()).toContainText("Mayor");
  await expect(tabla.locator("tbody tr").nth(1)).toContainText("Menor");
  await expect(tabla.locator("tbody tr").last()).toContainText("Desconocido");
  await tabla.getByRole("button", { name: "Filtrar Distribuido", exact: true }).click();
  await page.getByRole("spinbutton", { name: "Distribuido hasta", exact: true }).fill("0");
  await page.keyboard.press("Escape");
  await expect(tabla.locator("tbody tr")).toHaveCount(1);
  await expect(tabla.locator("tbody tr")).toContainText("Cero");
});


test("desglose mantiene filas compactas y filtros visibles en escritorio y móvil", async ({ page }) => {
  await escenarioEjecutivo(page);
  await page.goto("/finanzas?tab=reportes&mes=2026-09");
  const tabla = page.getByRole("table", { name: "Desglose de dinero por área, concepto y financiador" });
  const fila = tabla.locator("tbody tr").first();
  await expect(tabla.locator("thead")).toBeVisible();
  await expect(fila).toHaveCSS("display", "table-row");
  const posiciones = await fila.locator("td").evaluateAll((celdas) => celdas.map((c) => c.getBoundingClientRect().top));
  expect(Math.max(...posiciones) - Math.min(...posiciones)).toBeLessThan(1);
  expect((await fila.boundingBox()).height).toBeLessThan(100);
  await expect(page.getByText("Fecha efectiva: 2026-09-01 al 2026-09-30", { exact: true })).toBeVisible();
  await expect(page.getByText("Seleccionado: 2026-09 · Comparado: 2026-08 · Gastos vigentes", { exact: true })).toBeVisible();
  await page.getByRole("textbox", { name: "Buscar en desglose", exact: true }).fill("ausente");
  const quitar = page.getByRole("button", { name: "Quitar filtro Buscar en desglose", exact: true });
  await expect(quitar).toContainText("ausente");
  await quitar.click();
  await expect(tabla.locator("tbody tr")).toHaveCount(1);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(fila).toHaveCSS("display", "table-row");
  const region = page.getByRole("region", { name: "Desglose de dinero por área, concepto y financiador: desplazamiento horizontal", exact: true });
  await region.scrollIntoViewIfNeeded();
  await region.focus();
  await page.keyboard.press("ArrowRight");
  await expect.poll(() => region.evaluate((e) => e.scrollLeft)).toBeGreaterThan(0);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight)).toBe(true);
});
