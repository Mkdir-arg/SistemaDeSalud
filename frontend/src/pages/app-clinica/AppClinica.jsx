import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { Clinica, Perfil } from "./Clinica";
import { AppClinicaProvider } from "./estado";
import Inicio from "./Inicio";
import { Bienvenida, Codigo, Datos, Dni, MarcoIngreso } from "./Ingreso";
import { CodigoQr, EnFila, Llamado, Llegada } from "./Llegada";
import { DetalleResultado, Resultados } from "./Resultados";
import { Confirmar, Especialidad, Horario } from "./SacarTurno";
import { Marco } from "./Shell";
import { CancelarTurno, DetalleTurno, MisTurnos, TurnoConfirmado } from "./Turnos";
import { ruta } from "./ui";

/**
 * App de pacientes de una institución (marca blanca "Clínica Modelo"), pública
 * y sin API: sirve para mostrar en una demo cómo la ve un paciente desde el
 * celular o la compu. Cada pantalla tiene su ruta, así los links, el "atrás"
 * del navegador y una recarga se comportan como en una app real.
 */
export default function AppClinica() {
  useEffect(() => {
    const anterior = document.title;
    document.title = "Clínica Modelo · Mi portal";
    return () => { document.title = anterior; };
  }, []);

  return <div className="clinica-demo">
    <AppClinicaProvider>
      <Routes>
        <Route element={<MarcoIngreso />}>
          <Route index element={<Bienvenida />} />
          <Route path="ingresar" element={<Dni />} />
          <Route path="ingresar/datos" element={<Datos />} />
          <Route path="ingresar/codigo" element={<Codigo />} />
        </Route>
        <Route element={<Marco />}>
          <Route path="inicio" element={<Inicio />} />
          <Route path="turnos" element={<MisTurnos />} />
          <Route path="resultados" element={<Resultados />} />
          <Route path="clinica" element={<Clinica />} />
          <Route path="perfil" element={<Perfil />} />
        </Route>
        <Route element={<Marco enfoque />}>
          <Route path="sacar-turno" element={<Especialidad />} />
          <Route path="sacar-turno/horario" element={<Horario />} />
          <Route path="sacar-turno/confirmar" element={<Confirmar />} />
          <Route path="turnos/:id" element={<DetalleTurno />} />
          <Route path="turnos/:id/confirmado" element={<TurnoConfirmado />} />
          <Route path="turnos/:id/cancelar" element={<CancelarTurno />} />
          <Route path="turnos/:id/llegada" element={<Llegada />} />
          <Route path="turnos/:id/qr" element={<CodigoQr />} />
          <Route path="turnos/:id/fila" element={<EnFila />} />
          <Route path="resultados/:id" element={<DetalleResultado />} />
        </Route>
        <Route path="turnos/:id/llamado" element={<Llamado />} />
        <Route path="*" element={<Navigate to={ruta()} replace />} />
      </Routes>
    </AppClinicaProvider>
  </div>;
}
