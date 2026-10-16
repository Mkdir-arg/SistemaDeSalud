import { expect, test } from "@playwright/test";

const ID = 910012;
const campo = { id: 910020, formulario: ID, label: "Dato sintético", tipo: "texto_corto", tipo_display: "Texto corto", requerido: false, ayuda: "", opciones: [], orden: 0, valores_cargados: 0 };
const formulario = (congelado) => ({ id: ID, institucion: 1, titulo: "Formulario sintético AUD012", descripcion: "Definición sintética", area: null, area_nombre: "Institución", usos_n: 0, congelado_at: congelado ? "2026-10-15T12:00:00Z" : null, campos: [campo] });
const json = (ruta, data, status = 200) => ruta.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });

async function sesionSintetica(page) {
  const institucion = { id: 1, nombre: "Institución sintética AUD012" };
  await page.addInitScript(inst => {
    sessionStorage.setItem("salud.access", "access-ficticio-aud012");
    sessionStorage.setItem("salud.refresh", "refresh-ficticio-aud012");
    localStorage.setItem("salud.institucion", JSON.stringify(inst));
  }, institucion);
  // Todas las llamadas API están interceptadas: no requiere login, semillas,
  // configuración privada ni backend. Las rutas de cada prueba tienen prioridad.
  await page.route("**/api/**", ruta => {
    const pathname = new URL(ruta.request().url()).pathname;
    // El glob también coincide con /src/api/client.js en Vite DEV.
    if (!pathname.startsWith("/api/")) return ruta.continue();
    if (pathname === "/api/usuarios/me/") return json(ruta, {
      id: 12, email: "diseno-aud012@example.test", nombre_completo: "Diseño sintético",
      is_superuser: false, capacidades_por_institucion: { 1: ["diseno_flujos", "config_institucional"] },
      roles_por_institucion: { 1: ["admin_institucion"] }, financiadores: [],
    });
    if (pathname === "/api/instituciones/") return json(ruta, { count: 1, results: [institucion], next: null, previous: null });
    return json(ruta, { count: 0, results: [], next: null, previous: null });
  });
}

test("congelado conserva lectura y duplicar ofrece una definición editable", async ({ page }) => {
  await sesionSintetica(page);
  await page.route(`**/api/formularios/${ID}/`, r => json(r, formulario(true)));
  await page.route(`**/api/formularios/${ID}/usos/`, r => json(r, { usos: [], condiciones: [] }));
  await page.route(`**/api/formularios/${ID}/duplicar/`, r => json(r, { ...formulario(false), id: ID + 1 }, 201));
  await page.route(`**/api/formularios/${ID + 1}/`, r => json(r, { ...formulario(false), id: ID + 1, campos: [{ ...campo, id: campo.id + 1, formulario: ID + 1 }] }));
  await page.route(`**/api/formularios/${ID + 1}/usos/`, r => json(r, { usos: [], condiciones: [] }));
  await page.goto(`/formularios/${ID}`);
  await expect(page.getByText("Definición congelada", { exact: true })).toBeVisible();
  for (const nombre of ["Editar datos", "Eliminar formulario", "+ Agregar campo", "Editar campo", "Quitar campo", "Subir", "Bajar"]) {
    await expect(page.getByRole("button", { name: nombre, exact: true })).toBeDisabled();
  }
  await expect(page.getByRole("heading", { name: "Vista previa en vivo" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  await expect.poll(async () => page.getByRole("button", { name: "+ Agregar campo", exact: true }).evaluate(boton => {
    const limite = boton.parentElement.getBoundingClientRect();
    const rect = boton.getBoundingClientRect();
    return limite.right <= innerWidth + 1 && rect.right <= Math.min(limite.right, innerWidth) + 1;
  }), { message: "La cabecera y Agregar campo deben quedar completos en el viewport móvil" }).toBe(true);
  await expect(page.getByRole("list", { name: "Campos del formulario" }).getByRole("listitem")).toHaveAttribute("draggable", "false");
  await page.getByRole("button", { name: "Duplicar", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/formularios/${ID + 1}$`));
  await expect(page.getByRole("button", { name: "Editar datos", exact: true })).toBeEnabled();
  await expect(page.getByText("Definición congelada", { exact: true })).toHaveCount(0);
});

test("409 conserva metadatos locales y permite reconsultar sin sobrescribirlos", async ({ page }) => {
  await sesionSintetica(page);
  let congelado = false;
  await page.route(`**/api/formularios/${ID}/`, ruta => {
    if (ruta.request().method() === "PATCH") {
      congelado = true;
      return json(ruta, { detail: "La definición quedó congelada." }, 409);
    }
    return json(ruta, formulario(congelado));
  });
  await page.route(`**/api/formularios/${ID}/usos/`, r => json(r, {
    usos: [{ nodo_id: 910030, nodo_titulo: "Paso sintético", flujo_id: 910040, flujo_titulo: "Flujo sintético", version_numero: 1, version_estado: congelado ? "publicada" : "borrador", casos_activos: 0 }], condiciones: [],
  }));
  await page.goto(`/formularios/${ID}`);
  await expect(page.getByText("Borrador", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Editar datos", exact: true }).click();
  const dialogo = page.getByRole("dialog", { name: "Editar formulario" });
  await dialogo.getByLabel("Título *").fill("Texto local que no se debe perder");
  await dialogo.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(dialogo.getByRole("alert")).toContainText("Tus cambios locales se conservan");
  await expect(dialogo.getByLabel("Título *")).toHaveValue("Texto local que no se debe perder");
  await expect(dialogo.getByRole("button", { name: "Guardar", exact: true })).toBeDisabled();
  await dialogo.getByRole("button", { name: "Actualizar estado del formulario", exact: true }).click();
  await expect(dialogo.getByRole("status")).toContainText("duplicá el formulario");
  await expect(dialogo.getByLabel("Título *")).toHaveValue("Texto local que no se debe perder");
  await dialogo.getByRole("button", { name: "Cancelar", exact: true }).click();
  await expect(page.getByText("Publicada", { exact: true })).toBeVisible();
  await expect(page.getByText("Borrador", { exact: true })).toHaveCount(0);
});

test("409 al editar un campo conserva etiqueta y ayuda locales", async ({ page }) => {
  await sesionSintetica(page);
  let fallarLectura = false;
  await page.route(`**/api/formularios/${ID}/`, r => json(r, formulario(false)));
  await page.route(`**/api/formularios/${ID}/usos/`, r => fallarLectura ? json(r, { detail: "Fallo sintético de usos" }, 503) : json(r, { usos: [], condiciones: [] }));
  await page.route(`**/api/campos/${campo.id}/`, r => {
    fallarLectura = true;
    return json(r, { detail: "La definición quedó congelada." }, 409);
  });
  await page.goto(`/formularios/${ID}`);
  await page.getByRole("button", { name: "Editar campo", exact: true }).click();
  const dialogo = page.getByRole("dialog");
  await dialogo.getByLabel("Etiqueta *").fill("Etiqueta local");
  await dialogo.getByLabel("Texto de ayuda").fill("Ayuda local");
  await dialogo.getByRole("button", { name: "Guardar", exact: true }).click();
  await expect(dialogo.getByRole("alert")).toContainText("no se guardaron");
  await expect(dialogo.getByLabel("Etiqueta *")).toHaveValue("Etiqueta local");
  await expect(dialogo.getByLabel("Texto de ayuda")).toHaveValue("Ayuda local");
  await expect(dialogo.getByRole("button", { name: "Guardar", exact: true })).toBeDisabled();
  await expect(page.getByText("No se pudo actualizar el estado del formulario. Tus cambios locales se conservan.", { exact: true })).toBeVisible();
  await expect(dialogo.getByLabel("Etiqueta *")).toHaveValue("Etiqueta local");
  fallarLectura = false;
  await dialogo.getByRole("button", { name: "Actualizar estado del formulario", exact: true }).click();
  await expect(dialogo.getByRole("button", { name: "Guardar", exact: true })).toBeEnabled();
  await expect(dialogo.getByLabel("Texto de ayuda")).toHaveValue("Ayuda local");
});
