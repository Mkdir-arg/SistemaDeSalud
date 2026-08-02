import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useLista } from "@/api/queries";
import { Icon } from "@/components/icons";
import { EstadoError, EstadoVacio, SkeletonTabla } from "@/components/ui/estados";
import { cn } from "@/lib/cn";

const TAMANOS = [25, 50, 100];
const CLAVE_DENSIDAD = "cauce.densidad";

/**
 * Estado de la tabla en la URL: página y orden.
 *
 * Van en la URL y no en useState para que una vista filtrada se pueda **compartir
 * y recargar**: «mirá los casos de guardia ordenados por antigüedad» es un link,
 * no una instrucción. Se prefijan con `clave` para que dos tablas en la misma
 * pantalla no se pisen.
 *
 * La densidad NO va en la URL: es preferencia de la persona, no de la vista (no
 * querés imponerle tu densidad a quien abre tu link). Va en localStorage.
 */
export function useTablaUrl(clave, { ordenInicial = "", tamanoInicial = 25 } = {}) {
  const [params, setParams] = useSearchParams();
  const k = (n) => `${clave}_${n}`;

  const pagina = Number(params.get(k("pag"))) || 1;
  const orden = params.get(k("ord")) ?? ordenInicial;
  const tamano = Number(params.get(k("tam"))) || tamanoInicial;

  const set = useCallback(
    (cambios) => {
      const p = new URLSearchParams(params);
      for (const [n, v] of Object.entries(cambios)) {
        if (v === null || v === "" || v === undefined) p.delete(k(n));
        else p.set(k(n), String(v));
      }
      setParams(p, { replace: true });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [params, setParams, clave],
  );

  const [densidad, setDensidadState] = useState(
    () => localStorage.getItem(CLAVE_DENSIDAD) || "comoda",
  );
  const setDensidad = (d) => {
    localStorage.setItem(CLAVE_DENSIDAD, d);
    setDensidadState(d);
  };

  return {
    pagina,
    orden,
    tamano,
    densidad,
    setDensidad,
    irA: (n) => set({ pag: n <= 1 ? null : n }),
    // Al reordenar se vuelve a la página 1: seguir en la 7 de un orden nuevo no
    // significa nada y desorienta.
    ordenarPor: (campo) => {
      const nuevo = orden === campo ? `-${campo}` : orden === `-${campo}` ? "" : campo;
      set({ ord: nuevo || null, pag: null });
    },
    cambiarTamano: (n) => set({ tam: n === tamanoInicial ? null : n, pag: null }),
  };
}

/** Encabezado de columna: botón si es ordenable, texto si no. */
function Encabezado({ col, orden, ordenarPor, compacta }) {
  const activo = orden === col.orden || orden === `-${col.orden}`;
  const desc = orden === `-${col.orden}`;
  const clases = cn(
    "whitespace-nowrap px-lg text-left text-sm font-semibold text-texto-debil",
    compacta ? "py-2" : "py-3",
    col.className,
  );

  if (!col.orden) {
    return (
      <th scope="col" className={clases}>
        {col.label}
      </th>
    );
  }
  return (
    <th
      scope="col"
      className={cn(clases, "p-0")}
      aria-sort={activo ? (desc ? "descending" : "ascending") : "none"}
    >
      <button
        type="button"
        onClick={() => ordenarPor(col.orden)}
        className={cn(
          "group flex w-full items-center gap-1.5 px-lg text-left text-sm font-semibold",
          compacta ? "py-2" : "py-3",
          activo ? "text-accent" : "text-texto-debil hover:text-texto-medio",
        )}
        // Sin esto, el nombre accesible del botón es solo «Caso»: no se anuncia
        // que ordena ni en qué sentido. Incluye el texto visible, como pide el
        // criterio «Label in Name» de WCAG.
        aria-label={`Ordenar por ${col.label}${activo ? (desc ? " (descendente)" : " (ascendente)") : ""}`}
        title={`Ordenar por ${col.label}`}
      >
        {col.label}
        <Icon
          name={activo ? (desc ? "arrowDown" : "arrowUp") : "ordenable"}
          size={13}
          className={activo ? "" : "opacity-0 transition-opacity group-hover:opacity-60"}
        />
      </button>
    </th>
  );
}

/** Pie con el rango visible y la navegación. */
function Paginador({ pagina, paginas, total, tamano, desde, hasta, irA, cambiarTamano }) {
  const btn =
    "flex size-8 items-center justify-center rounded-md border border-borde text-texto-suave " +
    "enabled:hover:bg-superficie-2 disabled:opacity-40 disabled:cursor-not-allowed";
  return (
    <div className="flex flex-wrap items-center justify-between gap-md border-t border-division px-lg py-2.5">
      <div className="text-base text-texto-debil">
        {total === 0 ? "Sin resultados" : <>Mostrando <b className="font-semibold text-texto-medio">{desde}–{hasta}</b> de <b className="font-semibold text-texto-medio">{total}</b></>}
      </div>
      <div className="flex items-center gap-md">
        <label className="flex items-center gap-1.5 text-sm text-texto-debil">
          Filas
          <select
            value={tamano}
            onChange={(e) => cambiarTamano(Number(e.target.value))}
            className="h-8 rounded-md border border-campo-borde bg-superficie px-1.5 text-base outline-none"
          >
            {TAMANOS.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <div className="flex items-center gap-1">
          <button className={btn} onClick={() => irA(1)} disabled={pagina <= 1} aria-label="Primera página"><Icon name="chevronsLeft" size={15} /></button>
          <button className={btn} onClick={() => irA(pagina - 1)} disabled={pagina <= 1} aria-label="Página anterior"><Icon name="chevronLeft" size={15} /></button>
          <span className="px-2 text-base tabular-nums text-texto-suave">{pagina} / {paginas}</span>
          <button className={btn} onClick={() => irA(pagina + 1)} disabled={pagina >= paginas} aria-label="Página siguiente"><Icon name="chevronRight" size={15} /></button>
          <button className={btn} onClick={() => irA(paginas)} disabled={pagina >= paginas} aria-label="Última página"><Icon name="chevronsRight" size={15} /></button>
        </div>
      </div>
    </div>
  );
}

/**
 * Tabla de datos con paginación de servidor, orden y densidad.
 *
 * Presentacional: recibe las filas ya cargadas. Para el caso normal —listar un
 * recurso de la API— usar `TablaRecurso`, que le enchufa la consulta.
 */
export function DataTable({
  columnas,
  filas,
  total = 0,
  paginas = 1,
  estado,
  onRowClick,
  vacio = {},
  tabla,
  barra,
}) {
  const { pagina, orden, tamano, densidad, setDensidad, irA, ordenarPor, cambiarTamano } = tabla;
  const compacta = densidad === "compacta";
  const { cargando, refrescando, error, reintentar } = estado;

  const desde = total === 0 ? 0 : (pagina - 1) * tamano + 1;
  const hasta = Math.min(pagina * tamano, total);

  return (
    <div className="overflow-hidden rounded-lg border border-borde bg-superficie">
      {/* La barra existe siempre: aunque no haya filtros, aloja la densidad. */}
      <div className="flex flex-wrap items-center justify-between gap-md border-b border-division px-lg py-2.5">
        <div className="flex flex-wrap items-center gap-md">{barra}</div>
        <button
          type="button"
          onClick={() => setDensidad(compacta ? "comoda" : "compacta")}
          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-sm text-texto-debil hover:bg-superficie-2 hover:text-texto-medio"
          title={compacta ? "Ver más espaciado" : "Ver más filas en pantalla"}
        >
          <Icon name="rows" size={15} />
          {compacta ? "Cómoda" : "Compacta"}
        </button>
      </div>

      {error ? (
        <EstadoError error={error} onReintentar={reintentar} />
      ) : cargando ? (
        <SkeletonTabla filas={Math.min(tamano, 10)} columnas={columnas.length} />
      ) : filas.length === 0 ? (
        <EstadoVacio titulo={vacio.titulo || "Sin resultados"} detalle={vacio.detalle} accion={vacio.accion} />
      ) : (
        <>
          {/* El scroll horizontal vive acá dentro: el body de la página nunca
              debe desplazarse en horizontal. */}
          <div className="overflow-x-auto">
            <table
              className={cn(
                "w-full border-collapse text-md",
                // Mientras llega otra página se atenúa en vez de desmontarse:
                // así la tabla no salta ni pierde el scroll.
                refrescando && "opacity-60 transition-opacity",
              )}
            >
              <thead className="sticky top-0 z-10 bg-superficie-2">
                <tr>
                  {columnas.map((c) => (
                    <Encabezado key={c.key} col={c} orden={orden} ordenarPor={ordenarPor} compacta={compacta} />
                  ))}
                </tr>
              </thead>
              <tbody>
                {filas.map((f) => (
                  <tr
                    key={f.id}
                    onClick={onRowClick ? () => onRowClick(f) : undefined}
                    tabIndex={onRowClick ? 0 : undefined}
                    onKeyDown={
                      onRowClick
                        ? (e) => { if (e.key === "Enter") { e.preventDefault(); onRowClick(f); } }
                        : undefined
                    }
                    className={cn(
                      "border-t border-division",
                      onRowClick && "cursor-pointer hover:bg-superficie-2 focus-visible:bg-superficie-2",
                    )}
                  >
                    {columnas.map((c) => {
                      const contenido = c.render ? c.render(f) : f[c.key] ?? "—";
                      return (
                        <td
                          key={c.key}
                          className={cn(
                            "px-lg align-middle",
                            compacta ? "py-2" : "py-3.5",
                            // Por defecto una celda no parte en dos líneas: en una
                            // tabla larga la altura despareja arruina el barrido
                            // visual, que es justo para lo que sirve la densidad.
                            !c.envolver && "whitespace-nowrap",
                            c.className,
                          )}
                        >
                          {c.truncar ? (
                            <span className="block truncate" title={typeof contenido === "string" ? contenido : undefined}>
                              {contenido}
                            </span>
                          ) : (
                            contenido
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Paginador
            pagina={pagina} paginas={paginas} total={total} tamano={tamano}
            desde={desde} hasta={hasta} irA={irA} cambiarTamano={cambiarTamano}
          />
        </>
      )}
    </div>
  );
}

/**
 * `DataTable` conectada a un recurso de la API. Es la forma normal de usarla:
 *
 *     <TablaRecurso clave="casos" recurso="casos" params={{ institucion }} columnas={[…]} />
 */
export function TablaRecurso({
  clave, recurso, params = {}, columnas, ordenInicial = "", onRowClick, vacio, barra,
}) {
  const tabla = useTablaUrl(clave, { ordenInicial });
  const { pagina, orden, tamano } = tabla;

  const q = useLista(recurso, {
    ...params,
    page: pagina,
    pageSize: tamano,
    ordering: orden || undefined,
  });

  // Al cambiar un filtro hay que volver a la página 1: quedarse en la 7 de un
  // resultado que ahora tiene 2 páginas muestra una tabla vacía y parece un bug.
  const filtros = JSON.stringify(params);
  const filtrosPrevios = useRef(filtros);
  useEffect(() => {
    if (filtrosPrevios.current !== filtros) {
      filtrosPrevios.current = filtros;
      if (pagina !== 1) tabla.irA(1);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtros]);

  // Si se borran filas y la página actual queda fuera de rango, volver atrás.
  useEffect(() => {
    if (!q.isLoading && pagina > q.paginas) tabla.irA(q.paginas);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q.paginas, q.isLoading]);

  return (
    <DataTable
      columnas={columnas}
      filas={q.filas}
      total={q.total}
      paginas={q.paginas}
      onRowClick={onRowClick}
      vacio={vacio}
      barra={barra}
      tabla={tabla}
      estado={{
        cargando: q.isLoading,
        refrescando: q.isPlaceholderData,
        error: q.error,
        reintentar: q.refetch,
      }}
    />
  );
}
