import { expect, test } from "@playwright/test";
test.beforeEach(async ({ page }) => { page.on("pageerror", (error) => console.error("Error de página:", error.message)); });

const inst = { id: 2, nombre: "Hospital Escuela" };
const lista = (results) => ({ count: results.length, results, next: null, previous: null });
const cuenta = {
  id: 11, tipo: "pagar", gasto: 51, hecho: null, institucion: 2, area: 3, sensible: false,
  moneda: "ARS", importe_original: "100.00", obligacion_actual: "100.00", registrado_neto: "40.00", pendiente: "60.00",
  disponible_reintegro: "40.00", saldo_a_devolver: "0.00", version_esperada: "version-a", discrepancia_gasto: null,
  disponible_registro: "60.00", disponible_reducir: "100.00", por_aprobar: "0.00", reintegros_por_aprobar: "0.00", ajustes_por_aprobar: "0.00",
  periodo_economico: "2026-09-01", contraparte_nombre: "Proveedor de materiales", contraparte_referencia: "PROV-1",
  movimientos: [{ id: 71, tipo: "pago", importe: "40.00", fecha: "2026-09-14", referencia: "COM-1", original: null, disponible_reintegro: "40.00", estado: "aprobado", aprobado: true }],
  ajustes: [{ id: 91, importe: "-10.00", motivo: "Cancelación acordada", disponible_reintegro: "10.00", estado: "aprobado", aprobado: true, movimiento_vinculado: null }],
};

async function escenario(page, { permisos = ["ver_dinero", "registrar_dinero", "corregir_dinero", "aprobar_dinero"], fallaMovimiento = false, fallaDetalle = false } = {}) {
  const lecturas = []; const escrituras = [];
  const estado = { intentos: 0, fallaDetalle, cuenta: structuredClone(cuenta), cuentaPorPagar: null, politicas: [], pendientes: [], preview: null, ajustesGasto: [] };
  await page.addInitScript((institucion) => { localStorage.setItem("cauce.access", "credencial-ficticia-solo-mock"); localStorage.setItem("cauce.institucion", JSON.stringify(institucion)); }, inst);
  await page.route("**/api/**", async (route) => {
    const req = route.request(); const url = new URL(req.url()); const path = url.pathname.replace(/^\/api/, "");
    if (!url.pathname.startsWith("/api/")) return route.continue();
    if (req.method() === "GET") {
      lecturas.push(url);
      let data = lista([]);
      if (path === "/usuarios/me/") data = { id: 7, nombre: "Administración", is_superuser: false, capacidades_por_institucion: { 2: ["config_institucional"] }, roles_por_institucion: { 2: ["admin"] } };
      if (path === "/instituciones/") data = lista([inst]);
      if (path === "/areas/") data = lista([{ id: 3, nombre: "Consultorios", institucion: 2 }]);
      if (path === "/notificaciones/resumen/") data = { no_leidas: 0, recientes: [] };
      if (path === "/concesiones-financieras/mias/") data = { superusuario: false, concesiones: permisos.map((accion) => ({ institucion: 2, accion, todas_las_areas: true, areas: [], permite_sensibles: true, administrativa: true })) };
      if (path === "/obligaciones-financieras/") data = lista([estado.cuenta]);
      if (path === "/obligaciones-financieras/11/") {
        if (estado.fallaDetalle) return route.fulfill({ status: 403, json: { detail: "Ya no tenés acceso a esta cuenta." } });
        data = estado.cuenta;
      }
      if (path === "/reportes-dinero/") data = { cobros_brutos: "200.00", pagos_brutos: "40.00", reintegros_cobros: "10.00", reintegros_pagos: "5.00", cobros_netos: "190.00", pagos_netos: "35.00", diferencia: "155.00", por_aprobar: { pagos: "15.00", cobros: "0.00", reintegros_pagos: "0.00", reintegros_cobros: "0.00", cantidad: 1 } };
      if (path === "/movimientos-dinero/") data = lista([{ ...estado.cuenta.movimientos[0], obligacion: 11, obligacion_tipo: "pagar", contraparte_nombre: estado.cuenta.contraparte_nombre, periodo_economico: "2026-08-01" }]);
      if (path === "/prestaciones-costo/") data = lista([{ id: 44, nombre: "Consulta médica", activo: true }]);
      if (path === "/politicas-cobro/") data = lista(estado.politicas);
      if (path === "/pendientes-cobro/") data = lista(estado.pendientes);
      if (path === "/conceptos-gasto/") data = lista([{ id: 1, nombre: "Materiales", codigo: "MAT", institucion: 2, activo: true, sensible: false }]);
      if (path === "/gastos/") data = lista([{ id: 51, institucion: 2, area: 3, sensible: false, concepto: 1, concepto_nombre: "Materiales", importe: "100.00", importe_resultante: "100.00", total_ajustes: "0.00", estado: "aprobado", estado_operativo: "aprobado", periodo_economico: "2026-09-01", registrado: "2026-09-14T12:00:00Z", ajustes: estado.ajustesGasto, cuenta_por_pagar: estado.cuentaPorPagar }]);
      return route.fulfill({ json: data });
    }
    const body = req.postDataJSON(); escrituras.push({ path, body });
    if (path === "/obligaciones-financieras/11/movimientos/") {
      estado.intentos += 1;
      if (fallaMovimiento) return route.fulfill({ status: 503, json: { detail: "Respuesta perdida" } });
      return route.fulfill({ status: 201, json: estado.cuenta });
    }
    if (path === "/movimientos-dinero/71/previsualizar-reintegro/") {
      estado.preview = { importe: body.importe, efecto: body.efecto, aprobado: body.aprobado, estado: body.aprobado ? "aprobado" : "pendiente_aprobacion", pendiente_anterior: "60.00", pendiente_resultante: body.aprobado && body.efecto === "mantener" ? "70.00" : "60.00", obligacion_resultante: body.aprobado && body.efecto === "reducir" ? "90.00" : "100.00", registrado_neto_resultante: body.aprobado ? "30.00" : "40.00", pendiente_al_aprobar: body.efecto === "mantener" ? "70.00" : "60.00", importe_reservado: body.aprobado ? "0.00" : body.importe, version_esperada: "version-a" };
      return route.fulfill({ json: estado.preview });
    }
    if (/^\/movimientos-dinero\/\d+\/(aprobar|rechazar)\/$/.test(path)) {
      const id = Number(path.split("/")[2]); const item = estado.cuenta.movimientos.find((m) => m.id === id);
      item.estado = path.endsWith("/aprobar/") ? "aprobado" : "rechazado";
      return route.fulfill({ json: estado.cuenta });
    }
    if (/^\/obligaciones-financieras\/11\/(aprobar-ajuste|rechazar-ajuste)\/$/.test(path)) return route.fulfill({ json: estado.cuenta });
    if (/^\/ajustes-gasto\/\d+\/(aprobar|rechazar)\/$/.test(path)) return route.fulfill({ json: {} });
    if (["/gastos/", "/ajustes-gasto/"].includes(path)) return route.fulfill({ status: 201, json: { id: 52, ...body, estado: body.aprobado ? "aprobado" : "pendiente_aprobacion" } });
    if (path === "/obligaciones-financieras/") { estado.cuentaPorPagar = estado.cuenta.id; return route.fulfill({ status: 201, json: estado.cuenta }); }
    if (path === "/movimientos-dinero/71/reintegrar/" || path === "/obligaciones-financieras/11/reducir/") return route.fulfill({ status: 201, json: estado.cuenta });
    if (path === "/politicas-cobro/") {
      const nueva = { id: estado.politicas.length + 1, ...body, nombre_prestacion: "Consulta médica", vigente_desde: "2026-09-15T10:00:00Z" }; estado.politicas.push(nueva);
      return route.fulfill({ status: 201, json: nueva });
    }
    return route.fulfill({ status: 400, json: { detail: "Escritura no prevista en este contrato simulado." } });
  });
  return { lecturas, escrituras, estado };
}

test("ver dinero permite entrar sin lectura de gastos y separa el mes real del económico", async ({ page }) => {
  const { lecturas } = await escenario(page, { permisos: ["ver_dinero"] });
  await page.goto("/finanzas?tab=dinero&mes=2026-09");
  await expect(page.getByRole("heading", { name: "Dinero registrado", exact: true })).toBeVisible();
  await expect(page.getByText("ARS 155,00", { exact: true })).toBeVisible();
  await page.getByLabel("Mes de pagos y cobros").fill("2026-08");
  await expect.poll(() => lecturas.filter((u) => u.pathname === "/api/reportes-dinero/").at(-1)?.searchParams.get("fecha_desde")).toBe("2026-08-01");
  expect(lecturas.filter((u) => u.pathname === "/api/obligaciones-financieras/").at(-1)?.searchParams.get("periodo_mes")).toBe("2026-09");
  expect(lecturas.some((u) => /\/(gastos|reportes-finanzas|procesamiento-finanzas|conceptos-gasto)\//.test(u.pathname))).toBe(false);
  await page.getByRole("button", { name: "Ver cuenta", exact: true }).click();
  await expect(page.getByRole("button", { name: "Registrar pago", exact: true })).toHaveCount(0);
});

test("pago valida pendiente y conserva clave al reintentar, cambiándola si cambia el importe", async ({ page }) => {
  const { escrituras } = await escenario(page, { fallaMovimiento: true });
  await page.goto("/finanzas?tab=dinero&mes=2026-09");
  await page.getByRole("button", { name: "Ver cuenta", exact: true }).click();
  await page.getByRole("button", { name: "Registrar pago", exact: true }).click();
  await page.getByLabel("Importe en ARS", { exact: true }).fill("60.01");
  await expect(page.getByRole("button", { name: "Registrar pago", exact: true })).toBeDisabled();
  await page.getByLabel("Importe en ARS", { exact: true }).fill("10.00");
  await page.getByLabel("Referencia del pago o cobro").fill("COM-2");
  await page.getByRole("button", { name: "Registrar pago", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Podés reintentar");
  await page.getByRole("button", { name: "Registrar pago", exact: true }).click();
  await expect.poll(() => escrituras.length).toBe(2);
  expect(escrituras[0].body.clave).toBe(escrituras[1].body.clave);
  await page.getByLabel("Importe en ARS", { exact: true }).fill("12.00");
  await page.getByRole("button", { name: "Registrar pago", exact: true }).click();
  await expect.poll(() => escrituras.length).toBe(3);
  expect(escrituras[2].body.clave).not.toBe(escrituras[1].body.clave);
  await expect(page.getByRole("alert")).toContainText("Podés reintentar");
  await page.getByLabel("Importe en ARS", { exact: true }).fill("10.00");
  await page.getByRole("button", { name: "Registrar pago", exact: true }).click();
  await expect.poll(() => escrituras.length).toBe(4);
  expect(escrituras[3].body.clave).toBe(escrituras[0].body.clave);
  await expect(page.getByRole("alert")).toContainText("Podés reintentar");
  await page.getByLabel("Importe en ARS", { exact: true }).fill("10");
  await page.getByRole("button", { name: "Registrar pago", exact: true }).click();
  await expect.poll(() => escrituras.length).toBe(5);
  expect(escrituras[4].body.clave).toBe(escrituras[0].body.clave);
});

test("respuesta perdida de devolución conserva intención al actualizar la vista previa", async ({ page }) => {
  const { estado } = await escenario(page);
  const intentos = [];
  const registradas = new Map();
  let vistas = 0;
  await page.route("**/api/movimientos-dinero/71/previsualizar-reintegro/", (route) => {
    vistas += 1;
    return route.fulfill({ json: { importe: "10.00", aprobado: true, estado: "aprobado", efecto: "mantener",
      pendiente_anterior: vistas === 1 ? "60.00" : "70.00", pendiente_resultante: vistas === 1 ? "70.00" : "80.00",
      obligacion_resultante: "100.00", registrado_neto_resultante: vistas === 1 ? "30.00" : "20.00",
      version_esperada: vistas === 1 ? "version-a" : "version-b" } });
  });
  await page.route("**/api/movimientos-dinero/71/reintegrar/", (route) => {
    const body = route.request().postDataJSON(); intentos.push(body);
    if (!registradas.has(body.clave)) {
      const movimiento = { id: 72 + registradas.size, tipo: "reintegro", estado: "aprobado", importe: "10.00", fecha: body.fecha, original: 71, motivo: body.motivo, disponible_reintegro: "0.00" };
      registradas.set(body.clave, movimiento); estado.cuenta.movimientos.push(movimiento);
    }
    return intentos.length === 1 ? route.abort("failed") : route.fulfill({ json: estado.cuenta });
  });
  await page.goto("/finanzas?tab=dinero&mes=2026-09");
  await page.getByRole("button", { name: "Ver cuenta", exact: true }).click();
  await page.getByRole("button", { name: "Registrar devolución", exact: true }).click();
  await page.getByLabel("Importe en ARS", { exact: true }).fill("10.00");
  await page.getByLabel("Motivo", { exact: true }).fill("Devolución acordada");
  await page.getByRole("button", { name: "Ver resultado antes de confirmar" }).click();
  await page.getByRole("button", { name: "Confirmar devolución", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Podés reintentar");
  await page.getByRole("button", { name: "Actualizar vista previa", exact: true }).click();
  await page.getByRole("button", { name: "Confirmar devolución", exact: true }).click();
  await expect.poll(() => intentos.length).toBe(2);
  expect(intentos[1].version_esperada).not.toBe(intentos[0].version_esperada);
  expect(intentos[1].pendiente_esperado).not.toBe(intentos[0].pendiente_esperado);
  expect(intentos[1].clave).toBe(intentos[0].clave);
  await expect(page.getByRole("dialog").getByText("Devuelve parte del registro #71", { exact: true })).toHaveCount(1);
});

for (const efecto of ["mantener", "reducir", "reduccion_existente"]) {
  test(`devolución ${efecto} exige vista previa y confirma su versión`, async ({ page }) => {
    const { escrituras } = await escenario(page);
    await page.goto("/finanzas?tab=dinero&mes=2026-09");
    await page.getByRole("button", { name: "Ver cuenta", exact: true }).click();
    await page.getByRole("button", { name: "Registrar devolución", exact: true }).click();
    await page.getByLabel("Importe en ARS", { exact: true }).fill("10.00");
    await page.getByLabel("Motivo", { exact: true }).fill("Devolución acordada");
    await page.getByLabel("Qué pasa con la cuenta").selectOption(efecto);
    if (efecto === "reduccion_existente") await page.getByLabel("Reducción ya registrada").selectOption("91");
    await expect(page.getByRole("button", { name: "Confirmar devolución", exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Ver resultado antes de confirmar" }).click();
    await expect(page.getByRole("region", { name: "Resultado de la devolución" })).toBeVisible();
    expect(escrituras.some((e) => e.path.endsWith("/reintegrar/"))).toBe(false);
    await page.getByRole("button", { name: "Confirmar devolución", exact: true }).click();
    await expect.poll(() => escrituras.length).toBe(2);
    expect(escrituras[1].body).toMatchObject({ importe: "10.00", efecto, version_esperada: "version-a" });
    if (efecto === "reduccion_existente") expect(escrituras[1].body.ajuste).toBe(91);
  });
}

test("cambiar datos después de previsualizar obliga a revisar otra vez", async ({ page }) => {
  await escenario(page); await page.goto("/finanzas?tab=dinero&mes=2026-09");
  await page.getByRole("button", { name: "Ver cuenta", exact: true }).click();
  await page.getByRole("button", { name: "Registrar devolución", exact: true }).click();
  await page.getByLabel("Importe en ARS", { exact: true }).fill("10.00");
  await page.getByLabel("Motivo", { exact: true }).fill("Corrección");
  await page.getByRole("button", { name: "Ver resultado antes de confirmar" }).click();
  await expect(page.getByRole("button", { name: "Confirmar devolución", exact: true })).toBeVisible();
  await page.getByLabel("Importe en ARS", { exact: true }).fill("11.00");
  await expect(page.getByRole("button", { name: "Confirmar devolución", exact: true })).toHaveCount(0);
});

test("dinero sin pendientes compacta resumen y reservas sin ocultar disponible", async ({ page }, testInfo) => {
  await escenario(page);
  await page.route("**/api/reportes-dinero/**", (route) => route.fulfill({ json: { cobros_brutos: "200.00", pagos_brutos: "40.00", reintegros_cobros: "0.00", reintegros_pagos: "0.00", cobros_netos: "200.00", pagos_netos: "40.00", diferencia: "160.00", por_aprobar: { pagos: "0.00", cobros: "0.00", reintegros_pagos: "0.00", reintegros_cobros: "0.00", cantidad: 0 } } }));
  await page.goto("/finanzas?tab=dinero&mes=2026-09");
  await expect(page.getByText("Sin registros por aprobar.", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Dinero por aprobar", exact: true })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("dinero-sin-pendientes-desktop.png"), animations: "disabled" });
  await page.getByRole("button", { name: "Ver cuenta", exact: true }).click();
  await expect(page.getByRole("dialog").getByText("Sin reservas por aprobar.", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Reservas por aprobar", exact: true })).toHaveCount(0);
  await expect(page.getByRole("dialog")).toContainText("Disponible para registrar otro pago: ARS 60,00");
  await page.screenshot({ path: testInfo.outputPath("cuenta-sin-reservas-desktop.png"), animations: "disabled" });
  await page.setViewportSize({ width: 390, height: 844 });
  const dialogo = page.getByRole("dialog");
  await expect.poll(() => dialogo.evaluate((e) => e.scrollWidth <= e.clientWidth)).toBe(true);
  for (const nombre of ["Registrar pago", "Reducir o cancelar cuenta", "Registrar devolución"]) {
    const boton = dialogo.getByRole("button", { name: nombre, exact: true });
    await boton.scrollIntoViewIfNeeded();
    await expect(boton).toBeInViewport();
    const caja = await boton.boundingBox();
    expect(caja.x).toBeGreaterThanOrEqual(0);
    expect(caja.x + caja.width).toBeLessThanOrEqual(390);
  }
  await dialogo.getByText("Sin reservas por aprobar.", { exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("cuenta-sin-reservas-movil.png"), animations: "disabled" });
  await dialogo.getByRole("button", { name: "Cerrar", exact: true }).click();
  await expect.poll(() => page.locator("main > .overflow-auto").evaluate((e) => e.scrollWidth <= e.clientWidth)).toBe(true);
  await page.getByText("Sin registros por aprobar.", { exact: true }).scrollIntoViewIfNeeded();
  await expect(page.getByRole("button", { name: "Ver cuenta", exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("dinero-sin-pendientes-movil.png"), animations: "disabled" });
});

test("devolución vinculada a reducción previa no promete aprobación conjunta", async ({ page }) => {
  const { estado } = await escenario(page);
  estado.cuenta.movimientos.push({ id: 72, tipo: "reintegro", importe: "10.00", fecha: "2026-09-14", original: 71, ajuste: 91, motivo: "Devolución de reducción previa", estado: "pendiente_aprobacion" });
  await page.goto("/finanzas?tab=dinero&mes=2026-09");
  await page.getByRole("button", { name: "Ver cuenta", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Cuenta #11" })).toBeVisible();
  await expect(page.getByRole("dialog").getByText("se aprueban juntos", { exact: false })).toHaveCount(0);
  await expect(page.getByRole("dialog")).toContainText("vinculado a la reducción ya registrada #91");
  await expect(page.getByRole("button", { name: "Aprobar movimiento", exact: true })).toBeVisible();
});

test("crear cuenta por pagar solicita contraparte y no registra dinero", async ({ page }) => {
  const { escrituras } = await escenario(page, { permisos: ["ver_gastos", "ver_dinero", "registrar_dinero"] });
  await page.goto("/finanzas?tab=gastos&mes=2026-09");
  await page.getByRole("button", { name: "Crear cuenta por pagar", exact: true }).click();
  await page.getByLabel("A quién se debe pagar").fill("Proveedor de materiales");
  await page.getByRole("button", { name: "Crear cuenta", exact: true }).click();
  await expect.poll(() => escrituras.length).toBe(1);
  expect(escrituras[0]).toMatchObject({ path: "/obligaciones-financieras/", body: { gasto: 51, contraparte_nombre: "Proveedor de materiales" } });
  expect(escrituras[0].body.importe).toBeUndefined();
  await expect(page.getByRole("dialog", { name: "Cuenta #11" })).toBeVisible();
  await page.getByRole("dialog").getByRole("button", { name: "Cerrar", exact: true }).click();
  await expect(page.getByRole("button", { name: "Ver cuenta existente", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Crear cuenta por pagar", exact: true })).toHaveCount(0);
});

test("gasto con cuenta existente permite abrirla sin permiso de registrar dinero", async ({ page }) => {
  const { estado, escrituras } = await escenario(page, { permisos: ["ver_gastos", "ver_dinero"] });
  estado.cuentaPorPagar = 11;
  await page.goto("/finanzas?tab=gastos&mes=2026-09");
  await page.getByRole("button", { name: "Ver cuenta existente", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Cuenta #11" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Crear cuenta por pagar", exact: true })).toHaveCount(0);
  expect(escrituras).toHaveLength(0);
});

test("registrar dinero sin lectura no ofrece crear una cuenta que la API rechazaría", async ({ page }) => {
  const { escrituras } = await escenario(page, { permisos: ["ver_gastos", "registrar_dinero"] });
  await page.goto("/finanzas?tab=gastos&mes=2026-09");
  await expect(page.getByText("Materiales", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Crear cuenta por pagar", exact: true })).toHaveCount(0);
  expect(escrituras).toHaveLength(0);
});

test("política explicita cobro sin tomar costo ni asumir responsable", async ({ page }) => {
  const { escrituras } = await escenario(page, { permisos: ["configurar_cobros"] });
  await page.goto("/finanzas?mes=2026-09");
  await page.getByRole("button", { name: "Configurar cobros por atención", exact: true }).click();
  await page.getByRole("button", { name: "Configurar una atención", exact: true }).click();
  await page.getByRole("combobox", { name: "Atención", exact: true }).selectOption("44");
  await page.getByLabel("¿Esta atención se cobra?").selectOption("si");
  await page.getByRole("button", { name: "Guardar política", exact: true }).click();
  await expect.poll(() => escrituras.length).toBe(1);
  expect(escrituras[0].body).toMatchObject({ prestacion: 44, cobrar: true, importe: null, contraparte_nombre: "" });
  expect(escrituras[0].body.vigente_desde).toBeUndefined();
});

test("área institucional no consulta todas las áreas", async ({ page }) => {
  const { lecturas } = await escenario(page);
  await page.goto("/finanzas?tab=dinero&mes=2026-09&area=null");
  await expect(page.getByRole("heading", { name: "Dinero registrado", exact: true })).toBeVisible();
  for (const recurso of ["obligaciones-financieras", "reportes-dinero", "pendientes-cobro"]) {
    await expect.poll(() => lecturas.filter((u) => u.pathname === `/api/${recurso}/`).at(-1)?.searchParams.get("area_sin_asignar")).toBe("true");
    expect(lecturas.filter((u) => u.pathname === `/api/${recurso}/`).at(-1)?.searchParams.has("area")).toBe(false);
  }
});

test("detalle denegado no conserva importes ni acciones de la cuenta", async ({ page }) => {
  await escenario(page, { fallaDetalle: true });
  await page.goto("/finanzas?tab=dinero&mes=2026-09");
  await page.getByRole("button", { name: "Ver cuenta", exact: true }).click();
  const modal = page.getByRole("dialog");
  await expect(modal.getByRole("alert")).toContainText("No tenés permiso para ver esto");
  await expect(modal.getByRole("button", { name: "Registrar pago", exact: true })).toHaveCount(0);
  await expect(modal.getByText("ARS 100,00", { exact: true })).toHaveCount(0);
});

test("movimientos del período permiten abrir una cuenta de otro mes económico", async ({ page }) => {
  const { lecturas } = await escenario(page);
  await page.goto("/finanzas?tab=dinero&mes=2026-09");
  await page.getByLabel("Mes de pagos y cobros").fill("2026-09");
  await page.getByRole("button", { name: "Ver movimientos del período", exact: true }).click();
  await expect(page.getByRole("cell", { name: "2026-08", exact: true })).toBeVisible();
  expect(lecturas.filter((u) => u.pathname === "/api/movimientos-dinero/").at(-1)?.searchParams.get("fecha_desde")).toBe("2026-09-01");
  await page.getByRole("button", { name: "Ver cuenta #11", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Cuenta #11" })).toBeVisible();
});

for (const puedeAprobar of [true, false]) {
  for (const tipo of ["movimiento", "reducir", "reintegro"]) {
    test(`${tipo}: Aprobado por defecto depende del permiso y viaja explícito (${puedeAprobar})`, async ({ page }) => {
      const { escrituras } = await escenario(page, { permisos: ["ver_dinero", "registrar_dinero", "corregir_dinero", ...(puedeAprobar ? ["aprobar_dinero"] : [])] });
      await page.goto("/finanzas?tab=dinero&mes=2026-09");
      await page.getByRole("button", { name: "Ver cuenta", exact: true }).click();
      await page.getByRole("button", { name: tipo === "movimiento" ? "Registrar pago" : tipo === "reducir" ? "Reducir o cancelar cuenta" : "Registrar devolución", exact: true }).click();
      const checkbox = page.getByRole("checkbox", { name: "Aprobado", exact: true });
      if (puedeAprobar) await expect(checkbox).toBeChecked();
      else { await expect(checkbox).not.toBeChecked(); await expect(checkbox).toBeDisabled(); }
      await page.getByLabel("Importe en ARS", { exact: true }).fill("10.00");
      if (tipo !== "movimiento") await page.getByLabel("Motivo", { exact: true }).fill("Corrección administrativa");
      if (tipo === "reintegro") {
        await page.getByRole("button", { name: "Ver resultado antes de confirmar" }).click();
        if (!puedeAprobar) {
          await expect(page.getByRole("region", { name: "Resultado de la devolución" })).toContainText("Los importes confirmados no cambian todavía");
          await expect(page.getByText("Pendiente si se aprueba", { exact: true })).toBeVisible();
        }
      }
      await page.getByRole("button", { name: tipo === "movimiento" ? "Registrar pago" : tipo === "reducir" ? "Reducir o cancelar cuenta" : "Confirmar devolución", exact: true }).click();
      await expect.poll(() => escrituras.length).toBe(tipo === "reintegro" ? 2 : 1);
      expect(escrituras.at(-1).body.aprobado).toBe(puedeAprobar);
    });
  }
}

test("un aprobador puede destildar y dejar pago pendiente usando el disponible reservado", async ({ page }) => {
  const { escrituras, estado } = await escenario(page);
  Object.assign(estado.cuenta, { por_aprobar: "15.00", disponible_registro: "45.00" });
  await page.goto("/finanzas?tab=dinero&mes=2026-09");
  await expect(page.getByRole("region", { name: "Dinero por aprobar" })).toContainText("no están incluidos");
  await page.getByRole("button", { name: "Ver cuenta", exact: true }).click();
  await page.getByRole("button", { name: "Registrar pago", exact: true }).click();
  await page.getByRole("checkbox", { name: "Aprobado", exact: true }).uncheck();
  await page.getByLabel("Importe en ARS", { exact: true }).fill("45.01");
  await expect(page.getByRole("button", { name: "Registrar pago", exact: true })).toBeDisabled();
  await page.getByLabel("Importe en ARS", { exact: true }).fill("45.00");
  await page.getByRole("button", { name: "Registrar pago", exact: true }).click();
  await expect.poll(() => escrituras.length).toBe(1);
  expect(escrituras[0].body).toMatchObject({ aprobado: false, importe: "45.00" });
});

for (const rechazar of [false, true]) {
  test(`movimiento pendiente se ${rechazar ? "rechaza con motivo" : "aprueba"} desde la cuenta`, async ({ page }) => {
    const { estado, escrituras } = await escenario(page);
    estado.cuenta.movimientos.push({ id: 72, tipo: "pago", importe: "15.00", fecha: "2026-09-14", estado: "pendiente_aprobacion", aprobado: false, disponible_reintegro: "0.00", original: null });
    await page.goto("/finanzas?tab=dinero&mes=2026-09");
    await page.getByRole("button", { name: "Ver cuenta", exact: true }).click();
    await page.getByRole("button", { name: rechazar ? "Rechazar movimiento" : "Aprobar movimiento", exact: true }).click();
    if (rechazar) {
      await expect(page.getByRole("button", { name: "Confirmar rechazo", exact: true })).toBeDisabled();
      await page.getByLabel("Motivo del rechazo").fill("El comprobante no corresponde");
    }
    await page.getByRole("button", { name: rechazar ? "Confirmar rechazo" : "Confirmar aprobación", exact: true }).click();
    await expect.poll(() => escrituras.length).toBe(1);
    expect(escrituras[0].path).toBe(`/movimientos-dinero/72/${rechazar ? "rechazar" : "aprobar"}/`);
    if (rechazar) expect(escrituras[0].body.motivo).toBe("El comprobante no corresponde");
  });
}

test("devolución y reducción vinculada tienen una sola decisión", async ({ page }) => {
  const { estado } = await escenario(page);
  estado.cuenta.movimientos.push({ id: 72, tipo: "reintegro", importe: "10.00", fecha: "2026-09-14", estado: "pendiente_aprobacion", original: 71, ajuste: 92, disponible_reintegro: "0.00" });
  estado.cuenta.ajustes.push({ id: 92, importe: "-10.00", motivo: "Devolución y cancelación", estado: "pendiente_aprobacion", movimiento_vinculado: 72, disponible_reintegro: "0.00" });
  await page.goto("/finanzas?tab=dinero&mes=2026-09");
  await page.getByRole("button", { name: "Ver cuenta", exact: true }).click();
  await expect(page.getByRole("button", { name: "Aprobar movimiento", exact: true })).toHaveCount(1);
  await expect(page.getByRole("button", { name: "Aprobar reducción", exact: true })).toHaveCount(0);
  await expect(page.getByText("Se decide junto con la devolución #72.")).toBeVisible();
});

for (const puedeAprobar of [true, false]) {
  test(`gasto y ajuste manual usan aprobación explícita según permiso (${puedeAprobar})`, async ({ page }) => {
    const { escrituras } = await escenario(page, { permisos: ["ver_gastos", "registrar_gastos", "corregir_gastos", ...(puedeAprobar ? ["aprobar_gastos"] : [])] });
    await page.goto("/finanzas?tab=gastos&mes=2026-09");
    await page.getByRole("button", { name: "Registrar gasto", exact: true }).click();
    await page.getByRole("combobox", { name: "Área del gasto", exact: true }).selectOption("3");
    await page.getByRole("combobox", { name: /^Concepto/ }).selectOption("1");
    await page.getByLabel("Importe en ARS").fill("25.00");
    const checkbox = page.getByRole("checkbox", { name: "Aprobado", exact: true });
    if (puedeAprobar) { await expect(checkbox).toBeChecked(); await checkbox.uncheck(); }
    else { await expect(checkbox).not.toBeChecked(); await expect(checkbox).toBeDisabled(); }
    await page.getByRole("button", { name: "Confirmar", exact: true }).click();
    await expect.poll(() => escrituras.length).toBe(1);
    expect(escrituras[0].body.aprobado).toBe(false);
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.getByRole("button", { name: "Ajustar", exact: true }).click();
    if (puedeAprobar) await expect(checkbox).toBeChecked();
    else await expect(checkbox).toBeDisabled();
    await page.getByLabel("Ajuste en ARS", { exact: false }).fill("-10.00");
    await page.getByLabel("Motivo", { exact: true }).fill("Corrección acordada");
    await page.getByRole("button", { name: "Confirmar", exact: true }).click();
    await expect.poll(() => escrituras.length).toBe(2);
    expect(escrituras[1]).toMatchObject({ path: "/ajustes-gasto/", body: { aprobado: puedeAprobar } });
  });
}

test("ajuste de gasto pendiente muestra historia y permite rechazar con motivo", async ({ page }) => {
  const { estado, escrituras } = await escenario(page, { permisos: ["ver_gastos", "aprobar_gastos"] });
  estado.ajustesGasto = [{ id: 99, importe: "-10.00", motivo: "Corrección propuesta", estado: "pendiente_aprobacion", registrado_por: 7, registrado: "2026-09-14T12:00:00Z" }];
  await page.goto("/finanzas?tab=gastos&mes=2026-09");
  await page.getByRole("button", { name: "Detalle", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Pendiente de aprobación");
  await page.getByRole("button", { name: "Rechazar ajuste", exact: true }).click();
  await expect(page.getByRole("button", { name: "Confirmar rechazo", exact: true })).toBeDisabled();
  await page.getByLabel("Motivo del rechazo").fill("Importe incorrecto");
  await page.getByRole("button", { name: "Confirmar rechazo", exact: true }).click();
  await expect.poll(() => escrituras.length).toBe(1);
  expect(escrituras[0]).toEqual({ path: "/ajustes-gasto/99/rechazar/", body: { motivo: "Importe incorrecto" } });
});


test("las tablas de dinero envían búsqueda y orden al servidor", async ({ page }) => {
  const { lecturas } = await escenario(page);
  await page.goto("/finanzas?tab=dinero&mes=2026-09");
  await page.getByRole("textbox", { name: "Buscar cuentas", exact: true }).fill("Proveedor");
  await expect(page.getByRole("button", { name: "Quitar filtro Buscar cuentas", exact: true })).toContainText("Proveedor");
  await page.getByRole("button", { name: "Ordenar por A quién / de quién", exact: true }).click();
  await expect.poll(() => lecturas.some((u) => u.pathname === "/api/obligaciones-financieras/" && u.searchParams.get("search") === "Proveedor" && u.searchParams.get("ordering") === "contraparte_nombre")).toBe(true);
  await page.getByRole("button", { name: "Ver movimientos del período", exact: true }).click();
  await page.getByRole("textbox", { name: "Buscar movimientos", exact: true }).fill("COM");
  await page.getByRole("button", { name: "Ordenar por Importe", exact: true }).click();
  await expect.poll(() => lecturas.some((u) => u.pathname === "/api/movimientos-dinero/" && u.searchParams.get("search") === "COM" && u.searchParams.get("ordering") === "importe")).toBe(true);
  await page.getByRole("textbox", { name: "Buscar cobros por completar", exact: true }).fill("consulta");
  await page.getByRole("button", { name: "Ordenar por Arancel", exact: true }).click();
  await expect.poll(() => lecturas.some((u) => u.pathname === "/api/pendientes-cobro/" && u.searchParams.get("search") === "consulta" && u.searchParams.get("ordering") === "importe")).toBe(true);
});
