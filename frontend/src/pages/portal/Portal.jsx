import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Navigate, Outlet, Route, Routes, useNavigate } from "react-router-dom";

import { EVENTO_PORTAL_VENCIDO } from "@/api/portal";

import { Cobertura } from "./Cobertura";
import { ConIdentidadValidada, NOMBRE_PORTAL } from "./comun";
import { Bienvenida, Ingresar, Olvide, Registro, ReenviarVerificacion, Restablecer, VerificarEmail } from "./Cuenta";
import { Estudios } from "./Estudios";
import { Continuar, MiCuenta, ValidarIdentidad } from "./Identidad";
import { Inicio } from "./Inicio";
import { Llamado } from "./Llamado";
import { DetalleTurno, MisTurnos } from "./Turnos";

/**
 * Portal del paciente: cuenta propia con email y contraseña e identidad
 * validada contra RENAPER (#120), y la app con sus datos en toda la red (#122).
 * Es público (no pasa por la sesión de HEN) y usa su propio cliente,
 * `api/portal.js`.
 */
export default function Portal() {
  useEffect(() => {
    const anterior = document.title;
    document.title = NOMBRE_PORTAL;
    return () => { document.title = anterior; };
  }, []);

  return <div className="portal-paciente">
    <SesionVencida />
    <Routes>
      <Route element={<Marco />}>
        <Route index element={<Bienvenida />} />
        <Route path="crear-cuenta" element={<Registro />} />
        <Route path="verificar-email" element={<VerificarEmail />} />
        <Route path="reenviar-verificacion" element={<ReenviarVerificacion />} />
        <Route path="ingresar" element={<Ingresar />} />
        <Route path="olvide" element={<Olvide />} />
        <Route path="restablecer" element={<Restablecer />} />
        <Route path="continuar" element={<Continuar />} />
        <Route path="validar-identidad" element={<ValidarIdentidad />} />
      </Route>
      <Route element={<MarcoApp />}>
        <Route path="inicio" element={<Inicio />} />
        <Route path="turnos" element={<MisTurnos />} />
        <Route path="turnos/:id" element={<DetalleTurno />} />
        <Route path="estudios" element={<Estudios />} />
        <Route path="cobertura" element={<Cobertura />} />
        <Route path="llamado" element={<Llamado />} />
        <Route path="cuenta" element={<MiCuenta />} />
      </Route>
      <Route path="*" element={<Navigate to="/mi" replace />} />
    </Routes>
  </div>;
}

/**
 * Si la sesión vence y no se puede renovar, el cliente avisa con un evento y
 * desde acá se vuelve a ingresar, desde cualquier pantalla.
 */
function SesionVencida() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  useEffect(() => {
    const vencida = () => {
      qc.removeQueries({ queryKey: ["portal"] });
      navigate("/mi/ingresar", { replace: true, state: { aviso: "Tu sesión venció. Ingresá de nuevo." } });
    };
    window.addEventListener(EVENTO_PORTAL_VENCIDO, vencida);
    return () => window.removeEventListener(EVENTO_PORTAL_VENCIDO, vencida);
  }, [navigate, qc]);
  return null;
}

/**
 * Marco de la cuenta: una columna angosta, pensada primero para el celular. Como
 * en Figma, sin barra superior: cada pantalla trae su título y su «atrás».
 */
function Marco() {
  return <div className="flex min-h-dvh flex-col bg-fondo text-texto">
    <main className="mx-auto flex w-full max-w-[28rem] flex-1 flex-col md:py-8">
      <Outlet />
    </main>
  </div>;
}

/**
 * Marco de la app: sólo con la identidad validada. Como en Figma, sin pestañas:
 * el inicio lleva a cada sección y cada sección vuelve al inicio.
 */
function MarcoApp() {
  return <ConIdentidadValidada>{(cuenta) => <div className="flex min-h-dvh flex-col bg-fondo text-texto">
    <main className="mx-auto flex w-full max-w-[28rem] flex-1 flex-col px-5 pb-8 pt-4 md:py-10">
      <Outlet context={cuenta} />
    </main>
  </div>}</ConIdentidadValidada>;
}
