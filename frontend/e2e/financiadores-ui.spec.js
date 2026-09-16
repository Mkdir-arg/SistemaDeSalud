import { expect, test } from "@playwright/test";

const lista = (results) => ({ count: results.length, next: null, previous: null, results });
const organizaciones = [{ id: 21, nombre: "Mutual del Río", tipo: "mutual", rol: "admin" }, { id: 22, nombre: "Obra Social del Norte", tipo: "obra_social", rol: "admin" }];
const catalogo = [{ id: 3, codigo: "RX", nombre: "Radiografía", categoria: "Imágenes" }];
async function escenario(page, { rol = "admin", falloPlanes = false, mixto = false } = {}) {
  const peticiones = [];
  const escrituras = [];
  const planes = { 21: [{ id: 31, codigo: "BAS", nombre: "Plan Río", activo: true }], 22: [{ id: 32, codigo: "NOR", nombre: "Plan Norte", activo: true }] };
  const padron = [{ id: 45, numero: "00025", documento: "00123456", nombre: "Persona Ficticia", plan: 31, desde: "2026-01-01", vigente: true, finalizado_en: null, motivo_finalizacion: "" }];
  await page.addInitScript(() => { localStorage.setItem("cauce.access", "token-ficticio-mock"); localStorage.setItem("cauce.refresh", "refresh-ficticio-mock"); });
  if (mixto) await page.addInitScript(() => localStorage.setItem("cauce.institucion", JSON.stringify({ id: 2, nombre: "Hospital de prueba" })));
  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url()); const path = url.pathname.replace(/^\/api/, "");
    if (!url.pathname.startsWith("/api/")) return route.continue();
    peticiones.push(path);
    if (path === "/usuarios/me/") return route.fulfill({ json: { id: 9, email: "persona@example.test", nombre_completo: "Operador de prueba", capacidades_por_institucion: mixto ? { 2: ["casos_operar", "historia_clinica"] } : {}, roles_por_institucion: mixto ? { 2: ["medico"] } : {}, financiadores: organizaciones.map((o) => ({ ...o, rol })) } });
    if (path === "/instituciones/") return route.fulfill({ json: lista([]) });
    if (path === "/financiadores/") return route.fulfill({ json: lista(organizaciones.map((o) => ({ ...o, rol }))) });
    const match = path.match(/^\/financiadores\/(\d+)\/(.+)\/$/);
    if (match) {
      const [, id, recurso] = match;
      if (req.method() === "POST") {
        const body = req.postDataJSON(); escrituras.push({ path, body });
        if (recurso === "planes") { const plan = { id: 99, ...body }; planes[id].push(plan); return route.fulfill({ json: plan }); }
        if (recurso === "editar-plan") { const plan = planes[id].find((p) => p.id === body.plan); Object.assign(plan, { nombre: body.nombre, activo: body.activo }); return route.fulfill({ json: plan }); }
        if (recurso === "finalizar-afiliacion") Object.assign(padron[0], { vigente: false, finalizado_en: "2026-09-15T12:00:00Z", motivo_finalizacion: body.motivo });
        if (recurso === "reactivar-afiliacion") Object.assign(padron[0], { vigente: true, finalizado_en: null, motivo_finalizacion: "", plan: body.plan });
        return route.fulfill({ json: { id: 99, ...body } });
      }
      if (recurso === "planes") return route.fulfill(falloPlanes ? { status: 403, json: { detail: "Acceso revocado" } } : { json: lista(planes[id]) });
      if (recurso === "catalogo") return route.fulfill({ json: lista(catalogo) });
      if (recurso === "resumen") return route.fulfill({ json: { discrepancias: 0 } });
      if (recurso === "padron") return route.fulfill({ json: lista(padron) });
      return route.fulfill({ json: lista([]) });
    }
    return route.fulfill({ status: 404, json: { detail: `Ruta inesperada: ${path}` } });
  });
  return { peticiones, escrituras, planes, padron };
}

test("un financiador sin hospital entra a su portal y configura un plan", async ({ page }) => {
  const { escrituras, peticiones } = await escenario(page);
  await page.goto("/");
  await expect(page).toHaveURL(/\/financiadores$/);
  await expect(page.getByRole("heading", { name: "Planes", exact: true, level: 1 })).toBeVisible();
  await page.getByRole("button", { name: "Nuevo plan", exact: true }).click();
  await page.getByLabel("Código del plan").fill("PLUS");
  await page.getByLabel("Nombre del plan").fill("Plan Plus");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(page.getByRole("cell", { name: "Plan Plus", exact: true })).toBeVisible();
  expect(escrituras).toEqual([{ path: "/financiadores/21/planes/", body: { codigo: "PLUS", nombre: "Plan Plus" } }]);
  expect(peticiones.some((p) => p.includes("casos") || p.includes("historia") || p.includes("concesiones-financieras"))).toBe(false);
});

test("usa el sidebar compartido sin consultar ni mostrar módulos del hospital", async ({ page }) => {
  const { peticiones } = await escenario(page, { mixto: true });
  await page.goto("/financiadores");
  const menu = page.getByRole("navigation", { name: "Menú del financiador" });
  await expect(menu.getByRole("link", { name: "Planes", exact: true })).toHaveAttribute("aria-current", "page");
  await expect(menu.getByRole("link", { name: "Volver al hospital" })).toHaveAttribute("href", "/inicio");
  await expect(menu.getByRole("link", { name: "Historia clínica" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Notificaciones", exact: true })).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: /Buscar paciente/ })).toHaveCount(0);
  await expect(page.getByRole("cell", { name: "Plan Río", exact: true })).toBeVisible();
  expect(peticiones.every((p) => p === "/usuarios/me/" || p.startsWith("/financiadores/"))).toBe(true);
  await page.getByRole("button", { name: "Colapsar menú", exact: true }).click();
  await expect(page.getByRole("button", { name: "Expandir menú", exact: true })).toBeVisible();
  await menu.getByRole("link", { name: "Aranceles", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Aranceles" })).toBeVisible();
  await expect(menu.getByRole("link", { name: "Aranceles", exact: true })).toHaveAttribute("aria-current", "page");
});

test("organización y sección se conservan al recargar y al volver", async ({ page }) => {
  await escenario(page);
  await page.goto("/financiadores");
  await page.getByRole("combobox", { name: "Financiador", exact: true }).selectOption("22");
  await page.getByRole("link", { name: "Aranceles", exact: true }).click();
  await expect(page).toHaveURL(/\/financiadores\/aranceles\?financiador=22$/);
  await page.reload();
  await expect(page.getByRole("combobox", { name: "Financiador", exact: true })).toHaveValue("22");
  await expect(page.getByRole("heading", { level: 1, name: "Aranceles" })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("cell", { name: "Plan Norte", exact: true })).toBeVisible();
});

test("auditor no abre usuarios por ruta directa y una organización ajena no se sustituye", async ({ page }) => {
  const { peticiones } = await escenario(page, { rol: "auditor" });
  await page.goto("/financiadores/usuarios");
  await expect(page).toHaveURL(/\/financiadores$/);
  await expect(page.getByRole("cell", { name: "Plan Río", exact: true })).toBeVisible();
  expect(peticiones.some((p) => /financiadores\/\d+\/usuarios\//.test(p))).toBe(false);
  await page.goto("/financiadores?financiador=999");
  await expect(page.getByText("No tenés acceso al financiador seleccionado", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Nuevo plan" })).toHaveCount(0);
  await expect(page.getByRole("cell", { name: "Plan Río", exact: true })).toHaveCount(0);
});

test("menú móvil navega, se cierra y conserva el tema de Cauce", async ({ page }) => {
  await escenario(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/financiadores");
  await page.getByRole("button", { name: "Abrir menú", exact: true }).click();
  await page.getByRole("navigation", { name: "Menú del financiador" }).getByRole("link", { name: "Aranceles", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Aranceles" })).toBeVisible();
  await expect.poll(() => page.locator("aside").evaluate((el) => el.getBoundingClientRect().right)).toBeLessThanOrEqual(0);
  await page.getByRole("button", { name: "Cambiar a tema oscuro" }).click();
  await expect(page.getByRole("button", { name: "Cambiar a tema claro" })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test("configura porcentaje y cupo calendario sobre una prestación común", async ({ page }) => {
  const { escrituras } = await escenario(page);
  await page.goto("/financiadores");
  await page.getByRole("link", { name: "Cobertura", exact: true }).click();
  await page.getByRole("button", { name: "Nueva regla de cobertura" }).click();
  await page.getByRole("combobox", { name: "Plan", exact: true }).selectOption("31");
  await page.getByRole("combobox", { name: "Prestación", exact: true }).selectOption("3");
  await page.getByLabel("Porcentaje cubierto").fill("80");
  await page.getByLabel("Cupo por prestación").fill("6");
  await page.getByLabel("Vigente desde").fill("2027-01-01");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Registro guardado.");
  expect(escrituras[0].body).toMatchObject({ plan: 31, prestacion: 3, porcentaje: "80", cupo: 6, periodo: "anio", vigente_desde: "2027-01-01" });
});

test("cambiar organización descarta formularios y respuestas de la anterior", async ({ page }) => {
  await escenario(page);
  let liberar;
  const espera = new Promise((resolve) => { liberar = resolve; });
  await page.route("**/api/financiadores/21/planes/**", async (route) => { await espera; await route.fulfill({ json: lista([{ id: 31, codigo: "SECRETO", nombre: "Plan privado Río" }]) }); });
  await page.goto("/financiadores");
  await page.getByRole("combobox", { name: "Financiador", exact: true }).selectOption("22");
  await expect(page.getByRole("cell", { name: "Plan Norte", exact: true })).toBeVisible();
  liberar();
  await expect(page.getByText("Plan privado Río", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Nuevo plan", exact: true }).click();
  await page.getByLabel("Nombre del plan").fill("Borrador de Norte");
  await page.getByRole("button", { name: "Cancelar", exact: true }).click();
  await page.getByRole("combobox", { name: "Financiador", exact: true }).selectOption("21");
  await page.getByRole("button", { name: "Nuevo plan", exact: true }).click();
  await expect(page.getByLabel("Nombre del plan")).toHaveValue("");
});

test("auditor consulta sin acciones de escritura", async ({ page }) => {
  const { escrituras } = await escenario(page, { rol: "auditor" });
  await page.goto("/financiadores");
  await expect(page.getByText("Sólo lectura", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Nuevo plan" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Usuarios" })).toHaveCount(0);
  await page.getByRole("link", { name: "Padrón", exact: true }).click();
  await expect(page.getByRole("cell", { name: "00123456", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Importar Excel" })).toHaveCount(0);
  expect(escrituras).toEqual([]);
});

test("error de permisos se muestra como error y no como lista vacía", async ({ page }) => {
  await escenario(page, { falloPlanes: true });
  await page.goto("/financiadores");
  await expect(page.getByRole("alert").first()).toContainText("Acceso revocado");
  await expect(page.getByText("Todavía no hay registros", { exact: true })).toHaveCount(0);
});

test("preview importa bloques válidos y conserva detalle rechazado", async ({ page }) => {
  await escenario(page);
  let confirmaciones = 0;
  const lote = { id: 7, tipo: "consumos", estado: "preview", resumen: { total: 3, valida: 2, rechazada: 1, aplicada: 0, revision: 0, error_tecnico: 0 }, filas: [{ fila: 4, estado: "rechazada", errores: ["Afiliado no encontrado."] }] };
  await page.route("**/api/financiadores/21/importaciones/**", async (route) => route.fulfill({ json: route.request().method() === "POST" ? lote : lista([lote]) }));
  await page.route("**/api/financiadores/21/confirmar-importacion/", async (route) => {
    confirmaciones += 1;
    expect(route.request().postDataJSON()).toEqual({ importacion: 7, revisiones_duplicados: {} });
    await route.fulfill({ json: { ...lote, estado: confirmaciones === 2 ? "aplicada" : "preview", resumen: { ...lote.resumen, valida: 2 - confirmaciones, aplicada: confirmaciones } } });
  });
  await page.goto("/financiadores");
  await page.getByRole("link", { name: "Consumos externos" }).click();
  await page.getByRole("button", { name: "Importar Excel" }).click();
  await page.getByLabel("Archivo Excel (.xlsx)").setInputFiles({ name: "consumos.xlsx", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", buffer: Buffer.from("archivo-ficticio-API-interceptada") });
  await page.getByRole("button", { name: "Revisar archivo" }).click();
  await expect(page.getByRole("region", { name: "Resumen de importación" })).toContainText("Afiliado no encontrado.");
  expect(confirmaciones).toBe(0);
  await page.getByRole("button", { name: "Importar 2 filas válidas" }).click();
  await expect(page.getByRole("status")).toContainText("Se aplicaron 2 filas");
  expect(confirmaciones).toBe(2);
  await expect(page.getByRole("button", { name: "Descargar filas rechazadas" })).toBeVisible();
});

test("importación recuperable permite revisar duplicados con motivo individual", async ({ page }) => {
  await escenario(page);
  let body;
  const lote = { id: 8, tipo: "consumos", estado: "preview", resumen: { total: 1, valida: 0, rechazada: 0, aplicada: 0, revision: 1, error_tecnico: 0 }, filas: [{ fila: 2, estado: "revision", errores: ["Posible duplicado."] }] };
  await page.route("**/api/financiadores/21/importaciones/**", (route) => route.fulfill({ json: lista([lote]) }));
  await page.route("**/api/financiadores/21/confirmar-importacion/", (route) => { body = route.request().postDataJSON(); return route.fulfill({ json: { ...lote, estado: "aplicada", resumen: { ...lote.resumen, aplicada: 1, revision: 0 }, filas: [] } }); });
  await page.goto("/financiadores");
  await page.getByRole("link", { name: "Consumos externos" }).click();
  await page.getByRole("button", { name: "Importar Excel" }).click();
  await page.getByRole("button", { name: "Importación 8" }).click();
  await expect(page.getByRole("button", { name: "Importar 0 filas válidas" })).toBeDisabled();
  await page.getByLabel("Motivo de revisión de fila 2").fill("Verificado: fueron dos prestaciones distintas.");
  await page.getByRole("button", { name: "Importar filas válidas y revisadas" }).click();
  await expect(page.getByRole("status")).toContainText("Se aplicó 1 fila");
  expect(body.revisiones_duplicados).toEqual({ 2: "Verificado: fueron dos prestaciones distintas." });
});

test("portal se adapta a móvil y conserva contexto del financiador", async ({ page }, testInfo) => {
  await escenario(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/financiadores");
  await expect(page.getByRole("cell", { name: "Plan Río", exact: true })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("portal-movil.png"), fullPage: true });
});

test("activación exige contraseñas coincidentes y confirma sólo tras respuesta", async ({ page }) => {
  let enviado;
  await page.route("**/api/financiadores/activar/", (route) => { enviado = route.request().postDataJSON(); return route.fulfill({ json: { detail: "Cuenta activada" } }); });
  await page.goto("/financiadores/activar?uid=usuario-ficticio&token=token-ficticio");
  await page.getByLabel("Nueva contraseña").fill("ClaveFicticiaLarga9");
  await page.getByLabel("Confirmar contraseña").fill("OtraClaveFicticia9");
  await page.getByRole("button", { name: "Activar acceso" }).click();
  await expect(page.getByRole("alert")).toHaveText("Las contraseñas no coinciden.");
  expect(enviado).toBeUndefined();
  await page.getByLabel("Confirmar contraseña").fill("ClaveFicticiaLarga9");
  await page.getByRole("button", { name: "Activar acceso" }).click();
  await expect(page.getByRole("status")).toContainText("Tu contraseña se guardó");
  expect(enviado).toMatchObject({ uid: "usuario-ficticio", token: "token-ficticio" });
});

async function hospital(page, { liberar = true, resolver = true, completar = false, recuperables = [] } = {}) {
  const escritos = [];
  const inst = { id: 2, nombre: "Hospital de prueba" };
  const opciones = { configuracion: { activo: true, dias_reserva_antigua: 7 }, permisos: { configurar: true, operar: true, registrar_aceptacion: true, resolver: true }, catalogo, prestaciones: [{ id: 7, nombre: "Radiografía", comun: 3 }], casos: [{ id: 41, titulo: "Caso de prueba", documento: "00123456" }], convenios: [], financiadores: organizaciones };
  const reservas = [{ id: 71, caso: 41, fecha: "2026-01-01", cantidad: 1, estado: "reservada", antigua: true, prestacion_nombre: "Radiografía", puede_liberar: liberar, puede_resolver: false }, { id: 72, caso: 41, fecha: "2026-01-01", cantidad: 1, estado: "realizada", prestacion_nombre: "Consulta", puede_liberar: false, puede_resolver: resolver, distribucion: { estado: "pendiente", importe_paciente: "200.00", importe_financiador: "800.00" } }];
  if (completar) reservas.push({ id: 73, caso: 41, fecha: "2026-01-01", cantidad: 1, estado: "realizada", prestacion_nombre: "Laboratorio", puede_completar: true, puede_completar_arancel: true, distribucion: { estado: "arancel_pendiente", importe_paciente: null } });
  await page.addInitScript((i) => { localStorage.setItem("cauce.access", "token-ficticio-mock"); localStorage.setItem("cauce.institucion", JSON.stringify(i)); }, inst);
  await page.route("**/api/**", (route) => {
    const req = route.request(); const url = new URL(req.url()); const path = url.pathname;
    if (!path.startsWith("/api/")) return route.continue();
    if (path === "/api/usuarios/me/") return route.fulfill({ json: { id: 9, email: "hospital@example.test", capacidades_por_institucion: { 2: ["casos_operar", "config_institucional"] }, roles_por_institucion: { 2: ["medico"] }, financiadores: [] } });
    if (req.method() === "POST") {
      const body = req.postDataJSON(); escritos.push({ path, body });
      if (path === "/api/coberturas/evaluar/") return route.fulfill({ json: { ...body, firma: "firma-ficticia", nombre_prestacion: "Radiografía", estado: "parcial", motivo: "Cobertura según plan y cupo disponible", porcentaje: "80.00", cubiertas: 1, importe_total: "1000.00", importe_financiador: "800.00", importe_paciente: "200.00" } });
      return route.fulfill({ json: { id: 75, ...body } });
    }
    if (path === "/api/coberturas/opciones/") return route.fulfill({ json: opciones });
    if (path === "/api/coberturas/") return route.fulfill({ json: lista(reservas) });
    if (path === "/api/coberturas/recuperables/") return route.fulfill({ json: recuperables });
    if (path === "/api/concesiones-financieras/mias/") return route.fulfill({ json: { superusuario: false, concesiones: [{ institucion: 2, accion: "ver_dinero", todas_las_areas: true, areas: [] }] } });
    if (path === "/api/notificaciones/resumen/") return route.fulfill({ json: { no_leidas: 0, items: [] } });
    return route.fulfill({ json: lista([]) });
  });
  return { escritos };
}

test("hospital sólo libera al confirmar no realización y motivo", async ({ page }) => {
  const { escritos } = await hospital(page);
  await page.goto("/finanzas/coberturas");
  await page.getByRole("button", { name: "Revisar reserva", exact: true }).click();
  const dialogo = page.getByRole("dialog");
  await expect(dialogo.getByRole("button", { name: "Confirmar liberación" })).toBeDisabled();
  await dialogo.getByRole("checkbox", { name: "Verifiqué que esta prestación no se realizó" }).check();
  await dialogo.getByLabel("Motivo", { exact: true }).fill("Se verificó con el área que el paciente no asistió.");
  await dialogo.getByRole("button", { name: "Confirmar liberación" }).click();
  await expect(page.getByRole("status")).toContainText("Reserva liberada");
  expect(escritos).toEqual([{ path: "/api/coberturas/71/liberar/", body: { no_realizada: true, motivo: "Se verificó con el área que el paciente no asistió." } }]);
});

test("hospital conserva importe aceptado por prestación y descarta evaluación al cambiar cantidad", async ({ page }) => {
  const { escritos } = await hospital(page);
  await page.goto("/finanzas/coberturas");
  await page.getByRole("tab", { name: "Evaluar una prestación" }).click();
  await page.getByRole("combobox", { name: "Caso", exact: true }).selectOption("41");
  await page.getByRole("combobox", { name: "Prestación", exact: true }).selectOption("7");
  await page.getByRole("button", { name: "Consultar cobertura" }).click();
  const resultado = page.getByRole("region", { name: "Evaluación de cobertura" });
  await expect(resultado).toContainText("ARS 200,00");
  await resultado.getByRole("checkbox").check();
  await page.getByLabel("Cantidad", { exact: true }).fill("2");
  await expect(resultado).toHaveCount(0);
  await page.getByRole("button", { name: "Consultar cobertura" }).click();
  await expect(resultado.getByRole("checkbox")).not.toBeChecked();
  await resultado.getByRole("checkbox").check();
  await resultado.getByRole("button", { name: "Confirmar reserva de cobertura" }).click();
  await expect(page.getByRole("status")).toContainText("Cobertura reservada");
  expect(escritos.find((item) => item.path.endsWith("/reservar/")).body).toMatchObject({ caso: 41, prestacion: 7, cantidad: 2, acepta: true, firma: "firma-ficticia" });
});

test("rechazar asunción guarda decisión sin afirmar que el saldo esté pagado", async ({ page }) => {
  const { escritos } = await hospital(page);
  await page.goto("/finanzas/coberturas");
  await page.getByRole("button", { name: "Resolver saldo" }).click();
  await page.getByRole("combobox", { name: "Decisión", exact: true }).selectOption("rechazar");
  await page.getByLabel("Motivo", { exact: true }).fill("El hospital solicita mantener el saldo pendiente.");
  await page.getByRole("button", { name: "Registrar decisión" }).click();
  await expect(page.getByRole("status")).toContainText("Decisión administrativa registrada");
  expect(escritos[0].body).toMatchObject({ decision: "rechazar", importe: "200.00" });
  await expect(page.getByText("Pendiente de resolución administrativa", { exact: true })).toBeVisible();
});

test("sin permisos por reserva no se ofrecen liberación ni resolución", async ({ page }) => {
  await hospital(page, { liberar: false, resolver: false });
  await page.goto("/finanzas/coberturas");
  await expect(page.getByText("Antigua · revisar realización")).toBeVisible();
  await expect(page.getByRole("button", { name: "Revisar reserva" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Resolver saldo" })).toHaveCount(0);
});

test("completa un arancel pendiente con motivo sin cambiar afiliación", async ({ page }) => {
  const { escritos } = await hospital(page, { completar: true });
  await page.goto("/finanzas/coberturas");
  await page.getByRole("button", { name: "Completar datos" }).click();
  await page.getByLabel("Arancel por unidad (ARS)").fill("123.45");
  await page.getByLabel("Motivo de resolución").fill("Se confirmó el arancel acordado para esta atención.");
  await page.getByRole("button", { name: "Completar evaluación", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Evaluación completada");
  expect(escritos[0]).toEqual({ path: "/api/coberturas/73/completar/", body: { arancel: "123.45", motivo: "Se confirmó el arancel acordado para esta atención." } });
});

test("revisión de contexto admite afiliación pendiente sin inventar afiliado", async ({ page }) => {
  const { escritos } = await hospital(page, { recuperables: [{ id: 81, caso: 41, fecha: "2026-01-01", contexto_pendiente: true, afiliaciones: [], prestaciones: [{ id: 7, nombre: "Radiografía" }] }] });
  await page.goto("/finanzas/coberturas");
  await page.getByRole("button", { name: "Revisar contexto" }).click();
  await expect(page.getByRole("combobox", { name: "Afiliación de la atención", exact: true })).toHaveValue("");
  await page.getByRole("checkbox", { name: "Radiografía", exact: true }).check();
  await page.getByLabel("Motivo de la revisión").fill("Prestación realizada; afiliación aún por verificar.");
  await page.getByRole("button", { name: "Registrar contexto verificado" }).click();
  await expect(page.getByRole("status")).toContainText("Contexto revisado");
  expect(escritos[0].body).toMatchObject({ hecho: 81, afiliacion: null, prestaciones: [7] });
});

test("multipart y descarga reintentan con token renovado sin cambiar el lote", async ({ page }) => {
  await escenario(page);
  let importaciones = 0;
  let refresh = 0;
  const claves = [];
  const lote = { id: 9, tipo: "consumos", estado: "preview", resumen: { total: 1, valida: 1, aplicada: 0, rechazada: 0 }, filas: [] };
  await page.route("**/api/auth/token/refresh/", (route) => { refresh += 1; return route.fulfill({ json: { access: "access-renovado-ficticio", refresh: "refresh-renovado-ficticio" } }); });
  await page.route("**/api/financiadores/21/importaciones/**", (route) => {
    if (route.request().method() === "GET") return route.fulfill({ json: lista([]) });
    importaciones += 1;
    claves.push(route.request().postData()?.match(/name="clave"\r\n\r\n([^\r]+)/)?.[1]);
    return route.fulfill(importaciones === 1 ? { status: 401, json: { detail: "Access expirado" } } : { json: lote });
  });
  let descargas = 0;
  await page.route("**/api/financiadores/21/plantilla/**", (route) => {
    descargas += 1;
    if (descargas === 1) return route.fulfill({ status: 401, json: { detail: "Access expirado" } });
    return route.fulfill({ contentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers: { "Content-Disposition": 'attachment; filename="plantilla.xlsx"' }, body: "xlsx-ficticio" });
  });
  await page.goto("/financiadores");
  await page.getByRole("link", { name: "Consumos externos" }).click();
  await page.getByRole("button", { name: "Importar Excel" }).click();
  await page.getByLabel("Archivo Excel (.xlsx)").setInputFiles({ name: "consumos.xlsx", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", buffer: Buffer.from("ficticio") });
  await page.getByRole("button", { name: "Revisar archivo" }).click();
  await expect(page.getByRole("button", { name: "Importar 1 fila válida" })).toBeVisible();
  expect(importaciones).toBe(2);
  expect(claves[0]).toBeTruthy();
  expect(claves[0]).toBe(claves[1]);
  const descargado = page.waitForEvent("download");
  await page.getByRole("button", { name: "Descargar plantilla" }).click();
  expect((await descargado).suggestedFilename()).toBe("plantilla.xlsx");
  expect(descargas).toBe(2);
  expect(refresh).toBe(2);
});

test("financiador consulta actividad hospitalaria y discrepancias sin editarla", async ({ page }) => {
  await escenario(page);
  await page.route("**/api/financiadores/21/actividad/**", (route) => route.fulfill({ json: lista([{ id: 91, fecha: "2026-09-15", hospital: "Hospital Ficticio", prestacion: "Consulta", numero: "00025", documento: "00123456", cantidad: 1, cubiertas: 1, estado: "realizada", discrepancia: true, importe_financiador: "80.00", estado_cobro: "resuelta" }]) }));
  await page.goto("/financiadores");
  await page.getByRole("link", { name: "Actividad en hospitales", exact: true }).click();
  const region = page.getByRole("region", { name: "Actividad en hospitales", exact: true });
  await expect(region.getByRole("cell", { name: "Hospital Ficticio", exact: true })).toBeVisible();
  await expect(region.getByRole("cell", { name: "ARS 80,00", exact: true })).toBeVisible();
  await expect(region.getByText("Discrepancia", { exact: true })).toBeVisible();
  await expect(region.getByRole("button", { name: /Guardar|Crear|Registrar|Corregir/ })).toHaveCount(0);
});

for (const rol of ["admin", "operador", "auditor"]) {
  test(`${rol} consulta arancel general y acordado sin acciones de escritura`, async ({ page }) => {
    const { escrituras } = await escenario(page, { rol });
    const base = { convenio: 11, hospital: "Hospital Ficticio", codigo: "RX", arancel_general: "100.00", vigente_desde: "2026-09-01", fecha_consulta: "2026-09-15", cobrar: true, estado: "vigente", retorno_arancel_general: false };
    await page.route("**/api/financiadores/21/aranceles/**", (route) => route.fulfill({ json: lista([
      { ...base, id: 1, prestacion: "Radiografía", arancel: "100.00", origen_arancel: "general_hospital" },
      { ...base, id: 2, prestacion: "Consulta", arancel: "80.00", origen_arancel: "acordado_financiador" },
    ]) }));
    await page.goto("/financiadores");
    await page.getByRole("link", { name: "Aranceles", exact: true }).click();
    const region = page.getByRole("region", { name: "Aranceles", exact: true });
    await expect(region.getByRole("row").filter({ hasText: "Radiografía" })).toContainText("General del hospital");
    const acordado = region.getByRole("row").filter({ has: page.getByRole("cell", { name: "Consulta", exact: true }) });
    await expect(acordado).toContainText("ARS 100,00");
    await expect(acordado).toContainText("ARS 80,00");
    await expect(acordado).toContainText("Acordado con el financiador");
    await expect(acordado).toContainText("01/09/2026");
    await expect(acordado).toContainText("15/09/2026");
    await expect(region).toContainText("La cobertura y el copago dependen del plan, el cupo y la prestación");
    await expect(region.getByRole("button")).toHaveText(["Buscar", "Anterior", "Siguiente"]);
    expect(escrituras).toEqual([]);
  });
}

test("aranceles distingue datos pendientes de gratuidad y busca desde la primera página", async ({ page }) => {
  await escenario(page);
  const consultas = [];
  const base = { convenio: 11, hospital: "Hospital Ficticio", codigo: "RX", arancel_general: null, arancel: null, vigente_desde: null, fecha_consulta: "2026-09-15", cobrar: true, origen_arancel: "general_hospital", retorno_arancel_general: false };
  await page.route("**/api/financiadores/21/aranceles/**", (route) => {
    const params = new URL(route.request().url()).searchParams;
    consultas.push({ page: params.get("page"), search: params.get("search") });
    if (params.get("search")) return route.fulfill({ json: lista([]) });
    if (params.get("page") === "2") return route.fulfill({ json: lista([{ ...base, id: 4, prestacion: "Control", arancel_general: "90.00", arancel: "90.00", estado: "vigente", retorno_arancel_general: true }]) });
    return route.fulfill({ json: { count: 4, next: "?page=2", previous: null, results: [
      { ...base, id: 1, prestacion: "Laboratorio", estado: "arancel_pendiente" },
      { ...base, id: 2, prestacion: "Ecografía", estado: "politica_pendiente" },
      { ...base, id: 3, prestacion: "Vacunación", estado: "sin_cobro", cobrar: false, arancel: "0.00" },
    ] } });
  });
  await page.goto("/financiadores");
  await page.getByRole("link", { name: "Aranceles", exact: true }).click();
  const region = page.getByRole("region", { name: "Aranceles", exact: true });
  const pendiente = region.getByRole("row").filter({ hasText: "Laboratorio" });
  await expect(pendiente).toContainText("Arancel pendiente");
  await expect(pendiente).toContainText("Importe no disponible");
  await expect(pendiente).not.toContainText("ARS 0,00");
  await expect(region.getByRole("row").filter({ hasText: "Ecografía" })).toContainText("Política de cobro pendiente");
  await expect(region.getByRole("row").filter({ hasText: "Vacunación" })).toContainText("Sin cobro");
  await region.getByRole("button", { name: "Siguiente", exact: true }).click();
  await expect(region.getByRole("row").filter({ hasText: "Control" })).toContainText("General del hospital · excepción finalizada");
  await region.getByLabel("Buscar por hospital o prestación").fill("Hospital sin convenio");
  await region.getByRole("button", { name: "Buscar", exact: true }).click();
  await expect(region).toContainText("No hay resultados para esta búsqueda");
  expect(consultas.at(-1)).toEqual({ page: "1", search: "Hospital sin convenio" });
});

test("corregir documento conserva el identificador del afiliado", async ({ page }) => {
  const { escrituras } = await escenario(page);
  await page.goto("/financiadores");
  await page.getByRole("link", { name: "Padrón", exact: true }).click();
  await page.getByRole("button", { name: "Corregir identidad" }).click();
  await expect(page.getByLabel("Número de afiliado correcto")).toHaveValue("00025");
  await page.getByLabel("Documento correcto").fill("00123457");
  await page.getByLabel("Motivo de corrección").fill("Corrección de un dígito contrastada con el documento.");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Se conservó el consumo del afiliado");
  expect(escrituras[0]).toMatchObject({ path: "/financiadores/21/corregir-identidad/", body: { afiliado: 45, numero: "00025", documento: "00123457" } });
});

test("administrador modifica rol y desactiva acceso sin enviar contraseña", async ({ page }) => {
  const { escrituras } = await escenario(page);
  await page.route("**/api/financiadores/21/usuarios/**", (route) => route.request().method() === "GET" ? route.fulfill({ json: lista([{ id: 71, email: "segundo@example.test", nombre: "Usuario Ficticio", rol: "operador", activo: true }]) }) : route.fallback());
  await page.goto("/financiadores");
  await page.getByRole("link", { name: "Usuarios", exact: true }).click();
  await page.getByRole("button", { name: "Cambiar acceso" }).click();
  await page.getByRole("combobox", { name: "Rol", exact: true }).selectOption("auditor");
  await page.getByRole("checkbox", { name: "Acceso activo a este financiador" }).uncheck();
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("Acceso actualizado.");
  expect(escrituras[0].body).toEqual({ email: "segundo@example.test", nombre: "Usuario Ficticio", rol: "auditor", activo: false });
});

test("permite retomar un lote fuera de la primera página", async ({ page }) => {
  await escenario(page);
  const lote = { id: 2, tipo: "consumos", estado: "preview", resumen: { total: 1, valida: 1, aplicada: 0, rechazada: 0 }, filas: [] };
  await page.route("**/api/financiadores/21/importaciones/**", (route) => {
    const pagina = new URL(route.request().url()).searchParams.get("page");
    return route.fulfill({ json: pagina === "2" ? lista([lote]) : { count: 26, next: "?page=2", previous: null, results: [{ ...lote, id: 40, estado: "aplicada" }] } });
  });
  await page.goto("/financiadores");
  await page.getByRole("link", { name: "Consumos externos" }).click();
  await page.getByRole("button", { name: "Importar Excel" }).click();
  const dialogo = page.getByRole("dialog");
  await dialogo.getByRole("button", { name: "Siguiente", exact: true }).click();
  await dialogo.getByRole("button", { name: "Importación 2" }).click();
  await expect(dialogo.getByRole("button", { name: "Importar 1 fila válida" })).toBeVisible();
});

test("desactivar un plan conserva su código y lo retira de nuevas afiliaciones", async ({ page }) => {
  const { escrituras } = await escenario(page);
  await page.goto("/financiadores");
  await page.getByRole("button", { name: "Editar plan" }).click();
  const dialogo = page.getByRole("dialog");
  await expect(dialogo).toContainText("las asignaciones existentes se mantienen");
  await expect(dialogo.getByLabel("Código del plan")).toHaveCount(0);
  await dialogo.getByLabel("Nombre del plan").fill("Plan Río anterior");
  await dialogo.getByRole("checkbox", { name: "Plan activo para nuevas asignaciones" }).uncheck();
  await dialogo.getByRole("button", { name: "Guardar plan" }).click();
  expect(escrituras).toEqual([]);
  await dialogo.getByLabel("Motivo", { exact: true }).fill("El plan deja de recibir nuevas afiliaciones.");
  await dialogo.getByRole("button", { name: "Guardar plan" }).click();
  await expect(page.getByRole("row").filter({ hasText: "Plan Río anterior" })).toContainText("Inactivo");
  expect(escrituras[0]).toEqual({ path: "/financiadores/21/editar-plan/", body: { plan: 31, nombre: "Plan Río anterior", activo: false, motivo: "El plan deja de recibir nuevas afiliaciones." } });
  await page.getByRole("link", { name: "Padrón", exact: true }).click();
  await page.getByRole("button", { name: "Registrar afiliación", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "Plan", exact: true }).locator("option")).toHaveText(["Sin plan"]);
});

test("finalizar afiliación exige motivo y permite reactivarla sin reiniciar cupos", async ({ page }) => {
  const { escrituras, planes } = await escenario(page, { rol: "operador" });
  planes[21].push({ id: 33, codigo: "ANT", nombre: "Plan inactivo", activo: false });
  await page.goto("/financiadores/padron");
  await page.getByRole("button", { name: "Finalizar afiliación" }).click();
  let dialogo = page.getByRole("dialog");
  await expect(dialogo).toContainText("No genera deuda automática al paciente");
  await dialogo.getByRole("button", { name: "Cancelar" }).click();
  expect(escrituras).toEqual([]);
  await page.getByRole("button", { name: "Finalizar afiliación" }).click();
  await dialogo.getByLabel("Motivo", { exact: true }).fill("Baja solicitada por cambio de financiador.");
  await dialogo.getByRole("button", { name: "Confirmar finalización" }).click();
  await expect(page.getByRole("cell").filter({ hasText: "Finalizada" })).toContainText("Baja solicitada");
  await page.getByRole("button", { name: "Reactivar afiliación" }).click();
  dialogo = page.getByRole("dialog");
  await expect(dialogo).toContainText("el cupo no se reinicia");
  await expect(dialogo.getByRole("combobox", { name: "Plan", exact: true }).locator("option")).toHaveText(["Sin plan", "Plan Río"]);
  await dialogo.getByRole("combobox", { name: "Plan", exact: true }).selectOption("31");
  await dialogo.getByLabel("Motivo", { exact: true }).fill("Reingreso confirmado por el afiliado.");
  await dialogo.getByRole("button", { name: "Confirmar reactivación" }).click();
  await expect(page.getByRole("cell", { name: "Vigente", exact: true })).toBeVisible();
  expect(escrituras.map((item) => item.path)).toEqual(["/financiadores/21/finalizar-afiliacion/", "/financiadores/21/reactivar-afiliacion/"]);
  expect(escrituras[1].body).toEqual({ afiliado: 45, plan: 31, motivo: "Reingreso confirmado por el afiliado." });
});

test("el error de finalización conserva el motivo y no afirma un cambio de vigencia", async ({ page }) => {
  await escenario(page);
  await page.route("**/api/financiadores/21/finalizar-afiliacion/", (route) => route.fulfill({ status: 403, json: { detail: "El acceso fue revocado." } }));
  await page.goto("/financiadores/padron");
  await page.getByRole("button", { name: "Finalizar afiliación" }).click();
  const dialogo = page.getByRole("dialog");
  await dialogo.getByLabel("Motivo", { exact: true }).fill("Solicitud verificada.");
  await dialogo.getByRole("button", { name: "Confirmar finalización" }).click();
  await expect(dialogo.getByRole("alert")).toContainText("El acceso fue revocado");
  await expect(dialogo.getByLabel("Motivo", { exact: true })).toHaveValue("Solicitud verificada.");
  await expect(page.getByRole("status")).toHaveCount(0);
});

test("auditor consulta planes y padrón sin administrar su vigencia", async ({ page }) => {
  await escenario(page, { rol: "auditor" });
  await page.goto("/financiadores");
  await expect(page.getByRole("cell", { name: "Plan Río", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Editar plan" })).toHaveCount(0);
  await page.getByRole("link", { name: "Padrón", exact: true }).click();
  await expect(page.getByRole("cell", { name: "Persona Ficticia", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Finalizar afiliación|Reactivar afiliación/ })).toHaveCount(0);
});

test("convenios conserva el histórico y sólo acepta o rechaza la propuesta de contraparte", async ({ page }) => {
  const { escrituras } = await escenario(page);
  const convenios = [
    { id: 11, institucion_nombre: "Hospital activo", estado: "activo", propuesto_por: "hospital", aceptado_en: "2026-01-01T12:00:00Z" },
    { id: 12, institucion_nombre: "Hospital proponente", estado: "propuesto", propuesto_por: "hospital" },
    { id: 13, institucion_nombre: "Hospital invitado", estado: "propuesto", propuesto_por: "financiador" },
    { id: 14, institucion_nombre: "Hospital anterior", estado: "finalizado", cerrado_en: "2026-08-31T12:00:00Z", motivo_cierre: "Convenio anterior vencido." },
  ];
  await page.route("**/api/financiadores/21/convenios/**", (route) => route.fulfill({ json: lista(convenios) }));
  await page.goto("/financiadores/convenios");
  await expect(page.getByRole("row").filter({ hasText: "Hospital invitado" }).getByRole("button")).toHaveCount(0);
  await expect(page.getByRole("row").filter({ hasText: "Hospital anterior" })).toContainText("Convenio anterior vencido.");
  await page.getByRole("row").filter({ hasText: "Hospital activo" }).getByRole("button", { name: "Cerrar convenio" }).click();
  let dialogo = page.getByRole("dialog");
  await expect(dialogo).toContainText("Se conservan reservas y cargos anteriores");
  await dialogo.getByLabel("Motivo", { exact: true }).fill("Finalización acordada con el hospital.");
  await dialogo.getByRole("button", { name: "Confirmar cierre" }).click();
  await expect(page.getByRole("status")).toContainText("Se conservaron los registros anteriores");
  await page.getByRole("row").filter({ hasText: "Hospital proponente" }).getByRole("button", { name: "Rechazar propuesta" }).click();
  dialogo = page.getByRole("dialog");
  await dialogo.getByLabel("Motivo", { exact: true }).fill("Las condiciones requieren otra propuesta.");
  await dialogo.getByRole("button", { name: "Confirmar rechazo" }).click();
  await expect(dialogo).toHaveCount(0);
  expect(escrituras).toEqual([
    { path: "/financiadores/21/cerrar-convenio/", body: { convenio: 11, motivo: "Finalización acordada con el hospital." } },
    { path: "/financiadores/21/rechazar-convenio/", body: { convenio: 12, motivo: "Las condiciones requieren otra propuesta." } },
  ]);
});

test("actividad identifica el acceso mínimo a una operación histórica pendiente", async ({ page }) => {
  await escenario(page, { rol: "auditor" });
  await page.route("**/api/financiadores/21/actividad/**", (route) => route.fulfill({ json: lista([{ id: 91, fecha: "2026-09-15", hospital: "Hospital anterior", prestacion: "Consulta", numero: "00025", documento: "00123456", cantidad: 1, cubiertas: 1, estado: "realizada", importe_financiador: "80.00", estado_cobro: "pendiente", acceso: "pendiente_historico" }]) }));
  await page.goto("/financiadores/actividad");
  const region = page.getByRole("region", { name: "Actividad en hospitales", exact: true });
  await expect(region).toContainText("sólo se muestran operaciones históricas pendientes de resolución");
  await expect(region.getByRole("cell", { name: "Histórico pendiente", exact: true })).toBeVisible();
  await expect(region.getByRole("link", { name: /historia/i })).toHaveCount(0);
});

test("hospital cierra o rechaza convenios con motivo y muestra los estados finales", async ({ page }) => {
  const { escritos } = await hospital(page);
  await page.route("**/api/coberturas/opciones/**", (route) => route.fulfill({ json: { configuracion: { activo: true }, permisos: { configurar: true }, convenios: [
    { id: 11, financiador_nombre: "Mutual activa", estado: "activo", propuesto_por: "hospital" },
    { id: 12, financiador_nombre: "Mutual proponente", estado: "propuesto", propuesto_por: "financiador" },
    { id: 13, financiador_nombre: "Mutual anterior", estado: "rechazado", cerrado_en: "2026-08-31T12:00:00Z", motivo_cierre: "Propuesta rechazada por condiciones." },
  ] } }));
  await page.goto("/finanzas/coberturas");
  await page.getByRole("tab", { name: "Configuración" }).click();
  await expect(page.getByText("Mutual anterior · Rechazado", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Cerrar convenio" }).click();
  await page.getByRole("dialog").getByLabel("Motivo", { exact: true }).fill("Cierre confirmado con la mutual.");
  await page.getByRole("button", { name: "Confirmar cierre" }).click();
  await expect(page.getByRole("status")).toContainText("Convenio actualizado");
  await page.getByRole("button", { name: "Rechazar propuesta" }).click();
  await page.getByRole("dialog").getByLabel("Motivo", { exact: true }).fill("El hospital no acepta las condiciones propuestas.");
  await page.getByRole("button", { name: "Confirmar rechazo" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  expect(escritos.map((item) => item.path)).toEqual(["/api/coberturas/cerrar-convenio/", "/api/coberturas/rechazar-convenio/"]);
  expect(escritos[1].body).toEqual({ convenio: 12, motivo: "El hospital no acepta las condiciones propuestas." });
});

test("auditoría del hospital filtra las consultas de financiadores y explica su alcance", async ({ page }) => {
  await hospital(page);
  const filtros = [];
  await page.route("**/api/usuarios/me/", (route) => route.fulfill({ json: { id: 9, email: "hospital@example.test", capacidades_por_institucion: { 2: ["auditoria"] }, roles_por_institucion: { 2: ["director"] } } }));
  await page.route("**/api/accesos-clinicos/**", (route) => {
    filtros.push(new URL(route.request().url()).searchParams.get("tipo"));
    return route.fulfill({ json: lista([{ id: 1, momento: "2026-09-15T12:00:00Z", usuario: 19, usuario_nombre: "Operadora de mutual", usuario_email: "mutual@example.test", paciente: "Persona Ficticia", documento: "00123456", ciudadano: 4, institucion: 2, institucion_nombre: "Hospital de prueba", tipo: "financiador", tipo_display: "Consulta de un financiador", recurso: "financiadores-actividad", resultados: 1, detalle: "financiador=21 afiliado=45 acceso=pendiente_historico" }]) });
  });
  await page.goto("/accesos");
  await expect(page.getByRole("heading", { name: "Registro de accesos" })).toBeVisible();
  await expect(page.getByText(/Consultar esa actividad no da acceso a la historia/)).toBeVisible();
  await page.getByRole("combobox").filter({ has: page.locator('option[value="financiador"]') }).selectOption("financiador");
  await expect(page).toHaveURL(/tipo=financiador/);
  await expect(page.getByText("actividad hospitalaria del afiliado", { exact: true })).toBeVisible();
  await expect(page.getByText(/1 resultado.*financiador 21.*histórico pendiente/)).toBeVisible();
  expect(filtros).toContain("financiador");
});
