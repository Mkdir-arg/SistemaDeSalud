import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useDetalle, useLista } from "@/api/queries";
import { Icon } from "@/components/icons";
import { Avatar, Badge, Button, Card, Field, Input, Modal, Mono, Tabs, Textarea } from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton, SkeletonTabla } from "@/components/ui/estados";

import { useToast } from "@/components/ui/toast";
import { useFiltroUrl } from "@/components/ui/filtros";
import { cn } from "@/lib/cn";
import { fechaHora } from "@/lib/format";

/*
 * Una fecha SIN hora, en dd/mm/aaaa como el resto del expediente.
 *
 * `Estudio.fecha` y `Receta.fecha` son DateField: llegan «2026-07-01», y salían
 * así en pantalla, dos formatos de fecha en la misma pantalla de un registro
 * legal. Para quien lee en dd/mm, «2026-03-04» puede ser el 4 de marzo o el 3 de
 * abril, y en un estudio esa diferencia cambia la cronología.
 *
 * Se parte el texto en vez de usar `new Date`: `new Date("2026-07-01")` es
 * medianoche UTC y en Argentina se muestra como el 30 de junio, o sea que
 * formatear correría todos los estudios un día para atrás.
 */
function fecha(iso) {
  if (!iso) return "—";
  const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : String(iso);
}

export default function HistoriaDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  // La pestaña va en la URL: «mirá los estudios de este paciente» es un link.
  const [tab, setTab] = useFiltroUrl("tab", "evolucion");
  const [nuevaAtencion, setNuevaAtencion] = useState(false);
  const [editandoAntecedentes, setEditandoAntecedentes] = useState(false);

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
      // Con año y en dd/mm/aaaa. Sin el año salía «8/8», que en una fila de
      // contadores se lee como una razón —8 de 8, el mismo idioma que usa el
      // panel de integridad al lado— y que además no distingue una paciente
      // vista la semana pasada de una vista en 2019, en un registro que se
      // conserva diez años.
      n: hc?.entradas?.length
        ? new Date(hc.entradas[0].fecha).toLocaleDateString("es-AR")
        : "—",
      l: "última visita",
      chico: true,
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
        <Button
          onClick={() => setNuevaAtencion(true)}
          // Sin la historia cargada no se sabe si el paciente ya tiene una, y el
          // alta crearía una segunda.
          disabled={!!historias.error}
          className="flex items-center gap-2"
        >
          <Icon name="plus" size={15} /> Nueva atención
        </Button>
      </Card>

      {historias.isLoading ? (
        <SkeletonTabla filas={4} columnas={4} />
      ) : historias.error ? (
        /*
         * Si la historia no se pudo traer, NO se dibuja nada que cuelgue de
         * ella. Antes esta consulta fallaba en silencio y la pantalla mostraba
         * «0 consultas», «Sin entradas de evolución» y «Sin alergias
         * registradas»: no una lista vacía ambigua, una AFIRMACIÓN. Y arriba de
         * esa afirmación se prescribe un antibiótico.
         */
        <EstadoError
          error={historias.error}
          onReintentar={historias.refetch}
          titulo="No se pudo cargar la historia clínica"
        />
      ) : (
        <>
          <div className="mb-[22px] grid grid-cols-2 gap-3.5 sm:grid-cols-4">
            {metricas.map((m) => (
              <Card key={m.l} className="p-[18px]">
                <div className={cn("font-extrabold leading-none", m.chico ? "text-cifra" : "text-cifra-lg")}>
                  {m.n}
                </div>
                <div className="mt-1.5 text-sm text-texto-debil">{m.l}</div>
              </Card>
            ))}
          </div>

          {/*
            El desplazamiento le pertenece a la tira de pestañas, no a la página.
            A 390 px las cuatro pestañas miden 413 px: sin este contenedor el que
            se corría para el costado era el panel entero de la app, y eso se lee
            como pantalla rota y no como pantalla con scroll. `whitespace-nowrap`
            va en el contenedor de las pestañas porque se hereda: sin él la
            etiqueta se parte en tres renglones y la tira mide 87 px de alto.
          */}
          <div className="mb-5 max-w-full overflow-x-auto">
            <Tabs tabs={TABS} valor={tab} onChange={setTab} className="whitespace-nowrap" />
          </div>

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
              <Antecedentes hc={hc} onEditar={() => setEditandoAntecedentes(true)} />
              <Consentimiento ciudadanoId={id} estado={c?.consentimiento} />
              {hc && <Integridad hcId={hc.id} />}
            </div>
          </div>
        </>
      )}

      {nuevaAtencion && (
        <NuevaAtencionModal ciudadanoId={id} hcId={hc?.id} onClose={() => setNuevaAtencion(false)} />
      )}
      {editandoAntecedentes && (
        <AntecedentesModal hc={hc} onClose={() => setEditandoAntecedentes(false)} />
      )}
    </div>
  );
}

/*
 * Alergias y condiciones del paciente.
 *
 * El estado vacío es lo delicado de este panel. «Sin alergias registradas» se
 * lee como «este paciente no tiene alergias», y hasta ahora ese texto aparecía
 * sobre pacientes a los que NUNCA se les preguntó —no había ninguna pantalla
 * para cargarlos: el campo sólo se llenaba desde el seed de la demo—. En un
 * hospital eso significa la palabra «sin alergias» arriba de un paciente
 * alérgico a la penicilina, que es peor que no mostrar el campo.
 *
 * Por eso la marca de quién los cargó y cuándo no es un adorno: es lo único que
 * distingue «se preguntó y no tiene» de «no consta».
 */
function Antecedentes({ hc, onEditar }) {
  const consta = !!hc?.antecedentes_at;

  return (
    <Card className="p-[18px]">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-xs font-bold tracking-wider text-texto-debil">ANTECEDENTES</h2>
        {hc && (
          <button
            onClick={onEditar}
            className="text-sm font-semibold text-accent hover:underline"
          >
            Editar
          </button>
        )}
      </div>

      <Dato
        k="Alergias"
        // Una alergia se marca con color Y con palabra: en una historia
        // clínica confiar sólo en el rojo es un riesgo, no un detalle.
        v={
          hc?.alergias
            ? <span className="text-danger">⚠ {hc.alergias}</span>
            : consta
              ? <span className="text-texto-debil">Sin alergias conocidas</span>
              : <span className="text-badge-amber-fg">No consta</span>
        }
      />
      <div className="h-2.5" />
      <Dato
        k="Condiciones"
        v={hc?.condiciones || (consta ? "Ninguna" : <span className="text-badge-amber-fg">No consta</span>)}
      />

      <div className="mt-3 text-xs text-texto-debil">
        {consta
          ? `Cargados por ${hc.antecedentes_por_nombre || "el sistema"} · ${fechaHora(hc.antecedentes_at)}`
          : "Nadie registró los antecedentes de este paciente. «No consta» no quiere decir que no tenga."}
      </div>
    </Card>
  );
}

function AntecedentesModal({ hc, onClose }) {
  const toast = useToast();
  const [alergias, setAlergias] = useState(hc?.alergias || "");
  const [condiciones, setCondiciones] = useState(hc?.condiciones || "");

  const guardar = useAccion(
    () => api.patch(`/historias-clinicas/${hc.id}/`, { alergias, condiciones }),
    {
      // El padrón muestra la columna «Condiciones / alergias» derivada de acá.
      invalida: ["lista", "detalle"],
      onSuccess: () => { toast.ok("Antecedentes actualizados."); onClose(); },
      onError: (e) => toast.deError(e, "No se pudieron guardar los antecedentes."),
    },
  );

  return (
    <Modal
      title="Antecedentes del paciente"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardar.isPending} onClick={() => guardar.mutate()}>
            {guardar.isPending ? "Guardando…" : "Guardar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Alergias">
          <Input
            value={alergias}
            onChange={(e) => setAlergias(e.target.value)}
            autoFocus
            placeholder="Penicilina, AINEs…"
          />
        </Field>
        <Field label="Condiciones / antecedentes">
          <Input
            value={condiciones}
            onChange={(e) => setCondiciones(e.target.value)}
            placeholder="HTA, diabetes tipo 2…"
          />
        </Field>
        {/* Guardar vacío es una respuesta, y hay que poder darla: es la
            diferencia entre «se preguntó y no tiene» y «no se preguntó». */}
        <div className="text-sm text-texto-debil">
          Queda asentado quién los cargó y cuándo. Si preguntaste y el paciente no
          refiere alergias, guardá el campo vacío: eso ya es un dato.
        </div>
      </div>
    </Modal>
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
        {/* Se dice ANTES de intentar, no después del error: quien no puede
            firmar igual necesita dejar el asiento, y destildar es el camino. */}
        <div className="text-sm text-texto-debil">
          Firmar la asienta a tu nombre y con tu matrícula, y queda sellada: no se
          puede editar después. Sin firmar queda como borrador y se puede corregir.
        </div>
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
/*
 * El nombre del modelo, dicho como se le dice a un paciente.
 *
 * Del lado del registro se guarda el nombre del MODELO a propósito —una ruta se
 * puede renombrar y el registro tiene que seguir diciendo lo mismo dentro de
 * diez años—, pero eso es cómo se guarda, no cómo se muestra. Esta lista se lee
 * en voz alta frente a quien la pidió: «historiaclinica» en monoespaciado no es
 * una respuesta.
 */
const RECURSO = {
  ciudadano: "datos del paciente",
  historiaclinica: "historia clínica",
  entradahistoria: "evolución",
  estudio: "estudios",
  receta: "recetas",
  consentimientodatos: "consentimiento",
};

const POR_PAGINA = 25;

function Accesos({ ciudadanoId }) {
  const [pagina, setPagina] = useState(1);
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");

  const q = useLista("accesos-clinicos/de-paciente", {
    ciudadano: ciudadanoId,
    page: pagina,
    pageSize: POR_PAGINA,
    desde: desde || undefined,
    hasta: hasta || undefined,
  });

  const primero = (pagina - 1) * POR_PAGINA + 1;
  const ultimo = Math.min(pagina * POR_PAGINA, q.total);

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

  return (
    <div className="flex flex-col gap-2.5">
      {/*
        El total va ARRIBA de todo y no como nota al pie. Esta pestaña existe
        para contestar el art. 14 de la Ley 26.529 en el momento en que el
        paciente lo pregunta, y antes mostraba los primeros 50 de 553 sin decir
        que estaba cortada: una respuesta incompleta con cara de completa. Quien
        atiende el reclamo no tenía manera de saber que faltaban quinientos.
      */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="text-md text-texto-medio">
          {q.isLoading
            ? "Contando accesos…"
            : q.total
              ? <>Mostrando <strong>{primero}–{ultimo}</strong> de <strong>{q.total}</strong> accesos registrados</>
              : "Sin accesos registrados en este período"}
        </div>
        <div className="flex items-end gap-2">
          <Field label="Desde">
            <Input type="date" value={desde} onChange={(e) => { setDesde(e.target.value); setPagina(1); }} />
          </Field>
          <Field label="Hasta">
            <Input type="date" value={hasta} onChange={(e) => { setHasta(e.target.value); setPagina(1); }} />
          </Field>
        </div>
      </div>

      {q.isLoading ? (
        <SkeletonTabla filas={4} columnas={3} />
      ) : !q.filas.length ? (
        <EstadoVacio
          titulo={desde || hasta ? "Sin accesos en ese rango" : "Nadie consultó esta historia"}
          detalle="Cada consulta a estos datos queda registrada acá."
        />
      ) : (
        q.filas.map((a) => (
          <Card key={a.id} className="flex flex-wrap items-center justify-between gap-3 px-[18px] py-3.5">
            <div className="min-w-0">
              <div className="text-md font-semibold">{a.usuario_nombre || a.usuario_email}</div>
              <div className="text-sm text-texto-debil">
                {fechaHora(a.momento)} · {RECURSO[a.recurso] || a.recurso}
              </div>
            </div>
            <Badge tone={a.tipo === "detalle" ? "info" : "gray"}>{a.tipo_display}</Badge>
          </Card>
        ))
      )}

      {q.paginas > 1 && (
        <div className="flex items-center justify-center gap-3 pt-1.5">
          <Button
            variant="secondary"
            className="text-sm"
            disabled={pagina <= 1}
            onClick={() => setPagina((p) => p - 1)}
          >
            Anterior
          </Button>
          <span className="text-sm text-texto-debil">Página {pagina} de {q.paginas}</span>
          <Button
            variant="secondary"
            className="text-sm"
            disabled={pagina >= q.paginas}
            onClick={() => setPagina((p) => p + 1)}
          >
            Siguiente
          </Button>
        </div>
      )}
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

/*
 * El estado de la firma de UNA entrada, dicho donde se lee la historia.
 *
 * La API devuelve `integra` por entrada y la evolución la ignoraba: una entrada
 * alterada después de firmarse se mostraba con el mismo verde «Firmada» que una
 * intacta. El sistema tenía la información y elegía mostrar verde encima. La
 * pantalla que el médico lee es ésta, no el panel lateral —que además sólo
 * calcula a pedido y queda debajo de toda la evolución hasta `lg`—.
 *
 * Mismo criterio que el panel de INTEGRIDAD: el verde sólo cuando se puede
 * probar, porque «en verde se lee como un certificado».
 */
function SelloDeFirma({ entrada }) {
  if (!entrada.firmada) return null;
  if (entrada.integra === false) {
    return <Badge tone="error">⚠ Alterada después de firmarse</Badge>;
  }
  if (entrada.integra == null) {
    return <Badge tone="gray">Firmada · no verificable</Badge>;
  }
  return <Badge tone="green">Firmada</Badge>;
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
            <SelloDeFirma entrada={e} />
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
              {fecha(s.fecha)} · {s.autor || "—"} {s.archivo && <Mono className="ml-1.5">{s.archivo}</Mono>}
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
  const [suspendiendo, setSuspendiendo] = useState(null);

  if (!recetas.length) return <EstadoVacio titulo="Sin recetas" detalle="Las recetas se emiten durante la atención." />;
  return (
    <div className="flex flex-col gap-2.5">
      {recetas.map((r) => (
        <Card key={r.id} className="flex flex-wrap items-center justify-between gap-3 px-[18px] py-3.5">
          <div className="min-w-0">
            <div className="text-md text-texto-medio">{r.detalle}</div>
            <div className="text-sm text-texto-debil">
              {fecha(r.fecha)}
              {r.autor_nombre ? ` · ${r.autor_nombre}` : ""}
            </div>
          </div>
          <div className="flex items-center gap-2.5">
            <Badge tone={r.activa ? "green" : "gray"}>{r.activa ? "Activa" : "Inactiva"}</Badge>
            {/* Sin esto el estado sólo podía crecer: a los dos años el paciente
                crónico tiene veinte recetas «Activas» superpuestas y no hay
                manera de saber cuál es el tratamiento vigente. */}
            {r.activa && (
              <Button variant="secondary" className="text-sm" onClick={() => setSuspendiendo(r)}>
                Suspender
              </Button>
            )}
          </div>
        </Card>
      ))}

      {suspendiendo && (
        <SuspenderRecetaModal receta={suspendiendo} onClose={() => setSuspendiendo(null)} />
      )}
    </div>
  );
}

function SuspenderRecetaModal({ receta, onClose }) {
  const toast = useToast();
  const [motivo, setMotivo] = useState("");

  const suspender = useAccion(
    () => api.post(`/recetas/${receta.id}/suspender/`, { motivo }),
    {
      invalida: ["lista", "detalle"],
      onSuccess: () => { toast.ok("Medicación suspendida."); onClose(); },
      // Emitir y suspender los hace quien puede prescribir: el backend explica
      // cuál es la regla, así que se muestra su texto en vez de uno genérico.
      onError: (e) => toast.deError(e, "No se pudo suspender la receta."),
    },
  );

  return (
    <Modal
      title="Suspender medicación"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={suspender.isPending || !motivo.trim()} onClick={() => suspender.mutate()}>
            {suspender.isPending ? "Suspendiendo…" : "Suspender"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <div className="rounded-md bg-superficie-2 px-3 py-2.5 text-md text-texto-medio">
          {receta.detalle}
        </div>
        <Field label="Motivo *">
          <Textarea
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            autoFocus
            placeholder="Rotación de antibiótico, suspensión prequirúrgica…"
          />
        </Field>
        <div className="text-sm text-texto-debil">
          Queda un asiento firmado en la evolución. Suspender una medicación es un
          acto clínico: quien retome el tratamiento tiene que poder leer por qué se cortó.
        </div>
      </div>
    </Modal>
  );
}
