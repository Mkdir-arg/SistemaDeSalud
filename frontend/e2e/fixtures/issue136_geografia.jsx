import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { AuthProvider } from "../../src/auth/AuthContext";
import { ToastProvider } from "../../src/components/ui/toast";
import { EditarPacienteModal } from "../../src/pages/registros/PadronDetalle";
import FormularioPadron from "../../src/components/financiadores/FormularioPadron";
import { BLOQUES_PADRON } from "../../src/components/financiadores/padronCampos";
import { api } from "../../src/api/client";
import Geografia from "../../src/components/issue136_Geografia";
import { cuerpoGeo, hayGeoPendiente } from "../../src/lib/issue136_geografia";
import "../../src/index.css";

function Prueba() {
  const [geo, setGeo] = useState(null);
  const [guardado, setGuardado] = useState(false);
  const [cerrado, setCerrado] = useState(false);
  const [organizacion, setOrganizacion] = useState(21);
  const [visible, setVisible] = useState(true);
  const modo = new URLSearchParams(location.search).get("modo");
  if (guardado) return <p>Edición ficticia guardada</p>;
  if (cerrado) return <p>Edición ficticia cancelada</p>;
  if (modo === "editar-paciente") return <EditarPacienteModal paciente={{ id: 45, institucion: 21, nombre: "Paciente ficticio", domicilio: "Detalle anterior", geografia: { provincia: { id: 1, nombre: "Provincia A", origen: "georef" } } }} onClose={() => setCerrado(true)} onListo={() => setGuardado(true)} />;
  if (modo === "editar-afiliado") return <FormularioPadron titulo="Editar domicilio" campos={BLOQUES_PADRON.find((b) => b.titulo === "Domicilio").campos}
    inicial={{ calle: "Detalle anterior", provincia: "Provincia legada", localidad: "Localidad legada" }} geografiaOrganizacion={21}
    guardar={(cambios, motivo) => api.patch("/financiadores/21/padron/45/", { ...cambios, revision: 1, motivo })}
    onClose={() => {}} onGuardado={() => setGuardado(true)} />;
  return <main className="p-6"><h1>Domicilio ficticio</h1>
    {modo === "cache" && <>
      <button onClick={() => { setOrganizacion((id) => id === 21 ? 22 : 21); setGeo(null); }}>Cambiar organización de prueba</button>
      <button onClick={() => setVisible((v) => !v)}>{visible ? "Ocultar ubicación" : "Mostrar ubicación"}</button>
    </>}
    {visible && <Geografia value={geo} ambito="institucion" organizacion={organizacion} onChange={setGeo} />}
    <button disabled={hayGeoPendiente(geo)} onClick={() => fetch("/api/domicilio-ficticio/", { method: "POST", body: JSON.stringify({ geografia: cuerpoGeo(geo) }) })}>Guardar domicilio ficticio</button>
    <output aria-label="Estado sintético">{JSON.stringify(cuerpoGeo(geo))}</output></main>;
}
createRoot(document.getElementById("root")).render(<QueryClientProvider client={new QueryClient()}><BrowserRouter><AuthProvider><ToastProvider><Prueba /></ToastProvider></AuthProvider></BrowserRouter></QueryClientProvider>);
