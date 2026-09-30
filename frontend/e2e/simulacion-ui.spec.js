import { expect, test } from "@playwright/test";

/**
 * «Ver como» del superusuario: simulación de perfiles con cuentas de referencia.
 *
 * La API está interceptada entera y responde según el encabezado
 * `X-HEN-Simulacion`, como el backend real: con él, `/usuarios/me/` es la cuenta
 * de referencia. Lo que se prueba es el recorrido de la interfaz: el selector,
 * el encabezado en cada pedido, el indicador, la salida y la limpieza del estado.
 * La autorización del servidor se prueba en `apps/simulacion/tests.py`.
 */
const lista = (results = []) => ({ count: results.length, next: null, previous: null, results });
const HOSPITAL = { id: 2, nombre: "Hospital de prueba", tipo: "Hospital" };
const OTRO = { id: 3, nombre: "Otro hospital", tipo: "Hospital" };
const ROOT = { id: 1, email: "root@example.test", nombre_completo: "Root Ficticio", is_superuser: true, capacidades_por_institucion: {}, roles_por_institucion: {}, financiadores: [] };
const CAPS_ENFERMERIA = ["trabajo", "registros", "padron_admision", "historia_clinica", "solicitud_estudios", "turnos", "casos_operar", "filas", "internacion", "farmacia_stock", "traslados_red"];

function sesionDe(id, rol, etiqueta, ambito, lugar) {
  return {
    id, rol, etiqueta, ambito,
    institucion: ambito === "institucion" ? lugar : null,
    financiador: ambito === "financiador" ? lugar : null,
    cuenta: { id: 50, nombre: `Superusuario ${etiqueta}`, email: `${rol}@referencia.hen.invalid` },
    superusuario: { id: 1, nombre: "Root Ficticio", email: ROOT.email },
    iniciada: "2026-09-29T12:00:00Z", vence: "2026-09-29T20:00:00Z", finalizada: null,
  };
}

const CUENTAS = {
  enfermeria: (sesion) => ({ id: 50, email: sesion.cuenta.email, nombre_completo: sesion.cuenta.nombre, is_superuser: false, capacidades_por_institucion: { 2: CAPS_ENFERMERIA }, roles_por_institucion: { 2: ["enfermeria"] }, financiadores: [], simulacion: sesion }),
  operador: (sesion) => ({ id: 51, email: sesion.cuenta.email, nombre_completo: sesion.cuenta.nombre, is_superuser: false, capacidades_por_institucion: {}, roles_por_institucion: {}, financiadores: [{ id: 21, nombre: "Mutual del Río", rol: "operador" }], simulacion: sesion }),
  auditor: (sesion) => ({ id: 52, email: sesion.cuenta.email, nombre_completo: sesion.cuenta.nombre, is_superuser: false, capacidades_por_institucion: { global: ["auditoria"] }, roles_por_institucion: { global: ["auditor"] }, financiadores: [], simulacion: sesion }),
};

const CATALOGOS = {
  "": [{ rol: "auditor", etiqueta: "Auditor estatal", disponible: false, motivo: "Falta preparar la cuenta de referencia.", cuenta: null }],
  "?institucion=2": [
    { rol: "enfermeria", etiqueta: "Enfermería", disponible: true, motivo: "", cuenta: { id: 50 } },
    { rol: "medico", etiqueta: "Médico / profesional", disponible: false, motivo: "Falta preparar la cuenta de referencia.", cuenta: null },
  ],
  "?financiador=21": [
    { rol: "admin", etiqueta: "Administrador de financiador", disponible: false, motivo: "Falta preparar la cuenta de referencia.", cuenta: null },
    { rol: "operador", etiqueta: "Operador de financiador", disponible: true, motivo: "", cuenta: { id: 51 } },
  ],
};

async function escenario(page, { usuario = ROOT, institucion = HOSPITAL, simulacionGuardada = null, estadoCompartido = null } = {}) {
  const estado = estadoCompartido || { activa: null, pedidos: [], finalizadas: [], iniciadas: [], rechazar: false };
  await page.addInitScript(({ inst, sim }) => {
    sessionStorage.setItem("salud.access", "token-ficticio-mock");
    sessionStorage.setItem("salud.refresh", "refresh-ficticio-mock");
    if (inst) localStorage.setItem("salud.institucion", JSON.stringify(inst));
    if (sim && !sessionStorage.getItem("salud.simulacion-prueba")) {
      sessionStorage.setItem("salud.simulacion", JSON.stringify(sim));
      sessionStorage.setItem("salud.simulacion-prueba", "1");
    }
  }, { inst: institucion, sim: simulacionGuardada ? { id: simulacionGuardada.id } : null });
  if (simulacionGuardada) estado.activa = simulacionGuardada;

  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const path = url.pathname.replace(/^\/api/, "");
    const encabezado = req.headers()["x-hen-simulacion"] || null;
    estado.pedidos.push({ path, metodo: req.method(), encabezado });

    if (path.startsWith("/simulaciones/")) {
      // La administración de la simulación sale siempre con la identidad real.
      if (encabezado) return route.fulfill({ status: 403, json: { detail: "Solo un superusuario puede simular perfiles." } });
      if (path === "/simulaciones/catalogo/") return route.fulfill({ json: { perfiles: CATALOGOS[url.search] || [] } });
      if (path === "/simulaciones/" && req.method() === "POST") {
        const cuerpo = req.postDataJSON();
        estado.iniciadas.push(cuerpo);
        const sesion = cuerpo.rol === "operador"
          ? sesionDe(`sesion-${estado.iniciadas.length}`, "operador", "Operador de financiador", "financiador", { id: 21, nombre: "Mutual del Río", tipo: "mutual" })
          : cuerpo.rol === "auditor"
            ? sesionDe(`sesion-${estado.iniciadas.length}`, "auditor", "Auditor estatal", "plataforma", null)
            : sesionDe(`sesion-${estado.iniciadas.length}`, "enfermeria", "Enfermería", "institucion", HOSPITAL);
        estado.activa = sesion;
        return route.fulfill({ status: 201, json: sesion });
      }
      const fin = path.match(/^\/simulaciones\/([^/]+)\/finalizar\/$/);
      if (fin) {
        estado.finalizadas.push({ id: fin[1], motivo: req.postDataJSON()?.motivo });
        if (estado.activa?.id === fin[1]) estado.activa = null;
        return route.fulfill({ json: {} });
      }
    }

    if (encabezado) {
      if (estado.rechazar || encabezado !== estado.activa?.id) {
        estado.activa = null;
        return route.fulfill({ status: 403, json: { detail: "La simulación venció. Volvé a elegir un perfil.", simulacion: "rechazada" } });
      }
    }
    const simulando = encabezado ? estado.activa : null;
    if (path === "/usuarios/me/") return route.fulfill({ json: simulando ? CUENTAS[simulando.rol](simulando) : usuario });
    if (path === "/instituciones/") return route.fulfill({ json: lista(simulando ? [HOSPITAL] : [HOSPITAL, OTRO]) });
    if (path === "/financiadores/") return route.fulfill({ json: lista(simulando?.rol === "operador" ? [{ id: 21, nombre: "Mutual del Río", tipo: "mutual", rol: "operador" }] : [{ id: 21, nombre: "Mutual del Río", tipo: "mutual" }]) });
    if (path === "/notificaciones/resumen/") return route.fulfill({ json: { no_leidas: 0, items: [] } });
    if (path === "/mis-tareas/") return route.fulfill({ json: { tareas: [], filas: [] } });
    if (path === "/concesiones-financieras/mias/") return route.fulfill({ json: { superusuario: !simulando && usuario.is_superuser, concesiones: [] } });
    if (req.method() === "GET") return route.fulfill({ json: lista([]) });
    return route.fulfill({ json: {} });
  });
  return estado;
}

const menu = (page) => page.getByRole("navigation", { name: /Menú/ });
// Los grupos del menú se muestran solo si el perfil tiene algún ítem visible.
const grupo = (page, nombre) => menu(page).getByRole("button", { name: nombre, exact: true });

test("el superusuario simula enfermería con la cuenta de referencia y vuelve a Sistema", async ({ page }) => {
  const estado = await escenario(page);
  await page.goto("/inicio");
  const selector = page.getByLabel("Ver como");
  await expect(selector).toHaveValue("sistema");
  await expect(grupo(page, "CONFIGURACIÓN")).toBeVisible();
  // Una cuenta ausente se preparará al elegir el perfil, sin bloquear el selector.
  await expect(selector.locator("option", { hasText: "Médico / profesional" })).toBeEnabled();
  await expect(page.getByText("Este ámbito no tiene cuentas de referencia preparadas.")).toHaveCount(0);
  await page.getByLabel("Ayuda sobre Ver como").click();
  await expect(page.getByText(/se prepara su cuenta técnica si hace falta/)).toBeVisible();

  await selector.selectOption("enfermeria");
  const banner = page.getByRole("status", { name: "Simulación de perfil activa" });
  await expect(banner).toContainText("Simulando Enfermería");
  await expect(banner).toContainText("Institución: Hospital de prueba");
  await expect(banner).toContainText("queda a nombre de Root Ficticio");
  await expect(page.getByText("Superusuario Enfermería").first()).toBeVisible();
  await expect(grupo(page, "PACIENTES")).toBeVisible();
  await expect(grupo(page, "CONFIGURACIÓN")).toHaveCount(0);
  expect(estado.iniciadas).toEqual([{ ambito: "institucion", rol: "enfermeria", institucion: 2 }]);
  const tras = estado.pedidos.filter((p) => !p.path.startsWith("/simulaciones/")).slice(-3);
  expect(tras.length).toBeGreaterThan(0);
  expect(tras.every((p) => p.encabezado === "sesion-1")).toBe(true);

  await banner.getByRole("button", { name: "Volver a Sistema" }).click();
  await expect(banner).toHaveCount(0);
  await expect(page.getByLabel("Ver como")).toHaveValue("sistema");
  await expect(grupo(page, "CONFIGURACIÓN")).toBeVisible();
  expect(estado.finalizadas).toEqual([{ id: "sesion-1", motivo: "salida" }]);
  expect(await page.evaluate(() => sessionStorage.getItem("salud.simulacion"))).toBeNull();
  const cantidad = estado.pedidos.length;
  await page.reload();
  await expect(grupo(page, "CONFIGURACIÓN")).toBeVisible();
  expect(estado.pedidos.slice(cantidad).every((p) => p.encabezado === null)).toBe(true);
});

test("cerrar sesión termina la simulación y no la deja guardada", async ({ page }) => {
  const estado = await escenario(page);
  await page.goto("/inicio");
  await page.getByLabel("Ver como").selectOption("enfermeria");
  await expect(page.getByRole("status", { name: "Simulación de perfil activa" })).toBeVisible();
  await page.getByRole("button", { name: "Salir" }).click();
  await expect(page).toHaveURL(/\/login/);
  await expect.poll(() => estado.finalizadas).toEqual([{ id: "sesion-1", motivo: "cierre" }]);
  expect(await page.evaluate(() => sessionStorage.getItem("salud.simulacion"))).toBeNull();
});

test("si el servidor rechaza la simulación vuelve a Sistema y lo avisa", async ({ page }) => {
  const estado = await escenario(page);
  await page.goto("/inicio");
  await page.getByLabel("Ver como").selectOption("enfermeria");
  await expect(page.getByRole("status", { name: "Simulación de perfil activa" })).toBeVisible();
  estado.rechazar = true;
  await grupo(page, "PACIENTES").click();
  await menu(page).getByRole("link", { name: "Padrón de pacientes" }).click();
  await expect(page.getByText("La simulación terminó: La simulación venció.")).toBeVisible();
  await expect(page.getByRole("status", { name: "Simulación de perfil activa" })).toHaveCount(0);
  await expect(page.getByLabel("Ver como")).toHaveValue("sistema");
  expect(await page.evaluate(() => sessionStorage.getItem("salud.simulacion"))).toBeNull();
});

test("abrir otra simulación en una segunda pestaña invalida la primera", async ({ page }) => {
  const estado = await escenario(page);
  await page.goto("/inicio");
  await page.getByLabel("Ver como").selectOption("enfermeria");
  await expect(page.getByRole("status", { name: "Simulación de perfil activa" })).toBeVisible();

  const segunda = await page.context().newPage();
  await escenario(segunda, { estadoCompartido: estado });
  await segunda.goto("/inicio");
  await segunda.getByLabel("Ver como").selectOption("enfermeria");
  await expect(segunda.getByRole("status", { name: "Simulación de perfil activa" })).toBeVisible();
  expect(estado.iniciadas).toHaveLength(2);

  await page.goto("/inicio");
  await expect(page.getByRole("status", { name: "Simulación de perfil activa" })).toHaveCount(0);
  await expect(page.getByLabel("Ver como")).toHaveValue("sistema");
  expect(await page.evaluate(() => sessionStorage.getItem("salud.simulacion"))).toBeNull();
  await expect(segunda.getByRole("status", { name: "Simulación de perfil activa" })).toBeVisible();
  expect(JSON.parse(await segunda.evaluate(() => sessionStorage.getItem("salud.simulacion"))).id).toBe("sesion-2");
});

test("al recargar no conserva una institución ajena al ámbito simulado", async ({ page }) => {
  const sesion = sesionDe("sesion-9", "enfermeria", "Enfermería", "institucion", HOSPITAL);
  await escenario(page, { institucion: OTRO, simulacionGuardada: sesion });
  await page.goto("/inicio");
  await expect(page.getByRole("status", { name: "Simulación de perfil activa" })).toContainText("Hospital de prueba");
  await expect(page.getByRole("complementary").getByText("Hospital de prueba", { exact: true })).toBeVisible();
  await expect(page.getByText("Otro hospital")).toHaveCount(0);
});

test("desde un financiador de plataforma simula al operador con su portal", async ({ page }) => {
  const estado = await escenario(page, { institucion: null });
  await page.goto("/financiadores?financiador=21");
  const selector = page.getByLabel("Ver como");
  await expect(selector.locator("option", { hasText: "Operador de financiador" })).toBeEnabled();
  await selector.selectOption("operador");
  await expect(page.getByRole("status", { name: "Simulación de perfil activa" })).toContainText("Financiador: Mutual del Río");
  await expect(page.getByRole("navigation", { name: "Menú del financiador" })).toBeVisible();
  expect(estado.iniciadas).toEqual([{ ambito: "financiador", rol: "operador", financiador: 21 }]);
  await page.getByRole("button", { name: "Volver a Sistema" }).click();
  await expect(page).toHaveURL(/\/financiadores\?financiador=21/);
  await expect(page.getByRole("navigation", { name: "Menú de plataforma" })).toBeVisible();
});

test("el auditor estatal sin institución llega al registro de accesos", async ({ page }) => {
  const estado = await escenario(page, { institucion: null });
  await page.goto("/directorio");
  await page.getByLabel("Ver como").selectOption("auditor");
  await expect(page.getByRole("status", { name: "Simulación de perfil activa" })).toContainText("Auditor estatal");
  await expect(page.getByRole("heading", { name: "Registro de accesos" })).toBeVisible();
  const navegacion = page.getByRole("navigation", { name: "Menú de plataforma" });
  await expect(navegacion.getByRole("link", { name: "Registro de accesos" })).toBeVisible();
  await expect(navegacion.getByRole("link", { name: "Usuarios" })).toHaveCount(0);
  expect(estado.iniciadas).toEqual([{ ambito: "plataforma", rol: "auditor" }]);
});

test("quien no es superusuario no ve el selector", async ({ page }) => {
  await escenario(page, {
    usuario: { id: 7, email: "medica@example.test", nombre_completo: "Médica", is_superuser: false, capacidades_por_institucion: { 2: ["casos_operar"] }, roles_por_institucion: { 2: ["medico"] }, financiadores: [] },
  });
  await page.goto("/inicio");
  await expect(menu(page)).toBeVisible();
  await expect(page.getByLabel("Ver como")).toHaveCount(0);
});
