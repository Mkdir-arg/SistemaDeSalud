import test from "node:test";
import assert from "node:assert/strict";
import { cuerpoAlta, cuitValido, formatoCuit, obligatoriosCompletos, pasoConDatos, tieneDatos, validarPaso, datosIniciales } from "./altaAfiliado.js";

const HOY = "2026-10-13";
const paso1 = { tipo_documento: "DNI", documento: "30123456", cuil: "20-30123456-3", apellidos: "González Pérez", nombres: "María José", numero: "00025" };
const paso2 = { plan: "31", desde: HOY, delegacion: "Sede Central", motivo: "Adhesión voluntaria", grupo: "titular" };

test("CUIT/CUIL: dígito verificador y formato mientras se escribe", () => {
  assert.equal(cuitValido("20-30123456-3"), true);
  assert.equal(cuitValido("20301234567"), false);
  assert.equal(cuitValido("30-71234567-1"), true);
  assert.equal(cuitValido("123"), false);
  assert.equal(formatoCuit("2030123"), "20-30123");
  assert.equal(formatoCuit("20301234563999"), "20-30123456-3");
});

test("paso 1 exige identidad y número de afiliado, y cruza CUIL con DNI", () => {
  assert.deepEqual(Object.keys(validarPaso(0, { tipo_documento: "DNI" }, HOY)), ["documento", "apellidos", "nombres", "numero"]);
  assert.deepEqual(validarPaso(0, paso1, HOY), {});
  assert.match(validarPaso(0, { ...paso1, cuil: "20-12345678-6" }, HOY).cuil, /no coincide/);
  assert.match(validarPaso(0, { ...paso1, cuil: "20-30123456-7" }, HOY).cuil, /dígito verificador/);
  assert.match(validarPaso(0, { ...paso1, documento: "123" }, HOY).documento, /7 u 8/);
  assert.match(validarPaso(0, { ...paso1, fecha_nacimiento: "2026-10-14" }, HOY).fecha_nacimiento, /futura/);
  // Pasaporte: sin la regla numérica del DNI ni el cruce con CUIL.
  assert.deepEqual(validarPaso(0, { ...paso1, tipo_documento: "PAS", documento: "AB123", cuil: "" }, HOY), {});
});

test("paso 2: familiar vuelve obligatorios titular y parentesco", () => {
  assert.deepEqual(validarPaso(1, paso2, HOY), {});
  assert.deepEqual(Object.keys(validarPaso(1, { ...paso2, grupo: "familiar" }, HOY)), ["titular", "parentesco"]);
  assert.match(validarPaso(1, { ...paso2, desde: "2026-10-14" }, HOY).desde, /futura/);
});

test("pasos opcionales: formato y campos condicionales según régimen", () => {
  assert.deepEqual(validarPaso(2, {}, HOY), {});
  assert.match(validarPaso(2, { email: "x@", codigo_postal: "18" }, HOY).email, /correo/);
  assert.deepEqual(Object.keys(validarPaso(2, { codigo_postal: "B1824ABC" }, HOY)), []);
  assert.match(validarPaso(3, { regimen: "dependencia", cuit_empleador: "30-71234567-9" }, HOY).cuit_empleador, /dígito/);
  // CUIT cargado pero oculto por cambiar de régimen: no bloquea.
  assert.deepEqual(validarPaso(3, { regimen: "monotributo", cuit_empleador: "1" }, HOY), {});
  assert.match(validarPaso(3, { regimen: "desempleo", subsidio_desde: "2026-05-01", subsidio_hasta: "2026-04-01" }, HOY).subsidio_hasta, /posterior/);
});

test("obligatorios y estado de los pasos", () => {
  assert.equal(obligatoriosCompletos({ ...paso1, ...paso2 }), true);
  assert.equal(obligatoriosCompletos(paso1), false);
  assert.equal(tieneDatos(datosIniciales()), false);
  assert.equal(tieneDatos({ ...datosIniciales(), apellidos: "X" }), true);
  assert.equal(pasoConDatos(3, { regimen: "" }), false);
});

test("el cuerpo envía sólo lo visible, con identificadores sin separadores", () => {
  const body = cuerpoAlta({ ...paso1, ...paso2, titular: 45, parentesco: "conyuge", regimen: "monotributo", cuit_empleador: "30-71234567-1", telefono: " 11 5555-0000 ", email: "" });
  assert.deepEqual(body, {
    solo_crear: true, nombre: "María José González Pérez",
    tipo_documento: "DNI", documento: "30123456", cuil: "20301234563", apellidos: "González Pérez", nombres: "María José", numero: "00025",
    plan: 31, desde: HOY, delegacion: "Sede Central", motivo: "Adhesión voluntaria",
    telefono: "11 5555-0000", regimen: "monotributo",
  });
  const familiar = cuerpoAlta({ ...paso1, ...paso2, grupo: "familiar", titular: 45, parentesco: "conyuge" });
  assert.equal(familiar.titular, 45);
  assert.equal(familiar.parentesco, "conyuge");
});
