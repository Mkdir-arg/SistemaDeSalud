import { lazy, Suspense, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "@/api/client";
import { importeARS } from "@/api/finanzas";
import { query } from "@/api/queries";
import { Ayuda, Badge, Button, Card, Input, Modal, Select, Spinner } from "@/components/ui";
import { Icon } from "@/components/icons";
import { EstadoError, EstadoVacio } from "@/components/ui/estados";
import { fechaHora } from "@/lib/format";
import { RespaldoGrafico } from "./ResumenFinanzas";
import { DetalleCuenta, MovimientosPeriodo } from "./DineroFinanzas";
import { filtroAreaDinero } from "./dinero";
import TablaAgregadaFinanzas from "./TablaAgregadaFinanzas";
import { AyudaFinanzas, FiltrosActivos } from "./ControlesFinanzas";

const Tendencia = lazy(() => import("./GraficoReportes").then((m) => ({ default: m.TendenciaReporte })));
const Comparacion = lazy(() => import("./GraficoReportes").then((m) => ({ default: m.ComparacionGrupos })));
const medidasGastos = [["aprobados", "Gastos aprobados"]];
const medidasDinero = [["cobros_netos", "Cobros netos"], ["pagos_netos", "Pagos netos"]];
const disponible = (d) => (d.cantidad_registros ?? d.cantidad_movimientos) > 0;
const porcentaje = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2, signDisplay: "exceptZero" });
const colorVariacion = (valor) => Number(valor) > 0 ? "text-badge-green-fg" : Number(valor) < 0 ? "text-badge-error-fg" : "text-texto-debil";

function Variacion({ dato }) {
  if (!dato || dato.importe == null) return <span className="text-sm text-texto-debil">Sin base comparable</span>;
  return <span className="finance-report-change"><strong className={colorVariacion(dato.importe)}>{Number(dato.importe) > 0 ? "+" : ""}{importeARS(dato.importe)}</strong>
    <span className={colorVariacion(dato.porcentaje)}>{dato.porcentaje == null ? "Sin base porcentual" : `${porcentaje.format(Number(dato.porcentaje))}% nominal`}</span>
  </span>;
}

function Grafico({ children, identificador }) {
  return <div data-reporte-grafico={identificador}><RespaldoGrafico mensaje="No se pudo dibujar el gráfico. Podés consultar todos los importes en la tabla."><Suspense fallback={<Spinner label="Preparando visualización…" />}>{children}</Suspense></RespaldoGrafico></div>;
}

function Indicador({ titulo, campo, reporte, onAbrir }) {
  const a = reporte.actual, b = reporte.anterior;
  const valor = (fila) => disponible(fila) ? importeARS(fila[campo]) : "Sin registros";
  return <Card className="finance-report-metric">
    <h3>{titulo}</h3>
    <button className="finance-report-amount" onClick={() => onAbrir(a, campo)} aria-label={`Ver ${titulo.toLowerCase()} de ${a.periodo_economico.slice(0, 7)}`}>{valor(a)}</button>
    <button className="finance-report-baseline" onClick={() => onAbrir(b, campo)} aria-label={`Ver ${titulo.toLowerCase()} de ${b.periodo_economico.slice(0, 7)}`}>{b.periodo_economico.slice(0, 7)} · {valor(b)}</button>
    <Variacion dato={reporte.variaciones[campo]} />
  </Card>;
}

function SerieMensual({ reporte, medidas, onAbrir, exportacion }) {
  return <Card className="finance-report-panel">
    <div className="flex items-center justify-between gap-2"><h3 className="font-semibold">Evolución mensual · ARS</h3><AyudaFinanzas titulo={`Cómo leer la evolución de ${medidas === medidasGastos ? "gastos" : "dinero"}`}><p>Los huecos indican meses sin registros, no importes cero. Los puntos huecos señalan meses abiertos o con carga o aprobación pendiente.</p><p>Seleccioná un punto para abrir sus fuentes. También podés usar el detalle mensual bajo el gráfico.</p></AyudaFinanzas></div>
    {reporte.serie.some(disponible) ? <Grafico identificador={medidas === medidasGastos ? "tendencia_gastos" : "tendencia_dinero"}><Tendencia serie={reporte.serie} medidas={medidas} onAbrir={onAbrir} /></Grafico> : <EstadoVacio titulo="Sin registros para dibujar una tendencia" detalle="Revisá el período y el área. No equivale a una actividad económica nula." />}
    <details className="finance-report-detail"><summary>Ver importes y fuentes de cada mes</summary>
      <TablaAgregadaFinanzas exportacion={exportacion} clave={`reporte_serie_${medidas === medidasGastos ? "gastos" : "dinero"}`} titulo="Serie mensual exacta"
        contexto={medidas === medidasGastos ? "Gastos vigentes por mes económico" : "Movimientos aprobados por fecha efectiva"}
        filas={reporte.serie.map((fila) => ({ ...fila, id: fila.periodo_economico, lectura: !disponible(fila) ? "Sin registros aprobados" : (fila.provisional ?? fila.mes_abierto) ? "Lectura provisional" : "Registros visibles" }))}
        columnas={[
          { key: "periodo_economico", label: "Mes", exportar: (fila) => fila.periodo_economico.slice(0, 7), render: (fila) => fila.periodo_economico.slice(0, 7) },
          ...medidas.map(([campo, nombre]) => ({ key: campo, label: nombre, numerica: true, valor: (fila) => disponible(fila) ? fila[campo] : null,
            exportar: (fila) => disponible(fila) ? importeARS(fila[campo]) : "Sin registros",
            render: (fila) => <button className="finance-report-link" onClick={() => onAbrir(fila, campo)}>{disponible(fila) ? importeARS(fila[campo]) : "Sin registros"}</button> })),
          { key: "lectura", label: "Lectura" },
        ]} />
    </details>
  </Card>;
}

function Consulta({ consulta, children }) {
  if (consulta.error) return <EstadoError error={consulta.error} onReintentar={consulta.refetch} titulo="No se pudo consultar este informe" />;
  if (!consulta.data) return <Spinner label="Cargando informe…" />;
  return children(consulta.data);
}

export default function ReportesEjecutivos({ institucion, permisos, mes, area, areaNombre, onGastos }) {
  const [, setSearchParams] = useSearchParams();
  const [comparar, setComparar] = useState("mes_anterior");
  const [meses, setMeses] = useState(6);
  const [detalle, setDetalle] = useState(null);
  const [cuenta, setCuenta] = useState(null);
  const [busqueda, setBusqueda] = useState("");
  const [tipo, setTipo] = useState("cobrar");
  const [exportando, setExportando] = useState(false);
  const [errorPdf, setErrorPdf] = useState("");
  const exportacion = useRef({});
  const seccion = useRef(null);
  const filtros = { institucion: institucion.id, periodo_economico: `${mes}-01`, ...filtroAreaDinero(area), comparar, meses };
  const opciones = (recurso, permiso) => ({
    queryKey: ["finanzas", permisos.usuarioId, institucion.id, "ejecutivo", recurso, filtros],
    queryFn: () => api.get(`/${recurso}/comparativa/${query(filtros)}`),
    enabled: permisos.tiene(permiso), gcTime: 0, placeholderData: undefined,
  });
  const gastos = useQuery(opciones("reportes-finanzas", "ver_gastos"));
  const dinero = useQuery(opciones("reportes-dinero", "ver_dinero"));
  const consultas = [permisos.tiene("ver_gastos") && gastos, permisos.tiene("ver_dinero") && dinero].filter(Boolean);
  const listoParaPdf = consultas.length > 0 && consultas.every((c) => c.data && !c.error && !c.isFetching);
  async function descargarPdf() {
    if (!listoParaPdf || exportando) return;
    setErrorPdf("");
    const tablas = Object.fromEntries(Object.entries(exportacion.current).map(([clave, preparar]) => [clave, preparar()]));
    if (Object.values(tablas).some((t) => t.invalidos)) {
      setErrorPdf("Corregí los filtros de importe antes de descargar el reporte.");
      return;
    }
    // Congelar datos, selección y SVG juntos, antes de cargar el generador.
    const graficos = Object.fromEntries([...seccion.current.querySelectorAll("[data-reporte-grafico]")].map((el) => {
      const svg = el.querySelector(".recharts-wrapper > svg.recharts-surface");
      return [el.dataset.reporteGrafico, svg?.cloneNode(true)];
    }));
    const instantanea = { institucion: institucion.nombre, mes, area: areaNombre, meses, tipo, busqueda, tablas, graficos,
      gastos: permisos.tiene("ver_gastos") ? gastos.data : null, dinero: permisos.tiene("ver_dinero") ? dinero.data : null };
    setExportando(true);
    try {
      const { descargarReportePdf } = await import("./reportePdf");
      await descargarReportePdf(instantanea);
    } catch {
      setErrorPdf("No se pudo generar el PDF. Recargá la página y volvé a intentarlo.");
    } finally {
      setExportando(false);
    }
  }
  const abrirGasto = (fila, campo, grupo = null) => onGastos(grupo, campo === "pendientes_aprobacion" ? "pendiente_aprobacion" : "aprobado", fila.periodo_economico, false);
  function abrirControles(fila) {
    setSearchParams((previos) => {
      const siguientes = new URLSearchParams(previos);
      [...siguientes.keys()].filter((clave) => clave.startsWith("calendario_")).forEach((clave) => siguientes.delete(clave));
      siguientes.set("tab", "calendario");
      siguientes.set("mes", fila.periodo_economico.slice(0, 7));
      siguientes.set("calendario_f_estado_carga", "falta_cargar");
      return siguientes;
    });
  }
  function abrirDinero(fila, campo, grupo = null) {
    // Cada cifra tiene su propia población. Una página avanzada de otro
    // desglose puede no existir en el siguiente y ocultaría sus fuentes.
    setSearchParams((previos) => {
      const siguientes = new URLSearchParams(previos);
      siguientes.delete("movimientos_dinero_pag");
      [...siguientes.keys()].filter((clave) => clave.startsWith("movimientos_dinero_f_")).forEach((clave) => siguientes.delete(clave));
      return siguientes;
    }, { replace: true });
    const contexto = { institucion: institucion.id, fecha_desde: fila.fecha_desde, fecha_hasta: fila.fecha_hasta,
      ...(grupo ? grupo.filtros : filtroAreaDinero(area)), estado: campo === "pendientes" ? "pendiente_aprobacion" : "aprobado" };
    if (campo === "cobros_netos") contexto.tipo_cuenta = "cobrar";
    if (campo === "pagos_netos") contexto.tipo_cuenta = "pagar";
    setDetalle({ filtros: contexto, titulo: grupo ? `${grupo.area_nombre} · ${grupo.concepto_nombre} · ${grupo.pagador_nombre}` : "Movimientos que explican el importe", periodo: fila.periodo_economico.slice(0, 7) });
  }
  return <section ref={seccion} className="finance-report" aria-label="Reportes ejecutivos">
    <header className="finance-report-heading">
      <div className="flex items-center gap-2"><h2 className="font-semibold">Comparación de períodos</h2><AyudaFinanzas titulo="Cómo leer los reportes"><p>Los importes están en pesos argentinos, sin ajuste por inflación. Se compara el mes elegido con el anterior o con el mismo mes del año anterior.</p><p>La variación es actual menos anterior. Sólo se calcula un porcentaje si ambos períodos tienen registros y la base anterior es positiva. Una suba o baja no indica por sí sola una mejora.</p><p>Gastos y movimientos de dinero son magnitudes diferentes: no se suman. El informe incluye sólo fuentes registradas dentro de tus permisos; no representa el costo total, la rentabilidad ni la disponibilidad del hospital.</p><p>Las cifras abren sus fuentes. Son consultas en vivo: nuevas cargas o aprobaciones pueden cambiar el detalle.</p></AyudaFinanzas></div>
      <div className="finance-report-tools"><Select aria-label="Comparar período" value={comparar} onChange={(e) => setComparar(e.target.value)}><option value="mes_anterior">Mes anterior</option><option value="anio_anterior">Mismo mes del año anterior</option></Select><Select aria-label="Trayectoria" value={meses} onChange={(e) => setMeses(Number(e.target.value))}><option value="6">6 meses</option><option value="12">12 meses</option></Select><Button variant="secondary" onClick={descargarPdf} disabled={!listoParaPdf || exportando} aria-busy={exportando}><Icon name="download" size={16} />{exportando ? "Preparando PDF…" : "Descargar PDF"}</Button><AyudaFinanzas titulo="Qué incluye el PDF"><p>Los gráficos, los totales y todas las filas que cumplen los filtros de cada tabla, aunque estén en otra página o el detalle mensual esté cerrado. Se conserva el orden seleccionado.</p><p>Los filtros de tabla no modifican los gráficos ni los totales. El PDF identifica los períodos, el alcance y la fecha de consulta. Se descarga sólo cuando las consultas autorizadas están completas.</p></AyudaFinanzas></div>
    </header>
    {errorPdf && <p role="alert" className="text-sm text-badge-error-fg">{errorPdf}</p>}
    <div className="finance-report-columns">
    {permisos.tiene("ver_gastos") ? <Consulta consulta={gastos}>{(d) => <section aria-label="Informe de gastos" className="finance-report-section">
      <div className="finance-report-section-title"><div><h2>Gastos</h2><p>Mes económico · {d.actual.periodo_economico.slice(0, 7)} / {d.anterior.periodo_economico.slice(0, 7)}</p></div><div className="flex items-center gap-2">{d.actual.mes_abierto && <Badge tone="amber">Mes abierto</Badge>}<AyudaFinanzas titulo="Importes y pendientes de gastos"><p>El aprobado incluye los ajustes aprobados y lo distribuido entre atenciones. Los ajustes por aprobar no modifican ese importe. Durante el procesamiento, la distribución no está disponible.</p><p>Un mes abierto puede mostrar una baja aparente frente a uno cerrado. Terminar el mes o completar sus controles no garantiza que toda la carga esté registrada. Sin controles configurados no se puede verificar su completitud.</p><p>Los pendientes de ambos períodos abren el calendario correspondiente. Cada importe abre sus gastos, incluidos los que no tienen control mensual.</p></AyudaFinanzas></div></div>
      <div className="finance-report-metrics finance-report-metrics-two"><Indicador titulo="Gastos aprobados" campo="aprobados" reporte={d} onAbrir={abrirGasto} /><Indicador titulo="Gastos por aprobar" campo="pendientes_aprobacion" reporte={d} onAbrir={abrirGasto} /></div>
      <div className="finance-report-status" role="status">{[d.actual, d.anterior].map((fila) => <span key={fila.periodo_economico}>
        <strong>{fila.periodo_economico.slice(0, 7)}:</strong>{" "}{!fila.controles ? "Sin controles configurados" : fila.controles_sin_completar > 0 ? <button className="finance-report-link" onClick={() => abrirControles(fila)}>{fila.controles_sin_completar} {fila.controles_sin_completar === 1 ? "control pendiente" : "controles pendientes"} de carga · revisar</button> : "Controles sin pendientes"}
      </span>)}{d.actual.ajustes_pendientes > 0 && <button className="finance-report-link" onClick={() => abrirGasto(d.actual, "aprobados")}>{d.actual.ajustes_pendientes} ajustes por aprobar · revisar gastos</button>}{d.actual.actualizando && <Badge tone="amber">Distribución en actualización</Badge>}</div>
      <SerieMensual reporte={d} medidas={medidasGastos} onAbrir={abrirGasto} exportacion={exportacion} />
      <Card className="finance-report-panel finance-report-charts">
        <div className="flex items-center justify-between gap-2"><h3 className="font-semibold">Gastos por área y concepto · ARS</h3><AyudaFinanzas titulo="Cómo comparar los grupos de gastos"><p>Se muestran hasta ocho grupos con mayor gasto aprobado actual. Las barras comparan ambos períodos en la misma escala.</p><p>La tabla incluye todos los grupos. Sus filtros y orden no cambian los gráficos ni los totales. Cada importe abre los gastos del área, concepto y mes seleccionados.</p></AyudaFinanzas></div>
        {d.agrupaciones.length ? <Grafico identificador="grupos_gastos"><Comparacion grupos={d.agrupaciones} periodoActual={d.actual.periodo_economico} periodoAnterior={d.anterior.periodo_economico} onAbrir={(g, periodo) => abrirGasto(d[periodo], "aprobados", g)} /></Grafico> : <EstadoVacio titulo="Sin gastos registrados en ambos períodos" />}
        <h3 className="mt-4 font-semibold">Detalle por área y concepto</h3>
        <TablaAgregadaFinanzas exportacion={exportacion} clave="reporte_grupos_gastos" titulo="Comparación exacta de gastos"
          contexto={`Seleccionado: ${d.actual.periodo_economico.slice(0, 7)} · Comparado: ${d.anterior.periodo_economico.slice(0, 7)} · Gastos vigentes`}
          filas={d.agrupaciones.map((g) => ({ ...g, id: `${g.area}:${g.concepto}` }))}
          columnas={[
            { key: "area_concepto", label: "Área / concepto", valor: (g) => `${g.area_nombre} ${g.concepto_nombre}`, render: (g) => <><strong>{g.concepto_nombre}</strong><p className="text-texto-debil">{g.area_nombre}</p></> },
            ...["anterior", "actual"].map((periodo) => ({ key: periodo, label: d[periodo].periodo_economico.slice(0, 7), numerica: true, valor: (g) => g[periodo]?.aprobados,
              exportar: (g) => g[periodo] ? importeARS(g[periodo].aprobados) : "Sin registros",
              render: (g) => g[periodo] ? <button className="finance-report-link" onClick={() => abrirGasto(d[periodo], "aprobados", g)}>{importeARS(g[periodo].aprobados)}</button> : "Sin registros" })),
            { key: "variacion", label: "Variación nominal", numerica: true, valor: (g) => g.variacion?.importe, exportar: (g) => ({ variacion: g.variacion }), render: (g) => <Variacion dato={g.variacion} /> },
          ]} />
      </Card>
      <p className="finance-report-cut">Consultado {fechaHora(d.calculado_en)}</p>
    </section>}</Consulta> : <p className="finance-report-scope">Los gastos no están incluidos en tu acceso. No se representan como cero.</p>}
    {permisos.tiene("ver_dinero") ? <Consulta consulta={dinero}>{(d) => {
      const grupos = d.agrupaciones.filter((g) => g.filtros.tipo_cuenta === tipo && `${g.area_nombre} ${g.concepto_nombre} ${g.pagador_nombre}`.toLocaleLowerCase("es").includes(busqueda.toLocaleLowerCase("es")));
      return <section aria-label="Informe de dinero" className="finance-report-section">
        <div className="finance-report-section-title"><div><h2>Pagos y cobros</h2><p>Fecha efectiva · {d.actual.fecha_desde} al {d.actual.fecha_hasta}</p></div><div className="flex items-center gap-2">{d.actual.mes_abierto && <Badge tone="amber">Mes abierto</Badge>}<AyudaFinanzas titulo="Importes y pendientes de dinero"><p>Cobros y pagos netos de devoluciones, según la fecha efectiva de cada movimiento. La diferencia es cobros menos pagos: no es saldo disponible ni rentabilidad.</p><p>Los movimientos por aprobar se consultan aparte y están excluidos de los totales. Un mes abierto se compara de forma provisional.</p><p>Las cifras abren movimientos, luego su cuenta y origen. Las cuentas pueden pertenecer a otro mes económico.</p></AyudaFinanzas></div></div>
        <div className="finance-report-metrics">{[...medidasDinero, ["diferencia", "Diferencia del período"]].map(([campo, titulo]) => <Indicador key={campo} titulo={titulo} campo={campo} reporte={d} onAbrir={abrirDinero} />)}</div>
        <div className="finance-report-status"><button className="finance-report-link" onClick={() => abrirDinero(d.actual, "pendientes")}>{d.actual.por_aprobar.cantidad} movimientos por aprobar</button></div>
        <SerieMensual reporte={d} medidas={medidasDinero} onAbrir={abrirDinero} exportacion={exportacion} />
        <Card className="finance-report-panel"><div className="finance-report-table-heading"><div className="flex items-center gap-2"><h3 className="font-semibold">Detalle de pagos y cobros</h3><AyudaFinanzas titulo="Cómo se agrupa el dinero"><p>Cobros por área, prestación y financiador; pagos por área y concepto de gasto. Los copagos se muestran a nombre del paciente.</p><p>El financiador proviene del vínculo de cobertura de la cuenta, no de coincidencias de nombres. Sin ese vínculo, queda sin identificar.</p><p>La búsqueda y el tipo de movimiento filtran esta tabla, no los totales del informe. Cada importe abre sus movimientos.</p></AyudaFinanzas></div><div className="finance-report-tools"><Select aria-label="Desglose de dinero" value={tipo} onChange={(e) => setTipo(e.target.value)}><option value="cobrar">Cobros por financiador</option><option value="pagar">Pagos por concepto</option></Select><Input aria-label="Buscar en desglose" placeholder="Buscar área, prestación, financiador…" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} /></div></div>
          <FiltrosActivos filtros={{ valores: { search: busqueda }, cambiar: ({ search }) => setBusqueda(search || "") }} definiciones={[{ key: "search", label: "Buscar en desglose" }]} />
          <TablaAgregadaFinanzas exportacion={exportacion} clave={`reporte_grupos_${tipo}`} titulo="Desglose de dinero por área, concepto y financiador"
            contexto={`Fecha efectiva: ${d.actual.fecha_desde} al ${d.actual.fecha_hasta}`}
            filas={grupos.map((g) => ({ ...g, id: JSON.stringify(g.filtros) }))} vacio={{ titulo: "Sin movimientos para este desglose", detalle: "Revisá el tipo de movimiento y los filtros." }}
            columnas={[
              { key: "area_concepto", label: "Área / concepto", valor: (g) => `${g.area_nombre} ${g.concepto_nombre}`, render: (g) => <><strong>{g.concepto_nombre}</strong><p className="text-texto-debil">{g.area_nombre}</p></> },
              { key: "pagador_nombre", label: tipo === "cobrar" ? "Responsable del pago" : "Destino" },
              { key: "neto", label: "Neto confirmado", numerica: true, valor: (g) => g.cantidad_movimientos ? g[tipo === "cobrar" ? "cobros_netos" : "pagos_netos"] : null,
                exportar: (g) => g.cantidad_movimientos ? importeARS(g[tipo === "cobrar" ? "cobros_netos" : "pagos_netos"]) : "Sin movimientos aprobados",
                render: (g) => <button className="finance-report-link" onClick={() => abrirDinero(d.actual, tipo === "cobrar" ? "cobros_netos" : "pagos_netos", g)}>{g.cantidad_movimientos ? importeARS(g[tipo === "cobrar" ? "cobros_netos" : "pagos_netos"]) : "Sin movimientos aprobados"}</button> },
              { key: "pendientes", label: "Por aprobar", numerica: true, valor: (g) => g.por_aprobar.cantidad,
                render: (g) => <button className="finance-report-link" onClick={() => abrirDinero(d.actual, "pendientes", g)}>{g.por_aprobar.cantidad} registros</button> },
            ]} />
        </Card><p className="finance-report-cut">Consultado {fechaHora(d.calculado_en)}</p>
      </section>;
    }}</Consulta> : <p className="finance-report-scope">Los pagos y cobros no están incluidos en tu acceso. No se representan como cero.</p>}
    </div>
    {detalle && <Modal title={`Fuentes del informe · ${detalle.periodo}`} ayuda="Los reintegros se restan del cobro o pago original para explicar el neto. Se conserva la fecha efectiva de cada movimiento." onClose={() => setDetalle(null)} width={1040}><p className="font-semibold">{detalle.titulo}</p><MovimientosPeriodo key={JSON.stringify(detalle.filtros)} filtros={detalle.filtros} institucion={institucion} permisos={permisos} onCuenta={setCuenta} /></Modal>}
    {cuenta != null && <DetalleCuenta id={cuenta} institucion={institucion} permisos={permisos} onClose={() => setCuenta(null)} />}
  </section>;
}
