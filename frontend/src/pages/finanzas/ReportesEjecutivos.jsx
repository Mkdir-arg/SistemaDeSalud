import { lazy, Suspense, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { importeARS } from "@/api/finanzas";
import { query } from "@/api/queries";
import { Card, Field, Input, Modal, Select, Spinner } from "@/components/ui";
import { EstadoError, EstadoVacio } from "@/components/ui/estados";
import { fechaHora } from "@/lib/format";
import { RespaldoGrafico } from "./ResumenFinanzas";
import { DetalleCuenta, MovimientosPeriodo } from "./DineroFinanzas";
import { filtroAreaDinero } from "./dinero";

const Tendencia = lazy(() => import("./GraficoReportes").then((m) => ({ default: m.TendenciaReporte })));
const Comparacion = lazy(() => import("./GraficoReportes").then((m) => ({ default: m.ComparacionGrupos })));
const medidasGastos = [["aprobados", "Gastos aprobados"]];
const medidasDinero = [["cobros_netos", "Cobros netos"], ["pagos_netos", "Pagos netos"]];
const disponible = (d) => (d.cantidad_registros ?? d.cantidad_movimientos) > 0;
const porcentaje = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2, signDisplay: "exceptZero" });

function Variacion({ dato }) {
  if (!dato || dato.importe == null) return <span className="text-sm text-texto-debil">Sin base comparable</span>;
  return <span className="finance-report-change"><strong>{Number(dato.importe) > 0 ? "+" : ""}{importeARS(dato.importe)}</strong>
    <span>{dato.porcentaje == null ? dato.motivo : `${porcentaje.format(Number(dato.porcentaje))}% nominal`}</span>
  </span>;
}

function Grafico({ children }) {
  return <RespaldoGrafico mensaje="No se pudo dibujar el gráfico. Podés consultar todos los importes en la tabla."><Suspense fallback={<Spinner label="Preparando visualización…" />}>{children}</Suspense></RespaldoGrafico>;
}

function Indicador({ titulo, campo, reporte, onAbrir }) {
  const a = reporte.actual, b = reporte.anterior;
  const valor = (fila) => disponible(fila) ? importeARS(fila[campo]) : "Sin registros";
  return <div className="finance-report-metric">
    <h3>{titulo}</h3>
    <button className="finance-report-amount" onClick={() => onAbrir(a, campo)} aria-label={`Ver ${titulo.toLowerCase()} de ${a.periodo_economico.slice(0, 7)}`}>{valor(a)}</button>
    <button className="finance-report-baseline" onClick={() => onAbrir(b, campo)} aria-label={`Ver ${titulo.toLowerCase()} de ${b.periodo_economico.slice(0, 7)}`}>{b.periodo_economico.slice(0, 7)} · {valor(b)}</button>
    <Variacion dato={reporte.variaciones[campo]} />
  </div>;
}

function SerieMensual({ reporte, medidas, onAbrir }) {
  return <Card className="finance-report-panel">
    <h3 className="font-semibold">Trayectoria mensual</h3><p className="text-sm text-texto-debil">ARS nominales · Los huecos indican meses sin registros. El punto hueco señala un mes abierto.</p>
    {reporte.serie.some(disponible) ? <Grafico><Tendencia serie={reporte.serie} medidas={medidas} onAbrir={onAbrir} /></Grafico> : <EstadoVacio titulo="Sin registros para dibujar una tendencia" detalle="Revisá el período y el área. No equivale a una actividad económica nula." />}
    <details className="finance-report-detail"><summary>Ver importes y fuentes de cada mes</summary><div className="finance-table"><div className="finance-table-content"><table><caption className="sr-only">Serie mensual exacta</caption><thead><tr><th>Mes</th>{medidas.map(([campo, nombre]) => <th key={campo}>{nombre}</th>)}<th>Lectura</th></tr></thead><tbody>{reporte.serie.map((fila) => <tr key={fila.periodo_economico}><th scope="row" data-label="Mes">{fila.periodo_economico.slice(0, 7)}</th>{medidas.map(([campo, nombre]) => <td key={campo} data-label={nombre}><button className="finance-report-link" onClick={() => onAbrir(fila, campo)}>{disponible(fila) ? importeARS(fila[campo]) : "Sin registros"}</button></td>)}<td data-label="Lectura">{!disponible(fila) ? "Sin registros aprobados" : fila.mes_abierto ? "Mes abierto · provisional" : "Registros visibles"}</td></tr>)}</tbody></table></div></div></details>
  </Card>;
}

function Consulta({ consulta, children }) {
  if (consulta.error) return <EstadoError error={consulta.error} onReintentar={consulta.refetch} titulo="No se pudo consultar este informe" />;
  if (!consulta.data) return <div className="finance-report-loading" role="status">Preparando comparaciones y verificando el alcance…</div>;
  return children(consulta.data);
}

export default function ReportesEjecutivos({ institucion, permisos, mes, area, onGastos }) {
  const [comparar, setComparar] = useState("mes_anterior");
  const [meses, setMeses] = useState(6);
  const [detalle, setDetalle] = useState(null);
  const [cuenta, setCuenta] = useState(null);
  const [busqueda, setBusqueda] = useState("");
  const [tipo, setTipo] = useState("cobrar");
  const filtros = { institucion: institucion.id, periodo_economico: `${mes}-01`, ...filtroAreaDinero(area), comparar, meses };
  const opciones = (recurso, permiso) => ({
    queryKey: ["finanzas", permisos.usuarioId, institucion.id, "ejecutivo", recurso, filtros],
    queryFn: () => api.get(`/${recurso}/comparativa/${query(filtros)}`),
    enabled: permisos.tiene(permiso), gcTime: 0, placeholderData: undefined,
  });
  const gastos = useQuery(opciones("reportes-finanzas", "ver_gastos"));
  const dinero = useQuery(opciones("reportes-dinero", "ver_dinero"));
  const abrirGasto = (fila, campo, grupo = null) => onGastos(grupo, campo === "pendientes_aprobacion" ? "pendiente_aprobacion" : "aprobado", fila.periodo_economico, false);
  function abrirDinero(fila, campo, grupo = null) {
    const contexto = { institucion: institucion.id, fecha_desde: fila.fecha_desde, fecha_hasta: fila.fecha_hasta,
      ...(grupo ? grupo.filtros : filtroAreaDinero(area)), estado: campo === "pendientes" ? "pendiente_aprobacion" : "aprobado" };
    if (campo === "cobros_netos") contexto.tipo_cuenta = "cobrar";
    if (campo === "pagos_netos") contexto.tipo_cuenta = "pagar";
    setDetalle({ filtros: contexto, titulo: grupo ? `${grupo.area_nombre} · ${grupo.concepto_nombre} · ${grupo.pagador_nombre}` : "Movimientos que explican el importe", periodo: fila.periodo_economico.slice(0, 7) });
  }
  return <section className="finance-report" aria-label="Reportes ejecutivos">
    <header className="finance-report-heading">
      <div><p className="finance-report-eyebrow">FINANZAS / LECTURA EJECUTIVA</p><h2>Los números, con su explicación.</h2><p>{institucion.nombre} · {mes} · Alcance visible según tus permisos</p></div>
      <div className="flex flex-wrap gap-3"><Field label="Comparar período"><Select value={comparar} onChange={(e) => setComparar(e.target.value)}><option value="mes_anterior">Mes anterior</option><option value="anio_anterior">Mismo mes del año anterior</option></Select></Field><Field label="Trayectoria"><Select value={meses} onChange={(e) => setMeses(Number(e.target.value))}><option value="6">6 meses</option><option value="12">12 meses</option></Select></Field></div>
    </header>
    <p className="finance-report-scope">Gastos por mes económico y dinero por fecha efectiva. Son lecturas diferentes: no se suman ni expresan rentabilidad. Variaciones nominales, sin ajuste por inflación.</p>
    {permisos.tiene("ver_gastos") ? <Consulta consulta={gastos}>{(d) => <section aria-label="Informe de gastos" className="finance-report-section">
      <div className="finance-report-section-title"><span aria-hidden="true">01</span><div><h2>Qué se registró como gasto</h2><p>Mes económico · {d.actual.periodo_economico.slice(0, 7)} frente a {d.anterior.periodo_economico.slice(0, 7)}</p></div></div>
      <Card className="finance-report-metrics"><Indicador titulo="Gastos aprobados" campo="aprobados" reporte={d} onAbrir={abrirGasto} /><Indicador titulo="Gastos por aprobar" campo="pendientes_aprobacion" reporte={d} onAbrir={abrirGasto} />
        <div className="finance-report-reading"><h3>Antes de interpretar</h3><p>{d.actual.mes_abierto ? "El mes está abierto. Compararlo con un mes cerrado puede mostrar una baja aparente." : "El cierre del mes calendario no certifica que toda la carga esté completa."}</p><p>{d.actual.actualizando ? "Repartos en actualización: su distribución aún no está disponible." : "El gasto aprobado ya incluye lo distribuido entre atenciones."}</p>{d.actual.ajustes_pendientes > 0 && <p>{d.actual.ajustes_pendientes} ajustes por aprobar; no alteran estos importes.</p>}</div>
      </Card>
      <div className="finance-report-charts"><SerieMensual reporte={d} medidas={medidasGastos} onAbrir={abrirGasto} /><Card className="finance-report-panel"><h3 className="font-semibold">Dónde cambió el gasto</h3><p className="text-sm text-texto-debil">Hasta ocho grupos con mayor gasto aprobado actual. Todos los grupos están en el detalle.</p>{d.agrupaciones.length ? <Grafico><Comparacion grupos={d.agrupaciones} periodoActual={d.actual.periodo_economico} periodoAnterior={d.anterior.periodo_economico} onAbrir={(g, periodo) => abrirGasto(d[periodo], "aprobados", g)} /></Grafico> : <EstadoVacio titulo="Sin gastos registrados en ambos períodos" />}</Card></div>
      <Card className="finance-report-panel"><h3 className="font-semibold">Área × concepto · comparación exacta</h3><p className="text-sm text-texto-debil">Cada importe abre todos sus gastos aprobados, incluso los que no tienen un control mensual configurado.</p><div className="finance-table"><div className="finance-table-content"><table><caption className="sr-only">Comparación exacta de gastos</caption><thead><tr><th>Área / concepto</th><th>{d.anterior.periodo_economico.slice(0, 7)}</th><th>{mes}</th><th>Variación nominal</th></tr></thead><tbody>{d.agrupaciones.map((g) => <tr key={`${g.area}:${g.concepto}`}><th scope="row" data-label="Área / concepto"><strong>{g.concepto_nombre}</strong><p className="text-texto-debil">{g.area_nombre}</p></th>{["anterior", "actual"].map((periodo) => <td key={periodo} data-label={d[periodo].periodo_economico.slice(0, 7)}>{g[periodo] ? <button className="finance-report-link" onClick={() => abrirGasto(d[periodo], "aprobados", g)}>{importeARS(g[periodo].aprobados)}</button> : "Sin registros"}</td>)}<td data-label="Variación"><Variacion dato={g.variacion} /></td></tr>)}</tbody></table></div></div></Card>
      <p className="finance-report-cut">Consultado {fechaHora(d.calculado_en)} · {d.alcance}</p>
    </section>}</Consulta> : <p className="finance-report-scope">Los gastos no están incluidos en tu acceso. No se representan como cero.</p>}
    {permisos.tiene("ver_dinero") ? <Consulta consulta={dinero}>{(d) => {
      const grupos = d.agrupaciones.filter((g) => g.filtros.tipo_cuenta === tipo && `${g.area_nombre} ${g.concepto_nombre} ${g.pagador_nombre}`.toLocaleLowerCase("es").includes(busqueda.toLocaleLowerCase("es")));
      return <section aria-label="Informe de dinero" className="finance-report-section">
        <div className="finance-report-section-title"><span aria-hidden="true">02</span><div><h2>Qué dinero se movió</h2><p>Fecha efectiva · {d.actual.fecha_desde} al {d.actual.fecha_hasta}</p></div></div>
        <Card className="finance-report-metrics">{[...medidasDinero, ["diferencia", "Diferencia del período"]].map(([campo, titulo]) => <Indicador key={campo} titulo={titulo} campo={campo} reporte={d} onAbrir={abrirDinero} />)}</Card>
        <p className="finance-report-scope">Cobros y pagos netos de devoluciones. La diferencia no es saldo disponible. {d.actual.mes_abierto && "Mes abierto: comparación provisional."} <button className="finance-report-link" onClick={() => abrirDinero(d.actual, "pendientes")}>{d.actual.por_aprobar.cantidad} movimientos por aprobar</button>, excluidos de los totales.</p>
        <SerieMensual reporte={d} medidas={medidasDinero} onAbrir={abrirDinero} />
        <Card className="finance-report-panel"><div className="flex flex-wrap items-end justify-between gap-3"><div><h3 className="font-semibold">Origen y destino del dinero</h3><p className="text-sm text-texto-debil">Cobros: área × prestación × financiador. Pagos: área × concepto de gasto.</p></div><div className="flex flex-wrap gap-2"><Select aria-label="Desglose de dinero" value={tipo} onChange={(e) => setTipo(e.target.value)}><option value="cobrar">Cobros por financiador</option><option value="pagar">Pagos por concepto</option></Select><Input aria-label="Buscar en desglose" placeholder="Buscar área, prestación, financiador…" value={busqueda} onChange={(e) => setBusqueda(e.target.value)} /></div></div>
          <p className="mt-3 text-sm text-texto-debil">Los copagos pertenecen al paciente. Un pagador sin vínculo estructurado no se atribuye a una obra social por su nombre. La búsqueda filtra este detalle; no cambia los totales del informe.</p>
          {!grupos.length ? <EstadoVacio titulo="Sin movimientos para este desglose" detalle="Revisá el tipo de movimiento y la búsqueda." /> : <div className="finance-table"><div className="finance-table-content"><table><caption className="sr-only">Desglose de dinero por área, concepto y financiador</caption><thead><tr><th>Área / concepto</th><th>{tipo === "cobrar" ? "Responsable del pago" : "Destino"}</th><th>Neto confirmado</th><th>Por aprobar</th></tr></thead><tbody>{grupos.map((g) => <tr key={JSON.stringify(g.filtros)}><th scope="row" data-label="Área / concepto"><strong>{g.concepto_nombre}</strong><p className="text-texto-debil">{g.area_nombre}</p></th><td data-label="Responsable / destino">{g.pagador_nombre}</td><td data-label="Neto confirmado"><button className="finance-report-link" onClick={() => abrirDinero(d.actual, tipo === "cobrar" ? "cobros_netos" : "pagos_netos", g)}>{g.cantidad_movimientos ? importeARS(g[tipo === "cobrar" ? "cobros_netos" : "pagos_netos"]) : "Sin movimientos aprobados"}</button></td><td data-label="Por aprobar"><button className="finance-report-link" onClick={() => abrirDinero(d.actual, "pendientes", g)}>{g.por_aprobar.cantidad} registros</button></td></tr>)}</tbody></table></div></div>}
        </Card><p className="finance-report-cut">Consultado {fechaHora(d.calculado_en)} · {d.alcance}</p>
      </section>;
    }}</Consulta> : <p className="finance-report-scope">Los pagos y cobros no están incluidos en tu acceso. No se representan como cero.</p>}
    <footer className="finance-report-scope">Alcance del informe: fuentes registradas y visibles. No certifica cobertura completa de la economía hospitalaria. Costos clínicos integrales, recursos donados y disponibilidad requieren sus fuentes y reglas de atribución.</footer>
    {detalle && <Modal title={`Fuentes del informe · ${detalle.periodo}`} onClose={() => setDetalle(null)} width={1040}><p className="font-semibold">{detalle.titulo}</p><p className="mt-2 text-sm text-texto-debil">Los reintegros se restan del cobro o pago original para explicar el neto. Se conserva la fecha efectiva de cada movimiento.</p><MovimientosPeriodo key={JSON.stringify(detalle.filtros)} filtros={detalle.filtros} institucion={institucion} permisos={permisos} onCuenta={setCuenta} /></Modal>}
    {cuenta != null && <DetalleCuenta id={cuenta} institucion={institucion} permisos={permisos} onClose={() => setCuenta(null)} />}
  </section>;
}
