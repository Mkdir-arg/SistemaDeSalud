import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import { errorFinanciador, opcionesFinanciador, rutaFinanciador } from "@/api/financiadores";
import { Badge, Button, Card, Spinner } from "@/components/ui";
import FormularioPadron from "./FormularioPadron";
import FamiliaPadron from "./FamiliaPadron";
import LegajoPadron from "./LegajoPadron";
import HistorialPadron from "./HistorialPadron";
import RecursoProtegidoPadron from "./RecursoProtegidoPadron";
import TarjetaFicha, { DatosFicha } from "./TarjetaFicha";
import { derechoAfiliacionPadron } from "./padronTablaEstado";
import { ADMINISTRATIVOS, BLOQUES_PADRON, TIPOS_PLAN } from "./padronCampos";

const ICONOS = { Identidad: "idCard", Contacto: "bell", Domicilio: "mapPin", "Régimen y trabajo": "building", "Trámite y credencial": "clipboard", "Baja administrativa": "power" };

// `vista` reparte la ficha en las pestañas de la página; sin `vista` (diálogo de
// edición del padrón) se muestra completa.
export default function FichaPadronAdministrativa({ afiliado, organizacion, usuarioId, parametros, plataforma, integrado = false, onOcupado, vista }) {
  const ver = (parte) => !vista || vista === parte;
  const [edicion, setEdicion] = useState(null);
  const [recursoActivo, setRecursoActivo] = useState(null);
  const activo = integrado && (edicion ? "administracion" : recursoActivo);
  const qc = useQueryClient();
  const scope = ["financiadores", usuarioId, organizacion.id];
  const ruta = `${rutaFinanciador(organizacion.id, "padron")}${afiliado}/`;
  const ficha = useQuery({ queryKey: [...scope, "padron-detalle", afiliado], queryFn: () => api.get(ruta), gcTime: 0, retry: false });
  const planes = useQuery({ queryKey: [...scope, "opciones-planes"], queryFn: () => opcionesFinanciador(organizacion.id, "planes"), enabled: edicion?.titulo === "Plan de cobertura", gcTime: 0, retry: false });
  const puedeEditar = organizacion.rol === "admin" || organizacion.rol === "operador" || plataforma && organizacion.rol !== "auditor";
  async function actualizado() {
    await Promise.all([
      qc.invalidateQueries({ queryKey: scope }),
      qc.invalidateQueries({ queryKey: ["financiador", usuarioId, organizacion.id] }),
    ]);
  }
  if (ficha.isLoading) return <Spinner label="Consultando ficha administrativa…" />;
  if (ficha.error) return <Card className="p-4"><p role="alert">{errorFinanciador(ficha.error)}</p><Button variant="secondary" onClick={() => ficha.refetch()}>Reintentar ficha administrativa</Button></Card>;
  const persona = ficha.data;
  const permisos = persona.permisos || {};
  const camposPlan = [{ name: "plan", label: "Plan", numeric: true, options: (planes.data || []).filter((plan) => plan.activo !== false || plan.id === persona.plan).map((plan) => ({ id: plan.id, nombre: `${plan.nombre}${plan.activo === false ? " (inactivo actual)" : ""}` })) }];
  const derecho = derechoAfiliacionPadron(persona);
  const derechos = { administrativas: "Sin habilitar · sólo registro administrativo", finalizadas: "Finalizados", vigentes: "Habilitados · sujetos a reglas de cobertura", futuras: "Aún no vigentes" }[derecho] || "Sin informar";
  return <section className={integrado ? "space-y-6" : "space-y-4"} aria-label="Ficha administrativa del padrón">
    {ver("datos") && <div hidden={Boolean(activo)} className="space-y-4">
      <TarjetaFicha titulo="Estado administrativo" icono="shieldCheck" descripcion="La situación administrativa y la cuenta informada son independientes de la cobertura efectiva. Las fechas informadas no ejecutan cortes automáticos." accion={<div className="flex shrink-0 flex-wrap items-center gap-2"><Badge tone={persona.estado_administrativo === "activo" ? "green" : "amber"}>{ADMINISTRATIVOS[persona.estado_administrativo] || "Sin informar"}</Badge>{puedeEditar && <Button size="sm" variant="secondary" disabled={Boolean(persona.finalizado_en)} title={persona.finalizado_en ? "Reactivá la afiliación antes de cambiar el plan." : undefined} onClick={() => setEdicion({ titulo: "Plan de cobertura", descripcion: "El plan se aplica a evaluaciones nuevas. Cambiarlo conserva las fechas de derechos y los eventos ya registrados." })}>Cambiar plan</Button>}</div>}>
        <dl className="grid gap-x-6 gap-y-4 text-sm sm:grid-cols-2 lg:grid-cols-3"><div><dt className="text-xs font-medium uppercase tracking-wide text-texto-debil">Derechos actuales</dt><dd className="mt-1 font-medium">{derechos}</dd></div><div><dt className="text-xs font-medium uppercase tracking-wide text-texto-debil">Tipo de plan</dt><dd className={persona.plan_tipo ? "mt-1 font-medium" : "mt-1 text-texto-tenue"}>{TIPOS_PLAN[persona.plan_tipo] || "Sin informar"}</dd></div></dl>
        {persona.fin_prestacional_informado && derecho === "vigentes" && <p role="status" className="mt-4 rounded-md bg-badge-amber-bg p-3 text-sm text-badge-amber-fg">Hay un fin prestacional informado ({persona.fin_prestacional_informado}) y los derechos siguen vigentes. La finalización prestacional requiere la acción explícita de cobertura.</p>}
      </TarjetaFicha>
      <div className={integrado ? "space-y-4" : "grid items-start gap-4 xl:grid-cols-2"}>{BLOQUES_PADRON.map((bloque) => <section key={bloque.titulo} aria-label={bloque.titulo} className={!integrado && bloque.titulo === "Identidad" ? "xl:col-span-2" : undefined}>
        <TarjetaFicha titulo={bloque.titulo} icono={ICONOS[bloque.titulo]} descripcion={bloque.titulo === "Régimen y trabajo" ? "Empleador y actividad según el régimen; subsidio aplicable a desempleo. Campos sin informar se conservan para el legado. No hay validación automática ante ARCA o ANSES." : bloque.descripcion} accion={puedeEditar && <Button size="sm" variant="secondary" onClick={() => setEdicion(bloque)}>Editar {bloque.titulo.toLocaleLowerCase("es-AR")}</Button>}>
          <DatosFicha campos={bloque.campos} valores={persona} className={!integrado && bloque.titulo !== "Identidad" ? "lg:grid-cols-2" : undefined} />
        </TarjetaFicha>
      </section>)}</div>
    </div>}
    {ver("legajo") && <>
    <div hidden={Boolean(activo) && activo !== "familia"}><FamiliaPadron key={persona.id} ruta={ruta} persona={persona} scope={scope} organizacion={organizacion} parametros={parametros} puedeEditar={puedeEditar} actualizado={actualizado} integrado={integrado} onEdicion={setRecursoActivo} onOcupado={onOcupado} /></div>
    <div hidden={Boolean(activo) && activo !== "legajo"}><LegajoPadron key={`legajo:${persona.id}`} ruta={ruta} persona={persona} scope={scope} puedeEditar={puedeEditar} actualizado={actualizado} integrado={integrado} onEdicion={setRecursoActivo} onOcupado={onOcupado} /></div>
    <div hidden={Boolean(activo) && activo !== "salud"}>{permisos.salud_consulta === true && <RecursoProtegidoPadron key={`salud:${persona.id}`} recurso="salud" ruta={ruta} scope={scope} puedeEditar={permisos.salud_edicion === true} actualizado={actualizado} integrado={integrado} onEdicion={setRecursoActivo} onOcupado={onOcupado} />}</div>
    <div hidden={Boolean(activo) && activo !== "cobranza"}>{permisos.cobranza_consulta === true && <RecursoProtegidoPadron key={`cobranza:${persona.id}`} recurso="cobranza" ruta={ruta} scope={scope} puedeEditar={permisos.cobranza_edicion === true} actualizado={actualizado} integrado={integrado} onEdicion={setRecursoActivo} onOcupado={onOcupado} />}</div>
    </>}
    {ver("historial") && <div hidden={Boolean(activo)}><HistorialPadron key={`historial:${persona.id}`} ruta={`${ruta}historial/`} scope={scope} /></div>}
    {edicion && (edicion.titulo === "Plan de cobertura" && (planes.isLoading || planes.error) ? <Card className="p-4">{planes.error ? <p role="alert">{errorFinanciador(planes.error)} <Button onClick={() => planes.refetch()}>Reintentar</Button></p> : <Spinner label="Consultando planes…" />}<Button variant="ghost" onClick={() => setEdicion(null)}>Cancelar</Button></Card> : <FormularioPadron integrado={integrado} onOcupado={onOcupado} titulo={`Editar ${edicion.titulo.toLocaleLowerCase("es-AR")}`} descripcion={edicion.descripcion} campos={edicion.campos || camposPlan} inicial={persona} guardar={(cambios, motivo) => api.patch(ruta, { ...cambios, revision: persona.revision, motivo })} recargar={async () => { setEdicion(null); await actualizado(); }} onClose={() => setEdicion(null)} onGuardado={async () => { setEdicion(null); await actualizado(); }} />)}
  </section>;
}
