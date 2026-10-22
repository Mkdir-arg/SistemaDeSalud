import { useEffect, useRef, useState } from "react";
import { api } from "@/api/client";
import { errorFinanciador, rutaFinanciador } from "@/api/financiadores";
import { Ayuda, Button, Field, Input, Select, Textarea } from "@/components/ui";

const CAMPOS = { numero_interno: "Número interno", numero: "Número de afiliación", documento: "Documento", cuil: "CUIL", nombre: "Nombre completo" };
const ESTADOS = { valida: "Lista para aplicar", revision: "Requiere revisión", aplicada: "Aplicada", omitida: "Excluida" };

export default function ImportacionAdministrativa({ organizacion, formato, lote, setLote, lotes, onAplicado, onBloqueosChange, soloDetalle = false, coberturaHabilitada = true }) {
  const [archivo, setArchivo] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);
  const [edicion, setEdicion] = useState(null);
  const [pagina, setPagina] = useState(0);
  const [filtro, setFiltro] = useState("pendientes");
  const clave = useRef(crypto.randomUUID());
  useEffect(() => { clave.current = crypto.randomUUID(); }, [coberturaHabilitada]);
  const activo = useRef(true);
  useEffect(() => { activo.current = true; return () => { activo.current = false; }; }, []);
  useEffect(() => { onBloqueosChange({ selector: ocupado || !!edicion, cierre: ocupado || !!edicion }); }, [ocupado, edicion, onBloqueosChange]);
  useEffect(() => { setEdicion(null); setPagina(0); setError(null); }, [lote?.id]);
  const ruta = (recurso) => rutaFinanciador(organizacion.id, recurso);

  async function ejecutar(accion) {
    setOcupado(true); setError(null);
    try { await accion(); }
    catch (e) { if (activo.current) setError(errorFinanciador(e)); }
    finally { if (activo.current) setOcupado(false); }
  }
  async function revisar(event) {
    event.preventDefault();
    if (!archivo || ocupado) return;
    await ejecutar(async () => {
      const datos = new FormData();
      datos.append("archivo", archivo); datos.append("clave", clave.current); datos.append("cobertura_habilitada", String(coberturaHabilitada));
      const nuevo = await api.multipart(ruta(formato.recursoRevision), datos);
      if (activo.current) { setLote(nuevo); lotes.refetch(); }
    });
  }
  async function confirmar() {
    await ejecutar(async () => {
      let actual = lote;
      while (activo.current && actual.resumen.valida > 0) {
        const nuevo = await api.post(ruta("confirmar-importacion"), { importacion: actual.id });
        if (!activo.current) return;
        setLote(nuevo);
        if (nuevo.resumen.valida >= actual.resumen.valida) break;
        actual = nuevo;
      }
      lotes.refetch(); await onAplicado();
    });
  }
  async function guardar(accion) {
    await ejecutar(async () => {
      const nuevo = await api.post(ruta("subsanar-ostel"), {
        importacion: lote.id, fila: edicion.fila, revision: edicion.revision,
        datos: edicion.datos, motivo: edicion.motivo, accion,
      });
      if (activo.current) {
        setLote(nuevo);
        const fila = nuevo.filas.find((f) => f.fila === edicion.fila);
        if (fila?.errores.some((e) => e.includes("no se guardó la corrección"))) {
          setEdicion({ ...fila, datos: edicion.datos, motivo: edicion.motivo });
          setError(fila.errores.join(" "));
        } else setEdicion(null);
        lotes.refetch();
      }
    });
  }
  const filas = (lote?.filas || []).filter((f) => filtro === "todas" || (filtro === "pendientes" ? f.estado === "revision" : f.estado === filtro));
  const ultima = Math.max(0, Math.ceil(filas.length / 20) - 1);
  const visible = Math.min(pagina, ultima);
  return <div className="space-y-5">
    {lote && <p role="status" className="rounded-lg bg-superficie-2 p-3 text-sm">{lote.resumen.cobertura_habilitada === true ? "Personas nuevas: cobertura habilitada, sujeta a plan, fechas y reglas." : "Personas nuevas: sólo registro administrativo, sin habilitar cobertura."} En personas existentes se conserva la habilitación actual.</p>}
    {!soloDetalle && <form onSubmit={revisar} className="space-y-3">
      <div className="flex items-center gap-2"><h3 className="font-semibold">1. Elegí el archivo</h3><Ayuda>{formato.descripcion} Las ausencias no generan bajas. Los archivos de bajas sólo se conservan como evidencia para revisión.</Ayuda></div>
      <Button type="button" variant="secondary" disabled={ocupado} onClick={() => ejecutar(() => api.download(`${ruta("plantilla")}?${new URLSearchParams(formato.parametrosPlantilla("padron"))}`, formato.nombrePlantilla("padron")))}>Descargar plantilla</Button>
      <Field label="Archivo Excel (.xlsx)" ayuda="Hasta 5 MiB. Conservá identificadores y ceros tal como fueron informados."><Input type="file" accept=".xlsx" disabled={ocupado || !!edicion} onChange={(e) => { setArchivo(e.target.files[0] || null); setLote(null); clave.current = crypto.randomUUID(); }} /></Field>
      <Button disabled={!archivo || ocupado || !!edicion} type="submit">{ocupado ? "Procesando…" : "Revisar archivo"}</Button>
    </form>}
    {error && <p role="alert" className="rounded-md bg-badge-error-bg p-3 text-badge-error-fg">{error}</p>}
    {lote && <section className="space-y-4 border-t border-division pt-4" aria-label="Revisión administrativa">
      <h3 className="font-semibold">2. Aplicá las válidas y resolvé las pendientes</h3>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">{[["Listas para aplicar", "valida"], ["Requieren revisión", "revision"], ["Aplicadas", "aplicada"], ["Excluidas", "omitida"]].map(([titulo, estado]) => <div key={estado}><dt>{titulo}</dt><dd className="text-xl font-semibold">{lote.resumen[estado] || 0}</dd></div>)}</dl>
      <Button disabled={ocupado || !lote.resumen.valida || !!edicion} onClick={confirmar}>Aplicar {lote.resumen.valida || 0} filas válidas</Button>
      <p className="text-sm text-texto-debil">Las pendientes no bloquean las válidas. Cada fila se revalida al aplicar; las ya aplicadas no se repiten.</p>
      <Field label="Mostrar filas"><Select value={filtro} onChange={(e) => { setFiltro(e.target.value); setPagina(0); }}><option value="pendientes">Requieren revisión</option><option value="valida">Listas para aplicar</option><option value="aplicada">Aplicadas</option><option value="omitida">Excluidas</option><option value="todas">Todas</option></Select></Field>
      {filas.length === 0 ? <p role="status">No hay filas en esta categoría.</p> : <div className="overflow-auto"><table className="w-full text-left text-sm"><caption className="sr-only">Registros del lote</caption><thead><tr>{["Origen", "Persona", "Estado y observaciones", "Acción"].map((t) => <th key={t} scope="col" className="p-2">{t}</th>)}</tr></thead><tbody>{filas.slice(visible * 20, visible * 20 + 20).map((f) => <tr key={f.fila} className="border-t border-division"><td className="p-2">{f.hoja} · fila {f.fila_excel}</td><td className="p-2">{f.datos.nombre || "Sin nombre"}<br /><span className="text-texto-debil">CUIL {f.datos.cuil || "sin informar"} · interno {f.datos.numero_interno || "sin informar"}</span></td><td className="p-2">{ESTADOS[f.estado]}<p>{f.errores.join(" ")}</p></td><td className="p-2">{<Button variant="secondary" size="sm" disabled={ocupado || !!edicion} onClick={() => setEdicion({ ...f, datos: { ...f.datos }, motivo: "", lectura: ["aplicada", "omitida"].includes(f.estado) })}>{["aplicada", "omitida"].includes(f.estado) ? "Ver detalle" : "Revisar fila"}</Button>}</td></tr>)}</tbody></table></div>}
      {filas.length > 20 && <div className="flex items-center justify-between"><Button variant="ghost" disabled={visible === 0} onClick={() => setPagina(visible - 1)}>Anterior</Button><span>Página {visible + 1} de {ultima + 1}</span><Button variant="ghost" disabled={visible === ultima} onClick={() => setPagina(visible + 1)}>Siguiente</Button></div>}
      {edicion && <section className="space-y-3 rounded-lg border border-division p-4" aria-label="Subsanar fila">
        <h4 className="font-semibold">Revisar {edicion.hoja} · fila {edicion.fila_excel}</h4>
        <p className="text-sm">Corregí sólo con información comprobada. Guardar vuelve a validar; no fusiona personas ni aplica la fila.</p>
        {edicion.conflicto_cobertura && <p role="status" className="rounded-md bg-badge-amber-bg p-3 text-sm">Conflicto de cobertura: actualmente {edicion.conflicto_cobertura.actual ? "habilitada" : "sin habilitar"}; el lote solicita {edicion.conflicto_cobertura.solicitada ? "habilitarla" : "sólo registro administrativo"}. Al guardar con un motivo confirmás que se conserva la habilitación actual.</p>}
        <details><summary className="cursor-pointer">Ver valores originales del archivo</summary><dl className="mt-2 grid grid-cols-2 gap-2 text-sm">{Object.entries(edicion.original).map(([k, v]) => <div key={k}><dt className="font-medium">{k}</dt><dd>{v == null ? "Sin informar" : String(v)}</dd></div>)}</dl></details>
        {edicion.padron_actual && <div className="rounded-md bg-superficie-2 p-3 text-sm"><h5 className="font-semibold">Valores actuales en el padrón</h5>{Object.entries(CAMPOS).map(([k, titulo]) => <p key={k}>{titulo}: {edicion.padron_actual[k] || "Sin informar"}</p>)}</div>}
        {edicion.correcciones?.length > 0 && <details><summary>Historial de revisiones</summary>{edicion.correcciones.map((c, i) => <div key={i} className="border-t border-division py-2 text-sm"><p>{c.accion === "omitir" ? "Exclusión" : "Corrección"} · {c.fecha} · Usuario {c.usuario} · {c.motivo}</p>{Object.keys(CAMPOS).filter((k) => c.anterior[k] !== c.nuevo[k]).map((k) => <p key={k}>{CAMPOS[k]}: {c.anterior[k]} → {c.nuevo[k]}</p>)}</div>)}</details>}
        {edicion.bloqueo_fuente ? <p role="status">{edicion.bloqueo_fuente}</p> : <div className="grid gap-3 sm:grid-cols-2">{Object.entries(CAMPOS).map(([k, titulo]) => <Field key={k} label={titulo}><Input value={edicion.datos[k]} maxLength={k === "nombre" ? 160 : 80} disabled={ocupado || edicion.lectura} onChange={(e) => setEdicion({ ...edicion, datos: { ...edicion.datos, [k]: e.target.value } })} /></Field>)}</div>}
        <Field label="Motivo de la revisión" ayuda="Quedará registrado junto con los valores anteriores y el responsable."><Textarea value={edicion.motivo} maxLength={255} disabled={ocupado || edicion.lectura} onChange={(e) => setEdicion({ ...edicion, motivo: e.target.value })} /></Field>
        <div className="flex flex-wrap gap-2"><Button disabled={ocupado || edicion.lectura || !edicion.motivo.trim() || !!edicion.bloqueo_fuente} onClick={() => guardar("corregir")}>Guardar y revalidar</Button><Button variant="secondary" disabled={ocupado || edicion.lectura || !edicion.motivo.trim()} onClick={() => guardar("omitir")}>Excluir del lote</Button><Button variant="ghost" disabled={ocupado} onClick={() => setEdicion(null)}>Cancelar</Button></div>
        <p className="text-xs text-texto-debil">Excluir conserva la evidencia y deja esa fila sin aplicar; no elimina a ninguna persona del padrón.</p>
      </section>}
    </section>}
  </div>;
}
