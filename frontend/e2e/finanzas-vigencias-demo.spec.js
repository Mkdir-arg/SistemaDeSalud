import { expect, test } from "@playwright/test";

const institucion = { id: 2, nombre: "Hospital Escuela" };
const lista = (results) => ({ count: results.length, results, next: null, previous: null });
const hoy = new Date("2026-09-15T01:30:00Z"); // 14/09, 22:30 en Buenos Aires.
const valor = (id, desde, extra = {}) => ({ id, componente: 1, importe: "100.00", vigente_desde: desde, vigente_hasta: null, reemplaza: null, ...extra });

async function escenario(page, { valores = [], sensible = false, permiteSensibles = true } = {}) {
  await page.clock.setFixedTime(hoy);
  const escrituras = [];
  const db = {
    prestaciones: [{ id: 1, institucion: 2, nodo: 44, nombre: "Consulta médica", codigo: "CONSULTA", activo: true }],
    componentes: [{ id: 1, prestacion: 1, nombre: "Materiales", codigo: "MAT", activo: true, sensible }],
    valores: [...valores],
  };
  await page.addInitScript((inst) => {
    localStorage.setItem("cauce.access", "credencial-ficticia-solo-mock");
    localStorage.setItem("cauce.institucion", JSON.stringify(inst));
  }, institucion);
  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/^\/api/, "");
    const coleccion = { "/prestaciones-costo/": "prestaciones", "/componentes-costo/": "componentes", "/valores-componentes/": "valores" }[path];
    if (request.method() !== "GET") {
      const body = request.postDataJSON();
      escrituras.push({ path, body });
      if (!coleccion) return route.fulfill({ status: 400, json: { detail: "Escritura no prevista en el contrato simulado." } });
      const fila = { id: 100 + escrituras.length, ...body };
      db[coleccion].push(fila);
      return route.fulfill({ status: 201, json: fila });
    }
    let data = lista([]);
    if (path === "/usuarios/me/") data = { id: 7, nombre: "Elena", email: "elena@mock.test", is_superuser: false, capacidades_por_institucion: { 2: [] }, roles_por_institucion: { 2: ["administrativo"] } };
    if (path === "/instituciones/") data = lista([institucion]);
    if (path === "/areas/") data = lista([{ id: 3, institucion: 2, nombre: "Clínica médica" }]);
    if (path === "/notificaciones/resumen/") data = { no_leidas: 0, recientes: [] };
    if (path === "/concesiones-financieras/mias/") data = { superusuario: false, concesiones: ["ver_costos", "configurar_componentes"].map((accion) => ({ institucion: 2, accion, todas_las_areas: true, areas: [], permite_sensibles: permiteSensibles })) };
    if (path === "/prestaciones-costo/atenciones-disponibles/") data = [{ id: 44, titulo: "Consulta médica", flujo_nombre: "Consultorio", version_numero: 1, area: 3, area_nombre: "Clínica médica" }, { id: 45, titulo: "Control cardiológico", flujo_nombre: "Cardiología", version_numero: 1, area: 3, area_nombre: "Clínica médica" }];
    if (coleccion) data = lista(db[coleccion]);
    return route.fulfill({ json: data });
  });
  await page.goto("/finanzas?tab=costos&mes=2026-09");
  await page.getByRole("button", { name: "Configurar costos por atención", exact: true }).click();
  return { db, escrituras };
}

async function abrirValores(page) {
  await page.getByLabel("Atención configurada", { exact: false }).selectOption("1");
  await page.getByRole("button", { name: /^Materiales/ }).click();
  return page.getByRole("list", { name: "Valores del componente", exact: true });
}

test("vigente hoy precede a programados e históricos y un sucesor futuro no lo oculta", async ({ page }, testInfo) => {
  await escenario(page, { valores: [
    valor(1, "2026-01-01T03:00:00Z", { importe: "50.00", vigente_hasta: "2026-06-01T03:00:00Z" }),
    valor(2, "2026-06-01T03:00:00Z", { importe: "75.00", vigente_hasta: "2026-09-01T03:00:00Z", reemplaza: 1 }),
    valor(3, "2026-09-01T03:00:00Z", { importe: "100.00", reemplaza: 2 }),
    valor(4, "2026-10-01T03:00:00Z", { importe: "125.00", reemplaza: 3 }),
  ] });
  const filas = (await abrirValores(page)).getByRole("listitem");
  await expect(filas).toHaveCount(4);
  await expect(filas.nth(0)).toContainText("Vigente hoy");
  await expect(filas.nth(0)).toContainText("ARS 100,00");
  await expect(filas.nth(0).getByRole("button", { name: "Cambiar valor desde otra fecha" })).toHaveCount(0);
  await expect(filas.nth(1)).toContainText("Programado");
  await expect(filas.nth(1)).toContainText("ARS 125,00");
  await expect(filas.nth(2)).toContainText("Histórico");
  await expect(filas.nth(2)).toContainText("ARS 75,00");
  await expect(filas.nth(3)).toContainText("ARS 50,00");
  await expect(filas.nth(2)).toHaveClass(/text-texto-debil/);
  await page.screenshot({ path: testInfo.outputPath("valores-vigentes-programados-historicos.png"), animations: "disabled" });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.getByRole("dialog", { name: "Configurar costos por atención", exact: true }).evaluate((dialogo) => dialogo.scrollWidth <= dialogo.clientWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("valores-vigencias-movil.png"), animations: "disabled" });
});

test("vigencia respeta fin exclusivo y desempata correcciones por identificador", async ({ page }) => {
  await escenario(page, { valores: [
    valor(1, "2026-01-01T03:00:00Z", { importe: "25.00", vigente_hasta: hoy.toISOString() }),
    valor(2, hoy.toISOString(), { importe: "30.00" }),
    valor(3, hoy.toISOString(), { importe: "35.00", reemplaza: 2 }),
  ] });
  const filas = (await abrirValores(page)).getByRole("listitem");
  await expect(filas.nth(0)).toContainText("Vigente hoy");
  await expect(filas.nth(0)).toContainText("ARS 35,00");
  await expect(filas.nth(1)).toContainText("Histórico");
  await expect(filas.nth(2)).toContainText("Histórico");
  await expect(page.getByText("Vigente hoy", { exact: true })).toHaveCount(1);
});

test("cambiar valor conserva cero y precarga fecha/hora local sin confundirla con UTC", async ({ page }) => {
  const { escrituras } = await escenario(page, { valores: [valor(1, "2026-01-01T03:00:00Z", { importe: 0 })] });
  await abrirValores(page);
  await page.getByRole("button", { name: "Cambiar valor desde otra fecha" }).click();
  await expect(page.getByLabel("Importe por atención en ARS", { exact: true })).toHaveValue("0");
  await expect(page.getByLabel("Vigente desde", { exact: false })).toHaveValue("2026-09-14T22:30");
  await page.getByLabel("Motivo del cambio").fill("Nueva vigencia del componente");
  await page.getByRole("button", { name: "Guardar este paso", exact: true }).click();
  await expect.poll(() => escrituras.length).toBe(1);
  expect(escrituras[0].body).toMatchObject({ importe: "0", vigente_desde: "2026-09-15T01:30:00.000Z", reemplaza: 1, motivo_correccion: "Nueva vigencia del componente" });
});

test("cambiar un intervalo futuro sigue exigiendo inicio posterior y un fin válido", async ({ page }) => {
  const { escrituras } = await escenario(page, { valores: [valor(1, "2026-10-01T03:00:00Z")] });
  await abrirValores(page);
  await page.getByRole("button", { name: "Cambiar valor desde otra fecha" }).click();
  await page.getByLabel("Motivo del cambio").fill("Cambio programado");
  await page.getByRole("button", { name: "Guardar este paso", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("El nuevo valor debe empezar después del anterior. Este formulario no corrige importes históricos.");
  await page.getByLabel("Vigente desde", { exact: false }).fill("2026-11-01T10:00");
  await page.getByLabel("Vigente hasta (opcional)", { exact: false }).fill("2026-11-01T09:00");
  await page.getByRole("button", { name: "Guardar este paso", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveText("La fecha final debe ser posterior al inicio.");
  expect(escrituras).toEqual([]);
});

test("un intervalo nuevo propone fecha local actual y deja el importe a completar", async ({ page }) => {
  const { escrituras } = await escenario(page);
  await abrirValores(page);
  await page.getByRole("button", { name: "Agregar intervalo de valor", exact: true }).click();
  await expect(page.getByLabel("Vigente desde", { exact: false })).toHaveValue("2026-09-14T22:30");
  await expect(page.getByLabel("Importe por atención en ARS", { exact: true })).toHaveValue("");
  await page.getByLabel("Importe por atención en ARS", { exact: true }).fill("125.50");
  await page.getByRole("button", { name: "Guardar este paso", exact: true }).click();
  await expect.poll(() => escrituras.length).toBe(1);
  expect(escrituras[0].body).toMatchObject({ importe: "125.50", vigente_desde: "2026-09-15T01:30:00.000Z" });
  expect(escrituras[0].body).not.toHaveProperty("reemplaza");
});

for (const tipo of ["prestacion", "componente"]) {
  for (const codigo of ["", "  CODIGO-PROPIO  "]) {
    test(`${tipo}: código ${codigo ? "manual avanzado" : "omitido para generación del servidor"}`, async ({ page }) => {
      const { escrituras } = await escenario(page);
      if (tipo === "prestacion") {
        await page.getByRole("button", { name: "Configurar otra atención", exact: true }).click();
        await page.getByLabel("Atención del flujo publicado").selectOption("45");
      } else {
        await page.getByLabel("Atención configurada", { exact: false }).selectOption("1");
        await page.getByRole("button", { name: "Agregar componente", exact: true }).click();
        await page.getByLabel("Nombre", { exact: true }).fill("Insumos descartables");
      }
      await expect(page.getByLabel("Código de referencia", { exact: false })).toBeHidden();
      if (codigo) {
        await page.getByText("Opciones avanzadas", { exact: true }).click();
        await page.getByLabel("Código de referencia", { exact: false }).fill(codigo);
      }
      await page.getByRole("button", { name: "Guardar este paso", exact: true }).click();
      await expect.poll(() => escrituras.length).toBe(1);
      expect(escrituras[0].path).toBe(tipo === "prestacion" ? "/prestaciones-costo/" : "/componentes-costo/");
      if (codigo) expect(escrituras[0].body.codigo).toBe("CODIGO-PROPIO");
      else expect(escrituras[0].body).not.toHaveProperty("codigo");
    });
  }
}

test("el alcance sensible mantiene ocultas las acciones para cambiar valores", async ({ page }) => {
  await escenario(page, { sensible: true, permiteSensibles: false, valores: [valor(1, "2026-01-01T03:00:00Z")] });
  await abrirValores(page);
  await expect(page.getByRole("button", { name: "Agregar intervalo de valor", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Cambiar valor desde otra fecha", exact: true })).toHaveCount(0);
});
