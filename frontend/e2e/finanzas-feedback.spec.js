import { expect, test } from "@playwright/test";

async function entrarFinanzas(page, usuario = "admin") {
  const claveDemo = process.env.FINANZAS_DEMO_PASSWORD;
  if (!claveDemo) throw new Error("Definí FINANZAS_DEMO_PASSWORD con la clave local de la demo antes de ejecutar este recorrido.");
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(`finanzas.${usuario}@demo.local`);
  await page.locator('input[type="password"]').fill(claveDemo);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  await page.goto("/finanzas?mes=2026-09&tab=calendario");
  await expect(page.getByRole("heading", { name: "Finanzas y costos" }).last()).toBeVisible();
  await expect(page.locator("tbody tr").first()).toContainText("Demo");
}

test.beforeEach(async ({ page }) => entrarFinanzas(page));

test("mes y área actualizan automáticamente y sobreviven a recarga", async ({ page }) => {
  await expect(page.getByRole("button", { name: "Actualizar", exact: true })).toHaveCount(0);
  await expect(page.locator("p.uppercase").filter({ hasText: "Finanzas y costos" })).toHaveCount(0);
  await page.getByRole("combobox", { name: "Área", exact: true }).selectOption({ label: "Consultorios Demo" });
  await expect(page).toHaveURL(/area=\d+/);
  await page.reload();
  await expect(page.getByRole("combobox", { name: "Área", exact: true })).toHaveValue(/\d+/);
  await expect(page.getByLabel("Mes económico", { exact: true })).toHaveValue("2026-09");
  await expect(page.locator("tbody")).not.toContainText("Diagnóstico con diferencia");
});

test("ayuda se puede recorrer con mouse y cerrar con Escape sin desplazar contenido", async ({ page }) => {
  const boton = page.getByRole("button", { name: "Carga, aprobación y reparto", exact: true });
  const tablaAntes = await page.locator("table").boundingBox();
  await boton.hover();
  const ayuda = page.getByRole("dialog", { name: "Carga, aprobación y reparto", exact: true });
  await expect(ayuda).toBeVisible();
  await ayuda.hover();
  await expect(ayuda).toBeVisible();
  expect((await page.locator("table").boundingBox()).y).toBe(tablaAntes.y);
  await ayuda.getByRole("button", { name: "Cerrar Carga, aprobación y reparto" }).focus();
  await page.keyboard.press("Escape");
  await expect(ayuda).toHaveCount(0);
  await expect(boton).toBeFocused();
  await boton.click();
  await ayuda.getByRole("button", { name: "Cerrar Carga, aprobación y reparto" }).click();
  await expect(ayuda).toHaveCount(0);
  await page.getByRole("button", { name: "Agregar gasto esperado", exact: true }).click();
  const formulario = page.getByRole("dialog", { name: "Agregar gasto esperado", exact: true });
  await formulario.getByRole("button", { name: "Cómo funciona el control mensual", exact: true }).click();
  await page.keyboard.press("Escape");
  await expect(formulario).toBeVisible();
  await expect(page.getByRole("dialog", { name: "Cómo funciona el control mensual", exact: true })).toHaveCount(0);
});

test("todos los encabezados de datos envían el orden al servidor", async ({ page }) => {
  for (const [tab, recurso] of [["Control mensual", "/expectativas-gasto/calendario/"], ["Gastos registrados", "/gastos/"], ["Repartos", "/repartos-gasto/"]]) {
    await page.getByRole("tab", { name: tab, exact: true }).click();
    const botones = page.locator("thead button[aria-label^='Ordenar por']");
    for (let i = 0; i < await botones.count(); i += 1) {
      for (const sentido of ["ascending", "descending"]) {
        const solicitud = page.waitForResponse((r) => r.url().includes(recurso) && new URL(r.url()).searchParams.has("ordering"));
        await botones.nth(i).click();
        expect((await solicitud).status()).toBe(200);
        await expect(botones.nth(i).locator("..").locator("..")).toHaveAttribute("aria-sort", sentido);
      }
    }
  }
});

test("contador abre exactamente los gastos pendientes del área y concepto", async ({ page }) => {
  const fila = page.locator("tbody tr").filter({ hasText: "Electricidad" }).filter({ hasText: "Consultorios Demo" });
  const cantidad = Number((await fila.locator("td").nth(3).innerText()).split(" ")[0]);
  await fila.locator("td").nth(3).getByRole("button").click();
  await expect(page).toHaveURL(/tab=gastos/);
  await expect(page).toHaveURL(/gastos_f_estado_operativo=pendiente_aprobacion/);
  await expect(page.locator("tbody tr")).toHaveCount(cantidad);
  await expect(page.locator("tbody")).toContainText("Electricidad");
  await expect(page.locator("tbody")).not.toContainText("Reemplazado");
  await expect(page.getByRole("button", { name: "Quitar filtro Aprobación" })).toBeVisible();
});

test("rangos mantienen foco mientras cargan y se pueden quitar con cero resultados", async ({ page }) => {
  await page.getByRole("tab", { name: "Gastos registrados", exact: true }).click();
  await page.getByRole("button", { name: "Filtrar Importe original", exact: true }).click();
  const panel = page.getByRole("dialog", { name: "Filtrar Importe original", exact: true });
  await panel.getByLabel("Importe original (ARS) desde", { exact: true }).pressSequentially("999999");
  await expect(panel.getByLabel("Importe original (ARS) desde", { exact: true })).toHaveValue("999999");
  await expect(page).toHaveURL(/gastos_f_importe_min=999999/);
  await expect(page.getByText("Sin gastos visibles para este mes y área", { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Quitar filtro Importe original (ARS) desde", exact: true }).click();
  await expect(page.locator("tbody")).toContainText("Electricidad");
});

test("ajustes y reemplazos visibles; atribuciones conservan el total exacto", async ({ page }) => {
  await page.getByRole("tab", { name: "Gastos registrados", exact: true }).click();
  const ajuste = page.locator("tbody tr").filter({ has: page.getByRole("button", { name: "Ver 1 ajuste", exact: true }) });
  await expect(ajuste).toContainText("ARS -250,00");
  await expect(ajuste).toContainText("ARS 9.750,00");
  await page.getByRole("button", { name: /^Reemplazado por #/ }).first().click();
  await expect(page.getByRole("dialog")).toContainText("Reemplaza #");
  await page.keyboard.press("Escape");
  await page.getByRole("tab", { name: "Repartos", exact: true }).click();
  await expect(page.locator("tbody tr").filter({ hasText: "Mantenimiento" })).toContainText("Sin asignaciones");
  const reparto = page.locator("tbody tr").filter({ hasText: "Electricidad" });
  await reparto.getByRole("button", { name: /Ver 4 atenciones/ }).click();
  const detalle = page.getByRole("region", { name: /Atenciones del reparto/ });
  await expect(detalle).toContainText("ARS 30.000,01");
  await expect(detalle.getByText("Total distribuido", { exact: true }).locator("..").getByRole("definition")).toHaveText("ARS 30.000,01");
  await expect(detalle.locator("tbody tr")).toHaveCount(4);
  await expect(detalle.locator("tbody")).toContainText("ARS 7.500,01");
  await expect(detalle.locator("tbody")).toContainText("Consultorios Demo");
});

test("institucional filtra repartos sin mezclar áreas", async ({ page }) => {
  await page.getByRole("combobox", { name: "Área", exact: true }).selectOption("null");
  await page.getByRole("tab", { name: "Repartos", exact: true }).click();
  await expect(page.locator("tbody")).toContainText("Limpieza institucional");
  await expect(page.locator("tbody")).not.toContainText("Consultorios Demo");
});

test("perfil de área no ve remuneraciones ni detalle de costos sin autorización", async ({ page }) => {
  await page.getByRole("button", { name: "Cerrar sesión", exact: true }).click();
  await entrarFinanzas(page, "area");
  await expect(page.getByRole("button", { name: "Configurar repartos", exact: true })).toHaveCount(0);
  await page.getByRole("tab", { name: "Gastos registrados", exact: true }).click();
  await expect(page.locator("tbody")).not.toContainText("Remuneraciones");
  await expect(page.getByRole("button", { name: "Aprobar", exact: true })).toHaveCount(0);
  await page.getByRole("tab", { name: "Repartos", exact: true }).click();
  await page.getByRole("button", { name: /Ver 4 atenciones/ }).first().click();
  await expect(page.getByText("No tenés autorización para ver el detalle de las atenciones de este reparto.", { exact: true })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Referencia de atención", exact: true })).toHaveCount(0);
});

test("tablas y ayudas mantienen el ancho disponible en móvil", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const tab of ["Control mensual", "Gastos registrados", "Repartos"]) {
    await page.getByRole("tab", { name: tab, exact: true }).click();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  }
  await page.getByRole("button", { name: "Cómo leer un reparto", exact: true }).click();
  const panel = page.getByRole("dialog", { name: "Cómo leer un reparto", exact: true });
  await expect(panel).toBeVisible();
  const cuadro = await panel.boundingBox();
  expect(cuadro.x).toBeGreaterThanOrEqual(0);
  expect(cuadro.x + cuadro.width).toBeLessThanOrEqual(390);
  await page.keyboard.press("Escape");
  await expect(panel).toHaveCount(0);
});

test("importe de reparto no descarta silenciosamente decimales inválidos", async ({ page }) => {
  await page.getByRole("tab", { name: "Repartos", exact: true }).click();
  await page.getByRole("button", { name: "Filtrar Importe", exact: true }).click();
  const panel = page.getByRole("dialog", { name: "Filtrar Importe", exact: true });
  const minimo = panel.getByLabel("Importe (ARS) desde", { exact: true });
  const valido = page.waitForResponse((r) => r.url().includes("/repartos-gasto/") && new URL(r.url()).searchParams.get("saldo_centavos_min") === "-1");
  await minimo.fill("-0.01");
  expect((await valido).status()).toBe(200);
  const invalido = page.waitForResponse((r) => r.url().includes("/repartos-gasto/") && new URL(r.url()).searchParams.get("saldo_centavos_min") === "importe_invalido");
  await minimo.fill("1.000");
  expect((await invalido).status()).toBe(400);
  await expect(panel.getByRole("alert")).toContainText("hasta dos decimales");
  await expect(page.locator("tbody")).not.toContainText("Electricidad");
  await minimo.fill("0.01");
  await expect(panel.getByRole("alert")).toHaveCount(0);
  await expect(page.locator("tbody")).toContainText("Electricidad");
});

test("importe de gasto rechaza exponente cuando indica un rango inválido", async ({ page }) => {
  await page.getByRole("tab", { name: "Gastos registrados", exact: true }).click();
  await page.getByRole("button", { name: "Filtrar Importe original", exact: true }).click();
  const panel = page.getByRole("dialog", { name: "Filtrar Importe original", exact: true });
  const respuesta = page.waitForResponse((r) => r.url().includes("/gastos/") && new URL(r.url()).searchParams.get("importe_min") === "importe_invalido");
  await panel.getByLabel("Importe original (ARS) desde", { exact: true }).fill("1e3");
  expect((await respuesta).status()).toBe(400);
  await expect(panel.getByRole("alert")).toContainText("sin notación exponencial");
  await expect(page.locator("tbody")).not.toContainText("Electricidad");
});
