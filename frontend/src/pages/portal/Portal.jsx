import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Navigate, Outlet, Route, Routes, useNavigate } from "react-router-dom";

import { Icon } from "@/components/icons";
import { EVENTO_PORTAL_VENCIDO } from "@/api/portal";

import { NOMBRE_PORTAL } from "./comun";
import { Bienvenida, Ingresar, Olvide, Registro, ReenviarVerificacion, Restablecer, VerificarEmail } from "./Cuenta";
import { Continuar, CuentaLista, ValidarIdentidad } from "./Identidad";

/**
 * Portal del paciente (#120): cuenta propia con email y contraseña, e identidad
 * validada contra RENAPER. Es público (no pasa por la sesión de HEN) y usa su
 * propio cliente, `api/portal.js`. Las pantallas de datos (turnos, resultados)
 * llegan con el #122.
 */
export default function Portal() {
  useEffect(() => {
    const anterior = document.title;
    document.title = NOMBRE_PORTAL;
    return () => { document.title = anterior; };
  }, []);

  return <div className="portal-paciente">
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
        <Route path="cuenta" element={<CuentaLista />} />
        <Route path="*" element={<Navigate to="/mi" replace />} />
      </Route>
    </Routes>
  </div>;
}

/** Isotipo neutro mientras no haya marca. */
function Marca() {
  return <span aria-hidden="true" className="flex size-8 flex-none items-center justify-center rounded-md bg-accent text-white"><Icon name="shieldCheck" size={18} /></span>;
}

/**
 * Marco del portal: una columna angosta, pensada primero para el celular. Si la
 * sesión vence y no se puede renovar, el cliente avisa con un evento y desde
 * acá se vuelve a ingresar.
 */
function Marco() {
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

  return <div className="flex min-h-dvh flex-col bg-fondo text-texto">
    <header className="border-b border-borde bg-superficie">
      <div className="mx-auto flex h-14 max-w-[28rem] items-center gap-2.5 px-5 text-sm font-bold"><Marca />{NOMBRE_PORTAL}</div>
    </header>
    <main className="mx-auto flex w-full max-w-[28rem] flex-1 flex-col md:py-8">
      <Outlet />
    </main>
  </div>;
}
