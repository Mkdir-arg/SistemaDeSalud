import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { errorFinanciador } from "@/api/financiadores";
import { Badge, Button, Spinner } from "@/components/ui";
import TarjetaFicha, { DatosFicha } from "./TarjetaFicha";
import { estadoVencimiento } from "@/lib/padronEdicion";
import FormularioPadron from "./FormularioPadron";
import HistorialPadron from "./HistorialPadron";
import { CAMPOS_SALUD, CAMPOS_COBRANZA } from "./padronCampos";

export default function RecursoProtegidoPadron({ recurso, ruta, scope, puedeEditar, actualizado, integrado = false, onEdicion, onOcupado }) {
  const [editar, setEditar] = useState(false);
  useEffect(() => { onEdicion?.(editar ? recurso : null); }, [editar, onEdicion, recurso]);
  const [historial, setHistorial] = useState(false);
  const consulta = useQuery({ queryKey: [...scope, "protegido", ruta, recurso], queryFn: () => api.get(`${ruta}${recurso}/`), gcTime: 0, retry: false });
  const salud = recurso === "salud";
  const titulo = salud ? "Condiciones de salud informadas" : "Cobranza administrativa informada";
  const campos = salud ? CAMPOS_SALUD : CAMPOS_COBRANZA;
  return <section aria-label={titulo} className="space-y-3"><div hidden={integrado && Boolean(editar)}><TarjetaFicha titulo={titulo} icono={salud ? "stethoscope" : "wallet"} accion={puedeEditar && consulta.isSuccess && <Button size="sm" variant="secondary" onClick={() => setEditar(true)}>Editar {salud ? "condiciones de salud" : "cobranza informada"}</Button>} descripcion={salud ? "Recurso protegido por designación específica. No amplía el acceso a historia clínica. CUD por referencia externa, sin archivo adjunto; los vencimientos no cortan derechos automáticamente." : "Fuente y fecha informadas por la organización. No constituye deuda calculada, saldo contable, recaudación ni cobro confirmado. Sin integración con bancos, emisores ni proveedores de cupón; no ingreses número de tarjeta ni código de seguridad."}>{consulta.isLoading ? <Spinner label="Consultando recurso protegido…" /> : consulta.error ? <p role="alert">{errorFinanciador(consulta.error)} <Button variant="ghost" onClick={() => consulta.refetch()}>Reintentar</Button></p> : <>
      <DatosFicha campos={campos} valores={consulta.data} />
      <Button variant="ghost" className="mt-4" aria-expanded={historial} onClick={() => setHistorial(!historial)}>{historial ? "Cerrar historial protegido" : "Ver historial protegido"}</Button>
      {salud && consulta.data?.cud_vencimiento && <p className="mt-3 text-sm">CUD: <Badge tone={estadoVencimiento(consulta.data.cud_vencimiento) === "Vencido" ? "amber" : "gray"}>{estadoVencimiento(consulta.data.cud_vencimiento)}</Badge> · Sin corte automático de derechos.</p>}
    </>}</TarjetaFicha>
    {historial && consulta.isSuccess && <HistorialPadron ruta={`${ruta}${recurso}/historial/`} scope={scope} titulo={`Historial de ${salud ? "condiciones de salud" : "cobranza informada"}`} />}
    </div>
    {editar && consulta.isSuccess && <FormularioPadron integrado={integrado} onOcupado={onOcupado} titulo={`Editar ${salud ? "condiciones de salud" : "cobranza informada"}`} campos={campos} inicial={consulta.data} guardar={(cambios, motivo) => api.patch(`${ruta}${recurso}/`, { ...cambios, motivo, revision: consulta.data.revision })} recargar={async () => { setEditar(false); await consulta.refetch(); }} onClose={() => setEditar(false)} onGuardado={async () => { setEditar(false); await actualizado(); }} />}
  </section>;
}
