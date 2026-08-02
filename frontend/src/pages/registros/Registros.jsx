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

// Lista de historias clínicas. El detalle vive en /historia/:id.
export default function Registros() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [texto, setTexto, busqueda] = useBusquedaUrl("q");
  // `?nuevo=1` abre el alta directo desde «Accesos rápidos».
  const [nuevo, setNuevo] = useState(params.get("nuevo") === "1");

  // La búsqueda va al servidor. Es lo más importante de esta pantalla: en un
  // hospital hay miles de pacientes y buscar dentro de los 25 de la primera
  // página significa no encontrar a casi nadie.
  const paramsLista = { institucion: institucion?.id, search: busqueda || undefined };
  const { total } = useLista("ciudadanos", { ...paramsLista, pageSize: 1 }, { enabled: !!institucion });

  return (
    <div className="px-lg py-[26px] sm:px-[30px]">
      <div className="mb-[18px] flex flex-wrap items-center justify-between gap-lg">
        <div>
          <h1 className="text-cifra font-extrabold tracking-tight">Historias clínicas</h1>
          <div className="text-sm text-texto-debil">
            {plural(total, "paciente con registro", "pacientes con registro")}
          </div>
        </div>
        <div className="flex items-center gap-2.5">
          <Buscador
            valor={texto}
            onChange={setTexto}
            placeholder="Buscar por nombre o documento…"
            className="w-70"
            aria-label="Buscar paciente"
          />
          <Button onClick={() => setNuevo(true)} className="whitespace-nowrap">+ Crear registro</Button>
        </div>
      </div>

      <TablaRecurso
        clave="hc"
        recurso="ciudadanos"
        params={paramsLista}
        ordenInicial="apellido"
        onRowClick={(c) => navigate(`/historia/${c.id}`)}
        vacio={{
          titulo: busqueda ? "Ningún paciente coincide" : "Sin pacientes",
          detalle: busqueda
            ? "Probá con el documento, o con parte del apellido."
            : "Creá el primer registro para empezar a cargar historia clínica.",
        }}
        columnas={[
          {
            key: "paciente", label: "Paciente", orden: "apellido", truncar: true,
            render: (c) => (
              <div className="flex items-center gap-3">
                <Avatar nombre={`${c.nombre} ${c.apellido}`} i={c.id} size={38} />
                <div className="min-w-0">
                  <div className="truncate font-semibold">{c.nombre} {c.apellido}</div>
                  <div className="truncate text-sm text-texto-debil">
                    {c.documento ? `DNI ${c.documento}` : c.codigo}
                    {c.fecha_nacimiento ? ` · ${new Date(c.fecha_nacimiento).toLocaleDateString("es-AR")}` : ""}
                  </div>
                </div>
              </div>
            ),
          },
          { key: "obra_social", label: "Obra social", render: (c) => c.obra_social || "—" },
          {
            key: "cond", label: "Condiciones / alergias", envolver: true,
            render: (c) => (
              <div className="flex flex-wrap gap-1.5">
                {c.condiciones && <Badge tone="amber">{c.condiciones}</Badge>}
                {/* La alergia va con símbolo Y con la palabra: el color solo no
                    alcanza para quien no lo distingue. */}
                {c.alergias && <Badge tone="error">⚠ Alergia: {c.alergias}</Badge>}
                {!c.condiciones && !c.alergias && <span className="text-texto-tenue">—</span>}
              </div>
            ),
          },
          { key: "entradas", label: "Entradas", render: (c) => <Mono>{c.entradas}</Mono> },
          {
            key: "ultima", label: "Última",
            render: (c) => (c.ultima ? new Date(c.ultima).toLocaleDateString("es-AR") : "—"),
          },
        ]}
      />

      {nuevo && (
        <NuevoPacienteModal
          institucionId={institucion?.id}
          onClose={() => setNuevo(false)}
          onCreado={(id) => navigate(`/historia/${id}`)}
        />
      )}
    </div>
  );
}

function NuevoPacienteModal({ institucionId, onClose, onCreado }) {
  const toast = useToast();
  const [f, setF] = useState({ nombre: "", apellido: "", documento: "", fecha_nacimiento: "", obra_social: "" });
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

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
          <Button disabled={crear.isPending || !f.nombre} onClick={() => crear.mutate()}>
            {crear.isPending ? "Creando…" : "Crear"}
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
        <Field label="Fecha de nacimiento"><Input type="date" value={f.fecha_nacimiento} onChange={(e) => set("fecha_nacimiento", e.target.value)} /></Field>
        <Field label="Obra social"><Input value={f.obra_social} onChange={(e) => set("obra_social", e.target.value)} placeholder="OSDE" /></Field>
      </div>
    </Modal>
  );
}
