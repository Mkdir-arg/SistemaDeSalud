import { Card } from "@/components/ui";
import { duracionMinutos } from "@/lib/format";

// Fechas locales: el rango no cambia de día por la conversión a UTC.
export const isoLocal = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
export const isoHoy = () => isoLocal(new Date());
export const isoHace = (dias) => {
  const x = new Date();
  x.setDate(x.getDate() - (dias - 1));
  return isoLocal(x);
};
export const fechaValida = (iso) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso || "")) return false;
  const fecha = new Date(`${iso}T12:00:00`);
  return !Number.isNaN(fecha.getTime()) && isoLocal(fecha) === iso;
};
export const isoAntes = (hasta, dias) => {
  const fecha = new Date(`${hasta}T12:00:00`);
  fecha.setDate(fecha.getDate() - (dias - 1));
  return isoLocal(fecha);
};
export const fechaCorta = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : "—");

export function alertasOperacion(r) {
  if (!r) return [];
  return [
    ...(r.urgentes > 0 ? [{ l: "Urgentes", v: r.urgentes, destacado: true }] : []),
    ...(r.espera_prom_min >= 30 ? [{ l: "Espera prom.", v: duracionMinutos(r.espera_prom_min), destacado: true }] : []),
    ...(r.turnos_sin_registrar > 0 ? [{ l: "Turnos sin registrar", v: r.turnos_sin_registrar }] : []),
  ];
}

export function KpiDireccion({ titulo, valor, detalle }) {
  return <Card className="min-w-0 p-3.5"><h3 className="text-xs text-texto-suave">{titulo}</h3><p className="mt-2 text-xxl font-bold tabular-nums">{valor}</p><p className="mt-1 truncate text-xs text-texto-suave" title={detalle}>{detalle}</p></Card>;
}

export function BarrasIngresos({ serie = [] }) {
  const maximo = Math.max(1, ...serie.map((punto) => punto.casos || 0));
  return <div className="mt-5"><div className="flex h-36 items-end gap-1.5 border-b border-division">
    {serie.map((punto) => <div key={punto.fecha} className="group relative flex h-full min-w-0 flex-1 items-end" title={`${fechaCorta(punto.fecha)}: ${punto.casos} ingresos`}><div className="w-full rounded-t-sm bg-accent-fuerte" style={{ height: `${Math.max(punto.casos ? 5 : 0, (punto.casos / maximo) * 100)}%` }} /></div>)}
  </div><div className="mt-2 flex justify-between text-[10px] text-texto-tenue"><span>{fechaCorta(serie[0]?.fecha)}</span><span>{serie.some((punto) => punto.casos) ? "Ingresos registrados" : "Sin ingresos en el período"}</span><span>{fechaCorta(serie.at(-1)?.fecha)}</span></div></div>;
}

export function ResumenDireccion({ titulo, filas, vacio, limite = 4 }) {
  const tieneDatos = filas.some((fila) => fila.valor);
  return <Card className="p-4"><h3 className="mb-4 text-sm font-bold">{titulo}</h3>
    {vacio && !tieneDatos ? <p className="text-xs text-texto-suave">{vacio}</p> : <div className="space-y-3">{filas.slice(0, limite).map((fila) => <div key={fila.nombre} className="text-xs"><div className="mb-1 flex justify-between gap-2"><span>{fila.nombre}</span><span className="tabular-nums text-texto-suave">{fila.valor}{fila.detalle ? ` · ${fila.detalle}` : ""}</span></div><div className="h-1.5 overflow-hidden rounded-pill bg-superficie-2"><div className="h-full rounded-pill bg-accent-fuerte" style={{ width: `${Math.min(100, (fila.valor / fila.total) * 100)}%` }} /></div></div>)}</div>}
  </Card>;
}
