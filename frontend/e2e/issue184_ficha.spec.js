import { expect, test } from "@playwright/test";

const lista = (results) => ({ count: results.length, next: null, previous: null, results });
async function ficha(page, cambios, historial = []) {
  const org = { id: 21, nombre: "Financiador ficticio #184", tipo: "mutual", rol: "operador" };
  const persona = { id: 45, nombre: "Persona ficticia #184", numero: "00045", documento: "99018445", desde: "2026-01-01", plan: null, revision: 1, permisos: {}, ...cambios };
  await page.addInitScript(() => { sessionStorage.setItem("salud.access", "token-ficticio"); sessionStorage.setItem("salud.refresh", "refresh-ficticio"); });
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith("/api/")) return route.continue();
    if (path === "/api/usuarios/me/") return route.fulfill({ json: { id: 9, nombre_completo: "Operador ficticio", capacidades_por_institucion: {}, roles_por_institucion: {}, financiadores: [org] } });
    if (path === "/api/financiadores/") return route.fulfill({ json: lista([org]) });
    if (path === "/api/financiadores/21/ficha-afiliado/") return route.fulfill({ json: { ...lista([]), afiliado: persona, cupos: [], historial: [] } });
    if (path === "/api/financiadores/21/padron/45/") return route.fulfill({ json: persona });
    if (path.endsWith("/historial/")) {
      const pagina = new URL(route.request().url()).searchParams.get("page") || "1";
      return route.fulfill({ json: Array.isArray(historial) ? lista(historial) : historial[pagina] });
    }
    if (path.endsWith("/familia/")) return route.fulfill({ json: { titular: persona, integrantes: [] } });
    return route.fulfill({ json: lista([]) });
  });
  await page.goto("/financiadores/padron/45?financiador=21");
  await expect(page.getByRole("paragraph").filter({ hasText: /^Persona ficticia #184$/ })).toBeVisible();
}

for (const caso of [
  { nombre: "administrativa no anuncia vigencia ni aviso de derechos", datos: { estado: "vigente", vigente: true, cobertura_habilitada: false, fin_prestacional_informado: "2026-10-01" }, cabecera: "Sólo administrativa", derechos: "Sin habilitar · sólo registro administrativo" },
  { nombre: "finalización precede a cobertura deshabilitada", datos: { estado: "finalizada", vigente: false, cobertura_habilitada: false, finalizado_en: "2026-10-01T12:00:00Z" }, cabecera: "Finalizada", derechos: "Finalizados" },
  { nombre: "derecho ausente no se presenta como futuro", datos: { cobertura_habilitada: true }, cabecera: "Sin informar", derechos: "Sin informar" },
  { nombre: "futura habilitada conserva su estado", datos: { estado: "futura", vigente: false, cobertura_habilitada: true }, cabecera: "Aún no vigente", derechos: "Aún no vigentes" },
]) {
  test(`issue184: ficha ${caso.nombre}`, async ({ page }) => {
    await ficha(page, caso.datos);
    // La cabecera contiene el título y resumen, antes de las pestañas.
    const cabecera = page.getByRole("heading", { name: "Ficha del afiliado", exact: true }).locator("../..");
    await expect(cabecera.getByText(caso.cabecera, { exact: true })).toBeVisible();
    await expect(page.getByText("Derechos actuales", { exact: true }).locator("..").locator("dd")).toHaveText(caso.derechos);
    if (caso.datos.cobertura_habilitada === false) {
      await expect(cabecera.getByText("Vigente", { exact: true })).toHaveCount(0);
      await expect(page.getByRole("status").filter({ hasText: "los derechos siguen vigentes" })).toHaveCount(0);
    }
  });
}


test("issue184: historial conserva autor motivo desconocidos y navegación sin alterar derechos", async ({ page }) => {
  const evento = { tipo: "actualizacion", registrado: "2026-03-01T12:00:00Z", usuario_nombre: "Operador ficticio 184", origen: "importacion", lote: 184,
    motivo: "Revisión ficticia de antecedentes", cambios: { causa_baja: { anterior: "constructor", nuevo: "otra" }, alta_administrativa: { anterior: null, nuevo: "2026-03-01" } } };
  const primera = Array.from({ length: 10 }, (_, i) => ({ ...evento, id: i + 1 }));
  await ficha(page, { estado: "vigente", cobertura_habilitada: false, vigente: true }, {
    "1": { count: 11, next: "?page=2", previous: null, results: primera },
    "2": { count: 11, next: null, previous: "?page=1", results: [{ ...evento, id: 11, motivo: "Último antecedente ficticio" }] },
  });
  const tab = page.getByRole("tab", { name: "Historial", exact: true });
  await tab.focus();
  await page.keyboard.press("Enter");
  const historia = page.getByRole("region", { name: "Historia administrativa", exact: true });
  await expect(historia.getByRole("listitem")).toHaveCount(10);
  const primerEvento = historia.getByRole("listitem").first();
  await expect(primerEvento).toContainText("Registrado por Operador ficticio 184");
  await expect(primerEvento).toContainText("Motivo: Revisión ficticia de antecedentes");
  await expect(primerEvento).toContainText("Origen: Importación de padrón · Lote 184");
  await expect(primerEvento.getByText("constructor", { exact: true })).toBeVisible();
  await expect(primerEvento.getByText("Otra", { exact: true })).toBeVisible();
  await expect(primerEvento.getByText("01/03/2026", { exact: true })).toBeVisible();
  await historia.getByRole("button", { name: "Siguiente", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(historia.getByRole("listitem")).toHaveCount(1);
  await expect(historia).toContainText("Motivo: Último antecedente ficticio");
  await expect(historia.getByRole("button", { name: "Siguiente", exact: true })).toBeDisabled();
  await historia.getByRole("button", { name: "Anterior", exact: true }).click();
  await expect(historia.getByRole("listitem")).toHaveCount(10);
  const cabecera = page.getByRole("heading", { name: "Ficha del afiliado", exact: true }).locator("../..");
  await expect(cabecera.getByText("Sólo administrativa", { exact: true })).toBeVisible();
  await expect(cabecera.getByText("Vigente", { exact: true })).toHaveCount(0);
});
