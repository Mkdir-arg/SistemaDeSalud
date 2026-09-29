import { jsPDF } from "jspdf";
import { autoTable } from "jspdf-autotable";

import { CLINICA, fechaConAnio } from "./datos";

// Se importa solo al descargar. El PDF se arma en el navegador y dice en el pie
// que es de demostración: tiene forma de informe clínico y no debe circular como uno.
const tinta = "#1D1930", tenue = "#5E5680", acento = "#7031C7", alerta = "#9F0712";

export function descargarInforme(resultado, paciente) {
  const doc = new jsPDF({ unit: "mm", format: "a4", compress: true });
  const ancho = doc.internal.pageSize.getWidth();
  doc.setProperties({ title: `${resultado.titulo} - ${CLINICA.nombre}`, subject: "Informe de demostración con datos ficticios", creator: "HEN" });

  doc.setFillColor(acento);
  doc.rect(0, 0, ancho, 4, "F");
  doc.setFont("helvetica", "bold").setFontSize(16).setTextColor(tinta).text(CLINICA.nombre, 18, 20);
  doc.setFont("helvetica", "normal").setFontSize(9).setTextColor(tenue).text(`${CLINICA.direccion} · ${CLINICA.telefonos[0].texto}`, 18, 26);
  doc.text(resultado.area, ancho - 18, 20, { align: "right" });

  doc.setFont("helvetica", "bold").setFontSize(13).setTextColor(tinta).text(resultado.titulo, 18, 42);
  autoTable(doc, {
    startY: 47, theme: "plain", styles: { fontSize: 9, textColor: tinta, cellPadding: { top: 1, bottom: 1, left: 0, right: 4 } },
    columnStyles: { 0: { textColor: tenue, cellWidth: 38 } },
    body: [
      ["Paciente", paciente.nombre], ["DNI", Number(paciente.dni).toLocaleString("es-AR")],
      ["Fecha del estudio", fechaConAnio(resultado.dia)], ["Solicitado por", resultado.pedidoPor],
    ],
  });

  let y = doc.lastAutoTable.finalY + 8;
  if (resultado.valores) {
    autoTable(doc, {
      startY: y, head: [["Determinación", "Resultado", "Valores de referencia"]],
      body: resultado.valores.map((v) => [v.nombre, { content: v.fuera ? `${v.valor}  (fuera de rango)` : v.valor, styles: { textColor: v.fuera ? alerta : tinta, fontStyle: v.fuera ? "bold" : "normal" } }, v.referencia]),
      headStyles: { fillColor: "#F7F2FD", textColor: acento, fontStyle: "bold" }, styles: { fontSize: 9, textColor: tinta }, alternateRowStyles: { fillColor: "#FBFAFE" },
      margin: { left: 18, right: 18 },
    });
    y = doc.lastAutoTable.finalY + 8;
  }
  if (resultado.informe) {
    doc.setFont("helvetica", "bold").setFontSize(10).setTextColor(tinta).text("Informe", 18, y);
    doc.setFont("helvetica", "normal").setFontSize(10).text(doc.splitTextToSize(resultado.informe, ancho - 36), 18, y + 6);
  }

  const alto = doc.internal.pageSize.getHeight();
  doc.setDrawColor("#E3DDF2").line(18, alto - 20, ancho - 18, alto - 20);
  doc.setFont("helvetica", "normal").setFontSize(8).setTextColor(tenue)
    .text("Documento de demostración generado por HEN con datos ficticios. Sin validez clínica.", 18, alto - 14);
  doc.save(`${resultado.id}-${resultado.dia}.pdf`);
}
