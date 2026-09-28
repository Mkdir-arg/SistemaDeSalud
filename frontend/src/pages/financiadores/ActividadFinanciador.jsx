import { Fragment, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "@/api/client";
import { errorFinanciador, rutaFinanciador } from "@/api/financiadores";
import { importeARS } from "@/api/finanzas";
import { Badge, Button, Card, Checkbox, Field, Input, Select, Spinner } from "@/components/ui";
import { EstadoVacio } from "@/components/ui/estados";
import { fechaHora, plural } from "@/lib/format";
import { POR_PAGINA } from "@/api/queries";

const CAMPOS = ["desde", "hasta", "institucion", "plan", "sin_plan", "prestacion", "estado", "discrepancia", "search"];
const VACIOS = Object.fromEntries(CAMPOS.map((campo) => [campo, ""]));
const ESTADOS = { reservada: "Reservada", realizada: "Realizada", liberada: "Liberada" };
const DISTRIBUCIONES = { autorizacion_pendiente: "Autorización pendiente", resuelta: "Responsable definido", pendiente: "Pendiente de resolución", arancel_pendiente: "Arancel pendiente", evaluacion_pendiente: "Evaluación pendiente", sin_cobro: "Sin cobro" };
const fecha = (valor) => valor ? String(valor).slice(0, 10).split("-").reverse().join("/") : "—";

function intervaloMes(desplazamiento = 0) {
  const hoy = new Date();
  const primero = new Date(hoy.getFullYear(), hoy.getMonth() + desplazamiento, 1);
  const mes = `${primero.getFullYear()}-${String(primero.getMonth() + 1).padStart(2, "0")}`;
  return { desde: `${mes}-01`, hasta: `${mes}-${new Date(primero.getFullYear(), primero.getMonth() + 1, 0).getDate()}` };
}
const mesActual = () => ({ ...VACIOS, ...intervaloMes() });

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

function SelectorActividad({ label, value, onChange, opciones = [], todas, compacto = false }) {
  const faltaSeleccion = value && !opciones.some((item) => String(item.id) === value);
  const control = <Select aria-label={label} value={value} onChange={onChange}>
    <option value="">{todas}</option>
    {faltaSeleccion && <option value={value}>Selección {value}</option>}
    {opciones.map((item) => <option key={item.id} value={item.id}>{item.codigo ? `${item.codigo} · ` : ""}{item.nombre}</option>)}
  </Select>;
  return compacto ? control : <Field label={label}>{control}</Field>;
}

function ResumenActividad({ resumen, generado }) {
  if (!resumen) return <p role="status" className="text-sm text-texto-debil">El resumen no está disponible.</p>;
  const indicadores = [
    ["Importe asignado", importeARS(resumen.importe_asignado), "Arancel aplicable × cobertura"],
    ["Realizadas", resumen.realizadas ?? "—", `De ${resumen.registros ?? "—"} registros`],
    ["Reservas abiertas", resumen.reservadas ?? "—", "Pendientes de realización o liberación"],
    ["Con discrepancia", resumen.discrepancias ?? "—", "Requieren revisión"],
  ];
  return <section aria-label="Resumen de actividad"><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{indicadores.map(([label, valor, detalle]) => <Card key={label} className="p-5"><h3 className="text-sm text-texto-suave">{label}</h3><p className="mt-2 text-cifra font-bold tabular-nums">{valor}</p><p className="mt-1 text-xs text-texto-debil">{detalle}</p></Card>)}</div>
    <details className="mt-2 text-xs text-texto-debil"><summary className="cursor-pointer">Ver más indicadores y alcance del importe</summary><p className="mt-2">{resumen.liberadas ?? 0} liberadas · {resumen.cantidad_realizada ?? 0} unidades realizadas · {resumen.cubiertas_realizadas ?? 0} cubiertas · {resumen.importes_pendientes ?? 0} importes pendientes.</p><p className="mt-1">El importe suma prestaciones realizadas con valor conocido; incluye acuerdos posteriores y no representa un saldo pendiente.{generado && ` Consultado el ${fechaHora(generado)}.`}</p></details>
  </section>;
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
  const [mostrarFiltros, setMostrarFiltros] = useState(false);
  const [personalizar, setPersonalizar] = useState(false);
  const [detalle, setDetalle] = useState(null);
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
  const actual = intervaloMes();
  const anterior = intervaloMes(-1);
  const periodo = personalizar ? "personalizado" : aplicados.desde === actual.desde && aplicados.hasta === actual.hasta ? "actual" : aplicados.desde === anterior.desde && aplicados.hasta === anterior.hasta ? "anterior" : "personalizado";
  const filtrosAvanzadosActivos = Boolean(borrador.prestacion || borrador.search || borrador.discrepancia === "false");

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

  return <div className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><div role="group" aria-label="Período de actividad" className="flex flex-wrap rounded-md bg-superficie-2 p-1">{[["actual", "Mes actual", actual], ["anterior", "Mes anterior", anterior]].map(([id, nombre, fechas]) => <button key={id} type="button" aria-pressed={periodo === id} className={`rounded-sm px-3 py-2 text-sm ${periodo === id ? "bg-superficie font-semibold text-texto" : "text-texto-suave hover:text-texto"}`} onClick={() => { setPersonalizar(false); aplicar({ ...aplicados, ...fechas }); }}>{nombre}</button>)}<button type="button" aria-pressed={periodo === "personalizado"} className={`rounded-sm px-3 py-2 text-sm ${periodo === "personalizado" ? "bg-superficie font-semibold text-texto" : "text-texto-suave hover:text-texto"}`} onClick={() => { setPersonalizar(true); setMostrarFiltros(true); }}>Personalizado</button></div><Button variant="secondary" onClick={exportar} disabled={descargando || consulta.isFetching || superaLimite || cambiosPendientes || !filas.length}>{descargando ? "Exportando…" : "Exportar CSV"}</Button></div>
    <form className="space-y-3" onSubmit={(event) => { event.preventDefault(); setPersonalizar(false); aplicar({ ...borrador, search: borrador.search.trim() }); }}>
      <div className="grid items-center gap-3 sm:grid-cols-2 xl:grid-cols-[1fr_1fr_1fr_auto_auto]">
        <SelectorActividad compacto label="Hospital" value={borrador.institucion} onChange={editar("institucion")} opciones={opciones.instituciones} todas="Hospital: todos" />
        <SelectorActividad compacto label="Plan registrado" value={borrador.sin_plan === "true" ? "sin_plan" : borrador.plan} onChange={(event) => { const valor = event.target.value; setBorrador((previo) => ({ ...previo, plan: valor === "sin_plan" ? "" : valor, sin_plan: valor === "sin_plan" ? "true" : "" })); }} opciones={[{ id: "sin_plan", nombre: "Sin plan" }, ...(opciones.planes || [])]} todas="Plan: todos" />
        <Select aria-label="Estado" value={borrador.estado} onChange={editar("estado")}><option value="">Estado: todos</option>{Object.entries(ESTADOS).map(([id, nombre]) => <option key={id} value={id}>{nombre}</option>)}</Select>
        <Checkbox label="Solo con discrepancias" checked={borrador.discrepancia === "true"} onChange={(event) => setBorrador((previo) => ({ ...previo, discrepancia: event.target.checked ? "true" : "" }))} />
        <button type="button" className="text-sm font-medium text-accent hover:underline" aria-expanded={mostrarFiltros} onClick={() => setMostrarFiltros((valor) => !valor)}>Más filtros{filtrosAvanzadosActivos ? " (activos)" : ""}</button>
      </div>
      {mostrarFiltros && <div className="grid gap-3 rounded-md border border-borde bg-superficie p-4 sm:grid-cols-2 xl:grid-cols-4"><Field label="Desde"><Input type="date" value={borrador.desde} onChange={editar("desde")} /></Field><Field label="Hasta"><Input type="date" min={borrador.desde || undefined} value={borrador.hasta} onChange={editar("hasta")} /></Field><SelectorActividad label="Prestación" value={borrador.prestacion} onChange={editar("prestacion")} opciones={opciones.prestaciones} todas="Todas las prestaciones" /><Field label="Buscar afiliado o prestación"><Input value={borrador.search} onChange={editar("search")} placeholder="Nombre, documento, número o prestación" maxLength={160} /></Field><Field label="Discrepancias"><Select value={borrador.discrepancia} onChange={editar("discrepancia")}><option value="">Todas</option><option value="true">Con discrepancia</option><option value="false">Sin discrepancia</option></Select></Field></div>}
      <div className="flex flex-wrap items-center gap-2"><Button type="submit" disabled={consulta.isFetching}>Aplicar filtros</Button><Button type="button" variant="ghost" onClick={() => { setPersonalizar(false); aplicar(VACIOS); }}>Limpiar filtros</Button>{cambiosPendientes && <span role="status" className="text-sm text-texto-debil">Aplicá los cambios para actualizar la consulta y la exportación.</span>}</div>
    </form>
    {superaLimite && <p role="status" className="text-sm text-badge-amber-fg">El resultado supera el límite de exportación. Acotá el período o los filtros para descargarlo completo.</p>}
    {errorDescarga && <ErrorActividad error={errorDescarga} />}
    {consulta.isLoading ? <Spinner label="Consultando actividad…" /> : consulta.error ? <ErrorActividad error={consulta.error} reintentar={consulta.refetch} /> : <>
      <ResumenActividad resumen={consulta.data?.resumen} generado={consulta.data?.generado_en} />
      <Card className="overflow-hidden">{filas.length === 0 ? <EstadoVacio titulo="No hay actividad con estos filtros" detalle="Probá con otro período, hospital o afiliado." /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="border-b border-division bg-superficie-2 text-texto-debil"><tr>{["Afiliado", "Prestación", "Hospital", "Fecha", "Estado", ""].map((nombre) => <th key={nombre} scope="col" className="px-4 py-3 font-semibold">{nombre}</th>)}</tr></thead><tbody>{filas.map((fila) => <Fragment key={fila.id}><tr className="border-b border-division"><td className="px-4 py-3"><span className="font-medium text-texto">{fila.nombre || "—"}</span><p className="mt-1 text-xs text-texto-debil">{fila.numero || "Sin número"}</p></td><td className="px-4 py-3">{fila.prestacion || "—"}</td><td className="px-4 py-3">{fila.hospital || "—"}</td><td className="px-4 py-3">{fecha(fila.fecha)}</td><td className="px-4 py-3">{fila.discrepancia ? <Badge tone="error">Discrepancia</Badge> : <Badge tone={fila.estado === "realizada" ? "green" : "info"}>{ESTADOS[fila.estado] || fila.estado}</Badge>}</td><td className="px-4 py-3"><Button size="sm" variant="ghost" aria-expanded={detalle === fila.id} onClick={() => setDetalle((actual) => actual === fila.id ? null : fila.id)}>{detalle === fila.id ? "Ocultar" : "Ver"}</Button></td></tr>{detalle === fila.id && <tr className="border-b border-division bg-superficie-2"><td colSpan={6} className="p-4"><dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{COLUMNAS.map((columna) => <div key={columna.key}><dt className="text-xs text-texto-debil">{columna.label}</dt><dd className="mt-1">{columna.render ? columna.render(fila) : fila[columna.key] ?? "—"}</dd></div>)}</dl></td></tr>}</Fragment>)}</tbody></table></div>}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-division px-4 py-3"><span className="text-sm text-texto-debil">{plural(consulta.data?.count ?? filas.length, "registro", "registros")} · {(consulta.data?.count ?? filas.length) === 0 ? "Sin páginas" : `Página ${page} de ${Math.ceil((consulta.data?.count ?? filas.length) / POR_PAGINA)}`}</span><div className="flex gap-2"><Button size="sm" variant="ghost" disabled={page === 1 || consulta.isFetching} onClick={() => aplicar(aplicados, page - 1)}>Anterior</Button><Button size="sm" variant="ghost" disabled={!consulta.data?.next || consulta.isFetching} onClick={() => aplicar(aplicados, page + 1)}>Siguiente</Button></div></div>
      </Card>
      <p className="text-xs text-texto-debil">La consulta y la exportación quedan auditadas. El CSV incluye todas las páginas filtradas{limite != null && ` (hasta ${Number(limite).toLocaleString("es-AR")} registros)`}. Los importes no equivalen al saldo pendiente.</p>
    </>}
  </div>;
}
