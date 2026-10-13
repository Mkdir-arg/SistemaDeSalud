// El contexto del listado viaja en la URL; las páginas internas de la ficha
// pertenecen exclusivamente al afiliado abierto.
const PAGINAS_FICHA = ["page", "autorizaciones_page", "historial_page"];

export function parametrosFicha(parametros, financiador, paginaPadron) {
  const query = new URLSearchParams(parametros);
  PAGINAS_FICHA.forEach((campo) => query.delete(campo));
  query.set("financiador", String(financiador));
  if (paginaPadron > 1) query.set("padron_page", String(paginaPadron));
  else query.delete("padron_page");
  return query;
}

export function parametrosFamiliar(parametros) {
  const query = new URLSearchParams(parametros);
  PAGINAS_FICHA.forEach((campo) => query.delete(campo));
  return query;
}

export function parametrosListado(parametros, financiador) {
  const query = parametrosFamiliar(parametros);
  const pagina = query.get("padron_page");
  query.delete("padron_page");
  query.set("financiador", String(financiador));
  if (pagina) query.set("page", pagina);
  return query;
}
