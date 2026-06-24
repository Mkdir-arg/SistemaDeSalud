import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { Badge, Card, EmptyState, Mono, Spinner } from "../../components/ui";
import { Icon } from "../../components/icons";
import { antiguedad, casoId } from "../../lib/format";
import { color, nodeCat } from "../../theme";

const TEAL = nodeCat.espera.sol; // #16B1C9

export default function Fila() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [llamando, setLlamando] = useState(false);

  async function cargar() {
    setCargando(true);
    try {
      const data = await api.get("/items-fila/?atendido=false");
      const lista = data.results || data;
      lista.sort((a, b) => (b.urgente ? 1 : 0) - (a.urgente ? 1 : 0) || a.orden - b.orden);
      setItems(lista);
    } finally {
      setCargando(false);
    }
  }
  useEffect(() => {
    cargar();
  }, []);

  async function llamarSiguiente() {
    if (!items.length) return;
    setLlamando(true);
    try {
      await api.post(`/casos/${items[0].caso}/avanzar/`, {});
      await cargar();
    } finally {
      setLlamando(false);
    }
  }

  const filaNombre = items[0]?.nodo_titulo || "Sala de espera";

  return (
    <div style={{ padding: "26px 30px", maxWidth: 920 }}>
      {/* Cabecera de la fila */}
      <Card style={{ padding: "18px 22px", marginBottom: 18, display: "flex", alignItems: "center", gap: 16 }}>
        <div style={{ width: 46, height: 46, borderRadius: 12, background: nodeCat.espera.tint, color: TEAL, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
          <Icon name="list" size={22} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 18, fontWeight: 700 }}>{filaNombre}</div>
          <div style={{ fontSize: 12.5, color: color.slate500 }}>Fila del flujo · FIFO + urgencia</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 22, fontWeight: 800, lineHeight: 1 }}>{items.length}</div>
          <div style={{ fontSize: 11.5, color: color.slate400 }}>en espera</div>
        </div>
      </Card>

      <Card style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "16px 20px" }}>
          <div style={{ fontSize: 15, fontWeight: 700 }}>En espera</div>
          <button
            onClick={llamarSiguiente}
            disabled={!items.length || llamando}
            style={{ height: 38, padding: "0 16px", borderRadius: 9, background: items.length ? TEAL : "#EEF0F3", color: items.length ? "#fff" : color.slate400, fontSize: 13.5, fontWeight: 600, border: "none", cursor: items.length ? "pointer" : "not-allowed", display: "flex", alignItems: "center", gap: 8 }}
          >
            <Icon name="enter" size={15} /> {llamando ? "Llamando…" : "Llamar al siguiente"}
          </button>
        </div>

        {cargando ? (
          <Spinner />
        ) : items.length === 0 ? (
          <EmptyState title="La fila está vacía" hint="No hay casos esperando ser llamados." />
        ) : (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "44px 90px 1fr 90px 90px", gap: 12, padding: "10px 20px", background: color.subtle, borderTop: `1px solid ${color.divider}`, fontSize: 11, fontWeight: 700, letterSpacing: ".5px", color: color.slate400 }}>
              <div /><div>TURNO</div><div>PERSONA</div><div>INGRESO</div><div>ESPERA</div>
            </div>
            {items.map((it, i) => (
              <div
                key={it.id}
                onClick={() => navigate(`/casos/${it.caso}`)}
                style={{ display: "grid", gridTemplateColumns: "44px 90px 1fr 90px 90px", gap: 12, alignItems: "center", padding: "14px 20px", cursor: "pointer", borderTop: `1px solid ${color.divider}`, background: i === 0 ? color.accent50 : "#fff", boxShadow: i === 0 ? `inset 3px 0 0 ${color.accent}` : "none" }}
              >
                <span style={{ width: 26, height: 26, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700, background: i === 0 ? color.accent : "#EEF0F3", color: i === 0 ? "#fff" : color.slate500 }}>{i + 1}</span>
                <Mono style={{ fontWeight: 700 }}>{it.turno || casoId(it.caso)}</Mono>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 13.5, color: color.slate700 }}>{it.persona || casoId(it.caso)}</span>
                  {it.urgente && <Badge tone="error">urgente</Badge>}
                </div>
                <span style={{ fontSize: 13, color: color.slate500, fontFamily: "inherit" }}>{new Date(it.ingreso).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" })}</span>
                <span style={{ fontSize: 13, color: color.slate500 }}>{antiguedad(it.ingreso)}</span>
              </div>
            ))}
          </>
        )}
      </Card>
    </div>
  );
}
