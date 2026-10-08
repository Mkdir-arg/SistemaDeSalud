import { Link, useLocation } from "react-router-dom";

import { useCoberturaPortal, useLlamadoPortal, usePerfilPortal, useResultadosPortal, useTurnosPortal } from "@/api/portal";
import usuario from "@/assets/portal/user-circle.svg";
import { Icon } from "@/components/icons";
import { plural } from "@/lib/format";

import { ErrorConsulta, Exito, NOMBRE_PORTAL } from "./comun";
import { esHoy, esProximo, fechaLarga, hora, primerNombre, quienYDonde, tituloTurno } from "./datos";
import { Boton, Fila, Insignia, RADIO, TAMANO, Tarjeta, TEXTO } from "./ui";

const TARJETA = `hen-cta flex flex-col gap-2 ${RADIO.tarjeta} p-5 text-white`;

function ProximoTurno({ turno: t }) {
  const confirmado = t.estado === "confirmado";
  return <section aria-label="Tu próximo turno" className={TARJETA}>
    <p className="text-sm font-medium leading-[21px] first-letter:uppercase">{esHoy(t.inicio) ? "Tu turno es hoy" : `Tu próximo turno · ${fechaLarga(t.inicio)}`}</p>
    <h2 className="text-xxl font-bold leading-[30px]">{hora(t.inicio)} · {tituloTurno(t)}</h2>
    <p className={TAMANO.t15}>{quienYDonde(t)}</p>
    <div className="flex gap-2">
      <Boton variante="claro" chico to={`/mi/turnos/${t.id}`}>{t.puede_confirmar ? "Confirmar asistencia" : "Ver turno"}</Boton>
    </div>
    <p className={TAMANO.t13}>{confirmado ? "Confirmaste tu asistencia." : t.puede_confirmar ? "Confirmá que vas a ir: la institución lo ve en el acto." : t.estado_display}</p>
  </section>;
}

export function Inicio() {
  const { state } = useLocation();
  const perfil = usePerfilPortal();
  const turnos = useTurnosPortal();
  const resultados = useResultadosPortal();
  const coberturas = useCoberturaPortal();
  // Una sola consulta al entrar: la que se repite cada 5 s es la de la pantalla del llamado.
  const llamado = useLlamadoPortal({ consultar: false });

  const proximos = turnos.data?.filter(esProximo) || [];
  const listos = resultados.data?.filter((r) => r.realizado).length || 0;
  const enSala = ["en_espera", "llamado"].includes(llamado.data?.estado);
  const resumen = (q, texto) => (q.isPending ? "Cargando…" : q.isError ? "No pudimos cargarlo" : texto(q.data));

  return <div className="space-y-4">
    <header className="flex items-center gap-2.5">
      <span aria-hidden="true" className="flex size-9 flex-none items-center justify-center rounded-md bg-accent text-white"><Icon name="shieldCheck" size={18} /></span>
      <div className="min-w-0 flex-1">
        <p className={`${TAMANO.t13} font-medium text-texto-suave`}>{NOMBRE_PORTAL}</p>
        <h1 className="text-xxl font-bold leading-[30px]">{perfil.data ? `Hola, ${primerNombre(perfil.data.nombre)}` : "Hola"}</h1>
      </div>
      <Link to="/mi/cuenta" aria-label="Mi cuenta" className="flex size-10 flex-none items-center justify-center rounded-md hover:bg-accent-50 focus-visible:outline-2 focus-visible:outline-accent">
        <img src={usuario} alt="" width="20" height="20" />
      </Link>
    </header>
    {state?.aviso && <Exito>{state.aviso}</Exito>}
    {enSala && <Tarjeta className="overflow-hidden">
      <Fila titulo={llamado.data.estado === "llamado" ? `Te están llamando: ${llamado.data.box}` : "Estás en la sala de espera"} detalle={llamado.data.institucion?.nombre} extremo={<Insignia>{llamado.data.estado === "llamado" ? "Ahora" : "Esperando"}</Insignia>} to="/mi/llamado" ultimo />
    </Tarjeta>}
    {turnos.isError ? <ErrorConsulta consulta={turnos} texto="No pudimos cargar tus turnos." />
      : proximos[0] ? <ProximoTurno turno={proximos[0]} />
        : !turnos.isPending && <section className={TARJETA}>
          <h2 className={`${TAMANO.t22} font-bold`}>No tenés turnos próximos</h2>
          <p className={TAMANO.t15cuerpo}>Cuando una institución de la red te dé un turno, lo vas a ver acá.</p>
        </section>}
    <Tarjeta className="overflow-hidden">
      <Fila titulo="Mis turnos" detalle={resumen(turnos, () => (proximos.length ? plural(proximos.length, "próximo", "próximos") : "Sin turnos próximos"))} to="/mi/turnos" />
      <Fila titulo="Resultados" detalle={resumen(resultados, (l) => (l.length ? `${plural(l.length, "estudio", "estudios")} · ${listos} con resultado` : "Todavía no tenés estudios"))} to="/mi/estudios" />
      <Fila titulo="Mi cobertura" detalle={resumen(coberturas, (l) => (l.length ? l.map((c) => c.financiador).join(", ") : "Sin cobertura vigente"))} to="/mi/cobertura" />
      <Fila titulo="Sala de espera" detalle="Mirá si te están llamando" to="/mi/llamado" ultimo />
    </Tarjeta>
    <p className={TEXTO.nota}>Ves lo de todas las instituciones de la red donde te atendiste.</p>
  </div>;
}
