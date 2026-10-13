// Menú lateral del financiador. Lo comparten el portal y las pantallas hijas
// (ficha del afiliado) para que el sidebar no cambie al entrar a un detalle.
export const ROLES = { admin: "Administración", operador: "Operación", auditor: "Sólo lectura" };
export const SECCIONES = [
  { key: "inicio", label: "Inicio", icon: "home" },
  { key: "planes", label: "Planes", icon: "layers" },
  { key: "reglas", label: "Reglas de cobertura", icon: "clipboard" },
  { key: "aranceles", label: "Aranceles", icon: "list" },
  { key: "padron", label: "Padrón de afiliados", icon: "idCard" },
  { key: "consumos", label: "Consumos externos", icon: "fileText" },
  { key: "autorizaciones", label: "Autorizaciones", icon: "clipboard" },
  { key: "facturas", label: "Facturas", icon: "wallet" },
  { key: "actividad", label: "Actividad en hospitales", icon: "activity" },
  { key: "convenios", label: "Convenios", icon: "building" },
  { key: "usuarios", label: "Usuarios", icon: "users" },
  { key: "catalogo", label: "Catálogo común", icon: "cube" },
];

export function itemsFinanciador({ organizacion, plataforma, admin, sufijo }) {
  return SECCIONES.filter((item) => (organizacion || item.key === "catalogo" && plataforma) && (item.key !== "usuarios" || admin) && (item.key !== "catalogo" || plataforma))
    .map((item) => ({ ...item, to: `/financiadores/${item.key}${sufijo}` }));
}
