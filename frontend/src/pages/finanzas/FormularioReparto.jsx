import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { importeCentavos } from "@/api/finanzas";
import { query } from "@/api/queries";
import { Button, Field, Modal, Select, Input } from "@/components/ui";
import { useToast } from "@/components/ui/toast";

const ACCION = "configurar_repartos";

export default function FormularioReparto({ tipo, fila, mes, institucion, permisos, areas, conceptos, onClose }) {
  const qc = useQueryClient();
  const toast = useToast();
  const enCurso = useRef(false);
  const esCobertura = tipo === "cobertura-reparto";
  const esCorreccion = Boolean(fila);
  const [area, setArea] = useState(fila?.area ? String(fila.area) : "");
  const [concepto, setConcepto] = useState(fila?.concepto ? String(fila.concepto) : "");
  const [desde, setDesde] = useState(fila?.vigente_desde?.slice(0, 7) || mes);
  const [motivo, setMotivo] = useState("");
  const [confirmacionOperativa, setConfirmacionOperativa] = useState(false);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const areasPermitidas = areas.filter((item) => permisos.permite(ACCION, item.id));
  const areaElegida = areas.find((item) => String(item.id) === area);
  const conceptoElegido = conceptos.find((item) => String(item.id) === concepto);
  const datosCompletos = Boolean(area && desde && (esCobertura || conceptoElegido));
  const verificacion = useQuery({
    queryKey: ["finanzas", permisos.usuarioId, institucion.id, "verificacion-reparto", area, concepto, desde],
    queryFn: () => api.get(`/coberturas-actividad/verificacion/${query({
      institucion: institucion.id,
      area,
      periodo_economico: `${desde}-01`,
      concepto: esCobertura ? undefined : concepto,
    })}`),
    enabled: datosCompletos,
    staleTime: 0,
    gcTime: 0,
  });
  const puedeGuardar = datosCompletos
    && permisos.permite(ACCION, Number(area), conceptoElegido?.sensible)
    && verificacion.data?.integridad_tecnica
    && (!esCobertura || confirmacionOperativa)
    && (!esCorreccion || motivo.trim());

  async function guardar(e) {
    e.preventDefault();
    if (!puedeGuardar || enCurso.current) return;
    enCurso.current = true;
    setGuardando(true);
    setError("");
    try {
      const base = {
        institucion: institucion.id,
        area: Number(area),
        vigente_desde: `${desde}-01`,
        ...(esCorreccion ? {
          reemplaza: fila.id,
          motivo_correccion: motivo.trim(),
          ...(fila.vigente_desde?.slice(0, 7) === desde
            ? { vigente_hasta: fila.vigente_hasta }
            : {}),
        } : {}),
      };
      await api.post(esCobertura ? "/coberturas-actividad/" : "/reglas-reparto/", {
        ...base,
        ...(esCobertura
          ? { confirmacion_operativa: confirmacionOperativa }
          : { concepto: Number(concepto) }),
      });
      await qc.invalidateQueries({ queryKey: ["finanzas"] });
      toast.ok(esCobertura ? "Actividad verificada para repartir." : "Regla de reparto registrada.");
      onClose();
    } catch (err) {
      setError(typeof err.data === "object"
        ? Object.values(err.data || {}).flat().join(" · ")
        : (err.message || "No se pudo registrar la configuración."));
    } finally {
      enCurso.current = false;
      setGuardando(false);
    }
  }

  const resumen = verificacion.data;
  const estadoTitulo = !resumen?.integridad_tecnica
    ? "Actividad incompleta"
    : resumen?.cobertura_operativa_confirmada
      ? "Actividad verificada"
      : "Integridad técnica verificada";

  return <Modal title={esCorreccion
    ? `Corregir ${esCobertura ? "cobertura" : "regla"}`
    : esCobertura ? "Habilitar actividad para reparto" : "Agregar regla de reparto"}
  onClose={() => { if (!enCurso.current) onClose(); }} width={640}>
    <form onSubmit={guardar} className="space-y-4">
      <p className="text-md text-texto-debil">{esCobertura
        ? "Primero comprobamos los registros del sistema. Después confirmás desde qué mes el área carga aquí toda su actividad."
        : "Elegí qué concepto se distribuye entre las atenciones completadas del área. Antes de confirmar verás cantidades e importe."}</p>
      <Field label="Área"><Select required value={area} disabled={esCorreccion} onChange={(e) => setArea(e.target.value)}>
        <option value="">Elegí un área</option>
        {areasPermitidas.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}
      </Select></Field>
      {!esCobertura && <Field label="Concepto de gasto"><Select required value={concepto} disabled={esCorreccion} onChange={(e) => setConcepto(e.target.value)}>
        <option value="">Elegí un concepto</option>
        {conceptos.filter((item) => item.activo && permisos.permite(ACCION, Number(area), item.sensible)).map((item) => <option key={item.id} value={item.id}>{item.nombre}{item.sensible ? " · Sensible" : ""}</option>)}
      </Select></Field>}
      <Field label="Desde el mes"><Input type="month" required value={desde} onChange={(e) => setDesde(e.target.value)} /></Field>

      {verificacion.isLoading && <p className="text-sm text-texto-debil">Verificando actividad y totales…</p>}
      {verificacion.error && <p role="alert" className="text-md text-danger">No se pudo verificar la actividad. No se habilitará el reparto.</p>}
      {resumen && <section className={`rounded-lg border p-4 ${resumen.integridad_tecnica ? "border-badge-green-fg/40 bg-badge-green-bg" : "border-danger/40 bg-badge-error-bg"}`}>
        <h3 className="font-semibold">{estadoTitulo}</h3>
        <p className="mt-1 text-sm text-texto-debil">
          Control técnico: {resumen.atenciones_contrastables} atención(es) completada(s), {resumen.atenciones_registradas} hecho(s) financiero(s), diferencia {resumen.diferencias}.
        </p>
        <dl className="mt-3 grid gap-2 sm:grid-cols-3">
          <div><dt className="text-sm text-texto-debil">Total de atenciones</dt><dd className="font-semibold tabular-nums">{resumen.atenciones_registradas}</dd></div>
          <div><dt className="text-sm text-texto-debil">Importe aprobado visible</dt><dd className="font-semibold whitespace-nowrap">{importeCentavos(resumen.importe_total_centavos)}</dd></div>
          <div><dt className="text-sm text-texto-debil">Estimado por atención</dt><dd className="font-semibold whitespace-nowrap">{resumen.importe_estimado_por_atencion_centavos == null ? "Sin actividad" : importeCentavos(resumen.importe_estimado_por_atencion_centavos)}</dd></div>
        </dl>
        {!resumen.integridad_tecnica && <p className="mt-3 text-sm text-danger">Hay {resumen.diferencias} diferencia(s). El total de {importeCentavos(resumen.importe_total_centavos)} quedará pendiente hasta corregirlas.</p>}
        {resumen.integridad_tecnica && !resumen.cobertura_operativa_confirmada && !esCobertura && <p className="mt-3 text-sm text-texto-debil">La regla puede registrarse, pero el importe no se repartirá hasta confirmar la cobertura operativa del área.</p>}
      </section>}

      {esCobertura && resumen?.integridad_tecnica && <label className="flex items-start gap-3 rounded-lg border border-division p-3 text-sm">
        <input type="checkbox" className="mt-1" checked={confirmacionOperativa} onChange={(e) => setConfirmacionOperativa(e.target.checked)} />
        <span>Confirmo que desde {desde || "el mes elegido"} {areaElegida?.nombre || "el área"} registra todas sus atenciones en este sistema. Esta confirmación es distinta del control técnico mostrado arriba.</span>
      </label>}
      {esCorreccion && <Field label="Motivo de la corrección"><Input required value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Explicá brevemente por qué cambia" /></Field>}
      <p className="text-sm text-texto-debil">Esta configuración distribuye costos internos. No crea cargos, pagos ni tareas para el personal clínico.</p>
      {error && <p role="alert" className="text-md text-danger">{error}</p>}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" disabled={guardando} onClick={onClose}>Cancelar</Button>
        <Button type="submit" disabled={!puedeGuardar || guardando}>{guardando
          ? "Guardando…"
          : esCobertura ? "Verificar y habilitar" : "Registrar regla"}</Button>
      </div>
    </form>
  </Modal>;
}
