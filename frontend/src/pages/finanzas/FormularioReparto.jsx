import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { Button, Field, Modal, Select, Input } from "@/components/ui";
import { useToast } from "@/components/ui/toast";

const ACCION = "configurar_repartos";

export default function FormularioReparto({ tipo, mes, institucion, permisos, areas, conceptos, onClose }) {
  const qc = useQueryClient();
  const toast = useToast();
  const enCurso = useRef(false);
  const [area, setArea] = useState("");
  const [concepto, setConcepto] = useState("");
  const [desde, setDesde] = useState(mes);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const esCobertura = tipo === "cobertura-reparto";
  const areasPermitidas = areas.filter((fila) => permisos.permite(ACCION, fila.id));
  const conceptoElegido = conceptos.find((fila) => String(fila.id) === concepto);
  const puedeGuardar = area && desde && (esCobertura || conceptoElegido)
    && permisos.permite(ACCION, Number(area), conceptoElegido?.sensible);

  async function guardar(e) {
    e.preventDefault();
    if (!puedeGuardar || enCurso.current) return;
    enCurso.current = true;
    setGuardando(true);
    setError("");
    try {
      const base = { institucion: institucion.id, area: Number(area), vigente_desde: `${desde}-01` };
      await api.post(esCobertura ? "/coberturas-actividad/" : "/reglas-reparto/", {
        ...base,
        ...(esCobertura ? {} : { concepto: Number(concepto) }),
      });
      await qc.invalidateQueries({ queryKey: ["finanzas"] });
      toast.ok(esCobertura ? "Actividad habilitada para repartir." : "Regla de reparto registrada.");
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

  return <Modal title={esCobertura ? "Habilitar actividad para reparto" : "Agregar regla de reparto"} onClose={() => { if (!enCurso.current) onClose(); }} width={600}>
    <form onSubmit={guardar} className="space-y-4">
      <p className="text-md text-texto-debil">{esCobertura
        ? "Indicá desde qué mes la actividad del área es fiable. Los meses anteriores seguirán pendientes."
        : "Elegí qué concepto se distribuye entre las atenciones completadas del área."}</p>
      <Field label="Área"><Select required value={area} onChange={(e) => setArea(e.target.value)}>
        <option value="">Elegí un área</option>
        {areasPermitidas.map((fila) => <option key={fila.id} value={fila.id}>{fila.nombre}</option>)}
      </Select></Field>
      {!esCobertura && <Field label="Concepto de gasto"><Select required value={concepto} onChange={(e) => setConcepto(e.target.value)}>
        <option value="">Elegí un concepto</option>
        {conceptos.filter((fila) => fila.activo && permisos.permite(ACCION, Number(area), fila.sensible)).map((fila) => <option key={fila.id} value={fila.id}>{fila.nombre}{fila.sensible ? " · Sensible" : ""}</option>)}
      </Select></Field>}
      <Field label="Desde el mes"><Input type="month" required value={desde} onChange={(e) => setDesde(e.target.value)} /></Field>
      <p className="text-sm text-texto-debil">Esta configuración no crea cargos, pagos ni tareas para el personal clínico.</p>
      {error && <p role="alert" className="text-md text-danger">{error}</p>}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" disabled={guardando} onClick={onClose}>Cancelar</Button>
        <Button type="submit" disabled={!puedeGuardar || guardando}>{guardando ? "Guardando…" : "Confirmar"}</Button>
      </div>
    </form>
  </Modal>;
}
