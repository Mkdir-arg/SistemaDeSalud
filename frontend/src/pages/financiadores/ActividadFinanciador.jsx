import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "@/api/client";
import { errorFinanciador, rutaFinanciador } from "@/api/financiadores";
import { importeARS } from "@/api/finanzas";
import { Ayuda, Badge, Button, Card, Field, Input, Select, Spinner } from "@/components/ui";
import { EstadoVacio } from "@/components/ui/estados";
import { fechaHora, plural } from "@/lib/format";
import { POR_PAGINA } from "@/api/queries";

const CAMPOS = ["desde", "hasta", "institucion", "plan", "sin_plan", "prestacion", "estado", "discrepancia", "search"];
const VACIOS = Object.fromEntries(CAMPOS.map((campo) => [campo, ""]));
const ESTADOS = { reservada: "Reservada", realizada: "Realizada", liberada: "Liberada" };
const DISTRIBUCIONES = { autorizacion_pendiente: "Autorización pendiente", resuelta: "Responsable definido", pendiente: "Pendiente de resolución", arancel_pendiente: "Arancel pendiente", evaluacion_pendiente: "Evaluación pendiente", sin_cobro: "Sin cobro" };
const fecha = (valor) => valor ? String(valor).slice(0, 10).split("-").reverse().join("/") : "—";

function mesActual() {
  const hoy = new Date();
  const mes = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}`;
  return { ...VACIOS, desde: `${mes}-01`, hasta: `${mes}-${new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0).getDate()}` };
}

function filtrosDe(parametros) {
  // Las fechas vacías explícitas conservan "todos los períodos" al recargar.
  const iniciales = CAMPOS.some((campo) => parametros.has(campo)) ? VACIOS : mesActual();
  return Object.fromEntries(CAMPOS.map((campo) => [campo, parametros.get(campo) ?? iniciales[campo]]));
}

function queryDe(filtros) {
  return new URLSearchParams(Object.entries(filtros).filter(([, valor]) => valor !== ""));
}

function ErrorActividad({ error, reintentar }) {
  return <div role="alert" className="rounded-md border border-borde bg-badge-error-bg p-4 text-badge-error-fg">
    <p>{errorFinanciador(error)}</p>
    {reintentar && <Button className="mt-3" size="sm" variant="secondary" onClick={reintentar}>Reintentar</Button>}
  </div>;
}

function SelectorActividad({ label, value, onChange, opciones = [], todas }) {
  const faltaSeleccion = value && !opciones.some((item) => String(item.id) === value);
  return <Field label={label}><Select value={value} onChange={onChange}>
    <option value="">{todas}</option>
    {faltaSeleccion && <option value={value}>Selección {value}</option>}
    {opciones.map((item) => <option key={item.id} value={item.id}>{item.codigo ? `${item.codigo} · ` : ""}{item.nombre}</option>)}
  </Select></Field>;
}

function ResumenActividad({ resumen, generado }) {
  if (!resumen) return <p role="status" className="p-4 text-sm text-texto-debil">El resumen no está disponible.</p>;
  return <div className="border-b border-division p-4 sm:p-5" aria-label="Resumen de actividad">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div><div className="flex items-center gap-2"><h3 className="font-semibold">Total del conjunto filtrado</h3><Ayuda><span className="block">Incluye todas las páginas.</span><span className="mt-2 block">Sólo suma prestaciones realizadas con importe conocido e incluye acuerdos posteriores. No descuenta pagos ni ajustes y no representa el saldo pendiente. Las reservas y los importes pendientes quedan fuera del total.</span></Ayuda></div></div>
      <div className="sm:text-right"><p className="text-sm text-texto-debil">Importe original asignado al financiador</p><p className="mt-1 text-xl font-semibold tabular-nums">{importeARS(resumen.importe_asignado)}</p></div>
    </div>
    <dl className="mt-4 grid grid-cols-2 gap-x-5 gap-y-3 text-sm sm:grid-cols-4">
      {[["Registros", resumen.registros], ["Reservadas", resumen.reservadas], ["Realizadas", resumen.realizadas], ["Liberadas", resumen.liberadas], ["Cantidad realizada", resumen.cantidad_realizada], ["Unidades cubiertas realizadas", resumen.cubiertas_realizadas], ["Con discrepancias", resumen.discrepancias], ["Importes pendientes", resumen.importes_pendientes]].map(([label, valor]) => <div key={label}><dt className="text-texto-debil">{label}</dt><dd className="mt-1 font-semibold tabular-nums">{valor ?? "—"}</dd></div>)}
    </dl>
    {generado && <p className="mt-2 text-sm text-texto-tenue">Consultado el {fechaHora(generado)}. La exportación vuelve a consultar los datos y el acceso vigente.</p>}
  </div>;
}

const COLUMNAS = [
  { key: "fecha", label: "Fecha", render: (r) => fecha(r.fecha) },
  { key: "hospital", label: "Hospital" },
  { key: "nombre", label: "Afiliado", render: (r) => <><div>{r.nombre || "—"}</div><div className="mt-1 whitespace-nowrap text-texto-debil">N.º {r.numero} · DNI {r.documento}</div></> },
  { key: "plan", label: "Plan registrado" },
  { key: "prestacion", label: "Prestación", render: (r) => <>{r.prestacion}{r.codigo && <div className="mt-1 text-texto-debil">{r.codigo}</div>}</> },
  { key: "cantidad", label: "Cantidad" },
  { key: "cubiertas", label: "Unidades cubiertas" },
  { key: "estado", label: "Estado", render: (r) => ESTADOS[r.estado] || r.estado },
  { key: "importe_asignado", label: "Importe asignado", render: (r) => r.estado !== "realizada" ? "—" : r.importe_asignado == null ? <Badge tone="amber">Importe pendiente</Badge> : <><div className="whitespace-nowrap tabular-nums">{importeARS(r.importe_asignado)}</div>{Number(r.importe_acuerdos) > 0 && <div className="mt-1 text-texto-debil">Incluye {importeARS(r.importe_acuerdos)} de acuerdos</div>}</> },
  { key: "estado_cobro", label: "Distribución del cobro", render: (r) => DISTRIBUCIONES[r.estado_cobro] || "Al realizar la prestación" },
  { key: "discrepancia", label: "Revisión", render: (r) => r.discrepancia ? <Badge tone="amber">Discrepancia</Badge> : "—" },
  { key: "acceso", label: "Alcance del acceso", render: (r) => r.acceso === "pendiente_historico" ? <Badge tone="amber">Histórico pendiente</Badge> : r.acceso === "vigente" ? "Relación vigente" : "—" },
];

export default function ActividadFinanciador({ organizacion, scope }) {
  const [parametros, setParametros] = useSearchParams();
  const aplicados = filtrosDe(parametros);
  const filtrosClave = JSON.stringify(aplicados);
  const [borrador, setBorrador] = useState(aplicados);
  const [errorDescarga, setErrorDescarga] = useState(null);
  const [descargando, setDescargando] = useState(false);
  const paginaSolicitada = Number(parametros.get("page") || 1);
  const page = Number.isSafeInteger(paginaSolicitada) && paginaSolicitada > 0 ? paginaSolicitada : 1;
  const filtrosQuery = queryDe(aplicados);
  const query = new URLSearchParams(filtrosQuery);
  query.set("page", page);
  query.set("page_size", POR_PAGINA);
  const consulta = useQuery({ queryKey: [...scope, "actividad", query.toString()], queryFn: () => api.get(`${rutaFinanciador(organizacion.id, "actividad")}?${query}`), gcTime: 0 });
  const opciones = consulta.data?.opciones || {};
  const filas = consulta.data?.results || [];
  const cambiosPendientes = JSON.stringify(borrador) !== filtrosClave;
  const limite = consulta.data?.limite_exportacion;
  const superaLimite = limite != null && consulta.data?.count > limite;

  useEffect(() => { setBorrador(JSON.parse(filtrosClave)); setErrorDescarga(null); }, [filtrosClave]);
  useEffect(() => {
    if (!CAMPOS.some((campo) => parametros.has(campo)) || !parametros.has("financiador")) {
      const nuevos = new URLSearchParams(parametros);
      nuevos.set("financiador", organizacion.id);
      for (const campo of CAMPOS) if (aplicados[campo] || campo === "desde" || campo === "hasta") nuevos.set(campo, aplicados[campo]);
      setParametros(nuevos, { replace: true });
    }
  }, [parametros, organizacion.id, setParametros, filtrosClave]);

  function aplicar(filtros, nuevaPagina = 1) {
    const nuevos = new URLSearchParams({ financiador: organizacion.id });
    for (const campo of CAMPOS) if (filtros[campo] || campo === "desde" || campo === "hasta") nuevos.set(campo, filtros[campo]);
    if (nuevaPagina > 1) nuevos.set("page", nuevaPagina);
    setParametros(nuevos);
    setErrorDescarga(null);
  }
  function editar(campo) { return (event) => setBorrador((previo) => ({ ...previo, [campo]: event.target.value })); }
  async function exportar() {
    setDescargando(true); setErrorDescarga(null);
    try {
      const exportacion = new URLSearchParams(filtrosQuery);
      exportacion.set("formato", "csv");
      await api.download(`${rutaFinanciador(organizacion.id, "actividad")}?${exportacion}`, `actividad-financiador-${organizacion.id}.csv`);
    } catch (error) { setErrorDescarga(error); }
    finally { setDescargando(false); }
  }

  return <Card className="overflow-hidden">
    <form className="space-y-4 border-b border-division p-4 sm:p-5" onSubmit={(event) => { event.preventDefault(); aplicar({ ...borrador, search: borrador.search.trim() }); }}>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Field label="Desde"><Input type="date" value={borrador.desde} onChange={editar("desde")} /></Field>
        <Field label="Hasta"><Input type="date" min={borrador.desde || undefined} value={borrador.hasta} onChange={editar("hasta")} /></Field>
        <SelectorActividad label="Hospital" value={borrador.institucion} onChange={editar("institucion")} opciones={opciones.instituciones} todas="Todos los hospitales" />
        <SelectorActividad label="Plan registrado" value={borrador.sin_plan === "true" ? "sin_plan" : borrador.plan} onChange={(event) => { const valor = event.target.value; setBorrador((previo) => ({ ...previo, plan: valor === "sin_plan" ? "" : valor, sin_plan: valor === "sin_plan" ? "true" : "" })); }} opciones={[{ id: "sin_plan", nombre: "Sin plan" }, ...(opciones.planes || [])]} todas="Todos los planes" />
        <SelectorActividad label="Prestación" value={borrador.prestacion} onChange={editar("prestacion")} opciones={opciones.prestaciones} todas="Todas las prestaciones" />
        <Field label="Estado"><Select value={borrador.estado} onChange={editar("estado")}><option value="">Todos los estados</option>{Object.entries(ESTADOS).map(([id, nombre]) => <option key={id} value={id}>{nombre}</option>)}</Select></Field>
        <Field label="Discrepancias"><Select value={borrador.discrepancia} onChange={editar("discrepancia")}><option value="">Todas</option><option value="true">Con discrepancia</option><option value="false">Sin discrepancia</option></Select></Field>
        <Field label="Buscar afiliado o prestación" ayuda="El período corresponde a la fecha prevista de las reservas y a la fecha de realización de las prestaciones."><Input value={borrador.search} onChange={editar("search")} placeholder="Nombre, documento, número o prestación" maxLength={160} /></Field>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" disabled={consulta.isFetching}>Aplicar filtros</Button>
        <Button type="button" variant="ghost" onClick={() => aplicar(mesActual())}>Mes actual</Button>
        <Button type="button" variant="ghost" onClick={() => aplicar(VACIOS)}>Limpiar filtros</Button>
        {cambiosPendientes && <span role="status" className="text-sm text-texto-debil">Aplicá los cambios para actualizar la consulta y la exportación.</span>}
      </div>
    </form>
    {consulta.isLoading ? <Spinner label="Consultando actividad…" /> : consulta.error ? <div className="p-4"><ErrorActividad error={consulta.error} reintentar={consulta.refetch} /></div> : <>
      <ResumenActividad resumen={consulta.data?.resumen} generado={consulta.data?.generado_en} />
      <div className="space-y-3 border-b border-division p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="max-w-[42rem] text-sm text-texto-debil"><p>El CSV incluye todas las páginas con los filtros aplicados.{limite != null && ` Hasta ${Number(limite).toLocaleString("es-AR")} registros por descarga.`} La consulta y la exportación quedan auditadas.</p><p className="mt-1">Identificadores como texto e importes con coma decimal.</p></div>
          <Button variant="secondary" onClick={exportar} disabled={descargando || consulta.isFetching || cambiosPendientes || superaLimite || !filas.length}>{descargando ? "Exportando…" : "Exportar CSV"}</Button>
        </div>
        {superaLimite && <p role="status" className="text-sm text-badge-amber-fg">El resultado supera el límite de exportación. Acotá el período o los filtros para descargarlo completo.</p>}
        {errorDescarga && <ErrorActividad error={errorDescarga} />}
      </div>
      {filas.length === 0 ? <EstadoVacio titulo="No hay actividad con estos filtros" detalle="Probá con otro período, hospital o afiliado." /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b border-division bg-superficie-2 text-texto-debil"><tr>{COLUMNAS.map((columna) => <th key={columna.key} scope="col" className="whitespace-nowrap px-4 py-3 font-semibold">{columna.label}</th>)}</tr></thead><tbody>{filas.map((fila) => <tr key={fila.id} className="border-b border-division last:border-0">{COLUMNAS.map((columna) => <td key={columna.key} className="px-4 py-3 align-top">{columna.render ? columna.render(fila) : fila[columna.key] ?? "—"}</td>)}</tr>)}</tbody></table></div>}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-division px-4 py-3"><span className="text-sm text-texto-debil">{plural(consulta.data?.count ?? filas.length, "registro", "registros")} · Página {page}</span><div className="flex gap-2"><Button size="sm" variant="ghost" disabled={page === 1 || consulta.isFetching} onClick={() => aplicar(aplicados, page - 1)}>Anterior</Button><Button size="sm" variant="ghost" disabled={!consulta.data?.next || consulta.isFetching} onClick={() => aplicar(aplicados, page + 1)}>Siguiente</Button></div></div>
    </>}
  </Card>;
}
