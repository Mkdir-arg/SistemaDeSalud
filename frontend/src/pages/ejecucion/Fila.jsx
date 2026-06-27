import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { Badge, Card, EmptyState, Mono, Select, Spinner } from "../../components/ui";
import { Icon } from "../../components/icons";
import { antiguedad, casoId } from "../../lib/format";
import { color, nodeCat } from "../../theme";

const TEAL = nodeCat.espera.sol; // #16B1C9

export default function Fila() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [boxes, setBoxes] = useState([]);
  const [areaSel, setAreaSel] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [llamando, setLlamando] = useState(null); // id de box (o "global") en proceso
  const [error, setError] = useState("");

  async function cargarItems() {
    const data = await api.get("/items-fila/?atendido=false");
    const lista = data.results || data;
    lista.sort((a, b) => (b.urgente ? 1 : 0) - (a.urgente ? 1 : 0) || a.orden - b.orden);
    setItems(lista);
  }
  useEffect(() => {
    (async () => {
      setCargando(true);
      try {
        await cargarItems();
      } finally {
        setCargando(false);
      }
    })();
  }, []);

  // Áreas que tienen gente esperando.
  const areas = useMemo(() => {
    const m = {};
    items.forEach((it) => { if (it.area) m[it.area] = it.area_nombre || `Área ${it.area}`; });
    return Object.entries(m).map(([id, nombre]) => ({ id: Number(id), nombre }));
  }, [items]);

  // Elegir un área por defecto cuando aparecen items.
  useEffect(() => {
    if (areas.length && !areas.some((a) => a.id === areaSel)) setAreaSel(areas[0].id);
  }, [areas, areaSel]);

  // Boxes del área elegida.
  useEffect(() => {
    if (areaSel == null) { setBoxes([]); return; }
    api.get(`/boxes/?area=${areaSel}&activo=true`).then((d) => setBoxes(d.results || d));
  }, [areaSel]);

  // En la fila solo los que aún no fueron llamados (sin box asignado).
  const fila = items.filter((it) => it.area === areaSel && !it.box);
  const areaNombre = areas.find((a) => a.id === areaSel)?.nombre || "Sala de espera";

  async function llamar(box) {
    if (!fila.length) return;
    const casoId = fila[0].caso;
    setError("");
    setLlamando(box ? box.id : "global");
    try {
      await api.post(`/casos/${casoId}/llamar/`, box ? { box_id: box.id } : {});
      navigate(`/casos/${casoId}`); // el profesional pasa a atender al paciente llamado
    } catch (e) {
      setError(e?.data?.detail || "No se pudo llamar al paciente.");
      setLlamando(null);
    }
  }

  if (cargando) return <Spinner label="Cargando fila…" />;

  return (
    <div style={{ padding: "26px 30px" }}>
      {/* Cabecera */}
      <Card style={{ padding: "18px 22px", marginBottom: 18, display: "flex", alignItems: "center", gap: 16 }}>
        <div style={{ width: 46, height: 46, borderRadius: 12, background: nodeCat.espera.tint, color: TEAL, display: "flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
          <Icon name="list" size={22} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Fila de espera</div>
          <div style={{ fontSize: 12.5, color: color.slate500 }}>FIFO + urgencia · se llama desde cada box</div>
        </div>
        {areas.length > 1 && (
          <Select value={areaSel ?? ""} onChange={(e) => setAreaSel(Number(e.target.value))} style={{ width: "auto", height: 38 }}>
            {areas.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
          </Select>
        )}
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 22, fontWeight: 800, lineHeight: 1 }}>{fila.length}</div>
          <div style={{ fontSize: 11.5, color: color.slate400 }}>en {areaNombre}</div>
        </div>
      </Card>

      {error && (
        <div style={{ fontSize: 13, color: "#B42318", background: "#FCEBEB", padding: "10px 14px", borderRadius: 9, marginBottom: 16 }}>{error}</div>
      )}

      {/* Boxes: cada uno llama al siguiente */}
      <Card style={{ padding: "16px 20px", marginBottom: 18 }}>
        <div style={{ fontSize: 12.5, fontWeight: 700, color: color.slate600, marginBottom: 12 }}>Consultorios</div>
        {boxes.length === 0 ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
            <span style={{ fontSize: 12.5, color: color.slate400 }}>
              Esta área no tiene boxes configurados. Cargalos en Estructura → área → Boxes.
            </span>
            <BotonLlamar label="Llamar al siguiente" disabled={!fila.length || !!llamando} cargando={llamando === "global"} onClick={() => llamar(null)} />
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 10 }}>
            {boxes.map((b) => (
              <div key={b.id} style={{ border: `1px solid ${color.border}`, borderRadius: 11, padding: "12px 14px", display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, fontWeight: 700 }}>
                  <Icon name="enter" size={15} style={{ color: TEAL }} /> {b.nombre}
                </div>
                <BotonLlamar label="Llamar siguiente" disabled={!fila.length || !!llamando} cargando={llamando === b.id} onClick={() => llamar(b)} />
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Lista de espera */}
      <Card style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ fontSize: 15, fontWeight: 700, padding: "16px 20px" }}>En espera</div>
        {fila.length === 0 ? (
          <EmptyState title="La fila está vacía" hint="No hay pacientes esperando en esta área." />
        ) : (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "44px 90px 1fr 90px 90px", gap: 12, padding: "10px 20px", background: color.subtle, borderTop: `1px solid ${color.divider}`, fontSize: 11, fontWeight: 700, letterSpacing: ".5px", color: color.slate400 }}>
              <div /><div>TURNO</div><div>PERSONA</div><div>INGRESO</div><div>ESPERA</div>
            </div>
            {fila.map((it, i) => (
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
                <span style={{ fontSize: 13, color: color.slate500 }}>{new Date(it.ingreso).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" })}</span>
                <span style={{ fontSize: 13, color: color.slate500 }}>{antiguedad(it.ingreso)}</span>
              </div>
            ))}
          </>
        )}
      </Card>
    </div>
  );
}

function BotonLlamar({ label, disabled, cargando, onClick }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{ height: 36, padding: "0 14px", borderRadius: 9, background: disabled ? "#EEF0F3" : TEAL, color: disabled ? color.slate400 : "#fff", fontSize: 13, fontWeight: 600, border: "none", cursor: disabled ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 7 }}
    >
      <Icon name="enter" size={14} /> {cargando ? "Llamando…" : label}
    </button>
  );
}
