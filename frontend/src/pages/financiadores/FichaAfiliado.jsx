import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useLocation, useParams, useSearchParams } from "react-router-dom";
import { api } from "@/api/client";
import { errorFinanciador, filasDe, rutaFinanciador } from "@/api/financiadores";
import { POR_PAGINA } from "@/api/queries";
import { useAuth } from "@/auth/AuthContext";
import { Avatar, Ayuda, Badge, Button, Card, Spinner, Tabs, Textarea } from "@/components/ui";
import { Icon } from "@/components/icons";
import { cn } from "@/lib/cn";
import { EstadoVacio } from "@/components/ui/estados";
import { Shell } from "@/components/Shell";
import { fechaHora, plural } from "@/lib/format";
import { importeARS } from "@/api/finanzas";
import DetalleAutorizacion, { EstadoAutorizacion, PaginasAutorizacion } from "./DetalleAutorizacion";
import { ESTADOS } from "./ActividadFinanciador";
import { estadoCaso } from "@/lib/dominio";
import { parametrosListado } from "@/lib/padronNavigation";
import { NOMBRE_SISTEMA } from "@/lib/marca";
import FichaPadronAdministrativa from "@/components/financiadores/FichaPadronAdministrativa";
import TarjetaFicha from "@/components/financiadores/TarjetaFicha";
import { ROLES, itemsFinanciador } from "./menuFinanciador";

const fecha = (valor) => valor ? String(valor).slice(0, 10).split("-").reverse().join("/") : "—";
const fechaFin = (exclusivo) => fecha(new Date(Date.parse(`${exclusivo}T00:00:00Z`) - 86400000).toISOString());

function ErrorFicha({ error, reintentar }) {
  return <div role="alert" className="rounded-md bg-badge-error-bg p-4 text-badge-error-fg"><p>{errorFinanciador(error)}</p>{reintentar && <Button className="mt-3" size="sm" variant="secondary" onClick={reintentar}>Reintentar</Button>}</div>;
}

function HistoriaFinanciador({ id, afiliado, scope }) {
  const [pagina, setPagina] = useState(1);
  const [casoAbierto, setCasoAbierto] = useState(null);
  const [motivo, setMotivo] = useState("");
  const [evoluciones, setEvoluciones] = useState(null);
  const [error, setError] = useState(null);
  const [consultando, setConsultando] = useState(false);
  const casos = useQuery({ queryKey: [...scope, "historia-casos", afiliado, pagina], queryFn: () => api.get(`${rutaFinanciador(id, "ficha-historia-casos")}?${new URLSearchParams({ afiliado, page: pagina, page_size: POR_PAGINA })}`), gcTime: 0, retry: false });
  function cerrar() { setCasoAbierto(null); setEvoluciones(null); setMotivo(""); setError(null); }
  async function consultar(event) {
    event.preventDefault();
    if (motivo.trim().length < 10 || motivo.trim().length > 200) return;
    setConsultando(true); setError(null);
    try { setEvoluciones(await api.post(rutaFinanciador(id, "ficha-historia-evoluciones"), { afiliado: Number(afiliado), caso: casoAbierto, motivo: motivo.trim() })); }
    catch (err) { setError(err); }
    finally { setConsultando(false); }
  }
  const largo = motivo.trim().length;
  const total = casos.data?.count ?? 0;
  return (
    <section id="historia-clinica" className="scroll-mt-8 space-y-4" aria-label="Historia clínica">
      <div className="flex flex-wrap items-center gap-3">
        <span className="flex size-9 items-center justify-center rounded-md bg-badge-info-bg text-badge-info-fg"><Icon name="stethoscope" size={18} /></span>
        <h2 className="text-lg font-semibold">Historia clínica</h2><Ayuda etiqueta="Ayuda: Historia clínica">Evoluciones firmadas de los casos que ingresaron con tu cobertura en hospitales dentro de tu alcance. No incluye alergias, antecedentes, estudios ni recetas. Cada consulta queda registrada con tu motivo y la ve el hospital.</Ayuda>
        {total > 0 && <Badge tone="neutral">{plural(total, "caso alcanzado", "casos alcanzados")}</Badge>}
      </div>
      {casos.isLoading ? <Card className="p-4"><Spinner label="Consultando casos…" /></Card>
        : casos.error ? <ErrorFicha error={casos.error} reintentar={casos.refetch} />
        : !casos.data?.results?.length ? <Card><EstadoVacio icono="clipboard" titulo="No hay casos alcanzados" detalle="Cuando el afiliado ingrese con tu cobertura a un hospital con convenio, sus casos aparecen acá." /></Card>
        : <div className="space-y-3">
          {casos.data.results.map((caso) => {
            const abierto = casoAbierto === caso.id;
            const estado = estadoCaso[caso.estado];
            return (
              <Card key={caso.id} className={cn("overflow-hidden transition-shadow", abierto && "shadow-card ring-1 ring-accent")}>
                <div className="flex flex-wrap items-start justify-between gap-4 p-4 sm:p-5">
                  <div className="flex min-w-0 gap-3">
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-md bg-superficie-2 text-texto-debil"><Icon name="building" size={18} /></span>
                    <div className="min-w-0 space-y-1.5">
                      <p className="font-semibold">{caso.institucion.nombre} <span className="font-normal text-texto-debil">· Caso {caso.id}</span></p>
                      <div className="flex flex-wrap items-center gap-2 text-sm text-texto-debil">
                        <Badge tone={estado?.tone}>{estado?.label || caso.estado}</Badge>
                        {caso.acceso === "pendiente_historico" ? <Badge tone="amber">Histórico pendiente</Badge> : <Badge tone="green">Relación vigente</Badge>}
                        <span className="inline-flex items-center gap-1"><Icon name="calendar" size={14} />Ingreso {fechaHora(caso.creado)}</span>
                        <span className="inline-flex items-center gap-1"><Icon name="fileText" size={14} />{plural(caso.evoluciones_firmadas, "evolución firmada", "evoluciones firmadas")}</span>
                      </div>
                    </div>
                  </div>
                  {caso.evoluciones_firmadas > 0
                    ? !abierto && <Button size="sm" variant="secondary" onClick={() => { cerrar(); setCasoAbierto(caso.id); }}><Icon name="eye" size={15} />Ver evoluciones</Button>
                    : <span className="text-sm text-texto-debil">No hay evoluciones firmadas</span>}
                </div>
                {abierto && <div className="border-t border-division bg-superficie-2 p-4 sm:p-5">
                  {evoluciones === null ? <form className="max-w-2xl space-y-3" onSubmit={consultar}>
                    <div>
                      <label className="block font-medium" htmlFor={`motivo-${caso.id}`}>Motivo de consulta</label>
                      <p className="text-sm text-texto-debil">Queda registrado y visible para el hospital antes de ver las evoluciones.</p>
                    </div>
                    <Textarea id={`motivo-${caso.id}`} required minLength={10} maxLength={200} autoFocus value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Ej.: auditoría médica de la prestación facturada en septiembre" />
                    <p className={cn("text-xs tabular-nums", largo > 0 && largo < 10 ? "text-badge-amber-fg" : "text-texto-debil")}>{largo}/200 · mínimo 10 caracteres</p>
                    {error && <ErrorFicha error={error} />}
                    <div className="flex gap-2">
                      <Button type="submit" disabled={consultando || largo < 10 || largo > 200}>{consultando ? "Consultando…" : "Confirmar motivo"}</Button>
                      <Button type="button" variant="ghost" onClick={cerrar}>Cerrar</Button>
                    </div>
                  </form> : <div className="space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm text-texto-debil">Motivo registrado: <span className="text-texto-suave">«{motivo.trim()}»</span></p>
                      <Button size="sm" variant="ghost" onClick={cerrar}>Cerrar evoluciones</Button>
                    </div>
                    {!evoluciones.length ? <EstadoVacio titulo="No hay evoluciones firmadas" /> : <ol className="relative space-y-4 border-l border-borde pl-6">
                      {evoluciones.map((entrada) => <li key={entrada.id} className="relative">
                        <span className="absolute -left-[31px] top-5 size-3 rounded-full border-2 border-superficie bg-accent" aria-hidden="true" />
                        <article className="rounded-lg border border-borde bg-superficie p-4 sm:p-5">
                          <div className="flex flex-wrap items-start justify-between gap-2">
                            <h3 className="font-semibold">{entrada.titulo}</h3>
                            <Badge tone="green">Firmada</Badge>
                          </div>
                          <p className="mt-1 text-sm text-texto-debil">{fechaHora(entrada.fecha)} · {entrada.autor || "Autor no disponible"}{entrada.matricula && ` · Matrícula ${entrada.matricula}`}</p>
                          <p className="mt-3 max-w-prose whitespace-pre-wrap leading-relaxed text-texto-medio">{entrada.contenido}</p>
                        </article>
                      </li>)}
                    </ol>}
                  </div>}
                </div>}
              </Card>
            );
          })}
          {(pagina > 1 || casos.data.next) && <div className="flex items-center justify-end gap-3 text-sm text-texto-debil">
            <span>Página {pagina}</span>
            <Button size="sm" variant="secondary" disabled={pagina <= 1} onClick={() => { cerrar(); setPagina(pagina - 1); }}>Anterior</Button>
            <Button size="sm" variant="secondary" disabled={!casos.data.next} onClick={() => { cerrar(); setPagina(pagina + 1); }}>Siguiente</Button>
          </div>}
        </div>}
    </section>
  );
}

export default function FichaAfiliado() {
  const { afiliado } = useParams();
  const { user } = useAuth();
  const [parametros] = useSearchParams();
  return <FichaAfiliadoContenido key={`${user.id}:${parametros.get("financiador") || ""}:${afiliado}`} />;
}

function FichaAfiliadoContenido() {
  const { afiliado } = useParams();
  const location = useLocation();
  const { user } = useAuth();
  const plataforma = Boolean(user.is_superuser || Object.values(user.capacidades_por_institucion || {}).some((caps) => caps.includes("gobierno_plataforma")));
  const [parametros, setParametros] = useSearchParams();
  const [detalle, setDetalle] = useState(null);
  const [descargando, setDescargando] = useState(false);
  const [errorDescarga, setErrorDescarga] = useState(null);
  const qc = useQueryClient();
  const organizaciones = useQuery({ queryKey: ["financiadores", user.id, "organizaciones"], queryFn: async () => {
    const filas = [];
    for (let page = 1; ; page += 1) {
      const data = await api.get(`/financiadores/?page=${page}`);
      filas.push(...filasDe(data));
      if (!data.next) return filas;
    }
  }, gcTime: 0 });
  const seleccion = parametros.get("financiador");
  const organizacion = seleccion ? organizaciones.data?.find((item) => String(item.id) === seleccion) : plataforma ? null : organizaciones.data?.[0];
  const id = organizacion?.id;
  const scope = ["financiador", user.id, id];
  const numeroPagina = Number(parametros.get("page") || 1);
  const numeroAutorizaciones = Number(parametros.get("autorizaciones_page") || 1);
  const pagina = Number.isSafeInteger(numeroPagina) && numeroPagina > 0 ? numeroPagina : 1;
  const paginaAutorizaciones = Number.isSafeInteger(numeroAutorizaciones) && numeroAutorizaciones > 0 ? numeroAutorizaciones : 1;
  const ficha = useQuery({ queryKey: [...scope, "ficha", afiliado, pagina], queryFn: () => api.get(`${rutaFinanciador(id, "ficha-afiliado")}?${new URLSearchParams({ afiliado, page: pagina, page_size: POR_PAGINA })}`), enabled: Boolean(id), gcTime: 0, retry: false });
  const autorizaciones = useQuery({ queryKey: [...scope, "ficha-autorizaciones", afiliado, paginaAutorizaciones], queryFn: () => api.get(`${rutaFinanciador(id, "ficha-afiliado-autorizaciones")}?${new URLSearchParams({ afiliado, page: paginaAutorizaciones, page_size: POR_PAGINA })}`), enabled: Boolean(id), gcTime: 0, retry: false });
  const pendientes = useQuery({ queryKey: [...scope, "ficha-autorizaciones-pendientes", afiliado], queryFn: () => api.get(`${rutaFinanciador(id, "ficha-afiliado-autorizaciones")}?${new URLSearchParams({ afiliado, pendientes: true, page: 1, page_size: POR_PAGINA })}`), enabled: Boolean(id), gcTime: 0, retry: false });
  const persona = ficha.data?.afiliado;
  const filas = ficha.data?.results || [];
  const filasAutorizaciones = autorizaciones.data?.results || [];
  const volver = `/financiadores/padron?${parametrosListado(parametros, id || seleccion || "")}`;
  // Mismo menú que el portal; Padrón vuelve al listado con sus filtros.
  const menu = itemsFinanciador({ organizacion, plataforma, admin: plataforma || organizacion?.rol === "admin", sufijo: seleccion ? `?financiador=${encodeURIComponent(seleccion)}` : "" })
    .map((item) => item.key === "padron" ? { ...item, to: volver, end: false } : item);

  function cambiarPagina(campo, valor) {
    const nuevos = new URLSearchParams(parametros);
    if (valor > 1) nuevos.set(campo, valor);
    else nuevos.delete(campo);
    setParametros(nuevos);
  }
  async function exportar() {
    setDescargando(true); setErrorDescarga(null);
    try {
      await api.download(`${rutaFinanciador(id, "ficha-afiliado")}?${new URLSearchParams({ afiliado, formato: "csv" })}`, `ficha-afiliado-${afiliado}.csv`);
    } catch (error) { setErrorDescarga(error); }
    finally { setDescargando(false); }
  }
  async function guardado() {
    setDetalle(null);
    await qc.invalidateQueries({ queryKey: scope });
  }

  if (plataforma && !seleccion && !organizaciones.isLoading && !organizaciones.error) return <Navigate to="/directorio?vista=financiadores" replace />;

  const pedida = location.hash === "#historia-clinica" ? "historia" : parametros.get("tab");
  const pestanas = [
    { key: "datos", label: "Datos" },
    { key: "legajo", label: "Legajo y familia" },
    { key: "cobertura", label: "Cobertura y actividad", cuenta: pendientes.data?.count || null },
    ...(organizacion?.consulta_historia_clinica ? [{ key: "historia", label: "Historia clínica" }] : []),
    { key: "historial", label: "Historial" },
  ];
  const tab = pestanas.some((item) => item.key === pedida) ? pedida : "datos";
  function cambiarTab(valor) {
    const nuevos = new URLSearchParams(parametros);
    if (valor === "datos") nuevos.delete("tab");
    else nuevos.set("tab", valor);
    setParametros(nuevos, { replace: true });
  }
  const administrativa = (vista) => <FichaPadronAdministrativa key={`${id}:${afiliado}:${vista}`} vista={vista} afiliado={afiliado} organizacion={organizacion} usuarioId={user.id} parametros={parametros} plataforma={plataforma} />;

  // Plataforma navega con su propio Shell, igual que en el portal del financiador.
  return <Shell plataforma={plataforma} financiador={plataforma ? null : { nombre: organizacion?.nombre || NOMBRE_SISTEMA, titulo: "Ficha del afiliado", rol: ROLES[organizacion?.rol] || "Financiador", items: menu }}><div className="space-y-5 p-lg sm:p-[30px] xl:p-[40px]">
    <Link className="text-sm font-medium text-accent hover:underline" to={volver}>← Volver al padrón</Link>
    {/* Quién es primero: el resto de la ficha se lee en referencia a esta cabecera. */}
    <Card className="p-5 sm:p-6">
      <div className="flex flex-wrap items-center gap-4">
        {persona && <Avatar nombre={persona.nombre} size={56} />}
        <div className="min-w-0 flex-1 space-y-1">
          <h1 className="text-xs font-semibold uppercase tracking-wide text-texto-debil">Ficha del afiliado</h1>
          {persona ? <p className="text-cifra font-bold leading-tight">{persona.nombre}</p> : ficha.error ? null : <Spinner label="Consultando ficha…" />}
        </div>
        {persona && <div className="flex flex-wrap items-center gap-2">
          {persona.cobertura_habilitada === false && <Badge tone="amber">Sólo registro administrativo</Badge>}
          <Badge tone={{ vigente: "green", finalizada: "gray", futura: "info" }[persona.estado] || "neutral"}>{{ vigente: "Vigente", finalizada: "Finalizada", futura: "Aún no vigente" }[persona.estado] || persona.estado}</Badge>
          {pendientes.data?.count > 0 && <Badge tone="amber">{plural(pendientes.data.count, "autorización pendiente", "autorizaciones pendientes")}</Badge>}
        </div>}
      </div>
      {persona && <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-division pt-4 text-sm sm:grid-cols-3 lg:grid-cols-5">{[["N.º de afiliado", persona.numero], ["Documento", persona.documento], ["Plan", persona.plan_nombre || "Sin plan"], ["Desde", fecha(persona.desde)], ...(persona.finalizado_en ? [["Finalizada", fechaHora(persona.finalizado_en)]] : [])].map(([label, valor]) => <div key={label} className="min-w-0"><dt className="text-xs font-medium uppercase tracking-wide text-texto-debil">{label}</dt><dd className="mt-1 break-words font-medium tabular-nums">{valor}</dd></div>)}</dl>}
    </Card>
    {organizaciones.isLoading ? <Spinner label="Consultando financiador…" /> : organizaciones.error ? <ErrorFicha error={organizaciones.error} reintentar={organizaciones.refetch} /> : !organizacion ? <Card><EstadoVacio titulo="No tenés acceso al financiador seleccionado" /></Card> : <>
    <div className="overflow-x-auto"><Tabs variant="underline" tabs={pestanas} valor={tab} onChange={cambiarTab} className="min-w-max" /></div>
    <div role="tabpanel" aria-label={pestanas.find((item) => item.key === tab).label} className="space-y-4">
    {tab === "datos" && administrativa("datos")}
    {tab === "legajo" && administrativa("legajo")}
    {tab === "historia" && <HistoriaFinanciador key={`${id}:${afiliado}`} id={id} afiliado={afiliado} scope={scope} />}
    {(tab === "cobertura" || tab === "historial") && (ficha.isLoading ? <Spinner label="Consultando ficha…" /> : ficha.error ? <ErrorFicha error={ficha.error} reintentar={ficha.refetch} /> : tab === "historial" ? <>
      <section aria-label="Historial de la afiliación"><TarjetaFicha titulo="Historial de la afiliación" icono="layers" descripcion="Cada registro muestra una instantánea de la afiliación. Su fecha de afiliación no es el inicio de vigencia del plan; las correcciones del plan se aplican a evaluaciones nuevas y conservan las prestaciones ya registradas.">{!ficha.data.historial?.length ? <EstadoVacio titulo="No hay cambios registrados" /> : <ol className="relative space-y-5 border-l border-borde pl-6">{ficha.data.historial.map((h, index) => <li key={`${h.registrado}-${index}`} className="relative text-sm"><span className="absolute -left-[31px] top-1 size-3 rounded-full border-2 border-superficie bg-accent" aria-hidden="true" /><div className="flex flex-wrap items-center gap-2"><Badge tone={h.tipo === "finalizacion" ? "amber" : h.tipo === "reactivacion" ? "green" : "info"}>{({ actualizacion: "Actualización", finalizacion: "Finalización", reactivacion: "Reactivación" })[h.tipo] || h.tipo}</Badge><span className="font-semibold tabular-nums">{fechaHora(h.registrado)}</span></div><p className="mt-1.5">{h.numero} · {h.plan_nombre || "Sin plan"} · Afiliación desde {fecha(h.desde)}</p>{h.motivo && <p className="text-texto-suave">Motivo: {h.motivo}</p>}<p className="text-texto-debil">Registrado por {h.usuario_nombre}</p></li>)}</ol>}</TarjetaFicha></section>
      {administrativa("historial")}
    </> : <>
      <section aria-label="Resumen de actividad" className="grid overflow-hidden rounded-lg border border-borde bg-superficie sm:grid-cols-2 xl:grid-cols-5">{[["Prestaciones realizadas", ficha.data.resumen?.realizadas ?? 0], ["Unidades cubiertas", ficha.data.resumen?.cubiertas_realizadas ?? 0], ["Importe a cargo del financiador", importeARS(ficha.data.resumen?.importe_asignado ?? "0.00")], ["Discrepancias", ficha.data.resumen?.discrepancias ?? 0], ["Importes pendientes", ficha.data.resumen?.importes_pendientes ?? 0]].map(([titulo, valor]) => <div key={titulo} className="border-b border-division p-4 sm:border-r xl:border-b-0 xl:last:border-r-0"><p className="text-xs font-medium uppercase tracking-wide text-texto-debil">{titulo}</p><p className="mt-2 text-xl font-semibold tabular-nums">{valor}</p></div>)}</section>
      <section aria-label="Autorizaciones pendientes"><TarjetaFicha titulo="Autorizaciones pendientes" icono="bell" cuerpoClassName="p-0">{pendientes.isLoading ? <div className="p-5"><Spinner label="Consultando pendientes…" /></div> : pendientes.error ? <div className="p-5"><ErrorFicha error={pendientes.error} reintentar={pendientes.refetch} /></div> : !pendientes.data?.results?.length ? <EstadoVacio titulo="No hay autorizaciones pendientes" /> : <ul className="divide-y divide-division">{pendientes.data.results.map((fila) => <li key={fila.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3"><div><p className="font-medium">{fila.prestacion_nombre} · {fila.institucion_nombre}</p><p className="text-sm text-texto-debil"><EstadoAutorizacion estado={fila.estado} /> · Plazo de respuesta: {fila.plazo_respuesta ? fechaHora(fila.plazo_respuesta) : "Sin plazo"}</p></div><Button size="sm" variant="secondary" onClick={() => setDetalle(fila.id)}>Ver</Button></li>)}</ul>}</TarjetaFicha></section>
      <section aria-label="Cupos del período"><TarjetaFicha titulo="Cupos del período" icono="calendar" cuerpoClassName="overflow-x-auto p-0">{!ficha.data.cupos?.length ? <EstadoVacio titulo="No hay cupos con tope para este plan" /> : <table className="w-full text-left text-sm"><thead className="border-b border-division bg-superficie-2 text-texto-debil"><tr>{["Prestación", "Período", "Tope", "Usado", "Disponible"].map((label) => <th key={label} scope="col" className="px-4 py-3">{label}</th>)}</tr></thead><tbody>{ficha.data.cupos.map((cupo) => <tr key={cupo.prestacion.codigo} className="border-b border-division"><td className="px-4 py-3">{cupo.prestacion.nombre}<p className="text-xs text-texto-debil">{cupo.prestacion.codigo}</p></td><td className="px-4 py-3">{cupo.periodo === "mes" ? "Mes" : "Año"} calendario · {fecha(cupo.desde)} a {fechaFin(cupo.hasta_exclusivo)}</td><td className="px-4 py-3">{cupo.tope}</td><td className="px-4 py-3">{cupo.usado}</td><td className="px-4 py-3 font-semibold">{cupo.disponible}</td></tr>)}</tbody></table>}</TarjetaFicha></section>
      <section aria-label="Prestaciones"><TarjetaFicha titulo="Prestaciones" icono="activity" cuerpoClassName="p-0" accion={<Button size="sm" variant="secondary" disabled={descargando || ficha.isFetching || !filas.length || ficha.data.count > ficha.data.limite_exportacion} onClick={exportar}><Icon name="download" size={15} />{descargando ? "Exportando…" : "Exportar CSV"}</Button>}>
        {errorDescarga && <div className="p-4"><ErrorFicha error={errorDescarga} /></div>}
        {!filas.length ? <EstadoVacio titulo="No hay prestaciones visibles" /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b border-division bg-superficie-2 text-texto-debil"><tr>{["Fecha", "Prestación", "Hospital", "Estado", "Alcance"].map((label) => <th key={label} scope="col" className="px-4 py-3">{label}</th>)}</tr></thead><tbody>{filas.map((fila) => <tr key={fila.id} className="border-b border-division"><td className="px-4 py-3">{fecha(fila.fecha)}</td><td className="px-4 py-3">{fila.prestacion}<p className="text-xs text-texto-debil">{fila.codigo}</p></td><td className="px-4 py-3">{fila.hospital}</td><td className="px-4 py-3">{ESTADOS[fila.estado] || fila.estado}</td><td className="px-4 py-3">{fila.acceso === "pendiente_historico" ? <Badge tone="amber">Histórico pendiente</Badge> : "Relación vigente"}</td></tr>)}</tbody></table></div>}
          <div className="flex items-center justify-between border-t border-division px-5 py-3 text-sm text-texto-debil"><span>{ficha.data.count} prestaciones · Página {pagina}</span><div className="flex gap-2"><Button size="sm" variant="secondary" disabled={pagina <= 1} onClick={() => cambiarPagina("page", pagina - 1)}>Anterior</Button><Button size="sm" variant="secondary" disabled={!ficha.data.next} onClick={() => cambiarPagina("page", pagina + 1)}>Siguiente</Button></div></div></TarjetaFicha></section>
      <section aria-label="Autorizaciones"><TarjetaFicha titulo="Autorizaciones" icono="shieldCheck" cuerpoClassName="p-0">{autorizaciones.isLoading ? <Spinner label="Consultando autorizaciones…" /> : autorizaciones.error ? <ErrorFicha error={autorizaciones.error} reintentar={autorizaciones.refetch} /> : <>{!filasAutorizaciones.length ? <EstadoVacio titulo="No hay autorizaciones visibles" /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b border-division bg-superficie-2 text-texto-debil"><tr>{["Prestación", "Hospital", "Estado", "Solicitada", ""].map((label) => <th key={label} scope="col" className="px-4 py-3">{label}</th>)}</tr></thead><tbody>{filasAutorizaciones.map((fila) => <tr key={fila.id} className="border-b border-division"><td className="px-4 py-3">{fila.prestacion_nombre}<p className="text-xs text-texto-debil">{fila.codigo} · {fila.cantidad_solicitada} unidades</p></td><td className="px-4 py-3">{fila.institucion_nombre}</td><td className="px-4 py-3"><EstadoAutorizacion estado={fila.estado} /></td><td className="px-4 py-3">{fechaHora(fila.creado)}</td><td className="px-4 py-3"><Button size="sm" variant="secondary" onClick={() => setDetalle(fila.id)}>Ver</Button></td></tr>)}</tbody></table></div>}<PaginasAutorizacion consulta={autorizaciones} pagina={paginaAutorizaciones} cambiar={(valor) => cambiarPagina("autorizaciones_page", valor)} /></>}</TarjetaFicha></section>
    </>)}
    </div>
    {detalle && <DetalleAutorizacion id={detalle} ambito={{ financiador: id }} scope={scope} onClose={() => setDetalle(null)} onVerSolicitud={setDetalle} onGuardado={guardado} />}
    </>}
  </div></Shell>;
}
