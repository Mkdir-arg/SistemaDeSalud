import { jsPDF } from "jspdf";
import { autoTable } from "jspdf-autotable";
import { importeARS } from "@/api/finanzas";
import { fechaHora } from "@/lib/format";

// Se importa sólo al descargar. No se envían datos a un servicio de conversión.
const tinta = "#243444", tenue = "#536574", petroleo = "#287f92";
const colorSigno = (n) => Number(n) > 0 ? "#187344" : Number(n) < 0 ? "#b42332" : tenue;
const porcentaje = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2, signDisplay: "exceptZero" });
const disponible = (fila) => (fila.cantidad_registros ?? fila.cantidad_movimientos) > 0;
// Las fuentes estándar de PDF cubren español y símbolos monetarios latinos.
const texto = (valor) => String(valor ?? "").replace(/[\u2010-\u2015]/g, "-").replace(/\u2026/g, "...").replace(/[\u0000-\u0008\u000b-\u001f]/g, "");

function variacion(dato) {
  const importe = dato?.importe == null ? "Sin base comparable" : `${Number(dato.importe) > 0 ? "+" : ""}${importeARS(dato.importe)}`;
  const tasa = dato?.porcentaje == null ? "Sin base porcentual" : `${porcentaje.format(Number(dato.porcentaje))}%`;
  return [{ content: importe, styles: { textColor: colorSigno(dato?.importe), halign: "right" } },
    { content: tasa, styles: { textColor: colorSigno(dato?.porcentaje), halign: "right" } }];
}

async function imagenGrafico(svg) {
  if (!svg) return null;
  const ancho = Number(svg.getAttribute("width")), alto = Number(svg.getAttribute("height"));
  if (!(ancho > 0 && alto > 0)) return null;
  // Copia del SVG de Recharts: mismos puntos, barras y escala. Fondo de papel
  // y texto oscuro, independientemente del tema de pantalla.
  svg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  svg.querySelectorAll("text").forEach((el) => {
    el.setAttribute("fill", tenue);
    el.style.fill = tenue;
    el.style.fontFamily = "Arial, sans-serif";
  });
  const contenido = new XMLSerializer().serializeToString(svg)
    .replace(/var\(--color-superficie\)/g, "#ffffff")
    .replace(/var\(--color-division\)/g, "#dce3e8")
    .replace(/var\(--color-texto-debil\)/g, tenue);
  const url = URL.createObjectURL(new Blob([contenido], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const img = new Image();
    await new Promise((resolve, reject) => { img.onload = resolve; img.onerror = reject; img.src = url; });
    const canvas = document.createElement("canvas");
    canvas.width = ancho * 3;
    canvas.height = alto * 3;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "white";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    return { datos: canvas.toDataURL("image/png"), ancho, alto };
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function descargarReportePdf(informe) {
  const doc = new jsPDF({ unit: "mm", format: "a4", compress: true });
  doc.setProperties({ title: `Finanzas - ${informe.institucion} - ${informe.mes}`, subject: "Reporte ejecutivo de fuentes financieras registradas", creator: "Sistema de Salud" });
  const margen = 16, ancho = 178, limite = 275;
  let y = 32;
  const nuevaPagina = () => { doc.addPage(); y = 32; };
  const espacio = (alto) => { if (y + alto > limite) nuevaPagina(); };
  function parrafo(contenido, { tamano = 9, color = tenue, negrita = false } = {}) {
    doc.setFont("helvetica", negrita ? "bold" : "normal");
    doc.setFontSize(tamano);
    doc.setTextColor(color);
    const lineas = doc.splitTextToSize(texto(contenido), ancho);
    const paso = tamano * 0.46;
    for (const linea of lineas) {
      espacio(paso);
      doc.text(linea, margen, y);
      y += paso;
    }
    y += 3;
  }
  function titulo(contenido) {
    espacio(24);
    parrafo(contenido, { tamano: 14, color: tinta, negrita: true });
  }
  function tabla(encabezados, filas, numericas = []) {
    // Dos columnas permiten colorear cada signo por separado: un porcentaje
    // redondeado a cero o sin base permanece neutro aunque cambie el importe.
    const esVariacion = (celda) => typeof celda === "object" && celda !== null && "variacion" in celda;
    const variaciones = new Set(filas.flatMap((fila) => fila.flatMap((celda, i) => esVariacion(celda) ? [i] : [])));
    const cabeceras = encabezados.flatMap((e, i) => variaciones.has(i) ? ["Variación ARS", "Variación % nominal"] : [texto(e)]);
    autoTable(doc, {
      startY: y, head: [cabeceras], body: filas.length ? filas.map((fila) => fila.flatMap((celda, i) => esVariacion(celda) ? variacion(celda.variacion) : [{ content: texto(celda), styles: { halign: numericas.includes(i) ? "right" : "left" } }])) : [[{ content: "Sin registros para esta selección", colSpan: cabeceras.length }]],
      margin: { top: 32, bottom: 22, left: margen, right: margen },
      styles: { font: "helvetica", fontSize: 8.5, textColor: tinta, cellPadding: 2.5, lineColor: "#e2e8ed", lineWidth: 0.1, overflow: "linebreak" },
      headStyles: { fillColor: petroleo, textColor: "#ffffff", fontStyle: "bold" },
      alternateRowStyles: { fillColor: "#f3f6f8" },
      columnStyles: cabeceras.length === 5 && variaciones.size === 1 ? { 0: { cellWidth: 50 }, 1: { cellWidth: 32 }, 2: { cellWidth: 32 }, 3: { cellWidth: 32 }, 4: { cellWidth: 32 } } : {},
      rowPageBreak: "avoid", showHead: "everyPage",
    });
    y = doc.lastAutoTable.finalY + 8;
  }
  function detalle(clave, extra = "") {
    const t = informe.tablas[clave];
    if (!t) throw new Error(`Tabla no disponible: ${clave}`);
    espacio(60);
    titulo(t.titulo);
    parrafo(t.contexto);
    parrafo(`Filtros de esta tabla: ${[extra, ...t.filtros].filter(Boolean).join(" · ") || "ninguno"}. Orden: ${t.orden}. Filas: ${t.filas.length}.`, { tamano: 8 });
    tabla(t.columnas.map((c) => c.titulo), t.filas, t.columnas.flatMap((c, i) => c.numerica ? [i] : []));
  }
  async function grafico(clave, nombre, leyenda, hayDatos) {
    if (!hayDatos) {
      titulo(nombre);
      parrafo("Sin registros para dibujar el gráfico. No equivale a un importe cero.");
      return;
    }
    const img = await imagenGrafico(informe.graficos[clave]);
    if (!img) throw new Error(`Gráfico no disponible: ${clave}`);
    const escala = Math.min(ancho / img.ancho, (clave.startsWith("tendencia") ? 75 : 155) / img.alto);
    const alto = img.alto * escala, anchura = img.ancho * escala;
    espacio(alto + 26);
    titulo(nombre);
    doc.addImage(img.datos, "PNG", margen + (ancho - anchura) / 2, y, anchura, alto);
    y += alto + 4;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    let x = margen;
    for (const [nombreSerie, color] of leyenda) {
      doc.setDrawColor(color);
      doc.setLineWidth(0.8);
      doc.line(x, y - 1, x + 7, y - 1);
      doc.setTextColor(tenue);
      doc.text(texto(nombreSerie), x + 9, y);
      x += doc.getTextWidth(texto(nombreSerie)) + 18;
    }
    y += 10;
  }
  function resumen(reporte, medidas) {
    tabla(["Indicador", reporte.anterior.periodo_economico.slice(0, 7), reporte.actual.periodo_economico.slice(0, 7), "Variación nominal"], medidas.map(([campo, nombre]) => [nombre,
      disponible(reporte.anterior) ? importeARS(reporte.anterior[campo]) : "Sin registros",
      disponible(reporte.actual) ? importeARS(reporte.actual[campo]) : "Sin registros",
      { variacion: reporte.variaciones[campo] },
    ]), [1, 2, 3]);
    parrafo(`Fuente consultada: ${fechaHora(reporte.calculado_en)}. ${reporte.alcance}`, { tamano: 8 });
  }

  parrafo("Reporte financiero", { tamano: 23, color: tinta, negrita: true });
  parrafo(informe.institucion, { tamano: 13, color: tinta });
  const referencia = informe.gastos || informe.dinero;
  parrafo(`Seleccionado: ${informe.mes} · Comparado: ${referencia.anterior.periodo_economico.slice(0, 7)} · Trayectoria: ${informe.meses} meses`, { negrita: true });
  parrafo(`Área: ${informe.area}. Moneda: ARS, sin ajuste por inflación.`);
  parrafo("Consulta de registros vigentes, incluidos los meses anteriores; no es una versión histórica congelada ni un cierre contable. El PDF conserva los datos consultados en las fechas indicadas para cada fuente.");
  parrafo("Los filtros de cada tabla se identifican junto a ella y no alteran los gráficos ni los totales. Las tablas incluyen todas las filas filtradas, sin el límite de página de la pantalla.");
  parrafo("Verde indica aumento y rojo disminución; no implican mejora o deterioro. Sin base comparable y sin registros no equivalen a cero. Gastos y dinero son magnitudes diferentes y no se suman.");
  parrafo("El alcance se limita a las fuentes autorizadas; no representa el costo total del hospital.", { tamano: 8 });

  if (informe.gastos) {
    const g = informe.gastos;
    titulo("Gastos · mes económico");
    resumen(g, [["aprobados", "Gastos aprobados"], ["pendientes_aprobacion", "Gastos por aprobar"]]);
    for (const fila of [g.actual, g.anterior]) {
      parrafo(`${fila.periodo_economico.slice(0, 7)}: ${fila.mes_abierto ? "mes abierto" : "mes finalizado"}. ${!fila.controles ? "Sin controles configurados" : `${fila.controles_sin_completar} controles de carga pendientes de ${fila.controles}`}.`, { tamano: 8 });
    }
    parrafo(`Ajustes por aprobar: ${g.actual.ajustes_pendientes}. ${g.actual.actualizando ? "Distribución en actualización." : ""} El aprobado ya incluye lo distribuido.`, { tamano: 8 });
  } else {
    titulo("Gastos");
    parrafo("No incluidos en tu acceso. No se representan como cero.");
  }
  if (informe.dinero) {
    const d = informe.dinero;
    titulo("Pagos y cobros · fecha efectiva");
    resumen(d, [["cobros_netos", "Cobros netos"], ["pagos_netos", "Pagos netos"], ["diferencia", "Diferencia del período"]]);
    parrafo(`Seleccionado: ${d.actual.fecha_desde} al ${d.actual.fecha_hasta}. Comparado: ${d.anterior.fecha_desde} al ${d.anterior.fecha_hasta}. ${d.actual.mes_abierto ? "Mes seleccionado abierto." : ""}`, { tamano: 8 });
    parrafo(`${d.actual.por_aprobar.cantidad} movimientos por aprobar, excluidos de los netos. La diferencia es cobros menos pagos; no es saldo disponible ni rentabilidad.`, { tamano: 8 });
  } else {
    titulo("Pagos y cobros");
    parrafo("No incluidos en tu acceso. No se representan como cero.");
  }
  if (informe.gastos) {
    nuevaPagina();
    await grafico("tendencia_gastos", "Gastos · evolución mensual en ARS", [["Gastos aprobados", petroleo]], informe.gastos.serie.some(disponible));
    parrafo("Puntos huecos: lectura provisional. Huecos en la serie: sin registros.", { tamano: 8 });
    detalle("reporte_serie_gastos");
    nuevaPagina();
    await grafico("grupos_gastos", "Gastos por área y concepto · ARS", [[referencia.anterior.periodo_economico.slice(0, 7), "#82949e"], [informe.mes, petroleo]], informe.gastos.agrupaciones.length > 0);
    parrafo("Gráfico: hasta ocho grupos con mayor aprobado actual. La tabla conserva su propia selección y orden.", { tamano: 8 });
    detalle("reporte_grupos_gastos");
  }
  if (informe.dinero) {
    nuevaPagina();
    await grafico("tendencia_dinero", "Pagos y cobros · evolución mensual en ARS", [["Cobros netos", petroleo], ["Pagos netos", "#ad7133"]], informe.dinero.serie.some(disponible));
    parrafo("Puntos huecos: mes abierto. Huecos en la serie: sin movimientos aprobados.", { tamano: 8 });
    detalle("reporte_serie_dinero");
    detalle(`reporte_grupos_${informe.tipo}`, `Tipo: ${informe.tipo === "cobrar" ? "Cobros por financiador" : "Pagos por concepto"}${informe.busqueda ? ` · Búsqueda: ${informe.busqueda}` : ""}`);
  }
  const paginas = doc.getNumberOfPages();
  for (let i = 1; i <= paginas; i++) {
    doc.setPage(i);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(9);
    doc.setTextColor(petroleo);
    doc.text("FINANZAS / REPORTE EJECUTIVO", margen, 16);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(tenue);
    doc.text(informe.mes, 194, 16, { align: "right" });
    doc.setDrawColor("#dce3e8");
    doc.setLineWidth(0.25);
    doc.line(margen, 21, 194, 21);
    doc.line(margen, 280, 194, 280);
    doc.setFontSize(8);
    doc.text("Fuentes registradas dentro del alcance autorizado · ARS", margen, 286);
    doc.text(`${i} / ${paginas}`, 194, 286, { align: "right" });
  }
  await doc.save(`reporte-finanzas-${informe.mes}.pdf`, { returnPromise: true });
}
