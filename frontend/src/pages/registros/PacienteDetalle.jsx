import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { resumenCobertura, usePacienteAdministrativo } from "@/components/financiadores/CoberturaAdministrativa";
import { Icon } from "@/components/icons";
import { Avatar, Button, Card, Spinner, Tabs } from "@/components/ui";
import { EstadoError, EstadoVacio, SkeletonTabla } from "@/components/ui/estados";
import { useFiltroUrl } from "@/components/ui/filtros";
import { cn } from "@/lib/cn";
import { plural } from "@/lib/format";
import HistorialCoberturaPaciente from "../financiadores/HistorialCoberturaPaciente";
import { DatosPaciente, EditarPacienteModal } from "./PadronDetalle";
import {
  Accesos, AlergiaEnCabecera, Antecedentes, AntecedentesModal, Estudios,
  Evolucion, Integridad, NuevaAtencionModal, Recetas,
} from "./HistoriaDetalle";

const TABS_CLINICAS = [
  { key: "evolucion", label: "Evolución" },
  { key: "estudios", label: "Estudios" },
  { key: "recetas", label: "Recetas" },
  { key: "cobertura", label: "Cobertura" },
  { key: "accesos", label: "Quién la miró" },
];

function fecha(iso) {
  const m = String(iso || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso;
}

export default function PacienteDetalle() {
  const { id } = useParams();
  const { puedeVer } = useInstitucion();
  const paciente = usePacienteAdministrativo(id);
  const [tab, setTab] = useFiltroUrl("tab", "datos");
  const [editando, setEditando] = useState(false);
  const clinico = puedeVer("historia_clinica");
  const tabActual = clinico && TABS_CLINICAS.some((t) => t.key === tab) ? tab : "datos";

  if (paciente.error?.status === 404) return <EstadoVacio titulo="Paciente no disponible en esta institución" detalle="Volvé al listado de pacientes de la institución actual." />;
  if (paciente.error) return <EstadoError error={paciente.error} onReintentar={paciente.refetch} />;
  if (!paciente.data) return <Spinner label="Cargando ficha..." />;

  // Esta query auditada permanece montada aunque cambie la pestaña.
  const ficha = (clinica) => (
    <Ficha
      id={id}
      c={paciente.data}
      clinico={clinico}
      clinica={clinica}
      tab={tabActual}
      setTab={setTab}
      editando={editando}
      setEditando={setEditando}
      refetch={paciente.refetch}
    />
  );
  return clinico ? <ClinicaPaciente id={id} c={paciente.data} tab={tabActual}>{ficha}</ClinicaPaciente> : ficha(null);
}

function ClinicaPaciente({ id, c, tab, children }) {
  const { roles } = useInstitucion();
  const historias = useLista("historias-clinicas", { ciudadano: id }, { enabled: !!id });
  const hc = historias.filas[0];
  const [nuevaAtencion, setNuevaAtencion] = useState(false);
  const [editandoAntecedentes, setEditandoAntecedentes] = useState(false);
  const puedeFirmar = (roles || []).some((r) => r === "medico" || r === "admin");
  const estudios = hc?.estudios || [];
  const pendientes = estudios.filter((e) => !e.realizado).length;
  const metricas = [
    { n: hc?.entradas?.length || 0, l: "consultas" },
    { n: estudios.length, l: pendientes ? `estudios · ${plural(pendientes, "pendiente", "pendientes")}` : "estudios" },
    { n: (hc?.recetas || []).filter((r) => r.activa).length, l: "recetas activas" },
    { n: hc?.entradas?.length ? new Date(hc.entradas[0].fecha).toLocaleDateString("es-AR") : "—", l: "última visita", chico: true },
  ];

  useEffect(() => {
    if (!hc || tab !== "evolucion" || !window.location.hash.startsWith("#entrada-")) return;
    requestAnimationFrame(() => document.getElementById(window.location.hash.slice(1))?.scrollIntoView({ block: "center" }));
  }, [hc, tab]);

  return children({
    hc,
    historias,
    registrar: <Button onClick={() => setNuevaAtencion(true)} disabled={historias.isLoading || !!historias.error}
      className="flex w-full items-center justify-center gap-2 sm:w-auto">
      <Icon name="plus" size={15} /> Registrar atención
    </Button>,
    alergia: <AlergiaEnCabecera hc={hc} listo={!historias.isLoading && !historias.error} />,
    metricas: <div className="mb-[22px] grid grid-cols-2 gap-3.5 sm:grid-cols-4">
      {metricas.map((m) => <Card key={m.l} className="p-[18px]">
        <div className={cn("font-extrabold leading-none", m.chico ? "text-cifra" : "text-cifra-lg")}>{m.n}</div>
        <div className="mt-1.5 text-sm text-texto-debil">{m.l}</div>
      </Card>)}
    </div>,
    contenido: historias.isLoading ? <SkeletonTabla filas={4} columnas={4} /> : historias.error ?
      <EstadoError error={historias.error} onReintentar={historias.refetch} titulo="No se pudo cargar la historia clínica" /> :
      <div className="grid items-start gap-5 lg:grid-cols-[1fr_17.5rem]">
        <div>
          {tab === "evolucion" && <Evolucion entradas={hc?.entradas || []} puedeFirmar={puedeFirmar} pacienteNombre={`${c.nombre} ${c.apellido}`.trim()} />}
          {tab === "estudios" && <Estudios estudios={estudios} />}
          {tab === "recetas" && <Recetas recetas={hc?.recetas || []} />}
          {tab === "cobertura" && <HistorialCoberturaPaciente key={id} ciudadanoId={id} />}
          {tab === "accesos" && <Accesos ciudadanoId={id} />}
        </div>
        <div className="flex flex-col gap-3.5">
          <Antecedentes hc={hc} onEditar={() => setEditandoAntecedentes(true)} />
          {hc && <Integridad hcId={hc.id} />}
        </div>
      </div>,
    modales: <>
      {nuevaAtencion && <NuevaAtencionModal ciudadanoId={id} pacienteNombre={`${c.nombre} ${c.apellido}`.trim()}
        hcId={hc?.id} puedeFirmar={puedeFirmar} onClose={() => setNuevaAtencion(false)} />}
      {editandoAntecedentes && <AntecedentesModal hc={hc} onClose={() => setEditandoAntecedentes(false)} />}
    </>,
  });
}

function Ficha({ id, c, clinico, clinica, tab, setTab, editando, setEditando, refetch }) {
  const navigate = useNavigate();
  const nombre = `${c.nombre || ""} ${c.apellido || ""}`.trim();
  const tabs = [{ key: "datos", label: "Datos" }, ...(clinico ? TABS_CLINICAS.map((t) => ({
    ...t, cuenta: t.key === "evolucion" ? clinica?.hc?.entradas?.length : t.key === "estudios" ? clinica?.hc?.estudios?.length : t.key === "recetas" ? clinica?.hc?.recetas?.length : undefined,
  })) : [])];

  return <div className="px-lg py-[22px] sm:px-[30px]">
    <div className="mb-lg flex items-center gap-2.5">
      <button onClick={() => navigate("/pacientes")} aria-label="Volver a pacientes"
        className="flex size-8 items-center justify-center rounded-md border border-borde bg-superficie text-texto-debil hover:bg-superficie-2">
        <Icon name="back" size={15} />
      </button>
      <div className="text-md text-texto-debil">Pacientes · <strong className="text-texto-suave">{nombre || "Paciente"}</strong></div>
    </div>

    <Card className="mb-[18px] flex flex-wrap items-center gap-lg px-6 py-5">
      <Avatar nombre={nombre} i={c.id} size={52} />
      <div className="min-w-0 flex-1">
        <h2 className="text-xxl font-extrabold tracking-tight">{nombre || "Sin nombre"}</h2>
        <div className="flex flex-wrap items-center gap-x-2 text-base text-texto-debil">
          <span>{c.documento ? `DNI ${c.documento}` : c.codigo || "Sin documento"}</span>
          {c.fecha_nacimiento && <span>- {fecha(c.fecha_nacimiento)}</span>}
          {resumenCobertura(c) && <span>- {resumenCobertura(c)}</span>}
        </div>
      </div>
      <div className="flex w-full flex-wrap gap-2 sm:w-auto">
        <Button variant="secondary" onClick={() => setEditando(true)}><Icon name="edit" size={15} /> Editar datos</Button>
        {clinica?.registrar}
      </div>
    </Card>
    {clinica?.alergia}
    <div className="mb-5 max-w-full overflow-x-auto">
      <Tabs tabs={tabs} valor={tab} onChange={setTab} variant="underline" className="whitespace-nowrap" />
    </div>
    {tab === "datos" ? <DatosPaciente c={c} id={id} sinHistoriaClinica={!clinico} /> : <>
      {!clinica?.historias.isLoading && !clinica?.historias.error && clinica?.metricas}
      {clinica?.contenido}
    </>}
    {editando && <EditarPacienteModal key={c.id} paciente={c} onClose={() => setEditando(false)}
      onListo={() => { setEditando(false); refetch(); }} />}
    {clinica?.modales}
  </div>;
}
