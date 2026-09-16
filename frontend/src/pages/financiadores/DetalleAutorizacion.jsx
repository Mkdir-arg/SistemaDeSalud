import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { errorFinanciador } from "@/api/financiadores";
import { Badge, Button, Field, Input, Modal, Select, Spinner, Textarea } from "@/components/ui";
import { fechaHora } from "@/lib/format";

export const ESTADOS_AUTORIZACION = {
  pendiente: "Pendiente", observada: "Observada", aprobada: "Aprobada",
  rechazada: "Rechazada", vencida: "Vencida", anulada: "Anulada",
};
const fecha = (valor) => valor ? String(valor).slice(0, 10).split("-").reverse().join("/") : "—";

export function EstadoAutorizacion({ estado }) {
  return <Badge tone={estado === "aprobada" ? "green" : ["pendiente", "observada"].includes(estado) ? "amber" : "gray"}>{ESTADOS_AUTORIZACION[estado] || estado}</Badge>;
}

export function ErrorAutorizacion({ error, reintentar }) {
  return <div role="alert" className="rounded-md bg-badge-error-bg p-3 text-sm text-badge-error-fg">
    <p>{errorFinanciador(error)}</p>
    {reintentar && <Button type="button" size="sm" variant="secondary" className="mt-2" onClick={reintentar}>Actualizar solicitud</Button>}
  </div>;
}

export function PaginasAutorizacion({ consulta, pagina, cambiar }) {
  return <div className="flex flex-wrap items-center justify-between gap-3 border-t border-division p-4 text-sm">
    <span>{consulta.data?.count ?? 0} solicitudes · Página {pagina}</span>
    <div className="flex gap-2">
      <Button type="button" size="sm" variant="secondary" disabled={pagina <= 1 || consulta.isFetching} onClick={() => cambiar(pagina - 1)}>Anterior</Button>
      <Button type="button" size="sm" variant="secondary" disabled={!consulta.data?.next || consulta.isFetching} onClick={() => cambiar(pagina + 1)}>Siguiente</Button>
    </div>
  </div>;
}

export default function DetalleAutorizacion({ id, ambito, scope, onClose, onGuardado, onVerSolicitud, ocupadoClinica = false }) {
  const parametros = new URLSearchParams(ambito).toString();
  const consulta = useQuery({
    queryKey: [...scope, "detalle-autorizacion", id, parametros],
    queryFn: () => api.get(`/autorizaciones-cobertura/${id}/?${parametros}`),
    gcTime: 0, retry: false,
  });
  const d = consulta.data;
  return <Modal title={`Solicitud de autorización ${id}`} onClose={onClose} width={760}>
    {consulta.isLoading ? <Spinner label="Consultando solicitud…" /> : consulta.error ? <ErrorAutorizacion error={consulta.error} reintentar={consulta.refetch} /> : d && <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2"><EstadoAutorizacion estado={d.estado} />{d.urgente && <Badge tone="error">Urgente</Badge>}</div>
      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        {[["Hospital", d.institucion_nombre], ["Financiador", d.financiador_nombre], ["Afiliado", d.afiliado_nombre], ["Número de afiliado", d.afiliado_numero], ["Documento", d.documento], ["Prestación", d.prestacion_nombre], ["Cantidad solicitada", d.cantidad_solicitada], ["Plazo de respuesta", d.plazo_respuesta ? fechaHora(d.plazo_respuesta) : "Sin vencimiento automático"], ["Solicitud", fechaHora(d.creado)]].map(([label, valor]) => <div key={label}><dt className="text-texto-debil">{label}</dt><dd className="mt-1 break-words font-semibold">{valor ?? "—"}</dd></div>)}
      </dl>
      {d.anterior && <div className="flex flex-wrap items-center gap-2 rounded-md bg-superficie-2 p-3 text-sm"><span>Solicitud anterior: #{d.anterior}</span>{onVerSolicitud && <Button type="button" size="sm" variant="secondary" onClick={() => onVerSolicitud(d.anterior)}>Ver antecedente {d.anterior}</Button>}</div>}
      <section><h3 className="font-semibold">Justificación para el financiador</h3><p className="mt-1 whitespace-pre-wrap break-words text-sm">{d.justificacion}</p></section>
      {Number(d.cantidad_aprobada) > 0 && <section className="rounded-md bg-superficie-2 p-3 text-sm">
        <h3 className="font-semibold">Alcance de la aprobación</h3>
        <p className="mt-1">{d.cantidad_aprobada} unidades · Del {fecha(d.vigencia_desde)} al {fecha(d.vigencia_hasta)}</p>
        <p className="mt-1">Disponibles: {d.cantidades?.disponible ?? "—"} · Comprometidas: {d.cantidades?.comprometida ?? "—"} · Realizadas: {d.cantidades?.consumida ?? "—"}</p>
        {d.numero_externo && <p className="mt-1">Número externo: {d.numero_externo}</p>}
      </section>}
      {d.motivo_resolucion && <section><h3 className="font-semibold">Motivo de la resolución</h3><p className="mt-1 whitespace-pre-wrap break-words text-sm">{d.motivo_resolucion}</p>{d.evidencia && <p className="mt-2 whitespace-pre-wrap break-words text-sm text-texto-debil">Evidencia: {d.evidencia}</p>}</section>}
      <p className="text-sm text-texto-debil">Aprobar habilita la prestación dentro de su vigencia y cantidad. No registra una atención realizada, no aumenta el cupo del plan ni acepta un copago.</p>
      <AccionesAutorizacion key={`${d.id}:${d.revision}`} solicitud={d} ambito={ambito} refrescar={consulta.refetch} onGuardado={onGuardado} bloqueado={ocupadoClinica || consulta.isFetching} />
      <section className="border-t border-division pt-4"><h3 className="font-semibold">Historial de la solicitud</h3>
        <ol className="mt-3 space-y-3">{(d.historial || []).map((h) => <li key={h.id} className="border-l-2 border-division pl-3 text-sm"><p className="font-semibold">{ESTADOS_AUTORIZACION[h.estado] || h.accion}</p><p className="mt-1 whitespace-pre-wrap break-words">{h.motivo}</p><p className="mt-1 text-texto-debil">{fechaHora(h.creado)} · {h.usuario_nombre || "Usuario registrado"}</p></li>)}</ol>
      </section>
    </div>}
  </Modal>;
}

function AccionesAutorizacion({ solicitud: d, ambito, refrescar, onGuardado, bloqueado }) {
  const [accion, setAccion] = useState("");
  const [formulario, setFormulario] = useState({ decision: "", motivo: "", evidencia: "", numero_externo: "", cantidad_aprobada: String(d.cantidad_solicitada), vigencia_desde: "", vigencia_hasta: "", justificacion: "" });
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const enVuelo = useRef(false);
  const clave = useRef(crypto.randomUUID());
  const editar = (campo, valor) => { setFormulario((f) => ({ ...f, [campo]: valor })); clave.current = crypto.randomUUID(); };
  const conflicto = error?.status === 409 || (error?.status === 400 && /cambi[oó]|actualiz/i.test(errorFinanciador(error)));
  const aprobado = formulario.decision === "aprobar";
  const valido = accion === "resolver" ? formulario.decision && formulario.motivo.trim() && (!aprobado || (formulario.evidencia.trim() && Number(formulario.cantidad_aprobada) > 0 && formulario.vigencia_desde && formulario.vigencia_hasta)) : accion === "reenviar" ? formulario.justificacion.trim() : formulario.motivo.trim();

  async function guardar(event) {
    event.preventDefault();
    if (!valido || bloqueado || enVuelo.current || conflicto) return;
    enVuelo.current = true; setOcupado(true); setError(null);
    const body = accion === "resolver" ? {
      decision: formulario.decision, motivo: formulario.motivo.trim(), evidencia: formulario.evidencia.trim(), numero_externo: formulario.numero_externo.trim(),
      ...(aprobado ? { cantidad_aprobada: Number(formulario.cantidad_aprobada), vigencia_desde: formulario.vigencia_desde, vigencia_hasta: formulario.vigencia_hasta } : {}),
    } : accion === "reenviar" ? { justificacion: formulario.justificacion.trim() } : { motivo: formulario.motivo.trim() };
    try {
      await api.post(`/autorizaciones-cobertura/${d.id}/${accion}/?${new URLSearchParams(ambito)}`, { ...body, revision: d.revision, clave: clave.current });
      await onGuardado("Solicitud actualizada. La decisión no registra una prestación realizada.");
    } catch (e) { setError(e); }
    finally { enVuelo.current = false; setOcupado(false); }
  }

  if (!d.puede_resolver && !d.puede_reenviar && !d.puede_anular) return <p className="text-sm text-texto-debil">Esta solicitud está disponible sólo para consulta con tu acceso actual.</p>;
  return <section className="space-y-3 border-t border-division pt-4">
    {!accion ? <div className="flex flex-wrap gap-2">
      {d.puede_resolver && <Button disabled={bloqueado} onClick={() => setAccion("resolver")}>Resolver solicitud</Button>}
      {d.puede_reenviar && <Button variant="secondary" disabled={bloqueado} onClick={() => setAccion("reenviar")}>Responder observación</Button>}
      {d.puede_anular && <Button variant="ghost" disabled={bloqueado} onClick={() => setAccion("anular")}>Anular solicitud</Button>}
    </div> : <form className="space-y-3" onSubmit={guardar}>
      {error && <ErrorAutorizacion error={error} reintentar={conflicto ? refrescar : undefined} />}
      {conflicto && <p className="text-sm text-texto-debil">La solicitud cambió mientras la revisabas. Actualizala y revisá la nueva decisión antes de continuar.</p>}
      <fieldset disabled={ocupado || bloqueado || conflicto} className="space-y-3">
        {accion === "resolver" && <Field label="Decisión"><Select required value={formulario.decision} onChange={(e) => editar("decision", e.target.value)}><option value="">Seleccioná una decisión</option><option value="observar">Observar</option><option value="aprobar">Aprobar</option><option value="rechazar">Rechazar</option></Select></Field>}
        {accion === "reenviar" ? <Field label="Justificación actualizada" hint="Incluí sólo lo necesario para responder al financiador."><Textarea required maxLength={1000} value={formulario.justificacion} onChange={(e) => editar("justificacion", e.target.value)} /></Field> : <Field label={accion === "anular" ? "Motivo de anulación" : "Motivo de la decisión"}><Textarea required maxLength={255} value={formulario.motivo} onChange={(e) => editar("motivo", e.target.value)} /></Field>}
        {accion === "resolver" && <>
          <Field label="Evidencia de la decisión" hint={aprobado ? "Obligatoria para aprobar. Referencia o constancia de la revisión administrativa." : "Referencia o constancia de la revisión administrativa, si corresponde."}><Textarea required={aprobado} maxLength={1000} value={formulario.evidencia} onChange={(e) => editar("evidencia", e.target.value)} /></Field>
          <Field label="Número externo (opcional)"><Input maxLength={120} value={formulario.numero_externo} onChange={(e) => editar("numero_externo", e.target.value)} /></Field>
          {aprobado && <div className="grid gap-3 sm:grid-cols-3"><Field label="Cantidad autorizada"><Input type="number" min="1" max={d.cantidad_solicitada} step="1" required value={formulario.cantidad_aprobada} onChange={(e) => editar("cantidad_aprobada", e.target.value)} /></Field><Field label="Válida desde"><Input type="date" required value={formulario.vigencia_desde} onChange={(e) => editar("vigencia_desde", e.target.value)} /></Field><Field label="Válida hasta"><Input type="date" min={formulario.vigencia_desde || undefined} required value={formulario.vigencia_hasta} onChange={(e) => editar("vigencia_hasta", e.target.value)} /></Field></div>}
        </>}
      </fieldset>
      <div className="flex flex-wrap gap-2"><Button type="submit" disabled={!valido || ocupado || bloqueado || conflicto}>{ocupado ? "Guardando…" : accion === "resolver" ? "Registrar decisión" : accion === "reenviar" ? "Reenviar solicitud" : "Confirmar anulación"}</Button><Button type="button" variant="ghost" disabled={ocupado} onClick={() => { setAccion(""); setError(null); }}>Cancelar</Button></div>
    </form>}
  </section>;
}
