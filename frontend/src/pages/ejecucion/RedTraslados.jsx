import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import { Badge, Button, ConfirmDialog, Field, Input, Modal, Select, Tabs, Textarea } from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { antiguedad, fechaHora } from "@/lib/format";
import { cn } from "@/lib/cn";

/*
 * Traslados entre establecimientos.
 *
 * La misma pantalla sirve para los dos lados, pero lo que se puede hacer es
 * distinto: el que manda pide, cancela y avisa que salió la ambulancia; el que
 * recibe acepta, rechaza y registra la llegada. Separarlas en dos pantallas
 * duplicaría todo para que después alguien pregunte dónde ve «los míos».
 *
 * Abre donde ese establecimiento tiene algo: el grande en lo que le derivan
 * —un traslado sin responder es un paciente esperando en otra guardia— y el
 * chico en lo que deriva.
 */
const ESTADOS = {
  solicitado: { label: "Esperando respuesta", tone: "amber" },
  aceptado: { label: "Aceptado", tone: "green" },
  rechazado: { label: "Rechazado", tone: "error" },
  en_camino: { label: "En camino", tone: "info" },
  recibido: { label: "Recibido", tone: "green" },
  cancelado: { label: "Cancelado", tone: "gray" },
  fallido: { label: "No llegó", tone: "error" },
};

/*
 * Media hora sin respuesta ya es un problema: del otro lado hay un paciente
 * esperando una cama en una guardia. Pasado el umbral la fila cambia de tono,
 * porque «sin responder hace 4 h» en gris chico al borde derecho de la fila no
 * lo mira nadie. Lo mismo para el que aceptó y todavía no salió: «Aceptado» es
 * el estado donde hay una cama comprometida y nada se mueve.
 */
const DEMORA_MIN = 30;

/** ¿Hace más de `minutos` que pasó esto? */
const masDe = (ts, minutos) => !!ts && Date.now() - new Date(ts).getTime() > minutos * 60_000;

/*
 * Refresco automático, como en toda pantalla viva del sistema (la fila, mi
 * trabajo, el tablero). Sin esto, una pantalla abierta y en foco —el caso normal
 * en jefatura— queda congelada: el `staleTime` global sólo vuelve a pedir al
 * recuperar el foco de la ventana, así que un pedido que entra a las 14:05 no
 * aparece hasta que alguien cambia de ventana y vuelve. Un traslado sin
 * responder es un paciente esperando en otra guardia.
 */
const VIVA = { refetchInterval: 30_000, refetchIntervalInBackground: false };

/**
 * El reloj de la fila sigue al ESTADO, no siempre al pedido.
 *
 * «En camino · hace 6 h» sobre un móvil que salió recién es información falsa
 * para el equipo que espera al paciente, y la única salida que le queda es el
 * teléfono, que es lo que este módulo vino a reemplazar.
 */
function reloj(t) {
  if (t.estado === "en_camino" && t.salida_at) return { texto: "salió hace", ts: t.salida_at };
  if (t.estado === "recibido" && t.llegada_at) return { texto: "llegó hace", ts: t.llegada_at };
  if (t.estado === "solicitado") return { texto: "sin responder hace", ts: t.solicitado_at };
  // «Aceptado · hace 3 d» sobre una cama que se reservó recién decía la
  // antigüedad del PEDIDO, y se leía igual que la del traslado aceptado hace
  // tres días cuya ambulancia nunca salió. El equipo que reservó la cama mira
  // esta fila para decidir si esperar o llamar al hospital de origen.
  if (t.estado === "aceptado" && t.resuelto_at) return { texto: "aceptado hace", ts: t.resuelto_at };
  return { texto: "hace", ts: t.solicitado_at };
}

export default function RedTraslados() {
  const { institucion } = useInstitucion();
  const [tab, setTab] = useState(null);

  /*
   * Las redes de ESTE establecimiento, no las de todas mis membresías.
   *
   * El listado sin filtrar devuelve las redes de cualquier institución donde yo
   * tenga membresía, ordenadas por nombre: quedándose con la primera, una
   * dirección de red parada en el Hospital X miraba la tabla comparativa de otra
   * red —sin ninguna fila marcada «· acá»— y decidía a dónde mandar recursos
   * sobre establecimientos que no son los suyos. Y un hospital que además está
   * en una red de patología (trauma, perinatal, quemados) no tenía forma de ver
   * la otra: no existía en la pantalla y nada decía que faltara.
   */
  const redes = useLista(
    "redes",
    { activa: true, instituciones: institucion?.id, pageSize: 20 },
    { enabled: !!institucion?.id },
  );
  const [redId, setRedId] = useState(null);
  const red = redes.filas.find((r) => r.id === redId) || redes.filas[0];

  /*
   * La pestaña inicial depende de lo que este establecimiento hace.
   *
   * Un hospital chico deriva y no recibe: abrirlo siempre en «Nos derivan» lo
   * dejaba mirando una pantalla vacía, que es justo su caso normal y no una
   * excepción. Se abre donde hay algo que ver, y sólo se decide una vez —si
   * después la persona cambia de pestaña, se respeta—.
   */
  /*
   * Se cuentan los ABIERTOS: es lo que requiere una decisión, y es el número
   * que va en la pestaña. Con el total del histórico, un hospital con años de
   * traslados resueltos mostraría «412» al lado de «Nos derivan» y no diría
   * nada sobre si hay algo que responder ahora.
   */
  const comun = { abiertos: true, institucion: institucion?.id, pageSize: 1 };
  const entrantes = useLista("traslados", { ...comun, lado: "entrantes" }, VIVA);
  const salientes = useLista("traslados", { ...comun, lado: "salientes" }, VIVA);
  useEffect(() => {
    if (tab !== null || entrantes.isLoading || salientes.isLoading) return;
    setTab(entrantes.total > 0 || salientes.total === 0 ? "entrantes" : "salientes");
  }, [tab, entrantes.isLoading, entrantes.total, salientes.isLoading, salientes.total]);

  const TABS = [
    { key: "entrantes", label: "Nos derivan", cuenta: entrantes.total },
    { key: "salientes", label: "Derivamos", cuenta: salientes.total },
    { key: "panorama", label: "Panorama de la red" },
  ];

  if (!institucion?.id || redes.isLoading) return <Cargando />;
  if (redes.error) {
    return <div className="p-[30px]"><EstadoError error={redes.error} onReintentar={redes.refetch} /></div>;
  }
  if (!red) {
    return (
      <div className="p-lg sm:p-[26px] lg:px-[30px]">
        <EstadoVacio
          titulo="Este establecimiento no está en ninguna red"
          detalle="Una red define a qué otros establecimientos se les puede derivar un paciente. Se crea desde Administración."
          icono="map"
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-lg p-lg sm:p-[26px] lg:px-[30px]">
      <section className="flex flex-wrap items-center gap-lg rounded-lg border border-borde bg-superficie px-xl py-lg">
        <span className="flex size-11 shrink-0 items-center justify-center rounded-md bg-nodo-derivar-tint text-nodo-derivar-sol">
          <Icon name="map" size={22} />
        </span>
        <div className="min-w-40 flex-1">
          <h2 className="text-xl font-bold">Red de establecimientos</h2>
          <p className="text-base text-texto-debil">
            {red.nombre} · {red.instituciones_detalle?.length || 0} establecimientos
          </p>
        </div>
        {/* Con más de una red hay que poder elegir: la ocupación de la red por
            la que se va a derivar este paciente no se puede mirar si la pantalla
            se queda siempre con la primera por orden alfabético. */}
        {redes.filas.length > 1 && (
          <Select value={red.id} onChange={(e) => setRedId(Number(e.target.value))}
                  aria-label="Red" className="w-auto">
            {redes.filas.map((r) => <option key={r.id} value={r.id}>{r.nombre}</option>)}
          </Select>
        )}
      </section>

      <Tabs tabs={TABS} valor={tab} onChange={setTab} />

      {tab === null ? (
        <Skeleton className="h-64" />
      ) : tab === "panorama" ? (
        <Panorama red={red} institucion={institucion} />
      ) : (
        <Lista lado={tab} institucion={institucion} />
      )}
    </div>
  );
}

function Lista({ lado, institucion }) {
  const toast = useToast();
  const navigate = useNavigate();
  const [respondiendo, setRespondiendo] = useState(null);
  const [confirmando, setConfirmando] = useState(null);

  /*
   * Los abiertos y los resueltos se piden POR SEPARADO.
   *
   * Traer las primeras 100 filas del histórico y partirlas en el cliente
   * escondía justamente lo que esta pantalla existe para resolver: como
   * `-urgente` ordena primero, un hospital de referencia con 100 traslados
   * urgentes acumulados dejaba de ver cualquier pedido no urgente, incluido uno
   * de hace diez minutos, sin ninguna señal de que faltaban filas. Del otro
   * lado hay un paciente esperando una respuesta que no iba a llegar.
   *
   * Y entre los abiertos, el que espera hace MÁS tiempo va primero. Es una cola
   * de servicio y se atiende de arriba para abajo: con el más nuevo arriba,
   * quien abre «Nos derivan» contesta los pedidos frescos y el paciente que hace
   * cuatro horas espera una cama en otra guardia queda último o abajo del
   * pliegue. Es el mismo orden que la otra cola de la app (`ItemFila`: urgentes
   * primero y después por llegada ascendente).
   */
  const comun = { lado, institucion: institucion?.id };
  const abiertos = useLista(
    "traslados",
    { ...comun, abiertos: true, ordering: "-urgente,solicitado_at", pageSize: 200 },
    VIVA,
  );
  const resueltos = useLista(
    "traslados", { ...comun, abiertos: false, ordering: "-solicitado_at", pageSize: 20 },
  );

  const accion = useAccion(
    ({ id, nombre, cuerpo }) => api.post(`/traslados/${id}/${nombre}/`,
                                         { institucion: institucion?.id, ...(cuerpo || {}) }),
    {
      onSuccess: (_, { ok }) => {
        toast.ok(ok);
        abiertos.refetch();
        resueltos.refetch();
        setRespondiendo(null);
        setConfirmando(null);
      },
      onError: (e) => toast.deError(e),
    },
  );

  if (abiertos.error) {
    return <EstadoError error={abiertos.error} onReintentar={abiertos.refetch} />;
  }
  if (abiertos.isLoading || resueltos.isLoading) return <Skeleton className="h-64" />;
  if (!abiertos.filas.length && !resueltos.filas.length) {
    return (
      <EstadoVacio
        titulo={lado === "entrantes" ? "No hay traslados hacia acá" : "No derivamos a nadie todavía"}
        detalle={
          lado === "entrantes"
            ? "Cuando otro establecimiento pida trasladar un paciente, aparece acá."
            : "Se pide desde el caso del paciente, en «Derivar a otro establecimiento»."
        }
        icono="map"
      />
    );
  }

  /*
   * Lo que espera una decisión, aparte de lo que ya está viajando.
   *
   * En una sola lista ordenada por fecha de pedido, las filas que hay que
   * responder quedaban intercaladas con ambulancias en la calle: la que abre la
   * pantalla tiene que barrer entre medio para encontrar qué contestar.
   */
  const esperan = abiertos.filas.filter((t) => t.estado === "solicitado");
  const enViaje = abiertos.filas.filter((t) => t.estado !== "solicitado");
  const cerrados = resueltos.filas;
  const fila = (t, acciones) => (
    <Fila key={t.id} t={t} accion={accion} navigate={navigate} institucion={institucion}
          {...(acciones
            ? { onResponder: () => setRespondiendo(t),
                onConfirmar: (c) => setConfirmando({ ...c, t }) }
            : {})} />
  );

  return (
    <div className="flex flex-col gap-lg">
      {esperan.length > 0 && (
        <Seccion
          titulo="Esperan respuesta"
          extra={<Badge tone={esperan.some((t) => masDe(t.solicitado_at, DEMORA_MIN))
                                ? "error" : "amber"}>{esperan.length}</Badge>}
        >
          {esperan.map((t) => fila(t, true))}
        </Seccion>
      )}

      {enViaje.length > 0 && (
        <Seccion titulo="En viaje" extra={<Badge tone="info">{enViaje.length}</Badge>}>
          {enViaje.map((t) => fila(t, true))}
        </Seccion>
      )}

      {cerrados.length > 0 && (
        <Seccion
          titulo="Resueltos"
          extra={resueltos.total > cerrados.length && (
            <span className="text-sm text-texto-tenue">
              últimos {cerrados.length} de {resueltos.total}
            </span>
          )}
        >
          {cerrados.map((t) => fila(t, false))}
        </Seccion>
      )}

      {respondiendo && (
        <ResponderModal
          t={respondiendo}
          accion={accion}
          onClose={() => setRespondiendo(null)}
        />
      )}

      {confirmando && (
        <ConfirmarModal
          {...confirmando}
          accion={accion}
          onClose={() => setConfirmando(null)}
        />
      )}
    </div>
  );
}

function Seccion({ titulo, extra, children }) {
  return (
    <section className="overflow-hidden rounded-lg border border-borde bg-superficie">
      <header className="flex items-center gap-2 border-b border-division px-xl py-lg">
        <h3 className="flex-1 text-lg font-bold">{titulo}</h3>
        {extra}
      </header>
      <ul className="divide-y divide-division">{children}</ul>
    </section>
  );
}

function Fila({ t, accion, navigate, institucion, onResponder, onConfirmar }) {
  const est = ESTADOS[t.estado] || { label: t.estado_display, tone: "gray" };
  const ocupado = accion.isPending;
  // Pasado el umbral, la chapa lo dice. Antes esto vivía sólo en el «hace 4 h»
  // en gris chico del borde derecho, que es exactamente lo que nadie mira: un
  // pedido sin responder es un paciente esperando en otra guardia, y un
  // «Aceptado» que no sale es una cama comprometida por alguien que no llega.
  const tarde =
    (t.estado === "solicitado" && masDe(t.solicitado_at, DEMORA_MIN)) ||
    (t.estado === "aceptado" && masDe(t.resuelto_at, DEMORA_MIN));
  // El caso propio: el del otro lado no se puede abrir, y ofrecerlo sería
  // prometer algo que el servidor va a rechazar.
  const miCaso = t.soy_origen ? t.caso_origen : t.caso_destino;
  const { texto, ts } = reloj(t);
  // Cuando el paciente viene a otro de mis establecimientos, decir a cuál: en
  // «Nos derivan» no había forma de saber a qué efector propio llega.
  const otroLado = t.soy_origen
    ? `a ${t.destino_nombre}`
    : `desde ${t.origen_nombre}${t.destino_nombre !== institucion?.nombre ? ` → ${t.destino_nombre}` : ""}`;

  return (
    <li className="flex flex-wrap items-center gap-x-md gap-y-2 px-xl py-3.5">
      {t.urgente && <Badge tone="error">urgente</Badge>}
      {/* Ancho completo hasta `sm`: siendo el único ítem que encoge, en un
          celular cedía todo el espacio a la chapa de estado y a los botones y
          quedaban cuatro filas de «Luis …» indistinguibles, cada una con su
          botón azul. No se puede aceptar un traslado sin saber de quién es. */}
      <span className="w-full min-w-0 sm:w-auto sm:flex-1">
        <span className="block truncate text-md font-semibold">{t.paciente}</span>
        <span className="block text-sm text-texto-tenue sm:truncate">
          {otroLado}
          {" · "}{t.motivo_display}
          {t.area_destino_nombre && ` · ${t.area_destino_nombre}`}
          {t.estado === "en_camino" && t.movil && ` · ${t.movil}`}
          {t.estado === "aceptado" && tarde && " · todavía sin salir"}
        </span>
        {/* El motivo es lo que dice si insistir, buscar otro o esperar: vale
            igual para el rechazo, para la baja del origen y para el que no
            llegó. Sin él, del otro lado sólo queda una chapa gris. */}
        {["rechazado", "cancelado", "fallido"].includes(t.estado) && t.respuesta && (
          <span className="mt-0.5 block text-sm text-danger">{t.respuesta}</span>
        )}
      </span>

      <span className="whitespace-nowrap text-right text-sm text-texto-tenue">
        <Badge tone={tarde ? "error" : est.tone}>{est.label}</Badge>
        <span className={cn("mt-0.5 block", tarde && "font-semibold text-danger")}
              title={`Pedido el ${fechaHora(t.solicitado_at)}`}>
          {texto} {antiguedad(ts)}
        </span>
      </span>

      <div className="flex flex-wrap gap-1.5">
        {miCaso && (
          <Button size="sm" variant="secondary" onClick={() => navigate(`/casos/${miCaso}`)}>
            Ver caso
          </Button>
        )}
        {/* Cada lado ve sólo lo que le toca hacer. */}
        {!t.soy_origen && t.estado === "solicitado" && (
          <Button size="sm" disabled={ocupado} onClick={onResponder}>Responder</Button>
        )}
        {/* «Llegó» cierra el caso del otro hospital como DERIVADO y no se
            puede deshacer: sobre un traslado que todavía no salió, un clic de
            más lo saca de su bandeja con el paciente aún en la camilla. */}
        {!t.soy_origen && (t.estado === "aceptado" || t.estado === "en_camino") && (
          <Button size="sm" disabled={ocupado} onClick={() => onConfirmar({
            nombre: "recibido",
            titulo: "¿Llegó el paciente?",
            confirmar: "Sí, llegó",
            ok: "Paciente recibido",
            cuerpo: (
              <>
                Se cierra el caso de <strong>{t.origen_nombre}</strong> y {t.paciente} pasa a ser
                responsabilidad de este establecimiento.
                {t.estado === "aceptado" &&
                  " Ojo: todavía no registraron la salida de la ambulancia."}
              </>
            ),
          })}>
            Llegó
          </Button>
        )}
        {t.soy_origen && t.estado === "aceptado" && (
          <Button size="sm" disabled={ocupado} onClick={() => onConfirmar({
            nombre: "en-camino",
            titulo: "Salió la ambulancia",
            confirmar: "Registrar salida",
            ok: "Traslado en camino",
            // El móvil es lo que pregunta el que espera al paciente, y el campo
            // quedaba vacío para siempre porque nadie lo pedía.
            campo: { clave: "movil", label: "Móvil / ambulancia",
                     placeholder: "Ej.: Móvil 3", requerido: false },
            cuerpo: <>Se le avisa a <strong>{t.destino_nombre}</strong> que {t.paciente} salió.</>,
          })}>
            Salió
          </Button>
        )}
        {t.soy_origen && t.estado === "solicitado" && (
          <Button size="sm" variant="secondary" disabled={ocupado} onClick={() => onConfirmar({
            nombre: "cancelar",
            titulo: "Cancelar el pedido de traslado",
            confirmar: "Cancelar el pedido",
            peligroso: true,
            ok: "Traslado cancelado",
            campo: { clave: "motivo", label: "Motivo",
                     placeholder: "Ej.: mejoró y no necesita derivarse", requerido: true },
            cuerpo: (
              <>
                <strong>{t.destino_nombre}</strong> ya puede tener una cama reservada para
                {" "}{t.paciente}. Se le avisa con el motivo.
              </>
            ),
          })}>
            Cancelar
          </Button>
        )}
        {/* La salida para el traslado que sale mal. Sin ella el caso de origen
            queda congelado esperando a alguien que no va a llegar. */}
        {(t.estado === "aceptado" || t.estado === "en_camino") && (
          <Button size="sm" variant="secondary" disabled={ocupado} onClick={() => onConfirmar({
            nombre: "no-llego",
            titulo: "El paciente no llegó",
            confirmar: "Registrar",
            peligroso: true,
            ok: "Traslado no concretado",
            campo: { clave: "motivo", label: "Qué pasó",
                     placeholder: "Ej.: falleció en el traslado / lo retiró la familia",
                     requerido: true },
            cuerpo: (
              <>
                Se cierra el traslado, se cancela el caso abierto en
                {" "}<strong>{t.destino_nombre}</strong> y el caso de {t.origen_nombre} vuelve a
                poder continuar.
              </>
            ),
          })}>
            No llegó
          </Button>
        )}
      </div>
    </li>
  );
}

/**
 * Confirmación de los pasos que no se pueden deshacer, con el dato que el
 * backend ya acepta y la pantalla nunca pedía (el motivo, el móvil).
 *
 * «Cancelar» disparaba de una y con el cuerpo vacío: del otro lado había una
 * guardia con una cama reservada que se enteraba —si se enteraba— de una chapa
 * gris sin texto.
 */
function ConfirmarModal({ t, nombre, titulo, cuerpo, confirmar, ok, campo, peligroso, accion, onClose }) {
  const [valor, setValor] = useState("");
  const falta = campo?.requerido && !valor.trim();
  const disparar = () => accion.mutate({
    id: t.id, nombre, ok, cuerpo: campo ? { [campo.clave]: valor.trim() } : {},
  });

  // Los tres pasos que necesitan un dato usan `Modal` y no `ConfirmDialog`: el
  // motivo es obligatorio y el confirmar tiene que quedar deshabilitado hasta
  // que esté escrito, que es lo único que `ConfirmDialog` no puede hacer sin
  // que su botón se lea «…». El resto —dos botones, el peligroso en danger, el
  // que confirma diciendo QUÉ hace— sigue igual que ahí.
  if (!campo) {
    return (
      <ConfirmDialog title={titulo} confirmar={confirmar} peligroso={peligroso}
                     cargando={accion.isPending} onClose={onClose} onConfirmar={disparar}>
        {cuerpo}
      </ConfirmDialog>
    );
  }

  return (
    <Modal
      title={titulo}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={accion.isPending}>Volver</Button>
          <Button variant={peligroso ? "danger" : "primary"}
                  disabled={accion.isPending || falta} onClick={disparar}>
            {confirmar}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3 text-md text-texto-suave">
        <p>{cuerpo}</p>
        <Field
          label={campo.label}
          hint={campo.requerido ? "Del otro lado, esto es lo único que explica qué pasó." : undefined}
        >
          <Input value={valor} onChange={(e) => setValor(e.target.value)}
                 placeholder={campo.placeholder} autoFocus />
        </Field>
      </div>
    </Modal>
  );
}

/** Aceptar (eligiendo área) o rechazar (con motivo). */
function ResponderModal({ t, accion, onClose }) {
  const { institucion } = useInstitucion();
  const [area, setArea] = useState(t.area_destino || "");
  const [motivo, setMotivo] = useState("");

  /*
   * Sólo las áreas que pueden recibir el caso: `aceptar` lo rechaza si el área
   * no tiene una versión de flujo PUBLICADA, y el error llegaba como toast rojo
   * después de apretar «Aceptar», sin decir qué área sí sirve, con el traslado
   * todavía en «Esperando respuesta». En un establecimiento recién configurado
   * ése es el camino normal, no la excepción. Misma regla que en el caso.
   */
  const flujos = useLista("flujos", { institucion: institucion?.id, pageSize: 100 });
  const areas = [];
  const vistas = new Set();
  for (const f of flujos.filas) {
    const publicado = (f.versiones || []).some((v) => v.estado === "publicada");
    if (publicado && f.area && !vistas.has(f.area)) {
      vistas.add(f.area);
      areas.push({ id: f.area, nombre: f.area_nombre });
    }
  }

  return (
    <Modal
      title={`Traslado desde ${t.origen_nombre}`}
      onClose={onClose}
      footer={
        <>
          {/* Rechazar es una acción legítima, no un fracaso: un hospital que no
              puede recibir tiene que poder decirlo. Va en secundario porque
              aceptar es lo esperable, no porque rechazar esté mal. */}
          <Button
            variant="secondary"
            disabled={accion.isPending || !motivo.trim()}
            onClick={() => accion.mutate({
              id: t.id, nombre: "rechazar", cuerpo: { motivo },
              ok: "Traslado rechazado · se avisó al origen",
            })}
          >
            Rechazar
          </Button>
          <Button
            disabled={accion.isPending || !area}
            onClick={() => accion.mutate({
              id: t.id, nombre: "aceptar", cuerpo: { area_destino: Number(area) },
              ok: "Traslado aceptado · se abrió el caso",
            })}
          >
            Aceptar
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <div className="rounded-md bg-superficie-2 p-3">
          <div className="text-md font-semibold">{t.paciente}</div>
          <div className="text-sm text-texto-tenue">
            Documento {t.documento || "—"} · {t.motivo_display}
            {t.urgente && " · URGENTE"}
          </div>
          {t.detalle && <p className="mt-2 text-base text-texto-suave">{t.detalle}</p>}
        </div>

        <Field
          label="Área que lo recibe"
          hint={
            !flujos.isLoading && areas.length === 0
              ? "Ningún área de este establecimiento tiene un flujo publicado para recibir casos: hasta que lo haya, sólo se puede rechazar."
              : "Se abre un caso en el flujo publicado de esa área."
          }
        >
          <Select value={area} onChange={(e) => setArea(e.target.value)}>
            <option value="">Elegir…</option>
            {areas.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
          </Select>
        </Field>

        <Field
          label="Si no se puede recibir, el motivo"
          hint="Sin motivo, el otro hospital no sabe si insistir, buscar otro o esperar."
        >
          <Textarea value={motivo} onChange={(e) => setMotivo(e.target.value)}
                    placeholder="Ej.: no hay camas de UTI disponibles" />
        </Field>
      </div>
    </Modal>
  );
}

/**
 * Panorama de la red: cada establecimiento, uno debajo del otro, con los mismos
 * indicadores.
 *
 * Comparables es el punto. Una región mira esto para decidir a dónde mandar
 * recursos, y si cada establecimiento contara distinto la comparación mentiría.
 * Por eso las columnas son las mismas para todos, incluso cuando alguna no
 * aplica —un efector sin internación muestra «sin camas», no un 0 % que se
 * confunde con «vacío»—.
 */
function Panorama({ red, institucion }) {
  const [dias, setDias] = useState(30);
  const q = useQuery({
    queryKey: ["tablero-red", red.id, dias],
    queryFn: () => api.get(`/redes/${red.id}/tablero/?dias=${dias}`),
  });

  if (q.isLoading) return <Skeleton className="h-64" />;
  if (q.error) return <EstadoError error={q.error} onReintentar={q.refetch} />;

  const { establecimientos = [], totales = {}, saturados = [] } = q.data || {};

  return (
    <div className="flex flex-col gap-lg">
      {saturados.length > 0 && (
        <div className="flex items-start gap-2 rounded-md bg-badge-error-bg px-3.5 py-3 text-md text-badge-error-fg">
          <Icon name="alert" size={16} className="mt-0.5 flex-none" />
          <span>
            {saturados.length === 1 ? "Está saturado" : "Están saturados"}:{" "}
            <strong>{saturados.join(", ")}</strong>. Conviene derivar a otro lado.
          </span>
        </div>
      )}

      <section className="flex flex-wrap items-center gap-lg rounded-lg border border-borde bg-superficie px-xl py-lg">
        <div className="flex flex-1 flex-wrap gap-x-8 gap-y-3">
          <Cifra n={totales.casos_activos} l="casos activos" />
          <Cifra n={totales.camas_libres} l={`camas libres de ${totales.camas_operativas ?? 0}`} />
          <Cifra n={totales.traslados} l={`traslados en ${dias} días`} />
          {/* «Sin responder» no se recorta por el período: es el estado de ahora.
              Y con la antigüedad del más viejo al lado, que es el dato que
              decide si alguien levanta el teléfono. */}
          <Cifra
            n={totales.pendientes}
            l={totales.pendiente_mas_viejo
              ? `sin responder · el más viejo hace ${antiguedad(totales.pendiente_mas_viejo)}`
              : "sin responder"}
            tono={totales.pendientes > 0 ? "text-badge-amber-fg" : undefined}
          />
          <Cifra n={`${totales.rechazo_pct ?? 0}%`} l="rechazados" />
          <Cifra n={totales.viaje_prom_min ? `${totales.viaje_prom_min}′` : "—"} l="viaje promedio" />
        </div>
        <Select value={dias} onChange={(e) => setDias(Number(e.target.value))}
                aria-label="Período" className="w-auto">
          <option value={7}>7 días</option>
          <option value={30}>30 días</option>
          <option value={90}>90 días</option>
        </Select>
      </section>

      <section className="overflow-x-auto rounded-lg border border-borde bg-superficie">
        <table className="w-full min-w-[54rem] text-md">
          <thead>
            <tr className="border-b border-division bg-superficie-2 text-micro font-bold tracking-wide text-texto-tenue">
              <th className="px-xl py-2.5 text-left">ESTABLECIMIENTO</th>
              <th className="px-3 py-2.5 text-right">ACTIVOS</th>
              <th className="px-3 py-2.5 text-right">URGENTES</th>
              {/* «CAMAS 15/27» no decía qué eran los dos números y la fracción
                  invitaba a restar: 12 ocupadas contra el 33 % de la columna de
                  al lado, dos lecturas distintas del mismo hecho pegadas una a
                  la otra. La diferencia son las camas en higiene, que además son
                  las que se liberan con un llamado a limpieza. */}
              <th className="px-3 py-2.5 text-right">CAMAS LIBRES</th>
              <th className="px-3 py-2.5 text-right">OCUPACIÓN</th>
              <th className="px-3 py-2.5 text-right">DERIVÓ</th>
              <th className="px-3 py-2.5 text-right">RECIBIÓ</th>
              <th className="px-3 py-2.5 text-right">RESPONDE EN</th>
              <th className="px-xl py-2.5 text-right">RECHAZÓ</th>
            </tr>
          </thead>
          <tbody>
            {establecimientos.map((e) => (
              <tr key={e.id} className="border-b border-division last:border-b-0">
                <td className="px-xl py-3 font-semibold">
                  {e.nombre}
                  {e.id === institucion?.id && (
                    <span className="font-normal text-texto-tenue"> · acá</span>
                  )}
                </td>
                <td className="px-3 py-3 text-right tabular-nums">{e.casos_activos}</td>
                <td className={cn("px-3 py-3 text-right tabular-nums",
                                  e.urgentes > 0 && "font-bold text-danger")}>
                  {e.urgentes}
                </td>
                <td className="px-3 py-3 text-right tabular-nums text-texto-tenue">
                  {e.camas_operativas ? (
                    <>
                      <span className="font-semibold text-texto-fuerte">{e.camas_libres}</span>
                      {` de ${e.camas_operativas}`}
                      {e.camas_higiene > 0 && (
                        <span className="block text-xs">+{e.camas_higiene} en higiene</span>
                      )}
                    </>
                  ) : "—"}
                </td>
                <td className="px-3 py-3 text-right tabular-nums">
                  {e.camas_operativas ? (
                    <span className={cn("font-bold",
                      e.ocupacion >= 90 ? "text-danger"
                        : e.ocupacion >= 75 ? "text-badge-amber-fg" : "text-texto-fuerte")}>
                      {e.ocupacion}%
                    </span>
                  ) : (
                    <span className="text-texto-tenue">sin camas</span>
                  )}
                </td>
                <td className="px-3 py-3 text-right tabular-nums">{e.derivo}</td>
                <td className="px-3 py-3 text-right tabular-nums">
                  {e.recibio}
                  {e.pendientes > 0 && (
                    <span className="ml-1 text-badge-amber-fg">({e.pendientes} sin resp.)</span>
                  )}
                  {e.pendiente_mas_viejo && (
                    <span className="block text-xs text-badge-amber-fg">
                      el más viejo hace {antiguedad(e.pendiente_mas_viejo)}
                    </span>
                  )}
                </td>
                <td className="px-3 py-3 text-right tabular-nums text-texto-suave">
                  {e.demora_respuesta_min != null ? `${e.demora_respuesta_min}′` : "—"}
                </td>
                <td className="px-xl py-3 text-right tabular-nums">{e.rechazados}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function Cifra({ n, l, tono }) {
  return (
    <div>
      <div className={cn("text-lg font-extrabold leading-none tabular-nums", tono)}>{n ?? "—"}</div>
      <div className="mt-0.5 text-xs text-texto-tenue">{l}</div>
    </div>
  );
}

function Cargando() {
  return (
    <div className="flex flex-col gap-lg p-lg sm:p-[26px] lg:px-[30px]" role="status" aria-label="Cargando red…">
      <Skeleton className="h-[78px]" />
      <Skeleton className="h-12" />
      <Skeleton className="h-80" />
    </div>
  );
}
