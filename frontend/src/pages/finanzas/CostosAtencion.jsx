import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { query, useLista } from "@/api/queries";
import { importeARS, opcionesFinanzas } from "@/api/finanzas";
import { Badge, Button, Card, Checkbox, Field, Input, Modal, Select, Spinner, Textarea } from "@/components/ui";
import { DataTable, useTablaUrl } from "@/components/ui/tabla";
import { EstadoError, EstadoVacio } from "@/components/ui/estados";
import { fechaHora } from "@/lib/format";
import { AyudaFinanzas } from "./ControlesFinanzas";

// Los importes provienen del servidor. No se infiere un total hospitalario ni
// se mezclan cargos, pagos y atribuciones con el costo directo.
export default function CostosAtencion({ institucion, permisos, mes, area, areas, onGasto }) {
  const tabla = useTablaUrl("costos");
  const [caso, setCaso] = useState("");
  const [detalle, setDetalle] = useState(null);
  const filtros = { institucion: institucion.id, periodo_economico: `${mes}-01`, caso: caso || undefined,
    ...(area === "null" ? { area_sin_asignar: true } : { area: area || undefined }),
    page: tabla.pagina, pageSize: tabla.tamano, ordering: tabla.orden || "-ocurrida_en,-id" };
  const consulta = useLista("hechos-costo", filtros, { queryKey: ["finanzas", permisos.usuarioId, institucion.id, "costos", filtros], placeholderData: undefined, gcTime: 0, refetchInterval: 3000 });
  const detalleActual = consulta.filas.find((r) => r.id === detalle?.id);
  useEffect(() => {
    if (detalle && (!detalleActual || consulta.error)) setDetalle(null);
  }, [detalle, detalleActual, consulta.error]);
  useEffect(() => { setDetalle(null); }, [mes, area, tabla.pagina]);
  const nombreArea = (id) => areas.find((a) => a.id === id)?.nombre || (id == null ? "Institucional — sin área asignada" : "Área no disponible");
  return <section className="space-y-4" aria-label="Costos por atención">
    <DataTable adaptable columnas={[
      { key: "id", label: "Atención", orden: "id", render: (r) => <div><strong>Registro #{r.id}</strong><p className="text-sm text-texto-debil">Caso #{r.caso}</p></div> },
      { key: "ocurrida_en", label: "Fecha de atención", orden: "ocurrida_en", render: (r) => fechaHora(r.ocurrida_en) },
      { key: "area", label: "Área", render: (r) => nombreArea(r.area) },
      { key: "total_conocido", label: "Costo directo conocido", render: (r) => <span className="font-mono">{importeARS(r.total_conocido)}</span> },
      { key: "total_compartido_conocido", label: "Gasto compartido asignado", render: (r) => <span className="font-mono">{r.reparto_actualizando ? "Actualizando reparto" : importeARS(r.total_compartido_conocido)}</span> },
      { key: "estado_costo", label: "Alcance", render: (r) => <Badge tone={r.total_directo_es_completo ? "info" : "amber"}>{r.total_directo_es_completo ? "Directos completos" : "Directos pendientes"}</Badge> },
      { key: "detalle", label: "Detalle", render: (r) => <Button variant="ghost" size="sm" onClick={() => setDetalle(r)}>Ver composición</Button> },
    ]} filas={consulta.filas} total={consulta.total} paginas={consulta.paginas} tabla={tabla} mantenerEncabezados
      estado={{ cargando: consulta.isLoading, refrescando: consulta.refrescando, error: consulta.error, reintentar: consulta.refetch }}
      barra={<><Field label="Número de caso"><Input type="number" min="1" value={caso} onChange={(e) => { setCaso(e.target.value); setDetalle(null); tabla.irA(1); }} placeholder="Todos los casos" /></Field><AyudaFinanzas titulo="Qué costo muestra cada atención"><p>Directo conocido incluye los componentes configurados y sus ajustes. Compartido es la parte de gastos aprobados atribuida a esta atención, no un gasto adicional.</p><p>“Directos completos” sólo confirma esos componentes. No significa costo total del paciente ni del hospital. No se muestran historias clínicas ni cobros.</p></AyudaFinanzas></>}
      vacio={{ titulo: "Sin atenciones financieras visibles para estos filtros", detalle: "Las atenciones aparecen al completarse en el flujo clínico. Revisá el mes, el área y tus permisos." }} />
    {detalleActual && !consulta.error && <DetalleCosto fila={detalleActual} nombreArea={nombreArea(detalleActual.area)} onGasto={onGasto ? (id) => { setDetalle(null); onGasto(id); } : undefined} onClose={() => setDetalle(null)} />}
  </section>;
}

function DetalleCosto({ fila, nombreArea, onGasto, onClose }) {
  return <Modal title={`Costo de atención · Caso #${fila.caso}`} onClose={onClose} width={780} footer={<Button variant="secondary" onClick={onClose}>Cerrar detalle</Button>}><div className="space-y-6">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-semibold">{nombreArea}</p><p className="mt-1 text-sm text-texto-debil">Atención · {fechaHora(fila.ocurrida_en)}</p></div><Badge tone={fila.total_directo_es_completo ? "green" : "amber"}>{fila.total_directo_es_completo ? "Directos completos" : "Faltan costos directos"}</Badge></div>
    <section aria-label="Importes conocidos de la atención" className="grid gap-4 rounded-md bg-superficie-2 p-4 sm:grid-cols-2">
      <div><p className="text-sm text-texto-debil">Directo conocido</p><p className="mt-1 break-all text-cifra font-semibold tabular-nums">{importeARS(fila.total_conocido)}</p><p className="mt-1 text-sm text-texto-debil">Incluye ajustes de componentes</p></div>
      <div><p className="text-sm text-texto-debil">Compartido conocido</p><p className="mt-1 break-all text-cifra font-semibold tabular-nums">{fila.reparto_actualizando ? "Actualizando reparto" : importeARS(fila.total_compartido_conocido)}</p><p className="mt-1 text-sm text-texto-debil">Parte de gastos aprobados atribuida aquí</p></div>
    </section>
    <section className="space-y-3"><h3 className="font-semibold">Componentes directos</h3>
      {!fila.imputaciones.length ? <p className="text-sm text-texto-debil">Todavía no hay componentes imputados. No equivale a costo cero.</p> : fila.imputaciones.map((i) => <div key={i.componente} className="border-b border-division pb-3"><div className="flex flex-wrap items-start justify-between gap-3"><div><strong>{i.componente_nombre}</strong><p className="mt-1 text-sm text-texto-debil">Una vez por atención · Importe original</p></div><span className="tabular-nums">{importeARS(i.importe)}</span></div>{i.ajustes.length > 0 && <ul className="mt-3 space-y-2 border-l-2 border-division pl-3">{i.ajustes.map((a) => <li key={a.id} className="flex flex-wrap justify-between gap-2 text-sm"><span>Ajuste · {a.motivo}</span><span className="tabular-nums">{importeARS(a.importe)}</span></li>)}</ul>}</div>)}
    </section>
    <section className="space-y-3"><h3 className="font-semibold">Gastos compartidos atribuidos</h3>
      {fila.reparto_actualizando ? <p role="status" className="border-l-2 border-badge-amber-fg pl-3 text-sm">Actualizando reparto. Las atribuciones anteriores no se presentan como vigentes.</p> : <>{!fila.repartos_compartidos.length ? <p className="text-sm text-texto-debil">Sin atribuciones visibles. Esto no garantiza que no haya gastos pendientes.</p> : fila.repartos_compartidos.map((r) => <div key={r.reparto} className="flex flex-wrap justify-between gap-3 border-b border-division pb-3"><div>{onGasto ? <button className="font-medium text-accent underline underline-offset-2" onClick={() => onGasto(r.gasto)}>{r.concepto} · Gasto #{r.gasto}</button> : <strong>{r.concepto}</strong>}<p className="mt-1 text-sm text-texto-debil">Mes {r.periodo_economico.slice(0, 7)} · Reparto versión {r.version}</p></div><span className="tabular-nums">{importeARS(r.importe)}</span></div>)}</>}
    </section>
    <section className="border-t border-division pt-4"><div className="mb-3 flex items-center justify-between gap-2"><h3 className="font-semibold">Alcance y pendientes</h3><AyudaFinanzas titulo="Qué significa costo conocido"><p>{fila.limite}</p><p>Estos importes no son aranceles ni dinero cobrado. Directos completos sólo confirma los componentes configurados; no significa costo total del paciente ni del hospital.</p></AyudaFinanzas></div><ul className="list-disc space-y-1 pl-5 text-sm">{fila.faltantes.map((f, n) => <li key={`${f.motivo}:${n}`}>{f.motivo_display}{f.componente_codigo ? ` · ${f.componente_codigo}` : ""}</li>)}</ul><p className="mt-4 text-sm text-texto-debil">Último cálculo · {fila.actualizado_en ? fechaHora(fila.actualizado_en) : "Pendiente"}</p></section>
  </div></Modal>;
}

export function ConfiguracionCostos({ institucion, permisos, onClose }) {
  const qc = useQueryClient();
  const [seleccion, setSeleccion] = useState("");
  const [componente, setComponente] = useState(null);
  const [form, setForm] = useState(null);
  const opciones = (recurso, filtros = {}) => ({ queryKey: ["finanzas", permisos.usuarioId, institucion.id, "config-costos", recurso, filtros], queryFn: () => opcionesFinanzas(recurso, institucion.id, filtros), gcTime: 0 });
  const prestaciones = useQuery(opciones("prestaciones-costo"));
  const atenciones = useQuery({ queryKey: ["finanzas", permisos.usuarioId, institucion.id, "atenciones-disponibles"], queryFn: () => api.get(`/prestaciones-costo/atenciones-disponibles/${query({ institucion: institucion.id })}`), gcTime: 0 });
  const componentes = useQuery({ ...opciones("componentes-costo", { prestacion: seleccion }), enabled: Boolean(seleccion) });
  const valores = useQuery({ ...opciones("valores-componentes", { componente: componente?.id }), enabled: Boolean(componente) });
  const prestacion = prestaciones.data?.find((p) => String(p.id) === seleccion);
  const error = prestaciones.error || atenciones.error || componentes.error || valores.error;
  const refrescar = () => qc.invalidateQueries({ queryKey: ["finanzas", permisos.usuarioId, institucion.id] });
  const terminar = async (resultado, tipo) => {
    if (tipo === "prestacion") { setSeleccion(String(resultado.id)); setComponente(null); }
    if (tipo === "componente") setComponente(resultado);
    setForm(null);
    await refrescar();
  };
  return <Modal title="Configurar costos por atención" onClose={form ? undefined : onClose} width={840}>
    {form ? <FormularioCosto key={`${form.tipo}:${form.fila?.id || "nuevo"}`} {...form} institucion={institucion} permisos={permisos} prestacion={prestacion} componente={componente} atenciones={atenciones.data || []} prestaciones={prestaciones.data || []} onClose={() => { setForm(null); refrescar(); }} onGuardado={terminar} /> : <div className="space-y-4">
      <p className="text-md text-texto-debil">Configurá qué se cuenta una vez al completar cada atención. No crea cargos ni pagos y no reescribe los costos históricos.</p>
      {error && <EstadoError error={error} onReintentar={refrescar} titulo="No se pudo consultar la configuración de costos" />}
      {prestaciones.isLoading || atenciones.isLoading ? <Spinner label="Consultando atenciones y costos configurados…" /> : <>
        <div className="flex flex-wrap items-end gap-3"><div className="min-w-[240px] flex-1"><Field label="Atención configurada"><Select value={seleccion} onChange={(e) => { setSeleccion(e.target.value); setComponente(null); }}><option value="">Elegí una atención</option>{prestaciones.data?.map((p) => <option key={p.id} value={p.id}>{p.nombre}{p.activo ? "" : " · Inactiva"}</option>)}</Select></Field></div><Button disabled={Boolean(error)} onClick={() => setForm({ tipo: "prestacion" })}>Configurar otra atención</Button></div>
        {!prestacion ? <EstadoVacio titulo="Empezá por una atención publicada" detalle="Luego agregá sus componentes (por ejemplo, materiales) y el valor con su vigencia. Cada paso se guarda explícitamente." /> : <>
          <div className="flex items-center justify-between gap-3"><h3 className="font-semibold">Componentes de {prestacion.nombre}</h3><Button variant="secondary" disabled={Boolean(error)} onClick={() => setForm({ tipo: "componente" })}>Agregar componente</Button></div>
          {componentes.isLoading ? <Spinner label="Consultando componentes…" /> : !componentes.data?.length ? <p className="text-md text-texto-debil">Todavía no tiene componentes. La atención no tendrá un costo directo completo hasta configurarlos y darles un valor.</p> : <div className="flex flex-wrap gap-2">{componentes.data.map((c) => <Button key={c.id} variant={componente?.id === c.id ? "secondary" : "ghost"} onClick={() => setComponente(c)}>{c.nombre}{c.sensible ? " · Sensible" : ""}{c.activo ? "" : " · Inactivo"}</Button>)}</div>}
          {componente && <Card className="space-y-3 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">Valores y vigencias · {componente.nombre}</h3>{permisos.permite("configurar_componentes", null, componente.sensible) && <Button size="sm" variant="secondary" disabled={valores.isFetching || Boolean(error)} onClick={() => setForm({ tipo: "valor" })}>Agregar intervalo de valor</Button>}</div>
            {valores.isLoading ? <Spinner label="Consultando valores…" /> : !valores.data?.length ? <p className="text-md text-texto-debil">Falta el valor de este componente. Agregalo antes de registrar las atenciones de prueba.</p> : <ul className="space-y-3">{valores.data.map((v) => { const reemplazado = valores.data.some((otro) => otro.reemplaza === v.id); return <li key={v.id} className="flex flex-wrap justify-between gap-3 border-t border-division pt-3"><div><strong className="font-mono">{importeARS(v.importe)}</strong><p className="text-sm text-texto-debil">Desde {fechaHora(v.vigente_desde)} · Hasta {v.vigente_hasta ? fechaHora(v.vigente_hasta) : "sin fin"}{reemplazado ? " · Tiene sucesor (conservado en historial)" : ""}</p>{v.fuente && <p className="text-sm">Referencia: {v.fuente}</p>}{v.motivo_correccion && <p className="text-sm">Motivo: {v.motivo_correccion}</p>}</div>{!reemplazado && permisos.permite("configurar_componentes", null, componente.sensible) && <Button size="sm" variant="ghost" onClick={() => setForm({ tipo: "valor", fila: v })}>Cambiar valor desde otra fecha</Button>}</li>; })}</ul>}
          </Card>}
        </>}
      </>}
      <AyudaFinanzas titulo="Vigencias e historia del costo"><p>La atención guarda los componentes configurados al completarse. Agregar componentes después no completa silenciosamente esas atenciones anteriores.</p><p>Un nuevo valor se aplica según su fecha de inicio y conserva el anterior. Cambiar la configuración no modifica por sí solo las imputaciones históricas. Si publicás otra versión del flujo, revisá la configuración de sus nuevas atenciones.</p></AyudaFinanzas>
    </div>}
  </Modal>;
}

function FormularioCosto({ tipo, fila, institucion, permisos, prestacion, componente, atenciones, prestaciones, onClose, onGuardado }) {
  const bloqueo = useRef(false);
  const [guardando, setGuardando] = useState(false);
  const [incierto, setIncierto] = useState(false);
  const [error, setError] = useState("");
  const [datos, setDatos] = useState({ nombre: "", codigo: "", nodo: "", sensible: false, importe: "", desde: "", hasta: "", fuente: "", motivo: "" });
  const set = (key, value) => setDatos((prev) => ({ ...prev, [key]: value }));
  const titulos = { prestacion: "1. Vincular la atención publicada", componente: "2. Agregar un componente de costo", valor: "3. Definir valor y vigencia" };
  async function guardar(event) {
    event.preventDefault();
    if (bloqueo.current || incierto) return;
    setError("");
    if (tipo === "valor" && (datos.hasta && datos.hasta <= datos.desde)) { setError("La fecha final debe ser posterior al inicio."); return; }
    if (tipo === "valor" && fila && new Date(datos.desde) <= new Date(fila.vigente_desde)) { setError("El nuevo valor debe empezar después del anterior. Este formulario no corrige importes históricos."); return; }
    bloqueo.current = true; setGuardando(true);
    try {
      let resultado;
      if (tipo === "prestacion") resultado = await api.post("/prestaciones-costo/", { institucion: institucion.id, nodo: Number(datos.nodo), codigo: datos.codigo.trim(), nombre: datos.nombre.trim(), activo: true });
      if (tipo === "componente") resultado = await api.post("/componentes-costo/", { prestacion: prestacion.id, codigo: datos.codigo.trim(), nombre: datos.nombre.trim(), fuente: "atencion_directa", unidad: "atencion", base_calculo: "por_atencion", activo: true, sensible: datos.sensible, orden: 0 });
      if (tipo === "valor") resultado = await api.post("/valores-componentes/", { componente: componente.id, importe: datos.importe.replace(",", "."), moneda: "ARS", vigente_desde: new Date(datos.desde).toISOString(), vigente_hasta: datos.hasta ? new Date(datos.hasta).toISOString() : null, fuente: datos.fuente.trim(), ...(fila ? { reemplaza: fila.id, motivo_correccion: datos.motivo.trim() } : {}) });
      await onGuardado(resultado, tipo);
    } catch (err) {
      const noConfirmado = !err.status || err.status >= 500;
      setIncierto(noConfirmado);
      setError(noConfirmado ? "No se pudo confirmar el guardado. Volvé a consultar la configuración antes de repetir la operación." : typeof err.data === "object" ? Object.values(err.data || {}).flat().join(" · ") : err.message);
    } finally { bloqueo.current = false; setGuardando(false); }
  }
  return <form onSubmit={guardar} className="space-y-4"><h3 className="text-lg font-semibold">{titulos[tipo]}</h3>
    <fieldset disabled={guardando || incierto} className="space-y-4">
      {tipo === "prestacion" && <Field label="Atención del flujo publicado"><Select required value={datos.nodo} onChange={(e) => { set("nodo", e.target.value); const nodo = atenciones.find((n) => String(n.id) === e.target.value); if (nodo) set("nombre", nodo.titulo); }}><option value="">Elegí la atención</option>{atenciones.filter((n) => !prestaciones.some((p) => p.activo && p.nodo === n.id)).map((n) => <option key={n.id} value={n.id}>{n.flujo_nombre} · {n.titulo} · {n.area_nombre || "Institucional"} · Versión {n.version_numero}</option>)}</Select></Field>}
      {tipo !== "valor" && <><Field label="Nombre"><Input required maxLength={160} value={datos.nombre} onChange={(e) => set("nombre", e.target.value)} /></Field><Field label="Código de referencia" hint="Identificador propio del catálogo, por ejemplo MATERIAL-CONSULTA."><Input required maxLength={60} value={datos.codigo} onChange={(e) => set("codigo", e.target.value)} /></Field></>}
      {tipo === "componente" && <><p className="text-md">Se imputa una vez por cada atención completada de {prestacion.nombre}.</p>{permisos.permite("configurar_componentes", null, true) && <Checkbox label="Componente con información sensible" checked={datos.sensible} onChange={(e) => set("sensible", e.target.checked)} />}</>}
      {tipo === "valor" && <><p className="font-semibold">{componente.nombre} · {prestacion.nombre}</p>{fila && <p className="text-md text-texto-debil">Valor anterior: {importeARS(fila.importe)} desde {fechaHora(fila.vigente_desde)}. Se conserva en el historial.</p>}<Field label="Importe por atención en ARS"><Input required inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" value={datos.importe} onChange={(e) => set("importe", e.target.value)} /></Field><Field label="Vigente desde" hint="Fecha y hora local. Elegí un inicio anterior a las nuevas atenciones que deben usar este valor."><Input type="datetime-local" required value={datos.desde} onChange={(e) => set("desde", e.target.value)} /></Field><Field label="Vigente hasta (opcional)" hint="Fin exclusivo. Vacío significa sin fin."><Input type="datetime-local" value={datos.hasta} onChange={(e) => set("hasta", e.target.value)} /></Field><Field label="Fuente o referencia del valor"><Input maxLength={255} value={datos.fuente} onChange={(e) => set("fuente", e.target.value)} /></Field>{fila && <Field label="Motivo del cambio"><Textarea required maxLength={255} value={datos.motivo} onChange={(e) => set("motivo", e.target.value)} /></Field>}<p className="text-md text-texto-debil">Se agregará {importeARS(datos.importe.replace(",", "."))} como componente directo de cada atención elegible. No genera un pago ni cambia silenciosamente costos históricos.</p></>}
    </fieldset>
    {error && <p role="alert" className="text-md text-danger">{error}</p>}
    <div className="sticky bottom-0 flex justify-end gap-2 border-t border-division bg-superficie py-3"><Button type="button" variant="ghost" disabled={guardando} onClick={onClose}>Volver a configuración</Button><Button type="submit" disabled={guardando || incierto}>{guardando ? "Guardando…" : "Guardar este paso"}</Button></div>
  </form>;
}
