import test from "node:test";
import assert from "node:assert/strict";
import { cuerpoGeo, cambiarGeo, geografiaInicial, hayGeoPendiente, origenGeo } from "./issue136_geografia.js";
import { valorColumnaPadron } from "../components/financiadores/padronTablaEstado.js";

test("un cambio de padre conserva el texto y exige confirmar los descendientes", () => {
  const antes = { provincia: { id: 1, nombre: "Provincia A", origen: "georef" }, partido: { id: 2, nombre: "Partido A" }, localidad: { id: 3, nombre: "Lugar A" } };
  const despues = cambiarGeo(antes, "provincia", { id: 4, nombre: "Provincia B" });
  assert.equal(despues.localidad.nombre, "Lugar A");
  assert.equal(despues.localidad.id, undefined);
  assert.equal(hayGeoPendiente(despues), true);
  assert.equal(antes.localidad.id, 3);
  assert.deepEqual(cuerpoGeo(despues).localidad, { pendiente: true });
});

test("legado no se convierte en manual ni fabrica identificadores", () => {
  const inicial = geografiaInicial(null, { provincia: "Lugar legado" });
  assert.equal(origenGeo(inicial.provincia), "Sin homologar");
  assert.deepEqual(cuerpoGeo(inicial).provincia, { nombre: "Lugar legado", origen: "legado" });
});

test("la escritura manda referencias o carga manual explícita, sin confiar en etiquetas", () => {
  const geo = { provincia: { id: 1, nombre: "Otra etiqueta", origen: "manual" }, localidad: { manual: "Lugar nuevo" } };
  assert.deepEqual(cuerpoGeo(geo), { provincia: { id: 1 }, partido: null, localidad: { manual: "Lugar nuevo" } });
  assert.equal(origenGeo(geo.localidad), "Manual · sin verificar");
});

test("quitar un padre no borra silenciosamente la localidad", () => {
  const geo = cambiarGeo({ localidad: { manual: "Lugar rural" } }, "provincia", null);
  assert.equal(geo.localidad.nombre, "Lugar rural");
  assert.equal(hayGeoPendiente(geo), true);
});

test("tabla distingue manuales personales y laborales sin modificar el dato de edición", () => {
  const fila = { localidad: "Lugar personal", domicilio_laboral: "Detalle ficticio", geografia: { localidad: { nombre: "Lugar personal", origen: "manual" } }, geografia_laboral: { localidad: { nombre: "Lugar laboral", origen: "manual" } } };
  assert.equal(valorColumnaPadron(fila, { key: "localidad" }), "Lugar personal · Manual · sin verificar");
  assert.equal(valorColumnaPadron(fila, { key: "domicilio_laboral" }), "Detalle ficticio · Lugar laboral (Manual · sin verificar)");
  assert.equal(fila.localidad, "Lugar personal");
});
