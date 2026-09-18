import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { opcionesFinanzas } from "@/api/finanzas";
import { Ayuda, Button, Checkbox, Field, Select, Spinner } from "@/components/ui";
import { EstadoError } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";

const ACCIONES = [
  ["ver_costos", "Ver costos"], ["ver_gastos", "Ver gastos"],
  ["registrar_gastos", "Registrar gastos"], ["configurar_componentes", "Configurar componentes"],
  ["corregir_costos", "Corregir costos"], ["aprobar_gastos", "Aprobar gastos"],
  ["corregir_gastos", "Corregir gastos"], ["configurar_gastos_esperados", "Configurar gastos mensuales"],
  ["auditar_finanzas", "Auditar accesos financieros"], ["configurar_repartos", "Configurar repartos"],
  ["ver_dinero", "Ver pagos y cobros"], ["registrar_dinero", "Registrar pagos y cobros"],
  ["corregir_dinero", "Registrar devoluciones y reducciones"], ["configurar_cobros", "Configurar cobros por atención"],
  ["aprobar_dinero", "Aprobar pagos, cobros y sus correcciones"], ["aprobar_costos", "Aprobar ajustes de costos"],
  ["registrar_aceptacion", "Registrar aceptación de copagos por prestación"],
  ["resolver_cobertura", "Resolver saldos de cobertura con motivo"],
];
const formularioDe = (concesiones) => Object.fromEntries(ACCIONES.map(([accion]) => {
  const actual = concesiones.find((fila) => fila.accion === accion);
  return [accion, actual ? { ...actual, areas: [...actual.areas], otorgado: true }
    : { accion, areas: [], todas_las_areas: false, permite_sensibles: false, otorgado: false }];
}));
const payloadDe = (form) => ACCIONES.map(([accion]) => form[accion]).filter((fila) => fila.otorgado)
  .map(({ accion, todas_las_areas, permite_sensibles, areas }) => ({ accion, todas_las_areas, permite_sensibles, areas }));

/** Personal administrativo: acciones visibles, alcance avanzado por acción.
 * Mantiene tipografía, bordes sutiles, superficies y escala de espacios del sistema.
 */
export function EditorPermisosFinancieros({ institucion, usuarioId, membresias, onBusyChange, plegable = false }) {
  const [seleccion, setSeleccion] = useState("");
  const locales = membresias.filter((m) => m.institucion === institucion.id);
  const miembro = locales.find((m) => String(m.id) === seleccion) || locales[0];
  const [guardando, setGuardando] = useState(false);
  const estadoOcupado = (valor) => { setGuardando(valor); onBusyChange?.(valor); };
  const Contenedor = plegable ? "details" : "div";
  return <section aria-label="Permisos financieros" className="space-y-3 border-t border-division pt-3.5">
    <Contenedor className="space-y-3">
    {plegable ? <summary className="cursor-pointer rounded-md text-base font-bold text-texto-suave focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">Permisos financieros</summary>
      : <h3 className="text-base font-bold text-texto-suave">Permisos financieros</h3>}
    <p className="text-md text-texto-debil">{institucion.nombre}. Se guardan aparte de los datos personales. No modifican los permisos clínicos ni las otras membresías.</p>
    {locales.length > 1 && <Field label="Membresía de los permisos financieros">
      <Select value={miembro?.id || ""} disabled={guardando} onChange={(e) => setSeleccion(e.target.value)}>
        {locales.map((m) => <option key={m.id} value={m.id}>{m.rol_display || m.rol}{m.activo ? "" : " · Inactiva"}</option>)}
      </Select>
    </Field>}
    {miembro ? <ChecklistMembresia key={`${usuarioId}:${institucion.id}:${miembro.id}`} institucion={institucion}
      usuarioId={usuarioId} miembro={miembro} onBusyChange={estadoOcupado} />
      : <p className="text-md text-texto-debil">Agregá una membresía en esta institución para administrar sus permisos financieros.</p>}
    </Contenedor>
  </section>;
}

function ChecklistMembresia({ institucion, usuarioId, miembro, onBusyChange }) {
  const qc = useQueryClient();
  const toast = useToast();
  const enCurso = useRef(false);
  const [base, setBase] = useState(null);
  const [form, setForm] = useState(null);
  const [abiertos, setAbiertos] = useState({});
  const [guardando, setGuardando] = useState(false);
  const [bloqueado, setBloqueado] = useState(false);
  const [error, setError] = useState("");
  const grilla = useRef(null);
  const [columnas, setColumnas] = useState(1);
  const queryKey = ["editor-permisos", usuarioId, institucion.id, miembro.id];
  const consulta = useQuery({ queryKey,
    queryFn: () => api.get(`/concesiones-financieras/editar-membresia/?membresia=${miembro.id}`),
    gcTime: 0, retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false,
  });
  const areas = useQuery({ queryKey: ["editor-permisos-areas", usuarioId, institucion.id],
    queryFn: () => opcionesFinanzas("areas", institucion.id), gcTime: 0, retry: false,
  });
  const aplicar = (estado) => { setBase(estado); setForm(formularioDe(estado.concesiones)); };
  useEffect(() => { if (consulta.data && !base) aplicar(consulta.data); }, [consulta.data, base]);
  const errorConsulta = consulta.error || areas.error;
  const editorListo = Boolean(form && base && !areas.isLoading && !errorConsulta);
  useEffect(() => {
    if (!editorListo || !grilla.current) return;
    const observer = new ResizeObserver(([entrada]) => {
      setColumnas(Math.max(1, Math.min(3, Math.floor((entrada.contentRect.width + 8) / 288))));
    });
    observer.observe(grilla.current);
    return () => observer.disconnect();
  }, [editorListo]);
  const cargando = consulta.isFetching || areas.isFetching;
  const deshabilitado = guardando || bloqueado || cargando || Boolean(errorConsulta);
  const cambio = form && base && JSON.stringify(payloadDe(form)) !== JSON.stringify(payloadDe(formularioDe(base.concesiones)));
  const set = (accion, campo, valor) => setForm((anterior) => ({ ...anterior, [accion]: { ...anterior[accion], [campo]: valor } }));
  const alcance = (fila) => `${fila.todas_las_areas ? "Todas las áreas e institucional" : fila.areas.length
    ? fila.areas.map((id) => areas.data?.find((area) => area.id === id)?.nombre || `Área #${id}`).join(", ")
    : "Elegí un alcance"} · ${fila.permite_sensibles ? "incluye sensibles" : "sin sensibles"}`;

  async function recargar() {
    if (enCurso.current) return;
    const [resultado, resultadoAreas] = await Promise.all([consulta.refetch(), areas.refetch()]);
    if (resultado.data && !resultado.error && !resultadoAreas.error) {
      aplicar(resultado.data); setError(""); setBloqueado(false); setAbiertos({});
    }
  }

  async function guardar() {
    if (enCurso.current || deshabilitado || !cambio) return;
    const concesiones = payloadDe(form);
    if (concesiones.some((fila) => !fila.todas_las_areas && !fila.areas.length)) {
      setError("Elegí al menos un área o el alcance institucional para cada acción marcada.");
      return;
    }
    enCurso.current = true; setGuardando(true); onBusyChange?.(true); setError("");
    try {
      const resultado = await api.put("/concesiones-financieras/editar-membresia/", {
        membresia: miembro.id, version_esperada: base.version_esperada, concesiones,
      });
      aplicar(resultado); qc.setQueryData(queryKey, resultado);
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["permisos-finanzas"] }),
        qc.invalidateQueries({ queryKey: ["finanzas"] }),
      ]);
      toast.ok("Permisos financieros guardados.");
    } catch (err) {
      const incierto = !err.status || err.status >= 500;
      setBloqueado(incierto || err.status === 409);
      setError(incierto ? "No se pudo confirmar el guardado. Volvé a consultar los permisos antes de repetirlo."
        : err.status === 409 ? "Los permisos cambiaron mientras editabas. Volvé a consultarlos; no se aplicaron tus cambios."
          : typeof err.data === "object" ? Object.values(err.data || {}).flat().join(" · ") : err.message);
    } finally {
      enCurso.current = false; setGuardando(false); onBusyChange?.(false);
    }
  }

  if (errorConsulta) return <EstadoError error={errorConsulta} onReintentar={recargar} />;
  if (!form || !base || areas.isLoading) return <Spinner label="Consultando permisos financieros…" />;
  return <div className="space-y-3">
    {!base.activo && <p className="text-md text-texto-debil">Membresía inactiva: sus concesiones no otorgan acceso. Sólo podés conservarlas o revocarlas.</p>}
    <fieldset ref={grilla} disabled={deshabilitado} className="grid min-w-0 items-start gap-2" style={{ gridTemplateColumns: `repeat(${columnas}, minmax(0, 1fr))` }}>
      <legend className="sr-only">Acciones financieras de esta membresía</legend>
      {base.heredadas.length > 0 && <div className="flex items-center gap-2 text-sm font-semibold text-texto-debil" style={{ gridColumn: "1 / -1" }}>Lectura habilitada por rol<Ayuda>La lectura de costos y gastos, incluidos los sensibles, está habilitada en toda la institución por el rol administrador. No se revoca con estas casillas.</Ayuda></div>}
      {/* Pilas independientes: un alcance sólo desplaza su propia columna. */}
      {Array.from({ length: columnas }, (_, columna) => <div key={columna} className="min-w-0 space-y-2">
      {ACCIONES.filter((_, indice) => indice % columnas === columna).map(([accion, nombre]) => {
        const fila = form[accion];
        const heredada = base.heredadas.includes(accion);
        const existia = base.concesiones.some((c) => c.accion === accion);
        const otras = base.otras_membresias.filter((c) => c.accion === accion);
        return <div key={accion} className="min-w-0 break-words rounded-md border border-division px-3 py-2">
          <Checkbox label={nombre} checked={heredada || fila.otorgado}
            disabled={heredada || (!base.activo && !fila.otorgado && !existia)}
            onChange={(e) => { set(accion, "otorgado", e.target.checked); if (e.target.checked && !existia) setAbiertos((actual) => ({ ...actual, [accion]: true })); }} />
          {heredada && <span className="ml-6 text-sm font-semibold text-texto-debil">Por rol · no revocable aquí</span>}
          {!heredada && fila.otorgado && <p className="ml-6 text-sm text-texto-debil">{alcance(fila)}</p>}
          {otras.length > 0 && <div className="ml-6 flex items-center gap-1.5"><p className="text-sm text-texto-debil">En otra membresía</p><Ayuda>También hay permisos de esta acción en otra membresía. Sus alcances no se modifican aquí.</Ayuda></div>}
          {(fila.otorgado || (heredada && existia)) && <details open={Boolean(abiertos[accion])}
            onToggle={(e) => { const open = e.currentTarget.open; setAbiertos((actual) => actual[accion] === open ? actual : { ...actual, [accion]: open }); }} className="ml-6 mt-1 text-sm">
            <summary className="cursor-pointer font-medium text-accent">Alcance de {nombre}</summary>
            <div className="space-y-2 pb-1 pt-2">
              {heredada && existia && <>
                <div className="flex items-center gap-2"><Checkbox label={`Conservar concesión explícita · ${nombre}`} checked={fila.otorgado}
                  onChange={(e) => set(accion, "otorgado", e.target.checked)} /><Ayuda>Esta concesión adicional se conserva al guardar. Si la quitás, la lectura por rol sigue vigente.</Ayuda></div>
              </>}
              {fila.otorgado && <fieldset disabled={!base.activo} className="space-y-2">
              <Checkbox label="Todas las áreas e institucional" checked={fila.todas_las_areas}
                  onChange={(e) => { set(accion, "todas_las_areas", e.target.checked); set(accion, "areas", []); }} />
                {!fila.todas_las_areas && <div className="space-y-2">
                  {(areas.data || []).map((area) => <Checkbox key={area.id} label={area.nombre}
                    checked={fila.areas.includes(area.id)} onChange={(e) => set(accion, "areas", e.target.checked ? [...fila.areas, area.id] : fila.areas.filter((id) => id !== area.id))} />)}
                </div>}
                <Checkbox label="Incluir información sensible" checked={fila.permite_sensibles}
                  onChange={(e) => set(accion, "permite_sensibles", e.target.checked)} />
              </fieldset>}
            </div>
          </details>}
        </div>;
      })}
      </div>)}
    </fieldset>
    {error && <p role="alert" className="text-md text-danger">{error}</p>}
    {bloqueado && <Button variant="secondary" disabled={guardando || cargando} onClick={recargar}>Volver a consultar permisos</Button>}
    <div className="flex flex-wrap items-center gap-2 border-t border-division pt-3">
      <Button disabled={deshabilitado || !cambio} onClick={guardar}>{guardando ? "Guardando permisos…" : "Guardar permisos financieros"}</Button>
      <span className="text-sm text-texto-debil">{cambio ? "Hay cambios sin guardar en estos permisos." : "Los permisos reflejan lo registrado."}</span>
    </div>
  </div>;
}
