import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { errorFinanciador, opcionesFinanciador, rutaFinanciador } from "@/api/financiadores";
import { REGIMENES } from "@/components/financiadores/padronCampos";
import { Badge, Button, Card, Field, Input, Select, Spinner } from "@/components/ui";

import SimularPlazoDerechos from "./SimularPlazoDerechos";
import TrazabilidadReglas from "./TrazabilidadReglas";

const VACIO = { codigo: "", version: "1", fuente: "", regimen: "", plan_id: "", desde: "", hasta: "", fecha: "", motivo: "", plazo_dias_corridos: "" };

export default function BorradoresDerechos({ organizacion, usuarioId }) {
  const ruta = rutaFinanciador(organizacion.id, "borradores-derechos");
  const scope = ["financiadores", usuarioId, organizacion.id];
  const opciones = { gcTime: 0, retry: false, staleTime: Infinity, refetchOnWindowFocus: false };
  const consulta = useQuery({ ...opciones, queryKey: [...scope, "borradores-derechos"], queryFn: () => api.get(ruta) });
  const planes = useQuery({ ...opciones, queryKey: [...scope, "opciones-planes"], queryFn: () => opcionesFinanciador(organizacion.id, "planes") });
  const [trazabilidad, setTrazabilidad] = useState(false);
  const [simulacion, setSimulacion] = useState(null);
  const [formulario, setFormulario] = useState(VACIO);
  const [vista, setVista] = useState(null);
  const [errorVista, setErrorVista] = useState(null);
  const [previsualizando, setPrevisualizando] = useState(false);
  const activo = useRef(true);
  useEffect(() => { activo.current = true; return () => { activo.current = false; }; }, []);
  const [guardando, setGuardando] = useState(false);
  const [requiereConsulta, setRequiereConsulta] = useState(false);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState("");
  const enviando = useRef(false);
  const historial = consulta.data?.borradores || [];
  const ocupado = guardando || previsualizando || consulta.isFetching || planes.isFetching || requiereConsulta || !consulta.isSuccess || !planes.isSuccess;
  const cambiar = (campo) => (e) => {
    setVista(null); setErrorVista(null);
    setFormulario((actual) => ({ ...actual, [campo]: e.target.value }));
  };
  async function recargar() {
    setVista(null); setErrorVista(null);
    setRequiereConsulta(true);
    const resultado = await consulta.refetch();
    if (!resultado.error) { setRequiereConsulta(false); setError(null); }
    return !resultado.error;
  }
  async function guardar(e) {
    e.preventDefault();
    if (ocupado || enviando.current) return;
    const soloVista = e.nativeEvent.submitter?.value === "previsualizar";
    enviando.current = true;
    setGuardando(!soloVista); setPrevisualizando(soloVista);
    setVista(null); setErrorVista(null); setError(null); setMensaje("");
    const { motivo, fecha, ...campos } = formulario;
    const nueva = { ...campos, version: Number(campos.version), plan_id: campos.plan_id ? Number(campos.plan_id) : null, hasta: campos.hasta || null, plazo_dias_corridos: campos.plazo_dias_corridos === "" ? null : Number(campos.plazo_dias_corridos) };
    try {
      const destino = soloVista ? rutaFinanciador(organizacion.id, "borradores-derechos/previsualizar") : ruta;
      const resultado = await api.post(destino, { propuesta: [...historial, nueva], motivo, fecha, regimen: nueva.regimen, plan_id: nueva.plan_id });
      if (soloVista) {
        if (activo.current) setVista(resultado);
        return;
      }
      setMensaje(resultado.nuevas.length ? "Borrador guardado. Los derechos no cambiaron." : "No se agregaron versiones nuevas.");
      setFormulario(VACIO);
      await recargar();
    } catch (fallo) {
      if (soloVista) { if (activo.current) setErrorVista(fallo); }
      else { setError(fallo); setRequiereConsulta(true); }
    } finally { enviando.current = false; setGuardando(false); setPrevisualizando(false); }
  }
  const falloConsulta = consulta.error || planes.error;
  return <section className="space-y-5" aria-label="Reglas de derechos">
    <header className="space-y-2">
      <h1 className="text-cifra font-bold">Reglas de derechos</h1>
      <p className="text-sm text-texto-suave">Versiones de configuración en estado Borrador. La simulación temporal no aprueba ni activa derechos.</p>
      <p className="rounded-md border border-borde bg-badge-amber-bg p-3 text-sm text-badge-amber-fg">Guardar una versión no aprueba ni activa derechos.</p>
    </header>
    {mensaje && <p role="status" className="text-sm text-badge-green-fg">{mensaje}</p>}
    {(error || falloConsulta) && <div role="alert" className="rounded-md border border-borde p-3 text-sm">
      <p>{errorFinanciador(error || falloConsulta)}</p>
      <p>El resultado de una escritura fallida puede ser desconocido. Consultá las versiones antes de otro intento; no se reintenta automáticamente.</p>
    </div>}
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h2 className="text-lg font-semibold">Versiones guardadas</h2>
      <div className="flex flex-wrap gap-3">
        <Button variant="secondary" disabled={guardando || previsualizando} onClick={() => setTrazabilidad(true)}>Ver trazabilidad</Button>
        <Button variant="secondary" disabled={guardando || previsualizando || consulta.isFetching || planes.isFetching} onClick={() => Promise.all([planes.refetch(), recargar()])}>Volver a consultar</Button>
      </div>
    </div>
    <div className="grid items-start gap-5 xl:grid-cols-2">
      <Card className="min-w-0 p-4">
        {consulta.isFetching ? <Spinner label="Consultando versiones…" /> : consulta.isError ? <p>No se pudo consultar el historial.</p> : historial.length ? <ol aria-label="Versiones guardadas" className="divide-y divide-division">
          {historial.map((fila) => <li className="space-y-2 py-4 first:pt-0" key={`${fila.regimen}:${fila.plan_id}:${fila.codigo}:${fila.version}`}>
            <div className="flex flex-wrap items-center gap-2"><h3 className="break-all font-semibold">{fila.codigo} · v{fila.version}</h3><Badge>Borrador</Badge><Button size="sm" variant="secondary" onClick={() => setSimulacion(fila)}>Simular plazo</Button></div>
            <p className="text-sm">{REGIMENES[fila.regimen] || fila.regimen} · {fila.plan_id == null ? "Todos los planes" : planes.data?.find((p) => p.id === fila.plan_id)?.nombre || `Plan ${fila.plan_id}`}</p>
            <p className="text-sm text-texto-suave">{fila.plazo_dias_corridos == null ? "Sin plazo configurado" : `Plazo configurado: ${fila.plazo_dias_corridos} días corridos`}</p>
            <dl className="space-y-1 break-words text-sm text-texto-suave"><div><dt className="inline font-medium">Intervalo técnico: </dt><dd className="inline">{fila.desde} → {fila.hasta || "Sin fin informado"} {fila.hasta ? "(fin exclusivo)" : ""}</dd></div><div><dt className="inline font-medium">Fuente informada: </dt><dd className="inline">{fila.fuente}</dd></div></dl>
          </li>)}
        </ol> : <p className="text-sm text-texto-suave">Todavía no hay versiones guardadas.</p>}
      </Card>
      {organizacion.rol === "admin" ? <Card className="min-w-0 space-y-4 p-4">
        <h2 className="text-lg font-semibold">Nueva versión</h2>
        <p className="text-sm text-texto-suave">Sólo metadatos del borrador. Las fechas no son un corte de atención; la fuente informada no acredita normativa vigente.</p>
        <form onSubmit={guardar}>
          <fieldset disabled={ocupado} className="grid gap-4 sm:grid-cols-2">
            <Field label="Código de regla"><Input required maxLength={60} value={formulario.codigo} onChange={cambiar("codigo")} /></Field>
            <Field label="Versión"><Input required type="number" min="1" step="1" value={formulario.version} onChange={cambiar("version")} /></Field>
            <Field label="Régimen"><Select required value={formulario.regimen} onChange={cambiar("regimen")}><option value="">Seleccionar régimen</option>{Object.entries(REGIMENES).map(([valor, nombre]) => <option key={valor} value={valor}>{nombre}</option>)}</Select></Field>
            <Field label="Plan"><Select value={formulario.plan_id} onChange={cambiar("plan_id")}><option value="">Todos los planes</option>{planes.data?.map((plan) => <option key={plan.id} value={plan.id}>{plan.nombre}</option>)}</Select></Field>
            <Field label="Inicio técnico"><Input required type="date" value={formulario.desde} onChange={cambiar("desde")} /></Field>
            <Field label="Fin técnico exclusivo (opcional)"><Input type="date" value={formulario.hasta} onChange={cambiar("hasta")} /></Field>
            <div className="sm:col-span-2"><Field label="Fuente informada"><Input required maxLength={255} value={formulario.fuente} onChange={cambiar("fuente")} /></Field></div>
            <Field label="Plazo en días corridos (opcional)"><Input type="number" min="0" step="1" value={formulario.plazo_dias_corridos} onChange={cambiar("plazo_dias_corridos")} /></Field>
            <Field label="Fecha de consulta técnica"><Input required type="date" value={formulario.fecha} onChange={cambiar("fecha")} /></Field>
            <div className="sm:col-span-2"><Field label="Motivo del registro"><Input required maxLength={255} value={formulario.motivo} onChange={cambiar("motivo")} /></Field></div>
            <div className="flex flex-wrap gap-3 sm:col-span-2">
              <Button type="submit" disabled={ocupado}>{guardando ? "Guardando…" : "Guardar borrador"}</Button>
              <Button type="submit" value="previsualizar" variant="secondary" disabled={ocupado}>{previsualizando ? "Previsualizando…" : "Previsualizar propuesta"}</Button>
            </div>
          </fieldset>
          {requiereConsulta && <p className="mt-3 text-sm">Es necesario volver a consultar antes de guardar otra versión.</p>}
        </form>
        {errorVista && <p role="alert" className="text-sm text-badge-error-fg">No se pudo previsualizar. {errorFinanciador(errorVista)}</p>}
        {vista && <section aria-label="Vista previa de la propuesta" className="space-y-3 rounded-md border border-borde p-3 text-sm">
          <h3 className="font-semibold">Vista previa técnica</h3>
          <p>No se guardaron versiones ni se modificaron derechos.</p>
          <p>Versiones que se agregarían: {vista.nuevas.length}.</p>
          <ul className="space-y-1 break-words">{vista.nuevas.map((fila) => <li key={`${fila.regimen}:${fila.plan_id}:${fila.codigo}:${fila.version}`}>
            {fila.codigo} · v{fila.version} · {fila.plazo_dias_corridos == null ? "Sin plazo configurado" : `${fila.plazo_dias_corridos} días corridos`}
          </li>)}</ul>
          {[ ["Antes", vista.antes], ["Después", vista.despues] ].map(([nombre, estado]) => <div key={nombre}>
            <p>{nombre}: {estado.coincidencias.length} coincidencias técnicas. {estado.conflicto ? "Conflicto: no hay una regla única." : "Sin conflicto técnico."}</p>
            <p className="break-words">{estado.coincidencias.map((fila) => `${fila.codigo} · v${fila.version}`).join(", ") || "Sin coincidencias."}</p>
          </div>)}
          <p>No es una aprobación ni una reserva; al guardar se valida nuevamente la historia actual. No calcula personas afectadas ni decide prestaciones.</p>
        </section>}
      </Card> : <Card className="p-4"><p className="text-sm">Acceso de consulta. La administración del financiador puede registrar versiones.</p></Card>}
    </div>
    {trazabilidad && <TrazabilidadReglas key={`${usuarioId}:${organizacion.id}`} organizacion={organizacion} usuarioId={usuarioId} onClose={() => setTrazabilidad(false)} />}
    {simulacion && <SimularPlazoDerechos key={`${simulacion.regimen}:${simulacion.plan_id}:${simulacion.codigo}:${simulacion.version}`} organizacion={organizacion} regla={simulacion} onClose={() => setSimulacion(null)} />}
  </section>;
}
