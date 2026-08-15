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

/*
 * La fecha de nacimiento en dd/mm/aaaa, partiendo el texto.
 *
 * `fecha_nacimiento` es un DateField: llega «1974-09-11» y `new Date` lo lee
 * como medianoche UTC, que en Argentina se muestra como el 10 de septiembre. Un
 * día de menos en la fecha de nacimiento no es un detalle de formato: es el dato
 * con el que se distingue a dos pacientes del mismo apellido.
 */
function fechaCorta(iso) {
  const m = String(iso || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "";
}

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
        {/*
          El buscador encoge y el botón baja de línea. Con `w-70` fijo (280 px)
          dentro de un flex sin wrap, a 390 px la cabecera medía 432 px contra
          358 disponibles y el desborde se propagaba al contenedor de scroll de
          la app: el «+ Crear registro» quedaba cortado y para llegar a él había
          que arrastrar el panel entero de la aplicación, que se lee como
          pantalla rota. Es el mismo defecto que HistoriaDetalle ya arregló para
          su tira de pestañas.
        */}
        <div className="flex w-full flex-wrap items-center gap-2.5 sm:w-auto">
          <Buscador
            valor={texto}
            onChange={setTexto}
            placeholder="Buscar por nombre o documento…"
            className="min-w-0 flex-1 sm:w-70 sm:flex-none"
            aria-label="Buscar paciente"
          />
          <Button onClick={() => setNuevo(true)} className="whitespace-nowrap">+ Crear registro</Button>
        </div>
      </div>

      <TablaRecurso
        clave="hc"
        recurso="ciudadanos"
        exportable
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
                    {c.fecha_nacimiento ? ` · ${fechaCorta(c.fecha_nacimiento)}` : ""}
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

/*
 * El documento como se COMPARA. Espeja a `normalizar_documento` del backend.
 *
 * Sin esto el detector buscaba con el texto tal cual y después comparaba
 * `c.documento === doc`: escribir el DNI con puntos —como está impreso en el
 * documento que el administrativo tiene en la mano— no macheaba «30111222» y la
 * pantalla no avisaba nada. La defensa entera contra las dos historias clínicas
 * del mismo paciente se caía con un punto.
 */
function normalizarDocumento(valor) {
  return String(valor || "").replace(/[^0-9A-Za-z]/g, "").toUpperCase();
}

/** «Perez» y «Pérez» son el mismo apellido para quien lo escribió apurado. */
function igualSinAcentos(a, b) {
  return String(a || "").localeCompare(String(b || ""), "es", { sensitivity: "base" }) === 0;
}

function NuevoPacienteModal({ institucionId, onClose, onCreado }) {
  const toast = useToast();
  const navigate = useNavigate();
  const [f, setF] = useState({ nombre: "", apellido: "", documento: "", fecha_nacimiento: "", obra_social: "" });
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  /*
   * ¿Este paciente ya está cargado?
   *
   * El caso real es el paciente que vuelve: el administrativo lo busca por
   * apellido, no lo encuentra por un error de tipeo del ingreso anterior, y lo
   * carga de nuevo. Como la historia clínica es una por paciente, a partir de
   * ahí hay DOS historias del mismo y el médico abre una al azar: la alergia, la
   * medicación crónica y la última internación pueden estar en la otra.
   *
   * Se busca por documento mientras se escribe, antes de crear nada, y se
   * ofrece ir a la historia que ya existe. El backend también lo rechaza, pero
   * un error después de completar el formulario llega tarde y no dice adónde ir.
   */
  const doc = normalizarDocumento(f.documento);
  const posibles = useLista(
    "ciudadanos",
    { institucion: institucionId, search: doc, pageSize: 5 },
    { enabled: doc.length >= 6 },
  );
  const yaExiste = posibles.filas.find((c) => normalizarDocumento(c.documento) === doc);

  /*
   * El otro camino por el que se cuela el duplicado: el paciente que volvió y
   * la vez anterior se anotó sin documento.
   *
   * Ahí no hay documento con qué comparar, así que se avisa por apellido y
   * fecha de nacimiento. Es un AVISO y no un freno —dos personas pueden
   * compartir apellido y fecha—, pero alcanza para que el administrativo mire
   * antes de abrir una segunda historia que después no se puede fusionar.
   */
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

        {parecido && (
          <div className="rounded-md bg-badge-amber-bg px-3 py-2.5 text-md text-badge-amber-fg">
            <strong>
              {yaExiste
                ? "Ese documento ya está cargado:"
                : "Ya hay un paciente con ese apellido y esa fecha de nacimiento:"}
            </strong>{" "}
            {parecido.nombre} {parecido.apellido}
            {/* Se muestra el dato que NO se está tipeando: es con lo que se
                decide si es la misma persona o un homónimo. */}
            {yaExiste
              ? (parecido.fecha_nacimiento ? ` · ${fechaCorta(parecido.fecha_nacimiento)}` : "")
              : (parecido.documento ? ` · DNI ${parecido.documento}` : " · sin documento")}
            <div className="mt-2">
              <Button className="text-sm" onClick={() => navigate(`/historia/${parecido.id}`)}>
                ¿Es este paciente? Abrir su historia
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
