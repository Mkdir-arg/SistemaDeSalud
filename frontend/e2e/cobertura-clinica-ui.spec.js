import { expect, test } from "@playwright/test";

const lista = (results) => ({ count: results.length, next: null, previous: null, results });
const afiliacion = { id: 40, caso: 41, flujo_titulo: "Consulta programada", estado: "verificada", financiador_nombre: "Mutual del Río", plan_nombre: "Plan Familiar", numero: "00025", declaracion: "", motivo: "Credencial verificada al ingresar", usuario_nombre: "Personal de admisión", creado: "2026-09-16T12:00:00Z" };
const evaluacion = { firma: "firma-ficticia-actual", nombre_prestacion: "Consulta", estado: "parcial", motivo: "Cobertura según plan y cupo disponible", porcentaje: "80.00", cupo: 6, periodo: "anio", disponibles: 4, cubiertas: 1, cantidad: 1, fecha: "2026-09-16", importe_total: "10000.00", importe_financiador: "8000.00", importe_paciente: "2000.00" };

async function circuito(page, opciones = {}) {
  const institucion = { id: 2, nombre: "Hospital de prueba" };
  const estado = {
    caso: { id: 41, ciudadano: 5, ciudadano_nombre: "Paciente de Prueba", institucion: 2, version: 3, flujo_titulo: "Consulta programada", estado: "en_evaluacion", estado_display: "En evaluación", nodo_actual: 10, nodo_tipo: "form", paso_actual: "Admisión", area_actual: 4, area_nombre: "Consultorios", responsables: [], puede_tomar: true, puede_supervisar: false, prioridad: "normal", prioridad_display: "Normal", creado: "2026-09-16T12:00:00Z", actualizado: "2026-09-16T12:01:00Z" },
    afiliacion: opciones.sinAfiliacion ? null : { ...afiliacion },
    reservas: opciones.reservada ? [{ id: 71, prestacion: 7, prestacion_nombre: "Consulta", estado: "reservada", fecha: "2026-09-16", cantidad: 1, evaluacion: { ...evaluacion }, aceptacion: { importe: "2000.00", fecha: "2026-09-16T12:00:00Z" }, discrepancia: false, distribucion: null }] : [],
  };
  const escrituras = [];
  const lecturas = [];
  const contexto = () => ({ nodo: estado.caso.nodo_actual, actualizado: estado.caso.actualizado });
  await page.addInitScript((i) => {
    sessionStorage.setItem("salud.access", "access-solo-pruebas-interceptadas");
    localStorage.setItem("salud.institucion", JSON.stringify(i));
  }, institucion);
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const path = url.pathname.replace(/^\/api/, "");
    if (request.method() === "POST") {
      const body = request.postDataJSON();
      escrituras.push({ path, body });
      if (path === "/casos/41/cobertura-evaluar/") return route.fulfill({ json: { ...evaluacion, ...(opciones.evaluacion || {}) } });
      if (path === "/casos/41/cobertura-confirmar/") {
        if (opciones.fallaPrimerConfirmar && escrituras.filter((e) => e.path === path).length === 1) return route.fulfill({ status: 503, json: { detail: "No se pudo confirmar la respuesta. Reintentá la misma operación." } });
        for (const reserva of estado.reservas) reserva.estado = "liberada";
        const reserva = { id: 72, prestacion: 7, prestacion_nombre: "Consulta", estado: "reservada", fecha: "2026-09-16", cantidad: 1, evaluacion: { ...evaluacion }, aceptacion: body.acepta ? { importe: "2000.00", fecha: "2026-09-16T12:02:00Z" } : {}, discrepancia: false, distribucion: null };
        estado.reservas.unshift(reserva);
        return route.fulfill({ json: reserva });
      }
      if (path === "/casos/41/cobertura-afiliacion/") {
        estado.afiliacion = { ...afiliacion, id: 42, motivo: body.motivo };
        return route.fulfill({ json: estado.afiliacion });
      }
      if (path === "/casos/41/avanzar/") {
        estado.caso.nodo_actual = 11;
        estado.caso.paso_actual = "Registro de atención";
        estado.caso.actualizado = "2026-09-16T12:05:00Z";
        return route.fulfill({ json: estado.caso });
      }
      return route.fulfill({ status: 404, json: { detail: `Escritura inesperada: ${path}` } });
    }
    lecturas.push(path + url.search);
    if (path === "/usuarios/me/") return route.fulfill({ json: { id: 9, email: "personal@example.test", nombre_completo: "Personal de prueba", capacidades_por_institucion: { 2: ["casos_operar", "historia_clinica", "padron_admision"] }, roles_por_institucion: { 2: ["medico"] }, financiadores: [] } });
    if (path === "/instituciones/") return route.fulfill({ json: lista([institucion]) });
    if (path === "/notificaciones/resumen/") return route.fulfill({ json: { no_leidas: 0, items: [] } });
    if (path === "/concesiones-financieras/mias/") return route.fulfill({ json: { superusuario: false, concesiones: [] } });
    if (path === "/casos/41/") return route.fulfill({ json: estado.caso });
    if (path === "/casos/41/cobertura/") return route.fulfill(opciones.errorCobertura ? { status: opciones.errorCobertura, json: { detail: "No se pudo consultar la cobertura del caso" } } : { json: { activo: true, contexto: contexto(), puede_operar: !opciones.soloLectura, afiliacion: estado.afiliacion, afiliados: [{ id: 25, financiador_nombre: "Mutual del Río", plan_nombre: "Plan Familiar", numero: "00025" }], prestaciones: [{ id: 7, nombre: "Consulta", codigo: "CONS", puede_aceptar: !opciones.sinPermisoAceptacion }], reservas: estado.reservas, historial_afiliaciones: estado.afiliacion ? [estado.afiliacion] : [], historial_truncado: false } });
    if (path === "/nodos/10/" || path === "/nodos/11/") return route.fulfill({ json: { formulario: null } });
    if (path === "/ciudadanos/5/") return route.fulfill({ json: { id: 5, nombre: "Paciente", apellido: "de Prueba", documento: "00123456", consentimiento: true } });
    if (path === "/ciudadanos/5/cobertura/") {
      if (opciones.errorHistorial) return route.fulfill({ status: 403, json: { detail: "Sin permiso para consultar la cobertura" } });
      const segunda = url.searchParams.get("page") === "2";
      return route.fulfill({ json: { count: 2, next: segunda ? null : "http://ejemplo.test/api/ciudadanos/5/cobertura/?page=2", previous: segunda ? "http://ejemplo.test/api/ciudadanos/5/cobertura/?page=1" : null, results: [{ ...afiliacion, id: segunda ? 39 : 40, motivo: segunda ? "Selección anterior del caso" : afiliacion.motivo }] } });
    }
    return route.fulfill({ json: lista([]) });
  });
  return { escrituras, lecturas, estado };
}

test("el caso consulta sin reservar y registra aceptación por prestación e importe", async ({ page }) => {
  const { escrituras } = await circuito(page);
  await page.goto("/casos/41");
  await page.getByRole("button", { name: "Consultar cobertura", exact: true }).click();
  const importe = page.getByRole("region", { name: "Importe de Consulta" });
  await expect(importe.getByText("ARS 2.000,00", { exact: true })).toBeVisible();
  const aceptar = importe.getByRole("checkbox", { name: "El paciente aceptó expresamente ARS 2.000,00 por Consulta (1 unidad).", exact: true });
  await expect(aceptar).not.toBeChecked();
  expect(escrituras.map((e) => e.path)).toEqual(["/casos/41/cobertura-evaluar/"]);
  await aceptar.check();
  await importe.getByRole("button", { name: "Confirmar reserva de cobertura" }).click();
  await expect(page.getByRole("status")).toContainText("Cobertura confirmada");
  expect(escrituras.at(-1).body).toMatchObject({ prestacion: 7, firma: evaluacion.firma, acepta: true, contexto: { nodo: 10, actualizado: "2026-09-16T12:01:00Z" } });
  expect(escrituras.at(-1).body.clave).toMatch(/^[a-f0-9-]{36}$/);
  await expect(page.getByText(/Aceptación registrada: ARS 2.000,00/)).toBeVisible();
});

for (const estado of ["pendiente", "aprobada"]) {
  test(`la evaluación separa cobertura económica y autorización ${estado} sin afirmar deuda emitida`, async ({ page }) => {
    await circuito(page, { evaluacion: { requiere_autorizacion: true, autorizacion: 91, estado_autorizacion: estado, autorizacion_disponible: estado === "aprobada" ? 2 : 0 } });
    await page.goto("/casos/41");
    await page.getByRole("button", { name: "Consultar cobertura", exact: true }).click();
    const permiso = page.getByRole("region", { name: "Autorización de esta evaluación", exact: true });
    await expect(permiso.getByText(estado === "aprobada" ? "Aprobada" : "Pendiente", { exact: true })).toBeVisible();
    // La advertencia dejó de ocupar un renglón: vive en el «(?)» del bloque. Se
    // sigue verificando —es la que evita leer la evaluación como deuda emitida—,
    // pero hay que abrirla.
    await permiso.getByRole("button", { name: "Ver ayuda", exact: true }).click();
    await expect(permiso).toContainText("Los importes de esta evaluación todavía no son cuentas por cobrar");
    await page.keyboard.press("Escape");
    await expect(page.getByRole("button", { name: "Confirmar reserva de cobertura", exact: true })).toBeEnabled();
    if (estado === "pendiente") await expect(permiso).toContainText("la parte del financiador queda pendiente de autorización");
    else await expect(permiso).toContainText("Cantidad autorizada disponible: 2");
  });
}

test("no elige automáticamente la única afiliación disponible", async ({ page }) => {
  const { escrituras } = await circuito(page, { sinAfiliacion: true });
  await page.goto("/casos/41");
  await expect(page.getByRole("combobox", { name: "Tipo de afiliación", exact: true })).toHaveValue("");
  await page.getByRole("combobox", { name: "Tipo de afiliación", exact: true }).selectOption("verificada");
  await expect(page.getByRole("combobox", { name: "Afiliación del paciente", exact: true })).toHaveValue("");
  await expect(page.getByRole("button", { name: "Registrar afiliación", exact: true })).toBeDisabled();
  await page.getByRole("combobox", { name: "Afiliación del paciente", exact: true }).selectOption("25");
  await page.getByLabel("Motivo de la selección", { exact: true }).fill("Credencial presentada en admisión");
  await page.getByRole("button", { name: "Registrar afiliación", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Afiliación registrada");
  expect(escrituras[0].body).toMatchObject({ afiliado: 25, motivo: "Credencial presentada en admisión" });
});

test("renovar requiere verificar no realización y una nueva aceptación independiente", async ({ page }) => {
  const { escrituras } = await circuito(page, { reservada: true });
  await page.goto("/casos/41");
  await expect(page.getByRole("button", { name: "Corregir afiliación" })).toBeDisabled();
  await page.getByRole("button", { name: "Revisar importe" }).click();
  const importe = page.getByRole("region", { name: "Importe de Consulta" });
  const confirmar = importe.getByRole("button", { name: "Actualizar reserva de cobertura" });
  await expect(confirmar).toBeDisabled();
  await expect(importe.getByRole("checkbox", { name: /El paciente aceptó/ })).not.toBeChecked();
  await importe.getByRole("checkbox", { name: /El paciente aceptó/ }).check();
  await expect(confirmar).toBeDisabled();
  await importe.getByRole("checkbox", { name: "Confirmo que esta prestación todavía no se realizó" }).check();
  await confirmar.click();
  await expect(page.getByRole("status")).toContainText("Cobertura confirmada");
  expect(escrituras.at(-1).body).toMatchObject({ acepta: true, no_realizada: true });
  await expect(page.getByText("Liberada", { exact: true })).toBeVisible();
});

test("reintentar una confirmación conserva el UUID y el consentimiento de esa solicitud", async ({ page }) => {
  const { escrituras } = await circuito(page, { fallaPrimerConfirmar: true });
  await page.goto("/casos/41");
  await page.getByRole("button", { name: "Consultar cobertura", exact: true }).click();
  await page.getByRole("checkbox", { name: /El paciente aceptó/ }).check();
  await page.getByRole("button", { name: "Confirmar reserva de cobertura" }).click();
  await expect(page.getByRole("alert")).toContainText("Reintentá la misma operación");
  await page.getByRole("button", { name: "Confirmar reserva de cobertura" }).click();
  await expect(page.getByRole("status")).toContainText("Cobertura confirmada");
  const confirmaciones = escrituras.filter((e) => e.path.endsWith("cobertura-confirmar/"));
  expect(confirmaciones).toHaveLength(2);
  expect(confirmaciones[0].body).toEqual(confirmaciones[1].body);
});

test("sin permiso de aceptación puede reservar dejando el saldo pendiente", async ({ page }) => {
  const { escrituras } = await circuito(page, { sinPermisoAceptacion: true });
  await page.goto("/casos/41");
  await page.getByRole("button", { name: "Consultar cobertura", exact: true }).click();
  await expect(page.getByRole("checkbox", { name: /El paciente aceptó/ })).toHaveCount(0);
  await expect(page.getByText(/No se asigna automáticamente como deuda/)).toBeVisible();
  await page.getByRole("button", { name: "Confirmar reserva de cobertura" }).click();
  await expect(page.getByRole("status")).toContainText("Cobertura confirmada");
  expect(escrituras.at(-1).body.acepta).toBe(false);
});

for (const codigo of [403, 503]) {
  test(`un error ${codigo} de cobertura no bloquea completar el paso clínico`, async ({ page }) => {
    const { escrituras } = await circuito(page, { errorCobertura: codigo });
    await page.goto("/casos/41");
    await expect(page.getByRole("alert")).toContainText(codigo === 403 ? "No tenés permiso" : "No se pudo consultar");
    await expect(page.getByRole("button", { name: "Completar y avanzar" })).toBeEnabled();
    await page.getByRole("button", { name: "Completar y avanzar" }).click();
    await expect.poll(() => escrituras.some((e) => e.path === "/casos/41/avanzar/")).toBe(true);
  });
}

test("consulta sin permiso de operación conserva registros y oculta escrituras", async ({ page }) => {
  const { escrituras } = await circuito(page, { soloLectura: true, reservada: true });
  await page.goto("/casos/41");
  await expect(page.getByText(/La cobertura se muestra en modo de consulta/)).toBeVisible();
  await expect(page.getByText(/Aceptación registrada: ARS 2.000,00/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Corregir afiliación|Revisar importe|Consultar cobertura/ })).toHaveCount(0);
  expect(escrituras).toEqual([]);
});

test("avanzar el caso descarta la cotización y aceptación del paso anterior", async ({ page }) => {
  await circuito(page);
  await page.goto("/casos/41");
  await page.getByRole("button", { name: "Consultar cobertura", exact: true }).click();
  await page.getByRole("checkbox", { name: /El paciente aceptó/ }).check();
  await page.getByRole("button", { name: "Completar y avanzar" }).click();
  await expect(page.getByRole("region", { name: "Importe de Consulta" })).toHaveCount(0);
  await page.getByRole("button", { name: "Consultar cobertura", exact: true }).click();
  await expect(page.getByRole("checkbox", { name: /El paciente aceptó/ })).not.toBeChecked();
});

test("el historial del paciente pagina sin ofrecer enlaces a casos ni importes", async ({ page }) => {
  const { lecturas, escrituras } = await circuito(page);
  await page.goto("/historia/5?tab=cobertura");
  const historial = page.locator('[aria-label="Historial de cobertura del paciente"]');
  await expect(historial.getByText("Credencial verificada al ingresar", { exact: true })).toBeVisible();
  await expect(historial.getByRole("button", { name: "Anterior" })).toBeDisabled();
  await historial.getByRole("button", { name: "Siguiente" }).click();
  await expect(historial.getByText("Selección anterior del caso", { exact: true })).toBeVisible();
  await expect(historial.getByRole("button", { name: "Siguiente" })).toBeDisabled();
  await expect(historial.getByRole("link")).toHaveCount(0);
  await expect(historial.getByText(/ARS /)).toHaveCount(0);
  expect(lecturas).toContain("/ciudadanos/5/cobertura/?page=2&page_size=10");
  expect(escrituras).toEqual([]);
});

test("un historial 403 no se presenta como vacío", async ({ page }) => {
  await circuito(page, { errorHistorial: true });
  await page.goto("/historia/5?tab=cobertura");
  await expect(page.getByRole("alert")).toContainText("No tenés permiso para ver esto");
  await expect(page.getByText("No hay afiliaciones registradas en los casos visibles", { exact: true })).toHaveCount(0);
});

test("cobertura e historial conservan el layout móvil I-Core Salud sin desbordar", async ({ page }, testInfo) => {
  await circuito(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/casos/41");
  await page.getByRole("button", { name: "Consultar cobertura", exact: true }).click();
  await expect(page.getByRole("region", { name: "Importe de Consulta" })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  const panel = page.locator('[aria-label="Cobertura del caso"]');
  await expect.poll(() => panel.evaluate((el) => el.getBoundingClientRect().left)).toBeGreaterThanOrEqual(0);
  await expect.poll(() => panel.evaluate((el) => el.getBoundingClientRect().right)).toBeLessThanOrEqual(390);
  await panel.screenshot({ path: testInfo.outputPath("cobertura-caso-movil.png") });
  await page.goto("/historia/5?tab=cobertura");
  await expect(page.getByRole("heading", { name: "Cobertura por caso" })).toBeVisible();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("historial-cobertura-movil.png"), fullPage: true });
});
