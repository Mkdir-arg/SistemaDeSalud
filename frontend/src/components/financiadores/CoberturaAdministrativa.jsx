import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Badge, Card, Mono } from "@/components/ui";

export function resumenCobertura(paciente) {
  const cobertura = paciente?.cobertura_administrativa;
  const afiliaciones = cobertura?.afiliaciones || [];
  if (afiliaciones.length > 1) return `${afiliaciones.length} afiliaciones vigentes`;
  if (afiliaciones.length === 1) {
    const afiliacion = afiliaciones[0];
    return `${afiliacion.financiador_nombre} · ${afiliacion.plan_nombre}`;
  }
  const declarada = cobertura?.declaracion_legada ?? paciente?.obra_social;
  if (declarada) return `Declarada: ${declarada}`;
  return cobertura?.habilitada ? "Sin afiliación verificada" : "";
}

export function useConfiguracionCobertura(institucionId) {
  const { user } = useAuth();
  return useQuery({
    queryKey: ["cobertura-administrativa", user?.id, institucionId, "configuracion"],
    queryFn: () => api.get(`/ciudadanos/configuracion-cobertura/?institucion=${institucionId}`),
    enabled: !!user?.id && !!institucionId,
    gcTime: 0,
    retry: false,
  });
}

export function usePacienteAdministrativo(id) {
  const { user } = useAuth();
  const { institucion } = useInstitucion();
  return useQuery({
    queryKey: ["detalle", "ciudadanos", user?.id, institucion?.id, id],
    queryFn: () => api.get(`/ciudadanos/${id}/?institucion=${institucion.id}`),
    enabled: !!user?.id && !!institucion?.id && !!id,
    gcTime: 0,
  });
}

export function AvisoCoberturaCaso() {
  return (
    <p className="text-sm text-texto-debil">
      La afiliación de cada caso se elige al ingresar; no autoriza cargos.
      Las declaraciones nuevas se registran en la cobertura del caso, con motivo.
    </p>
  );
}

const ESTADOS = {
  vigente: "Afiliación vigente",
  multiple: "Varias afiliaciones vigentes",
  sin_documento: "Sin documento para consultar el padrón",
  sin_padron: "Sin afiliación vigente en el padrón habilitado",
  no_habilitada: "Cobertura estructurada no habilitada en este hospital",
};

function fecha(iso) {
  const partes = String(iso || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
  return partes ? `${partes[3]}/${partes[2]}/${partes[1]}` : "Sin fecha informada";
}

export default function CoberturaAdministrativa({ paciente }) {
  const cobertura = paciente?.cobertura_administrativa;
  const declarada = cobertura?.declaracion_legada ?? paciente?.obra_social;
  const afiliaciones = cobertura?.afiliaciones || [];
  return (
    <Card className="p-5" role="region" aria-label="Cobertura administrativa">
      <h2 className="mb-4 text-xs font-bold uppercase tracking-wider text-texto-debil">Cobertura administrativa</h2>
      <Badge className="max-w-full whitespace-normal" tone={cobertura?.estado === "vigente" ? "green" : cobertura?.estado === "multiple" ? "amber" : "gray"}>
        {ESTADOS[cobertura?.estado] || "Sin verificación de afiliación"}
      </Badge>
      {!!afiliaciones.length && (
        <ul className="mt-3 divide-y divide-division">
          {afiliaciones.map((afiliacion) => (
            <li key={afiliacion.id} className="py-3 first:pt-0">
              <div className="text-md font-semibold">{afiliacion.financiador_nombre} · {afiliacion.plan_nombre}</div>
              <div className="mt-1 text-sm text-texto-debil">Número <Mono>{afiliacion.numero}</Mono> · Vigente desde {fecha(afiliacion.desde)}</div>
              {!afiliacion.seleccionable && <p className="mt-1 text-sm text-badge-amber-fg">{afiliacion.motivo || "Requiere revisión antes de elegirla en un caso."}</p>}
            </li>
          ))}
        </ul>
      )}
      {declarada && (
        <div className="mt-4 border-t border-division pt-3">
          <div className="text-sm text-texto-debil">Cobertura declarada (dato anterior, sin verificar)</div>
          <div className="mt-1 text-md font-semibold">{declarada}</div>
        </div>
      )}
      <div className="mt-4"><AvisoCoberturaCaso /></div>
    </Card>
  );
}
