import { expect, test } from "@playwright/test";

const institucion = { id: 2, nombre: "Hospital de prueba" };
const lista = (results) => ({ count: results.length, results, next: null, previous: null });
const urlEditor = "/api/concesiones-financieras/editar-membresia/";
const lectura = { id: 1, membresia: 8, accion: "ver_gastos", areas: [3], todas_las_areas: false, permite_sensibles: false };
const registro = { id: 2, membresia: 8, accion: "registrar_gastos", areas: [4], todas_las_areas: false, permite_sensibles: true };

async function escenario(page, { admin = false, activo = true, detalleError = false } = {}) {
  const db = { concesiones: structuredClone([lectura, registro]), version: 1, conflicto: false, sinRespuesta: false };
  const escrituras = [];
  const peticiones = [];
  const membresias = [{ id: 8, usuario: 8, usuario_nombre: "Ana María Pérez del Río", usuario_email: "ana@prueba.test",
    institucion: 2, rol: admin ? "admin" : "administrativo", rol_display: admin ? "Admin de institución" : "Administrativo", activo, areas: [3] },
  { id: 9, usuario: 8, usuario_nombre: "Ana María Pérez del Río", usuario_email: "ana@prueba.test", institucion: 2,
    rol: "configurador", rol_display: "Configurador", activo: true, areas: [4] }];
  const snapshot = (miembro = 8) => ({ membresia: miembro, activo: miembro === 8 ? activo : true,
    concesiones: miembro === 8 ? db.concesiones : [{ ...lectura, id: 10, membresia: 9, areas: [4], permite_sensibles: true }],
    heredadas: admin ? ["ver_costos", "ver_gastos"] : [],
    otras_membresias: miembro === 8 ? [{ ...lectura, id: 10, membresia: 9, areas: [4], permite_sensibles: true }] : db.concesiones,
    version_esperada: String(db.version).padStart(64, "0") });
  await page.addInitScript((inst) => {
    localStorage.setItem("salud.access", "token-simulado-sin-acceso-real");
    localStorage.setItem("salud.institucion", JSON.stringify(inst));
  }, institucion);
  await page.route("**/api/**", async (route) => {
    const req = route.request(); const url = new URL(req.url()); const path = url.pathname;
    if (!path.startsWith("/api/")) return route.continue();
    peticiones.push({ path, method: req.method() });
    if (req.method() !== "GET") {
      const body = req.postDataJSON(); escrituras.push({ path, method: req.method(), body });
      if (path === urlEditor && req.method() === "PUT") {
        if (db.conflicto) {
          db.conflicto = false; db.version += 1;
          db.concesiones.push({ ...lectura, id: 12, accion: "ver_costos" });
          return route.fulfill({ status: 409, json: { detail: "La versión cambió." } });
        }
        if (db.sinRespuesta) return route.fulfill({ status: 503, json: { detail: "Respuesta no confirmada." } });
        db.concesiones = body.concesiones.map((fila, n) => ({ ...fila, membresia: 8,
          id: db.concesiones.find((anterior) => anterior.accion === fila.accion)?.id || n + 20 }));
        db.version += 1;
        return route.fulfill({ json: snapshot() });
      }
      if (path === "/api/usuarios/8/" && req.method() === "PATCH") return route.fulfill({ json: { id: 8, ...body } });
      return route.fulfill({ status: 400, json: { detail: "Escritura no prevista: bloqueada por la prueba." } });
    }
    let data = lista([]);
    if (path === "/api/usuarios/me/") data = { id: 7, nombre: "Administración", is_superuser: false,
      capacidades_por_institucion: { 2: ["config_institucional"] }, roles_por_institucion: { 2: ["admin"] } };
    if (path === "/api/usuarios/8/") {
      if (detalleError) return route.fulfill({ status: 503, json: { detail: "Detalle no disponible." } });
      data = { id: 8, email: "ana@prueba.test", nombre: "Ana María", apellido: "Pérez del Río", is_active: false };
    }
    if (path === "/api/instituciones/") data = lista([institucion]);
    if (path === "/api/areas/") data = lista([{ id: 3, nombre: "Clínica médica", institucion: 2 }, { id: 4, nombre: "Cardiología", institucion: 2 }]);
    if (path === "/api/membresias/") data = lista(membresias);
    if (path === urlEditor) data = snapshot(Number(url.searchParams.get("membresia")));
    if (path === "/api/concesiones-financieras/mias/") data = { superusuario: false, concesiones: [] };
    if (path === "/api/notificaciones/resumen/") data = { no_leidas: 0, recientes: [] };
    return route.fulfill({ json: data });
  });
  return { db, escrituras, peticiones };
}

async function abrirUsuario(page) {
  await page.goto("/administracion");
  await page.getByRole("row").filter({ hasText: "Ana María Pérez del Río" }).click();
  await expect(page.getByRole("dialog", { name: "Editar usuario" })).toBeVisible();
  const permisos = page.getByRole("region", { name: "Permisos financieros", exact: true });
  await permisos.locator("summary").filter({ hasText: /^Permisos financieros$/ }).click();
  return permisos;
}

test("permisos plegables conservan edición y adaptan hasta tres columnas sin desbordar", async ({ page }, testInfo) => {
  const { escrituras } = await escenario(page);
  await page.goto("/administracion");
  await page.getByRole("row").filter({ hasText: "Ana María Pérez del Río" }).click();
  const modal = page.getByRole("dialog", { name: "Editar usuario", exact: true });
  const permisos = modal.getByRole("region", { name: "Permisos financieros", exact: true });
  const plegar = permisos.locator("summary").filter({ hasText: /^Permisos financieros$/ });
  await expect(plegar).toBeVisible();
  await expect(permisos.getByLabel("Ver gastos", { exact: true })).not.toBeVisible();
  await plegar.click();
  const registrar = permisos.getByLabel("Registrar gastos", { exact: true });
  await registrar.uncheck();
  await plegar.click();
  await expect(registrar).not.toBeVisible();
  await plegar.focus();
  await page.keyboard.press("Enter");
  await expect(registrar).not.toBeChecked();
  const grilla = permisos.getByRole("group", { name: "Acciones financieras de esta membresía" });
  for (const [width, columnas] of [[1440, 3], [800, 2], [390, 1]]) {
    await page.setViewportSize({ width, height: 900 });
    // Fieldset puede conservar repeat(...) en el estilo calculado aunque la
    // grilla ya esté resuelta: comprobamos las columnas realmente dibujadas.
    await expect.poll(() => grilla.evaluate((el) => new Set([...el.children]
      .filter((fila) => fila.tagName === "DIV")
      .map((fila) => Math.round(fila.getBoundingClientRect().x))).size)).toBe(columnas);
    await expect.poll(() => modal.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
    await grilla.scrollIntoViewIfNeeded();
    await page.screenshot({ path: testInfo.outputPath(`permisos-${columnas}-columnas.png`), animations: "disabled" });
  }
  expect(escrituras).toHaveLength(0);
});

test("editar usuario carga nombre y apellido reales antes de permitir guardar datos personales", async ({ page }) => {
  const { escrituras } = await escenario(page);
  const permisos = await abrirUsuario(page);
  await expect(page.getByLabel("Nombre *", { exact: true })).toHaveValue("Ana María");
  await expect(page.getByLabel("Apellido", { exact: true })).toHaveValue("Pérez del Río");
  await expect(page.getByLabel("Activo", { exact: true })).not.toBeChecked();
  await expect(permisos.getByRole("checkbox", { name: "Ver gastos", exact: true })).toBeChecked();
  await page.getByRole("button", { name: "Guardar datos personales", exact: true }).click();
  await expect.poll(() => escrituras.length).toBe(1);
  expect(escrituras[0]).toEqual({ path: "/api/usuarios/8/", method: "PATCH", body: {
    email: "ana@prueba.test", nombre: "Ana María", apellido: "Pérez del Río", is_active: false,
  } });
});

test("fallo al obtener detalle no permite sobrescribir usuario con nombres vacíos", async ({ page }) => {
  const { escrituras } = await escenario(page, { detalleError: true });
  await page.goto("/administracion");
  await page.getByRole("row").filter({ hasText: "Ana María Pérez del Río" }).click();
  await expect(page.getByRole("button", { name: "Guardar datos personales", exact: true })).toBeDisabled();
  await expect(page.getByLabel("Nombre *", { exact: true })).toHaveCount(0);
  expect(escrituras).toHaveLength(0);
});

test("checklist conserva alcances diferentes sin unir membresías y guarda sólo permisos", async ({ page }, testInfo) => {
  const { escrituras } = await escenario(page);
  const permisos = await abrirUsuario(page);
  await expect(permisos.getByRole("checkbox", { name: "Ver gastos", exact: true })).toBeChecked();
  await expect(permisos.getByRole("checkbox", { name: "Registrar gastos", exact: true })).toBeChecked();
  await permisos.getByRole("checkbox", { name: "Ver costos", exact: true }).check();
  await permisos.getByRole("checkbox", { name: "Clínica médica · Ver costos", exact: true }).check();
  await permisos.getByRole("button", { name: "Guardar permisos financieros", exact: true }).click();
  await expect.poll(() => escrituras.length).toBe(1);
  expect(escrituras[0].path).toBe(urlEditor);
  expect(escrituras[0].body.concesiones).toEqual([
    { accion: "ver_costos", areas: [3], todas_las_areas: false, permite_sensibles: false },
    { accion: "ver_gastos", areas: [3], todas_las_areas: false, permite_sensibles: false },
    { accion: "registrar_gastos", areas: [4], todas_las_areas: false, permite_sensibles: true },
  ]);
  expect(escrituras[0].body.membresia).toBe(8);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await permisos.getByText("Alcance de Ver costos", { exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("permisos-integrados-movil.png"), animations: "disabled" });
});

test("heredados se ven Por rol y guardado no elimina concesión redundante", async ({ page }) => {
  const { escrituras } = await escenario(page, { admin: true });
  const permisos = await abrirUsuario(page);
  const lecturaRol = permisos.getByRole("checkbox", { name: "Ver gastos", exact: true });
  await expect(lecturaRol).toBeChecked(); await expect(lecturaRol).toBeDisabled();
  await expect(permisos.getByText("Por rol · no revocable aquí", { exact: true })).toHaveCount(2);
  await permisos.getByRole("checkbox", { name: "Registrar gastos", exact: true }).uncheck();
  await permisos.getByRole("button", { name: "Guardar permisos financieros", exact: true }).click();
  await expect.poll(() => escrituras.length).toBe(1);
  expect(escrituras[0].body.concesiones).toEqual([{ accion: "ver_gastos", areas: [3], todas_las_areas: false, permite_sensibles: false }]);
  await permisos.getByText("Alcance de Ver gastos", { exact: true }).click();
  await permisos.getByRole("checkbox", { name: "Conservar concesión explícita · Ver gastos", exact: true }).uncheck();
  await expect(lecturaRol).toBeChecked();
  await permisos.getByRole("button", { name: "Guardar permisos financieros", exact: true }).click();
  await expect.poll(() => escrituras.length).toBe(2);
  expect(escrituras[1].body.concesiones).toEqual([]);
  await expect(lecturaRol).toBeChecked(); await expect(lecturaRol).toBeDisabled();
});

test("conflicto bloquea repetición y exige consultar el estado de otro administrador", async ({ page }) => {
  const { db, escrituras } = await escenario(page);
  const permisos = await abrirUsuario(page);
  await permisos.getByRole("checkbox", { name: "Registrar gastos", exact: true }).uncheck();
  db.conflicto = true;
  await permisos.getByRole("button", { name: "Guardar permisos financieros", exact: true }).click();
  await expect(permisos.getByRole("alert")).toContainText("Los permisos cambiaron");
  await expect(permisos.getByRole("button", { name: "Guardar permisos financieros", exact: true })).toBeDisabled();
  await permisos.getByRole("button", { name: "Volver a consultar permisos", exact: true }).click();
  await expect(permisos.getByRole("checkbox", { name: "Registrar gastos", exact: true })).toBeChecked();
  await expect(permisos.getByRole("checkbox", { name: "Ver costos", exact: true })).toBeChecked();
  expect(escrituras).toHaveLength(1);
});

test("membresía inactiva permite revocar pero no alta ni editar alcance", async ({ page }) => {
  const { escrituras } = await escenario(page, { activo: false });
  const permisos = await abrirUsuario(page);
  await expect(permisos.getByRole("checkbox", { name: "Ver costos", exact: true })).toBeDisabled();
  await permisos.getByText("Alcance de Ver gastos", { exact: true }).click();
  await expect(permisos.getByRole("checkbox", { name: "Todas las áreas e institucional · Ver gastos", exact: true })).toBeDisabled();
  await permisos.getByRole("checkbox", { name: "Ver gastos", exact: true }).uncheck();
  await permisos.getByRole("button", { name: "Guardar permisos financieros", exact: true }).click();
  await expect.poll(() => escrituras.length).toBe(1);
  expect(escrituras[0].body.concesiones.map((c) => c.accion)).toEqual(["registrar_gastos"]);
});

test("administración retira el acceso antiguo y conserva permisos dentro de editar usuario", async ({ page }) => {
  await escenario(page);
  await page.goto("/administracion");
  await expect(page.getByRole("button", { name: "Permisos financieros", exact: true })).toHaveCount(0);
  await abrirUsuario(page);
  await expect(page.getByRole("dialog", { name: "Permisos financieros", exact: true })).toHaveCount(0);
  await expect(page.getByRole("checkbox", { name: "Ver gastos", exact: true })).toBeChecked();
  await expect(page.getByRole("button", { name: "Otorgar permisos", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Guardar permisos financieros", exact: true })).toBeVisible();
});

test("nombre apellido y nueva contraseña comparten fila y se apilan en móvil", async ({ page }, testInfo) => {
  await escenario(page);
  await abrirUsuario(page);
  const campos = [page.getByLabel("Nombre *", { exact: true }), page.getByLabel("Apellido", { exact: true }), page.getByLabel("Nueva contraseña", { exact: false })];
  const cajas = await Promise.all(campos.map((campo) => campo.boundingBox()));
  expect(Math.max(...cajas.map((c) => c.y)) - Math.min(...cajas.map((c) => c.y))).toBeLessThan(2);
  expect(cajas[0].x).toBeLessThan(cajas[1].x);
  expect(cajas[1].x).toBeLessThan(cajas[2].x);
  await page.screenshot({ path: testInfo.outputPath("datos-personales-alineados.png"), animations: "disabled" });
  await page.setViewportSize({ width: 390, height: 900 });
  const movil = await Promise.all(campos.map((campo) => campo.boundingBox()));
  expect(movil[0].y).toBeLessThan(movil[1].y);
  expect(movil[1].y).toBeLessThan(movil[2].y);
});

test("marcar y desplegar un permiso no desplaza tarjetas de otras columnas", async ({ page }, testInfo) => {
  const { escrituras } = await escenario(page);
  const permisos = await abrirUsuario(page);
  const grilla = permisos.getByRole("group", { name: "Acciones financieras de esta membresía" });
  await expect(grilla.locator(":scope > div")).toHaveCount(3);
  const posicionesAjenas = () => grilla.evaluate((el) => {
    const origen = el.getBoundingClientRect();
    return [...el.children].filter((col) => col.tagName === "DIV").slice(1)
      .flatMap((col) => [...col.children].map((tarjeta) => {
        const r = tarjeta.getBoundingClientRect();
        return [Math.round(r.x - origen.x), Math.round(r.y - origen.y)];
      }));
  });
  const antes = await posicionesAjenas();
  await permisos.getByLabel("Ver costos", { exact: true }).check();
  expect(await posicionesAjenas()).toEqual(antes);
  await permisos.getByText("Alcance de Ver costos", { exact: true }).click();
  expect(await posicionesAjenas()).toEqual(antes);
  await permisos.getByText("Alcance de Ver costos", { exact: true }).click();
  expect(await posicionesAjenas()).toEqual(antes);
  await grilla.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("columnas-independientes.png"), animations: "disabled" });
  expect(escrituras).toHaveLength(0);
});

test("respuesta incierta impide repetir guardado sin verificar primero", async ({ page }) => {
  const { db, escrituras } = await escenario(page);
  const permisos = await abrirUsuario(page);
  await permisos.getByRole("checkbox", { name: "Registrar gastos", exact: true }).uncheck();
  db.sinRespuesta = true;
  await permisos.getByRole("button", { name: "Guardar permisos financieros", exact: true }).click();
  await expect(permisos.getByRole("alert")).toContainText("No se pudo confirmar");
  await expect(permisos.getByRole("button", { name: "Guardar permisos financieros", exact: true })).toBeDisabled();
  expect(escrituras).toHaveLength(1);
});
