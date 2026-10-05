import { expect, test } from "@playwright/test";

const institucion = { id: 2, nombre: "Hospital de prueba", tipo: "Hospital", estado: "activo", activa: true };
const lista = (results = []) => ({ count: results.length, next: null, previous: null, results });
const resumen = { casos_activos: 12, urgentes: 2, en_cola: 3, espera_prom_min: 35, turnos_periodo: 18, turnos_ausentes: 4, turnos_sin_registrar: 1, cerrados: 8, ingresos: 15, camas_total: 10, camas_operativas: 8, camas_ocupadas: 6, ocupacion_camas: 75 };

// Sin `supervision` el usuario conserva `config_institucional`: con sólo
// `casos_operar` es un operador puro y /inicio muestra «Mi trabajo» (App.jsx).
async function escenario(page, supervision) {
  const pedidosTablero = [];
  await page.addInitScript((inst) => {
    sessionStorage.setItem("salud.access", "token-ficticio-mock");
    sessionStorage.setItem("salud.refresh", "refresh-ficticio-mock");
    localStorage.setItem("salud.institucion", JSON.stringify(inst));
    localStorage.removeItem("salud.menu");
  }, institucion);
  await page.route("**/api/**", (route) => {
    const url = new URL(route.request().url());
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const path = url.pathname.replace(/^\/api/, "");
    if (path === "/usuarios/me/") return route.fulfill({ json: { id: 7, email: "prueba@example.test", nombre_completo: "Persona de prueba", is_superuser: false, capacidades_por_institucion: { 2: supervision ? ["supervision", "config_institucional", "casos_operar", "turnos"] : ["config_institucional", "casos_operar", "turnos"] }, roles_por_institucion: { 2: [supervision ? "admin" : "administrativo"] }, financiadores: [] } });
    if (path === "/instituciones/") return route.fulfill({ json: lista([institucion]) });
    if (path === "/instituciones/2/metricas/") return route.fulfill({ json: { staff: 5, areas: 2, casos_activos: 12, turnos_hoy: 3 } });
    if (path === "/instituciones/2/puesta-en-marcha/") return route.fulfill({ json: { areas: true, usuarios: true, asignaciones: true, agenda_profesional: true, agenda_recurso: true, flujo_operativo: false } });
    if (path === "/instituciones/2/tablero/") {
      pedidosTablero.push(url);
      return route.fulfill({ json: { periodo: { desde: url.searchParams.get("desde"), hasta: url.searchParams.get("hasta"), agrupacion: "dia" }, resumen, serie_ingresos: [{ fecha: "2026-09-29", casos: 3 }], por_area: [{ area_id: 1, nombre: "Guardia", activos: 8, en_cola: 3 }, { area_id: 2, nombre: "Consultorios", activos: 4, en_cola: 0 }] } });
    }
    if (path === "/notificaciones/resumen/") return route.fulfill({ json: { no_leidas: 0, items: [] } });
    if (path === "/mis-tareas/") return route.fulfill({ json: { tareas: [], filas: [] } });
    if (path === "/concesiones-financieras/mias/") return route.fulfill({ json: { superusuario: false, concesiones: [] } });
    return route.fulfill({ json: route.request().method() === "GET" ? lista([]) : {} });
  });
  return pedidosTablero;
}

test("administración ve el resumen operativo y el enlace al tablero", async ({ page }) => {
  const pedidos = await escenario(page, true);
  await page.goto("/inicio");
  await expect(page.getByRole("heading", { name: "Casos activos" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Operación" })).toBeVisible();
  await expect(page.getByText("Urgentes", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /Ver tablero completo/ })).toHaveAttribute("href", "/dashboard");
  await expect(page.getByRole("heading", { name: "Carga por área" })).toBeVisible();
  expect(pedidos).toHaveLength(1);
  expect(pedidos[0].searchParams.get("desde")).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  expect(pedidos[0].searchParams.get("hasta")).toMatch(/^\d{4}-\d{2}-\d{2}$/);
});

test("sin supervisión conserva las cuatro métricas y no consulta el tablero", async ({ page }) => {
  const pedidos = await escenario(page, false);
  await page.goto("/inicio");
  await expect(page.getByRole("heading", { name: "Personal activo" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Operación" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: /Ver tablero completo/ })).toHaveCount(0);
  expect(pedidos).toHaveLength(0);
});

test("la ayuda abre y cierra con teclado y Escape", async ({ page }) => {
  await escenario(page, true);
  await page.goto("/inicio");
  const ayuda = page.getByRole("button", { name: "Ayuda sobre Requiere atención" });
  await ayuda.focus();
  await page.keyboard.press("Enter");
  await expect(ayuda).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("tooltip")).toContainText("turnos pasados");
  await page.keyboard.press("Escape");
  await expect(ayuda).toHaveAttribute("aria-expanded", "false");
  await page.keyboard.press("Space");
  await expect(ayuda).toHaveAttribute("aria-expanded", "true");
  await page.keyboard.press("Space");
  await expect(ayuda).toHaveAttribute("aria-expanded", "false");
});

test("un grupo cerrado conserva sus enlaces sin permitir foco", async ({ page }) => {
  await escenario(page, true);
  await page.goto("/inicio");
  const nav = page.getByRole("navigation", { name: "Menú principal" });
  const grupo = nav.getByRole("button", { name: "DIRECCIÓN" });
  await expect(grupo).toHaveAttribute("aria-expanded", "false");
  const enlace = nav.locator('a[href="/dashboard"]');
  await expect(enlace).toHaveCount(1);
  await expect(enlace.locator("xpath=..")).toHaveAttribute("inert", "");
  await grupo.focus();
  await page.keyboard.press("Tab");
  expect(await enlace.evaluate((elemento) => elemento === document.activeElement)).toBe(false);
});
