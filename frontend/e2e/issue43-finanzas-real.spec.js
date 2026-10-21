import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// Falla si no se preparó el escenario. No convertir ausencia de entorno en skip.
const datos = JSON.parse(readFileSync(resolve("../issue43-metadata.json"), "utf8"));
function persistido(caso) {
  return JSON.parse(execFileSync("python", ["tests/issue43/ejecutar.py", "estado", String(caso)],
    { cwd: resolve("../backend"), encoding: "utf8" }));
}
async function ingresar(page, email) {
  await page.goto("/login");
  await page.getByLabel(/Email/).fill(email);
  // Clave exclusivamente ficticia de los helpers de prueba existentes.
  await page.getByLabel(/^Contraseña/).fill("x");
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  await expect(page).not.toHaveURL(/\/login/);
  await page.evaluate((hospital) => localStorage.setItem("salud.institucion", JSON.stringify(hospital)), datos.hospital);
}
async function solicitar(page, caso) {
  await page.goto(`/casos/${caso}`);
  await page.getByRole("button", { name: "Solicitar autorización", exact: true }).click();
  await page.getByRole("combobox", { name: "Prestación a autorizar", exact: true }).selectOption(String(datos.prestacion));
  await page.getByLabel("Justificación para el financiador", { exact: true }).fill("Orden ficticia del recorrido #43");
  await page.getByRole("button", { name: "Enviar solicitud", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Solicitud enviada" })).toBeVisible();
  const estado = persistido(caso);
  expect(estado.solicitudes).toHaveLength(1);
  expect(estado.hechos).toBe(0);
  expect(estado.cuentas).toEqual([]);
  return estado.solicitudes[0].id;
}
async function decidir(page, id, decision) {
  await page.goto(`/financiadores/autorizaciones?financiador=${datos.financiador}`);
  // En cada escenario hay una sola solicitud pendiente en esta bandeja.
  // El id se comprueba al abrir el diálogo, sin depender del orden de filas.
  await page.getByRole("button", { name: "Revisar", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: `Solicitud de autorización ${id}`, exact: true });
  await dialog.getByRole("button", { name: "Resolver solicitud", exact: true }).click();
  await dialog.getByRole("combobox", { name: "Decisión", exact: true }).selectOption(decision);
  await dialog.getByLabel("Motivo de la decisión", { exact: true }).fill("Revisión administrativa ficticia #43");
  if (decision === "aprobar") {
    await dialog.getByLabel("Evidencia de la decisión", { exact: true }).fill("Orden ficticia comprobada #43");
    await dialog.getByLabel("Cantidad autorizada", { exact: true }).fill("1");
    await dialog.getByLabel("Válida desde", { exact: true }).fill(datos.fecha);
    await dialog.getByLabel("Válida hasta", { exact: true }).fill(datos.fecha);
  }
  await dialog.getByRole("button", { name: "Registrar decisión", exact: true }).click();
  await expect(dialog).not.toBeVisible();
}

test("solicitud, observación, reenvío, aprobación, reserva, realización, cargo y cobro persistidos", async ({ browser }) => {
  const hospital = await browser.newContext();
  const financiador = await browser.newContext();
  try {
    const page = await hospital.newPage();
    const resolutor = await financiador.newPage();
    await ingresar(page, datos.hospital_email);
    await ingresar(resolutor, datos.resolutor_email);
    const id = await solicitar(page, datos.caso);
    await decidir(resolutor, id, "observar");
    expect(persistido(datos.caso).solicitudes[0].estado).toBe("observada");
    await page.reload();
    await page.getByRole("button", { name: `Ver solicitud ${id}`, exact: true }).click();
    const dialog = page.getByRole("dialog", { name: `Solicitud de autorización ${id}`, exact: true });
    await dialog.getByRole("button", { name: "Responder observación", exact: true }).click();
    await dialog.getByLabel("Justificación actualizada", { exact: true }).fill("Orden aclarada por el hospital #43");
    await dialog.getByRole("button", { name: "Reenviar solicitud", exact: true }).click();
    await expect(dialog).not.toBeVisible();
    expect(persistido(datos.caso).solicitudes[0].estado).toBe("pendiente");
    const antes = persistido(datos.caso);
    await decidir(resolutor, id, "aprobar");
    const aprobada = persistido(datos.caso);
    expect(aprobada.solicitudes[0].estado).toBe("aprobada");
    expect(aprobada.nodo).toBe(antes.nodo);
    expect(aprobada.hechos).toBe(0);
    expect(aprobada.cuentas).toEqual([]);
    expect(aprobada.movimientos).toEqual([]);
    await page.reload();
    await page.getByRole("button", { name: "Consultar cobertura", exact: true }).click();
    await page.getByRole("checkbox", { name: /El paciente aceptó expresamente/ }).check();
    await page.getByRole("button", { name: "Confirmar reserva de cobertura", exact: true }).click();
    await expect.poll(() => persistido(datos.caso).reservas.length).toBe(1);
    expect(persistido(datos.caso).hechos).toBe(0);
    await page.getByLabel("Título de la atención", { exact: true }).fill("Atención ficticia #43");
    await page.getByLabel("Evolución / observaciones", { exact: true }).fill("Prestación realizada en el entorno exclusivo");
    const firma = page.getByRole("checkbox", { name: "Firmar la entrada", exact: true });
    await firma.uncheck();
    await page.getByRole("button", { name: "Registrar sin firmar y avanzar", exact: true }).click();
    await expect.poll(() => persistido(datos.caso).hechos).toBe(1);
    const realizado = persistido(datos.caso);
    expect(realizado.reservas[0].estado).toBe("realizada");
    expect(realizado.usos).toEqual([{ estado: "consumido", hecho_id: realizado.reservas[0].hecho_id }]);
    expect(realizado.cuentas.map((c) => c.importe_original).sort()).toEqual(["20.00", "80.00"]);
    const cuenta = realizado.cuentas.find((c) => c.importe_original === "80.00");
    await page.goto("/finanzas?tab=dinero");
    await page.getByRole("row").filter({ has: page.getByText(cuenta.contraparte_nombre, { exact: true }) })
      .getByRole("button", { name: "Ver cuenta", exact: true }).click();
    await page.getByRole("button", { name: "Registrar cobro", exact: true }).click();
    await page.getByLabel("Importe en ARS", { exact: true }).fill("80.00");
    await page.getByLabel("Referencia del pago o cobro", { exact: true }).fill("COBRO-FICTICIO-43");
    await page.getByRole("button", { name: "Registrar cobro", exact: true }).click();
    await expect.poll(() => persistido(datos.caso).movimientos.length).toBe(1);
    await page.reload();
    const cobrado = persistido(datos.caso);
    expect(cobrado.hechos).toBe(1);
    expect(cobrado.cuentas).toHaveLength(2);
    expect(cobrado.cuentas.find((c) => c.id === cuenta.id).pendiente).toBe("0.00");
    expect(cobrado.cuentas.find((c) => c.id !== cuenta.id).pendiente).toBe("20.00");
    expect(cobrado.movimientos[0]).toMatchObject({ importe: "80.00", estado: "aprobado", tipo: "cobro" });
    await expect(page.getByRole("heading", { name: "Cuentas por pagar y cobrar", exact: true })).toBeVisible();
  } finally { await hospital.close(); await financiador.close(); }
});

test("rechazo conserva el paso y no fabrica atención ni deuda del paciente", async ({ browser }) => {
  const hospital = await browser.newContext();
  const financiador = await browser.newContext();
  try {
    const page = await hospital.newPage();
    const resolutor = await financiador.newPage();
    await ingresar(page, datos.hospital_email);
    await ingresar(resolutor, datos.resolutor_email);
    const id = await solicitar(page, datos.rechazo);
    const antes = persistido(datos.rechazo);
    await decidir(resolutor, id, "rechazar");
    await page.reload();
    const despues = persistido(datos.rechazo);
    expect(despues.solicitudes[0].estado).toBe("rechazada");
    expect(despues.nodo).toBe(antes.nodo);
    expect(despues.hechos).toBe(0);
    expect(despues.cuentas).toEqual([]);
    expect(despues.movimientos).toEqual([]);
    await expect(page.getByText("Rechazada", { exact: true })).toBeVisible();
  } finally { await hospital.close(); await financiador.close(); }
});
