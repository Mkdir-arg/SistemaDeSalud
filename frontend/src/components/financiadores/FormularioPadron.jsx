import { useEffect, useRef, useState } from "react";
import { errorFinanciador } from "@/api/financiadores";
import { cambiosPadron, errorCampoPadron } from "@/lib/padronEdicion";
import { Button, Checkbox, Field, Input, Modal, Select, Textarea } from "@/components/ui";
import Geografia from "@/components/issue136_Geografia";
import { cuerpoGeo, geografiaInicial, hayGeoPendiente, nombreGeo } from "@/lib/issue136_geografia";

// Sólo envía campos del bloque que la API habilitó y que la persona cambió.
// No completa recursos sensibles ausentes con valores vacíos.
export default function FormularioPadron({ titulo, descripcion, campos, inicial = {}, guardar, onClose, onGuardado, recargar, antesCampos, requiereCambio = true, integrado = false, onOcupado, geografiaOrganizacion }) {
  const [datos, setDatos] = useState(() => Object.fromEntries(campos.map((campo) => [campo.name, inicial[campo.name] ?? (campo.boolean ? false : "")])));
  const [guardarVersion] = useState(() => guardar);
  const [original] = useState(() => ({ ...inicial }));
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [geo, setGeo] = useState(() => geografiaInicial(inicial.geografia, inicial));
  const [geoLaboral, setGeoLaboral] = useState(() => geografiaInicial(inicial.geografia_laboral));
  const [geoEditada, setGeoEditada] = useState(false);
  const [laboralEditada, setLaboralEditada] = useState(false);
  const domicilio = Boolean(geografiaOrganizacion && campos.some((c) => c.name === "provincia"));
  const laboral = Boolean(geografiaOrganizacion && campos.some((c) => c.name === "domicilio_laboral"));
  const formulario = useRef(null);
  useEffect(() => {
    if (!integrado) return;
    const previo = document.activeElement;
    formulario.current?.focus();
    return () => { setTimeout(() => { if (previo?.getClientRects().length) previo.focus(); }, 0); };
  }, [integrado]);
  useEffect(() => { onOcupado?.(ocupado); return () => onOcupado?.(false); }, [ocupado, onOcupado]);
  const cambios = cambiosPadron(campos, original, datos);
  if (geoEditada) cambios.geografia = cuerpoGeo(geo);
  if (laboralEditada || laboral && inicial.geografia_laboral && Object.hasOwn(cambios, "domicilio_laboral")) cambios.geografia_laboral = cuerpoGeo(geoLaboral);
  const geoPendiente = domicilio && hayGeoPendiente(geo) || laboral && hayGeoPendiente(geoLaboral);
  const conflicto = error?.status === 409;
  async function enviar(event) {
    event.preventDefault();
    if (ocupado || conflicto || geoPendiente || !motivo.trim() || requiereCambio && !Object.keys(cambios).length) return;
    setOcupado(true); setError(null);
    // Una recarga de fondo nunca sustituye la revisión con que se abrió el
    // formulario: hacerlo permitiría sobrescribir una edición concurrente.
    try { await guardarVersion(cambios, motivo.trim()); }
    catch (err) { setError(err); setOcupado(false); return; }
    // La escritura y la actualización del cliente son pasos distintos. Un
    // fallo de recarga no habilita enviar nuevamente una escritura exitosa.
    try { await onGuardado(); }
    catch { setError({ message: "Los cambios se guardaron. Cerrá y recargá la ficha para consultar el resultado." }); }
  }
  const contenido = <>
    <form ref={formulario} tabIndex={integrado ? -1 : undefined} onSubmit={enviar} className="space-y-4 outline-none">
      {error && <div role="alert" className="rounded-md bg-badge-error-bg p-3 text-badge-error-fg">{error.status ? errorFinanciador(error) : error.message}{conflicto && <p className="mt-2">Otra persona modificó este registro. Cerrá el formulario y recargá antes de volver a editar; tus cambios no se reenviaron.</p>}{conflicto && recargar && <Button type="button" variant="secondary" className="mt-2" onClick={recargar}>Recargar ficha</Button>}{ocupado && <Button type="button" variant="secondary" className="mt-2" onClick={onClose}>Cerrar</Button>}</div>}
      <fieldset disabled={ocupado || conflicto} className="grid gap-4 sm:grid-cols-2">
        {antesCampos}
        {domicilio && <div className="sm:col-span-2"><Geografia value={geo} ambito="financiador" organizacion={geografiaOrganizacion} disabled={ocupado || conflicto} onChange={(valor) => {
          setGeo(valor); setGeoEditada(true);
          setDatos((previo) => ({ ...previo, ...Object.fromEntries(["provincia", "partido", "localidad"].map((n) => [n, nombreGeo(valor[n])])) }));
        }} /></div>}
        {laboral && <div className="sm:col-span-2"><Geografia value={geoLaboral} ambito="financiador" organizacion={geografiaOrganizacion} disabled={ocupado || conflicto} onChange={(valor) => { setGeoLaboral(valor); setLaboralEditada(true); }} /></div>}
        {campos.map(({ name, label, options, numeric, boolean, textarea, nullable, tristate, ayuda, onSelect, ...props }) => {
          if (domicilio && ["provincia", "partido", "localidad"].includes(name)) return null;
          const cambiar = (event) => { const value = boolean ? event.target.checked : event.target.value; setDatos((previo) => ({ ...previo, [name]: value })); onSelect?.(value); };
          return <Field key={name} label={boolean ? undefined : label} ayuda={ayuda} error={errorCampoPadron(error, name)}>{boolean ? <Checkbox label={label} checked={Boolean(datos[name])} onChange={cambiar} /> : options ? <Select {...props} value={datos[name]} onChange={cambiar}><option value="">Sin informar</option>{options.map((opcion) => <option key={opcion.id} value={opcion.id}>{opcion.nombre}</option>)}</Select> : textarea ? <Textarea {...props} value={datos[name]} onChange={cambiar} /> : <Input {...props} value={datos[name]} onChange={cambiar} />}</Field>;
        })}
      </fieldset>
      <Field label="Motivo del cambio" error={errorCampoPadron(error, "motivo")} hint="Describí la corrección administrativa. No incluyas diagnósticos ni datos bancarios en el motivo."><Textarea required maxLength={255} disabled={ocupado || conflicto} value={motivo} onChange={(event) => setMotivo(event.target.value)} /></Field>
      {geoPendiente && <p role="alert" className="text-sm text-badge-amber-fg">Revisá los lugares pendientes antes de guardar.</p>}
      <div className="flex justify-end gap-2"><Button type="button" variant="ghost" disabled={ocupado} onClick={onClose}>Cancelar</Button><Button type="submit" disabled={ocupado || conflicto || geoPendiente || !motivo.trim() || requiereCambio && !Object.keys(cambios).length}>{ocupado ? "Guardando…" : "Guardar cambios"}</Button></div>
    </form>
  </>;
  return integrado ? <section aria-label={titulo}><h2 className="mb-3 text-lg font-semibold">{titulo}</h2>{descripcion && <p className="mb-4 text-sm text-texto-debil">{descripcion}</p>}{contenido}</section> : <Modal title={titulo} ayuda={descripcion} onClose={ocupado ? undefined : onClose} width={760}>{contenido}</Modal>;
}
