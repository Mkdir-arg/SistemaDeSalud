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

export function accesoFinanciador(usuario, organizacion) {
  // /usuarios/me representa la identidad efectiva; nunca sumar el actor real de «Ver como».
  const plataforma = Boolean(usuario?.is_superuser || Object.values(usuario?.capacidades_por_institucion || {}).some((caps) => caps.includes("gobierno_plataforma")));
  const admin = Boolean(usuario?.is_superuser || organizacion?.rol === "admin");
  return { plataforma, admin, operador: admin || organizacion?.rol === "operador" };
}

export function itemsFinanciador({ organizacion, plataforma, sufijo }) {
  // El servidor devuelve el rol real, o admin para el superusuario efectivo.
  const miembro = Object.hasOwn(ROLES, organizacion?.rol);
  return SECCIONES.filter((item) => item.key === "catalogo" ? plataforma :
    item.key === "usuarios" ? organizacion?.rol === "admin" || plataforma && organizacion?.puede_designar_admin_inicial === true : miembro)
    .map((item) => ({ ...item, to: `/financiadores/${item.key}${item.key === "catalogo" ? "" : sufijo}` }));
}
