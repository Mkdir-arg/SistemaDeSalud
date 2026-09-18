import { Component, lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { query } from "@/api/queries";
import { importeARS } from "@/api/finanzas";
import { Badge, Button, Card, Input, Select, Spinner } from "@/components/ui";
import { EstadoError, EstadoVacio } from "@/components/ui/estados";
import { fechaHora } from "@/lib/format";
import TablaAgregadaFinanzas from "./TablaAgregadaFinanzas";
import { AyudaFinanzas, PanelFlotante } from "./ControlesFinanzas";
import { coincideEstadoMes, tieneReferencia } from "./evolucion";

const GraficoFinanzas = lazy(() => import("./GraficoFinanzas"));
const GraficoEvolucion = lazy(() => import("./GraficoFinanzas").then((modulo) => ({ default: modulo.GraficoEvolucion })));

export class RespaldoGrafico extends Component {
  state = { fallo: false };
  static getDerivedStateFromError() { return { fallo: true }; }
  render() {
    return this.state.fallo ? <p role="alert" className="p-4">{this.props.mensaje || "No se pudo mostrar el gráfico. Elegí Listado para consultar todos los importes."}</p> : this.props.children;
  }
}

const parametros = (institucion, mes, area) => ({ institucion: institucion.id, periodo_economico: `${mes}-01`,
  ...(area === "null" ? { area_sin_asignar: true } : { area: area || undefined }) });

const estadosMes = { sin_control: "Sin configuración mensual vigente", sin_carga: "Carga sin completar", incompleto: "Carga o aprobación incompleta", mes_abierto: "Mes abierto · provisional", completo: "Carga y aprobación completas" };

function EvolucionMensual({ institucion, usuarioId, mes, area, onGastos }) {
  const [meses, setMeses] = useState(12);
  // null significa todos, incluso los que aparecen al ampliar el período.
  const [seleccion, setSeleccion] = useState(null);
  const [busqueda, setBusqueda] = useState("");
  const [referencia, setReferencia] = useState(false);
  const [estado, setEstado] = useState("ambos");
  const [verImportes, setVerImportes] = useState(false);
  const filtros = { ...parametros(institucion, mes, area), meses };
  const consulta = useQuery({ queryKey: ["finanzas", usuarioId, institucion.id, "evolucion", filtros], queryFn: () => api.get(`/reportes-finanzas/evolucion/${query(filtros)}`), gcTime: 0 });
  const datos = consulta.data;
  const opciones = datos?.conceptos || [];
  const elegidos = seleccion ?? opciones;
  const ids = new Set(elegidos.map((c) => c.id));
  const series = useMemo(() => (datos?.series || []).filter((s) => seleccion === null || seleccion.some((c) => c.id === s.id)), [datos?.series, seleccion]);
  const ausentes = elegidos.filter((c) => !opciones.some((o) => o.id === c.id));
  const hayReferencias = series.some(tieneReferencia);
  const referenciaVisible = referencia && hayReferencias;
  const hayImportes = series.some((s) => s.meses.some((fila) => coincideEstadoMes(fila, estado) && fila.importe_aprobado != null && !["sin_control", "sin_carga"].includes(fila.estado)));
  const ajustesPendientes = series.reduce((total, serie) => total + serie.meses.reduce((suma, fila) => suma + (fila.ajustes_pendientes || 0), 0), 0);
  const errorConsulta = Array.isArray(consulta.error?.data) ? { status: consulta.error.status, message: consulta.error.data.join(" ") } : consulta.error;
  const abrir = (fila, concepto) => onGastos({ concepto }, "aprobado", fila.periodo_economico);
  const quitar = (id) => setSeleccion(elegidos.filter((c) => c.id !== id));
  return <section className="flex min-h-0 min-w-0 flex-1 flex-col px-4 py-3" aria-label="Evolución de gastos mensuales">
    <h3 className="sr-only">Evolución mensual</h3>
    <div className="mb-1 flex max-w-full flex-wrap items-center gap-2">
      {!consulta.error && datos && <PanelFlotante titulo="Elegir conceptos de evolución" etiqueta={`Conceptos (${series.length}/${opciones.length})`} activo={seleccion !== null}>
        <Input aria-label="Buscar conceptos de evolución" placeholder="Buscar concepto…" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} />
        <div className="my-2 flex flex-wrap gap-2"><Button size="sm" variant="ghost" onClick={() => setSeleccion(null)}>Mostrar todos</Button><Button size="sm" variant="ghost" onClick={() => setSeleccion([])}>Quitar todos</Button></div>
        <div className="space-y-1">{opciones.filter((c) => c.nombre.toLocaleLowerCase("es").includes(busqueda.toLocaleLowerCase("es"))).map((c) => <label key={c.id} className="flex cursor-pointer items-center gap-2 rounded p-2 hover:bg-superficie-2"><input type="checkbox" className="shrink-0 accent-accent" checked={ids.has(c.id)} onChange={(e) => e.target.checked ? setSeleccion([...elegidos, c]) : quitar(c.id)} /><span className="min-w-0 break-words">{c.nombre}</span></label>)}</div>
        {busqueda && !opciones.some((c) => c.nombre.toLocaleLowerCase("es").includes(busqueda.toLocaleLowerCase("es"))) && <p className="mt-3 text-sm text-texto-debil">No hay conceptos con ese nombre.</p>}
      </PanelFlotante>}
      <Select className="w-[130px]" aria-label="Período de evolución" value={meses} onChange={(e) => setMeses(Number(e.target.value))}><option value="6">6 meses</option><option value="12">12 meses</option></Select>
      {!consulta.error && series.length > 0 && <>
        <Select className="w-[230px] max-w-full" aria-label="Estado de los meses" value={estado} onChange={(e) => setEstado(e.target.value)}><option value="ambos">Completos y provisionales</option><option value="completo">Carga y aprobación completas</option><option value="provisional">Mes incompleto o abierto</option></Select>
        <Button size="sm" variant="ghost" disabled={!hayReferencias} title={!hayReferencias ? "Los conceptos seleccionados no tienen referencias en este período" : undefined} aria-pressed={referenciaVisible} onClick={() => setReferencia((valor) => !valor)}>{referenciaVisible ? "Ocultar referencias" : "Comparar con referencias"}</Button>
        <Button size="sm" variant="ghost" aria-expanded={verImportes} onClick={() => setVerImportes((valor) => !valor)}>{verImportes ? "Ocultar importes mensuales" : "Ver importes mensuales"}</Button>
      </>}
      <AyudaFinanzas titulo="Cómo leer la evolución mensual"><p>Se muestran todos los conceptos visibles de Gastos mensuales. Elegí cuáles comparar o destacá uno desde su nombre. Cada concepto conserva su color; el color no indica aprobación ni ahorro.</p><p>Incluye sólo áreas con configuración mensual vigente en cada mes. Si cambia la cantidad de áreas configuradas, cambia la cobertura del total comparado. Los importes son gastos aprobados, incluidos sus ajustes, no el costo total del hospital.</p><p>La línea une meses con carga y aprobación completas. Los puntos huecos muestran importes provisionales: faltan cargas o aprobaciones, o el mes sigue abierto. Una baja aparente no prueba un ahorro. Sin configuración o sin carga no equivale a cero.</p><p>El filtro de estado se aplica por concepto y mes a los gastos, al detalle y al listado. Las referencias conservan todo el período, aunque ocultes gastos por su estado. Se muestran las de todos los conceptos seleccionados con alguna referencia; cero es válido y los meses sin referencia quedan vacíos. Son orientativas, no dinero gastado ni presupuesto aprobado; cada referencia mensual requiere que todas sus configuraciones tengan referencia. Son pesos de cada mes, sin ajuste por inflación.</p></AyudaFinanzas>
    </div>
    {consulta.error ? <EstadoError error={errorConsulta} onReintentar={consulta.refetch} titulo="No se pudo consultar la evolución mensual" /> : !datos ? <Spinner label="Consultando evolución mensual…" /> : <>
      {ajustesPendientes > 0 && <p role="status" className="mb-2 text-sm text-texto-debil">En los conceptos y meses consultados hay {ajustesPendientes} {ajustesPendientes === 1 ? "ajuste por aprobar" : "ajustes por aprobar"}. No modifican los importes aprobados; esos meses siguen provisionales hasta su revisión.</p>}
      {ausentes.length > 0 && <p role="status" className="mb-2 text-sm text-texto-debil">Hay {ausentes.length} conceptos seleccionados sin configuración mensual visible en este período. Se conservan para cuando vuelvas a ampliarlo.</p>}
      {ausentes.length > 0 && <div className="mb-2 flex flex-wrap gap-2">{ausentes.map((c) => <Button key={c.id} size="sm" variant="ghost" aria-label={`Quitar concepto no disponible ${c.nombre}`} onClick={() => quitar(c.id)}>{c.nombre} · no disponible ×</Button>)}</div>}
      {!opciones.length ? <p className="mt-4 text-sm text-texto-debil">No hay gastos mensuales configurados en este período. Configurá un gasto mensual o revisá mes y área.</p> : !series.length ? <div className="py-6 text-center"><p>No hay conceptos seleccionados disponibles para comparar.</p><Button className="mt-3" variant="secondary" onClick={() => setSeleccion(null)}>Mostrar todos los conceptos</Button></div> : <>
        {!hayImportes && <p role="status" className="my-2 text-sm text-texto-debil">No hay importes aprobados para graficar con este filtro.{referenciaVisible ? " Se mantienen las referencias de todo el período." : ""}</p>}
        <RespaldoGrafico mensaje="No se pudo mostrar la evolución. Abrí Ver importes mensuales para consultar los datos."><Suspense fallback={<p role="status">Preparando gráfico… Los importes están disponibles debajo.</p>}><GraficoEvolucion series={series} estado={estado} referencia={referenciaVisible} onMes={abrir} onQuitar={quitar} /></Suspense></RespaldoGrafico>
        {verImportes && <ul aria-label="Importes mensuales" className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{series[0].meses.map((mesFila, indice) => <li key={mesFila.periodo_economico} className="min-w-0 rounded-md border border-division p-3 text-sm"><strong>{mesFila.periodo_economico.slice(0, 7)}</strong>{series.map((serie) => {
          const fila = serie.meses[indice];
          const visible = coincideEstadoMes(fila, estado);
          const mostrarReferencia = referenciaVisible && tieneReferencia(serie);
          if (!visible && !mostrarReferencia) return null;
          return <div key={serie.id} className="mt-3 border-t border-division pt-2"><strong className="break-words">{serie.nombre}</strong><p className="mt-1 text-texto-debil">{visible ? `${fila.controles} configuraciones incluidas · ${estadosMes[fila.estado]}` : "Gasto oculto por el filtro de estado"}</p>{visible && fila.ajustes_pendientes > 0 && <p className="mt-1 text-texto-debil">Ajustes por aprobar: {fila.ajustes_pendientes}</p>}{!visible ? null : fila.importe_aprobado == null || fila.estado === "sin_carga" ? <p className="mt-2">{fila.importe_aprobado == null ? "Sin importe" : `Aprobado registrado: ${importeARS(fila.importe_aprobado)} · carga pendiente`}</p> : <button className="mt-2 break-all text-accent underline underline-offset-2 tabular-nums" onClick={() => abrir(fila, serie.id)} aria-label={`Ver gastos aprobados de ${fila.periodo_economico.slice(0, 7)} · ${serie.nombre}`}>{importeARS(fila.importe_aprobado)}</button>}{mostrarReferencia && <p className="mt-1 break-all">Referencia: {fila.monto_referencia == null ? "No disponible para todo el mes" : importeARS(fila.monto_referencia)}</p>}</div>;
        })}{!series.some((s) => coincideEstadoMes(s.meses[indice], estado) || (referenciaVisible && tieneReferencia(s))) && <p className="mt-2 text-texto-debil">Sin registros con este estado.</p>}</li>)}</ul>}
      </>}
    </>}
  </section>;
}

export function ProcesamientoFinanzas({ institucion, usuarioId, mes, area }) {
  const qc = useQueryClient();
  const anterior = useRef(null);
  const filtros = parametros(institucion, mes, area);
  const estado = useQuery({ queryKey: ["finanzas", usuarioId, institucion.id, "procesamiento", filtros],
    queryFn: () => api.get(`/procesamiento-finanzas/${query(filtros)}`), gcTime: 0,
    refetchInterval: 3000, refetchIntervalInBackground: false });
  const firma = estado.data ? `${estado.data.estado}:${estado.data.ultimo_exito}` : null;
  useEffect(() => {
    if (anterior.current && firma && anterior.current !== firma) {
      qc.invalidateQueries({ queryKey: ["finanzas", usuarioId, institucion.id],
        predicate: (q) => q.queryKey[3] !== "procesamiento" });
    }
    anterior.current = firma;
  }, [firma, qc, usuarioId, institucion.id]);
  if (estado.error) return <EstadoError error={estado.error} titulo="No se pudo comprobar la actualización de repartos" onReintentar={estado.refetch} />;
  if (!estado.data) return <p role="status" className="text-sm text-texto-debil">Comprobando actualización de repartos…</p>;
  const d = estado.data;
  const pendiente = d.estado !== "actualizado";
  return <div role="status" className="flex flex-wrap items-center gap-3 text-sm">
    <Badge tone={d.estado === "error" ? "error" : pendiente ? "amber" : "green"}>{d.estado === "error" ? "No se pudo actualizar" : pendiente ? (d.worker_activo ? "Actualizando repartos" : "Actualización pendiente") : "Repartos actualizados"}</Badge>
    {(pendiente || !d.worker_activo) && <span className="text-texto-debil">{d.mensaje}</span>}
    <AyudaFinanzas titulo="Cuándo se actualizan los repartos"><p>{d.mensaje}</p>{d.ultimo_exito && <p>Última ejecución correcta: {fechaHora(d.ultimo_exito)}</p>}<p>Los cambios de gastos, aprobaciones, ajustes, reglas y actividad disparan el cálculo en segundo plano. Guardar confirma la carga, no que el reparto ya haya terminado.</p><p>No necesitás dejar abierta esta pantalla. Si el proceso se detiene, los cambios quedan pendientes para recuperarse; mientras tanto no se presentan como un resultado actualizado.</p></AyudaFinanzas>
  </div>;
}

export default function ResumenFinanzas({ institucion, usuarioId, mes, area, onGastos, onRepartos, onMensuales }) {
  const [representacion, setRepresentacion] = useState("barras");
  const [vista, setVista] = useState("gastos");
  const filtros = parametros(institucion, mes, area);
  const consulta = useQuery({ queryKey: ["finanzas", usuarioId, institucion.id, "reporte", filtros],
    queryFn: () => api.get(`/reportes-finanzas/${query(filtros)}`), gcTime: 0 });
  const mensuales = useQuery({ queryKey: ["finanzas", usuarioId, institucion.id, "mensuales-pendientes", filtros],
    queryFn: () => api.get(`/expectativas-gasto/calendario/${query({ ...filtros, estado_carga: "falta_cargar", pageSize: 1 })}`), gcTime: 0 });
  if (consulta.error) return <EstadoError error={consulta.error} titulo="No se pudo consultar el resumen financiero" onReintentar={consulta.refetch} />;
  if (!consulta.data) return <Spinner label="Preparando resumen de gastos…" />;
  const d = consulta.data;
  const importe = (valor) => valor == null ? "Actualización pendiente" : importeARS(valor);
  return <section aria-label="Resumen de gastos" className="flex min-h-0 flex-1 flex-col gap-4">
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {[
        ["Gastos aprobados", d.aprobados, () => onGastos(null, "aprobado"), "Ver gastos aprobados"],
        ["Por aprobar", d.pendientes_aprobacion, () => onGastos(null, "pendiente_aprobacion"), "Revisar pendientes"],
        ["Distribuido entre atenciones", d.distribuido, () => onRepartos("distribuido"), "Ver distribución"],
        ["Sin distribuir", d.sin_distribuir, () => onRepartos("sin_distribuir"), "Revisar repartos"],
        ["Gastos mensuales pendientes", mensuales.data?.count ?? 0, onMensuales, "Ver gastos mensuales pendientes"],
      ].map(([label, valor, accion, enlace]) => <Card key={label} className="min-w-0 p-4"><h3 className="text-sm text-texto-debil">{label}</h3><div className="mt-2 flex flex-wrap items-center justify-between gap-2"><p className="break-all text-lg font-semibold tabular-nums">{importe(valor)}</p><Button size="sm" variant="ghost" aria-label={enlace} title={enlace} onClick={accion}>Ver →</Button></div></Card>)}
    </div>
    {d.ajustes_pendientes > 0 && <div role="status" className="flex flex-wrap items-center gap-2 text-sm"><p>{d.ajustes_pendientes} {d.ajustes_pendientes === 1 ? "ajuste por aprobar" : "ajustes por aprobar"}. <span className="text-texto-debil">No modifican los importes aprobados. Revisalos en el historial de cada gasto.</span></p><Button size="sm" variant="ghost" aria-label="Revisar gastos con ajustes" onClick={() => onGastos(null, "aprobado")}>Revisar gastos →</Button></div>}
    {d.actualizando && <p role="status" className="text-md text-texto-debil">Hay cambios en procesamiento. Los gastos guardados ya figuran; su distribución se mostrará al terminar.</p>}
    <Card className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <div role="group" aria-label="Controles del resumen" className="flex flex-wrap items-center justify-between gap-3 border-b border-division px-4 py-3">
        <h3 className="font-semibold">Gastos por área y concepto · ARS</h3>
        <div className="flex flex-wrap items-center gap-3">
          <div role="group" aria-label="Representación del resumen" className="flex flex-wrap gap-1">{[["barras", "Barras"], ["dona", "Dos niveles"], ["evolucion", "Evolución mensual"], ["listado", "Listado"]].map(([opcion, nombre]) => <Button key={opcion} size="sm" variant={representacion === opcion ? "secondary" : "ghost"} aria-pressed={representacion === opcion} onClick={() => setRepresentacion(opcion)}>{nombre}</Button>)}</div>
          <div className="w-[230px] max-w-full">
          {["barras", "dona"].includes(representacion) ? <Select aria-label="Comparar" value={vista} onChange={(e) => setVista(e.target.value)}><option value="gastos">Gastos</option><option value="distribucion">Distribución del aprobado</option></Select>
            : <p className="flex h-10 items-center px-3 text-sm text-texto-debil">{representacion === "evolucion" ? "Gastos mensuales" : "Todas las medidas"}</p>}
          </div>
        </div>
      </div>
      {representacion === "evolucion" ? <EvolucionMensual key={`${institucion.id}:${area}:${mes}`} institucion={institucion} usuarioId={usuarioId} mes={mes} area={area} onGastos={onGastos} />
        : !d.agrupaciones.length ? <EstadoVacio titulo="Todavía no hay gastos para estos filtros" detalle="Registrá un gasto o revisá el mes y el área. Esto no significa que el hospital no tenga gastos." />
        : representacion !== "listado" ? <RespaldoGrafico><Suspense fallback={<p role="status" className="p-4">Preparando gráfico… El listado ya está disponible.</p>}><GraficoFinanzas grupos={d.agrupaciones} representacion={representacion} vista={vista} onGastos={onGastos} onRepartos={onRepartos} /></Suspense></RespaldoGrafico> : <TablaAgregadaFinanzas clave="resumen_grupos" titulo="Gastos por área y concepto · ARS"
          contexto={`Gastos vigentes · Mes económico ${mes}`}
          filas={d.agrupaciones.map((g) => ({ ...g, id: `${g.area}:${g.concepto}` }))}
          columnas={[
            { key: "area_concepto", label: "Área / concepto", valor: (g) => `${g.area_nombre || "Institucional"} ${g.concepto_nombre}`,
              render: (g) => <><strong>{g.area_nombre || "Institucional — sin área asignada"}</strong><p className="text-texto-debil">{g.concepto_nombre}</p>{g.ajustes_pendientes > 0 && <button className="mt-1 text-sm text-accent underline underline-offset-2" onClick={() => onGastos(g, "aprobado")}>{g.ajustes_pendientes} {g.ajustes_pendientes === 1 ? "ajuste por aprobar" : "ajustes por aprobar"}</button>}</> },
            ...[["aprobados", "Aprobado", "aprobado"], ["pendientes_aprobacion", "Por aprobar", "pendiente_aprobacion"], ["distribuido", "Distribuido"], ["sin_distribuir", "Sin distribuir"]].map(([campo, label, estado]) => ({ key: campo, label, numerica: true,
              render: (g) => g[campo] == null ? importe(g[campo]) : <button className="tabular-nums text-accent underline underline-offset-2" onClick={() => estado ? onGastos(g, estado) : onRepartos(campo, g)}>{importe(g[campo])}</button> })),
          ]} />}</Card>
  </section>;
}
