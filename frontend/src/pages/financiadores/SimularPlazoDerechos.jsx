import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "@/api/client";
import { errorFinanciador, rutaFinanciador } from "@/api/financiadores";
import { Button, Field, Input, Modal } from "@/components/ui";

export default function SimularPlazoDerechos({ organizacion, regla, onClose }) {
  const [campos, setCampos] = useState({ dias_corridos: "", fecha: "", referencia: "", evidencia: "" });
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const activo = useRef(true), enviando = useRef(false);
  useEffect(() => { activo.current = true; return () => { activo.current = false; }; }, []);
  const cambiar = (campo) => (e) => {
    setCampos((actual) => ({ ...actual, [campo]: e.target.value }));
    setResultado(null); setError(null);
  };
  async function calcular(e) {
    e.preventDefault();
    if (enviando.current) return;
    enviando.current = true; setOcupado(true); setResultado(null); setError(null);
    try {
      const respuesta = await api.post(rutaFinanciador(organizacion.id, "borradores-derechos/simular-plazo"), {
        regla: { codigo: regla.codigo, version: regla.version, regimen: regla.regimen, plan_id: regla.plan_id },
        dias_corridos: Number(campos.dias_corridos), fecha: campos.fecha,
        referencia: campos.referencia || null, evidencia: campos.evidencia || null,
      });
      if (activo.current) setResultado(respuesta);
    } catch (fallo) { if (activo.current) setError(errorFinanciador(fallo)); }
    finally { enviando.current = false; if (activo.current) setOcupado(false); }
  }
  return createPortal(<Modal title="Simular plazo" onClose={onClose} width={600}>
    <div className="space-y-4">
      <p className="text-sm"><strong>{regla.codigo} · v{regla.version}</strong><br />Fuente guardada: {regla.fuente}</p>
      <p className="rounded-md bg-badge-amber-bg p-3 text-sm text-badge-amber-fg">Consulta técnica sin escrituras. No cambia derechos ni convierte meses normativos en días.</p>
      <form onSubmit={calcular}>
        <fieldset disabled={ocupado} className="grid gap-4 sm:grid-cols-2">
          <Field label="Días corridos"><Input required type="number" min="0" step="1" value={campos.dias_corridos} onChange={cambiar("dias_corridos")} /></Field>
          <Field label="Fecha de evaluación"><Input required type="date" value={campos.fecha} onChange={cambiar("fecha")} /></Field>
          <Field label="Fecha de referencia (opcional)"><Input type="date" value={campos.referencia} onChange={cambiar("referencia")} /></Field>
          <Field label="Referencia de evidencia (opcional)"><Input maxLength={255} value={campos.evidencia} onChange={cambiar("evidencia")} /></Field>
          <div className="sm:col-span-2"><Button type="submit" disabled={ocupado}>{ocupado ? "Calculando…" : "Calcular simulación"}</Button></div>
        </fieldset>
      </form>
      {error && <p role="alert" className="text-sm text-badge-error-fg">{error}</p>}
      {resultado && <div role="status" className="space-y-2 rounded-md border border-borde p-3 text-sm">
        {resultado.estado === "calculado" ? <><p>Límite calculado: {resultado.limite}</p><p>Evaluación: {({ antes: "antes del límite", en: "en el límite", despues: "después del límite" })[resultado.relacion]}.</p></> : <p>{resultado.estado === "requiere_evidencia" ? "Falta fecha de referencia o evidencia; no se calculó un límite." : "La versión no coincide con el ámbito o la vigencia técnica consultados."}</p>}
        <p>Versión consultada: {resultado.regla.version}. Plazo simulado: {resultado.dias_corridos} días corridos.</p>
        <p>La evidencia es informada, no validada. Este resultado no habilita ni corta prestaciones.</p>
      </div>}
    </div>
  </Modal>, document.body);
}
