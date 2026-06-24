import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useInstitucion } from "../../auth/InstitutionContext";
import { PageHeader } from "../../components/Shell";
import { Badge, Spinner } from "../../components/ui";
import { color, estadoVersion } from "../../theme";

// Mapa panorámico de los flujos de la institución sobre un lienzo con grilla.
export default function MapaFlujos() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const [flujos, setFlujos] = useState([]);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    if (!institucion) return;
    (async () => {
      try {
        const d = await api.get(`/flujos/?institucion=${institucion.id}`);
        setFlujos(d.results || d);
      } finally {
        setCargando(false);
      }
    })();
  }, [institucion]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: "20px 30px 14px" }}>
        <div style={{ fontSize: 16, fontWeight: 700 }}>Cómo se encadenan los procesos</div>
        <div style={{ fontSize: 13, color: color.slate500, marginTop: 3, maxWidth: 640 }}>
          Cada bloque es un flujo; las flechas son derivaciones entre flujos. Hacé clic en un bloque para abrirlo en el diseñador.
        </div>
      </div>
      <div style={{ flex: 1, overflow: "auto", background: "#FBFBFD", backgroundImage: "radial-gradient(circle, #D9DDE5 1.1px, transparent 1.1px)", backgroundSize: "20px 20px", padding: 32 }}>
        {cargando ? (
          <Spinner />
        ) : flujos.length === 0 ? (
          <div style={{ fontSize: 14, color: color.slate400 }}>No hay flujos en esta institución.</div>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 22 }}>
            {flujos.map((f) => {
              const pub = (f.versiones || []).find((v) => v.estado === "publicada");
              const v = pub || (f.versiones || [])[0];
              const est = v ? estadoVersion[v.estado] : null;
              return (
                <div
                  key={f.id}
                  onClick={() => navigate(`/flujos/${f.id}`)}
                  style={{ width: 240, background: "#fff", border: `1px solid ${color.border}`, borderRadius: 14, padding: "16px 18px", cursor: "pointer", boxShadow: "0 1px 3px rgba(16,24,40,.07)" }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10, marginBottom: 10 }}>
                    <div style={{ fontSize: 15, fontWeight: 700 }}>{f.titulo}</div>
                    {est && <Badge tone={est.tone}>{est.label}</Badge>}
                  </div>
                  <div style={{ fontSize: 12.5, color: color.slate500 }}>
                    {(f.versiones || []).length} versión(es){v ? ` · ${v.etiqueta}` : ""}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
