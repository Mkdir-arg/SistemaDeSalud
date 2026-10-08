import { mensajePortal, useDescargarResultado, useResultadosPortal } from "@/api/portal";
import { Icon } from "@/components/icons";

import { Alerta, Consulta, Vacio } from "./comun";
import { diaMes } from "./datos";
import { Cabecera, Insignia, Tarjeta, TEXTO } from "./ui";

/**
 * Los estudios de toda la red (Figma «6a · Resultados»). Los solicitados sin
 * resultado también se ven (decisión del #121), sin descarga. El archivo es el
 * que cargó la institución: no se arma nada en el navegador.
 */
export function Estudios() {
  const resultados = useResultadosPortal();
  const descargar = useDescargarResultado();
  return <>
    <Cabecera titulo="Resultados" atras="/mi/inicio" />
    <Consulta consulta={resultados} cargando="Cargando tus estudios…" error="No pudimos cargar tus estudios."
      vacio={<Vacio icono="flask" titulo="Todavía no tenés estudios">Cuando una institución de la red te pida o cargue un estudio, lo vas a ver acá.</Vacio>}>
      {(lista) => <div className="space-y-4">
        <Alerta>{descargar.isError ? mensajePortal(descargar.error, "No pudimos descargar el estudio.") : null}</Alerta>
        <Tarjeta className="overflow-hidden">
          {lista.map((e, i) => <Estudio key={e.id} estudio={e} ultimo={i === lista.length - 1} descargar={descargar} />)}
        </Tarjeta>
        <p className={TEXTO.nota}>Los pedidos sin resultado se actualizan cuando la institución carga el estudio.</p>
      </div>}
    </Consulta>
  </>;
}

function Estudio({ estudio: e, ultimo, descargar }) {
  const bajando = descargar.isPending && descargar.variables?.id === e.id;
  return <div className={`flex items-center gap-3 px-4 py-3.5 ${ultimo ? "" : "border-b border-borde"}`}>
    <span className="min-w-0 flex-1">
      <strong className={`block ${TEXTO.filaTitulo}`}>{e.tipo}</strong>
      <span className={`block ${TEXTO.filaDetalle}`}>{e.institucion?.nombre}{e.realizado ? ` · ${diaMes(e.fecha)}` : ""}</span>
      {!e.realizado && <span className={`block ${TEXTO.filaDetalle}`}>Solicitado el {diaMes(e.fecha)}, todavía sin resultado</span>}
      {e.realizado && !e.descargable && <span className={`block ${TEXTO.filaDetalle}`}>El archivo está en la institución: pedilo ahí.</span>}
    </span>
    {e.realizado
      ? e.resultado && <Insignia tono={e.resultado === "alterado" ? "ambar" : "verde"}>{e.resultado_display}</Insignia>
      : <Insignia>En proceso</Insignia>}
    {e.descargable && <button type="button" aria-label={`Descargar ${e.tipo}`} onClick={() => descargar.mutate(e)} disabled={bajando}
      className="-mr-2 flex size-10 flex-none items-center justify-center rounded-md text-accent hover:bg-accent-50 focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50">
      <Icon name="download" size={18} />
    </button>}
  </div>;
}
