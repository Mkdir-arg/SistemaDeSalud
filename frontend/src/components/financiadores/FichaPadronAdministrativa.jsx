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
import { ADMINISTRATIVOS, BLOQUES_PADRON, TIPOS_PLAN, valorCampoPadron } from "./padronCampos";

export default function FichaPadronAdministrativa({ afiliado, organizacion, usuarioId, parametros, plataforma }) {
  const [edicion, setEdicion] = useState(null);
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
  if (ficha.isLoading) return <Spinner label="Consultando padrón ampliado…" />;
  if (ficha.error) return <Card className="p-4"><p role="alert">{errorFinanciador(ficha.error)}</p><Button variant="secondary" onClick={() => ficha.refetch()}>Reintentar padrón ampliado</Button></Card>;
  const persona = ficha.data;
  const permisos = persona.permisos || {};
  const camposPlan = [{ name: "plan", label: "Plan", numeric: true, options: (planes.data || []).filter((plan) => plan.activo !== false || plan.id === persona.plan).map((plan) => ({ id: plan.id, nombre: `${plan.nombre}${plan.activo === false ? " (inactivo actual)" : ""}` })) }];
  return <section className="space-y-6" aria-label="Ficha administrativa del padrón">
    <Card className="p-5"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">Estado administrativo</h2><Badge tone={persona.estado_administrativo === "activo" ? "green" : "amber"}>{ADMINISTRATIVOS[persona.estado_administrativo] || "Sin informar"}</Badge></div><p className="mt-2 text-sm">Derechos actuales: {persona.finalizado_en ? "Finalizados" : persona.vigente ? "Vigentes" : "Aún no vigentes"}. Tipo de plan: {TIPOS_PLAN[persona.plan_tipo] || "Sin informar"}.</p><p className="mt-2 text-sm text-texto-debil">La situación administrativa y la cuenta informada son independientes de la cobertura efectiva. Las fechas informadas no ejecutan cortes automáticos.</p>{persona.fin_prestacional_informado && persona.vigente && <p role="status" className="mt-3 text-sm text-badge-amber-fg">Hay un fin prestacional informado ({persona.fin_prestacional_informado}) y los derechos siguen vigentes. La finalización prestacional requiere la acción explícita de cobertura.</p>}{puedeEditar && <Button variant="ghost" className="mt-3" disabled={Boolean(persona.finalizado_en)} title={persona.finalizado_en ? "Reactivá la afiliación antes de cambiar el plan." : undefined} onClick={() => setEdicion({ titulo: "Plan de cobertura", descripcion: "El plan se aplica a evaluaciones nuevas. Cambiarlo conserva las fechas de derechos y los eventos ya registrados." })}>Cambiar plan</Button>}</Card>
    {BLOQUES_PADRON.map((bloque) => <section key={bloque.titulo} aria-label={bloque.titulo} className="space-y-3"><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-lg font-semibold">{bloque.titulo}</h2>{puedeEditar && <Button size="sm" variant="secondary" onClick={() => setEdicion(bloque)}>Editar {bloque.titulo.toLocaleLowerCase("es-AR")}</Button>}</div>{bloque.descripcion && <p className="text-sm text-texto-debil">{bloque.descripcion}</p>}<Card className="p-4"><dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">{bloque.campos.map((campo) => <div key={campo.name}><dt className="text-texto-debil">{campo.label}</dt><dd className="mt-1 break-words font-medium">{valorCampoPadron(campo, persona[campo.name])}</dd></div>)}</dl>{bloque.titulo === "Régimen y trabajo" && <p className="mt-3 text-sm text-texto-debil">Empleador y actividad según el régimen; subsidio aplicable a desempleo. Campos sin informar se conservan para el legado. No hay validación automática ante ARCA o ANSES.</p>}</Card></section>)}
    <FamiliaPadron key={persona.id} ruta={ruta} persona={persona} scope={scope} organizacion={organizacion} parametros={parametros} puedeEditar={puedeEditar} actualizado={actualizado} />
    <LegajoPadron key={`legajo:${persona.id}`} ruta={ruta} persona={persona} scope={scope} puedeEditar={puedeEditar} actualizado={actualizado} />
    {permisos.salud_consulta === true && <RecursoProtegidoPadron key={`salud:${persona.id}`} recurso="salud" ruta={ruta} scope={scope} puedeEditar={permisos.salud_edicion === true} actualizado={actualizado} />}
    {permisos.cobranza_consulta === true && <RecursoProtegidoPadron key={`cobranza:${persona.id}`} recurso="cobranza" ruta={ruta} scope={scope} puedeEditar={permisos.cobranza_edicion === true} actualizado={actualizado} />}
    <HistorialPadron key={`historial:${persona.id}`} ruta={`${ruta}historial/`} scope={scope} />
    {edicion && (edicion.titulo === "Plan de cobertura" && (planes.isLoading || planes.error) ? <Card className="p-4">{planes.error ? <p role="alert">{errorFinanciador(planes.error)} <Button onClick={() => planes.refetch()}>Reintentar</Button></p> : <Spinner label="Consultando planes…" />}<Button variant="ghost" onClick={() => setEdicion(null)}>Cancelar</Button></Card> : <FormularioPadron titulo={`Editar ${edicion.titulo.toLocaleLowerCase("es-AR")}`} descripcion={edicion.descripcion} campos={edicion.campos || camposPlan} inicial={persona} guardar={(cambios, motivo) => api.patch(ruta, { ...cambios, revision: persona.revision, motivo })} recargar={async () => { setEdicion(null); await actualizado(); }} onClose={() => setEdicion(null)} onGuardado={async () => { setEdicion(null); await actualizado(); }} />)}
  </section>;
}
