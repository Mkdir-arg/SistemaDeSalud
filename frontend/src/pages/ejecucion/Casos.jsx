import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useInstitucion } from "../../auth/InstitutionContext";
import { PageHeader } from "../../components/Shell";
import { Badge, Card, Mono, Spinner, Table } from "../../components/ui";
import { casoId } from "../../lib/format";
import { color, estadoCaso } from "../../theme";

function asignacion(c) {
  if (c.asignado_nombre) return c.asignado_nombre;
  if (c.nodo_tipo === "espera") return "En fila";
  if (c.nodo_tipo === "tiempo") return "Dormido";
  return "Sin asignar";
}

export default function Casos() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const [casos, setCasos] = useState([]);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    if (!institucion) return;
    setCargando(true);
    (async () => {
      try {
        const d = await api.get(`/casos/?institucion=${institucion.id}`);
        setCasos(d.results || d);
      } finally {
        setCargando(false);
      }
    })();
  }, [institucion]);

  return (
    <>
      <PageHeader subtitle="Consultá y auditá todos los casos del sistema. Hacé clic en un caso para ver su trazabilidad." />
      <div style={{ padding: "18px 30px 30px" }}>
        <Card style={{ overflow: "hidden", padding: 0 }}>
          {cargando ? (
            <Spinner />
          ) : (
            <Table
              rows={casos}
              onRowClick={(c) => navigate(`/casos/${c.id}`)}
              vacio="No hay casos"
              columns={[
                { key: "id", label: "Caso", render: (c) => <Mono style={{ fontWeight: 700 }}>{casoId(c.id)}</Mono> },
                { key: "flujo_titulo", label: "Flujo" },
                { key: "paso_actual", label: "Paso actual", render: (c) => <span style={{ color: color.slate600 }}>{c.paso_actual || "—"}</span> },
                { key: "estado", label: "Estado", render: (c) => { const e = estadoCaso[c.estado] || { label: c.estado_display, tone: "neutral" }; return <Badge tone={e.tone}>{e.label}</Badge>; } },
                { key: "area_nombre", label: "Área", render: (c) => c.area_nombre || "—" },
                { key: "asignacion", label: "Asignación", render: (c) => { const a = asignacion(c); return <span style={{ color: a === "Sin asignar" ? color.slate400 : color.slate700 }}>{a}</span>; } },
              ]}
            />
          )}
        </Card>
      </div>
    </>
  );
}
