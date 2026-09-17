import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "@/api/client";
import { errorFinanciador, filasDe, opcionesFinanciador, rutaFinanciador } from "@/api/financiadores";
import { useAuth } from "@/auth/AuthContext";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Badge, Button, Card, Checkbox, Field, Input, Modal, Select, Spinner } from "@/components/ui";
import { importeARS } from "@/api/finanzas";
import { EstadoVacio } from "@/components/ui/estados";
import { Shell } from "@/components/Shell";
import { fechaHora, plural } from "@/lib/format";
import ImportacionFinanciador from "./ImportacionFinanciador";
import ActividadFinanciador from "./ActividadFinanciador";
import AutorizacionesFinanciador from "./AutorizacionesFinanciador";

const ROLES = { admin: "Administración", operador: "Operación", auditor: "Sólo lectura" };
const SECCIONES = [
  { key: "planes", label: "Planes", icon: "layers" },
  { key: "reglas", label: "Cobertura", icon: "clipboard" },
  { key: "aranceles", label: "Aranceles", icon: "list" },
  { key: "padron", label: "Padrón", icon: "idCard" },
  { key: "consumos", label: "Consumos externos", icon: "fileText" },
  { key: "autorizaciones", label: "Autorizaciones", icon: "clipboard" },
  { key: "actividad", label: "Actividad en hospitales", icon: "activity" },
  { key: "convenios", label: "Convenios", icon: "building" },
  { key: "usuarios", label: "Usuarios", icon: "users" },
  { key: "catalogo", label: "Catálogo común", icon: "cube" },
];
const HOY = () => new Date().toLocaleDateString("en-CA");
const fecha = (valor) => valor ? String(valor).slice(0, 10).split("-").reverse().join("/") : "—";
export const ESTADOS_CONVENIO = { activo: "Activo", propuesto: "Pendiente de aceptación", rechazado: "Rechazado", finalizado: "Finalizado" };
const plataformaDe = (user) => Boolean(user?.is_superuser || Object.values(user?.capacidades_por_institucion || {}).some((caps) => caps.includes("gobierno_plataforma")));

export function ErrorPortal({ error, reintentar }) {
  return <div role="alert" className="rounded-md border border-borde bg-badge-error-bg p-4 text-badge-error-fg"><p>{errorFinanciador(error)}</p>{reintentar && <Button className="mt-3" size="sm" variant="secondary" onClick={reintentar}>Reintentar</Button>}</div>;
}

export default function PortalFinanciadores() {
  const { user } = useAuth();
  const { institucion } = useInstitucion();
  const { seccion = "planes" } = useParams();
  const [parametros, setParametros] = useSearchParams();
  const seleccion = parametros.get("financiador") || "";
  const [crear, setCrear] = useState(false);
  const organizaciones = useQuery({ queryKey: ["financiadores", user.id, "organizaciones"], queryFn: async () => {
    const filas = [];
    for (let page = 1; ; page += 1) {
      const data = await api.get(`/financiadores/?page=${page}`);
      filas.push(...filasDe(data));
      if (!data.next) return filas;
    }
  }, gcTime: 0 });
  const lista = organizaciones.data || [];
  const organizacion = seleccion ? lista.find((item) => String(item.id) === seleccion) : lista[0];
  const plataforma = plataformaDe(user);
  const admin = plataforma || organizacion?.rol === "admin";
  const sufijo = seleccion ? `?financiador=${encodeURIComponent(seleccion)}` : "";
  const items = SECCIONES.filter((item) => (item.key !== "usuarios" || admin) && (item.key !== "catalogo" || plataforma))
    .map((item) => ({ ...item, to: `/financiadores${item.key === "planes" ? "" : `/${item.key}`}${sufijo}` }));
  const actual = items.find((item) => item.key === seccion);
  if (organizacion && !actual) return <Navigate to={`/financiadores${sufijo}`} replace />;
  return <Shell financiador={{
    nombre: organizacion?.nombre || "I-Core Salud",
    rol: plataforma ? "Plataforma" : ROLES[organizacion?.rol] || "Sin organización asignada",
    titulo: actual?.label || "Financiadores",
    items,
    selector: lista.length > 0 && <Field label="Financiador"><Select value={organizacion?.id || ""} onChange={(e) => setParametros({ financiador: e.target.value })}>{!organizacion && <option value="" disabled>Seleccioná un financiador</option>}{lista.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</Select></Field>,
    volver: institucion ? { to: "/inicio", label: "Volver al hospital" } : plataforma ? { to: "/", label: "Directorio" } : null,
  }}>
    <div className="space-y-6 p-lg sm:p-[30px]">
      {plataforma && <div className="flex justify-end"><Button variant="secondary" onClick={() => setCrear(true)}>Nuevo financiador</Button></div>}
      {organizaciones.isLoading ? <Spinner label="Consultando financiadores…" /> : organizaciones.error ? <ErrorPortal error={organizaciones.error} reintentar={organizaciones.refetch} /> : organizacion ? <EspacioFinanciador key={`${user.id}:${organizacion.id}:${seccion}`} organizacion={organizacion} usuarioId={user.id} plataforma={plataforma} tab={seccion} /> : <Card><EstadoVacio titulo={seleccion ? "No tenés acceso al financiador seleccionado" : "Todavía no tenés un financiador asignado"} detalle="El administrador de tu organización puede habilitar tu acceso. La plataforma da de alta las nuevas organizaciones." /></Card>}
      {crear && <FormularioPortal titulo="Nuevo financiador" campos={[{ name: "nombre", label: "Nombre", required: true }, { name: "tipo", label: "Tipo", options: [{ id: "obra_social", nombre: "Obra social" }, { id: "mutual", nombre: "Mutual" }, { id: "otro", nombre: "Otro financiador" }], required: true }]} guardar={(body) => api.post("/financiadores/", body)} onClose={() => setCrear(false)} onGuardado={async () => { await organizaciones.refetch(); setCrear(false); }} />}
    </div>
  </Shell>;
}

function EspacioFinanciador({ organizacion, usuarioId, plataforma, tab }) {
  const [modal, setModal] = useState(null);
  const [mensaje, setMensaje] = useState("");
  const [activacion, setActivacion] = useState("");
  const qc = useQueryClient();
  const admin = plataforma || organizacion.rol === "admin";
  const operador = admin || organizacion.rol === "operador";
  const scope = ["financiadores", usuarioId, organizacion.id];
  const planes = useQuery({ queryKey: [...scope, "opciones-planes"], queryFn: () => opcionesFinanciador(organizacion.id, "planes"), gcTime: 0 });
  const catalogo = useQuery({ queryKey: [...scope, "catalogo"], queryFn: () => opcionesFinanciador(organizacion.id, "catalogo"), gcTime: 0 });
  const resumen = useQuery({ queryKey: [...scope, "resumen"], queryFn: () => api.get(rutaFinanciador(organizacion.id, "resumen")), gcTime: 0 });
  const puedeCrear = !["actividad", "aranceles", "autorizaciones"].includes(tab) && (["padron", "consumos"].includes(tab) ? operador : admin);
  const titulos = { planes: "Nuevo plan", reglas: "Nueva regla de cobertura", padron: "Registrar afiliación", consumos: "Registrar consumo externo", convenios: "Proponer convenio", usuarios: "Dar acceso", catalogo: "Nueva prestación común" };
  async function actualizado(texto, resultado) {
    await qc.invalidateQueries({ queryKey: scope });
    if (resultado?.activacion) setActivacion(resultado.activacion);
    setMensaje(texto);
    setModal(null);
  }
  const errorOpciones = planes.error || catalogo.error;
  return <>
    <Card className="border-l-4 border-l-accent p-4 sm:p-5"><h3 className="font-semibold">Cobertura compartida entre hospitales</h3><p className="mt-1 text-sm text-texto-debil">El cupo de cada afiliado se comparte entre los hospitales de I-Core Salud. Los consumos externos actualizan el saldo disponible; no generan un cobro hospitalario. El hospital carga sus aranceles.</p>{resumen.data?.discrepancias > 0 && <p className="mt-3 font-semibold text-badge-amber-fg">{resumen.data.discrepancias} discrepancias requieren revisión. Las decisiones ya registradas se conservan.</p>}{resumen.error && <p role="status" className="mt-2 text-sm text-texto-debil">No se pudo consultar el resumen. <button className="text-accent underline" onClick={() => resumen.refetch()}>Reintentar</button></p>}</Card>
    {mensaje && <div role="status" className="rounded-md bg-badge-green-bg p-3 text-badge-green-fg">{mensaje}</div>}
    {activacion && <EnlaceActivacion ruta={activacion} onClose={() => setActivacion("")} />}
    <section aria-label={SECCIONES.find((item) => item.key === tab)?.label}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3"><p className="max-w-[48rem] text-sm text-texto-debil">{DESCRIPCIONES[tab]}</p>{puedeCrear && <div className="flex flex-wrap gap-2">{["padron", "consumos"].includes(tab) && <Button variant="secondary" onClick={() => setModal("importar")}>Importar Excel</Button>}<Button onClick={() => setModal("crear")}>{titulos[tab]}</Button></div>}</div>
      {errorOpciones && <ErrorPortal error={errorOpciones} reintentar={() => { planes.refetch(); catalogo.refetch(); }} />}
      {tab === "autorizaciones" ? <AutorizacionesFinanciador organizacion={organizacion} scope={scope} /> : tab === "actividad" ? <ActividadFinanciador organizacion={organizacion} scope={scope} /> : <ListaPortal key={tab} recurso={tab} organizacion={organizacion} scope={scope} admin={admin} operador={operador} planes={planes.data || []} catalogo={catalogo.data || []} actualizado={actualizado} />}
    </section>
    {modal === "crear" && <CrearRegistro recurso={tab} organizacion={organizacion} scope={scope} planes={planes} catalogo={catalogo} titulo={titulos[tab]} onClose={() => setModal(null)} onGuardado={async (resultado) => { if (resultado?.activacion) setActivacion(resultado.activacion); await actualizado("Registro guardado."); }} />}
    {modal === "importar" && <ImportacionFinanciador organizacion={organizacion} tipo={tab} scope={scope} onClose={() => setModal(null)} onAplicado={() => qc.invalidateQueries({ queryKey: scope })} />}
  </>;
}

const DESCRIPCIONES = {
  autorizaciones: "Solicitudes enviadas por los hospitales. Resolver requiere un permiso explícito; aprobar habilita una prestación sin registrarla como realizada ni aceptar un copago.",
  planes: "Administrá los planes que asignás a tus afiliados. Cada plan conserva su código para las cargas masivas. Desactivar un plan impide nuevas asignaciones y conserva las existentes.",
  reglas: "Indicá el porcentaje cubierto y, cuando corresponda, el cupo mensual o anual. Las nuevas vigencias conservan el historial anterior.",
  aranceles: "Aranceles vigentes al consultar, cargados por los hospitales con convenio activo. Se aplica el arancel general salvo una excepción acordada. La cobertura y el copago dependen del plan, el cupo y la prestación, y se confirman antes de realizarla.",
  padron: "Altas y actualizaciones de afiliados. Finalizar o reactivar una afiliación requiere una acción explícita con motivo. Una importación nunca da de baja a quienes no aparecen en el archivo.",
  consumos: "Prestaciones recibidas fuera de I-Core Salud. Se descuentan del cupo del mes o año en que ocurrieron, aunque se registren después.",
  actividad: "Reservas y prestaciones de tus afiliados registradas por hospitales de I-Core Salud. Sin relación vigente, sólo se muestran operaciones históricas pendientes de resolución. Las discrepancias conservan las decisiones previas y requieren revisión administrativa.",
  convenios: "Los convenios habilitan la relación con cada hospital. La contraparte debe aceptar la propuesta.",
  usuarios: "Cada acceso pertenece a esta organización. El rol determina qué puede consultar o modificar la persona.",
  catalogo: "Catálogo compartido por todos los financiadores y hospitales. La plataforma administra su identidad; cada hospital conserva sus aranceles.",
};

function EnlaceActivacion({ ruta, onClose }) {
  const [copiado, setCopiado] = useState(false);
  const [error, setError] = useState(false);
  const enlace = new URL(ruta, window.location.origin).href;
  async function copiar() {
    try { await navigator.clipboard.writeText(enlace); setCopiado(true); setError(false); }
    catch { setError(true); }
  }
  return <Card className="space-y-3 p-4"><h3 className="font-semibold">Activación del nuevo usuario</h3><p className="text-sm text-texto-debil">Compartí este enlace de un solo uso con la persona para que cree su contraseña.</p><Field label="Enlace de activación"><Input readOnly value={enlace} onFocus={(e) => e.target.select()} /></Field>{error && <p role="alert" className="text-sm text-texto-debil">No se pudo copiar automáticamente. Seleccioná el enlace y copialo.</p>}<div className="flex gap-2"><Button size="sm" variant="secondary" onClick={copiar}>{copiado ? "Enlace copiado" : "Copiar enlace"}</Button><Button size="sm" variant="ghost" onClick={onClose}>Cerrar</Button></div></Card>;
}

function ListaPortal({ recurso, organizacion, scope, admin, operador, planes, catalogo, actualizado }) {
  const [page, setPage] = useState(1);
  const [busqueda, setBusqueda] = useState("");
  const [buscar, setBuscar] = useState("");
  const [error, setError] = useState(null);
  const [aceptando, setAceptando] = useState(null);
  const [correccion, setCorreccion] = useState(null);
  const [identidad, setIdentidad] = useState(null);
  const [usuario, setUsuario] = useState(null);
  const [vigencia, setVigencia] = useState(null);
  const consulta = useQuery({ queryKey: [...scope, recurso, page, buscar], queryFn: () => api.get(`${rutaFinanciador(organizacion.id, recurso)}?${new URLSearchParams({ page, search: buscar })}`), gcTime: 0 });
  const filas = filasDe(consulta.data);
  const columnas = columnasDe(recurso, planes, catalogo);
  if (recurso === "consumos" && operador) columnas.push({ key: "corregir", label: "Correcciones", render: (r) => r.corrige ? `Corrige consumo ${r.corrige}` : <Button size="sm" variant="ghost" onClick={() => setCorreccion(r)}>Corregir cantidad</Button> });
  if (recurso === "padron" && operador) columnas.push({ key: "identidad", label: "Identificación", render: (r) => <Button size="sm" variant="ghost" onClick={() => setIdentidad(r)}>Corregir identidad</Button> });
  if (recurso === "usuarios" && admin) columnas.push({ key: "acceso", label: "Acceso", render: (r) => <Button size="sm" variant="ghost" onClick={() => setUsuario(r)}>Cambiar acceso</Button> });
  if (recurso === "planes" && admin) columnas.push({ key: "acciones", label: "Administración", render: (r) => <Button size="sm" variant="ghost" onClick={() => setVigencia({ accion: "editar-plan", fila: r })}>Editar plan</Button> });
  if (recurso === "padron" && operador) columnas.push({ key: "vigencia", label: "Vigencia", render: (r) => <Button size="sm" variant="ghost" onClick={() => setVigencia({ accion: r.finalizado_en ? "reactivar-afiliacion" : "finalizar-afiliacion", fila: r })}>{r.finalizado_en ? "Reactivar afiliación" : "Finalizar afiliación"}</Button> });
  if (recurso === "convenios" && admin) columnas.push({ key: "acciones", label: "Acciones", render: (r) => <div className="flex flex-wrap gap-2">{r.estado === "propuesto" && r.propuesto_por === "hospital" && <><Button size="sm" variant="secondary" disabled={aceptando != null} onClick={() => aceptar(r)}>{aceptando === r.id ? "Aceptando…" : "Aceptar convenio"}</Button><Button size="sm" variant="ghost" onClick={() => setVigencia({ accion: "rechazar-convenio", fila: r })}>Rechazar propuesta</Button></>}{r.estado === "activo" && <><Button size="sm" variant="ghost" onClick={() => setVigencia({ accion: "plazo-autorizacion", fila: r })}>Plazo de autorización</Button><Button size="sm" variant="ghost" onClick={() => setVigencia({ accion: "cerrar-convenio", fila: r })}>Cerrar convenio</Button></>}{["rechazado", "finalizado"].includes(r.estado) && "—"}</div> });
  async function aceptar(convenio) {
    setError(null); setAceptando(convenio.id);
    try { await api.post(rutaFinanciador(organizacion.id, "aceptar-convenio"), { convenio: convenio.id }); await actualizado("Convenio aceptado."); }
    catch (e) { setError(e); }
    finally { setAceptando(null); }
  }
  return <><Card className="overflow-hidden">
    {["padron", "consumos", "aranceles"].includes(recurso) && <form className="flex flex-wrap items-end gap-2 border-b border-division p-4" onSubmit={(e) => { e.preventDefault(); setPage(1); setBuscar(busqueda.trim()); }}><div className="min-w-0 flex-1"><Field label={recurso === "padron" ? "Buscar por afiliado, documento o nombre" : recurso === "aranceles" ? "Buscar por hospital o prestación" : "Buscar consumo"}><Input value={busqueda} onChange={(e) => setBusqueda(e.target.value)} /></Field></div><Button variant="secondary" type="submit">Buscar</Button></form>}
    {error && <div className="p-4"><ErrorPortal error={error} /></div>}
    {consulta.isLoading ? <Spinner label="Cargando registros…" /> : consulta.error ? <div className="p-4"><ErrorPortal error={consulta.error} reintentar={consulta.refetch} /></div> : filas.length === 0 ? <EstadoVacio titulo={buscar ? "No hay resultados para esta búsqueda" : "Todavía no hay registros"} detalle={recurso === "aranceles" ? (buscar ? "Probá con otro hospital o prestación." : "Se mostrarán las prestaciones vinculadas de los hospitales con convenio activo.") : buscar ? "Probá con otro documento, número o nombre." : "Los registros de esta sección aparecerán acá."} /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b border-division bg-superficie-2 text-texto-debil"><tr>{columnas.map((col) => <th key={col.key} scope="col" className="whitespace-nowrap px-4 py-3 font-semibold">{col.label}</th>)}</tr></thead><tbody>{filas.map((fila) => <tr key={recurso === "aranceles" ? `${fila.convenio}:${fila.id}` : fila.id} className="border-b border-division last:border-0">{columnas.map((col) => <td key={col.key} className="px-4 py-3 align-top">{col.render ? col.render(fila) : fila[col.key] ?? "—"}</td>)}</tr>)}</tbody></table></div>}
    {!consulta.error && !consulta.isLoading && <div className="flex flex-wrap items-center justify-between gap-3 border-t border-division px-4 py-3"><span className="text-sm text-texto-debil">{plural(consulta.data?.count ?? filas.length, "registro", "registros")} · Página {page}</span><div className="flex gap-2"><Button size="sm" variant="ghost" disabled={page === 1 || consulta.isFetching} onClick={() => setPage((p) => p - 1)}>Anterior</Button><Button size="sm" variant="ghost" disabled={!consulta.data?.next || consulta.isFetching} onClick={() => setPage((p) => p + 1)}>Siguiente</Button></div></div>}
  </Card>{correccion && <FormularioPortal titulo="Corregir consumo externo" descripcion={`La cantidad correcta reemplaza el efecto del consumo ${correccion.id}. El registro original y su motivo se conservan. Cero anula su cantidad consumida.`} campos={[{ name: "cantidad", label: "Cantidad correcta", type: "number", min: 0, max: 100000, step: 1, numeric: true, required: true }, { name: "motivo", label: "Motivo de corrección", maxLength: 255, required: true }]} guardar={(body) => api.post(rutaFinanciador(organizacion.id, "corregir-consumo"), { consumo: correccion.id, ...body })} onClose={() => setCorreccion(null)} onGuardado={async () => { setCorreccion(null); await actualizado("Corrección registrada. Se conservó el consumo original."); }} />}
  {identidad && <FormularioPortal titulo="Corregir identidad del afiliado" descripcion="Esta corrección conserva el afiliado, su consumo y sus vínculos. Usala para corregir un identificador cargado por error." campos={[{ name: "numero", label: "Número de afiliado correcto", default: identidad.numero, maxLength: 80, required: true }, { name: "documento", label: "Documento correcto", default: identidad.documento, maxLength: 80, required: true }, { name: "motivo", label: "Motivo de corrección", maxLength: 255, required: true }]} guardar={(body) => api.post(rutaFinanciador(organizacion.id, "corregir-identidad"), { afiliado: identidad.id, ...body })} onClose={() => setIdentidad(null)} onGuardado={async () => { setIdentidad(null); await actualizado("Identidad corregida. Se conservó el consumo del afiliado."); }} />}
  {usuario && <FormularioPortal titulo="Cambiar acceso al financiador" descripcion="El cambio se aplica sólo a esta organización. Se conserva la contraseña del usuario." campos={[{ name: "email", label: "Correo electrónico", default: usuario.email, readOnly: true, required: true }, { name: "nombre", label: "Nombre y apellido", default: usuario.nombre || "", required: true }, { name: "rol", label: "Rol", default: usuario.rol, options: Object.entries(ROLES).map(([id, nombre]) => ({ id, nombre })), required: true }, { name: "activo", boolean: true, default: usuario.activo !== false, render: (value, onChange) => <Checkbox label="Acceso activo a este financiador" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} /> }, campoPermisoAutorizaciones(usuario.resuelve_autorizaciones)]} guardar={(body) => api.post(rutaFinanciador(organizacion.id, "usuarios"), body)} onClose={() => setUsuario(null)} onGuardado={async (resultado) => { setUsuario(null); await actualizado("Acceso actualizado.", resultado); }} />}
  {vigencia && <EditarVigencia {...vigencia} planes={planes} guardar={(body) => api.post(rutaFinanciador(organizacion.id, vigencia.accion), body)} onClose={() => setVigencia(null)} onGuardado={async () => { setVigencia(null); await actualizado("Vigencia actualizada. Se conservaron los registros anteriores."); }} />}</>;
}

export function EditarVigencia({ accion, fila, planes = [], guardar, onClose, onGuardado }) {
  const activos = planes.filter((plan) => plan.activo !== false);
  const motivo = { name: "motivo", label: "Motivo", maxLength: 255, required: true };
  const configuracion = {
    "plazo-autorizacion": { titulo: "Plazo de respuesta a autorizaciones", descripcion: "Se aplica a nuevas solicitudes de este convenio. Las solicitudes existentes conservan su vencimiento; dejarlo vacío no genera vencimientos automáticos.", campos: [{ name: "plazo_autorizacion_horas", label: "Plazo de respuesta (horas)", default: fila.plazo_autorizacion_horas ?? "", type: "number", numeric: true, min: 1, max: 8760, step: 1 }, motivo], id: { convenio: fila.id }, confirmacion: "Guardar plazo" },
    "editar-plan": { titulo: `Editar plan ${fila.codigo}`, descripcion: "El código se conserva. Un plan inactivo no puede asignarse a nuevas afiliaciones ni casos; las asignaciones existentes se mantienen.", campos: [{ name: "nombre", label: "Nombre del plan", default: fila.nombre, maxLength: 160, required: true }, { name: "activo", boolean: true, default: fila.activo !== false, render: (value, onChange) => <Checkbox label="Plan activo para nuevas asignaciones" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} /> }, motivo], id: { plan: fila.id }, confirmacion: "Guardar plan" },
    "finalizar-afiliacion": { titulo: "Finalizar afiliación", descripcion: `${fila.numero} · ${fila.nombre}. La finalización rige desde ahora y deja de habilitar nuevas coberturas. Se conservan identidad, cupos consumidos, reservas y cargos registrados. No genera deuda automática al paciente.`, campos: [motivo], id: { afiliado: fila.id }, confirmacion: "Confirmar finalización" },
    "reactivar-afiliacion": { titulo: "Reactivar afiliación", descripcion: `${fila.numero} · ${fila.nombre}. La afiliación volverá a estar vigente desde hoy. Se conservan la identidad y los consumos anteriores del período; el cupo no se reinicia. Elegí un plan activo o continuá sin plan.`, campos: [{ name: "plan", label: "Plan", options: activos, default: activos.some((p) => p.id === fila.plan) ? fila.plan : "", numeric: true, empty: "Sin plan" }, motivo], id: { afiliado: fila.id }, confirmacion: "Confirmar reactivación" },
    "cerrar-convenio": { titulo: "Cerrar convenio", descripcion: `${fila.institucion_nombre || fila.financiador_nombre || "Convenio"}. El cierre rige desde ahora: las nuevas evaluaciones quedan sin cobertura por este convenio. Se conservan reservas y cargos anteriores. No genera deuda automática al paciente. Se puede proponer un nuevo convenio posteriormente.`, campos: [motivo], id: { convenio: fila.id }, confirmacion: "Confirmar cierre" },
    "rechazar-convenio": { titulo: "Rechazar propuesta de convenio", descripcion: `${fila.institucion_nombre || fila.financiador_nombre || "Convenio"}. La propuesta no habilitará cobertura. Quedará registrada con el motivo del rechazo y se podrá proponer otro convenio.`, campos: [motivo], id: { convenio: fila.id }, confirmacion: "Confirmar rechazo" },
  }[accion];
  return <FormularioPortal {...configuracion} guardar={(body) => guardar({ ...configuracion.id, ...body })} onClose={onClose} onGuardado={onGuardado} />;
}

function campoPermisoAutorizaciones(valor = false) {
  return { name: "resuelve_autorizaciones", boolean: true, default: Boolean(valor), render: (checked, onChange) => <div className="space-y-2"><Checkbox label="Permitir resolver autorizaciones de este financiador" checked={Boolean(checked)} onChange={(e) => onChange(e.target.checked)} /><p className="text-sm text-texto-debil">Concesión explícita para observar, aprobar o rechazar solicitudes. El rol de lectura por sí solo no concede este permiso.</p></div> };
}

function columnasDe(recurso, planes, catalogo) {
  const nombrePlan = (id) => planes.find((p) => p.id === id)?.nombre || (id ? `Plan ${id}` : "Todos los planes");
  const nombrePrestacion = (id) => catalogo.find((p) => p.id === id)?.nombre || (id ? `Prestación ${id}` : "Todas");
  const codigo = { key: "codigo", label: "Código" };
  const nombre = { key: "nombre", label: "Nombre" };
  return {
    planes: [codigo, nombre, { key: "activo", label: "Estado", render: (r) => <Badge tone={r.activo === false ? "gray" : "green"}>{r.activo === false ? "Inactivo" : "Activo"}</Badge> }],
    aranceles: [
      { key: "hospital", label: "Hospital" }, codigo, { key: "prestacion", label: "Prestación" },
      { key: "arancel_general", label: "Arancel general", render: (r) => r.arancel_general == null ? "Sin definir" : importeARS(r.arancel_general) },
      { key: "arancel", label: "Arancel aplicable", render: (r) => r.estado === "sin_cobro" ? "Sin cobro" : importeARS(r.arancel) },
      { key: "origen_arancel", label: "Origen", render: (r) => r.origen_arancel === "acordado_financiador" ? "Acordado con el financiador" : r.retorno_arancel_general ? "General del hospital · excepción finalizada" : "General del hospital" },
      { key: "estado", label: "Estado", render: (r) => <Badge tone={r.estado === "vigente" ? "green" : r.estado === "sin_cobro" ? "gray" : "amber"}>{({ vigente: "Vigente", sin_cobro: "Sin cobro", arancel_pendiente: "Arancel pendiente", politica_pendiente: "Política de cobro pendiente" })[r.estado] || r.estado}</Badge> },
      { key: "vigente_desde", label: "Vigente desde", render: (r) => fecha(r.vigente_desde) },
      { key: "fecha_consulta", label: "Consultado el", render: (r) => fecha(r.fecha_consulta) },
    ],
    catalogo: [codigo, nombre, { key: "categoria", label: "Categoría" }],
    reglas: [{ key: "requiere_autorizacion", label: "Autorización previa", render: (r) => r.requiere_autorizacion ? "Requerida" : "No requerida" }, { key: "plan", label: "Plan", render: (r) => nombrePlan(r.plan) }, { key: "prestacion", label: "Prestación / categoría", render: (r) => r.prestacion ? nombrePrestacion(r.prestacion) : r.categoria || "Cobertura general" }, { key: "porcentaje", label: "Cobertura", render: (r) => `${Number(r.porcentaje).toLocaleString("es-AR")}%` }, { key: "cupo", label: "Cupo", render: (r) => r.cupo == null ? "Sin cupo" : `${r.cupo} por ${r.periodo === "mes" ? "mes" : "año"} calendario` }, { key: "vigente_desde", label: "Desde", render: (r) => fecha(r.vigente_desde) }],
    padron: [{ key: "numero", label: "N.º de afiliado" }, { key: "documento", label: "Documento" }, nombre, { key: "plan", label: "Plan", render: (r) => r.plan_nombre || (r.plan ? nombrePlan(r.plan) : "Sin plan") }, { key: "desde", label: "Desde", render: (r) => fecha(r.desde) }, { key: "vigente", label: "Estado", render: (r) => <><Badge tone={r.finalizado_en ? "gray" : r.vigente === false ? "amber" : "green"}>{r.finalizado_en ? "Finalizada" : r.vigente === false ? "Aún no vigente" : "Vigente"}</Badge>{r.finalizado_en && <p className="mt-1 text-xs text-texto-debil">Desde {fechaHora(r.finalizado_en)} · {r.motivo_finalizacion}</p>}</> }],
    consumos: [{ key: "afiliado", label: "Afiliado", render: (r) => [r.afiliado_numero, r.afiliado_documento, r.afiliado_nombre].filter(Boolean).join(" · ") || r.numero || `Afiliado ${r.afiliado}` }, { key: "prestacion", label: "Prestación", render: (r) => nombrePrestacion(r.prestacion) }, { key: "fecha", label: "Fecha", render: (r) => fecha(r.fecha) }, { key: "cantidad", label: "Cantidad" }, { key: "referencia", label: "Referencia" }, { key: "discrepancia", label: "Revisión", render: (r) => r.discrepancia ? <Badge tone="amber">Discrepancia</Badge> : "—" }],
    convenios: [{ key: "institucion_nombre", label: "Hospital" }, { key: "plazo_autorizacion_horas", label: "Plazo de autorización", render: (r) => r.plazo_autorizacion_horas == null ? "Sin vencimiento automático" : `${r.plazo_autorizacion_horas} horas` }, { key: "estado", label: "Estado", render: (r) => <Badge tone={r.estado === "activo" ? "green" : r.estado === "propuesto" ? "amber" : "gray"}>{ESTADOS_CONVENIO[r.estado] || r.estado}</Badge> }, { key: "propuesto_por", label: "Propuesto por", render: (r) => ({ hospital: "Hospital", financiador: "Financiador", plataforma: "Plataforma" })[r.propuesto_por] || r.propuesto_por }, { key: "aceptado_en", label: "Aceptado el", render: (r) => fechaHora(r.aceptado_en) }, { key: "cerrado_en", label: "Cierre / rechazo", render: (r) => r.cerrado_en ? <>{fechaHora(r.cerrado_en)}<p className="mt-1 text-xs text-texto-debil">{r.motivo_cierre}</p></> : "—" }],
    usuarios: [{ key: "resuelve_autorizaciones", label: "Resolver autorizaciones", render: (r) => r.resuelve_autorizaciones ? "Permiso concedido" : "Sin permiso" }, { key: "email", label: "Correo electrónico" }, nombre, { key: "rol", label: "Rol", render: (r) => ROLES[r.rol] || r.rol }, { key: "activo", label: "Estado", render: (r) => <Badge tone={r.activo === false ? "gray" : "green"}>{r.activo === false ? "Inactivo" : "Activo"}</Badge> }],
  }[recurso];
}

function CrearRegistro({ recurso, organizacion, scope, planes, catalogo, titulo, onClose, onGuardado }) {
  const hospitales = useQuery({ queryKey: [...scope, "instituciones"], queryFn: () => opcionesFinanciador(organizacion.id, "instituciones"), enabled: recurso === "convenios", gcTime: 0 });
  const necesitaPlanes = ["padron", "reglas"].includes(recurso);
  const necesitaCatalogo = ["consumos", "reglas"].includes(recurso);
  const error = (necesitaPlanes && planes.error) || (necesitaCatalogo && catalogo.error) || (recurso === "convenios" && hospitales.error);
  const cargando = (necesitaPlanes && planes.isLoading) || (necesitaCatalogo && catalogo.isLoading) || (recurso === "convenios" && hospitales.isLoading);
  if (error || cargando) return <Modal title={titulo} onClose={onClose}>{error ? <ErrorPortal error={error} reintentar={() => { planes.refetch(); catalogo.refetch(); if (recurso === "convenios") hospitales.refetch(); }} /> : <Spinner label="Cargando opciones…" />}</Modal>;
  const p = (planes.data || []).filter((plan) => recurso !== "padron" || plan.activo !== false).map((plan) => ({ ...plan, nombre: plan.activo === false ? `${plan.nombre} (inactivo)` : plan.nombre }));
  const prestaciones = (catalogo.data || []).map((item) => ({ ...item, nombre: `${item.codigo} · ${item.nombre}` }));
  const campos = {
    catalogo: [{ name: "codigo", label: "Código común", maxLength: 60, required: true }, { name: "nombre", label: "Nombre de la prestación", maxLength: 160, required: true }, { name: "categoria", label: "Categoría", maxLength: 80, required: true }],
    planes: [{ name: "codigo", label: "Código del plan", required: true, maxLength: 50 }, { name: "nombre", label: "Nombre del plan", required: true, maxLength: 160 }],
    reglas: [{ name: "requiere_autorizacion", boolean: true, default: false, render: (value, onChange) => <Checkbox label="Requiere autorización previa del financiador" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} /> }, { name: "plan", label: "Plan", options: p, empty: "Todos los planes", numeric: true }, { name: "prestacion", label: "Prestación", options: prestaciones, empty: "Elegir una categoría en el siguiente campo", numeric: true }, { name: "categoria", label: "Categoría (si no elegís prestación)", options: [...new Set(prestaciones.map((item) => item.categoria).filter(Boolean))].map((value) => ({ id: value, nombre: value })), empty: "Sin categoría" }, { name: "porcentaje", label: "Porcentaje cubierto", type: "number", min: 0, max: 100, step: "0.01", required: true }, { name: "cupo", label: "Cupo por prestación (opcional)", type: "number", min: 1, step: 1, numeric: true, hint: "Dejalo vacío si no hay límite de cantidad. Los cupos se definen para una prestación concreta." }, { name: "periodo", label: "Período calendario", options: [{ id: "mes", nombre: "Mes calendario" }, { id: "anio", nombre: "Año calendario" }], default: "anio", required: true }, { name: "vigente_desde", label: "Vigente desde", type: "date", min: HOY(), default: HOY(), required: true }],
    padron: [{ name: "numero", label: "Número de afiliado", required: true, hint: "Conservá los ceros iniciales." }, { name: "documento", label: "Documento", required: true }, { name: "nombre", label: "Nombre y apellido", required: true }, { name: "plan", label: "Plan", options: p, numeric: true, empty: "Sin plan" }, { name: "desde", label: "Afiliación vigente desde", type: "date", default: HOY(), required: true }],
    consumos: [{ name: "afiliado", numeric: true, render: (value, onChange) => <BuscarAfiliado scope={scope} organizacion={organizacion} value={value} onChange={onChange} /> }, { name: "prestacion", label: "Prestación", options: prestaciones, numeric: true, required: true }, { name: "fecha", label: "Fecha de la prestación", type: "date", max: HOY(), required: true }, { name: "cantidad", label: "Cantidad", type: "number", min: 1, step: 1, numeric: true, required: true }, { name: "referencia", label: "Referencia externa (opcional)", hint: "Usá la misma referencia para reconocer un registro ya enviado." }, { name: "motivo_duplicado", maxLength: 255, label: "Motivo para registrar un posible duplicado (opcional)", hint: "Completalo sólo si verificaste que otro registro similar corresponde a una prestación distinta." }],
    convenios: [{ name: "institucion", label: "Hospital", options: hospitales.data || [], numeric: true, required: true }],
    usuarios: [campoPermisoAutorizaciones(), { name: "email", label: "Correo electrónico", type: "email", required: true }, { name: "nombre", label: "Nombre y apellido", required: true }, { name: "rol", label: "Rol", options: [{ id: "admin", nombre: "Administración: configura y gestiona accesos" }, { id: "operador", nombre: "Operación: padrón y consumos" }, { id: "auditor", nombre: "Auditoría: sólo lectura" }], required: true }],
  }[recurso];
  return <FormularioPortal titulo={titulo} campos={campos} onClose={onClose} onGuardado={onGuardado} descripcion={recurso === "reglas" ? "El porcentaje se aplica sobre el arancel del hospital, o sobre su excepción acordada. Agregar una vigencia no modifica decisiones registradas." : recurso === "usuarios" ? "El acceso se limita a este financiador. La credencial de una persona que ya usa I-Core Salud se conserva." : undefined} guardar={(body) => api.post(rutaFinanciador(organizacion.id, recurso), body)} />;
}

function BuscarAfiliado({ scope, organizacion, value, onChange }) {
  const [texto, setTexto] = useState("");
  const [buscar, setBuscar] = useState("");
  const [seleccionado, setSeleccionado] = useState(null);
  useEffect(() => { const timer = setTimeout(() => setBuscar(texto.trim()), 250); return () => clearTimeout(timer); }, [texto]);
  const consulta = useQuery({ queryKey: [...scope, "buscar-afiliado", buscar], queryFn: () => api.get(`${rutaFinanciador(organizacion.id, "padron")}?${new URLSearchParams({ search: buscar, page: 1 })}`), enabled: buscar.length >= 2, gcTime: 0 });
  const encontrados = filasDe(consulta.data);
  const opciones = seleccionado && !encontrados.some((item) => item.id === seleccionado.id) ? [seleccionado, ...encontrados] : encontrados;
  return <div className="space-y-2"><Field label="Buscar afiliado" hint="Ingresá al menos dos caracteres del documento, número o nombre."><Input value={texto} onChange={(e) => setTexto(e.target.value)} /></Field>{consulta.error && <ErrorPortal error={consulta.error} reintentar={consulta.refetch} />}<Field label="Afiliado"><Select required value={value} onChange={(e) => { onChange(e.target.value); setSeleccionado(opciones.find((item) => String(item.id) === e.target.value)); }}><option value="">{consulta.isFetching ? "Buscando…" : "Seleccioná un afiliado"}</option>{opciones.map((item) => <option key={item.id} value={item.id}>{item.numero} · {item.documento} · {item.nombre}</option>)}</Select></Field>{consulta.data?.next && <p className="text-sm text-texto-debil">Hay más resultados. Precisá la búsqueda para encontrar al afiliado.</p>}{buscar.length >= 2 && !consulta.isFetching && !consulta.error && encontrados.length === 0 && <p className="text-sm text-texto-debil">Sin resultados. Primero registrá al afiliado en el padrón.</p>}</div>;
}

export function FormularioPortal({ titulo, campos, descripcion, guardar, onClose, onGuardado, confirmacion = "Guardar" }) {
  const [datos, setDatos] = useState(() => Object.fromEntries(campos.map((campo) => [campo.name, campo.default ?? ""])));
  const [error, setError] = useState(null);
  const [guardando, setGuardando] = useState(false);
  async function enviar(e) {
    e.preventDefault(); setError(null); setGuardando(true);
    const body = Object.fromEntries(campos.map((campo) => [campo.name, campo.boolean ? Boolean(datos[campo.name]) : campo.numeric ? (datos[campo.name] === "" ? null : Number(datos[campo.name])) : String(datos[campo.name]).trim()]));
    try { const resultado = await guardar(body); await onGuardado(resultado); }
    catch (err) { setError(err); }
    finally { setGuardando(false); }
  }
  return <Modal title={titulo} onClose={guardando ? undefined : onClose} width={620}>
    <form className="space-y-4" onSubmit={enviar}>{descripcion && <p className="text-sm text-texto-debil">{descripcion}</p>}{error && <ErrorPortal error={error} />}<fieldset disabled={guardando} className="space-y-4">{campos.map(({ name, label, hint, options, empty, numeric, boolean, render, default: valorInicial, ...props }) => <div key={name}>{render ? render(datos[name], (value) => setDatos({ ...datos, [name]: value })) : <Field label={label} hint={hint}>{options ? <Select {...props} value={datos[name]} onChange={(e) => setDatos({ ...datos, [name]: e.target.value })}><option value="">{empty || "Seleccioná una opción"}</option>{options.map((op) => <option key={op.id} value={op.id}>{op.nombre}</option>)}</Select> : <Input {...props} value={datos[name]} onChange={(e) => setDatos({ ...datos, [name]: e.target.value })} />}</Field>}</div>)}</fieldset><div className="flex justify-end gap-2 border-t border-division pt-4"><Button type="button" variant="ghost" disabled={guardando} onClick={onClose}>Cancelar</Button><Button type="submit" disabled={guardando}>{guardando ? "Guardando…" : confirmacion}</Button></div></form>
  </Modal>;
}
