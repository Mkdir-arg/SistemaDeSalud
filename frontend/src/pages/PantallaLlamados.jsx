import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { LogoFull } from "@/components/Logo";

/**
 * Pantalla pública de llamados: la TV de la sala de espera.
 *
 * La pantalla comparte la paleta HEN, pero conserva su layout de cartel:
 *
 *   · Siempre se ve en claro, independientemente del tema del puesto.
 *   · Su tipografía se mide en `vw`/`vh` porque tiene que leerse igual en un
 *     monitor de 24" y en una TV de 55". Eso no son breakpoints: es escalado
 *     continuo, y expresarlo con clases arbitrarias (`text-[4.4vw]`) sería el
 *     mismo estilo inline con más ruido.
 *   · Comparte la marca HEN y sus tokens de color con el resto de la app.
 *
 * Lo que sí se migró: la capa de datos (TanStack Query) y la accesibilidad.
 * ────────────────────────────────────────────────────────────────────────────
 */
export default function PantallaLlamados() {
  const { token } = useParams();
  const [sonido, setSonido] = useState(false);
  const [ahora, setAhora] = useState(() => new Date());
  const [flash, setFlash] = useState(false);
  const ultimaClave = useRef(null);

  const q = useQuery({
    queryKey: ["pantalla", token],
    queryFn: () => api.get(`/pantalla/${token}/`),
    refetchInterval: 3000,
    // La TV queda encendida y desatendida: tiene que seguir refrescando aunque
    // el navegador considere la pestaña en segundo plano.
    refetchIntervalInBackground: true,
    retry: (n, e) => e?.status !== 404 && n < 3,
  });
  const data = q.data;

  // Reloj de la cabecera.
  useEffect(() => {
    const id = setInterval(() => setAhora(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const beep = useCallback(() => {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      const ctx = new Ctx();
      [880, 1175].forEach((f, i) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.frequency.value = f;
        osc.type = "sine";
        osc.connect(gain);
        gain.connect(ctx.destination);
        const t = ctx.currentTime + i * 0.35;
        gain.gain.setValueAtTime(0.0001, t);
        gain.gain.exponentialRampToValueAtTime(0.4, t + 0.05);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.3);
        osc.start(t);
        osc.stop(t + 0.32);
      });
    } catch {
      /* el navegador puede bloquear el audio hasta que haya una interacción */
    }
  }, []);

  // Destello + timbre cuando cambia el llamado. La clave incluye las veces
  // llamado: un rellamado al MISMO paciente también tiene que avisar.
  const top = data?.llamados?.[0];
  const clave = top ? `${top.id}:${top.veces ?? 1}` : null;
  useEffect(() => {
    if (clave === null) return;
    if (ultimaClave.current !== null && clave !== ultimaClave.current) {
      setFlash(true);
      const id = setTimeout(() => setFlash(false), 2800);
      if (sonido) beep();
      ultimaClave.current = clave;
      return () => clearTimeout(id);
    }
    ultimaClave.current = clave;
  }, [clave, sonido, beep]);

  const error = q.error
    ? q.error.status === 404
      ? "Pantalla no encontrada. Verificá el enlace."
      : "Sin conexión con el servidor."
    : "";

  const actual = data?.llamados?.[0] || null;
  const anteriores = (data?.llamados || []).slice(1, 7);
  const hora = ahora.toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" });
  const fecha = ahora.toLocaleDateString("es-AR", { weekday: "long", day: "numeric", month: "long" });

  return (
    <div style={S.root}>
      <header style={S.header}>
        <LogoFull size={52} />
        <div style={S.headCentro}>
          <div style={S.headNodo}>{data?.nodo?.titulo || "Llamados"}</div>
          <div style={S.headArea}>{data?.area_nombre || data?.flujo_titulo || ""}</div>
        </div>
        <div style={S.reloj}>
          <div style={S.relojHora}>{hora}</div>
          <div style={S.relojFecha}>{fecha}</div>
        </div>
        <button
          onClick={() => setSonido((s) => !s)}
          style={S.sonidoBtn(sonido)}
          // El botón es un emoji: sin nombre accesible no se puede saber qué hace
          // ni en qué estado está.
          aria-pressed={sonido}
          aria-label={sonido ? "Desactivar el timbre al llamar" : "Activar el timbre al llamar"}
          title={sonido ? "Timbre activado" : "Timbre desactivado"}
        >
          <span aria-hidden="true">{sonido ? "🔔" : "🔕"}</span>
        </button>
      </header>

      <div style={S.body}>
        <aside style={S.aside}>
          <ArteMedico />
          <div style={S.asideFoot}>
            <div style={S.asideLbl}>SALA</div>
            <div style={S.asideArea}>{data?.area_nombre || "Espera"}</div>
            {typeof data?.en_espera === "number" && (
              <div style={S.esperaChip}>
                <span style={S.esperaNum}>{data.en_espera}</span> en espera
              </div>
            )}
          </div>
        </aside>

        <main style={S.tabla}>
          {error ? (
            <div style={S.estado}><div style={S.error} role="alert">{error}</div></div>
          ) : q.isLoading ? (
            <div style={S.estado}><div style={S.idle}>Conectando…</div></div>
          ) : !actual ? (
            <div style={S.estado}>
              <div style={S.idle}>Aguarde a ser llamado</div>
              <div style={S.idleSub}>Los llamados aparecerán aquí</div>
            </div>
          ) : (
            <>
              <div style={S.thead}>
                <div>Paciente</div>
                <div style={{ textAlign: "right" }}>Consultorio</div>
              </div>

              {/* `aria-live`: si alguien mira la sala con un lector de pantalla,
                  el llamado nuevo se anuncia solo. */}
              <div style={{ ...S.actual, ...(flash ? S.actualFlash : null) }} aria-live="assertive" aria-atomic="true">
                <div style={S.actualBar} />
                <div style={S.actualInfo}>
                  <div style={S.actualEtq}>
                    {actual.urgente ? "URGENTE" : "LLAMANDO"}
                    {actual.veces > 1 && <span style={S.veces}>· {actual.veces}º llamado</span>}
                  </div>
                  <div style={S.actualNombre(actual.persona || actual.ticket || "")}>
                    {actual.persona || actual.ticket}
                  </div>
                </div>
                <div style={S.actualBox}>{actual.box || "—"}</div>
              </div>

              {anteriores.map((it, i) => (
                <div key={it.id} style={{ ...S.fila, background: i % 2 ? "var(--color-superficie-2)" : "var(--color-superficie)" }}>
                  <div style={S.filaNombre}>{it.persona || it.ticket}</div>
                  <div style={S.filaBox}>{it.box || "—"}</div>
                </div>
              ))}
            </>
          )}
        </main>
      </div>
    </div>
  );
}

/** Ilustración médica (SVG inline, sin assets externos). */
function ArteMedico() {
  return (
    <svg viewBox="0 0 360 360" style={S.arte} aria-hidden="true">
      <defs>
        <linearGradient id="disco" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--color-acento-aqua)" />
          <stop offset="1" stopColor="var(--color-brand-teal)" />
        </linearGradient>
      </defs>
      {[[40, 60], [300, 50], [60, 290], [310, 300], [330, 170]].map(([x, y], i) => (
        <g key={i} transform={`translate(${x} ${y})`} opacity="0.35">
          <rect x="-5" y="-16" width="10" height="32" rx="4" fill="var(--color-acento-aqua)" />
          <rect x="-16" y="-5" width="32" height="10" rx="4" fill="var(--color-acento-aqua)" />
        </g>
      ))}
      <circle cx="180" cy="180" r="105" fill="url(#disco)" />
      <circle cx="180" cy="180" r="105" fill="none" stroke="#fff" strokeOpacity="0.5" strokeWidth="3" />
      <path
        d="M95 182 H140 L152 150 L170 214 L188 160 L200 182 H265"
        fill="none" stroke="#fff" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round"
      />
    </svg>
  );
}

// La llamada mantiene el ámbar semántico; el resto usa los tokens HEN.
const TEAL = "var(--color-brand-teal)";
const NARANJA = "var(--color-badge-amber-fg)";
const INK = "var(--color-texto)";
const MUTE = "var(--color-texto-suave)";

const S = {
  root: { position: "fixed", inset: 0, background: "var(--color-fondo)", color: INK, display: "flex", flexDirection: "column", fontFamily: "var(--font-sans)", overflow: "hidden" },

  header: { display: "flex", alignItems: "center", gap: "2vw", height: "13vh", padding: "0 2.5vw", background: "var(--color-superficie)", borderBottom: `2px solid ${TEAL}` },
  headCentro: { flex: 1, textAlign: "center", minWidth: 0 },
  headNodo: { fontSize: "2.4vw", fontWeight: 800, lineHeight: 1.05, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" },
  headArea: { fontSize: "1.2vw", color: MUTE, fontWeight: 600, marginTop: "0.4vh" },
  reloj: { textAlign: "right", flex: "none" },
  relojHora: { fontSize: "2.4vw", fontWeight: 800, lineHeight: 1, color: TEAL },
  relojFecha: { fontSize: "0.95vw", color: MUTE, textTransform: "capitalize", marginTop: "0.5vh" },
  sonidoBtn: (on) => ({ flex: "none", width: "3.4vw", height: "3.4vw", borderRadius: "50%", border: `1px solid ${on ? TEAL : "var(--color-borde)"}`, background: on ? "var(--color-accent-50)" : "var(--color-superficie)", cursor: "pointer", fontSize: "1.4vw" }),

  body: { flex: 1, display: "flex", minHeight: 0 },

  aside: { width: "34%", position: "relative", background: "linear-gradient(160deg, var(--color-accent-50), color-mix(in srgb, var(--color-acento-aqua) 12%, white))", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", borderRight: `1px solid var(--color-borde)` },
  arte: { width: "70%", maxWidth: "70%" },
  asideFoot: { position: "absolute", bottom: "4vh", left: 0, right: 0, textAlign: "center" },
  asideLbl: { fontSize: "1vw", letterSpacing: "3px", color: TEAL, fontWeight: 700 },
  asideArea: { fontSize: "2.6vw", fontWeight: 800, color: TEAL, lineHeight: 1.05, marginTop: "0.6vh" },
  esperaChip: { marginTop: "1.6vh", display: "inline-block", background: "var(--color-superficie)", borderRadius: "999px", padding: "0.8vh 1.4vw", fontSize: "1.1vw", color: MUTE, fontWeight: 600, boxShadow: "0 2px 8px rgba(20,60,80,.08)" },
  esperaNum: { color: TEAL, fontWeight: 800, fontSize: "1.5vw", marginRight: "0.4vw" },

  tabla: { flex: 1, display: "flex", flexDirection: "column", padding: "2.5vh 2.5vw", minWidth: 0 },
  thead: { display: "grid", gridTemplateColumns: "1fr auto", padding: "0 1.5vw 1.2vh", fontSize: "1.1vw", fontWeight: 700, letterSpacing: "1.5px", textTransform: "uppercase", color: MUTE, borderBottom: `3px solid ${TEAL}` },

  actual: { display: "flex", alignItems: "center", gap: "1.5vw", position: "relative", background: "var(--color-badge-amber-bg)", borderRadius: "14px", padding: "2.4vh 1.8vw", margin: "1.6vh 0", overflow: "hidden", boxShadow: "0 6px 20px rgba(180,105,14,.18)", transition: "box-shadow .4s" },
  actualFlash: { boxShadow: `0 0 0 4px ${NARANJA}, 0 6px 24px rgba(180,105,14,.4)` },
  actualBar: { position: "absolute", left: 0, top: 0, bottom: 0, width: "8px", background: NARANJA },
  actualInfo: { flex: 1, minWidth: 0 },
  actualEtq: { fontSize: "1.2vw", fontWeight: 800, letterSpacing: "2px", color: NARANJA },
  veces: { marginLeft: "0.6vw", color: "var(--color-badge-error-fg)", letterSpacing: "1px" },
  // El nombre encoge según su largo. En un cartel de sala el nombre ES la
  // información: recortarlo con «…» (como pasaba con «RUBÉN QU…») es el peor
  // fallo posible de esta pantalla, así que antes se achica la tipografía.
  actualNombre: (n) => ({
    fontSize: n.length > 26 ? "2.5vw" : n.length > 20 ? "3vw" : n.length > 15 ? "3.6vw" : "4.4vw",
    fontWeight: 900, lineHeight: 1.05, textTransform: "uppercase", color: INK,
    overflowWrap: "anywhere",
  }),
  // El consultorio cede espacio al nombre: se lee igual con menos cuerpo porque
  // es una palabra conocida y corta.
  actualBox: { flex: "none", fontSize: "2.4vw", fontWeight: 900, color: "#fff", background: NARANJA, borderRadius: "12px", padding: "1vh 1.4vw", minWidth: "6vw", textAlign: "center", whiteSpace: "nowrap" },

  fila: { display: "grid", gridTemplateColumns: "1fr auto", alignItems: "center", padding: "1.7vh 1.5vw", borderRadius: "10px" },
  filaNombre: { fontSize: "2.3vw", fontWeight: 700, color: INK, textTransform: "uppercase", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" },
  filaBox: { fontSize: "2.1vw", fontWeight: 800, color: TEAL, textAlign: "right" },

  estado: { flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", textAlign: "center" },
  // Estado de espera: es lo que se ve la mayor parte del tiempo en la sala.
  //
  // Las dos líneas se leen a distancia; los colores HEN se medirán en el TV real.
  idle: { fontSize: "3.4vw", fontWeight: 800, color: INK },
  idleSub: { fontSize: "1.4vw", color: MUTE, marginTop: "1.5vh" },
  error: { fontSize: "1.9vw", color: "var(--color-badge-error-fg)", fontWeight: 700 },
};
