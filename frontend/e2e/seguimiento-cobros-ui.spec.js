import { expect, test } from "@playwright/test";

const lista = (results) => ({ count: results.length, next: null, previous: null, results });
const hospitales = [{ id: 2, nombre: "Hospital de prueba" }, { id: 3, nombre: "Hospital del Sur" }];
const importes = {
  importe_original: "10000.00", ajustes_aprobados: "-1000.00", obligacion_actual: "9000.00",
  registrado_neto: "3000.00", pendiente: "6000.00", saldo_a_devolver: "0.00",
  por_aprobar: "500.00", reintegros_por_aprobar: "200.00", ajustes_por_aprobar: "100.00",
};
const cuenta = {
  id: 91, reserva: 81, caso: 41, fecha: "2026-09-15", prestacion: "Consulta programada",
  financiador: 21, financiador_nombre: "Mutual del Río", responsable: "paciente",
  contraparte_nombre: "Paciente de prueba", area: 4, sensible: true, ...importes,
};
function respuesta(results = [cuenta], extra = {}) {
  return {
    ...lista(results), generado_en: "2026-09-16T12:00:00Z",
    limite_exportacion: 5000,
    opciones: { areas: [{ id: 4, nombre: "Consultorios" }], financiadores: [{ id: 21, nombre: "Mutual del Río" }] },
    resumen: { registros: 1, ...importes }, ...extra,
  };
}

async function escenario(page, { seguimiento = true, permisoDinero = true, editar = false } = {}) {
  const consultas = [];
  const escrituras = [];
  const estado = { actualizado: false };
  await page.addInitScript((institucion) => {
    sessionStorage.setItem("salud.access", "access-solo-pruebas-interceptadas");
    if (!localStorage.getItem("salud.institucion")) localStorage.setItem("salud.institucion", JSON.stringify(institucion));
  }, hospitales[0]);
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const path = url.pathname.replace(/^\/api/, "");
    consultas.push({ path, params: Object.fromEntries(url.searchParams) });
    if (request.method() === "POST") {
      escrituras.push({ path, body: request.postDataJSON() });
      if (path === "/obligaciones-financieras/91/movimientos/") {
        estado.actualizado = true;
        return route.fulfill({ json: { id: 200, estado: "aprobado" } });
      }
      return route.fulfill({ status: 404, json: { detail: `Escritura inesperada: ${path}` } });
    }
    if (path === "/usuarios/me/") return route.fulfill({ json: {
      id: 9, email: "finanzas@example.test", nombre_completo: "Personal de Finanzas",
      capacidades_por_institucion: { 2: ["casos_operar"], 3: ["casos_operar"] },
      roles_por_institucion: { 2: ["administrativo"], 3: ["administrativo"] }, financiadores: [],
    } });
    if (path === "/instituciones/") return route.fulfill({ json: lista(hospitales) });
    if (path === "/notificaciones/resumen/") return route.fulfill({ json: { no_leidas: 0, items: [] } });
    if (path === "/concesiones-financieras/mias/") return route.fulfill({ json: {
      superusuario: false,
      concesiones: permisoDinero ? hospitales.flatMap((hospital) => (editar ? ["ver_dinero", "registrar_dinero", "aprobar_dinero"] : ["ver_dinero"]).map((accion) => ({ institucion: hospital.id, accion, areas: [4], todas_las_areas: false, permite_sensibles: true }))) : [],
    } });
    if (path === "/coberturas/opciones/") return route.fulfill({ json: { permisos: { seguimiento, operar: false, configurar: false }, configuracion: { activo: true } } });
    if (path === "/coberturas/") return route.fulfill({ json: lista([]) });
    if (path === "/seguimiento-cobros/") {
      const filas = estado.actualizado ? [{ ...cuenta, registrado_neto: "4000.00", pendiente: "5000.00" }] : [cuenta];
      return route.fulfill({ json: respuesta(filas, estado.actualizado ? { resumen: { registros: 1, ...importes, registrado_neto: "4000.00", pendiente: "5000.00" } } : {}) });
    }
    if (path === "/obligaciones-financieras/91/") return route.fulfill({ json: {
      ...cuenta, tipo: "cobrar", periodo_economico: "2026-09-01", hecho: 50,
      disponible_registro: "6000.00", disponible_reducir: "8500.00", movimientos: [], ajustes: [],
      ...(estado.actualizado ? { registrado_neto: "4000.00", pendiente: "5000.00" } : {}),
    } });
    return route.fulfill({ json: lista([]) });
  });
  return { consultas, escrituras, estado };
}

const entrada = "/finanzas/coberturas?tab=seguimiento";

test("filtra por fecha de prestación y conserva filtros, página y navegación", async ({ page }) => {
  await escenario(page);
  const consultas = [];
  await page.route("**/api/seguimiento-cobros/**", (route) => {
    const params = Object.fromEntries(new URL(route.request().url()).searchParams);
    consultas.push(params);
    return route.fulfill({ json: respuesta([cuenta], { count: 30, next: params.page === "2" ? null : "?page=2" }) });
  });
  await page.goto(`${entrada}&desde=2026-09-01&hasta=2026-09-30&page=2`);
  await expect(page.getByText("30 registros · Página 2", { exact: true })).toBeVisible();
  await page.getByLabel("Desde", { exact: true }).fill("2026-08-01");
  await page.getByLabel("Hasta", { exact: true }).fill("2026-08-31");
  await page.getByRole("combobox", { name: "Área de origen", exact: true }).selectOption("4");
  await page.getByRole("combobox", { name: "Financiador de la cobertura", exact: true }).selectOption("21");
  await page.getByRole("combobox", { name: "Responsable del cobro", exact: true }).selectOption("paciente");
  await page.getByRole("combobox", { name: "Estado", exact: true }).selectOption("por_aprobar");
  await page.getByLabel("Buscar caso, responsable o prestación").fill("  Consulta  ");
  await page.getByRole("button", { name: "Aplicar filtros" }).click();
  await expect.poll(() => consultas.at(-1)).toEqual({ desde: "2026-08-01", hasta: "2026-08-31", area: "4", financiador: "21", responsable: "paciente", estado: "por_aprobar", search: "Consulta", vista: "cuentas", institucion: "2", page: "1", page_size: "10" });
  await expect(page.getByText(/aunque se hayan registrado en otra fecha/)).toBeVisible();
  await page.reload();
  await expect(page.getByRole("combobox", { name: "Responsable del cobro", exact: true })).toHaveValue("paciente");
  await expect(page.getByLabel("Desde", { exact: true })).toHaveValue("2026-08-01");
  await page.goBack();
  await expect(page.getByText("30 registros · Página 2", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Desde", { exact: true })).toHaveValue("2026-09-01");
});

test("los totales de todas las páginas distinguen dinero aprobado y por aprobar", async ({ page }, testInfo) => {
  await escenario(page);
  await page.route("**/api/seguimiento-cobros/**", (route) => {
    const segunda = new URL(route.request().url()).searchParams.get("page") === "2";
    return route.fulfill({ json: respuesta([{ ...cuenta, id: segunda ? 92 : 91, contraparte_nombre: segunda ? "Segundo paciente" : "Paciente de prueba" }], { count: 30, next: segunda ? null : "?page=2", resumen: { registros: 30, ...importes, pendiente: "55000.00" } }) });
  });
  await page.goto(entrada);
  const resumen = page.getByRole("region", { name: "Resumen del seguimiento" });
  await expect(resumen).toContainText("ARS 55.000,00");
  await expect(resumen).toContainText("ARS 500,00");
  await page.getByRole("button", { name: "Ayuda sobre el seguimiento de cobros", exact: true }).click();
  await expect(page.getByRole("tooltip")).toContainText("pueden coexistir con un saldo en cero");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Siguiente", exact: true }).click();
  await expect(page.getByText("Segundo paciente", { exact: true })).toBeVisible();
  await expect(resumen).toContainText("ARS 55.000,00");
  await page.screenshot({ path: testInfo.outputPath("seguimiento-cuentas.png"), fullPage: true, animations: "disabled" });
});

test("pendientes y captura no presentan deuda ni convierten importes desconocidos en cero", async ({ page }) => {
  const { escrituras } = await escenario(page);
  const consultas = [];
  await page.route("**/api/seguimiento-cobros/**", (route) => {
    const params = Object.fromEntries(new URL(route.request().url()).searchParams);
    consultas.push(params);
    if (params.vista === "captura") return route.fulfill({ json: respuesta([{ id: 50, caso: 41, fecha: "2026-09-15", sensible: true, estado: "captura_pendiente", motivo: "Atención sin cargos registrados" }], { resumen: { registros: 1 } }) });
    return route.fulfill({ json: respuesta([{ id: 81, reserva: 81, caso: 41, fecha: "2026-09-15", prestacion: "Consulta programada", financiador: 21, financiador_nombre: "Mutual del Río", estado: "arancel_pendiente", motivo: "Falta definir el arancel", importe_pendiente: null }], { resumen: { registros: 1, importes_desconocidos: 1, importe_pendiente: "0.00" } }) });
  });
  await page.goto(`${entrada}&vista=pendientes&financiador=21&estado=arancel_pendiente&desde=&hasta=`);
  await expect(page.getByRole("row").filter({ hasText: "Falta definir el arancel" })).toContainText("Por determinar");
  await expect(page.getByRole("row").filter({ hasText: "Falta definir el arancel" })).not.toContainText("ARS");
  await expect(page.getByRole("region", { name: "Resumen del seguimiento" })).toContainText("todavía no constituyen una deuda asignada");
  await page.getByRole("combobox", { name: "Vista", exact: true }).selectOption("captura");
  await expect(page.getByText("Atención sin cargos registrados", { exact: true })).toBeVisible();
  expect(consultas.at(-1)).toEqual({ vista: "captura", institucion: "2", page: "1", page_size: "10" });
  await expect(page.getByRole("combobox", { name: "Financiador de la cobertura", exact: true })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Resumen del seguimiento" })).not.toContainText("ARS");
  await page.getByRole("button", { name: "Ver reservas y saldos", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Reservas y saldos" })).toHaveAttribute("aria-selected", "true");
  expect(escrituras).toEqual([]);
});

test("limpiar conserva todos los períodos y el mes actual se aplica explícitamente", async ({ page }) => {
  const { consultas } = await escenario(page);
  await page.goto(entrada);
  await expect(page.getByRole("heading", { name: "Seguimiento de cobros", exact: true })).toBeVisible();
  const mes = await page.evaluate(() => {
    const hoy = new Date(); const prefijo = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}`;
    return { desde: `${prefijo}-01`, hasta: `${prefijo}-${new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0).getDate()}` };
  });
  await expect.poll(() => consultas.filter((c) => c.path === "/seguimiento-cobros/").at(-1)?.params).toMatchObject(mes);
  await page.getByRole("button", { name: "Limpiar filtros" }).click();
  await expect(page.getByLabel("Desde", { exact: true })).toHaveValue("");
  await page.reload();
  await expect(page.getByLabel("Desde", { exact: true })).toHaveValue("");
  await page.getByRole("button", { name: "Mes actual", exact: true }).click();
  await expect(page.getByLabel("Desde", { exact: true })).toHaveValue(mes.desde);
});

test("permiso denegado no consulta seguimiento ni muestra cuentas", async ({ page }) => {
  const { consultas } = await escenario(page, { seguimiento: false });
  await page.goto(entrada);
  await expect(page.getByRole("alert")).toContainText("Esta sección no está disponible");
  await expect(page.getByRole("tab", { name: "Seguimiento de cobros" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Exportar CSV" })).toHaveCount(0);
  expect(consultas.some((c) => c.path === "/seguimiento-cobros/")).toBe(false);
});

test("sin área asignada persiste sin enviar un identificador de área incompatible", async ({ page }) => {
  const { consultas } = await escenario(page);
  await page.goto(`${entrada}&area=4&desde=&hasta=`);
  await page.getByRole("combobox", { name: "Área de origen", exact: true }).selectOption("sin_area");
  await page.getByRole("button", { name: "Aplicar filtros" }).click();
  await expect.poll(() => consultas.filter((c) => c.path === "/seguimiento-cobros/").at(-1)?.params).toEqual({ area_sin_asignar: "true", vista: "cuentas", institucion: "2", page: "1" });
  await page.reload();
  await expect(page.getByRole("combobox", { name: "Área de origen", exact: true })).toHaveValue("sin_area");
  await page.getByRole("combobox", { name: "Área de origen", exact: true }).selectOption("4");
  await page.getByRole("button", { name: "Aplicar filtros" }).click();
  await expect.poll(() => consultas.filter((c) => c.path === "/seguimiento-cobros/").at(-1)?.params).toEqual({ area: "4", vista: "cuentas", institucion: "2", page: "1" });
});

test("concesión revocada evita una consulta aunque la opción estuviera disponible", async ({ page }) => {
  const { consultas } = await escenario(page, { permisoDinero: false });
  await page.goto(entrada);
  await expect(page.getByRole("alert")).toContainText("No tenés permiso para consultar el seguimiento");
  await expect(page.getByRole("button", { name: "Exportar CSV" })).toHaveCount(0);
  expect(consultas.some((c) => c.path === "/seguimiento-cobros/")).toBe(false);
});

test("un error reemplaza cuentas y totales sin aparentar un saldo cero", async ({ page }) => {
  await escenario(page);
  let falla = false;
  await page.route("**/api/seguimiento-cobros/**", (route) => route.fulfill(falla ? { status: 503, json: { detail: "No se pudo consultar el seguimiento" } } : { json: respuesta() }));
  await page.goto(entrada);
  await expect(page.getByText("Paciente de prueba", { exact: true })).toBeVisible();
  falla = true;
  await page.getByLabel("Desde", { exact: true }).fill("2026-01-01");
  await page.getByRole("button", { name: "Aplicar filtros" }).click();
  await expect(page.getByRole("alert")).toContainText("No se pudo consultar el seguimiento");
  await expect(page.getByRole("region", { name: "Resumen del seguimiento" })).toHaveCount(0);
  await expect(page.getByText("Paciente de prueba", { exact: true })).toHaveCount(0);
  falla = false;
  await page.getByRole("button", { name: "Reintentar", exact: true }).click();
  await expect(page.getByText("Paciente de prueba", { exact: true })).toBeVisible();
});

test("cambiar hospital descarta filtros ajenos y datos anteriores", async ({ page }) => {
  await escenario(page);
  const consultas = [];
  await page.route("**/api/seguimiento-cobros/**", async (route) => {
    const params = Object.fromEntries(new URL(route.request().url()).searchParams);
    consultas.push(params);
    if (params.institucion === "3") await new Promise((resolve) => setTimeout(resolve, 350));
    return route.fulfill({ json: respuesta([{ ...cuenta, contraparte_nombre: params.institucion === "3" ? "Paciente del Sur" : "Paciente de prueba" }]) });
  });
  await page.goto(`${entrada}&seguimiento_institucion=2&desde=2026-01-01&hasta=2026-01-31&financiador=21&page=2`);
  await expect(page.getByText("Paciente de prueba", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "I-Core Hospital de prueba Institución", exact: true }).click();
  await page.getByRole("button", { name: "Hospital del Sur Institución", exact: true }).click();
  // El Shell vuelve al inicio cuando cambia la institución; el enlace conservado
  // tampoco debe restaurar los filtros ni el caché del hospital anterior.
  await page.goto(`${entrada}&seguimiento_institucion=2&desde=2026-01-01&hasta=2026-01-31&financiador=21&page=2`);
  await expect(page.getByText("Paciente del Sur", { exact: true })).toBeVisible();
  await expect(page.getByText("Paciente de prueba", { exact: true })).toHaveCount(0);
  expect(consultas.at(-1)).toMatchObject({ institucion: "3", page: "1" });
  expect(consultas.at(-1)).not.toHaveProperty("financiador");
  await expect(page).toHaveURL(/seguimiento_institucion=3/);
});

test("Ver cuenta reutiliza el registro de dinero y actualiza el seguimiento al guardar", async ({ page }) => {
  const { consultas, escrituras } = await escenario(page, { editar: true });
  await page.goto(entrada);
  await page.getByRole("button", { name: "Ver cuenta", exact: true }).click();
  const modal = page.getByRole("dialog", { name: "Cuenta #91" });
  await expect(modal).toBeVisible();
  await modal.getByRole("button", { name: "Registrar cobro", exact: true }).click();
  await modal.getByLabel("Importe en ARS", { exact: true }).fill("1000");
  await modal.getByLabel("Referencia del pago o cobro", { exact: true }).fill("Comprobante de prueba");
  const consultasAntes = consultas.filter((c) => c.path === "/seguimiento-cobros/").length;
  await modal.getByRole("button", { name: "Registrar cobro", exact: true }).click();
  await expect.poll(() => consultas.filter((c) => c.path === "/seguimiento-cobros/").length).toBeGreaterThan(consultasAntes);
  await expect(page.getByRole("region", { name: "Resumen del seguimiento" })).toContainText("ARS 5.000,00");
  expect(escrituras).toHaveLength(1);
  expect(escrituras[0]).toMatchObject({ path: "/obligaciones-financieras/91/movimientos/", body: { importe: "1000", aprobado: true, referencia: "Comprobante de prueba" } });
  expect(escrituras[0].body.clave).toMatch(/^[a-f0-9-]{36}$/);
});

test("lectura financiera en móvil conserva I-Core Salud y no habilita registrar dinero", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await escenario(page);
  await page.goto(entrada);
  await page.getByRole("button", { name: "Ver cuenta", exact: true }).click();
  const modal = page.getByRole("dialog", { name: "Cuenta #91" });
  await expect(modal.getByText("Paciente de prueba", { exact: true })).toBeVisible();
  await expect(modal.getByRole("button", { name: "Registrar cobro" })).toHaveCount(0);
  await expect(modal.getByRole("button", { name: "Reducir o cancelar cuenta" })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("seguimiento-cuenta-movil.png"), fullPage: true, animations: "disabled" });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("saldar la última cuenta de la segunda página permite volver a la primera conservando filtros", async ({ page }) => {
  const { estado, escrituras } = await escenario(page, { editar: true });
  const consultas = [];
  await page.route("**/api/seguimiento-cobros/**", (route) => {
    const params = Object.fromEntries(new URL(route.request().url()).searchParams);
    consultas.push(params);
    const segunda = params.page === "2";
    if (segunda && estado.actualizado) return route.fulfill({ status: 404, json: { detail: "Página inválida." } });
    const total = estado.actualizado ? 25 : 26;
    const filas = segunda ? [cuenta] : Array.from({ length: 25 }, (_, i) => ({ ...cuenta, id: 100 + i, contraparte_nombre: `Cuenta restante ${i + 1}` }));
    return route.fulfill({ json: respuesta(filas, { count: total, next: segunda || estado.actualizado ? null : "?page=2", previous: segunda ? "?page=1" : null, resumen: { registros: total, ...importes, pendiente: estado.actualizado ? "150000.00" : "156000.00" } }) });
  });
  await page.route("**/api/obligaciones-financieras/91/", (route) => route.fulfill({ json: {
    ...cuenta, tipo: "cobrar", periodo_economico: "2026-09-01", hecho: 50,
    disponible_registro: estado.actualizado ? "0.00" : "6000.00", disponible_reducir: "9000.00", movimientos: [], ajustes: [],
    por_aprobar: "0.00", reintegros_por_aprobar: "0.00", ajustes_por_aprobar: "0.00",
    registrado_neto: estado.actualizado ? "9000.00" : "3000.00", pendiente: estado.actualizado ? "0.00" : "6000.00",
  } }));
  await page.goto(`${entrada}&vista=cuentas&desde=2026-09-01&hasta=2026-09-30&financiador=21&responsable=paciente&area=4&estado=pendiente&search=Consulta&page=2`);
  await expect(page.getByText("26 registros · Página 2", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Ver cuenta", exact: true }).click();
  const modal = page.getByRole("dialog", { name: "Cuenta #91" });
  await modal.getByRole("button", { name: "Registrar cobro", exact: true }).click();
  await modal.getByLabel("Importe en ARS", { exact: true }).fill("6000");
  await modal.getByRole("button", { name: "Registrar cobro", exact: true }).click();
  await expect(modal.getByRole("button", { name: "Registrar cobro", exact: true })).toHaveCount(0);
  await modal.getByRole("button", { name: "Cerrar", exact: true }).click();
  await expect(page.getByText(/Esta página ya no está disponible/)).toBeVisible();
  await expect(page.getByRole("region", { name: "Resumen del seguimiento" })).toHaveCount(0);
  await page.getByRole("button", { name: "Volver a la primera página", exact: true }).click();
  await expect(page.getByText("25 registros · Página 1", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Resumen del seguimiento" })).toContainText("ARS 150.000,00");
  expect(consultas.at(-1)).toEqual({ vista: "cuentas", desde: "2026-09-01", hasta: "2026-09-30", area: "4", financiador: "21", responsable: "paciente", estado: "pendiente", search: "Consulta", institucion: "2", page: "1", page_size: "10" });
  expect(escrituras).toHaveLength(1);
  expect(escrituras[0]).toMatchObject({ body: { importe: "6000", aprobado: true } });
  await expect(page.getByText("Paciente de prueba", { exact: true })).toHaveCount(0);
});

test("un 404 ajeno a la paginación conserva el error sin ofrecer recuperación engañosa", async ({ page }) => {
  await escenario(page);
  await page.route("**/api/seguimiento-cobros/**", (route) => route.fulfill({ status: 404, json: { detail: "La institución no está disponible." } }));
  await page.goto(`${entrada}&page=2`);
  await expect(page.getByRole("alert")).toContainText("La institución no está disponible.");
  await expect(page.getByRole("button", { name: "Volver a la primera página" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Resumen del seguimiento" })).toHaveCount(0);
});

for (const vista of ["cuentas", "pendientes", "captura"]) {
  test(`exporta ${vista} con permiso de lectura y los filtros aplicados, sin paginación`, async ({ page }) => {
    const { escrituras } = await escenario(page);
    const descargas = [];
    await page.route("**/api/seguimiento-cobros/**", (route) => {
      const params = Object.fromEntries(new URL(route.request().url()).searchParams);
      if (params.formato === "csv") {
        descargas.push(params);
        return route.fulfill({ contentType: "text/csv; charset=utf-8", headers: { "Content-Disposition": `attachment; filename="seguimiento-${vista}-hospital-2.csv"` }, body: "\uFEFFFecha;Caso\r\n15/09/2026;41\r\n" });
      }
      const fila = vista === "captura" ? { id: 50, caso: 41, fecha: "2026-09-15", estado: "captura_pendiente", motivo: "Atención sin cargos registrados" }
        : vista === "pendientes" ? { ...cuenta, estado: "arancel_pendiente", motivo: "Falta definir el arancel", importe_pendiente: null } : cuenta;
      return route.fulfill({ json: respuesta([fila], { count: 26, resumen: vista === "captura" ? { registros: 26 } : vista === "pendientes" ? { registros: 26, importes_desconocidos: 26, importe_pendiente: "0.00" } : { registros: 26, ...importes } }) });
    });
    const filtros = { vista, desde: "2026-09-01", hasta: "2026-09-30", area: "4", search: vista === "captura" ? "41" : "Consulta", ...(vista !== "captura" ? { financiador: "21", estado: vista === "cuentas" ? "pendiente" : "arancel_pendiente" } : {}), ...(vista === "cuentas" ? { responsable: "paciente" } : {}) };
    await page.goto(`${entrada}&${new URLSearchParams(filtros)}&page=2&page_size=1`);
    const exportacion = page.getByRole("region", { name: "Exportación del seguimiento" });
    await expect(exportacion).toContainText("todas las páginas con los filtros aplicados");
    await expect(exportacion).toContainText("5.000 registros");
    const archivo = page.waitForEvent("download");
    await exportacion.getByRole("button", { name: "Exportar CSV", exact: true }).click();
    expect((await archivo).suggestedFilename()).toBe(`seguimiento-${vista}-hospital-2.csv`);
    expect(descargas).toEqual([{ ...filtros, institucion: "2", formato: "csv" }]);
    expect(escrituras).toEqual([]);
  });
}

test("exportar exige aplicar cambios, respeta el límite y no habilita descargas vacías", async ({ page }) => {
  await escenario(page);
  const descargas = [];
  await page.route("**/api/seguimiento-cobros/**", (route) => {
    const params = new URL(route.request().url()).searchParams;
    if (params.has("formato")) descargas.push(params.toString());
    const search = params.get("search");
    return route.fulfill({ json: respuesta(search === "vacio" ? [] : [cuenta], { count: search === "exceso" ? 5001 : search === "vacio" ? 0 : 5000 }) });
  });
  await page.goto(entrada);
  const boton = page.getByRole("button", { name: "Exportar CSV", exact: true });
  await expect(boton).toBeEnabled();
  await page.getByLabel("Buscar caso, responsable o prestación").fill("exceso");
  await expect(boton).toBeDisabled();
  await expect(page.getByText(/Aplicá los cambios para actualizar la consulta y la exportación/)).toBeVisible();
  await page.getByRole("button", { name: "Aplicar filtros" }).click();
  await expect(page.getByText(/El resultado supera el límite de exportación/)).toBeVisible();
  await expect(boton).toBeDisabled();
  await page.getByLabel("Buscar caso, responsable o prestación").fill("vacio");
  await page.getByRole("button", { name: "Aplicar filtros" }).click();
  await expect(page.getByText("Sin registros con estos filtros", { exact: true })).toBeVisible();
  await expect(boton).toBeDisabled();
  expect(descargas).toEqual([]);
});

for (const status of [400, 503]) {
  test(`un error ${status} de exportación conserva la consulta y no descarga archivo`, async ({ page }) => {
    await escenario(page);
    const archivos = [];
    page.on("download", (archivo) => archivos.push(archivo));
    await page.route("**/api/seguimiento-cobros/**", (route) => {
      const csv = new URL(route.request().url()).searchParams.has("formato");
      return route.fulfill(csv ? { status, json: status === 400 ? { detail: "El resultado supera el límite permitido para exportar." } : { detail: "No se pudo auditar la exportación. Intentá nuevamente." } } : { json: respuesta() });
    });
    await page.goto(entrada);
    await page.getByRole("button", { name: "Exportar CSV", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText(status === 400 ? "El resultado supera el límite permitido" : "No se pudo auditar la exportación");
    await expect(page.getByRole("region", { name: "Resumen del seguimiento" })).toContainText("ARS 6.000,00");
    await expect(page.getByText("Paciente de prueba", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Exportar CSV", exact: true })).toBeEnabled();
    expect(archivos).toEqual([]);
  });
}

test("una descarga en curso evita doble clic y mantiene fija la selección local", async ({ page }) => {
  await escenario(page);
  let liberar;
  const espera = new Promise((resolve) => { liberar = resolve; });
  const descargas = [];
  await page.route("**/api/seguimiento-cobros/**", async (route) => {
    const params = Object.fromEntries(new URL(route.request().url()).searchParams);
    if (params.formato === "csv") {
      descargas.push(params);
      await espera;
      return route.fulfill({ contentType: "text/csv", body: "Fecha;Caso\r\n15/09/2026;41" });
    }
    return route.fulfill({ json: respuesta([cuenta], { count: 26, next: "?page=2" }) });
  });
  await page.goto(entrada);
  const boton = page.getByRole("button", { name: "Exportar CSV", exact: true });
  await expect(boton).toBeEnabled();
  await boton.evaluate((elemento) => { elemento.click(); elemento.click(); });
  await expect.poll(() => descargas.length).toBe(1);
  await expect(page.getByRole("button", { name: "Exportando CSV…", exact: true })).toBeDisabled();
  await expect(page.getByRole("combobox", { name: "Vista", exact: true })).toBeDisabled();
  await expect(page.getByLabel("Desde", { exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Siguiente", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Ver cuenta", exact: true })).toBeDisabled();
  await expect(page.getByText(/Preparando archivo: Cuentas por cobrar · Hospital de prueba/)).toBeVisible();
  const archivo = page.waitForEvent("download");
  liberar();
  expect((await archivo).suggestedFilename()).toBe("seguimiento-cuentas-hospital-2.csv");
  await expect(page.getByRole("combobox", { name: "Vista", exact: true })).toBeEnabled();
  expect(descargas).toHaveLength(1);
});

test("cambiar de hospital no traslada un error de la descarga anterior", async ({ page }) => {
  await escenario(page);
  let liberar;
  const espera = new Promise((resolve) => { liberar = resolve; });
  const descargas = [];
  await page.route("**/api/seguimiento-cobros/**", async (route) => {
    const params = Object.fromEntries(new URL(route.request().url()).searchParams);
    if (params.formato === "csv") {
      descargas.push(params);
      await espera;
      return route.fulfill({ status: 503, json: { detail: "Error de exportación del hospital anterior" } });
    }
    return route.fulfill({ json: respuesta([{ ...cuenta, contraparte_nombre: params.institucion === "3" ? "Paciente del Sur" : "Paciente de prueba" }]) });
  });
  await page.goto(entrada);
  await page.getByRole("button", { name: "Exportar CSV", exact: true }).click();
  await expect.poll(() => descargas.length).toBe(1);
  await page.getByRole("button", { name: "I-Core Hospital de prueba Institución", exact: true }).click();
  await page.getByRole("button", { name: "Hospital del Sur Institución", exact: true }).click();
  await page.getByRole("link", { name: "Coberturas y copagos", exact: true }).click();
  await page.getByRole("tab", { name: "Seguimiento de cobros", exact: true }).click();
  await expect(page.getByText("Paciente del Sur", { exact: true })).toBeVisible();
  const respuestaAnterior = page.waitForResponse((response) => response.url().includes("formato=csv") && response.status() === 503);
  liberar();
  await respuestaAnterior;
  await expect(page.getByRole("button", { name: "Exportar CSV", exact: true })).toBeEnabled();
  await expect(page.getByText("Error de exportación del hospital anterior", { exact: true })).toHaveCount(0);
  expect(descargas[0].institucion).toBe("2");
});

test("sin respuesta válida del listado no ofrece exportar", async ({ page }) => {
  await escenario(page);
  let liberar;
  const espera = new Promise((resolve) => { liberar = resolve; });
  await page.route("**/api/seguimiento-cobros/**", async (route) => {
    await espera;
    return route.fulfill({ status: 503, json: { detail: "No se pudo consultar el seguimiento" } });
  });
  await page.goto(entrada);
  await expect(page.getByText("Consultando seguimiento de cobros…", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Exportar CSV" })).toHaveCount(0);
  liberar();
  await expect(page.getByRole("alert")).toContainText("No se pudo consultar el seguimiento");
  await expect(page.getByRole("button", { name: "Exportar CSV" })).toHaveCount(0);
});
