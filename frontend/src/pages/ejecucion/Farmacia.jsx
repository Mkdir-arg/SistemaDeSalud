import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import { Badge, Button, Field, Input, Modal, Select, Tabs } from "@/components/ui";
import { EstadoError, EstadoVacio, Skeleton } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { fechaHora } from "@/lib/format";
import { cn } from "@/lib/cn";

/*
 * Farmacia.
 *
 * Abre en «Qué resolver» y no en el listado de stock a propósito: lo primero
 * que alguien de farmacia necesita saber a la mañana es qué falta y qué vence,
 * no cuántas gasas hay. El listado completo está a un clic.
 */
export default function Farmacia() {
  const { institucion } = useInstitucion();
  const [tab, setTab] = useState("alertas");
  const [deposito, setDeposito] = useState("");

  const depositos = useLista(
    "depositos",
    { institucion: institucion?.id, activo: true, pageSize: 50 },
    { enabled: institucion?.id != null },
  );

  const TABS = [
    { key: "alertas", label: "Qué resolver" },
    { key: "stock", label: "Stock" },
    { key: "movimientos", label: "Movimientos" },
  ];

  return (
    <div className="flex flex-col gap-lg p-lg sm:p-[26px] lg:px-[30px]">
      <section className="flex flex-wrap items-center gap-lg rounded-lg border border-borde bg-superficie px-xl py-lg">
        <span className="flex size-11 shrink-0 items-center justify-center rounded-md bg-nodo-accion-tint text-nodo-accion-sol">
          <Icon name="cube" size={22} />
        </span>
        <div className="min-w-40 flex-1">
          <h2 className="text-xl font-bold">Farmacia e insumos</h2>
          <p className="text-base text-texto-debil">
            Stock por depósito · lo que falta y lo que vence
          </p>
        </div>
        <select
          aria-label="Depósito"
          value={deposito}
          onChange={(e) => setDeposito(e.target.value)}
          className="h-9 rounded-md border border-campo-borde bg-superficie px-2 text-md outline-none focus:border-accent"
        >
          <option value="">Todos los depósitos</option>
          {depositos.filas.map((d) => (
            <option key={d.id} value={d.id}>{d.nombre}</option>
          ))}
        </select>
      </section>

      <Tabs tabs={TABS} valor={tab} onChange={setTab} />

      {tab === "alertas" && <Alertas institucion={institucion} deposito={deposito} />}
      {tab === "stock" && <Stock institucion={institucion} deposito={deposito} depositos={depositos.filas} />}
      {tab === "movimientos" && <Movimientos institucion={institucion} deposito={deposito} />}
    </div>
  );
}

function Alertas({ institucion, deposito }) {
  const q = useQuery({
    queryKey: ["farmacia-alertas", institucion?.id, deposito],
    queryFn: () => api.get(
      `/pedidos-stock/alertas/?institucion=${institucion.id}${deposito ? `&deposito=${deposito}` : ""}`
    ),
    enabled: institucion?.id != null,
  });

  if (q.isLoading) return <Skeleton className="h-64" />;
  if (q.error) return <EstadoError error={q.error} onReintentar={q.refetch} />;

  const { faltantes = [], por_vencer: vencen = [] } = q.data || {};
  if (!faltantes.length && !vencen.length) {
    return (
      <EstadoVacio
        titulo="Nada que resolver"
        detalle="Ningún insumo está por debajo de su mínimo ni vence en los próximos dos meses."
        icono="check"
      />
    );
  }

  return (
    <div className="grid items-start gap-lg lg:grid-cols-2">
      <section className="overflow-hidden rounded-lg border border-borde bg-superficie">
        <header className="flex items-center gap-2 border-b border-division px-xl py-lg">
          <Icon name="alert" size={16} className="text-danger" />
          <h3 className="flex-1 text-lg font-bold">Por debajo del mínimo</h3>
          <Badge tone={faltantes.length ? "error" : "gray"}>{faltantes.length}</Badge>
        </header>
        {faltantes.length === 0 ? (
          <p className="px-xl py-lg text-base text-texto-tenue">No falta nada.</p>
        ) : (
          <ul className="divide-y divide-division">
            {faltantes.map((f, i) => (
              <li key={i} className="flex flex-wrap items-center gap-x-md gap-y-1 px-xl py-3">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-md font-semibold">{f.insumo}</span>
                  <span className="block text-sm text-texto-tenue">{f.deposito}</span>
                </span>
                {/* El número solo no dice nada: «3» es grave o irrelevante según
                    el mínimo. Se muestran los dos juntos. */}
                <span className="whitespace-nowrap tabular-nums">
                  <strong className="text-danger">{f.cantidad}</strong>
                  <span className="text-texto-tenue"> de {f.minimo} {f.unidad}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="overflow-hidden rounded-lg border border-borde bg-superficie">
        <header className="flex items-center gap-2 border-b border-division px-xl py-lg">
          <Icon name="refresh" size={16} className="text-badge-amber-fg" />
          <h3 className="flex-1 text-lg font-bold">Vencen pronto</h3>
          <Badge tone={vencen.length ? "warning" : "gray"}>{vencen.length}</Badge>
        </header>
        {vencen.length === 0 ? (
          <p className="px-xl py-lg text-base text-texto-tenue">Nada vence en los próximos dos meses.</p>
        ) : (
          <ul className="divide-y divide-division">
            {vencen.map((v, i) => (
              <li key={i} className="flex flex-wrap items-center gap-x-md gap-y-1 px-xl py-3">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-md font-semibold">{v.insumo}</span>
                  <span className="block text-sm text-texto-tenue">
                    {v.deposito} · lote {v.lote}
                  </span>
                </span>
                <span className="whitespace-nowrap text-right">
                  <span className={cn("block text-md font-bold tabular-nums",
                    v.vencido ? "text-danger" : "text-badge-amber-fg")}>
                    {v.vencido ? "vencido" : `en ${v.dias} d`}
                  </span>
                  <span className="block text-sm text-texto-tenue tabular-nums">
                    {v.cantidad} u.
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Stock({ institucion, deposito, depositos }) {
  const toast = useToast();
  const [busca, setBusca] = useState("");
  const [mover, setMover] = useState(null); // {existencia, modo}
  const q = useLista(
    "stock",
    {
      "deposito__institucion": institucion?.id,
      deposito: deposito || undefined,
      search: busca || undefined,
      pageSize: 300,
    },
    { enabled: institucion?.id != null },
  );

  // Se agrupa por insumo: quien mira quiere «cuánta dipirona hay», y una lista
  // con un renglón por lote obliga a sumar de cabeza.
  const porInsumo = useMemo(() => {
    const m = new Map();
    for (const e of q.filas) {
      const k = `${e.insumo}-${e.deposito}`;
      if (!m.has(k)) {
        m.set(k, {
          insumo: e.insumo, nombre: e.insumo_nombre, deposito: e.deposito,
          deposito_nombre: e.deposito_nombre, unidad: e.unidad,
          minimo: e.stock_minimo, total: 0, lotes: [],
        });
      }
      const g = m.get(k);
      g.total += e.cantidad;
      if (e.cantidad > 0) g.lotes.push(e);
    }
    return [...m.values()].sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
  }, [q.filas]);

  if (q.error) return <EstadoError error={q.error} onReintentar={q.refetch} />;

  return (
    <div className="flex flex-col gap-lg">
      <Input
        value={busca}
        onChange={(e) => setBusca(e.target.value)}
        placeholder="Buscar insumo, genérico o lote…"
        aria-label="Buscar en el stock"
      />
      {q.isLoading ? (
        <Skeleton className="h-64" />
      ) : porInsumo.length === 0 ? (
        <EstadoVacio titulo="Sin stock cargado" detalle="Registrá un ingreso para empezar." icono="cube" />
      ) : (
        <section className="overflow-hidden rounded-lg border border-borde bg-superficie">
          <ul className="divide-y divide-division">
            {porInsumo.map((g) => {
              const falta = g.minimo > 0 && g.total < g.minimo;
              return (
                <li key={`${g.insumo}-${g.deposito}`} className="px-xl py-3">
                  <div className="flex flex-wrap items-center gap-x-md gap-y-1.5">
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-md font-semibold">{g.nombre}</span>
                      <span className="block text-sm text-texto-tenue">{g.deposito_nombre}</span>
                    </span>
                    <span className="whitespace-nowrap text-right tabular-nums">
                      <span className={cn("text-md font-bold", falta && "text-danger")}>
                        {g.total}
                      </span>
                      <span className="text-sm text-texto-tenue"> {g.unidad}</span>
                      {g.minimo > 0 && (
                        <span className="block text-xs text-texto-tenue">mín. {g.minimo}</span>
                      )}
                    </span>
                    <Button size="sm" variant="secondary"
                            onClick={() => setMover({ grupo: g, modo: "consumo" })}>
                      Registrar salida
                    </Button>
                  </div>
                  {g.lotes.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {g.lotes.map((l) => (
                        <span
                          key={l.id}
                          className={cn(
                            "rounded-pill px-2 py-px text-xs font-medium",
                            l.vencido
                              ? "bg-badge-error-bg text-badge-error-fg"
                              : "bg-division text-texto-suave",
                          )}
                        >
                          {l.lote_numero ? `${l.lote_numero}: ` : ""}{l.cantidad}
                          {l.vencimiento && ` · vence ${l.vencimiento.split("-").reverse().join("/")}`}
                        </span>
                      ))}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {mover && (
        <MovimientoModal
          grupo={mover.grupo}
          depositos={depositos}
          onClose={() => setMover(null)}
          onListo={() => { setMover(null); q.refetch(); }}
          toast={toast}
        />
      )}
    </div>
  );
}

/** Salida de stock: consumo, transferencia o baja. */
function MovimientoModal({ grupo, depositos, onClose, onListo, toast }) {
  const [modo, setModo] = useState("consumo");
  const [cantidad, setCantidad] = useState(1);
  const [destino, setDestino] = useState("");
  const [motivo, setMotivo] = useState("");

  const registrar = useAccion(
    () => {
      const base = { deposito: grupo.deposito, insumo: grupo.insumo, cantidad: Number(cantidad), motivo };
      if (modo === "transferencia") {
        return api.post("/movimientos-stock/transferencia/", {
          origen: grupo.deposito, destino: Number(destino), insumo: grupo.insumo,
          cantidad: Number(cantidad), motivo,
        });
      }
      return api.post(`/movimientos-stock/${modo}/`, base);
    },
    {
      onSuccess: () => { toast.ok("Movimiento registrado."); onListo(); },
      onError: (e) => toast.deError(e, "No se pudo registrar el movimiento."),
    },
  );

  const otros = depositos.filter((d) => d.id !== grupo.deposito);
  // La baja pide motivo: sin él es indistinguible de un faltante, y el backend
  // lo rechaza. Decirlo acá evita el ida y vuelta.
  const faltaMotivo = modo === "baja" && !motivo.trim();
  const faltaDestino = modo === "transferencia" && !destino;

  return (
    <Modal
      title={`${grupo.nombre} · ${grupo.deposito_nombre}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button
            disabled={registrar.isPending || cantidad < 1 || faltaMotivo || faltaDestino}
            onClick={() => registrar.mutate()}
          >
            {registrar.isPending ? "…" : "Registrar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <div className="text-md text-texto-suave">
          Hay <strong className="tabular-nums">{grupo.total}</strong> {grupo.unidad}.
          {/* El lote lo elige el motor: primero el que vence antes. Decirlo evita
              que alguien lo busque y no lo encuentre. */}
          <span className="text-texto-tenue"> El lote se toma del que vence antes.</span>
        </div>
        <Field label="Tipo de salida">
          <Select value={modo} onChange={(e) => setModo(e.target.value)}>
            <option value="consumo">Consumo (se usó en un paciente)</option>
            <option value="transferencia">Transferencia a otro depósito</option>
            <option value="baja">Baja (vencido, roto, extraviado)</option>
          </Select>
        </Field>
        {modo === "transferencia" && (
          <Field label="Depósito de destino">
            <Select value={destino} onChange={(e) => setDestino(e.target.value)}>
              <option value="">Elegir…</option>
              {otros.map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}
            </Select>
          </Field>
        )}
        <Field label={`Cantidad (${grupo.unidad})`}>
          <Input type="number" min="1" max={grupo.total} value={cantidad}
                 onChange={(e) => setCantidad(e.target.value)} />
        </Field>
        <Field
          label={modo === "baja" ? "Motivo (obligatorio)" : "Motivo"}
          hint={modo === "baja" ? "Sin motivo, una baja es indistinguible de un faltante." : undefined}
        >
          <Input value={motivo} onChange={(e) => setMotivo(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}

const TONO_MOV = {
  ingreso: "success", consumo: "info", transferencia: "gray",
  ajuste: "warning", baja: "error",
};

function Movimientos({ institucion, deposito }) {
  const q = useLista(
    "movimientos-stock",
    {
      "insumo__institucion": institucion?.id,
      ordering: "-fecha",
      pageSize: 100,
    },
    { enabled: institucion?.id != null },
  );
  const filas = deposito
    ? q.filas.filter((m) => String(m.origen) === deposito || String(m.destino) === deposito)
    : q.filas;

  if (q.error) return <EstadoError error={q.error} onReintentar={q.refetch} />;
  if (q.isLoading) return <Skeleton className="h-64" />;
  if (!filas.length) {
    return <EstadoVacio titulo="Sin movimientos" detalle="Todavía no se registró ningún movimiento de stock." icono="list" />;
  }

  return (
    <section className="overflow-hidden rounded-lg border border-borde bg-superficie">
      <ul className="divide-y divide-division">
        {filas.map((m) => (
          <li key={m.id} className="flex flex-wrap items-center gap-x-md gap-y-1 px-xl py-3">
            <Badge tone={TONO_MOV[m.tipo] || "gray"}>{m.tipo_display}</Badge>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-md font-semibold">
                {m.cantidad} × {m.insumo_nombre}
              </span>
              <span className="block truncate text-sm text-texto-tenue">
                {[m.origen_nombre && `de ${m.origen_nombre}`,
                  m.destino_nombre && `a ${m.destino_nombre}`,
                  m.lote_numero && `lote ${m.lote_numero}`,
                  m.paciente,
                  m.motivo].filter(Boolean).join(" · ")}
              </span>
            </span>
            <span className="whitespace-nowrap text-right text-sm text-texto-tenue">
              <span className="block">{fechaHora(m.fecha)}</span>
              {m.autor_nombre && <span className="block">{m.autor_nombre}</span>}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
