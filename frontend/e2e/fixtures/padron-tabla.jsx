// Harness de componente: NO backend, orden/filtro ni evidencia de persistencia.
import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, useSearchParams } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import PadronTabla from "../../src/components/financiadores/PadronTabla";
import { cambiarEstadoPadron, estadoDerechoPadron, parametrosConsultaPadron } from "../../src/components/financiadores/padronTablaEstado";
import "../../src/index.css";

const filas = [
  { id: 1, nombre: "Afiliado Ficticio A", numero: "001", documento: "90000001", plan: 3, vigente: true, desde: "2026-10-01", estado_administrativo: "en_tramite", localidad: "Río", regimen: "dependencia" },
  { id: 2, nombre: "Afiliado Ficticio B", numero: "002", documento: "90000002", plan: null, vigente: false, desde: "2026-12-01", estado_administrativo: "en_tramite", localidad: "Monte", regimen: "monotributo" },
];
function Prueba() {
  const [parametros, setParametros] = useSearchParams();
  const [accion, setAccion] = useState("");
  const [pendientes, setPendientes] = useState(false);
  const [mostrarTabla, setMostrarTabla] = useState(true);
  const [notificaciones, setNotificaciones] = useState(0);
  const consulta = parametrosConsultaPadron(parametros).toString();
  useEffect(() => { void fetch(`/__fixture_padron_consulta?${consulta}`); }, [consulta]);
  const modo = parametros.get("modo");
  return <main className="p-4">
    <label>Estado global<select value={estadoDerechoPadron(parametros)} onChange={(e) => setParametros(cambiarEstadoPadron(parametros, e.target.value))}><option value="vigentes">Vigentes</option><option value="finalizadas">Finalizadas</option><option value="futuras">Futuras</option><option value="todos">Todos</option></select></label>
    <button disabled={pendientes}>Exportar ficticio</button>
    <button onClick={() => setMostrarTabla((v) => !v)}>Mostrar u ocultar tabla</button>
    <button onClick={() => { const nuevos = new URLSearchParams(parametros); nuevos.set("financiador", "22"); setParametros(nuevos); }}>Cambiar organización</button>
    {mostrarTabla && <PadronTabla filas={modo ? [] : filas} total={modo ? 0 : 25} paginas={modo ? 1 : 3}
      parametros={parametros} onParametrosChange={setParametros} planes={[{ id: 3, nombre: "Plan Base Ficticio" }]}
      onFiltrosPendientesChange={(v) => { setPendientes(v); setNotificaciones((n) => n + 1); }}
      fichaHref={(f) => `?${parametros}&ficha=${f.id}`}
      renderAcciones={(f) => <button onClick={() => setAccion(`Editar ${f.id}`)}>Editar {f.nombre}</button>}
      estado={{ cargando: modo === "cargando", refrescando: false, error: modo === "error" ? new Error("Consulta rechazada") : null, reintentar: () => setParametros({}) }} />}
    <output aria-label="Notificaciones pendientes">{notificaciones}</output>
    <output aria-label="Acción realizada">{accion}</output>
    <output aria-label="Consulta aplicada" className="block break-all">{consulta}</output>
  </main>;
}
createRoot(document.getElementById("root")).render(<QueryClientProvider client={new QueryClient()}><BrowserRouter><Prueba /></BrowserRouter></QueryClientProvider>);
