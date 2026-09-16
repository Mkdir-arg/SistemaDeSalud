import { Badge } from "@/components/ui";

export const ESTADOS_EVALUACION_AUTORIZACION = {
  no_requerida: "No requerida", sin_solicitud: "Sin solicitud", pendiente: "Pendiente",
  observada: "Observada", aprobada: "Aprobada", rechazada: "Rechazada", vencida: "Vencida",
  anulada: "Anulada", sin_cantidad: "Sin cantidad disponible", fuera_vigencia: "Fuera de vigencia",
};

export default function AutorizacionEvaluacion({ evaluacion }) {
  if (!evaluacion?.requiere_autorizacion) return null;
  const aprobada = evaluacion.estado_autorizacion === "aprobada";
  return <div className="space-y-2 rounded-md border border-division p-3 text-sm" role="region" aria-label="Autorización de esta evaluación">
    <div className="flex flex-wrap items-center gap-2"><span className="font-semibold">Autorización previa</span><Badge tone={aprobada ? "green" : "amber"}>{ESTADOS_EVALUACION_AUTORIZACION[evaluacion.estado_autorizacion] || "Pendiente de verificar"}</Badge></div>
    {evaluacion.autorizacion && <p>Solicitud {evaluacion.autorizacion}{evaluacion.autorizacion_disponible != null ? ` · Cantidad autorizada disponible: ${evaluacion.autorizacion_disponible}` : ""}</p>}
    <p className="text-texto-debil">{aprobada ? "La vigencia y la cantidad aprobada se verifican otra vez al reservar y realizar la prestación." : "La reserva puede comprometer cupo del plan. Si se realiza sin aprobación vigente, la parte del financiador queda pendiente de autorización; el copago requiere aceptación expresa."}</p>
    <p className="text-texto-debil">Los importes de esta evaluación todavía no son cuentas por cobrar.</p>
  </div>;
}
