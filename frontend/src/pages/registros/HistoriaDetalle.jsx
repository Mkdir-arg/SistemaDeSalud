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
    // «Quién la miró» es un derecho del paciente, no una herramienta de
    // auditoría interna: va acá, en su historia, donde se lo puede contestar
    // en el momento en que lo pregunta.
    { key: "accesos", label: "Quién la miró" },
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
              {tab === "accesos" && <Accesos ciudadanoId={id} />}
            </div>

            <div className="flex flex-col gap-3.5 lg:order-last">
              <Card className="p-[18px]">
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

              <Consentimiento ciudadanoId={id} estado={c?.consentimiento} />
              {hc && <Integridad hcId={hc.id} />}
            </div>
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

/*
 * Consentimiento para el tratamiento de datos (Ley 25.326).
 *
 * Se agrega, nunca se edita: revocar es un registro nuevo. Lo que vale ante un
 * reclamo es qué se consintió y cuándo, no el estado de hoy.
 */
function Consentimiento({ ciudadanoId, estado }) {
  const toast = useToast();
  const [pidiendo, setPidiendo] = useState(null); // "otorgar" | "revocar"

  // Sin registro NO es lo mismo que revocado, y mostrarlos igual haría creer
  // que el paciente dijo que no.
  const sinRegistro = estado == null;

  return (
    <Card className="p-[18px]">
      <h2 className="mb-3 text-xs font-bold tracking-wider text-texto-debil">
        CONSENTIMIENTO DE DATOS
      </h2>

      {sinRegistro ? (
        <div className="text-md text-texto-debil">
          Sin registro.{" "}
          <span className="text-texto-medio">
            No consta que se haya pedido; no es lo mismo que una negativa.
          </span>
        </div>
      ) : (
        <>
          <Badge tone={estado.otorgado ? "green" : "amber"}>
            {estado.otorgado ? "Otorgado" : "Revocado"}
          </Badge>
          <div className="mt-2 text-sm text-texto-debil">
            {fechaHora(estado.momento)}
            {estado.modo ? ` · ${MODO[estado.modo] || estado.modo}` : ""}
          </div>
          {estado.alcance && <div className="mt-1 text-sm text-texto-medio">{estado.alcance}</div>}
        </>
      )}

      <div className="mt-3.5 flex gap-2">
        {(sinRegistro || !estado.otorgado) && (
          <Button className="text-sm" onClick={() => setPidiendo("otorgar")}>Registrar consentimiento</Button>
        )}
        {!sinRegistro && estado.otorgado && (
          <Button variant="secondary" className="text-sm" onClick={() => setPidiendo("revocar")}>
            Registrar revocación
          </Button>
        )}
      </div>

      {/* La urgencia no depende de esto y decirlo importa: sin la aclaración,
          un «revocado» en pantalla invita a dudar antes de atender. */}
      <div className="mt-3 text-xs text-texto-debil">
        La atención de urgencia no depende del consentimiento. Acá se deja constancia,
        no se bloquea nada.
      </div>

      {pidiendo && (
        <ConsentimientoModal
          ciudadanoId={ciudadanoId}
          otorgar={pidiendo === "otorgar"}
          onClose={() => setPidiendo(null)}
          onListo={() => { toast.ok("Registrado."); setPidiendo(null); }}
        />
      )}
    </Card>
  );
}

/*
 * Tiene que coincidir con `ConsentimientoDatos.Modo` del backend.
 *
 * Acá decía «electronico», que no existe: el alta devolvía 400 y un
 * consentimiento guardado como «digital» se mostraba con el valor crudo. Una
 * lista de opciones duplicada de este lado se desincroniza sin que nada avise,
 * así que hay un test que manda cada opción del selector contra la API.
 */
const MODO = { escrito: "Escrito", verbal: "Verbal", digital: "Digital" };

function ConsentimientoModal({ ciudadanoId, otorgar, onClose, onListo }) {
  const toast = useToast();
  const [modo, setModo] = useState("escrito");
  const [alcance, setAlcance] = useState("");

  const guardar = useAccion(
    () => api.post("/consentimientos/", {
      ciudadano: ciudadanoId, otorgado: otorgar, modo, alcance,
    }),
    {
      // El detalle del paciente lo trae derivado del último registro.
      invalida: ["lista", "detalle"],
      onSuccess: onListo,
      onError: (e) => toast.deError(e, "No se pudo registrar."),
    },
  );

  return (
    <Modal
      title={otorgar ? "Registrar consentimiento" : "Registrar revocación"}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardar.isPending} onClick={() => guardar.mutate()}>
            {guardar.isPending ? "Registrando…" : "Registrar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Cómo se tomó">
          <select
            value={modo}
            onChange={(e) => setModo(e.target.value)}
            className="h-9 w-full rounded-md border border-campo-borde bg-superficie px-2.5 text-md text-texto-medio"
          >
            {Object.entries(MODO).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Field>
        <Field label="Alcance / observaciones">
          <Textarea
            value={alcance}
            onChange={(e) => setAlcance(e.target.value)}
            placeholder={otorgar ? "Atención y tratamiento de datos de salud" : "Motivo de la revocación"}
          />
        </Field>
        <div className="text-sm text-texto-debil">
          {/* Que quede claro antes de guardar, no después: acá no hay deshacer. */}
          Queda como registro nuevo, con la fecha y quién lo tomó. No reemplaza ni borra
          los anteriores.
        </div>
      </div>
    </Modal>
  );
}

/*
 * Verificación de integridad de la historia.
 *
 * Sin esto, «está firmada» es una afirmación que nadie puede comprobar: alguien
 * con acceso a la base podía editar una atención de hace dos años sin dejar
 * rastro. Se dispara a pedido porque es lo que se hace antes de presentar la
 * historia ante un reclamo, no en cada visita.
 */
function Integridad({ hcId }) {
  const [verificar, setVerificar] = useState(false);
  // `useDetalle` arma `/historias-clinicas/<id>/verificar/`, que es la acción
  // del backend.
  const q = useDetalle("historias-clinicas", verificar ? `${hcId}/verificar` : null);

  return (
    <Card className="p-[18px]">
      <h2 className="mb-3 text-xs font-bold tracking-wider text-texto-debil">INTEGRIDAD</h2>

      {!verificar && (
        <>
          <div className="mb-3 text-md text-texto-medio">
            Comprueba que ninguna atención firmada haya cambiado después de firmarse.
          </div>
          <Button variant="secondary" className="text-sm" onClick={() => setVerificar(true)}>
            Verificar la historia
          </Button>
        </>
      )}

      {verificar && q.isLoading && <div className="text-md text-texto-debil">Verificando…</div>}

      {verificar && q.error && (
        <div className="text-md text-danger">No se pudo verificar. Probá de nuevo.</div>
      )}

      {q.data && <Resultado r={q.data} />}
    </Card>
  );
}

/*
 * El resultado de verificar, dicho sin prometer de más.
 *
 * `ok` del backend significa «no se encontraron problemas», y sin entradas
 * selladas no se puede encontrar ninguno: la primera versión de este panel
 * mostraba «Sin alteraciones» en verde arriba de «0 de 11 entradas firmadas
 * están selladas». Eso es justo lo que el sellado existe para no hacer —afirmar
 * que un registro está intacto sin poder probarlo—, y en verde se lee como un
 * certificado.
 */
function Resultado({ r }) {
  const sinSellar = r.firmadas - r.selladas;

  if (!r.firmadas) {
    return <div className="text-md text-texto-debil">No hay atenciones firmadas para verificar.</div>;
  }

  if (!r.selladas) {
    return (
      <>
        <Badge tone="gray">No verificable</Badge>
        <div className="mt-2 text-sm text-texto-medio">
          Las {r.firmadas} atenciones firmadas son anteriores al sellado. No se puede
          afirmar ni desmentir que estén intactas.
        </div>
      </>
    );
  }

  return (
    <>
      <Badge tone={r.ok ? "green" : "error"}>
        {r.ok ? "Sin alteraciones" : "⚠ Hay entradas alteradas"}
      </Badge>
      <div className="mt-2 text-sm text-texto-debil">
        {/* El alcance va pegado al veredicto, no como nota al pie: «sin
            alteraciones» sobre parte de la historia no es lo mismo que sobre
            toda. */}
        {sinSellar
          ? `Verificadas ${r.selladas} de ${r.firmadas} atenciones firmadas.`
          : `Verificadas las ${r.firmadas} atenciones firmadas.`}
      </div>
      {!!sinSellar && (
        <div className="mt-1 text-sm text-texto-medio">
          Las otras {sinSellar} son anteriores al sellado y quedan fuera de esta
          comprobación.
        </div>
      )}
      {(r.problemas || []).map((p) => (
        <div key={p.entrada} className="mt-2 rounded-md bg-badge-error-bg px-2.5 py-2 text-sm text-badge-error-fg">
          <strong>{p.titulo}</strong>: {p.motivo}
        </div>
      ))}
    </>
  );
}

/*
 * Quién miró esta historia (Ley 26.529, art. 14).
 *
 * Es el derecho concreto que da la ley: el paciente puede pedir esta lista. Va
 * en su historia y no sólo en la pantalla de auditoría porque hay que poder
 * contestarla en el momento en que la pregunta.
 */
function Accesos({ ciudadanoId }) {
  const q = useLista("accesos-clinicos/de-paciente", { ciudadano: ciudadanoId, pageSize: 50 });

  if (q.isLoading) return <SkeletonTabla filas={4} columnas={3} />;
  // El registro es tan sensible como lo que audita: lo ven conducción y
  // plataforma. A un médico el backend le responde 403, y eso se explica en vez
  // de mostrarle una lista vacía que parecería decir «nadie la miró».
  if (q.error?.status === 403) {
    return (
      <EstadoVacio
        titulo="No tenés permiso para ver esta lista"
        detalle="El registro de accesos lo consultan la administración de la institución y la jefatura de área."
        icono="alert"
      />
    );
  }
  if (q.error) return <EstadoError error={q.error} onReintentar={q.refetch} />;
  if (!q.filas.length) {
    return <EstadoVacio titulo="Nadie consultó esta historia" detalle="Cada consulta a estos datos queda registrada acá." />;
  }

  return (
    <div className="flex flex-col gap-2.5">
      {q.filas.map((a) => (
        <Card key={a.id} className="flex flex-wrap items-center justify-between gap-3 px-[18px] py-3.5">
          <div className="min-w-0">
            <div className="text-md font-semibold">{a.usuario_nombre || a.usuario_email}</div>
            <div className="text-sm text-texto-debil">
              {fechaHora(a.momento)} · <Mono>{a.recurso}</Mono>
            </div>
          </div>
          <Badge tone={a.tipo === "detalle" ? "info" : "gray"}>{a.tipo_display}</Badge>
        </Card>
      ))}
    </div>
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
