import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "@/api/client";
import { errorFinanciador, filasDe, rutaFinanciador } from "@/api/financiadores";
import { POR_PAGINA } from "@/api/queries";
import { useAuth } from "@/auth/AuthContext";
import { Badge, Button, Card, Spinner } from "@/components/ui";
import { EstadoVacio } from "@/components/ui/estados";
import { Shell } from "@/components/Shell";
import { fechaHora } from "@/lib/format";
import DetalleAutorizacion, { EstadoAutorizacion, PaginasAutorizacion } from "./DetalleAutorizacion";
import { ESTADOS } from "./ActividadFinanciador";

const fecha = (valor) => valor ? String(valor).slice(0, 10).split("-").reverse().join("/") : "—";

function ErrorFicha({ error, reintentar }) {
  return <div role="alert" className="rounded-md bg-badge-error-bg p-4 text-badge-error-fg"><p>{errorFinanciador(error)}</p>{reintentar && <Button className="mt-3" size="sm" variant="secondary" onClick={reintentar}>Reintentar</Button>}</div>;
}

export default function FichaAfiliado() {
  const { afiliado } = useParams();
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
      <section className="space-y-3" aria-label="Prestaciones"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">Prestaciones</h2><Button variant="secondary" disabled={descargando || ficha.isFetching || !filas.length || ficha.data.count > ficha.data.limite_exportacion} onClick={exportar}>{descargando ? "Exportando…" : "Exportar CSV"}</Button></div>
        {errorDescarga && <ErrorFicha error={errorDescarga} />}
        <Card className="overflow-hidden">{!filas.length ? <EstadoVacio titulo="No hay prestaciones visibles" /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b border-division bg-superficie-2 text-texto-debil"><tr>{["Fecha", "Prestación", "Hospital", "Estado", "Alcance"].map((label) => <th key={label} scope="col" className="px-4 py-3">{label}</th>)}</tr></thead><tbody>{filas.map((fila) => <tr key={fila.id} className="border-b border-division"><td className="px-4 py-3">{fecha(fila.fecha)}</td><td className="px-4 py-3">{fila.prestacion}<p className="text-xs text-texto-debil">{fila.codigo}</p></td><td className="px-4 py-3">{fila.hospital}</td><td className="px-4 py-3">{ESTADOS[fila.estado] || fila.estado}</td><td className="px-4 py-3">{fila.acceso === "pendiente_historico" ? <Badge tone="amber">Histórico pendiente</Badge> : "Relación vigente"}</td></tr>)}</tbody></table></div>}
          <div className="flex items-center justify-between border-t border-division p-4 text-sm"><span>{ficha.data.count} prestaciones · Página {pagina}</span><div className="flex gap-2"><Button size="sm" variant="secondary" disabled={pagina <= 1} onClick={() => cambiarPagina("page", pagina - 1)}>Anterior</Button><Button size="sm" variant="secondary" disabled={!ficha.data.next} onClick={() => cambiarPagina("page", pagina + 1)}>Siguiente</Button></div></div></Card></section>
      <section className="space-y-3" aria-label="Autorizaciones"><h2 className="text-lg font-semibold">Autorizaciones</h2><Card className="overflow-hidden">{autorizaciones.isLoading ? <Spinner label="Consultando autorizaciones…" /> : autorizaciones.error ? <ErrorFicha error={autorizaciones.error} reintentar={autorizaciones.refetch} /> : <>{!filasAutorizaciones.length ? <EstadoVacio titulo="No hay autorizaciones visibles" /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b border-division bg-superficie-2 text-texto-debil"><tr>{["Prestación", "Hospital", "Estado", "Solicitada", ""].map((label) => <th key={label} scope="col" className="px-4 py-3">{label}</th>)}</tr></thead><tbody>{filasAutorizaciones.map((fila) => <tr key={fila.id} className="border-b border-division"><td className="px-4 py-3">{fila.prestacion_nombre}<p className="text-xs text-texto-debil">{fila.codigo} · {fila.cantidad_solicitada} unidades</p></td><td className="px-4 py-3">{fila.institucion_nombre}</td><td className="px-4 py-3"><EstadoAutorizacion estado={fila.estado} /></td><td className="px-4 py-3">{fechaHora(fila.creado)}</td><td className="px-4 py-3"><Button size="sm" variant="secondary" onClick={() => setDetalle(fila.id)}>Ver</Button></td></tr>)}</tbody></table></div>}<PaginasAutorizacion consulta={autorizaciones} pagina={paginaAutorizaciones} cambiar={(valor) => cambiarPagina("autorizaciones_page", valor)} /></>}</Card></section>
      {detalle && <DetalleAutorizacion id={detalle} ambito={{ financiador: id }} scope={scope} onClose={() => setDetalle(null)} onVerSolicitud={setDetalle} onGuardado={guardado} />}
    </>}
  </div></Shell>;
}
