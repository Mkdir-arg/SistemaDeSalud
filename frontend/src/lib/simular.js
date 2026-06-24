// Simulación de un caso recorriendo un flujo — espeja la lógica del motor del
// backend (apps/casos/motor.py) pero del lado del cliente, SIN tocar la base.
// Se usa en el diseñador (modo "Probar") y para "Reproducir" el recorrido.

export const TIPOS_AUTO = new Set(["inicio", "decision", "accion", "derivar", "estado"]);
export const TIPOS_STOP = new Set(["form", "atencion", "espera", "tiempo", "fin"]);

// Evalúa una condición de rama (decisión) contra los valores cargados.
export function cumple(cond, valores) {
  if (!cond || !cond.campo) return true; // rama por defecto
  const actual = valores[cond.campo];
  if (actual == null || actual === "") return false;
  const esperado = cond.valor;
  switch (cond.operador) {
    case "=":
      return String(actual) === String(esperado);
    case "!=":
      return String(actual) !== String(esperado);
    case "contiene":
      return String(actual).toLowerCase().includes(String(esperado).toLowerCase());
    case ">":
    case "<": {
      const a = parseFloat(actual), e = parseFloat(esperado);
      if (isNaN(a) || isNaN(e)) return false;
      return cond.operador === ">" ? a > e : a < e;
    }
    default:
      return false;
  }
}

// Próximo nodo a partir de `nodoId` (resuelve la rama de una Decisión).
export function siguiente(nodos, conexiones, nodoId, valores) {
  const nodo = nodos.find((n) => n.id === nodoId);
  const salidas = conexiones.filter((c) => c.origen === nodoId);
  if (!salidas.length) return null;
  if (nodo?.tipo === "decision") {
    const conCond = salidas.filter((c) => c.condicion && c.condicion.campo);
    for (const c of conCond) if (cumple(c.condicion, valores)) return c.destino;
    const def = salidas.find((c) => !(c.condicion && c.condicion.campo));
    return def ? def.destino : conCond[0] ? conCond[0].destino : null;
  }
  return salidas[0].destino;
}

export function nodoInicio(nodos) {
  return nodos.find((n) => n.tipo === "inicio") || nodos[0];
}

// Desde `nodoId`, atraviesa los nodos automáticos hasta la próxima parada.
// Devuelve { parada, camino } (camino = ids visitados en esta corrida).
export function correrAuto(nodos, conexiones, nodoId, valores) {
  const camino = [];
  const visto = new Set();
  let actual = nodoId;
  while (actual != null) {
    camino.push(actual);
    const nodo = nodos.find((n) => n.id === actual);
    if (!nodo || TIPOS_STOP.has(nodo.tipo)) break;
    if (visto.has(actual)) break; // corta ciclos
    visto.add(actual);
    actual = siguiente(nodos, conexiones, actual, valores);
  }
  return { parada: camino[camino.length - 1] ?? null, camino };
}

// Camino "por defecto" completo (para Reproducir sin simular): arranca en Inicio
// y siempre toma la primera rama / la rama por defecto, hasta un Fin o callejón.
export function caminoPorDefecto(nodos, conexiones) {
  const inicio = nodoInicio(nodos);
  if (!inicio) return [];
  const camino = [];
  const visto = new Set();
  let actual = inicio.id;
  while (actual != null && !visto.has(actual)) {
    camino.push(actual);
    visto.add(actual);
    const nodo = nodos.find((n) => n.id === actual);
    if (nodo?.tipo === "fin") break;
    actual = siguiente(nodos, conexiones, actual, {});
  }
  return camino;
}
