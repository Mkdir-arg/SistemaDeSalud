import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { importeARS, opcionesFinanzas } from "@/api/finanzas";
import { useLista } from "@/api/queries";
import { Button, Card, Checkbox, Field, Input, Modal, Select, Spinner } from "@/components/ui";
import { DataTable, useTablaUrl } from "@/components/ui/tabla";
import { useFiltrosFinanzas } from "./ControlesFinanzas";
import { EstadoError } from "@/components/ui/estados";
import { decimalDinero, filtroAreaDinero, importeValido, mensajeErrorDinero } from "./dinero";

export default function ConfiguracionCobros({ institucion, permisos, onClose }) {
  const qc = useQueryClient();
  const [formulario, setFormulario] = useState(null);
  const base = ["finanzas", permisos.usuarioId, institucion.id, "configuracion-cobros"];
  const prestaciones = useQuery({ queryKey: [...base, "prestaciones"], queryFn: () => opcionesFinanzas("prestaciones-costo", institucion.id), gcTime: 0 });
  const politicas = useQuery({ queryKey: [...base, "politicas"], queryFn: () => opcionesFinanzas("politicas-cobro", institucion.id), gcTime: 0 });
  const error = prestaciones.error || politicas.error;
  const ultimas = new Map();
  for (const politica of politicas.data || []) {
    const anterior = ultimas.get(politica.prestacion);
    if (!anterior || politica.vigente_desde > anterior.vigente_desde || (politica.vigente_desde === anterior.vigente_desde && politica.id > anterior.id)) ultimas.set(politica.prestacion, politica);
  }
  async function guardado() { setFormulario(null); await qc.invalidateQueries({ queryKey: ["finanzas"] }); }
  return <Modal title="Configurar cobros por atención" onClose={formulario ? undefined : onClose} width={780}>
    {formulario ? <FormularioPolitica key={formulario.id || "nueva"} fila={formulario} prestaciones={prestaciones.data || []} permisos={permisos} onClose={() => setFormulario(null)} onGuardado={guardado} /> : <div className="space-y-4">
      <p className="text-sm text-texto-debil">Elegí si una atención genera una cuenta por cobrar. Su costo interno y su arancel son importes distintos. Sin una política explícita no se genera un cobro.</p>
      {error && <EstadoError error={error} onReintentar={() => { prestaciones.refetch(); politicas.refetch(); }} />}
      {prestaciones.isLoading || politicas.isLoading ? <Spinner label="Consultando configuración…" /> : <><Button disabled={Boolean(error) || !prestaciones.data?.length} onClick={() => setFormulario({})}>Configurar una atención</Button>{!prestaciones.data?.length && <p className="text-sm text-texto-debil">Primero debe existir una atención vinculada en el catálogo institucional.</p>}
      <div className="space-y-3">{!(politicas.data || []).length ? <p className="text-sm text-texto-debil">Todavía no hay políticas de cobro.</p> : politicas.data.map((p) => <Card key={p.id} className="flex flex-wrap items-start justify-between gap-3 p-4"><div><h3 className="font-semibold">{p.nombre_prestacion}</h3><p className="mt-1 text-sm">{p.cobrar ? `Con cobro · ${p.importe == null ? "Arancel pendiente de definir" : importeARS(p.importe)}` : "Sin cobro"}</p><p className="mt-1 text-sm text-texto-debil">Desde {new Date(p.vigente_desde).toLocaleString("es-AR")} · Versión #{p.id} · {ultimas.get(p.prestacion)?.id === p.id ? "Última configuración" : "Histórica"}</p>{p.cobrar && <p className="mt-1 text-sm text-texto-debil">{p.contraparte_nombre ? `Responsable: ${p.contraparte_nombre}` : "Responsable pendiente: se completará antes de crear la cuenta"}</p>}</div>{ultimas.get(p.prestacion)?.id === p.id && <Button size="sm" variant="secondary" onClick={() => setFormulario(p)}>Cambiar para futuras atenciones</Button>}</Card>)}</div></>}
      <p className="text-sm text-texto-debil">Cada cambio crea una versión desde el momento de guardado. No modifica cuentas ni atenciones anteriores. Desactivar el catálogo no suspende el cobro: cambiá esta política a «No: atención sin cobro», incluso si la atención está inactiva.</p>
    </div>}
  </Modal>;
}

function FormularioPolitica({ fila, prestaciones, permisos, onClose, onGuardado }) {
  const [prestacion, setPrestacion] = useState(String(fila.prestacion || ""));
  const [cobrar, setCobrar] = useState(fila.cobrar ? "si" : "no");
  const [importe, setImporte] = useState(fila.importe || "");
  const [nombre, setNombre] = useState(fila.contraparte_nombre || "");
  const [referencia, setReferencia] = useState(fila.contraparte_referencia || "");
  const [sensible, setSensible] = useState(Boolean(fila.sensible));
  const bloqueo = useRef(false);
  const [guardando, setGuardando] = useState(false);
  const [incierto, setIncierto] = useState(false);
  const [error, setError] = useState("");
  async function guardar(e) {
    e.preventDefault();
    if (bloqueo.current || incierto || !prestacion) return;
    bloqueo.current = true; setGuardando(true); setError("");
    try {
      await api.post("/politicas-cobro/", { prestacion: Number(prestacion), cobrar: cobrar === "si", importe: cobrar === "si" && importe ? decimalDinero(importe) : null, contraparte_nombre: cobrar === "si" ? nombre.trim() : "", contraparte_referencia: cobrar === "si" ? referencia.trim() : "", sensible });
      await onGuardado();
    } catch (err) { const dudoso = !err.status || err.status >= 500; setIncierto(dudoso); setError(dudoso ? "No se pudo confirmar el guardado. Volvé a consultar las políticas antes de crear otra versión." : mensajeErrorDinero(err)); }
    finally { bloqueo.current = false; setGuardando(false); }
  }
  return <form onSubmit={guardar} className="space-y-4"><h3 className="text-lg font-semibold">{fila.id ? "Cambiar política para futuras atenciones" : "Nueva política de cobro"}</h3><fieldset disabled={guardando || incierto} className="space-y-4"><Field label="Atención"><Select required value={prestacion} disabled={Boolean(fila.id)} onChange={(e) => setPrestacion(e.target.value)}><option value="">Elegí una atención</option>{prestaciones.filter((p) => p.activo || p.id === fila.prestacion).map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}</Select></Field><Field label="¿Esta atención se cobra?"><Select value={cobrar} onChange={(e) => setCobrar(e.target.value)}><option value="no">No: atención sin cobro</option><option value="si">Sí: generar cuenta por cobrar</option></Select></Field>{cobrar === "si" && <><Field label="Arancel en ARS" hint="No se toma del costo interno. Si falta, la atención quedará pendiente hasta definirlo."><Input inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" value={importe} onChange={(e) => setImporte(e.target.value)} /></Field><Field label="Quién debe pagar" hint="No se atribuye automáticamente al paciente. Podés completarlo después en los cobros pendientes."><Input maxLength={160} value={nombre} onChange={(e) => setNombre(e.target.value)} /></Field><Field label="Referencia del responsable"><Input maxLength={160} value={referencia} onChange={(e) => setReferencia(e.target.value)} /></Field></>}{permisos.permite("configurar_cobros", null, true) && <Checkbox label="Información sensible" checked={sensible} onChange={(e) => setSensible(e.target.checked)} />}</fieldset><p className="text-sm text-texto-debil">Se aplica desde el guardado a nuevas atenciones. No cobra dinero automáticamente.</p>{error && <p role="alert" className="text-sm text-danger">{error}</p>}<div className="flex justify-end gap-2"><Button type="button" variant="ghost" disabled={guardando} onClick={onClose}>Volver</Button><Button type="submit" disabled={guardando || incierto || !prestacion || (cobrar === "si" && importe !== "" && !importeValido(importe))}>{guardando ? "Guardando…" : "Guardar política"}</Button></div></form>;
}

export function PendientesCobro({ institucion, permisos, area }) {
  const tabla = useTablaUrl("pendientes_cobro");
  const busqueda = useFiltrosFinanzas("pendientes_cobro", ["search"]);
  const [fila, setFila] = useState(null);
  const params = { institucion: institucion.id, ...filtroAreaDinero(area), estado: "pendiente", ...busqueda.valores, ordering: tabla.orden, page: tabla.pagina, pageSize: tabla.tamano };
  const consulta = useLista("pendientes-cobro", params, { queryKey: ["finanzas", permisos.usuarioId, institucion.id, "pendientes-cobro", params], gcTime: 0, placeholderData: undefined });
  return <section className="space-y-3 border-t border-division pt-5"><div><h2 className="text-lg font-semibold">Cobros por completar</h2><p className="mt-1 text-sm text-texto-debil">Atenciones con cobro previsto que necesitan arancel o responsable. Incluye todos los meses del área seleccionada; todavía no son cuentas.</p></div>
    <RecuperacionCobros institucion={institucion} permisos={permisos} area={area} />
    <DataTable adaptable mantenerEncabezados barra={<Input aria-label="Buscar cobros por completar" placeholder="Prestación o responsable…" value={busqueda.valores.search || ""} onChange={(e) => busqueda.cambiar({ search: e.target.value })} />} filas={consulta.error ? [] : consulta.filas} total={consulta.error ? 0 : consulta.total} paginas={consulta.paginas} tabla={tabla} estado={{ cargando: consulta.isLoading, error: consulta.error, reintentar: consulta.refetch }} vacio={{ titulo: "Sin cobros pendientes de completar" }} columnas={[
      { key: "hecho", orden: "hecho_id", label: "Atención", render: (r) => `${r.nombre_prestacion} · #${r.hecho}` },
      { key: "importe", orden: "importe", label: "Arancel", render: (r) => r.importe == null ? "Falta definir" : importeARS(r.importe) },
      { key: "contraparte_nombre", orden: "contraparte_nombre", label: "Quién debe pagar", render: (r) => r.contraparte_nombre || "Falta definir" },
      { key: "acciones", label: "Acciones", render: (r) => permisos.permite("registrar_dinero", r.area, r.sensible) && <Button size="sm" variant="secondary" onClick={() => setFila(r)}>Completar cobro</Button> },
    ]} />
    {fila && <ResolverPendiente key={fila.id} fila={fila} onClose={() => setFila(null)} />}
  </section>;
}

function RecuperacionCobros({ institucion, permisos, area }) {
  const qc = useQueryClient();
  const tabla = useTablaUrl("recuperacion_cobros");
  const busqueda = useFiltrosFinanzas("recuperacion_cobros", ["search"]);
  const bloqueo = useRef(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const params = { institucion: institucion.id, ...filtroAreaDinero(area), ...busqueda.valores, ordering: tabla.orden, page: tabla.pagina, pageSize: tabla.tamano };
  const consulta = useLista("pendientes-cobro/recuperables", params, { queryKey: ["finanzas", permisos.usuarioId, institucion.id, "recuperacion-cobros", params], gcTime: 0, placeholderData: undefined });
  async function recuperar(hecho) {
    if (bloqueo.current) return;
    bloqueo.current = true; setGuardando(true); setError("");
    try { await api.post("/pendientes-cobro/recuperar/", { hecho }); await qc.invalidateQueries({ queryKey: ["finanzas"] }); }
    catch (err) { setError(mensajeErrorDinero(err)); }
    finally { bloqueo.current = false; setGuardando(false); }
  }
  if (consulta.error) return <EstadoError error={consulta.error} onReintentar={consulta.refetch} titulo="No se pudo verificar si hay cobros por recuperar" />;
  if (!consulta.total && !busqueda.valores.search && !consulta.isLoading) return null;
  return <Card className="space-y-3 p-4"><h3 className="font-semibold">Cobros que necesitan recuperación</h3><p className="text-sm text-texto-debil">La atención se completó, pero su registro de cobro quedó pendiente. Reintentar conserva la configuración de esa atención.</p>{error && <p role="alert" className="text-sm text-danger">{error}</p>}<DataTable adaptable mantenerEncabezados vacio={{ titulo: "Sin atenciones para esta búsqueda" }} barra={<Input aria-label="Buscar atención por recuperar" placeholder="Número de atención…" value={busqueda.valores.search || ""} onChange={(e) => busqueda.cambiar({ search: e.target.value })} />} filas={consulta.filas} total={consulta.total} paginas={consulta.paginas} tabla={tabla} estado={{ cargando: consulta.isLoading }} columnas={[
    { key: "hecho", orden: "id", label: "Atención", render: (r) => `Atención #${r.hecho}` },
    { key: "motivo", label: "Qué falta" },
    { key: "acciones", label: "Acciones", render: (r) => permisos.permite("registrar_dinero", r.area, r.sensible) ? <Button size="sm" variant="secondary" disabled={guardando} onClick={() => recuperar(r.hecho)}>Reintentar registro</Button> : "Requiere autorización para registrar dinero sensible" },
  ]} /></Card>;
}

function ResolverPendiente({ fila, onClose }) {
  const qc = useQueryClient();
  const [importe, setImporte] = useState(fila.importe ?? "");
  const [nombre, setNombre] = useState(fila.contraparte_nombre || "");
  const [referencia, setReferencia] = useState(fila.contraparte_referencia || "");
  const bloqueo = useRef(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  async function guardar(e) {
    e.preventDefault();
    if (bloqueo.current) return;
    bloqueo.current = true; setGuardando(true); setError("");
    try {
      await api.post(`/pendientes-cobro/${fila.id}/resolver/`, { ...(fila.importe == null ? { importe: decimalDinero(importe) } : {}), ...(!fila.contraparte_nombre ? { contraparte_nombre: nombre.trim(), contraparte_referencia: referencia.trim() } : {}) });
      await qc.invalidateQueries({ queryKey: ["finanzas"] }); onClose();
    } catch (err) { setError(mensajeErrorDinero(err)); }
    finally { bloqueo.current = false; setGuardando(false); }
  }
  return <Modal title="Completar cuenta por cobrar" onClose={guardando ? undefined : onClose} width={560}><form onSubmit={guardar} className="space-y-4"><p>{fila.nombre_prestacion} · Atención #{fila.hecho}</p><fieldset disabled={guardando} className="space-y-4"><Field label="Arancel en ARS"><Input required inputMode="decimal" disabled={fila.importe != null} value={importe} onChange={(e) => setImporte(e.target.value)} /></Field><Field label="Quién debe pagar"><Input required maxLength={160} disabled={Boolean(fila.contraparte_nombre)} value={nombre} onChange={(e) => setNombre(e.target.value)} /></Field><Field label="Referencia del responsable"><Input maxLength={160} disabled={Boolean(fila.contraparte_nombre)} value={referencia} onChange={(e) => setReferencia(e.target.value)} /></Field></fieldset><p className="text-sm text-texto-debil">Se creará la cuenta por cobrar. No registra un cobro ni asigna la deuda automáticamente al paciente.</p>{error && <p role="alert" className="text-sm text-danger">{error}</p>}<div className="flex justify-end gap-2"><Button type="button" variant="ghost" disabled={guardando} onClick={onClose}>Cancelar</Button><Button type="submit" disabled={guardando || !nombre.trim() || !importeValido(importe)}>{guardando ? "Guardando…" : "Crear cuenta por cobrar"}</Button></div></form></Modal>;
}
