import { useState } from "react";

import { api } from "@/api/client";
import { useAccion, useDetalle, useLista } from "@/api/queries";
import { useAuth } from "@/auth/AuthContext";
import { Icon } from "@/components/icons";
import { Badge, Button, Card, Field, Input, Modal, Mono, Textarea } from "@/components/ui";
import { EstadoError, EstadoVacio, SkeletonTabla } from "@/components/ui/estados";

import { useToast } from "@/components/ui/toast";
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
export function AlergiaEnCabecera({ hc, listo }) {
  if (!listo) return null;
  return (
    <div className={cn("mb-5 flex flex-wrap items-center gap-x-2 rounded-lg border px-4 py-2.5 text-base",
      hc?.alergias ? "border-badge-error-fg/25 bg-badge-error-bg" : "border-borde bg-superficie")}>
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
export function Antecedentes({ hc, onEditar }) {
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

export function AntecedentesModal({ hc, onClose }) {
  const toast = useToast();
  const [alergias, setAlergias] = useState(hc?.alergias || "");
  const [condiciones, setCondiciones] = useState(hc?.condiciones || "");

  const guardar = useAccion(
    () => api.patch(`/historias-clinicas/${hc.id}/`, { alergias, condiciones }),
    {
      // El listado de pacientes muestra la columna «Alergias» derivada de acá.
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

export function NuevaAtencionModal({ ciudadanoId, pacienteNombre, hcId, puedeFirmar, onClose }) {
  const toast = useToast();
  const { user } = useAuth();
  const [titulo, setTitulo] = useState("");
  const [contenido, setContenido] = useState("");
  const [confirmandoFirma, setConfirmandoFirma] = useState(false);

  const guardar = useAccion(
    async (firmar) => {
      // El paciente puede no tener historia todavía: se crea al vuelo.
      let historia = hcId;
      if (!historia) {
        const hc = await api.post("/historias-clinicas/", { ciudadano: ciudadanoId });
        historia = hc.id;
      }
      return api.post("/entradas-historia/", { historia, titulo, contenido, firmada: firmar });
    },
    {
      onSuccess: (_entrada, firmar) => { toast.ok(firmar ? "Atención firmada." : "Borrador guardado."); onClose(); },
      // Firmar exige matrícula (regla del motor): el error del backend explica
      // exactamente eso, así que se muestra tal cual en vez de uno genérico.
      onError: (e) => toast.deError(e, "No se pudo registrar la atención."),
    },
  );

  return (
    <Modal
      title={confirmandoFirma ? "Confirmar firma de la atención" : "Registrar atención"}
      onClose={confirmandoFirma ? () => setConfirmandoFirma(false) : onClose}
      width={560}
      footer={
        <>
          <Button variant="secondary" disabled={guardar.isPending} onClick={confirmandoFirma ? () => setConfirmandoFirma(false) : onClose}>
            {confirmandoFirma ? "Volver a editar" : "Cancelar"}
          </Button>
          {confirmandoFirma ? <Button disabled={guardar.isPending} onClick={() => guardar.mutate(true)}>
            {guardar.isPending ? "Firmando…" : "Firmar y registrar"}
          </Button> : <>
            <Button variant="secondary" disabled={guardar.isPending || !titulo.trim() || !contenido.trim()} onClick={() => guardar.mutate(false)}>Guardar borrador</Button>
            {puedeFirmar && <Button disabled={guardar.isPending || !titulo.trim() || !contenido.trim()} onClick={() => setConfirmandoFirma(true)}>Firmar y registrar</Button>}
          </>}
        </>
      }
    >
      {confirmandoFirma ? <div className="space-y-2 text-md text-texto-suave">
        <p>Paciente: <strong>{pacienteNombre || `#${ciudadanoId}`}</strong></p>
        <p>Firma: <strong>{user?.nombre_completo || user?.email}</strong></p>
        <p>Entrada: <strong>{titulo.trim()}</strong></p>
        <p>Al firmar quedará sellada y ya no podrás editarla; las correcciones requerirán una entrada nueva.</p>
      </div> :
      <div className="flex flex-col gap-3.5">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Tipo de entrada *">
            <Input value={titulo} onChange={(e) => setTitulo(e.target.value)} autoFocus placeholder="Evolución, control…" />
          </Field>
          <Field label="Fecha y hora">
            <Input value="Se asigna al guardar" readOnly />
          </Field>
        </div>
        <Field label="Evolución *">
          <Textarea value={contenido} onChange={(e) => setContenido(e.target.value)} />
        </Field>
        {/* Se dice ANTES de intentar, no después del error: quien no puede
            firmar igual necesita dejar el asiento, y destildar es el camino. */}
        <div className="text-sm text-texto-debil">
          El borrador se puede editar. Al firmar, la entrada queda sellada a tu
          nombre y matrícula; las correcciones se agregan como una nueva entrada.
        </div>
      </div>
      }
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
export function Integridad({ hcId }) {
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
export function Accesos({ ciudadanoId }) {
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

export function Evolucion({ entradas, puedeFirmar, pacienteNombre }) {
  // `null` = ninguno abierto. Guarda la entrada y qué se va a hacer con ella.
  const [editando, setEditando] = useState(null);
  const [firmando, setFirmando] = useState(null);

  if (!entradas.length) {
    return <EstadoVacio titulo="Sin entradas de evolución" detalle="Registrá una atención para empezar la historia." />;
  }
  return (
    <div className="flex flex-col gap-3">
      {entradas.map((e) => (
        <Card key={e.id} id={`entrada-${e.id}`} className="p-[18px]">
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
              <Button variant="secondary" className="text-sm" onClick={() => setFirmando(e)}>
                  Firmar
                </Button>
              )}
            </div>
          )}
        </Card>
      ))}

      {editando && <EditarBorradorModal entrada={editando} onClose={() => setEditando(null)} />}
      {firmando && <FirmarBorradorModal entrada={firmando} pacienteNombre={pacienteNombre} onClose={() => setFirmando(null)} />}
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

function FirmarBorradorModal({ entrada, pacienteNombre, onClose }) {
  const toast = useToast();
  const { user } = useAuth();

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
        <p className="text-md text-texto-suave">Paciente: <strong>{pacienteNombre}</strong> · Firma: <strong>{user?.nombre_completo || user?.email}</strong></p>
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

export function Estudios({ estudios }) {
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

export function Recetas({ recetas }) {
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
