import { expect, test } from "@playwright/test";

const lista = (results) => ({ count: results.length, next: null, previous: null, results });
const instituciones = [{ id: 1, nombre: "Hospital Central", tipo: "Hospital" }, { id: 2, nombre: "Hospital Norte", tipo: "Hospital" }];
const afiliacion = { id: 10, financiador_id: 4, financiador_nombre: "Mutual Actual", plan_id: 5, plan_nombre: "Plan Familiar", numero: "000071", desde: "2026-09-01", seleccionable: true, motivo: "" };
const cobertura = (afiliaciones = [afiliacion]) => ({ habilitada: true, estado: afiliaciones.length > 1 ? "multiple" : afiliaciones.length ? "vigente" : "sin_padron", declaracion_legada: "Obra social anterior", afiliaciones });
const paciente = (datos = {}) => ({ id: 7, nombre: "Ana", apellido: "de Prueba", documento: "00123456", institucion: 1, obra_social: "Obra social anterior", consentimiento: null, cobertura_administrativa: cobertura(), ...datos });

async function preparar(page, opciones = {}) {
  const estado = { pacientes: opciones.pacientes || [paciente()], configuracionError: opciones.configuracionError || false, errorBusqueda: false };
  const escrituras = [];
  const lecturas = [];
  await page.addInitScript((institucion) => {
    localStorage.setItem("salud.access", "token-ficticio-interceptado");
    localStorage.setItem("salud.institucion", JSON.stringify(institucion));
  }, instituciones[0]);
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const path = url.pathname.replace(/^\/api/, "");
    if (request.method() === "POST" || request.method() === "PATCH") {
      const body = request.postDataJSON();
      escrituras.push({ path, body, method: request.method() });
      if (path === "/ciudadanos/") {
        const creado = paciente({ ...body, id: 99, cobertura_administrativa: opciones.habilitada === false ? { habilitada: false, estado: "no_habilitada", afiliaciones: [], declaracion_legada: body.obra_social } : cobertura([]) });
        estado.pacientes.push(creado);
        return route.fulfill({ status: 201, json: creado });
      }
      if (path === "/ciudadanos/7/") {
        Object.assign(estado.pacientes[0], body);
        return route.fulfill({ json: estado.pacientes[0] });
      }
      return route.fulfill({ status: 404, json: { detail: "Escritura no prevista" } });
    }
    lecturas.push(path + url.search);
    if (path === "/usuarios/me/") return route.fulfill({ json: { id: 30, nombre_completo: "Admisión de prueba", email: "admision@example.test", capacidades_por_institucion: { 1: ["padron_admision"], 2: ["padron_admision"] }, roles_por_institucion: { 1: ["administrativo"], 2: ["administrativo"] }, financiadores: [] } });
    if (path === "/instituciones/") return route.fulfill({ json: lista(instituciones) });
    if (path === "/notificaciones/resumen/") return route.fulfill({ json: { no_leidas: 0, items: [] } });
    if (path === "/concesiones-financieras/mias/") return route.fulfill({ json: { superusuario: false, concesiones: [] } });
    if (path === "/ciudadanos/configuracion-cobertura/") {
      if (estado.configuracionError) return route.fulfill({ status: 503, json: { detail: "Configuración temporalmente no disponible" } });
      return route.fulfill({ json: { institucion: Number(url.searchParams.get("institucion")), habilitada: opciones.habilitada !== false } });
    }
    if (path === "/ciudadanos/") {
      if (opciones.interceptarLista && await opciones.interceptarLista({ route, url })) return;
      if (estado.errorBusqueda && url.searchParams.has("search")) return route.fulfill({ status: 503, json: { detail: "Búsqueda no disponible" } });
      const resultados = estado.pacientes.filter((c) => c.institucion === Number(url.searchParams.get("institucion")) && (!url.searchParams.get("search") || `${c.nombre} ${c.apellido} ${c.documento}`.toLowerCase().includes(url.searchParams.get("search").toLowerCase())));
      return route.fulfill({ json: lista(resultados) });
    }
    if (/^\/ciudadanos\/\d+\/$/.test(path)) {
      const encontrado = estado.pacientes.find((c) => c.id === Number(path.split("/")[2]) && c.institucion === Number(url.searchParams.get("institucion")));
      return route.fulfill(encontrado ? { json: encontrado } : { status: 404, json: { detail: "Paciente no encontrado en este hospital" } });
    }
    return route.fulfill({ json: lista([]) });
  });
  return { estado, escrituras, lecturas };
}

test("Admisión ve afiliaciones actuales múltiples y legado separado sin acceder a historia clínica", async ({ page }, testInfo) => {
  const segunda = { ...afiliacion, id: 11, financiador_id: 6, financiador_nombre: "Obra Social Vigente", plan_nombre: "Plan Integral", numero: "000090" };
  const { lecturas, escrituras } = await preparar(page, { pacientes: [paciente({ cobertura_administrativa: cobertura([afiliacion, segunda]) })] });
  await page.goto("/padron/7");
  const resumen = page.getByRole("region", { name: "Cobertura administrativa" });
  await expect(resumen.getByText("Varias afiliaciones vigentes", { exact: true })).toBeVisible();
  await expect(resumen.getByText("Mutual Actual · Plan Familiar", { exact: true })).toBeVisible();
  await expect(resumen.getByText("Obra Social Vigente · Plan Integral", { exact: true })).toBeVisible();
  await expect(resumen.getByText("000071", { exact: true })).toBeVisible();
  await expect(resumen.getByText(/Vigente desde 01\/09\/2026/)).toHaveCount(2);
  await expect(resumen.getByText("Cobertura declarada (dato anterior, sin verificar)")).toBeVisible();
  await expect(resumen.getByText(/La afiliación de cada caso se elige al ingresar; no autoriza cargos/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Abrir historia" })).toHaveCount(0);
  expect(lecturas.some((p) => /historias-clinicas|\/cobertura\//.test(p))).toBe(false);
  expect(escrituras).toHaveLength(0);
  await page.screenshot({ path: testInfo.outputPath("cobertura-administrativa-escritorio.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(resumen).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await resumen.screenshot({ path: testInfo.outputPath("cobertura-administrativa-movil.png") });
});

test("listado y buscador común distinguen afiliación vigente y texto sin verificar", async ({ page }) => {
  await preparar(page, { pacientes: [paciente(), paciente({ id: 8, nombre: "Beatriz", cobertura_administrativa: undefined, obra_social: "Mutual declarada" })] });
  await page.goto("/padron");
  await expect(page.getByRole("cell", { name: "Mutual Actual · Plan Familiar", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Declarada: Mutual declarada", exact: true })).toBeVisible();
  await page.getByRole("combobox", { name: "Buscar paciente por nombre o documento", exact: true }).fill("Beatriz");
  await expect(page.getByRole("listbox")).toContainText("Declarada: Mutual declarada");
  await page.getByRole("listbox").getByText("Beatriz de Prueba", { exact: true }).click();
  await expect(page.getByRole("region", { name: "Cobertura administrativa" })).toContainText("Sin verificación de afiliación");
});

test("alta habilitada omite el texto de obra social y conserva los datos personales", async ({ page }) => {
  const { escrituras } = await preparar(page);
  await page.goto("/padron?nuevo=1");
  await page.getByLabel("Nombre *", { exact: true }).fill("Paciente Nuevo");
  await expect(page.getByText(/Las declaraciones nuevas se registran en la cobertura del caso/)).toBeVisible();
  await expect(page.getByLabel("Cobertura declarada (sin verificar)")).toHaveCount(0);
  await page.getByRole("button", { name: "Crear", exact: true }).click();
  await expect(page).toHaveURL(/\/padron\/99$/);
  expect(escrituras[0].body).toMatchObject({ institucion: 1, nombre: "Paciente Nuevo" });
  expect(escrituras[0].body).not.toHaveProperty("obra_social");
});

test("hospital no habilitado permite cargar cobertura etiquetada como declarada", async ({ page }) => {
  const { escrituras } = await preparar(page, { habilitada: false });
  await page.goto("/padron?nuevo=1");
  await page.getByLabel("Nombre *", { exact: true }).fill("Nuevo Declarado");
  await page.getByLabel("Cobertura declarada (sin verificar)").fill("Mutual informada");
  await page.getByRole("button", { name: "Crear", exact: true }).click();
  await expect(page).toHaveURL(/\/padron\/99$/);
  expect(escrituras[0].body.obra_social).toBe("Mutual informada");
  const region = page.getByRole("region", { name: "Cobertura administrativa" });
  await expect(region).toContainText("Cobertura estructurada no habilitada en este hospital");
  await expect(region).toContainText("Mutual informada");
});

test("editar otros datos en hospital habilitado conserva el legado sin enviarlo", async ({ page }) => {
  const { escrituras } = await preparar(page);
  await page.goto("/padron/7");
  await page.getByRole("button", { name: "Editar datos", exact: true }).click();
  await expect(page.getByLabel("Cobertura declarada (sin verificar)")).toHaveCount(0);
  await page.getByLabel("Domicilio", { exact: true }).fill("Calle de prueba 123");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Datos actualizados");
  expect(escrituras[0].body).toMatchObject({ domicilio: "Calle de prueba 123" });
  expect(escrituras[0].body).not.toHaveProperty("obra_social");
  await expect(page.getByRole("region", { name: "Cobertura administrativa" })).toContainText("Obra social anterior");
});

test("editar un hospital no habilitado conserva la operatoria del dato declarado", async ({ page }) => {
  const { escrituras } = await preparar(page, { habilitada: false, pacientes: [paciente({ cobertura_administrativa: { habilitada: false, estado: "no_habilitada", declaracion_legada: "Obra social anterior", afiliaciones: [] } })] });
  await page.goto("/padron/7");
  await page.getByRole("button", { name: "Editar datos", exact: true }).click();
  await page.getByLabel("Cobertura declarada (sin verificar)").fill("Nueva declaración");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Datos actualizados");
  expect(escrituras[0].body.obra_social).toBe("Nueva declaración");
});

test("un error de configuración se muestra, bloquea el alta y permite reintentar", async ({ page }) => {
  const { estado, escrituras } = await preparar(page, { configuracionError: true });
  await page.goto("/padron?nuevo=1");
  await page.getByLabel("Nombre *", { exact: true }).fill("Paciente Seguro");
  await expect(page.getByRole("alert")).toContainText("Configuración temporalmente no disponible");
  await expect(page.getByRole("button", { name: "Crear", exact: true })).toBeDisabled();
  expect(escrituras).toHaveLength(0);
  estado.configuracionError = false;
  await page.getByRole("button", { name: "Reintentar", exact: true }).click();
  await expect(page.getByRole("button", { name: "Crear", exact: true })).toBeEnabled();
});

test("cambiar de hospital consulta su configuración y descarta el formulario anterior", async ({ page }) => {
  const { estado, lecturas, escrituras } = await preparar(page);
  await page.goto("/padron?nuevo=1");
  await page.getByLabel("Nombre *", { exact: true }).fill("Nombre del hospital anterior");
  await expect(page.getByRole("button", { name: "Crear", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Cancelar", exact: true }).click();
  await page.getByRole("button", { name: /Hospital Central Hospital$/ }).click();
  await page.getByRole("button", { name: "Hospital Norte Hospital", exact: true }).click();
  estado.configuracionError = true;
  await page.getByRole("link", { name: "Padrón de pacientes", exact: true }).click();
  await page.getByRole("button", { name: "+ Crear registro", exact: true }).click();
  await expect(page.getByLabel("Nombre *", { exact: true })).toHaveValue("");
  await page.getByLabel("Nombre *", { exact: true }).fill("Paciente del nuevo hospital");
  await expect(page.getByRole("alert")).toContainText("Configuración temporalmente no disponible");
  await expect(page.getByRole("button", { name: "Crear", exact: true })).toBeDisabled();
  expect(lecturas).toContain("/ciudadanos/configuracion-cobertura/?institucion=2");
  expect(escrituras).toHaveLength(0);
});

test("el buscador descarta la respuesta tardía del hospital anterior y muestra errores del nuevo", async ({ page }) => {
  let liberarAnterior;
  const esperaAnterior = new Promise((resolve) => { liberarAnterior = resolve; });
  let pidioAnterior = false;
  const { estado } = await preparar(page, {
    interceptarLista: async ({ route, url }) => {
      if (url.searchParams.get("institucion") === "1" && url.searchParams.get("search") === "Ana") {
        pidioAnterior = true;
        await esperaAnterior;
        await route.fulfill({ json: lista([paciente()]) });
        return true;
      }
      return false;
    },
  });
  await page.goto("/padron");
  await page.getByRole("combobox", { name: "Buscar paciente por nombre o documento", exact: true }).fill("Ana");
  await expect.poll(() => pidioAnterior).toBe(true);
  await page.getByRole("combobox", { name: "Buscar paciente por nombre o documento", exact: true }).press("Escape");
  await page.getByRole("button", { name: /Hospital Central Hospital$/ }).click();
  await page.getByRole("button", { name: "Hospital Norte Hospital", exact: true }).click();
  await expect(page).toHaveURL(/\/inicio$/);
  estado.errorBusqueda = true;
  await page.getByRole("combobox", { name: "Buscar paciente por nombre o documento", exact: true }).fill("Ana nueva");
  await expect(page.getByRole("listbox").getByRole("alert")).toContainText("No se pudo buscar al paciente");
  liberarAnterior();
  await expect(page.getByRole("listbox")).not.toContainText("Mutual Actual");
  estado.errorBusqueda = false;
  await page.getByRole("button", { name: "Reintentar", exact: true }).click();
  await expect(page.getByRole("listbox")).toContainText("Sin pacientes");
});
