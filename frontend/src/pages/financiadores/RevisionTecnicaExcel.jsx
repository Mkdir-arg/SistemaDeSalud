import { useEffect, useRef, useState } from "react";
import { api } from "@/api/client";
import { errorFinanciador, prevalidarFormato, rutaFinanciador } from "@/api/financiadores";
import { Ayuda, Badge, Button, Card, Field, Input } from "@/components/ui";

const DESCRIPCIONES = {
  encabezado_incorrecto: "Encabezado ausente, cambiado o fuera de orden",
  encabezado_ausente: "Falta la fila de encabezados",
  columna_adicional: "Columna adicional con contenido",
  fila_duplicada: "Fila repetida exactamente",
  formula: "Fórmula detectada; no se ejecutó",
  error_excel: "La celda contiene un error de Excel",
  tipo_no_admitido: "Tipo de celda no admitido",
  booleano_invalido: "Valor booleano XLSX inválido",
  numero_invalido: "Representación numérica XLSX inválida",
  fecha_xml_invalida: "Representación de fecha XLSX no admitida",
  hoja_no_reconocida: "Hoja no reconocida; no se revisaron sus filas",
  sin_hojas_reconocidas: "No se encontraron hojas reconocidas para este formato",
};
const descripcion = (codigo) => DESCRIPCIONES[codigo] || "Anomalía técnica";

export default function RevisionTecnicaExcel({ organizacion, formato, tipo, onBloqueosChange }) {
  const [archivo, setArchivo] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [descargando, setDescargando] = useState(false);
  const activo = useRef(true);
  useEffect(() => { activo.current = true; return () => { activo.current = false; }; }, []);
  useEffect(() => { onBloqueosChange({ selector: ocupado || descargando, cierre: false }); }, [ocupado, descargando, onBloqueosChange]);

  async function descargar() {
    setDescargando(true); setError(null);
    try {
      await api.download(`${rutaFinanciador(organizacion.id, "plantilla")}?${new URLSearchParams(formato.parametrosPlantilla(tipo))}`, formato.nombrePlantilla(tipo));
    } catch (err) {
      if (activo.current) setError(errorFinanciador(err));
    } finally {
      if (activo.current) setDescargando(false);
    }
  }

  async function revisar(event) {
    event.preventDefault();
    if (!archivo || ocupado) return;
    setOcupado(true); setError(null); setResultado(null);
    try {
      const datos = await prevalidarFormato(organizacion.id, formato.recursoRevision, archivo);
      if (activo.current) setResultado(datos);
    } catch (err) {
      if (activo.current) setError(errorFinanciador(err));
    } finally {
      if (activo.current) setOcupado(false);
    }
  }

  function seleccionar(event) {
    const seleccionado = event.target.files[0] || null;
    setResultado(null); setError(null); setArchivo(null);
    if (seleccionado && (!seleccionado.name.toLowerCase().endsWith(".xlsx") || seleccionado.size > formato.maxBytes)) {
      setError(`Seleccioná un archivo .xlsx de hasta ${formato.maxBytes / (1024 * 1024)} MiB.`);
      return;
    }
    setArchivo(seleccionado);
  }

  return <div className="space-y-5">
      <p role="status" className="text-sm text-badge-amber-fg">{formato.aviso}</p>
      <Card className="p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold">1. Prepará el archivo</h3>
            <Ayuda etiqueta="Ayuda sobre la plantilla">
              <span className="block">{formato.descripcion}</span>
              <span className="block">Conservá los identificadores como texto. La revisión comprueba la estructura del archivo; no guarda afiliados ni determina cobertura.</span>
            </Ayuda>
          </div>
          <Button variant="secondary" disabled={descargando || ocupado} onClick={descargar}>{descargando ? "Descargando…" : "Descargar plantilla"}</Button>
        </div>
      </Card>
      <form onSubmit={revisar} className="space-y-3">
        <h3 className="font-semibold">2. Revisá el archivo</h3>
        <Field label="Archivo Excel (.xlsx)" ayuda={`Máximo ${formato.maxBytes / (1024 * 1024)} MiB. No se conserva el archivo ni se crea un lote de importación.`}>
          <Input type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" disabled={ocupado} onChange={seleccionar} />
        </Field>
        {error && <p role="alert" className="rounded-md bg-badge-error-bg p-3 text-badge-error-fg">{error}</p>}
        <Button type="submit" disabled={!archivo || ocupado}>{ocupado ? "Revisando…" : "Revisar archivo"}</Button>
        {ocupado && <p role="status" className="text-sm text-texto-debil">Leyendo el archivo y verificando su estructura…</p>}
      </form>
      {resultado && <section aria-label="Resultado de revisión técnica" className="space-y-4 border-t border-division pt-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-semibold">Resultado técnico</h3>
          <Badge tone={resultado.resumen.anomalias ? "amber" : "gray"}>{resultado.resumen.anomalias ? "Con observaciones" : "Sin anomalías técnicas detectadas"}</Badge>
        </div>
        <p role="status" className="text-sm text-texto-debil">La revisión terminó. Este resultado no acredita que los registros sean aptos para importar.</p>
        <dl className="grid grid-cols-2 gap-3 rounded-lg bg-superficie-2 p-4">
          {Object.entries(resultado.resumen.filas_no_vacias).map(([hoja, total]) => <div key={hoja}><dt className="text-sm text-texto-debil">{hoja} · filas con datos</dt><dd className="text-xl font-semibold tabular-nums">{total.toLocaleString("es-AR")}</dd></div>)}
          <div><dt className="text-sm text-texto-debil">Duplicados exactos</dt><dd className="text-xl font-semibold">{resultado.resumen.duplicados_exactos}</dd></div>
          <div><dt className="text-sm text-texto-debil">Anomalías técnicas</dt><dd className="text-xl font-semibold">{resultado.resumen.anomalias}</dd></div>
        </dl>
        <p className="text-sm text-texto-debil">Se excluyen las filas totalmente vacías. Los duplicados se comparan dentro de cada hoja y no identifican personas. Las fórmulas compartidas no se comparan.</p>
        {resultado.resumen.anomalias > 0 && <>
          <ul className="space-y-1 text-sm">{Object.entries(resultado.anomalias_por_codigo).map(([codigo, total]) => <li key={codigo}>{descripcion(codigo)}: {total}</li>)}</ul>
          {resultado.detalle_truncado && <p role="status" className="text-sm text-badge-amber-fg">Se muestran las primeras {resultado.limite_detalle} anomalías. Los conteos incluyen todas las detectadas.</p>}
          <div className="max-h-80 overflow-auto">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Detalle de anomalías técnicas</caption>
              <thead><tr className="border-b border-division">{["Hoja", "Fila", "Columna", "Observación"].map((titulo) => <th key={titulo} scope="col" className="p-2">{titulo}</th>)}</tr></thead>
              <tbody>{resultado.anomalias.map((item, indice) => <tr key={indice} className="border-b border-division">
                <td className="p-2">{item.hoja || "—"}</td><td className="p-2">{item.fila ?? "—"}</td>
                <td className="p-2">{item.columna ? `${item.columna}${resultado.columnas[item.columna - 1] ? ` · esperado: ${resultado.columnas[item.columna - 1]}` : ""}` : "—"}</td>
                <td className="p-2">{descripcion(item.codigo)}{item.fila_original ? ` (original: fila ${item.fila_original})` : ""}</td>
              </tr>)}</tbody>
            </table>
          </div>
        </>}
      </section>}
    </div>;
}
