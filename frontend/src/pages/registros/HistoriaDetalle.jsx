import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useDetalle, useLista } from "@/api/queries";
import { Icon } from "@/components/icons";
import { Avatar, Badge, Button, Card, Field, Input, Modal, Mono, Tabs, Textarea } from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton, SkeletonTabla } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { useFiltroUrl } from "@/components/ui/filtros";
import { fechaHora } from "@/lib/format";

export default function HistoriaDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  // La pestaña va en la URL: «mirá los estudios de este paciente» es un link.
  const [tab, setTab] = useFiltroUrl("tab", "evolucion");
  const [nuevaAtencion, setNuevaAtencion] = useState(false);

  const paciente = useDetalle("ciudadanos", id);
  // La historia se busca por paciente; puede no existir todavía.
  const historias = useLista("historias-clinicas", { ciudadano: id }, { enabled: !!id });
  const hc = historias.filas[0];

  if (paciente.error) return <EstadoError error={paciente.error} onReintentar={paciente.refetch} />;

  const c = paciente.data;
  const nombre = c ? `${c.nombre} ${c.apellido}`.trim() : "";

  const metricas = [
    { n: hc?.entradas?.length || 0, l: "consultas" },
    { n: hc?.estudios?.length || 0, l: "estudios" },
    { n: (hc?.recetas || []).filter((r) => r.activa).length, l: "recetas activas" },
    {
      n: hc?.entradas?.length
        ? new Date(hc.entradas[0].fecha).toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit" })
        : "—",
      l: "última visita",
    },
  ];

  const TABS = [
    { key: "evolucion", label: "Evolución", cuenta: hc?.entradas?.length },
    { key: "estudios", label: "Estudios", cuenta: hc?.estudios?.length },
    { key: "recetas", label: "Recetas", cuenta: hc?.recetas?.length },
  ];

  return (
    <div className="px-lg py-[22px] sm:px-[30px]">
      <div className="mb-lg flex items-center gap-2.5">
        <button
          onClick={() => navigate("/historia")}
          aria-label="Volver a historias clínicas"
          className="flex size-8 items-center justify-center rounded-md border border-borde bg-superficie text-texto-debil hover:bg-superficie-2"
        >
          <Icon name="back" size={15} />
        </button>
        <div className="text-md text-texto-debil">
          Historias clínicas · <strong className="text-texto-suave">{nombre || "…"}</strong>
        </div>
      </div>

      <Card className="mb-[18px] flex flex-wrap items-center gap-lg px-6 py-5">
        <Avatar nombre={nombre} i={c?.id || 0} size={52} />
        <div className="min-w-0 flex-1">
          <h1 className="text-xxl font-extrabold tracking-tight">
            {c ? nombre : <Skeleton className="h-6 w-52" />}
          </h1>
          <div className="text-base text-texto-debil">
            {c?.documento ? `DNI ${c.documento}` : ""}
            {c?.fecha_nacimiento ? ` · ${new Date(c.fecha_nacimiento).toLocaleDateString("es-AR")}` : ""}
            {c?.obra_social ? ` · ${c.obra_social}` : ""}
          </div>
          {c?.codigo && (
            <div className="mt-2 inline-flex items-center gap-1.5 rounded-md bg-badge-info-bg px-2.5 py-1 text-xs font-semibold text-badge-info-fg">
              <Icon name="enter" size={12} /> Identidad del Legajo ciudadano (externo) · <Mono>{c.codigo}</Mono>
            </div>
          )}
        </div>
        <Button onClick={() => setNuevaAtencion(true)} className="flex items-center gap-2">
          <Icon name="plus" size={15} /> Nueva atención
        </Button>
      </Card>

      {historias.isLoading ? (
        <SkeletonTabla filas={4} columnas={4} />
      ) : (
        <>
          <div className="mb-[22px] grid grid-cols-2 gap-3.5 sm:grid-cols-4">
            {metricas.map((m) => (
              <Card key={m.l} className="p-[18px]">
                <div className="text-cifra-lg font-extrabold leading-none">{m.n}</div>
                <div className="mt-1.5 text-sm text-texto-debil">{m.l}</div>
              </Card>
            ))}
          </div>

          <Tabs tabs={TABS} valor={tab} onChange={setTab} className="mb-5" />

          {/* Los antecedentes bajan debajo del contenido hasta `lg`: en una tablet
              una columna de 280px al lado deja la evolución ilegible. */}
          <div className="grid items-start gap-5 lg:grid-cols-[1fr_17.5rem]">
            <div>
              {tab === "evolucion" && <Evolucion entradas={hc?.entradas || []} />}
              {tab === "estudios" && <Estudios estudios={hc?.estudios || []} />}
              {tab === "recetas" && <Recetas recetas={hc?.recetas || []} />}
            </div>

            <Card className="p-[18px] lg:order-last">
              <h2 className="mb-3 text-xs font-bold tracking-wider text-texto-debil">ANTECEDENTES</h2>
              <Dato
                k="Alergias"
                // Una alergia se marca con color Y con palabra: en una historia
                // clínica confiar sólo en el rojo es un riesgo, no un detalle.
                v={
                  hc?.alergias
                    ? <span className="text-danger">⚠ {hc.alergias}</span>
                    : <span className="text-texto-debil">Sin alergias registradas</span>
                }
              />
              <div className="h-2.5" />
              <Dato k="Condiciones" v={hc?.condiciones || "—"} />
            </Card>
          </div>
        </>
      )}

      {nuevaAtencion && (
        <NuevaAtencionModal ciudadanoId={id} hcId={hc?.id} onClose={() => setNuevaAtencion(false)} />
      )}
    </div>
  );
}

function NuevaAtencionModal({ ciudadanoId, hcId, onClose }) {
  const toast = useToast();
  const [titulo, setTitulo] = useState("");
  const [contenido, setContenido] = useState("");
  const [firmada, setFirmada] = useState(true);

  const guardar = useAccion(
    async () => {
      // El paciente puede no tener historia todavía: se crea al vuelo.
      let historia = hcId;
      if (!historia) {
        const hc = await api.post("/historias-clinicas/", { ciudadano: ciudadanoId });
        historia = hc.id;
      }
      return api.post("/entradas-historia/", { historia, titulo, contenido, firmada });
    },
    {
      onSuccess: () => { toast.ok("Atención registrada."); onClose(); },
      // Firmar exige matrícula (regla del motor): el error del backend explica
      // exactamente eso, así que se muestra tal cual en vez de uno genérico.
      onError: (e) => toast.deError(e, "No se pudo registrar la atención."),
    },
  );

  return (
    <Modal
      title="Nueva atención"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardar.isPending || !titulo} onClick={() => guardar.mutate()}>
            {guardar.isPending ? "Registrando…" : "Registrar atención"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Título *">
          <Input value={titulo} onChange={(e) => setTitulo(e.target.value)} autoFocus placeholder="Evaluación inicial, Control…" />
        </Field>
        <Field label="Evolución / observaciones">
          <Textarea value={contenido} onChange={(e) => setContenido(e.target.value)} />
        </Field>
        <label className="flex cursor-pointer items-center gap-2.5 text-md text-texto-medio">
          <input type="checkbox" checked={firmada} onChange={(e) => setFirmada(e.target.checked)} /> Firmar la entrada
        </label>
      </div>
    </Modal>
  );
}

function Dato({ k, v }) {
  return (
    <div>
      <div className="mb-0.5 text-sm text-texto-debil">{k}</div>
      <div className="text-md font-semibold">{v}</div>
    </div>
  );
}

function Evolucion({ entradas }) {
  if (!entradas.length) {
    return <EstadoVacio titulo="Sin entradas de evolución" detalle="Registrá una atención para empezar la historia." />;
  }
  return (
    <div className="flex flex-col gap-3">
      {entradas.map((e) => (
        <Card key={e.id} className="p-[18px]">
          <div className="mb-1.5 flex items-center justify-between gap-3">
            <h3 className="text-md font-bold">{e.titulo}</h3>
            {e.firmada && <Badge tone="green">Firmada</Badge>}
          </div>
          {e.contenido && <div className="mb-2 text-md text-texto-medio">{e.contenido}</div>}
          <div className="text-xs text-texto-debil">
            {fechaHora(e.fecha)}
            {e.autor_nombre ? ` · ${e.autor_nombre}` : ""}
            {e.matricula ? ` · M.N. ${e.matricula}` : ""}
          </div>
        </Card>
      ))}
    </div>
  );
}

function Estudios({ estudios }) {
  if (!estudios.length) return <EstadoVacio titulo="Sin estudios" detalle="Los estudios se cargan desde el flujo de diagnóstico." />;
  return (
    <div className="flex flex-col gap-2.5">
      {estudios.map((s) => (
        <Card key={s.id} className="flex flex-wrap items-center justify-between gap-3 px-[18px] py-3.5">
          <div className="min-w-0">
            <div className="text-md font-semibold">{s.tipo}</div>
            <div className="text-sm text-texto-debil">
              {s.fecha} · {s.autor || "—"} {s.archivo && <Mono className="ml-1.5">{s.archivo}</Mono>}
            </div>
          </div>
          {s.resultado && (
            <Badge tone={s.resultado === "normal" ? "green" : "amber"}>{s.resultado_display}</Badge>
          )}
        </Card>
      ))}
    </div>
  );
}

function Recetas({ recetas }) {
  if (!recetas.length) return <EstadoVacio titulo="Sin recetas" detalle="Las recetas se emiten durante la atención." />;
  return (
    <div className="flex flex-col gap-2.5">
      {recetas.map((r) => (
        <Card key={r.id} className="flex flex-wrap items-center justify-between gap-3 px-[18px] py-3.5">
          <div className="min-w-0">
            <div className="text-md text-texto-medio">{r.detalle}</div>
            <div className="text-sm text-texto-debil">{r.fecha}</div>
          </div>
          <Badge tone={r.activa ? "green" : "gray"}>{r.activa ? "Activa" : "Inactiva"}</Badge>
        </Card>
      ))}
    </div>
  );
}
