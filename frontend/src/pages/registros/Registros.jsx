import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { useAuth } from "@/auth/AuthContext";
import { AvisoCoberturaCaso, resumenCobertura, useConfiguracionCobertura } from "@/components/financiadores/CoberturaAdministrativa";
import { Avatar, Badge, Button, Field, IconButton, Input, Modal, Select } from "@/components/ui";
import { Buscador, useBusquedaUrl } from "@/components/ui/filtros";
import { TablaRecurso } from "@/components/ui/tabla";
import { useToast } from "@/components/ui/toast";
import { EstadoError } from "@/components/ui/estados";
import { plural } from "@/lib/format";
import { busquedaPaciente, normalizarDocumento, precargarPaciente } from "@/lib/paciente";

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
        </div>
      </div>
    </div>
  );
}

const columnasPadron = (abrirFicha, revelar, revelando, verAlergias) => [
  { key: "paciente", label: "Paciente", orden: "apellido", truncar: true, render: (c) => <PacienteCelda c={c} /> },
  ...(verAlergias ? [{ key: "alergias", label: "Alergias", envolver: true, render: (c) => c.alergias ? <Badge tone="error">{c.alergias}</Badge> : "—" }] : []),
  { key: "edad", label: "Edad", render: (c) => c.edad == null ? "—" : `${c.edad} años` },
  { key: "domicilio", label: "Domicilio", truncar: true, render: (c) => c.domicilio || "—" },
  { key: "cobertura", label: "Cobertura", envolver: true, render: (c) => resumenCobertura(c) || "-" },
  { key: "ultima", label: "Última atención", render: (c) => c.ultima ? fechaCorta(c.ultima) : "—" },
  {
    key: "consentimiento", label: "Consentimiento",
    render: (c) => c.consentimiento == null
      ? <span className="text-texto-tenue">Sin registro</span>
      : <Badge tone={c.consentimiento.otorgado ? "green" : "amber"}>
          {c.consentimiento.otorgado ? "Otorgado" : "Revocado"}
        </Badge>,
  },
  // Columna fija y botones compartidos, como «Ver» en Bandeja y «Editar» en
  // Usuarios: con ocho columnas, a 1440 px la acción quedaba cortada por el borde
  // de la tabla, y su estilo propio no se parecía a ninguna otra acción de fila.
  { key: "acciones", label: "Acciones", fija: true, render: (c) => <div className="flex items-center gap-2">
    <Button variant="secondary" size="sm" onClick={(e) => { e.stopPropagation(); abrirFicha(c); }}
      onKeyDown={(e) => e.stopPropagation()}>
      Ver ficha
    </Button>
    <IconButton icon="eye" variant="soft" size="sm" disabled={revelando === c.id}
      onClick={(e) => { e.stopPropagation(); revelar(c); }}
      onKeyDown={(e) => e.stopPropagation()}
      label={`Revelar datos de ${nombreCompleto(c)}`}
      title="Revelar datos completos; esta consulta queda auditada"
      className="disabled:opacity-50"
    />
  </div> },
];

export default function Registros() {
  const toast = useToast();
  const { institucion, puedeVer } = useInstitucion();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [texto, setTexto, busqueda] = useBusquedaUrl("q");
  const [exportando, setExportando] = useState(false);
  const [motivoExportacion, setMotivoExportacion] = useState("");
  const [varianteExportacion, setVarianteExportacion] = useState("minimizado");
  const [descargando, setDescargando] = useState(false);
  const [revelado, setRevelado] = useState(null);
  const [revelando, setRevelando] = useState(null);
  const peticionRevelado = useRef(0);

  const nuevo = params.get("nuevo") === "1";
  const terminoBusqueda = busquedaPaciente(busqueda);
  const paramsLista = { institucion: institucion?.id, search: terminoBusqueda || undefined };
  useEffect(() => {
    peticionRevelado.current += 1;
    setRevelado(null);
    setRevelando(null);
    return () => { peticionRevelado.current += 1; };
  }, [user?.id, institucion?.id, busqueda, params.toString()]);
  const { total } = useLista("ciudadanos", { ...paramsLista, pageSize: 1 }, {
    enabled: !!institucion,
    queryKey: ["lista", "ciudadanos", user?.id, institucion?.id, "total", terminoBusqueda],
    placeholderData: undefined,
    gcTime: 0,
  });

  async function exportar() {
    setDescargando(true);
    try {
      await api.downloadPost("/ciudadanos/exportar/", {
        institucion: institucion.id,
        search: terminoBusqueda || "",
        ordering: params.get("padron_ord") || "apellido",
        variante: varianteExportacion,
        motivo: motivoExportacion.trim(),
      }, `pacientes-${varianteExportacion}.csv`);
      toast.ok("Exportación registrada y descargada.");
      setExportando(false);
      setMotivoExportacion("");
    } catch (error) {
      toast.deError(error, "No se pudo exportar el padrón.");
    } finally {
      setDescargando(false);
    }
  }

  async function revelar(c) {
    const intento = ++peticionRevelado.current;
    setRevelando(c.id);
    try {
      const datos = await api.get(`/ciudadanos/${c.id}/?institucion=${institucion.id}`);
      if (peticionRevelado.current === intento) setRevelado({ ...datos, nombre: nombreCompleto(c) });
    } catch (error) {
      if (peticionRevelado.current === intento) toast.deError(error, "No se pudieron revelar los datos.");
    } finally {
      if (peticionRevelado.current === intento) setRevelando(null);
    }
  }

  if (nuevo) return <NuevoPaciente
    key={`${user?.id}:${institucion?.id}`}
    institucionId={institucion?.id}
    busquedaInicial={params.get("q") || ""}
    onClose={() => navigate("/pacientes")}
    onCreado={(id) => navigate(`/pacientes/${id}`)}
  />;

  return (
    <div className="px-lg py-[26px] sm:px-[30px]">
      <div className="mb-[18px] flex flex-wrap items-center justify-between gap-lg">
        <div>
          <h2 className="text-cifra font-extrabold tracking-tight">
            Pacientes
          </h2>
          <div className="text-sm text-texto-debil">
            {plural(total, "persona registrada", "personas registradas")}
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
          <Button onClick={() => navigate(`/pacientes?nuevo=1${texto ? `&q=${encodeURIComponent(texto)}` : ""}`)} className="whitespace-nowrap">+ Registrar paciente</Button>
          <Button variant="secondary" onClick={() => setExportando(true)} className="whitespace-nowrap">Exportar…</Button>
        </div>
      </div>

      <p className="mb-4 rounded-md border border-accent-100 bg-accent-50 px-4 py-2.5 text-sm text-texto-suave">
        Por tu rol, el documento, la fecha de nacimiento y el domicilio se muestran parcialmente. Revelar los datos completos queda registrado en el registro de accesos.
      </p>

      <TablaRecurso
        key={`${user?.id}:${institucion?.id}`}
        clave="padron"
        recurso="ciudadanos"
        params={paramsLista}
        ambitoConsulta={[user?.id, institucion?.id]}
        opcionesConsulta={{ gcTime: 0, placeholderData: undefined, enabled: !!institucion?.id }}
        ordenInicial="apellido"
        onRowClick={(c) => navigate(`/pacientes/${c.id}`)}
        vacio={{
          titulo: busqueda ? "Ningún paciente coincide" : "Sin pacientes",
          detalle: busqueda
            ? "Probá con el documento, o con parte del apellido."
            : "Creá el primer registro administrativo del padrón.",
        }}
        columnas={columnasPadron((c) => navigate(`/pacientes/${c.id}`), revelar, revelando, puedeVer("historia_clinica"))}
      />

      {revelado && <Modal title={`Datos de ${revelado.nombre}`} onClose={() => setRevelado(null)} footer={
        <Button variant="secondary" onClick={() => setRevelado(null)}>Cerrar</Button>
      }>
        <dl className="grid gap-4 sm:grid-cols-2">
          <div><dt className="text-sm text-texto-debil">DNI</dt><dd className="font-semibold">{revelado.documento || "Sin documento"}</dd></div>
          <div><dt className="text-sm text-texto-debil">Fecha de nacimiento</dt><dd className="font-semibold">{fechaCorta(revelado.fecha_nacimiento) || "Sin registrar"}</dd></div>
          <div className="sm:col-span-2"><dt className="text-sm text-texto-debil">Domicilio</dt><dd className="font-semibold">{revelado.domicilio || "Sin registrar"}</dd></div>
        </dl>
      </Modal>}

      {exportando && <Modal title="Exportar pacientes" onClose={() => !descargando && setExportando(false)} footer={<>
        <Button variant="secondary" disabled={descargando} onClick={() => setExportando(false)}>Volver</Button>
        <Button disabled={descargando || motivoExportacion.trim().length < 10 || motivoExportacion.trim().length > 500}
          onClick={exportar}>{descargando ? "Preparando…" : "Registrar y descargar"}</Button>
      </>}>
        <div className="flex flex-col gap-4">
          <p className="text-base text-texto-debil">
            Institución: <strong>{institucion?.nombre}</strong>. Se exportan todos los resultados de la búsqueda actual,
            sin limitarse a la página visible. La descarga queda asentada en el registro de accesos.
          </p>
          <Field label="Datos incluidos">
            <Select value={varianteExportacion} onChange={(e) => setVarianteExportacion(e.target.value)}>
              <option value="minimizado">Padrón minimizado: referencia, iniciales, últimos 4 del documento, año y consentimiento</option>
              {puedeVer("historia_clinica") && <option value="identificado">Padrón identificado: datos personales y domicilio</option>}
              {puedeVer("historia_clinica") && <option value="clinico">Resumen clínico: condiciones, alergias y actividad</option>}
            </Select>
          </Field>
          <Field label="Motivo de la exportación *"
            hint="Entre 10 y 500 caracteres. Quedará visible para quienes auditan los accesos.">
            <Input value={motivoExportacion} onChange={(e) => setMotivoExportacion(e.target.value)} maxLength={500} />
          </Field>
        </div>
      </Modal>}

    </div>
  );
}

function igualSinAcentos(a, b) {
  return String(a || "").localeCompare(String(b || ""), "es", { sensitivity: "base" }) === 0;
}

function NuevoPaciente({ institucionId, busquedaInicial, onClose, onCreado }) {
  const toast = useToast();
  const { user } = useAuth();
  const configuracion = useConfiguracionCobertura(institucionId);
  const configuracionLista = typeof configuracion.data?.habilitada === "boolean" && !configuracion.error;
  const navigate = useNavigate();
  const [f, setF] = useState(() => ({ ...precargarPaciente(busquedaInicial), fecha_nacimiento: "", domicilio: "", obra_social: "" }));
  const nombreRef = useRef(null);
  const documentoRef = useRef(null);
  useEffect(() => {
    // Al abrir el alta, enfocamos el campo precargado.
    const id = requestAnimationFrame(() => (f.documento ? documentoRef : nombreRef).current?.focus());
    return () => cancelAnimationFrame(id);
  }, []);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const doc = normalizarDocumento(f.documento);
  const posibles = useLista(
    "ciudadanos",
    { institucion: institucionId, documento: doc, pageSize: 5 },
    {
      enabled: doc.length >= 6,
      queryKey: ["lista", "ciudadanos", user?.id, institucionId, "documento", doc],
      placeholderData: undefined,
      gcTime: 0,
    },
  );
  const yaExiste = posibles.filas[0];

  const apellido = f.apellido.trim();
  const homonimos = useLista(
    "ciudadanos",
    { institucion: institucionId, search: apellido, fecha_nacimiento: f.fecha_nacimiento, pageSize: 10 },
    {
      enabled: !yaExiste && apellido.length >= 3 && !!f.fecha_nacimiento,
      queryKey: ["lista", "ciudadanos", user?.id, institucionId, "homonimos", apellido, f.fecha_nacimiento],
      placeholderData: undefined,
      gcTime: 0,
    },
  );
  const mismaPersona =
    !yaExiste &&
    homonimos.filas.find(
      (c) =>
        igualSinAcentos(c.apellido, apellido),
    );
  const parecido = yaExiste || mismaPersona;

  const crear = useAccion(
    () => {
      const { obra_social, ...datos } = f;
      return api.post("/ciudadanos/", {
        institucion: institucionId,
        ...datos,
        ...(!configuracion.data.habilitada ? { obra_social } : {}),
        fecha_nacimiento: f.fecha_nacimiento || null,
      });
    },
    {
      onSuccess: (c) => { toast.ok("Registro creado."); onCreado(c.id); },
      onError: (e) => toast.deError(e, "No se pudo crear el registro."),
    },
  );

  const acciones = <>
    <Button variant="secondary" onClick={onClose}>Cancelar</Button>
    <Button disabled={crear.isPending || !f.nombre.trim() || !!yaExiste || !configuracionLista} onClick={() => crear.mutate()}>
      {crear.isPending ? "Registrando…" : "Registrar paciente"}
    </Button>
  </>;

  const formulario = <div className="grid gap-4 lg:grid-cols-2 lg:items-start">
    <section className="rounded-lg border border-borde bg-superficie p-5">
      <h3 className="mb-4 text-base font-bold">Identidad</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Documento (opcional para NN)">
          <Input ref={documentoRef} value={f.documento} onChange={(e) => set("documento", e.target.value)} placeholder="Número de documento" />
        </Field>
        <Field label="Fecha de nacimiento">
          <Input type="date" value={f.fecha_nacimiento} onChange={(e) => set("fecha_nacimiento", e.target.value)} />
        </Field>
        <Field label="Nombre *"><Input ref={nombreRef} value={f.nombre} onChange={(e) => set("nombre", e.target.value)} /></Field>
        <Field label="Apellido"><Input value={f.apellido} onChange={(e) => set("apellido", e.target.value)} /></Field>
      </div>
      {parecido && <div className="mt-4 rounded-md bg-badge-amber-bg px-3 py-2.5 text-md text-badge-amber-fg">
        <strong>{yaExiste ? "Ese documento ya está cargado:" : "Ya hay un paciente con ese apellido y esa fecha de nacimiento:"}</strong>{" "}
        {parecido.nombre} {parecido.apellido}
        {parecido.documento ? ` · DNI ${parecido.documento}` : ""}
        <div className="mt-2"><Button variant="secondary" className="text-sm" onClick={() => navigate(`/pacientes/${parecido.id}`)}>Abrir este paciente</Button></div>
      </div>}
    </section>
    <div className="grid gap-4">
      <section className="rounded-lg border border-borde bg-superficie p-5">
        <h3 className="mb-4 text-base font-bold">Contacto y domicilio</h3>
        <Field label="Domicilio (opcional)">
          <Input value={f.domicilio} onChange={(e) => set("domicilio", e.target.value)} placeholder="Calle y número" maxLength={255} />
        </Field>
      </section>
      <section className="rounded-lg border border-borde bg-superficie p-5">
        <h3 className="mb-4 text-base font-bold">Cobertura declarada</h3>
        {configuracion.error ? <EstadoError error={configuracion.error} onReintentar={configuracion.refetch} titulo="No se pudo consultar la configuración de cobertura" />
          : !configuracionLista ? <p className="text-sm text-texto-debil" role="status">Consultando la configuración de cobertura…</p>
            : configuracion.data.habilitada ? <AvisoCoberturaCaso /> : <Field label="Financiador (opcional)" hint="La cobertura se verifica al iniciar un caso.">
              <Input value={f.obra_social} onChange={(e) => set("obra_social", e.target.value)} placeholder="Nombre declarado por el paciente" />
            </Field>}
      </section>
    </div>
  </div>;

  return <div className="px-lg py-[26px] sm:px-[30px]">
    <div className="mx-auto max-w-5xl">
      <h2 className="text-cifra font-extrabold tracking-tight">Registrar paciente</h2>
      <p className="mb-5 text-sm text-texto-debil">Primero buscamos en el padrón para evitar duplicar registros.</p>
      <p className="mb-5 rounded-md border border-accent-100 bg-accent-50 px-4 py-2.5 text-sm text-texto-suave">
        {doc.length >= 6 && posibles.isFetching ? "Buscando coincidencias por documento…"
          : yaExiste ? "Ese documento ya corresponde a un paciente de esta institución. Abrí su ficha para continuar."
            : doc.length >= 6 ? "No se encontró ese documento en el padrón de esta institución."
              : "Ingresá el documento para buscar pacientes registrados antes del alta."}
      </p>
      {formulario}
      <div className="mt-5 flex justify-end gap-2">{acciones}</div>
    </div>
  </div>;

}
