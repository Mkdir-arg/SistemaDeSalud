import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Avatar, Badge, Button, Field, Input, Modal, Mono } from "@/components/ui";
import { Buscador, useBusquedaUrl } from "@/components/ui/filtros";
import { TablaRecurso } from "@/components/ui/tabla";
import { useToast } from "@/components/ui/toast";
import { plural } from "@/lib/format";

function fechaCorta(iso) {
  const m = String(iso || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "";
}

function nombreCompleto(c) {
  return `${c?.nombre || ""} ${c?.apellido || ""}`.trim();
}

function PacienteCelda({ c }) {
  return (
    <div className="flex items-center gap-3">
      <Avatar nombre={nombreCompleto(c)} i={c.id} size={38} />
      <div className="min-w-0">
        <div className="truncate font-semibold">{nombreCompleto(c) || "Sin nombre"}</div>
        <div className="truncate text-sm text-texto-debil">
          {c.documento ? `DNI ${c.documento}` : c.codigo || "Sin documento"}
          {c.fecha_nacimiento ? ` - ${fechaCorta(c.fecha_nacimiento)}` : ""}
        </div>
      </div>
    </div>
  );
}

const columnasHistoria = [
  { key: "paciente", label: "Paciente", orden: "apellido", truncar: true, render: (c) => <PacienteCelda c={c} /> },
  { key: "obra_social", label: "Obra social", render: (c) => c.obra_social || "-" },
  {
    key: "cond", label: "Condiciones / alergias", envolver: true,
    render: (c) => (
      <div className="flex flex-wrap gap-1.5">
        {c.condiciones && <Badge tone="amber">{c.condiciones}</Badge>}
        {c.alergias && <Badge tone="error">Alergia: {c.alergias}</Badge>}
        {!c.condiciones && !c.alergias && <span className="text-texto-tenue">-</span>}
      </div>
    ),
  },
  { key: "entradas", label: "Entradas", render: (c) => <Mono>{c.entradas}</Mono> },
  { key: "ultima", label: "Última", render: (c) => (c.ultima ? new Date(c.ultima).toLocaleDateString("es-AR") : "-") },
];

const columnasPadron = [
  { key: "paciente", label: "Paciente", orden: "apellido", truncar: true, render: (c) => <PacienteCelda c={c} /> },
  { key: "obra_social", label: "Cobertura", render: (c) => c.obra_social || "-" },
  { key: "domicilio", label: "Domicilio", truncar: true, render: (c) => c.domicilio || "-" },
  {
    key: "consentimiento", label: "Consentimiento",
    render: (c) => c.consentimiento == null
      ? <span className="text-texto-tenue">Sin registro</span>
      : <Badge tone={c.consentimiento.otorgado ? "green" : "amber"}>
          {c.consentimiento.otorgado ? "Otorgado" : "Revocado"}
        </Badge>,
  },
];

export default function Registros({ modo = "historia" }) {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [texto, setTexto, busqueda] = useBusquedaUrl("q");
  const [nuevo, setNuevo] = useState(params.get("nuevo") === "1");

  const esPadron = modo === "padron";
  const detalleBase = esPadron ? "/padron" : "/historia";
  const paramsLista = { institucion: institucion?.id, search: busqueda || undefined };
  const { total } = useLista("ciudadanos", { ...paramsLista, pageSize: 1 }, { enabled: !!institucion });

  return (
    <div className="px-lg py-[26px] sm:px-[30px]">
      <div className="mb-[18px] flex flex-wrap items-center justify-between gap-lg">
        <div>
          <h1 className="text-cifra font-extrabold tracking-tight">
            {esPadron ? "Padrón de pacientes" : "Historias clínicas"}
          </h1>
          <div className="text-sm text-texto-debil">
            {esPadron
              ? plural(total, "persona registrada", "personas registradas")
              : plural(total, "paciente con registro", "pacientes con registro")}
          </div>
        </div>
        <div className="flex w-full flex-wrap items-center gap-2.5 sm:w-auto">
          <Buscador
            valor={texto}
            onChange={setTexto}
            placeholder="Buscar por nombre o documento..."
            className="min-w-0 flex-1 sm:w-70 sm:flex-none"
            aria-label="Buscar paciente"
          />
          <Button onClick={() => setNuevo(true)} className="whitespace-nowrap">+ Crear registro</Button>
        </div>
      </div>

      <TablaRecurso
        clave={esPadron ? "padron" : "hc"}
        recurso="ciudadanos"
        exportable
        params={paramsLista}
        ordenInicial="apellido"
        onRowClick={(c) => navigate(`${detalleBase}/${c.id}`)}
        vacio={{
          titulo: busqueda ? "Ningún paciente coincide" : "Sin pacientes",
          detalle: busqueda
            ? "Probá con el documento, o con parte del apellido."
            : esPadron
              ? "Creá el primer registro administrativo del padrón."
              : "Creá el primer registro para empezar a cargar historia clínica.",
        }}
        columnas={esPadron ? columnasPadron : columnasHistoria}
      />

      {nuevo && (
        <NuevoPacienteModal
          institucionId={institucion?.id}
          modo={modo}
          onClose={() => setNuevo(false)}
          onCreado={(id) => navigate(`${detalleBase}/${id}`)}
        />
      )}
    </div>
  );
}

function normalizarDocumento(valor) {
  return String(valor || "").replace(/[^0-9A-Za-z]/g, "").toUpperCase();
}

function igualSinAcentos(a, b) {
  return String(a || "").localeCompare(String(b || ""), "es", { sensitivity: "base" }) === 0;
}

function NuevoPacienteModal({ institucionId, modo, onClose, onCreado }) {
  const toast = useToast();
  const navigate = useNavigate();
  const [f, setF] = useState({ nombre: "", apellido: "", documento: "", fecha_nacimiento: "", obra_social: "" });
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const destinoBase = modo === "padron" ? "/padron" : "/historia";

  const doc = normalizarDocumento(f.documento);
  const posibles = useLista(
    "ciudadanos",
    { institucion: institucionId, search: doc, pageSize: 5 },
    { enabled: doc.length >= 6 },
  );
  const yaExiste = posibles.filas.find((c) => normalizarDocumento(c.documento) === doc);

  const apellido = f.apellido.trim();
  const homonimos = useLista(
    "ciudadanos",
    { institucion: institucionId, search: apellido, pageSize: 10 },
    { enabled: !yaExiste && apellido.length >= 3 && !!f.fecha_nacimiento },
  );
  const mismaPersona =
    !yaExiste &&
    homonimos.filas.find(
      (c) =>
        c.fecha_nacimiento === f.fecha_nacimiento &&
        igualSinAcentos(c.apellido, apellido),
    );
  const parecido = yaExiste || mismaPersona;

  const crear = useAccion(
    () =>
      api.post("/ciudadanos/", {
        institucion: institucionId,
        ...f,
        fecha_nacimiento: f.fecha_nacimiento || null,
      }),
    {
      onSuccess: (c) => { toast.ok("Registro creado."); onCreado(c.id); },
      onError: (e) => toast.deError(e, "No se pudo crear el registro."),
    },
  );

  return (
    <Modal
      title="Nuevo registro de paciente"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={crear.isPending || !f.nombre || !!yaExiste} onClick={() => crear.mutate()}>
            {crear.isPending ? "Creando..." : "Crear"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <div className="flex gap-3">
          <Field label="Nombre *"><Input value={f.nombre} onChange={(e) => set("nombre", e.target.value)} autoFocus /></Field>
          <Field label="Apellido"><Input value={f.apellido} onChange={(e) => set("apellido", e.target.value)} /></Field>
        </div>
        <Field label="Documento"><Input value={f.documento} onChange={(e) => set("documento", e.target.value)} placeholder="27418305" /></Field>

        {parecido && (
          <div className="rounded-md bg-badge-amber-bg px-3 py-2.5 text-md text-badge-amber-fg">
            <strong>
              {yaExiste
                ? "Ese documento ya está cargado:"
                : "Ya hay un paciente con ese apellido y esa fecha de nacimiento:"}
            </strong>{" "}
            {parecido.nombre} {parecido.apellido}
            {yaExiste
              ? (parecido.fecha_nacimiento ? ` - ${fechaCorta(parecido.fecha_nacimiento)}` : "")
              : (parecido.documento ? ` - DNI ${parecido.documento}` : " - sin documento")}
            <div className="mt-2">
              <Button className="text-sm" onClick={() => navigate(`${destinoBase}/${parecido.id}`)}>
                Abrir este paciente
              </Button>
            </div>
          </div>
        )}
        <Field label="Fecha de nacimiento"><Input type="date" value={f.fecha_nacimiento} onChange={(e) => set("fecha_nacimiento", e.target.value)} /></Field>
        <Field label="Obra social"><Input value={f.obra_social} onChange={(e) => set("obra_social", e.target.value)} placeholder="OSDE" /></Field>
      </div>
    </Modal>
  );
}
