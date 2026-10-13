import { useState } from "react";
import { Icon } from "@/components/icons";
import { Button, Checkbox } from "@/components/ui";
import { Buscador } from "@/components/ui/filtros";
import { PanelFlotante } from "@/pages/finanzas/ControlesFinanzas";
import { COLUMNAS_PREDETERMINADAS, GRUPOS_PADRON, cambiarColumnasPadron } from "./padronTablaEstado";

const normalizar = (texto) => texto.toLocaleLowerCase("es").normalize("NFD").replace(/\p{Diacritic}/gu, "");

/** Elegir columnas sin mover la página: panel flotante con buscador y grupos. */
export default function ColumnasPadron({ elegidas, parametros, onParametrosChange }) {
  const [busca, setBusca] = useState("");
  const clave = normalizar(busca.trim());
  const cambiar = (claves) => onParametrosChange(cambiarColumnasPadron(parametros, claves));
  const grupos = GRUPOS_PADRON.map((g) => ({ ...g, columnas: g.columnas.filter((c) => !clave || normalizar(c.label).includes(clave) || normalizar(g.titulo).includes(clave)) })).filter((g) => g.columnas.length);
  const personalizadas = parametros.has("columnas");
  return <PanelFlotante titulo="Columnas visibles" nombre={`Columnas visibles (${elegidas.length})`} activo={personalizadas}
    etiqueta={<><Icon name="layers" size={15} />Columnas<span className="rounded-pill bg-superficie-2 px-1.5 text-xs font-semibold tabular-nums text-texto-medio">{elegidas.length}</span></>}>
    <Buscador aria-label="Buscar columna" placeholder="Buscar columna…" valor={busca} onChange={setBusca} />
    <div className="-mx-4 mt-3 max-h-[min(55vh,26rem)] overflow-y-auto border-y border-division px-4 py-2">
      {grupos.map((g) => {
        const opcionales = g.columnas.filter((c) => !c.required);
        const todas = opcionales.every((c) => elegidas.includes(c.key));
        return <div key={g.titulo} role="group" aria-label={g.titulo} className="py-2">
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-texto-debil">{g.titulo}</span>
            {opcionales.length > 1 && <button type="button" className="text-xs font-medium text-accent hover:underline"
              aria-label={`${todas ? "Ocultar" : "Mostrar"} todas las columnas de ${g.titulo}`}
              onClick={() => cambiar(todas ? elegidas.filter((k) => !opcionales.some((c) => c.key === k)) : [...elegidas, ...opcionales.map((c) => c.key)])}>{todas ? "Ocultar todas" : "Mostrar todas"}</button>}
          </div>
          <div className="space-y-1.5">{g.columnas.map((col) => <Checkbox key={col.key} label={col.label} checked={elegidas.includes(col.key)} disabled={col.required}
            title={col.required ? "Siempre visible" : undefined}
            onChange={(e) => cambiar(e.target.checked ? [...elegidas, col.key] : elegidas.filter((k) => k !== col.key))} />)}</div>
        </div>;
      })}
      {!grupos.length && <p className="py-4 text-center text-sm text-texto-debil">Ninguna columna coincide.</p>}
    </div>
    <div className="mt-3 flex items-center justify-between gap-2">
      <span className="text-xs text-texto-debil">Afiliado y N.º son fijas.</span>
      <Button type="button" variant="secondary" size="sm" className="whitespace-nowrap" disabled={!personalizadas} onClick={() => cambiar(COLUMNAS_PREDETERMINADAS)}>Restaurar columnas</Button>
    </div>
  </PanelFlotante>;
}
