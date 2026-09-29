import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, mensajeError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { useInstitucion } from "../auth/InstitutionContext";
import { Icon } from "./icons";

/*
 * «Ver como»: el superusuario opera con una cuenta de referencia del perfil.
 *
 * No es una vista previa del menú. El backend autoriza y acota cada pedido con
 * esa cuenta, así que lo que se ve y lo que se puede hacer es lo del perfil. La
 * autoría sigue siendo del superusuario. El catálogo sale del servidor: si a un
 * perfil le falta la cuenta, se muestra y no se puede elegir.
 */

const AMBITO_LABEL = { plataforma: "Plataforma", institucion: "Institución", financiador: "Financiador" };

function consultaDe(ambito) {
  if (ambito.tipo === "institucion") return `?institucion=${ambito.id}`;
  if (ambito.tipo === "financiador") return `?financiador=${ambito.id}`;
  return "";
}

// A dónde lleva entrar a un perfil o volver a Sistema en cada ámbito.
function destinoDe(ambito) {
  if (ambito.tipo === "financiador") return `/financiadores?financiador=${ambito.id}`;
  if (ambito.tipo === "plataforma") return "/directorio";
  return "/inicio";
}

/** El ámbito que se puede simular desde la pantalla actual, o null. */
export function ambitoSimulable({ simulacion, esPlataforma, esFinanciador, institucion, location }) {
  if (simulacion) {
    return {
      tipo: simulacion.ambito,
      id: simulacion.institucion?.id ?? simulacion.financiador?.id ?? null,
    };
  }
  if (esPlataforma) {
    const financiador = new URLSearchParams(location.search).get("financiador");
    if (location.pathname.startsWith("/financiadores") && /^\d+$/.test(financiador || "")) {
      return { tipo: "financiador", id: Number(financiador) };
    }
    return { tipo: "plataforma", id: null };
  }
  if (esFinanciador || !institucion) return null;
  return { tipo: "institucion", id: institucion.id };
}

function useCambioDePerfil(ambito) {
  const { iniciarSimulacion, salirDeSimulacion } = useAuth();
  const { setInstitucion } = useInstitucion();
  const navigate = useNavigate();
  const [cambiando, setCambiando] = useState(false);
  const [error, setError] = useState("");

  async function elegir(rol) {
    setError("");
    setCambiando(true);
    try {
      if (rol === "sistema") {
        await salirDeSimulacion();
        if (ambito.tipo !== "institucion") setInstitucion(null);
      } else {
        const me = await iniciarSimulacion({
          ambito: ambito.tipo,
          rol,
          ...(ambito.tipo === "institucion" ? { institucion: ambito.id } : {}),
          ...(ambito.tipo === "financiador" ? { financiador: ambito.id } : {}),
        });
        // El contexto de institución queda en el ámbito simulado, o vacío.
        setInstitucion(me.simulacion?.ambito === "institucion" ? me.simulacion.institucion : null);
      }
      navigate(destinoDe(ambito), { replace: true });
    } catch (e) {
      setError(mensajeError(e, "No se pudo cambiar de perfil."));
    } finally {
      setCambiando(false);
    }
  }

  return { elegir, cambiando, error };
}

export function SelectorSimulacion({ ambito }) {
  const { simulacion } = useAuth();
  const { elegir, cambiando, error } = useCambioDePerfil(ambito);
  const catalogo = useQuery({
    queryKey: ["simulacion-catalogo", ambito.tipo, ambito.id],
    queryFn: () => api.real.get(`/simulaciones/catalogo/${consultaDe(ambito)}`),
    staleTime: 0,
    gcTime: 0,
  });
  const perfiles = catalogo.data?.perfiles || [];
  const faltantes = perfiles.filter((p) => !p.disponible);

  return (
    <div className="mx-3 mt-2 rounded-md border border-borde bg-superficie-2 px-2 py-2 text-xs">
      <label htmlFor="selector-simulacion" className="block font-semibold text-texto">Ver como</label>
      <select
        id="selector-simulacion"
        value={simulacion?.rol || "sistema"}
        disabled={cambiando || catalogo.isLoading}
        onChange={(e) => elegir(e.target.value)}
        className="mt-1 h-8 w-full rounded-md border border-campo-borde bg-superficie px-2 text-xs text-texto disabled:opacity-60"
      >
        <option value="sistema">Sistema · acceso completo</option>
        {perfiles.map((p) => (
          <option key={p.rol} value={p.rol} disabled={!p.disponible} title={p.motivo || undefined}>
            {p.etiqueta}{p.disponible ? "" : " (no disponible)"}
          </option>
        ))}
      </select>
      {catalogo.error && <p role="alert" className="mt-1 text-danger">No se pudo consultar los perfiles de este ámbito.</p>}
      {faltantes.length > 0 && (
        <p className="mt-1 text-texto-suave">
          {faltantes.length === perfiles.length
            ? "Este ámbito no tiene cuentas de referencia preparadas."
            : `Sin cuenta de referencia: ${faltantes.map((p) => p.etiqueta).join(", ")}.`}
        </p>
      )}
      {error && <p role="alert" className="mt-1 text-danger">{error}</p>}
      <p className="mt-1 text-texto-suave">Se opera con los permisos reales del perfil; lo que hagas queda a tu nombre.</p>
    </div>
  );
}

/** Indicador fijo de la simulación, con la salida a Sistema. */
export function BannerSimulacion() {
  const { simulacion, avisoSimulacion, descartarAvisoSimulacion } = useAuth();
  const ambito = simulacion ? ambitoSimulable({ simulacion }) : null;
  const { elegir, cambiando, error } = useCambioDePerfil(ambito || { tipo: "plataforma", id: null });

  if (!simulacion) {
    if (!avisoSimulacion) return null;
    return (
      <div role="status" className="flex flex-wrap items-center gap-2 border-b border-borde bg-badge-amber-bg px-lg py-2 text-sm text-badge-amber-fg sm:px-[24px]">
        <Icon name="alert" size={15} />
        <span>La simulación terminó: {avisoSimulacion} Volviste a Sistema.</span>
        <button type="button" onClick={descartarAvisoSimulacion} className="ml-auto font-semibold underline">Entendido</button>
      </div>
    );
  }

  const lugar = simulacion.institucion?.nombre || simulacion.financiador?.nombre || "Plataforma";
  const quien = simulacion.superusuario?.nombre || simulacion.superusuario?.email;
  return (
    <div role="status" aria-label="Simulación de perfil activa"
      className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-accent-100 bg-accent-50 px-lg py-2 text-sm text-texto sm:px-[24px]">
      <Icon name="eye" size={15} className="text-accent" />
      <span>
        <strong>Simulando {simulacion.etiqueta}</strong>
        <span className="text-texto-suave"> · {AMBITO_LABEL[simulacion.ambito]}: {lugar}</span>
      </span>
      <span className="text-texto-suave">
        Permisos de «{simulacion.cuenta?.nombre}». Lo que hagas queda a nombre de {quien}.
      </span>
      {error && <span role="alert" className="text-danger">{error}</span>}
      <button
        type="button"
        onClick={() => elegir("sistema")}
        disabled={cambiando}
        className="ml-auto flex h-8 shrink-0 items-center gap-1.5 rounded-md border border-accent-100 bg-superficie px-3 font-semibold text-accent hover:bg-accent-100 disabled:opacity-60"
      >
        <Icon name="back" size={14} /> Volver a Sistema
      </button>
    </div>
  );
}
