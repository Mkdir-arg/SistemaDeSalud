import { useEffect } from "react";

import { useLlamadoPortal } from "@/api/portal";
import campana from "@/assets/portal/bell-ring.svg";
import { Icon } from "@/components/icons";

import { Consulta } from "./comun";
import { hora } from "./datos";
import { Boton, Cabecera, TAMANO, Tarjeta, TEXTO } from "./ui";

/**
 * ¿Me están llamando? Mientras la pantalla está abierta consulta cada 5
 * segundos (#121): el aviso llega en menos de 10 sin recargar. No hay fila
 * simulada ni posición: el backend sólo sabe si la persona espera o si un box
 * la llamó.
 */
export function Llamado() {
  const llamado = useLlamadoPortal();
  return <>
    <Cabecera titulo="Sala de espera" atras="/mi/inicio" />
    <Consulta consulta={llamado} cargando="Consultando…" error="No pudimos saber si te están llamando.">
      {(datos) => datos.estado === "llamado" ? <TeLlaman datos={datos} /> : <Esperando datos={datos} />}
    </Consulta>
  </>;
}

/** Pantalla completa, como en Figma «5c · Te están llamando». */
function TeLlaman({ datos }) {
  useEffect(() => { navigator.vibrate?.([200, 100, 200]); }, [datos.llamado_at]);
  return <div role="alert" aria-labelledby="titulo-llamado" className="hen-cta fixed inset-0 z-30 flex items-center justify-center px-5 py-8 text-center text-white">
    <div className="flex w-full max-w-[28rem] flex-col items-center gap-4">
      <span className="relative flex size-24 items-center justify-center">
        <span className="absolute inset-0 rounded-full bg-white/30 motion-safe:animate-ping" />
        <span className="relative flex size-24 items-center justify-center rounded-full bg-superficie"><img src={campana} alt="" width="44" height="44" /></span>
      </span>
      <h2 id="titulo-llamado" className="text-cifra-lg font-bold leading-[38px]">Te están llamando</h2>
      <p className="text-xl font-semibold leading-7">{datos.box}</p>
      <p className={TAMANO.t16}>{datos.institucion?.nombre}</p>
      <p className={`${TAMANO.t13} text-white/90`}>{datos.veces > 1 ? `Te llamaron ${datos.veces} veces. ` : ""}Último llamado a las {hora(datos.llamado_at)}.</p>
      <div className="w-full"><Boton variante="claro" to="/mi/inicio">Volver al inicio</Boton></div>
    </div>
  </div>;
}

function Esperando({ datos }) {
  const enEspera = datos.estado === "en_espera";
  return <div className="space-y-4">
    <Tarjeta className="flex flex-col items-center gap-2 p-6 text-center">
      <span className="flex size-12 items-center justify-center rounded-full bg-accent-50 text-accent"><Icon name={enEspera ? "reloj" : "bell"} size={24} /></span>
      <h2 className={`mt-2 ${TAMANO.t17} font-semibold`}>{enEspera ? "Estás en la sala de espera" : "No estás en una sala de espera"}</h2>
      <p className={TEXTO.cuerpo}>
        {enEspera
          ? `${datos.institucion?.nombre}. Cuando te llamen, lo vas a ver en esta pantalla. Dejala abierta.`
          : "Cuando des presente en la recepción de una institución de la red, desde acá vas a ver cuándo te llaman."}
      </p>
    </Tarjeta>
    <p aria-live="polite" className={`flex items-center justify-center gap-2 ${TEXTO.nota}`}>
      <span aria-hidden="true" className="size-2 rounded-full bg-brand-teal motion-safe:animate-pulse" />Se actualiza sola cada 5 segundos.
    </p>
  </div>;
}
