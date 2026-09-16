import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { api } from "@/api/client";
import { errorFinanciador } from "@/api/financiadores";
import { importeARS, usePermisosFinanzas } from "@/api/finanzas";
import { Badge, Button, Card, Field, Input, Select, Spinner } from "@/components/ui";
import { EstadoError, EstadoVacio } from "@/components/ui/estados";
import { fechaHora, plural } from "@/lib/format";
import { DetalleCuenta } from "../finanzas/DineroFinanzas";

const CAMPOS = ["desde", "hasta", "area", "area_sin_asignar", "financiador", "responsable", "estado", "search"];
const VACIOS = Object.fromEntries(CAMPOS.map((campo) => [campo, ""]));
const VISTAS = {
  cuentas: "Cuentas por cobrar",
  pendientes: "Pendientes administrativos",
  captura: "Atenciones sin captura de cargos",
};
const ESTADOS = {
  cuentas: { pendiente: "Con saldo pendiente", saldada: "Saldadas", a_devolver: "Con saldo a devolver", por_aprobar: "Con registros por aprobar" },
  pendientes: { pendiente: "Pendiente de resolución", arancel_pendiente: "Arancel pendiente", evaluacion_pendiente: "Evaluación pendiente", sin_distribucion: "Sin distribución" },
};
const fecha = (valor) => valor ? String(valor).slice(0, 10).split("-").reverse().join("/") : "—";

function ErrorSeguimiento({ error, reintentar }) {
  return <EstadoError error={{ status: error.status, message: errorFinanciador(error) }} onReintentar={reintentar} />;
}

function mesActual() {
  const hoy = new Date();
  const mes = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}`;
  return { ...VACIOS, desde: `${mes}-01`, hasta: `${mes}-${new Date(hoy.getFullYear(), hoy.getMonth() + 1, 0).getDate()}` };
}

function filtrosDe(parametros, institucion) {
  const otroHospital = parametros.has("seguimiento_institucion") && parametros.get("seguimiento_institucion") !== String(institucion);
  const iniciales = otroHospital || !CAMPOS.some((campo) => parametros.has(campo)) ? mesActual() : VACIOS;
  const vista = !otroHospital && VISTAS[parametros.get("vista")] ? parametros.get("vista") : "cuentas";
  const filtros = Object.fromEntries(CAMPOS.map((campo) => [campo, otroHospital ? iniciales[campo] : parametros.get(campo) ?? iniciales[campo]]));
  if (vista !== "cuentas") filtros.responsable = "";
  if (vista === "captura") { filtros.financiador = ""; filtros.estado = ""; }
  return { ...filtros, vista };
}

function Selector({ label, value, onChange, opciones = [], todas }) {
  return <Field label={label}>
    <Select value={value} onChange={onChange}>
      <option value="">{todas}</option>
      {value && !opciones.some((opcion) => String(opcion.id) === value) && <option value={value}>Selección {value}</option>}
      {opciones.map((opcion) => <option key={opcion.id} value={opcion.id}>{opcion.nombre}</option>)}
    </Select>
  </Field>;
}

function Importes({ datos, campos, className = "" }) {
  return <dl className={`grid gap-x-5 gap-y-3 text-sm sm:grid-cols-3 ${className}`}>
    {campos.map(([titulo, campo]) => <div key={campo}>
      <dt className="text-texto-debil">{titulo}</dt>
      <dd className="mt-1 font-semibold tabular-nums">{importeARS(datos[campo])}</dd>
    </div>)}
  </dl>;
}

function Resumen({ vista, datos, generado }) {
  if (!datos) return <p role="status" className="p-4 text-sm text-texto-debil">El resumen no está disponible.</p>;
  return <section aria-label="Resumen del seguimiento" className="space-y-4 border-b border-division p-4 sm:p-5">
    <div><h3 className="font-semibold">Total del conjunto filtrado</h3><p className="mt-1 text-sm text-texto-debil">{plural(datos.registros, "registro", "registros")} · Incluye todas las páginas.</p></div>
    {vista === "cuentas" && <>
      <Importes datos={datos} campos={[["Importe actual de las cuentas", "obligacion_actual"], ["Cobrado neto confirmado", "registrado_neto"], ["Saldo pendiente de cobro", "pendiente"]]} />
      <Importes datos={datos} campos={[["Cobros por aprobar", "por_aprobar"], ["Devoluciones por aprobar", "reintegros_por_aprobar"], ["Reducciones por aprobar", "ajustes_por_aprobar"]]} />
      <details className="border-t border-division pt-3">
        <summary className="cursor-pointer text-sm font-medium">Importes originales, ajustes y devoluciones</summary>
        <Importes className="mt-3" datos={datos} campos={[["Importe original", "importe_original"], ["Ajustes aprobados", "ajustes_aprobados"], ["Saldo a devolver", "saldo_a_devolver"]]} />
      </details>
      <p className="text-sm text-texto-debil">Los saldos incluyen sólo movimientos y ajustes aprobados. Los importes por aprobar se muestran por separado y pueden coexistir con un saldo en cero; una cuenta con registros por aprobar sigue requiriendo revisión.</p>
    </>}
    {vista === "pendientes" && <>
      <Importes datos={datos} campos={[["Importe administrativo conocido", "importe_pendiente"]]} />
      <p className="text-sm text-texto-debil">{plural(datos.importes_desconocidos, "registro con importe por determinar", "registros con importe por determinar")}. El total conocido no incluye esos registros. Estos pendientes todavía no constituyen una deuda asignada.</p>
    </>}
    {vista === "captura" && <p className="text-sm text-texto-debil">Atenciones registradas que todavía no tienen captura de cargos. Requieren revisión; no se presume un responsable ni un importe a cobrar.</p>}
    {generado && <p className="text-sm text-texto-tenue">Consultado el {fechaHora(generado)}.</p>}
  </section>;
}

function columnasDe(vista, onCuenta, onReservas, bloqueado) {
  const origen = [
    { key: "fecha", label: "Fecha de prestación", render: (fila) => fecha(fila.fecha) },
    { key: "caso", label: "Origen", render: (fila) => <><p className="whitespace-nowrap">Caso #{fila.caso}</p>{fila.prestacion && <p className="mt-1 text-texto-debil">{fila.prestacion}</p>}</> },
  ];
  if (vista === "captura") return [...origen,
    { key: "estado", label: "Revisión", render: () => <Badge tone="amber">Captura pendiente</Badge> },
    { key: "motivo", label: "Motivo" },
    { key: "acciones", label: "Acciones", render: () => <Button size="sm" variant="secondary" disabled={bloqueado} onClick={onReservas}>Ver reservas y saldos</Button> },
  ];
  if (vista === "pendientes") return [...origen,
    { key: "financiador_nombre", label: "Financiador de la cobertura", render: (fila) => fila.financiador_nombre || "Sin financiador registrado" },
    { key: "estado", label: "Revisión", render: (fila) => <Badge tone="amber">{ESTADOS.pendientes[fila.estado] || fila.estado}</Badge> },
    { key: "importe_pendiente", label: "Importe administrativo", render: (fila) => fila.importe_pendiente == null ? <Badge tone="amber">Por determinar</Badge> : importeARS(fila.importe_pendiente) },
    { key: "motivo", label: "Motivo" },
    { key: "acciones", label: "Acciones", render: () => <Button size="sm" variant="secondary" disabled={bloqueado} onClick={onReservas}>Ver reservas y saldos</Button> },
  ];
  return [...origen,
    { key: "contraparte_nombre", label: "Responsable del cobro", render: (fila) => <><p className="font-medium">{fila.contraparte_nombre}</p><p className="mt-1 text-texto-debil">{fila.responsable === "paciente" ? "Paciente" : "Financiador"} · Cuenta #{fila.id}</p><p className="mt-1 text-texto-debil">Cobertura: {fila.financiador_nombre || "Sin financiador registrado"}</p></> },
    { key: "obligacion_actual", label: "Importe de la cuenta", render: (fila) => <><p className="whitespace-nowrap font-medium tabular-nums">{importeARS(fila.obligacion_actual)}</p><p className="mt-1 text-texto-debil">Original: {importeARS(fila.importe_original)}</p><p className="mt-1 text-texto-debil">Ajustes aprobados: {importeARS(fila.ajustes_aprobados)}</p></> },
    { key: "registrado_neto", label: "Cobrado neto confirmado", render: (fila) => importeARS(fila.registrado_neto) },
    { key: "pendiente", label: "Pendiente de cobro", render: (fila) => <span className="font-semibold tabular-nums">{importeARS(fila.pendiente)}</span> },
    { key: "por_aprobar", label: "Registros por aprobar", render: (fila) => <div className="space-y-1"><p>Cobros: {importeARS(fila.por_aprobar)}</p><p>Devoluciones: {importeARS(fila.reintegros_por_aprobar)}</p><p>Reducciones: {importeARS(fila.ajustes_por_aprobar)}</p></div> },
    { key: "saldo_a_devolver", label: "Saldo a devolver", render: (fila) => importeARS(fila.saldo_a_devolver) },
    { key: "acciones", label: "Acciones", render: (fila) => <Button size="sm" variant="secondary" disabled={bloqueado} onClick={() => onCuenta(fila.id)}>Ver cuenta</Button> },
  ];
}

export default function SeguimientoCobros({ usuarioId, institucion, onReservas }) {
  const permisos = usePermisosFinanzas();
  const [parametros, setParametros] = useSearchParams();
  const aplicados = filtrosDe(parametros, institucion.id);
  const firma = JSON.stringify(aplicados);
  const [borrador, setBorrador] = useState(aplicados);
  const [cuenta, setCuenta] = useState(null);
  const [descargando, setDescargando] = useState(false);
  const [errorDescarga, setErrorDescarga] = useState(null);
  const [origenDescarga, setOrigenDescarga] = useState("");
  const descargaEnCurso = useRef(false);
  const montado = useRef(true);
  const contextoActual = useRef("");
  contextoActual.current = `${institucion.id}:${firma}`;
  const hospitalCambio = parametros.has("seguimiento_institucion") && parametros.get("seguimiento_institucion") !== String(institucion.id);
  const paginaSolicitada = Number(parametros.get("page") || 1);
  const page = !hospitalCambio && Number.isSafeInteger(paginaSolicitada) && paginaSolicitada > 0 ? paginaSolicitada : 1;
  const query = new URLSearchParams(Object.entries(aplicados).filter(([, valor]) => valor !== ""));
  query.set("institucion", institucion.id);
  query.set("page", page);
  const consulta = useQuery({
    queryKey: ["finanzas", usuarioId, institucion.id, "seguimiento-cobros", query.toString()],
    queryFn: () => api.get(`/seguimiento-cobros/?${query}`),
    enabled: permisos.tiene("ver_dinero") && !permisos.error,
    gcTime: 0,
    placeholderData: undefined,
  });
  const opciones = consulta.error ? {} : consulta.data?.opciones || {};
  const filas = consulta.error ? [] : consulta.data?.results || [];
  const columnas = columnasDe(aplicados.vista, setCuenta, onReservas, descargando);
  const cambiosPendientes = JSON.stringify(borrador) !== firma;
  const limite = consulta.data?.limite_exportacion;
  const limiteDisponible = Number.isSafeInteger(limite) && limite > 0;
  const superaLimite = limiteDisponible && consulta.data?.count > limite;
  const paginaInvalida = page > 1 && consulta.error?.status === 404
    && ["Página inválida.", "Invalid page."].includes(consulta.error?.data?.detail);

  useEffect(() => { montado.current = true; return () => { montado.current = false; }; }, []);
  useEffect(() => { setBorrador(JSON.parse(firma)); setErrorDescarga(null); }, [firma]);
  useEffect(() => {
    if (hospitalCambio || !parametros.has("seguimiento_institucion") || !CAMPOS.some((campo) => parametros.has(campo))) {
      const nuevos = new URLSearchParams(parametros);
      nuevos.set("seguimiento_institucion", institucion.id);
      nuevos.set("vista", aplicados.vista);
      for (const campo of CAMPOS) {
        if (aplicados[campo] || campo === "desde" || campo === "hasta") nuevos.set(campo, aplicados[campo]);
        else nuevos.delete(campo);
      }
      if (hospitalCambio) nuevos.delete("page");
      setParametros(nuevos, { replace: true });
    }
  }, [parametros, institucion.id, hospitalCambio, firma, setParametros]);

  function aplicar(filtros, pagina = 1) {
    if (descargaEnCurso.current) return;
    const nuevos = new URLSearchParams({ tab: "seguimiento", seguimiento_institucion: institucion.id, vista: filtros.vista });
    for (const campo of CAMPOS) if (filtros[campo] || campo === "desde" || campo === "hasta") nuevos.set(campo, filtros[campo]);
    if (pagina > 1) nuevos.set("page", pagina);
    setParametros(nuevos);
  }
  function editar(campo) { return (event) => setBorrador((previo) => ({ ...previo, [campo]: event.target.value })); }
  function cambiarVista(event) {
    const vista = event.target.value;
    aplicar({ ...aplicados, vista, estado: "", responsable: "", ...(vista === "captura" ? { financiador: "", search: "" } : {}) });
    setCuenta(null);
  }
  async function exportar() {
    if (descargaEnCurso.current || consulta.isFetching || consulta.error || cambiosPendientes || !filas.length || !limiteDisponible || superaLimite || !permisos.tiene("ver_dinero")) return;
    descargaEnCurso.current = true;
    const contexto = contextoActual.current;
    const exportacion = new URLSearchParams(query);
    exportacion.delete("page");
    exportacion.delete("page_size");
    exportacion.set("formato", "csv");
    const origen = `${VISTAS[aplicados.vista]} · ${institucion.nombre}`;
    setOrigenDescarga(origen);
    setDescargando(true);
    setErrorDescarga(null);
    try {
      await api.download(`/seguimiento-cobros/?${exportacion}`, `seguimiento-${aplicados.vista}-hospital-${institucion.id}.csv`);
    } catch (error) {
      if (montado.current && contextoActual.current === contexto) setErrorDescarga(error);
    } finally {
      descargaEnCurso.current = false;
      if (montado.current) setDescargando(false);
    }
  }

  if (permisos.isLoading) return <Spinner label="Consultando permisos financieros…" />;
  if (permisos.error) return <ErrorSeguimiento error={permisos.error} reintentar={permisos.refetch} />;
  if (!permisos.tiene("ver_dinero")) return <Card className="p-5"><p role="alert">No tenés permiso para consultar el seguimiento de cobros en este hospital.</p></Card>;

  return <Card className="overflow-hidden">
    <form className="border-b border-division p-4 sm:p-5" onSubmit={(event) => { event.preventDefault(); aplicar({ ...borrador, search: borrador.search.trim() }); }}>
      <fieldset disabled={descargando} className="space-y-4">
      <div><h2 className="text-lg font-semibold">Seguimiento de cobros</h2><p className="mt-1 text-sm text-texto-debil">Revisá las cuentas y los pendientes de las prestaciones realizadas en el hospital.</p></div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Field label="Vista"><Select value={aplicados.vista} onChange={cambiarVista}>{Object.entries(VISTAS).map(([valor, nombre]) => <option key={valor} value={valor}>{nombre}</option>)}</Select></Field>
        <Field label="Desde"><Input type="date" value={borrador.desde} onChange={editar("desde")} /></Field>
        <Field label="Hasta"><Input type="date" min={borrador.desde || undefined} value={borrador.hasta} onChange={editar("hasta")} /></Field>
        <Selector label="Área de origen" value={borrador.area_sin_asignar === "true" ? "sin_area" : borrador.area} onChange={(event) => {
          const valor = event.target.value;
          setBorrador((previo) => ({ ...previo, area: valor === "sin_area" ? "" : valor, area_sin_asignar: valor === "sin_area" ? "true" : "" }));
        }} opciones={[{ id: "sin_area", nombre: "Sin área asignada" }, ...(opciones.areas || [])]} todas="Todas las áreas permitidas" />
        {aplicados.vista !== "captura" && <Selector label="Financiador de la cobertura" value={borrador.financiador} onChange={editar("financiador")} opciones={opciones.financiadores} todas="Todos los financiadores" />}
        {aplicados.vista === "cuentas" && <Field label="Responsable del cobro"><Select value={borrador.responsable} onChange={editar("responsable")}><option value="">Todos los responsables</option><option value="financiador">Financiador</option><option value="paciente">Paciente</option></Select></Field>}
        {aplicados.vista !== "captura" && <Field label="Estado"><Select value={borrador.estado} onChange={editar("estado")}><option value="">Todos los estados</option>{Object.entries(ESTADOS[aplicados.vista]).map(([valor, nombre]) => <option key={valor} value={valor}>{nombre}</option>)}</Select></Field>}
        <Field label={aplicados.vista === "captura" ? "Buscar caso" : "Buscar caso, responsable o prestación"}><Input value={borrador.search} onChange={editar("search")} maxLength={160} placeholder={aplicados.vista === "captura" ? "Número de caso" : "Caso, nombre o prestación"} /></Field>
      </div>
      <p className="text-sm text-texto-debil">El período corresponde a la fecha de la prestación. Los cobros y las devoluciones se consideran aunque se hayan registrado en otra fecha. Sólo se muestran los datos incluidos en tus permisos.</p>
      {aplicados.vista === "cuentas" && <p className="text-sm text-texto-debil">El filtro de financiador incluye los copagos de sus pacientes. Elegí el responsable para distinguir quién debe pagar.</p>}
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" disabled={consulta.isFetching}>Aplicar filtros</Button>
        <Button type="button" variant="ghost" onClick={() => aplicar({ ...mesActual(), vista: aplicados.vista })}>Mes actual</Button>
        <Button type="button" variant="ghost" onClick={() => aplicar({ ...VACIOS, vista: aplicados.vista })}>Limpiar filtros</Button>
        {cambiosPendientes && <span role="status" className="text-sm text-texto-debil">Aplicá los cambios para actualizar la consulta y la exportación.</span>}
      </div>
      </fieldset>
    </form>
    {consulta.isLoading ? <Spinner label="Consultando seguimiento de cobros…" /> : paginaInvalida ? <div role="status" className="space-y-3 p-4 sm:p-5">
      <p>Esta página ya no está disponible con los filtros aplicados. Los registros pueden haber cambiado al actualizar una cuenta.</p>
      <Button variant="secondary" onClick={() => aplicar(aplicados)}>Volver a la primera página</Button>
    </div> : consulta.error ? <div className="p-4"><ErrorSeguimiento error={consulta.error} reintentar={consulta.refetch} /></div> : <>
      <Resumen vista={aplicados.vista} datos={consulta.data?.resumen} generado={consulta.data?.generado_en} />
      <section aria-label="Exportación del seguimiento" className="space-y-3 border-b border-division p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="max-w-[44rem] text-sm text-texto-debil">
            <p>El CSV incluye todas las páginas con los filtros aplicados.{limiteDisponible && ` Hasta ${limite.toLocaleString("es-AR")} registros por descarga.`} La exportación queda auditada y vuelve a consultar permisos y saldos.</p>
            <p className="mt-1">El archivo corresponde al hospital, la vista y los filtros elegidos al iniciar la descarga. Importes en ARS con coma decimal e identificadores como texto.</p>
          </div>
          <Button variant="secondary" onClick={exportar} disabled={descargando || consulta.isFetching || cambiosPendientes || !limiteDisponible || superaLimite || !filas.length}>{descargando ? "Exportando CSV…" : "Exportar CSV"}</Button>
        </div>
        {descargando && <p role="status" className="text-sm text-texto-debil">Preparando archivo: {origenDescarga}. Si cambiás de pantalla, la descarga conserva esta selección.</p>}
        {!limiteDisponible && <p role="status" className="text-sm text-texto-debil">La exportación no está disponible por el momento.</p>}
        {superaLimite && <p role="status" className="text-sm text-badge-amber-fg">El resultado supera el límite de exportación. Acotá el período o los filtros para descargarlo completo.</p>}
        {errorDescarga && <ErrorSeguimiento error={errorDescarga} />}
      </section>
      {!filas.length ? <EstadoVacio titulo="Sin registros con estos filtros" detalle="Probá con otro período, área o estado." /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm">
        <thead className="border-b border-division bg-superficie-2 text-texto-debil"><tr>{columnas.map((columna) => <th key={columna.key} scope="col" className="whitespace-nowrap px-4 py-3 font-semibold">{columna.label}</th>)}</tr></thead>
        <tbody>{filas.map((fila) => <tr key={fila.id} className="border-b border-division last:border-0">{columnas.map((columna) => <td key={columna.key} className="px-4 py-3 align-top">{columna.render ? columna.render(fila) : fila[columna.key] || "—"}</td>)}</tr>)}</tbody>
      </table></div>}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-division px-4 py-3">
        <span className="text-sm text-texto-debil">{plural(consulta.data?.count ?? filas.length, "registro", "registros")} · Página {page}</span>
        <div className="flex gap-2"><Button size="sm" variant="ghost" disabled={page === 1 || consulta.isFetching || descargando} onClick={() => aplicar(aplicados, page - 1)}>Anterior</Button><Button size="sm" variant="ghost" disabled={!consulta.data?.next || consulta.isFetching || descargando} onClick={() => aplicar(aplicados, page + 1)}>Siguiente</Button></div>
      </div>
    </>}
    {cuenta != null && <DetalleCuenta key={cuenta} id={cuenta} institucion={institucion} permisos={permisos} onClose={() => setCuenta(null)} />}
  </Card>;
}
