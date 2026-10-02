import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useLocation, useParams, useSearchParams } from "react-router-dom";
import { api } from "@/api/client";
import { errorFinanciador, filasDe, rutaFinanciador } from "@/api/financiadores";
import { POR_PAGINA } from "@/api/queries";
import { useAuth } from "@/auth/AuthContext";
import { Badge, Button, Card, Spinner } from "@/components/ui";
import { EstadoVacio } from "@/components/ui/estados";
import { Shell } from "@/components/Shell";
import { fechaHora } from "@/lib/format";
import { importeARS } from "@/api/finanzas";
import DetalleAutorizacion, { EstadoAutorizacion, PaginasAutorizacion } from "./DetalleAutorizacion";
import { ESTADOS } from "./ActividadFinanciador";

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
  return <section id="historia-clinica" className="space-y-3 scroll-mt-8" aria-label="Historia clínica"><h2 className="text-lg font-semibold">Historia clínica</h2><p className="text-sm text-texto-debil">Evoluciones firmadas de los casos que ingresaron con tu cobertura en hospitales dentro de tu alcance. No incluye alergias, antecedentes, estudios ni recetas. Cada consulta queda registrada con tu motivo y la ve el hospital.</p>
    <Card className="p-4">{casos.isLoading ? <Spinner label="Consultando casos…" /> : casos.error ? <ErrorFicha error={casos.error} reintentar={casos.refetch} /> : !casos.data?.results?.length ? <EstadoVacio titulo="No hay casos alcanzados" /> : <div className="space-y-3">{casos.data.results.map((caso) => <div key={caso.id} className="rounded-md border border-division p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="font-medium">{caso.institucion.nombre} · Caso {caso.id}</p><p className="text-sm text-texto-debil">Ingreso {fechaHora(caso.creado)} · {caso.estado} · {caso.evoluciones_firmadas} evoluciones firmadas · {caso.acceso === "pendiente_historico" ? "Histórico pendiente" : "Relación vigente"}</p></div><Button size="sm" variant="secondary" onClick={() => { cerrar(); setCasoAbierto(caso.id); }}>Ver evoluciones</Button></div>
      {casoAbierto === caso.id && <div className="mt-4 border-t border-division pt-4">{evoluciones === null ? <form className="space-y-3" onSubmit={consultar}><label className="block text-sm font-medium" htmlFor={`motivo-${caso.id}`}>Motivo de consulta</label><textarea id={`motivo-${caso.id}`} className="w-full rounded-md border border-borde bg-superficie p-2" required minLength={10} maxLength={200} value={motivo} onChange={(e) => setMotivo(e.target.value)} /><p className="text-xs text-texto-debil">Entre 10 y 200 caracteres. Quedará registrado y visible para el hospital.</p>{error && <ErrorFicha error={error} />}<div className="flex gap-2"><Button type="submit" disabled={consultando || motivo.trim().length < 10 || motivo.trim().length > 200}>{consultando ? "Consultando…" : "Confirmar motivo"}</Button><Button type="button" variant="ghost" onClick={cerrar}>Cerrar</Button></div></form> : <div className="space-y-3"><Button size="sm" variant="ghost" onClick={cerrar}>Cerrar evoluciones</Button>{!evoluciones.length ? <EstadoVacio titulo="No hay evoluciones firmadas" /> : evoluciones.map((entrada) => <article key={entrada.id} className="rounded-md border border-division p-4"><h3 className="font-semibold">{entrada.titulo}</h3><p className="text-sm text-texto-debil">{fechaHora(entrada.fecha)} · {entrada.autor || "Autor no disponible"}{entrada.matricula && ` · Matrícula ${entrada.matricula}`}</p><p className="mt-3 whitespace-pre-wrap text-sm">{entrada.contenido}</p></article>)}</div>}</div>}</div>)}<div className="flex justify-end gap-2"><Button size="sm" variant="secondary" disabled={pagina <= 1} onClick={() => { cerrar(); setPagina(pagina - 1); }}>Anterior</Button><Button size="sm" variant="secondary" disabled={!casos.data.next} onClick={() => { cerrar(); setPagina(pagina + 1); }}>Siguiente</Button></div></div>}</Card>
  </section>;
}

export default function FichaAfiliado() {
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
  useEffect(() => { if (location.hash === "#historia-clinica" && ficha.data && organizacion?.consulta_historia_clinica) document.getElementById("historia-clinica")?.scrollIntoView(); }, [location.hash, ficha.data, organizacion?.consulta_historia_clinica]);
  const persona = ficha.data?.afiliado;
  const filas = ficha.data?.results || [];
  const filasAutorizaciones = autorizaciones.data?.results || [];
  const volver = `/financiadores/padron?${new URLSearchParams({ financiador: id || seleccion || "", ...Object.fromEntries(["plan", "estado", "search", "padron_page"].filter((campo) => parametros.has(campo)).map((campo) => [campo === "padron_page" ? "page" : campo, parametros.get(campo)])) })}`;

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

  return <Shell plataforma={plataforma} financiador={{ nombre: organizacion?.nombre || "HEN", titulo: "Ficha del afiliado", rol: organizacion?.rol || "Financiador", items: [{ key: "padron", label: "Padrón de afiliados", icon: "idCard", to: volver }] }}><div className="space-y-6 p-lg sm:p-[30px] xl:p-[40px]">
    <Link className="text-sm font-medium text-accent hover:underline" to={volver}>← Volver al padrón</Link>
    <h1 className="text-cifra font-bold">Ficha del afiliado</h1>
    {organizaciones.isLoading ? <Spinner label="Consultando financiador…" /> : organizaciones.error ? <ErrorFicha error={organizaciones.error} reintentar={organizaciones.refetch} /> : !organizacion ? <Card><EstadoVacio titulo="No tenés acceso al financiador seleccionado" /></Card> : ficha.isLoading ? <Spinner label="Consultando ficha…" /> : ficha.error ? <ErrorFicha error={ficha.error} reintentar={ficha.refetch} /> : <>
      <Card className="p-5"><h2 className="text-lg font-semibold">{persona.nombre}</h2><dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">{[["Documento", persona.documento], ["N.º de afiliado", persona.numero], ["Plan", persona.plan_nombre || "Sin plan"], ["Desde", fecha(persona.desde)], ["Finalizada", persona.finalizado_en ? fechaHora(persona.finalizado_en) : "—"], ["Estado", { vigente: "Vigente", finalizada: "Finalizada", futura: "Aún no vigente" }[persona.estado]]].map(([label, valor]) => <div key={label}><dt className="text-texto-debil">{label}</dt><dd className="mt-1 font-medium">{valor}</dd></div>)}</dl></Card>
      <section aria-label="Resumen de actividad" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">{[["Prestaciones realizadas", ficha.data.resumen?.realizadas ?? 0], ["Unidades cubiertas", ficha.data.resumen?.cubiertas_realizadas ?? 0], ["Importe a cargo del financiador", importeARS(ficha.data.resumen?.importe_asignado ?? "0.00")], ["Discrepancias", ficha.data.resumen?.discrepancias ?? 0], ["Importes pendientes", ficha.data.resumen?.importes_pendientes ?? 0]].map(([titulo, valor]) => <Card key={titulo} className="p-4"><p className="text-sm text-texto-debil">{titulo}</p><p className="mt-2 text-xl font-semibold tabular-nums">{valor}</p></Card>)}</section>
      <section aria-label="Autorizaciones pendientes" className="space-y-3"><h2 className="text-lg font-semibold">Autorizaciones pendientes</h2><Card className="p-4">{pendientes.isLoading ? <Spinner label="Consultando pendientes…" /> : pendientes.error ? <ErrorFicha error={pendientes.error} reintentar={pendientes.refetch} /> : !pendientes.data?.results?.length ? <EstadoVacio titulo="No hay autorizaciones pendientes" /> : <div className="space-y-2">{pendientes.data.results.map((fila) => <div key={fila.id} className="flex flex-wrap items-center justify-between gap-3 border-b border-division py-2"><div><p className="font-medium">{fila.prestacion_nombre} · {fila.institucion_nombre}</p><p className="text-sm text-texto-debil"><EstadoAutorizacion estado={fila.estado} /> · Plazo de respuesta: {fila.plazo_respuesta ? fechaHora(fila.plazo_respuesta) : "Sin plazo"}</p></div><Button size="sm" variant="secondary" onClick={() => setDetalle(fila.id)}>Ver</Button></div>)}</div>}</Card></section>
      <section aria-label="Cupos del período" className="space-y-3"><h2 className="text-lg font-semibold">Cupos del período</h2><Card className="overflow-x-auto">{!ficha.data.cupos?.length ? <EstadoVacio titulo="No hay cupos con tope para este plan" /> : <table className="w-full text-left text-sm"><thead className="border-b border-division bg-superficie-2 text-texto-debil"><tr>{["Prestación", "Período", "Tope", "Usado", "Disponible"].map((label) => <th key={label} scope="col" className="px-4 py-3">{label}</th>)}</tr></thead><tbody>{ficha.data.cupos.map((cupo) => <tr key={cupo.prestacion.codigo} className="border-b border-division"><td className="px-4 py-3">{cupo.prestacion.nombre}<p className="text-xs text-texto-debil">{cupo.prestacion.codigo}</p></td><td className="px-4 py-3">{cupo.periodo === "mes" ? "Mes" : "Año"} calendario · {fecha(cupo.desde)} a {fechaFin(cupo.hasta_exclusivo)}</td><td className="px-4 py-3">{cupo.tope}</td><td className="px-4 py-3">{cupo.usado}</td><td className="px-4 py-3 font-semibold">{cupo.disponible}</td></tr>)}</tbody></table>}</Card></section>
      <section aria-label="Historial de la afiliación" className="space-y-3"><h2 className="text-lg font-semibold">Historial de la afiliación</h2><Card className="p-4">{!ficha.data.historial?.length ? <EstadoVacio titulo="No hay cambios registrados" /> : <ol className="space-y-3">{ficha.data.historial.map((h, index) => <li key={`${h.registrado}-${index}`} className="border-b border-division pb-3 text-sm"><p className="font-medium">{({ actualizacion: "Actualización", finalizacion: "Finalización", reactivacion: "Reactivación" })[h.tipo] || h.tipo} · {fechaHora(h.registrado)}</p><p>{h.numero} · {h.plan_nombre || "Sin plan"} · Desde {fecha(h.desde)}</p>{h.motivo && <p>Motivo: {h.motivo}</p>}<p className="text-texto-debil">Registrado por {h.usuario_nombre}</p></li>)}</ol>}</Card></section>
      <section className="space-y-3" aria-label="Prestaciones"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">Prestaciones</h2><Button variant="secondary" disabled={descargando || ficha.isFetching || !filas.length || ficha.data.count > ficha.data.limite_exportacion} onClick={exportar}>{descargando ? "Exportando…" : "Exportar CSV"}</Button></div>
        {errorDescarga && <ErrorFicha error={errorDescarga} />}
        <Card className="overflow-hidden">{!filas.length ? <EstadoVacio titulo="No hay prestaciones visibles" /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b border-division bg-superficie-2 text-texto-debil"><tr>{["Fecha", "Prestación", "Hospital", "Estado", "Alcance"].map((label) => <th key={label} scope="col" className="px-4 py-3">{label}</th>)}</tr></thead><tbody>{filas.map((fila) => <tr key={fila.id} className="border-b border-division"><td className="px-4 py-3">{fecha(fila.fecha)}</td><td className="px-4 py-3">{fila.prestacion}<p className="text-xs text-texto-debil">{fila.codigo}</p></td><td className="px-4 py-3">{fila.hospital}</td><td className="px-4 py-3">{ESTADOS[fila.estado] || fila.estado}</td><td className="px-4 py-3">{fila.acceso === "pendiente_historico" ? <Badge tone="amber">Histórico pendiente</Badge> : "Relación vigente"}</td></tr>)}</tbody></table></div>}
          <div className="flex items-center justify-between border-t border-division p-4 text-sm"><span>{ficha.data.count} prestaciones · Página {pagina}</span><div className="flex gap-2"><Button size="sm" variant="secondary" disabled={pagina <= 1} onClick={() => cambiarPagina("page", pagina - 1)}>Anterior</Button><Button size="sm" variant="secondary" disabled={!ficha.data.next} onClick={() => cambiarPagina("page", pagina + 1)}>Siguiente</Button></div></div></Card></section>
      <section className="space-y-3" aria-label="Autorizaciones"><h2 className="text-lg font-semibold">Autorizaciones</h2><Card className="overflow-hidden">{autorizaciones.isLoading ? <Spinner label="Consultando autorizaciones…" /> : autorizaciones.error ? <ErrorFicha error={autorizaciones.error} reintentar={autorizaciones.refetch} /> : <>{!filasAutorizaciones.length ? <EstadoVacio titulo="No hay autorizaciones visibles" /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b border-division bg-superficie-2 text-texto-debil"><tr>{["Prestación", "Hospital", "Estado", "Solicitada", ""].map((label) => <th key={label} scope="col" className="px-4 py-3">{label}</th>)}</tr></thead><tbody>{filasAutorizaciones.map((fila) => <tr key={fila.id} className="border-b border-division"><td className="px-4 py-3">{fila.prestacion_nombre}<p className="text-xs text-texto-debil">{fila.codigo} · {fila.cantidad_solicitada} unidades</p></td><td className="px-4 py-3">{fila.institucion_nombre}</td><td className="px-4 py-3"><EstadoAutorizacion estado={fila.estado} /></td><td className="px-4 py-3">{fechaHora(fila.creado)}</td><td className="px-4 py-3"><Button size="sm" variant="secondary" onClick={() => setDetalle(fila.id)}>Ver</Button></td></tr>)}</tbody></table></div>}<PaginasAutorizacion consulta={autorizaciones} pagina={paginaAutorizaciones} cambiar={(valor) => cambiarPagina("autorizaciones_page", valor)} /></>}</Card></section>
      {organizacion.consulta_historia_clinica && <HistoriaFinanciador id={id} afiliado={afiliado} scope={scope} />}
      {detalle && <DetalleAutorizacion id={detalle} ambito={{ financiador: id }} scope={scope} onClose={() => setDetalle(null)} onVerSolicitud={setDetalle} onGuardado={guardado} />}
    </>}
  </div></Shell>;
}
