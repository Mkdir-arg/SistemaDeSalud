import { expect, test } from "@playwright/test";

/**
 * App de pacientes de demostración (/demo/app-clinica). No tiene API: todo vive
 * en sessionStorage, así que alcanza con Vite (`playwright.app-clinica.config.js`).
 *
 * El reloj se fija un martes a media mañana: la app ofrece turnos "de hoy" según
 * la hora, y sin esto el resultado dependería de cuándo se corre la suite.
 */
const BASE = "/demo/app-clinica";
const MARTES_10 = new Date("2026-09-29T10:00:00-03:00");

test.beforeEach(async ({ page }) => {
  await page.clock.install({ time: MARTES_10 });
  // La app no debe pedirle nada al backend; si lo hace, que falle a la vista.
  // Solo la ruta del backend: un patrón suelto también atrapa /src/api/*.js de Vite.
  await page.route(/^https?:\/\/[^/]+\/api\//, (ruta) => ruta.fulfill({ status: 500, body: "la app clínica no usa la API" }));
});

async function ingresar(page, dni = "34521521") {
  await page.goto(BASE);
  await page.getByRole("link", { name: "Ingresar con mi DNI" }).click();
  await page.getByLabel("Número de documento").fill(dni);
  await page.getByRole("button", { name: "Continuar" }).click();
}

async function codigo(page) {
  await page.getByLabel("Código de 4 dígitos").fill("5820");
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(`${BASE}/inicio`);
}

test("se ve como una app y no como la maqueta de un celular", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("salud.tema", "oscuro"));
  await page.goto(BASE);
  await expect(page.getByRole("heading", { name: /Te damos la bienvenida/ })).toBeVisible();
  for (const resto of ["9:41", "5G", "Explorar pantallas", "simulación"]) await expect(page.getByText(resto)).toHaveCount(0);
  // La app de la clínica mantiene su tema claro aunque la persona use oscuro en HEN.
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await expect(page.getByRole("link", { name: "Conocé HEN" })).toHaveAttribute("href", "/presentacion");
});

test("sin sesión, un link interno vuelve a la bienvenida", async ({ page }) => {
  await page.goto(`${BASE}/turnos`);
  await expect(page).toHaveURL(BASE);
  await page.goto(`${BASE}/no-existe`);
  await expect(page).toHaveURL(BASE);
});

test("paciente conocida: da presente, avanza en la fila y la llaman", async ({ page }) => {
  await ingresar(page);
  await expect(page.getByText("terminado en")).toContainText("21");
  await codigo(page);
  await expect(page.getByText("Tu turno de hoy")).toBeVisible();
  await expect(page.getByRole("link", { name: "Cómo llegar" })).toHaveAttribute("href", /google\.com\/maps/);

  await page.getByRole("link", { name: "Dar presente" }).click();
  await page.getByRole("link", { name: "Usar el QR de la entrada" }).click();
  await expect(page.getByRole("img", { name: "Código QR de presente" })).toBeVisible();
  await page.getByRole("button", { name: "Listo, ya lo escaneé" }).click();
  await expect(page).toHaveURL(/\/fila$/);
  await expect(page.getByText("3.º")).toBeVisible();

  // Una recarga no saca a nadie de la fila: la posición sale de la hora del presente.
  await page.reload();
  await expect(page.getByText("Estás en la fila")).toBeVisible();

  await page.clock.fastForward(25_000);
  await expect(page).toHaveURL(/\/llamado$/);
  await expect(page.getByRole("heading", { name: "Te están llamando" })).toBeVisible();
  await page.getByRole("button", { name: "Voy para allá" }).click();
  await expect(page.getByText("En consulta")).toBeVisible();
});

test("paciente nueva: alta, turno con su cobertura, cambio y cancelación", async ({ page }) => {
  await ingresar(page, "40111222");
  await expect(page.getByRole("heading", { name: "Es tu primera vez en la clínica" })).toBeVisible();
  await page.getByLabel("Nombre y apellido").fill("Lucía Fernández");
  await page.getByLabel("Fecha de nacimiento").fill("1994-02-03");
  await page.getByLabel("Celular").fill("11 4444-7788");
  await page.getByLabel("Cobertura").selectOption({ label: "Swiss Medical SMG20" });
  await page.getByRole("button", { name: "Continuar" }).click();
  await expect(page.getByText("terminado en")).toContainText("88");
  await codigo(page);

  await expect(page.getByRole("heading", { name: "Hola, Lucía" })).toBeVisible();
  await page.getByRole("link", { name: "Sacar turno" }).first().click();
  await page.getByRole("link", { name: /^Pediatría/ }).click();
  await page.getByRole("radio", { name: "Mañana" }).click();
  await page.locator("button[aria-pressed]").first().click();
  await page.getByRole("button", { name: /^Continuar con mañana/ }).click();
  await expect(page.getByText("Sin cargo con Swiss Medical SMG20")).toBeVisible();
  await page.getByRole("button", { name: "Confirmar turno" }).click();
  await expect(page.getByRole("heading", { name: /Tu turno quedó confirmado/ })).toBeVisible();

  const descarga = page.waitForEvent("download");
  await page.getByRole("button", { name: "Agregar al calendario" }).click();
  expect((await descarga).suggestedFilename()).toMatch(/^turno-pediatria-.*\.ics$/);

  // Reprogramar mantiene el mismo turno y lo mueve de día.
  await page.getByRole("link", { name: "Ver el turno" }).click();
  const detalle = page.url();
  await page.getByRole("link", { name: "Cambiar día u horario" }).click();
  await page.getByRole("radio").nth(3).click();
  await page.locator("button[aria-pressed]").last().click();
  await page.getByRole("button", { name: /^Continuar con/ }).click();
  await page.getByRole("button", { name: "Confirmar cambio" }).click();
  await expect(page.getByRole("heading", { name: "Listo, cambiamos tu turno" })).toBeVisible();
  await page.getByRole("link", { name: "Ver el turno" }).click();
  await expect(page).toHaveURL(detalle);

  await page.getByRole("link", { name: "Cancelar turno" }).click();
  await page.getByRole("button", { name: "Sí, cancelar turno" }).click();
  await expect(page.getByText("No tenés turnos próximos.")).toBeVisible();
  await page.getByRole("tab", { name: "Anteriores" }).click();
  await expect(page.getByText("Cancelado")).toBeVisible();
});

test("resultados: el informe se descarga en PDF y lleva al turno con quien lo pidió", async ({ page }) => {
  await ingresar(page);
  await codigo(page);
  await page.goto(`${BASE}/resultados`);
  await page.getByRole("link", { name: /Análisis de sangre completo/ }).click();
  await expect(page.getByText("Fuera de rango")).toHaveCount(2);
  const descarga = page.waitForEvent("download");
  await page.getByRole("button", { name: "Descargar informe (PDF)" }).click();
  expect((await descarga).suggestedFilename()).toMatch(/^laboratorio-.*\.pdf$/);
  await page.getByRole("link", { name: /Ver tu turno con Dra\. Paula Ríos/ }).click();
  await expect(page.getByRole("heading", { name: /Clínica médica/ })).toBeVisible();
});

test("la clínica y el perfil: teléfonos reales como links y cierre de sesión", async ({ page }) => {
  await ingresar(page);
  await codigo(page);
  await page.goto(`${BASE}/clinica`);
  await expect(page.getByRole("link", { name: "Llamar" })).toHaveAttribute("href", "tel:+541145550000");
  await page.goto(`${BASE}/perfil`);
  await expect(page.getByText("34.521.521")).toBeVisible();
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL(BASE);
  await page.goto(`${BASE}/inicio`);
  await expect(page).toHaveURL(BASE);
});
