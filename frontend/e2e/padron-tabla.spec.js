import { expect, test } from "@playwright/test";

const ruta = "/e2e/fixtures/padron-tabla.html";
const columna = (page, nombre) => page.getByRole("columnheader", { name: `Ordenar por ${nombre}`, exact: false });

test.beforeEach(async ({ page }) => {
  await page.route("**/__fixture_padron_consulta?**", (route) => route.fulfill({ json: {} }));
});

test("columnas por teclado, reload y restaurar conservan identidad y acciones", async ({ page }) => {
  await page.goto(`${ruta}?financiador=21&page=2`);
  const columnas = page.getByRole("button", { name: "Columnas visibles" });
  await expect(columnas).toContainText("5");
  await columnas.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("searchbox", { name: "Buscar columna" })).toBeFocused();
  await expect(page.getByRole("checkbox", { name: "Afiliado", exact: true })).toBeDisabled();
  await expect(page.getByRole("checkbox", { name: "N.º de afiliado", exact: true })).toBeDisabled();
  const localidad = page.getByRole("checkbox", { name: "Localidad", exact: true });
  await localidad.focus();
  await page.keyboard.press("Space");
  await expect(columna(page, "Localidad")).toBeVisible();
  await expect(page).toHaveURL(/columnas=/);
  await page.reload();
  await expect(columna(page, "Localidad")).toBeVisible();
  await expect(columnas).toContainText("6");
  await columnas.click();
  await page.getByRole("checkbox", { name: "Plan", exact: true }).uncheck();
  await expect(columna(page, "Plan")).toHaveCount(0);
  await expect(page.getByRole("columnheader", { name: "Acciones", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(columnas).toBeFocused();
  await page.getByRole("button", { name: "Editar Afiliado Ficticio A" }).click();
  await expect(page.getByLabel("Acción realizada")).toHaveText("Editar 1");
  await columnas.click();
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
  await page.getByRole("button", { name: /^Filtros/ }).click();
  await page.getByLabel("Filtrar Afiliado", { exact: true }).fill("Zeta");
  await expect(page.getByLabel("Consulta aplicada")).toContainText("flt_nombre=Zeta");
  expect(new URL(page.url()).searchParams.has("page")).toBe(false);
  // No filtra las filas ya cargadas: Portal hará otra consulta al backend.
  await expect(page.getByRole("link", { name: "Afiliado Ficticio A" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("button", { name: "Quitar filtro Afiliado: «Zeta»" })).toBeVisible();
  await page.getByRole("button", { name: /^Filtros/ }).click();
  await expect(page.getByLabel("Filtrar Afiliado", { exact: true })).toHaveValue("Zeta");
  await expect(columna(page, "Afiliado")).toHaveAttribute("aria-sort", "descending");
});

test("filtros de columna oculta se ven como chips y se pueden limpiar", async ({ page }) => {
  await page.goto(`${ruta}?page=3&flt_localidad=Río&flt_regimen=dependencia`);
  await expect(page.getByRole("button", { name: /^Filtros/ })).toContainText("2");
  await page.getByRole("button", { name: "Quitar filtro Régimen: Relación de dependencia" }).click();
  expect(new URL(page.url()).searchParams.has("flt_regimen")).toBe(false);
  // Un grupo con filtros aplicados abre desplegado, aunque la columna no se vea.
  await page.getByRole("button", { name: /^Filtros/ }).click();
  await expect(page.getByLabel("Filtrar Localidad", { exact: true })).toHaveValue("Río");
  await page.getByLabel("Filtrar Localidad", { exact: true }).fill("");
  await expect.poll(() => new URL(page.url()).searchParams.has("flt_localidad")).toBe(false);
  await expect(page.getByRole("button", { name: /^Quitar filtro/ })).toHaveCount(0);
});

test("filtrar no depende de las columnas visibles; buscar un dato y Escape", async ({ page }) => {
  await page.goto(`${ruta}?columnas=nombre,numero`);
  await page.getByRole("button", { name: /^Filtros/ }).click();
  await page.getByRole("searchbox", { name: "Buscar filtro" }).fill("nacimiento");
  await page.getByLabel("Fecha de nacimiento desde", { exact: true }).fill("2000-01-01");
  await expect(page.getByLabel("Consulta aplicada")).toContainText("flt_fecha_nacimiento_desde=2000-01-01");
  expect(new URL(page.url()).searchParams.get("columnas")).toBe("nombre,numero");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Filtros del padrón" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Filtros/ })).toBeFocused();
  await page.getByRole("button", { name: "Limpiar todo" }).click();
  expect(new URL(page.url()).searchParams.has("flt_fecha_nacimiento_desde")).toBe(false);
});

test("Estado global único respeta aliases finalizadas/futuras y los limpia al cambiar", async ({ page }) => {
  for (const derecho of ["finalizadas", "futuras"]) {
    await page.goto(`${ruta}?flt_derecho=${derecho}`);
    await expect(page.getByRole("combobox", { name: "Estado global" })).toHaveValue(derecho);
    const query = new URLSearchParams(await page.getByLabel("Consulta aplicada").textContent());
    expect(query.get("estado")).toBeNull();
    expect(query.get("flt_derecho")).toBe(derecho);
    await expect(page.getByRole("combobox", { name: "Filtrar Estado", exact: true })).toHaveCount(0);
    await page.getByRole("combobox", { name: "Estado global" }).selectOption("vigentes");
    await expect.poll(() => new URL(page.url()).searchParams.has("flt_derecho")).toBe(false);
    await expect(page.getByLabel("Consulta aplicada")).toContainText("estado=vigentes");
  }
});

test("ocho letras rápidas producen un GET aplicado y replace, export pendiente", async ({ page }) => {
  await page.clock.install();
  const pedidos = [];
  page.on("request", (r) => { if (r.url().includes("/__fixture_padron_consulta?")) pedidos.push(r); });
  await page.goto(ruta);
  await expect.poll(() => pedidos.length).toBe(1);
  const historial = await page.evaluate(() => history.length);
  await page.getByRole("button", { name: /^Filtros/ }).click();
  const campo = page.getByLabel("Filtrar Afiliado", { exact: true });
  await campo.pressSequentially("Gonzalez");
  await expect(campo).toHaveValue("Gonzalez");
  await expect(page.getByRole("button", { name: "Exportar ficticio" })).toBeDisabled();
  await expect(page.getByRole("status").filter({ hasText: "Aplicando filtros" })).toBeVisible();
  expect(pedidos).toHaveLength(1);
  await page.clock.runFor(300);
  await expect.poll(() => pedidos.length).toBe(2);
  expect(pedidos.at(-1).method()).toBe("GET");
  expect(new URL(pedidos.at(-1).url()).searchParams.get("flt_nombre")).toBe("Gonzalez");
  await expect(page.getByRole("button", { name: "Exportar ficticio" })).toBeEnabled();
  expect(await page.evaluate(() => history.length)).toBe(historial);
  await expect(page.getByLabel("Notificaciones pendientes")).toHaveText("3");
});

test("borrador conserva orden y otro select cambiados mientras espera", async ({ page }) => {
  await page.clock.install();
  await page.goto(`${ruta}?financiador=21&page=3`);
  await page.getByRole("button", { name: /^Filtros/ }).click();
  await page.getByLabel("Filtrar Afiliado", { exact: true }).fill("Alfa");
  await page.getByRole("button", { name: "Ordenar por Afiliado", exact: true }).click();
  await page.getByRole("button", { name: "Régimen y trabajo", exact: true }).click();
  await page.getByRole("combobox", { name: "Régimen", exact: true }).selectOption("monotributo");
  await expect(page.getByLabel("Filtrar Afiliado", { exact: true })).toHaveValue("Alfa");
  await page.clock.runFor(300);
  await expect(page.getByLabel("Consulta aplicada")).toContainText("flt_nombre=Alfa");
  const query = new URLSearchParams(await page.getByLabel("Consulta aplicada").textContent());
  expect(query.get("ordering")).toBe("nombre");
  expect(query.get("regimen")).toBe("monotributo");
  expect(query.get("page")).toBe("1");
});

test("Back cancela borrador y sincroniza el valor aplicado", async ({ page }) => {
  await page.clock.install();
  await page.goto(`${ruta}?flt_nombre=Previo`);
  await page.getByRole("button", { name: /^Filtros/ }).click();
  await page.getByRole("button", { name: "Ordenar por Afiliado", exact: true }).click();
  await page.getByLabel("Filtrar Afiliado", { exact: true }).fill("No aplicar");
  await page.goBack();
  await expect(page.getByLabel("Filtrar Afiliado", { exact: true })).toHaveValue("Previo");
  await page.clock.runFor(1000);
  await expect(page.getByLabel("Consulta aplicada")).not.toContainText("No+aplicar");
  await expect(page.getByRole("button", { name: "Exportar ficticio" })).toBeEnabled();
});

test("desmontar o cambiar organización cancela timer y pendientes", async ({ page }) => {
  await page.clock.install();
  for (const accion of ["Mostrar u ocultar tabla", "Cambiar organización"]) {
    await page.goto(`${ruta}?financiador=21`);
    await page.getByRole("button", { name: /^Filtros/ }).click();
    await page.getByLabel("Filtrar Afiliado", { exact: true }).fill("No aplicar");
    await expect(page.getByRole("button", { name: "Exportar ficticio" })).toBeDisabled();
    await page.getByRole("button", { name: accion, exact: true }).click();
    await page.clock.runFor(1000);
    expect(new URL(page.url()).searchParams.has("flt_nombre")).toBe(false);
    await expect(page.getByRole("button", { name: "Exportar ficticio" })).toBeEnabled();
  }
});

test("texto y número comparten un batch; volver al valor aplicado no consulta", async ({ page }) => {
  await page.clock.install();
  const pedidos = [];
  page.on("request", (r) => { if (r.url().includes("/__fixture_padron_consulta?")) pedidos.push(r); });
  await page.goto(`${ruta}?columnas=nombre,numero,titular`);
  await expect.poll(() => pedidos.length).toBe(1);
  await page.getByRole("button", { name: /^Filtros/ }).click();
  const nombre = page.getByLabel("Filtrar Afiliado", { exact: true });
  await nombre.fill("Descartar");
  await nombre.fill("");
  await page.clock.runFor(300);
  expect(pedidos).toHaveLength(1);
  await expect(page.getByRole("button", { name: "Exportar ficticio" })).toBeEnabled();
  await nombre.fill("Alfa");
  await page.getByRole("button", { name: "Grupo familiar", exact: true }).click();
  await page.getByRole("spinbutton", { name: "Filtrar ID del titular" }).pressSequentially("12345");
  expect(pedidos).toHaveLength(1);
  await page.clock.runFor(300);
  await expect.poll(() => pedidos.length).toBe(2);
  const query = new URL(pedidos.at(-1).url()).searchParams;
  expect(query.get("flt_titular")).toBe("12345");
  expect(query.get("flt_nombre")).toBe("Alfa");
});

test("fecha y select se aplican inmediatamente sin borrar texto pendiente", async ({ page }) => {
  await page.clock.install();
  await page.goto(`${ruta}?columnas=nombre,numero,fecha_nacimiento`);
  await page.getByRole("button", { name: /^Filtros/ }).click();
  await page.getByLabel("Filtrar Afiliado", { exact: true }).fill("Alfa");
  await page.getByRole("button", { name: "Identidad", exact: true }).click();
  await page.getByLabel("Fecha de nacimiento desde", { exact: true }).fill("2000-01-01");
  await expect(page.getByLabel("Consulta aplicada")).toContainText("flt_fecha_nacimiento_desde=2000-01-01");
  await expect(page.getByLabel("Consulta aplicada")).not.toContainText("flt_nombre");
  await page.clock.runFor(300);
  await expect(page.getByLabel("Consulta aplicada")).toContainText("flt_nombre=Alfa");
});

test("vacío, carga y error accesible conservan controles y reintento", async ({ page }) => {
  await page.goto(`${ruta}?modo=vacio`);
  await expect(page.getByText("Sin afiliados para estos filtros")).toBeVisible();
  await expect(page.getByRole("button", { name: "Columnas visibles" })).toContainText("5");
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
  await page.getByRole("button", { name: "Columnas visibles" }).click();
  await page.getByRole("checkbox", { name: "Localidad", exact: true }).check();
  await page.getByRole("button", { name: "Cerrar Columnas visibles" }).click();
  await page.getByRole("button", { name: "Ordenar por Localidad", exact: true }).click();
  await expect(columna(page, "Localidad")).toHaveAttribute("aria-sort", "ascending");
  await page.getByRole("button", { name: "Página siguiente" }).click();
  await expect(page).toHaveURL(/page=2/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("clic en el texto de una columna la marca sin cerrar el panel", async ({ page }) => {
  await page.goto(ruta);
  await page.getByRole("button", { name: "Columnas visibles" }).click();
  const panel = page.getByRole("dialog", { name: "Columnas visibles" });
  await panel.getByText("Localidad", { exact: true }).click();
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("checkbox", { name: "Localidad", exact: true })).toBeChecked();
  await panel.getByText("Documento", { exact: true }).click();
  await expect(columna(page, "Documento")).toBeVisible();
  await expect(panel).toBeVisible();
});

test("Limpiar todo vuelve al padrón entero y descarta lo que se estaba tipeando", async ({ page }) => {
  await page.clock.install();
  await page.goto(`${ruta}?flt_localidad=Río&search=Ana&plan=3`);
  await page.getByRole("button", { name: /^Filtros/ }).click();
  await page.getByLabel("Filtrar Afiliado", { exact: true }).fill("Zeta");
  await page.getByRole("button", { name: "Limpiar todo", exact: true }).click();
  await page.clock.runFor(1000);
  const url = new URL(page.url()).searchParams;
  for (const clave of ["flt_localidad", "flt_nombre", "search", "plan"]) expect(url.has(clave)).toBe(false);
  await expect(page.getByRole("searchbox", { name: "Buscar por afiliado, documento o nombre" })).toHaveValue("");
  await expect(page.getByLabel("Filtrar Afiliado", { exact: true })).toHaveValue("");
});

test("quitar un chip descarta el borrador del mismo filtro", async ({ page }) => {
  await page.clock.install();
  await page.goto(`${ruta}?flt_nombre=Previo`);
  await page.getByRole("button", { name: /^Filtros/ }).click();
  await page.getByLabel("Filtrar Afiliado", { exact: true }).fill("Otro");
  await page.getByRole("button", { name: "Quitar filtro Afiliado: «Previo»" }).click();
  await page.clock.runFor(1000);
  expect(new URL(page.url()).searchParams.has("flt_nombre")).toBe(false);
});
