import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api, tokens } from "@/api/client";
import { query, useAccion, useLista } from "@/api/queries";
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
  // El lote vencido que se vino a sacar del estante. Hacerlo a mano son seis
  // pasos (memorizar insumo, depósito y lote, ir a Stock, buscarlo, abrir
  // Salida, cambiar a Baja, elegir el lote): esa fricción es la razón por la que
  // la ampolla vencida sigue en el botiquín.
  const [aDarDeBaja, setADarDeBaja] = useState(null);
  // De qué insumo se está mirando el historial. La pregunta que se le hace a
  // Movimientos es siempre la misma —«el recuento dio 3 y el sistema decía
  // 20»— y sin filtro hay que paginar de a 25 el historial de toda la
  // institución hasta contestar «no figura».
  const [focoHistorial, setFocoHistorial] = useState(null);

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
    setADarDeBaja(null);
    setTab("stock");
  };

  const resolverVencimiento = (v) => {
    setDeposito(String(v.deposito_id));
    setFoco({ id: v.insumo_id, nombre: v.insumo });
    // Lo que YA venció tiene una sola cosa por hacer —sacarlo del estante y del
    // número que la guardia mira a la noche—, así que se abre la baja derecho
    // con ese lote. Lo que todavía se puede usar sólo se muestra: ahí la
    // decisión (consumirlo primero, transferirlo) no es una sola.
    setADarDeBaja(
      v.vencido ? { insumo: v.insumo_id, deposito: v.deposito_id, lote: v.lote_id } : null,
    );
    setTab("stock");
  };

  const verHistorial = (g) => {
    setDeposito(String(g.deposito));
    setFocoHistorial({ id: g.insumo, nombre: g.nombre, deposito: g.deposito_nombre });
    setTab("movimientos");
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
        <Alertas
          institucion={institucion}
          deposito={deposito}
          onResolver={resolver}
          onResolverVencimiento={resolverVencimiento}
        />
      )}
      {tab === "stock" && (
        <Stock
          institucion={institucion}
          deposito={deposito}
          depositos={depositos.filas}
          foco={foco}
          onQuitarFoco={() => setFoco(null)}
          onVerTodosLosDepositos={() => setDeposito("")}
          aDarDeBaja={aDarDeBaja}
          onBajaAbierta={() => setADarDeBaja(null)}
          onVerHistorial={verHistorial}
        />
      )}
      {tab === "movimientos" && (
        <Movimientos
          institucion={institucion}
          deposito={deposito}
          depositos={depositos.filas}
          foco={focoHistorial}
          onQuitarFoco={() => setFocoHistorial(null)}
        />
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

/**
 * Marca de insumo controlado (Ley 19.303).
 *
 * Es texto y no sólo color, y es la misma en las tres pestañas: el recuento de
 * estupefacientes y el libro de controlados se arman mirando estas listas, y si
 * la morfina se lee igual que una gasa hay que saber de memoria cuáles exigen
 * doble firma —y cuáles hay que volcar al libro—.
 */
function Controlado({ si }) {
  if (!si) return null;
  return (
    <span className="shrink-0 rounded-pill bg-badge-error-bg px-1.5 py-px text-xs font-semibold text-badge-error-fg">
      controlado
    </span>
  );
}

/**
 * Nombre del insumo con su marca.
 *
 * La marca va como hermana del nombre y no dentro: metida adentro, el truncado
 * se la come justo en los nombres largos —«Morfina clorhidrato Ampolla 10
 * mg/ml»— que son los que más falta hace marcar.
 */
function NombreInsumo({ nombre, controlado, className, truncado = "sm:truncate" }) {
  return (
    <span className={cn("flex items-center gap-1.5", className)}>
      <span className={cn("min-w-0", truncado)} title={nombre}>{nombre}</span>
      <Controlado si={controlado} />
    </span>
  );
}

/**
 * Descarga el listado que está en pantalla, con sus mismos filtros.
 *
 * El servidor ya lo sirve (`?formato=csv`); lo que faltaba era la puerta. El
 * inventario físico se hace con una hoja impresa: sin ella se cuenta con el
 * celular en la mano abriendo modales, o se cuenta en papel y el sistema queda
 * como copia tardía de un papel que es la verdad.
 *
 * Va por `fetch` y no navegando a la URL porque la sesión es un token: una
 * navegación no lleva la cabecera `Authorization` y el servidor contesta 401.
 */
function useExportarCSV(recurso, params, toast) {
  const [bajando, setBajando] = useState(false);

  async function ir() {
    setBajando(true);
    try {
      const r = await fetch(`/api/${recurso}/${query({ ...params, formato: "csv" })}`, {
        headers: { Authorization: `Bearer ${tokens.access}` },
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const url = URL.createObjectURL(await r.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download =
        (r.headers.get("Content-Disposition") || "").match(/filename="([^"]+)"/)?.[1] ||
        `${recurso}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      // Se libera enseguida: el blob queda retenido hasta revocarlo.
      URL.revokeObjectURL(url);
    } catch (e) {
      toast.deError(e, "No se pudo descargar la planilla.");
    } finally {
      setBajando(false);
    }
  }

  return { bajando, ir };
}

/** Botón de exportar, igual en Stock y en Movimientos. */
function BotonExportar({ exportar }) {
  return (
    <Button variant="secondary" disabled={exportar.bajando} onClick={exportar.ir}>
      <Icon name="download" size={15} /> {exportar.bajando ? "Preparando…" : "Exportar"}
    </Button>
  );
}

function Alertas({ institucion, deposito, onResolver, onResolverVencimiento }) {
  const q = useQuery({
    // La clave va DENTRO del prefijo «lista», que es lo único que `useAccion`
    // invalida al terminar una acción. Afuera, reponer un faltante y volver acá
    // mostraba la alerta vieja o la nueva según cuánto hubiera tardado la
    // persona en llenar el modal (`staleTime` de 30 s): la lectura natural de un
    // faltante que sigue en rojo es que la reposición no se registró, y repetir
    // la transferencia deja el botiquín con el doble y la central corta.
    queryKey: ["lista", "farmacia-alertas", institucion?.id, deposito],
    queryFn: () => api.get(
      `/pedidos-stock/alertas/?institucion=${institucion.id}${deposito ? `&deposito=${deposito}` : ""}`
    ),
    enabled: institucion?.id != null,
  });

  if (q.isLoading) return <Skeleton className="h-64" />;
  if (q.error) return <EstadoError error={q.error} onReintentar={q.refetch} />;

  const { faltantes = [], por_vencer: vencen = [] } = q.data || {};
  // Lo que ya venció y lo que va a vencer son dos trabajos distintos y sólo uno
  // es de hoy: «Vencen pronto 9» en ámbar no distingue «hay 6 lotes vencidos
  // ahora en el botiquín de guardia» de «hay 9 que vencen el mes que viene».
  const vencidos = vencen.filter((v) => v.vencido);
  const proximos = vencen.filter((v) => !v.vencido);
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
                  {/* Mismo tratamiento que la lista de stock: en un teléfono
                      —que es donde se miran las alertas, caminando por el
                      pasillo— lo que se cortaba al truncar era la presentación y
                      la dosis, que es lo único que distingue dos renglones del
                      mismo genérico. Y ahí el `title` no se puede leer. */}
                  <span className="w-full min-w-0 sm:w-auto sm:flex-1">
                    <NombreInsumo nombre={f.insumo} controlado={f.controlado}
                                  className="text-md font-semibold" />
                    <span className="block text-sm text-texto-tenue">{f.deposito}</span>
                  </span>
                  {/* El número solo no dice nada: «3» es grave o irrelevante según
                      el mínimo. Se muestran los dos juntos. */}
                  <span className="ml-auto whitespace-nowrap text-right tabular-nums">
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
        <header className="flex flex-wrap items-center gap-2 border-b border-division px-xl py-lg">
          <Icon name="refresh" size={16} className="text-badge-amber-fg" />
          <h3 className="flex-1 text-lg font-bold">Vencen pronto</h3>
          {vencidos.length > 0 && <Badge tone="error">{vencidos.length} vencido/s</Badge>}
          <Badge tone={proximos.length ? "amber" : "gray"}>{proximos.length}</Badge>
        </header>
        {vencen.length === 0 ? (
          <p className="px-xl py-lg text-base text-texto-tenue">Nada vence en los próximos dos meses.</p>
        ) : (
          <ul className="divide-y divide-division">
            {vencidos.length > 0 && (
              <li className="bg-superficie-2 px-xl py-1.5 text-sm font-semibold text-danger">
                Ya vencidos · hay que darlos de baja
              </li>
            )}
            {vencidos.map((v, i) => (
              <FilaQueVence key={`v${i}`} v={v} onResolver={onResolverVencimiento} />
            ))}
            {proximos.length > 0 && (
              <li className="bg-superficie-2 px-xl py-1.5 text-sm font-semibold text-texto-suave">
                Todavía se pueden usar
              </li>
            )}
            {proximos.map((v, i) => (
              <FilaQueVence key={`p${i}`} v={v} onResolver={onResolverVencimiento} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/**
 * Un lote que vence, como renglón accionable.
 *
 * Un faltante no se resuelve desde la pantalla (hay que comprar o pedir) y sin
 * embargo tenía botón; un lote vencido sí se resuelve acá y en un paso —darlo de
 * baja para que salga del estante y del número que la guardia mira a la noche— y
 * era el que no tenía ninguno. Esa fricción es la que hace que la lista se deje
 * de mirar y que la ampolla vencida siga en el botiquín.
 */
function FilaQueVence({ v, onResolver }) {
  return (
    <li>
      <button
        type="button"
        onClick={() => onResolver(v)}
        aria-label={v.vencido
          ? `Dar de baja el lote ${v.lote} de ${v.insumo} en ${v.deposito}`
          : `Ver ${v.insumo} en ${v.deposito}`}
        className="flex w-full flex-wrap items-center gap-x-md gap-y-1 px-xl py-3 text-left hover:bg-superficie-2"
      >
        <span className="w-full min-w-0 sm:w-auto sm:flex-1">
          <NombreInsumo nombre={v.insumo} controlado={v.controlado}
                        className="text-md font-semibold" />
          <span className="block text-sm text-texto-tenue">
            {v.deposito} · lote {v.lote}
          </span>
        </span>
        <span className="ml-auto whitespace-nowrap text-right">
          <span className={cn("block text-md font-bold tabular-nums",
            v.vencido ? "text-danger" : "text-badge-amber-fg")}>
            {v.vencido ? "vencido" : `en ${v.dias} d`}
          </span>
          <span className="block text-sm text-texto-tenue tabular-nums">
            {v.cantidad} {v.unidad || "u."}
          </span>
        </span>
        <Icon name="chevronRight" size={15} className="text-texto-tenue" />
      </button>
    </li>
  );
}

/** Ordena los lotes de un insumo como se sacan del estante: primero el que vence antes. */
function porVencimiento(a, b) {
  if (!a.vencimiento) return 1;
  if (!b.vencimiento) return -1;
  return a.vencimiento.localeCompare(b.vencimiento);
}

function Stock({
  institucion, deposito, depositos, foco, onQuitarFoco, onVerTodosLosDepositos,
  aDarDeBaja, onBajaAbierta, onVerHistorial,
}) {
  const toast = useToast();
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);
  const [mover, setMover] = useState(null);
  const [recuento, setRecuento] = useState(null);
  const [ingreso, setIngreso] = useState(false);
  const [traza, setTraza] = useState(null);

  const filtros = {
    "deposito__institucion": institucion?.id,
    deposito: deposito || undefined,
    insumo: foco?.id || undefined,
    search: busca || undefined,
    // Agrupamos por (depósito, insumo): pidiendo ese mismo orden, los renglones
    // de un grupo llegan juntos y sólo el del borde puede quedar partido entre
    // dos páginas.
    ordering: "deposito__nombre,insumo__nombre",
  };

  const q = useLista(
    "stock",
    {
      ...filtros,
      page: pagina,
      // 200 es el máximo que sirve el servidor (cauce/pagination.py). Pedir 300
      // no traía 300: recortaba en silencio y el total del insumo del corte
      // salía menor al real, en rojo como faltante teniendo el resto.
      pageSize: 200,
    },
    { enabled: institucion?.id != null },
  );
  const exportar = useExportarCSV("stock", filtros, toast);

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
          controlado: e.controlado,
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

  const sinFilas = !q.isLoading && grupos.length === 0;
  const nombreDeposito = depositos.find((d) => String(d.id) === String(deposito))?.nombre;

  // Cuando el depósito elegido no tiene nada, se pregunta por el resto de la
  // institución: «acá no hay, hay 30 en Farmacia central» es la respuesta que la
  // persona vino a buscar, y es lo que la manda a pedir una transferencia en vez
  // de a registrar un ingreso que nunca ocurrió.
  const enOtros = useLista(
    "stock",
    {
      "deposito__institucion": institucion?.id,
      insumo: foco?.id || undefined,
      search: busca || undefined,
      ordering: "deposito__nombre",
      pageSize: 50,
    },
    { enabled: institucion?.id != null && sinFilas && Boolean(deposito || foco) },
  );

  // Se llegó desde un lote vencido en «Qué resolver»: apenas la fila está en
  // pantalla se abre la baja con ese lote puesto.
  useEffect(() => {
    if (!aDarDeBaja || q.isLoading) return;
    const g = grupos.find(
      (x) => x.insumo === aDarDeBaja.insumo && x.deposito === aDarDeBaja.deposito,
    );
    if (g) setMover({ ...g, modoInicial: "baja", loteInicial: aDarDeBaja.lote });
    // Se limpia aunque no se haya encontrado la fila: si no, el intento se
    // repite en cada render y la pantalla queda trabada.
    onBajaAbierta();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aDarDeBaja, grupos, q.isLoading]);

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
        <BotonExportar exportar={exportar} />
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
      ) : sinFilas ? (
        <StockVacio
          busca={busca}
          onLimpiarBusca={() => setBusca("")}
          foco={foco}
          onQuitarFoco={onQuitarFoco}
          deposito={nombreDeposito}
          onVerTodosLosDepositos={onVerTodosLosDepositos}
          otros={enOtros.filas}
          onIngreso={() => setIngreso(true)}
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
                      <NombreInsumo nombre={g.nombre} controlado={g.controlado}
                                    className="text-md font-semibold" />
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
                      {/* El momento en que alguien necesita el historial es
                          siempre el mismo: el recuento dio 3 y el sistema decía
                          20. Sin este camino hay que paginar de a 25 el
                          historial de toda la institución. */}
                      <Button size="sm" variant="secondary"
                              aria-label={`Ver el historial de ${g.nombre} en ${g.deposito_nombre}`}
                              onClick={() => onVerHistorial(g)}>
                        Historial
                      </Button>
                    </span>
                  </div>
                  {g.lotes.some((l) => l.cantidad > 0) && (
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {g.lotes.filter((l) => l.cantidad > 0).map((l) => {
                        const clases = cn(
                          "rounded-pill px-2 py-px text-xs font-medium",
                          l.vencido
                            ? "bg-badge-error-bg text-badge-error-fg"
                            : "bg-division text-texto-suave",
                        );
                        const texto = (
                          <>
                            {l.lote_numero ? `${l.lote_numero}: ` : ""}{l.cantidad}
                            {l.vencimiento && ` · vence ${l.vencimiento.split("-").reverse().join("/")}`}
                          </>
                        );
                        // El lote lleva a quién lo recibió. Es un trabajo con
                        // reloj: cuando ANMAT retira un lote hay que ubicar y
                        // llamar a esas personas en el día, y hasta ahora la
                        // única forma era que alguien con acceso al servidor
                        // armara la consulta a mano.
                        return l.lote ? (
                          <button
                            key={l.id}
                            type="button"
                            onClick={() => setTraza(l)}
                            aria-label={`Ver a quién se le aplicó el lote ${l.lote_numero} de ${g.nombre}`}
                            className={cn(clases, "hover:underline")}
                          >
                            {texto}
                          </button>
                        ) : (
                          <span key={l.id} className={clases}>{texto}</span>
                        );
                      })}
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
      {traza && <TrazaLoteModal fila={traza} onClose={() => setTraza(null)} />}
    </div>
  );
}

/**
 * Los estados vacíos del stock, que no son el mismo.
 *
 * «Sin stock cargado» sobre una búsqueda sin resultados le dice a la enfermera
 * que filtró «Botiquín de guardia» y buscó «adrenalina» que el sistema está
 * vacío, cuando lo cierto es que en ese botiquín no hay y en Farmacia central
 * hay 30: la manda a registrar un ingreso en vez de a pedir una transferencia.
 * Un tipeo («morfna») produce la misma conclusión falsa.
 */
function StockVacio({
  busca, onLimpiarBusca, foco, onQuitarFoco, deposito, onVerTodosLosDepositos, otros, onIngreso,
}) {
  // Dónde sí hay: es la respuesta que la persona vino a buscar y la que la manda
  // a transferir en vez de a cargar un ingreso que no ocurrió.
  const donde = [...new Set(otros.map((e) => e.deposito_nombre))].slice(0, 3);

  if (busca) {
    return (
      <EstadoVacio
        titulo={`Ningún insumo coincide con «${busca}»`}
        detalle={deposito
          ? `Se buscó sólo en ${deposito}. Puede haber en otro depósito.`
          : "Revisá cómo está escrito: se busca por nombre, genérico o número de lote."}
        icono="search"
        accion={
          <div className="flex flex-wrap items-center justify-center gap-md">
            <Button variant="secondary" onClick={onLimpiarBusca}>Limpiar la búsqueda</Button>
            {deposito && (
              <Button variant="secondary" onClick={onVerTodosLosDepositos}>
                Buscar en todos los depósitos
              </Button>
            )}
          </div>
        }
      />
    );
  }
  if (foco) {
    return (
      <EstadoVacio
        titulo={`No hay ${foco.nombre}${deposito ? ` en ${deposito}` : ""}`}
        detalle={donde.length
          ? `Sí hay en ${donde.join(", ")}: se repone con una transferencia desde ahí.`
          : "No queda en ningún depósito de la institución."}
        icono="cube"
        accion={
          <Button variant="secondary" onClick={onQuitarFoco}>Ver todo el stock</Button>
        }
      />
    );
  }
  if (deposito) {
    return (
      <EstadoVacio
        titulo={`No hay stock en ${deposito}`}
        detalle={donde.length
          ? `Sí hay en ${donde.join(", ")}: se repone con una transferencia desde ahí.`
          : "Tampoco hay en el resto de la institución."}
        icono="cube"
        accion={
          <Button variant="secondary" onClick={onVerTodosLosDepositos}>
            Ver todos los depósitos
          </Button>
        }
      />
    );
  }
  return (
    <EstadoVacio
      titulo="Sin stock cargado"
      detalle="Registrá un ingreso para empezar."
      icono="cube"
      accion={<Button onClick={onIngreso}>Registrar ingreso</Button>}
    />
  );
}

/**
 * A quién le tocó un lote.
 *
 * Es la razón declarada por la que todo el módulo imputa el consumo al caso, y
 * es un trabajo con reloj: cuando ANMAT retira un lote hay que ubicar y llamar
 * en el día a las personas que lo recibieron. El endpoint ya existía; sin esta
 * pantalla, farmacia revisa remitos y planillas en papel, que es justo lo que el
 * módulo dice venir a reemplazar.
 */
function TrazaLoteModal({ fila, onClose }) {
  const q = useQuery({
    queryKey: ["lista", "farmacia-traza", fila.lote],
    queryFn: () => api.get(`/movimientos-stock/trazar-lote/?lote=${fila.lote}`),
  });
  const pacientes = q.data?.pacientes || [];

  return (
    <Modal
      title={`Lote ${fila.lote_numero} · ${q.data?.lote?.insumo || ""}`}
      onClose={onClose}
      footer={<Button variant="secondary" onClick={onClose}>Cerrar</Button>}
    >
      {q.isLoading ? (
        <Skeleton className="h-40" />
      ) : q.error ? (
        <EstadoError error={q.error} onReintentar={q.refetch} />
      ) : (
        <div className="flex flex-col gap-3.5">
          <div className="text-md text-texto-suave">
            Quedan <strong className="tabular-nums">{fila.cantidad}</strong> en el estante
            {fila.vencimiento &&
              ` · vence ${fila.vencimiento.split("-").reverse().join("/")}`}
            {fila.vencido && <strong className="text-danger"> · vencido</strong>}
          </div>
          {pacientes.length === 0 ? (
            <p className="text-base text-texto-tenue">
              Todavía no se registró ningún consumo de este lote imputado a un paciente.
            </p>
          ) : (
            <ul className="max-h-40 divide-y divide-division overflow-y-auto rounded-md border border-borde">
              {pacientes.map((p, i) => (
                <li key={i} className="flex flex-wrap items-center gap-x-md gap-y-1 px-2.5 py-2">
                  <span className="min-w-0 flex-1">
                    <span className="block text-md font-semibold">
                      {p.paciente || "Sin paciente"}
                    </span>
                    <span className="block text-sm text-texto-tenue">
                      {[p.deposito, fechaHora(p.fecha)].filter(Boolean).join(" · ")}
                    </span>
                  </span>
                  <span className="whitespace-nowrap text-right text-md tabular-nums">
                    {p.cantidad}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="text-sm text-texto-tenue">
            Lo que queda de este lote se saca del estante con Salida → Baja, eligiendo el lote.
          </p>
        </div>
      )}
    </Modal>
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
  // `modoInicial` y `loteInicial` llegan cuando se vino desde un lote vencido de
  // «Qué resolver»: ahí la acción ya está decidida y hacerla elegir de nuevo es
  // la mitad de la fricción que se venía a sacar.
  const [modo, setModo] = useState(grupo.modoInicial || (otros.length ? "transferencia" : "baja"));
  const [cantidad, setCantidad] = useState(1);
  const [destino, setDestino] = useState("");
  const [motivo, setMotivo] = useState("");
  const conStock = grupo.lotes.filter((l) => l.cantidad > 0);
  const conLote = conStock.filter((l) => l.lote);
  const [lote, setLote] = useState(
    () => String(grupo.loteInicial || (conLote[0] ? conLote[0].lote : "")),
  );

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
                      {/* La misma marca que en las tres pestañas: si el buscador
                          la dice de una forma y la lista de otra, se lee como
                          decoración de una lista y no como una propiedad del
                          insumo. */}
                      <NombreInsumo
                        nombre={`${i.nombre} ${i.presentacion}`.trim()}
                        controlado={i.controlado}
                        truncado="truncate"
                      />
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

function Movimientos({ institucion, deposito, depositos, foco, onQuitarFoco }) {
  const toast = useToast();
  const [pagina, setPagina] = useState(1);
  const [busca, setBusca] = useState("");
  const [tipo, setTipo] = useState("");

  const filtros = {
    "insumo__institucion": institucion?.id,
    // El filtro va al servidor: aplicado sobre las filas ya traídas, elegir un
    // depósito mostraba «Sin movimientos» aunque hubiera habido veinte esa
    // mañana, más atrás en el historial.
    deposito: deposito || undefined,
    insumo: foco?.id || undefined,
    tipo: tipo || undefined,
    search: busca || undefined,
    ordering: "-fecha",
  };
  const q = useLista(
    "movimientos-stock",
    { ...filtros, page: pagina, pageSize: 25 },
    { enabled: institucion?.id != null },
  );
  const exportar = useExportarCSV("movimientos-stock", filtros, toast);

  useEffect(() => { setPagina(1); }, [deposito, busca, tipo, foco?.id]);

  if (q.error) return <EstadoError error={q.error} onReintentar={q.refetch} />;

  const nombre = depositos.find((d) => String(d.id) === String(deposito))?.nombre;
  const filtrado = Boolean(busca || tipo || foco);

  return (
    <div className="flex flex-col gap-lg">
      <div className="flex flex-wrap items-center gap-md">
        <div className="min-w-52 flex-1">
          <Input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar insumo, lote o motivo…"
            aria-label="Buscar en el historial"
          />
        </div>
        <Select value={tipo} onChange={(e) => setTipo(e.target.value)}
                aria-label="Tipo de movimiento" className="w-auto">
          <option value="">Todos los tipos</option>
          <option value="ingreso">Ingresos</option>
          <option value="consumo">Consumos</option>
          <option value="transferencia">Transferencias</option>
          <option value="ajuste">Ajustes de inventario</option>
          <option value="baja">Bajas</option>
        </Select>
        <BotonExportar exportar={exportar} />
      </div>

      {foco && (
        <div className="flex flex-wrap items-center gap-md rounded-md border border-borde bg-superficie px-lg py-2.5 text-base">
          {/* De qué se está viendo el historial, dicho en la pantalla: si no, una
              lista filtrada se lee como el historial completo y «no figura»
              vuelve a ser la respuesta equivocada. */}
          <span className="text-texto-suave">
            Historial de <b className="font-semibold">{foco.nombre}</b>
            {foco.deposito ? ` en ${foco.deposito}` : ""}
          </span>
          <button onClick={onQuitarFoco} className="font-semibold text-accent hover:underline">
            Ver todos los movimientos
          </button>
        </div>
      )}

      {q.isLoading ? (
        <Skeleton className="h-64" />
      ) : !q.filas.length ? (
        <EstadoVacio
          titulo="Sin movimientos"
          // Decir «nunca se registró nada» sobre un depósito o un filtro que sí
          // tuvo movimientos hace que quien busca cierre la pantalla convencido
          // de que nadie tocó nada.
          detalle={filtrado
            ? "Ningún movimiento coincide con lo que estás filtrando."
            : deposito
              ? `No hay movimientos de ${nombre || "ese depósito"}.`
              : "Todavía no se registró ningún movimiento de stock."}
          icono="list"
        />
      ) : (
        <section className="overflow-hidden rounded-lg border border-borde bg-superficie">
          <ul className="divide-y divide-division">
            {q.filas.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center gap-x-md gap-y-1 px-xl py-3">
                <Badge tone={TONO_MOV[m.tipo] || "gray"}>{m.tipo_display}</Badge>
                <span className="min-w-0 flex-1">
                  <NombreInsumo
                    nombre={`${m.cantidad} × ${m.insumo_nombre}`}
                    controlado={m.controlado}
                    className="text-md font-semibold"
                    truncado="truncate"
                  />
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
      )}
    </div>
  );
}
