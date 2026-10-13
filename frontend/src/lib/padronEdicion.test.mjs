import test from "node:test";
import assert from "node:assert/strict";
import { cambiosPadron, errorCampoPadron, estadoVencimiento } from "./padronEdicion.js";

test("editar contacto no envía sensibles vacíos ni otros bloques", () => {
  assert.deepEqual(cambiosPadron([{ name: "telefono" }], { telefono: "123", cbu: "protegido" }, { telefono: "456", cbu: "", cud: false }), { telefono: "456" });
});
test("omite campos intactos y conserva borrado explícito, identificadores y booleanos", () => {
  const campos = [{ name: "numero" }, { name: "correo" }, { name: "titular", numeric: true }, { name: "dbt", boolean: true }];
  assert.deepEqual(cambiosPadron(campos, { numero: "00100", correo: "a@example.test", titular: 2, dbt: true }, { numero: "00100", correo: "", titular: "", dbt: false }), { correo: "", titular: null, dbt: false });
});
test("errores por campo preservan los mensajes del servidor", () => {
  assert.equal(errorCampoPadron({ data: { cuil: ["Dígito inválido", "Revisá el documento"] } }, "cuil"), "Dígito inválido Revisá el documento");
});

test("salud no equipara dato desconocido con No y permite retirar fechas explícitamente", () => {
  const campos = [{ name: "cud", tristate: true }, { name: "dbt", tristate: true }, { name: "cud_vencimiento", nullable: true }];
  assert.deepEqual(cambiosPadron(campos, { cud: null, dbt: true, cud_vencimiento: "2026-10-09" }, { cud: "false", dbt: "", cud_vencimiento: "" }), { cud: false, dbt: null, cud_vencimiento: null });
  assert.deepEqual(cambiosPadron(campos, { cud: false, dbt: null }, { cud: "false", dbt: "" }), {});
});

test("vencimiento distingue ayer, hoy, mañana y fecha ausente sin inferir cobertura", () => {
  assert.equal(estadoVencimiento("2026-10-08", "2026-10-09"), "Vencido");
  assert.equal(estadoVencimiento("2026-10-09", "2026-10-09"), "Vence hoy");
  assert.equal(estadoVencimiento("2026-10-10", "2026-10-09"), "Vigente por fecha");
  assert.equal(estadoVencimiento(null, "2026-10-09"), "Sin vencimiento informado");
});
