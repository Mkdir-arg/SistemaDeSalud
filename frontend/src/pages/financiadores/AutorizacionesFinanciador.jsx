import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import { Ayuda, Badge, Button, Card, Field, Input, Select, Spinner } from "@/components/ui";
import { EstadoVacio } from "@/components/ui/estados";
import { fechaHora } from "@/lib/format";
import DetalleAutorizacion, { ErrorAutorizacion, EstadoAutorizacion, ESTADOS_AUTORIZACION, PaginasAutorizacion } from "./DetalleAutorizacion";
import { POR_PAGINA } from "@/api/queries";

const CAMPOS = ["estado", "grupo", "hospital", "urgente", "desde", "hasta", "search"];
const VACIOS = Object.fromEntries(CAMPOS.map((campo) => [campo, ""]));

export default function AutorizacionesFinanciador({ organizacion, scope }) {
  const [parametros, setParametros] = useSearchParams();
  const qc = useQueryClient();
  const filtros = Object.fromEntries(CAMPOS.map((campo) => [campo, parametros.get(campo) || ""]));
  if (!CAMPOS.some((campo) => parametros.has(campo))) filtros.estado = "pendiente";
  const filtrosClave = JSON.stringify(filtros);
  const [borrador, setBorrador] = useState(filtros);
  const [masFiltros, setMasFiltros] = useState(false);
  const [detalle, setDetalle] = useState(null);
  const [mensaje, setMensaje] = useState("");
  const n = Number(parametros.get("page") || 1);
  const pagina = Number.isSafeInteger(n) && n > 0 ? n : 1;
  const query = new URLSearchParams({ financiador: organizacion.id, page: pagina, page_size: POR_PAGINA });
  Object.entries(filtros).forEach(([campo, valor]) => { if (valor) query.set(campo, valor); });
  const consulta = useQuery({
    queryKey: [...scope, "autorizaciones", query.toString()],
    queryFn: () => api.get(`/autorizaciones-cobertura/?${query}`),
    gcTime: 0, retry: false,
  });
  useEffect(() => { setBorrador(JSON.parse(filtrosClave)); }, [filtrosClave]);
  const editar = (campo) => (event) => setBorrador((anterior) => ({ ...anterior, [campo]: event.target.value }));
  const filas = consulta.data?.results || [];
  const pestaña = filtros.grupo === "resueltas" ? "resueltas" : filtros.estado === "pendiente" ? "pendiente" : filtros.estado === "observada" ? "observada" : "todas";
  function aplicar(valores, page = 1) {
    const nuevos = new URLSearchParams({ financiador: organizacion.id });
    Object.entries(valores).forEach(([campo, valor]) => { if (valor) nuevos.set(campo, valor); });
    if (page > 1) nuevos.set("page", page);
    setParametros(nuevos);
  }
  function cambiarPestaña(valor) {
    aplicar({ ...filtros, estado: ["pendiente", "observada"].includes(valor) ? valor : "", grupo: ["resueltas", "todas"].includes(valor) ? valor : "" });
  }
  async function guardado(texto) {
    setDetalle(null); setMensaje(texto);
    await qc.invalidateQueries({ queryKey: scope });
  }
  return <div className="space-y-5">
    {mensaje && <p role="status" className="rounded-md bg-badge-green-bg p-3 text-sm text-badge-green-fg">{mensaje}</p>}
    <div aria-label="Estado de autorizaciones" className="flex flex-wrap gap-6 border-b border-division">{[["pendiente", "Pendientes"], ["observada", "Observadas"], ["resueltas", "Resueltas"], ["todas", "Todas"]].map(([valor, nombre]) => <button key={valor} type="button" aria-pressed={pestaña === valor} onClick={() => cambiarPestaña(valor)} className={`border-b-2 pb-3 text-sm font-medium ${pestaña === valor ? "border-accent text-accent" : "border-transparent text-texto-suave hover:text-texto"}`}>{nombre}</button>)}</div>
    <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); aplicar({ ...borrador, search: borrador.search.trim() }); }}>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-[1.4fr_1fr_1fr_auto]">
        <Input aria-label="Buscar afiliado o referencia" placeholder="Buscar afiliado o referencia" maxLength={120} value={borrador.search} onChange={editar("search")} />
        <Select aria-label="Hospital solicitante" value={borrador.hospital} onChange={editar("hospital")}><option value="">Hospital: todos</option>{borrador.hospital && !(consulta.data?.opciones?.instituciones || []).some((h) => String(h.id) === borrador.hospital) && <option value={borrador.hospital}>Hospital {borrador.hospital}</option>}{(consulta.data?.opciones?.instituciones || []).map((h) => <option key={h.id} value={h.id}>{h.nombre}</option>)}</Select>
        <Select aria-label="Urgencia" value={borrador.urgente} onChange={editar("urgente")}><option value="">Urgencia: todas</option><option value="true">Urgentes</option><option value="false">No urgentes</option></Select>
        <button type="button" className="text-sm font-medium text-accent hover:underline" aria-expanded={masFiltros} onClick={() => setMasFiltros((valor) => !valor)}>Más filtros</button>
      </div>
      {masFiltros && <div className="grid gap-3 rounded-md border border-borde bg-superficie p-4 sm:grid-cols-3"><Field label="Estado de autorización"><Select value={borrador.estado} onChange={(event) => setBorrador((previo) => ({ ...previo, estado: event.target.value, grupo: "" }))}><option value="">Todos los estados</option>{Object.entries(ESTADOS_AUTORIZACION).map(([valor, nombre]) => <option key={valor} value={valor}>{nombre}</option>)}</Select></Field><Field label="Solicitada desde"><Input type="date" value={borrador.desde} onChange={editar("desde")} /></Field><Field label="Solicitada hasta"><Input type="date" min={borrador.desde || undefined} value={borrador.hasta} onChange={editar("hasta")} /></Field></div>}
      <div className="flex flex-wrap items-center gap-2"><Button type="submit" disabled={consulta.isFetching}>Aplicar filtros</Button><Button type="button" variant="ghost" onClick={() => aplicar({ ...VACIOS, estado: "pendiente" })}>Limpiar filtros</Button><Button type="button" variant="ghost" disabled={consulta.isFetching} onClick={() => consulta.refetch()}>Actualizar bandeja</Button>{JSON.stringify(borrador) !== filtrosClave && <span role="status" className="text-sm text-texto-debil">Hay filtros sin aplicar.</span>}</div>
    </form>
    <Card className="overflow-hidden">{consulta.isLoading ? <Spinner label="Consultando autorizaciones…" /> : consulta.error ? <div className="p-4"><ErrorAutorizacion error={consulta.error} reintentar={consulta.refetch} />{pagina > 1 && <Button className="mt-3" variant="secondary" onClick={() => aplicar(filtros)}>Volver a la primera página</Button>}</div> : <>
      {!filas.length ? <EstadoVacio titulo="No hay solicitudes para estos filtros" detalle="Las solicitudes de los hospitales aparecerán en esta bandeja." /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b border-division bg-superficie-2 text-texto-debil"><tr>{["Afiliado", "Prestación", "Hospital", "Solicitada", "Urgencia", ""].map((nombre) => <th key={nombre} scope="col" className="px-4 py-3 font-semibold">{nombre}</th>)}</tr></thead><tbody>{filas.map((fila) => <tr key={fila.id} className="border-b border-division last:border-0">
        <td className="px-4 py-3 align-top"><span className="font-medium text-texto">{fila.afiliado_nombre}</span><p className="mt-1 text-xs text-texto-debil">{fila.afiliado_numero}</p></td>
        <td className="px-4 py-3 align-top">{fila.prestacion_nombre}<p className="mt-1 text-xs text-texto-debil">{fila.cantidad_solicitada} unidades · <EstadoAutorizacion estado={fila.estado} /></p></td>
        <td className="px-4 py-3 align-top">{fila.institucion_nombre}</td>
        <td className="px-4 py-3 align-top">{fechaHora(fila.creado)}</td>
        <td className="px-4 py-3 align-top"><Badge tone={fila.urgente ? "error" : "gray"}>{fila.urgente ? "Urgente" : "No urgente"}</Badge></td>
        <td className="px-4 py-3 align-top"><Button size="sm" variant="secondary" onClick={() => setDetalle(fila.id)}>{["pendiente", "observada"].includes(fila.estado) ? "Revisar" : "Ver"}</Button></td>
      </tr>)}</tbody></table></div>}
      <PaginasAutorizacion consulta={consulta} pagina={pagina} cambiar={(page) => aplicar(filtros, page)} />
    </>}</Card>
    {detalle && <DetalleAutorizacion id={detalle} ambito={{ financiador: organizacion.id }} scope={scope} onClose={() => setDetalle(null)} onVerSolicitud={setDetalle} onGuardado={guardado} />}
  </div>;
}
