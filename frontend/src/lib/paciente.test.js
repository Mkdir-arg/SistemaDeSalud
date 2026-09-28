import assert from "node:assert/strict";
import test from "node:test";

import { busquedaPaciente, precargarPaciente } from "./paciente.js";

test("precarga documento o nombre según el texto buscado", () => {
  const casos = [
    ["30.123.456", { nombre: "", apellido: "", documento: "30.123.456" }],
    ["30123456", { nombre: "", apellido: "", documento: "30123456" }],
    ["FIC000123", { nombre: "", apellido: "", documento: "FIC000123" }],
    ["Pérez", { nombre: "Pérez", apellido: "", documento: "" }],
    ["Juan Pérez", { nombre: "Juan", apellido: "Pérez", documento: "" }],
    ["", { nombre: "", apellido: "", documento: "" }],
  ];
  for (const [texto, esperado] of casos) {
    assert.deepEqual(precargarPaciente(texto), esperado, texto);
  }
});

test("la búsqueda usa el mismo documento normalizado que guarda el backend", () => {
  assert.equal(busquedaPaciente("30.123.456"), "30123456");
  assert.equal(busquedaPaciente("FIC000123"), "FIC000123");
  assert.equal(busquedaPaciente("Juan Pérez"), "Juan Pérez");
});
