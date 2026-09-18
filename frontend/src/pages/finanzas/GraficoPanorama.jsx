import { Bar, BarChart, CartesianGrid, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { importeARS } from "@/api/finanzas";

// Number sólo posiciona el dibujo; la ayuda muestra las cadenas decimales del
// servidor. Petróleo identifica lo cobrado y lo directo; ocre lo pagado y lo
// atribuido. Ninguno de los dos indica éxito ni error.
const compacto = new Intl.NumberFormat("es-AR", { notation: "compact", maximumFractionDigits: 1 });
const colores = { cobros_netos: "#287f92", pagos_netos: "#ad7133", directo_conocido: "#287f92", compartido_conocido: "#ad7133" };

function AyudaPanorama({ active, payload, medidas }) {
  const fila = payload?.[0]?.payload;
  if (!active || !fila) return null;
  return <div role="tooltip" className="finance-report-tooltip"><strong>{fila.nombre}</strong>
    {medidas.map(([campo, nombre]) => <p key={campo}>{nombre}: <strong>{fila.exactos[campo] == null ? "Sin registros" : importeARS(fila.exactos[campo])}</strong></p>)}
    {fila.detalle && <p className="text-xs text-texto-debil">{fila.detalle}</p>}
  </div>;
}

// Las series se comparan lado a lado, nunca apiladas: sumarlas inventaría un
// total que el módulo no calcula (gasto atribuido no es costo adicional).
export default function BarrasPanorama({ filas, medidas, etiqueta, onAbrir }) {
  const datos = filas.map((fila) => ({
    nombre: fila.nombre, detalle: fila.detalle, fila,
    exactos: Object.fromEntries(medidas.map(([campo]) => [campo, fila[campo] ?? null])),
    ...Object.fromEntries(medidas.map(([campo]) => [campo, fila[campo] == null ? null : Number(fila[campo])])),
  }));
  return <div role="region" aria-label={etiqueta} className="finance-chart-canvas min-w-0" style={{ minHeight: Math.max(190, datos.length * 62 + 56) }}>
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={datos} layout="vertical" margin={{ top: 8, right: 24, bottom: 0, left: 0 }} accessibilityLayer>
        <CartesianGrid horizontal={false} stroke="var(--color-division)" />
        <XAxis type="number" tickFormatter={(valor) => compacto.format(valor)} tick={{ fill: "var(--color-texto-debil)", fontSize: 12 }} />
        <YAxis type="category" dataKey="nombre" width={170} tick={{ fill: "var(--color-texto-debil)", fontSize: 12 }} interval={0} />
        <ReferenceLine x={0} stroke="var(--color-texto-debil)" />
        <Tooltip content={<AyudaPanorama medidas={medidas} />} cursor={{ fill: "var(--color-superficie-2)" }} />
        <Legend />
        {medidas.map(([campo, nombre]) => <Bar key={campo} dataKey={campo} name={nombre} fill={colores[campo]} maxBarSize={16} radius={[0, 2, 2, 0]}
          isAnimationActive={false} cursor="pointer" onClick={(dato) => onAbrir(dato.fila || dato.payload?.fila)} />)}
      </BarChart>
    </ResponsiveContainer>
  </div>;
}
