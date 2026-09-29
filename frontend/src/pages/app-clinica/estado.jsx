import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { DNI_CONOCIDO, historiaConocida, pacienteConocida, profesional, turno as nuevoTurno } from "./datos";

// El estado vive en sessionStorage: sobrevive a recargas y links directos dentro
// de la misma pestaña, y al cerrarla la demo vuelve a empezar de cero. Nada sale
// del navegador.
const CLAVE = "hen.app-clinica.v1";
const INICIAL = { paciente: null, ingreso: null, borrador: null, turnos: [], resultados: [], preferencias: { recordatorios: true, resultados: true } };

function leer() {
  try {
    const guardado = JSON.parse(sessionStorage.getItem(CLAVE));
    return guardado?.paciente !== undefined ? { ...INICIAL, ...guardado } : INICIAL;
  } catch {
    return INICIAL;
  }
}

// Fila de ejemplo: al dar presente la persona queda 3.ª y avanza un lugar cada
// pocos segundos, para que el llamado llegue durante la presentación.
export const LUGAR_INICIAL = 3;
export const SEGUNDOS_POR_LUGAR = 8;

/** En qué etapa está un turno ahora mismo. La fila se deriva del reloj, no se guarda. */
export function etapa(turno, ahora = Date.now()) {
  if (turno.estado !== "presente") return { tipo: turno.estado };
  const avance = Math.floor((ahora - turno.presenteDesde) / (SEGUNDOS_POR_LUGAR * 1000));
  const lugar = LUGAR_INICIAL - avance;
  return lugar > 0 ? { tipo: "en-fila", lugar } : { tipo: "llamado" };
}

export const ACTIVOS = new Set(["confirmado", "presente", "en-consulta"]);

/** Reloj que se actualiza solo mientras `activo`; alcanza para la fila. */
export function useAhora(activo = true, cada = 1000) {
  const [ahora, setAhora] = useState(Date.now);
  useEffect(() => {
    if (!activo) return undefined;
    const id = setInterval(() => setAhora(Date.now()), cada);
    return () => clearInterval(id);
  }, [activo, cada]);
  return ahora;
}

const Contexto = createContext(null);

export function AppClinicaProvider({ children }) {
  const [estado, setEstado] = useState(leer);
  const [aviso, setAviso] = useState(null);
  const temporizador = useRef();
  const actual = useRef(estado);
  actual.current = estado;

  useEffect(() => {
    try { sessionStorage.setItem(CLAVE, JSON.stringify(estado)); } catch { /* sin almacenamiento: la demo sigue en memoria */ }
  }, [estado]);

  const avisar = useCallback((texto) => {
    clearTimeout(temporizador.current);
    setAviso({ texto, id: Date.now() });
    temporizador.current = setTimeout(() => setAviso(null), 3500);
  }, []);

  const acciones = useMemo(() => {
    const cambiarTurno = (id, cambios) => setEstado((e) => ({ ...e, turnos: e.turnos.map((t) => (t.id === id ? { ...t, ...cambios } : t)) }));
    return {
      empezarIngreso: (dni) => setEstado((e) => ({ ...e, ingreso: { dni, conocida: dni === DNI_CONOCIDO } })),
      guardarDatos: (datos) => setEstado((e) => ({ ...e, ingreso: { ...e.ingreso, datos } })),
      confirmarCodigo: () => setEstado((e) => {
        if (e.ingreso?.conocida) return { ...e, ingreso: null, paciente: pacienteConocida(), ...historiaConocida() };
        return { ...e, ingreso: null, paciente: { dni: e.ingreso.dni, ...e.ingreso.datos, desde: String(new Date().getFullYear()) }, turnos: [], resultados: [] };
      }),
      elegir: (cambios) => setEstado((e) => ({ ...e, borrador: { ...e.borrador, ...cambios } })),
      empezarTurno: (borrador = {}) => setEstado((e) => ({ ...e, borrador })),
      /** Confirma el borrador: crea un turno nuevo o reprograma uno existente. Devuelve su id. */
      reservar: () => {
        // Se lee del ref y no dentro del updater: React no garantiza correrlo en
        // el momento (y en StrictMode lo corre dos veces), así que el id se perdería.
        const { profesionalId, dia, hora, recordatorio = true, reprograma } = actual.current.borrador;
        const p = profesional(profesionalId);
        if (reprograma) {
          setEstado((e) => ({ ...e, borrador: null, turnos: e.turnos.map((t) => (t.id === reprograma ? { ...t, profesionalId, especialidad: p.especialidad, profesional: p.nombre, consultorio: p.consultorio, dia, hora, recordatorio, estado: "confirmado", presenteDesde: undefined } : t)) }));
          return reprograma;
        }
        const creado = nuevoTurno(profesionalId, dia, hora, { recordatorio });
        setEstado((e) => ({ ...e, borrador: null, turnos: [...e.turnos, creado] }));
        return creado.id;
      },
      cancelar: (id) => cambiarTurno(id, { estado: "cancelado", presenteDesde: undefined }),
      darPresente: (id) => cambiarTurno(id, { estado: "presente", presenteDesde: Date.now() }),
      entrarAConsulta: (id) => cambiarTurno(id, { estado: "en-consulta" }),
      verResultado: (id) => setEstado((e) => ({ ...e, resultados: e.resultados.map((r) => (r.id === id ? { ...r, nuevo: false } : r)) })),
      preferencia: (clave, valor) => setEstado((e) => ({ ...e, preferencias: { ...e.preferencias, [clave]: valor } })),
      salir: () => setEstado(INICIAL),
    };
  }, []);

  const valor = useMemo(() => ({ ...estado, acciones, aviso, avisar }), [estado, acciones, aviso, avisar]);
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export const useApp = () => useContext(Contexto);

/** Próximo turno vigente (el de hoy primero), o null. */
export function proximoTurno(turnos) {
  return [...turnos].filter((t) => ACTIVOS.has(t.estado)).sort((a, b) => `${a.dia}${a.hora}`.localeCompare(`${b.dia}${b.hora}`))[0] || null;
}
