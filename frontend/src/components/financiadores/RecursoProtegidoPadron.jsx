import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { errorFinanciador } from "@/api/financiadores";
import { Badge, Button, Card, Spinner } from "@/components/ui";
import { estadoVencimiento } from "@/lib/padronEdicion";
import FormularioPadron from "./FormularioPadron";
import HistorialPadron from "./HistorialPadron";
import { CAMPOS_SALUD, CAMPOS_COBRANZA, valorCampoPadron } from "./padronCampos";

export default function RecursoProtegidoPadron({ recurso, ruta, scope, puedeEditar, actualizado }) {
  const [editar, setEditar] = useState(false);
  const [historial, setHistorial] = useState(false);
  const consulta = useQuery({ queryKey: [...scope, "protegido", ruta, recurso], queryFn: () => api.get(`${ruta}${recurso}/`), gcTime: 0, retry: false });
  const salud = recurso === "salud";
  const titulo = salud ? "Condiciones de salud informadas" : "Cobranza administrativa informada";
  const campos = salud ? CAMPOS_SALUD : CAMPOS_COBRANZA;
  return <section aria-label={titulo} className="space-y-3"><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-lg font-semibold">{titulo}</h2>{puedeEditar && consulta.isSuccess && <Button variant="secondary" onClick={() => setEditar(true)}>Editar {salud ? "condiciones de salud" : "cobranza informada"}</Button>}</div>
    <p className="text-sm text-texto-debil">{salud ? "Recurso protegido por designación específica. No amplía el acceso a historia clínica. CUD por referencia externa, sin archivo adjunto; los vencimientos no cortan derechos automáticamente." : "Fuente y fecha informadas por la organización. No constituye deuda calculada, saldo contable, recaudación ni cobro confirmado. Sin integración con bancos, emisores ni proveedores de cupón; no ingreses número de tarjeta ni código de seguridad."}</p>
    <Card className="p-4">{consulta.isLoading ? <Spinner label="Consultando recurso protegido…" /> : consulta.error ? <p role="alert">{errorFinanciador(consulta.error)} <Button variant="ghost" onClick={() => consulta.refetch()}>Reintentar</Button></p> : <>
      <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">{campos.map((campo) => <div key={campo.name}><dt className="text-texto-debil">{campo.label}</dt><dd className="mt-1 break-words whitespace-pre-wrap font-medium">{valorCampoPadron(campo, consulta.data?.[campo.name])}</dd></div>)}</dl>
      <Button variant="ghost" className="mt-4" aria-expanded={historial} onClick={() => setHistorial(!historial)}>{historial ? "Cerrar historial protegido" : "Ver historial protegido"}</Button>
      {salud && consulta.data?.cud_vencimiento && <p className="mt-3 text-sm">CUD: <Badge tone={estadoVencimiento(consulta.data.cud_vencimiento) === "Vencido" ? "amber" : "gray"}>{estadoVencimiento(consulta.data.cud_vencimiento)}</Badge> · Sin corte automático de derechos.</p>}
    </>}</Card>
    {historial && consulta.isSuccess && <HistorialPadron ruta={`${ruta}${recurso}/historial/`} scope={scope} titulo={`Historial de ${salud ? "condiciones de salud" : "cobranza informada"}`} />}
    {editar && consulta.isSuccess && <FormularioPadron titulo={`Editar ${salud ? "condiciones de salud" : "cobranza informada"}`} campos={campos} inicial={consulta.data} guardar={(cambios, motivo) => api.patch(`${ruta}${recurso}/`, { ...cambios, motivo, revision: consulta.data.revision })} recargar={async () => { setEditar(false); await consulta.refetch(); }} onClose={() => setEditar(false)} onGuardado={async () => { setEditar(false); await actualizado(); }} />}
  </section>;
}
