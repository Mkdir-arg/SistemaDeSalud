import { useEffect, useRef, useState } from "react";
import { api } from "@/api/client";
import { errorFinanciador, rutaFinanciador } from "@/api/financiadores";
import { Button } from "@/components/ui";

export default function ExportarPadron({ organizacion, query, total, consultando, filtrosPendientes = false, errorConsulta }) {
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);
  const activo = useRef(true);
  const actual = useRef(query.toString());
  const consultaBloqueada = useRef(filtrosPendientes);
  consultaBloqueada.current = filtrosPendientes;
  actual.current = query.toString();
  useEffect(() => { activo.current = true; return () => { activo.current = false; }; }, []);
  async function exportar() {
    if (ocupado || consultando || filtrosPendientes || errorConsulta || total === 0 || total > 5000) return;
    const captura = actual.current;
    const parametros = new URLSearchParams(captura);
    parametros.delete("page"); parametros.delete("page_size");
    parametros.set("formato", "xlsx");
    setOcupado(true); setError(null);
    try { await api.download(`${rutaFinanciador(organizacion.id, "padron")}exportar/?${parametros}`, `padron-${organizacion.id}.xlsx`, () => activo.current && actual.current === captura && !consultaBloqueada.current); }
    catch (err) { if (activo.current && actual.current === captura) setError(err); }
    finally { if (activo.current) setOcupado(false); }
  }
  return <div className="space-y-2"><div className="flex flex-wrap items-center gap-3"><Button variant="secondary" disabled={ocupado || consultando || filtrosPendientes || Boolean(errorConsulta) || total === 0 || total > 5000} onClick={exportar}>{ocupado ? "Exportando…" : "Exportar XLSX"}</Button><p className="text-sm text-texto-debil">Todas las filas filtradas y ordenadas, con las columnas elegidas. Hasta 5000 registros; sin salud ni cobranza.</p></div>{total > 5000 && <p role="status" className="text-sm text-badge-amber-fg">El resultado supera 5000 registros. Acotá los filtros para descargarlo completo.</p>}{error && <p role="alert" className="text-sm text-badge-error-fg">{errorFinanciador(error)}</p>}</div>;
}
