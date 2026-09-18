import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "@/api/client";
import { filasDe } from "@/api/financiadores";
import { importeARS } from "@/api/finanzas";
import { useAuth } from "@/auth/AuthContext";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Ayuda, Badge, Button, Card, Checkbox, Field, Input, Modal, Select, Spinner, Tabs, Textarea } from "@/components/ui";
import { EstadoVacio } from "@/components/ui/estados";
import { EditarVigencia, ErrorPortal, ESTADOS_CONVENIO } from "./PortalFinanciadores";
import { fechaHora, plural } from "@/lib/format";
import SeguimientoCobros from "./SeguimientoCobros";
import AutorizacionEvaluacion from "./AutorizacionEvaluacion";
import { POR_PAGINA } from "@/api/queries";

const hoy = () => new Date().toLocaleDateString("en-CA");
const ESTADOS = { autorizacion_pendiente: "Autorización pendiente", reservada: "Reservada", realizada: "Realizada", liberada: "Liberada", pendiente: "Pendiente de resolución administrativa", resuelta: "Resuelta", arancel_pendiente: "Arancel pendiente", evaluacion_pendiente: "Pendiente de evaluación", sin_cobro: "Sin cobro" };

export default function CoberturasHospital() {
  const { user } = useAuth();
  const { institucion } = useInstitucion();
  return <EspacioHospital key={`${user.id}:${institucion.id}`} usuarioId={user.id} institucion={institucion} />;
}

function EspacioHospital({ usuarioId, institucion }) {
  const scope = ["coberturas-hospital", usuarioId, institucion.id];
  const [parametros, setParametros] = useSearchParams();
  const tab = parametros.get("tab") || "reservas";
  const setTab = (valor) => { const nuevos = new URLSearchParams(parametros); nuevos.set("tab", valor); setParametros(nuevos); };
  const qc = useQueryClient();
  const opciones = useQuery({ queryKey: [...scope, "opciones"], queryFn: () => api.get(`/coberturas/opciones/?institucion=${institucion.id}`), gcTime: 0 });
  const actualizar = () => qc.invalidateQueries({ queryKey: scope });
  if (opciones.isLoading) return <Spinner label="Consultando cobertura y permisos…" />;
  if (opciones.error) return <div className="p-6"><ErrorPortal error={opciones.error} reintentar={opciones.refetch} /></div>;
  const datos = opciones.data;
  const permisos = datos.permisos || {};
  const tabs = [{ key: "reservas", label: "Reservas y saldos" }, ...(permisos.seguimiento ? [{ key: "seguimiento", label: "Seguimiento de cobros" }] : []), ...(permisos.operar ? [{ key: "atencion", label: "Evaluar una prestación" }] : []), ...(permisos.configurar ? [{ key: "configuracion", label: "Configuración" }] : [])];
  return <div className="space-y-5 p-4 sm:p-8">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex items-center gap-2"><h1 className="text-2xl font-bold">Coberturas y copagos</h1><Ayuda>{institucion.nombre} · Cobertura por prestación, reservas compartidas y saldos a resolver.</Ayuda></div></div><Link to="/finanzas" className="text-sm font-semibold text-accent hover:underline">Finanzas y cobros</Link></div>
    {!datos.configuracion?.activo && <Card className="p-4"><div className="flex items-center gap-2"><p className="font-semibold">El circuito de cobertura todavía no está habilitado</p><Ayuda>Un usuario con permiso de configuración puede habilitarlo después de verificar prestaciones, aranceles y convenios.</Ayuda></div></Card>}
    <div className="overflow-x-auto"><Tabs tabs={tabs} valor={tab} onChange={setTab} /></div>
    {!tabs.some((item) => item.key === tab) && <Card className="p-5"><p role="alert">Esta sección no está disponible con tus permisos en este hospital.</p><Button className="mt-3" variant="secondary" onClick={() => setTab("reservas")}>Ver reservas y saldos</Button></Card>}
    {tab === "reservas" && <ReservasHospital scope={scope} institucion={institucion} opciones={datos} actualizar={actualizar} />}
    {tab === "seguimiento" && permisos.seguimiento && <SeguimientoCobros usuarioId={usuarioId} institucion={institucion} onReservas={() => setTab("reservas")} />}
    {tab === "atencion" && permisos.operar && <AtencionCobertura scope={scope} institucion={institucion} opciones={datos} actualizar={actualizar} />}
    {tab === "configuracion" && permisos.configurar && <ConfiguracionHospital opciones={datos} institucion={institucion} actualizar={actualizar} />}
  </div>;
}

function CatalogoComun({ catalogo = [], prestaciones = [] }) {
  const porComun = new Map();
  for (const p of prestaciones) {
    if (p.comun == null) continue;
    porComun.set(p.comun, [...(porComun.get(p.comun) || []), p]);
  }
  const sinVincular = prestaciones.filter((p) => p.comun == null).length;
  return <section aria-label="Prestaciones del catálogo común" className="mt-5 border-t border-division pt-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="flex items-center gap-2"><h3 className="font-semibold">Prestaciones del catálogo común</h3><Ayuda>Lo administra la plataforma y es el mismo para todos los hospitales y financiadores. Acá se ve qué prestación de este hospital quedó vinculada a cada una.</Ayuda></div>
      {sinVincular > 0 && <span className="text-sm text-badge-amber-fg">{plural(sinVincular, "prestación del hospital sin vincular", "prestaciones del hospital sin vincular")}</span>}
    </div>
    {!catalogo.length ? <div className="mt-3"><EstadoVacio titulo="El catálogo común todavía no tiene prestaciones" /></div> : <div className="mt-3 overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-superficie-2 text-texto-debil"><tr>{["Código", "Prestación", "Categoría", "Vinculada en este hospital"].map((label) => <th key={label} scope="col" className="px-3 py-2">{label}</th>)}</tr></thead><tbody>{catalogo.map((item) => {
      const locales = porComun.get(item.id) || [];
      return <tr key={item.id} className="border-t border-division"><td className="px-3 py-2 font-mono">{item.codigo}</td><td className="px-3 py-2">{item.nombre}</td><td className="px-3 py-2 text-texto-debil">{item.categoria || "—"}</td><td className="px-3 py-2">{locales.length ? locales.map((p) => p.nombre).join(" · ") : <span className="text-texto-debil">Sin vincular</span>}</td></tr>;
    })}</tbody></table></div>}
  </section>;
}

function ConfiguracionHospital({ opciones, institucion, actualizar }) {
  const [activo, setActivo] = useState(Boolean(opciones.configuracion?.activo));
  const [dias, setDias] = useState(opciones.configuracion?.dias_reserva_antigua ?? 7);
  const [prestacion, setPrestacion] = useState("");
  const [comun, setComun] = useState("");
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [mensaje, setMensaje] = useState("");
  const [financiador, setFinanciador] = useState("");
  const [convenio, setConvenio] = useState("");
  const [prestacionArancel, setPrestacionArancel] = useState("");
  const [importe, setImporte] = useState("");
  const [vigencia, setVigencia] = useState(hoy());
  const [cambioConvenio, setCambioConvenio] = useState(null);
  async function guardar(e, accion, body) {
    e.preventDefault(); setError(null); setMensaje(""); setOcupado(true);
    try { await api.post(`/coberturas/${accion}/`, body); await actualizar(); setMensaje("Configuración guardada."); }
    catch (err) { setError(err); }
    finally { setOcupado(false); }
  }
  return <div className="space-y-4">{error && <ErrorPortal error={error} />}{mensaje && <p role="status" className="rounded-md bg-badge-green-bg p-3 text-badge-green-fg">{mensaje}</p>}
    <Card className="p-5"><h2 className="text-lg font-semibold">Circuito de cobertura</h2><form className="mt-4 max-w-[36rem] space-y-4" onSubmit={(e) => guardar(e, "configurar", { institucion: institucion.id, activo, dias_reserva_antigua: Number(dias) })}><Checkbox label="Habilitar cobertura y distribución de cobros para este hospital" checked={activo} onChange={(e) => setActivo(e.target.checked)} disabled={ocupado} /><div className="w-full max-w-[24rem]"><Field label="Considerar antigua una reserva después de (días)" ayuda="Sólo la señala para revisión. No libera cupos automáticamente."><Input className="w-full" type="number" min={1} max={365} value={dias} onChange={(e) => setDias(e.target.value)} required disabled={ocupado} /></Field></div><Button disabled={ocupado}>Guardar configuración</Button></form></Card>
    <Card className="p-5"><div className="flex items-center gap-2"><h2 className="text-lg font-semibold">Vincular prestaciones al catálogo común</h2><Ayuda>La vinculación permite aplicar la cobertura de la misma prestación entre hospitales. El arancel sigue perteneciendo al hospital.</Ayuda></div><form className="mt-4 flex flex-wrap items-end gap-3" onSubmit={(e) => guardar(e, "vincular-prestacion", { prestacion: Number(prestacion), comun: Number(comun) })}><div className="min-w-[220px] flex-1"><Field label="Prestación del hospital"><Select required value={prestacion} onChange={(e) => setPrestacion(e.target.value)} disabled={ocupado}><option value="">Seleccioná una prestación</option>{(opciones.prestaciones || []).map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}</Select></Field></div><div className="min-w-[220px] flex-1"><Field label="Prestación del catálogo común"><Select required value={comun} onChange={(e) => setComun(e.target.value)} disabled={ocupado}><option value="">Seleccioná una prestación</option>{(opciones.catalogo || []).map((p) => <option key={p.id} value={p.id}>{p.codigo} · {p.nombre}</option>)}</Select></Field></div><Button disabled={ocupado}>Guardar vínculo</Button></form><CatalogoComun catalogo={opciones.catalogo} prestaciones={opciones.prestaciones} /></Card>
    <Card className="p-5"><div className="flex items-center gap-2"><h2 className="text-lg font-semibold">Convenios con financiadores</h2><Ayuda>La contraparte acepta cada propuesta. Cerrar un convenio conserva las reservas y los cargos anteriores; deja de habilitar nuevas coberturas.</Ayuda></div><form className="mt-4 flex flex-wrap items-end gap-3" onSubmit={(e) => guardar(e, "convenio", { institucion: institucion.id, financiador: Number(financiador) })}><div className="min-w-[220px] flex-1"><Field label="Financiador para el convenio"><Select required value={financiador} onChange={(e) => setFinanciador(e.target.value)} disabled={ocupado}><option value="">Seleccioná un financiador</option>{(opciones.financiadores || []).map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</Select></Field></div><Button disabled={ocupado}>Proponer convenio</Button></form><div className="mt-4 space-y-3">{(opciones.convenios || []).map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 border-t border-division pt-3"><div className="text-sm"><span>{item.financiador_nombre || `Financiador ${item.financiador}`} · {ESTADOS_CONVENIO[item.estado] || item.estado}</span>{item.cerrado_en && <p className="mt-1 text-xs text-texto-debil">{fechaHora(item.cerrado_en)} · {item.motivo_cierre}</p>}</div><div className="flex flex-wrap gap-2">{item.estado === "propuesto" && item.propuesto_por === "financiador" && <><Button size="sm" variant="secondary" disabled={ocupado} onClick={(e) => guardar(e, "aceptar-convenio", { convenio: item.id })}>Aceptar convenio</Button><Button size="sm" variant="ghost" disabled={ocupado} onClick={() => setCambioConvenio({ accion: "rechazar-convenio", fila: item })}>Rechazar propuesta</Button></>}{item.estado === "activo" && <Button size="sm" variant="ghost" disabled={ocupado} onClick={() => setCambioConvenio({ accion: "cerrar-convenio", fila: item })}>Cerrar convenio</Button>}</div></div>)}</div></Card>
    <Card className="p-5"><div className="flex items-center gap-2"><h2 className="text-lg font-semibold">Aranceles</h2><Ayuda>Se utiliza el arancel general del hospital. Una excepción acordada con el financiador reemplaza ese valor desde su vigencia. Una prestación sin arancel queda pendiente y no genera deuda.</Ayuda></div><Link to="/finanzas?tab=dinero" className="mt-3 inline-block text-sm font-semibold text-accent hover:underline">Ir a pagos y cobros para configurar el arancel general</Link><form className="mt-5 space-y-4 border-t border-division pt-4" onSubmit={(e) => guardar(e, "arancel", { convenio: Number(convenio), prestacion: Number(prestacionArancel), importe: importe.trim() || null, vigente_desde: vigencia })}><h3 className="font-semibold">Excepción acordada</h3><Field label="Convenio activo"><Select required value={convenio} onChange={(e) => setConvenio(e.target.value)} disabled={ocupado}><option value="">Seleccioná un convenio</option>{(opciones.convenios || []).filter((item) => item.estado === "activo").map((item) => <option key={item.id} value={item.id}>{item.financiador_nombre || `Financiador ${item.financiador}`}</option>)}</Select></Field><Field label="Prestación con arancel acordado"><Select required value={prestacionArancel} onChange={(e) => setPrestacionArancel(e.target.value)} disabled={ocupado}><option value="">Seleccioná una prestación</option>{(opciones.prestaciones || []).map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</Select></Field><div className="grid gap-3 sm:grid-cols-2"><Field label="Importe acordado (ARS)" ayuda="Vacío vuelve a utilizar el arancel general desde la nueva vigencia."><Input type="number" min="0.01" step="0.01" value={importe} onChange={(e) => setImporte(e.target.value)} disabled={ocupado} /></Field><Field label="Arancel vigente desde"><Input type="date" min={hoy()} required value={vigencia} onChange={(e) => setVigencia(e.target.value)} disabled={ocupado} /></Field></div><Button disabled={ocupado}>Guardar arancel acordado</Button></form></Card>
    {cambioConvenio && <EditarVigencia {...cambioConvenio} guardar={(body) => api.post(`/coberturas/${cambioConvenio.accion}/`, body)} onClose={() => setCambioConvenio(null)} onGuardado={async () => { setCambioConvenio(null); setConvenio(""); await actualizar(); setMensaje("Convenio actualizado. Se conservaron las reservas y los cargos anteriores."); }} />}
  </div>;
}

function AtencionCobertura({ scope, institucion, opciones, actualizar }) {
  const [caso, setCaso] = useState("");
  const [numero, setNumero] = useState("");
  const [buscar, setBuscar] = useState("");
  useEffect(() => { const timer = setTimeout(() => setBuscar(numero.trim()), 2000); return () => clearTimeout(timer); }, [numero]);
  const consulta = useQuery({ queryKey: [...scope, "buscar-caso", buscar], queryFn: () => api.get(`/coberturas/opciones/?${new URLSearchParams({ institucion: institucion.id, search: buscar })}`), enabled: Boolean(buscar), gcTime: 0 });
  const candidatos = [...(consulta.data?.casos || []), ...(opciones.casos || []).filter((item) => !(consulta.data?.casos || []).some((encontrado) => encontrado.id === item.id))];
  const seleccionado = candidatos.find((item) => String(item.id) === caso);
  return <div className="space-y-4"><Card className="space-y-4 p-5"><div className="min-w-0"><Field label="Buscar paciente o caso" ayuda="La búsqueda se actualiza dos segundos después de escribir. La afiliación elegida se conserva para este caso aunque cambie el padrón."><Input value={numero} onChange={(e) => setNumero(e.target.value)} placeholder="Nombre, documento o número de caso" /></Field></div>{consulta.error && <ErrorPortal error={consulta.error} reintentar={consulta.refetch} />}{buscar && consulta.data && !consulta.data.casos?.length && <p className="text-sm text-texto-debil">No hay casos disponibles con esa búsqueda dentro de tus permisos.</p>}<Field label="Caso"><Select value={caso} onChange={(e) => setCaso(e.target.value)}><option value="">Seleccioná un caso</option>{candidatos.map((item) => <option key={item.id} value={item.id}>{item.paciente ? `${item.paciente} · ` : ""}{item.titulo || `Caso ${item.id}`}{item.documento ? ` · ${item.documento}` : ""}</option>)}</Select></Field></Card>{seleccionado && <OperacionCaso key={caso} caso={seleccionado} scope={scope} institucion={institucion} opciones={opciones} actualizar={actualizar} />}</div>;
}

function OperacionCaso({ caso, scope, institucion, opciones, actualizar }) {
  const [documento, setDocumento] = useState(caso.documento || "");
  const [buscar, setBuscar] = useState("");
  const [tipo, setTipo] = useState("verificada");
  const [afiliado, setAfiliado] = useState("");
  const [declaracion, setDeclaracion] = useState("");
  const [motivo, setMotivo] = useState("");
  const [prestacion, setPrestacion] = useState("");
  const [cantidad, setCantidad] = useState("1");
  const [fecha, setFecha] = useState(hoy());
  const [evaluacion, setEvaluacion] = useState(null);
  const [acepta, setAcepta] = useState(false);
  const [clave, setClave] = useState(() => crypto.randomUUID());
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [mensaje, setMensaje] = useState("");
  const afiliados = useQuery({ queryKey: [...scope, "afiliados", buscar], queryFn: () => api.get(`/coberturas/afiliados/?${new URLSearchParams({ institucion: institucion.id, documento: buscar })}`), enabled: Boolean(buscar), gcTime: 0 });
  function limpiarEvaluacion() { setEvaluacion(null); setAcepta(false); setClave(crypto.randomUUID()); setMensaje(""); }
  async function operar(accion, body, resultado) {
    setError(null); setMensaje(""); setOcupado(true);
    try { const data = await api.post(`/coberturas/${accion}/`, body); resultado(data); await actualizar(); }
    catch (err) { setError(err); }
    finally { setOcupado(false); }
  }
  const body = { caso: caso.id, prestacion: Number(prestacion), fecha, cantidad: Number(cantidad) };
  const pendiente = ["pendiente_evaluacion", "arancel_pendiente"].includes(evaluacion?.estado);
  return <div className="space-y-4">{error && <ErrorPortal error={error} />}{mensaje && <p role="status" className="rounded-md bg-badge-green-bg p-3 text-badge-green-fg">{mensaje}</p>}
    <Card className="p-5"><h2 className="text-lg font-semibold">Afiliación del caso</h2>{caso.afiliacion && <p className="mt-2 text-sm text-texto-debil">Selección actual: {caso.afiliacion.financiador_nombre || caso.afiliacion.estado}. Los cargos anteriores conservan su responsable.</p>}<form className="mt-4 space-y-4" onSubmit={(e) => { e.preventDefault(); operar("afiliacion", { caso: caso.id, afiliado: tipo === "verificada" ? Number(afiliado) : null, particular: tipo === "particular", declaracion: tipo === "pendiente" ? declaracion : "", motivo }, () => { limpiarEvaluacion(); setMensaje("Afiliación del caso registrada."); }); }}><Field label="Tipo de afiliación"><Select value={tipo} onChange={(e) => setTipo(e.target.value)} disabled={ocupado}><option value="verificada">Afiliación verificada en el padrón</option><option value="particular">Atención particular</option><option value="pendiente">Declaración pendiente de verificación</option></Select></Field>{tipo === "verificada" && <><div className="flex flex-wrap items-end gap-2"><div className="flex-1"><Field label="Documento del paciente"><Input value={documento} onChange={(e) => { setDocumento(e.target.value); setAfiliado(""); }} disabled={ocupado} /></Field></div><Button type="button" variant="secondary" disabled={!documento.trim() || ocupado} onClick={() => setBuscar(documento.trim())}>Buscar afiliaciones</Button></div>{afiliados.error && <ErrorPortal error={afiliados.error} reintentar={afiliados.refetch} />}<Field label="Afiliación"><Select value={afiliado} required onChange={(e) => setAfiliado(e.target.value)} disabled={ocupado || afiliados.isFetching}><option value="">{afiliados.isFetching ? "Buscando…" : "Seleccioná una afiliación"}</option>{filasDe(afiliados.data).map((item) => <option key={item.id} value={item.id}>{item.financiador_nombre} · {item.numero} · {item.plan_nombre || "Sin plan"}</option>)}</Select></Field>{buscar && !afiliados.isFetching && !afiliados.error && filasDe(afiliados.data).length === 0 && <p className="text-sm text-texto-debil">No hay coincidencias en financiadores con convenio activo. Podés registrar la declaración pendiente.</p>}</>}{tipo === "pendiente" && <Field label="Afiliación declarada"><Input value={declaracion} onChange={(e) => setDeclaracion(e.target.value)} required disabled={ocupado} /></Field>}<Field label="Motivo de selección o corrección"><Input value={motivo} onChange={(e) => setMotivo(e.target.value)} required maxLength={255} disabled={ocupado} /></Field><Button disabled={ocupado || !opciones.configuracion?.activo}>Registrar afiliación del caso</Button></form></Card>
    <Card className="p-5"><h2 className="text-lg font-semibold">Prestación e importe</h2><form className="mt-4 space-y-4" onSubmit={(e) => { e.preventDefault(); setAcepta(false); setEvaluacion(null); operar("evaluar", body, (data) => { setEvaluacion(data); setClave(crypto.randomUUID()); }); }}><Field label="Prestación"><Select value={prestacion} required disabled={ocupado} onChange={(e) => { setPrestacion(e.target.value); limpiarEvaluacion(); }}><option value="">Seleccioná una prestación</option>{(opciones.prestaciones || []).map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</Select></Field><div className="grid grid-cols-2 gap-3"><Field label="Fecha de la prestación"><Input type="date" value={fecha} required disabled={ocupado} onChange={(e) => { setFecha(e.target.value); limpiarEvaluacion(); }} /></Field><Field label="Cantidad"><Input type="number" min={1} max={100000} step={1} value={cantidad} required disabled={ocupado} onChange={(e) => { setCantidad(e.target.value); limpiarEvaluacion(); }} /></Field></div><Button variant="secondary" disabled={ocupado || !opciones.configuracion?.activo}>Consultar cobertura</Button></form>
      {evaluacion && <section aria-label="Evaluación de cobertura" className="mt-5 space-y-4 border-t border-division pt-5"><p className="font-semibold">{evaluacion.motivo}</p><p className="text-sm text-texto-debil">{evaluacion.cubiertas} de {plural(evaluacion.cantidad, "unidad cubierta", "unidades cubiertas")} al {Number(evaluacion.porcentaje).toLocaleString("es-AR")}%{evaluacion.cupo != null ? ` · Cupo ${evaluacion.periodo === "mes" ? "mensual" : "anual"}: ${evaluacion.cupo}` : ""}.</p><dl className="grid gap-3 rounded-lg bg-superficie-2 p-4 sm:grid-cols-3">{[["Importe total", evaluacion.importe_total], ["A cargo del financiador", evaluacion.importe_financiador], ["A cargo del paciente", evaluacion.importe_paciente]].map(([label, value]) => <div key={label}><dt className="text-sm text-texto-debil">{label}</dt><dd className="mt-1 font-semibold">{importeARS(value)}</dd></div>)}</dl><AutorizacionEvaluacion evaluacion={evaluacion} />{pendiente ? <div className="flex items-center gap-2"><p className="text-sm font-semibold">Evaluación incompleta</p><Ayuda>La atención puede continuar. Completá la evaluación antes de confirmar cobertura; no se generará una deuda por datos faltantes.</Ayuda></div> : <>{evaluacion.importe_paciente !== "0.00" && <>{opciones.permisos?.registrar_aceptacion && <Checkbox label={`El paciente aceptó expresamente ${importeARS(evaluacion.importe_paciente)} por ${evaluacion.nombre_prestacion} (${plural(evaluacion.cantidad, "unidad", "unidades")}).`} checked={acepta} onChange={(e) => { setAcepta(e.target.checked); setClave(crypto.randomUUID()); }} disabled={ocupado} />}{!acepta && <p className="text-sm text-badge-amber-fg">Sin aceptación, la parte del paciente queda pendiente de resolución administrativa cuando se realice la prestación.</p>}</>}<div className="flex items-center gap-2"><Button disabled={ocupado} onClick={() => operar("reservar", { ...body, firma: evaluacion.firma, clave, acepta }, () => { limpiarEvaluacion(); setMensaje("Cobertura reservada. El consumo se confirma al registrar la realización."); })}>{ocupado ? "Confirmando…" : "Confirmar reserva de cobertura"}</Button><Ayuda>La consulta no ocupa cupo. Confirmar reserva el cupo hasta que se registre la realización o se confirme que no se realizó.</Ayuda></div></>}</section>}
    </Card>
  </div>;
}

function ReservasHospital({ scope, institucion, opciones, actualizar }) {
  const [page, setPage] = useState(1);
  const [soloAntiguas, setSoloAntiguas] = useState(false);
  const [texto, setTexto] = useState("");
  const [buscar, setBuscar] = useState("");
  const [estado, setEstado] = useState("");
  const [saldo, setSaldo] = useState(false);
  const [prestacion, setPrestacion] = useState("");
  const [modal, setModal] = useState(null);
  const [mensaje, setMensaje] = useState("");
  useEffect(() => { const timer = setTimeout(() => { setBuscar(texto.trim()); setPage(1); }, 2000); return () => clearTimeout(timer); }, [texto]);
  const consulta = useQuery({ queryKey: [...scope, "reservas", page, buscar, estado, saldo, prestacion, soloAntiguas], queryFn: () => api.get(`/coberturas/?${new URLSearchParams({ institucion: institucion.id, page, page_size: POR_PAGINA, ...(buscar ? { search: buscar } : {}), ...(estado ? { estado } : {}), ...(prestacion ? { prestacion } : {}), ...(saldo ? { con_saldo: "true" } : {}), ...(soloAntiguas ? { antiguas: "true" } : {}) })}`), gcTime: 0 });
  const filas = filasDe(consulta.data);
  return <div className="space-y-4"><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5"><Field label="Buscar"><Input value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Paciente, caso o prestación" /></Field><Field label="Estado"><Select value={estado} onChange={(e) => { setEstado(e.target.value); setPage(1); }}><option value="">Todos</option>{Object.entries(ESTADOS).map(([id, nombre]) => <option key={id} value={id}>{nombre}</option>)}</Select></Field><Field label="Prestación"><Select value={prestacion} onChange={(e) => { setPrestacion(e.target.value); setPage(1); }}><option value="">Todas</option>{(opciones.prestaciones || []).map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</Select></Field><Checkbox label="Con saldo pendiente" checked={saldo} onChange={(e) => { setSaldo(e.target.checked); setPage(1); }} /><div className="flex items-center gap-2"><Checkbox label="Sólo reservas antiguas" checked={soloAntiguas} onChange={(e) => { setSoloAntiguas(e.target.checked); setPage(1); }} /><Ayuda>Las reservas antiguas no vencen automáticamente. Los filtros de texto se actualizan dos segundos después de escribir.</Ayuda></div></div>{mensaje && <p role="status" className="rounded-md bg-badge-green-bg p-3 text-badge-green-fg">{mensaje}</p>}<Card className="overflow-hidden">{consulta.isLoading ? <Spinner label="Cargando reservas…" /> : consulta.error ? <div className="p-4"><ErrorPortal error={consulta.error} reintentar={consulta.refetch} /></div> : !filas.length ? <EstadoVacio titulo="No hay reservas para este filtro" /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-superficie-2 text-texto-debil"><tr>{["Caso / prestación", "Fecha / cantidad", "Cobertura", "Saldo", "Acciones"].map((label) => <th key={label} scope="col" className="px-4 py-3">{label}</th>)}</tr></thead><tbody>{filas.map((item) => <tr key={item.id} className="border-t border-division"><td className="space-y-1 px-4 py-3"><p className="font-semibold">{item.caso_titulo || `Caso ${item.caso}`}</p><p>{item.prestacion_nombre || item.evaluacion?.nombre_prestacion}</p></td><td className="px-4 py-3">{item.fecha}<p className="text-texto-debil">{plural(item.cantidad, "unidad", "unidades")}</p></td><td className="space-y-2 px-4 py-3"><Badge tone={item.estado === "realizada" ? "green" : "gray"}>{ESTADOS[item.estado] || item.estado}</Badge>{item.antigua && <p className="text-badge-amber-fg">Antigua · revisar realización</p>}{item.discrepancia && <p className="text-badge-amber-fg">Discrepancia · se conserva lo registrado</p>}</td><td className="px-4 py-3">{item.distribucion ? <><p>{ESTADOS[item.distribucion.estado] || item.distribucion.estado}</p><p className="mt-1 font-semibold">Paciente: {importeARS(item.distribucion.importe_paciente)}</p>{item.distribucion.estado === "autorizacion_pendiente" && <p className="mt-1 text-badge-amber-fg">Financiador pendiente de autorización: {importeARS(item.distribucion.importe_financiador)}</p>}</> : "Se determina al realizar"}</td><td className="space-y-2 px-4 py-3">{item.puede_completar && <Button size="sm" variant="secondary" onClick={() => setModal({ tipo: "completar", item })}>Completar datos</Button>}{item.puede_liberar && item.estado === "reservada" && <Button size="sm" variant="secondary" onClick={() => setModal({ tipo: "liberar", item })}>Revisar reserva</Button>}{item.puede_resolver && ["pendiente", "autorizacion_pendiente"].includes(item.distribucion?.estado) && <Button size="sm" variant="secondary" onClick={() => setModal({ tipo: "resolver", item })}>Resolver saldo</Button>}</td></tr>)}</tbody></table></div>}<div className="flex items-center justify-between gap-3 border-t border-division p-3"><span className="text-sm text-texto-debil">Página {page}</span><div className="flex gap-2"><Button size="sm" variant="ghost" disabled={page === 1 || consulta.isFetching} onClick={() => setPage(page - 1)}>Anterior</Button><Button size="sm" variant="ghost" disabled={!consulta.data?.next || consulta.isFetching} onClick={() => setPage(page + 1)}>Siguiente</Button></div></div></Card><RecuperablesHospital scope={scope} institucion={institucion} actualizar={actualizar} />{modal?.tipo === "completar" ? <CompletarCobertura item={modal.item} scope={scope} institucion={institucion} onClose={() => setModal(null)} onGuardado={async () => { await actualizar(); setMensaje("Evaluación completada conservando los registros anteriores."); setModal(null); }} /> : modal && <ResolverReserva {...modal} onClose={() => setModal(null)} onGuardado={async () => { await actualizar(); setMensaje(modal.tipo === "liberar" ? "Reserva liberada con confirmación de no realización." : "Decisión administrativa registrada."); setModal(null); }} />}</div>;
}

function CompletarCobertura({ item, scope, institucion, onClose, onGuardado }) {
  const [importe, setImporte] = useState("");
  const [tipo, setTipo] = useState("conservar");
  const [afiliado, setAfiliado] = useState("");
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const necesitaArancel = item.distribucion?.estado === "arancel_pendiente";
  const puedeArancel = Boolean(item.puede_completar_arancel);
  const consulta = useQuery({ queryKey: [...scope, "completar-afiliados", item.id], queryFn: () => api.get(`/coberturas/afiliados/?${new URLSearchParams({ institucion: institucion.id, documento: item.paciente_documento || "", reserva: item.id })}`), enabled: tipo === "verificada", gcTime: 0 });
  async function guardar(e) {
    e.preventDefault(); setError(null); setOcupado(true);
    const body = { motivo, ...(importe && puedeArancel ? { arancel: importe } : {}), ...(tipo === "particular" ? { particular: true } : tipo === "verificada" ? { afiliado: Number(afiliado) } : {}) };
    try { await api.post(`/coberturas/${item.id}/completar/`, body); await onGuardado(); }
    catch (err) { setError(err); }
    finally { setOcupado(false); }
  }
  return <Modal title="Completar evaluación pendiente" ayuda="Se conserva el registro original y queda constancia de esta resolución." onClose={ocupado ? undefined : onClose} width={600}><form className="space-y-4" onSubmit={guardar}><p className="text-sm text-texto-debil">{item.prestacion_nombre} · Caso {item.caso}</p>{error && <ErrorPortal error={error} />}{puedeArancel && <Field label="Arancel por unidad (ARS)" ayuda={necesitaArancel ? "Completá el arancel faltante." : "Opcional: completá sólo si falta definir el importe."}><Input type="number" min="0.01" step="0.01" required={necesitaArancel} value={importe} onChange={(e) => setImporte(e.target.value)} disabled={ocupado} /></Field>}{necesitaArancel && !puedeArancel && <p className="text-sm text-badge-amber-fg">El arancel faltante requiere un usuario con permiso de configuración de cobros.</p>}{!necesitaArancel && <><Field label="Revisión de afiliación"><Select value={tipo} onChange={(e) => setTipo(e.target.value)} disabled={ocupado}><option value="conservar">Conservar la afiliación registrada</option><option value="verificada">Confirmar afiliación verificada</option><option value="particular">Confirmar atención particular</option></Select></Field>{tipo === "verificada" && <>{consulta.error && <ErrorPortal error={consulta.error} reintentar={consulta.refetch} />}<Field label="Afiliación verificada"><Select required disabled={ocupado || consulta.isFetching} value={afiliado} onChange={(e) => setAfiliado(e.target.value)}><option value="">{consulta.isFetching ? "Buscando…" : "Seleccioná una afiliación"}</option>{filasDe(consulta.data).map((a) => <option key={a.id} value={a.id}>{a.financiador_nombre} · {a.numero} · {a.nombre}</option>)}</Select></Field></>}</>}<Field label="Motivo de resolución"><Textarea required maxLength={255} value={motivo} onChange={(e) => setMotivo(e.target.value)} disabled={ocupado} /></Field><div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose} disabled={ocupado}>Cancelar</Button><Button disabled={ocupado || (necesitaArancel && !puedeArancel)}>{ocupado ? "Completando…" : "Completar evaluación"}</Button></div></form></Modal>;
}

function RecuperablesHospital({ scope, institucion, actualizar }) {
  const [revision, setRevision] = useState(null);
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(null);
  const [mensaje, setMensaje] = useState("");
  const consulta = useQuery({ queryKey: [...scope, "recuperables"], queryFn: () => api.get(`/coberturas/recuperables/?institucion=${institucion.id}`), gcTime: 0 });
  async function recuperar(hecho) {
    setError(null); setMensaje(""); setOcupado(hecho.id);
    try { await api.post("/coberturas/recuperar/", { hecho: hecho.id }); await actualizar(); setMensaje("Procesamiento reintentado. Consultá el resultado en reservas y saldos."); }
    catch (err) { setError(err); }
    finally { setOcupado(null); }
  }
  if (consulta.isLoading) return <Spinner label="Consultando procesamientos pendientes…" />;
  if (consulta.error) return <ErrorPortal error={consulta.error} reintentar={consulta.refetch} />;
  const filas = filasDe(consulta.data);
  if (!filas.length && !mensaje) return null;
  return <Card className="space-y-4 p-5"><div className="flex items-center gap-2"><h2 className="text-lg font-semibold">Atenciones pendientes de procesamiento</h2><Ayuda>La atención ya se registró. Completá su contexto o reintentá el procesamiento para resolver su cobertura.</Ayuda></div>{error && <ErrorPortal error={error} />}{mensaje && <p role="status" className="text-sm text-badge-green-fg">{mensaje}</p>}{filas.map((hecho) => <div key={hecho.id} className="flex flex-wrap items-center justify-between gap-3 border-t border-division pt-3"><div><p className="font-semibold">Caso {hecho.caso}</p><p className="text-sm text-texto-debil">{fechaHora(hecho.fecha)} · {hecho.contexto_pendiente ? "Contexto pendiente de revisión" : "Procesamiento pendiente"}</p></div><Button size="sm" variant="secondary" disabled={ocupado != null} onClick={() => hecho.contexto_pendiente ? setRevision(hecho) : recuperar(hecho)}>{ocupado === hecho.id ? "Reintentando…" : hecho.contexto_pendiente ? "Revisar contexto" : "Reintentar procesamiento"}</Button></div>)}{revision && <RevisarContexto hecho={revision} onClose={() => setRevision(null)} onGuardado={async () => { setRevision(null); await actualizar(); setMensaje("Contexto revisado. Consultá el resultado en reservas y saldos."); }} />}</Card>;
}

function RevisarContexto({ hecho, onClose, onGuardado }) {
  const [afiliacion, setAfiliacion] = useState("");
  const [prestaciones, setPrestaciones] = useState([]);
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  async function guardar(e) {
    e.preventDefault(); setError(null); setOcupado(true);
    try { await api.post("/coberturas/revisar-contexto/", { hecho: hecho.id, afiliacion: afiliacion ? Number(afiliacion) : null, prestaciones, motivo }); await onGuardado(); }
    catch (err) { setError(err); }
    finally { setOcupado(false); }
  }
  return <Modal title={`Revisar contexto del caso ${hecho.caso}`} ayuda="Seleccioná la afiliación y las prestaciones que correspondían a esta atención ya realizada. La decisión se conserva con su motivo." onClose={ocupado ? undefined : onClose} width={640}><form className="space-y-4" onSubmit={guardar}>{error && <ErrorPortal error={error} />}<Field label="Afiliación de la atención"><Select value={afiliacion} onChange={(e) => setAfiliacion(e.target.value)} disabled={ocupado}><option value="">Pendiente de verificación</option>{(hecho.afiliaciones || []).map((item) => <option key={item.id} value={item.id}>{item.declaracion || item.estado} · Registro {item.id}</option>)}</Select></Field><fieldset disabled={ocupado} className="space-y-2"><legend className="mb-2 text-sm font-semibold">Prestaciones realizadas</legend>{(hecho.prestaciones || []).map((item) => <Checkbox key={item.id} label={item.nombre} checked={prestaciones.includes(item.id)} onChange={(e) => setPrestaciones(e.target.checked ? [...prestaciones, item.id] : prestaciones.filter((id) => id !== item.id))} />)}</fieldset><Field label="Motivo de la revisión"><Textarea required maxLength={255} value={motivo} onChange={(e) => setMotivo(e.target.value)} disabled={ocupado} /></Field><div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose} disabled={ocupado}>Cancelar</Button><Button disabled={ocupado || !prestaciones.length}>{ocupado ? "Registrando…" : "Registrar contexto verificado"}</Button></div></form></Modal>;
}

function ResolverReserva({ tipo, item, onClose, onGuardado }) {
  const parte = item.distribucion?.estado === "autorizacion_pendiente" ? "financiador" : "paciente";
  const importePendiente = item.distribucion?.[`importe_${parte}`];
  const [motivo, setMotivo] = useState("");
  const [confirmado, setConfirmado] = useState(false);
  const [decision, setDecision] = useState("");
  const [evidencia, setEvidencia] = useState("");
  const [clave, setClave] = useState(() => crypto.randomUUID());
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);
  const acuerdo = ["paciente", "financiador"].includes(decision);
  async function guardar(e) {
    e.preventDefault(); setOcupado(true); setError(null);
    try { await api.post(`/coberturas/${item.id}/${tipo}/`, tipo === "liberar" ? { motivo, no_realizada: confirmado } : { decision, importe: importePendiente, ...(parte === "financiador" ? { parte } : {}), motivo, evidencia, clave }); await onGuardado(); }
    catch (err) { setError(err); }
    finally { setOcupado(false); }
  }
  return <Modal title={tipo === "liberar" ? "Revisar reserva antigua o no realizada" : "Resolver saldo administrativo"} onClose={ocupado ? undefined : onClose} width={620}><form className="space-y-4" onSubmit={guardar}>{error && <ErrorPortal error={error} />}<p className="font-semibold">{item.prestacion_nombre || item.evaluacion?.nombre_prestacion} · Caso {item.caso}</p>{tipo === "liberar" ? <Checkbox label="Verifiqué que esta prestación no se realizó" checked={confirmado} onChange={(e) => setConfirmado(e.target.checked)} disabled={ocupado} /> : <><p className="text-sm text-texto-debil">{parte === "financiador" ? "Importe del financiador pendiente de autorización" : "Saldo completo del paciente"}: {importeARS(importePendiente)}. La decisión queda registrada con usuario, fecha y motivo.{parte === "financiador" && " Este importe todavía no constituye una cuenta exigible. La decisión no modifica el copago ni aprueba la autorización."}</p><Field label="Decisión"><Select required value={decision} onChange={(e) => { setDecision(e.target.value); setClave(crypto.randomUUID()); }} disabled={ocupado}><option value="">Seleccioná una decisión</option><option value="asumir">El hospital asume el saldo</option><option value="rechazar">El hospital rechaza asumirlo: continúa pendiente</option><option value="paciente">El paciente acepta pagar el saldo</option><option value="financiador">El financiador acepta pagar el saldo</option></Select></Field>{acuerdo && <Field label="Evidencia del acuerdo expreso" ayuda="Registrá la referencia del acuerdo documentado para esta prestación e importe."><Textarea value={evidencia} onChange={(e) => { setEvidencia(e.target.value); setClave(crypto.randomUUID()); }} required disabled={ocupado} /></Field>}</>}<Field label="Motivo" ayuda="Rechazar la asunción conserva el saldo pendiente. No cancela la atención ni registra dinero recibido."><Textarea value={motivo} onChange={(e) => { setMotivo(e.target.value); setClave(crypto.randomUUID()); }} maxLength={255} required disabled={ocupado} /></Field><div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={onClose} disabled={ocupado}>Cancelar</Button><Button disabled={ocupado || (tipo === "liberar" && !confirmado)}>{ocupado ? "Guardando…" : tipo === "liberar" ? "Confirmar liberación" : "Registrar decisión"}</Button></div></form></Modal>;
}
