/**
 * Cómo se lee el registro de accesos (Ley 26.529, art. 14 y 15).
 *
 * Vive en un módulo y no en cada pantalla porque las dos que muestran estos
 * datos —el registro de la jefatura y la pestaña «Quién la miró» de la historia—
 * tienen que decir lo mismo del mismo evento. Cuando cada una tenía su criterio,
 * la exportación del padrón salía en ámbar en una y en gris en la otra, y la que
 * la bajaba de tono era justo la que se lee frente a quien reclama.
 */

/**
 * El nombre del modelo, dicho como se le dice a un paciente.
 *
 * Del lado del registro se guarda el nombre del MODELO a propósito —una ruta se
 * puede renombrar y el registro tiene que seguir diciendo lo mismo dentro de
 * diez años—, pero eso es cómo se guarda, no cómo se muestra. Esta lista se lee
 * en voz alta frente a quien la pidió, y quien responde ante la Ley 25.326 es un
 * director o un jefe de área: «historiaclinica» en monoespaciado no es una
 * respuesta.
 */
export const RECURSO = {
  ciudadano: "datos del paciente",
  historiaclinica: "historia clínica",
  entradahistoria: "evolución",
  estudio: "estudios",
  receta: "recetas",
  consentimientodatos: "consentimiento",
};

/** Siempre devuelve algo: un recurso nuevo del backend no puede dejar la celda vacía. */
export const nombreRecurso = (recurso) => RECURSO[recurso] || recurso || "—";

/**
 * Tono de cada tipo de acceso.
 *
 * «Alguien se llevó tus datos en un archivo» y «alguien abrió el listado» no son
 * el mismo hecho y no pueden tener el mismo peso visual: quien barre la lista
 * buscando lo grave necesita dónde apoyar la vista.
 */
export const TONO_ACCESO = { detalle: "info", listado: "gray", exportacion: "amber" };

/**
 * El filtro de un listado, en castellano.
 *
 * La diferencia entre «buscó a una persona» y «se llevó el padrón del área» es
 * la diferencia entre un acceso normal y una fuga, y estaba escrita en el idioma
 * de la base («institucion=1 search=Quiroga»). En la práctica esa columna se
 * saltea, y saltearla es perder el único dato que las separa.
 *
 * `institucionActual` se omite del texto: repetir la institución en la que uno
 * está parado es ruido en todas las filas.
 */
export function filtrosLegibles(detalle, institucionActual) {
  const partes = [];
  for (const par of String(detalle || "").split(" ").filter(Boolean)) {
    const i = par.indexOf("=");
    if (i < 0) continue;
    const clave = par.slice(0, i);
    const valor = par.slice(i + 1);
    if (clave === "institucion") {
      if (String(valor) !== String(institucionActual ?? "")) partes.push(`de la institución ${valor}`);
      continue;
    }
    if (clave === "search") partes.push(`buscó “${valor}”`);
    else if (clave === "ciudadano" || clave === "historia__ciudadano") partes.push("de un paciente");
    else if (clave === "historia") partes.push("de una historia");
    else partes.push(`${clave}: ${valor}`);
  }
  // Sin filtros no es «nada»: es el listado entero de lo que esa persona alcanza,
  // que es el acceso más amplio que puede quedar registrado como listado.
  return partes.length ? partes.join(" · ") : "sin filtrar";
}
