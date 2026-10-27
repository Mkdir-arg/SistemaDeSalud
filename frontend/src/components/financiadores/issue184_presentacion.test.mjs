import assert from "node:assert/strict";
import test from "node:test";
import { COLUMNAS_PADRON, cambiarColumnasPadron, cambiarConsultaPadron, filtrosActivosPadron, obtenerColumnasPadron, parametrosConsultaPadron, valorColumnaPadron } from "./padronTablaEstado.js";

const columna = (key) => COLUMNAS_PADRON.find((c) => c.key === key);

test("issue184: un derecho desconocido no se anuncia vigente", () => {
  for (const vigente of [undefined, null, "", "false", 0]) {
    assert.equal(valorColumnaPadron({ vigente }, columna("derecho")), "Sin informar");
  }
  assert.equal(valorColumnaPadron({ vigente: true }, columna("derecho")), "Vigente");
  assert.equal(valorColumnaPadron({ vigente: false }, columna("derecho")), "Aún no vigente");
  assert.equal(valorColumnaPadron({ finalizado_en: "2026-10-01" }, columna("derecho")), "Finalizada");
  assert.equal(valorColumnaPadron({ cobertura_habilitada: false, vigente: true }, columna("derecho")), "Sólo administrativa");
  assert.equal(valorColumnaPadron({ cobertura_habilitada: false, vigente: false }, columna("derecho")), "Sólo administrativa");
  assert.equal(valorColumnaPadron({ cobertura_habilitada: false }, columna("derecho")), "Sólo administrativa");
  assert.equal(valorColumnaPadron({ cobertura_habilitada: false, finalizado_en: "2026-10-01" }, columna("derecho")), "Finalizada");
  assert.equal(valorColumnaPadron({ cobertura_habilitada: true }, columna("derecho")), "Sin informar");
});

test("issue184: códigos desconocidos conservan evidencia literal, incluso propiedades de Object", () => {
  for (const key of ["estado_administrativo", "plan_tipo", "parentesco"]) {
    for (const valor of ["NO_HOMOLOGADO", "constructor", "toString", "__proto__"]) {
      assert.equal(valorColumnaPadron({ [key]: valor }, columna(key)), valor);
    }
  }
  assert.equal(valorColumnaPadron({ estado_administrativo: "en_tramite" }, columna("estado_administrativo")), "En trámite");
  assert.deepEqual(filtrosActivosPadron(new URLSearchParams("estado_administrativo=constructor&flt_parentesco=__proto__")).map((f) => f.etiqueta), ["Estado administrativo: constructor", "Parentesco: __proto__"]);
});

test("issue184: faltantes y ceros se distinguen sin deducir parentesco o plan", () => {
  for (const valor of [null, undefined, ""]) {
    assert.equal(valorColumnaPadron({ nombre: valor }, columna("nombre")), "Sin informar");
    assert.equal(valorColumnaPadron({ parentesco: valor }, columna("parentesco")), "Sin informar");
  }
  assert.equal(valorColumnaPadron({ numero: "00001" }, columna("numero")), "00001");
  assert.equal(valorColumnaPadron({ numero: 0 }, columna("numero")), "0");
  assert.equal(valorColumnaPadron({ plan: null }, columna("plan")), "Sin plan");
  assert.equal(valorColumnaPadron({ plan: 99 }, columna("plan")), "Plan 99");
});

test("issue184: cambios de filtro conservan columnas y consulta reproducible de exportación", () => {
  const origen = new URLSearchParams("financiador=21&page=3&estado=todos&ordering=-numero&historial_page=2");
  const configurada = cambiarColumnasPadron(origen, ["localidad", "estado_administrativo"]);
  const filtrada = cambiarConsultaPadron(configurada, { flt_localidad: "Ficticia", estado_administrativo: "en_tramite" });
  const consulta = parametrosConsultaPadron(new URLSearchParams(filtrada.toString()));
  assert.deepEqual(obtenerColumnasPadron(consulta), ["nombre", "numero", "estado_administrativo", "localidad"]);
  assert.equal(consulta.get("estado"), "todos");
  assert.equal(consulta.get("ordering"), "-numero");
  assert.equal(consulta.get("flt_localidad"), "Ficticia");
  assert.equal(consulta.get("estado_administrativo"), "en_tramite");
  assert.equal(consulta.get("page"), "1");
  assert.equal(consulta.has("financiador"), false);
  assert.equal(consulta.has("historial_page"), false);
  assert.equal(origen.get("page"), "3");
});


test("issue184: tabla y ficha comparten precedencia sin deducir fechas", () => {
  for (const [fila, esperado] of [
    [{ estado: "vigente" }, "Vigente"],
    [{ estado: "futura" }, "Aún no vigente"],
    [{ estado: "finalizada", cobertura_habilitada: false }, "Finalizada"],
    [{ estado: "vigente", cobertura_habilitada: false }, "Sólo administrativa"],
    [{ estado: "futura", vigente: true }, "Vigente"],
    [{ estado: "vigente", vigente: false }, "Aún no vigente"],
    [{ estado: "vigente", vigente: "false" }, "Sin informar"],
    [{ estado: "constructor", desde: "2020-01-01" }, "Sin informar"],
  ]) assert.equal(valorColumnaPadron(fila, columna("derecho")), esperado);
});


test("issue184: URL previa exporta las columnas en el mismo orden visible sin ocultar errores", () => {
  const parametros = new URLSearchParams("columnas=numero,nombre,localidad,plan&estado=todos&page=2");
  const original = parametros.toString();
  assert.deepEqual(parametrosConsultaPadron(parametros).get("columnas").split(","), obtenerColumnasPadron(parametros));
  assert.equal(parametros.toString(), original);
  for (const columnas of ["nombre,nombre", "nombre,numero,cbu", "nombre", "nombre,numero,numero", ""]) {
    const consulta = parametrosConsultaPadron(new URLSearchParams({ columnas }));
    assert.equal(consulta.get("columnas"), columnas, "Backend debe seguir rechazando selecciones inválidas");
  }
  const repetidas = new URLSearchParams("columnas=nombre,numero&columnas=nombre,numero,cbu");
  assert.deepEqual(parametrosConsultaPadron(repetidas).getAll("columnas"), repetidas.getAll("columnas"));
});
