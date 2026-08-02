import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import { Button, Field, Input, Modal, Mono } from "@/components/ui";
import { Buscador, useBusquedaUrl } from "@/components/ui/filtros";
import { TablaRecurso } from "@/components/ui/tabla";
import { useToast } from "@/components/ui/toast";

// Lista de formularios. El constructor vive en /formularios/:id.
export default function Formularios() {
  const { institucion } = useInstitucion();
  const navigate = useNavigate();
  const [texto, setTexto, busqueda] = useBusquedaUrl("q");
  const [nuevo, setNuevo] = useState(false);

  return (
    <div className="px-lg py-[26px] sm:px-[30px]">
      <div className="mb-[18px] flex flex-wrap items-center justify-between gap-lg">
        <div>
          <h1 className="text-cifra-lg font-extrabold tracking-tight">Formularios</h1>
          <div className="mt-0.5 text-base text-texto-debil">
            Definí los campos que los flujos piden en cada paso.
          </div>
        </div>
        <div className="flex items-center gap-2.5">
          <Buscador valor={texto} onChange={setTexto} placeholder="Buscar formulario…" className="w-64" aria-label="Buscar formulario" />
          <Button onClick={() => setNuevo(true)} className="flex items-center gap-2 whitespace-nowrap">
            <Icon name="plus" size={15} /> Nuevo formulario
          </Button>
        </div>
      </div>

      <TablaRecurso
        clave="forms"
        recurso="formularios"
        params={{ institucion: institucion?.id, search: busqueda || undefined }}
        ordenInicial="titulo"
        onRowClick={(f) => navigate(`/formularios/${f.id}`)}
        vacio={{
          titulo: busqueda ? "Ningún formulario coincide" : "No hay formularios",
          detalle: busqueda ? "Probá con otro título." : "Creá el primero para que los flujos tengan qué pedir.",
          accion: !busqueda && <Button onClick={() => setNuevo(true)}>Nuevo formulario</Button>,
        }}
        columnas={[
          {
            key: "titulo", label: "Formulario", orden: "titulo", truncar: true,
            render: (f) => (
              <div className="flex items-center gap-2.5">
                <span className="flex size-9 flex-none items-center justify-center rounded-md bg-accent-50 text-accent">
                  <Icon name="form" size={17} />
                </span>
                <span className="truncate font-semibold">{f.titulo}</span>
              </div>
            ),
          },
          { key: "campos", label: "Campos", render: (f) => <Mono>{f.campos?.length || 0}</Mono> },
          {
            key: "vinculados", label: "Vinculados",
            render: (f) => <Mono>{(f.campos || []).filter((c) => c.origen).length}</Mono>,
          },
          {
            key: "descripcion", label: "Descripción", truncar: true,
            render: (f) => <span className="text-texto-debil">{f.descripcion || "—"}</span>,
          },
        ]}
      />

      {nuevo && (
        <NuevoFormModal
          institucionId={institucion?.id}
          onClose={() => setNuevo(false)}
          onCreated={(id) => navigate(`/formularios/${id}`)}
        />
      )}
    </div>
  );
}

function NuevoFormModal({ institucionId, onClose, onCreated }) {
  const toast = useToast();
  const [titulo, setTitulo] = useState("");

  const crear = useAccion(() => api.post("/formularios/", { institucion: institucionId, titulo }), {
    onSuccess: (f) => onCreated(f.id),
    onError: (e) => toast.deError(e, "No se pudo crear el formulario."),
  });

  return (
    <Modal
      title="Nuevo formulario"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={crear.isPending || !titulo} onClick={() => crear.mutate()}>
            {crear.isPending ? "…" : "Crear y diseñar"}
          </Button>
        </>
      }
    >
      <Field label="Título *">
        <Input value={titulo} onChange={(e) => setTitulo(e.target.value)} autoFocus placeholder="Datos del paciente" />
      </Field>
    </Modal>
  );
}
