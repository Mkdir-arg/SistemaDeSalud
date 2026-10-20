import test from "node:test";
import assert from "node:assert/strict";
import { formatosPara, guardarFormatoPreferido, leerFormatoPreferido } from "./formatosImportacion.js";

function memoria() {
  const valores = new Map();
  return { getItem: (k) => valores.get(k) ?? null, setItem: (k, v) => valores.set(k, v) };
}

test("sin preferencia usa la plantilla del sistema", () => {
  assert.deepEqual(leerFormatoPreferido(1, "padron", formatosPara("padron"), memoria()), { id: "sistema", persistencia: true });
});

test("recuerda la selección y la aísla por usuario y tipo de carga", () => {
  const storage = memoria();
  assert.equal(guardarFormatoPreferido(1, "padron", "ostel", storage), true);
  assert.equal(leerFormatoPreferido(1, "padron", formatosPara("padron"), storage).id, "ostel");
  assert.equal(leerFormatoPreferido(2, "padron", formatosPara("padron"), storage).id, "sistema");
  assert.equal(leerFormatoPreferido(1, "consumos", formatosPara("consumos"), storage).id, "sistema");
});

test("formato eliminado, desconocido o incompatible vuelve al predeterminado", () => {
  for (const id of ["retirado", "{json-roto}", "ostel"]) {
    const storage = memoria();
    guardarFormatoPreferido(1, "consumos", id, storage);
    assert.equal(leerFormatoPreferido(1, "consumos", formatosPara("consumos"), storage).id, "sistema");
  }
});

test("storage bloqueado no impide usar la pantalla y se informa", () => {
  const storage = { getItem() { throw Error("bloqueado"); }, setItem() { throw Error("bloqueado"); } };
  assert.deepEqual(leerFormatoPreferido(1, "padron", formatosPara("padron"), storage), { id: "sistema", persistencia: false });
  assert.equal(guardarFormatoPreferido(1, "padron", "ostel", storage), false);
});

test("no comparte preferencias entre usuarios sin identificar", () => {
  const storage = memoria();
  assert.equal(guardarFormatoPreferido(null, "padron", "ostel", storage), false);
  assert.equal(leerFormatoPreferido(null, "padron", formatosPara("padron"), storage).id, "sistema");
});

test("admite N entradas sin cambios en el filtrado o persistencia", () => {
  const registro = Array.from({ length: 30 }, (_, n) => ({ id: `formato-${n}`, tipos: ["padron"], modo: "revision" }));
  const opciones = formatosPara("padron", registro);
  const storage = memoria();
  assert.equal(opciones.length, 30);
  guardarFormatoPreferido(1, "padron", "formato-29", storage);
  assert.equal(leerFormatoPreferido(1, "padron", opciones, storage).id, "formato-29");
  assert.deepEqual(formatosPara("consumos", registro), []);
});
