import { decimalACentavos } from "@/api/finanzas";
import { DataTable, useTablaUrl } from "@/components/ui/tabla";
import { FiltroColumna, FiltrosActivos, useFiltrosFinanzas } from "./ControlesFinanzas";

const texto = (valor) => String(valor ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es");
const numero = (valor) => {
  const centavos = decimalACentavos(valor);
  return centavos === "importe_invalido" ? null : BigInt(centavos);
};

// Sólo para agregaciones completas ya devueltas por el servidor. Nunca ordenar
// aquí una página de una lista remota: sus filtros y orden pertenecen a la API.
export default function TablaAgregadaFinanzas({ clave, titulo, filas, columnas, vacio }) {
  const tabla = useTablaUrl(clave);
  const tamano = [25, 50, 100].includes(tabla.tamano) ? tabla.tamano : 25;
  const definiciones = columnas.map((col) => col.numerica
    ? ["min", "max"].map((limite) => ({ key: `${col.key}_${limite}`, label: `${col.label} ${limite === "min" ? "desde" : "hasta"}`, type: "number", step: "0.01" }))
    : [{ key: col.key, label: col.label }]);
  const filtros = useFiltrosFinanzas(clave, definiciones.flat().map((c) => c.key));
  const valor = (fila, col) => col.valor ? col.valor(fila) : fila[col.key];
  const invalidos = definiciones.flat().some((c) => c.type === "number" && filtros.valores[c.key] && numero(filtros.valores[c.key]) == null);
  const visibles = invalidos ? [] : filas.filter((fila) => columnas.every((col) => {
    const dato = valor(fila, col);
    if (!col.numerica) return texto(dato).includes(texto(filtros.valores[col.key]));
    return ["min", "max"].every((limite) => {
      const filtro = filtros.valores[`${col.key}_${limite}`];
      if (!filtro) return true;
      const n = numero(dato);
      return n != null && (limite === "min" ? n >= numero(filtro) : n <= numero(filtro));
    });
  }));
  const columna = columnas.find((c) => c.key === tabla.orden.replace(/^-/, ""));
  if (columna) visibles.sort((a, b) => {
    const va = valor(a, columna), vb = valor(b, columna);
    // Desconocido no es cero; queda al final en ambos sentidos.
    if (va == null || vb == null) return va == null ? (vb == null ? 0 : 1) : -1;
    const orden = columna.numerica
      ? (numero(va) > numero(vb) ? 1 : numero(va) < numero(vb) ? -1 : 0)
      : texto(va).localeCompare(texto(vb), "es", { numeric: true });
    return tabla.orden.startsWith("-") ? -orden : orden;
  });
  const paginas = Math.max(1, Math.ceil(visibles.length / tamano));
  const pagina = Math.max(1, Math.min(Number.isInteger(tabla.pagina) ? tabla.pagina : 1, paginas));
  return <DataTable adaptable mantenerEncabezados titulo={titulo}
    filas={visibles.slice((pagina - 1) * tamano, pagina * tamano)} total={visibles.length} paginas={paginas}
    tabla={{ ...tabla, pagina, tamano }} estado={{}} vacio={vacio}
    barra={<>{invalidos && <span role="alert">Ingresá importes con hasta dos decimales.</span>}<FiltrosActivos filtros={filtros} definiciones={definiciones.flat()} /></>}
    columnas={columnas.map((col, i) => ({ ...col, orden: col.key, filtro: <FiltroColumna label={col.label} controles={definiciones[i]} filtros={filtros} /> }))} />;
}
