import { memo, useCallback, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { decimalACentavos, importeARS } from "@/api/finanzas";
import { Select } from "@/components/ui";
import { AyudaFinanzas } from "./ControlesFinanzas";
import { coincideEstadoMes, tieneReferencia } from "./evolucion";

const medidas = {
  aprobados: { nombre: "Aprobado", color: "var(--color-badge-green-fg)" },
  pendientes_aprobacion: { nombre: "Por aprobar", color: "var(--color-badge-amber-fg)" },
  distribuido: { nombre: "Distribuido", color: "var(--color-badge-green-fg)" },
  sin_distribuir: { nombre: "Sin distribuir", color: "var(--color-texto-debil)" },
};
const compacto = new Intl.NumberFormat("es-AR", { notation: "compact", maximumFractionDigits: 1 });
const porcentaje = new Intl.NumberFormat("es-AR", { style: "percent", maximumFractionDigits: 1 });

// Fríos → cálidos, sin verde (reservado a estados en el resto del módulo).
const paletaParticipacion = [[225, 75, 52], [265, 70, 60], [300, 65, 43], [330, 80, 62], [390, 85, 48], [360, 75, 45]];
function colorParticipacion(posicion) {
  const tramo = posicion * (paletaParticipacion.length - 1);
  const inicio = Math.min(Math.floor(tramo), paletaParticipacion.length - 2);
  const [matiz, saturacion, luminosidad] = paletaParticipacion[inicio].map((valor, i) => valor + (paletaParticipacion[inicio + 1][i] - valor) * (tramo - inicio));
  return `hsl(${matiz % 360} ${saturacion}% ${luminosidad}%)`;
}
const escalaParticipacion = { background: `linear-gradient(to right, ${paletaParticipacion.map((_, i) => colorParticipacion(i / (paletaParticipacion.length - 1))).join(", ")})` };
const porNombre = (a, b) => a.nombre.localeCompare(b.nombre, "es") || a.indice - b.indice;
const porImporte = (a, b) => a.centavos == null ? (b.centavos == null ? porNombre(a, b) : 1)
  : b.centavos == null ? -1 : a.centavos === b.centavos ? porNombre(a, b) : a.centavos > b.centavos ? -1 : 1;

// Identidad, no posición ni importe: agregar/quitar conceptos no cambia su color.
// El ángulo áureo separa los identificadores consecutivos sin limitar categorías.
const colorConcepto = (id) => `hsl(${(Number(id) * 137.508) % 360} 65% 43%)`;

export function GraficoEvolucion({ series, estado, referencia, onMes, onQuitar }) {
  const contenedor = useRef(null);
  const [destacado, setDestacado] = useState(null);
  const [ayudaActiva, setAyudaActiva] = useState(false);
  const foco = series.some((s) => s.id === destacado) ? destacado : null;
  const datos = useMemo(() => series[0].meses.map((mes, indice) => ({
    periodo_economico: mes.periodo_economico,
    nombre: `${mes.periodo_economico.slice(5, 7)}/${mes.periodo_economico.slice(2, 4)}`,
    ...Object.fromEntries(series.flatMap((s) => {
      const fila = s.meses[indice];
      return [
        [`mes_${s.id}`, fila],
        [`confirmado_${s.id}`, coincideEstadoMes(fila, estado) && fila.estado === "completo" && fila.importe_aprobado != null ? Number(fila.importe_aprobado) : null],
        [`provisional_${s.id}`, coincideEstadoMes(fila, estado) && ["incompleto", "mes_abierto"].includes(fila.estado) && fila.importe_aprobado != null ? Number(fila.importe_aprobado) : null],
        [`referencia_${s.id}`, fila.monto_referencia == null ? null : Number(fila.monto_referencia)],
      ];
    })),
  })), [series, estado]);
  const seriesReferencia = referencia ? series.filter(tieneReferencia) : [];
  const opacidad = (id) => foco == null || foco === id ? 1 : 0.2;
  const punto = (serie) => ({ cx, cy, payload, value }) => {
    const fila = payload?.[`mes_${serie.id}`];
    if (!fila || value == null || !Number.isFinite(cx) || !Number.isFinite(cy)) return null;
    // El punto maneja su propio foco/activación. No debe activar además el
    // foco de todo LineChart: reposicionaría la ayuda entre pointerdown y click.
    return <circle cx={cx} cy={cy} r={5} strokeWidth={2} stroke={colorConcepto(serie.id)} fill={fila.estado === "completo" ? colorConcepto(serie.id) : "var(--color-superficie)"} opacity={opacidad(serie.id)} role="button" tabIndex={0} aria-label={`Ver gastos aprobados de ${fila.periodo_economico.slice(0, 7)} · ${serie.nombre}`} onFocus={(e) => e.stopPropagation()} className="cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent" onClick={() => onMes(fila, serie.id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); onMes(fila, serie.id); } }} />;
  };
  return <>
    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
    <ul aria-label="Conceptos comparados" className="flex flex-wrap gap-2">{series.map((s) => <li key={s.id} className="flex min-w-0 max-w-full items-center rounded-md border border-division">
      <button type="button" aria-label={`Destacar ${s.nombre}`} aria-pressed={foco === s.id} onClick={() => setDestacado(foco === s.id ? null : s.id)} className="flex min-w-0 items-center gap-2 rounded px-2 py-1 text-left text-sm hover:bg-superficie-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"><span aria-hidden="true" className="h-0.5 w-5 shrink-0" style={{ background: colorConcepto(s.id), opacity: opacidad(s.id) }} /><span className="min-w-0 break-words">{s.nombre}</span></button>
      <button type="button" aria-label={`Quitar concepto ${s.nombre}`} onClick={() => onQuitar(s.id)} className="shrink-0 rounded px-2 py-1 text-texto-debil hover:bg-superficie-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">×</button>
    </li>)}</ul>
    <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-texto-debil">{estado !== "provisional" && <span>● Carga y aprobación completas</span>}{estado !== "completo" && <span>○ Mes incompleto o abierto</span>}{seriesReferencia.length > 0 && <span>┄ Referencias · todo el período</span>}</div>
    </div>
    <div ref={contenedor} role="region" aria-label="Gráfico de evolución de gastos mensuales" className="finance-chart-canvas finance-evolution-space min-w-0"><ResponsiveContainer width="100%" height="100%"><LineChart data={datos} margin={{ top: 12, right: 12, bottom: 8, left: 0 }} accessibilityLayer>
      <CartesianGrid vertical={false} stroke="var(--color-division)" /><XAxis dataKey="nombre" tick={{ fill: "var(--color-texto-debil)", fontSize: 12 }} minTickGap={20} /><YAxis width={60} tickFormatter={(valor) => compacto.format(valor)} tick={{ fill: "var(--color-texto-debil)", fontSize: 12 }} />
      <ReferenceLine y={0} stroke="var(--color-texto-debil)" />
      <Tooltip active={ayudaActiva || undefined} filterNull={false} portal={document.body} wrapperStyle={{ position: "fixed", zIndex: 100, top: 0, left: 0 }} content={<DetalleEvolucion datos={datos} series={series} estado={estado} referencia={referencia} contenedor={contenedor} mantener={setAyudaActiva} />} />
      {series.flatMap((serie) => [
        <Line key={`confirmado_${serie.id}`} type="linear" dataKey={`confirmado_${serie.id}`} name={serie.nombre} stroke={colorConcepto(serie.id)} strokeOpacity={opacidad(serie.id)} strokeWidth={foco === serie.id ? 3 : 2} connectNulls={false} dot={punto(serie)} activeDot={punto(serie)} isAnimationActive="auto" animationBegin={0} animationDuration={350} animationEasing="ease-out" />,
        <Line key={`provisional_${serie.id}`} type="linear" dataKey={`provisional_${serie.id}`} name={`${serie.nombre} · provisional`} stroke="none" connectNulls={false} dot={punto(serie)} activeDot={punto(serie)} isAnimationActive={false} />,
      ])}
      {seriesReferencia.map((s) => <Line key={`referencia_${s.id}`} type="linear" dataKey={`referencia_${s.id}`} name={`Referencia · ${s.nombre}`} stroke={colorConcepto(s.id)} strokeOpacity={opacidad(s.id)} strokeDasharray="5 4" connectNulls={false} dot={{ r: 2, fill: "var(--color-superficie)" }} activeDot={false} isAnimationActive="auto" animationBegin={0} animationDuration={350} animationEasing="ease-out" />)}
    </LineChart></ResponsiveContainer></div>
  </>;
}

// El portal de Recharts conserva cierre con Escape. La ayuda se mide dentro
// del viewport para no cortarse en la tarjeta, incluso con muchos conceptos.
function DetalleEvolucion({ active, label, coordinate, datos, series, estado, referencia, contenedor, mantener }) {
  const panel = useRef(null);
  const [posicion, setPosicion] = useState({ left: 8, top: 8 });
  useLayoutEffect(() => {
    if (!active || !panel.current || !contenedor.current) return;
    const ubicar = () => {
      const origen = contenedor.current.getBoundingClientRect();
      const caja = panel.current.getBoundingClientRect();
      const x = origen.left + (coordinate?.x || 0);
      const y = origen.top + (coordinate?.y || 0);
      setPosicion({
        left: Math.max(8, Math.min(x + 12, window.innerWidth - caja.width - 8)),
        top: Math.max(8, Math.min(y - caja.height - 12, window.innerHeight - caja.height - 8)),
      });
    };
    ubicar();
    window.addEventListener("resize", ubicar);
    window.addEventListener("scroll", ubicar, true);
    return () => { window.removeEventListener("resize", ubicar); window.removeEventListener("scroll", ubicar, true); };
  }, [active, label, coordinate?.x, coordinate?.y, series, estado, referencia, contenedor]);
  const mes = datos.find((m) => m.nombre === label);
  if (!active || !mes) return null;
  return <div ref={panel} role="tooltip" style={posicion} onMouseEnter={() => mantener(true)} onMouseLeave={() => mantener(false)} onMouseMove={(e) => e.stopPropagation()} className="fixed max-h-[60vh] w-[300px] max-w-[calc(100vw-16px)] overflow-y-auto rounded-md border border-borde bg-superficie p-3 text-sm text-texto shadow-card">
    <strong>{mes.periodo_economico.slice(0, 7)}</strong>{series.map((s) => {
      const fila = mes[`mes_${s.id}`];
      const visible = coincideEstadoMes(fila, estado);
      const mostrarReferencia = referencia && tieneReferencia(s);
      if (!visible && !mostrarReferencia) return null;
      return <div key={s.id} className="mt-2 border-t border-division pt-2"><strong className="break-words">{s.nombre}</strong>{visible ? <><p className="break-words tabular-nums">Aprobado: {fila.importe_aprobado == null ? "Sin datos" : importeARS(fila.importe_aprobado)}</p><p className="text-xs text-texto-debil">{fila.estado === "completo" ? "Carga y aprobación completas" : fila.estado === "sin_control" ? "Sin configuración mensual vigente" : fila.estado === "sin_carga" ? "Carga sin completar: no equivale a cero" : "Provisional: no interpretar como ahorro"}</p></> : <p className="text-xs text-texto-debil">Gasto oculto por el filtro de estado</p>}{mostrarReferencia && <p>Referencia: {fila.monto_referencia == null ? "No disponible" : importeARS(fila.monto_referencia)}</p>}</div>;
    })}
  </div>;
}

function DetalleImportes({ active, payload, claves }) {
  const grupo = payload?.[0]?.payload?.grupo;
  const seleccionada = payload?.[0]?.payload?.clave;
  if (!active || !grupo) return null;
  return <div className="max-w-[280px] rounded-md border border-borde bg-superficie p-3 text-sm text-texto shadow-card">
    <strong>{grupo.area_nombre || "Institucional — sin área asignada"}</strong><p>{grupo.concepto_nombre}</p>
    {(seleccionada ? [seleccionada] : claves).map((clave) => <p key={clave} className="mt-1 tabular-nums">{medidas[clave].nombre}: {grupo[clave] == null ? "Actualización pendiente" : importeARS(grupo[clave])}</p>)}
  </div>;
}

// El foco/resaltado vive fuera: Pie reinicia su animación si cambian sus props.
const GraficoCircular = memo(function GraficoCircular({ internos, externos, celdasInternas, celdasExternas, tramaId, claves, abrir, abrirConcepto, resaltar }) {
  return <div role="region" aria-label="Gráfico de dos niveles por área, concepto y estado" className="finance-chart-canvas finance-pie-space min-w-0"><ResponsiveContainer width="100%" height="100%"><PieChart accessibilityLayer>
    <defs><pattern id={tramaId} width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="7" height="7" fill="var(--color-superficie-2)" /><line x1="0" y1="0" x2="0" y2="7" stroke="var(--color-texto-debil)" strokeWidth="2" /></pattern></defs>
    <Pie data={internos} dataKey="peso" nameKey="nombre" innerRadius={0} outerRadius="70%" label={false} labelLine={false} isAnimationActive="auto" animationBegin={0} animationDuration={350} animationEasing="ease-out" cursor="pointer" onMouseEnter={(dato) => resaltar(dato.indice)} onMouseLeave={() => resaltar(null)} onClick={(dato) => abrirConcepto(dato.grupo)}>
      {celdasInternas}
    </Pie>
    <Pie data={externos} dataKey="peso" nameKey="nombre" innerRadius="72%" outerRadius="96%" label={false} isAnimationActive="auto" animationBegin={0} animationDuration={350} animationEasing="ease-out" cursor="pointer" onMouseEnter={(dato) => resaltar(dato.indice)} onMouseLeave={() => resaltar(null)} onClick={(dato) => abrir(dato.grupo, dato.clave)}>
      {celdasExternas}
    </Pie><Tooltip content={<DetalleImportes claves={claves} />} />
  </PieChart></ResponsiveContainer></div>;
});

export default function GraficoFinanzas({ grupos, representacion, vista, onGastos, onRepartos }) {
  const [destacado, setDestacado] = useState(null);
  const [orden, setOrden] = useState("mayor");
  const tramaId = useId().replace(/:/g, "");
  const claves = useMemo(() => vista === "gastos" ? ["aprobados", "pendientes_aprobacion"] : ["distribuido", "sin_distribuir"], [vista]);
  // Number sólo posiciona el dibujo. Los importes de ayuda y listado conservan
  // las cadenas decimales originales; no se calcula dinero en el navegador.
  // Identidad estable: un sondeo sin cambios no vuelve a animar el gráfico.
  const datos = useMemo(() => grupos.map((grupo, indice) => {
    const centavos = claves.map((clave) => decimalACentavos(grupo[clave]));
    return { grupo, nombre: `${grupo.area_nombre || "Institucional"} · ${grupo.concepto_nombre}`, indice,
      centavos: centavos.includes("importe_invalido") ? null : centavos.reduce((total, valor) => total + BigInt(valor), 0n),
      ...Object.fromEntries(claves.map((clave) => [clave, grupo[clave] == null ? null : Number(grupo[clave])])) };
  }), [grupos, claves]);
  const barras = useMemo(() => [...datos].sort(orden === "nombre" ? porNombre : orden === "menor"
    ? (a, b) => a.centavos == null || b.centavos == null || a.centavos === b.centavos ? porImporte(a, b) : -porImporte(a, b)
    : porImporte), [datos, orden]);
  // Sólo geometría: ambos anillos usan el mismo orden y escala. Los importes
  // visibles siguen siendo los decimales del servidor, nunca esta suma float.
  const internos = useMemo(() => {
    const sectores = [...datos].sort(porImporte).map((dato) => ({ ...dato, peso: claves.reduce((total, clave) => total + (dato[clave] || 0), 0) }));
    const total = sectores.reduce((suma, dato) => suma + dato.peso, 0);
    const niveles = [...new Set(sectores.map((dato) => dato.centavos))];
    const posiciones = new Map(niveles.map((valor, i) => [valor, niveles.length === 1 ? 1 : 1 - i / (niveles.length - 1)]));
    return sectores.map((dato) => ({ ...dato, participacion: total > 0 ? dato.peso / total : 0,
      // Rangos exactos: importes iguales comparten color, sin amplificar ruido float.
      color: colorParticipacion(posiciones.get(dato.centavos)),
    }));
  }, [datos, claves]);
  const externos = useMemo(() => internos.flatMap((dato) => claves.map((clave) => ({ ...dato, clave, peso: dato[clave] }))), [internos, claves]);
  // Resaltar con CSS no cambia los sectores de Recharts ni reinicia su animación.
  const celdasInternas = useMemo(() => internos.map((dato) => <Cell key={dato.indice} className={`finance-sector finance-sector-${dato.indice}`} fill={dato.color} stroke="var(--color-superficie)" />), [internos]);
  const celdasExternas = useMemo(() => externos.map((dato) => <Cell key={`${dato.indice}:${dato.clave}`} className={`finance-sector finance-sector-${dato.indice}`} fill={dato.clave === claves[0] ? "var(--color-texto-debil)" : `url(#${tramaId})`} stroke="var(--color-superficie)" />), [externos, claves, tramaId]);
  const incompleto = datos.some((d) => claves.some((clave) => d[clave] == null));
  const invalido = datos.some((d) => claves.some((clave) => d[clave] != null && !Number.isFinite(d[clave])));
  const negativo = datos.some((d) => claves.some((clave) => d[clave] < 0));
  const cero = datos.every((d) => claves.every((clave) => d[clave] === 0));
  const abrir = useCallback((grupo, clave) => {
    if (!grupo || grupo[clave] == null) return;
    if (clave === "aprobados" || clave === "pendientes_aprobacion") onGastos(grupo, clave === "aprobados" ? "aprobado" : "pendiente_aprobacion");
    else onRepartos(clave === "distribuido" ? "distribuido" : "sin_distribuir", grupo);
  }, [onGastos, onRepartos]);
  const abrirConcepto = useCallback((grupo) => vista === "gastos" ? onGastos(grupo) : onRepartos(undefined, grupo), [vista, onGastos, onRepartos]);
  const aviso = invalido ? "No se pueden representar estos importes. Consultá sus valores exactos en Listado."
    : incompleto ? "Actualización pendiente: todavía no hay una distribución completa para graficar. Consultá el listado o la vista Gastos."
      : representacion === "dona" && negativo ? "Hay importes negativos: los anillos no los representan correctamente. Elegí Barras o Listado."
        : cero ? "Los importes de esta vista son cero. Podés consultar sus registros desde Listado." : null;
  const ayuda = <AyudaFinanzas titulo="Cómo explorar el gráfico"><p>{vista === "distribucion" ? "Distribuido + sin distribuir explican lo aprobado; no son gastos adicionales." : "Gastos aprobados y pendientes de aprobación, separados."}</p><p>Seleccioná una barra o porción para abrir sus registros. La ayuda del dibujo muestra los importes exactos en ARS. Ordenar compara la suma de las dos series, no una sola.</p><p>En Listado podés recorrer todos los importes con el teclado. Las escalas del gráfico son aproximadas; los centavos se conservan en la ayuda y en el listado.</p><p>Dos niveles: el interior identifica área y concepto; el exterior divide ese mismo importe por estado. No sumes ambos anillos. El interior abre todos los registros del concepto; el exterior filtra además el estado. No se dibuja con negativos ni con resultados pendientes.</p></AyudaFinanzas>;
  return <div className="flex min-h-0 flex-1 flex-col gap-2 p-4">
    {aviso ? <p role="status" className="rounded-md bg-superficie-2 p-4 text-md">{aviso}</p> : <>
      {representacion === "barras" ? <>
        <div className="flex min-h-10 flex-wrap items-center justify-between gap-3 text-sm"><div className="flex flex-wrap gap-4">{claves.map((clave) => <span key={clave} className="inline-flex items-center gap-2"><span className="h-3 w-3 rounded-sm" style={{ background: medidas[clave].color }} />{medidas[clave].nombre}</span>)}</div><div className="flex items-center gap-2"><label className="flex items-center gap-2">Ordenar<Select className="w-[200px]" value={orden} onChange={(e) => setOrden(e.target.value)}><option value="mayor">Mayor importe primero</option><option value="menor">Menor importe primero</option><option value="nombre">Área y concepto</option></Select></label>{ayuda}</div></div>
        <div role="region" aria-label="Gráfico de barras por área y concepto" className="finance-chart-canvas min-w-0 flex-1" style={{ minHeight: Math.max(180, datos.length * 56 + 36) }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barras} layout="vertical" margin={{ top: 8, right: 24, bottom: 8, left: 0 }} accessibilityLayer>
              <CartesianGrid horizontal={false} stroke="var(--color-division)" />
              <XAxis type="number" tickFormatter={(valor) => compacto.format(valor)} tick={{ fill: "var(--color-texto-debil)", fontSize: 12 }} />
              <YAxis type="category" dataKey="nombre" width={180} tick={{ fill: "var(--color-texto-debil)", fontSize: 12 }} interval={0} />
              <ReferenceLine x={0} stroke="var(--color-texto-debil)" />
              <Tooltip content={<DetalleImportes claves={claves} />} cursor={{ fill: "var(--color-superficie-2)" }} />
              {claves.map((clave) => <Bar key={clave} dataKey={clave} name={medidas[clave].nombre} fill={medidas[clave].color} maxBarSize={20} isAnimationActive="auto" animationBegin={0} animationDuration={350} animationEasing="ease-out" cursor="pointer" onClick={(dato) => abrir(dato.grupo || dato.payload?.grupo, clave)} />)}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </> : <>
        <div className="flex min-h-8 flex-wrap items-center justify-between gap-3 text-sm"><div className="flex flex-wrap items-center gap-4"><span className="text-texto-debil">Exterior</span>{claves.map((clave, i) => <span key={clave} className="inline-flex items-center gap-2"><span aria-hidden="true" className={`h-3 w-3 rounded-sm ${i === 0 ? "bg-texto-debil" : "finance-state-pattern"}`} />{medidas[clave].nombre}</span>)}</div>{ayuda}</div>
        <div className="finance-chart-layout" data-finance-emphasis={destacado}>
          <style>{destacado == null ? "" : `.finance-chart-layout[data-finance-emphasis="${destacado}"] .finance-sector:not(.finance-sector-${destacado}) { fill-opacity: 0.3; }`}</style>
          <div className="finance-chart-categories min-w-0"><div className="mb-2 flex flex-wrap items-center gap-2 text-sm text-texto-debil"><span>Menor</span><span aria-hidden="true" className="finance-weight-scale h-3 w-24 rounded-sm" style={escalaParticipacion} /><span>Mayor participación</span><AyudaFinanzas titulo="Colores de participación"><p>Los conceptos se ordenan de mayor a menor participación. La escala interior va de azul a rojo, usando los extremos primero e incorporando tonos intermedios según la cantidad de participaciones distintas. Los importes iguales comparten color.</p><p>El color expresa posición relativa, no una identidad fija del concepto. Se recalcula con los datos o la comparación. Rojo no significa error ni gasto indebido. Los porcentajes son aproximados.</p><p>El exterior sólido representa {medidas[claves[0]].nombre.toLowerCase()}; el rayado representa {medidas[claves[1]].nombre.toLowerCase()}. Ambos niveles representan el mismo dinero.</p></AyudaFinanzas></div>
          <ul aria-label="Importes del gráfico de dos niveles" className="grid min-w-0 gap-2 text-sm">{internos.map((dato) => <li key={dato.indice} className="min-w-0 border-b border-division pb-2" onMouseEnter={() => setDestacado(dato.indice)} onMouseLeave={() => setDestacado(null)} onFocus={() => setDestacado(dato.indice)} onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setDestacado(null); }}><button className="flex w-full items-start gap-2 rounded-md px-1 text-left hover:bg-superficie-2" onClick={() => abrirConcepto(dato.grupo)}><span className="mt-1 h-3 w-3 shrink-0 rounded-sm" style={{ background: dato.color }} /><span className="min-w-0 break-words">{dato.nombre} <span className="tabular-nums text-texto-debil">· ≈ {porcentaje.format(dato.participacion)}</span></span></button><div className="mt-1 flex flex-wrap gap-2">{claves.map((clave) => <button key={clave} className="rounded p-1 text-left text-accent underline underline-offset-2" onClick={() => abrir(dato.grupo, clave)}>{medidas[clave].nombre}: <span className="tabular-nums">{importeARS(dato.grupo[clave])}</span></button>)}</div></li>)}</ul></div>
          <GraficoCircular internos={internos} externos={externos} celdasInternas={celdasInternas} celdasExternas={celdasExternas} tramaId={tramaId} claves={claves} abrir={abrir} abrirConcepto={abrirConcepto} resaltar={setDestacado} />
        </div>
      </>}
    </>}
  </div>;
}
