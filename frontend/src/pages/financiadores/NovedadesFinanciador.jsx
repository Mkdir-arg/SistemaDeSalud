import { useState } from "react";
import { createPortal } from "react-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { errorFinanciador, filasDe, rutaFinanciador } from "@/api/financiadores";
import { Button, Card, Checkbox, Field, Input, Modal, Select, Spinner, Textarea } from "@/components/ui";

const ESTADOS = { pendiente: "Pendiente", conciliada: "Conciliada sin aplicación", descartada: "Descartada" };
const CONFLICTOS = { padron_modificado: "El padrón cambió desde el registro de la propuesta.", referencia_repetida: "La fuente y referencia coinciden con otra propuesta. No se eligió una ganadora." };
const AVISO = "Registrar o conciliar evidencia no modifica el padrón, la vigencia ni los derechos.";

function vacia() {
  return { clave: crypto.randomUUID(), afiliado: "", fuente: "", referencia: "", codigo: "",
    fecha_informada: "", descripcion: "", motivo: "", rectifica: null };
}

export default function NovedadesFinanciador({ organizacion, scope, operador }) {
  const qc = useQueryClient();
  const [estado, setEstado] = useState("");
  const [pagina, setPagina] = useState(1);
  const [seleccion, setSeleccion] = useState(null);
  const [formulario, setFormulario] = useState(null);
  const [personaInicial, setPersonaInicial] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);
  const [motivo, setMotivo] = useState("");
  const [confirmar, setConfirmar] = useState(false);
  const base = rutaFinanciador(organizacion.id, "novedades");
  const clave = [...scope, "novedades"];
  const listado = useQuery({ queryKey: [...clave, estado, pagina], gcTime: 0,
    queryFn: () => api.get(`${base}?estado=${estado}&page=${pagina}`) });
  const detalle = useQuery({ queryKey: [...clave, "detalle", seleccion], enabled: seleccion != null,
    gcTime: 0, queryFn: () => api.get(`${base}${seleccion}/`) });
  const novedad = detalle.data;

  function abrir(id) { setSeleccion(id); setMotivo(""); setConfirmar(false); setError(null); }
  function nueva(antecedente = null) {
    setPersonaInicial(antecedente?.persona_actual || null);
    setFormulario(antecedente ? { ...antecedente.original, clave: crypto.randomUUID(),
      rectifica: antecedente.id, motivo: "" } : vacia());
    setSeleccion(null); setError(null);
  }
  async function guardar(event) {
    event.preventDefault(); setOcupado(true); setError(null);
    try {
      const resultado = await api.post(base, { ...formulario, afiliado: Number(formulario.afiliado),
        fecha_informada: formulario.fecha_informada || null });
      qc.setQueryData([...clave, "detalle", resultado.id], resultado);
      setFormulario(null); abrir(resultado.id);
      await qc.invalidateQueries({ queryKey: clave });
    } catch (e) { setError(e); } finally { setOcupado(false); }
  }
  async function decidir(accion) {
    setOcupado(true); setError(null);
    try {
      const resultado = await api.post(`${base}${novedad.id}/resolver/`, {
        accion, motivo, revision: novedad.revision, revision_padron: novedad.persona_actual.revision,
        confirmar_conflictos: confirmar,
      });
      qc.setQueryData([...clave, "detalle", resultado.id], resultado);
      setMotivo(""); setConfirmar(false);
      await qc.invalidateQueries({ queryKey: clave });
    } catch (e) { setError(e); } finally { setOcupado(false); }
  }
  async function actualizar() {
    setConfirmar(false); setError(null);
    await detalle.refetch();
  }
  const cerrar = () => { setSeleccion(null); setError(null); };

  return <div className="space-y-4">
    <p role="note" className="rounded-lg border border-division bg-superficie-2 p-4 text-sm">{AVISO}</p>
    <details className="rounded-lg border border-division p-3 text-sm">
      <summary className="cursor-pointer font-semibold">Deuda OSTEL: efectos no habilitados</summary>
      <p className="mt-2">No se interpretan fechas o causales como cortes prestacionales, ni se aplican bajas, reingresos, gracia, mora o cambios de plan automáticamente. No se propagan efectos a familias, atención o dinero. Esas conductas requieren reglas validadas; no impiden revisar evidencia administrativa.</p>
    </details>
    <div className="flex flex-wrap items-end justify-between gap-3">
      <Field label="Estado de la novedad"><Select value={estado} onChange={(e) => { setEstado(e.target.value); setPagina(1); }}>
        <option value="">Todos</option>{Object.entries(ESTADOS).map(([valor, etiqueta]) => <option key={valor} value={valor}>{etiqueta}</option>)}
      </Select></Field>
      {operador && <Button onClick={() => nueva()}>Registrar novedad</Button>}
    </div>
    {listado.isPending ? <Spinner /> : listado.error ? <p role="alert">{errorFinanciador(listado.error)} <Button variant="secondary" onClick={() => listado.refetch()}>Reintentar</Button></p> : <>
      {!filasDe(listado.data).length && <Card><p className="text-sm text-texto-suave">No hay novedades en este estado.</p></Card>}
      <ul aria-label="Novedades registradas" className="space-y-3">{filasDe(listado.data).map((item) => <li key={item.id}>
        <Card><div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0 flex-1 break-words"><p className="font-semibold">{item.original.fuente} · {item.original.referencia || "Sin referencia externa"}</p>
            <p className="mt-1 text-sm text-texto-suave">#{item.id} · {ESTADOS[item.estado]} · {item.original.codigo || "Sin código informado"}</p></div>
          <Button variant="secondary" onClick={() => abrir(item.id)} aria-label={`Ver novedad ${item.id}`}>Ver detalle</Button>
        </div></Card>
      </li>)}</ul>
      <nav aria-label="Paginación de novedades" className="flex items-center justify-between gap-3">
        <Button variant="secondary" disabled={!listado.data?.previous} onClick={() => setPagina((n) => n - 1)}>Anterior</Button>
        <span className="text-sm">Página {pagina} · {listado.data?.count || 0} novedades</span>
        <Button variant="secondary" disabled={!listado.data?.next} onClick={() => setPagina((n) => n + 1)}>Siguiente</Button>
      </nav>
    </>}
    {formulario && operador && createPortal(<FormularioNovedad formulario={formulario} cambiar={setFormulario}
      personaInicial={personaInicial} basePadron={rutaFinanciador(organizacion.id, "padron")}
      scope={scope} ocupado={ocupado} error={error} guardar={guardar} cerrar={() => setFormulario(null)} />, document.body)}
    {seleccion != null && createPortal(<Modal title={`Novedad #${seleccion}`} width={860}
      onClose={ocupado ? undefined : cerrar} footer={<Button variant="secondary" disabled={ocupado} onClick={cerrar}>Cerrar</Button>}>
      {detalle.isPending ? <Spinner /> : detalle.error ? <p role="alert">{errorFinanciador(detalle.error)} <Button onClick={actualizar}>Reintentar</Button></p> : novedad && <div className="space-y-4">
        <p className="font-semibold">{ESTADOS[novedad.estado]}</p><p className="text-sm">{AVISO}</p>
        <section aria-label="Evidencia original" className="rounded-lg border border-division p-4">
          <h2 className="mb-2 font-semibold">Evidencia original</h2>
          <dl className="grid gap-2 text-sm sm:grid-cols-2">{[["Fuente", novedad.original.fuente], ["Referencia", novedad.original.referencia],
            ["Código informado", novedad.original.codigo], ["Fecha informada (sin efecto automático)", novedad.original.fecha_informada],
            ["Rectifica propuesta", novedad.original.rectifica]].map(([etiqueta, valor]) => <div key={etiqueta} className="min-w-0 break-words"><dt className="text-texto-suave">{etiqueta}</dt><dd>{valor || "Sin informar"}</dd></div>)}</dl>
          <p className="mt-3 whitespace-pre-wrap break-words text-sm">{novedad.original.descripcion}</p>
        </section>
        <div className="grid gap-3 sm:grid-cols-2">{[["Al registrar", novedad.persona_inicial], ["Padrón actual", novedad.persona_actual]].map(([titulo, persona]) => <section key={titulo} className="rounded-lg bg-superficie-2 p-3 text-sm">
          <h2 className="font-semibold">{titulo}</h2><p>{persona.nombre}</p><p>Documento: {persona.documento}</p><p>Revisión: {persona.revision} · {persona.finalizada ? "Afiliación finalizada" : "Afiliación no finalizada"}</p>
        </section>)}</div>
        {novedad.conflictos.length > 0 && <div role="status" className="rounded-lg bg-badge-amber-bg p-3 text-sm text-badge-amber-fg">
          <h2 className="font-semibold">Revisión de conflictos</h2><ul className="mt-2 list-inside list-disc">{novedad.conflictos.map((c) => <li key={c}>{CONFLICTOS[c] || c}</li>)}</ul>
          {novedad.coincidencias.length > 0 && <p>Propuestas relacionadas: {novedad.coincidencias.map((id) => `#${id}`).join(", ")}</p>}
        </div>}
        <section aria-label="Historial de la propuesta"><h2 className="font-semibold">Historial de decisiones</h2>
          <ol className="mt-2 space-y-2">{novedad.historia.map((h, i) => <li key={i} className="rounded-lg border border-division p-3 text-sm">
            <p className="font-semibold">{h.accion === "registrar" ? "Registro" : h.accion === "conciliar" ? "Conciliación sin aplicación" : "Descarte"} · Usuario {h.usuario}</p>
            <p className="text-texto-suave">{new Date(h.fecha).toLocaleString("es-AR")}</p><p className="mt-1 whitespace-pre-wrap break-words">{h.motivo}</p>
          </li>)}</ol>
        </section>
        {error && <p role="alert" className="text-badge-error-fg">{errorFinanciador(error)}</p>}
        {operador && novedad.estado === "pendiente" && <section className="space-y-3 border-t border-division pt-4">
          <Field label="Motivo de la decisión"><Textarea value={motivo} maxLength={255} disabled={ocupado} onChange={(e) => setMotivo(e.target.value)} /></Field>
          {novedad.conflictos.length > 0 && <Checkbox label="Revisé expresamente los conflictos y coincidencias indicados" checked={confirmar} disabled={ocupado} onChange={(e) => setConfirmar(e.target.checked)} />}
          <div className="flex flex-wrap gap-2"><Button disabled={ocupado || !motivo.trim() || novedad.conflictos.length > 0 && !confirmar} onClick={() => decidir("conciliar")}>Conciliar sin aplicar efectos</Button>
            <Button variant="secondary" disabled={ocupado || !motivo.trim()} onClick={() => decidir("descartar")}>Descartar propuesta</Button>
            <Button variant="ghost" disabled={ocupado} onClick={actualizar}>Actualizar comparación</Button></div>
        </section>}
        {operador && <Button variant="secondary" disabled={ocupado} onClick={() => nueva(novedad)}>Registrar rectificación</Button>}
      </div>}
    </Modal>, document.body)}
  </div>;
}

function FormularioNovedad({ formulario, cambiar, personaInicial, basePadron, scope, ocupado, error, guardar, cerrar }) {
  const [busqueda, setBusqueda] = useState(personaInicial?.documento || "");
  const personas = useQuery({ queryKey: [...scope, "novedades-personas", busqueda],
    enabled: busqueda.trim().length >= 2, gcTime: 0,
    queryFn: () => api.get(`${basePadron}?search=${encodeURIComponent(busqueda.trim())}&page_size=20`) });
  const opciones = [...filasDe(personas.data)];
  if (personaInicial && !opciones.some((p) => p.id === personaInicial.id)) opciones.unshift(personaInicial);
  const campo = (nombre) => ({ value: formulario[nombre] ?? "", disabled: ocupado,
    onChange: (e) => cambiar({ ...formulario, [nombre]: e.target.value }) });
  return <Modal title={formulario.rectifica ? `Rectificar novedad #${formulario.rectifica}` : "Registrar novedad"} width={760}
    onClose={ocupado ? undefined : cerrar} footer={<><Button variant="secondary" disabled={ocupado} onClick={cerrar}>Cancelar</Button><Button type="submit" form="formulario-novedad" disabled={ocupado}>Guardar propuesta</Button></>}>
    <form id="formulario-novedad" onSubmit={guardar} className="space-y-4">
      <p className="text-sm">{AVISO} Los datos originales se conservan; una rectificación crea otra propuesta.</p>
      {error && <p role="alert" className="text-badge-error-fg">{errorFinanciador(error)}</p>}
      <Field label="Buscar persona por documento o nombre"><Input value={busqueda} maxLength={160} disabled={ocupado || formulario.rectifica != null} onChange={(e) => setBusqueda(e.target.value)} /></Field>
      {personas.error && <p role="alert">{errorFinanciador(personas.error)}</p>}
      <Field label="Persona del padrón"><Select {...campo("afiliado")} required disabled={ocupado || formulario.rectifica != null}>
        <option value="">Seleccionar persona</option>{opciones.map((p) => <option key={p.id} value={p.id}>{p.documento} · {p.nombre}</option>)}
      </Select></Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Fuente"><Input {...campo("fuente")} maxLength={80} required /></Field>
        <Field label="Referencia externa"><Input {...campo("referencia")} maxLength={120} /></Field>
        <Field label="Código informado"><Input {...campo("codigo")} maxLength={80} /></Field>
        <Field label="Fecha informada"><Input {...campo("fecha_informada")} type="date" /></Field>
      </div>
      <Field label="Descripción administrativa" hint="No incluir datos clínicos ni interpretar esta evidencia como una orden de baja o reingreso."><Textarea {...campo("descripcion")} maxLength={2000} required /></Field>
      <Field label="Motivo del registro"><Textarea {...campo("motivo")} maxLength={255} required /></Field>
    </form>
  </Modal>;
}
