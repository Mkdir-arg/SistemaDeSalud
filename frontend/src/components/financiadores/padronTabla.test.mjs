import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { COLUMNAS_PADRON, COLUMNAS_PREDETERMINADAS, cambiarColumnasPadron, cambiarConsultaPadron, obtenerColumnasPadron, ordenarPadron, parametrosConsultaPadron, valorColumnaPadron } from "./padronTablaEstado.js";

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
