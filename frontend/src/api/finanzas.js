import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/auth/AuthContext";
import { useInstitucion } from "@/auth/InstitutionContext";
import { api } from "./client";
import { query } from "./queries";

const ACCIONES_GASTOS = ["ver_gastos", "registrar_gastos", "aprobar_gastos", "corregir_gastos", "configurar_gastos_esperados"];

export function usePermisosFinanzas() {
  const { user } = useAuth();
  const { institucion, vista } = useInstitucion();
  const consulta = useQuery({
    queryKey: ["permisos-finanzas", user?.id],
    queryFn: () => api.get("/concesiones-financieras/mias/"),
    enabled: Boolean(user),
    staleTime: 0,
    gcTime: 0,
  });
  const superusuario = consulta.data?.superusuario && vista === "sistema";
  const concesiones = (consulta.data?.concesiones || []).filter((c) => c.institucion === institucion?.id);
  const tiene = (accion) => Boolean(superusuario || concesiones.some((c) => c.accion === accion));
  const permite = (accion, area, sensible = false, central = false) => Boolean(
    superusuario || concesiones.some((c) => c.accion === accion
      && (!sensible || c.permite_sensibles) && (!central || c.administrativa)
      && (c.todas_las_areas || (area != null && c.areas.includes(Number(area)))))
  );
  return { ...consulta, tiene, permite, acceso: ACCIONES_GASTOS.some(tiene), usuarioId: user?.id };
}

// Los selectores deben recorrer todas las páginas: una opción fuera de la
// primera página no puede desaparecer del formulario silenciosamente.
export async function opcionesFinanzas(recurso, institucion, filtros = {}) {
  const filas = [];
  for (let page = 1; ; page += 1) {
    const datos = await api.get(`/${recurso}/${query({ ...filtros, institucion, page })}`);
    filas.push(...(Array.isArray(datos) ? datos : datos.results));
    if (!datos.next) return filas;
  }
}

export const ESTADOS_CARGA = {
  falta_cargar: { label: "Falta cargar", tone: "amber" },
  carga_completa: { label: "Carga completa", tone: "info" },
  no_corresponde: { label: "No corresponde", tone: "gray" },
};
export const ESTADOS_GASTO = {
  pendiente_aprobacion: { label: "Pendiente de aprobación", tone: "amber" },
  aprobado: { label: "Aprobado", tone: "green" },
  rechazado: { label: "Rechazado", tone: "error" },
  reemplazado: { label: "Reemplazado", tone: "gray" },
};

export function importeARS(valor) {
  if (valor == null || valor === "") return "Importe no disponible";
  // Conservar el decimal del backend; no sumar ni convertir dinero a float.
  const [entero, decimales = "00"] = String(valor).split(".");
  return `ARS ${entero.replace(/\B(?=(\d{3})+(?!\d))/g, ".")},${decimales.padEnd(2, "0")}`;
}
