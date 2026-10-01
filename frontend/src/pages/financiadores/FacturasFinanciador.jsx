import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { adjuntarFactura, descargarFactura, filasDe, opcionesFinanciador, rutaFacturaFinanciador, rutaFinanciador, errorFinanciador } from "@/api/financiadores";
import { Badge, Button, Card, Field, Input, Modal, Select, Spinner, Textarea } from "@/components/ui";
import { EstadoVacio } from "@/components/ui/estados";

const AVISO = "Versión preliminar: registra documentación de facturas. No emite comprobantes fiscales, no los valida ante ARCA, no liquida, no concilia ni registra pagos";
const HOY = () => new Date().toLocaleDateString("en-CA");
const TIPOS = { factura: "Factura", nota_credito: "Nota de crédito", nota_debito: "Nota de débito", otro: "Otro" };
const inicial = { direccion: "recibida", contraparte_tipo: "institucion", convenio: "", afiliado: "", contraparte_nombre: "", contraparte_identificador: "", tipo: "factura", letra: "", numero: "", fecha: HOY(), importe: "", periodo: "", concepto: "", observaciones: "" };

export default function FacturasFinanciador({ organizacion, usuarioId }) {
  const [direccion, setDireccion] = useState("");
  const [pagina, setPagina] = useState(1);
  const [id, setId] = useState(null);
  const [modal, setModal] = useState(null);
  const [error, setError] = useState(null);
  const qc = useQueryClient();
  const base = rutaFacturaFinanciador(organizacion.id);
  const scope = ["financiadores", usuarioId, organizacion.id, "facturas"];
  const lista = useQuery({ queryKey: [...scope, direccion, pagina], queryFn: () => api.get(`${base}?${new URLSearchParams({ page: pagina, ...(direccion && { direccion }) })}`), gcTime: 0 });
  const detalle = useQuery({ queryKey: [...scope, id], queryFn: () => api.get(`${base}${id}/`), enabled: Boolean(id), gcTime: 0 });
  const puedeEscribir = organizacion.rol !== "auditor";
  const volver = () => { setId(null); setModal(null); setError(null); };
  const cerrar = () => setModal(null);
  const actualizar = async () => { await qc.invalidateQueries({ queryKey: scope }); setModal(null); };
  async function descargar() {
    setError(null);
    try { await descargarFactura(organizacion.id, id, detalle.data?.adjunto_nombre || "factura"); }
    catch (err) { setError(err); }
  }
  return <section className="space-y-5" aria-label="Documentación de facturas">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex items-center gap-3"><h1 className="text-cifra font-bold">Documentación de facturas</h1><Badge tone="amber">Versión preliminar</Badge></div><p className="mt-1 text-sm text-texto-suave">Facturas recibidas y emitidas por este financiador fuera de Salud.</p></div>{puedeEscribir && !id && <Button onClick={() => setModal("nueva")}>Nueva factura</Button>}</div>
    <p className="rounded-md border border-borde bg-superficie-2 p-3 text-sm text-texto-suave">{AVISO}.</p>
    {error && <p role="alert" className="text-sm text-badge-error-fg">{errorFinanciador(error)}</p>}
    {modal === "nueva" && <Formulario organizacion={organizacion} base={base} onCancel={cerrar} onGuardado={async (factura) => { await actualizar(); setId(factura.id); }} />}
    {id ? <>
      <Button variant="secondary" onClick={volver}>← Volver al listado</Button>
      {detalle.isLoading ? <Spinner label="Cargando factura…" /> : detalle.error ? <p role="alert">{errorFinanciador(detalle.error)}</p> : detalle.data && <>
        <Card className="p-5 space-y-3"><h2 className="text-lg font-semibold">{TIPOS[detalle.data.tipo]} {detalle.data.letra || ""} {detalle.data.numero}</h2><p><Badge tone="green">Registrada</Badge> · {detalle.data.direccion === "recibida" ? "Recibida" : "Emitida por el financiador"}</p><p>Contraparte: {detalle.data.contraparte_nombre}</p><p>Fecha: {detalle.data.fecha} · Importe: ARS {Number(detalle.data.importe).toLocaleString("es-AR", { minimumFractionDigits: 2 })}</p>{detalle.data.periodo && <p>Período: {detalle.data.periodo}</p>}{detalle.data.concepto && <p>Concepto: {detalle.data.concepto}</p>}{detalle.data.observaciones && <p>Observaciones: {detalle.data.observaciones}</p>}
          {detalle.data.adjunto_disponible ? <div>{detalle.data.adjunto_nombre ? <Button variant="secondary" onClick={descargar}>Descargar {detalle.data.adjunto_nombre}</Button> : <p>Sin adjunto.</p>}</div> : <p>Adjuntos no disponibles en este entorno</p>}
          {puedeEscribir && <div className="flex flex-wrap gap-2"><Button variant="secondary" onClick={() => setModal("editar")}>Editar</Button>{detalle.data.adjunto_disponible && !detalle.data.adjunto_nombre && <Button variant="secondary" onClick={() => setModal("adjunto")}>Agregar adjunto</Button>}</div>}</Card>
        {modal === "editar" && <Formulario organizacion={organizacion} base={base} factura={detalle.data} onCancel={cerrar} onGuardado={actualizar} />}
        {modal === "adjunto" && <Adjuntar organizacionId={organizacion.id} id={id} onCancel={cerrar} onGuardado={actualizar} />}
      </>}
    </> : <>
      <Field label="Dirección"><Select value={direccion} onChange={(event) => { setPagina(1); setDireccion(event.target.value); }}><option value="">Todas</option><option value="recibida">Recibidas</option><option value="emitida">Emitidas por el financiador</option></Select></Field>
      {lista.isLoading ? <Spinner label="Cargando facturas…" /> : lista.error ? <p role="alert">{errorFinanciador(lista.error)} <Button variant="secondary" onClick={() => lista.refetch()}>Reintentar</Button></p> : filasDe(lista.data).length === 0 ? <Card><EstadoVacio titulo="Todavía no hay facturas registradas" detalle="Registrá la primera factura para documentarla." /></Card> : <Card className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-superficie-2"><tr><th scope="col" className="p-3">Número</th><th scope="col" className="p-3">Dirección</th><th scope="col" className="p-3">Contraparte</th><th scope="col" className="p-3">Fecha</th><th scope="col" className="p-3">Importe</th><th scope="col" className="p-3">Estado</th></tr></thead><tbody>{filasDe(lista.data).map((item) => <tr key={item.id} className="border-t border-division"><td className="p-3"><button className="font-semibold text-accent underline" onClick={() => setId(item.id)}>{item.numero}</button></td><td className="p-3">{item.direccion === "recibida" ? "Recibida" : "Emitida"}</td><td className="p-3">{item.contraparte_nombre}</td><td className="p-3">{item.fecha}</td><td className="p-3">ARS {Number(item.importe).toLocaleString("es-AR", { minimumFractionDigits: 2 })}</td><td className="p-3"><Badge tone="green">Registrada</Badge></td></tr>)}</tbody></table></Card>}
      {!lista.error && <div className="flex gap-2"><Button variant="secondary" disabled={pagina === 1} onClick={() => setPagina(pagina - 1)}>Anterior</Button><Button variant="secondary" disabled={!lista.data?.next} onClick={() => setPagina(pagina + 1)}>Siguiente</Button></div>}
    </>}
  </section>;
}

function Formulario({ organizacion, base, factura, onCancel, onGuardado }) {
  const [datos, setDatos] = useState(() => factura ? Object.fromEntries(Object.keys(inicial).map((campo) => [campo, factura[campo] ?? ""])) : inicial);
  const [buscar, setBuscar] = useState("");
  const [error, setError] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const convenios = useQuery({ queryKey: ["facturas-convenios", organizacion.id], queryFn: () => opcionesFinanciador(organizacion.id, "convenios"), enabled: datos.contraparte_tipo === "institucion", gcTime: 0 });
  const afiliados = useQuery({ queryKey: ["facturas-afiliados", organizacion.id, buscar], queryFn: () => api.get(`${rutaFinanciador(organizacion.id, "padron")}?${new URLSearchParams({ search: buscar })}`), enabled: datos.contraparte_tipo === "afiliado" && buscar.length >= 2, gcTime: 0 });
  const opcionesAfiliado = filasDe(afiliados.data);
  const afiliadoActual = factura?.afiliado && !opcionesAfiliado.some((x) => x.id === factura.afiliado) ? [{ id: factura.afiliado, nombre: factura.contraparte_nombre }] : [];
  const editar = (campo) => (event) => setDatos((previo) => ({ ...previo, [campo]: event.target.value }));
  async function guardar(event) {
    event.preventDefault(); setGuardando(true); setError(null);
    try {
      const body = { ...datos, convenio: datos.contraparte_tipo === "institucion" && datos.convenio ? Number(datos.convenio) : null, afiliado: datos.contraparte_tipo === "afiliado" && datos.afiliado ? Number(datos.afiliado) : null };
      const resultado = factura ? await api.patch(`${base}${factura.id}/`, body) : await api.post(base, body);
      await onGuardado(resultado);
    } catch (err) { setError(err); }
    finally { setGuardando(false); }
  }
  return <Modal title={factura ? "Editar factura" : "Nueva factura"} onClose={onCancel} width={680}><form onSubmit={guardar} className="space-y-4">{error && <p role="alert" className="text-badge-error-fg">{errorFinanciador(error)}</p>}<fieldset disabled={guardando} className="grid gap-4 sm:grid-cols-2">
    {convenios.error && datos.contraparte_tipo === "institucion" && <p role="alert">{errorFinanciador(convenios.error)} <Button type="button" variant="secondary" onClick={() => convenios.refetch()}>Reintentar</Button></p>}
    {afiliados.error && datos.contraparte_tipo === "afiliado" && <p role="alert">{errorFinanciador(afiliados.error)} <Button type="button" variant="secondary" onClick={() => afiliados.refetch()}>Reintentar</Button></p>}
    <Field label="Dirección"><Select value={datos.direccion} onChange={editar("direccion")}><option value="recibida">Recibida</option><option value="emitida">Emitida por el financiador</option></Select></Field>
    <Field label="Tipo de contraparte"><Select value={datos.contraparte_tipo} onChange={(e) => setDatos((previo) => ({ ...previo, contraparte_tipo: e.target.value, convenio: "", afiliado: "", contraparte_nombre: "" }))}><option value="institucion">Institución</option><option value="afiliado">Afiliado</option></Select></Field>
    {datos.contraparte_tipo === "institucion" ? <Field label="Convenio (opcional)"><Select value={datos.convenio} onChange={editar("convenio")}><option value="">Sin vínculo</option>{(convenios.data || []).map((x) => <option key={x.id} value={x.id}>{x.institucion_nombre} · {x.estado}</option>)}</Select></Field> : <div className="space-y-2"><Field label="Buscar afiliado"><Input value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder="Nombre, documento o número" /></Field><Field label="Afiliación (opcional)"><Select value={datos.afiliado} onChange={editar("afiliado")}><option value="">Sin vínculo</option>{[...afiliadoActual, ...opcionesAfiliado].map((x) => <option key={x.id} value={x.id}>{x.nombre} · {x.numero || ""}</option>)}</Select></Field>{afiliados.data?.next && <p className="text-xs">Precisá la búsqueda para ver más resultados.</p>}</div>}
    {!(datos.convenio || datos.afiliado) && <><Field label="Nombre de contraparte"><Input required maxLength={160} value={datos.contraparte_nombre} onChange={editar("contraparte_nombre")} /></Field><Field label="CUIT o documento (opcional)"><Input maxLength={80} value={datos.contraparte_identificador} onChange={editar("contraparte_identificador")} /></Field></>}
    <Field label="Tipo"><Select value={datos.tipo} onChange={editar("tipo")}>{Object.entries(TIPOS).map(([valor, titulo]) => <option key={valor} value={valor}>{titulo}</option>)}</Select></Field><Field label="Letra"><Select value={datos.letra} onChange={editar("letra")}><option value="">Ninguna</option>{["A", "B", "C", "M"].map((x) => <option key={x}>{x}</option>)}</Select></Field>
    <Field label="Número"><Input required maxLength={120} value={datos.numero} onChange={editar("numero")} /></Field><Field label="Fecha"><Input required type="date" max={HOY()} value={datos.fecha} onChange={editar("fecha")} /></Field><Field label="Importe ARS"><Input required type="number" min="0.01" step="0.01" value={datos.importe} onChange={editar("importe")} /></Field><Field label="Período (opcional)"><Input maxLength={100} value={datos.periodo} onChange={editar("periodo")} /></Field><Field label="Concepto (opcional)"><Input maxLength={255} value={datos.concepto} onChange={editar("concepto")} /></Field><Field label="Observaciones (opcional)"><Textarea value={datos.observaciones} onChange={editar("observaciones")} /></Field>
  </fieldset><div className="flex gap-2"><Button type="submit" disabled={guardando}>{guardando ? "Guardando…" : "Guardar factura"}</Button><Button type="button" variant="secondary" disabled={guardando} onClick={onCancel}>Cancelar</Button></div></form></Modal>;
}

function Adjuntar({ organizacionId, id, onCancel, onGuardado }) {
  const [archivo, setArchivo] = useState(null);
  const [error, setError] = useState(null);
  const [guardando, setGuardando] = useState(false);
  async function subir(e) { e.preventDefault(); setGuardando(true); setError(null); try { await adjuntarFactura(organizacionId, id, archivo); await onGuardado(); } catch (err) { setError(err); } finally { setGuardando(false); } }
  return <Modal title="Agregar adjunto" onClose={onCancel}><form onSubmit={subir} className="space-y-3">{error && <p role="alert" className="text-badge-error-fg">{errorFinanciador(error)}</p>}<Field label="PDF o imagen, hasta 10 MB"><Input required type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" onChange={(e) => setArchivo(e.target.files?.[0] || null)} /></Field><div className="flex gap-2"><Button type="submit" disabled={!archivo || guardando}>{guardando ? "Adjuntando…" : "Adjuntar"}</Button><Button type="button" variant="secondary" disabled={guardando} onClick={onCancel}>Cancelar</Button></div></form></Modal>;
}
