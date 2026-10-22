// Fixture exclusivo #184. Sin API, persistencia ni personas reales.
import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, useSearchParams } from "react-router-dom";
import PadronTabla from "../../src/components/financiadores/PadronTabla";
import "../../src/index.css";

const filas = [
  { id: 1, nombre: "", numero: "00001", estado_administrativo: "constructor" },
  { id: 2, nombre: "Registro Ficticio", numero: "00002", cobertura_habilitada: false, vigente: true, estado_administrativo: "en_tramite" },
  { id: 3, nombre: "Finalizada Ficticia", numero: "00003", cobertura_habilitada: false, finalizado_en: "2026-10-01", estado_administrativo: "baja_administrativa" },
];

function Prueba() {
  const [parametros, setParametros] = useSearchParams();
  return <main className="p-4"><PadronTabla filas={filas} total={3} paginas={1}
    estado={{ cargando: false, refrescando: false, error: null }}
    parametros={parametros} onParametrosChange={setParametros}
    fichaHref={(fila) => { const siguientes = new URLSearchParams(parametros); siguientes.set("ficha", fila.id); return `?${siguientes}`; }} />
  </main>;
}
createRoot(document.getElementById("root")).render(<BrowserRouter><Prueba /></BrowserRouter>);
