import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { ESTADOS_CARGA, importeARS } from "@/api/finanzas";
import { Button, Checkbox, Field, Input, Modal, Select, Textarea } from "@/components/ui";
import { useToast } from "@/components/ui/toast";

const CONFIGURAR = "configurar_gastos_esperados";
const TITULOS = {
  gasto: "Registrar gasto", reemplazo: "Reemplazar carga", concepto: "Nuevo concepto de gasto",
  expectativa: "Configurar gasto esperado", indicar: "Indicar estado de carga",
  aprobar: "Aprobar gasto", rechazar: "Rechazar gasto", ajuste: "Ajustar gasto aprobado",
};

export default function FormularioGasto({ tipo, fila, mes, institucion, permisos, areas, conceptos, onClose }) {
  const qc = useQueryClient();
  const toast = useToast();
  const guardandoRef = useRef(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const [incierto, setIncierto] = useState(false);
  const [datos, setDatos] = useState({
    area: fila ? (fila.area == null ? "null" : String(fila.area)) : "",
    concepto: fila?.concepto ? String(fila.concepto) : "",
    importe: tipo === "reemplazo" ? fila.importe : "",
    mes, codigo: "", nombre: "", sensible: false, motivo: "",
    estado: fila?.estado_carga || "falta_cargar",
  });
  const set = (campo, valor) => setDatos((d) => ({ ...d, [campo]: valor }));
  const esCarga = ["gasto", "reemplazo"].includes(tipo);
  const configuraAmbito = esCarga || tipo === "expectativa";
  const accion = esCarga ? "registrar_gastos" : CONFIGURAR;
  const area = datos.area === "null" ? null : Number(datos.area);
  const concepto = conceptos.find((c) => String(c.id) === datos.concepto);
  const central = datos.area !== "" && permisos.permite("registrar_gastos", area, concepto?.sensible, true);
  const close = () => { if (!guardandoRef.current) onClose(); };

  async function guardar(e) {
    e.preventDefault();
    if (guardandoRef.current || incierto) return;
    setError("");
    if (configuraAmbito && (!concepto || datos.area === "" || !permisos.permite(accion, area, concepto.sensible))) {
      setError("Elegí un concepto y un ámbito habilitados por tus permisos.");
      return;
    }
    guardandoRef.current = true;
    setGuardando(true);
    try {
      let resultado;
      if (esCarga) resultado = await api.post("/gastos/", {
        institucion: institucion.id, concepto: concepto.id, area,
        importe: datos.importe.replace(",", "."), periodo_economico: `${datos.mes}-01`,
        ...(tipo === "reemplazo" ? { reemplaza: fila.id } : {}),
      });
      if (tipo === "concepto") await api.post("/conceptos-gasto/", {
        institucion: institucion.id, codigo: datos.codigo, nombre: datos.nombre, sensible: datos.sensible,
      });
      if (tipo === "expectativa") await api.post("/expectativas-gasto/", {
        institucion: institucion.id, concepto: concepto.id, area, vigente_desde: `${datos.mes}-01`,
      });
      if (tipo === "indicar") await api.post(`/expectativas-gasto/${fila.id}/indicar/`, {
        periodo_economico: `${mes}-01`, estado: datos.estado,
      });
      if (tipo === "aprobar") await api.post(`/gastos/${fila.id}/aprobar/`, {});
      if (tipo === "rechazar") await api.post(`/gastos/${fila.id}/rechazar/`, { motivo: datos.motivo });
      if (tipo === "ajuste") await api.post("/ajustes-gasto/", {
        gasto: fila.id, importe: datos.importe.replace(",", "."), motivo: datos.motivo,
      });
      await qc.invalidateQueries({ queryKey: ["finanzas"] });
      toast.ok(esCarga ? `Gasto #${resultado.id} registrado: ${resultado.estado === "aprobado" ? "aprobado" : "pendiente de aprobación"}.` : "Operación registrada.");
      onClose();
    } catch (err) {
      const mensajes = typeof err.data === "object" ? Object.values(err.data || {}).flat().join(" · ") : err.message;
      const sinConfirmacion = !err.status || err.status >= 500;
      setIncierto(sinConfirmacion);
      setError(sinConfirmacion ? "No se pudo confirmar si la operación quedó registrada. Cerrá y actualizá los registros antes de volver a cargarla." : mensajes);
    } finally {
      guardandoRef.current = false;
      setGuardando(false);
    }
  }

  return <Modal title={TITULOS[tipo]} onClose={close} width={540}>
    <form onSubmit={guardar} className="space-y-4">
      <p className="text-md text-texto-debil">{institucion.nombre} · Período {configuraAmbito ? datos.mes : mes}</p>
      {fila && <div className="rounded-md border border-borde bg-superficie-2 p-3 text-md">
        <strong>{fila.concepto_nombre}</strong><br />{fila.area_nombre || "Ámbito institucional"}
        {fila.importe != null && <div className="mt-1 font-mono">Original: {importeARS(fila.importe)}</div>}
      </div>}
      <fieldset disabled={guardando} className="space-y-4">
        {tipo === "concepto" && <>
          <Field label="Código"><Input required maxLength={60} value={datos.codigo} onChange={(e) => set("codigo", e.target.value)} /></Field>
          <Field label="Nombre"><Input required maxLength={160} value={datos.nombre} onChange={(e) => set("nombre", e.target.value)} /></Field>
          {permisos.permite(CONFIGURAR, null, true) && <Checkbox label="Concepto sensible" checked={datos.sensible} onChange={(e) => set("sensible", e.target.checked)} />}
        </>}
        {configuraAmbito && <>
          <Field label="Ámbito del gasto"><Select required value={datos.area} onChange={(e) => { set("area", e.target.value); set("concepto", ""); }}>
            <option value="">Elegí un ámbito</option>
            {permisos.permite(accion, null) && <option value="null">Institucional (sin área)</option>}
            {areas.filter((a) => permisos.permite(accion, a.id)).map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
          </Select></Field>
          <Field label="Concepto"><Select required value={datos.concepto} onChange={(e) => set("concepto", e.target.value)}>
            <option value="">Elegí un concepto</option>
            {conceptos.filter((c) => c.activo && datos.area !== "" && permisos.permite(accion, area, c.sensible)).map((c) => <option key={c.id} value={c.id}>{c.nombre}{c.sensible ? " · Sensible" : ""}</option>)}
          </Select></Field>
          <Field label={esCarga ? "Período económico" : "Se espera desde"}><Input type="month" required value={datos.mes} onChange={(e) => set("mes", e.target.value)} /></Field>
        </>}
        {(esCarga || tipo === "ajuste") && <Field label={tipo === "ajuste" ? "Ajuste en ARS (positivo o negativo)" : "Importe en ARS"} hint="Hasta dos decimales, sin separador de miles.">
          <Input required inputMode="decimal" pattern={tipo === "ajuste" ? "-?[0-9]+([.,][0-9]{1,2})?" : "[0-9]+([.,][0-9]{1,2})?"} value={datos.importe} onChange={(e) => set("importe", e.target.value)} />
        </Field>}
        {["rechazar", "ajuste"].includes(tipo) && <Field label="Motivo"><Textarea required maxLength={255} value={datos.motivo} onChange={(e) => set("motivo", e.target.value)} /></Field>}
        {tipo === "indicar" && <Field label="Estado de carga"><Select value={datos.estado} onChange={(e) => set("estado", e.target.value)}>
          {Object.entries(ESTADOS_CARGA).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}
        </Select></Field>}
      </fieldset>
      {esCarga && datos.area !== "" && <p className="text-md text-texto-suave">{central ? "Tu carga quedará aprobada al registrarla." : "Tu carga quedará pendiente de aprobación central."} No registra un pago ni asigna costos a pacientes.</p>}
      {tipo === "indicar" && <p className="text-md text-texto-debil">La indicación describe la carga de este concepto y mes. Los gastos pendientes conservan su aprobación separada.</p>}
      {tipo === "aprobar" && <p className="text-md text-texto-debil">La fuente quedará aprobada. Su importe original se conservará; las correcciones posteriores se harán mediante ajustes.</p>}
      {error && <p role="alert" className="text-md text-danger">{error}</p>}
      <div className="flex justify-end gap-2 border-t border-division pt-4">
        <Button type="button" variant="ghost" disabled={guardando} onClick={close}>Cancelar</Button>
        <Button type="submit" disabled={guardando || incierto}>{guardando ? "Guardando…" : "Confirmar"}</Button>
      </div>
    </form>
  </Modal>;
}
