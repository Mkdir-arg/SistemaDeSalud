import { useEffect, useMemo, useState } from "react";
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
  // El insumo que se vino a resolver desde una alerta. Sin esto, actuar sobre un
  // faltante obligaba a memorizar insumo y depósito, ir a Stock y buscarlo.
  const [foco, setFoco] = useState(null);

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

  const resolver = (f) => {
    setDeposito(String(f.deposito_id));
    setFoco({ id: f.insumo_id, nombre: f.insumo });
    setTab("stock");
  };

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

      {tab === "alertas" && (
        <Alertas institucion={institucion} deposito={deposito} onResolver={resolver} />
      )}
      {tab === "stock" && (
        <Stock
          institucion={institucion}
          deposito={deposito}
          depositos={depositos.filas}
          foco={foco}
          onQuitarFoco={() => setFoco(null)}
        />
      )}
      {tab === "movimientos" && (
        <Movimientos institucion={institucion} deposito={deposito} depositos={depositos.filas} />
      )}
    </div>
  );
}

/** Pie de lista: qué parte se está viendo y cómo pasar de página. */
function Paginacion({ pagina, paginas, total, mostrando, irA, unidad }) {
  if (!total) return null;
  const btn =
    "flex size-8 items-center justify-center rounded-md border border-borde text-texto-suave " +
    "enabled:hover:bg-superficie-2 disabled:opacity-40 disabled:cursor-not-allowed";
  return (
    <div className="flex flex-wrap items-center justify-between gap-md border-t border-division px-lg py-2.5">
      {/* «25 de 531» y no «25»: una lista que se corta en silencio hace que la
          respuesta a «¿quién sacó las ampollas?» sea «no figura» cuando en
          realidad es «está más atrás». */}
      <div className="text-base text-texto-debil">
        Mostrando <b className="font-semibold text-texto-medio">{mostrando}</b> de{" "}
        <b className="font-semibold text-texto-medio">{total}</b> {unidad}
      </div>
      {paginas > 1 && (
        <div className="flex items-center gap-1">
          <button className={btn} onClick={() => irA(pagina - 1)} disabled={pagina <= 1}
                  aria-label="Página anterior"><Icon name="chevronLeft" size={15} /></button>
          <span className="px-2 text-base tabular-nums text-texto-suave">{pagina} / {paginas}</span>
          <button className={btn} onClick={() => irA(pagina + 1)} disabled={pagina >= paginas}
                  aria-label="Página siguiente"><Icon name="chevronRight" size={15} /></button>
        </div>
      )}
    </div>
  );
}

function Alertas({ institucion, deposito, onResolver }) {
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
        icono="inbox"
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
              <li key={i}>
                {/* El renglón lleva a su fila del stock con el depósito puesto:
                    una alerta que no se puede accionar se deja de mirar. */}
                <button
                  type="button"
                  onClick={() => onResolver(f)}
                  className="flex w-full flex-wrap items-center gap-x-md gap-y-1 px-xl py-3 text-left hover:bg-superficie-2"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-md font-semibold">{f.insumo}</span>
                    <span className="block text-sm text-texto-tenue">{f.deposito}</span>
                  </span>
                  {/* El número solo no dice nada: «3» es grave o irrelevante según
                      el mínimo. Se muestran los dos juntos. */}
                  <span className="whitespace-nowrap text-right tabular-nums">
                    <span className="block">
                      <strong className="text-danger">{f.cantidad}</strong>
                      <span className="text-texto-tenue"> de {f.minimo} {f.unidad}</span>
                    </span>
                    {/* Tener todo vencido no es lo mismo que no tener: hay algo
                        que dar de baja y alguien a quien reclamarle. */}
                    {f.vencida > 0 && (
                      <span className="block text-sm text-danger">{f.vencida} vencida/s</span>
                    )}
                  </span>
                  <Icon name="chevronRight" size={15} className="text-texto-tenue" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="overflow-hidden rounded-lg border border-borde bg-superficie">
        <header className="flex items-center gap-2 border-b border-division px-xl py-lg">
          <Icon name="refresh" size={16} className="text-badge-amber-fg" />
          <h3 className="flex-1 text-lg font-bold">Vencen pronto</h3>
          <Badge tone={vencen.length ? "amber" : "gray"}>{vencen.length}</Badge>
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

/** Ordena los lotes de un insumo como se sacan del estante: primero el que vence antes. */
function porVencimiento(a, b) {
  if (!a.vencimiento) return 1;
  if (!b.vencimiento) return -1;
  return a.vencimiento.localeCompare(b.vencimiento);
}

function Stock({ institucion, deposito, depositos, foco, onQuitarFoco }) {
  const toast = useToast();
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);
  const [mover, setMover] = useState(null);
  const [recuento, setRecuento] = useState(null);
  const [ingreso, setIngreso] = useState(false);

  const q = useLista(
    "stock",
    {
      "deposito__institucion": institucion?.id,
      deposito: deposito || undefined,
      insumo: foco?.id || undefined,
      search: busca || undefined,
      // Agrupamos por (depósito, insumo): pidiendo ese mismo orden, los renglones
      // de un grupo llegan juntos y sólo el del borde puede quedar partido entre
      // dos páginas.
      ordering: "deposito__nombre,insumo__nombre",
      page: pagina,
      // 200 es el máximo que sirve el servidor (cauce/pagination.py). Pedir 300
      // no traía 300: recortaba en silencio y el total del insumo del corte
      // salía menor al real, en rojo como faltante teniendo el resto.
      pageSize: 200,
    },
    { enabled: institucion?.id != null },
  );

  useEffect(() => { setPagina(1); }, [deposito, busca, foco?.id]);

  // Se agrupa por insumo: quien mira quiere «cuánta dipirona hay», y una lista
  // con un renglón por lote obliga a sumar de cabeza.
  const grupos = useMemo(() => {
    const m = new Map();
    for (const e of q.filas) {
      const k = `${e.deposito}-${e.insumo}`;
      if (!m.has(k)) {
        m.set(k, {
          insumo: e.insumo, nombre: e.insumo_nombre, deposito: e.deposito,
          deposito_nombre: e.deposito_nombre, unidad: e.unidad,
          minimo: e.stock_minimo, usable: 0, vencido: 0, lotes: [],
        });
      }
      const g = m.get(k);
      // Lo vencido se cuenta aparte: sumarlo hacía que un botiquín con toda la
      // adrenalina vencida se leyera igual que uno abastecido, y que enfermería
      // se enterara recién al cargar el consumo, en el paro.
      if (e.vencido) g.vencido += e.cantidad;
      else g.usable += e.cantidad;
      g.lotes.push(e);
    }
    const lista = [...m.values()];
    for (const g of lista) g.lotes.sort(porVencimiento);
    return lista.map((g, i) => ({
      ...g,
      // El grupo del borde puede seguir en la página de al lado: su total no es
      // el total real, así que no se usa para pintar el rojo de «falta».
      parcial: q.paginas > 1
        && ((pagina > 1 && i === 0) || (pagina < q.paginas && i === lista.length - 1)),
    }));
  }, [q.filas, q.paginas, pagina]);

  if (q.error) return <EstadoError error={q.error} onReintentar={q.refetch} />;

  return (
    <div className="flex flex-col gap-lg">
      <div className="flex flex-wrap items-center gap-md">
        <div className="min-w-52 flex-1">
          <Input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar insumo, genérico o lote…"
            aria-label="Buscar en el stock"
          />
        </div>
        <Button onClick={() => setIngreso(true)}>
          <Icon name="plus" size={15} /> Registrar ingreso
        </Button>
      </div>

      {foco && (
        <div className="flex flex-wrap items-center gap-md rounded-md border border-borde bg-superficie px-lg py-2.5 text-base">
          <span className="text-texto-suave">
            Mostrando sólo <b className="font-semibold">{foco.nombre}</b>
          </span>
          <button onClick={onQuitarFoco} className="font-semibold text-accent hover:underline">
            Ver todo el stock
          </button>
        </div>
      )}

      {q.isLoading ? (
        <Skeleton className="h-64" />
      ) : grupos.length === 0 ? (
        <EstadoVacio
          titulo="Sin stock cargado"
          detalle="Registrá un ingreso para empezar."
          icono="cube"
          accion={<Button onClick={() => setIngreso(true)}>Registrar ingreso</Button>}
        />
      ) : (
        <section className="overflow-hidden rounded-lg border border-borde bg-superficie">
          <ul className="divide-y divide-division">
            {grupos.map((g) => {
              const falta = g.minimo > 0 && !g.parcial && g.usable < g.minimo;
              return (
                <li key={`${g.insumo}-${g.deposito}`} className="px-xl py-3">
                  <div className="flex flex-wrap items-center gap-x-md gap-y-1.5">
                    {/* El nombre se lleva la fila entera en pantallas angostas: lo
                        que se cortaba al final era la presentación y la dosis
                        («Ampolla 1 mg/ml» vs «Comprimido 500 mg»), que es lo
                        único que distingue dos renglones del mismo genérico. */}
                    <span className="w-full min-w-0 sm:w-auto sm:flex-1">
                      <span className="block text-md font-semibold sm:truncate" title={g.nombre}>
                        {g.nombre}
                      </span>
                      <span className="block text-sm text-texto-tenue">{g.deposito_nombre}</span>
                    </span>
                    <span className="ml-auto whitespace-nowrap text-right tabular-nums">
                      <span className={cn("text-md font-bold", falta && "text-danger")}>
                        {g.usable}{g.parcial && "+"}
                      </span>
                      <span className="text-sm text-texto-tenue"> {g.unidad}</span>
                      {g.vencido > 0 && (
                        <span className="block text-xs font-semibold text-danger">
                          {g.vencido} vencida/s
                        </span>
                      )}
                      {g.minimo > 0 && (
                        <span className="block text-xs text-texto-tenue">mín. {g.minimo}</span>
                      )}
                    </span>
                    <span className="flex gap-1.5">
                      {/* Con el insumo en el nombre accesible: si no, la lista es
                          una fila de veinte botones que se llaman igual. */}
                      <Button size="sm" variant="secondary"
                              aria-label={`Registrar salida de ${g.nombre} en ${g.deposito_nombre}`}
                              onClick={() => setMover(g)}>
                        Salida
                      </Button>
                      <Button size="sm" variant="secondary"
                              aria-label={`Ajustar por recuento ${g.nombre} en ${g.deposito_nombre}`}
                              onClick={() => setRecuento(g)}>
                        Recuento
                      </Button>
                    </span>
                  </div>
                  {g.lotes.some((l) => l.cantidad > 0) && (
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {g.lotes.filter((l) => l.cantidad > 0).map((l) => (
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
          <Paginacion
            pagina={pagina}
            paginas={q.paginas}
            total={q.total}
            mostrando={q.filas.length}
            irA={setPagina}
            unidad="renglones de stock"
          />
        </section>
      )}

      {mover && (
        <MovimientoModal
          grupo={mover}
          depositos={depositos}
          onClose={() => setMover(null)}
          onListo={() => { setMover(null); q.refetch(); }}
          toast={toast}
        />
      )}
      {recuento && (
        <RecuentoModal
          grupo={recuento}
          onClose={() => setRecuento(null)}
          onListo={() => { setRecuento(null); q.refetch(); }}
          toast={toast}
        />
      )}
      {ingreso && (
        <IngresoModal
          institucion={institucion}
          depositos={depositos}
          depositoInicial={deposito}
          onClose={() => setIngreso(false)}
          onListo={() => { setIngreso(false); q.refetch(); }}
          toast={toast}
        />
      )}
    </div>
  );
}

/**
 * Salida de stock: transferencia o baja.
 *
 * El consumo NO está acá y es a propósito: esta pantalla no sabe a qué paciente
 * se le dio, y un consumo sin caso no aparece en `trazar-lote` —cuando ANMAT
 * retira el lote, la respuesta sobre esas unidades es «no sabemos»—. Se registra
 * en el caso, que es donde el sistema ya sabe el paciente y el depósito.
 */
function MovimientoModal({ grupo, depositos, onClose, onListo, toast }) {
  const otros = depositos.filter((d) => d.id !== grupo.deposito);
  const [modo, setModo] = useState(otros.length ? "transferencia" : "baja");
  const [cantidad, setCantidad] = useState(1);
  const [destino, setDestino] = useState("");
  const [motivo, setMotivo] = useState("");
  const conStock = grupo.lotes.filter((l) => l.cantidad > 0);
  const conLote = conStock.filter((l) => l.lote);
  const [lote, setLote] = useState(() => (conLote[0] ? String(conLote[0].lote) : ""));

  const elegido = conLote.find((l) => String(l.lote) === lote);
  const tope = modo === "baja" && conLote.length ? (elegido?.cantidad ?? 0) : grupo.usable;

  const registrar = useAccion(
    () => {
      if (modo === "transferencia") {
        return api.post("/movimientos-stock/transferencia/", {
          origen: grupo.deposito, destino: Number(destino), insumo: grupo.insumo,
          cantidad: Number(cantidad), motivo,
        });
      }
      // La baja va con lote: es de una partida concreta —normalmente la
      // vencida— y elegirla es justamente lo que se quiere registrar.
      return api.post("/movimientos-stock/baja/", {
        deposito: grupo.deposito, insumo: grupo.insumo, cantidad: Number(cantidad),
        lote: elegido ? Number(lote) : undefined, motivo,
      });
    },
    {
      onSuccess: () => { toast.ok("Movimiento registrado."); onListo(); },
      onError: (e) => toast.deError(e, "No se pudo registrar el movimiento."),
    },
  );

  // La baja pide motivo: sin él es indistinguible de un faltante, y el backend
  // lo rechaza. Decirlo acá evita el ida y vuelta.
  const faltaMotivo = modo === "baja" && !motivo.trim();
  const faltaDestino = modo === "transferencia" && !destino;
  const faltaLote = modo === "baja" && conLote.length > 0 && !elegido;

  return (
    <Modal
      title={`${grupo.nombre} · ${grupo.deposito_nombre}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button
            disabled={registrar.isPending || cantidad < 1 || faltaMotivo || faltaDestino || faltaLote}
            onClick={() => registrar.mutate()}
          >
            {registrar.isPending ? "…" : "Registrar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <div className="text-md text-texto-suave">
          Hay <strong className="tabular-nums">{grupo.usable}</strong> {grupo.unidad} en condiciones
          {grupo.vencido > 0 && (
            <strong className="text-danger"> y {grupo.vencido} vencida/s</strong>
          )}.
          <span className="text-texto-tenue">
            {modo === "transferencia"
              ? " La transferencia toma el lote que vence antes."
              : " La baja sale del lote que elijas."}
          </span>
        </div>
        <Field label="Tipo de salida">
          <Select value={modo} onChange={(e) => setModo(e.target.value)}>
            {otros.length > 0 && <option value="transferencia">Transferencia a otro depósito</option>}
            <option value="baja">Baja (vencido, roto, extraviado)</option>
          </Select>
        </Field>
        <p className="text-sm text-texto-tenue">
          Lo que se usó en un paciente se registra en su caso: es lo que lo deja imputado
          a quien lo recibió.
        </p>
        {modo === "transferencia" && (
          <Field label="Depósito de destino">
            <Select value={destino} onChange={(e) => setDestino(e.target.value)}>
              <option value="">Elegir…</option>
              {otros.map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}
            </Select>
          </Field>
        )}
        {modo === "baja" && conLote.length > 0 && (
          <Field label="Lote que se da de baja">
            <Select value={lote} onChange={(e) => setLote(e.target.value)}>
              {conLote.map((l) => (
                <option key={l.id} value={l.lote}>
                  {l.lote_numero} · {l.cantidad} {grupo.unidad}
                  {l.vencimiento && ` · vence ${l.vencimiento.split("-").reverse().join("/")}`}
                  {l.vencido ? " · VENCIDO" : ""}
                </option>
              ))}
            </Select>
          </Field>
        )}
        <Field label={`Cantidad (${grupo.unidad})`}>
          <Input type="number" min="1" max={tope} value={cantidad}
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

/**
 * Recuento de inventario.
 *
 * Se cuenta lote por lote, que es como se cuenta en el estante: un ajuste sin
 * lote dejaba unidades que no vencen nunca y que ante un retiro no se pueden
 * atribuir a ninguna partida.
 */
function RecuentoModal({ grupo, onClose, onListo, toast }) {
  const filas = grupo.lotes.length
    ? grupo.lotes
    : [{ id: "sin-lote", lote: null, lote_numero: null, cantidad: 0 }];
  const [contados, setContados] = useState(
    () => Object.fromEntries(filas.map((f) => [f.id, String(f.cantidad)])),
  );
  const [motivo, setMotivo] = useState("");

  const guardar = useAccion(
    async () => {
      const cambios = filas.filter((f) => Number(contados[f.id]) !== f.cantidad);
      for (const f of cambios) {
        await api.post("/movimientos-stock/ajuste/", {
          deposito: grupo.deposito, insumo: grupo.insumo, lote: f.lote || undefined,
          contado: Number(contados[f.id]), motivo,
        });
      }
      return cambios.length;
    },
    {
      onSuccess: (n) => {
        toast.ok(n ? "Recuento registrado." : "El recuento coincide con el sistema: no hubo ajuste.");
        onListo();
      },
      onError: (e) => toast.deError(e, "No se pudo registrar el recuento."),
    },
  );

  const invalido = filas.some((f) => {
    const n = Number(contados[f.id]);
    return contados[f.id] === "" || Number.isNaN(n) || n < 0;
  });

  return (
    <Modal
      title={`Recuento · ${grupo.nombre}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardar.isPending || invalido} onClick={() => guardar.mutate()}>
            {guardar.isPending ? "…" : "Guardar recuento"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <div className="text-md text-texto-suave">
          {grupo.deposito_nombre} · anotá lo que contaste en el estante.
          <span className="block text-sm text-texto-tenue">
            La diferencia queda como un movimiento de ajuste con su motivo, así no es
            un número que cambió solo.
          </span>
        </div>
        {filas.map((f) => (
          <Field
            key={f.id}
            label={f.lote_numero ? `Lote ${f.lote_numero}` : "Sin lote"}
            hint={`El sistema tiene ${f.cantidad} ${grupo.unidad}`}
          >
            <Input
              type="number" min="0" value={contados[f.id]}
              onChange={(e) => setContados({ ...contados, [f.id]: e.target.value })}
            />
          </Field>
        ))}
        <Field label="Motivo">
          <Input value={motivo} onChange={(e) => setMotivo(e.target.value)}
                 placeholder="Recuento mensual" />
        </Field>
      </div>
    </Modal>
  );
}

/**
 * Ingreso de mercadería.
 *
 * Sin esto el stock sólo podía bajar: lo que llega no tenía dónde anotarse, así
 * que la pantalla empezaba a diferir del estante la primera semana y no volvía
 * nunca. Como la mayoría de los insumos llevan lote, el alta de la partida va en
 * el mismo paso: obligar a cargarla en otra pantalla que no existe es lo mismo
 * que no tener ingreso.
 */
function IngresoModal({ institucion, depositos, depositoInicial, onClose, onListo, toast }) {
  const [deposito, setDeposito] = useState(depositoInicial || "");
  const [busca, setBusca] = useState("");
  const [insumo, setInsumo] = useState(null);
  const [cantidad, setCantidad] = useState(1);
  const [lote, setLote] = useState("");
  const [numero, setNumero] = useState("");
  const [vence, setVence] = useState("");
  const [motivo, setMotivo] = useState("");

  const insumos = useLista(
    "insumos",
    { institucion: institucion?.id, activo: true, search: busca || undefined, pageSize: 20 },
    { enabled: institucion?.id != null && busca.trim().length >= 2 },
  );
  const lotes = useLista(
    "lotes",
    { insumo: insumo?.id, pageSize: 50 },
    { enabled: insumo != null },
  );

  const registrar = useAccion(
    async () => {
      let loteId = lote && lote !== "nuevo" ? Number(lote) : null;
      if (lote === "nuevo") {
        const creado = await api.post("/lotes/", {
          insumo: insumo.id, numero: numero.trim(), vencimiento: vence || null,
        });
        loteId = creado.id;
      }
      return api.post("/movimientos-stock/ingreso/", {
        deposito: Number(deposito), insumo: insumo.id, cantidad: Number(cantidad),
        lote: loteId || undefined, motivo,
      });
    },
    {
      onSuccess: () => { toast.ok("Ingreso registrado."); onListo(); },
      onError: (e) => toast.deError(e, "No se pudo registrar el ingreso."),
    },
  );

  const faltaLote = insumo?.requiere_lote
    && (!lote || (lote === "nuevo" && !numero.trim()));
  const listo = deposito && insumo && Number(cantidad) > 0 && !faltaLote;

  return (
    <Modal
      title="Registrar ingreso"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={registrar.isPending || !listo} onClick={() => registrar.mutate()}>
            {registrar.isPending ? "…" : "Registrar ingreso"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Depósito">
          <Select value={deposito} onChange={(e) => setDeposito(e.target.value)}>
            <option value="">Elegir…</option>
            {depositos.map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}
          </Select>
        </Field>

        {insumo ? (
          <Field label="Insumo">
            <div className="flex flex-wrap items-center gap-md rounded-md border border-campo-borde px-2.5 py-2">
              <span className="min-w-0 flex-1 text-md font-semibold">{insumo.nombre_completo}</span>
              <button
                className="text-base font-semibold text-accent hover:underline"
                onClick={() => { setInsumo(null); setLote(""); }}
              >
                Cambiar
              </button>
            </div>
          </Field>
        ) : (
          <Field label="Insumo" hint="Escribí al menos dos letras del nombre o del genérico.">
            <Input value={busca} onChange={(e) => setBusca(e.target.value)}
                   placeholder="Buscar en el catálogo…" />
            {busca.trim().length >= 2 && (
              <div className="mt-1.5 max-h-40 overflow-y-auto rounded-md border border-borde">
                {insumos.isLoading ? (
                  <p className="px-2.5 py-2 text-base text-texto-tenue">Buscando…</p>
                ) : insumos.filas.length === 0 ? (
                  <p className="px-2.5 py-2 text-base text-texto-tenue">
                    Nada con ese nombre en el catálogo.
                  </p>
                ) : (
                  insumos.filas.map((i) => (
                    <button
                      key={i.id}
                      className="block w-full px-2.5 py-2 text-left text-base hover:bg-superficie-2"
                      onClick={() => {
                        setInsumo({
                          id: i.id, requiere_lote: i.requiere_lote, unidad: i.unidad,
                          nombre_completo: `${i.nombre} ${i.presentacion}`.trim(),
                        });
                        setLote("");
                      }}
                    >
                      {i.nombre} {i.presentacion}
                      {i.controlado && <span className="text-danger"> · controlado</span>}
                    </button>
                  ))
                )}
              </div>
            )}
          </Field>
        )}

        {insumo?.requiere_lote && (
          <Field
            label="Lote"
            hint="Sin lote no se puede responder un retiro de ANMAT."
          >
            <Select value={lote} onChange={(e) => setLote(e.target.value)}>
              <option value="">Elegir…</option>
              {lotes.filas.map((l) => (
                <option key={l.id} value={l.id} disabled={l.vencido}>
                  {l.numero}
                  {l.vencimiento && ` · vence ${l.vencimiento.split("-").reverse().join("/")}`}
                  {l.vencido ? " · vencido" : ""}
                </option>
              ))}
              <option value="nuevo">Cargar una partida nueva…</option>
            </Select>
          </Field>
        )}
        {lote === "nuevo" && (
          <div className="flex flex-wrap gap-md">
            <div className="min-w-40 flex-1">
              <Field label="Número de lote">
                <Input value={numero} onChange={(e) => setNumero(e.target.value)} />
              </Field>
            </div>
            <div className="min-w-40 flex-1">
              <Field label="Vencimiento">
                <Input type="date" value={vence} onChange={(e) => setVence(e.target.value)} />
              </Field>
            </div>
          </div>
        )}

        <Field label={`Cantidad${insumo ? ` (${insumo.unidad})` : ""}`}>
          <Input type="number" min="1" value={cantidad}
                 onChange={(e) => setCantidad(e.target.value)} />
        </Field>
        <Field label="Motivo">
          <Input value={motivo} onChange={(e) => setMotivo(e.target.value)}
                 placeholder="Compra, donación, remito…" />
        </Field>
      </div>
    </Modal>
  );
}

// Los tonos son los que `Badge` conoce (ui.jsx). `success` y `warning` no
// existen: caían en el gris neutro, así que un ajuste de inventario —el evento
// que se busca cuando el stock no cuadra— se veía igual que una carga de rutina.
const TONO_MOV = {
  ingreso: "green", consumo: "info", transferencia: "gray",
  ajuste: "amber", baja: "error",
};

function Movimientos({ institucion, deposito, depositos }) {
  const [pagina, setPagina] = useState(1);
  const q = useLista(
    "movimientos-stock",
    {
      "insumo__institucion": institucion?.id,
      // El filtro va al servidor: aplicado sobre las filas ya traídas, elegir un
      // depósito mostraba «Sin movimientos» aunque hubiera habido veinte esa
      // mañana, más atrás en el historial.
      deposito: deposito || undefined,
      ordering: "-fecha",
      page: pagina,
      pageSize: 25,
    },
    { enabled: institucion?.id != null },
  );

  useEffect(() => { setPagina(1); }, [deposito]);

  if (q.error) return <EstadoError error={q.error} onReintentar={q.refetch} />;
  if (q.isLoading) return <Skeleton className="h-64" />;
  if (!q.filas.length) {
    const nombre = depositos.find((d) => String(d.id) === String(deposito))?.nombre;
    return (
      <EstadoVacio
        titulo="Sin movimientos"
        // Decir «nunca se registró nada» sobre un depósito que sí tuvo
        // movimientos hace que quien busca cierre la pantalla convencido de que
        // nadie tocó nada.
        detalle={deposito
          ? `No hay movimientos de ${nombre || "ese depósito"}.`
          : "Todavía no se registró ningún movimiento de stock."}
        icono="list"
      />
    );
  }

  return (
    <section className="overflow-hidden rounded-lg border border-borde bg-superficie">
      <ul className="divide-y divide-division">
        {q.filas.map((m) => (
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
      <Paginacion
        pagina={pagina}
        paginas={q.paginas}
        total={q.total}
        mostrando={q.filas.length}
        irA={setPagina}
        unidad="movimientos"
      />
    </section>
  );
}
