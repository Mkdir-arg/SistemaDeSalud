import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "@/api/client";
import { errorFinanciador, rutaFinanciador } from "@/api/financiadores";
import { Button, Modal } from "@/components/ui";

export default function FamiliaFilaOstel({ organizacion, lote, fila, onCerrar, onAplicado }) {
  const [propuesta, setPropuesta] = useState(null);
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState(null);
  const [confirmado, setConfirmado] = useState(false);
  const activo = useRef(true);
  const ruta = rutaFinanciador(organizacion.id, `padron/${fila.afiliado}/familia-ostel`);
  const fuente = { importacion: lote.id, fila: fila.fila };
  const titulares = lote.filas.filter((f) => f.estado === "aplicada" && f.afiliado === propuesta?.titular);
  const titular = titulares.length === 1 ? titulares[0] : null;

  async function consultar() {
    setOcupado(true); setError(null); setPropuesta(null);
    try {
      const nueva = await api.get(`${ruta}?${new URLSearchParams(fuente)}`);
      if (activo.current) setPropuesta(nueva);
    } catch (e) {
      if (activo.current) setError(errorFinanciador(e));
    } finally {
      if (activo.current) setOcupado(false);
    }
  }
  // El padre fija lote/fila mediante key y bloquea su cambio mientras está abierto.
  useEffect(() => {
    activo.current = true;
    consultar();
    return () => { activo.current = false; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function confirmar() {
    if (ocupado || !propuesta || !titular || confirmado) return;
    setOcupado(true); setError(null);
    try {
      await api.post(ruta, { ...fuente, ...propuesta });
      if (!activo.current) return;
      setConfirmado(true);
      setPropuesta(null);
      try { await onAplicado(); }
      catch { if (activo.current) setError("El vínculo fue confirmado, pero no se pudo actualizar el padrón visible. Cierre y vuelva a consultar la ficha."); }
    } catch (e) {
      if (activo.current) {
        // Una respuesta perdida no prueba rollback. Nunca repetir el POST a ciegas.
        setPropuesta(null);
        setError(e.status >= 400 && e.status < 500
          ? `${errorFinanciador(e)} Consulte nuevamente la propuesta antes de confirmar.`
          : "No se pudo verificar el resultado. El vínculo puede haberse registrado. Consulte nuevamente la propuesta antes de confirmar.");
      }
    } finally {
      if (activo.current) setOcupado(false);
    }
  }

  return createPortal(<Modal title="Vincular familia OSTEL" width={640}
    onClose={ocupado ? undefined : onCerrar} footer={<>
      <Button variant="secondary" disabled={ocupado} onClick={onCerrar}>{confirmado ? "Cerrar" : "Cancelar"}</Button>
      {!confirmado && (propuesta && titular
        ? <Button disabled={ocupado} onClick={confirmar}>Confirmar vínculo</Button>
        : <Button disabled={ocupado} onClick={consultar}>Consultar propuesta</Button>)}
    </>}>
    <div className="space-y-4">
      <p className="text-sm text-texto-debil">Lote {lote.id} · fila {fila.fila_excel ?? fila.fila}. Identidad según las filas aplicadas; el servidor revalida antes de guardar.</p>
      <section aria-label="Integrante"><h3 className="font-semibold">Integrante</h3>
        <p>{fila.datos.nombre || "Sin nombre"}</p><p className="text-sm text-texto-debil">Número interno: {fila.datos.numero_interno || "Sin informar"}</p></section>
      {titular && <section aria-label="Titular propuesto" className="border-t border-division pt-4">
        <h3 className="font-semibold">Titular propuesto</h3><p>{titular.datos.nombre || "Sin nombre"}</p>
        <p className="text-sm text-texto-debil">Número interno: {titular.datos.numero_interno || "Sin informar"} · fila {titular.fila_excel ?? titular.fila}</p>
      </section>}
      {propuesta && !titular && <p role="alert">No se pudo identificar una única fila aplicada del titular. Cierre y vuelva a consultar el lote.</p>}
      <p className="rounded-md bg-superficie-2 p-3 text-sm">Sólo se confirma el vínculo familiar. No se interpreta CODPAR ni se modifican la clasificación del parentesco o los derechos de cobertura.</p>
      {ocupado && <p role="status">Procesando…</p>}
      {error && <p role="alert">{error}</p>}
      {confirmado && <p role="status">Vínculo confirmado. No se modificaron la clasificación ni la cobertura.</p>}
    </div>
  </Modal>, document.body);
}
