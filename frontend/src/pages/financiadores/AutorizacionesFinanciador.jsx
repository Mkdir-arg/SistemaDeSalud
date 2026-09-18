import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import { Ayuda, Badge, Button, Card, Field, Input, Select, Spinner } from "@/components/ui";
import { EstadoVacio } from "@/components/ui/estados";
import { fechaHora } from "@/lib/format";
import DetalleAutorizacion, { ErrorAutorizacion, EstadoAutorizacion, ESTADOS_AUTORIZACION, PaginasAutorizacion } from "./DetalleAutorizacion";
import { POR_PAGINA } from "@/api/queries";

const CAMPOS = ["estado", "hospital", "urgente", "desde", "hasta", "search"];
const VACIOS = Object.fromEntries(CAMPOS.map((campo) => [campo, ""]));

export default function AutorizacionesFinanciador({ organizacion, scope }) {
  const [parametros, setParametros] = useSearchParams();
  const qc = useQueryClient();
  const filtros = Object.fromEntries(CAMPOS.map((campo) => [campo, parametros.get(campo) || ""]));
  const filtrosClave = JSON.stringify(filtros);
  const [borrador, setBorrador] = useState(filtros);
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
  function aplicar(valores, page = 1) {
    const nuevos = new URLSearchParams({ financiador: organizacion.id });
    Object.entries(valores).forEach(([campo, valor]) => { if (valor) nuevos.set(campo, valor); });
    if (page > 1) nuevos.set("page", page);
    setParametros(nuevos);
  }
  async function guardado(texto) {
    setDetalle(null); setMensaje(texto);
    await qc.invalidateQueries({ queryKey: scope });
  }
  return <div className="space-y-4">
    {mensaje && <p role="status" className="rounded-md bg-badge-green-bg p-3 text-sm text-badge-green-fg">{mensaje}</p>}
    <Card className="overflow-hidden">
      <form className="space-y-3 border-b border-division p-4" onSubmit={(event) => { event.preventDefault(); aplicar({ ...borrador, search: borrador.search.trim() }); }}>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <Field label="Estado de autorización"><Select value={borrador.estado} onChange={editar("estado")}><option value="">Todos los estados</option>{Object.entries(ESTADOS_AUTORIZACION).map(([valor, nombre]) => <option key={valor} value={valor}>{nombre}</option>)}</Select></Field>
          <Field label="Hospital solicitante"><Select value={borrador.hospital} onChange={editar("hospital")}><option value="">Todos los hospitales</option>{borrador.hospital && !(consulta.data?.opciones?.instituciones || []).some((h) => String(h.id) === borrador.hospital) && <option value={borrador.hospital}>Hospital {borrador.hospital}</option>}{(consulta.data?.opciones?.instituciones || []).map((h) => <option key={h.id} value={h.id}>{h.nombre}</option>)}</Select></Field>
          <Field label="Urgencia"><Select value={borrador.urgente} onChange={editar("urgente")}><option value="">Todas</option><option value="true">Urgentes</option><option value="false">No urgentes</option></Select></Field>
          <Field label="Solicitada desde"><Input type="date" value={borrador.desde} onChange={editar("desde")} /></Field>
          <Field label="Solicitada hasta"><Input type="date" min={borrador.desde || undefined} value={borrador.hasta} onChange={editar("hasta")} /></Field>
          <Field label="Buscar afiliado o referencia" ayuda="El período corresponde a la fecha de solicitud. El plazo de respuesta y la vigencia de una aprobación se muestran por separado."><Input maxLength={120} value={borrador.search} onChange={editar("search")} /></Field>
        </div>
        <div className="flex flex-wrap items-center gap-2"><Button type="submit" disabled={consulta.isFetching}>Aplicar filtros</Button><Button type="button" variant="ghost" onClick={() => aplicar(VACIOS)}>Limpiar filtros</Button><Button type="button" variant="ghost" disabled={consulta.isFetching} onClick={() => consulta.refetch()}>Actualizar bandeja</Button>{JSON.stringify(borrador) !== filtrosClave && <span role="status" className="text-sm text-texto-debil">Hay filtros sin aplicar.</span>}</div>
      </form>
      {consulta.isLoading ? <Spinner label="Consultando autorizaciones…" /> : consulta.error ? <div className="p-4"><ErrorAutorizacion error={consulta.error} reintentar={consulta.refetch} />{pagina > 1 && <Button className="mt-3" variant="secondary" onClick={() => aplicar(filtros)}>Volver a la primera página</Button>}</div> : <>
        {!filas.length ? <EstadoVacio titulo="No hay solicitudes para estos filtros" detalle="Las solicitudes de los hospitales aparecerán en esta bandeja." /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b border-division bg-superficie-2 text-texto-debil"><tr>{["Solicitud", "Hospital", "Afiliado", "Prestación", "Estado", "Plazo de respuesta", "Acción"].map((nombre) => <th key={nombre} scope="col" className="whitespace-nowrap px-4 py-3 font-semibold">{nombre}</th>)}</tr></thead><tbody>{filas.map((fila) => <tr key={fila.id} className="border-b border-division last:border-0">
          <td className="px-4 py-3 align-top"><span className="font-semibold">#{fila.id}</span><p className="mt-1 text-texto-debil">{fechaHora(fila.creado)}</p>{fila.urgente && <Badge tone="error">Urgente</Badge>}</td>
          <td className="px-4 py-3 align-top">{fila.institucion_nombre}</td>
          <td className="px-4 py-3 align-top">{fila.afiliado_nombre}<p className="mt-1 text-texto-debil">N.º {fila.afiliado_numero}</p></td>
          <td className="px-4 py-3 align-top">{fila.prestacion_nombre}<p className="mt-1 text-texto-debil">{fila.cantidad_solicitada} unidades solicitadas</p></td>
          <td className="px-4 py-3 align-top"><EstadoAutorizacion estado={fila.estado} /></td>
          <td className="px-4 py-3 align-top">{fila.plazo_respuesta ? fechaHora(fila.plazo_respuesta) : "Sin vencimiento automático"}</td>
          <td className="px-4 py-3 align-top"><Button size="sm" variant="secondary" onClick={() => setDetalle(fila.id)}>Ver solicitud {fila.id}</Button></td>
        </tr>)}</tbody></table></div>}
        <PaginasAutorizacion consulta={consulta} pagina={pagina} cambiar={(page) => aplicar(filtros, page)} />
      </>}
    </Card>
    {detalle && <DetalleAutorizacion id={detalle} ambito={{ financiador: organizacion.id }} scope={scope} onClose={() => setDetalle(null)} onVerSolicitud={setDetalle} onGuardado={guardado} />}
  </div>;
}
