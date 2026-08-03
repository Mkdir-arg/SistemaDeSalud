import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import { useQuery } from "@tanstack/react-query";

import { useAccion, useDetalle, useLista } from "@/api/queries";
import { Icon } from "@/components/icons";
import { PageHeader } from "@/components/Shell";
import { Badge, Button, Card, Checkbox, Field, Input, Mono, Select, Stepper, Textarea } from "@/components/ui";
import { EstadoError, Skeleton } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { antiguedad, casoId, fechaHora } from "@/lib/format";
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

      {/*
        Dos columnas en pantalla ancha, apiladas debajo de `lg`.

        El panel de trabajo va en la columna ANCHA y la ficha del caso en la
        angosta. Estaba al revés: `lg:order-1` lo empujaba a la segunda columna,
        así que el formulario donde se registra la atención —con su textarea, el
        pedido de estudios, la interconsulta y los insumos— vivía en 320 px
        mientras al lado sobraban mil. Los nombres de insumo salían cortados
        («Dipiron…») y los selects no entraban.

        Apiladas, en cambio, la ficha va primero: en una tablet lo que se
        consulta es el estado del caso, no el formulario.
      */}
      <div className="grid items-start gap-lg px-lg pb-8 pt-lg lg:grid-cols-[1fr_20rem] lg:gap-xxl lg:px-8">
        <div className="order-last flex flex-col gap-lg lg:order-first">
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

          {caso.cama && <PanelCama caso={caso} ejecutar={ejecutar} ocupado={accion.isPending} />}

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
  if (tipo === "atencion" && caso.nodo_con_fila && !caso.llamado && !caso.ausente) {
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
  if (tipo === "cama") return <PasoCama caso={caso} ocupado={ocupado} ejecutar={ejecutar} />;
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

/**
 * Paso «Asignar cama»: el paciente espera una cama del sector.
 *
 * Se listan las camas libres y se elige una. No se asigna sola a propósito: qué
 * cama le toca a quién depende de aislamiento, del sexo de la sala y de la
 * gravedad, y adivinarlo se paga caro.
 */
function PasoCama({ caso, ocupado, ejecutar }) {
  const q = useQuery({
    queryKey: ["camas-disponibles", caso.id],
    queryFn: () => api.get(`/casos/${caso.id}/cama/`),
  });
  const camas = q.data?.camas || [];

  return (
    <Card className="p-lg sm:p-xxl">
      <CabeceraPaso tipo="cama" titulo={caso.paso_actual} />
      {q.isLoading ? (
        <Skeleton className="h-24" />
      ) : camas.length === 0 ? (
        /* Sin camas el caso no avanza, y eso es información operativa: el
           sector está lleno. Decirlo es más útil que un panel vacío. */
        <div className="flex items-start gap-2 rounded-md bg-badge-amber-bg px-3.5 py-3 text-md text-badge-amber-fg">
          <Icon name="alert" size={16} className="mt-0.5 flex-none" />
          <span>
            No hay camas libres en el sector. El paciente queda esperando; se lo
            puede internar apenas se libere una, desde acá o desde{" "}
            <strong>Internación</strong>.
          </span>
        </div>
      ) : (
        <>
          <p className="mb-3 text-md text-texto-suave">
            {camas.length === 1 ? "Hay 1 cama libre" : `Hay ${camas.length} camas libres`} en el sector.
          </p>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(9rem,1fr))] gap-2">
            {camas.map((c) => (
              <button
                key={c.id}
                disabled={ocupado}
                onClick={() => ejecutar(
                  () => api.post(`/casos/${caso.id}/cama/`, { cama_id: c.id }),
                  `Internado en la cama ${c.nombre}`,
                )}
                className="flex flex-col gap-0.5 rounded-md border border-borde px-3 py-2.5 text-left transition-colors hover:border-accent-100 hover:bg-accent-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <span className="font-mono text-md font-bold">{c.nombre}</span>
                <span className="text-sm text-texto-tenue">{c.sector}</span>
              </button>
            ))}
          </div>
        </>
      )}
    </Card>
  );
}

/**
 * Dónde está internado y qué se puede hacer desde ahí.
 *
 * Va en la columna de información y no en el panel del paso: la cama acompaña
 * al paciente por varios pasos del flujo —evolución, conducta— y el pase o el
 * egreso pueden hacerse en cualquiera de ellos.
 */
function PanelCama({ caso, ejecutar, ocupado }) {
  const [pasando, setPasando] = useState(false);
  const q = useQuery({
    queryKey: ["camas-libres", caso.institucion],
    queryFn: () => api.get(`/camas/?area__institucion=${caso.institucion}&estado=libre&page_size=200`),
    enabled: pasando,
  });
  const camas = q.data?.results || [];

  return (
    <Card className="p-xl">
      <h3 className="mb-3 text-xs font-bold tracking-wide text-texto-tenue">INTERNACIÓN</h3>
      <div className="flex items-center gap-2.5">
        <span className="flex size-9 flex-none items-center justify-center rounded-md bg-accent-50 text-accent">
          <Icon name="bed" size={17} />
        </span>
        <div className="min-w-0">
          <div className="font-mono text-md font-bold">{caso.cama.nombre}</div>
          <div className="truncate text-sm text-texto-tenue">
            {caso.cama.sector} · hace {antiguedad(caso.cama.desde)}
          </div>
        </div>
      </div>

      {pasando ? (
        <div className="mt-3 flex flex-col gap-2">
          <div className="text-sm font-semibold text-texto-suave">Pasar a otra cama</div>
          {q.isLoading ? (
            <Skeleton className="h-16" />
          ) : camas.length === 0 ? (
            <p className="text-sm text-texto-tenue">No hay camas libres en la institución.</p>
          ) : (
            <div className="flex max-h-48 flex-col gap-1 overflow-y-auto">
              {camas.map((c) => (
                <button
                  key={c.id}
                  disabled={ocupado}
                  onClick={() => ejecutar(
                    () => api.post(`/casos/${caso.id}/pase/`, { cama_id: c.id }),
                    `Pasó a la cama ${c.nombre}`,
                  )}
                  className="flex items-baseline justify-between gap-2 rounded-md border border-division px-2.5 py-1.5 text-left hover:bg-superficie-2"
                >
                  <span className="font-mono text-base font-bold">{c.nombre}</span>
                  <span className="truncate text-sm text-texto-tenue">{c.sector}</span>
                </button>
              ))}
            </div>
          )}
          <Button size="sm" variant="secondary" onClick={() => setPasando(false)}>Cancelar</Button>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" disabled={ocupado} onClick={() => setPasando(true)}>
            Pase de sector
          </Button>
          <Button
            size="sm"
            variant="secondary"
            disabled={ocupado}
            onClick={() => ejecutar(
              () => api.post(`/casos/${caso.id}/egreso-cama/`),
              "Egresó de internación · la cama quedó en higiene",
            )}
          >
            Egreso
          </Button>
        </div>
      )}
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

  /*
   * Dado por ausente: la única acción honesta es reencolarlo si aparece.
   * Ofrecer el formulario de atención sería invitar a asentar en la historia
   * clínica una atención que no ocurrió.
   */
  if (caso.ausente) {
    return (
      <Card className="p-lg sm:p-xxl">
        <CabeceraPaso tipo="atencion" titulo={caso.paso_actual} />
        <div className="flex flex-wrap items-center gap-3 rounded-md border border-borde bg-superficie-2 px-3.5 py-3">
          <Icon name="alert" size={18} className="shrink-0 text-texto-tenue" />
          <div className="min-w-40 flex-1 text-md text-texto-suave">
            No se presentó cuando se lo llamó. Salió de la cola y el box quedó
            libre. Si aparece, vuelve a la cola <strong>al final</strong>: ya se
            llamó a los que estaban después.
          </div>
          <Button
            size="sm"
            disabled={ocupado}
            onClick={() => ejecutar(
              () => api.post(`/casos/${caso.id}/devolver/`),
              "Volvió a la cola, al final",
            )}
          >
            Apareció · volver a la cola
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-lg sm:p-xxl">
      <CabeceraPaso tipo="atencion" titulo={caso.paso_actual} />

      {/* El cartel preguntaba «¿No se presentó?» y la única respuesta posible era
          rellamar. Si el paciente no aparecía nunca, quedaba llamado para
          siempre: el box figuraba ocupado y el caso contaba como en atención. */}
      {caso.nodo_con_fila && caso.llamado && (
        <div className="mb-lg flex flex-wrap items-center gap-3 rounded-md border border-badge-amber-fg/25 bg-badge-amber-bg px-3.5 py-3">
          <Icon name="enter" size={18} className="shrink-0 text-badge-amber-fg" />
          <div className="min-w-40 flex-1 text-md text-badge-amber-fg">
            Paciente llamado{caso.llamado_box ? <> a <strong>{caso.llamado_box}</strong></> : ""}.
            {rellamos > 0
              ? <> Se rellamó {rellamos === 1 ? "una vez" : `${rellamos} veces`} — mirá la pantalla de la sala.</>
              : <> ¿No se presentó?</>}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={rellamar.isPending || ocupado}
              onClick={() => rellamar.mutate(undefined, { onSuccess: () => setRellamos((n) => n + 1) })}
            >
              {rellamar.isPending ? "Rellamando…" : "Rellamar"}
            </Button>
            {/* Vuelve a SU lugar en la cola: la demora no fue del paciente. */}
            <Button
              size="sm"
              variant="secondary"
              disabled={ocupado}
              onClick={() => ejecutar(
                () => api.post(`/casos/${caso.id}/devolver/`),
                "Volvió a la cola, en su lugar",
              )}
            >
              Volver a la cola
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={ocupado}
              onClick={() => ejecutar(
                () => api.post(`/casos/${caso.id}/ausente/`),
                "Marcado como ausente · el box quedó libre",
              )}
            >
              No se presentó
            </Button>
          </div>
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

          <TrasladoExterno caso={caso} ocupado={ocupado} ejecutar={ejecutar} />

          <Insumos caso={caso} ocupado={ocupado} toast={toast} />

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

/**
 * Insumos usados en esta atención.
 *
 * Registrarlo acá y no en Farmacia es lo que hace que el consumo quede imputado
 * al paciente: es la diferencia entre «bajaron 3 ampollas del botiquín» y «a
 * esta persona se le dieron 3 ampollas de este lote», que es lo único que sirve
 * cuando hay que responder un retiro de ANMAT.
 *
 * El depósito no se elige: es el del área donde se está atendiendo. Preguntarlo
 * cada vez sería pedirle a quien atiende que sepa algo que el sistema ya sabe.
 */
function Insumos({ caso, ocupado, toast }) {
  const [busca, setBusca] = useState("");
  const [cantidades, setCantidades] = useState({});

  const depositos = useLista(
    "depositos",
    { institucion: caso.institucion, activo: true, pageSize: 50 },
  );
  // El botiquín del área donde se atiende; si no hay, la central.
  const deposito = useMemo(() => {
    const d = depositos.filas;
    return d.find((x) => x.area === caso.area_actual) || d.find((x) => x.central) || d[0];
  }, [depositos.filas, caso.area_actual]);

  const stock = useQuery({
    queryKey: ["stock-consumo", deposito?.id, busca],
    queryFn: () => api.get(
      `/stock/?deposito=${deposito.id}&search=${encodeURIComponent(busca)}&page_size=40`
    ),
    enabled: !!deposito && busca.trim().length >= 2,
  });

  const usados = useQuery({
    queryKey: ["consumos-caso", caso.id],
    queryFn: () => api.get(`/movimientos-stock/?caso=${caso.id}&tipo=consumo&page_size=50`),
  });

  // Se agrupa por insumo: la búsqueda devuelve un renglón por lote y quien
  // atiende elige un insumo, no un lote —de eso se ocupa el motor—.
  const opciones = useMemo(() => {
    const m = new Map();
    for (const e of stock.data?.results || []) {
      if (!m.has(e.insumo)) {
        m.set(e.insumo, { id: e.insumo, nombre: e.insumo_nombre, unidad: e.unidad, total: 0 });
      }
      m.get(e.insumo).total += e.cantidad;
    }
    return [...m.values()].filter((o) => o.total > 0);
  }, [stock.data]);

  const registrar = useAccion(
    ({ insumo, cantidad }) => api.post("/movimientos-stock/consumo/", {
      deposito: deposito.id, insumo, cantidad, caso: caso.id,
    }),
    {
      invalida: [],
      onSuccess: (_, { nombre }) => {
        toast.ok(`${nombre} registrado`);
        setCantidades({});
        usados.refetch();
        stock.refetch();
      },
      onError: (e) => toast.deError(e, "No se pudo registrar el consumo."),
    },
  );

  if (!depositos.isLoading && !deposito) return null; // la institución no usa farmacia

  return (
    <section className="rounded-md border border-borde p-3.5">
      <h4 className="mb-2 text-base font-bold text-texto-suave">
        Insumos usados
        {deposito && <span className="font-normal text-texto-tenue"> · {deposito.nombre}</span>}
      </h4>

      {(usados.data?.results || []).length > 0 && (
        <ul className="mb-2.5 flex flex-col gap-1">
          {usados.data.results.map((m) => (
            <li key={m.id} className="flex items-baseline justify-between gap-2 text-base">
              <span className="min-w-0 truncate">{m.cantidad} × {m.insumo_nombre}</span>
              {m.lote_numero && (
                <span className="whitespace-nowrap font-mono text-sm text-texto-tenue">
                  lote {m.lote_numero}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      <Input
        value={busca}
        onChange={(e) => setBusca(e.target.value)}
        placeholder="Buscar un insumo del botiquín…"
        aria-label="Buscar insumo"
        disabled={ocupado || !deposito}
      />

      {busca.trim().length >= 2 && (
        stock.isLoading ? (
          <Skeleton className="mt-2 h-14" />
        ) : opciones.length === 0 ? (
          /* Que no haya es información: hay que pedir reposición, no seguir
             buscando con otras palabras. */
          <p className="mt-2 text-sm text-texto-tenue">
            No hay stock de eso en {deposito?.nombre}.
          </p>
        ) : (
          <div className="mt-2 flex flex-col gap-1.5">
            {opciones.map((o) => (
              <div key={o.id} className="flex flex-wrap items-center gap-2">
                <span className="min-w-0 flex-1 truncate text-base">
                  {o.nombre}
                  <span className="text-texto-tenue"> · hay {o.total} {o.unidad}</span>
                </span>
                <Input
                  type="number"
                  min="1"
                  max={o.total}
                  value={cantidades[o.id] ?? 1}
                  onChange={(e) => setCantidades({ ...cantidades, [o.id]: e.target.value })}
                  aria-label={`Cantidad de ${o.nombre}`}
                  className="w-20"
                />
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={ocupado || registrar.isPending}
                  onClick={() => registrar.mutate({
                    insumo: o.id, cantidad: Number(cantidades[o.id] ?? 1), nombre: o.nombre,
                  })}
                >
                  Registrar
                </Button>
              </div>
            ))}
          </div>
        )
      )}
    </section>
  );
}

/**
 * Derivar a OTRO establecimiento.
 *
 * Va separado de la interconsulta a propósito, aunque las dos «derivan»: una
 * manda el caso a otra área de esta casa y vuelve; la otra manda al paciente a
 * otro hospital, que puede decir que no. Mezclarlas en el mismo selector haría
 * que se elija por error el destino equivocado.
 *
 * Sólo aparece si el establecimiento pertenece a una red: donde no la hay, es
 * una opción que nunca va a funcionar.
 */
function TrasladoExterno({ caso, ocupado, ejecutar }) {
  const [destino, setDestino] = useState("");
  const [motivo, setMotivo] = useState("complejidad");
  const [detalle, setDetalle] = useState("");

  const q = useQuery({
    queryKey: ["destinos-traslado", caso.institucion],
    queryFn: () => api.get(`/traslados/destinos/?institucion=${caso.institucion}`),
  });
  const destinos = q.data?.destinos || [];
  if (q.isLoading || destinos.length === 0) return null;

  return (
    <section>
      <h4 className="mb-2 text-base font-bold text-texto-suave">Derivar a otro establecimiento</h4>
      <div className="flex flex-col gap-2">
        <Select aria-label="Establecimiento de destino" value={destino}
                onChange={(e) => setDestino(e.target.value)}>
          <option value="">— Elegir establecimiento —</option>
          {destinos.map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}
        </Select>
        <Select aria-label="Motivo del traslado" value={motivo}
                onChange={(e) => setMotivo(e.target.value)}>
          <option value="complejidad">Mayor complejidad</option>
          <option value="especialidad">Especialidad no disponible</option>
          <option value="cama">Falta de cama</option>
          <option value="estudio">Estudio no disponible</option>
          <option value="cercania">Cercanía al domicilio</option>
          <option value="otro">Otro</option>
        </Select>
        {/* El resumen es lo ÚNICO clínico que cruza al otro hospital: su
            historia clínica no viaja. Quien recibe decide con esto. */}
        <Textarea value={detalle} onChange={(e) => setDetalle(e.target.value)}
                  placeholder="Resumen para quien recibe: es lo único que va a ver del cuadro." />
        <Button
          variant="secondary"
          disabled={ocupado || !destino}
          onClick={() => ejecutar(
            () => api.post("/traslados/solicitar/", {
              caso: caso.id, destino: Number(destino), motivo, detalle: detalle.trim(),
            }),
            "Traslado solicitado · el paciente sigue a cargo hasta que lo reciban",
          )}
        >
          Solicitar traslado
        </Button>
      </div>
    </section>
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
    // `min-w-0` en el valor: en un flex el contenido no se achica por debajo de
    // su ancho natural, así que un antecedente largo («Hipertensión arterial ·
    // Diabetes tipo 2») se salía de la tarjeta en vez de cortar línea. La
    // etiqueta no se achica: es corta y es lo que da sentido al valor.
    <div className="flex items-baseline justify-between gap-3 text-md">
      <dt className="flex-none text-texto-debil">{k}</dt>
      <dd className="min-w-0 text-right font-medium text-texto-fuerte">{v}</dd>
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
      <div className="order-last flex flex-col gap-lg lg:order-first">
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
