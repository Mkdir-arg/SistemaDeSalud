import { expect, test } from "@playwright/test";

import { desbordaHorizontal, fallosDeContraste } from "./apoyo";

/**
 * Landing pública en / y el recorrido landing → login → destino según el rol.
 *
 * La API está interceptada entera: ningún test crea sesiones ni lee datos reales.
 * La landing en particular no debe pedir nada a la API.
 */
const lista = (results = []) => ({ count: results.length, next: null, previous: null, results });
const CENTRAL = { id: 1, nombre: "Hospital Central", tipo: "Hospital" };
const NORTE = { id: 2, nombre: "Hospital Norte", tipo: "Hospital" };

const USUARIOS = {
  plataforma: { id: 1, email: "plataforma@example.test", is_superuser: true, capacidades_por_institucion: {}, roles_por_institucion: {}, financiadores: [] },
  una: { id: 2, email: "una@example.test", is_superuser: false, capacidades_por_institucion: { 1: ["casos_operar"] }, roles_por_institucion: { 1: ["medico"] }, financiadores: [] },
  varias: { id: 3, email: "varias@example.test", is_superuser: false, capacidades_por_institucion: { 1: ["casos_operar"], 2: ["casos_operar"] }, roles_por_institucion: { 1: ["medico"], 2: ["medico"] }, financiadores: [] },
  financiador: { id: 4, email: "fin@example.test", is_superuser: false, capacidades_por_institucion: {}, roles_por_institucion: {}, financiadores: [{ id: 9, nombre: "Mutual de prueba" }] },
};
const INSTITUCIONES = { plataforma: [CENTRAL, NORTE], una: [CENTRAL], varias: [CENTRAL, NORTE], financiador: [] };

/** Intercepta la API como `quien`. Devuelve las rutas de API pedidas. */
async function simularApi(page, quien) {
  const pedidos = [];
  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const pathname = new URL(req.url()).pathname;
    // Vite también sirve /src/api/*.js: son módulos del frontend, no la API.
    if (!pathname.startsWith("/api/")) return route.continue();
    const path = pathname.replace(/^\/api/, "");
    pedidos.push(path);
    if (!quien) return route.fulfill({ status: 401, json: { detail: "Sin sesión" } });
    if (path === "/auth/token/") return route.fulfill({ json: { access: "token-ficticio-mock", refresh: "refresh-ficticio-mock" } });
    if (req.method() !== "GET") return route.fulfill({ status: 400, json: { detail: "Escritura no prevista bloqueada por la prueba" } });
    if (path === "/usuarios/me/") return route.fulfill({ json: USUARIOS[quien] });
    if (path === "/instituciones/") return route.fulfill({ json: lista(INSTITUCIONES[quien]) });
    if (path === "/notificaciones/resumen/") return route.fulfill({ json: { no_leidas: 0, recientes: [] } });
    if (path === "/instituciones/tablero-plataforma/") return route.fulfill({ json: { instituciones: 2, activas: 2, en_alta: 0, atendidos: 0, ocupacion: 0, personal_activo: 0, serie: [], alertas: [], indicadores: [] } });
    if (path === "/concesiones-financieras/mias/") return route.fulfill({ json: { superusuario: false, concesiones: [] } });
    return route.fulfill({ json: lista() });
  });
  return pedidos;
}

async function ingresar(page) {
  await page.fill('input[type="email"]', "persona@example.test");
  await page.fill('input[type="password"]', "clave-ficticia");
  await page.click('button[type="submit"]');
}

test.describe("Landing pública", () => {
  test("se ve sin sesión, sin armazón de la app y sin consultar la API", async ({ page }) => {
    const pedidos = await simularApi(page, null);
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1, name: /Salud conectada/ })).toBeVisible();
    await expect(page.getByText("Vista ilustrativa · datos de ejemplo")).toBeVisible();
    await expect(page.getByText(/Cifras de ejemplo/)).toBeVisible();
    await expect(page.locator("aside")).toHaveCount(0);
    await expect(page).toHaveURL(/\/$/);
    expect(pedidos).toEqual([]);
  });

  test("Ingresar e Ingresar al sistema llevan al login, y el login vuelve al inicio", async ({ page }) => {
    await simularApi(page, null);
    for (const nombre of ["Ingresar", "Ingresar al sistema"]) {
      await page.goto("/");
      await page.getByRole("link", { name: nombre, exact: true }).first().click();
      await expect(page).toHaveURL(/\/login$/);
    }
    await page.getByRole("link", { name: "Volver al inicio" }).click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { level: 1, name: /Salud conectada/ })).toBeVisible();
  });

  test("/presentacion es un alias de /", async ({ page }) => {
    await simularApi(page, null);
    await page.goto("/presentacion");
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { level: 1, name: /Salud conectada/ })).toBeVisible();
  });

  test("ningún enlace visible queda sin destino", async ({ page }) => {
    await simularApi(page, null);
    await page.goto("/");
    const enlaces = await page.locator("a:visible").evaluateAll((as) => as.map((a) => ({ texto: a.textContent.trim(), href: a.getAttribute("href") })));
    expect(enlaces.length).toBeGreaterThan(0);
    for (const { texto, href } of enlaces) {
      expect(href, texto).toBeTruthy();
      expect(href, texto).not.toBe("#");
      if (href.startsWith("#")) await expect(page.locator(href), texto).toHaveCount(1);
    }
    // Sin canal aprobado, la demo no aparece; la maqueta clínica sigue a mano.
    await expect(page.getByRole("link", { name: "Solicitar una demo" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: /Ver maqueta de la app clínica/ })).toHaveAttribute("href", "/demo/app-clinica");
  });

  test("se recorre con teclado desde la marca", async ({ page }) => {
    await simularApi(page, null);
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "HEN, inicio" })).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Cómo funciona" })).toBeFocused();
  });

  for (const tema of ["claro", "oscuro"]) {
    test(`contraste AA y sin desborde (${tema})`, async ({ page }) => {
      await simularApi(page, null);
      await page.addInitScript((t) => localStorage.setItem("salud.tema", t), tema);
      await page.goto("/");
      await expect(page.locator("html")).toHaveClass(tema === "oscuro" ? /\bdark\b/ : /^(?!.*\bdark\b)/);
      const fallos = await fallosDeContraste(page);
      expect(fallos, JSON.stringify(fallos, null, 2)).toEqual([]);
      for (const ancho of [375, 390, 1440]) {
        await page.setViewportSize({ width: ancho, height: 900 });
        await expect.poll(() => desbordaHorizontal(page), { message: `desborda a ${ancho}px` }).toBe(false);
      }
    });
  }

  test("el tema elegido en la landing se conserva en el login", async ({ page }) => {
    await simularApi(page, null);
    await page.addInitScript(() => { if (!localStorage.getItem("salud.tema")) localStorage.setItem("salud.tema", "claro"); });
    await page.goto("/");
    await page.getByRole("button", { name: "Cambiar a tema oscuro" }).click();
    await expect(page.locator("html")).toHaveClass(/\bdark\b/);
    await page.getByRole("link", { name: "Ingresar", exact: true }).click();
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.locator("html")).toHaveClass(/\bdark\b/);
    // Al recargar, lo aplica el script del <head> antes de que pinte React.
    await page.reload({ waitUntil: "domcontentloaded" });
    expect(await page.evaluate(() => document.documentElement.classList.contains("dark"))).toBe(true);
  });
});

test.describe("Ingreso según el rol", () => {
  test("plataforma entra al directorio, no a la landing", async ({ page }) => {
    await simularApi(page, "plataforma");
    await page.goto("/login");
    await ingresar(page);
    await expect(page).toHaveURL(/\/directorio$/);
    await expect(page.getByRole("heading", { name: "Instituciones", exact: true })).toBeVisible();
  });

  test("con una institución entra directo a su inicio", async ({ page }) => {
    await simularApi(page, "una");
    await page.goto("/login");
    await ingresar(page);
    await expect(page).toHaveURL(/\/inicio$/);
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("salud.institucion")).id)).toBe(1);
  });

  test("con varias instituciones elige entre las autorizadas", async ({ page }) => {
    await simularApi(page, "varias");
    await page.goto("/login");
    await ingresar(page);
    await expect(page).toHaveURL(/\/directorio$/);
    await expect(page.getByRole("heading", { name: "Elegí una institución" })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Ingresar a / })).toHaveCount(2);
    await page.getByRole("button", { name: "Ingresar a Hospital Norte" }).click();
    await expect(page).toHaveURL(/\/inicio$/);
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("salud.institucion")).id)).toBe(2);
  });

  test("el usuario solo financiador conserva su portal", async ({ page }) => {
    await simularApi(page, "financiador");
    await page.goto("/login");
    await ingresar(page);
    await expect(page).toHaveURL(/\/financiadores/);
  });

  test("un enlace profundo sin sesión vuelve a su destino después del login", async ({ page }) => {
    await simularApi(page, "una");
    await page.goto("/casos?estado=abierto");
    await expect(page).toHaveURL(/\/login$/);
    await ingresar(page);
    await expect(page).toHaveURL(/\/casos\?estado=abierto$/);
  });

  test("con sesión abierta el login no se muestra de nuevo", async ({ page }) => {
    await simularApi(page, "una");
    await page.addInitScript(() => sessionStorage.setItem("salud.access", "token-ficticio-mock"));
    await page.goto("/login");
    await expect(page).toHaveURL(/\/inicio$/);
  });

  test("una ruta desconocida no cae en la landing", async ({ page }) => {
    await simularApi(page, null);
    await page.goto("/no-existe");
    await expect(page).toHaveURL(/\/login$/);
  });
});
