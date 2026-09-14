import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { opcionesFinanzas } from "@/api/finanzas";
import { Button, Checkbox, ConfirmDialog, Field, Modal, Select, Spinner } from "@/components/ui";
import { EstadoError } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";

// Refleja las acciones ya expuestas por ConcesionFinanciera. El servidor
// valida de nuevo rol, institución, áreas y sensibilidad en cada escritura.
const ACCIONES = [
  ["ver_costos", "Ver costos", false],
  ["ver_gastos", "Ver gastos", false],
  ["registrar_gastos", "Registrar gastos", false],
  ["configurar_componentes", "Configurar componentes", true],
  ["corregir_costos", "Corregir costos", true],
  ["aprobar_gastos", "Aprobar gastos", true],
  ["corregir_gastos", "Corregir gastos", true],
  ["configurar_gastos_esperados", "Configurar gastos esperados", true],
  ["auditar_finanzas", "Auditar accesos financieros", true],
  ["configurar_repartos", "Configurar repartos", true],
];
const nombreAccion = (accion) => ACCIONES.find(([valor]) => valor === accion)?.[1] || accion;

export default function ConcesionesFinancieras({ institucion, usuarioId, onClose }) {
  const qc = useQueryClient();
  const toast = useToast();
  const enCurso = useRef(false);
  const [membresiaId, setMembresiaId] = useState("");
  const [form, setForm] = useState(null);
  const [revocar, setRevocar] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const [incierto, setIncierto] = useState(false);
  const [error, setError] = useState("");
  const listadoRef = useRef(null);
  const formularioRef = useRef(null);
  const posicionLista = useRef(0);
  useEffect(() => {
    if (form) {
      formularioRef.current?.focus();
      formularioRef.current?.closest('[role="dialog"]')?.scrollTo({ top: 0 });
    } else if (listadoRef.current) listadoRef.current.scrollTop = posicionLista.current;
  }, [form?.id, Boolean(form)]);
  const opciones = (recurso, filtros = {}) => ({
    queryKey: ["finanzas", usuarioId, institucion.id, "administrar-permisos", recurso, filtros],
    queryFn: () => opcionesFinanzas(recurso, institucion.id, filtros), gcTime: 0,
  });
  const miembros = useQuery(opciones("membresias"));
  const areas = useQuery(opciones("areas"));
  const concesiones = useQuery({ ...opciones("concesiones-financieras", { membresia: membresiaId }), enabled: Boolean(membresiaId) });
  const miembro = (miembros.data || []).find((m) => String(m.id) === membresiaId);
  const administrativa = miembro?.rol === "admin";
  const cargando = miembros.isFetching || areas.isFetching || (membresiaId && concesiones.isFetching);
  const errorConsulta = miembros.error || areas.error || concesiones.error;
  const puedeGuardar = miembro?.activo && !cargando && !errorConsulta && !guardando && !incierto;
  const set = (campo, valor) => setForm((anterior) => ({ ...anterior, [campo]: valor }));
  const close = () => { if (!enCurso.current) onClose(); };
  const nombreArea = (id) => (areas.data || []).find((a) => a.id === id)?.nombre || `Área #${id}`;
  const alcance = (c) => c.todas_las_areas ? "Todas las áreas e institucional" : c.areas.map(nombreArea).join(", ");

  async function refrescar() {
    await qc.invalidateQueries({ queryKey: ["permisos-finanzas"] });
    await qc.invalidateQueries({ queryKey: ["finanzas"] });
  }

  async function ejecutar(operacion) {
    if (enCurso.current || incierto) return;
    enCurso.current = true;
    setGuardando(true);
    setError("");
    try {
      await operacion();
      setForm(null);
      setRevocar(null);
      await refrescar();
      toast.ok("Permiso financiero actualizado.");
    } catch (err) {
      const sinConfirmacion = !err.status || err.status >= 500;
      setIncierto(sinConfirmacion);
      setError(sinConfirmacion
        ? "No se pudo confirmar el cambio. Cerrá y volvé a consultar los permisos antes de repetirlo."
        : (typeof err.data === "object" ? Object.values(err.data || {}).flat().join(" · ") : err.message));
      setRevocar(null);
    } finally {
      enCurso.current = false;
      setGuardando(false);
    }
  }

  function guardar(e) {
    e.preventDefault();
    if (!puedeGuardar || !(form.id ? form.accion : form.acciones.length)) return;
    if (!form.todas_las_areas && !form.areas.length) {
      setError("Elegí al menos un área o el alcance institucional explícito.");
      return;
    }
    const datos = { membresia: miembro.id, accion: form.accion, todas_las_areas: form.todas_las_areas,
      areas: form.todas_las_areas ? [] : form.areas, permite_sensibles: form.permite_sensibles };
    ejecutar(() => form.id ? api.patch(`/concesiones-financieras/${form.id}/`, datos) : api.post("/concesiones-financieras/otorgar-multiples/", { ...datos, accion: undefined, acciones: form.acciones }));
  }

  return <Modal title="Permisos financieros" onClose={close} width={760}>
    <div className="space-y-4">
      <p className="text-md text-texto-debil">{institucion.nombre} · Elegí qué puede hacer esta persona y en qué áreas. Registrar no concede lectura.</p>
      {miembros.isLoading || areas.isLoading ? <Spinner label="Consultando miembros y áreas…" /> : <Field label="Persona y membresía">
        <Select value={membresiaId} disabled={guardando || incierto || Boolean(form)} onChange={(e) => { setMembresiaId(e.target.value); setForm(null); setError(""); }}>
          <option value="">Elegí una membresía</option>
          {(miembros.data || []).map((m) => <option key={m.id} value={m.id}>{m.usuario_nombre || m.usuario_email} · {m.rol_display || m.rol}{m.activo ? "" : " · Inactiva"}</option>)}
        </Select>
      </Field>}
      {errorConsulta && <EstadoError error={errorConsulta} onReintentar={refrescar} />}
      {miembro && !miembro.activo && <p className="text-md text-texto-debil">Membresía inactiva: sus concesiones no otorgan acceso. Podés revocarlas, pero no ampliarlas desde esta pantalla.</p>}
      {miembro && administrativa && <p className="text-md text-texto-debil">El administrador tiene lectura de costos y gastos, incluidos los sensibles, en toda esta institución por su rol. Las demás acciones requieren permiso explícito.</p>}
      {miembro && !errorConsulta && !form && <>
        {concesiones.isLoading ? <Spinner label="Consultando concesiones…" /> : <div ref={listadoRef} onScroll={(e) => { posicionLista.current = e.currentTarget.scrollTop; }} className="max-h-[45vh] space-y-3 overflow-y-auto">
          {!concesiones.data?.length && <p className="text-md text-texto-debil">Sin concesiones financieras registradas.</p>}
          {(concesiones.data || []).map((c) => <div key={c.id} className="rounded-md border border-borde p-3">
            <strong className="text-md">{nombreAccion(c.accion)}</strong>
            <p className="text-md text-texto-debil">{alcance(c)} · {c.permite_sensibles ? "Incluye sensibles" : "Sin sensibles"}</p>
            <div className="mt-2 flex gap-2">
              <Button size="sm" variant="secondary" disabled={!puedeGuardar} onClick={() => { setForm({ ...c }); setError(""); }}>Editar alcance</Button>
              <Button size="sm" variant="ghost" disabled={guardando || incierto || cargando} onClick={() => setRevocar(c)}>Revocar</Button>
            </div>
          </div>)}
        </div>}
        <Button variant="secondary" disabled={!puedeGuardar} onClick={() => { setForm({ acciones: [], areas: [], todas_las_areas: false, permite_sensibles: false }); setError(""); }}>Otorgar permisos</Button>
      </>}
      {form && miembro && <form onSubmit={guardar} className="space-y-4 border-t border-division pt-4">
        <h3 ref={formularioRef} tabIndex={-1} className="font-semibold outline-none">{form.id ? "Editar alcance del permiso" : "Nueva concesión explícita"}</h3>
        <fieldset disabled={!puedeGuardar} className="space-y-3">
          {form.id ? <p className="font-semibold">{nombreAccion(form.accion)}</p> : <fieldset className="grid gap-2 sm:grid-cols-2"><legend className="mb-2 font-semibold">Acciones financieras</legend>
            {ACCIONES.map(([valor, nombre]) => { const existente = concesiones.data?.some((c) => c.accion === valor); return <Checkbox key={valor} className={existente ? "cursor-not-allowed text-texto-debil opacity-50 [&_input]:cursor-not-allowed" : undefined} title={existente ? "Este permiso ya existe. Usá Editar alcance para modificarlo." : undefined} label={`${nombre}${existente ? " · Ya otorgado" : ""}`} disabled={existente} checked={form.acciones.includes(valor)} onChange={(e) => set("acciones", e.target.checked ? [...form.acciones, valor] : form.acciones.filter((a) => a !== valor))} />; })}
          </fieldset>}
          <Checkbox label="Todas las áreas e institucional (sin área asignada)" checked={form.todas_las_areas} onChange={(e) => { set("todas_las_areas", e.target.checked); set("areas", []); }} />
          {!form.todas_las_areas && <fieldset className="space-y-2"><legend className="mb-2 text-md font-semibold">Áreas autorizadas</legend>
            {(areas.data || []).map((a) => <Checkbox key={a.id} label={a.nombre} checked={form.areas.includes(a.id)} onChange={(e) => set("areas", e.target.checked ? [...form.areas, a.id] : form.areas.filter((id) => id !== a.id))} />)}
          </fieldset>}
          <Checkbox label="Permitir información sensible para las acciones y áreas seleccionadas" checked={form.permite_sensibles} onChange={(e) => set("permite_sensibles", e.target.checked)} />
        </fieldset>
        <p className="text-md text-texto-debil">Confirmás {form.id ? nombreAccion(form.accion) : form.acciones.map(nombreAccion).join(", ") || "ninguna acción seleccionada"} para {miembro.usuario_nombre || miembro.usuario_email}: {form.todas_las_areas || form.areas.length ? alcance(form) : "falta elegir alcance"} · {form.permite_sensibles ? "incluye sensibles" : "sin sensibles"}. Los permisos existentes no se amplían.</p>
        <div className="sticky bottom-0 flex justify-end gap-2 border-t border-division bg-superficie py-3">
          <Button type="button" variant="ghost" disabled={guardando} onClick={() => setForm(null)}>Cancelar edición</Button>
          <Button type="submit" disabled={!puedeGuardar}>{guardando ? "Guardando…" : "Confirmar permiso"}</Button>
        </div>
      </form>}
      {error && <p role="alert" className="text-md text-danger">{error}</p>}
      {revocar && <ConfirmDialog title="¿Revocar el permiso financiero?" confirmar="Revocar permiso" peligroso cargando={guardando}
        onClose={() => { if (!enCurso.current) setRevocar(null); }} onConfirmar={() => ejecutar(() => api.del(`/concesiones-financieras/${revocar.id}/`))}>
        Se quita {nombreAccion(revocar.accion)} a {miembro.usuario_nombre || miembro.usuario_email} en {institucion.nombre}: {alcance(revocar)}. Otras concesiones pueden seguir habilitando acceso. No se borran gastos, costos ni auditorías.
      </ConfirmDialog>}
    </div>
  </Modal>;
}
