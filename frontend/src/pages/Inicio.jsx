import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "@/api/client";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import { Badge, Card, Spinner } from "@/components/ui";
import { EstadoError } from "@/components/ui/estados";

/**
 * Secciones de la institución, filtradas por capacidad igual que el menú.
 *
 * El acento de cada una sale de la paleta de nodos. No es que una sección «sea»
 * un tipo de nodo: se reusa la paleta porque ya está definida en tokens y tiene
 * su variante oscura resuelta. Antes eran hex fijos con el tinte al 10% (`+"1A"`),
 * que en tema oscuro quedaba un manchón claro sobre fondo negro.
 *
 * El color va SOLO en el ícono y su fondo. Nunca en texto: esta paleta no llega
 * al contraste AA como texto y ya rompió tres veces por usarla así.
 */
const SECCIONES = [
  { label: "Flujos", hint: "Diseñar y publicar procesos", icon: "workflow", to: "/flujos", cap: "diseno_flujos", cat: "form" },
  { label: "Formularios", hint: "Biblioteca de formularios", icon: "form", to: "/formularios", cap: "diseno_flujos", cat: "derivar" },
  { label: "Bandeja de tareas", hint: "Operar casos del día", icon: "inbox", to: "/bandeja", cap: "casos_operar", cat: "decision" },
  { label: "Historia clínica", hint: "Expedientes de pacientes", icon: "clipboard", to: "/historia", cap: "historia_clinica", cat: "atencion" },
  { label: "Estructura organizativa", hint: "Áreas, sub-áreas y staff", icon: "cube", to: "/estructura", cap: "config_institucional", cat: "tiempo" },
  { label: "Administración", hint: "Usuarios y accesos", icon: "users", to: "/administracion", cap: "config_institucional", cat: "estado" },
];

// Clases completas por categoría: Tailwind no puede resolver `bg-nodo-${cat}-tint`
// en tiempo de compilación, así que si se arma el nombre por concatenación la
// clase no llega al CSS y el color desaparece sin error.
const ACENTO = {
  form: "bg-nodo-form-tint text-nodo-form-sol",
  derivar: "bg-nodo-derivar-tint text-nodo-derivar-sol",
  decision: "bg-nodo-decision-tint text-nodo-decision-sol",
  atencion: "bg-nodo-atencion-tint text-nodo-atencion-sol",
  tiempo: "bg-nodo-tiempo-tint text-nodo-tiempo-sol",
  estado: "bg-nodo-estado-tint text-nodo-estado-sol",
};

export default function Inicio() {
  const { institucion, puedeVer } = useInstitucion();
  // Sub-recurso, no un detalle: `useDetalle` arma `/recurso/{id}/` y acá hace falta
  // `/instituciones/{id}/metricas/`.
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["metricas-institucion", institucion?.id],
    queryFn: () => api.get(`/instituciones/${institucion.id}/metricas/`),
    enabled: institucion?.id != null,
  });

  if (!institucion) return <Spinner />;

  const secciones = SECCIONES.filter((s) => puedeVer(s.cap));
  const metricas = [
    { n: data?.areas, l: "Áreas" },
    { n: data?.subareas, l: "Sub-áreas" },
    { n: data?.staff, l: "Staff" },
    { n: data?.casos_activos, l: "Casos activos" },
  ];

  return (
    <div className="px-lg py-[26px] sm:px-[30px]">
      {/* Cabecera de institución */}
      <Card data-tour="inicio-institucion" className="mb-5 flex flex-wrap items-center gap-lg px-6 py-[22px]">
        <div className="flex size-12 flex-none items-center justify-center rounded-lg bg-accent-50 text-accent">
          <Icon name="building" size={24} />
        </div>
        <div className="leading-tight">
          <div className="text-xl font-bold">{institucion.nombre}</div>
          <div className="text-sm text-texto-tenue">{institucion.tipo || "Institución"}</div>
        </div>
        <div className="flex-1" />
        <Link
          to="/bandeja"
          data-tour="inicio-operar"
          className="flex h-10 items-center gap-2 rounded-lg bg-accent-fuerte px-lg text-base font-semibold text-sobre-accent hover:brightness-110"
        >
          <Icon name="enter" size={15} /> Operar
        </Link>
        <Badge tone={institucion.activa === false ? "gray" : "green"}>
          {institucion.activa === false ? "Inactiva" : "Activa"}
        </Badge>
      </Card>

      {/* Métricas */}
      {error ? (
        <Card className="mb-6">
          <EstadoError error={error} onReintentar={refetch} titulo="No se pudieron cargar las métricas" />
        </Card>
      ) : (
        <div className="mb-6 grid grid-cols-2 gap-3.5 sm:grid-cols-4">
          {metricas.map((c) => (
            <Card key={c.l} className="p-[18px]">
              {/* `cifra`, no `xxl`: es el contenido de la tarjeta, no un título. */}
              <div className="text-cifra font-bold leading-none">
                {isLoading ? "…" : (c.n ?? "—")}
              </div>
              <div className="mt-[7px] text-sm text-texto-tenue">{c.l}</div>
            </Card>
          ))}
        </div>
      )}

      {/* Secciones de la institución */}
      <h2 className="mb-3.5 text-base font-bold text-texto-suave">Secciones de la institución</h2>
      <div className="grid gap-lg sm:grid-cols-2 lg:grid-cols-3">
        {secciones.map((s) => (
          // <Link> y no <Card onClick>: son navegaciones, así que tienen que
          // abrirse en pestaña nueva con ctrl+clic y ser alcanzables por teclado.
          <Link
            key={s.to}
            to={s.to}
            data-tour={`inicio-${s.to.slice(1)}`}
            className="rounded-lg border border-borde bg-superficie p-5 transition hover:border-accent-100 hover:shadow-float"
          >
            <div className={`mb-3 flex size-10 items-center justify-center rounded-lg ${ACENTO[s.cat]}`}>
              <Icon name={s.icon} size={20} />
            </div>
            <div className="text-md font-bold">{s.label}</div>
            <div className="mt-0.5 text-sm text-texto-tenue">{s.hint}</div>
          </Link>
        ))}
      </div>
    </div>
  );
}
