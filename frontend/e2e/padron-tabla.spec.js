import { expect, test } from "@playwright/test";

const ruta = "/e2e/fixtures/padron-tabla.html";
const columna = (page, nombre) => page.getByRole("columnheader", { name: `Ordenar por ${nombre}`, exact: false });

test("columnas por teclado, reload y restaurar conservan identidad y acciones", async ({ page }) => {
  await page.goto(`${ruta}?financiador=21&page=2`);
  const summary = page.getByText("Columnas visibles (5)", { exact: true });
  await summary.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("checkbox", { name: "Afiliado", exact: true })).toBeDisabled();
  await expect(page.getByRole("checkbox", { name: "N.º de afiliado", exact: true })).toBeDisabled();
  const localidad = page.getByRole("checkbox", { name: "Localidad", exact: true });
  await localidad.focus();
  await page.keyboard.press("Space");
  await expect(columna(page, "Localidad")).toBeVisible();
  await expect(page).toHaveURL(/columnas=/);
  await page.reload();
  await expect(columna(page, "Localidad")).toBeVisible();
  await page.getByText("Columnas visibles (6)", { exact: true }).click();
  await page.getByRole("checkbox", { name: "Plan", exact: true }).uncheck();
  await expect(columna(page, "Plan")).toHaveCount(0);
  await expect(page.getByRole("columnheader", { name: "Acciones", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Editar Afiliado Ficticio A" }).click();
  await expect(page.getByLabel("Acción realizada")).toHaveText("Editar 1");
  await page.getByRole("button", { name: "Restaurar columnas" }).click();
  await expect(columna(page, "Localidad")).toHaveCount(0);
  await expect(columna(page, "Plan")).toBeVisible();
  await expect(page).toHaveURL(/page=2/);
});

test("orden asc/desc y filtros se comunican al servidor, página1 en URL", async ({ page }) => {
  await page.goto(`${ruta}?financiador=21&page=3&padron_page=3&ordering=numero`);
  await page.getByRole("button", { name: "Ordenar por Afiliado", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(columna(page, "Afiliado")).toHaveAttribute("aria-sort", "ascending");
  await expect(page.getByLabel("Consulta aplicada")).toContainText("ordering=nombre");
  expect(new URL(page.url()).searchParams.has("page")).toBe(false);
  expect(new URL(page.url()).searchParams.has("padron_page")).toBe(false);
  await page.getByRole("button", { name: "Ordenar por Afiliado (ascendente)" }).click();
  await expect(columna(page, "Afiliado")).toHaveAttribute("aria-sort", "descending");
  await page.getByRole("button", { name: "Página siguiente" }).click();
  await expect(page).toHaveURL(/page=2/);
  await page.getByText("Filtros administrativos", { exact: true }).click();
  await page.getByLabel("Filtrar Afiliado", { exact: true }).fill("Zeta");
  await expect(page.getByLabel("Consulta aplicada")).toContainText("flt_nombre=Zeta");
  expect(new URL(page.url()).searchParams.has("page")).toBe(false);
  // No filtra las filas ya cargadas: Portal hará otra consulta al backend.
  await expect(page.getByRole("link", { name: "Afiliado Ficticio A" })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Filtrar Afiliado", { exact: true })).toHaveValue("Zeta");
  await expect(columna(page, "Afiliado")).toHaveAttribute("aria-sort", "descending");
});

test("filtros de columna oculta siguen visibles y se pueden limpiar", async ({ page }) => {
  await page.goto(`${ruta}?page=3&flt_localidad=Río&flt_regimen=dependencia`);
  await expect(page.getByLabel("Filtrar Localidad", { exact: true })).toHaveValue("Río");
  await expect(page.getByRole("combobox", { name: "Filtrar Régimen", exact: true })).toHaveValue("dependencia");
  await page.getByLabel("Filtrar Localidad", { exact: true }).fill("");
  expect(new URL(page.url()).searchParams.has("flt_localidad")).toBe(false);
  await page.getByRole("combobox", { name: "Filtrar Régimen", exact: true }).selectOption("");
  expect(new URL(page.url()).searchParams.has("flt_regimen")).toBe(false);
});

test("vacío, carga y error accesible conservan controles y reintento", async ({ page }) => {
  await page.goto(`${ruta}?modo=vacio`);
  await expect(page.getByText("Sin afiliados para estos filtros")).toBeVisible();
  await expect(page.getByText("Columnas visibles (5)", { exact: true })).toBeVisible();
  await page.goto(`${ruta}?modo=cargando`);
  await expect(page.getByRole("status", { name: "Cargando…" })).toBeVisible();
  await page.goto(`${ruta}?modo=error`);
  await expect(page.getByRole("alert")).toContainText("Consulta rechazada");
  await page.getByRole("button", { name: "Reintentar" }).click();
  await expect(page.getByRole("link", { name: "Afiliado Ficticio A" })).toBeVisible();
});

test("móvil permite elegir, ordenar y paginar sin scroll global", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(ruta);
  await page.getByText("Columnas visibles (5)", { exact: true }).click();
  await page.getByRole("checkbox", { name: "Localidad", exact: true }).check();
  await page.getByText("Columnas visibles (6)", { exact: true }).click();
  await page.getByRole("button", { name: "Ordenar por Localidad", exact: true }).click();
  await expect(columna(page, "Localidad")).toHaveAttribute("aria-sort", "ascending");
  await page.getByRole("button", { name: "Página siguiente" }).click();
  await expect(page).toHaveURL(/page=2/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
