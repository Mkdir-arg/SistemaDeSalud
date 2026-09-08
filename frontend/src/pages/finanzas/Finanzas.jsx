import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useLista } from "@/api/queries";
import { ESTADOS_CARGA, ESTADOS_GASTO, importeARS, opcionesFinanzas, usePermisosFinanzas } from "@/api/finanzas";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Badge, Button, Card, Field, Input, Modal, Select, Spinner, Tabs } from "@/components/ui";
import { EstadoError, EstadoVacio } from "@/components/ui/estados";
import { DataTable, useTablaUrl } from "@/components/ui/tabla";
import { fechaHora } from "@/lib/format";
import FormularioGasto from "./FormularioGasto";
import FormularioReparto from "./FormularioReparto";

const CONFIGURAR = "configurar_gastos_esperados";
const CONFIGURAR_REPARTOS = "configurar_repartos";
const mesActual = () => {
  const hoy = new Date();
  return `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}`;
};

function Estado({ valor, calendario = false }) {
  const datos = (calendario ? ESTADOS_CARGA : ESTADOS_GASTO)[valor];
  return <Badge tone={datos?.tone || "gray"}>{datos?.label || "Estado no disponible"}</Badge>;
}

const importeCentavos = (centavos) => {
  const valor = BigInt(String(centavos || 0));
  const signo = valor < 0n ? "-" : "";
  const absoluto = valor < 0n ? -valor : valor;
  return importeARS(`${signo}${absoluto / 100n}.${String(absoluto % 100n).padStart(2, "0")}`);
};

function TablaFinanciera({ consulta, tabla, columnas, vacio }) {
  return <DataTable columnas={columnas} filas={consulta.filas} total={consulta.total} paginas={consulta.paginas}
    tabla={tabla} vacio={vacio} estado={{ cargando: consulta.isLoading, refrescando: consulta.refrescando,
      error: consulta.error, reintentar: consulta.refetch }} />;
}

function HistorialCarga({ fila, usuarioId, onClose }) {
  const tabla = useTablaUrl("indicaciones");
  const params = { page: tabla.pagina, pageSize: tabla.tamano };
  const consulta = useLista(`expectativas-gasto/${fila.id}/indicaciones`, params, {
    queryKey: ["finanzas", usuarioId, fila.institucion, "historial", fila.id, params], placeholderData: undefined,
    gcTime: 0,
  });
  return <Modal title={`Historial · ${fila.concepto_nombre}`} onClose={onClose} width={720}>
    <p className="mb-4 text-md text-texto-debil">{fila.area_nombre || "Ámbito institucional"} · Cada indicación conserva su fecha de registro.</p>
    <TablaFinanciera consulta={consulta} tabla={tabla} vacio={{ titulo: "Todavía no hay indicaciones" }} columnas={[
      { key: "periodo_economico", label: "Mes", render: (r) => r.periodo_economico.slice(0, 7) },
      { key: "estado", label: "Carga", render: (r) => <Estado valor={r.estado} calendario /> },
      { key: "registrado", label: "Registrado", render: (r) => fechaHora(r.registrado) },
    ]} />
  </Modal>;
}

function VersionesEsperado({ fila, usuarioId, onClose, onHistorial }) {
  const tabla = useTablaUrl("versiones");
  const params = { institucion: fila.institucion, concepto: fila.concepto,
    area: fila.area ?? "null", ordering: "-vigente_desde,-id", page: tabla.pagina, pageSize: tabla.tamano };
  const consulta = useLista("expectativas-gasto", params, {
    queryKey: ["finanzas", usuarioId, fila.institucion, "versiones", params],
    placeholderData: undefined, gcTime: 0,
  });
  return <Modal title={`Versiones · ${fila.concepto_nombre}`} onClose={onClose} width={820}>
    <p className="mb-4 text-md text-texto-debil">{fila.area_nombre || "Ámbito institucional"} · Intervalos registrados, con fin exclusivo. Una versión sucesora limita la anterior desde su inicio. Sólo se muestran versiones incluidas en tus permisos.</p>
    <TablaFinanciera consulta={consulta} tabla={tabla} vacio={{ titulo: "Sin versiones visibles" }} columnas={[
      { key: "id", label: "Versión", render: (r) => <div>#{r.id}{r.reemplaza && <p className="text-sm text-texto-debil">Reemplaza #{r.reemplaza}</p>}</div> },
      { key: "vigente_desde", label: "Desde", render: (r) => r.vigente_desde.slice(0, 7) },
      { key: "vigente_hasta", label: "Hasta (exclusivo)", render: (r) => r.vigente_hasta?.slice(0, 7) || "Sin fin declarado" },
      { key: "motivo_correccion", label: "Registro", render: (r) => <div>{r.motivo_correccion || "Configuración inicial"}<p className="text-sm text-texto-debil">{fechaHora(r.registrado)}</p></div> },
      { key: "acciones", label: "Acciones", render: (r) => <Button size="sm" variant="ghost" onClick={() => onHistorial(r)}>Historial de carga</Button> },
    ]} />
  </Modal>;
}

export default function Finanzas() {
  const permisos = usePermisosFinanzas();
  const { institucion } = useInstitucion();
  if (permisos.isLoading) return <Spinner label="Consultando permisos financieros…" />;
  if (permisos.error) return <EstadoError error={permisos.error} onReintentar={permisos.refetch} />;
  if (!permisos.acceso) return <EstadoVacio titulo="Sin acceso a Finanzas" detalle="Necesitás una concesión financiera explícita en esta institución." />;
  // Al cambiar de usuario/institución se descartan formularios y datos visibles
  // del ámbito anterior, incluso si todavía hay respuestas de red en vuelo.
  return <ContenidoFinanzas key={`${permisos.usuarioId}:${institucion.id}`} institucion={institucion} permisos={permisos} />;
}

function ContenidoFinanzas({ institucion, permisos }) {
  const [mes, setMes] = useState(mesActual);
  const [area, setArea] = useState("");
  const [tab, setTab] = useState("calendario");
  const [modal, setModal] = useState(null);
  const [, setSearchParams] = useSearchParams();
  const calendarioTabla = useTablaUrl("calendario");
  const gastosTabla = useTablaUrl("gastos");
  const repartosTabla = useTablaUrl("repartos");
  const puedeLeer = permisos.tiene("ver_gastos");
  const puedeCatalogo = permisos.tiene("registrar_gastos") || permisos.tiene(CONFIGURAR) || permisos.tiene(CONFIGURAR_REPARTOS);
  const tieneMes = /^\d{4}-(0[1-9]|1[0-2])$/.test(mes);
  const filtro = { institucion: institucion.id, area: area || undefined, periodo_economico: `${mes}-01` };
  const opciones = (recurso, tabla, habilitada) => ({
    enabled: habilitada && tieneMes,
    placeholderData: undefined,
    gcTime: 0,
    queryKey: ["finanzas", permisos.usuarioId, institucion.id, recurso, filtro, tabla.pagina, tabla.tamano, tabla.orden],
  });
  const calendario = useLista("expectativas-gasto/calendario", {
    ...filtro, page: calendarioTabla.pagina, pageSize: calendarioTabla.tamano,
  }, opciones("calendario", calendarioTabla, puedeLeer && tab === "calendario"));
  const gastos = useLista("gastos", {
    ...filtro, page: gastosTabla.pagina, pageSize: gastosTabla.tamano, ordering: gastosTabla.orden,
  }, opciones("gastos", gastosTabla, puedeLeer && tab === "gastos"));
  const repartos = useLista("repartos-gasto", {
    gasto__institucion: institucion.id,
    gasto__area: area === "null" ? -1 : area || undefined,
    gasto__periodo_economico: `${mes}-01`,
    page: repartosTabla.pagina,
    pageSize: repartosTabla.tamano,
    ordering: "-calculado,-version,-id",
  }, opciones("repartos", repartosTabla, puedeLeer && tab === "repartos"));
  const areas = useQuery({
    queryKey: ["finanzas", permisos.usuarioId, institucion.id, "areas"],
    queryFn: () => opcionesFinanzas("areas", institucion.id),
    gcTime: 0,
  });
  const conceptos = useQuery({
    queryKey: ["finanzas", permisos.usuarioId, institucion.id, "conceptos"],
    queryFn: () => opcionesFinanzas("conceptos-gasto", institucion.id), enabled: puedeCatalogo,
    gcTime: 0,
  });
  const catalogoListo = !areas.isLoading && !areas.error && !conceptos.isLoading && !conceptos.error;
  const abrir = (tipo, fila) => setModal({ tipo, fila });
  const habilitada = (accion, fila) => !permisos.isFetching && permisos.permite(accion, fila.area, fila.sensible);
  const areasVisibles = (areas.data || []).filter((a) => ["ver_gastos", "registrar_gastos", CONFIGURAR, CONFIGURAR_REPARTOS].some((accion) => permisos.permite(accion, a.id)));
  function cambiarFiltro(set, valor) {
    set(valor);
    setSearchParams((previos) => {
      const siguientes = new URLSearchParams(previos);
      siguientes.delete("calendario_pag");
      siguientes.delete("gastos_pag");
      siguientes.delete("repartos_pag");
      return siguientes;
    }, { replace: true });
    setModal(null);
  }

  const columnasCalendario = [
    { key: "concepto_nombre", label: "Concepto esperado", render: (r) => <div><strong>{r.concepto_nombre}</strong><p className="text-sm text-texto-debil">Versión #{r.id}{r.reemplaza ? ` · Reemplaza #${r.reemplaza}` : ""}</p>{r.sensible && <div className="text-sm text-texto-debil">Sensible</div>}</div> },
    { key: "area_nombre", label: "Ámbito", render: (r) => r.area_nombre || "Institucional" },
    { key: "estado_carga", label: "Estado de carga", render: (r) => <div className="space-y-1"><Estado valor={r.estado_carga} calendario /><p className="text-sm text-texto-debil">{r.indicacion_id == null ? "Sin indicación registrada" : fechaHora(r.indicacion_registrada)}</p></div> },
    { key: "gastos_pendientes", label: "Por aprobar", render: (r) => <span className="font-semibold tabular-nums">{r.gastos_pendientes} registro(s)</span> },
    { key: "gastos_aprobados", label: "Aprobados", render: (r) => `${r.gastos_aprobados} registro(s)` },
    { key: "acciones", label: "Acciones", render: (r) => <div className="flex flex-wrap gap-2">
      {habilitada(CONFIGURAR, r) && <Button size="sm" variant="secondary" onClick={() => abrir("indicar", r)}>Indicar carga</Button>}
      <Button size="sm" variant="ghost" onClick={() => abrir("historial", r)}>Historial</Button>
      <Button size="sm" variant="ghost" onClick={() => abrir("versiones", r)}>Ver versiones</Button>
      {habilitada(CONFIGURAR, r) && <Button size="sm" variant="ghost" onClick={() => abrir("version", r)}>Nueva versión</Button>}
    </div> },
  ];
  const columnasGastos = [
    { key: "concepto_nombre", label: "Gasto", render: (r) => <div><strong>{r.concepto_nombre}</strong><p className="text-sm text-texto-debil">#{r.id} · {r.area_nombre || "Institucional"}{r.sensible ? " · Sensible" : ""}</p></div> },
    { key: "importe", label: "Importe original", render: (r) => <span className="whitespace-nowrap font-mono">{importeARS(r.importe)}</span> },
    { key: "estado_operativo", label: "Aprobación", render: (r) => <Estado valor={r.estado_operativo} /> },
    { key: "registrado", label: "Registro", orden: "registrado", render: (r) => <div>{fechaHora(r.registrado)}<p className="text-sm text-texto-debil">{r.origen === "central" ? "Carga central" : "Carga de área"}</p></div> },
    { key: "acciones", label: "Acciones", render: (r) => <div className="flex flex-wrap gap-2">
      <Button size="sm" variant="ghost" onClick={() => abrir("detalle", r)}>Detalle</Button>
      {r.estado_operativo === "pendiente_aprobacion" && habilitada("aprobar_gastos", r) && <>
        <Button size="sm" variant="secondary" onClick={() => abrir("aprobar", r)}>Aprobar</Button>
        <Button size="sm" variant="ghost" onClick={() => abrir("rechazar", r)}>Rechazar</Button>
      </>}
      {["pendiente_aprobacion", "rechazado"].includes(r.estado_operativo) && habilitada("registrar_gastos", r) && <Button size="sm" variant="ghost" disabled={!catalogoListo} onClick={() => abrir("reemplazo", r)}>Reemplazar</Button>}
      {r.estado_operativo === "aprobado" && habilitada("corregir_gastos", r) && <Button size="sm" variant="secondary" onClick={() => abrir("ajuste", r)}>Ajustar</Button>}
    </div> },
  ];
  const columnasRepartos = [
    { key: "gasto", label: "Gasto repartido", render: (r) => <div><strong>{r.concepto_nombre}</strong><p className="text-sm text-texto-debil">{r.area_nombre || "Institucional"} · Gasto #{r.gasto} · Versión {r.version}{r.vigente ? " · Vigente" : " · Histórica"}</p></div> },
    { key: "periodo_economico", label: "Mes", render: (r) => r.periodo_economico.slice(0, 7) },
    { key: "estado", label: "Resultado", render: (r) => <div><Badge tone={r.estado === "distribuido" ? "green" : r.estado === "sin_actividad" ? "blue" : "amber"}>{r.estado === "distribuido" ? "Distribuido" : r.estado === "sin_actividad" ? "Sin actividad" : "Pendiente"}</Badge>{r.motivo && <p className="mt-1 text-sm text-texto-debil">{r.motivo === "sin_regla" ? "Falta una regla" : r.motivo === "sin_cobertura" ? "Falta habilitar actividad" : "Fuente no elegible"}</p>}</div> },
    { key: "saldo_centavos", label: "Importe", render: (r) => <span className="whitespace-nowrap font-mono">{importeCentavos(r.saldo_centavos)}</span> },
    { key: "atribuciones", label: "Atenciones", render: (r) => <div className="tabular-nums">{r.atribuciones} atribución(es){r.saldo_no_atribuido_centavos !== 0 && <p className="text-sm text-texto-debil">Sin atribuir: {importeCentavos(r.saldo_no_atribuido_centavos)}</p>}</div> },
  ];

  return <div className="space-y-5 p-lg sm:p-xxl">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div><p className="text-sm font-semibold uppercase tracking-wide text-accent">Finanzas y costos</p>
        <h2 className="mt-1 text-xl font-bold">Gastos y calendario mensual</h2>
        <p className="mt-2 max-w-[48rem] text-md text-texto-debil">Revisá qué falta cargar y qué gastos necesitan aprobación en {institucion.nombre}.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {permisos.tiene("registrar_gastos") && <Button disabled={!catalogoListo || permisos.isFetching} onClick={() => abrir("gasto")}>Registrar gasto</Button>}
        {permisos.tiene(CONFIGURAR) && <Button variant="secondary" disabled={!catalogoListo || permisos.isFetching} onClick={() => abrir("expectativa")}>Configurar esperado</Button>}
        {permisos.permite(CONFIGURAR, null) && <Button variant="ghost" onClick={() => abrir("concepto")}>Nuevo concepto</Button>}
        {permisos.tiene(CONFIGURAR_REPARTOS) && <Button variant="secondary" disabled={areas.isLoading} onClick={() => abrir("cobertura-reparto")}>Habilitar actividad</Button>}
        {permisos.tiene(CONFIGURAR_REPARTOS) && <Button variant="ghost" disabled={!catalogoListo} onClick={() => abrir("regla-reparto")}>Agregar regla</Button>}
      </div>
    </div>
    <Card className="p-4">
      <div className="flex flex-wrap items-end gap-4">
        <Field label="Mes económico"><Input type="month" required value={mes} onChange={(e) => cambiarFiltro(setMes, e.target.value)} /></Field>
        <div className="min-w-[220px]"><Field label="Área"><Select value={area} onChange={(e) => cambiarFiltro(setArea, e.target.value)}>
          <option value="">Todos mis ámbitos</option>
          {permisos.permite("ver_gastos", null) && <option value="null">Sólo institucional</option>}
          {areasVisibles.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
        </Select></Field></div>
        <Button variant="ghost" disabled={!tieneMes} onClick={() => { permisos.refetch(); if (puedeLeer) (tab === "calendario" ? calendario : tab === "gastos" ? gastos : repartos).refetch(); }}>Actualizar</Button>
      </div>
      <p className="mt-3 text-sm text-texto-debil">Carga, aprobación y reparto son estados separados. Un reparto nunca registra cargos ni pagos.</p>
    </Card>
    {areas.error && <EstadoError error={areas.error} onReintentar={areas.refetch} titulo="No se pudieron cargar las áreas" />}
    {conceptos.error && <EstadoError error={conceptos.error} onReintentar={conceptos.refetch} titulo="No se pudo cargar el catálogo de gastos" />}
    {!puedeLeer ? <EstadoVacio titulo="Tu acceso permite operar sin consultar el listado" detalle="Registrar gastos no concede acceso de lectura. Las cargas delegadas se envían a aprobación central." /> : <>
      <Tabs tabs={[{ key: "calendario", label: "Carga esperada" }, { key: "gastos", label: "Gastos registrados" }, { key: "repartos", label: "Repartos" }]} valor={tab} onChange={setTab} />
      {!tieneMes ? <p role="alert">Elegí un mes válido.</p> : tab === "calendario"
        ? <TablaFinanciera consulta={calendario} tabla={calendarioTabla} columnas={columnasCalendario} vacio={{ titulo: "Sin expectativas para este mes y ámbito", detalle: "Esto no significa que no haya gastos: sólo se muestran conceptos configurados." }} />
        : tab === "gastos"
          ? <TablaFinanciera consulta={gastos} tabla={gastosTabla} columnas={columnasGastos} vacio={{ titulo: "Sin gastos visibles para este mes y ámbito", detalle: "Sólo se muestran registros incluidos en tus permisos." }} />
          : <TablaFinanciera consulta={repartos} tabla={repartosTabla} columnas={columnasRepartos} vacio={{ titulo: "Todavía no hay repartos para este mes", detalle: "Los gastos sin regla o cobertura aparecerán como pendientes después del procesamiento." }} />}
      <p className="text-sm text-texto-debil">Las cantidades corresponden a registros visibles. No expresan un costo total ni cubren gastos que aún no fueron declarados.</p>
    </>}
    {modal?.tipo === "historial" && <HistorialCarga fila={modal.fila} usuarioId={permisos.usuarioId} onClose={() => setModal(null)} />}
    {modal?.tipo === "versiones" && <VersionesEsperado fila={modal.fila} usuarioId={permisos.usuarioId} onClose={() => setModal(null)} onHistorial={(fila) => abrir("historial", fila)} />}
    {modal?.tipo === "detalle" && <DetalleGasto fila={modal.fila} onClose={() => setModal(null)} />}
    {["cobertura-reparto", "regla-reparto"].includes(modal?.tipo) && <FormularioReparto {...modal} mes={mes} institucion={institucion} permisos={permisos} areas={areas.data || []} conceptos={conceptos.data || []} onClose={() => setModal(null)} />}
    {modal && !["historial", "detalle", "versiones", "cobertura-reparto", "regla-reparto"].includes(modal.tipo) && <FormularioGasto {...modal} mes={mes} institucion={institucion} permisos={permisos} areas={areas.data || []} conceptos={conceptos.data || []} onClose={() => setModal(null)} />}
  </div>;
}

function DetalleGasto({ fila, onClose }) {
  return <Modal title={`Gasto #${fila.id} · ${fila.concepto_nombre}`} onClose={onClose} width={600}>
    <div className="space-y-4 text-md">
      <p>{fila.area_nombre || "Ámbito institucional"} · Mes {fila.periodo_economico.slice(0, 7)}</p>
      <Estado valor={fila.estado_operativo} />
      <p className="font-mono">Importe original: {importeARS(fila.importe)}</p>
      <p className="text-texto-debil">Registrado {fechaHora(fila.registrado)}</p>
      {fila.aprobado_en && <p>Aprobado {fechaHora(fila.aprobado_en)}</p>}
      {fila.motivo_rechazo && <p>Motivo de rechazo: {fila.motivo_rechazo}</p>}
      {fila.reemplaza && <p>Reemplaza la carga #{fila.reemplaza}.</p>}
      {fila.reemplazado_por && <p>Reemplazado por la carga #{fila.reemplazado_por}.</p>}
      <h3 className="font-semibold">Ajustes del importe original</h3>
      {!fila.ajustes.length ? <p className="text-texto-debil">Sin ajustes registrados.</p> : <ul className="space-y-3">{fila.ajustes.map((a) => <li key={a.id} className="border-t border-division pt-3"><span className="font-mono">{importeARS(a.importe)}</span> · {a.motivo}<p className="text-sm text-texto-debil">{fechaHora(a.registrado)}</p></li>)}</ul>}
    </div>
  </Modal>;
}
