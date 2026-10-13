import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { COLUMNAS_PADRON, COLUMNAS_PREDETERMINADAS, GRUPOS_PADRON, controlesFiltroPadron, filtrosActivosPadron, cambiarColumnasPadron, cambiarConsultaPadron, cambiarEstadoPadron, estadoDerechoPadron, obtenerColumnasPadron, ordenarPadron, parametrosConsultaPadron, valorColumnaPadron } from "./padronTablaEstado.js";

test("catálogo coincide exactamente con backend; no ofrece datos protegidos", () => {
  const backend = JSON.parse(readFileSync(new URL("../../../../backend/apps/financiadores/padron_columnas.json", import.meta.url), "utf8"));
  assert.deepEqual(COLUMNAS_PADRON, backend);
  for (const key of ["cbu", "banco", "situacion", "cud", "dbt", "parentesco_sensible", "acciones", "revision"]) assert.ok(!COLUMNAS_PADRON.some((c) => c.key === key));
});

test("mostrar/ocultar/restaurar conserva obligatorias y contexto sin mutar entrada", () => {
  const original = new URLSearchParams("financiador=21&page=3&search=Alfa&ordering=-nombre");
  const custom = cambiarColumnasPadron(original, ["localidad"]);
  assert.deepEqual(obtenerColumnasPadron(custom), ["nombre", "numero", "localidad"]);
  assert.equal(custom.get("page"), "3");
  assert.equal(original.has("columnas"), false);
  const restored = cambiarColumnasPadron(custom, COLUMNAS_PREDETERMINADAS);
  assert.deepEqual(obtenerColumnasPadron(restored), COLUMNAS_PREDETERMINADAS);
  assert.equal(restored.has("columnas"), false);
  assert.equal(restored.get("ordering"), "-nombre");
});

test("filtro/orden/tamaño reinician página una vez y conservan contexto de ficha", () => {
  const p = new URLSearchParams("financiador=21&page=3&padron_page=3&columnas=nombre,numero,localidad&historial_page=2&derecho=todos");
  const next = cambiarConsultaPadron(p, { flt_localidad: "Río", page_size: 25 });
  assert.equal(next.has("page"), false);
  assert.equal(next.has("padron_page"), false);
  assert.equal(next.get("financiador"), "21");
  assert.equal(next.get("columnas"), "nombre,numero,localidad");
  const asc = ordenarPadron(next, "nombre");
  const desc = ordenarPadron(asc, "nombre");
  assert.equal(asc.get("ordering"), "nombre");
  assert.equal(desc.get("ordering"), "-nombre");
  assert.equal(ordenarPadron(desc, "nombre").has("ordering"), false);
  assert.equal(cambiarConsultaPadron(next, { estado: "vigentes" }).has("derecho"), false);
});

test("consulta aplicada sobrevivirá reload sin enviar scope ni paginación de ficha", () => {
  const url = "financiador=21&page=2&padron_page=8&historial_page=4&columnas=nombre,numero,localidad&flt_localidad=Rio&ordering=-localidad";
  const consulta = parametrosConsultaPadron(new URLSearchParams(url));
  assert.equal(consulta.get("page_size"), "10");
  assert.equal(consulta.get("estado"), "vigentes");
  assert.equal(consulta.get("financiador"), null);
  assert.equal(consulta.get("historial_page"), null);
  assert.equal(consulta.get("ordering"), "-localidad");
  assert.equal(consulta.get("flt_localidad"), "Rio");
  assert.deepEqual([...parametrosConsultaPadron(new URLSearchParams(url))], [...consulta]);
});

test("presentación mantiene texto/ceros, nombres de plan y estados diferenciados", () => {
  const col = (k) => COLUMNAS_PADRON.find((c) => c.key === k);
  assert.equal(valorColumnaPadron({ numero: "001" }, col("numero")), "001");
  assert.equal(valorColumnaPadron({ plan: 3 }, col("plan"), [{ id: 3, nombre: "Base Río" }]), "Base Río");
  assert.equal(valorColumnaPadron({ vigente: false, finalizado_en: null }, col("derecho")), "Aún no vigente");
  assert.equal(valorColumnaPadron({ vigente: false, finalizado_en: "2026-10-13" }, col("derecho")), "Finalizada");
});

test("tamaño por URL coincide con selector y consulta; valores fuera del selector usan 10", () => {
  for (const [pedido, esperado] of [["25", "25"], ["100", "100"], ["200", "10"], ["0", "10"], ["texto", "10"]]) {
    assert.equal(parametrosConsultaPadron(new URLSearchParams({ page_size: pedido })).get("page_size"), esperado);
  }
});

test("aliases de derecho no se combinan con vigentes implícito", () => {
  for (const estado of ["finalizadas", "futuras", "vigentes"]) {
    const params = new URLSearchParams({ flt_derecho: estado });
    assert.equal(estadoDerechoPadron(params), estado);
    assert.equal(parametrosConsultaPadron(params).get("estado"), null);
    assert.equal(parametrosConsultaPadron(params).get("flt_derecho"), estado);
  }
  assert.equal(estadoDerechoPadron(new URLSearchParams()), "vigentes");
  assert.equal(parametrosConsultaPadron(new URLSearchParams()).get("estado"), "vigentes");
  assert.equal(estadoDerechoPadron(new URLSearchParams("derecho=todos&estado=vigentes&flt_derecho=futuras")), "todos");
  // No reinterpretar ni descartar criterios explícitos de API, incluso invalidos.
  assert.equal(parametrosConsultaPadron(new URLSearchParams("estado=vigentes&flt_derecho=futuras")).get("estado"), "vigentes");
  assert.equal(parametrosConsultaPadron(new URLSearchParams("flt_derecho=invalido")).get("flt_derecho"), "invalido");
});

test("cambiar Estado canónico limpia aliases y página, conserva otros filtros", () => {
  const params = new URLSearchParams("financiador=21&page=3&padron_page=3&derecho=todos&flt_derecho=futuras&ordering=-nombre&flt_apellidos=Alfa");
  const nuevos = cambiarEstadoPadron(params, "finalizadas");
  assert.equal(estadoDerechoPadron(nuevos), "finalizadas");
  for (const key of ["derecho", "flt_derecho", "page", "padron_page"]) assert.equal(nuevos.has(key), false);
  assert.equal(nuevos.get("ordering"), "-nombre");
  assert.equal(nuevos.get("flt_apellidos"), "Alfa");
});

test("cada columna está en un único grupo de presentación", () => {
  const claves = GRUPOS_PADRON.flatMap((g) => g.columnas.map((c) => c?.key));
  assert.deepEqual([...claves].sort(), COLUMNAS_PADRON.map((c) => c.key).sort());
});

test("chips usan los parámetros históricos y los flt_ aunque la columna esté oculta", () => {
  const params = new URLSearchParams("columnas=nombre,numero&regimen=pasivo&alta_desde=2026-01-02&flt_localidad=Río&flt_plan_vacio=true&flt_plan=3&estado=todos&search=x");
  assert.deepEqual(filtrosActivosPadron(params, [{ id: 3, nombre: "Base" }]).map((f) => [f.clave, f.etiqueta]), [
    ["flt_plan", "Plan: Base"], ["flt_plan_vacio", "Plan: sin cargar"],
    ["flt_localidad", "Localidad: «Río»"], ["regimen", "Régimen: Jubilado / pensionado"],
    ["alta_desde", "Alta administrativa desde 02/01/2026"],
  ]);
  const historicos = new URLSearchParams("estado_administrativo=en_tramite&flt_regimen=dependencia&baja_hasta=2026-03-04");
  assert.deepEqual(filtrosActivosPadron(historicos).map((f) => f.etiqueta), ["Estado administrativo: En trámite", "Régimen: Relación de dependencia", "Baja administrativa hasta 04/03/2026"]);
  // Estado y Plan son controles de la barra: no se duplican en el panel.
  assert.deepEqual(controlesFiltroPadron(COLUMNAS_PADRON.find((c) => c.key === "derecho")), []);
  assert.deepEqual(controlesFiltroPadron(COLUMNAS_PADRON.find((c) => c.key === "plan")).map((c) => c.clave), ["flt_plan_vacio"]);
});
