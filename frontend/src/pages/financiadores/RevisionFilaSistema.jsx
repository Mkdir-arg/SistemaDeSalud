// Revisión de una fila de la plantilla del sistema, en un diálogo propio como
// en OSTEL. Se editan los valores de la fila tal como en la planilla; el
// backend vuelve a leerla y revalida el lote.
import { createPortal } from "react-dom";
import { Button, Field, Input, Modal, Textarea } from "@/components/ui";

export default function RevisionFilaSistema({ edicion, setEdicion, columnas, ocupado, error, onGuardar, onCerrar }) {
  const { lectura } = edicion;
  const marcadas = new Set(edicion.columnas_error || []);
  const pie = lectura ? <Button variant="secondary" onClick={onCerrar}>Cerrar</Button> : <>
    <Button variant="ghost" disabled={ocupado} onClick={onCerrar}>Cancelar</Button>
    <Button variant="secondary" disabled={ocupado || !edicion.motivo.trim()} onClick={() => onGuardar("omitir")}>Excluir del lote</Button>
    <Button disabled={ocupado || !edicion.motivo.trim()} onClick={() => onGuardar("corregir")}>{ocupado ? "Guardando…" : "Guardar y revalidar"}</Button>
  </>;
  return createPortal(<Modal title={`${lectura ? "Detalle" : "Revisar"} de Carga · fila ${edicion.fila}`} width={880}
    onClose={ocupado ? undefined : onCerrar} footer={pie}>
    <div className="space-y-5" aria-label="Subsanar fila" role="region">
      {error && <p role="alert" className="rounded-md bg-badge-error-bg p-3 text-badge-error-fg">{error}</p>}
      {edicion.errores?.length > 0 && <p className="rounded-md bg-badge-amber-bg p-3 text-sm">{edicion.errores.join(" ")}</p>}
      <div className="grid gap-3 sm:grid-cols-2">
        {columnas.map((columna, i) => <Field key={columna} label={columna} error={marcadas.has(columna) || marcadas.has(i + 1) ? "Revisá este valor." : null}>
          <Input value={edicion.valores[i] ?? ""} maxLength={300} disabled={ocupado || lectura} placeholder={/fecha|desde|hasta/i.test(columna) ? "AAAA-MM-DD" : undefined}
            onChange={(e) => setEdicion({ ...edicion, valores: edicion.valores.map((v, j) => j === i ? e.target.value : v) })} />
        </Field>)}
      </div>
      {!lectura && <Field label="Motivo de la revisión" ayuda="Quedará registrado junto con los valores anteriores y el responsable."><Textarea value={edicion.motivo} maxLength={255} disabled={ocupado} onChange={(e) => setEdicion({ ...edicion, motivo: e.target.value })} /></Field>}
      {edicion.correcciones?.length > 0 && <details className="rounded-md border border-division p-3"><summary className="cursor-pointer font-semibold">Historial de revisiones ({edicion.correcciones.length})</summary>{edicion.correcciones.map((c, i) => <div key={i} className="mt-2 border-t border-division pt-2 text-sm"><p>{c.accion === "omitir" ? "Exclusión" : "Corrección"} · {new Date(c.fecha).toLocaleString("es-AR")} · Usuario {c.usuario} · {c.motivo}</p>
        {columnas.filter((_, j) => (c.anterior[j] ?? "") !== (c.nuevo[j] ?? "")).map((columna) => { const j = columnas.indexOf(columna); return <p key={columna}>{columna}: {c.anterior[j] || "vacío"} → {c.nuevo[j] || "vacío"}</p>; })}
      </div>)}</details>}
      {!lectura && <p className="text-xs text-texto-debil">Excluir conserva la evidencia y deja esa fila sin aplicar; no elimina a ninguna persona del padrón ni ningún consumo.</p>}
    </div>
  </Modal>, document.body);
}
