import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import { PageHeader, useRefresh } from "@/components/Shell";
import { Badge, Button, Card, Field, Modal, Select } from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton } from "@/components/ui/estados";
import { BuscadorPaciente, PacienteElegido } from "@/components/ui/paciente";
import { useToast } from "@/components/ui/toast";
import { antiguedad } from "@/lib/format";
import { cn } from "@/lib/cn";
import { estadoCaso } from "@/lib/dominio";

const REFRESCO_MS = 30_000;

// Umbrales de espera. En una guardia, cuánto lleva esperando un caso pesa tanto
// como su prioridad.
const ESPERA_AMBAR_MIN = 15;
const ESPERA_ROJO_MIN = 30;

function espera(iso) {
  const m = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  if (m >= ESPERA_ROJO_MIN) return { clase: "text-danger font-bold", borde: "border-l-danger", demorado: true };
  if (m >= ESPERA_AMBAR_MIN) return { clase: "text-badge-amber-fg font-bold", borde: "border-l-badge-amber-fg", demorado: true };
  return { clase: "text-texto-tenue", borde: "border-l-transparent", demorado: false };
}

const masViejo = (isos) => (isos.length ? isos.reduce((a, b) => (new Date(a) < new Date(b) ? a : b)) : null);

/**
 * «Mi trabajo»: la worklist del operador, segmentada por paso. Las bandas las
 * arma el backend en `/mis-tareas/` a partir de usuario → grupos → nodos.
 */
export default function MiTrabajo() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const { setRefresco } = useRefresh();
  const [areaSel, setAreaSel] = useState(null);
  const [ingresar, setIngresar] = useState(null);
  const [buscarEstado, setBuscarEstado] = useState(false);

  const q = useQuery({
    queryKey: ["mis-tareas", institucion?.id],
    queryFn: () => api.get(`/mis-tareas/?institucion=${institucion.id}`),
    enabled: !!institucion,
    // Worklist vivo: el operador deja la pantalla abierta mientras entran casos.
    // Query pausa el intervalo con la pestaña oculta y refresca al volver el
    // foco, así que ya no hace falta manejar `visibilitychange` a mano.
    refetchInterval: REFRESCO_MS,
    refetchIntervalInBackground: false,
  });

  // Publica «última actualización» en la barra superior.
  useEffect(() => {
    setRefresco({ ultima: q.dataUpdatedAt ? new Date(q.dataUpdatedAt).toISOString() : null, refrescando: q.isFetching });
  }, [q.dataUpdatedAt, q.isFetching, setRefresco]);
  useEffect(() => () => setRefresco(null), [setRefresco]);

  if (q.isLoading) return <CargandoTrabajo />;
  if (q.error) {
    return <div className="p-8"><EstadoError error={q.error} titulo="No pudimos cargar tu trabajo" onReintentar={q.refetch} /></div>;
  }

  const d = { iniciar: [], tareas: [], filas: [], esperando: [], puestos: [], ...q.data };
  const vacio = !d.iniciar.length && !d.tareas.length && !d.filas.length && !d.esperando.length && !d.puestos.length;

  const areas = [...new Set(
    [...d.iniciar, ...d.tareas, ...d.filas, ...d.esperando, ...d.puestos].map((x) => x.area_nombre).filter(Boolean),
  )].sort();
  const multi = areas.length > 1;
  const areaActiva = areaSel && areas.includes(areaSel) ? areaSel : multi ? null : areas[0] || null;

  const deArea = (a) => ({
    iniciar: d.iniciar.filter((x) => x.area_nombre === a),
    tareas: d.tareas.filter((x) => x.area_nombre === a),
    filas: d.filas.filter((x) => x.area_nombre === a),
    esperando: d.esperando.filter((x) => x.area_nombre === a),
    puestos: d.puestos.filter((x) => x.area_nombre === a),
  });

  return (
    <>
      <PageHeader subtitle={areaActiva && multi ? areaActiva : "Lo que podés iniciar y lo que está esperando por vos."} />

      <div className="flex flex-col gap-7 px-lg pb-8 pt-[22px] sm:px-8">
        {vacio ? (
          <EstadoVacio
            titulo="No tenés tareas pendientes"
            detalle="Cuando entren casos a los pasos que operás, van a aparecer acá."
          />
        ) : areaActiva ? (
          <>
            {multi && (
              <button
                onClick={() => setAreaSel(null)}
                className="flex items-center gap-1.5 self-start text-md font-semibold text-accent hover:underline"
              >
                <Icon name="back" size={14} /> Áreas
              </button>
            )}
            <Bandas
              d={d}
              dd={deArea(areaActiva)}
              areaActiva={areaActiva}
              onIngresar={setIngresar}
              onBuscarEstado={() => setBuscarEstado(true)}
            />
          </>
        ) : (
          <Seccion titulo="Mis áreas">
            <div className="grid grid-cols-[repeat(auto-fit,minmax(15rem,1fr))] gap-3.5">
              {areas.map((a) => (
                <TarjetaArea key={a} area={a} d={d} onEntrar={() => setAreaSel(a)} />
              ))}
            </div>
          </Seccion>
        )}

        {!areaSel && (d.mis_casos || []).length > 0 && (
          <Seccion titulo="Mis casos en curso">
            <Card className="overflow-hidden">
              <ul>
                {d.mis_casos.map((c) => (
                  <li key={c.id}>
                    <button
                      onClick={() => navigate(`/casos/${c.id}`)}
                      className="flex w-full items-center gap-3 border-t border-division px-lg py-3 text-left first:border-t-0 hover:bg-superficie-2"
                    >
                      <PuntoPrioridad prioridad={c.prioridad} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-md font-semibold">{c.ciudadano_nombre || "—"}</span>
                        <span className="block truncate text-sm text-texto-tenue">
                          {[c.paso_actual, c.area_nombre, c.flujo_titulo].filter(Boolean).join(" · ")}
                        </span>
                      </span>
                      {c.esperando
                        ? <Badge tone="amber">Esperando</Badge>
                        : <span className="shrink-0 text-sm text-texto-tenue">{c.estado_display}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
          </Seccion>
        )}
      </div>

      {ingresar && (
        <ModalIngresarPaciente
          item={ingresar}
          institucionId={institucion?.id}
          onClose={() => setIngresar(null)}
          onCreado={(id) => { setIngresar(null); navigate(`/casos/${id}`); }}
        />
      )}
      {buscarEstado && (
        <ModalEstadoPaciente
          institucionId={institucion?.id}
          onIr={(path) => { setBuscarEstado(false); navigate(path); }}
          onClose={() => setBuscarEstado(false)}
        />
      )}
    </>
  );
}

// --------------------------------------------------------------------------- //
// Bandas de trabajo
// --------------------------------------------------------------------------- //
function Bandas({ d, dd, areaActiva, onIngresar, onBuscarEstado }) {
  const navigate = useNavigate();
  const pulso = d.resumen_areas?.[areaActiva];
  const boxesPorArea = [...new Map(dd.filas.map((f) => [f.area_id, f])).values()];
  const ingresosHoy = (d.mis_ingresos || []).filter((c) => c.area_nombre === areaActiva);

  return (
    <>
      {pulso && <Seccion titulo="Pulso del área (hoy)"><Pulso r={pulso} /></Seccion>}

      {dd.iniciar.length > 0 && (
        <Seccion titulo="Iniciar">
          <div className="grid grid-cols-[repeat(auto-fill,minmax(17rem,1fr))] gap-3">
            {dd.iniciar.map((it) => (
              <Card key={it.version_id} className="flex flex-col gap-3 p-lg">
                <div>
                  <div className="text-md font-bold">{it.flujo_titulo}</div>
                  <div className="text-base text-texto-tenue">{it.area_nombre} · empieza en «{it.paso}»</div>
                </div>
                <Button onClick={() => onIngresar(it)}>
                  <Icon name="enter" size={15} /> Ingresar paciente
                </Button>
              </Card>
            ))}
          </div>
        </Seccion>
      )}

      <Seccion titulo="Accesos rápidos">
        <div className="flex flex-wrap gap-3">
          <AccesoRapido icon="search" label="Estado de un paciente" hint="Buscar su ingreso o expediente" onClick={onBuscarEstado} />
          <AccesoRapido icon="clipboard" label="Historias clínicas" hint="Buscar, ver y crear expedientes" onClick={() => navigate("/historia")} />
        </div>
      </Seccion>

      {dd.puestos.length > 0 && (
        <Seccion titulo="Mis puestos">
          <div className="grid grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] gap-3">
            {dd.puestos.map((p) => <TarjetaPuesto key={p.nodo_id} p={p} onAbrir={() => navigate(`/puesto/${p.nodo_id}`)} />)}
          </div>
        </Seccion>
      )}

      {boxesPorArea.length > 0 && (
        <Seccion titulo="Tu box">
          <div className="flex flex-col gap-3">
            {boxesPorArea.map((f) => <BarraBox key={f.area_id} f={f} />)}
          </div>
        </Seccion>
      )}

      {dd.tareas.length > 0 && (
        <Seccion titulo="Para hacer ahora">
          <div className="flex flex-col gap-3.5">
            {dd.tareas.map((b) => <TarjetaTarea key={b.nodo_id} b={b} />)}
          </div>
        </Seccion>
      )}

      {dd.filas.length > 0 && (
        <Seccion titulo="Mis filas">
          <div className="flex flex-col gap-3.5">
            {dd.filas.map((f) => <TarjetaFila key={f.nodo_id} f={f} />)}
          </div>
        </Seccion>
      )}

      {dd.esperando.length > 0 && (
        <Seccion titulo="Esperando resultados">
          <Card className="overflow-hidden">
            <ul>
              {dd.esperando.map((c) => (
                <li key={c.id}>
                  <button
                    onClick={() => navigate(`/casos/${c.id}`)}
                    className="flex w-full items-center gap-3 border-t border-division px-lg py-3 text-left first:border-t-0 hover:bg-superficie-2"
                  >
                    <Icon name="clipboard" size={15} className="shrink-0 text-texto-tenue" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-md font-semibold">{c.ciudadano_nombre || "—"}</span>
                      <span className="block truncate text-sm text-texto-tenue">{c.flujo_titulo} · esperando «{c.espera_de}»</span>
                    </span>
                    <Badge tone="amber">En espera</Badge>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        </Seccion>
      )}

      {ingresosHoy.length > 0 && (
        <Seccion titulo="Mis ingresos de hoy">
          <Card className="overflow-hidden">
            <ul>
              {ingresosHoy.map((c) => (
                <li key={c.id}>
                  <button
                    onClick={() => navigate(`/casos/${c.id}`)}
                    className="flex w-full items-center gap-3 border-t border-division px-lg py-3 text-left first:border-t-0 hover:bg-superficie-2"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-md font-semibold">{c.ciudadano_nombre || "—"}</span>
                      <span className="block truncate text-sm text-texto-tenue">
                        {c.paso_actual || "—"} · ingresó hace {antiguedad(c.creado)}
                      </span>
                    </span>
                    <span className="shrink-0 text-sm text-texto-tenue">{c.estado_display}</span>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        </Seccion>
      )}
    </>
  );
}

function Seccion({ titulo, children }) {
  return (
    <section>
      <h2 className="mb-2.5 text-xs font-bold uppercase tracking-wide text-texto-tenue">{titulo}</h2>
      {children}
    </section>
  );
}

function Pulso({ r }) {
  const tiles = [
    { label: "En espera", n: r.en_espera },
    { label: "En atención", n: r.en_atencion },
    { label: "Ingresos hoy", n: r.ingresos_hoy },
    { label: "Urgentes", n: r.urgentes, alerta: r.urgentes > 0 },
    { label: "Espera prom.", n: `${r.espera_prom_min} min` },
  ];
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(9.5rem,1fr))] gap-3">
      {tiles.map((t) => (
        <Card key={t.label} className={cn("border-l-[3px] px-lg py-3.5", t.alerta ? "border-l-danger" : "border-l-borde")}>
          <div className={cn("text-cifra-lg font-extrabold leading-none tabular-nums", t.alerta ? "text-danger" : "text-texto")}>{t.n}</div>
          <div className="mt-1.5 text-sm text-texto-debil">{t.label}</div>
        </Card>
      ))}
    </div>
  );
}

function AccesoRapido({ icon, label, hint, onClick }) {
  return (
    <button
      onClick={onClick}
      className="flex min-w-56 flex-1 items-center gap-3 rounded-lg border border-borde bg-superficie p-3.5 text-left transition-shadow hover:shadow-float sm:flex-none"
    >
      <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-accent-50 text-accent">
        <Icon name={icon} size={18} />
      </span>
      <span>
        <span className="block text-md font-bold">{label}</span>
        <span className="block text-sm text-texto-tenue">{hint}</span>
      </span>
    </button>
  );
}

function TarjetaArea({ area, d, onEntrar }) {
  const puestos = d.puestos.filter((x) => x.area_nombre === area);
  const r = {
    pasos: puestos.length,
    ahora: puestos.reduce((s, p) => s + (p.ahora || 0), 0),
    urgentes: puestos.reduce((s, p) => s + (p.urgentes || 0), 0),
    encola: d.filas.filter((x) => x.area_nombre === area).reduce((s, f) => s + (f.en_cola || 0), 0),
    iniciar: d.iniciar.some((x) => x.area_nombre === area),
  };
  return (
    <button
      onClick={onEntrar}
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-l-[3px] border-borde bg-superficie p-lg text-left transition-shadow hover:shadow-float",
        r.urgentes > 0 ? "border-l-danger" : "border-l-borde",
      )}
    >
      <span className="flex items-center gap-2.5">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-accent-50 text-accent">
          <Icon name="building" size={18} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-lg font-bold">{area}</span>
          <span className="block text-sm text-texto-tenue">{r.pasos} paso{r.pasos !== 1 ? "s" : ""}</span>
        </span>
        {r.urgentes > 0 && <Badge tone="error">{r.urgentes} urg.</Badge>}
      </span>
      <span className="flex items-baseline gap-lg text-base text-texto-debil">
        <span><strong className={cn("text-xl", r.ahora > 0 ? "text-texto" : "text-texto-tenue")}>{r.ahora}</strong> pendientes</span>
        {r.encola > 0 && <span><strong className="text-xl text-texto">{r.encola}</strong> en cola</span>}
      </span>
      <span className="flex items-center">
        {r.iniciar && <span className="text-sm text-texto-tenue">+ Ingresar disponible</span>}
        <span className="ml-auto text-md font-semibold text-accent">Entrar →</span>
      </span>
    </button>
  );
}

const PUESTO_ICON = { entrada: "enter", fila: "list", tarea: "inbox" };

function TarjetaPuesto({ p, onAbrir }) {
  return (
    <button
      onClick={onAbrir}
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-l-[3px] border-borde bg-superficie p-3.5 text-left transition-shadow hover:shadow-float",
        p.urgentes > 0 ? "border-l-danger" : "border-l-borde",
      )}
    >
      <span className="flex items-center gap-2.5">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-accent-50 text-accent">
          <Icon name={PUESTO_ICON[p.rol] || "inbox"} size={15} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-md font-bold">{p.nodo_titulo}</span>
          <span className="block truncate text-sm text-texto-tenue">
            {[p.flujo_titulo, p.area_nombre].filter(Boolean).join(" · ")}
          </span>
        </span>
        {p.urgentes > 0 && <Badge tone="error">{p.urgentes} urg.</Badge>}
      </span>
      <span className="flex items-end gap-lg">
        <span>
          <span className={cn("block text-cifra-lg font-extrabold leading-none tabular-nums", p.ahora > 0 ? "text-texto" : "text-texto-tenue")}>{p.ahora}</span>
          <span className="mt-1 block text-xs text-texto-debil">{p.rol === "fila" ? "en cola" : "ahora"}</span>
        </span>
        <span>
          <span className="block text-cifra-lg font-extrabold leading-none tabular-nums text-texto-suave">{p.hoy}</span>
          <span className="mt-1 block text-xs text-texto-debil">hoy</span>
        </span>
        {p.desde && (
          <span className={cn("flex-1 text-right text-sm", espera(p.desde).clase)}>
            + antiguo · {antiguedad(p.desde)}
          </span>
        )}
      </span>
    </button>
  );
}

function CabeceraBanda({ icon, titulo, sub, total, urgentes, totalLabel = "esperando", desde, abierto, onToggle }) {
  return (
    <button onClick={onToggle} className="flex w-full items-center gap-3 px-lg py-3 text-left" aria-expanded={abierto}>
      <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-accent-50 text-accent">
        <Icon name={icon} size={16} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-md font-bold">{titulo}</span>
        <span className="block truncate text-sm text-texto-tenue">{sub}</span>
      </span>
      {desde && <span className={cn("hidden text-sm sm:inline", espera(desde).clase)}>el más antiguo · {antiguedad(desde)}</span>}
      {urgentes > 0 && <Badge tone="error">{urgentes} urgente{urgentes > 1 ? "s" : ""}</Badge>}
      <Badge tone="neutral">{total} {totalLabel}</Badge>
      <Icon name="back" size={13} className={cn("shrink-0 text-texto-tenue", abierto ? "-rotate-90" : "rotate-90")} />
    </button>
  );
}

const subtitulo = (b) => {
  const base = [b.flujo_titulo, b.area_nombre].filter(Boolean).join(" · ");
  return b.grupos?.length ? `${base} · ${b.grupos.join(", ")}` : base;
};

function TarjetaTarea({ b }) {
  const navigate = useNavigate();
  const toast = useToast();
  const [abierto, setAbierto] = useState(true);
  const tomar = useAccion((caso) => api.post(`/casos/${caso}/tomar/`), {
    onError: (e) => toast.deError(e, "No se pudo tomar el caso."),
  });

  return (
    <Card className="overflow-hidden">
      <CabeceraBanda
        icon="inbox" titulo={b.nodo_titulo} sub={subtitulo(b)} total={b.total} urgentes={b.urgentes}
        desde={masViejo(b.casos.map((c) => c.creado))} abierto={abierto} onToggle={() => setAbierto((v) => !v)}
      />
      {abierto && (b.casos.length === 0 ? (
        <p className="border-t border-division px-lg py-3.5 text-base text-texto-tenue">Sin casos por ahora.</p>
      ) : (
        <ul>
          {b.casos.map((c) => {
            const e = espera(c.creado);
            const enCurso = c.asignado_a && !c.mio;
            return (
              <li key={c.id}>
                <div
                  className={cn(
                    "flex items-center gap-3 border-t border-l-[3px] border-division py-3 pl-3 pr-lg",
                    e.borde,
                    enCurso && "opacity-60",
                  )}
                >
                  <PuntoPrioridad prioridad={c.prioridad} />
                  <button onClick={() => navigate(`/casos/${c.id}`)} className="min-w-0 flex-1 text-left">
                    <span className="flex items-center gap-2">
                      <span className="truncate text-md font-semibold">{c.ciudadano_nombre || "Sin paciente"}</span>
                      <ChipPrioridad prioridad={c.prioridad} />
                    </span>
                    <span className="block truncate text-sm text-texto-tenue">
                      <span className={e.clase}>{antiguedad(c.creado)}</span> · {c.estado_display}
                      {enCurso ? ` · en curso por ${c.asignado_nombre}` : ""}
                    </span>
                  </button>
                  {c.mio ? (
                    <Button size="sm" onClick={() => navigate(`/casos/${c.id}`)}>Continuar</Button>
                  ) : enCurso ? (
                    <Badge tone="neutral">Tomado</Badge>
                  ) : (
                    <Button
                      size="sm" variant="secondary" disabled={tomar.isPending}
                      onClick={() => tomar.mutate(c.id, { onSuccess: () => navigate(`/casos/${c.id}`) })}
                    >
                      {tomar.isPending ? "…" : "Tomar y abrir"}
                    </Button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      ))}
    </Card>
  );
}

function BarraBox({ f }) {
  const toast = useToast();
  const [boxSel, setBoxSel] = useState(() => {
    const libre = f.boxes.find((b) => !b.ocupado_por);
    return libre ? String(libre.id) : "";
  });
  const miBox = f.boxes.find((b) => b.id === f.mi_box) || null;

  const ocupar = useAccion((box) => api.post(`/boxes/${box}/ocupar/`), {
    invalida: ["lista", "mis-tareas"],
    onError: (e) => toast.deError(e, "No se pudo ocupar el box."),
  });
  const liberar = useAccion((box) => api.post(`/boxes/${box}/liberar/`), {
    invalida: ["lista", "mis-tareas"],
    onError: (e) => toast.deError(e, "No se pudo liberar el box."),
  });
  const ocupado = ocupar.isPending || liberar.isPending;

  return (
    <Card className={cn("flex flex-wrap items-center gap-3 border-l-[3px] p-lg", miBox ? "border-l-badge-green-fg" : "border-l-accent")}>
      <span className={cn(
        "flex size-9 shrink-0 items-center justify-center rounded-md",
        miBox ? "bg-badge-green-bg text-badge-green-fg" : "bg-accent-50 text-accent",
      )}>
        <Icon name="cube" size={18} />
      </span>
      <div className="min-w-40 flex-1">
        <div className="text-md font-bold">{f.area_nombre}</div>
        <div className="text-base text-texto-tenue">
          {miBox
            ? <>Atendiendo en <strong className="text-badge-green-fg">{miBox.nombre}</strong></>
            : "Elegí tu box para empezar a llamar pacientes"}
        </div>
      </div>
      {miBox ? (
        <Button variant="secondary" disabled={ocupado} onClick={() => liberar.mutate(f.mi_box)}>Salir del box</Button>
      ) : f.boxes.length === 0 ? (
        <span className="text-md text-texto-tenue">El área no tiene boxes configurados.</span>
      ) : (
        <>
          <Select aria-label="Box" className="max-w-56" value={boxSel} onChange={(e) => setBoxSel(e.target.value)}>
            {f.boxes.map((b) => (
              <option key={b.id} value={b.id} disabled={!!b.ocupado_por}>
                {b.nombre}{b.ocupado_por ? ` · ocupado por ${b.ocupado_por_nombre}` : ""}
              </option>
            ))}
          </Select>
          <Button disabled={!boxSel || ocupado} onClick={() => ocupar.mutate(boxSel)}>
            {ocupado ? "…" : "Ocupar box"}
          </Button>
        </>
      )}
    </Card>
  );
}

function TarjetaFila({ f }) {
  const navigate = useNavigate();
  const toast = useToast();
  const [abierto, setAbierto] = useState(true);
  const siguiente = f.casos[0];

  const llamar = useAccion((caso) => api.post(`/casos/${caso}/llamar/`, { box_id: f.mi_box }), {
    invalida: ["lista", "mis-tareas"],
    onError: (e) => toast.deError(e, "No se pudo llamar al paciente."),
  });
  const alLlamar = (caso) => {
    if (!caso || !f.mi_box) return;
    llamar.mutate(caso.id, { onSuccess: () => navigate(`/casos/${caso.id}`) });
  };

  return (
    <Card className="overflow-hidden">
      <CabeceraBanda
        icon="list" titulo={f.nodo_titulo} sub={[f.flujo_titulo, f.area_nombre].filter(Boolean).join(" · ")}
        total={f.en_cola} urgentes={f.urgentes} totalLabel="en cola"
        desde={masViejo(f.casos.map((c) => c.ingreso))} abierto={abierto} onToggle={() => setAbierto((v) => !v)}
      />

      <div className="flex items-center gap-2.5 border-t border-division bg-superficie-2 px-lg py-3">
        {f.mi_box ? (
          <Button disabled={!siguiente || llamar.isPending} onClick={() => alLlamar(siguiente)}>
            {llamar.isPending
              ? "Llamando…"
              : siguiente
                ? `Llamar siguiente${siguiente.ciudadano_nombre ? " · " + siguiente.ciudadano_nombre : ""}`
                : "Sin pacientes en cola"}
          </Button>
        ) : (
          <span className="text-md text-texto-tenue">Ocupá tu box (arriba, en «Tu box») para poder llamar.</span>
        )}
      </div>

      {abierto && (f.casos.length === 0 ? (
        <p className="border-t border-division p-lg text-center text-base text-texto-tenue">
          Nadie esperando en la sala por ahora.
        </p>
      ) : (
        <ul>
          {f.casos.slice(0, 6).map((c, i) => {
            const e = espera(c.ingreso);
            return (
              <li
                key={c.item_id}
                className={cn("flex items-center gap-2.5 border-t border-l-[3px] border-division py-2 pl-3 pr-lg", e.borde)}
              >
                <span className="w-5 text-right text-sm text-texto-tenue tabular-nums">{i + 1}</span>
                <PuntoPrioridad prioridad={c.prioridad || (c.urgente ? "urgente" : "normal")} />
                <span className="min-w-0 flex-1 truncate text-md">{c.ciudadano_nombre || "—"}</span>
                <span className={cn("shrink-0 text-sm tabular-nums", e.clase)}>{antiguedad(c.ingreso)}</span>
                <Button
                  size="sm" variant="secondary"
                  disabled={llamar.isPending || !f.mi_box}
                  title={!f.mi_box ? "Ocupá un box primero" : ""}
                  onClick={() => alLlamar(c)}
                >
                  Llamar
                </Button>
              </li>
            );
          })}
        </ul>
      ))}
    </Card>
  );
}

function PuntoPrioridad({ prioridad }) {
  const clase =
    prioridad === "urgente" ? "bg-danger" : prioridad === "alta" ? "bg-badge-amber-fg" : "bg-borde";
  return <span title={prioridad} className={cn("size-2.5 shrink-0 rounded-pill", clase)} />;
}

const PRIO_CHIP = { urgente: { label: "Urgente", tone: "error" }, alta: { label: "Alta", tone: "amber" } };
function ChipPrioridad({ prioridad }) {
  const p = PRIO_CHIP[prioridad];
  return p ? <Badge tone={p.tone}>{p.label}</Badge> : null;
}

// --------------------------------------------------------------------------- //
// Modales
// --------------------------------------------------------------------------- //
function ModalIngresarPaciente({ item, institucionId, onClose, onCreado }) {
  const toast = useToast();
  const [paciente, setPaciente] = useState(null);
  const [prioridad, setPrioridad] = useState("normal");

  const ingresar = useAccion(async () => {
    const caso = await api.post("/casos/", {
      institucion: institucionId, version: item.version_id, ciudadano: paciente.id, prioridad,
    });
    await api.post(`/casos/${caso.id}/iniciar/`);
    return caso;
  }, {
    invalida: ["lista", "mis-tareas"],
    onError: (e) => toast.deError(e, "No se pudo ingresar al paciente."),
  });

  return (
    <Modal
      title={`Ingresar paciente · ${item.flujo_titulo}`}
      onClose={onClose}
      width={520}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          {paciente && (
            <Button disabled={ingresar.isPending} onClick={() => ingresar.mutate(undefined, { onSuccess: (c) => onCreado(c.id) })}>
              {ingresar.isPending ? "Ingresando…" : "Ingresar e iniciar"}
            </Button>
          )}
        </>
      }
    >
      {paciente ? (
        <div className="flex flex-col gap-3.5">
          <PacienteElegido paciente={paciente} onCambiar={() => setPaciente(null)} />
          <Field label="Prioridad">
            <Select value={prioridad} onChange={(e) => setPrioridad(e.target.value)}>
              <option value="normal">Normal</option>
              <option value="alta">Alta</option>
              <option value="urgente">Urgente</option>
            </Select>
          </Field>
        </div>
      ) : (
        <BuscadorPaciente institucionId={institucionId} onElegir={setPaciente} />
      )}
    </Modal>
  );
}

function ModalEstadoPaciente({ institucionId, onIr, onClose }) {
  const [paciente, setPaciente] = useState(null);
  const casos = useLista(
    "casos",
    { institucion: institucionId, ciudadano: paciente?.id, pageSize: 20 },
    { enabled: !!paciente },
  );

  return (
    <Modal
      title="Estado de un paciente"
      onClose={onClose}
      width={520}
      footer={<Button variant="secondary" onClick={onClose}>Cerrar</Button>}
    >
      {!paciente ? (
        <BuscadorPaciente institucionId={institucionId} onElegir={setPaciente} permitirCrear={false} />
      ) : (
        <div className="flex flex-col gap-3.5">
          <PacienteElegido paciente={paciente} onCambiar={() => setPaciente(null)} />

          <Button variant="secondary" onClick={() => onIr(`/historia/${paciente.id}`)}>
            <Icon name="clipboard" size={15} /> Ver expediente (historia clínica)
          </Button>

          <div>
            <h4 className="mb-2 text-xs font-bold tracking-wide text-texto-tenue">SUS CASOS</h4>
            {casos.isLoading ? (
              <Skeleton className="h-20" />
            ) : casos.filas.length === 0 ? (
              <p className="text-md text-texto-tenue">No tiene casos registrados.</p>
            ) : (
              <ul className="overflow-hidden rounded-md border border-borde">
                {casos.filas.map((c) => {
                  const e = estadoCaso[c.estado] || { label: c.estado_display, tone: "neutral" };
                  return (
                    <li key={c.id}>
                      <button
                        onClick={() => onIr(`/casos/${c.id}`)}
                        className="flex w-full items-center gap-2.5 border-t border-division px-3.5 py-2.5 text-left first:border-t-0 hover:bg-superficie-2"
                      >
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-md font-semibold">{c.flujo_titulo}</span>
                          <span className="block truncate text-sm text-texto-tenue">
                            {c.paso_actual || "—"}{c.area_nombre ? ` · ${c.area_nombre}` : ""}
                          </span>
                        </span>
                        <Badge tone={e.tone}>{e.label}</Badge>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}

function CargandoTrabajo() {
  return (
    <div className="flex flex-col gap-7 px-lg pb-8 pt-[22px] sm:px-8" role="status" aria-label="Cargando tu trabajo…">
      <div className="grid grid-cols-[repeat(auto-fit,minmax(9.5rem,1fr))] gap-3">
        {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-[76px]" />)}
      </div>
      <Skeleton className="h-28" />
      <Skeleton className="h-64" />
    </div>
  );
}
