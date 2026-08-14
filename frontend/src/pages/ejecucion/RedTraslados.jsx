import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import { Badge, Button, Field, Input, Modal, Select, Tabs, Textarea } from "@/components/ui";
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
  solicitado: { label: "Esperando respuesta", tone: "warning" },
  aceptado: { label: "Aceptado", tone: "success" },
  rechazado: { label: "Rechazado", tone: "error" },
  en_camino: { label: "En camino", tone: "info" },
  recibido: { label: "Recibido", tone: "success" },
  cancelado: { label: "Cancelado", tone: "gray" },
};

export default function RedTraslados() {
  const { institucion } = useInstitucion();
  const [tab, setTab] = useState(null);

  const redes = useLista("redes", { activa: true, pageSize: 20 });
  const red = redes.filas[0];

  /*
   * La pestaña inicial depende de lo que este establecimiento hace.
   *
   * Un hospital chico deriva y no recibe: abrirlo siempre en «Nos derivan» lo
   * dejaba mirando una pantalla vacía, que es justo su caso normal y no una
   * excepción. Se abre donde hay algo que ver, y sólo se decide una vez —si
   * después la persona cambia de pestaña, se respeta—.
   */
  const entrantes = useLista("traslados", { lado: "entrantes", pageSize: 1 });
  const salientes = useLista("traslados", { lado: "salientes", pageSize: 1 });
  useEffect(() => {
    if (tab !== null || entrantes.isLoading || salientes.isLoading) return;
    setTab(entrantes.total > 0 || salientes.total === 0 ? "entrantes" : "salientes");
  }, [tab, entrantes.isLoading, entrantes.total, salientes.isLoading, salientes.total]);

  const TABS = [
    { key: "entrantes", label: "Nos derivan" },
    { key: "salientes", label: "Derivamos" },
    { key: "panorama", label: "Panorama de la red" },
  ];

  if (redes.isLoading) return <Cargando />;
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
      </section>

      <Tabs tabs={TABS} valor={tab} onChange={setTab} />

      {tab === null ? (
        <Skeleton className="h-64" />
      ) : tab === "panorama" ? (
        <Panorama red={red} institucion={institucion} />
      ) : (
        <Lista lado={tab} />
      )}
    </div>
  );
}

function Lista({ lado }) {
  const toast = useToast();
  const navigate = useNavigate();
  const [respondiendo, setRespondiendo] = useState(null);
  const q = useLista("traslados", { lado, ordering: "-urgente,-solicitado_at", pageSize: 100 });

  const accion = useAccion(
    ({ id, nombre, cuerpo }) => api.post(`/traslados/${id}/${nombre}/`, cuerpo || {}),
    {
      onSuccess: (_, { ok }) => { toast.ok(ok); q.refetch(); setRespondiendo(null); },
      onError: (e) => toast.deError(e),
    },
  );

  if (q.error) return <EstadoError error={q.error} onReintentar={q.refetch} />;
  if (q.isLoading) return <Skeleton className="h-64" />;
  if (!q.filas.length) {
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

  // Lo pendiente arriba: es lo único que requiere una decisión.
  const pendientes = q.filas.filter((t) => t.abierto);
  const cerrados = q.filas.filter((t) => !t.abierto);

  return (
    <div className="flex flex-col gap-lg">
      {pendientes.length > 0 && (
        <section className="overflow-hidden rounded-lg border border-borde bg-superficie">
          <header className="flex items-center gap-2 border-b border-division px-xl py-lg">
            <h3 className="flex-1 text-lg font-bold">En curso</h3>
            <Badge tone="warning">{pendientes.length}</Badge>
          </header>
          <ul className="divide-y divide-division">
            {pendientes.map((t) => (
              <Fila key={t.id} t={t} accion={accion} navigate={navigate}
                    onResponder={() => setRespondiendo(t)} />
            ))}
          </ul>
        </section>
      )}

      {cerrados.length > 0 && (
        <section className="overflow-hidden rounded-lg border border-borde bg-superficie">
          <header className="border-b border-division px-xl py-lg">
            <h3 className="text-lg font-bold">Resueltos</h3>
          </header>
          <ul className="divide-y divide-division">
            {cerrados.map((t) => (
              <Fila key={t.id} t={t} accion={accion} navigate={navigate} />
            ))}
          </ul>
        </section>
      )}

      {respondiendo && (
        <ResponderModal
          t={respondiendo}
          accion={accion}
          onClose={() => setRespondiendo(null)}
        />
      )}
    </div>
  );
}

function Fila({ t, accion, navigate, onResponder }) {
  const est = ESTADOS[t.estado] || { label: t.estado_display, tone: "gray" };
  const ocupado = accion.isPending;
  // El caso propio: el del otro lado no se puede abrir, y ofrecerlo sería
  // prometer algo que el servidor va a rechazar.
  const miCaso = t.soy_origen ? t.caso_origen : t.caso_destino;

  return (
    <li className="flex flex-wrap items-center gap-x-md gap-y-2 px-xl py-3.5">
      {t.urgente && <Badge tone="error">urgente</Badge>}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-md font-semibold">{t.paciente}</span>
        <span className="block truncate text-sm text-texto-tenue">
          {t.soy_origen ? `a ${t.destino_nombre}` : `desde ${t.origen_nombre}`}
          {" · "}{t.motivo_display}
          {t.area_destino_nombre && ` · ${t.area_destino_nombre}`}
        </span>
        {/* El motivo del rechazo es lo que dice si insistir o buscar otro. */}
        {t.estado === "rechazado" && t.respuesta && (
          <span className="mt-0.5 block text-sm text-danger">{t.respuesta}</span>
        )}
      </span>

      <span className="whitespace-nowrap text-right text-sm text-texto-tenue">
        <Badge tone={est.tone}>{est.label}</Badge>
        <span className="mt-0.5 block">hace {antiguedad(t.solicitado_at)}</span>
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
        {!t.soy_origen && (t.estado === "aceptado" || t.estado === "en_camino") && (
          <Button size="sm" disabled={ocupado}
                  onClick={() => accion.mutate({ id: t.id, nombre: "recibido", ok: "Paciente recibido" })}>
            Llegó
          </Button>
        )}
        {t.soy_origen && t.estado === "aceptado" && (
          <Button size="sm" disabled={ocupado}
                  onClick={() => accion.mutate({ id: t.id, nombre: "en-camino", ok: "Traslado en camino" })}>
            Salió
          </Button>
        )}
        {t.soy_origen && t.estado === "solicitado" && (
          <Button size="sm" variant="secondary" disabled={ocupado}
                  onClick={() => accion.mutate({ id: t.id, nombre: "cancelar", ok: "Traslado cancelado" })}>
            Cancelar
          </Button>
        )}
      </div>
    </li>
  );
}

/** Aceptar (eligiendo área) o rechazar (con motivo). */
function ResponderModal({ t, accion, onClose }) {
  const { institucion } = useInstitucion();
  const [area, setArea] = useState(t.area_destino || "");
  const [motivo, setMotivo] = useState("");
  const areas = useLista("areas", { institucion: institucion?.id, activa: true, pageSize: 100 });

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
          hint="Se abre un caso en el flujo publicado de esa área."
        >
          <Select value={area} onChange={(e) => setArea(e.target.value)}>
            <option value="">Elegir…</option>
            {areas.filas.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
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
          <Cifra n={totales.pendientes} l="sin responder"
                 tono={totales.pendientes > 0 ? "text-badge-amber-fg" : undefined} />
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
              <th className="px-3 py-2.5 text-right">CAMAS</th>
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
                  {e.camas_operativas ? `${e.camas_libres}/${e.camas_operativas}` : "—"}
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
