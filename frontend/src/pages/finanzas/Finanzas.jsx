import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { useLista } from "@/api/queries";
import { api } from "@/api/client";
import { ESTADOS_CARGA, ESTADOS_GASTO, decimalACentavos, importeARS, importeCentavos, opcionesFinanzas, usePermisosFinanzas } from "@/api/finanzas";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Badge, Button, Card, Field, Input, Modal, Select, Spinner, Tabs } from "@/components/ui";
import { EstadoError, EstadoVacio } from "@/components/ui/estados";
import { DataTable, useTablaUrl } from "@/components/ui/tabla";
import { fechaHora } from "@/lib/format";
import { Icon } from "@/components/icons";
import FormularioGasto from "./FormularioGasto";
import FormularioReparto from "./FormularioReparto";
import ResumenFinanzas, { ProcesamientoFinanzas } from "./ResumenFinanzas";
import "./finanzas.css";
import CostosAtencion, { ConfiguracionCostos } from "./CostosAtencion";
import DineroFinanzas, { CrearCuentaPorPagar, DetalleCuenta } from "./DineroFinanzas";
import ConfiguracionCobros from "./ConfiguracionCobros";
import ReportesEjecutivos from "./ReportesEjecutivos";
import { DecisionAprobacion, EstadoAprobacion, TrazaAprobacion } from "./AprobacionFinanzas";
import { AyudaFinanzas, FiltroColumna, FiltrosActivos, PanelFlotante, useFiltrosFinanzas } from "./ControlesFinanzas";

const CONFIGURAR = "configurar_gastos_esperados";
const CONFIGURAR_REPARTOS = "configurar_repartos";
const INSTITUCIONAL = "Institucional — sin área asignada";
const CAMPOS_CALENDARIO = ["concepto", "estado_carga", "gastos_pendientes_min", "gastos_pendientes_max", "gastos_aprobados_min", "gastos_aprobados_max", "monto_referencia_min", "monto_referencia_max", "importe_aprobado_min", "importe_aprobado_max", "diferencia_referencia_min", "diferencia_referencia_max"];
const CAMPOS_GASTOS = ["control_mensual", "id", "concepto", "estado_operativo", "importe_min", "importe_max", "total_ajustes_min", "total_ajustes_max", "importe_resultante_min", "importe_resultante_max", "registrado_desde", "registrado_hasta"];
const CAMPOS_REPARTOS = ["gasto__concepto", "estado", "sin_distribuir", "saldo_centavos_min", "saldo_centavos_max", "cantidad_atribuciones_min", "cantidad_atribuciones_max"];
const opcionesEstado = (estados) => Object.entries(estados).map(([value, datos]) => ({ value, label: datos.label }));
const rango = (key, label) => {
  const entero = key.startsWith("gastos_") || key === "cantidad_atribuciones";
  return ["min", "max"].map((limite) => ({ key: `${key}_${limite}`, label: `${label} ${limite === "min" ? "desde" : "hasta"}`, type: "number", step: entero ? "1" : "0.01", ...(entero ? { min: 0 } : {}) }));
};
const mesActual = () => {
  const hoy = new Date();
  return `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}`;
};

function Estado({ valor, calendario = false }) {
  const datos = (calendario ? ESTADOS_CARGA : ESTADOS_GASTO)[valor];
  return <Badge tone={datos?.tone || "gray"}>{datos?.label || "Estado no disponible"}</Badge>;
}

function TablaFinanciera({ consulta, tabla, columnas, vacio, barra, detalleFila }) {
  return <DataTable adaptable columnas={columnas} filas={consulta.filas} total={consulta.total} paginas={consulta.paginas}
    tabla={tabla} vacio={vacio} barra={barra} detalleFila={detalleFila} detalleSinRelleno mantenerEncabezados estado={{ cargando: consulta.isLoading, refrescando: consulta.refrescando,
      error: consulta.error, reintentar: consulta.refetch }} />;
}

function HistorialRepartos({ institucion, area, mes, usuarioId, columnas, detalleFila, onClose }) {
  const tabla = useTablaUrl("historial_repartos");
  const params = {
    gasto__institucion: institucion.id,
    gasto__area: area || undefined,
    gasto__periodo_economico: `${mes}-01`,
    vigente: false,
    page: tabla.pagina,
    pageSize: tabla.tamano,
    ordering: tabla.orden || "-calculado,-version,-id",
  };
  const consulta = useLista("repartos-gasto", params, {
    queryKey: ["finanzas", usuarioId, institucion.id, "historial-repartos", params],
    placeholderData: undefined,
    gcTime: 0,
  });
  return <Modal title="Historial de repartos" onClose={onClose} width={920}>
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-division pb-4"><div><p className="font-semibold">{institucion.nombre} · {mes}</p><p className="mt-1 text-sm text-texto-debil">Versiones anteriores de los repartos del filtro seleccionado</p></div><Badge tone="gray">Histórico · no suma al total actual</Badge></div>
    <TablaFinanciera consulta={consulta} tabla={tabla} columnas={columnas.map(({ filtro, ...col }) => col)} detalleFila={detalleFila} vacio={{ titulo: "No hay versiones históricas para este filtro" }} />
  </Modal>;
}

function ConfiguracionRepartos({ institucion, usuarioId, onNuevo, onCorregir, onClose }) {
  const coberturas = useQuery({
    queryKey: ["finanzas", usuarioId, institucion.id, "coberturas-vigentes"],
    queryFn: () => opcionesFinanzas("coberturas-actividad", institucion.id, { vigente: true }),
    gcTime: 0,
  });
  const reglas = useQuery({
    queryKey: ["finanzas", usuarioId, institucion.id, "reglas-vigentes"],
    queryFn: () => opcionesFinanzas("reglas-reparto", institucion.id, { vigente: true }),
    gcTime: 0,
  });
  const error = coberturas.error || reglas.error;
  return <Modal title="Configuración vigente de repartos" onClose={onClose} width={820}>
    <div className="mb-5 flex flex-wrap gap-2">
      <Button variant="secondary" onClick={() => onNuevo("cobertura-reparto")}>Verificar un área</Button>
      <Button variant="ghost" onClick={() => onNuevo("regla-reparto")}>Agregar regla</Button>
    </div>
    <AyudaFinanzas titulo="Áreas verificadas y reglas"><p>La verificación del área confirma que cada atención completada tiene su registro financiero y que el área registra aquí toda su actividad. La regla indica qué concepto de gasto se distribuye.</p></AyudaFinanzas>
    {error && <EstadoError error={error} titulo="No se pudo consultar la configuración" onReintentar={() => { coberturas.refetch(); reglas.refetch(); }} />}
    {!error && (coberturas.isLoading || reglas.isLoading) && <Spinner label="Consultando configuración…" />}
    {!error && !coberturas.isLoading && !reglas.isLoading && <div className="grid gap-4 md:grid-cols-2">
      <Card className="p-4"><h3 className="font-semibold">Áreas verificadas</h3>
        <div className="mt-3 space-y-3">{(coberturas.data || []).length === 0
          ? <p className="text-sm text-texto-debil">Todavía no hay áreas verificadas.</p>
          : coberturas.data.map((item) => <div key={item.id} className="border-t border-division pt-3 first:border-0 first:pt-0">
            <p className="font-medium">{item.area_nombre}</p><p className="text-sm text-texto-debil">Desde {item.vigente_desde.slice(0, 7)}</p>
            <Button size="sm" variant="ghost" onClick={() => onCorregir("cobertura-reparto", item)}>Corregir</Button>
          </div>)}</div>
      </Card>
      <Card className="p-4"><h3 className="font-semibold">Reglas activas</h3>
        <div className="mt-3 space-y-3">{(reglas.data || []).length === 0
          ? <p className="text-sm text-texto-debil">Todavía no hay reglas activas.</p>
          : reglas.data.map((item) => <div key={item.id} className="border-t border-division pt-3 first:border-0 first:pt-0">
            <p className="font-medium">{item.concepto_nombre}</p><p className="text-sm text-texto-debil">{item.area_nombre} · Desde {item.vigente_desde.slice(0, 7)}</p>
            <Button size="sm" variant="ghost" onClick={() => onCorregir("regla-reparto", item)}>Corregir</Button>
          </div>)}</div>
      </Card>
    </div>}
  </Modal>;
}

function HistorialCarga({ fila, usuarioId, onClose }) {
  const tabla = useTablaUrl("indicaciones");
  const params = { page: tabla.pagina, pageSize: tabla.tamano };
  const consulta = useLista(`expectativas-gasto/${fila.id}/indicaciones`, params, {
    queryKey: ["finanzas", usuarioId, fila.institucion, "historial", fila.id, params], placeholderData: undefined,
    gcTime: 0,
  });
  return <Modal title={`Historial · ${fila.concepto_nombre}`} onClose={onClose} width={720}>
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-division pb-4"><div><p className="font-semibold">{fila.area_nombre || INSTITUCIONAL}</p><p className="mt-1 text-sm text-texto-debil">Declaraciones de carga por mes · Gasto mensual #{fila.id}</p></div><Badge tone="gray">Historial de carga</Badge></div>
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
  return <Modal title={`Historial de configuración · ${fila.concepto_nombre}`} onClose={onClose} width={820}>
    <div className="mb-4 flex items-center justify-between gap-3 border-b border-division pb-4"><div><p className="font-semibold">{fila.area_nombre || INSTITUCIONAL}</p><p className="mt-1 text-sm text-texto-debil">Configuraciones del concepto y sus períodos de vigencia</p></div><AyudaFinanzas titulo="Vigencia de gastos mensuales"><p>Cada modificación conserva la configuración anterior. La nueva configuración se usa desde su mes de inicio; el mes indicado como fin ya no se incluye. No necesitás crear una configuración nueva cada mes.</p><p>Los números identifican registros, no la cantidad de modificaciones. Sólo se muestran registros incluidos en tus permisos.</p></AyudaFinanzas></div>
    <TablaFinanciera consulta={consulta} tabla={tabla} vacio={{ titulo: "Sin versiones visibles" }} columnas={[
      { key: "id", label: "Referencia", render: (r) => <div>#{r.id}{r.reemplaza && <p className="text-sm text-texto-debil">Reemplaza #{r.reemplaza}</p>}</div> },
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
  const [modal, setModal] = useState(null);
  const [expandido, setExpandido] = useState(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const mes = searchParams.get("mes") || mesActual();
  const area = searchParams.get("area") || "";
  const tabs = [
    ...(permisos.tiene("ver_gastos") ? [{ key: "resumen", label: "Resumen" }, { key: "gastos", label: "Gastos registrados" }, { key: "calendario", label: "Gastos mensuales" }, { key: "repartos", label: "Repartos" }] : []),
    ...(permisos.tiene("ver_costos") ? [{ key: "costos", label: "Costos por atención" }] : []),
    ...(permisos.tiene("ver_dinero") ? [{ key: "dinero", label: "Pagos y cobros" }] : []),
    ...(permisos.tiene("ver_gastos") || permisos.tiene("ver_dinero") ? [{ key: "reportes", label: "Reportes" }] : []),
  ];
  const tab = tabs.some((t) => t.key === searchParams.get("tab")) ? searchParams.get("tab") : tabs[0]?.key;
  const filtrosCalendario = useFiltrosFinanzas("calendario", CAMPOS_CALENDARIO);
  const filtrosGastos = useFiltrosFinanzas("gastos", CAMPOS_GASTOS);
  const filtrosRepartos = useFiltrosFinanzas("repartos", CAMPOS_REPARTOS);
  const calendarioTabla = useTablaUrl("calendario");
  const gastosTabla = useTablaUrl("gastos");
  const repartosTabla = useTablaUrl("repartos");
  const puedeLeer = permisos.tiene("ver_gastos");
  const puedeCatalogo = permisos.tiene("registrar_gastos") || permisos.tiene(CONFIGURAR) || permisos.tiene(CONFIGURAR_REPARTOS);
  const tieneMes = /^\d{4}-(0[1-9]|1[0-2])$/.test(mes);
  const filtro = { institucion: institucion.id, area: area || undefined, periodo_economico: `${mes}-01` };
  const opciones = (recurso, tabla, filtros, habilitada) => ({
    enabled: habilitada && tieneMes,
    placeholderData: undefined,
    gcTime: 0,
    queryKey: ["finanzas", permisos.usuarioId, institucion.id, recurso, filtro, filtros, tabla.pagina, tabla.tamano, tabla.orden],
  });
  const calendario = useLista("expectativas-gasto/calendario", {
    ...filtro, ...filtrosCalendario.valores, page: calendarioTabla.pagina, pageSize: calendarioTabla.tamano, ordering: calendarioTabla.orden,
  }, opciones("calendario", calendarioTabla, filtrosCalendario.valores, puedeLeer && tab === "calendario"));
  const gastos = useLista("gastos", {
    ...filtro,
    ...Object.fromEntries(Object.entries(filtrosGastos.valores).map(([key, value]) => [key,
      /^(importe|total_ajustes|importe_resultante)_(min|max)$/.test(key) && value && !/^-?\d+(\.\d{0,2})?$/.test(value) ? "importe_invalido" : value])),
    page: gastosTabla.pagina, pageSize: gastosTabla.tamano, ordering: gastosTabla.orden,
  }, opciones("gastos", gastosTabla, filtrosGastos.valores, puedeLeer && tab === "gastos"));
  const repartos = useLista("repartos-gasto", {
    gasto__institucion: institucion.id,
    gasto__area: area || undefined,
    gasto__periodo_economico: `${mes}-01`,
    vigente: true,
    ...Object.fromEntries(Object.entries(filtrosRepartos.valores).map(([key, value]) => [key, key.startsWith("saldo_centavos_") && value ? decimalACentavos(value) : value])),
    page: repartosTabla.pagina,
    pageSize: repartosTabla.tamano,
    ordering: repartosTabla.orden || "-calculado,-version,-id",
  }, opciones("repartos", repartosTabla, filtrosRepartos.valores, puedeLeer && tab === "repartos"));
  const areas = useQuery({
    queryKey: ["finanzas", permisos.usuarioId, institucion.id, "areas"],
    queryFn: () => opcionesFinanzas("areas", institucion.id),
    gcTime: 0,
  });
  const conceptos = useQuery({
    queryKey: ["finanzas", permisos.usuarioId, institucion.id, "conceptos"],
    queryFn: () => opcionesFinanzas("conceptos-gasto", institucion.id), enabled: puedeCatalogo || puedeLeer,
    gcTime: 0,
  });
  const catalogoListo = !areas.isLoading && !areas.error && !conceptos.isLoading && !conceptos.error;
  const abrir = (tipo, fila) => setModal({ tipo, fila });
  const acciones = [
    { tipo: "gasto", label: "Registrar gasto", tab: "gastos", permitida: permisos.tiene("registrar_gastos"), catalogo: true, primaria: true },
    { tipo: "expectativa", label: "Agregar gasto mensual", tabs: ["gastos", "calendario"], permitida: permisos.tiene(CONFIGURAR), catalogo: true },
    { tipo: "concepto", label: "Nuevo concepto", permitida: permisos.permite(CONFIGURAR, null) },
    { tipo: "configuracion-repartos", label: "Configurar repartos", tab: "repartos", permitida: permisos.tiene(CONFIGURAR_REPARTOS), catalogo: true },
    { tipo: "configuracion-costos", label: "Configurar costos por atención", tab: "costos", permitida: permisos.permite("configurar_componentes", null) },
    { tipo: "configuracion-cobros", label: "Configurar cobros por atención", tab: "dinero", permitida: permisos.permite("configurar_cobros", null) },
  ].filter((accion) => accion.permitida);
  // Un operador sin lectura conserva sus acciones aunque no tenga pestañas.
  const correspondeAlTab = (accion) => accion.tab === tab || accion.tabs?.includes(tab);
  // Las acciones con catálogo usan conceptos de gasto (registro, mensual y reparto).
  const usaConceptos = acciones.some((accion) => accion.catalogo && correspondeAlTab(accion));
  const esContextual = (accion) => !tabs.length || correspondeAlTab(accion) || (accion.tipo === "concepto" && usaConceptos);
  const otrasAcciones = acciones.filter((accion) => !esContextual(accion));
  const botonAccion = (accion, secundaria = false) => <Button key={accion.tipo}
    variant={secundaria ? "ghost" : accion.primaria ? "primary" : "secondary"}
    className={secundaria ? "h-auto min-h-10 w-full justify-start py-2 text-left" : undefined}
    disabled={permisos.isFetching || (accion.catalogo && !catalogoListo)}
    onClick={() => abrir(accion.tipo)}>{accion.label}</Button>;
  const abrirCuenta = (id) => setModal({ tipo: "cuenta-existente", id });
  const habilitada = (accion, fila) => !permisos.isFetching && permisos.permite(accion, fila.area, fila.sensible);
  const areasVisibles = (areas.data || []).filter((a) => ["ver_costos", "ver_gastos", "registrar_gastos", "ver_dinero", "registrar_dinero", CONFIGURAR, CONFIGURAR_REPARTOS].some((accion) => permisos.permite(accion, a.id)));
  const veInstitucional = permisos.permite(tab === "dinero" ? "ver_dinero" : "ver_gastos", null) || (tab === "reportes" && permisos.permite("ver_dinero", null));
  function cambiarFiltro(campo, valor) {
    setSearchParams((previos) => {
      const siguientes = new URLSearchParams(previos);
      if (valor) siguientes.set(campo, valor); else siguientes.delete(campo);
      siguientes.delete("calendario_pag");
      siguientes.delete("gastos_pag");
      siguientes.delete("repartos_pag");
      siguientes.delete("costos_pag");
      return siguientes;
    }, { replace: true });
    setModal(null);
    setExpandido(null);
  }
  function verGastos(fila, estado, periodo, controlMensual = true) {
    setSearchParams((previos) => {
      const siguientes = new URLSearchParams(previos);
      [...siguientes.keys()].filter((key) => key.startsWith("gastos_")).forEach((key) => siguientes.delete(key));
      siguientes.set("tab", "gastos");
      if (fila) {
        if (fila.area !== undefined) siguientes.set("area", fila.area === null ? "null" : String(fila.area));
        siguientes.set("gastos_f_concepto", String(fila.concepto));
      }
      if (estado) siguientes.set("gastos_f_estado_operativo", estado);
      if (periodo) {
        siguientes.set("mes", periodo.slice(0, 7));
        if (controlMensual) siguientes.set("gastos_f_control_mensual", "true");
      }
      return siguientes;
    });
  }
  function verRepartos(estado, fila) {
    setSearchParams((previos) => {
      const siguientes = new URLSearchParams(previos);
      [...siguientes.keys()].filter((key) => key.startsWith("repartos_")).forEach((key) => siguientes.delete(key));
      siguientes.set("tab", "repartos");
      if (estado === "sin_distribuir") siguientes.set("repartos_f_sin_distribuir", "true");
      else if (estado) siguientes.set("repartos_f_estado", estado);
      if (fila) {
        siguientes.set("area", fila.area == null ? "null" : String(fila.area));
        siguientes.set("repartos_f_gasto__concepto", String(fila.concepto));
      }
      return siguientes;
    });
  }
  function verGastoRelacionado(id) {
    setModal({ tipo: "detalle-remoto", id });
  }
  const opcionesConceptos = (conceptos.data || []).map((c) => ({ value: c.id, label: c.nombre }));
  const definicionesCalendario = {
    concepto_nombre: [{ key: "concepto", label: "Concepto", opciones: opcionesConceptos }],
    estado_carga: [{ key: "estado_carga", label: "Estado de carga", opciones: opcionesEstado(ESTADOS_CARGA) }],
    gastos_pendientes: rango("gastos_pendientes", "Por aprobar"),
    gastos_aprobados: rango("gastos_aprobados", "Aprobados"),
    monto_referencia: rango("monto_referencia", "Referencia mensual (ARS)"),
    importe_aprobado: rango("importe_aprobado", "Importe aprobado (ARS)"),
    diferencia_referencia: rango("diferencia_referencia", "Diferencia (ARS)"),
  };
  const definicionesGastos = {
    control_mensual: [{ key: "control_mensual", label: "Gastos mensuales", opciones: [{ value: "true", label: "Sólo gastos mensuales" }] }],
    concepto_nombre: [{ key: "concepto", label: "Concepto", opciones: opcionesConceptos }, { key: "id", label: "Número de gasto", type: "number", min: 1 }],
    importe: rango("importe", "Importe original (ARS)"),
    total_ajustes: rango("total_ajustes", "Ajustes (ARS)"),
    importe_resultante: rango("importe_resultante", "Importe resultante (ARS)"),
    estado_operativo: [{ key: "estado_operativo", label: "Aprobación", opciones: opcionesEstado(ESTADOS_GASTO) }],
    registrado: [{ key: "registrado_desde", label: "Registro desde", type: "date" }, { key: "registrado_hasta", label: "Registro hasta", type: "date" }],
  };
  const definicionesRepartos = {
    sin_distribuir: [{ key: "sin_distribuir", label: "Saldo sin distribuir", opciones: [{ value: "true", label: "Fuentes aprobadas con saldo" }] }],
    gasto: [{ key: "gasto__concepto", label: "Concepto", opciones: opcionesConceptos }],
    estado: [{ key: "estado", label: "Resultado", opciones: [{ value: "distribuido", label: "Distribuido" }, { value: "sin_actividad", label: "Sin actividad" }, { value: "pendiente", label: "Pendiente" }] }],
    saldo_centavos: rango("saldo_centavos", "Importe (ARS)"),
    atribuciones: rango("cantidad_atribuciones", "Atenciones"),
  };
  const filtrosArea = { valores: { area }, cambiar: ({ area: valor }) => cambiarFiltro("area", valor) };
  const controlArea = [{ key: "area", label: "Área", opciones: [...(permisos.permite("ver_gastos", null) ? [{ value: "null", label: INSTITUCIONAL }] : []), ...areasVisibles.map((a) => ({ value: a.id, label: a.nombre }))] }];
  const conFiltros = (columnas, definiciones, filtros) => columnas.map((col) => ({ ...col,
    ...(definiciones[col.key] ? { filtro: <FiltroColumna label={col.label} controles={definiciones[col.key]} filtros={filtros} /> } : {}),
    ...(col.key === "area_nombre" ? { filtro: <FiltroColumna label="Área" controles={controlArea} filtros={filtrosArea} /> } : {}),
  }));
  const detalleReparto = (fila) => !fila.actualizando ? <DetalleRepartoDesplegable key={`${permisos.usuarioId}:${institucion.id}:${mes}:${area}`} abierto={expandido === fila.id}><DetalleAtribuciones fila={fila} usuarioId={permisos.usuarioId} institucionId={institucion.id} /></DetalleRepartoDesplegable> : null;

  const columnasCalendario = [
    { key: "concepto_nombre", label: "Concepto mensual", orden: "concepto__nombre", render: (r) => <div><strong>{r.concepto_nombre}</strong>{r.sensible && <div className="text-sm text-texto-debil">Sensible</div>}</div> },
    { key: "area_nombre", label: "Área", orden: "area__nombre", render: (r) => r.area_nombre || INSTITUCIONAL },
    { key: "estado_carga", label: "Estado de carga", orden: "estado_carga", render: (r) => <div className="space-y-1"><Estado valor={r.estado_carga} calendario /><p className="text-sm text-texto-debil">{r.indicacion_id == null ? "Sin indicación registrada" : fechaHora(r.indicacion_registrada)}</p></div> },
    { key: "gastos_pendientes", label: "Por aprobar", orden: "gastos_pendientes", render: (r) => <div className="space-y-1"><ConteoGastos cantidad={r.gastos_pendientes} onClick={() => verGastos(r, "pendiente_aprobacion")} />{r.ajustes_pendientes > 0 && <Button size="sm" variant="ghost" onClick={() => verGastos(r, "aprobado")}>{r.ajustes_pendientes} {r.ajustes_pendientes === 1 ? "ajuste" : "ajustes"} por aprobar</Button>}</div> },
    { key: "gastos_aprobados", label: "Aprobados", orden: "gastos_aprobados", render: (r) => <ConteoGastos cantidad={r.gastos_aprobados} onClick={() => verGastos(r, "aprobado")} /> },
    { key: "monto_referencia", label: "Referencia mensual", orden: "monto_referencia", render: (r) => <span className="whitespace-nowrap font-mono">{r.monto_referencia == null ? <span aria-label="Sin referencia">-</span> : importeARS(r.monto_referencia)}</span> },
    { key: "importe_aprobado", label: "Importe aprobado", orden: "importe_aprobado", render: (r) => <span className="whitespace-nowrap font-mono">{importeARS(r.importe_aprobado)}</span> },
    { key: "diferencia_referencia", label: "Diferencia", orden: "diferencia_referencia", render: (r) => <DiferenciaReferencia valor={r.diferencia_referencia} /> },
    { key: "acciones", label: "Acciones", render: (r) => <Button size="sm" variant="ghost" aria-label={`Administrar ${r.concepto_nombre} · ${r.area_nombre || INSTITUCIONAL}`} onClick={() => abrir("administrar-control", r)}><Icon name="edit" size={16} />Administrar</Button> },
  ];
  const columnasGastos = [
    { key: "concepto_nombre", label: "Gasto", orden: "concepto_nombre", render: (r) => <div><strong>{r.concepto_nombre}</strong><p className="text-sm text-texto-debil">#{r.id}{r.sensible ? " · Sensible" : ""}</p><RelacionGasto fila={r} onAbrir={verGastoRelacionado} /></div> },
    { key: "area_nombre", label: "Área", orden: "area__nombre", render: (r) => r.area_nombre || INSTITUCIONAL },
    { key: "importe_resultante", label: "Importe vigente", orden: "importe_resultante", render: (r) => <div><span className="whitespace-nowrap font-mono font-semibold">{importeARS(r.importe_resultante)}</span>{r.reemplazado_por && <p className="text-sm text-texto-debil">No vigente</p>}</div> },
    { key: "estado_operativo", label: "Aprobación", orden: "estado_operativo", render: (r) => <Estado valor={r.estado_operativo} /> },
    { key: "registrado", label: "Registro", orden: "registrado", render: (r) => <div>{fechaHora(r.registrado)}<p className="text-sm text-texto-debil">{r.origen === "central" ? "Carga central" : "Carga de área"}</p></div> },
    { key: "acciones", label: "Acciones", render: (r) => <div className="flex flex-wrap gap-2">
      <Button size="sm" variant="ghost" onClick={() => abrir("detalle", r)}>Detalle</Button>
      {r.estado_operativo === "pendiente_aprobacion" && habilitada("aprobar_gastos", r) && <>
        <Button size="sm" variant="secondary" onClick={() => abrir("aprobar", r)}>Aprobar</Button>
        <Button size="sm" variant="ghost" onClick={() => abrir("rechazar", r)}>Rechazar</Button>
      </>}
      {["pendiente_aprobacion", "rechazado"].includes(r.estado_operativo) && habilitada("registrar_gastos", r) && <Button size="sm" variant="ghost" disabled={!catalogoListo} onClick={() => abrir("reemplazo", r)}>Reemplazar</Button>}
      {r.estado_operativo === "aprobado" && habilitada("corregir_gastos", r) && <Button size="sm" variant="secondary" onClick={() => abrir("ajuste", r)}>Ajustar</Button>}
      {r.cuenta_por_pagar != null && habilitada("ver_dinero", r) && <Button size="sm" variant="ghost" onClick={() => abrirCuenta(r.cuenta_por_pagar)}>Ver cuenta existente</Button>}
      {r.cuenta_por_pagar == null && r.estado_operativo === "aprobado" && habilitada("registrar_dinero", r) && habilitada("ver_dinero", r) && <Button size="sm" variant="ghost" onClick={() => abrir("cuenta-pagar", r)}>Crear cuenta por pagar</Button>}
    </div> },
  ];
  const columnasRepartos = [
    { key: "gasto", label: "Gasto repartido", orden: "gasto__concepto__nombre", render: (r) => <div><strong>{r.concepto_nombre}</strong><p className="text-sm text-texto-debil">Gasto #{r.gasto} · Versión {r.version}{r.vigente ? " · Vigente" : " · Histórica"}</p></div> },
    { key: "area_nombre", label: "Área", orden: "gasto__area__nombre", render: (r) => r.area_nombre || INSTITUCIONAL },
    { key: "periodo_economico", label: "Mes", orden: "gasto__periodo_economico", filtro: <FiltroColumna label="Mes" controles={[{ key: "mes", label: "Mes económico", type: "month" }]} filtros={{ valores: { mes }, cambiar: ({ mes: valor }) => cambiarFiltro("mes", valor) }} />, render: (r) => r.periodo_economico.slice(0, 7) },
    { key: "estado", label: "Resultado", orden: "estado", render: (r) => <div><Badge tone={r.actualizando ? "amber" : r.estado === "distribuido" ? "green" : r.estado === "sin_actividad" ? "info" : "amber"}>{r.actualizando ? "Actualización pendiente" : r.estado === "distribuido" ? "Distribuido" : r.estado === "sin_actividad" ? "Sin actividad" : "Pendiente"}</Badge>{r.motivo && <p className="mt-1 text-sm text-texto-debil">{r.motivo === "sin_regla" ? "Falta una regla" : r.motivo === "sin_cobertura" ? "Falta confirmar cobertura operativa" : r.motivo === "actividad_incompleta" ? "La verificación técnica encontró diferencias" : "Fuente no elegible"}</p>}</div> },
    { key: "saldo_centavos", label: "Importe", orden: "saldo_centavos", render: (r) => <span className="whitespace-nowrap font-mono">{r.actualizando ? "Actualizando reparto" : importeCentavos(r.saldo_centavos)}</span> },
    { key: "atribuciones", label: "Atenciones", orden: "cantidad_atribuciones", render: (r) => <div className="tabular-nums">{r.actualizando ? "Actualización pendiente" : r.atribuciones > 0 ? <button type="button" aria-expanded={expandido === r.id} className="text-accent underline underline-offset-2" onClick={() => setExpandido(expandido === r.id ? null : r.id)}>{expandido === r.id ? "▾ Ocultar" : "▸ Ver"} {r.atribuciones} {r.atribuciones === 1 ? "atención" : "atenciones"}</button> : "Sin asignaciones"}{!r.actualizando && r.saldo_no_atribuido_centavos !== 0 && <p className="text-sm text-texto-debil">Sin distribuir: {importeCentavos(r.saldo_no_atribuido_centavos)}</p>}</div> },
  ];

  return <div data-finance-tab={tab} className="finance-page flex min-h-full flex-col gap-5 p-lg sm:p-xxl">
    <div>
      <div role="group" aria-label="Acciones de Finanzas" className="flex flex-wrap items-center justify-between gap-3">
      <h1 className="flex min-h-10 items-center text-xl font-bold">Finanzas y costos</h1>
      <div className="ml-auto flex max-w-full min-w-0 items-start gap-2">
      <div className="flex min-h-10 min-w-0 flex-wrap justify-end gap-2">
        {(areas.isLoading || conceptos.isLoading) ? <span role="status" className="inline-flex h-10 items-center text-sm text-texto-debil">Preparando acciones…</span> : <>
        {acciones.filter(esContextual).map((accion) => botonAccion(accion))}
        </>}
      </div>
        {!areas.isLoading && !conceptos.isLoading && otrasAcciones.length > 0 && <PanelFlotante key={`${tab}:${modal?.tipo || ""}`} titulo="Acciones de finanzas" icono="list" botonPrincipal>
          <div className="space-y-1">{otrasAcciones.map((accion) => botonAccion(accion, true))}</div>
        </PanelFlotante>}
      </div>
      </div>
      <div className="mt-2 flex items-center gap-2"><p className="text-md text-texto-debil">Gastos registrados, su distribución y costos conocidos de {institucion.nombre}, según tu acceso.</p><AyudaFinanzas titulo="Qué información incluye Finanzas"><p>El administrador institucional puede consultar los gastos registrados de todas las áreas, incluidos los sensibles. Otros usuarios ven los alcances autorizados.</p><p>No existe todavía un cálculo integral del costo total del hospital. Los costos no registrados o no integrados no están incluidos, incluso para administración.</p><p>Aprobado es el gasto con sus ajustes. Distribuido y sin distribuir explican ese mismo aprobado: no son gastos adicionales.</p></AyudaFinanzas></div>
    </div>
    <Card className="p-4">
      <div role="group" aria-label="Filtros y secciones de finanzas" className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-wrap items-end gap-3">
        <div className="w-[180px]"><Field label={tab === "reportes" ? "Mes del informe" : "Mes económico"}><Input type="month" required value={mes} onChange={(e) => cambiarFiltro("mes", e.target.value)} /></Field></div>
        <div className="w-[210px] max-w-full"><Field label="Área"><Select value={area} onChange={(e) => cambiarFiltro("area", e.target.value)}>
          <option value="">{veInstitucional ? "Todas las áreas e institucional" : "Todas mis áreas"}</option>
          {veInstitucional && <option value="null">{INSTITUCIONAL}</option>}
          {areasVisibles.map((a) => <option key={a.id} value={a.id}>{a.nombre}</option>)}
        </Select></Field></div>
        <AyudaFinanzas titulo="Carga, aprobación y reparto"><p>Carga, aprobación y reparto son estados separados. Un reparto nunca registra cargos ni pagos.</p><p>La configuración de gastos mensuales indica qué conceptos debe informar el área cada mes. Marcar la carga completa no aprueba sus gastos ni verifica sus atenciones.</p></AyudaFinanzas>
        </div>
        {tabs.length > 0 && <Tabs className="max-w-full overflow-x-auto [&>button]:whitespace-nowrap [&>button]:px-2.5 [&>button]:text-sm" tabs={tabs} valor={tab} onChange={(valor) => cambiarFiltro("tab", valor)} />}
      </div>
      {puedeLeer && tieneMes && tab !== "dinero" && <div className="mt-4 border-t border-division pt-3"><ProcesamientoFinanzas institucion={institucion} usuarioId={permisos.usuarioId} mes={mes} area={area} /></div>}
    </Card>
    {areas.error && <EstadoError error={areas.error} onReintentar={areas.refetch} titulo="No se pudieron cargar las áreas" />}
    {conceptos.error && <EstadoError error={conceptos.error} onReintentar={conceptos.refetch} titulo="No se pudo cargar el catálogo de gastos" />}
    {!tabs.length ? <EstadoVacio titulo="Tu acceso permite operar sin consultar el listado" detalle="Registrar gastos no concede acceso de lectura. Las cargas delegadas se envían a aprobación central." /> : <>
      {!tieneMes ? <p role="alert">Elegí un mes válido.</p> : tab === "resumen" ? <ResumenFinanzas institucion={institucion} usuarioId={permisos.usuarioId} mes={mes} area={area} onGastos={verGastos} onRepartos={verRepartos} />
        : tab === "reportes" ? <ReportesEjecutivos key={`${mes}:${area}`} institucion={institucion} permisos={permisos} mes={mes} area={area} onGastos={verGastos} />
        : tab === "costos" ? <CostosAtencion key={`${mes}:${area}`} institucion={institucion} permisos={permisos} mes={mes} area={area} areas={areas.data || []} onGasto={permisos.tiene("ver_gastos") ? verGastoRelacionado : undefined} />
        : tab === "dinero" ? <DineroFinanzas key={area} institucion={institucion} permisos={permisos} mes={mes} area={area} />
        : tab === "calendario"
        ? <TablaFinanciera consulta={calendario} tabla={calendarioTabla} columnas={conFiltros(columnasCalendario, definicionesCalendario, filtrosCalendario)} barra={<><FiltrosActivos filtros={filtrosCalendario} definiciones={Object.values(definicionesCalendario).flat()} /><AyudaFinanzas titulo="Cómo leer los gastos mensuales"><p>Las cantidades corresponden a gastos visibles y vigentes; no incluyen los reemplazados ni los aún no declarados. Podés abrir cada cantidad para revisar sus gastos.</p><p>Los ajustes por aprobar no modifican el importe aprobado; se revisan en el historial de cada gasto.</p><p>La diferencia es referencia menos aprobado: positiva en verde, negativa en rojo y cero neutro. Verde no garantiza ahorro ni carga completa: pueden faltar cargas o aprobaciones. Un guion indica que no hay referencia, no que sea cero.</p><p>Modificar vigencia cambia desde cuándo se espera este concepto. No hace falta repetir esa configuración cada mes. Su historial se conserva.</p></AyudaFinanzas></>} vacio={{ titulo: "Sin gastos mensuales para este mes y área", detalle: "Revisá los filtros aplicados. Sólo se muestran conceptos configurados." }} />
        : tab === "gastos"
          ? <TablaFinanciera consulta={gastos} tabla={gastosTabla} columnas={conFiltros(columnasGastos, definicionesGastos, filtrosGastos)} barra={<><FiltrosActivos filtros={filtrosGastos} definiciones={Object.values(definicionesGastos).flat()} />{["importe", "total_ajustes"].includes(gastosTabla.orden.replace(/^-/, "")) && <div className="flex flex-wrap items-center gap-2 text-sm"><span>Orden guardado: {gastosTabla.orden.includes("total_ajustes") ? "ajustes" : "importe original"} ({gastosTabla.orden.startsWith("-") ? "mayor a menor" : "menor a mayor"})</span><Button size="sm" variant="ghost" onClick={() => gastosTabla.ordenarPor("importe_resultante")}>Ordenar por importe vigente</Button></div>}<AyudaFinanzas titulo="Importes y correcciones"><p>El importe vigente es el original más sus ajustes. En Detalle podés ver el original, los ajustes y su historial. Un registro reemplazado conserva su historial, pero no se suma como gasto vigente.</p><p>Los enlaces de reemplazo permiten seguir cada corrección. Sólo ves gastos incluidos en tus permisos.</p></AyudaFinanzas></>} vacio={{ titulo: "Sin gastos visibles para este mes y área", detalle: "Revisá los filtros aplicados. Sólo se muestran registros incluidos en tus permisos." }} />
          : <TablaFinanciera consulta={repartos} tabla={repartosTabla} columnas={conFiltros(columnasRepartos, definicionesRepartos, filtrosRepartos)} detalleFila={detalleReparto} barra={<><FiltrosActivos filtros={filtrosRepartos} definiciones={Object.values(definicionesRepartos).flat()} /><Button size="sm" variant="ghost" onClick={() => abrir("historial-repartos")}>Ver historial</Button><AyudaFinanzas titulo="Cómo leer un reparto"><p>Actividad verificada significa que cada atención completada tiene su registro financiero correcto y que el área confirmó que registra aquí todas sus atenciones.</p><p>El importe de cada fila es el gasto aprobado con sus ajustes. “Atenciones” muestra cuántas lo comparten y permite revisar cada importe asignado.</p><p>Las versiones históricas se consultan por separado y no se suman al total actual. Un reparto no crea cargos ni pagos.</p></AyudaFinanzas></>} vacio={{ titulo: "Sin repartos para estos filtros", detalle: "Los gastos sin regla o cobertura aparecerán como pendientes después del procesamiento." }} />}
    </>}
    {modal?.tipo === "configuracion-costos" && <ConfiguracionCostos institucion={institucion} permisos={permisos} onClose={() => setModal(null)} />}
    {modal?.tipo === "configuracion-cobros" && <ConfiguracionCobros institucion={institucion} permisos={permisos} onClose={() => setModal(null)} />}
    {modal?.tipo === "cuenta-pagar" && <CrearCuentaPorPagar gasto={modal.fila} onClose={() => setModal(null)} onCreada={abrirCuenta} />}
    {modal?.tipo === "cuenta-existente" && <DetalleCuenta key={modal.id} id={modal.id} institucion={institucion} permisos={permisos} onClose={() => setModal(null)} />}
    {modal?.tipo === "administrar-control" && <DetalleControlMensual fila={modal.fila} mes={mes} puedeConfigurar={habilitada(CONFIGURAR, modal.fila)} onAccion={(tipo) => abrir(tipo, modal.fila)} onClose={() => setModal(null)} />}
    {modal?.tipo === "historial" && <HistorialCarga fila={modal.fila} usuarioId={permisos.usuarioId} onClose={() => setModal(null)} />}
    {modal?.tipo === "versiones" && <VersionesEsperado fila={modal.fila} usuarioId={permisos.usuarioId} onClose={() => setModal(null)} onHistorial={(fila) => abrir("historial", fila)} />}
    {modal?.tipo === "detalle" && <DetalleGasto fila={modal.fila} permisos={permisos} onAbrir={verGastoRelacionado} onClose={() => setModal(null)} />}
    {modal?.tipo === "detalle-remoto" && <DetalleGastoRemoto id={modal.id} usuarioId={permisos.usuarioId} institucionId={institucion.id} permisos={permisos} onAbrir={verGastoRelacionado} onClose={() => setModal(null)} />}
    {modal?.tipo === "historial-repartos" && <HistorialRepartos institucion={institucion} area={area} mes={mes} usuarioId={permisos.usuarioId} columnas={columnasRepartos} detalleFila={detalleReparto} onClose={() => setModal(null)} />}
    {modal?.tipo === "configuracion-repartos" && <ConfiguracionRepartos institucion={institucion} usuarioId={permisos.usuarioId} onNuevo={(tipo) => abrir(tipo)} onCorregir={(tipo, fila) => abrir(tipo, fila)} onClose={() => setModal(null)} />}
    {["cobertura-reparto", "regla-reparto"].includes(modal?.tipo) && <FormularioReparto {...modal} mes={mes} institucion={institucion} permisos={permisos} areas={areas.data || []} conceptos={conceptos.data || []} onClose={() => setModal(null)} />}
    {modal && !["administrar-control", "configuracion-costos", "configuracion-cobros", "cuenta-pagar", "cuenta-existente", "historial", "detalle", "detalle-remoto", "versiones", "historial-repartos", "configuracion-repartos", "cobertura-reparto", "regla-reparto"].includes(modal.tipo) && <FormularioGasto {...modal} mes={mes} institucion={institucion} permisos={permisos} areas={areas.data || []} conceptos={conceptos.data || []} onClose={() => setModal(null)} />}
  </div>;
}

function DiferenciaReferencia({ valor }) {
  if (valor == null) return <span aria-label="Sin referencia" className="font-mono">-</span>;
  const centavos = BigInt(decimalACentavos(valor));
  return <span className={`whitespace-nowrap font-mono ${centavos > 0n ? "text-badge-green-fg" : centavos < 0n ? "text-badge-error-fg" : "text-texto-debil"}`}>{importeARS(centavos > 0n ? `+${valor}` : valor)}</span>;
}

function ConteoGastos({ cantidad, onClick }) {
  const texto = `${cantidad} ${cantidad === 1 ? "registro" : "registros"}`;
  return cantidad ? <button type="button" className="font-semibold tabular-nums text-accent underline underline-offset-2" onClick={onClick}>{texto}</button> : <span className="tabular-nums text-texto-debil">{texto}</span>;
}

function RelacionGasto({ fila, onAbrir }) {
  return <div className="space-y-1 text-sm">{fila.reemplaza && <button type="button" className="block text-accent underline underline-offset-2" onClick={() => onAbrir(fila.reemplaza)}>Reemplaza #{fila.reemplaza}</button>}
    {fila.reemplazado_por && <button type="button" className="block text-accent underline underline-offset-2" onClick={() => onAbrir(fila.reemplazado_por)}>Reemplazado por #{fila.reemplazado_por}</button>}</div>;
}

function DetalleGastoRemoto({ id, usuarioId, institucionId, ...props }) {
  const consulta = useQuery({ queryKey: ["finanzas", usuarioId, institucionId, "gasto-detalle", id], queryFn: () => api.get(`/gastos/${id}/`), gcTime: 0 });
  if (!consulta.error && consulta.data) return <DetalleGasto fila={consulta.data} {...props} />;
  return <Modal title={`Gasto #${id}`} onClose={props.onClose}>{consulta.error
    ? <EstadoError error={consulta.error} titulo="No se pudo consultar el gasto relacionado" onReintentar={consulta.refetch} />
    : <Spinner label="Consultando gasto…" />}</Modal>;
}

function DetalleRepartoDesplegable({ abierto, children }) {
  const [montado, setMontado] = useState(false);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (!abierto) {
      setVisible(false);
      const cierre = setTimeout(() => setMontado(false), window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 220);
      return () => clearTimeout(cierre);
    }
    setMontado(true);
    // Un frame con altura cero antes de expandir; no se consulta al estar cerrado.
    let siguiente;
    const inicio = requestAnimationFrame(() => { siguiente = requestAnimationFrame(() => setVisible(true)); });
    return () => { cancelAnimationFrame(inicio); cancelAnimationFrame(siguiente); };
  }, [abierto]);
  return <div inert={!abierto ? "" : undefined} aria-hidden={!abierto} className="grid transition-[grid-template-rows,opacity] duration-200 ease-out motion-reduce:transition-none" style={{ gridTemplateRows: visible && abierto ? "1fr" : "0fr", opacity: visible && abierto ? 1 : 0 }}>
    <div className="min-h-0 overflow-hidden">{montado && <div className="border-t border-division p-4">{children}</div>}</div>
  </div>;
}

function DetalleAtribuciones({ fila, usuarioId, institucionId }) {
  const tabla = useTablaUrl(`atribuciones_${fila.id}`);
  const params = { page: tabla.pagina, pageSize: tabla.tamano };
  const consulta = useLista(`repartos-gasto/${fila.id}/atribuciones`, params, {
    queryKey: ["finanzas", usuarioId, institucionId, "atribuciones", fila.id, params], placeholderData: undefined, gcTime: 0,
  });
  if (consulta.error?.status === 403) return <p role="status" className="text-md text-texto-suave">No tenés autorización para ver el detalle de las atenciones de este reparto.</p>;
  return <section aria-label={`Atenciones del reparto del gasto ${fila.gasto}`} className="space-y-3">
    <h3 className="font-semibold">Distribución del gasto #{fila.gasto}</h3>
    {consulta.data && <dl className="flex flex-wrap gap-6 text-md">
      <div><dt className="text-texto-debil">Total del gasto</dt><dd className="font-mono">{importeCentavos(consulta.data.saldo_centavos)}</dd></div>
      <div><dt className="text-texto-debil">Total distribuido</dt><dd className="font-mono">{importeCentavos(consulta.data.importe_atribuido_centavos)}</dd></div>
      <div><dt className="text-texto-debil">Sin distribuir</dt><dd className="font-mono">{importeCentavos(consulta.data.saldo_no_atribuido_centavos)}</dd></div>
    </dl>}
    <TablaFinanciera consulta={consulta} tabla={tabla} columnas={[
      { key: "referencia_atencion", label: "Referencia de atención", render: (r) => `#${r.referencia_atencion}` },
      { key: "caso_navegable", label: "Atención / caso", envolver: true, render: (r) => r.caso_navegable ? <div><Link className="font-medium text-accent underline underline-offset-2" to={`/casos/${r.caso_navegable}`}>{r.caso_descripcion || "Ver atención"}</Link><p className="mt-1 text-sm text-texto-debil">Caso #{r.caso_navegable}</p></div> : <span className="inline-flex items-center gap-2 text-sm text-texto-debil">Sin enlace <AyudaFinanzas titulo="Por qué no puedo abrir este caso"><p>El caso no está disponible o no tenés acceso clínico en esta institución. El permiso financiero no concede acceso clínico.</p></AyudaFinanzas></span> },
      { key: "ocurrida_en", label: "Fecha", render: (r) => fechaHora(r.ocurrida_en) },
      { key: "area_nombre", label: "Área" },
      { key: "importe_centavos", label: "Importe asignado", render: (r) => <span className="font-mono">{importeCentavos(r.importe_centavos)}</span> },
    ]} vacio={{ titulo: "Sin atenciones atribuidas" }} />
  </section>;
}

function DetalleGasto({ fila, permisos, onClose, onAbrir }) {
  const qc = useQueryClient();
  const [decision, setDecision] = useState(null);
  async function guardado() { await qc.invalidateQueries({ queryKey: ["finanzas"] }); onClose(); }
  const puedeAprobar = permisos && !permisos.isFetching && permisos.permite("aprobar_gastos", fila.area, fila.sensible);
  if (decision) return <Modal title={`Ajuste del gasto #${fila.id}`} width={560}><DecisionAprobacion {...decision} onClose={() => setDecision(null)} onGuardado={guardado} /></Modal>;
  return <Modal title={`Gasto #${fila.id} · ${fila.concepto_nombre}`} onClose={onClose} width={680} footer={<Button variant="secondary" onClick={onClose}>Cerrar detalle</Button>}>
    <div className="space-y-6 text-md">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="font-semibold">{fila.area_nombre || INSTITUCIONAL}</p><p className="mt-1 text-sm text-texto-debil">Mes económico · {fila.periodo_economico.slice(0, 7)}</p></div><Estado valor={fila.estado_operativo} /></div>
      {fila.reemplazado_por && <p className="border-l-2 border-badge-amber-fg pl-3 text-sm">Registro reemplazado: se conserva como historial, pero no se suma al gasto vigente.</p>}
      <section aria-label="Importe del gasto" className="rounded-md bg-superficie-2 p-4">
        <p className="text-sm text-texto-debil">Importe resultante</p><p className="mt-1 break-all text-cifra font-semibold tabular-nums">{importeARS(fila.importe_resultante)}</p>
        <dl className="mt-4 grid grid-cols-2 gap-4 border-t border-division pt-3"><div><dt className="text-sm text-texto-debil">Importe original</dt><dd className="mt-1 break-all tabular-nums">{importeARS(fila.importe)}</dd></div><div><dt className="text-sm text-texto-debil">Ajustes aprobados</dt><dd className="mt-1 break-all tabular-nums">{importeARS(fila.total_ajustes)}</dd></div></dl><p className="mt-3 text-sm text-texto-debil">Los ajustes pendientes o rechazados se conservan en el historial y no se suman al importe resultante.</p>
      </section>
      {fila.motivo_rechazo && <section className="border-l-2 border-danger pl-3"><h3 className="font-semibold">Motivo de rechazo</h3><p className="mt-1">{fila.motivo_rechazo}</p></section>}
      <section><h3 className="mb-3 font-semibold">Ajustes del importe original</h3>
        {!fila.ajustes.length ? <p className="text-sm text-texto-debil">Sin ajustes registrados.</p> : <ul className="divide-y divide-division">{fila.ajustes.map((a) => <li key={a.id} className="space-y-3 py-3"><div className="flex flex-wrap justify-between gap-3"><p className="break-words">{a.motivo}</p><strong className="tabular-nums">{importeARS(a.importe)}</strong></div><EstadoAprobacion fila={a} /><TrazaAprobacion fila={a} />{puedeAprobar && a.estado === "pendiente_aprobacion" && <div className="flex gap-2"><Button size="sm" variant="secondary" onClick={() => setDecision({ titulo: `Aprobar ajuste #${a.id}`, url: `/ajustes-gasto/${a.id}/aprobar/` })}>Aprobar ajuste</Button><Button size="sm" variant="ghost" onClick={() => setDecision({ titulo: `Rechazar ajuste #${a.id}`, rechazar: true, url: `/ajustes-gasto/${a.id}/rechazar/` })}>Rechazar ajuste</Button></div>}</li>)}</ul>}
      </section>
      <section className="border-t border-division pt-4"><h3 className="mb-3 font-semibold">Registro y seguimiento</h3><dl className="grid gap-3 text-sm sm:grid-cols-2"><div><dt className="text-texto-debil">Registrado</dt><dd className="mt-1">{fechaHora(fila.registrado)}</dd></div>{fila.aprobado_en && <div><dt className="text-texto-debil">Aprobado</dt><dd className="mt-1">{fechaHora(fila.aprobado_en)}</dd></div>}</dl><div className="mt-3"><RelacionGasto fila={fila} onAbrir={onAbrir} /></div></section>
    </div>
  </Modal>;
}

function DetalleControlMensual({ fila, mes, puedeConfigurar, onAccion, onClose }) {
  return <Modal title={`Gastos mensuales · ${fila.concepto_nombre}`} onClose={onClose} width={680} footer={<Button variant="secondary" onClick={onClose}>Cerrar detalle</Button>}>
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="font-semibold">{fila.area_nombre || INSTITUCIONAL}</p><p className="mt-1 text-sm text-texto-debil">Mes económico · {mes}</p></div><Estado valor={fila.estado_carga} calendario /></div>
      <section aria-label="Importes de gastos mensuales" className="rounded-md bg-superficie-2 p-4">
        <p className="text-sm text-texto-debil">Gasto aprobado</p><p className="mt-1 break-all text-cifra font-semibold tabular-nums">{importeARS(fila.importe_aprobado)}</p>
        <dl className="mt-4 grid grid-cols-2 gap-4 border-t border-division pt-3"><div><dt className="text-sm text-texto-debil">Monto de referencia</dt><dd className="mt-1 break-all tabular-nums">{fila.monto_referencia == null ? "No configurado" : importeARS(fila.monto_referencia)}</dd></div><div><dt className="flex items-center gap-2 text-sm text-texto-debil">Diferencia <AyudaFinanzas titulo="Cómo interpretar la diferencia"><p>Es la referencia menos lo aprobado, incluidos los ajustes. Es orientativa: el cierre de carga sigue siendo manual, incluso si la diferencia es cero.</p></AyudaFinanzas></dt><dd className="mt-1 break-all tabular-nums">{fila.diferencia_referencia == null ? "Sin referencia" : importeARS(fila.diferencia_referencia)}</dd></div></dl>
      </section>
      {puedeConfigurar && <section><h3 className="mb-3 font-semibold">Gestionar este gasto mensual</h3><div className="flex flex-wrap gap-2"><Button onClick={() => onAccion("indicar")}>Indicar estado de carga</Button><Button variant="secondary" onClick={() => onAccion("version")}>Modificar configuración y vigencia</Button></div></section>}
      <section className="border-t border-division pt-4"><h3 className="mb-2 font-semibold">Consultar historial</h3><div className="flex flex-wrap gap-2"><Button variant="ghost" onClick={() => onAccion("historial")}>Historial de carga</Button><Button variant="ghost" onClick={() => onAccion("versiones")}>Historial de configuración</Button></div></section>
    </div>
  </Modal>;
}
