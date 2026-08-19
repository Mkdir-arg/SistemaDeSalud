import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useDetalle, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import { Avatar, Badge, Button, Card, Field, Input, Modal, Mono, Tabs, Textarea } from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton, SkeletonTabla } from "@/components/ui/estados";

import { useToast } from "@/components/ui/toast";
import { useFiltroUrl } from "@/components/ui/filtros";
// El vocabulario del registro de accesos es compartido con la pantalla de
// auditoría a propósito: el mismo evento tiene que decirse y pintarse igual en
// las dos, y la que lo bajaba de tono era justo la que se lee frente al paciente.
import { nombreRecurso, TONO_ACCESO } from "@/lib/auditoria";
import { cn } from "@/lib/cn";
import { fechaHora, plural } from "@/lib/format";

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

function esArchivoProtegido(ref) {
  const s = String(ref || "");
  return s.startsWith("uploads/") || s.includes("/api/archivos/descargar/uploads/");
}

function nombreArchivo(ref) {
  const s = String(ref || "");
  return s.split(/[\\/]/).filter(Boolean).pop() || "archivo";
}

/*
 * La edad, al lado de la fecha de nacimiento.
 *
 * Es el dato con el que se decide una dosis pediátrica, y hasta acá había que
 * calcularlo de cabeza: «23/2/2015» es un chico de 11 años y eso no se lee, se
 * hace. Se arma con las partes de la fecha y no con `new Date`, por lo mismo que
 * explica `fecha()`: la fecha nace a medianoche UTC y en Argentina se muestra un
 * día antes, que en el cumpleaños del paciente cambia el número.
 */
function edad(iso) {
  const m = String(iso || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  const [a, mes, dia] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const hoy = new Date();
  const cumplio =
    hoy.getMonth() + 1 > mes || (hoy.getMonth() + 1 === mes && hoy.getDate() >= dia);
  const años = hoy.getFullYear() - a - (cumplio ? 0 : 1);
  if (años < 0) return null;
  return años < 1 ? "menos de 1 año" : plural(años, "año", "años");
}

export default function HistoriaDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { roles } = useInstitucion();
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
  // Firmar una atención lo habilita el rol (regla del motor: `quien_firma`), y
  // la matrícula la valida el backend al intentarlo. Acá sólo se decide si el
  // botón «Firmar» tiene sentido: ofrecérselo a quien nunca puede usarlo es
  // prometer un camino que no existe, que es el defecto que se está corrigiendo.
  const puedeFirmar = (roles || []).some((r) => r === "medico" || r === "admin");

  // Un estudio SOLICITADO y todavía no hecho también cuenta en «estudios»: el
  // contador mezclaba pedidos con realizados, y de ahí sale esperar un informe
  // que nadie pidió o pedir el estudio de nuevo.
  const estudios = hc?.estudios || [];
  const pendientes = estudios.filter((e) => !e.realizado).length;

  // Cada dato entero o en el renglón siguiente, nunca partido al medio. A 390 px
  // «DNI 7775258 · 11/9/1974 · PAMI» salía en cuatro renglones, con el separador
  // «·» solo en una línea. Confirmar que se está escribiendo en la historia del
  // paciente correcto es el chequeo de seguridad más básico que hay, y con dos
  // «Acosta» en el padrón el documento en pedazos deja de servir para eso.
  const identificacion = !c
    ? []
    : [
        c.documento ? `DNI ${c.documento}` : null,
        c.fecha_nacimiento
          ? [fecha(c.fecha_nacimiento), edad(c.fecha_nacimiento)].filter(Boolean).join(" · ")
          : null,
        c.obra_social || null,
      ].filter(Boolean);

  const metricas = [
    { n: hc?.entradas?.length || 0, l: "consultas" },
    {
      n: estudios.length,
      l: pendientes ? `estudios · ${plural(pendientes, "pendiente", "pendientes")}` : "estudios",
    },
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
          <div className="flex flex-wrap items-center gap-x-2 text-base text-texto-debil">
            {identificacion.map((d, i) => (
              <span key={d} className="whitespace-nowrap">
                {/* El separador viaja pegado al dato que sigue: suelto, quedaba
                    solo en un renglón. */}
                {i > 0 && <span className="mr-2 text-texto-tenue" aria-hidden="true">·</span>}
                {d}
              </span>
            ))}
          </div>
          <AlergiaEnCabecera hc={hc} listo={!historias.isLoading && !historias.error} />
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
          // Renglón propio abajo de `sm`. Como hermano del bloque de
          // identificación en un `flex-wrap`, el botón no bajaba de línea y lo
          // estrangulaba hasta 60 px: el nombre salía en dos líneas y el
          // documento en cuatro. `w-full` lo obliga a ocupar su propia fila.
          className="flex w-full items-center justify-center gap-2 sm:w-auto"
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
              una columna de 280px al lado deja la evolución ilegible. Lo urgente
              —la alergia— ya no vive acá: está en la cabecera, arriba de todo y
              en cualquier ancho. Este panel es el detalle (quién la cargó y
              cuándo) y el lugar donde se edita. */}
          <div className="grid items-start gap-5 lg:grid-cols-[1fr_17.5rem]">
            <div>
              {tab === "evolucion" && <Evolucion entradas={hc?.entradas || []} puedeFirmar={puedeFirmar} />}
              {tab === "estudios" && <Estudios estudios={estudios} />}
              {tab === "recetas" && <Recetas recetas={hc?.recetas || []} />}
              {tab === "accesos" && <Accesos ciudadanoId={id} />}
            </div>

            <div className="flex flex-col gap-3.5">
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
 * La alergia, en la cabecera y en todos los anchos.
 *
 * Vivía sólo en el panel lateral, que por debajo de 1024 px cae DESPUÉS de toda
 * la evolución: medido a 390 px sobre un paciente con diez entradas, el título
 * ANTECEDENTES arrancaba a 2355 px del inicio —casi tres pantallas de scroll— y
 * a 768 px, la tablet de enfermería, a 2006 px. El médico que abre la historia
 * en el celular del pasillo ve el nombre, los contadores y la primera evolución,
 * y prescribe desde ahí: enterrar la alergia debajo de la evolución tiene el
 * mismo efecto práctico que no mostrarla.
 *
 * El estado vacío usa el mismo criterio que el panel: «no consta» no es «no
 * tiene». Y si la historia no se pudo traer no se dice NADA, porque afirmar
 * «sin alergias» sobre un dato que no llegó es el peor error posible acá.
 */
function AlergiaEnCabecera({ hc, listo }) {
  if (!listo) return null;
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-x-2 text-base">
      {hc?.alergias ? (
        // Símbolo Y palabra: en una historia clínica confiar sólo en el rojo es
        // un riesgo, no un detalle de estilo.
        <span className="font-bold text-danger">⚠ Alergia: {hc.alergias}</span>
      ) : (
        <span className="text-texto-debil">
          Alergias:{" "}
          {hc?.antecedentes_at
            ? "sin alergias conocidas"
            : <span className="font-semibold text-badge-amber-fg">no consta</span>}
        </span>
      )}
      {hc?.condiciones && <span className="text-texto-debil">· {hc.condiciones}</span>}
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
  const [historial, setHistorial] = useState(false);

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
          {/* El mismo campo `alcance` guarda dos cosas distintas: para qué se
              consintió, o por qué se revocó. Sin rótulo, el motivo de una
              revocación se lee en el mismo renglón y con la misma cara que el
              alcance de un consentimiento otorgado. */}
          {estado.alcance && (
            <div className="mt-1 text-sm text-texto-medio">
              <span className="text-texto-debil">
                {estado.otorgado ? "Alcance: " : "Motivo de la revocación: "}
              </span>
              {estado.alcance}
            </div>
          )}
          {/* El modelo guarda cada fila justamente porque «lo que importa ante
              un reclamo no es el estado de hoy sino qué se consintió y cuándo»,
              y esa era la única pregunta que el producto no podía contestar: las
              filas estaban en la base y no había ninguna pantalla que las
              mostrara. Armar la cronología a mano por SQL, además, deja fuera
              del registro de accesos a quien la arma. */}
          <button
            onClick={() => setHistorial((v) => !v)}
            className="mt-2 text-sm font-semibold text-accent hover:underline"
          >
            {historial ? "Ocultar historial" : "Ver historial"}
          </button>
          {historial && <HistorialConsentimientos ciudadanoId={ciudadanoId} />}
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
 * La cronología: otorgó en 2019, revocó en 2023, volvió a otorgar en 2024.
 *
 * El endpoint ya existía, ya filtra por paciente y ya queda auditado; lo que
 * faltaba era la pantalla. Un dato que se guarda para un momento puntual —el
 * reclamo, la inspección— y no se puede leer en ese momento cuesta lo mismo que
 * no guardarlo.
 */
function HistorialConsentimientos({ ciudadanoId }) {
  const q = useLista("consentimientos", { ciudadano: ciudadanoId, pageSize: 50 });

  if (q.isLoading) return <div className="mt-2 text-sm text-texto-debil">Buscando el historial…</div>;
  if (q.error) {
    return <div className="mt-2 text-sm text-danger">No se pudo traer el historial. Probá de nuevo.</div>;
  }
  if (!q.filas.length) return <div className="mt-2 text-sm text-texto-debil">Sin registros.</div>;

  return (
    <>
      <ol className="mt-2.5 flex flex-col gap-2.5 border-t border-division pt-2.5">
        {q.filas.map((c) => (
          <li key={c.id} className="text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={c.otorgado ? "green" : "amber"}>{c.otorgado ? "Otorgado" : "Revocado"}</Badge>
              <span className="text-texto-debil">{fechaHora(c.momento)}</span>
            </div>
            <div className="mt-0.5 text-texto-debil">
              {c.modo_display || c.modo}
              {c.tomado_por_nombre ? ` · lo tomó ${c.tomado_por_nombre}` : ""}
            </div>
            {c.alcance && (
              <div className="text-texto-medio">
                {c.otorgado ? "Alcance: " : "Motivo: "}{c.alcance}
              </div>
            )}
          </li>
        ))}
      </ol>
      {q.total > q.filas.length && (
        // Una lista cortada sin decirlo es la misma respuesta incompleta con
        // cara de completa que se corrigió en la pestaña de accesos.
        <div className="mt-2 text-xs text-texto-debil">
          Se muestran los {q.filas.length} más recientes de {q.total}.
        </div>
      )}
    </>
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
  // Las que quedan legítimamente afuera las cuenta el backend: son las
  // anteriores a la fecha desde la que este sistema sella. Una firmada sin sello
  // POSTERIOR a esa fecha no es «no verificable», es un problema —el alta sella
  // en la misma transacción, así que esa fila no la escribió la aplicación— y
  // viene entre `problemas`.
  const sinSellar = r.fuera_de_alcance ?? r.firmadas - r.selladas;
  const desde = r.sella_desde ? fechaHora(r.sella_desde) : null;

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
          {/* Con la fecha, «anterior al sellado» se puede comprobar. Sin ella era
              una excusa que cualquiera podía invocar sobre una entrada
              insertada por afuera y fechada dos años atrás. */}
          Las otras {sinSellar} quedan fuera de esta comprobación por ser anteriores
          al sellado{desde ? `, que en este sistema empezó el ${desde}` : ""}.
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
 * Un mismo acto, una sola línea.
 *
 * Abrir la historia una vez escribe DOS filas —la ficha del paciente y la
 * historia clínica son dos lecturas— con el mismo minuto, y hay actos que dejan
 * más. Contadas de a una, la paciente que lee «637» se lleva la idea de que su
 * historia se consultó seiscientas veces cuando fueron la mitad de aperturas de
 * los profesionales que la atienden. Una cifra alarmante y falsa entregada por
 * el propio hospital es material de reclamo, no una respuesta a un reclamo.
 *
 * Se agrupa por persona y minuto y se dice cuántos eventos junta, para no
 * esconder nada: lo que se colapsa es el conteo, no el dato.
 */
function porActo(filas) {
  const actos = [];
  for (const a of filas) {
    const minuto = String(a.momento || "").slice(0, 16);
    const ultimo = actos[actos.length - 1];
    if (ultimo && ultimo.usuario === a.usuario && ultimo.minuto === minuto) {
      ultimo.eventos.push(a);
      continue;
    }
    actos.push({ id: a.id, usuario: a.usuario, minuto, eventos: [a] });
  }
  return actos;
}

const POR_PAGINA = 25;

/*
 * Quién miró esta historia (Ley 26.529, art. 14).
 *
 * Es el derecho concreto que da la ley: el paciente puede pedir esta lista. Va
 * en su historia y no sólo en la pantalla de auditoría porque hay que poder
 * contestarla en el momento en que la pregunta, y en ese momento la pregunta es
 * «quiénes»: primero el resumen por persona, después la cronología.
 */
function Accesos({ ciudadanoId }) {
  const [pagina, setPagina] = useState(1);
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [quien, setQuien] = useState("");

  const q = useLista("accesos-clinicos/de-paciente", {
    ciudadano: ciudadanoId,
    page: pagina,
    pageSize: POR_PAGINA,
    desde: desde || undefined,
    hasta: hasta || undefined,
    usuario: quien || undefined,
  });

  // El resumen lo arma el backend sobre TODOS los accesos del período, no sobre
  // la página: contar por persona con 25 de 637 filas contestaría cualquier cosa.
  // Va en su propia consulta y SIN el filtro por profesional; si saliera de la
  // lista filtrada, elegir a una persona borraría a las demás del selector y no
  // habría cómo volver.
  const resumen = useLista("accesos-clinicos/de-paciente", {
    ciudadano: ciudadanoId,
    pageSize: 1,
    desde: desde || undefined,
    hasta: hasta || undefined,
  });
  const personas = resumen.data?.personas || [];
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
      {/* El panel lleva título propio. La tira de pestañas se desplaza y en un
          celular la activa puede quedar fuera de cuadro: sin encabezado, el link
          que se manda para contestar «quién miró mi historia» aterriza en una
          lista de nombres de profesionales con fechas arriba de la ficha de una
          paciente, que se puede leer como quién la atendió. */}
      <h2 className="text-lg font-bold tracking-tight">Quién miró esta historia</h2>

      {/* La respuesta a la pregunta que se hizo. La pregunta es «quiénes», y la
          respuesta correcta es «tres personas, y son estas»: lo que la pantalla
          entregaba era «637 accesos» repartidos en 26 páginas, que nadie lee en
          un mostrador. */}
      {!!personas.length && (
        <Card className="px-[18px] py-3.5">
          <div className="text-md font-semibold">
            {plural(personas.length, "persona consultó", "personas consultaron")} esta historia
          </div>
          <ul className="mt-2 flex flex-col gap-1.5">
            {personas.map((p) => (
              <li key={p.usuario} className="flex flex-wrap items-baseline gap-x-2 text-sm">
                <span className="font-semibold text-texto-medio">{p.nombre}</span>
                <span className="text-texto-debil">
                  {plural(p.veces, "evento", "eventos")} · de {fechaHora(p.primera)} a {fechaHora(p.ultima)}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

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
        <div className="flex flex-wrap items-end gap-2">
          {personas.length > 1 && (
            <Field label="Profesional">
              <select
                value={quien}
                onChange={(e) => { setQuien(e.target.value); setPagina(1); }}
                className="h-9 rounded-md border border-campo-borde bg-superficie px-2.5 text-md text-texto-medio"
              >
                <option value="">Todos</option>
                {personas.map((p) => (
                  <option key={p.usuario} value={p.usuario}>{p.nombre}</option>
                ))}
              </select>
            </Field>
          )}
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
        porActo(q.filas).map((acto) => {
          const a = acto.eventos[0];
          const recursos = [...new Set(acto.eventos.map((e) => nombreRecurso(e.recurso)))];
          return (
            <Card key={acto.id} className="flex flex-wrap items-center justify-between gap-3 px-[18px] py-3.5">
              <div className="min-w-0">
                <div className="text-md font-semibold">{a.usuario_nombre || a.usuario_email}</div>
                <div className="text-sm text-texto-debil">
                  {fechaHora(a.momento)} · {recursos.join(" y ")}
                </div>
                {acto.eventos.length > 1 && (
                  // Se dice cuántos junta: la fecha llega al minuto, así que dos
                  // filas idénticas no dejan distinguir «el sistema lo anotó dos
                  // veces» de «lo abrió dos veces», y agrupar sin avisar sería
                  // esconder la diferencia en vez de nombrarla.
                  <div className="text-xs text-texto-debil">
                    {plural(acto.eventos.length, "evento del registro", "eventos del registro")} en
                    el mismo minuto: se muestran como una sola consulta.
                  </div>
                )}
              </div>
              <Badge tone={TONO_ACCESO[a.tipo] || "gray"}>{a.tipo_display}</Badge>
            </Card>
          );
        })
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
  // El borrador se marca con chapa y con palabras. Antes se distinguía sólo por
  // la AUSENCIA de un badge, que se lee igual que «no cargó» o «no aplica»:
  // meses después, quien lee la evolución para reconstruir qué pasó no puede
  // separar el registro firmado del borrador de alguien, y ante un reclamo esa
  // diferencia es toda la diferencia.
  if (!entrada.firmada) return <Badge tone="amber">Sin firmar · borrador</Badge>;
  if (entrada.integra === false) {
    return <Badge tone="error">⚠ Alterada después de firmarse</Badge>;
  }
  if (entrada.integra == null) {
    return <Badge tone="gray">Firmada · no verificable</Badge>;
  }
  return <Badge tone="green">Firmada</Badge>;
}

function Evolucion({ entradas, puedeFirmar }) {
  // `null` = ninguno abierto. Guarda la entrada y qué se va a hacer con ella.
  const [editando, setEditando] = useState(null);
  const [firmando, setFirmando] = useState(null);

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
          {/*
            El borrador se completa desde acá. El modal de alta promete con
            todas las letras que «sin firmar queda como borrador y se puede
            corregir», y desde la pantalla no se podía: quien destildaba «Firmar»
            dejaba un asiento que quedaba en la historia para siempre, sin marca
            y sin forma de terminarlo —las entradas no se borran por diseño—. La
            API ya lo permite (PATCH sobre lo no firmado).
          */}
          {!e.firmada && (
            <div className="mt-3 flex flex-wrap gap-2">
              <Button variant="secondary" className="text-sm" onClick={() => setEditando(e)}>
                Editar
              </Button>
              {puedeFirmar && (
                <Button className="text-sm" onClick={() => setFirmando(e)}>
                  Firmar
                </Button>
              )}
            </div>
          )}
        </Card>
      ))}

      {editando && <EditarBorradorModal entrada={editando} onClose={() => setEditando(null)} />}
      {firmando && <FirmarBorradorModal entrada={firmando} onClose={() => setFirmando(null)} />}
    </div>
  );
}

function EditarBorradorModal({ entrada, onClose }) {
  const toast = useToast();
  const [titulo, setTitulo] = useState(entrada.titulo || "");
  const [contenido, setContenido] = useState(entrada.contenido || "");

  const guardar = useAccion(
    () => api.patch(`/entradas-historia/${entrada.id}/`, { titulo, contenido }),
    {
      onSuccess: () => { toast.ok("Borrador actualizado."); onClose(); },
      onError: (e) => toast.deError(e, "No se pudo guardar el borrador."),
    },
  );

  return (
    <Modal
      title="Corregir borrador"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardar.isPending || !titulo} onClick={() => guardar.mutate()}>
            {guardar.isPending ? "Guardando…" : "Guardar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Título *">
          <Input value={titulo} onChange={(e) => setTitulo(e.target.value)} autoFocus />
        </Field>
        <Field label="Evolución / observaciones">
          <Textarea value={contenido} onChange={(e) => setContenido(e.target.value)} />
        </Field>
        <div className="text-sm text-texto-debil">
          Sigue siendo un borrador: no cuenta como registro firmado hasta que alguien
          lo firme.
        </div>
      </div>
    </Modal>
  );
}

function FirmarBorradorModal({ entrada, onClose }) {
  const toast = useToast();

  const firmar = useAccion(
    () => api.patch(`/entradas-historia/${entrada.id}/`, { firmada: true }),
    {
      onSuccess: () => { toast.ok("Atención firmada."); onClose(); },
      // Firmar exige rol y matrícula (regla del motor): el backend explica cuál
      // falta, así que se muestra su texto en vez de uno genérico.
      onError: (e) => toast.deError(e, "No se pudo firmar la atención."),
    },
  );

  return (
    <Modal
      title="Firmar la atención"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={firmar.isPending} onClick={() => firmar.mutate()}>
            {firmar.isPending ? "Firmando…" : "Firmar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        {/* Se firma lo que se está leyendo, no un id: el texto va delante. */}
        <div className="rounded-md bg-superficie-2 px-3 py-2.5">
          <div className="text-md font-bold">{entrada.titulo}</div>
          {entrada.contenido && <div className="mt-1 text-md text-texto-medio">{entrada.contenido}</div>}
        </div>
        <div className="text-sm text-texto-debil">
          Queda a tu nombre y con tu matrícula, y se sella: después no se puede
          editar. Para corregirla habría que registrar una atención nueva.
        </div>
      </div>
    </Modal>
  );
}

/*
 * En qué estado está un estudio, siempre dicho.
 *
 * Hay TRES estados reales y la pantalla dibujaba dos: el motor crea el estudio
 * al SOLICITARLO (queda `realizado=False` y sin resultado) y lo marca realizado
 * al cerrarse el sub-caso, donde el resultado sigue siendo opcional. Sin badge
 * quedaban tapados dos estados opuestos —pedido y hecho sin informe—, y ver
 * «TAC de cerebro · 15/08/2026 · Laura Méndez» sin ninguna marca lleva a asumir
 * que está hecho: se espera un informe que nadie pidió, o se pide el estudio de
 * nuevo. El dato viene en la API y la pantalla del caso ya lo muestra bien.
 */
function EstadoEstudio({ estudio }) {
  // «Alterado» va en rojo y no en ámbar: el ámbar acá ya significa «falta
  // hacerlo», y el mismo color para dos estados opuestos no informa nada.
  if (!estudio.realizado) return <Badge tone="amber">Pendiente</Badge>;
  if (!estudio.resultado) return <Badge tone="gray">Realizado · sin informe</Badge>;
  return (
    <Badge tone={estudio.resultado === "normal" ? "green" : "error"}>
      {estudio.resultado_display}
    </Badge>
  );
}

function Estudios({ estudios }) {
  const toast = useToast();
  const [descargando, setDescargando] = useState(null);

  async function descargar(estudio) {
    setDescargando(estudio.id);
    try {
      await api.downloadArchivo(estudio.archivo, nombreArchivo(estudio.archivo));
    } catch (e) {
      toast.deError(e, "No se pudo descargar el archivo.");
    } finally {
      setDescargando(null);
    }
  }

  if (!estudios.length) return <EstadoVacio titulo="Sin estudios" detalle="Los estudios se cargan desde el flujo de diagnóstico." />;
  return (
    <div className="flex flex-col gap-2.5">
      {estudios.map((s) => (
        <Card key={s.id} className="flex flex-wrap items-center justify-between gap-3 px-[18px] py-3.5">
          <div className="min-w-0">
            <div className="text-md font-semibold">{s.tipo}</div>
            <div className="text-sm text-texto-debil">
              {fecha(s.fecha)} · {s.autor || "—"}{" "}
              {s.archivo && (esArchivoProtegido(s.archivo) ? (
                <Button
                  size="sm"
                  variant="ghost"
                  className="ml-1 h-7 px-2 align-middle text-sm"
                  disabled={descargando === s.id}
                  onClick={() => descargar(s)}
                >
                  <Icon name="download" size={14} />
                  {descargando === s.id ? "Descargando..." : "Archivo"}
                </Button>
              ) : (
                <Mono className="ml-1.5">{s.archivo}</Mono>
              ))}
            </div>
          </div>
          <EstadoEstudio estudio={s} />
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
