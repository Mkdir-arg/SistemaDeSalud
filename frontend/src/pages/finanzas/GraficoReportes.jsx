import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { importeARS } from "@/api/finanzas";

// Number se usa exclusivamente para la geometría; ayudas y tablas muestran
// las cadenas decimales del servidor, sin recalcular importes en el cliente.
const compacto = new Intl.NumberFormat("es-AR", { notation: "compact", maximumFractionDigits: 1 });
const colores = { aprobados: "#287f92", cobros_netos: "#287f92", pagos_netos: "#ad7133", actual: "#287f92", anterior: "#82949e" };
export const nombreMes = (fecha) => new Intl.DateTimeFormat("es-AR", { month: "short", year: "2-digit", timeZone: "UTC" }).format(new Date(`${fecha}T12:00:00Z`));

function Ayuda({ active, payload, label, medidas }) {
  if (!active || !payload?.length) return null;
  const fila = payload[0].payload;
  return <div role="tooltip" className="finance-report-tooltip"><strong>{fila.titulo || label}</strong>
    {medidas.map(([campo, nombre]) => <p key={campo}>{nombre}: <strong>{fila.exactos[campo] == null ? "Sin registros comparables" : importeARS(fila.exactos[campo])}</strong></p>)}
    {fila.abierto && <p>Lectura provisional: mes abierto, carga o aprobación pendiente</p>}
    <p className="text-xs text-texto-debil">Seleccioná el gráfico o usá el listado para ver el origen.</p>
  </div>;
}

export function TendenciaReporte({ serie, medidas, onAbrir }) {
  const datos = serie.map((fila) => {
    const disponible = (fila.cantidad_registros ?? fila.cantidad_movimientos) > 0;
    return { mes: nombreMes(fila.periodo_economico), titulo: fila.periodo_economico.slice(0, 7), fila, abierto: fila.provisional ?? fila.mes_abierto,
      exactos: Object.fromEntries(medidas.map(([campo]) => [campo, disponible ? fila[campo] : null])),
      ...Object.fromEntries(medidas.map(([campo]) => [campo, disponible ? Number(fila[campo]) : null])) };
  });
  const punto = (campo, activo = false) => ({ cx, cy, payload, value }) => value == null ? null : <circle key={`${campo}:${payload.mes}`} cx={cx} cy={cy} r={activo ? 6 : 4} fill={payload.abierto ? "var(--color-superficie)" : colores[campo]} stroke={colores[campo]} strokeWidth={2} style={{ cursor: "pointer" }} onClick={() => onAbrir(payload.fila, campo)} />;
  return <div className="finance-report-trend" role="img" aria-label="Tendencia mensual; importes y navegación disponibles en la tabla">
    <ResponsiveContainer width="100%" height="100%"><LineChart data={datos} margin={{ top: 20, right: 20, bottom: 0, left: 0 }} accessibilityLayer>
      <CartesianGrid vertical={false} stroke="var(--color-division)" /><XAxis dataKey="mes" tick={{ fill: "var(--color-texto-debil)", fontSize: 12 }} /><YAxis width={66} tickFormatter={(v) => compacto.format(v)} tick={{ fill: "var(--color-texto-debil)", fontSize: 12 }} />
      <ReferenceLine y={0} stroke="var(--color-texto-debil)" /><Tooltip content={<Ayuda medidas={medidas} />} /><Legend />
      {medidas.map(([campo, nombre]) => <Line key={campo} dataKey={campo} name={nombre} type="linear" stroke={colores[campo]} strokeWidth={2.5} strokeDasharray={campo === "pagos_netos" ? "6 3" : undefined} connectNulls={false} dot={punto(campo)} activeDot={punto(campo, true)} isAnimationActive={false} />)}
    </LineChart></ResponsiveContainer>
  </div>;
}

export function ComparacionGrupos({ grupos, periodoActual, periodoAnterior, onAbrir }) {
  const medidas = [["anterior", periodoAnterior.slice(0, 7)], ["actual", periodoActual.slice(0, 7)]];
  const datos = [...grupos].sort((a, b) => Number(b.actual?.aprobados || 0) - Number(a.actual?.aprobados || 0)).slice(0, 8).map((g, i) => ({
    nombre: `${i + 1}. ${g.concepto_nombre}`, titulo: `${g.area_nombre} · ${g.concepto_nombre}`, grupo: g,
    actual: g.actual ? Number(g.actual.aprobados) : null, anterior: g.anterior ? Number(g.anterior.aprobados) : null,
    exactos: { actual: g.actual?.aprobados ?? null, anterior: g.anterior?.aprobados ?? null },
  }));
  return <div role="img" aria-label="Comparación de gastos por área y concepto; detalle exacto en la tabla" style={{ height: Math.max(220, datos.length * 65 + 65) }}>
    <ResponsiveContainer width="100%" height="100%"><BarChart data={datos} layout="vertical" margin={{ top: 10, right: 18, bottom: 0, left: 0 }} accessibilityLayer>
      <CartesianGrid horizontal={false} stroke="var(--color-division)" /><XAxis type="number" tickFormatter={(v) => compacto.format(v)} tick={{ fill: "var(--color-texto-debil)", fontSize: 12 }} /><YAxis type="category" dataKey="nombre" width={125} tick={{ fill: "var(--color-texto-debil)", fontSize: 11 }} interval={0} />
      <ReferenceLine x={0} stroke="var(--color-texto-debil)" /><Tooltip content={<Ayuda medidas={medidas} />} /><Legend />
      {medidas.map(([campo, nombre]) => <Bar key={campo} dataKey={campo} name={nombre} fill={colores[campo]} maxBarSize={13} radius={[0, 2, 2, 0]} isAnimationActive={false} cursor="pointer" onClick={(dato) => onAbrir(dato.grupo || dato.payload?.grupo, campo)} />)}
    </BarChart></ResponsiveContainer>
  </div>;
}
