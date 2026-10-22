import { expect, test } from "@playwright/test";

const ruta = "/e2e/fixtures/issue184_padron.html?estado=todos&columnas=nombre,numero,derecho,estado_administrativo&ordering=-numero&flt_localidad=Ficticia";

test("issue184: nombre vacío tiene enlace accesible y navega por teclado conservando configuración", async ({ page }) => {
  const errores = [];
  page.on("pageerror", (error) => errores.push(error.message));
  await page.goto(ruta);
  const enlace = page.getByRole("link", { name: "Sin informar", exact: true });
  await expect(enlace).toBeVisible();
  await enlace.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/ficha=1/);
  const params = new URL(page.url()).searchParams;
  expect(params.get("columnas")).toBe("nombre,numero,derecho,estado_administrativo");
  expect(params.get("ordering")).toBe("-numero");
  expect(params.get("flt_localidad")).toBe("Ficticia");
  await page.reload();
  await expect(enlace).toBeVisible();
  const fila = page.getByRole("row").filter({ has: enlace });
  await expect(fila.getByRole("cell", { name: "00001", exact: true })).toBeVisible();
  await expect(fila.getByRole("cell", { name: "constructor", exact: true })).toBeVisible();
  await expect(fila.getByRole("cell", { name: "Vigente", exact: true })).toHaveCount(0);
  expect(errores).toEqual([]);
});

test("issue184: derecho y administrativo conservan texto distinto y precedencia", async ({ page }) => {
  await page.goto(ruta);
  const administrativa = page.getByRole("row").filter({ hasText: "Registro Ficticio" });
  await expect(administrativa.getByRole("cell", { name: "Sólo administrativa", exact: true })).toBeVisible();
  await expect(administrativa.getByRole("cell", { name: "En trámite", exact: true })).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "Finalizada Ficticia" }).getByRole("cell", { name: "Finalizada", exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Estado", exact: true }).getByRole("option", { name: "Sólo registro administrativo", exact: true })).toHaveCount(1);
});

test("issue184: Escape devuelve foco y recarga conserva columnas y filtros", async ({ page }) => {
  await page.goto(ruta);
  const filtros = page.getByRole("button", { name: /^Filtros/ });
  await filtros.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("searchbox", { name: "Buscar filtro" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(filtros).toBeFocused();
  const columnas = page.getByRole("button", { name: "Columnas visibles" });
  await columnas.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("searchbox", { name: "Buscar columna" })).toBeFocused();
  await page.getByRole("checkbox", { name: "Localidad", exact: true }).check();
  await page.keyboard.press("Escape");
  await expect(columnas).toBeFocused();
  await page.reload();
  await expect(page.getByRole("button", { name: "Ordenar por Localidad", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Quitar filtro Localidad: «Ficticia»" })).toBeVisible();
});
