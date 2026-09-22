import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/api/client";
import { importeARS } from "@/api/finanzas";
import { errorFinanciador } from "@/api/financiadores";
import { useAuth } from "@/auth/AuthContext";
import { Icon } from "@/components/icons";
import { Ayuda, Badge, Button, Card, Checkbox, Field, Input, Select, Textarea } from "@/components/ui";
import { EstadoError } from "@/components/ui/estados";
import { cn } from "@/lib/cn";
import { fechaHora, plural } from "@/lib/format";
import AutorizacionesCaso from "./AutorizacionesCaso";
import AutorizacionEvaluacion, { ESTADOS_EVALUACION_AUTORIZACION } from "./AutorizacionEvaluacion";

const ESTADOS = {
  verificada: "Afiliación verificada", pendiente: "Pendiente de verificación", particular: "Atención particular",
  reservada: "Reservada", realizada: "Realizada", liberada: "Liberada",
  autorizacion_pendiente: "Autorización pendiente", resuelta: "Responsable definido", arancel_pendiente: "Arancel pendiente",
  evaluacion_pendiente: "Evaluación pendiente", sin_cobro: "Sin cobro",
};
const tono = (estado) => estado === "pendiente" || estado?.includes("pendiente") ? "amber" : estado === "verificada" || estado === "realizada" ? "green" : "gray";
const fecha = (iso) => iso ? String(iso).slice(0, 10).split("-").reverse().join("/") : "—";

/**
 * La consulta de cobertura del caso, compartida por el panel y por la fila de
 * la ficha. Misma clave: react-query hace un solo pedido para los dos.
 */
function useCoberturaCaso(caso) {
  const { user } = useAuth();
  return useQuery({
    queryKey: ["cobertura-caso", user?.id, caso.id, caso.actualizado, caso.nodo_actual],
    queryFn: () => api.get(`/casos/${caso.id}/cobertura/`),
    gcTime: 0,
    retry: false,
  });
}

/**
 * Qué le falta a la cobertura de este caso para quien puede operarla.
 *
 * `null` si no hay nada pendiente, si el módulo no está habilitado o si la
 * persona no puede operar. Si no, `{ tipo: "afiliacion" }` o
 * `{ tipo: "prestaciones", cantidad }` con las prestaciones del paso que no
 * tienen una reserva abierta ni realizada. Una reserva liberada no cuenta: se
 * verificó que la prestación no se hizo, así que hay que consultar de nuevo.
 */
export function pendienteCobertura(datos) {
  if (!datos?.activo || !datos.puede_operar) return null;
  if (!datos.afiliacion) return { tipo: "afiliacion", cantidad: 0 };
  const cubiertas = new Set(
    (datos.reservas || []).filter((r) => r.estado === "reservada" || r.estado === "realizada").map((r) => r.prestacion),
  );
  const cantidad = (datos.prestaciones || []).filter((p) => !cubiertas.has(p.id)).length;
  return cantidad > 0 ? { tipo: "prestaciones", cantidad } : null;
}

/**
 * El estado de la cobertura en una línea, para la ficha del caso.
 *
 * Donde el módulo no está habilitado el panel no se pinta, y esta fila es lo
 * único que lo dice. Con afiliación registrada pero prestaciones sin consultar
 * lo dice debajo del badge: si no, la ficha mostraba «Afiliación verificada» en
 * verde y el pendiente quedaba escondido.
 */
export function EstadoCoberturaCaso({ caso }) {
  const consulta = useCoberturaCaso(caso);
  if (consulta.isLoading) return <span className="text-texto-tenue">…</span>;
  if (consulta.error || !consulta.data) return <span className="text-texto-debil">Sin datos</span>;
  const datos = consulta.data;
  if (!datos.activo) return <span className="text-texto-debil">No habilitada</span>;
  if (!datos.afiliacion) return <Badge tone="amber">Sin afiliación</Badge>;
  const pendiente = pendienteCobertura(datos);
  return (
    <span className="inline-flex flex-col items-end gap-1">
      <Badge tone={tono(datos.afiliacion.estado)}>{ESTADOS[datos.afiliacion.estado] || datos.afiliacion.estado}</Badge>
      {pendiente?.tipo === "prestaciones" && (
        <span className="text-sm text-badge-amber-fg">{plural(pendiente.cantidad, "prestación sin consultar", "prestaciones sin consultar")}</span>
      )}
    </span>
  );
}

const ID_PANEL = "cobertura-caso";

function irAlPanel() {
  const panel = document.getElementById(ID_PANEL);
  if (!panel) return;
  const plegable = panel.querySelector("details");
  if (plegable) plegable.open = true;
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

/**
 * Franja ámbar para el panel del paso: la cobertura quedó detrás del trabajo y
 * hace falta que quien va a avanzar sepa que la tiene pendiente antes de tocar
 * el botón. No bloquea nada: el motor deja completar el paso clínico aunque la
 * cobertura falle, y eso es a propósito.
 */
export function AvisoCoberturaPendiente({ caso, className }) {
  const consulta = useCoberturaCaso(caso);
  const pendiente = pendienteCobertura(consulta.data);
  if (!pendiente) return null;
  const texto = pendiente.tipo === "afiliacion"
    ? "Falta registrar la afiliación de este caso."
    : `Falta consultar la cobertura de ${plural(pendiente.cantidad, "prestación", "prestaciones")} de este paso.`;
  return (
    <div className={cn("flex flex-wrap items-center gap-3 rounded-md border border-badge-amber-fg/25 bg-badge-amber-bg px-3.5 py-3", className)}>
      <Icon name="alert" size={18} className="shrink-0 text-badge-amber-fg" />
      <div className="min-w-40 flex-1 text-md text-badge-amber-fg">
        <strong>Cobertura pendiente.</strong> {texto} El paso se puede completar igual.
      </div>
      <Button type="button" size="sm" variant="secondary" onClick={irAlPanel}>Ir a la cobertura</Button>
    </div>
  );
}

export default function CoberturaCaso({ caso, ocupado = false }) {
  const qc = useQueryClient();
  const [mensaje, setMensaje] = useState("");
  const consulta = useCoberturaCaso(caso);

  async function actualizar(texto) {
    setMensaje(texto);
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["cobertura-caso"] }),
      qc.invalidateQueries({ queryKey: ["historial-cobertura"] }),
      qc.invalidateQueries({ queryKey: ["detalle", "casos"] }),
    ]);
  }

  const datos = consulta.data;
  // Sin el módulo habilitado no hay nada que operar: el panel ocupaba 250 px
  // para decir «no está habilitada» y «todavía no se registró la afiliación».
  // Lo dice la fila «Cobertura» de la ficha. Mientras carga tampoco se pinta:
  // en el hospital que no lo usa aparecería y desaparecería en cada entrada.
  if (consulta.isLoading || (datos && !datos.activo)) return null;

  return (
    <Card id={ID_PANEL} className="p-0" aria-label="Cobertura del caso">
      {/* Plegable, abierta por defecto: va detrás del panel del paso y quien ya
          resolvió la cobertura puede guardarla; quien la tiene pendiente la ve
          entera sin tocar nada. */}
      <details open>
        <summary className="cursor-pointer p-lg text-lg font-bold sm:px-xxl sm:pt-xxl">Cobertura del caso</summary>
        <div className="px-lg pb-lg sm:px-xxl sm:pb-xxl">
          {/* La ayuda va junto al botón y no en el <summary>: un click ahí
              plegaría el panel en vez de abrir la ayuda. */}
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Ayuda>Registrá la afiliación y consultá el importe antes de la prestación. Una autorización pendiente se gestiona según el circuito de atención; no acepta cargos del paciente.</Ayuda>
            <Button type="button" size="sm" variant="ghost" disabled={consulta.isFetching || ocupado} onClick={() => actualizar("")}>Actualizar cobertura</Button>
          </div>
          {mensaje && <p role="status" className="mt-4 rounded-md bg-badge-green-bg p-3 text-sm text-badge-green-fg">{mensaje}</p>}
          {consulta.error ? (
            <EstadoError error={consulta.error} onReintentar={consulta.refetch} titulo="No se pudo consultar la cobertura" />
          ) : datos && (
            <ContenidoCobertura
              key={JSON.stringify([caso.id, datos.contexto, datos.afiliacion?.id])}
              casoId={caso.id}
              datos={datos}
              ocupadoClinica={ocupado}
              actualizar={actualizar}
            />
          )}
          {datos?.activo && <AutorizacionesCaso key={caso.id} caso={caso} ocupadoClinica={ocupado} />}
        </div>
      </details>
    </Card>
  );
}

function ContenidoCobertura({ casoId, datos, ocupadoClinica, actualizar }) {
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);
  const [corregir, setCorregir] = useState(false);
  const bloqueado = ocupado || ocupadoClinica;
  const puedeOperar = datos.activo && datos.puede_operar;
  const reservas = datos.reservas || [];
  const tieneReservas = reservas.some((r) => r.estado === "reservada");

  async function operar(accion, body, mensaje) {
    setError(null);
    setOcupado(true);
    try {
      const resultado = await api.post(`/casos/${casoId}/cobertura-${accion}/`, { contexto: datos.contexto, ...body });
      if (mensaje) await actualizar(mensaje);
      return resultado;
    } catch (err) {
      setError(err);
      return null;
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className="mt-5 space-y-5">
      {!datos.activo && <p className="rounded-md bg-superficie-2 p-3 text-sm text-texto-debil">La gestión de cobertura no está habilitada en este hospital.</p>}
      {error && <p role="alert" className="rounded-md bg-badge-error-bg p-3 text-sm text-badge-error-fg">{errorFinanciador(error)}</p>}
      <section aria-label="Afiliación de este caso" className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="font-semibold">Afiliación de este caso</h3>
            {datos.afiliacion ? <ResumenAfiliacion afiliacion={datos.afiliacion} /> : <p className="mt-1 text-sm text-badge-amber-fg">Todavía no se registró la afiliación.</p>}
          </div>
          {datos.afiliacion && puedeOperar && !corregir && (
            <span className="flex items-center gap-2"><Button type="button" size="sm" variant="secondary" disabled={bloqueado || tieneReservas} onClick={() => setCorregir(true)}>Corregir afiliación</Button>{tieneReservas && puedeOperar && <Ayuda>La afiliación no se puede corregir mientras haya reservas abiertas. Revisá su realización antes de solicitar una liberación en Finanzas.</Ayuda>}</span>
          )}
        </div>
        {puedeOperar && !tieneReservas && (!datos.afiliacion || corregir) && (
          <SeleccionAfiliacion
            afiliados={datos.afiliados || []}
            esCorreccion={Boolean(datos.afiliacion)}
            ocupado={bloqueado}
            cancelar={() => setCorregir(false)}
            guardar={(body) => operar("afiliacion", body, "Afiliación registrada para este caso. Se conservaron las decisiones anteriores.")}
          />
        )}
        {datos.activo && !datos.puede_operar && <p className="text-sm text-texto-debil">La cobertura se muestra en modo de consulta. Tu acceso a este caso no permite modificarla.</p>}
      </section>

      {datos.activo && (
        <section aria-label="Prestaciones del paso actual" className="space-y-3 border-t border-division pt-5">
          <h3 className="font-semibold">Prestaciones del paso actual</h3>
          {!(datos.prestaciones || []).length ? <p className="text-sm text-texto-debil">Este paso no tiene prestaciones configuradas para consultar cobertura.</p> : (
            <div className="space-y-3">
              {datos.prestaciones.map((prestacion) => (
                <PrestacionCaso
                  key={`${prestacion.id}:${Boolean(prestacion.puede_aceptar)}:${Boolean(puedeOperar)}`}
                  prestacion={prestacion}
                  reservas={reservas.filter((r) => r.prestacion === prestacion.id)}
                  puedeOperar={puedeOperar}
                  conAfiliacion={Boolean(datos.afiliacion)}
                  exigeAceptacion={Boolean(datos.exige_aceptacion)}
                  ocupado={bloqueado}
                  operar={operar}
                />
              ))}
            </div>
          )}
          {!datos.afiliacion && (datos.prestaciones || []).length > 0 && <p className="text-sm text-texto-debil">Registrá una afiliación, atención particular o declaración pendiente para consultar estas prestaciones.</p>}
        </section>
      )}

      {reservas.length > 0 && <RegistrosPrestacion reservas={reservas} />}
      {(datos.historial_afiliaciones || []).length > 0 && (
        <details className="border-t border-division pt-4">
          <summary className="cursor-pointer text-sm font-semibold text-texto-suave">Historial de afiliación del caso{datos.historial_truncado && <Ayuda className="ml-2">Se muestran las selecciones más recientes. El historial completo está disponible en la pestaña Cobertura del paciente.</Ayuda>}</summary>
          <ol className="mt-3 space-y-3">
            {datos.historial_afiliaciones.map((item) => <li key={item.id} className="border-l-2 border-division pl-3"><ResumenAfiliacion afiliacion={item} /></li>)}
          </ol>
        </details>
      )}
    </div>
  );
}

function ResumenAfiliacion({ afiliacion }) {
  return (
    <div className="mt-2 space-y-1 text-sm">
      <Badge tone={tono(afiliacion.estado)}>{ESTADOS[afiliacion.estado] || afiliacion.estado}</Badge>
      {afiliacion.financiador_nombre && <p className="font-semibold">{afiliacion.financiador_nombre} · {afiliacion.plan_nombre || "Sin plan"}</p>}
      {afiliacion.numero && <p>N.º de afiliado: {afiliacion.numero}</p>}
      {afiliacion.declaracion && <p className="break-words">{afiliacion.declaracion}</p>}
      <p className="break-words text-texto-debil">{afiliacion.motivo}</p>
      <p className="text-texto-tenue">{fechaHora(afiliacion.creado)} · {afiliacion.usuario_nombre || "Usuario registrado"}</p>
    </div>
  );
}

function SeleccionAfiliacion({ afiliados, esCorreccion, ocupado, cancelar, guardar }) {
  const [tipo, setTipo] = useState("");
  const [afiliado, setAfiliado] = useState("");
  const [declaracion, setDeclaracion] = useState("");
  const [motivo, setMotivo] = useState("");
  const valido = motivo.trim() && (tipo === "particular" || (tipo === "verificada" && afiliado) || (tipo === "pendiente" && declaracion.trim()));

  function guardarSeleccion(event) {
    event.preventDefault();
    if (!valido || ocupado) return;
    guardar({ motivo: motivo.trim(), ...(tipo === "verificada" ? { afiliado: Number(afiliado) } : tipo === "particular" ? { particular: true } : { declaracion: declaracion.trim() }) });
  }

  return (
    <form onSubmit={guardarSeleccion} className="space-y-3 rounded-md border border-division p-4">
      <p className="text-sm text-texto-debil">{esCorreccion ? "La corrección se aplicará a las próximas evaluaciones de este caso. Las prestaciones y decisiones anteriores se conservan." : "La selección queda vinculada a este caso; un cambio posterior en el padrón no la reemplaza automáticamente."}</p>
      <Field label="Tipo de afiliación">
        <Select value={tipo} required disabled={ocupado} onChange={(e) => { setTipo(e.target.value); setAfiliado(""); }}>
          <option value="">Seleccioná una opción</option>
          <option value="verificada">Afiliación verificada en el padrón</option>
          <option value="pendiente">Declaración pendiente de verificación</option>
          <option value="particular">Atención particular</option>
        </Select>
      </Field>
      {tipo === "verificada" && (
        <>
          <Field label="Afiliación del paciente">
            <Select value={afiliado} required disabled={ocupado} onChange={(e) => setAfiliado(e.target.value)}>
              <option value="">Seleccioná una afiliación</option>
              {afiliados.map((item) => <option key={item.id} value={item.id}>{item.financiador_nombre} · {item.plan_nombre || "Sin plan"} · {item.numero}</option>)}
            </Select>
          </Field>
          {!afiliados.length && <p className="text-sm text-badge-amber-fg">No hay afiliaciones vigentes disponibles para este paciente con convenio activo. Podés registrar una declaración pendiente de verificación.</p>}
        </>
      )}
      {tipo === "pendiente" && <Field label="Afiliación declarada" ayuda="Obra social o mutual, plan y número que informa el paciente."><Input value={declaracion} required maxLength={160} disabled={ocupado} onChange={(e) => setDeclaracion(e.target.value)} /></Field>}
      {tipo && <Field label={esCorreccion ? "Motivo de la corrección" : "Motivo de la selección"}><Textarea value={motivo} required maxLength={255} disabled={ocupado} onChange={(e) => setMotivo(e.target.value)} /></Field>}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={ocupado || !valido}>{ocupado ? "Registrando…" : esCorreccion ? "Registrar corrección" : "Registrar afiliación"}</Button>
        {esCorreccion && <Button type="button" variant="ghost" disabled={ocupado} onClick={cancelar}>Cancelar</Button>}
      </div>
    </form>
  );
}

function PrestacionCaso({ prestacion, reservas, puedeOperar, conAfiliacion, exigeAceptacion, ocupado, operar }) {
  const [evaluacion, setEvaluacion] = useState(null);
  const [acepta, setAcepta] = useState(false);
  const [noRealizada, setNoRealizada] = useState(false);
  const [clave, setClave] = useState(null);
  const reservada = reservas.some((r) => r.estado === "reservada");
  const pendiente = evaluacion && ["pendiente_evaluacion", "arancel_pendiente"].includes(evaluacion.estado);
  const importePaciente = evaluacion?.importe_paciente;
  const tieneCopago = importePaciente != null && !/^0(?:\.0+)?$/.test(String(importePaciente));

  async function evaluar() {
    if (!puedeOperar || ocupado) return;
    setEvaluacion(null);
    setAcepta(false);
    setNoRealizada(false);
    setClave(null);
    const resultado = await operar("evaluar", { prestacion: prestacion.id });
    if (resultado) {
      setEvaluacion(resultado);
      setClave(crypto.randomUUID());
    }
  }

  async function confirmar() {
    if (!puedeOperar || !evaluacion || !clave || ocupado || (reservada && !noRealizada)) return;
    const resultado = await operar("confirmar", { prestacion: prestacion.id, firma: evaluacion.firma, clave, acepta, ...(reservada ? { no_realizada: noRealizada } : {}) }, "Cobertura confirmada. El consumo se registra al realizar la prestación.");
    if (resultado) { setEvaluacion(null); setAcepta(false); setNoRealizada(false); setClave(null); }
  }

  return (
    <div className="rounded-md border border-division p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="font-semibold">{prestacion.nombre}</h4>
          {reservada && <p className="mt-1 text-sm text-texto-debil">Tiene una reserva abierta. Podés revisar sus condiciones y renovar la aceptación.</p>}
        </div>
        {puedeOperar && <Button type="button" variant="secondary" size="sm" disabled={ocupado || !conAfiliacion} onClick={evaluar}>{evaluacion ? "Volver a evaluar" : reservada ? "Revisar importe" : "Consultar cobertura"}</Button>}
      </div>
      {puedeOperar && evaluacion && (
        <section aria-label={`Importe de ${prestacion.nombre}`} className="mt-4 space-y-3 border-t border-division pt-4">
          <p className="text-sm font-semibold">{evaluacion.motivo}</p>
          <p className="text-sm text-texto-debil">{fecha(evaluacion.fecha)} · {plural(evaluacion.cantidad, "unidad", "unidades")}. {evaluacion.cubiertas} cubiertas al {Number(evaluacion.porcentaje || 0).toLocaleString("es-AR")}%{evaluacion.cupo != null ? ` · Cupo ${evaluacion.periodo === "mes" ? "mensual" : "anual"}: ${evaluacion.cupo}; disponibles: ${evaluacion.disponibles ?? "—"}` : ""}.</p>
          <dl className="grid gap-3 rounded-md bg-superficie-2 p-4 sm:grid-cols-3">
            {[["Importe total", evaluacion.importe_total], ["A cargo del financiador", evaluacion.importe_financiador], ["A cargo del paciente", importePaciente]].map(([label, valor]) => <div key={label}><dt className="text-sm text-texto-debil">{label}</dt><dd className="mt-1 font-semibold">{importeARS(valor)}</dd></div>)}
          </dl>
          <AutorizacionEvaluacion evaluacion={evaluacion} />
          {pendiente ? <p className="text-sm text-badge-amber-fg">Faltan datos para confirmar la cobertura. La atención puede continuar y la resolución quedará pendiente en Finanzas.</p> : (
            <>
              {reservada && <>
                <Checkbox label="Confirmo que esta prestación todavía no se realizó" checked={noRealizada} disabled={ocupado} onChange={(e) => { setNoRealizada(e.target.checked); setClave(crypto.randomUUID()); }} />
              </>}
              {tieneCopago && <>
                {prestacion.puede_aceptar && <Checkbox label={`El paciente aceptó expresamente ${importeARS(importePaciente)} por ${prestacion.nombre} (${plural(evaluacion.cantidad, "unidad", "unidades")}).`} checked={acepta} disabled={ocupado} onChange={(e) => { setAcepta(e.target.checked); setClave(crypto.randomUUID()); }} />}
                {!prestacion.puede_aceptar && <p className="text-sm text-texto-debil">No tenés permiso para registrar la aceptación del paciente. Podés confirmar la cobertura sin aceptación.</p>}
                {!acepta && (exigeAceptacion
                  ? <p className="text-sm text-badge-amber-fg">Este paso exige la aceptación: sin registrarla no se puede avanzar. Si corresponde atender igual, pedí una continuación supervisada con motivo; una urgencia no queda bloqueada.</p>
                  : <p className="text-sm text-badge-amber-fg">Sin aceptación, este importe queda pendiente de resolución administrativa al realizar la prestación. No se asigna automáticamente como deuda al paciente.</p>)}
              </>}
              <div className="flex items-center gap-2">
                <Button type="button" disabled={ocupado || (reservada && !noRealizada)} onClick={confirmar}>{ocupado ? "Confirmando…" : reservada ? "Actualizar reserva de cobertura" : "Confirmar reserva de cobertura"}</Button>
                <Ayuda><span className="block">Consultar no ocupa cupo. Confirmar lo reserva hasta registrar la realización o verificar que no se realizó.</span>{reservada && <span className="mt-2 block">Actualizar reemplaza la reserva abierta y conserva su historial. La aceptación anterior no se reutiliza.</span>}</Ayuda>
              </div>
            </>
          )}
        </section>
      )}
    </div>
  );
}

function RegistrosPrestacion({ reservas }) {
  return (
    <details aria-label="Coberturas registradas" open={reservas.length <= 3} className="border-t border-division pt-5">
      <summary className="cursor-pointer font-semibold">Coberturas registradas · {reservas.length}</summary>
      <ul className="mt-3 space-y-3">
        {reservas.map((reserva) => (
          <li key={reserva.id} className="space-y-2 rounded-md border border-division p-4 text-sm">
            <div className="flex flex-wrap items-start justify-between gap-2"><p className="font-semibold">{reserva.prestacion_nombre || reserva.evaluacion?.nombre_prestacion}</p><Badge tone={tono(reserva.estado)}>{ESTADOS[reserva.estado] || reserva.estado}</Badge></div>
            <p className="text-texto-debil">{fecha(reserva.fecha)} · {plural(reserva.cantidad, "unidad", "unidades")}</p>
            <p>Financiador: {importeARS(reserva.evaluacion?.importe_financiador)} · Paciente: {importeARS(reserva.evaluacion?.importe_paciente)}</p>
            {reserva.evaluacion?.requiere_autorizacion && <p className="text-texto-debil">Autorización al evaluar: {ESTADOS_EVALUACION_AUTORIZACION[reserva.evaluacion.estado_autorizacion] || "Pendiente de verificar"}. Esta evaluación se conserva como antecedente.</p>}
            {reserva.uso_autorizacion && <p className="font-semibold">Uso actual de autorización {reserva.uso_autorizacion.solicitud}: {({ comprometido: "Comprometido", consumido: "Consumido", liberado: "Liberado" })[reserva.uso_autorizacion.estado] || reserva.uso_autorizacion.estado} · {plural(reserva.uso_autorizacion.cantidad, "unidad", "unidades")}</p>}
            {reserva.aceptacion?.importe != null ? <p className="text-texto-debil">Aceptación registrada: {importeARS(reserva.aceptacion.importe)} · {fechaHora(reserva.aceptacion.fecha)}</p> : <p className="text-texto-debil">Sin aceptación registrada del paciente.</p>}
            {reserva.distribucion && <p className="font-semibold">{reserva.distribucion.estado === "pendiente" ? "Saldo pendiente de resolución administrativa" : ESTADOS[reserva.distribucion.estado] || reserva.distribucion.estado}</p>}
            {reserva.discrepancia && <p className="text-badge-amber-fg">Discrepancia detectada. Se conserva lo registrado y queda disponible para revisión en Finanzas.</p>}
          </li>
        ))}
      </ul>
    </details>
  );
}
