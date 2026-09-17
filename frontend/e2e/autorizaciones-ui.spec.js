import { expect, test } from "@playwright/test";

const lista = (results, extra = {}) => ({ count: results.length, next: null, previous: null, results, ...extra });
const organizaciones = [{ id: 21, nombre: "Mutual del Río", rol: "admin" }, { id: 22, nombre: "Mutual Norte", rol: "admin" }];
const intento = "11111111-1111-4111-8111-111111111111";
const base = {
  id: 91, financiador: 21, financiador_nombre: "Mutual del Río", institucion: 2, institucion_nombre: "Hospital Ficticio",
  caso: 41, prestacion: 7, prestacion_nombre: "Consulta", afiliado_nombre: "Persona Ficticia", afiliado_numero: "00025", documento: "00123456",
  estado: "pendiente", revision: 1, cantidad_solicitada: 2, cantidad_aprobada: 0, cantidades: { disponible: 0, comprometida: 0, consumida: 0 },
  intento, justificacion: "Solicitud para continuidad del tratamiento", urgente: false, creado: "2026-09-16T12:00:00Z", plazo_respuesta: "2026-09-18T12:00:00Z",
  puede_resolver: true, puede_reenviar: false, puede_anular: false, historial: [{ id: 1, estado: "pendiente", motivo: "Solicitud inicial", usuario_nombre: "Admisión", creado: "2026-09-16T12:00:00Z" }],
};

async function escenario(page, opciones = {}) {
  const estado = {
    solicitud: { ...base, ...opciones.solicitud },
    fallo: opciones.fallo || "", listaVacia: false,
    contexto: { caso: 41, intento, prestaciones: [{ id: 7, nombre: "Consulta", codigo: "CONS" }], puede_solicitar: true, motivo: "", ...opciones.contexto },
    usuario: { id: 50, email: "operador@example.test", nombre: "Operador", rol: "auditor", activo: true, resuelve_autorizaciones: false },
    convenio: { id: 17, institucion_nombre: "Hospital Ficticio", estado: "activo", propuesto_por: "hospital", plazo_autorizacion_horas: null },
    version: { id: 3, flujo: 4, etiqueta: "v1", estado: opciones.publicada ? "publicada" : "borrador", tipo_circuito: opciones.publicada ? "programado" : "no_definido", nodos: [{ id: 10, tipo: "atencion", titulo: "Atención", x: 200, y: 200, config: {}, grupos: [] }], conexiones: [] },
  };
  const escrituras = [];
  const lecturas = [];
  await page.addInitScript((hospital) => {
    localStorage.setItem("salud.access", "token-ficticio-interceptado");
    if (hospital) localStorage.setItem("salud.institucion", JSON.stringify({ id: 2, nombre: "Hospital Ficticio" }));
  }, !!opciones.hospital);
  await page.route("**/api/**", async (route) => {
    const r = route.request(); const url = new URL(r.url());
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const path = url.pathname.replace(/^\/api/, "");
    if (["POST", "PATCH"].includes(r.method())) {
      const body = r.postDataJSON(); escrituras.push({ path, body, params: Object.fromEntries(url.searchParams) });
      if (path.includes("autorizaciones-cobertura")) {
        if (estado.fallo === "transitorio") { estado.fallo = ""; return route.fulfill({ status: 503, json: { detail: "No se pudo confirmar. Reintentá la misma operación." } }); }
        if (estado.fallo === "revision") {
          estado.fallo = ""; Object.assign(estado.solicitud, { revision: 2, estado: "rechazada", puede_resolver: false });
          return route.fulfill({ status: 400, json: { detail: "La solicitud cambió. Actualizá antes de resolver." } });
        }
        if (path.endsWith("/resolver/")) Object.assign(estado.solicitud, { estado: body.decision === "observar" ? "observada" : body.decision === "aprobar" ? "aprobada" : "rechazada", revision: 2, puede_resolver: false, motivo_resolucion: body.motivo, ...body });
        if (path.endsWith("/reenviar/")) Object.assign(estado.solicitud, { estado: "pendiente", revision: 2, puede_reenviar: false, justificacion: body.justificacion });
        estado.listaVacia = false;
        return route.fulfill({ status: 201, json: estado.solicitud });
      }
      if (path === "/financiadores/21/usuarios/") Object.assign(estado.usuario, body);
      if (path === "/financiadores/21/plazo-autorizacion/") Object.assign(estado.convenio, body);
      if (path === "/casos/41/continuar-autorizacion/") estado.contexto.espera_autorizacion = { ...estado.contexto.espera_autorizacion, estado: "supervisada" };
      if (path === "/versiones-flujo/3/") { Object.assign(estado.version, body); return route.fulfill({ json: estado.version }); }
      if (path === "/nodos/10/") { Object.assign(estado.version.nodos[0], body); return route.fulfill({ json: estado.version.nodos[0] }); }
      return route.fulfill({ json: { id: 100, ...body } });
    }
    lecturas.push({ path, params: Object.fromEntries(url.searchParams) });
    if (path === "/usuarios/me/") return route.fulfill({ json: { id: 9, is_superuser: !!opciones.editor, email: "personal@example.test", nombre_completo: "Personal de prueba", capacidades_por_institucion: opciones.hospital ? { 2: ["casos_operar", "historia_clinica", "padron_admision"] } : {}, roles_por_institucion: opciones.hospital ? { 2: ["medico"] } : {}, financiadores: organizaciones.map((o) => ({ ...o, rol: opciones.rol || "admin" })) } });
    if (path === "/instituciones/") return route.fulfill({ json: lista(opciones.hospital ? [{ id: 2, nombre: "Hospital Ficticio" }] : []) });
    if (path === "/financiadores/") return route.fulfill({ json: lista(organizaciones.map((o) => ({ ...o, rol: opciones.rol || "admin" }))) });
    if (path === "/financiadores/21/usuarios/") return route.fulfill({ json: lista([estado.usuario]) });
    if (path === "/financiadores/21/convenios/") return route.fulfill({ json: lista([estado.convenio]) });
    if (/\/financiadores\/\d+\/planes\//.test(path)) return route.fulfill({ json: lista([{ id: 31, nombre: "Plan Río", codigo: "BAS", activo: true }]) });
    if (/\/financiadores\/\d+\/catalogo\//.test(path)) return route.fulfill({ json: lista([{ id: 3, nombre: "Consulta", codigo: "CONS", categoria: "Consultas" }]) });
    if (/\/financiadores\/\d+\/resumen\//.test(path)) return route.fulfill({ json: { discrepancias: 0 } });
    if (path === "/autorizaciones-cobertura/contexto/") return route.fulfill({ json: estado.contexto });
    if (path === "/autorizaciones-cobertura/") {
      const segunda = url.searchParams.get("page") === "2";
      return route.fulfill({ json: lista(url.searchParams.get("financiador") === "22" || estado.listaVacia ? [] : [{ ...estado.solicitud, id: segunda ? 92 : 91 }], { ...(opciones.paginada ? { count: 30, next: segunda ? null : "?page=2" } : {}), opciones: { instituciones: [{ id: 2, nombre: "Hospital Ficticio" }] } }) });
    }
    if (/^\/autorizaciones-cobertura\/\d+\/$/.test(path)) {
      if (path === "/autorizaciones-cobertura/90/" && opciones.antecedenteOculto) return route.fulfill({ status: 404, json: { detail: "La solicitud anterior no está disponible con tu acceso actual." } });
      if (path === "/autorizaciones-cobertura/90/") return route.fulfill({ json: { ...estado.solicitud, id: 90, anterior: null, estado: "rechazada", puede_resolver: false } });
      return route.fulfill({ json: estado.solicitud });
    }
    if (path === "/casos/41/") return route.fulfill({ json: { id: 41, ciudadano: 5, ciudadano_nombre: "Persona Ficticia", institucion: 2, version: 3, flujo_titulo: "Consulta programada", estado: "en_evaluacion", estado_display: "En evaluación", nodo_actual: 10, nodo_tipo: "atencion", paso_actual: "Atención", responsables: [], puede_tomar: true, puede_supervisar: true, prioridad: "normal", prioridad_display: "Normal", creado: "2026-09-16T12:00:00Z", actualizado: "2026-09-16T12:01:00Z" } });
    if (path === "/casos/41/cobertura/") return route.fulfill({ json: { activo: true, puede_operar: false, contexto: { nodo: 10 }, afiliacion: { estado: "verificada", financiador_nombre: "Mutual del Río", numero: "00025" }, prestaciones: [], reservas: [] } });
    if (path === "/nodos/10/") return route.fulfill({ json: { formulario: null } });
    if (path === "/ciudadanos/5/") return route.fulfill({ json: { id: 5, nombre: "Persona", apellido: "Ficticia", consentimiento: true } });
    if (path === "/flujos/4/") return route.fulfill({ json: { id: 4, titulo: "Circuito de prueba", institucion: 2, versiones: [{ id: 3, etiqueta: "v1" }] } });
    if (path === "/versiones-flujo/3/") return route.fulfill({ json: estado.version });
    if (path === "/coberturas/opciones/") return route.fulfill({ json: { configuracion: { activo: true }, permisos: { seguimiento: true, configurar: false, operar: false } } });
    if (path === "/coberturas/") return route.fulfill({ json: lista([{ id: 81, caso: 41, prestacion_nombre: "Consulta", cantidad: 1, fecha: "2026-09-16", estado: "realizada", puede_resolver: true, distribucion: { estado: "autorizacion_pendiente", importe_financiador: "8000.00", importe_paciente: "2000.00", obligacion_paciente: 18, obligacion_financiador: null } }]) });
    if (path === "/notificaciones/resumen/") return route.fulfill({ json: { no_leidas: 0, items: [] } });
    if (path === "/concesiones-financieras/mias/") return route.fulfill({ json: { superusuario: false, concesiones: opciones.finanzas ? ["ver_dinero", "resolver_cobertura"].map((accion) => ({ institucion: 2, accion, todas_las_areas: true, permite_sensibles: true, areas: [] })) : [] } });
    return route.fulfill({ json: lista([]) });
  });
  return { estado, escrituras, lecturas };
}

test("bandeja en sidebar conserva filtros y paginación y descarta otro financiador", async ({ page }) => {
  const { lecturas } = await escenario(page, { paginada: true });
  await page.goto("/financiadores/autorizaciones?financiador=21&page=2");
  await expect(page.getByRole("navigation", { name: "Menú del financiador" }).getByRole("link", { name: "Autorizaciones", exact: true })).toHaveAttribute("aria-current", "page");
  await expect(page.getByText("30 solicitudes · Página 2")).toBeVisible();
  await page.getByRole("combobox", { name: "Estado de autorización", exact: true }).selectOption("pendiente");
  await page.getByRole("combobox", { name: "Hospital solicitante", exact: true }).selectOption("2");
  await page.getByRole("combobox", { name: "Urgencia", exact: true }).selectOption("true");
  await page.getByLabel("Solicitada desde", { exact: true }).fill("2026-09-01");
  await page.getByRole("button", { name: "Aplicar filtros", exact: true }).click();
  await expect(page.getByText("30 solicitudes · Página 1")).toBeVisible();
  expect(lecturas.filter((r) => r.path === "/autorizaciones-cobertura/").at(-1).params).toMatchObject({ financiador: "21", estado: "pendiente", hospital: "2", urgente: "true", desde: "2026-09-01", page: "1" });
  await page.reload();
  await expect(page.getByRole("combobox", { name: "Urgencia", exact: true })).toHaveValue("true");
  await page.getByRole("combobox", { name: "Financiador", exact: true }).selectOption("22");
  await expect(page.getByText("No hay solicitudes para estos filtros", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Ver solicitud 91", exact: true })).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: "Urgencia", exact: true })).toHaveValue("");
});

test("auditor sin concesión consulta historial sin resolver ni abrir historia clínica", async ({ page }) => {
  const { lecturas, escrituras } = await escenario(page, { rol: "auditor", solicitud: { puede_resolver: false } });
  await page.goto("/financiadores/autorizaciones");
  await page.getByRole("button", { name: "Ver solicitud 91" }).click();
  await expect(page.getByText("Solicitud inicial", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Resolver solicitud", exact: true })).toHaveCount(0);
  expect(lecturas.some((r) => /historias|\/casos\//.test(r.path))).toBe(false);
  expect(escrituras).toHaveLength(0);
});

test("el antecedente conserva el ámbito y muestra la solicitud anterior sin modificarla", async ({ page }) => {
  const { lecturas, escrituras } = await escenario(page, { solicitud: { anterior: 90 } });
  await page.goto("/financiadores/autorizaciones?financiador=21");
  await page.getByRole("button", { name: "Ver solicitud 91" }).click();
  await expect(page.getByRole("dialog")).toContainText("Solicitud anterior: #90");
  await page.getByRole("button", { name: "Ver antecedente 90" }).click();
  await expect(page.getByRole("dialog", { name: "Solicitud de autorización 90" })).toContainText("Rechazada");
  expect(lecturas.find((r) => r.path === "/autorizaciones-cobertura/90/").params).toEqual({ financiador: "21" });
  await expect(page.getByRole("button", { name: "Resolver solicitud", exact: true })).toHaveCount(0);
  expect(escrituras).toHaveLength(0);
});

test("antecedente no disponible conserva su referencia y expone el error de acceso", async ({ page }) => {
  await escenario(page, { antecedenteOculto: true, solicitud: { anterior: 90 } });
  await page.goto("/financiadores/autorizaciones");
  await page.getByRole("button", { name: "Ver solicitud 91" }).click();
  await page.getByRole("button", { name: "Ver antecedente 90" }).click();
  await expect(page.getByRole("dialog", { name: "Solicitud de autorización 90" })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("La solicitud anterior no está disponible");
});

test("bandeja y detalle conservan el espacio móvil de I-Core Salud", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await escenario(page, { rol: "auditor", solicitud: { puede_resolver: false } });
  await page.goto("/financiadores/autorizaciones");
  await expect(page.getByRole("button", { name: "Ver solicitud 91" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("autorizaciones-movil.png"), fullPage: true, animations: "disabled" });
  await page.getByRole("button", { name: "Ver solicitud 91" }).click();
  await expect(page.getByRole("dialog")).toContainText("Justificación para el financiador");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("autorizacion-detalle-movil.png"), fullPage: true, animations: "disabled" });
});

async function abrirResolucion(page) {
  await page.goto("/financiadores/autorizaciones");
  await page.getByRole("button", { name: "Ver solicitud 91" }).click();
  await page.getByRole("button", { name: "Resolver solicitud", exact: true }).click();
}

test("aprobar exige evidencia, conserva clave al reintentar y no realiza la prestación", async ({ page }, testInfo) => {
  const { escrituras } = await escenario(page, { fallo: "transitorio" });
  await abrirResolucion(page);
  await page.getByRole("combobox", { name: "Decisión", exact: true }).selectOption("aprobar");
  await page.getByLabel("Motivo de la decisión", { exact: true }).fill("Revisión administrativa conforme");
  await page.getByLabel("Válida desde", { exact: true }).fill("2026-09-16");
  await page.getByLabel("Válida hasta", { exact: true }).fill("2026-09-30");
  await expect(page.getByRole("button", { name: "Registrar decisión" })).toBeDisabled();
  await page.getByLabel("Evidencia de la decisión", { exact: false }).fill("Acta interna ficticia 123");
  await page.getByRole("button", { name: "Registrar decisión" }).click();
  await expect(page.getByRole("alert")).toContainText("Reintentá la misma operación");
  await page.screenshot({ path: testInfo.outputPath("autorizacion-resolucion.png"), fullPage: true, animations: "disabled" });
  await page.getByRole("button", { name: "Registrar decisión" }).click();
  await expect(page.getByRole("status")).toContainText("Solicitud actualizada");
  expect(escrituras).toHaveLength(2);
  expect(escrituras[1].body).toEqual(escrituras[0].body);
  expect(escrituras[0]).toMatchObject({ path: "/autorizaciones-cobertura/91/resolver/", params: { financiador: "21" }, body: { decision: "aprobar", revision: 1, cantidad_aprobada: 2, evidencia: "Acta interna ficticia 123" } });
  expect(escrituras.some((r) => r.path.includes("avanzar"))).toBe(false);
});

test("conflicto de revisión bloquea reenvío ciego y actualiza la decisión vigente", async ({ page }) => {
  const { escrituras } = await escenario(page, { fallo: "revision" });
  await abrirResolucion(page);
  await page.getByRole("combobox", { name: "Decisión", exact: true }).selectOption("observar");
  await page.getByLabel("Motivo de la decisión", { exact: true }).fill("Falta referencia de la prestación");
  await page.getByRole("button", { name: "Registrar decisión" }).click();
  await expect(page.getByRole("alert")).toContainText("La solicitud cambió");
  await expect(page.getByRole("button", { name: "Registrar decisión" })).toBeDisabled();
  await page.getByRole("button", { name: "Actualizar solicitud", exact: true }).click();
  await expect(page.getByText("Esta solicitud está disponible sólo para consulta con tu acceso actual.")).toBeVisible();
  expect(escrituras).toHaveLength(1);
});

test("el caso solicita con intento estable y justificación mínima sin enviar historia ni urgencia", async ({ page }) => {
  const { estado, escrituras } = await escenario(page, { hospital: true, fallo: "transitorio" });
  estado.listaVacia = true;
  await page.goto("/casos/41");
  await page.getByRole("button", { name: "Solicitar autorización", exact: true }).click();
  await page.getByRole("combobox", { name: "Prestación a autorizar", exact: true }).selectOption("7");
  await page.getByLabel("Cantidad solicitada", { exact: true }).fill("2");
  await page.getByLabel("Justificación para el financiador", { exact: false }).fill("Consulta por continuidad del tratamiento");
  await page.getByRole("button", { name: "Enviar solicitud", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Reintentá la misma operación");
  await page.getByRole("button", { name: "Enviar solicitud", exact: true }).click();
  await expect(page.getByText(/Solicitud enviada al financiador/)).toBeVisible();
  expect(escrituras).toHaveLength(2);
  expect(escrituras[0].body).toEqual(escrituras[1].body);
  expect(Object.keys(escrituras[0].body).sort()).toEqual(["cantidad", "caso", "clave", "intento", "justificacion", "prestacion"]);
  expect(escrituras[0].body.intento).toBe(intento);
});

test("un nuevo intento de atención descarta la solicitud que todavía no se envió", async ({ page }) => {
  const { estado, escrituras } = await escenario(page, { hospital: true });
  await page.goto("/casos/41");
  await page.getByRole("button", { name: "Solicitar autorización", exact: true }).click();
  await page.getByRole("combobox", { name: "Prestación a autorizar", exact: true }).selectOption("7");
  await page.getByLabel("Justificación para el financiador", { exact: false }).fill("Borrador del intento anterior");
  estado.contexto.intento = "22222222-2222-4222-8222-222222222222";
  await page.getByRole("button", { name: "Actualizar solicitudes", exact: true }).click();
  await expect(page.getByRole("button", { name: "Solicitar autorización", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Solicitar autorización", exact: true }).click();
  await expect(page.getByLabel("Justificación para el financiador", { exact: false })).toHaveValue("");
  expect(escrituras).toHaveLength(0);
});

test("observación se responde en el ámbito del hospital sin conceder aprobación", async ({ page }) => {
  const { escrituras } = await escenario(page, { hospital: true, solicitud: { estado: "observada", puede_resolver: false, puede_reenviar: true } });
  await page.goto("/casos/41");
  await page.getByRole("button", { name: "Ver solicitud 91" }).click();
  await page.getByRole("button", { name: "Responder observación" }).click();
  await page.getByLabel("Justificación actualizada", { exact: false }).fill("Referencia de la prestación agregada");
  await page.getByRole("button", { name: "Reenviar solicitud", exact: true }).click();
  await expect(page.getByText(/Solicitud actualizada/)).toBeVisible();
  expect(escrituras[0]).toMatchObject({ path: "/autorizaciones-cobertura/91/reenviar/", params: { institucion: "2" }, body: { revision: 1, justificacion: "Referencia de la prestación agregada" } });
});

test("levantar espera exige permiso explícito y motivo sin avanzar clínicamente", async ({ page }) => {
  const { escrituras } = await escenario(page, { hospital: true, contexto: { puede_continuar_autorizacion: true, espera_autorizacion: { estado: "esperando", intento, motivo: "Autorización requerida" } } });
  await page.goto("/casos/41");
  const espera = page.getByRole("region", { name: "Espera de autorización" });
  await expect(espera.getByRole("button", { name: "Levantar espera con motivo" })).toBeDisabled();
  await espera.getByLabel("Motivo para continuar la atención", { exact: true }).fill("Supervisión autoriza continuidad clínica");
  await espera.getByRole("button", { name: "Levantar espera con motivo" }).click();
  await expect(page.getByText(/Espera levantada/)).toBeVisible();
  expect(escrituras).toEqual([{ path: "/casos/41/continuar-autorizacion/", params: {}, body: { intento, motivo: "Supervisión autoriza continuidad clínica" } }]);
});

test("sin permiso para levantar espera muestra el estado sin ofrecer la acción", async ({ page }) => {
  await escenario(page, { hospital: true, contexto: { puede_continuar_autorizacion: false, espera_autorizacion: { estado: "esperando", intento } } });
  await page.goto("/casos/41");
  await expect(page.getByRole("region", { name: "Espera de autorización" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Levantar espera con motivo" })).toHaveCount(0);
});

test("administración concede resolver de forma explícita sin cambiar el rol de lectura", async ({ page }) => {
  const { escrituras } = await escenario(page);
  await page.goto("/financiadores/usuarios");
  await page.getByRole("button", { name: "Cambiar acceso" }).click();
  const permiso = page.getByRole("checkbox", { name: "Permitir resolver autorizaciones de este financiador" });
  await expect(permiso).not.toBeChecked();
  await permiso.check();
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Acceso actualizado");
  expect(escrituras[0].body).toMatchObject({ rol: "auditor", resuelve_autorizaciones: true });
});

test("regla exige autorización sólo al marcarla y convenio admite plazo vacío", async ({ page }) => {
  const { escrituras } = await escenario(page);
  await page.goto("/financiadores/reglas");
  await page.getByRole("button", { name: "Nueva regla de cobertura" }).click();
  const requiere = page.getByRole("checkbox", { name: "Requiere autorización previa del financiador" });
  await expect(requiere).not.toBeChecked();
  await requiere.check();
  await page.getByRole("combobox", { name: "Prestación", exact: true }).selectOption("3");
  await page.getByLabel("Porcentaje cubierto", { exact: true }).fill("80");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Registro guardado");
  expect(escrituras[0].body.requiere_autorizacion).toBe(true);
  await page.getByRole("link", { name: "Convenios", exact: true }).click();
  await page.getByRole("button", { name: "Plazo de autorización", exact: true }).click();
  await page.getByLabel("Motivo", { exact: true }).fill("Convenio sin vencimiento automático");
  await page.getByRole("button", { name: "Guardar plazo", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Vigencia actualizada");
  expect(escrituras.at(-1)).toMatchObject({ path: "/financiadores/21/plazo-autorizacion/", body: { convenio: 17, plazo_autorizacion_horas: null, motivo: "Convenio sin vencimiento automático" } });
});

test("editor permite esperar sólo en atención programada configurada explícitamente", async ({ page }) => {
  const { escrituras } = await escenario(page, { hospital: true, editor: true });
  await page.goto("/flujos/4");
  const tipo = page.getByRole("combobox", { name: "Tipo de circuito de esta versión", exact: true });
  await expect(tipo).toHaveValue("no_definido");
  await page.locator('[data-nodo="10"]').dblclick();
  const espera = page.getByRole("checkbox", { name: "Esperar autorización antes de registrar la atención", exact: true });
  await expect(espera).toBeDisabled();
  await page.getByRole("button", { name: "Cerrar", exact: true }).click();
  await tipo.selectOption("programado");
  await expect(tipo).toHaveValue("programado");
  await page.locator('[data-nodo="10"]').dblclick();
  await expect(espera).not.toBeChecked();
  await espera.check();
  await expect.poll(() => escrituras.some((r) => r.path === "/nodos/10/" && r.body.config?.esperar_autorizacion === true)).toBe(true);
  expect(escrituras[0]).toMatchObject({ path: "/versiones-flujo/3/", body: { tipo_circuito: "programado" } });
});

test("editor publicado no cambia clasificación ni espera de atención", async ({ page }) => {
  const { escrituras } = await escenario(page, { hospital: true, editor: true, publicada: true });
  await page.goto("/flujos/4");
  await expect(page.getByRole("combobox", { name: "Tipo de circuito de esta versión", exact: true })).toBeDisabled();
  await page.locator('[data-nodo="10"]').dblclick();
  await expect(page.getByRole("checkbox", { name: "Esperar autorización antes de registrar la atención", exact: true })).toBeDisabled();
  expect(escrituras).toHaveLength(0);
});

test("resolver autorización financiera pendiente identifica importe financiador y conserva copago separado", async ({ page }) => {
  const { escrituras } = await escenario(page, { hospital: true, finanzas: true });
  await page.goto("/finanzas/coberturas");
  await page.getByRole("button", { name: "Resolver saldo", exact: true }).click();
  const modal = page.getByRole("dialog");
  await expect(modal).toContainText("Importe del financiador pendiente de autorización: ARS 8.000,00");
  await expect(modal).toContainText("La decisión no modifica el copago ni aprueba la autorización");
  await modal.getByRole("combobox", { name: "Decisión", exact: true }).selectOption("paciente");
  await modal.getByLabel("Motivo", { exact: true }).fill("Acuerdo posterior expreso por esta consulta");
  await modal.getByLabel("Evidencia del acuerdo expreso", { exact: false }).fill("Paciente acepta ARS 8.000,00 por Consulta según constancia 1");
  await modal.getByRole("button", { name: "Registrar decisión", exact: true }).click();
  await expect(page.getByText("Decisión administrativa registrada.", { exact: true })).toBeVisible();
  expect(escrituras[0]).toMatchObject({ path: "/coberturas/81/resolver/", body: { parte: "financiador", decision: "paciente", importe: "8000.00", evidencia: "Paciente acepta ARS 8.000,00 por Consulta según constancia 1" } });
});
