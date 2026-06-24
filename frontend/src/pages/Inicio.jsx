import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useInstitucion } from "../auth/InstitutionContext";
import { Badge, Card, Spinner } from "../components/ui";
import { Icon } from "../components/icons";
import { color } from "../theme";

// Panel de institución (pantalla Inicio), fiel a docs/captures/02-panel-institucion.png
export default function Inicio() {
  const { institucion, puedeVer } = useInstitucion();
  const navigate = useNavigate();
  const [m, setM] = useState(null);

  useEffect(() => {
    if (!institucion) return;
    api.get(`/instituciones/${institucion.id}/metricas/`).then(setM).catch(() => setM({}));
  }, [institucion]);

  const metricas = [
    { n: m?.areas ?? "—", l: "Áreas" },
    { n: m?.subareas ?? "—", l: "Sub-áreas" },
    { n: m?.staff ?? "—", l: "Staff" },
    { n: m?.casos_activos ?? "—", l: "Casos activos" },
  ];

  // Secciones de la institución (gateadas por rol, como el menú).
  const secciones = [
    { label: "Flujos", hint: "Diseñar y publicar procesos", icon: "workflow", to: "/flujos", grupo: "DISEÑO", c: "#3949C0" },
    { label: "Formularios", hint: "Biblioteca de formularios", icon: "form", to: "/formularios", grupo: "DISEÑO", c: "#0E8893" },
    { label: "Bandeja de tareas", hint: "Operar casos del día", icon: "inbox", to: "/bandeja", grupo: "TRABAJO", c: "#A96A12" },
    { label: "Historia clínica", hint: "Expedientes de pacientes", icon: "clipboard", to: "/historia", grupo: "REGISTROS", c: "#D14B8F" },
    { label: "Estructura organizativa", hint: "Áreas, sub-áreas y staff", icon: "cube", to: "/estructura", grupo: "SISTEMA", c: "#0E9E8E" },
    { label: "Administración", hint: "Usuarios y accesos", icon: "users", to: "/administracion", grupo: "SISTEMA", c: "#5B7A99" },
  ].filter((s) => puedeVer(s.grupo));

  if (!institucion) return <Spinner />;

  return (
    <div style={{ padding: "26px 30px" }}>
      {/* Cabecera de institución */}
      <Card style={{ padding: "22px 24px", marginBottom: 20, display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div style={{ width: 48, height: 48, borderRadius: 12, background: color.accent50, color: color.accent, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
          <Icon name="building" size={24} />
        </div>
        <div style={{ lineHeight: 1.3 }}>
          <div style={{ fontSize: 19, fontWeight: 700 }}>{institucion.nombre}</div>
          <div style={{ fontSize: 12.5, color: color.slate400 }}>{institucion.tipo || "Institución"}</div>
        </div>
        <div style={{ flex: 1 }} />
        <button
          onClick={() => navigate("/bandeja")}
          style={{ height: 40, padding: "0 16px", borderRadius: 10, background: color.ink, color: "#fff", fontSize: 13, fontWeight: 600, display: "flex", alignItems: "center", gap: 8, border: "none", cursor: "pointer" }}
        >
          <Icon name="enter" size={15} /> Operar
        </button>
        <Badge tone={institucion.activa === false ? "gray" : "green"}>{institucion.activa === false ? "Inactiva" : "Activa"}</Badge>
      </Card>

      {/* Métricas */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 24 }}>
        {metricas.map((c) => (
          <Card key={c.l} style={{ padding: 18 }}>
            <div style={{ fontSize: 24, fontWeight: 700, lineHeight: 1 }}>{c.n}</div>
            <div style={{ fontSize: 12.5, color: color.slate400, marginTop: 7 }}>{c.l}</div>
          </Card>
        ))}
      </div>

      {/* Secciones de la institución */}
      <div style={{ fontSize: 13, fontWeight: 700, color: color.slate700, marginBottom: 14 }}>Secciones de la institución</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
        {secciones.map((s) => (
          <Card
            key={s.to}
            onClick={() => navigate(s.to)}
            style={{ padding: 20, cursor: "pointer", transition: "border-color .12s, box-shadow .12s" }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = color.accent100; e.currentTarget.style.boxShadow = "0 6px 18px rgba(16,24,40,.08)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = color.border; e.currentTarget.style.boxShadow = "none"; }}
          >
            <div style={{ width: 40, height: 40, borderRadius: 10, background: s.c + "1A", color: s.c, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 12 }}>
              <Icon name={s.icon} size={20} />
            </div>
            <div style={{ fontSize: 14.5, fontWeight: 700 }}>{s.label}</div>
            <div style={{ fontSize: 12.5, color: color.slate400, marginTop: 2 }}>{s.hint}</div>
          </Card>
        ))}
      </div>
    </div>
  );
}
