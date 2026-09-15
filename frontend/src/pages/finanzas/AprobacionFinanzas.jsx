import { useRef, useState } from "react";
import { api } from "@/api/client";
import { Badge, Button, Checkbox, Field, Textarea } from "@/components/ui";
import { fechaHora } from "@/lib/format";
import { mensajeErrorDinero } from "./dinero";

export function CampoAprobado({ puedeAprobar, aprobado, onChange, disabled = false }) {
  return <div className="space-y-2 border-t border-division pt-3">
    <Checkbox label="Aprobado" checked={puedeAprobar && aprobado} disabled={disabled || !puedeAprobar} onChange={(e) => onChange(e.target.checked)} />
    <p className="text-sm text-texto-debil">{!puedeAprobar
      ? "Tu permiso permite registrar. Quedará pendiente para que una persona autorizada lo apruebe."
      : aprobado ? "Se incorporará a los importes confirmados al guardar." : "Se guardará pendiente de aprobación, sin incorporarse a los importes confirmados."}</p>
  </div>;
}

export function EstadoAprobacion({ fila }) {
  const estado = fila.estado;
  const datos = { aprobado: ["Aprobado", "green"], pendiente_aprobacion: ["Pendiente de aprobación", "amber"], rechazado: ["Rechazado", "error"] }[estado];
  return <Badge tone={datos?.[1] || "gray"}>{datos?.[0] || "Estado no disponible"}</Badge>;
}

export function TrazaAprobacion({ fila }) {
  const autor = fila.autor ?? fila.registrado_por;
  const registro = fila.registrado;
  return <div className="space-y-1 text-sm text-texto-debil">
    {(autor || registro) && <p>Registrado{autor ? ` por usuario #${autor}` : ""}{registro ? ` · ${fechaHora(registro)}` : ""}</p>}
    {fila.aprobado_en && <p>Aprobado{fila.aprobado_por ? ` por usuario #${fila.aprobado_por}` : ""} · {fechaHora(fila.aprobado_en)}</p>}
    {fila.rechazado_en && <p>Rechazado{fila.rechazado_por ? ` por usuario #${fila.rechazado_por}` : ""} · {fechaHora(fila.rechazado_en)}</p>}
    {fila.motivo_rechazo && <p>Motivo del rechazo: {fila.motivo_rechazo}</p>}
  </div>;
}

export function DecisionAprobacion({ titulo, rechazar, url, datos = {}, onClose, onGuardado }) {
  const [motivo, setMotivo] = useState("");
  const bloqueo = useRef(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  async function guardar(e) {
    e.preventDefault();
    if (bloqueo.current || (rechazar && !motivo.trim())) return;
    bloqueo.current = true; setGuardando(true); setError("");
    try { await api.post(url, { ...datos, ...(rechazar ? { motivo: motivo.trim() } : {}) }); await onGuardado(); }
    catch (err) { setError(mensajeErrorDinero(err)); }
    finally { bloqueo.current = false; setGuardando(false); }
  }
  return <form onSubmit={guardar} className="space-y-4"><h3 className="text-lg font-semibold">{titulo}</h3>
    <p className="text-sm text-texto-debil">{rechazar ? "El registro conservará su historial y no se incorporará a los importes confirmados." : "Al aprobar, el registro se incorporará a los importes confirmados."}</p>
    {rechazar && <Field label="Motivo del rechazo"><Textarea required maxLength={255} disabled={guardando} value={motivo} onChange={(e) => setMotivo(e.target.value)} /></Field>}
    {error && <p role="alert" className="text-sm text-danger">{error}</p>}
    <div className="flex justify-end gap-2"><Button type="button" variant="ghost" disabled={guardando} onClick={onClose}>Volver al detalle</Button><Button type="submit" disabled={guardando || (rechazar && !motivo.trim())}>{guardando ? "Guardando…" : rechazar ? "Confirmar rechazo" : "Confirmar aprobación"}</Button></div>
  </form>;
}
