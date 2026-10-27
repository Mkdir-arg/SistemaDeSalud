// Revisión de una fila OSTEL en su propio diálogo, encima del modal de
// importación. Se corrigen la identidad y la ficha; el backend vuelve a validar.
import { createPortal } from "react-dom";
import { Button, Field, Input, Modal, Select, Textarea } from "@/components/ui";
import { COLUMNAS_OSTEL, PROVINCIAS } from "./formatosImportacion";

export const CAMPOS = { numero_interno: "Número interno", numero: "Número de afiliación", documento: "Documento", cuil: "CUIL", nombre: "Nombre completo" };
// Campo de la ficha → columna OSTEL de la que viene.
const FICHA = {
  calle: ["Calle", "A_CALLE"], altura: ["Altura", "A_NRO"], piso: ["Piso", "A_PISO"], departamento: ["Departamento", "A_DPTO"],
  codigo_postal: ["Código postal", "CODPOS"], localidad: ["Localidad", "DESLOCA"], provincia: ["Provincia", "CODPROV"],
  telefono: ["Teléfono", "A_TEL1"], celular: ["Celular", "CELU1"], email: ["Email", "EMAIL1"],
  sexo: ["Sexo", "SEXO"], fecha_nacimiento: ["Fecha de nacimiento", "FEC_NAC"],
};
const LARGOS = { calle: 160, altura: 20, piso: 20, departamento: 20, codigo_postal: 20, localidad: 100, telefono: 60, celular: 60, email: 254 };

// Lo que se puede corregir arranca con lo que el archivo dejó listo para
// aplicar. Un campo advertido se precarga con el valor crudo del archivo para
// que se vea qué hay que arreglar (salvo listas cerradas: sexo y provincia).
export function fichaInicial(fila) {
  return Object.fromEntries(Object.entries(FICHA).map(([campo, [, columna]]) => {
    if (fila.ficha?.[campo]) return [campo, fila.ficha[campo]];
    const crudo = fila.original?.[columna];
    const advertido = fila.advertidos?.includes(campo) && !["sexo", "provincia"].includes(campo);
    return [campo, advertido && crudo != null ? String(crudo) : ""];
  }));
}

function avisoDe(fila, campo) {
  const i = (fila.advertidos || []).indexOf(campo);
  return i >= 0 ? fila.advertencias[i] : null;
}

function texto(valor) {
  return valor == null || valor === "" ? null : String(valor);
}

export default function RevisionFilaOstel({ edicion, setEdicion, ocupado, error, onGuardar, onCerrar }) {
  const lectura = edicion.lectura;
  const bloqueada = !!edicion.bloqueo_fuente;
  const cambiar = (grupo, campo, valor) => setEdicion({ ...edicion, [grupo]: { ...edicion[grupo], [campo]: valor } });
  const pie = lectura ? <Button variant="secondary" onClick={onCerrar}>Cerrar</Button> : <>
    <Button variant="ghost" disabled={ocupado} onClick={onCerrar}>Cancelar</Button>
    <Button variant="secondary" disabled={ocupado || !edicion.motivo.trim()} onClick={() => onGuardar("omitir")}>Excluir del lote</Button>
    <Button disabled={ocupado || !edicion.motivo.trim() || bloqueada} onClick={() => onGuardar("corregir")}>{ocupado ? "Guardando…" : "Guardar y revalidar"}</Button>
  </>;
  return createPortal(<Modal title={`${lectura ? "Detalle" : "Revisar"} de ${edicion.hoja} · fila ${edicion.fila_excel}`} width={880}
    onClose={ocupado ? undefined : onCerrar} footer={pie}>
    <div className="space-y-5" aria-label="Subsanar fila" role="region">
      {error && <p role="alert" className="rounded-md bg-badge-error-bg p-3 text-badge-error-fg">{error}</p>}
      {edicion.errores?.length > 0 && <p className="rounded-md bg-badge-amber-bg p-3 text-sm">{edicion.errores.join(" ")}</p>}
      {edicion.conflicto_cobertura && <p role="status" className="rounded-md bg-badge-amber-bg p-3 text-sm">Conflicto de cobertura: actualmente {edicion.conflicto_cobertura.actual ? "habilitada" : "sin habilitar"}; el lote solicita {edicion.conflicto_cobertura.solicitada ? "habilitarla" : "sólo registro administrativo"}. Al guardar con un motivo confirmás que se conserva la habilitación actual.</p>}

      {!bloqueada && <section className="space-y-3">
        <h4 className="font-semibold">Identidad</h4>
        <div className="grid gap-3 sm:grid-cols-2">
          {Object.entries(CAMPOS).map(([k, titulo]) => <Field key={k} label={titulo}><Input value={edicion.datos[k]} maxLength={k === "nombre" ? 160 : 80} disabled={ocupado || lectura} onChange={(e) => cambiar("datos", k, e.target.value)} /></Field>)}
        </div>
        {edicion.padron_actual && <div className="rounded-md bg-superficie-2 p-3 text-sm"><h5 className="font-semibold">Valores actuales en el padrón</h5>{Object.entries(CAMPOS).map(([k, titulo]) => <p key={k}>{titulo}: {edicion.padron_actual[k] || "Sin informar"}</p>)}</div>}
      </section>}

      {!bloqueada && <section className="space-y-3 border-t border-division pt-4">
        <h4 className="font-semibold">Ficha</h4>
        <div className="grid gap-3 sm:grid-cols-2">
          {Object.entries(FICHA).map(([campo, [titulo]]) => {
            const props = { value: edicion.ficha[campo], disabled: ocupado || lectura, onChange: (e) => cambiar("ficha", campo, e.target.value) };
            return <Field key={campo} label={titulo} error={avisoDe(edicion, campo)}>
              {campo === "sexo" ? <Select {...props}><option value="">Sin actualizar</option><option value="F">F</option><option value="M">M</option></Select>
                : campo === "provincia" ? <Select {...props}><option value="">Sin actualizar</option>{PROVINCIAS.map((p) => <option key={p} value={p}>{p}</option>)}</Select>
                  : <Input {...props} type={campo === "fecha_nacimiento" ? "date" : campo === "email" ? "email" : "text"} maxLength={LARGOS[campo]} />}
            </Field>;
          })}
        </div>
      </section>}

      {!lectura && <Field label="Motivo de la revisión" ayuda="Quedará registrado junto con los valores anteriores y el responsable."><Textarea value={edicion.motivo} maxLength={255} disabled={ocupado} onChange={(e) => setEdicion({ ...edicion, motivo: e.target.value })} /></Field>}

      {edicion.correcciones?.length > 0 && <details className="rounded-md border border-division p-3"><summary className="cursor-pointer font-semibold">Historial de revisiones ({edicion.correcciones.length})</summary>{edicion.correcciones.map((c, i) => <div key={i} className="mt-2 border-t border-division pt-2 text-sm"><p>{c.accion === "omitir" ? "Exclusión" : "Corrección"} · {new Date(c.fecha).toLocaleString("es-AR")} · Usuario {c.usuario} · {c.motivo}</p>
        {Object.keys(CAMPOS).filter((k) => c.anterior[k] !== c.nuevo[k]).map((k) => <p key={k}>{CAMPOS[k]}: {c.anterior[k]} → {c.nuevo[k]}</p>)}
        {c.ficha_nueva && Object.keys(FICHA).filter((k) => (c.ficha_anterior?.[k] || "") !== (c.ficha_nueva[k] || "")).map((k) => <p key={k}>{FICHA[k][0]}: {c.ficha_anterior?.[k] || "sin actualizar"} → {c.ficha_nueva[k] || "sin actualizar"}</p>)}
      </div>)}</details>}

      <details className="rounded-md border border-division p-3">
        <summary className="cursor-pointer font-semibold">Valores originales del archivo</summary>
        <p className="mt-2 text-xs text-texto-debil">Las 40 columnas tal como llegaron. Las que no se usan se conservan como evidencia.</p>
        <div className="mt-2 max-h-80 overflow-auto"><table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-superficie"><tr className="border-b border-division"><th scope="col" className="p-2">Columna</th><th scope="col" className="p-2">Valor</th><th scope="col" className="p-2">Se usa como</th></tr></thead>
          <tbody>{COLUMNAS_OSTEL.map(([columna, uso]) => {
            const valor = texto(edicion.original?.[columna]);
            return <tr key={columna} className="border-b border-division last:border-0"><td className="p-2 font-mono text-xs">{columna}</td><td className={valor ? "p-2" : "p-2 text-texto-tenue"}>{valor ?? "—"}</td><td className="p-2 text-texto-debil">{uso || "Evidencia"}</td></tr>;
          })}</tbody>
        </table></div>
      </details>
      {!lectura && <p className="text-xs text-texto-debil">Excluir conserva la evidencia y deja esa fila sin aplicar; no elimina a ninguna persona del padrón.</p>}
    </div>
  </Modal>, document.body);
}
