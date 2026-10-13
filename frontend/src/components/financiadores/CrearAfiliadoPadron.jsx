import { useState } from "react";
import { api } from "@/api/client";
import { errorFinanciador, rutaFinanciador } from "@/api/financiadores";
import { errorCampoPadron } from "@/lib/padronEdicion";
import { Button, Field, Input, Modal, Select, Textarea } from "@/components/ui";
import { BLOQUES_PADRON, CAMPOS_FAMILIA } from "./padronCampos";

const basicos = [
  { name: "numero", label: "Número de afiliado", required: true, maxLength: 80 },
  { name: "documento", label: "Documento", required: true, maxLength: 80 },
  { name: "nombre", label: "Nombre y apellido", required: true, maxLength: 160 },
  { name: "desde", label: "Afiliación vigente desde", type: "date", required: true },
];
export default function CrearAfiliadoPadron({ organizacion, planes, onClose, onGuardado }) {
  const [datos, setDatos] = useState({ desde: new Date().toLocaleDateString("en-CA", { timeZone: "America/Argentina/Buenos_Aires" }) });
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const campoPlan = { name: "plan", label: "Plan", numeric: true, options: planes.filter((plan) => plan.activo !== false).map((plan) => ({ id: plan.id, nombre: plan.nombre })) };
  const bloques = [...BLOQUES_PADRON.map((bloque) => ({ ...bloque, campos: bloque.campos.filter((campo) => !["numero", "documento", "nombre"].includes(campo.name)) })), { titulo: "Familia (opcional)", campos: CAMPOS_FAMILIA }];
  const campos = [...basicos, campoPlan, ...bloques.flatMap((bloque) => bloque.campos)];
  function control({ name, label, options, numeric, nullable, ...props }) {
    const cambiar = (event) => setDatos((previo) => ({ ...previo, [name]: event.target.value }));
    return <Field key={name} label={label} error={errorCampoPadron(error, name)}>{options ? <Select {...props} value={datos[name] ?? ""} onChange={cambiar}><option value="">Sin informar</option>{options.map((opcion) => <option key={opcion.id} value={opcion.id}>{opcion.nombre}</option>)}</Select> : <Input {...props} value={datos[name] ?? ""} onChange={cambiar} />}</Field>;
  }
  async function enviar(event) {
    event.preventDefault();
    if (ocupado) return;
    const body = { motivo: motivo.trim(), solo_crear: true };
    campos.forEach((campo) => {
      const valor = datos[campo.name];
      if (valor == null || valor === "") return;
      body[campo.name] = campo.numeric ? Number(valor) : valor;
    });
    setOcupado(true); setError(null);
    let resultado;
    try { resultado = await api.post(rutaFinanciador(organizacion.id, "padron"), body); }
    catch (err) { setError(err); setOcupado(false); return; }
    try { await onGuardado(resultado); }
    catch { setError({ message: "La afiliación se guardó. Cerrá y recargá el padrón para consultar el resultado." }); }
  }
  return <Modal title="Registrar afiliación" onClose={ocupado ? undefined : onClose} width={840}><form className="space-y-5" onSubmit={enviar}>
    <p className="text-sm text-texto-debil">Los datos ampliados son opcionales para el legado. Identificadores como texto con sus ceros. Si el documento ya existe, abrí su ficha para editarlo con la versión actual. Salud y cobranza se cargan por separado con designación específica.</p>
    {error && <div role="alert" className="rounded-md bg-badge-error-bg p-3 text-badge-error-fg">{error.status ? errorFinanciador(error) : error.message}{ocupado && <Button type="button" variant="secondary" onClick={onClose}>Cerrar</Button>}</div>}
    <fieldset disabled={ocupado} className="space-y-4"><div className="grid gap-4 sm:grid-cols-2">{[...basicos, campoPlan].map(control)}</div>
      {bloques.map((bloque) => <details key={bloque.titulo} className="rounded-md border border-division p-3"><summary className="cursor-pointer font-semibold">{bloque.titulo}</summary>{bloque.descripcion && <p className="mt-2 text-sm text-texto-debil">{bloque.descripcion}</p>}{bloque.titulo === "Familia (opcional)" && <p className="mt-2 text-sm text-texto-debil">ID de un titular existente de esta organización. También podés vincularlo por búsqueda desde la ficha después de registrar el alta.</p>}<div className="mt-4 grid gap-4 sm:grid-cols-2">{bloque.campos.map(control)}</div></details>)}
      <Field label="Motivo del alta" error={errorCampoPadron(error, "motivo")}><Textarea required maxLength={255} value={motivo} onChange={(event) => setMotivo(event.target.value)} /></Field>
    </fieldset><div className="flex justify-end gap-2"><Button type="button" variant="ghost" disabled={ocupado} onClick={onClose}>Cancelar</Button><Button type="submit" disabled={ocupado || !motivo.trim()}>{ocupado ? "Guardando…" : "Registrar afiliación"}</Button></div>
  </form></Modal>;
}
