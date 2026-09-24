import { expect, test } from "@playwright/test";

const institucion = { id: 2, nombre: "Hospital Escuela" };
const lista = (results = []) => ({ count: results.length, results, next: null, previous: null });
const todos = ["ver_gastos", "ver_costos", "ver_dinero", "registrar_gastos", "configurar_gastos_esperados", "configurar_repartos", "configurar_componentes", "configurar_cobros"];

async function escenario(page, { permisos = todos, errorPermisos = false, esperarPermisos, esperarCatalogo } = {}) {
  const escrituras = [];
  await page.addInitScript((inst) => {
    sessionStorage.setItem("salud.access", "credencial-ficticia-solo-mock");
    localStorage.setItem("salud.institucion", JSON.stringify(inst));
  }, institucion);
  // Todas las solicitudes API se interceptan; jamás se escriben datos de demo.
  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const pathname = new URL(req.url()).pathname;
    // Vite también sirve /src/api/*.js: son módulos del frontend, no la API.
    if (!pathname.startsWith("/api/")) return route.continue();
    const path = pathname.replace(/^\/api/, "");
    if (req.method() !== "GET") {
      const body = req.postDataJSON();
      escrituras.push({ path, body });
      return route.fulfill(path === "/conceptos-gasto/"
        ? { status: 201, json: { id: 3, codigo: "AUTO-3", ...body } }
        : { status: 400, json: { detail: "Escritura no prevista bloqueada por la prueba" } });
    }
    let data = lista();
    if (path === "/usuarios/me/") data = { id: 7, nombre: "Administración Escuela", email: "admin@mock.local", is_superuser: false, capacidades_por_institucion: { 2: ["config_institucional"] }, roles_por_institucion: { 2: ["administrativo"] } };
    if (path === "/instituciones/") data = lista([institucion]);
    if (path === "/areas/") {
      if (esperarCatalogo) await esperarCatalogo;
      data = lista([{ id: 3, institucion: 2, nombre: "Consultorios" }]);
    }
    if (path === "/concesiones-financieras/mias/") {
      if (esperarPermisos) await esperarPermisos;
      if (errorPermisos) return route.fulfill({ status: 403, json: { detail: "Permisos no disponibles" } });
      data = { superusuario: false, concesiones: permisos.map((accion) => ({ institucion: 2, accion, todas_las_areas: true, areas: [], permite_sensibles: true })) };
    }
    if (path === "/notificaciones/resumen/") data = { no_leidas: 0, recientes: [] };
    if (path === "/reportes-finanzas/") data = { aprobados: "0.00", pendientes_aprobacion: "0.00", distribuido: "0.00", sin_distribuir: "0.00", moneda: "ARS", agrupaciones: [] };
    if (path === "/reportes-dinero/") data = { cobros_netos: "0.00", pagos_netos: "0.00", diferencia: "0.00", cantidad_movimientos: 0, fecha_desde: "2026-09-01", fecha_hasta: "2026-09-30", moneda: "ARS", por_aprobar: { cantidad: 0 }, agrupaciones: [] };
    if (path === "/reportes-costos/") data = { atenciones: 0, atenciones_incompletas: 0, ajustes_pendientes: 0, reparto_actualizando: false, directo_conocido: "0.00", compartido_conocido: "0.00", moneda: "ARS", agrupaciones: { area: [], prestacion: [] } };
    if (path === "/procesamiento-finanzas/") data = { estado: "actualizado", pendientes: 0, worker_activo: true, mensaje: "Sin cambios pendientes." };
    if (path === "/instituciones/2/metricas/") data = { areas: 1, subareas: 0, staff: 1, casos_activos: 0 };
    return route.fulfill({ json: data });
  });
  return escrituras;
}

for (const [tab, visibles] of [
  ["resumen", []], ["calendario", ["Agregar gasto mensual", "Nuevo concepto"]],
  ["gastos", ["Registrar gasto", "Agregar gasto mensual", "Nuevo concepto"]],
  ["costos", ["Configurar costos por atención"]],
  ["repartos", ["Nuevo concepto", "Configurar repartos"]],
  ["dinero", ["Configurar cobros por atención"]],
]) {
  test(`cabecera ${tab}: sólo acciones contextuales y resto en menú`, async ({ page }) => {
    await escenario(page);
    await page.goto(`/finanzas?tab=${tab}&mes=2026-09`);
    const cabecera = page.getByRole("group", { name: "Acciones de Finanzas", exact: true });
    await expect(cabecera.getByRole("button", { name: "Acciones de finanzas" })).toBeVisible();
    await expect(cabecera.getByRole("button")).toHaveCount(visibles.length + 1);
    for (const nombre of visibles) await expect(cabecera.getByRole("button", { name: nombre, exact: true })).toBeEnabled();
    await cabecera.getByRole("button", { name: "Acciones de finanzas" }).click();
    const menu = page.getByRole("dialog", { name: "Acciones de finanzas" });
    await expect(menu).toBeVisible();
    for (const nombre of visibles) await expect(menu.getByRole("button", { name: nombre, exact: true })).toHaveCount(0);
    if (!visibles.includes("Nuevo concepto")) await expect(menu.getByRole("button", { name: "Nuevo concepto", exact: true })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(menu).toHaveCount(0);
    await expect(cabecera.getByRole("button", { name: "Acciones de finanzas" })).toBeFocused();
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 900 });
      const limite = await cabecera.boundingBox();
      const desplegable = await cabecera.getByRole("button", { name: "Acciones de finanzas" }).boundingBox();
      expect(Math.abs(desplegable.x + desplegable.width - limite.x - limite.width)).toBeLessThan(2);
      await expect(cabecera.getByRole("button").last()).toHaveAccessibleName("Acciones de finanzas");
      for (const nombre of visibles) {
        const boton = await cabecera.getByRole("button", { name: nombre, exact: true }).boundingBox();
        expect(boton.x + boton.width).toBeLessThanOrEqual(desplegable.x);
      }
    }
  });
}

test("cambiar pestaña cierra el menú, conserva el mes y no desborda en móvil", async ({ page }, testInfo) => {
  await escenario(page);
  await page.goto("/finanzas?tab=gastos&mes=2026-09");
  await page.getByRole("button", { name: "Acciones de finanzas" }).click();
  await page.getByRole("tab", { name: "Costos por atención", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Acciones de finanzas" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Registrar gasto", exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Mes económico", { exact: true })).toHaveValue("2026-09");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("tab", { name: "Gastos registrados", exact: true }).click();
  await page.getByRole("button", { name: "Acciones de finanzas" }).click();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("acciones-movil.png"), animations: "disabled" });
});

test("desplegable comparte el estilo primario y la altura de Registrar gasto", async ({ page }, testInfo) => {
  await escenario(page);
  await page.goto("/finanzas?tab=gastos");
  const registrar = page.getByRole("button", { name: "Registrar gasto", exact: true });
  const acciones = page.getByRole("button", { name: "Acciones de finanzas", exact: true });
  const estilo = (el) => {
    const css = getComputedStyle(el);
    return [css.height, css.backgroundColor, css.color, css.borderRadius, css.fontWeight, css.paddingLeft];
  };
  await expect(acciones).toBeVisible();
  expect(await acciones.evaluate(estilo)).toEqual(await registrar.evaluate(estilo));
  await page.screenshot({ path: testInfo.outputPath("botonera-escritorio.png"), animations: "disabled" });
  await acciones.click();
  await expect(page.getByRole("dialog", { name: "Acciones de finanzas" }).getByText("Acciones de finanzas", { exact: true })).toBeVisible();
});

test("lector no recibe acciones prohibidas y registrador sin lectura conserva la carga", async ({ page }) => {
  await escenario(page, { permisos: ["ver_gastos"] });
  await page.goto("/finanzas?tab=gastos");
  await expect(page.getByRole("tab", { name: "Gastos registrados", exact: true })).toBeVisible();
  await expect(page.getByRole("group", { name: "Acciones de Finanzas", exact: true }).getByRole("button")).toHaveCount(0);
  await page.unroute("**/api/**");
  await escenario(page, { permisos: ["registrar_gastos"] });
  await page.reload();
  await expect(page.getByRole("button", { name: "Registrar gasto", exact: true })).toBeEnabled();
  await expect(page.getByRole("tab")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Acciones de finanzas" })).toHaveCount(0);
  await page.getByRole("button", { name: "Registrar gasto", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Registrar gasto", exact: true })).toBeVisible();
});

for (const codigo of ["", "MANUAL-1"]) {
  test(`nuevo concepto ${codigo ? "respeta código manual avanzado" : "omite código para generación automática"}`, async ({ page }) => {
    const escrituras = await escenario(page);
    await page.goto("/finanzas?tab=gastos");
    await page.getByRole("button", { name: "Nuevo concepto", exact: true }).click();
    const formulario = page.getByRole("dialog", { name: "Nuevo concepto de gasto" });
    await expect(page.getByRole("dialog", { name: "Acciones de finanzas" })).toHaveCount(0);
    await formulario.getByLabel("Nombre", { exact: true }).fill("Mantenimiento de ascensores");
    await expect(formulario.getByLabel("Código de referencia (opcional)")).not.toBeVisible();
    if (codigo) {
      await formulario.getByText("Opciones avanzadas", { exact: true }).click();
      await formulario.getByLabel("Código de referencia (opcional)").fill(codigo);
    }
    await formulario.getByRole("button", { name: "Confirmar", exact: true }).click();
    await expect(formulario).toHaveCount(0);
    expect(escrituras).toEqual([{ path: "/conceptos-gasto/", body: { institucion: 2, nombre: "Mantenimiento de ascensores", sensible: false, ...(codigo ? { codigo } : {}) } }]);
  });
}

test("gasto mensual usa una sola terminología y explica que no genera operaciones", async ({ page }) => {
  await escenario(page);
  await page.goto("/finanzas?tab=gastos");
  await expect(page.getByRole("tab", { name: "Gastos mensuales", exact: true })).toBeVisible();
  await expect(page.getByText(/gasto esperado|control mensual/i)).toHaveCount(0);
  await page.getByRole("button", { name: "Agregar gasto mensual", exact: true }).click();
  const formulario = page.getByRole("dialog", { name: "Agregar gasto mensual", exact: true });
  await expect(formulario.getByLabel("Vigente desde", { exact: true })).toBeVisible();
  await formulario.getByRole("button", { name: "Cómo funcionan los gastos mensuales", exact: true }).click();
  await expect(page.getByText("No genera gastos, cuentas ni pagos automáticamente.", { exact: false })).toBeVisible();
});

test("preparación de catálogo no ofrece acciones prematuramente", async ({ page }) => {
  let liberar;
  const esperarCatalogo = new Promise((resolve) => { liberar = resolve; });
  await escenario(page, { esperarCatalogo });
  await page.goto("/finanzas?tab=gastos");
  await expect(page.getByText("Preparando acciones…", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Registrar gasto", exact: true })).toHaveCount(0);
  liberar();
  await expect(page.getByRole("button", { name: "Registrar gasto", exact: true })).toBeEnabled();
});

for (const [nombre, opciones, visible] of [
  ["registrador financiero", { permisos: ["registrar_gastos"] }, true],
  ["sin acceso financiero", { permisos: [] }, false],
  ["error de permisos", { errorPermisos: true }, false],
]) {
  test(`Inicio: acceso rápido para ${nombre}`, async ({ page }) => {
    await escenario(page, opciones);
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Secciones de la institución" })).toBeVisible();
    const acceso = page.locator('[data-tour="inicio-finanzas"]');
    if (visible) {
      await expect(acceso).toBeVisible();
      await acceso.click();
      await expect(page).toHaveURL(/\/finanzas/);
    } else await expect(acceso).toHaveCount(0);
  });
}

test("Inicio oculta el acceso mientras consulta permisos", async ({ page }) => {
  let liberar;
  const esperarPermisos = new Promise((resolve) => { liberar = resolve; });
  await escenario(page, { esperarPermisos });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Secciones de la institución" })).toBeVisible();
  await expect(page.locator('[data-tour="inicio-finanzas"]')).toHaveCount(0);
  liberar();
  await expect(page.locator('[data-tour="inicio-finanzas"]')).toBeVisible();
});
