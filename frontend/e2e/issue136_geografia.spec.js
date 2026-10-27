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

test("búsqueda encadenada sólo consulta Salud y conserva filtros organizacionales", async ({ page }) => {
  const externas = [];
  page.on("request", (r) => { if (r.url().includes("apis.datos.gob.ar")) externas.push(r.url()); });
  const consultas = await preparar(page);
  await page.getByRole("combobox", { name: "Elegir provincia", exact: true }).selectOption("1");
  await page.getByRole("combobox", { name: "Elegir partido / departamento / comuna", exact: true }).selectOption("2");
  await page.getByRole("combobox", { name: "Elegir localidad", exact: true }).selectOption("3");
  await expect(page.getByLabel("Estado sintético")).toContainText('"localidad":{"id":3}');
  expect(consultas.some((u) => u.searchParams.get("tipo") === "localidad" && u.searchParams.get("provincia") === "1" && u.searchParams.get("partido") === "2")).toBeTruthy();
  expect(consultas.every((u) => u.searchParams.get("organizacion") === "21" && u.searchParams.get("ambito") === "institucion")).toBeTruthy();
  expect(externas).toEqual([]);
});

test("API caída permite carga manual distinguida y guardado", async ({ page }) => {
  await preparar(page, true);
  await expect(page.getByText("No se pudo consultar el catálogo.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Cargar manualmente", exact: true }).first().click();
  await page.getByLabel("Provincia · carga manual", { exact: true }).fill("Provincia ficticia");
  await expect(page.getByLabel("Estado sintético")).toContainText('"manual":"Provincia ficticia"');
  await expect(page.getByText("Manual · sin verificar. Ingresá sólo", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar domicilio ficticio" })).toBeEnabled();
  const req = page.waitForRequest((r) => r.url().includes("domicilio-ficticio") && r.method() === "POST");
  await page.getByRole("button", { name: "Guardar domicilio ficticio" }).click();
  expect((await req).postDataJSON().geografia.provincia).toEqual({ manual: "Provincia ficticia" });
});

test("lugar ausente permite manual y cambio de padre pide revisión sin borrar texto", async ({ page }) => {
  await preparar(page);
  await page.getByRole("combobox", { name: "Elegir provincia", exact: true }).selectOption("1");
  await page.getByRole("combobox", { name: "Elegir partido / departamento / comuna", exact: true }).selectOption("2");
  await page.getByLabel("Buscar localidad", { exact: true }).fill("Ausente");
  await expect(page.getByText("No hay coincidencias.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Cargar manualmente", exact: true }).last().click();
  await page.getByLabel("Localidad · carga manual", { exact: true }).fill("Lugar rural ficticio");
  await page.getByRole("combobox", { name: "Elegir provincia", exact: true }).selectOption("4");
  await expect(page.getByRole("button", { name: "Guardar domicilio ficticio" })).toBeDisabled();
  await expect(page.getByLabel("Estado sintético")).toContainText('"pendiente":true');
  await expect(page.getByText("Lugar rural ficticio · Revisar selección")).toBeVisible();
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
  await expect(page.getByText("Provincia legada", { exact: false })).toBeVisible();
  await page.getByRole("textbox", { name: "Calle", exact: true }).fill("Nuevo detalle ficticio");
  await page.getByRole("textbox", { name: "Motivo del cambio", exact: false }).fill("Corrección sintética de calle");
  await page.getByRole("button", { name: "Guardar cambios", exact: true }).click();
  await expect(page.getByText("Edición ficticia guardada")).toBeVisible();
  expect(cuerpo).toEqual({ calle: "Nuevo detalle ficticio", revision: 1, motivo: "Corrección sintética de calle" });
});
