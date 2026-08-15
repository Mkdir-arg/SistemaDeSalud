import { Link } from "react-router-dom";

import { useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Avatar, Badge, Card } from "@/components/ui";
import { Buscador, FiltroSelect, LimpiarFiltros, useBusquedaUrl, useFiltroUrl } from "@/components/ui/filtros";
import { TablaRecurso } from "@/components/ui/tabla";
import { filtrosLegibles, nombreRecurso, TONO_ACCESO } from "@/lib/auditoria";
import { fechaHora, plural } from "@/lib/format";
import { cn } from "@/lib/cn";

/*
 * Registro de accesos a datos clínicos (Ley 26.529).
 *
 * Contesta la pregunta que un hospital hoy no puede contestar: «¿quién vio la
 * historia de esta persona?». Es la primera que aparece cuando alguien denuncia
 * que su información circuló, y leer una historia no deja ninguna marca en ella.
 *
 * Sólo lectura: un registro de auditoría con un botón de borrar no sirve para
 * auditar. Tampoco se exporta desde acá —mirarlo ya es mirar datos de pacientes,
 * y una descarga suelta con esos nombres es justamente lo que este registro
 * existe para poder rastrear—. La única acción es abrir la historia del paciente
 * de una fila, y va como link explícito y avisado porque ESO SÍ escribe en el
 * registro, a nombre de quien está auditando.
 */

const TIPOS = [
  { value: "detalle", label: "Consulta de un registro" },
  { value: "listado", label: "Consulta de un listado" },
  { value: "exportacion", label: "Exportación a archivo" },
];

const AVISO_HISTORIA = "Abrir la historia queda registrado a tu nombre.";

export default function Accesos() {
  const { institucion } = useInstitucion();
  const [texto, setTexto, busqueda] = useBusquedaUrl("q");
  const [tipo, setTipo] = useFiltroUrl("tipo", "");
  const [desde, setDesde] = useFiltroUrl("desde", "");
  const [hasta, setHasta] = useFiltroUrl("hasta", "");
  // Alcance: por defecto se ve todo lo que la persona puede auditar, y cada fila
  // dice de qué institución es. Filtrar por defecto escondería los accesos que
  // no quedaron atribuidos a ninguna, que es lo contrario de auditar.
  const [soloInstitucion, setSoloInstitucion] = useFiltroUrl("institucion", "");

  const params = {
    search: busqueda || undefined,
    tipo: tipo || undefined,
    desde: desde || undefined,
    hasta: hasta || undefined,
    institucion: soloInstitucion || undefined,
  };
  const { total } = useLista("accesos-clinicos", { ...params, pageSize: 1 });

  const activos = [busqueda, tipo, desde, hasta, soloInstitucion].filter(Boolean).length;

  return (
    <div className="px-lg py-[26px] sm:px-[30px]">
      <div className="mb-[18px]">
        <h1 className="text-cifra font-extrabold tracking-tight">Registro de accesos</h1>
        <div className="text-sm text-texto-debil">
          Quién consultó datos clínicos, y de quién. {plural(total, "acceso registrado", "accesos registrados")}.
        </div>
        {/* El alcance, dicho. Todo lo que rodea a la tabla afirma el hospital de
            la barra lateral, así que cada fila se lee como suya: con membresía
            en dos instituciones eso es atribuirle a un hospital un acceso que
            ocurrió en otro, en el documento que después se presenta ante el
            paciente o ante la autoridad de aplicación. */}
        <div className="text-sm text-texto-debil">
          Alcance:{" "}
          <strong className="text-texto-suave">
            {soloInstitucion && institucion
              ? institucion.nombre
              : "todas las instituciones donde podés auditar"}
          </strong>
        </div>
      </div>

      {/* Quien mira esta pantalla necesita saber qué está viendo antes de sacar
          conclusiones: un listado del padrón no es lo mismo que abrir la
          historia de una persona, y en la tabla las dos son «un acceso». */}
      <Card className="mb-[18px] px-[18px] py-3.5 text-md text-texto-medio">
        Se registra la consulta a datos clínicos —abrir la historia de un paciente, sus
        estudios, sus recetas—, no la navegación general del sistema. El registro lo
        escribe el sistema al leer: no se edita ni se borra desde ningún lado. Abrir
        una historia desde acá es leerla, así que también queda registrado, a tu nombre.
      </Card>

      <div className="mb-3.5 flex flex-wrap items-center gap-2.5">
        <Buscador
          valor={texto}
          onChange={setTexto}
          placeholder="Buscar por profesional, paciente o documento…"
          className="w-80"
          aria-label="Buscar en el registro de accesos"
        />
        <FiltroSelect valor={tipo} onChange={setTipo} opciones={TIPOS} todos="Todo tipo de acceso" />
        {institucion && (
          <FiltroSelect
            valor={soloInstitucion}
            onChange={setSoloInstitucion}
            opciones={[{ value: String(institucion.id), label: institucion.nombre }]}
            todos="Todas las instituciones"
            etiqueta="Institución del acceso"
          />
        )}
        <Fecha etiqueta="Desde" valor={desde} onChange={setDesde} />
        <Fecha etiqueta="Hasta" valor={hasta} onChange={setHasta} />
        <LimpiarFiltros
          activos={activos}
          onLimpiar={() => {
            setTexto(""); setTipo(""); setDesde(""); setHasta(""); setSoloInstitucion("");
          }}
        />
      </div>

      <TablaRecurso
        clave="accesos"
        recurso="accesos-clinicos"
        params={params}
        ordenInicial="-momento"
        /* Sin `onRowClick`: la tabla le pone cursor, foco y Enter a TODAS las
           filas apenas existe uno, y casi la mitad no tenía a dónde ir —las de
           listado y las de exportación no apuntan a un paciente—. La fila que
           más ganas dan de abrir es justo la de exportación, y no hacía nada:
           quien la clickea concluye que la pantalla está rota o que ahí no hay
           nada más, y las dos conclusiones son falsas. Ahora lo clickeable es un
           link, sólo donde hay historia que abrir. */
        vacio={{
          titulo: activos ? "Ningún acceso coincide" : "Sin accesos registrados",
          detalle: activos
            ? "Probá con el apellido o el documento del paciente, o con el apellido del profesional. También podés ampliar el rango de fechas."
            : "Acá aparece cada consulta a datos clínicos, apenas alguien abra una historia.",
        }}
        columnas={[
          {
            key: "momento", label: "Cuándo", orden: "momento",
            render: (a) => <span className="whitespace-nowrap">{fechaHora(a.momento)}</span>,
          },
          {
            key: "usuario", label: "Quién consultó", orden: "usuario", truncar: true,
            render: (a) => (
              <div className="flex items-center gap-2.5">
                <Avatar nombre={a.usuario_nombre || a.usuario_email} i={a.usuario} size={32} />
                <div className="min-w-0">
                  <div className="truncate font-semibold">{a.usuario_nombre || "—"}</div>
                  <div className="truncate text-sm text-texto-debil">{a.usuario_email}</div>
                </div>
              </div>
            ),
          },
          {
            key: "paciente", label: "De quién", truncar: true,
            render: (a) =>
              a.paciente ? (
                <div className="min-w-0">
                  <div className="truncate font-semibold">{a.paciente}</div>
                  {a.documento && <div className="text-sm text-texto-debil">DNI {a.documento}</div>}
                  {/* El aviso va en el link y no después del clic: quien
                      investiga una filtración abre veinte filas para ver de
                      quién habla cada una, y eso son cuarenta accesos nuevos
                      firmados con su nombre, en las listas que después leen esos
                      mismos pacientes. */}
                  <Link
                    to={`/historia/${a.ciudadano}`}
                    title={AVISO_HISTORIA}
                    className="text-sm font-semibold text-accent hover:underline"
                  >
                    ver historia
                  </Link>
                </div>
              ) : (
                // Un listado no apunta a una persona. Decirlo es importante:
                // dejarlo en «—» haría leer un acceso al padrón como si no
                // hubiera tocado datos de nadie.
                <span className="text-texto-debil">Varios (listado)</span>
              ),
          },
          {
            key: "institucion", label: "Institución", truncar: true,
            render: (a) =>
              a.institucion_nombre ? (
                <span className="text-texto-medio">{a.institucion_nombre}</span>
              ) : (
                // Sin esto, un acceso que no se pudo atribuir se leía como del
                // hospital que figura en la barra lateral.
                <span className="text-texto-debil">No atribuido a ninguna</span>
              ),
          },
          {
            key: "tipo", label: "Qué hizo",
            render: (a) => <Badge tone={TONO_ACCESO[a.tipo] || "gray"}>{a.tipo_display}</Badge>,
          },
          {
            key: "recurso", label: "Sobre qué", orden: "recurso", envolver: true,
            render: (a) => (
              <div className="min-w-0">
                {/* El nombre humano adelante y el del modelo en el `title`: el
                    crudo sirve para rastrear en la base, no para contestarle a
                    un director. */}
                <span title={a.recurso}>{nombreRecurso(a.recurso)}</span>
                {a.tipo !== "detalle" && (
                  <div className="text-sm text-texto-debil">
                    {plural(a.resultados, "resultado", "resultados")}
                    {` · ${filtrosLegibles(a.detalle, a.institucion)}`}
                  </div>
                )}
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}

/*
 * La etiqueta va visible y al lado, no sólo como `aria-label`: dos campos de
 * fecha seguidos se ven idénticos, y «dd/mm/aaaa» no dice cuál es el desde.
 */
function Fecha({ etiqueta, valor, onChange }) {
  return (
    <label className="flex items-center gap-1.5 text-sm text-texto-debil">
      {etiqueta}
      <input
        type="date"
        value={valor}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          "h-8 rounded-md border border-campo-borde bg-superficie px-2 text-base text-texto-medio outline-none focus:border-accent",
          valor && "border-accent-100 bg-accent-50 text-accent",
        )}
      />
    </label>
  );
}
