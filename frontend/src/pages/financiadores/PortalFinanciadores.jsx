import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "@/api/client";
import { errorFinanciador, filasDe, opcionesFinanciador, rutaFinanciador } from "@/api/financiadores";
import { useAuth } from "@/auth/AuthContext";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Ayuda, Badge, Button, Card, Checkbox, Field, Input, Modal, Select, Spinner } from "@/components/ui";
import { importeARS } from "@/api/finanzas";
import { EstadoVacio } from "@/components/ui/estados";
import { Shell } from "@/components/Shell";
import { fechaHora, plural } from "@/lib/format";
import ImportacionFinanciador from "./ImportacionFinanciador";
import ActividadFinanciador from "./ActividadFinanciador";
import AutorizacionesFinanciador from "./AutorizacionesFinanciador";
import { POR_PAGINA } from "@/api/queries";

const ROLES = { admin: "Administración", operador: "Operación", auditor: "Sólo lectura" };
const SECCIONES = [
  { key: "inicio", label: "Inicio", icon: "home" },
  { key: "planes", label: "Planes", icon: "layers" },
  { key: "reglas", label: "Reglas de cobertura", icon: "clipboard" },
  { key: "aranceles", label: "Aranceles", icon: "list" },
  { key: "padron", label: "Padrón de afiliados", icon: "idCard" },
  { key: "consumos", label: "Consumos externos", icon: "fileText" },
  { key: "autorizaciones", label: "Autorizaciones", icon: "clipboard" },
  { key: "actividad", label: "Actividad en hospitales", icon: "activity" },
  { key: "convenios", label: "Convenios", icon: "building" },
  { key: "usuarios", label: "Usuarios", icon: "users" },
  { key: "catalogo", label: "Catálogo común", icon: "cube" },
];
const HOY = () => new Date().toLocaleDateString("en-CA");
const fecha = (valor) => valor ? String(valor).slice(0, 10).split("-").reverse().join("/") : "—";
const documentoParcial = (valor) => valor ? `•••${String(valor).slice(-3)}` : "Sin DNI";
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
  const organizaciones = useQuery({ queryKey: ["financiadores", user.id, "organizaciones"], queryFn: async () => {
    const filas = [];
    for (let page = 1; ; page += 1) {
      const data = await api.get(`/financiadores/?page=${page}`);
      filas.push(...filasDe(data));
      if (!data.next) return filas;
    }
  }, gcTime: 0 });
  const lista = organizaciones.data || [];
  const plataforma = plataformaDe(user);
  const organizacion = seleccion ? lista.find((item) => String(item.id) === seleccion) : plataforma ? null : lista[0];
  const admin = plataforma || organizacion?.rol === "admin";
  const sufijo = seleccion ? `?financiador=${encodeURIComponent(seleccion)}` : "";
  const items = SECCIONES.filter((item) => (organizacion || item.key === "catalogo" && plataforma) && (item.key !== "usuarios" || admin) && (item.key !== "catalogo" || plataforma))
    .map((item) => ({ ...item, to: `/financiadores${item.key === "planes" ? "" : `/${item.key}`}${sufijo}` }));
  const actual = items.find((item) => item.key === seccion);
  if (plataforma && !seleccion && !organizaciones.isLoading && !organizaciones.error && seccion !== "catalogo") return <Navigate to="/directorio?vista=financiadores" replace />;
  if (organizacion && !actual) return <Navigate to={`/financiadores${sufijo}`} replace />;
  const cuerpo = <div className="space-y-6 p-lg sm:p-[30px] xl:p-[40px]">
    {plataforma && <>
      <div><Link to="/directorio?vista=financiadores" className="text-xs font-semibold text-accent hover:underline">← Volver a financiadores</Link>
        <h2 className="mt-2 text-xl font-bold">{organizacion?.nombre || "Catálogo común"}</h2>
        <p className="mt-1 text-sm text-texto-suave">{actual?.label || "Financiadores"} · Administración de plataforma</p></div>
      <nav aria-label="Secciones del financiador" className="flex flex-wrap gap-2 border-b border-division pb-2">
        {items.map((item) => <Link key={item.key} to={item.to} aria-current={item.key === seccion ? "page" : undefined}
          className={`whitespace-nowrap rounded-md px-3 py-2 text-xs font-semibold ${item.key === seccion ? "bg-accent-50 text-accent" : "text-texto-suave hover:bg-superficie-2"}`}>{item.label}</Link>)}
      </nav>
    </>}
    {organizaciones.isLoading ? <Spinner label="Consultando financiadores…" /> : organizaciones.error ? <ErrorPortal error={organizaciones.error} reintentar={organizaciones.refetch} /> : organizacion ? <EspacioFinanciador key={`${user.id}:${organizacion.id}:${seccion}`} organizacion={organizacion} usuarioId={user.id} plataforma={plataforma} tab={seccion} /> : plataforma && seccion === "catalogo" && !seleccion ? <CatalogoGlobal usuarioId={user.id} /> : <Card><EstadoVacio titulo={seleccion ? "No tenés acceso al financiador seleccionado" : "Todavía no tenés un financiador asignado"} detalle={seleccion && lista.length ? "Elegí un financiador disponible en el directorio." : "El administrador de tu organización puede habilitar tu acceso."} /></Card>}
  </div>;
  if (plataforma) return <Shell plataforma>{cuerpo}</Shell>;
  return <Shell financiador={{
    nombre: organizacion?.nombre || "HEN",
    rol: ROLES[organizacion?.rol] || "Sin organización asignada",
    titulo: actual?.label || "Financiadores",
    items,
    selector: lista.length > 0 && <div className="rounded-md border border-borde bg-superficie-2 px-2.5 py-2 text-xs"><label className="sr-only" htmlFor="selector-financiador">Financiador</label><select id="selector-financiador" className="w-full bg-transparent font-semibold text-texto outline-none" value={organizacion?.id || ""} onChange={(e) => setParametros({ financiador: e.target.value })}>{!organizacion && <option value="" disabled>Seleccioná un financiador</option>}{lista.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}</select><p className="mt-1 text-texto-suave">Financiador · {({ obra_social: "Obra social", mutual: "Mutual", otro: "Organización" })[organizacion?.tipo] || "Organización"}</p></div>,
    volver: institucion ? { to: "/inicio", label: "Volver al hospital" } : null,
  }}>{cuerpo}</Shell>;
}

function CatalogoGlobal({ usuarioId }) {
  const [pagina, setPagina] = useState(1);
  const [crear, setCrear] = useState(false);
  const consulta = useQuery({
    queryKey: ["catalogo-comun", usuarioId, pagina],
    queryFn: () => api.get(`/financiadores/catalogo-comun/?page=${pagina}`),
    gcTime: 0,
  });
  const filas = filasDe(consulta.data);
  const total = consulta.data?.count || 0;
  useEffect(() => {
    if (pagina > 1 && (consulta.error?.status === 404 || consulta.isSuccess && total === 0)) setPagina(1);
  }, [consulta.error, consulta.isSuccess, pagina, total]);
  return <Card className="overflow-hidden">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-division p-4"><p className="text-sm text-texto-debil">Prestaciones compartidas por hospitales y financiadores.</p><Button onClick={() => setCrear(true)}>Nueva prestación común</Button></div>
    {consulta.isLoading ? <Spinner label="Cargando catálogo…" /> : consulta.error ? <div className="p-4"><ErrorPortal error={consulta.error} reintentar={consulta.refetch} /></div> : filas.length === 0 ? <EstadoVacio titulo="El catálogo común todavía está vacío" detalle="Agregá una prestación para que los hospitales puedan vincularla." /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="bg-superficie-2 text-texto-debil"><tr><th className="px-4 py-3" scope="col">Código</th><th className="px-4 py-3" scope="col">Prestación</th><th className="px-4 py-3" scope="col">Categoría</th></tr></thead><tbody>{filas.map((item) => <tr key={item.id} className="border-t border-division"><td className="px-4 py-3 font-mono">{item.codigo}</td><td className="px-4 py-3">{item.nombre}</td><td className="px-4 py-3">{item.categoria}</td></tr>)}</tbody></table></div>}
    {!consulta.error && !consulta.isLoading && <div className="flex items-center justify-between border-t border-division p-3 text-sm"><span>{plural(total, "prestación", "prestaciones")} · {total ? `Página ${pagina}` : "Sin páginas"}</span><div className="flex gap-2"><Button size="sm" variant="ghost" disabled={pagina === 1 || consulta.isFetching} onClick={() => setPagina(pagina - 1)}>Anterior</Button><Button size="sm" variant="ghost" disabled={!consulta.data?.next || consulta.isFetching} onClick={() => setPagina(pagina + 1)}>Siguiente</Button></div></div>}
    {crear && <FormularioPortal titulo="Nueva prestación común" campos={[{ name: "codigo", label: "Código", maxLength: 60, required: true }, { name: "nombre", label: "Prestación", maxLength: 160, required: true }, { name: "categoria", label: "Categoría", maxLength: 80, required: true }]} guardar={(body) => api.post("/financiadores/catalogo-comun/", body)} onClose={() => setCrear(false)} onGuardado={async () => { await consulta.refetch(); setCrear(false); }} />}
  </Card>;
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
  const puedeCrear = tab === "catalogo" ? plataforma : !["inicio", "actividad", "aranceles", "autorizaciones"].includes(tab) && (["padron", "consumos"].includes(tab) ? operador : admin);
  const titulos = { planes: "Nuevo plan", reglas: "Nueva regla de cobertura", padron: "Registrar afiliación", consumos: "Registrar consumo externo", convenios: "Proponer convenio", usuarios: "Invitar usuario", catalogo: "Nueva prestación común" };
  async function actualizado(texto, resultado) {
    await qc.invalidateQueries({ queryKey: scope });
    if (resultado?.activacion) setActivacion(resultado.activacion);
    setMensaje(texto);
    setModal(null);
  }
  const errorOpciones = planes.error || catalogo.error;
  if (tab === "inicio") return <InicioFinanciador organizacion={organizacion} resumen={resumen} plataforma={plataforma} />;
  const titulo = SECCIONES.find((item) => item.key === tab)?.label || "Financiador";
  const tituloVisual = tab === "catalogo" ? "Catálogo de prestaciones" : titulo;
  return <>
    {resumen.data?.discrepancias > 0 && <p role="status" className="rounded-md bg-badge-amber-bg p-3 font-semibold text-badge-amber-fg">{resumen.data.discrepancias} discrepancias requieren revisión. Las decisiones ya registradas se conservan.</p>}
    {resumen.error && <p role="status" className="text-sm text-texto-debil">No se pudo consultar el resumen. <button className="text-accent underline" onClick={() => resumen.refetch()}>Reintentar</button></p>}
    {mensaje && <div role="status" className="rounded-md bg-badge-green-bg p-3 text-badge-green-fg">{mensaje}</div>}
    {activacion && <EnlaceActivacion ruta={activacion} onClose={() => setActivacion("")} />}
    <section aria-label={titulo}>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4"><div><div className="flex items-center gap-2"><h1 className="text-cifra font-bold">{tituloVisual}</h1><Ayuda etiqueta={`Ayuda sobre ${titulo}`}>{DESCRIPCIONES[tab]}</Ayuda></div><p className="mt-1 text-sm text-texto-suave">{RESUMENES_SECCION[tab]}</p></div>{puedeCrear && <div className="flex flex-wrap gap-2">{["padron", "consumos"].includes(tab) && <Button variant="secondary" onClick={() => setModal("importar")}>Importar Excel</Button>}<Button onClick={() => setModal("crear")}>{titulos[tab]}</Button></div>}</div>
      {errorOpciones && <ErrorPortal error={errorOpciones} reintentar={() => { planes.refetch(); catalogo.refetch(); }} />}
      {tab === "autorizaciones" ? <AutorizacionesFinanciador organizacion={organizacion} scope={scope} /> : tab === "actividad" ? <ActividadFinanciador organizacion={organizacion} scope={scope} /> : <ListaPortal key={tab} recurso={tab} organizacion={organizacion} scope={scope} admin={admin} operador={operador} planes={planes.data || []} catalogo={catalogo.data || []} actualizado={actualizado} />}
    </section>
    {modal === "crear" && <CrearRegistro recurso={tab} organizacion={organizacion} scope={scope} planes={planes} catalogo={catalogo} titulo={titulos[tab]} onClose={() => setModal(null)} onGuardado={async (resultado) => { if (resultado?.activacion) setActivacion(resultado.activacion); await actualizado("Registro guardado."); }} />}
    {modal === "importar" && <ImportacionFinanciador organizacion={organizacion} tipo={tab} scope={scope} onClose={() => setModal(null)} onAplicado={() => qc.invalidateQueries({ queryKey: scope })} />}
  </>;
}

function InicioFinanciador({ organizacion, resumen, plataforma }) {
  const sufijo = `?financiador=${organizacion.id}`;
  const accesos = [
    ["Planes", "planes", resumen.data?.planes],
    ["Padrón de afiliados", "padron", resumen.data?.afiliados],
    ["Consumos externos", "consumos", resumen.data?.consumos],
    ["Discrepancias", "actividad", resumen.data?.discrepancias],
  ];
  return <section>
    {!plataforma && <h2 className="text-xl font-bold">{organizacion.nombre}</h2>}
    <p className="text-sm text-texto-suave">Resumen de cobertura y actividad de la organización.</p>
    {resumen.error && <div className="mt-4"><ErrorPortal error={resumen.error} reintentar={resumen.refetch} /></div>}
    <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {accesos.map(([titulo, ruta, valor]) => <Link key={ruta} to={`/financiadores/${ruta}${sufijo}`} className="rounded-lg border border-borde bg-superficie p-4 hover:border-accent-100 hover:shadow-card">
        <h3 className="text-xs text-texto-suave">{titulo}</h3><strong className="mt-2 block text-xxl tabular-nums">{resumen.isLoading ? "…" : valor ?? "—"}</strong><span className="mt-2 block text-xs font-semibold text-accent">Ver sección →</span>
      </Link>)}
    </div>
    {resumen.data?.discrepancias > 0 && <p className="mt-5 rounded-md border border-badge-amber-fg/25 bg-badge-amber-bg p-3 text-sm text-badge-amber-fg" role="status">Hay discrepancias que requieren revisión. Las decisiones registradas se conservan.</p>}
  </section>;
}

const DESCRIPCIONES = {
  autorizaciones: "Solicitudes enviadas por los hospitales. Resolver requiere un permiso explícito; aprobar habilita una prestación sin registrarla como realizada ni aceptar un copago.",
  planes: "Administrá los planes que asignás a tus afiliados. Cada plan conserva su código para las cargas masivas. Desactivar un plan impide nuevas asignaciones y conserva las existentes.",
  reglas: "Indicá el porcentaje cubierto y, cuando corresponda, el cupo mensual o anual. Las nuevas vigencias conservan el historial anterior.",
  aranceles: "Aranceles vigentes al consultar, cargados por los hospitales con convenio activo. Se aplica el arancel general salvo una excepción acordada. La cobertura y el copago dependen del plan, el cupo y la prestación, y se confirman antes de realizarla.",
  padron: "Altas y actualizaciones de afiliados. Finalizar o reactivar una afiliación requiere una acción explícita con motivo. Una importación nunca da de baja a quienes no aparecen en el archivo.",
  consumos: "Prestaciones recibidas fuera de HEN. Se descuentan del cupo del mes o año en que ocurrieron, aunque se registren después.",
  actividad: "Reservas y prestaciones de tus afiliados registradas por hospitales de HEN. Sin relación vigente, sólo se muestran operaciones históricas pendientes de resolución. Las discrepancias conservan las decisiones previas y requieren revisión administrativa.",
  convenios: "Los convenios habilitan la relación con cada hospital. La contraparte debe aceptar la propuesta.",
  usuarios: "Cada acceso pertenece a esta organización. El rol determina qué puede consultar o modificar la persona.",
  catalogo: "Catálogo compartido por todos los financiadores y hospitales. La plataforma administra su identidad; cada hospital conserva sus aranceles.",
};

const RESUMENES_SECCION = {
  planes: "Planes de cobertura disponibles para los afiliados de esta organización.",
  reglas: "Prestaciones cubiertas por cada plan, porcentajes y cupos vigentes.",
  aranceles: "Precios de las prestaciones en hospitales con convenio vigente. El arancel acordado reemplaza al general.",
  padron: "Afiliaciones registradas. Las importaciones incrementales no dan de baja las afiliaciones omitidas.",
  consumos: "Prestaciones recibidas fuera de la red que se descuentan del cupo disponible.",
  autorizaciones: "Solicitudes de los hospitales para prestaciones que requieren autorización previa.",
  actividad: "Reservas, prestaciones realizadas y liberaciones en hospitales de la red.",
  convenios: "Acuerdos con hospitales de la red y su estado actual.",
  usuarios: "Personas que operan en nombre de esta organización.",
  catalogo: "Prestaciones compartidas de la red.",
};

const VACIOS_PORTAL = {
  planes: "Creá un plan para poder asignarlo a los afiliados.",
  reglas: "Definí una regla para indicar qué prestaciones cubre cada plan.",
  padron: "Registrá un afiliado o importá el padrón para comenzar.",
  consumos: "Los consumos externos registrados o importados aparecerán acá.",
  convenios: "Proponé un convenio a un hospital para habilitar la relación.",
  usuarios: "Agregá una persona para darle acceso a este financiador.",
  catalogo: "Agregá una prestación al catálogo común para que los hospitales puedan vincularla.",
};

function EnlaceActivacion({ ruta, onClose }) {
  const [copiado, setCopiado] = useState(false);
  const [error, setError] = useState(false);
  const enlace = new URL(ruta, window.location.origin).href;
  async function copiar() {
    try { await navigator.clipboard.writeText(enlace); setCopiado(true); setError(false); }
    catch { setError(true); }
  }
  return <Card className="space-y-3 p-4"><div className="flex items-center gap-2"><h3 className="font-semibold">Activación del nuevo usuario</h3><Ayuda>Compartí este enlace de un solo uso con la persona para que cree su contraseña.</Ayuda></div><Field label="Enlace de activación"><Input readOnly value={enlace} onFocus={(e) => e.target.select()} /></Field>{error && <p role="alert" className="text-sm text-texto-debil">No se pudo copiar automáticamente. Seleccioná el enlace y copialo.</p>}<div className="flex gap-2"><Button size="sm" variant="secondary" onClick={copiar}>{copiado ? "Enlace copiado" : "Copiar enlace"}</Button><Button size="sm" variant="ghost" onClick={onClose}>Cerrar</Button></div></Card>;
}

function ListaPortal({ recurso, organizacion, scope, admin, operador, planes, catalogo, actualizado }) {
  const [parametros, setParametros] = useSearchParams();
  const planFiltro = ["reglas", "padron"].includes(recurso) ? parametros.get("plan") || "" : "";
  const estadoFiltro = recurso === "padron" ? parametros.get("estado") || "vigentes" : "";
  const convenioFiltro = recurso === "convenios" ? parametros.get("estado") || "activo" : "";
  const [page, setPage] = useState(1);
  const [busqueda, setBusqueda] = useState("");
  const [buscar, setBuscar] = useState("");
  const [error, setError] = useState(null);
  const [aceptando, setAceptando] = useState(null);
  const [correccion, setCorreccion] = useState(null);
  const [identidad, setIdentidad] = useState(null);
  const [usuario, setUsuario] = useState(null);
  const [vigencia, setVigencia] = useState(null);
  const query = new URLSearchParams({ page, search: buscar, page_size: POR_PAGINA });
  if (planFiltro) query.set("plan", planFiltro);
  if (estadoFiltro) query.set("estado", estadoFiltro);
  if (convenioFiltro) query.set("estado", convenioFiltro);
  const consulta = useQuery({ queryKey: [...scope, recurso, query.toString()], queryFn: () => api.get(`${rutaFinanciador(organizacion.id, recurso)}?${query}`), gcTime: 0 });
  const filas = filasDe(consulta.data);
  const total = consulta.data?.count ?? filas.length;
  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA));
  useEffect(() => {
    if (page > 1 && (consulta.error?.status === 404 || consulta.isSuccess && page > paginas)) setPage(consulta.error ? 1 : paginas);
  }, [consulta.error, consulta.isSuccess, page, paginas]);
  useEffect(() => { setPage(1); }, [planFiltro, estadoFiltro, convenioFiltro]);
  const columnas = columnasDe(recurso, planes, catalogo, organizacion.id);
  if (recurso === "consumos" && operador) columnas.push({ key: "corregir", label: "Correcciones", render: (r) => r.corrige ? `Corrige consumo ${r.corrige}` : <Button size="sm" variant="ghost" onClick={() => setCorreccion(r)}>Corregir cantidad</Button> });
  if (recurso === "padron" && operador) columnas.push({ key: "acciones", label: "Acciones", render: (r) => <div className="flex flex-wrap gap-1"><Button size="sm" variant="ghost" onClick={() => setIdentidad(r)}>Corregir identidad</Button><Button size="sm" variant="ghost" onClick={() => setVigencia({ accion: r.finalizado_en ? "reactivar-afiliacion" : "finalizar-afiliacion", fila: r })}>{r.finalizado_en ? "Reactivar" : "Finalizar"}</Button></div> });
  if (recurso === "usuarios" && admin) columnas.push({ key: "acceso", label: "Acceso", render: (r) => <Button size="sm" variant="ghost" onClick={() => setUsuario(r)}>Cambiar acceso</Button> });
  if (recurso === "planes" && admin) columnas.push({ key: "acciones", label: "Administración", render: (r) => <Button size="sm" variant="ghost" onClick={() => setVigencia({ accion: "editar-plan", fila: r })}>Editar plan</Button> });
  if (recurso === "convenios" && admin) columnas.push({ key: "acciones", label: "Acciones", render: (r) => <div className="flex flex-wrap gap-2">{r.estado === "propuesto" && r.propuesto_por === "hospital" && <><Button size="sm" variant="secondary" disabled={aceptando != null} onClick={() => aceptar(r)}>{aceptando === r.id ? "Aceptando…" : "Aceptar convenio"}</Button><Button size="sm" variant="ghost" onClick={() => setVigencia({ accion: "rechazar-convenio", fila: r })}>Rechazar propuesta</Button></>}{r.estado === "activo" && <><Button size="sm" variant="ghost" onClick={() => setVigencia({ accion: "plazo-autorizacion", fila: r })}>Plazo de autorización</Button><Button size="sm" variant="ghost" onClick={() => setVigencia({ accion: "cerrar-convenio", fila: r })}>Cerrar convenio</Button></>}{["rechazado", "finalizado"].includes(r.estado) && "—"}</div> });
  async function aceptar(convenio) {
    setError(null); setAceptando(convenio.id);
    try { await api.post(rutaFinanciador(organizacion.id, "aceptar-convenio"), { convenio: convenio.id }); await actualizado("Convenio aceptado."); }
    catch (e) { setError(e); }
    finally { setAceptando(null); }
  }
  function cambiarFiltro(campo, valor) {
    const nuevos = new URLSearchParams({ financiador: organizacion.id });
    const plan = campo === "plan" ? valor : planFiltro;
    if (plan) nuevos.set("plan", plan);
    if (recurso === "padron") nuevos.set("estado", campo === "estado" ? valor : estadoFiltro);
    if (recurso === "convenios") nuevos.set("estado", valor);
    setParametros(nuevos);
  }
  return <>{recurso === "convenios" && <div aria-label="Estado de convenios" className="mb-4 flex flex-wrap gap-5 border-b border-division">{[["activo", "Vigentes"], ["propuesto", "Propuestos"], ["cerrado", "Cerrados"], ["todos", "Todos"]].map(([valor, etiqueta]) => <button key={valor} type="button" aria-pressed={convenioFiltro === valor} onClick={() => cambiarFiltro("estado", valor)} className={`border-b-2 pb-3 text-sm font-medium ${convenioFiltro === valor ? "border-accent text-accent" : "border-transparent text-texto-suave hover:text-texto"}`}>{etiqueta}</button>)}</div>}
    {["padron", "consumos", "aranceles", "catalogo"].includes(recurso) && <form className="mb-6 flex flex-wrap items-center gap-3" onSubmit={(e) => { e.preventDefault(); setPage(1); setBuscar(busqueda.trim()); }}><div className="min-w-[14rem] flex-1"><Input aria-label={recurso === "padron" ? "Buscar por afiliado, documento o nombre" : recurso === "aranceles" ? "Buscar por hospital o prestación" : recurso === "catalogo" ? "Buscar por nombre o código" : "Buscar consumo"} placeholder={recurso === "padron" ? "Buscar por n.º de afiliado, DNI o nombre" : recurso === "aranceles" ? "Buscar por hospital o prestación" : recurso === "catalogo" ? "Buscar por nombre o código" : "Buscar consumo"} value={busqueda} onChange={(e) => setBusqueda(e.target.value)} /></div>{recurso === "padron" && <><Select className="w-auto min-w-[11rem]" aria-label="Plan" value={planFiltro} onChange={(e) => cambiarFiltro("plan", e.target.value)}><option value="">Plan: todos</option>{planes.map((plan) => <option key={plan.id} value={plan.id}>{plan.nombre}</option>)}</Select><Select className="w-auto min-w-[11rem]" aria-label="Estado" value={estadoFiltro} onChange={(e) => cambiarFiltro("estado", e.target.value)}><option value="vigentes">Estado: vigentes</option><option value="finalizadas">Finalizadas</option><option value="futuras">Aún no vigentes</option><option value="todos">Todos</option></Select></>}<Button variant="secondary" type="submit">Buscar</Button></form>}
    <Card className="overflow-hidden">
    {recurso === "reglas" && <div className="border-b border-division p-4"><Field label="Plan"><Select value={planFiltro} onChange={(e) => cambiarFiltro("plan", e.target.value)}><option value="">Todos los planes</option>{planes.map((plan) => <option key={plan.id} value={plan.id}>{plan.nombre}</option>)}</Select></Field></div>}
    {error && <div className="p-4"><ErrorPortal error={error} /></div>}
    {consulta.isLoading ? <Spinner label="Cargando registros…" /> : consulta.error ? <div className="p-4"><ErrorPortal error={consulta.error} reintentar={consulta.refetch} /></div> : filas.length === 0 ? <EstadoVacio titulo={buscar ? "No hay resultados para esta búsqueda" : "Todavía no hay registros"} detalle={buscar ? (recurso === "aranceles" ? "Probá con otro hospital o prestación." : "Probá con otro documento, número o nombre.") : recurso === "aranceles" ? "Se mostrarán las prestaciones vinculadas de los hospitales con convenio activo." : VACIOS_PORTAL[recurso] || "Los registros de esta sección aparecerán acá."} /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b border-division bg-superficie-2 text-texto-debil"><tr>{columnas.map((col) => <th key={col.key} scope="col" className="whitespace-nowrap px-4 py-3 font-semibold">{col.label}</th>)}</tr></thead><tbody>{filas.map((fila) => <tr key={recurso === "aranceles" ? `${fila.convenio}:${fila.id}` : fila.id} className="border-b border-division last:border-0">{columnas.map((col) => <td key={col.key} className="px-4 py-3 align-top">{col.render ? col.render(fila) : fila[col.key] ?? "—"}</td>)}</tr>)}</tbody></table></div>}
    {!consulta.error && !consulta.isLoading && <div className="flex flex-wrap items-center justify-between gap-3 border-t border-division px-4 py-3"><span className="text-sm text-texto-debil">{plural(total, "registro", "registros")} · {total === 0 ? "Sin páginas" : `Página ${page} de ${paginas}`}</span><div className="flex gap-2"><Button size="sm" variant="ghost" disabled={total === 0 || page === 1 || consulta.isFetching} onClick={() => setPage((p) => p - 1)}>Anterior</Button><Button size="sm" variant="ghost" disabled={total === 0 || !consulta.data?.next || consulta.isFetching} onClick={() => setPage((p) => p + 1)}>Siguiente</Button></div></div>}
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
  return { name: "resuelve_autorizaciones", boolean: true, default: Boolean(valor), render: (checked, onChange) => <div className="flex items-center gap-2"><Checkbox label="Permitir resolver autorizaciones de este financiador" checked={Boolean(checked)} onChange={(e) => onChange(e.target.checked)} /><Ayuda>Concesión explícita para observar, aprobar o rechazar solicitudes. El rol de lectura por sí solo no concede este permiso.</Ayuda></div> };
}

function columnasDe(recurso, planes, catalogo, financiadorId) {
  const nombrePlan = (id) => planes.find((p) => p.id === id)?.nombre || (id ? `Plan ${id}` : "Todos los planes");
  const nombrePrestacion = (id) => catalogo.find((p) => p.id === id)?.nombre || (id ? `Prestación ${id}` : "Todas");
  const codigo = { key: "codigo", label: "Código" };
  return {
    planes: [{ key: "nombre", label: "Plan", render: (r) => <><span className="font-medium text-texto">{r.nombre}</span><span className="mt-1 block text-xs text-texto-debil">Código {r.codigo}</span></> }, { key: "activo", label: "Estado", render: (r) => <Badge tone={r.activo === false ? "gray" : "green"}>{r.activo === false ? "Inactivo" : "Vigente"}</Badge> }, { key: "reglas", label: "Reglas", render: (r) => <Link className="text-accent hover:underline" to={`/financiadores/reglas?${new URLSearchParams({ financiador: financiadorId, plan: r.id })}`}>Ver reglas</Link> }],
    aranceles: [
      { key: "prestacion", label: "Prestación" }, { key: "hospital", label: "Hospital" },
      { key: "arancel_general", label: "Arancel general", render: (r) => r.arancel_general == null ? "Sin definir" : importeARS(r.arancel_general) },
      { key: "arancel_acordado", label: "Arancel acordado", render: (r) => r.origen_arancel === "acordado_financiador" && r.arancel != null ? importeARS(r.arancel) : "—" },
      { key: "arancel", label: "Se aplica", render: (r) => r.estado !== "vigente" ? <Badge tone="amber">{({ sin_cobro: "Sin cobro", arancel_pendiente: "Arancel pendiente", politica_pendiente: "Política pendiente" })[r.estado] || r.estado}</Badge> : <Badge tone={r.origen_arancel === "acordado_financiador" ? "info" : "gray"}>{r.origen_arancel === "acordado_financiador" ? "Acordado" : "General"}</Badge> },
    ],
    catalogo: [codigo, { key: "nombre", label: "Prestación" }, { key: "categoria", label: "Tipo" }],
    reglas: [{ key: "prestacion", label: "Prestación", render: (r) => r.prestacion ? nombrePrestacion(r.prestacion) : r.categoria || "Cobertura general" }, { key: "plan", label: "Plan", render: (r) => nombrePlan(r.plan) }, { key: "porcentaje", label: "Cobertura", render: (r) => <>{Number(r.porcentaje).toLocaleString("es-AR")}%{r.requiere_autorizacion && <p className="mt-1 text-xs text-texto-debil">Autorización previa</p>}</> }, { key: "cupo", label: "Tope", render: (r) => r.cupo == null ? "Sin tope" : `${r.cupo} por ${r.periodo === "mes" ? "mes" : "año"} calendario` }, { key: "vigente_desde", label: "Desde", render: (r) => fecha(r.vigente_desde) }],
    padron: [{ key: "nombre", label: "Afiliado", render: (r) => <><span className="font-medium text-texto">{r.nombre}</span><span className="mt-1 block text-xs text-texto-debil">DNI {documentoParcial(r.documento)}</span></> }, { key: "numero", label: "N.º de afiliado" }, { key: "plan", label: "Plan", render: (r) => r.plan ? nombrePlan(r.plan) : "Sin plan" }, { key: "vigente", label: "Estado", render: (r) => <><Badge tone={r.finalizado_en ? "gray" : r.vigente === false ? "amber" : "green"}>{r.finalizado_en ? "Finalizada" : r.vigente === false ? "Aún no vigente" : "Vigente"}</Badge><p className="mt-1 text-xs text-texto-debil">{r.finalizado_en ? `Finalizada el ${fechaHora(r.finalizado_en)}` : `Desde ${fecha(r.desde)}`}</p></> }],
    consumos: [{ key: "afiliado", label: "Afiliado", render: (r) => <>{r.afiliado_nombre || `Afiliado ${r.afiliado}`}<p className="mt-1 text-xs text-texto-debil">N.º {r.afiliado_numero || "—"} · DNI {documentoParcial(r.afiliado_documento)}</p></> }, { key: "prestacion", label: "Prestación", render: (r) => nombrePrestacion(r.prestacion) }, { key: "fecha", label: "Fecha", render: (r) => fecha(r.fecha) }, { key: "cantidad", label: "Cantidad" }, { key: "referencia", label: "Referencia" }, { key: "correccion", label: "Estado", render: (r) => r.corrige ? <Badge tone="info">Corrección</Badge> : <Badge tone="green">Registrado</Badge> }],
    convenios: [{ key: "institucion_nombre", label: "Hospital" }, { key: "vigencia", label: "Vigencia", render: (r) => r.cerrado_en ? `Cerrado el ${fechaHora(r.cerrado_en)}` : r.aceptado_en ? `Desde ${fechaHora(r.aceptado_en)}` : "Pendiente de aceptación" }, { key: "plazo_autorizacion_horas", label: "Plazo de autorización", render: (r) => r.plazo_autorizacion_horas == null ? "Sin vencimiento automático" : `${r.plazo_autorizacion_horas} horas` }, { key: "estado", label: "Estado", render: (r) => <><Badge tone={r.estado === "activo" ? "green" : r.estado === "propuesto" ? "amber" : "gray"}>{ESTADOS_CONVENIO[r.estado] || r.estado}</Badge>{r.motivo_cierre && <p className="mt-1 text-xs text-texto-debil">{r.motivo_cierre}</p>}</> }],
    usuarios: [{ key: "nombre", label: "Usuario", render: (r) => <><span className="font-medium text-texto">{r.nombre}</span><span className="mt-1 block text-xs text-texto-debil">{r.email}</span></> }, { key: "rol", label: "Permiso", render: (r) => <>{ROLES[r.rol] || r.rol}{r.resuelve_autorizaciones && <p className="mt-1 text-xs text-texto-debil">Resuelve autorizaciones</p>}</> }, { key: "activo", label: "Estado", render: (r) => <Badge tone={r.activo === false ? "gray" : "green"}>{r.activo === false ? "Inactivo" : "Activo"}</Badge> }],
  }[recurso];
}

function CrearRegistro({ recurso, organizacion, scope, planes, catalogo, titulo, onClose, onGuardado }) {
  const hospitales = useQuery({ queryKey: [...scope, "instituciones"], queryFn: () => opcionesFinanciador(organizacion.id, "instituciones"), enabled: recurso === "convenios", gcTime: 0 });
  const necesitaPlanes = ["padron", "reglas"].includes(recurso);
  const necesitaCatalogo = ["consumos", "reglas"].includes(recurso);
  const error = (necesitaPlanes && planes.error) || (necesitaCatalogo && catalogo.error) || (recurso === "convenios" && hospitales.error);
  const cargando = (necesitaPlanes && planes.isLoading) || (necesitaCatalogo && catalogo.isLoading) || (recurso === "convenios" && hospitales.isLoading);
  if (error || cargando) return <Modal title={titulo} onClose={onClose}>{error ? <ErrorPortal error={error} reintentar={() => { planes.refetch(); catalogo.refetch(); if (recurso === "convenios") hospitales.refetch(); }} /> : <Spinner label="Cargando opciones…" />}</Modal>;
  if (recurso === "reglas") return <FormularioRegla organizacion={organizacion} planes={planes.data || []} catalogo={catalogo.data || []} onClose={onClose} onGuardado={onGuardado} />;
  const p = (planes.data || []).filter((plan) => recurso !== "padron" || plan.activo !== false).map((plan) => ({ ...plan, nombre: plan.activo === false ? `${plan.nombre} (inactivo)` : plan.nombre }));
  const prestaciones = (catalogo.data || []).map((item) => ({ ...item, nombre: `${item.codigo} · ${item.nombre}` }));
  const campos = {
    catalogo: [{ name: "codigo", label: "Código común", maxLength: 60, required: true }, { name: "nombre", label: "Nombre de la prestación", maxLength: 160, required: true }, { name: "categoria", label: "Categoría", maxLength: 80, required: true }],
    planes: [{ name: "codigo", label: "Código del plan", required: true, maxLength: 50 }, { name: "nombre", label: "Nombre del plan", required: true, maxLength: 160 }],
    padron: [{ name: "numero", label: "Número de afiliado", required: true, ayuda: "Conservá los ceros iniciales." }, { name: "documento", label: "Documento", required: true }, { name: "nombre", label: "Nombre y apellido", required: true }, { name: "plan", label: "Plan", options: p, numeric: true, empty: "Sin plan" }, { name: "desde", label: "Afiliación vigente desde", type: "date", default: HOY(), required: true }],
    consumos: [{ name: "afiliado", numeric: true, render: (value, onChange) => <BuscarAfiliado scope={scope} organizacion={organizacion} value={value} onChange={onChange} /> }, { name: "prestacion", label: "Prestación", options: prestaciones, numeric: true, required: true }, { name: "fecha", label: "Fecha de la prestación", type: "date", max: HOY(), required: true }, { name: "cantidad", label: "Cantidad", type: "number", min: 1, step: 1, numeric: true, required: true }, { name: "referencia", label: "Referencia externa (opcional)", ayuda: "Usá la misma referencia para reconocer un registro ya enviado." }, { name: "motivo_duplicado", maxLength: 255, label: "Motivo para registrar un posible duplicado (opcional)", ayuda: "Completalo sólo si verificaste que otro registro similar corresponde a una prestación distinta." }],
    convenios: [{ name: "institucion", label: "Hospital", options: hospitales.data || [], numeric: true, required: true }],
    usuarios: [campoPermisoAutorizaciones(), { name: "email", label: "Correo electrónico", type: "email", required: true }, { name: "nombre", label: "Nombre y apellido", required: true }, { name: "rol", label: "Rol", options: [{ id: "admin", nombre: "Administración: configura y gestiona accesos" }, { id: "operador", nombre: "Operación: padrón y consumos" }, { id: "auditor", nombre: "Auditoría: sólo lectura" }], required: true }],
  }[recurso];
  return <FormularioPortal titulo={titulo} campos={campos} onClose={onClose} onGuardado={onGuardado} descripcion={recurso === "usuarios" ? "El acceso se limita a este financiador. La credencial de una persona que ya usa HEN se conserva." : undefined} guardar={(body) => api.post(rutaFinanciador(organizacion.id, recurso), body)} />;
}

function FormularioRegla({ organizacion, planes, catalogo, onClose, onGuardado }) {
  const [datos, setDatos] = useState({ plan: "", destino: "", porcentaje: "", limitar: false, cupo: "", periodo: "anio", vigente_desde: HOY(), requiere_autorizacion: false });
  const [error, setError] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const categorias = [...new Set(catalogo.map((item) => item.categoria).filter(Boolean))].sort();
  const separador = datos.destino.indexOf(":");
  const tipo = datos.destino.slice(0, separador);
  const valor = datos.destino.slice(separador + 1);
  const nombrePlan = planes.find((plan) => String(plan.id) === datos.plan)?.nombre || "cualquier plan";
  const nombreDestino = tipo === "prestacion" ? catalogo.find((item) => String(item.id) === valor)?.nombre : valor;
  const porcentaje = Number(datos.porcentaje);
  const copago = Number.isFinite(porcentaje) ? Math.max(0, 100 - porcentaje) : null;
  const editar = (campo) => (event) => setDatos((previo) => ({ ...previo, [campo]: event.target.value }));

  async function guardar(event) {
    event.preventDefault();
    setError(null);
    setGuardando(true);
    try {
      const body = {
        plan: datos.plan ? Number(datos.plan) : null,
        prestacion: tipo === "prestacion" ? Number(valor) : null,
        categoria: tipo === "categoria" ? valor : "",
        porcentaje: datos.porcentaje,
        cupo: datos.limitar && tipo === "prestacion" ? Number(datos.cupo) : null,
        periodo: datos.periodo,
        vigente_desde: datos.vigente_desde,
        requiere_autorizacion: datos.requiere_autorizacion,
      };
      const resultado = await api.post(rutaFinanciador(organizacion.id, "reglas"), body);
      await onGuardado(resultado);
    } catch (err) { setError(err); }
    finally { setGuardando(false); }
  }

  return <Modal title="Nueva regla de cobertura" onClose={guardando ? undefined : onClose} width={620}>
    <form className="space-y-5" onSubmit={guardar}>
      {error && <ErrorPortal error={error} />}
      <fieldset disabled={guardando} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Plan" ayuda="Dejalo en todos para aplicar la regla a cualquier plan."><Select value={datos.plan} onChange={editar("plan")}><option value="">Todos los planes</option>{planes.map((plan) => <option key={plan.id} value={plan.id}>{plan.nombre}{plan.activo === false ? " (inactivo)" : ""}</option>)}</Select></Field>
          <Field label="Prestación o categoría" ayuda="Elegí una prestación concreta o una categoría del catálogo."><Select required value={datos.destino} onChange={(event) => setDatos((previo) => ({ ...previo, destino: event.target.value, limitar: event.target.value.startsWith("categoria:") ? false : previo.limitar }))}><option value="">Seleccioná una opción</option><optgroup label="Prestaciones">{catalogo.map((item) => <option key={item.id} value={`prestacion:${item.id}`}>{item.nombre}</option>)}</optgroup><optgroup label="Categorías">{categorias.map((categoria) => <option key={categoria} value={`categoria:${categoria}`}>{categoria}</option>)}</optgroup></Select></Field>
        </div>
        <Field label="Porcentaje de cobertura" ayuda={datos.porcentaje !== "" && porcentaje >= 0 && porcentaje <= 100 ? `El paciente cubre el ${copago.toLocaleString("es-AR")}% restante, sujeto a la evaluación del caso.` : "Se calcula sobre el arancel aplicable."}><Input required type="number" min="0" max="100" step="0.01" value={datos.porcentaje} onChange={editar("porcentaje")} /></Field>
        <div className="rounded-lg border border-borde p-4">
          <Checkbox label="Limitar la cantidad cubierta" checked={datos.limitar} disabled={tipo === "categoria"} onChange={(event) => setDatos((previo) => ({ ...previo, limitar: event.target.checked }))} />
          {tipo === "categoria" && <p className="mt-1 text-xs text-texto-debil">Los cupos de cantidad se definen para una prestación concreta.</p>}
          {datos.limitar && <div className="mt-4 grid gap-4 sm:grid-cols-2"><Field label="Cantidad máxima"><Input required type="number" min="1" step="1" value={datos.cupo} onChange={editar("cupo")} /></Field><Field label="Período" ayuda="El cupo se renueva al comenzar cada período calendario."><Select value={datos.periodo} onChange={editar("periodo")}><option value="anio">Año calendario</option><option value="mes">Mes calendario</option></Select></Field></div>}
        </div>
        <div className="grid gap-4 sm:grid-cols-2"><Field label="Vigente desde"><Input required type="date" min={HOY()} value={datos.vigente_desde} onChange={editar("vigente_desde")} /></Field><div className="flex items-end pb-2"><Checkbox label="Requiere autorización previa" checked={datos.requiere_autorizacion} onChange={(event) => setDatos((previo) => ({ ...previo, requiere_autorizacion: event.target.checked }))} /></div></div>
      </fieldset>
      {nombreDestino && datos.porcentaje !== "" && porcentaje >= 0 && porcentaje <= 100 && <p className="rounded-lg border border-borde bg-superficie-2 p-3 text-sm text-texto-suave">Vista previa: {nombreDestino} tiene cobertura del {porcentaje.toLocaleString("es-AR")}% para {nombrePlan}{datos.limitar && datos.cupo ? `, hasta ${datos.cupo} por ${datos.periodo === "mes" ? "mes" : "año"} calendario` : ", sin cupo de cantidad"}. Las decisiones ya registradas se conservan.</p>}
      <div className="flex justify-end gap-2 border-t border-division pt-4"><Button type="button" variant="ghost" disabled={guardando} onClick={onClose}>Cancelar</Button><Button type="submit" disabled={guardando}>{guardando ? "Guardando…" : "Guardar regla"}</Button></div>
    </form>
  </Modal>;
}

function BuscarAfiliado({ scope, organizacion, value, onChange }) {
  const [texto, setTexto] = useState("");
  const [buscar, setBuscar] = useState("");
  const [seleccionado, setSeleccionado] = useState(null);
  useEffect(() => { const timer = setTimeout(() => setBuscar(texto.trim()), 250); return () => clearTimeout(timer); }, [texto]);
  const consulta = useQuery({ queryKey: [...scope, "buscar-afiliado", buscar], queryFn: () => api.get(`${rutaFinanciador(organizacion.id, "padron")}?${new URLSearchParams({ search: buscar, page: 1 })}`), enabled: buscar.length >= 2, gcTime: 0 });
  const encontrados = filasDe(consulta.data);
  const opciones = seleccionado && !encontrados.some((item) => item.id === seleccionado.id) ? [seleccionado, ...encontrados] : encontrados;
  return <div className="space-y-2"><Field label="Buscar afiliado" ayuda="Ingresá al menos dos caracteres del documento, número o nombre."><Input value={texto} onChange={(e) => setTexto(e.target.value)} /></Field>{consulta.error && <ErrorPortal error={consulta.error} reintentar={consulta.refetch} />}<Field label="Afiliado"><Select required value={value} onChange={(e) => { onChange(e.target.value); setSeleccionado(opciones.find((item) => String(item.id) === e.target.value)); }}><option value="">{consulta.isFetching ? "Buscando…" : "Seleccioná un afiliado"}</option>{opciones.map((item) => <option key={item.id} value={item.id}>{item.numero} · {item.documento} · {item.nombre}</option>)}</Select></Field>{consulta.data?.next && <p className="text-sm text-texto-debil">Hay más resultados. Precisá la búsqueda para encontrar al afiliado.</p>}{buscar.length >= 2 && !consulta.isFetching && !consulta.error && encontrados.length === 0 && <p className="text-sm text-texto-debil">Sin resultados. Primero registrá al afiliado en el padrón.</p>}</div>;
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
  return <Modal title={titulo} ayuda={descripcion} onClose={guardando ? undefined : onClose} width={620}>
    <form className="space-y-4" onSubmit={enviar}>{error && <ErrorPortal error={error} />}<fieldset disabled={guardando} className="space-y-4">{campos.map(({ name, label, ayuda, options, empty, numeric, boolean, render, default: valorInicial, ...props }) => <div key={name}>{render ? render(datos[name], (value) => setDatos({ ...datos, [name]: value })) : <Field label={label} ayuda={ayuda}>{options ? <Select {...props} value={datos[name]} onChange={(e) => setDatos({ ...datos, [name]: e.target.value })}><option value="">{empty || "Seleccioná una opción"}</option>{options.map((op) => <option key={op.id} value={op.id}>{op.nombre}</option>)}</Select> : <Input {...props} value={datos[name]} onChange={(e) => setDatos({ ...datos, [name]: e.target.value })} />}</Field>}</div>)}</fieldset><div className="flex justify-end gap-2 border-t border-division pt-4"><Button type="button" variant="ghost" disabled={guardando} onClick={onClose}>Cancelar</Button><Button type="submit" disabled={guardando}>{guardando ? "Guardando…" : confirmacion}</Button></div></form>
  </Modal>;
}
