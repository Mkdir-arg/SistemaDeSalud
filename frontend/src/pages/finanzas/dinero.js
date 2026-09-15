import { useRef, useState } from "react";
import { decimalACentavos } from "@/api/finanzas";

export const fechaLocal = () => {
  const hoy = new Date();
  return `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}-${String(hoy.getDate()).padStart(2, "0")}`;
};
export const decimalDinero = (valor) => String(valor).trim().replace(",", ".");
export const filtroAreaDinero = (area) => area === "null" ? { area_sin_asignar: true } : { area: area || undefined };
export function importeValido(valor, maximo) {
  const centavos = decimalACentavos(decimalDinero(valor));
  if (centavos === "importe_invalido" || BigInt(centavos) <= 0n) return false;
  return maximo == null || BigInt(centavos) <= BigInt(decimalACentavos(maximo));
}
export const mensajeErrorDinero = (error) => typeof error.data === "object"
  ? Object.values(error.data || {}).flat().join(" · ") : error.message || "No se pudo completar la operación.";

// Cada intención conserva su clave, incluso después de una respuesta perdida.
// Cada contenido usa una clave propia durante la vida del formulario. Volver
// a datos ya enviados recupera su clave; nada se persiste en el navegador.
export function useOperacionDinero() {
  const enCurso = useRef(false);
  const intenciones = useRef(new Map());
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  async function ejecutar(payload, operacion) {
    if (enCurso.current) return;
    // La previsualización puede cambiar al recuperarse una respuesta perdida.
    // Sus controles de concurrencia no cambian la operación que se intenta.
    const firma = JSON.stringify(Object.fromEntries(Object.entries(payload)
      .filter(([campo]) => campo !== "version_esperada" && campo !== "pendiente_esperado")
      .map(([campo, valor]) => [campo, campo === "importe" ? decimalACentavos(decimalDinero(valor)) : valor])));
    if (!intenciones.current.has(firma)) intenciones.current.set(firma, crypto.randomUUID());
    enCurso.current = true;
    setGuardando(true);
    setError("");
    try { await operacion({ ...payload, clave: intenciones.current.get(firma) }); }
    catch (err) {
      setError(!err.status || err.status >= 500
        ? "No se pudo confirmar el resultado. Podés reintentar estos mismos datos: se conservará la referencia de la operación para evitar duplicarla."
        : mensajeErrorDinero(err));
    } finally { enCurso.current = false; setGuardando(false); }
  }
  return { ejecutar, guardando, error, enCurso };
}
