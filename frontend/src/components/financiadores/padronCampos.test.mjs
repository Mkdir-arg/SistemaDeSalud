import test from "node:test";
import assert from "node:assert/strict";
import { BLOQUES_PADRON, CAMPOS_FAMILIA, CAMPOS_COBRANZA, CAMPOS_SALUD, valorCampoPadron } from "./padronCampos.js";

test("los bloques generales nunca editan condiciones, bancarios ni fechas de derechos", () => {
  const generales = [...BLOQUES_PADRON.flatMap((bloque) => bloque.campos), ...CAMPOS_FAMILIA].map((campo) => campo.name);
  for (const name of [...CAMPOS_SALUD, ...CAMPOS_COBRANZA].map((campo) => campo.name).concat(["desde", "finalizado_en"])) assert.equal(generales.includes(name), false, name);
  assert.equal(new Set(generales).size, generales.length);
});
test("el historial de legajo presenta anterior/nuevo legibles, con estados y fechas", () => {
  assert.equal(valorCampoPadron({ name: "legajo:1" }, { tipo: "estudio", estado: "verificado", vence_en: "2026-10-09" }), "Tipo de presentación: Estudio\nEstado de presentación: Verificado\nVencimiento: 09/10/2026");
});
test("indicadores sensibles mantienen desconocido y valores explícitos", () => {
  const cud = CAMPOS_SALUD.find((campo) => campo.name === "cud");
  assert.equal(valorCampoPadron(cud, null), "Sin informar");
  assert.equal(valorCampoPadron(cud, false), "No");
  assert.equal(valorCampoPadron(cud, true), "Sí");
});
