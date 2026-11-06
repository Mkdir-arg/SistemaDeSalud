// Fixture exclusivo #184. Sin backend ni persistencia; descarga API interceptada.
import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, useSearchParams } from "react-router-dom";
import PadronTabla from "../../src/components/financiadores/PadronTabla";
import ExportarPadron from "../../src/components/financiadores/ExportarPadron";
import { parametrosConsultaPadron } from "../../src/components/financiadores/padronTablaEstado";
import "../../src/index.css";

const filas = [
  { id: 1, nombre: "", numero: "00001", estado_administrativo: "constructor" },
  { id: 2, nombre: "Registro Ficticio", numero: "00002", numero_interno: "000184", titular: 3, titular_nombre: "Finalizada Ficticia", cobertura_habilitada: false, vigente: true, estado_administrativo: "en_tramite" },
  { id: 3, nombre: "Finalizada Ficticia", numero: "00003", cobertura_habilitada: false, finalizado_en: "2026-10-01", estado_administrativo: "baja_administrativa" },
];

function Prueba() {
  const [parametros, setParametros] = useSearchParams();
  return <main className="p-4"><PadronTabla filas={filas} total={3} paginas={1}
    estado={{ cargando: false, refrescando: false, error: null }}
    parametros={parametros} onParametrosChange={setParametros}
    barra={<ExportarPadron organizacion={{ id: 21 }} query={parametrosConsultaPadron(parametros)} total={3} consultando={false} />}
    fichaHref={(fila) => { const siguientes = new URLSearchParams(parametros); siguientes.set("ficha", fila.id); return `?${siguientes}`; }} />
  </main>;
}
createRoot(document.getElementById("root")).render(<BrowserRouter><Prueba /></BrowserRouter>);
