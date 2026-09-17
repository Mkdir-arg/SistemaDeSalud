import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { importeARS } from "@/api/finanzas";
import { query, useLista } from "@/api/queries";
import { Badge, Button, Card, Field, Input, Modal, Select, Spinner, Textarea } from "@/components/ui";
import { DataTable, useTablaUrl } from "@/components/ui/tabla";
import { EstadoError } from "@/components/ui/estados";
import { AyudaFinanzas, useFiltrosFinanzas } from "./ControlesFinanzas";
import { PendientesCobro } from "./ConfiguracionCobros";
import { CampoAprobado, DecisionAprobacion, EstadoAprobacion, TrazaAprobacion } from "./AprobacionFinanzas";
import { decimalDinero, fechaLocal, filtroAreaDinero, importeValido, mensajeErrorDinero, useOperacionDinero } from "./dinero";

const signoCuenta = (tipo) => tipo === "pagar" ? "Por pagar" : "Por cobrar";
const nombreMovimiento = { pago: "Pago", cobro: "Cobro", reintegro_pago: "Devolución recibida", reintegro_cobro: "Devolución entregada" };
const etiquetaMovimiento = (movimiento, tipoCuenta) => movimiento.tipo === "reintegro" || movimiento.original
  ? tipoCuenta === "pagar" ? "Devolución recibida del proveedor" : "Devolución entregada al pagador"
  : nombreMovimiento[movimiento.tipo] || (tipoCuenta === "pagar" ? "Pago" : "Cobro");
const opcionesConsulta = (permisos, institucion, ...partes) => ({
  queryKey: ["finanzas", permisos.usuarioId, institucion.id, "dinero", ...partes],
  gcTime: 0, placeholderData: undefined,
});

export default function DineroFinanzas({ institucion, permisos, mes, area }) {
  const tabla = useTablaUrl("dinero");
  const busqueda = useFiltrosFinanzas("dinero", ["search"]);
  const [tipo, setTipo] = useState("");
  const [detalle, setDetalle] = useState(null);
  const params = { institucion: institucion.id, ...filtroAreaDinero(area), periodo_mes: mes, tipo, ...busqueda.valores, ordering: tabla.orden, page: tabla.pagina, pageSize: tabla.tamano };
  const cuentas = useLista("obligaciones-financieras", params, opcionesConsulta(permisos, institucion, "cuentas", params));
  return <div className="space-y-5">
    <ResumenDinero institucion={institucion} permisos={permisos} area={area} onCuenta={setDetalle} />
    <div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-lg font-semibold">Cuentas por pagar y cobrar</h2><p className="mt-1 text-sm text-texto-debil">Obligaciones del mes económico {mes}. Un gasto aprobado no significa que ya fue pagado.</p></div><Field label="Tipo de cuenta"><Select value={tipo} onChange={(e) => { setTipo(e.target.value); tabla.irA(1); }}><option value="">Todas</option><option value="pagar">Por pagar</option><option value="cobrar">Por cobrar</option></Select></Field></div>
    <DataTable adaptable filas={cuentas.error ? [] : cuentas.filas} total={cuentas.error ? 0 : cuentas.total} paginas={cuentas.paginas} tabla={tabla}
      mantenerEncabezados barra={<Input aria-label="Buscar cuentas" placeholder="Nombre o referencia de la contraparte…" value={busqueda.valores.search || ""} onChange={(e) => busqueda.cambiar({ search: e.target.value })} />}
      estado={{ cargando: cuentas.isLoading, refrescando: cuentas.refrescando, error: cuentas.error, reintentar: cuentas.refetch }}
      vacio={{ titulo: "Sin cuentas para este mes y área", detalle: "Las cuentas por pagar se crean explícitamente desde un gasto aprobado. Los cobros dependen de la configuración de la atención." }}
      columnas={[
        { key: "tipo", label: "Cuenta", orden: "tipo", render: (r) => <div><Badge tone={r.tipo === "pagar" ? "amber" : "info"}>{signoCuenta(r.tipo)}</Badge><p className="mt-1 text-sm text-texto-debil">#{r.id}</p></div> },
        { key: "contraparte_nombre", label: "A quién / de quién", orden: "contraparte_nombre", render: (r) => <div><strong>{r.contraparte_nombre}</strong><p className="text-sm text-texto-debil">{r.contraparte_referencia}</p></div> },
        { key: "obligacion_actual", label: "Importe de la cuenta", render: (r) => importeARS(r.obligacion_actual) },
        { key: "registrado_neto", label: "Pagado / cobrado confirmado", render: (r) => importeARS(r.registrado_neto) },
        { key: "por_aprobar", label: "Pago / cobro por aprobar", render: (r) => importeARS(r.por_aprobar) },
        { key: "pendiente", label: "Pendiente", render: (r) => <span className="font-semibold tabular-nums">{importeARS(r.pendiente)}</span> },
        { key: "acciones", label: "Acciones", render: (r) => <Button size="sm" variant="secondary" onClick={() => setDetalle(r.id)}>Ver cuenta</Button> },
      ]} />
    <PendientesCobro institucion={institucion} permisos={permisos} mes={mes} area={area} />
    {detalle != null && <DetalleCuenta key={detalle} id={detalle} institucion={institucion} permisos={permisos} onClose={() => setDetalle(null)} />}
  </div>;
}

function ResumenDinero({ institucion, permisos, area, onCuenta }) {
  const [mesDinero, setMesDinero] = useState(fechaLocal().slice(0, 7));
  const [verMovimientos, setVerMovimientos] = useState(false);
  const valido = /^\d{4}-(0[1-9]|1[0-2])$/.test(mesDinero);
  const [anio, mesNumero] = mesDinero.split("-").map(Number);
  const ultimoDia = valido ? new Date(anio, mesNumero, 0).getDate() : 1;
  const filtros = { institucion: institucion.id, ...filtroAreaDinero(area), fecha_desde: `${mesDinero}-01`, fecha_hasta: `${mesDinero}-${ultimoDia}` };
  const consulta = useQuery({ ...opcionesConsulta(permisos, institucion, "resumen", filtros), enabled: valido,
    queryFn: () => api.get(`/reportes-dinero/${query(filtros)}`) });
  const d = consulta.error ? null : consulta.data;
  return <Card className="space-y-4 p-4"><div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-lg font-semibold">Dinero registrado</h2><p className="mt-1 text-sm text-texto-debil">Los totales incluyen sólo registros aprobados, por fecha real del pago, cobro o devolución. Este mes es independiente del mes económico de las cuentas.</p></div><Field label="Mes de pagos y cobros"><Input type="month" required value={mesDinero} onChange={(e) => setMesDinero(e.target.value)} /></Field></div>
    {!valido && <p role="alert">Elegí un mes válido para consultar el dinero.</p>}
    {consulta.isLoading && <Spinner label="Consultando pagos y cobros…" />}
    {consulta.error && <EstadoError error={consulta.error} onReintentar={consulta.refetch} />}
    {d && <><dl className="grid gap-4 sm:grid-cols-3">{[["Cobros netos", "cobros_netos"], ["Pagos netos", "pagos_netos"], ["Diferencia del período", "diferencia"]].map(([nombre, campo]) => <div key={campo}><dt className="text-sm text-texto-debil">{nombre}</dt><dd className="mt-1 break-all text-xl font-semibold tabular-nums">{importeARS(d[campo])}</dd></div>)}</dl><details className="border-t border-division pt-3"><summary className="cursor-pointer text-sm font-medium">Ver importes originales y devoluciones</summary><dl className="mt-3 grid gap-3 sm:grid-cols-2">{[["Cobros registrados", "cobros_brutos"], ["Pagos registrados", "pagos_brutos"], ["Devoluciones de cobros", "reintegros_cobros"], ["Devoluciones de pagos", "reintegros_pagos"]].map(([nombre, campo]) => <div key={campo}><dt className="text-sm text-texto-debil">{nombre}</dt><dd className="tabular-nums">{importeARS(d[campo])}</dd></div>)}</dl></details></>}
    <p className="text-sm text-texto-debil">La diferencia es cobros netos menos pagos netos del período. No representa dinero disponible, rentabilidad ni costo del hospital.</p>
    {d?.por_aprobar && (d.por_aprobar.cantidad > 0 ? <section aria-label="Dinero por aprobar" className="space-y-3 border-t border-division pt-3"><h3 className="font-semibold">Por aprobar · {d.por_aprobar.cantidad} registro(s)</h3><p className="text-sm text-texto-debil">Estos importes no están incluidos en los totales confirmados.</p><dl className="grid gap-3 sm:grid-cols-2">{[["Pagos por aprobar", "pagos"], ["Cobros por aprobar", "cobros"], ["Devoluciones de pagos por aprobar", "reintegros_pagos"], ["Devoluciones de cobros por aprobar", "reintegros_cobros"]].map(([label, campo]) => <div key={campo}><dt className="text-sm text-texto-debil">{label}</dt><dd className="tabular-nums">{importeARS(d.por_aprobar[campo])}</dd></div>)}</dl></section> : <p className="border-t border-division pt-3 text-sm text-texto-debil">Sin registros por aprobar.</p>)}
    <Button variant="ghost" aria-expanded={verMovimientos} onClick={() => setVerMovimientos(!verMovimientos)}>{verMovimientos ? "Ocultar movimientos del período" : "Ver movimientos del período"}</Button>
    {verMovimientos && valido && <MovimientosPeriodo key={mesDinero} filtros={filtros} institucion={institucion} permisos={permisos} onCuenta={onCuenta} />}
  </Card>;
}

export function MovimientosPeriodo({ filtros, institucion, permisos, onCuenta }) {
  const tabla = useTablaUrl("movimientos_dinero");
  const busqueda = useFiltrosFinanzas("movimientos_dinero", ["search"]);
  const params = { ...filtros, ...busqueda.valores, ordering: tabla.orden, page: tabla.pagina, pageSize: tabla.tamano };
  const consulta = useLista("movimientos-dinero", params, opcionesConsulta(permisos, institucion, "movimientos", params));
  return <section className="space-y-3 border-t border-division pt-4"><p className="text-sm text-texto-debil">Cada pago, cobro o devolución del período, aunque su cuenta pertenezca a otro mes económico.</p><DataTable adaptable mantenerEncabezados barra={<Input aria-label="Buscar movimientos" placeholder="Contraparte o referencia del movimiento…" value={busqueda.valores.search || ""} onChange={(e) => busqueda.cambiar({ search: e.target.value })} />} filas={consulta.error ? [] : consulta.filas} total={consulta.error ? 0 : consulta.total} paginas={consulta.paginas} tabla={tabla} estado={{ cargando: consulta.isLoading, error: consulta.error, reintentar: consulta.refetch }} vacio={{ titulo: "Sin movimientos en estas fechas" }} columnas={[
    { key: "fecha", orden: "fecha", label: "Fecha real" },
    { key: "tipo", orden: "tipo", label: "Movimiento", render: (r) => etiquetaMovimiento(r, r.obligacion_tipo) },
    { key: "contraparte_nombre", orden: "obligacion__contraparte_nombre", label: "A quién / de quién" },
    { key: "importe", orden: "importe", label: "Importe", render: (r) => importeARS(r.importe) },
    { key: "estado", orden: "estado", label: "Aprobación", render: (r) => <EstadoAprobacion fila={r} /> },
    { key: "periodo_economico", orden: "obligacion__periodo_economico", label: "Mes de la cuenta", render: (r) => r.periodo_economico?.slice(0, 7) },
    { key: "acciones", label: "Origen", render: (r) => <Button size="sm" variant="ghost" onClick={() => onCuenta(r.obligacion)}>Ver cuenta #{r.obligacion}</Button> },
  ]} /></section>;
}

export function DetalleCuenta({ id, institucion, permisos, onClose }) {
  const qc = useQueryClient();
  const [accion, setAccion] = useState(null);
  const consulta = useQuery({ ...opcionesConsulta(permisos, institucion, "cuenta", id), queryFn: () => api.get(`/obligaciones-financieras/${id}/`) });
  const fila = consulta.error ? null : consulta.data;
  async function actualizado() {
    setAccion(null);
    await qc.invalidateQueries({ queryKey: ["finanzas"] });
  }
  const puede = (permiso) => fila && !permisos.isFetching && permisos.permite(permiso, fila.area, fila.sensible);
  function decidir(registro, rechazar, esAjuste = false) {
    setAccion({ tipo: "decision", rechazar, titulo: `${rechazar ? "Rechazar" : "Aprobar"} ${esAjuste ? "reducción" : "movimiento"} #${registro.id}`,
      url: esAjuste ? `/obligaciones-financieras/${fila.id}/${rechazar ? "rechazar-ajuste" : "aprobar-ajuste"}/` : `/movimientos-dinero/${registro.id}/${rechazar ? "rechazar" : "aprobar"}/`,
      datos: esAjuste ? { ajuste: registro.id } : {},
    });
  }
  return <Modal title={`Cuenta #${id}`} onClose={accion ? undefined : onClose} width={780}>
    {consulta.isLoading && <Spinner label="Consultando cuenta…" />}
    {consulta.error && <EstadoError error={consulta.error} onReintentar={consulta.refetch} />}
    {fila && (accion ? accion.tipo === "decision"
      ? <DecisionAprobacion key={accion.url} {...accion} onClose={() => setAccion(null)} onGuardado={actualizado} />
      : <OperacionCuenta key={`${accion.tipo}:${accion.movimiento?.id || ""}`} fila={fila} puedeAprobar={puede("aprobar_dinero")} {...accion} onClose={() => setAccion(null)} onGuardado={actualizado} /> : <div className="space-y-5">
      <div><Badge tone={fila.tipo === "pagar" ? "amber" : "info"}>{signoCuenta(fila.tipo)}</Badge><h3 className="mt-2 text-lg font-semibold">{fila.contraparte_nombre}</h3><p className="text-sm text-texto-debil">{fila.contraparte_referencia || "Sin referencia adicional"} · Mes económico {fila.periodo_economico?.slice(0, 7)}</p><p className="mt-1 text-sm">{fila.gasto ? `Gasto de origen #${fila.gasto}` : `Atención de origen #${fila.hecho}`}</p></div>
      <dl className="grid gap-4 sm:grid-cols-3">{[["Importe actual de la cuenta", "obligacion_actual"], [fila.tipo === "pagar" ? "Pagado neto" : "Cobrado neto", "registrado_neto"], ["Pendiente", "pendiente"]].map(([nombre, campo]) => <div key={campo}><dt className="text-sm text-texto-debil">{nombre}</dt><dd className="mt-1 text-xl font-semibold tabular-nums">{importeARS(fila[campo])}</dd></div>)}</dl>
      <p className="text-sm text-texto-debil">Importe original: {importeARS(fila.importe_original)}. Los pagos y las devoluciones se conservan en el historial.</p>
      {["por_aprobar", "reintegros_por_aprobar", "ajustes_por_aprobar"].some((campo) => importeValido(fila[campo])) ? <section aria-label="Reservas por aprobar" className="space-y-3 border-t border-division pt-3"><p className="text-sm text-texto-debil">El saldo y el dinero neto anteriores incluyen sólo lo aprobado. Los registros pendientes reservan importes para evitar cargarlos dos veces.</p><dl className="grid gap-3 sm:grid-cols-3">{[["Pagos / cobros por aprobar", "por_aprobar"], ["Devoluciones por aprobar", "reintegros_por_aprobar"], ["Reducciones por aprobar", "ajustes_por_aprobar"]].map(([label, campo]) => <div key={campo}><dt className="text-sm text-texto-debil">{label}</dt><dd className="tabular-nums">{importeARS(fila[campo])}</dd></div>)}</dl></section> : <p className="border-t border-division pt-3 text-sm text-texto-debil">Sin reservas por aprobar.</p>}
      <p className="text-sm">Disponible para registrar otro {fila.tipo === "pagar" ? "pago" : "cobro"}: <strong>{importeARS(fila.disponible_registro)}</strong></p>
      {fila.discrepancia_gasto && <p role="status" className="border-l-2 border-badge-amber-fg pl-3 text-sm">El gasto y la cuenta difieren. Revisá ambos: no se ajustan automáticamente y corregirlos no registra una devolución de dinero.</p>}
      {importeValido(fila.saldo_a_devolver) && <p role="status" className="text-sm">Saldo a devolver: {importeARS(fila.saldo_a_devolver)}.</p>}
      <div className="flex flex-wrap gap-2">{puede("registrar_dinero") && importeValido(fila.disponible_registro) && <Button onClick={() => setAccion({ tipo: "movimiento" })}>{fila.tipo === "pagar" ? "Registrar pago" : "Registrar cobro"}</Button>}{puede("corregir_dinero") && importeValido(fila.disponible_reducir) && <Button variant="secondary" onClick={() => setAccion({ tipo: "reducir" })}>Reducir o cancelar cuenta</Button>}</div>
      <section className="space-y-3 border-t border-division pt-4"><h3 className="font-semibold">Pagos, cobros y devoluciones</h3>{!fila.movimientos?.length ? <p className="text-sm text-texto-debil">Todavía no se registró dinero para esta cuenta.</p> : fila.movimientos.map((m) => <div key={m.id} className="flex flex-wrap items-start justify-between gap-3 border-b border-division pb-3"><div className="space-y-2"><strong>{etiquetaMovimiento(m, fila.tipo)} · {importeARS(m.importe)}</strong><div><EstadoAprobacion fila={m} /></div><p className="text-sm text-texto-debil">{m.fecha} · {m.referencia || m.motivo || `Registro #${m.id}`}</p>{m.original && <p className="text-sm text-texto-debil">Devuelve parte del registro #{m.original}{m.ajuste ? fila.ajustes?.some((a) => a.id === m.ajuste && a.movimiento_vinculado === m.id) ? "; incluye su reducción de cuenta y se aprueban juntos" : `; vinculado a la reducción ya registrada #${m.ajuste}` : ""}</p>}<TrazaAprobacion fila={m} /></div><div className="flex flex-wrap gap-2">{puede("aprobar_dinero") && m.estado === "pendiente_aprobacion" && <><Button size="sm" variant="secondary" onClick={() => decidir(m, false)}>Aprobar movimiento</Button><Button size="sm" variant="ghost" onClick={() => decidir(m, true)}>Rechazar movimiento</Button></>}{puede("corregir_dinero") && m.estado === "aprobado" && !m.original && importeValido(m.disponible_reintegro) && <Button size="sm" variant="ghost" onClick={() => setAccion({ tipo: "reintegro", movimiento: m })}>Registrar devolución</Button>}</div></div>)}</section>
      <section className="space-y-3"><h3 className="font-semibold">Reducciones de la cuenta</h3>{!fila.ajustes?.length ? <p className="text-sm text-texto-debil">Sin reducciones.</p> : fila.ajustes.map((a) => <div key={a.id} className="space-y-2 border-b border-division pb-3"><p className="text-sm">#{a.id} · {a.motivo} · {importeARS(a.importe)}</p><EstadoAprobacion fila={a} /><TrazaAprobacion fila={a} />{a.movimiento_vinculado ? <p className="text-sm text-texto-debil">Se decide junto con la devolución #{a.movimiento_vinculado}.</p> : puede("aprobar_dinero") && a.estado === "pendiente_aprobacion" && <div className="flex gap-2"><Button size="sm" variant="secondary" onClick={() => decidir(a, false, true)}>Aprobar reducción</Button><Button size="sm" variant="ghost" onClick={() => decidir(a, true, true)}>Rechazar reducción</Button></div>}</div>)}</section>
    </div>)}
  </Modal>;
}

function OperacionCuenta({ fila, tipo, movimiento, puedeAprobar, onClose, onGuardado }) {
  const [importe, setImporte] = useState("");
  const [fecha, setFecha] = useState(fechaLocal());
  const [referencia, setReferencia] = useState("");
  const [motivo, setMotivo] = useState("");
  const [efecto, setEfecto] = useState("mantener");
  const [ajuste, setAjuste] = useState("");
  const [preview, setPreview] = useState(null);
  const [verificando, setVerificando] = useState(false);
  const [errorPreview, setErrorPreview] = useState("");
  const [eleccionAprobado, setEleccionAprobado] = useState(true);
  const aprobado = puedeAprobar && eleccionAprobado;
  const operacion = useOperacionDinero();
  const devolver = tipo === "reintegro";
  const reducir = tipo === "reducir";
  const titulo = devolver ? "Registrar devolución" : reducir ? "Reducir o cancelar cuenta" : fila.tipo === "pagar" ? "Registrar pago" : "Registrar cobro";
  const maximo = devolver ? movimiento.disponible_reintegro : reducir ? fila.disponible_reducir : fila.disponible_registro;
  const payload = { importe: decimalDinero(importe), aprobado, ...(reducir ? { motivo: motivo.trim() } : { fecha, ...(devolver ? { motivo: motivo.trim(), efecto, ...(efecto === "reduccion_existente" ? { ajuste: Number(ajuste) } : {}) } : { referencia: referencia.trim() }) }) };
  const firma = JSON.stringify(payload);
  const previewActual = preview?.firma === firma ? preview.datos : null;
  const valido = importeValido(importe, maximo) && (reducir || devolver ? motivo.trim() : true) && (reducir || fecha) && (!devolver || efecto !== "reduccion_existente" || ajuste);
  const bloqueado = operacion.guardando || verificando;
  async function previsualizar(e) {
    e.preventDefault();
    if (!valido || bloqueado) return;
    setVerificando(true); setErrorPreview(""); setPreview(null);
    try {
      const datos = await api.post(`/movimientos-dinero/${movimiento.id}/previsualizar-reintegro/`, payload);
      setPreview({ firma, datos });
    } catch (err) { setErrorPreview(mensajeErrorDinero(err)); }
    finally { setVerificando(false); }
  }
  async function guardar(e) {
    e.preventDefault();
    if (!valido || bloqueado || (devolver && !previewActual)) return;
    const cuerpo = devolver ? { ...payload, version_esperada: previewActual.version_esperada, pendiente_esperado: previewActual.pendiente_anterior } : payload;
    const url = devolver ? `/movimientos-dinero/${movimiento.id}/reintegrar/` : `/obligaciones-financieras/${fila.id}/${reducir ? "reducir" : "movimientos"}/`;
    await operacion.ejecutar(cuerpo, async (datos) => { await api.post(url, datos); await onGuardado(); });
  }
  return <form onSubmit={devolver && !previewActual ? previsualizar : guardar} className="space-y-4"><h3 className="text-lg font-semibold">{titulo}</h3><p className="text-sm text-texto-debil">{fila.contraparte_nombre} · Máximo: {importeARS(maximo)}</p>
    {devolver && <p className="text-sm font-medium">{fila.tipo === "pagar" ? "El proveedor devuelve dinero al hospital." : "El hospital devuelve dinero a quien pagó."}</p>}
    <fieldset disabled={bloqueado} className="space-y-4"><Field label="Importe en ARS"><Input required inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" value={importe} onChange={(e) => setImporte(e.target.value)} /></Field>
      {!reducir && <Field label="Fecha real del movimiento"><Input required type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} /></Field>}
      {reducir || devolver ? <Field label="Motivo"><Textarea required maxLength={255} value={motivo} onChange={(e) => setMotivo(e.target.value)} /></Field> : <Field label="Referencia del pago o cobro"><Input maxLength={160} value={referencia} onChange={(e) => setReferencia(e.target.value)} placeholder="Comprobante o referencia interna" /></Field>}
      {devolver && <><Field label="Qué pasa con la cuenta"><Select value={efecto} onChange={(e) => setEfecto(e.target.value)}><option value="mantener">Sigue pendiente: habrá que volver a pagar o cobrar</option><option value="reducir">Se reduce o cancela la cuenta por este importe</option><option value="reduccion_existente">La cuenta ya se redujo: vincular esa reducción</option></Select></Field>{efecto === "reduccion_existente" && <Field label="Reducción ya registrada"><Select required value={ajuste} onChange={(e) => setAjuste(e.target.value)}><option value="">Elegí la reducción</option>{(fila.ajustes || []).filter((a) => importeValido(a.disponible_reintegro)).map((a) => <option key={a.id} value={a.id}>#{a.id} · {a.motivo} · Disponible {importeARS(a.disponible_reintegro)}</option>)}</Select></Field>}<p className="text-sm text-texto-debil">La devolución se vincula al {fila.tipo === "pagar" ? "pago" : "cobro"} #{movimiento.id}. Vincular una reducción existente evita descontar dos veces la misma cancelación.</p></>}
      {reducir && <p className="text-sm text-texto-debil">Esta operación reduce la obligación. No devuelve dinero. Para una devolución, usá el pago o cobro original de la cuenta.</p>}
    </fieldset>
    <CampoAprobado puedeAprobar={puedeAprobar} aprobado={aprobado} onChange={setEleccionAprobado} disabled={bloqueado} />
    {importe && !importeValido(importe, maximo) && <p role="alert" className="text-sm text-danger">Indicá un importe positivo, con hasta dos decimales y dentro del máximo disponible.</p>}
    {previewActual && <section aria-label="Resultado de la devolución" className="space-y-3 rounded-lg border border-division p-4"><h4 className="font-semibold">Antes de confirmar</h4><dl className="grid gap-3 sm:grid-cols-2">{[["Pendiente anterior", "pendiente_anterior"], [aprobado ? "Pendiente después de devolver" : "Pendiente confirmado al guardar", "pendiente_resultante"], ["Importe confirmado de la cuenta", "obligacion_resultante"], ["Pagado / cobrado neto confirmado", "registrado_neto_resultante"], ...(!aprobado ? [["Pendiente si se aprueba", "pendiente_al_aprobar"], ["Importe reservado por aprobar", "importe_reservado"]] : [])].map(([nombre, campo]) => <div key={campo}><dt className="text-sm text-texto-debil">{nombre}</dt><dd className="font-semibold tabular-nums">{importeARS(previewActual[campo])}</dd></div>)}</dl><p className="text-sm">{aprobado ? "Confirmar registrará la devolución aprobada y el efecto elegido sobre la cuenta." : "Se guardará pendiente. Los importes confirmados no cambian todavía; se reserva el importe hasta aprobar o rechazar."}</p></section>}
    {(operacion.error || errorPreview) && <p role="alert" className="text-sm text-danger">{operacion.error || errorPreview}</p>}
    <div className="flex flex-wrap justify-end gap-2"><Button type="button" variant="ghost" disabled={bloqueado} onClick={onClose}>Volver a la cuenta</Button>{devolver && previewActual && <Button type="button" variant="secondary" disabled={bloqueado} onClick={previsualizar}>Actualizar vista previa</Button>}<Button type="submit" disabled={!valido || bloqueado}>{bloqueado ? "Consultando…" : devolver ? previewActual ? "Confirmar devolución" : "Ver resultado antes de confirmar" : titulo}</Button></div>
  </form>;
}

export function CrearCuentaPorPagar({ gasto, onClose, onCreada }) {
  const qc = useQueryClient();
  const [nombre, setNombre] = useState("");
  const [referencia, setReferencia] = useState("");
  const operacion = useOperacionDinero();
  async function guardar(e) {
    e.preventDefault();
    if (!nombre.trim()) return;
    await operacion.ejecutar({ gasto: gasto.id, contraparte_nombre: nombre.trim(), contraparte_referencia: referencia.trim() }, async (datos) => {
      const cuenta = await api.post("/obligaciones-financieras/", datos);
      await qc.invalidateQueries({ queryKey: ["finanzas"] });
      onCreada(cuenta.id);
    });
  }
  return <Modal title="Crear cuenta por pagar" onClose={operacion.guardando ? undefined : onClose} width={560}><form onSubmit={guardar} className="space-y-4"><p>Gasto #{gasto.id} · {gasto.concepto_nombre} · {importeARS(gasto.importe_resultante ?? gasto.importe)}</p><AyudaFinanzas titulo="Qué se crea"><p>Se vincula una cuenta al gasto aprobado, conservando su importe. No registra un pago ni vuelve a sumar el gasto. Indicá a quién se le debe pagar.</p></AyudaFinanzas><fieldset disabled={operacion.guardando} className="space-y-4"><Field label="A quién se debe pagar"><Input required maxLength={160} value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Proveedor o responsable del cobro" /></Field><Field label="Referencia de la contraparte"><Input maxLength={160} value={referencia} onChange={(e) => setReferencia(e.target.value)} placeholder="Identificador o referencia interna" /></Field></fieldset>{operacion.error && <p role="alert" className="text-sm text-danger">{operacion.error}</p>}<div className="flex justify-end gap-2"><Button type="button" variant="ghost" disabled={operacion.guardando} onClick={onClose}>Cancelar</Button><Button type="submit" disabled={operacion.guardando || !nombre.trim()}>{operacion.guardando ? "Guardando…" : "Crear cuenta"}</Button></div></form></Modal>;
}
