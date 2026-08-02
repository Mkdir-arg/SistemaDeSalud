// Iconos de línea (estilo del sistema de diseño: SVG stroke, no glifos).
// Trazo currentColor para heredar el color del contexto.
const PATHS = {
  inbox: "M22 12h-6l-2 3h-4l-2-3H2 M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z",
  list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  workflow: "M3 4h6v6H3zM15 14h6v6h-6zM9 7h4a2 2 0 0 1 2 2v8",
  building: "M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18ZM10 6h.01M14 6h.01M10 10h.01M14 10h.01M10 14h.01M14 14h.01M10 18h4",
  layers: "M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83ZM2 12.65l9.17 4.16a2 2 0 0 0 1.66 0L22 12.65M2 17.65l9.17 4.16a2 2 0 0 0 1.66 0L22 17.65",
  users: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75",
  activity: "M22 12h-4l-3 9L9 3l-3 9H2",
  power: "M12 2v10M18.36 6.64a9 9 0 1 1-12.73 0",
  x: "M18 6 6 18M6 6l12 12",
  plus: "M5 12h14M12 5v14",
  refresh: "M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8M21 3v5h-5M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16M3 21v-5h5",
  back: "M19 12H5M12 19l-7-7 7-7",
  home: "M3 9.5 12 3l9 6.5M5 9v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9",
  fileText: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M9 13h6M9 17h5",
  clipboard: "M9 2h6a1 1 0 0 1 1 1v1h1a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h1V3a1 1 0 0 1 1-1zM12 10v6M9 13h6",
  idCard: "M3 5h18a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zM14 9h4M14 13h4M6.5 16c.5-1.4 1.6-2 3-2s2.5.6 3 2",
  map: "M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14",
  form: "M5 3h14a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1zM8 8h8M8 12h8M8 16h4",
  cube: "M12 2 21 7v10l-9 5-9-5V7zM12 12 21 7M12 12v10M12 12 3 7",
  enter: "M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3",
  search: "M11 17a6 6 0 1 0 0-12 6 6 0 0 0 0 12zM21 21l-4.35-4.35",
  edit: "M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z",
  copy: "M9 9h10a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V10a1 1 0 0 1 1-1zM5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1",
  trash: "M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6",
  help: "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM9.1 9a3 3 0 0 1 5.8 1c0 2-3 2-3 4M12 17h.01",
  bell: "M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.94 1.94 0 0 0 3.4 0",
  play: "M6 4.5v15l13-7.5z",
  flask: "M9 3h6M10 3v6.5L5 18a1.5 1.5 0 0 0 1.3 2.3h11.4A1.5 1.5 0 0 0 19 18l-5-8.5V3M8 14h8",
  minus: "M5 12h14",
  download: "M12 3v12M7 11l5 5 5-5M4 19h16",
  maximize: "M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M21 16v3a2 2 0 0 1-2 2h-3M3 16v3a2 2 0 0 0 2 2h3",
  undo: "M9 14 4 9l5-5M4 9h11a5 5 0 0 1 0 10h-1",
  redo: "M15 14l5-5-5-5M20 9H9a5 5 0 0 0 0 10h1",
  alert: "M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0zM12 9v4M12 17h.01",
  chevronLeft: "M15 18l-6-6 6-6",
  chevronRight: "M9 18l6-6-6-6",
  chevronsLeft: "M11 17l-5-5 5-5M18 17l-5-5 5-5",
  chevronsRight: "M13 17l5-5-5-5M6 17l5-5-5-5",
  // Indicadores de orden de columna.
  arrowUp: "M12 19V5M5 12l7-7 7 7",
  arrowDown: "M12 5v14M19 12l-7 7-7-7",
  // Doble flecha tenue: la columna es ordenable pero no es la activa.
  ordenable: "M8 9l4-4 4 4M8 15l4 4 4-4",
  filter: "M3 5h18l-7 8v6l-4 2v-8z",
  luna: "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z",
  sol: "M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  // Densidad de tabla (cómoda / compacta).
  rows: "M3 5h18M3 12h18M3 19h18",
};

// Para `users` hace falta un círculo que no entra en el path simple.
const EXTRA = {
  users: <circle cx="9" cy="7" r="4" />,
  sol: <circle cx="12" cy="12" r="4" />,
};

// `style` sigue existiendo para los llamadores con estilos inline (los que quedan
// por migrar); `className` es la vía para los componentes nuevos.
export function Icon({ name, size = 18, strokeWidth = 1.8, style, className }) {
  const d = PATHS[name];
  if (!d) return null;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={{ flex: "none", ...style }}
      aria-hidden="true"
    >
      <path d={d} />
      {EXTRA[name]}
    </svg>
  );
}
