import assert from "node:assert/strict";
import test from "node:test";
import { combinarLote, confirmarTanda } from "./importacionRespuesta.mjs";

const resumen = { total: 2, valida: 2, revision: 0, rechazada: 0, aplicada: 0, error_tecnico: 0, omitida: 0 };
const completa = { id: 182, version: 3, tipo: "padron", modo_respuesta: "completa", huella_lote: "base",
  estado: "preview", resumen, filas: [1, 2].map((fila) => ({ fila, estado: "valida", original: { APENOM: `PERSONA FICTICIA ${fila}` } })) };
const cambios = { id: 182, version: 3, tipo: "padron", modo_respuesta: "cambios", base_huella: "base", huella_lote: "nueva",
  estado: "preview", resumen: { ...resumen, valida: 1, aplicada: 1 },
  filas_cambiadas: [{ ...completa.filas[0], estado: "aplicada", afiliado: 1 }] };

test("combina sin mutar el estado anterior y conserva evidencia/orden", () => {
  const actual = structuredClone(completa);
  const nuevo = combinarLote(actual, cambios);
  assert.equal(nuevo.filas[0].estado, "aplicada");
  assert.equal(actual.filas[0].estado, "valida");
  assert.equal(nuevo.filas[1], actual.filas[1]);
  assert.deepEqual(nuevo.filas[0].original, actual.filas[0].original);
  assert.equal(nuevo.huella_lote, "nueva");
  assert.ok(!("filas_cambiadas" in nuevo));
});

test("acepta respuesta tradicional y reemplazo completo tras pérdida de respuesta", () => {
  const tradicional = { ...completa };
  delete tradicional.modo_respuesta; delete tradicional.huella_lote;
  assert.equal(combinarLote(completa, tradicional), tradicional);
  const recuperada = { ...completa, huella_lote: "actualizada", estado: "aplicada",
    resumen: { ...resumen, aplicada: 2, valida: 0 }, filas: completa.filas.map((f) => ({ ...f, estado: "aplicada" })) };
  assert.equal(combinarLote(completa, recuperada), recuperada);
});

test("rechaza base ajena, otro lote, filas desconocidas/duplicadas y contadores inconsistentes", () => {
  for (const cambiar of [
    (r) => { r.base_huella = "otra"; }, (r) => { r.id = 999; },
    (r) => { r.filas_cambiadas[0].fila = 999; },
    (r) => { r.filas_cambiadas.push(r.filas_cambiadas[0]); },
    (r) => { r.resumen.aplicada = 99; }, (r) => { r.filas = []; },
  ]) {
    const respuesta = structuredClone(cambios);
    cambiar(respuesta);
    assert.throws(() => combinarLote(completa, respuesta), /sincronizar/);
  }
});

test("rechaza modo desconocido y resumen que no trae filas completas", () => {
  assert.throws(() => combinarLote(completa, { ...completa, modo_respuesta: "otro" }));
  const incompleta = { ...completa };
  delete incompleta.filas;
  assert.throws(() => combinarLote(completa, incompleta));
});

test("envía la huella conocida y no reintenta ocultamente ante un corte", async () => {
  const pedidos = [];
  await confirmarTanda(completa, async (body) => { pedidos.push(body); return cambios; });
  assert.equal(pedidos[0].huella_lote, "base");
  await confirmarTanda({ ...completa, huella_lote: null }, async (body) => { pedidos.push(body); return completa; });
  assert.ok(!("huella_lote" in pedidos[1]));
  let llamadas = 0;
  await assert.rejects(confirmarTanda(completa, async () => { llamadas++; throw new Error("Corte ficticio"); }));
  assert.equal(llamadas, 1);
});
