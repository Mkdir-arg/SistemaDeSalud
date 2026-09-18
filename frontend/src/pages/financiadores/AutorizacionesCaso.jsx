import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { Ayuda, Badge, Button, Field, Input, Select, Spinner, Textarea } from "@/components/ui";
import { fechaHora } from "@/lib/format";
import DetalleAutorizacion, { ErrorAutorizacion, EstadoAutorizacion, PaginasAutorizacion } from "./DetalleAutorizacion";
import { POR_PAGINA } from "@/api/queries";

export default function AutorizacionesCaso({ caso, ocupadoClinica }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const scope = ["autorizaciones-caso", user?.id, caso.institucion, caso.id];
  const [pagina, setPagina] = useState(1);
  const [detalle, setDetalle] = useState(null);
  const [mensaje, setMensaje] = useState("");
  const contexto = useQuery({
    queryKey: [...scope, "contexto", caso.nodo_actual, caso.actualizado],
    queryFn: () => api.get(`/autorizaciones-cobertura/contexto/?caso=${caso.id}`),
    gcTime: 0, retry: false,
  });
  const consulta = useQuery({
    queryKey: [...scope, "lista", pagina, caso.actualizado],
    queryFn: () => api.get(`/autorizaciones-cobertura/?${new URLSearchParams({ institucion: caso.institucion, caso: caso.id, page: pagina, page_size: POR_PAGINA })}`),
    gcTime: 0, retry: false,
  });
  async function actualizar(texto) {
    setDetalle(null); setMensaje(texto);
    await Promise.all([
      qc.invalidateQueries({ queryKey: scope }),
      qc.invalidateQueries({ queryKey: ["cobertura-caso"] }),
      qc.invalidateQueries({ queryKey: ["detalle", "casos"] }),
    ]);
  }
  const datos = contexto.data;
  const espera = datos?.espera_autorizacion;
  return <section aria-label="Autorizaciones de este caso" className="mt-5 space-y-4 border-t border-division pt-5">
    <div className="flex flex-wrap items-center justify-between gap-2"><div className="flex items-center gap-2"><h3 className="font-semibold">Autorizaciones de este caso</h3><Ayuda>Se envía al financiador sólo la justificación necesaria. La autorización conserva el hospital, la prestación y el intento de atención que la originaron.</Ayuda></div><Button size="sm" variant="ghost" disabled={contexto.isFetching || consulta.isFetching || ocupadoClinica} onClick={() => actualizar("")}>Actualizar solicitudes</Button></div>
    {mensaje && <p role="status" className="rounded-md bg-badge-green-bg p-3 text-sm text-badge-green-fg">{mensaje}</p>}
    {contexto.isLoading ? <Spinner label="Consultando el paso de atención…" /> : contexto.error ? <ErrorAutorizacion error={contexto.error} reintentar={contexto.refetch} /> : datos && <>
      {espera?.estado === "esperando" && <EsperaAutorizacion key={`${caso.id}:${espera.intento}`} caso={caso} espera={espera} puedeContinuar={datos.puede_continuar_autorizacion} ocupado={ocupadoClinica} actualizar={actualizar} />}
      {datos.puede_solicitar ? <SolicitarAutorizacion key={`${caso.id}:${datos.intento}`} caso={caso} contexto={datos} ocupadoClinica={ocupadoClinica || contexto.isFetching} actualizar={actualizar} /> : datos.motivo && <p className="text-sm text-texto-debil">{datos.motivo}</p>}
    </>}
    {consulta.isLoading ? <Spinner label="Consultando solicitudes del caso…" /> : consulta.error ? <ErrorAutorizacion error={consulta.error} reintentar={consulta.refetch} /> : <>
      {(consulta.data?.results || []).length ? <ul className="divide-y divide-division rounded-md border border-division">
        {consulta.data.results.map((s) => <li key={s.id} className="flex flex-wrap items-start justify-between gap-3 p-3 text-sm">
          <div><p className="font-semibold">{s.prestacion_nombre} · {s.cantidad_solicitada} unidades</p><p className="mt-1 text-texto-debil">{s.financiador_nombre} · {fechaHora(s.creado)}</p><div className="mt-2 flex flex-wrap gap-2"><EstadoAutorizacion estado={s.estado} />{s.urgente && <Badge tone="error">Urgente</Badge>}</div></div>
          <Button size="sm" variant="secondary" onClick={() => setDetalle(s.id)}>Ver solicitud {s.id}</Button>
        </li>)}
      </ul> : <p className="text-sm text-texto-debil">Este caso todavía no tiene solicitudes de autorización.</p>}
      {(consulta.data?.count > 0 || pagina > 1) && <PaginasAutorizacion consulta={consulta} pagina={pagina} cambiar={setPagina} />}
    </>}
    {detalle && <DetalleAutorizacion id={detalle} ambito={{ institucion: caso.institucion }} scope={scope} onClose={() => setDetalle(null)} onVerSolicitud={setDetalle} onGuardado={actualizar} ocupadoClinica={ocupadoClinica} />}
  </section>;
}

function SolicitarAutorizacion({ caso, contexto, ocupadoClinica, actualizar }) {
  const [abierto, setAbierto] = useState(false);
  const [prestacion, setPrestacion] = useState("");
  const [cantidad, setCantidad] = useState("1");
  const [justificacion, setJustificacion] = useState("");
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const clave = useRef(crypto.randomUUID());
  const enVuelo = useRef(false);
  const cambiar = (setter) => (event) => { setter(event.target.value); clave.current = crypto.randomUUID(); };
  const valido = prestacion && Number.isInteger(Number(cantidad)) && Number(cantidad) > 0 && justificacion.trim();
  async function solicitar(event) {
    event.preventDefault();
    if (!valido || ocupadoClinica || enVuelo.current) return;
    enVuelo.current = true; setOcupado(true); setError(null);
    try {
      await api.post("/autorizaciones-cobertura/", { caso: caso.id, prestacion: Number(prestacion), intento: contexto.intento, cantidad: Number(cantidad), justificacion: justificacion.trim(), clave: clave.current });
      setAbierto(false); setPrestacion(""); setJustificacion(""); clave.current = crypto.randomUUID();
      await actualizar("Solicitud enviada al financiador. La prestación todavía no se registró como realizada.");
    } catch (e) { setError(e); }
    finally { enVuelo.current = false; setOcupado(false); }
  }
  return !abierto ? <Button variant="secondary" disabled={ocupadoClinica || !(contexto.prestaciones || []).length} onClick={() => setAbierto(true)}>Solicitar autorización</Button> : <form onSubmit={solicitar} className="space-y-3 rounded-md border border-division p-4">
    {error && <ErrorAutorizacion error={error} />}
    <fieldset disabled={ocupado || ocupadoClinica} className="space-y-3">
      <Field label="Prestación a autorizar"><Select required value={prestacion} onChange={cambiar(setPrestacion)}><option value="">Seleccioná una prestación</option>{(contexto.prestaciones || []).map((p) => <option key={p.id} value={p.id}>{p.codigo ? `${p.codigo} · ` : ""}{p.nombre}</option>)}</Select></Field>
      <Field label="Cantidad solicitada"><Input type="number" min="1" max="100000" step="1" required value={cantidad} onChange={cambiar(setCantidad)} /></Field>
      <Field label="Justificación para el financiador" ayuda="Describí el motivo administrativo y clínico mínimo. Evitá copiar la historia clínica completa."><Textarea required maxLength={1000} value={justificacion} onChange={cambiar(setJustificacion)} /></Field>
    </fieldset>
    <div className="flex flex-wrap gap-2"><Button type="submit" disabled={!valido || ocupado || ocupadoClinica}>{ocupado ? "Enviando…" : "Enviar solicitud"}</Button><Button type="button" variant="ghost" disabled={ocupado} onClick={() => setAbierto(false)}>Cancelar</Button></div>
  </form>;
}

function EsperaAutorizacion({ caso, espera, puedeContinuar, ocupado, actualizar }) {
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState(null);
  const [guardando, setGuardando] = useState(false);
  async function continuar(event) {
    event.preventDefault();
    if (!motivo.trim() || guardando || ocupado) return;
    setGuardando(true); setError(null);
    try {
      await api.post(`/casos/${caso.id}/continuar-autorizacion/`, { intento: espera.intento, motivo: motivo.trim() });
      await actualizar("Espera levantada. La prestación sigue pendiente de realización; la autorización y los importes se conservan.");
    } catch (e) { setError(e); }
    finally { setGuardando(false); }
  }
  return <div className="space-y-3 rounded-md bg-badge-amber-bg p-4 text-sm text-badge-amber-fg" role="region" aria-label="Espera de autorización">
    <h4 className="font-semibold">Atención programada en espera de autorización</h4>
    <p>El paso de atención permanece pendiente. La aprobación no registra la prestación como realizada.</p>
    {espera.motivo && <p>{espera.motivo}</p>}
    {puedeContinuar && <form className="space-y-3" onSubmit={continuar}>
      <p>Continuar con motivo levanta esta espera; no aprueba cobertura ni acepta cargos del paciente.</p>
      {error && <ErrorAutorizacion error={error} />}
      <Field label="Motivo para continuar la atención"><Textarea required maxLength={255} disabled={ocupado || guardando} value={motivo} onChange={(e) => setMotivo(e.target.value)} /></Field>
      <Button type="submit" disabled={ocupado || guardando || !motivo.trim()}>{guardando ? "Registrando…" : "Levantar espera con motivo"}</Button>
    </form>}
  </div>;
}
