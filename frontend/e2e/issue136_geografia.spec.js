import { test, expect } from "@playwright/test";

async function preparar(page, fallo = false) {
  page.on("pageerror", (error) => { throw error; });
  const consultas = [];
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.startsWith("/api/")) return route.continue();
    if (url.pathname === "/api/usuarios/me/") return route.fulfill({ json: { id: 1, nombre: "Operador ficticio" } });
    if (url.pathname === "/api/geografia/estado/") return route.fulfill({ json: { version: 1, actualizado: "2026-10-22T00:00:00Z", error: "" } });
    if (url.pathname === "/api/geografia/lugares/") {
      consultas.push(url);
      if (fallo) return route.fulfill({ status: 503, json: { detail: "Falla simulada" } });
      const tipo = url.searchParams.get("tipo");
      const results = tipo === "provincia" ? [{ id: 1, nombre: "Provincia A", origen: "georef" }, { id: 4, nombre: "Provincia B", origen: "georef" }]
        : tipo === "partido" ? [{ id: 2, nombre: "Departamento A", origen: "georef" }]
          : [{ id: 3, nombre: "Localidad A", origen: "georef" }];
      return route.fulfill({ json: { results: url.searchParams.get("search") === "Ausente" ? [] : results, next: null, count: results.length } });
    }
    return route.fulfill({ json: {} });
  });
  await page.goto("/e2e/fixtures/issue136_geografia.html");
  return consultas;
}

async function elegir(page, nivel, nombre) {
  const campo = page.getByRole("combobox", { name: nivel, exact: true });
  await campo.click();
  await page.getByRole("option", { name: nombre, exact: true }).click();
  await expect(campo).toHaveValue(nombre);
}

test("un campo por nivel permite elegir con teclado sin enviar el formulario", async ({ page }) => {
  await preparar(page);
  await expect(page.getByRole("combobox")).toHaveCount(3);
  await expect(page.getByRole("combobox", { name: "Localidad", exact: true })).toBeDisabled();
  for (const [nivel, nombre] of [["Provincia", "Provincia A"], ["Partido / Departamento / Comuna", "Departamento A"], ["Localidad", "Localidad A"]]) {
    const campo = page.getByRole("combobox", { name: nivel, exact: true });
    await campo.focus();
    await expect(page.getByRole("option", { name: nombre, exact: true })).toBeVisible();
    await campo.press("ArrowDown");
    await expect(page.getByRole("option", { name: nombre, exact: true })).toHaveAttribute("aria-selected", "true");
    await campo.press("Enter");
    await expect(campo).toHaveValue(nombre);
    await expect(campo).toHaveAttribute("aria-expanded", "false");
  }
  await expect(page.getByLabel("Estado sintético")).toContainText('"localidad":{"id":3}');
});

test("salir sin elegir restaura la selección y no guarda el texto buscado", async ({ page }) => {
  await preparar(page);
  await elegir(page, "Provincia", "Provincia A");
  const campo = page.getByRole("combobox", { name: "Provincia", exact: true });
  await campo.fill("Provincia B");
  await page.getByRole("heading", { name: "Domicilio ficticio" }).click();
  await expect(campo).toHaveValue("Provincia A");
  await expect(campo).toHaveAttribute("aria-expanded", "false");
  const req = page.waitForRequest((r) => r.url().includes("domicilio-ficticio") && r.method() === "POST");
  await page.getByRole("button", { name: "Guardar domicilio ficticio" }).click();
  expect((await req).postDataJSON().geografia.provincia).toEqual({ id: 1 });
});

test("volver a elegir la misma provincia conserva partido y localidad confirmados", async ({ page }) => {
  await preparar(page);
  await elegir(page, "Provincia", "Provincia A");
  await elegir(page, "Partido / Departamento / Comuna", "Departamento A");
  await elegir(page, "Localidad", "Localidad A");
  await elegir(page, "Provincia", "Provincia A");
  await expect(page.getByLabel("Estado sintético")).toContainText('"localidad":{"id":3}');
  await expect(page.getByRole("button", { name: "Guardar domicilio ficticio" })).toBeEnabled();
});

test("Enter sin elegir resultado no envía la edición administrativa", async ({ page }) => {
  await preparar(page);
  let escrituras = 0;
  await page.route("**/api/financiadores/21/padron/45/", (route) => {
    escrituras++;
    return route.fulfill({ json: route.request().postDataJSON() });
  });
  await page.goto("/e2e/fixtures/issue136_geografia.html?modo=editar-afiliado");
  await page.getByRole("textbox", { name: "Calle", exact: true }).fill("Detalle de prueba");
  await page.getByRole("textbox", { name: "Motivo del cambio", exact: false }).fill("Corrección sintética");
  await expect(page.getByRole("button", { name: "Guardar cambios", exact: true })).toBeEnabled();
  const campo = page.getByRole("combobox", { name: "Provincia", exact: true });
  await campo.click();
  await expect(page.getByRole("option", { name: "Provincia A", exact: true })).toBeVisible();
  await campo.press("Enter");
  await campo.press("Escape");
  await expect(campo).toHaveValue("Provincia legada");
  await expect(page.getByRole("button", { name: "Guardar cambios", exact: true })).toBeVisible();
  expect(escrituras).toBe(0);
});

test("Escape cierra resultados y restaura el valor sin cerrar el modal de paciente", async ({ page }) => {
  await preparar(page);
  await page.goto("/e2e/fixtures/issue136_geografia.html?modo=editar-paciente");
  const campo = page.getByRole("combobox", { name: "Provincia", exact: true });
  await campo.fill("Provincia B");
  await expect(page.getByRole("listbox", { name: "Provincia", exact: true })).toBeVisible();
  await campo.press("Escape");
  await expect(page.getByRole("listbox")).toHaveCount(0);
  await expect(campo).toHaveValue("Provincia A");
  await expect(page.getByRole("dialog")).toBeVisible();
  await campo.press("Escape");
  await expect(page.getByText("Edición ficticia cancelada", { exact: true })).toBeVisible();
});

test("al escribir no ofrece resultados viejos mientras espera la búsqueda", async ({ page }) => {
  await preparar(page);
  await page.route("**/api/geografia/lugares/**", (route) => {
    const busqueda = new URL(route.request().url()).searchParams.get("search");
    return route.fulfill({ json: { results: [{ id: busqueda ? 4 : 1, nombre: busqueda ? "Provincia B" : "Provincia A", origen: "georef" }], next: null } });
  });
  const campo = page.getByRole("combobox", { name: "Provincia", exact: true });
  await campo.click();
  await expect(page.getByRole("option", { name: "Provincia A", exact: true })).toBeVisible();
  await campo.press("ArrowDown");
  await campo.fill("Provincia B");
  await campo.press("Enter");
  await expect(page.getByLabel("Estado sintético")).not.toContainText('"id":1');
  await expect(page.getByRole("option", { name: "Provincia A", exact: true })).toHaveCount(0);
  await page.getByRole("option", { name: "Provincia B", exact: true }).click();
  await expect(page.getByLabel("Estado sintético")).toContainText('"provincia":{"id":4}');
});

test("pagina resultados y vuelve a la primera página al reabrir", async ({ page }) => {
  await preparar(page);
  await page.route("**/api/geografia/lugares/**", (route) => {
    const segunda = new URL(route.request().url()).searchParams.get("page") === "2";
    return route.fulfill({ json: {
      results: [{ id: segunda ? 4 : 1, nombre: segunda ? "Provincia B" : "Provincia A", origen: "georef" }],
      next: segunda ? null : "/api/geografia/lugares/?page=2",
    } });
  });
  const campo = page.getByRole("combobox", { name: "Provincia", exact: true });
  await campo.click();
  await page.getByRole("button", { name: "Más resultados", exact: true }).click();
  await page.getByRole("option", { name: "Provincia B", exact: true }).click();
  await expect(campo).toHaveValue("Provincia B");
  await campo.click();
  await expect(page.getByRole("option", { name: "Provincia A", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Anteriores", exact: true })).toHaveCount(0);
});

test("una búsqueda inexistente se conserva al optar por carga manual", async ({ page }) => {
  await preparar(page);
  const campo = page.getByRole("combobox", { name: "Provincia", exact: true });
  await campo.fill("Ausente");
  await expect(page.getByText("No hay coincidencias.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Cargar manualmente", exact: true }).first().click();
  await expect(page.getByRole("textbox", { name: "Provincia · carga manual", exact: true })).toHaveValue("Ausente");
  await expect(page.getByLabel("Estado sintético")).toContainText('"provincia":{"manual":"Ausente"}');
  await page.getByRole("button", { name: "Buscar en catálogo", exact: true }).click();
  await expect(campo).toHaveValue("Ausente");
  await expect(page.getByText("Manual · sin verificar", { exact: true })).toBeVisible();
});

for (const ancho of [320, 460, 760, 1024]) {
  test(`ubicación se adapta a un contenedor de ${ancho}px en escritorio`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await preparar(page);
    const ubicacion = page.getByLabel("Ubicación territorial", { exact: true });
    await ubicacion.evaluate((elemento, ancho) => { elemento.style.width = `${ancho}px`; }, ancho);
    const medidas = await ubicacion.locator("input, select, button").evaluateAll((controles) => controles.map((control) => ({
      angosto: control.matches("input, select") && control.getBoundingClientRect().width < 240,
      desborda: control.scrollWidth > control.clientWidth + 1,
    })));
    expect(medidas.filter((m) => m.angosto || m.desborda)).toEqual([]);
  });
}

for (const modo of ["editar-paciente", "editar-afiliado"]) {
  for (const ancho of [390, 1440]) {
    test(`${modo} mantiene campos legibles a ${ancho}px`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width: ancho, height: 900 });
      await preparar(page);
      await page.goto(`/e2e/fixtures/issue136_geografia.html?modo=${modo}`);
      const ubicacion = page.getByLabel("Ubicación territorial", { exact: true });
      const limite = (await ubicacion.boundingBox()).width;
      const anchos = await ubicacion.locator("input, select").evaluateAll((controles) => controles.map((c) => c.getBoundingClientRect().width));
      expect(anchos.every((valor) => valor >= Math.min(240, limite) - 1)).toBeTruthy();
      expect(await ubicacion.evaluate((e) => e.scrollWidth <= e.clientWidth + 1)).toBeTruthy();
      await ubicacion.getByRole("combobox", { name: "Provincia", exact: true }).click();
      await expect(ubicacion.getByRole("option", { name: "Provincia A", exact: true })).toBeVisible();
      expect(await ubicacion.evaluate((e) => e.scrollWidth <= e.clientWidth + 1)).toBeTruthy();
      await ubicacion.screenshot({ path: testInfo.outputPath(`selector-${modo}-${ancho}.png`) });
    });
  }
}

test("búsqueda encadenada sólo consulta Salud y conserva filtros organizacionales", async ({ page }) => {
  const externas = [];
  page.on("request", (r) => { if (r.url().includes("apis.datos.gob.ar")) externas.push(r.url()); });
  const consultas = await preparar(page);
  await elegir(page, "Provincia", "Provincia A");
  await elegir(page, "Partido / Departamento / Comuna", "Departamento A");
  await elegir(page, "Localidad", "Localidad A");
  await expect(page.getByLabel("Estado sintético")).toContainText('"localidad":{"id":3}');
  expect(consultas.some((u) => u.searchParams.get("tipo") === "localidad" && u.searchParams.get("provincia") === "1" && u.searchParams.get("partido") === "2")).toBeTruthy();
  expect(consultas.every((u) => u.searchParams.get("organizacion") === "21" && u.searchParams.get("ambito") === "institucion")).toBeTruthy();
  expect(externas).toEqual([]);
});

test("API caída permite carga manual distinguida y guardado", async ({ page }) => {
  await preparar(page, true);
  await page.getByRole("combobox", { name: "Provincia", exact: true }).click();
  await expect(page.getByText("No se pudo consultar el catálogo.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Cargar manualmente", exact: true }).first().click();
  await page.getByLabel("Provincia · carga manual", { exact: true }).fill("Provincia ficticia");
  await expect(page.getByLabel("Estado sintético")).toContainText('"manual":"Provincia ficticia"');
  await expect(page.getByText("Manual · sin verificar. Se reutiliza sólo", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar domicilio ficticio" })).toBeEnabled();
  const req = page.waitForRequest((r) => r.url().includes("domicilio-ficticio") && r.method() === "POST");
  await page.getByRole("button", { name: "Guardar domicilio ficticio" }).click();
  expect((await req).postDataJSON().geografia.provincia).toEqual({ manual: "Provincia ficticia" });
});

test("lugar ausente permite manual y cambio de padre pide revisión sin borrar texto", async ({ page }) => {
  await preparar(page);
  await elegir(page, "Provincia", "Provincia A");
  await elegir(page, "Partido / Departamento / Comuna", "Departamento A");
  await page.getByRole("combobox", { name: "Localidad", exact: true }).fill("Ausente");
  await expect(page.getByText("No hay coincidencias.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Cargar manualmente", exact: true }).last().click();
  await page.getByLabel("Localidad · carga manual", { exact: true }).fill("Lugar rural ficticio");
  await elegir(page, "Provincia", "Provincia B");
  await expect(page.getByRole("button", { name: "Guardar domicilio ficticio" })).toBeDisabled();
  await expect(page.getByLabel("Estado sintético")).toContainText('"pendiente":true');
  await expect(page.getByRole("combobox", { name: "Localidad", exact: true })).toHaveValue("Lugar rural ficticio");
  await expect(page.getByRole("alert").first()).toContainText("Cambió una unidad anterior");
});

test("editar detalle de paciente mantiene la ubicación elegida explícitamente", async ({ page }) => {
  await preparar(page);
  let cuerpo;
  await page.route("**/api/ciudadanos/45/", (route) => { cuerpo = route.request().postDataJSON(); return route.fulfill({ json: cuerpo }); });
  await page.goto("/e2e/fixtures/issue136_geografia.html?modo=editar-paciente");
  await page.getByRole("textbox", { name: "Domicilio", exact: true }).fill("Nuevo detalle ficticio");
  await page.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(page.getByText("Edición ficticia guardada")).toBeVisible();
  expect(cuerpo.geografia.provincia).toEqual({ id: 1 });
});

test("editar otro campo del domicilio conserva legado sin convertirlo en manual", async ({ page }) => {
  await preparar(page);
  let cuerpo;
  await page.route("**/api/financiadores/21/padron/45/", (route) => { cuerpo = route.request().postDataJSON(); return route.fulfill({ json: cuerpo }); });
  await page.goto("/e2e/fixtures/issue136_geografia.html?modo=editar-afiliado");
  await expect(page.getByRole("combobox", { name: "Provincia", exact: true })).toHaveValue("Provincia legada");
  await expect(page.getByText("Sin homologar", { exact: true }).first()).toBeVisible();
  await page.getByRole("textbox", { name: "Calle", exact: true }).fill("Nuevo detalle ficticio");
  await page.getByRole("textbox", { name: "Motivo del cambio", exact: false }).fill("Corrección sintética de calle");
  await page.getByRole("button", { name: "Guardar cambios", exact: true }).click();
  await expect(page.getByText("Edición ficticia guardada")).toBeVisible();
  expect(cuerpo).toEqual({ calle: "Nuevo detalle ficticio", revision: 1, motivo: "Corrección sintética de calle" });
});
