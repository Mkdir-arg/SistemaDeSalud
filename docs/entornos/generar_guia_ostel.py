"""Exporta la guía revisable a PDF. Utilidad documental; requiere reportlab."""
import re
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer,
    Table, TableStyle,
)


RAIZ = Path(__file__).resolve().parents[2]
FUENTE = Path(__file__).with_name("guia-evaluacion-ostel.md")
DESTINO = RAIZ / "output" / "pdf" / "guia-evaluacion-ostel.pdf"
TINTA, VERDE = colors.HexColor("#172A38"), colors.HexColor("#16756B")


def estilos():
    fuentes = Path("C:/Windows/Fonts")
    if (fuentes / "arial.ttf").exists():
        for nombre, archivo in (("Guia", "arial.ttf"), ("GuiaBold", "arialbd.ttf"), ("GuiaItalic", "ariali.ttf")):
            pdfmetrics.registerFont(TTFont(nombre, str(fuentes / archivo)))
        pdfmetrics.registerFontFamily("Guia", normal="Guia", bold="GuiaBold", italic="GuiaItalic", boldItalic="GuiaBold")
        fuente, negrita = "Guia", "GuiaBold"
    else:
        fuente, negrita = "Helvetica", "Helvetica-Bold"
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle("TituloGuia", fontName=negrita, fontSize=23, leading=28, textColor=TINTA, spaceAfter=16),
        "h2": ParagraphStyle("SeccionGuia", fontName=negrita, fontSize=13, leading=17, textColor=VERDE, spaceBefore=17, spaceAfter=9, keepWithNext=True),
        "texto": ParagraphStyle("TextoGuia", parent=base["BodyText"], fontName=fuente, fontSize=10, leading=14.5, textColor=TINTA, spaceAfter=8),
        "celda": ParagraphStyle("CeldaGuia", fontName=fuente, fontSize=8, leading=11, textColor=TINTA, alignment=TA_LEFT),
        "cabecera": ParagraphStyle("CabeceraGuia", fontName=negrita, fontSize=8, leading=11, textColor=colors.white),
        "pie": fuente,
    }


def inline(texto):
    texto = escape(texto.replace("—", "-").replace("–", "-"))
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    texto = re.sub(r"`(.+?)`", r"<font color='#16756B'>\1</font>", texto)
    return texto


def generar():
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    s = estilos()
    lineas = FUENTE.read_text(encoding="utf-8").splitlines()
    contenido, parrafo = [], []

    def cerrar():
        if parrafo:
            contenido.append(Paragraph(inline(" ".join(parrafo)), s["texto"]))
            parrafo.clear()

    indice = 0
    while indice < len(lineas):
        linea = lineas[indice].strip()
        if linea.startswith("|"):
            cerrar()
            filas = []
            while indice < len(lineas) and lineas[indice].strip().startswith("|"):
                partes = [p.strip() for p in lineas[indice].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", p) for p in partes):
                    estilo = s["cabecera"] if not filas else s["celda"]
                    filas.append([Paragraph(inline(p), estilo) for p in partes])
                indice += 1
            ancho = (210 - 36) * mm
            columnas = len(filas[0])
            tabla = Table(filas, colWidths=[ancho / columnas] * columnas, repeatRows=1, hAlign="LEFT")
            tabla.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), TINTA),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#EEF5F3"), colors.white]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LINEBELOW", (0, 0), (-1, 0), 1, VERDE),
            ]))
            contenido.extend([tabla, Spacer(1, 9)])
            continue
        if linea.startswith("# "):
            cerrar()
            contenido.extend([Paragraph(inline(linea[2:]), s["titulo"]), HRFlowable(width="100%", thickness=2, color=VERDE), Spacer(1, 12)])
        elif linea.startswith("## "):
            cerrar()
            contenido.append(Paragraph(inline(linea[3:]), s["h2"]))
        elif re.match(r"(?:- |\d+\. )", linea):
            cerrar()
            numero = re.match(r"(\d+)\. ", linea)
            texto = re.sub(r"^(?:- |\d+\. )", "", linea)
            indice += 1
            while indice < len(lineas) and lineas[indice].startswith("   "):
                texto += " " + lineas[indice].strip()
                indice += 1
            item = ListItem(Paragraph(inline(texto), s["texto"]), leftIndent=12)
            contenido.append(ListFlowable([item], bulletType="1" if numero else "bullet", start=int(numero[1]) if numero else None, leftIndent=15, bulletFontSize=8))
            continue
        elif not linea:
            cerrar()
        else:
            parrafo.append(linea)
        indice += 1
    cerrar()

    def pie(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(VERDE)
        canvas.line(18 * mm, 17 * mm, 192 * mm, 17 * mm)
        canvas.setFont(s["pie"], 8)
        canvas.setFillColor(TINTA)
        canvas.drawString(18 * mm, 12 * mm, "PLEXO | Guía de uso y evaluación para OSTEL | Datos ficticios")
        canvas.drawRightString(192 * mm, 12 * mm, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(str(DESTINO), pagesize=(210 * mm, 297 * mm),
        rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=24 * mm,
        title="PLEXO - Guía de uso y evaluación para OSTEL", author="PLEXO")
    doc.build(contenido, onFirstPage=pie, onLaterPages=pie)
    print(DESTINO)


if __name__ == "__main__":
    generar()
