import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useDetalle, useLista } from "@/api/queries";
import { Icon } from "@/components/icons";
import { PageHeader } from "@/components/Shell";
import { Badge, Button, Card, Checkbox, Field, Input, Mono, Select, Stepper, Textarea } from "@/components/ui";
import { EstadoError, Skeleton } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { casoId, fechaHora } from "@/lib/format";
import { cn } from "@/lib/cn";
import { estadoCaso, nombreNodo } from "@/lib/dominio";
import { CancelarModal, ReasignarModal } from "../Supervision";

// Orden conceptual del stepper de ejecución.
const PASOS = [
  { label: "Recibido", estados: ["recibido"] },
  { label: "En proceso", estados: ["en_evaluacion", "en_espera"] },
  { label: "Derivado", estados: ["derivado"] },
  { label: "Atendido", estados: ["atendido"] },
  { label: "Cerrado", estados: ["cerrado"] },
];
const pasoActual = (estado) => Math.max(0, PASOS.findIndex((p) => p.estados.includes(estado)));

export default function CasoDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();

  const q = useDetalle("casos", id);
  const caso = q.data;

  const hcQ = useLista(
    "historias-clinicas",
    { ciudadano: caso?.ciudadano },
    { enabled: !!caso?.ciudadano },
  );
  const hc = hcQ.filas[0] || null;

  // Todas las acciones del caso pasan por acá: una sola mutación que invalida las
  // listas (bandeja, fila, tablero) y el detalle. Antes cada acción recargaba a
  // mano y el error se mostraba en un div propio de la pantalla.
  const accion = useAccion((fn) => fn(), {
    invalida: ["lista", "detalle", "puesto"],
    onError: (e) => toast.deError(e),
  });
  const ejecutar = (fn, ok) => accion.mutate(fn, { onSuccess: () => ok && toast.ok(ok) });

  if (q.isLoading) return <CargandoCaso />;
  if (q.error) return <div className="p-8"><EstadoError error={q.error} onReintentar={q.refetch} /></div>;

  const est = estadoCaso[caso.estado] || { label: caso.estado_display, tone: "neutral" };
  const cerrado = ["cerrado", "cancelado"].includes(caso.estado);
  const cat = caso.nodo_tipo ? nombreNodo(caso.nodo_tipo) : null;

  return (
    <>
      <PageHeader subtitle={`${caso.flujo_titulo}${caso.ciudadano_nombre ? " · " + caso.ciudadano_nombre : ""}`} />

      {/* Dos columnas en pantalla ancha; apiladas debajo de `lg`, con la
          información del caso primero (es lo que se consulta en una tablet). */}
      <div className="grid items-start gap-lg px-lg pb-8 pt-lg lg:grid-cols-[1fr_20rem] lg:gap-xxl lg:px-8">
        <div className="flex flex-col gap-lg lg:order-1">
          <Card className="px-lg py-7 sm:px-8">
            <div className="overflow-x-auto">
              <Stepper steps={PASOS} current={pasoActual(caso.estado)} />
            </div>
            {caso.paso_actual && (
              <div className="mt-xl flex flex-wrap items-center gap-2.5 border-t border-division pt-lg">
                <span className="text-xs font-bold tracking-wide text-texto-tenue">PASO ACTUAL</span>
                {cat && <ChipNodo tipo={caso.nodo_tipo} />}
                <span className="text-lg font-bold">{caso.paso_actual}</span>
              </div>
            )}
          </Card>

          {hc && (hc.alergias || hc.condiciones) && <Antecedentes hc={hc} />}

          <PanelPaso
            caso={caso}
            cerrado={cerrado}
            ocupado={accion.isPending}
            ejecutar={ejecutar}
            hc={hc}
          />

          {caso.valores?.length > 0 && (
            <Card className="p-lg sm:p-xxl">
              <h3 className="text-lg font-bold">Datos cargados</h3>
              <dl className="mt-3 flex flex-col gap-2.5">
                {caso.valores.map((v) => (
                  <div key={v.id} className="flex justify-between gap-lg text-md">
                    <dt className="text-texto-debil">{v.campo_label}</dt>
                    <dd className="text-right font-medium text-texto-fuerte">{v.valor || "—"}</dd>
                  </div>
                ))}
              </dl>
            </Card>
          )}
        </div>

        <div className="flex flex-col gap-lg">
          <Card className="p-xl">
            <h3 className="mb-3.5 text-xs font-bold tracking-wide text-texto-tenue">INFORMACIÓN DEL CASO</h3>
            <dl className="flex flex-col gap-3">
              <Dato k="Caso" v={<Mono className="font-bold">{casoId(caso.id)}</Mono>} />
              <Dato k="Estado" v={<Badge tone={est.tone}>{est.label}</Badge>} />
              <Dato k="Paso actual" v={caso.paso_actual || "—"} />
              <Dato k="Flujo" v={caso.flujo_titulo} />
              <Dato k="Área actual" v={caso.area_nombre || "—"} />
              <Dato k="Responsable" v={caso.responsables?.length ? caso.responsables.map((g) => g.nombre).join(", ") : "Abierto a todos"} />
              <Dato k="Asignado a" v={caso.asignado_nombre || "Sin asignar"} />
              <Dato k="Ingreso" v={fechaHora(caso.creado)} />
              <Dato k="Prioridad" v={caso.prioridad_display} />
            </dl>
          </Card>

          {caso.puede_supervisar && !cerrado && (
            <PanelSupervision caso={caso} ejecutar={ejecutar} ocupado={accion.isPending} />
          )}

          {(caso.origen || caso.derivados?.length > 0) && (
            <Card className="p-xl">
              <h3 className="text-lg font-bold">Derivaciones</h3>
              <div className="mt-3 flex flex-col gap-2">
                {caso.origen && (
                  <button
                    onClick={() => navigate(`/casos/${caso.origen}`)}
                    className="rounded-md border border-division p-2.5 text-left hover:bg-superficie-2"
                  >
                    <span className="block text-xs text-texto-tenue">Originado desde</span>
                    <span className="block text-md font-semibold text-accent">
                      {casoId(caso.origen)} · {caso.origen_flujo}
                    </span>
                  </button>
                )}
                {(caso.derivados || []).map((d) => {
                  const e = estadoCaso[d.estado] || { label: d.estado, tone: "neutral" };
                  return (
                    <button
                      key={d.id}
                      onClick={() => navigate(`/casos/${d.id}`)}
                      className="flex items-center justify-between gap-2 rounded-md border border-division p-2.5 text-left hover:bg-superficie-2"
                    >
                      <span className="min-w-0">
                        <span className="block text-xs text-texto-tenue">Derivado a</span>
                        <span className="block truncate text-md font-semibold text-accent">
                          {casoId(d.id)} · {d.flujo_titulo}
                        </span>
                      </span>
                      <Badge tone={e.tone}>{e.label}</Badge>
                    </button>
                  );
                })}
              </div>
            </Card>
          )}

          <Card className="p-xl">
            <h3 className="text-lg font-bold">Trazabilidad</h3>
            <Timeline eventos={caso.eventos || []} />
          </Card>
        </div>
      </div>
    </>
  );
}

// --------------------------------------------------------------------------- //
// Piezas
// --------------------------------------------------------------------------- //
/**
 * Chip con la categoría del nodo (10 tipos, colores dinámicos).
 *
 * La etiqueta va en color de texto normal, no en el color de la categoría: esos
 * colores están pensados para bordes y rellenos del lienzo, no para llevar texto
 * —el rosa de «Atención» sobre su propio tinte da 3,56:1—. El color lo cargan el
 * punto y el borde, que es donde sí funciona.
 */
function ChipNodo({ tipo, className }) {
  const cat = nombreNodo(tipo);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-pill border px-2.5 py-[3px] text-sm font-semibold text-texto-medio",
        className,
      )}
      style={{
        background: `var(--color-nodo-${tipo}-tint)`,
        borderColor: `var(--color-nodo-${tipo}-bd)`,
      }}
    >
      <span className="size-1.5 rounded-sm" style={{ background: `var(--color-nodo-${tipo}-sol)` }} />
      {cat}
    </span>
  );
}

function Antecedentes({ hc }) {
  return (
    <Card className="overflow-hidden p-0">
      {/* Tono ámbar («prestá atención»), no los colores de categoría de nodo: los
          antecedentes no son un paso del flujo, y esa paleta no tiene variante
          oscura ni está pensada para llevar texto encima. */}
      <div className="flex items-center justify-between gap-2 border-b border-division bg-badge-amber-bg px-xl py-3.5">
        <span className="flex items-center gap-2 text-md font-bold text-badge-amber-fg">
          <Icon name="clipboard" size={17} /> Historia clínica · antecedentes
        </span>
        <span className="text-xs text-badge-amber-fg opacity-80">solo lectura</span>
      </div>
      <dl className="grid gap-3.5 px-xl py-lg sm:grid-cols-2">
        <Dato k="Alergias" v={<span className={hc.alergias ? "text-danger" : "text-texto-debil"}>{hc.alergias || "—"}</span>} />
        <Dato k="Condiciones" v={hc.condiciones || "—"} />
      </dl>
    </Card>
  );
}

function PanelSupervision({ caso, ejecutar, ocupado }) {
  const [modal, setModal] = useState(null);
  return (
    <Card className="p-xl">
      <h3 className="mb-3.5 text-xs font-bold tracking-wide text-texto-tenue">SUPERVISIÓN</h3>
      <div className="flex flex-col gap-3">
        <Field label="Prioridad">
          <Select
            value={caso.prioridad}
            disabled={ocupado}
            onChange={(e) => ejecutar(
              () => api.post(`/casos/${caso.id}/priorizar/`, { prioridad: e.target.value }),
              "Prioridad actualizada",
            )}
          >
            <option value="normal">Normal</option>
            <option value="alta">Alta</option>
            <option value="urgente">Urgente</option>
          </Select>
        </Field>
        <Button variant="secondary" disabled={ocupado} onClick={() => setModal("reasignar")}>Reasignar</Button>
        <Button variant="danger" disabled={ocupado} onClick={() => setModal("cancelar")}>Cancelar caso</Button>
      </div>
      {/* Los dos modales son los mismos de Supervisión: resuelven solos sus datos
          y su mutación, así que esta pantalla no repite la lógica. */}
      {modal === "reasignar" && <ReasignarModal caso={caso} onClose={() => setModal(null)} onDone={() => setModal(null)} />}
      {modal === "cancelar" && <CancelarModal caso={caso} onClose={() => setModal(null)} onDone={() => setModal(null)} />}
    </Card>
  );
}

function PanelPaso({ caso, cerrado, ocupado, ejecutar, hc }) {
  if (!caso.nodo_actual && !cerrado) {
    return (
      <Card className="p-lg sm:p-xxl">
        <h3 className="text-lg font-bold">Sin iniciar</h3>
        <p className="my-2 text-md text-texto-debil">
          El caso todavía no arrancó por el flujo. Iniciá para colocarlo en el primer paso.
        </p>
        <Button disabled={ocupado} onClick={() => ejecutar(() => api.post(`/casos/${caso.id}/iniciar/`), "Caso iniciado")}>
          {ocupado ? "Iniciando…" : "Iniciar caso"}
        </Button>
      </Card>
    );
  }

  if (cerrado) {
    return (
      <Card className="flex items-center gap-3 p-lg sm:p-xxl">
        <span className="flex size-9 items-center justify-center rounded-pill bg-badge-green-bg text-badge-green-fg">✓</span>
        <div>
          <div className="text-lg font-bold">Caso cerrado</div>
          <div className="text-md text-texto-debil">Este caso completó su recorrido.</div>
        </div>
      </Card>
    );
  }

  if (caso.esperando) {
    return (
      <Card className="p-lg sm:p-xxl">
        <CabeceraPaso tipo={caso.nodo_tipo} titulo={caso.paso_actual} />
        <p className="text-md text-texto-suave">
          El caso está <strong>esperando el resultado de un estudio</strong> derivado a otra área.
          Cuando el estudio se realice, el caso vuelve solo y vas a poder continuar la atención.
        </p>
      </Card>
    );
  }

  if (caso.responsables?.length > 0 && !caso.puede_tomar) {
    return (
      <Card className="p-lg sm:p-xxl">
        <CabeceraPaso tipo={caso.nodo_tipo} titulo={caso.paso_actual} />
        <p className="text-md text-texto-suave">
          Este paso lo realiza <strong>{caso.responsables.map((g) => g.nombre).join(", ")}</strong>.
          No integrás {caso.responsables.length === 1 ? "ese grupo" : "esos grupos"}, así que no podés ejecutarlo.
        </p>
      </Card>
    );
  }

  const tipo = caso.nodo_tipo;
  if (tipo === "atencion" && caso.nodo_con_fila && !caso.llamado) {
    return (
      <Card className="p-lg sm:p-xxl">
        <CabeceraPaso tipo="atencion" titulo={caso.paso_actual} />
        <p className="text-md text-texto-suave">
          El paciente está en la <strong>sala de espera</strong>. Será atendido cuando se lo llame
          desde un box, en la pantalla <strong>«Filas de espera»</strong>.
        </p>
      </Card>
    );
  }
  if (tipo === "form") return <PasoFormulario caso={caso} ocupado={ocupado} ejecutar={ejecutar} />;
  if (tipo === "atencion") return <PasoAtencion caso={caso} ocupado={ocupado} ejecutar={ejecutar} hc={hc} />;
  if (tipo === "espera") {
    return <PasoSimple caso={caso} ocupado={ocupado} ejecutar={ejecutar}
      texto="El caso está en la fila. Cuando sea llamado, continúa al siguiente paso." accion="Llamar y continuar" />;
  }
  if (tipo === "tiempo") {
    return <PasoSimple caso={caso} ocupado={ocupado} ejecutar={ejecutar}
      texto="El caso está en pausa hasta cumplir el tiempo. Reactivá para continuar." accion="Reactivar" />;
  }

  return (
    <Card className="p-lg sm:p-xxl">
      <h3 className="text-lg font-bold">{caso.paso_actual}</h3>
      <p className="mt-2 text-md text-texto-debil">Este paso no requiere una acción manual.</p>
    </Card>
  );
}

function CabeceraPaso({ tipo, titulo }) {
  const cat = nombreNodo(tipo);
  return (
    <div className="mb-lg flex items-center gap-2.5">
      <span
        className="flex size-8 shrink-0 items-center justify-center rounded-md border"
        style={{ background: `var(--color-nodo-${tipo}-tint)`, borderColor: `var(--color-nodo-${tipo}-bd)` }}
      >
        <span className="size-2.5 rounded-sm" style={{ background: `var(--color-nodo-${tipo}-sol)` }} />
      </span>
      <div>
        <div className="text-micro font-bold tracking-wide text-texto-tenue">{cat.toUpperCase()}</div>
        <div className="text-lg font-bold">{titulo}</div>
      </div>
    </div>
  );
}

function PasoFormulario({ caso, ocupado, ejecutar }) {
  const [valores, setValores] = useState({});
  const nodo = useDetalle("nodos", caso.nodo_actual);
  const form = useDetalle("formularios", nodo.data?.formulario, { enabled: !!nodo.data?.formulario });

  if (nodo.isLoading || (nodo.data?.formulario && form.isLoading)) {
    return <Card className="flex flex-col gap-3 p-lg sm:p-xxl">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14" />)}</Card>;
  }
  const campos = form.data?.campos || [];

  return (
    <Card className="p-lg sm:p-xxl">
      <CabeceraPaso tipo="form" titulo={caso.paso_actual} />
      {campos.length === 0 ? (
        <p className="text-md text-texto-debil">Este formulario no tiene campos definidos.</p>
      ) : (
        <div className="flex flex-col gap-3.5">
          {campos.map((c) => (
            <Field key={c.id} label={c.label + (c.requerido ? " *" : "")} hint={c.ayuda}>
              <CampoInput campo={c} value={valores[c.id] || ""} onChange={(v) => setValores((p) => ({ ...p, [c.id]: v }))} />
            </Field>
          ))}
        </div>
      )}
      <Button
        className="mt-xl"
        disabled={ocupado}
        onClick={() => ejecutar(() => api.post(`/casos/${caso.id}/avanzar/`, { valores }), "Paso completado")}
      >
        {ocupado ? "Guardando…" : "Completar y avanzar"}
      </Button>
    </Card>
  );
}

function CampoInput({ campo, value, onChange }) {
  if (campo.tipo === "texto_largo") return <Textarea value={value} onChange={(e) => onChange(e.target.value)} />;
  if (campo.tipo === "fecha") return <Input type="date" value={value} onChange={(e) => onChange(e.target.value)} />;
  if (campo.tipo === "seleccion_unica") {
    return (
      <Select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Seleccionar…</option>
        {(campo.opciones || []).map((o) => <option key={o} value={o}>{o}</option>)}
      </Select>
    );
  }
  if (campo.tipo === "archivo") return <CampoArchivo value={value} onChange={onChange} />;
  return <Input value={value} onChange={(e) => onChange(e.target.value)} />;
}

function CampoArchivo({ value, onChange }) {
  const toast = useToast();
  const subir = useAccion((file) => api.upload(file), {
    invalida: [],
    onError: (e) => toast.deError(e, "No se pudo subir el archivo."),
  });
  return (
    <div className="flex items-center gap-2.5">
      <input
        type="file"
        disabled={subir.isPending}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) subir.mutate(file, { onSuccess: (r) => onChange(r.nombre) });
        }}
        className="text-md file:mr-2 file:rounded-md file:border file:border-accent-100 file:bg-accent-50 file:px-2.5 file:py-1 file:text-base file:font-semibold file:text-accent"
      />
      {subir.isPending && <span className="text-sm text-texto-tenue">Subiendo…</span>}
      {value && !subir.isPending && <span className="text-base text-texto-suave">✓ {value}</span>}
    </div>
  );
}

function PasoAtencion({ caso, ocupado, ejecutar, hc }) {
  const toast = useToast();
  const realizandoEstudio = !!caso.estudio_tipo;
  const [titulo, setTitulo] = useState(caso.paso_actual || "");
  const [contenido, setContenido] = useState("");
  const [firmada, setFirmada] = useState(true);
  const [tipoEstudio, setTipoEstudio] = useState("");
  const [areaEstudio, setAreaEstudio] = useState("");
  const [detalleReceta, setDetalleReceta] = useState("");
  const [motivoIc, setMotivoIc] = useState("");
  const [areaIc, setAreaIc] = useState("");
  const [resultado, setResultado] = useState("");
  const [archivo, setArchivo] = useState("");

  const estudios = hc?.estudios || [];
  const recetas = hc?.recetas || [];

  // Áreas a las que se puede derivar: las que tienen flujo publicado derivable.
  const flujos = useLista("flujos", { institucion: caso.institucion, pageSize: 100 }, { enabled: !realizandoEstudio });
  const areasDestino = [];
  const vistas = new Set();
  for (const f of flujos.filas) {
    const pub = (f.versiones || []).some((v) => v.estado === "publicada");
    if (pub && f.origen_inicio !== "manual" && f.area && f.area !== caso.area_actual && !vistas.has(f.area)) {
      vistas.add(f.area);
      areasDestino.push({ id: f.area, nombre: f.area_nombre });
    }
  }

  // Rellamar no recarga el caso: es feedback liviano sobre la pantalla de la sala.
  const rellamar = useAccion(() => api.post(`/casos/${caso.id}/rellamar/`), {
    invalida: [],
    onError: (e) => toast.deError(e, "No se pudo rellamar."),
  });
  const [rellamos, setRellamos] = useState(0);

  return (
    <Card className="p-lg sm:p-xxl">
      <CabeceraPaso tipo="atencion" titulo={caso.paso_actual} />

      {caso.nodo_con_fila && caso.llamado && (
        <div className="mb-lg flex flex-wrap items-center gap-3 rounded-md border border-badge-amber-fg/25 bg-badge-amber-bg px-3.5 py-3">
          <Icon name="enter" size={18} className="shrink-0 text-badge-amber-fg" />
          <div className="min-w-40 flex-1 text-md text-badge-amber-fg">
            Paciente llamado{caso.llamado_box ? <> a <strong>{caso.llamado_box}</strong></> : ""}.
            {rellamos > 0
              ? <> Se rellamó {rellamos === 1 ? "una vez" : `${rellamos} veces`} — mirá la pantalla de la sala.</>
              : <> ¿No se presentó?</>}
          </div>
          <Button
            size="sm"
            variant="secondary"
            disabled={rellamar.isPending}
            onClick={() => rellamar.mutate(undefined, { onSuccess: () => setRellamos((n) => n + 1) })}
          >
            {rellamar.isPending ? "Rellamando…" : "Rellamar"}
          </Button>
        </div>
      )}

      {realizandoEstudio && (
        <p className="mb-3 text-base text-texto-debil">
          Estudio a realizar: <strong className="text-texto-medio">{caso.estudio_tipo}</strong>
        </p>
      )}

      <div className="flex flex-col gap-3.5">
        <Field label="Título de la atención">
          <Input value={titulo} onChange={(e) => setTitulo(e.target.value)} />
        </Field>
        <Field label={realizandoEstudio ? "Informe / observaciones" : "Evolución / observaciones"}>
          <Textarea value={contenido} onChange={(e) => setContenido(e.target.value)} placeholder="Lo que se asienta en la historia clínica…" />
        </Field>
        <Checkbox checked={firmada} onChange={(e) => setFirmada(e.target.checked)} label="Firmar la entrada" />
      </div>

      {realizandoEstudio ? (
        <div className="mt-xl flex flex-col gap-3.5 border-t border-division pt-lg">
          <Field label="Resultado del estudio">
            <Select value={resultado} onChange={(e) => setResultado(e.target.value)}>
              <option value="">— Sin especificar —</option>
              <option value="normal">Normal</option>
              <option value="alterado">Alterado</option>
            </Select>
          </Field>
          <Field label="Archivo del estudio (opcional)">
            <CampoArchivo value={archivo} onChange={setArchivo} />
          </Field>
        </div>
      ) : (
        <div className="mt-xl flex flex-col gap-lg border-t border-division pt-lg">
          <section>
            <h4 className="mb-2 text-base font-bold text-texto-suave">Solicitar estudio</h4>
            <div className="flex flex-wrap gap-2">
              <Input
                className="min-w-48 flex-1"
                value={tipoEstudio}
                onChange={(e) => setTipoEstudio(e.target.value)}
                placeholder="Ej.: Radiografía de tórax"
              />
              <Button
                variant="secondary"
                disabled={ocupado || !tipoEstudio.trim()}
                onClick={() => ejecutar(
                  () => api.post(`/casos/${caso.id}/estudio/`, {
                    tipo: tipoEstudio.trim(),
                    ...(areaEstudio ? { area_id: Number(areaEstudio) } : {}),
                  }),
                  "Estudio solicitado",
                )}
              >
                Solicitar
              </Button>
            </div>
            <Select className="mt-2" size="sm" aria-label="Destino del estudio" value={areaEstudio} onChange={(e) => setAreaEstudio(e.target.value)}>
              <option value="">Registrar en la HC (sin derivar)</option>
              {areasDestino.map((a) => (
                <option key={a.id} value={a.id}>Derivar a {a.nombre} (el caso espera la vuelta)</option>
              ))}
            </Select>
            {estudios.length > 0 && (
              <ul className="mt-2.5 flex flex-col gap-1.5">
                {estudios.map((e) => (
                  <li key={e.id} className="flex items-center justify-between gap-2.5 rounded-md border border-borde bg-superficie-2 px-3 py-1.5 text-md">
                    <span className="text-texto-medio">{e.tipo}{e.resultado_display ? ` · ${e.resultado_display}` : ""}</span>
                    <Badge tone={e.realizado ? "green" : "amber"}>{e.realizado ? "realizado" : "pendiente"}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <h4 className="mb-2 text-base font-bold text-texto-suave">Interconsulta a otra área</h4>
            <Input value={motivoIc} onChange={(e) => setMotivoIc(e.target.value)} placeholder="Motivo (ej.: descartar foco neurológico)" />
            <div className="mt-2 flex flex-wrap gap-2">
              <Select className="min-w-40 flex-1" size="sm" aria-label="Área de la interconsulta" value={areaIc} onChange={(e) => setAreaIc(e.target.value)}>
                <option value="">— Elegir área —</option>
                {areasDestino.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
              </Select>
              <Button
                variant="secondary"
                disabled={ocupado || !areaIc}
                onClick={() => ejecutar(
                  () => api.post(`/casos/${caso.id}/interconsulta/`, { area_id: Number(areaIc), motivo: motivoIc.trim() }),
                  "Interconsulta solicitada",
                )}
              >
                Derivar y esperar
              </Button>
            </div>
          </section>

          <ListaConAlta
            label="Emitir receta"
            placeholder="Medicación / indicaciones"
            value={detalleReceta}
            onChange={setDetalleReceta}
            disabled={ocupado}
            onAgregar={() => ejecutar(
              () => api.post(`/casos/${caso.id}/receta/`, { detalle: detalleReceta.trim() }),
              "Receta emitida",
            )}
            items={recetas.map((r) => ({ id: r.id, txt: r.detalle, tag: r.activa ? "activa" : "" }))}
            vacio="Sin recetas."
          />
        </div>
      )}

      <Button
        className="mt-xl"
        disabled={ocupado}
        onClick={() => ejecutar(
          () => api.post(`/casos/${caso.id}/avanzar/`, {
            titulo, contenido, firmada,
            ...(realizandoEstudio ? { resultado, archivo } : {}),
          }),
          realizandoEstudio ? "Resultado cargado" : "Atención registrada",
        )}
      >
        {ocupado ? "Registrando…" : realizandoEstudio ? "Cargar resultado y cerrar" : "Registrar atención y avanzar"}
      </Button>
    </Card>
  );
}

/** Campo + botón «Agregar» y la lista de lo ya cargado. */
function ListaConAlta({ label, placeholder, value, onChange, onAgregar, disabled, items, vacio }) {
  return (
    <section>
      <h4 className="mb-2 text-base font-bold text-texto-suave">{label}</h4>
      <div className="flex flex-wrap gap-2">
        <Input
          className="min-w-48 flex-1"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          onKeyDown={(e) => { if (e.key === "Enter" && value.trim()) onAgregar(); }}
        />
        <Button variant="secondary" disabled={disabled || !value.trim()} onClick={onAgregar}>Agregar</Button>
      </div>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-texto-tenue">{vacio}</p>
      ) : (
        <ul className="mt-2.5 flex flex-col gap-1.5">
          {items.map((it) => (
            <li key={it.id} className="flex items-center justify-between gap-2.5 rounded-md border border-borde bg-superficie-2 px-3 py-1.5 text-md">
              <span className="text-texto-medio">{it.txt}</span>
              {it.tag && <Badge tone="neutral">{it.tag}</Badge>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function PasoSimple({ caso, ocupado, ejecutar, texto, accion }) {
  return (
    <Card className="p-lg sm:p-xxl">
      <CabeceraPaso tipo={caso.nodo_tipo} titulo={caso.paso_actual} />
      <p className="mb-lg text-md text-texto-debil">{texto}</p>
      <Button disabled={ocupado} onClick={() => ejecutar(() => api.post(`/casos/${caso.id}/avanzar/`, {}), "Caso avanzado")}>
        {ocupado ? "Procesando…" : accion}
      </Button>
    </Card>
  );
}

function Dato({ k, v }) {
  return (
    <div className="flex items-center justify-between gap-3 text-md">
      <dt className="text-texto-debil">{k}</dt>
      <dd className="text-right font-medium text-texto-fuerte">{v}</dd>
    </div>
  );
}

function Timeline({ eventos }) {
  if (eventos.length === 0) return <p className="mt-3 text-md text-texto-tenue">Sin eventos todavía.</p>;
  return (
    <ol className="mt-3.5 flex flex-col">
      {eventos.map((e, i) => (
        <li key={e.id} className="flex gap-2.5">
          <div className="flex flex-col items-center">
            <span className="mt-1 size-2.5 shrink-0 rounded-pill bg-accent ring-2 ring-superficie" />
            {i < eventos.length - 1 && <span className="my-0.5 w-0.5 flex-1 bg-division" />}
          </div>
          <div className="pb-lg">
            <div className="text-md font-semibold text-texto-medio">{e.titulo}</div>
            {e.detalle && <div className="text-sm text-texto-debil">{e.detalle}</div>}
            <div className="mt-0.5 text-xs text-texto-tenue">{e.autor_nombre} · {fechaHora(e.fecha)}</div>
          </div>
        </li>
      ))}
    </ol>
  );
}

function CargandoCaso() {
  return (
    <div className="grid items-start gap-lg px-lg pb-8 pt-lg lg:grid-cols-[1fr_20rem] lg:gap-xxl lg:px-8" role="status" aria-label="Cargando caso…">
      <div className="flex flex-col gap-lg lg:order-1">
        <Skeleton className="h-32" />
        <Skeleton className="h-64" />
      </div>
      <div className="flex flex-col gap-lg">
        <Skeleton className="h-72" />
        <Skeleton className="h-48" />
      </div>
    </div>
  );
}
