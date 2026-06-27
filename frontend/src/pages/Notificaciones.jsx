import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { PageHeader } from "../components/Shell";
import { Button, Card, EmptyState, Spinner } from "../components/ui";
import { Icon } from "../components/icons";
import { antiguedad } from "../lib/format";
import { color } from "../theme";

// Historial completo de notificaciones del usuario.
export default function Notificaciones() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [cargando, setCargando] = useState(true);

  async function cargar() {
    setCargando(true);
    try {
      const d = await api.get("/notificaciones/");
      setItems(d.results || d);
    } finally {
      setCargando(false);
    }
  }
  useEffect(() => { cargar(); }, []);

  async function abrir(n) {
    if (!n.leida) await api.post("/notificaciones/leer/", { ids: [n.id] });
    if (n.caso) navigate(`/casos/${n.caso}`);
    else cargar();
  }
  async function marcarTodas() { await api.post("/notificaciones/leer/", {}); cargar(); }

  const hayNoLeidas = items.some((n) => !n.leida);

  return (
    <>
      <PageHeader
        subtitle="Tus avisos: estudios que volvieron, reasignaciones, casos urgentes y cancelaciones."
        right={
          <div style={{ display: "flex", gap: 10 }}>
            {hayNoLeidas && <Button variant="secondary" onClick={marcarTodas}>Marcar todas leídas</Button>}
            <Button variant="secondary" onClick={cargar}>↻ Actualizar</Button>
          </div>
        }
      />
      <div style={{ padding: "22px 32px" }}>
        {cargando && !items.length ? (
          <Spinner label="Cargando notificaciones…" />
        ) : items.length === 0 ? (
          <EmptyState title="No tenés notificaciones" hint="Acá van a aparecer tus avisos a medida que sucedan." />
        ) : (
          <Card style={{ overflow: "hidden" }}>
            {items.map((n, i) => (
              <div key={n.id} onClick={() => abrir(n)}
                style={{ display: "flex", gap: 12, padding: "14px 16px", cursor: "pointer", borderTop: i ? `1px solid ${color.divider}` : "none", background: n.leida ? "#fff" : color.accent50 }}>
                <div style={{ width: 30, height: 30, borderRadius: 8, background: color.subtle, color: color.slate500, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
                  <Icon name="bell" size={15} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600 }}>{n.titulo}</div>
                  {n.detalle && <div style={{ fontSize: 12.5, color: color.slate500 }}>{n.detalle}</div>}
                  <div style={{ fontSize: 11.5, color: color.slate400, marginTop: 2 }}>hace {antiguedad(n.creada)}</div>
                </div>
                {!n.leida && <span style={{ width: 8, height: 8, borderRadius: 99, background: color.accent, flex: "none", marginTop: 6 }} />}
              </div>
            ))}
          </Card>
        )}
      </div>
    </>
  );
}
