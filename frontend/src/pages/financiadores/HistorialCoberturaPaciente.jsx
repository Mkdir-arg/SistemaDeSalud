import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { Ayuda, Badge, Button, Card, Spinner } from "@/components/ui";
import { EstadoError, EstadoVacio } from "@/components/ui/estados";
import { casoId, fechaHora, plural } from "@/lib/format";
import { POR_PAGINA } from "@/api/queries";

const ESTADOS = { verificada: "Afiliación verificada", pendiente: "Pendiente de verificación", particular: "Atención particular" };

export default function HistorialCoberturaPaciente({ ciudadanoId }) {
  const { user } = useAuth();
  const [page, setPage] = useState(1);
  const consulta = useQuery({
    queryKey: ["historial-cobertura", user?.id, ciudadanoId, page],
    queryFn: () => api.get(`/ciudadanos/${ciudadanoId}/cobertura/?page=${page}&page_size=${POR_PAGINA}`),
    retry: false,
    gcTime: 0,
  });

  return (
    <Card aria-label="Historial de cobertura del paciente">
      <div className="border-b border-division p-5">
        <div className="flex items-center gap-2"><h2 className="text-lg font-bold">Cobertura por caso</h2><Ayuda>Afiliaciones y correcciones registradas en los casos a los que tenés acceso. Cada atención conserva su selección, aunque después cambie el padrón del financiador.</Ayuda></div>
      </div>
      {consulta.isLoading ? <Spinner label="Consultando historial de cobertura…" /> : consulta.error ? (
        <EstadoError error={consulta.error} onReintentar={consulta.refetch} titulo="No se pudo consultar el historial de cobertura" />
      ) : !(consulta.data?.results || []).length ? (
        <EstadoVacio titulo="No hay afiliaciones registradas en los casos visibles" detalle="La afiliación se selecciona desde la cobertura de cada caso." />
      ) : (
        <ol className="divide-y divide-division">
          {consulta.data.results.map((item) => (
            <li key={item.id} className="space-y-2 p-5 text-sm">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="font-semibold">{casoId(item.caso)} · {item.flujo_titulo}</p>
                <Badge tone={item.estado === "pendiente" ? "amber" : item.estado === "verificada" ? "green" : "gray"}>{ESTADOS[item.estado] || item.estado}</Badge>
              </div>
              {item.financiador_nombre && <p className="font-semibold">{item.financiador_nombre} · {item.plan_nombre || "Sin plan"}</p>}
              {item.numero && <p>N.º de afiliado: {item.numero}</p>}
              {item.declaracion && <p className="break-words">{item.declaracion}</p>}
              <p className="break-words text-texto-debil">{item.motivo}</p>
              <p className="text-texto-tenue">{fechaHora(item.creado)} · {item.usuario_nombre || "Usuario registrado"}</p>
            </li>
          ))}
        </ol>
      )}
      {consulta.data && !consulta.error && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-division p-4">
          <p className="text-sm text-texto-debil">{plural(consulta.data.count, "registro", "registros")} · {consulta.data.count === 0 ? "Sin páginas" : `Página ${page} de ${Math.ceil(consulta.data.count / POR_PAGINA)}`}</p>
          <div className="flex gap-2">
            <Button type="button" size="sm" variant="ghost" disabled={page === 1 || consulta.isFetching} onClick={() => setPage(page - 1)}>Anterior</Button>
            <Button type="button" size="sm" variant="ghost" disabled={!consulta.data.next || consulta.isFetching} onClick={() => setPage(page + 1)}>Siguiente</Button>
          </div>
        </div>
      )}
    </Card>
  );
}
