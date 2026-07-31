import { cn } from "@/lib/cn";
import { Icon } from "@/components/icons";

/**
 * Bloque gris que ocupa el lugar del contenido mientras carga.
 *
 * Va en lugar del spinner centrado: el spinner borra la pantalla y no dice nada
 * del contenido; el esqueleto conserva la forma, así la vista no salta cuando
 * llegan los datos y se percibe más rápida.
 */
export function Skeleton({ className }) {
  return <div className={cn("animate-pulse rounded-md bg-division", className)} aria-hidden="true" />;
}

// Anchos desparejos pero DETERMINISTAS: una tabla real no tiene todas las celdas
// del mismo largo, y sortearlos haría titilar el esqueleto en cada render.
const ANCHOS = ["w-16", "w-40", "w-32", "w-20", "w-28", "w-24"];

/** Esqueleto con forma de tabla: n filas por m columnas. */
export function SkeletonTabla({ filas = 8, columnas = 6 }) {
  return (
    <div role="status" aria-label="Cargando…">
      {Array.from({ length: filas }).map((_, f) => (
        <div key={f} className="flex items-center gap-lg border-b border-division px-lg py-3.5 last:border-0">
          {Array.from({ length: columnas }).map((_, c) => (
            <Skeleton key={c} className={cn("h-4", ANCHOS[(f + c) % ANCHOS.length])} />
          ))}
        </div>
      ))}
    </div>
  );
}

/** No hay datos que mostrar. Distinto de un error: acá el sistema funcionó. */
export function EstadoVacio({ titulo, detalle, accion, icono = "inbox" }) {
  return (
    <div className="flex flex-col items-center gap-2 px-xxl py-12 text-center">
      <span className="mb-1 flex size-11 items-center justify-center rounded-pill bg-superficie-2 text-texto-tenue">
        <Icon name={icono} size={20} />
      </span>
      <div className="text-lg font-bold text-texto-suave">{titulo}</div>
      {detalle && <div className="max-w-md text-base text-texto-debil">{detalle}</div>}
      {accion && <div className="mt-2">{accion}</div>}
    </div>
  );
}

/**
 * Algo falló. Siempre con reintento: un error sin salida obliga a recargar la
 * página entera y se pierde el contexto (filtros, paso del caso, lo que sea).
 */
export function EstadoError({ error, onReintentar, titulo = "No se pudieron cargar los datos" }) {
  const esPermiso = error?.status === 403 || error?.status === 401;
  return (
    <div className="flex flex-col items-center gap-2 px-xxl py-12 text-center" role="alert">
      <span className="mb-1 flex size-11 items-center justify-center rounded-pill bg-badge-error-bg text-badge-error-fg">
        <Icon name="alert" size={20} />
      </span>
      <div className="text-lg font-bold text-texto-suave">
        {esPermiso ? "No tenés permiso para ver esto" : titulo}
      </div>
      <div className="max-w-md text-base text-texto-debil">
        {esPermiso
          ? "Pedile a un administrador que revise tu rol en esta institución."
          : error?.message || "Puede ser un problema de conexión."}
      </div>
      {!esPermiso && onReintentar && (
        <button
          onClick={onReintentar}
          className="mt-3 inline-flex h-8 items-center gap-1.5 rounded-md border border-accent-100 bg-accent-50 px-3 text-base font-semibold text-accent hover:bg-accent-100"
        >
          <Icon name="refresh" size={14} /> Reintentar
        </button>
      )}
    </div>
  );
}
