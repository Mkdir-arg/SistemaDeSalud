import assert from "node:assert/strict";
import test from "node:test";

import { leerCredencialesFragmento, limpiarFragmentoCredenciales } from "./credencialesInstitucionales.js";

test("lee y decodifica exclusivamente parámetros del fragmento", () => {
  assert.deepEqual(leerCredencialesFragmento("#uid=MTcy&token=token-sintetico&nuevo_email=ana%2Bprueba%40example.test"), {
    uid: "MTcy", token: "token-sintetico", nuevo_email: "ana+prueba@example.test",
  });
  assert.deepEqual(leerCredencialesFragmento(""), { uid: "", token: "", nuevo_email: "" });
});

test("leer es puro para doble render; limpiar elimina secretos sin perder ruta o estado", () => {
  const ubicacion = { pathname: "/restablecer-acceso", search: "?origen=correo", hash: "#uid=MTcy&token=secreto-sintetico" };
  const credenciales = leerCredencialesFragmento(ubicacion.hash);
  assert.deepEqual(leerCredencialesFragmento(ubicacion.hash), credenciales);
  const estado = { idx: 2 };
  const llamadas = [];
  limpiarFragmentoCredenciales(ubicacion, { state: estado, replaceState: (...args) => llamadas.push(args) });
  assert.deepEqual(llamadas, [[estado, "", "/restablecer-acceso?origen=correo"]]);
  assert.equal(JSON.stringify(llamadas).includes("secreto-sintetico"), false);
});

test("sin fragmento no reescribe historial", () => {
  limpiarFragmentoCredenciales({ hash: "" }, { replaceState: () => assert.fail("No debe modificar historial") });
});
