import { useCoberturaPortal } from "@/api/portal";

import { Consulta, Vacio } from "./comun";
import { diaMesAnio } from "./datos";
import { Cabecera, Fila, Insignia, TAMANO, Tarjeta, TEXTO } from "./ui";

/**
 * Las afiliaciones vigentes por documento (#121). `confirmada`: una institución
 * vinculó la afiliación a esta persona. Si no, sólo coincide el documento del
 * padrón del financiador, y se dice así. Usa las filas de Figma; la pantalla en
 * sí no está en el diseño.
 */
export function Cobertura() {
  const coberturas = useCoberturaPortal();
  return <>
    <Cabecera titulo="Mi cobertura" atras="/mi/inicio" />
    <Consulta consulta={coberturas} cargando="Cargando tu cobertura…" error="No pudimos cargar tu cobertura."
      vacio={<Vacio icono="idCard" titulo="No encontramos una cobertura vigente">Si tenés obra social o prepaga, presentá la credencial en la institución: la registran al atenderte.</Vacio>}>
      {(lista) => <div className="space-y-4">
        {lista.map((c) => <Tarjeta key={c.id} className="overflow-hidden">
          <div className="border-b border-borde px-4 py-3.5">
            <strong className={`block ${TAMANO.t17} font-semibold`}>{c.financiador}</strong>
            <span className={TEXTO.filaDetalle}>{[c.financiador_tipo, c.plan].filter(Boolean).join(" · ")}</span>
          </div>
          <Fila titulo="Número de afiliado" detalle={c.numero} />
          <Fila titulo="Vigente desde" detalle={diaMesAnio(c.desde)} />
          <Fila titulo={c.confirmada ? "Confirmada por tu institución" : "Según tu documento"}
            detalle={c.confirmada ? null : "Figura en el padrón con tu número de documento. Ninguna institución la verificó todavía."}
            extremo={<Insignia tono={c.confirmada ? "verde" : "gris"}>{c.confirmada ? "Confirmada" : "Sin verificar"}</Insignia>} ultimo />
        </Tarjeta>)}
      </div>}
    </Consulta>
  </>;
}
