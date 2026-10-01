import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import { Shell } from "@/components/Shell";
import Accesos from "@/pages/auditoria/Accesos";
import { Avatar, Badge, Button, Field, Input, Modal, Select } from "@/components/ui";
import { Buscador, useBusquedaUrl, useFiltroUrl } from "@/components/ui/filtros";
import { TablaRecurso } from "@/components/ui/tabla";
import { useToast } from "@/components/ui/toast";
import { plural } from "@/lib/format";

const ESTADO_TONE = { activa: "green", en_alta: "amber", inactiva: "gray" };
const ROLES_INSTITUCION = [
  { value: "admin", label: "Admin de institución" },
  { value: "configurador", label: "Configurador" },
  { value: "jefe_area", label: "Jefe / Supervisor de área" },
  { value: "administrativo", label: "Administrativo" },
  { value: "enfermeria", label: "Enfermería" },
  { value: "medico", label: "Profesional de la salud" },
];


/** Listados globales dentro del armazón común, sin contexto clínico institucional. */
export default function Directorio() {
  const { puedeVer } = useInstitucion();
  const administra = puedeVer("gobierno_plataforma");
  const audita = puedeVer("auditoria");
  const [vista] = useFiltroUrl("vista", administra ? "instituciones" : "accesos");

  return (
    <Shell plataforma>
      <div className="mx-auto max-w-[1500px] p-lg sm:p-[24px]">
        {vista === "accesos" && audita ? <Accesos />
          : !administra ? <p>No tenés acceso al directorio.</p>
          : vista === "usuarios" ? <UsuariosView />
          : vista === "financiadores" ? <FinanciadoresView />
          : <InstitucionesView />}
      </div>
    </Shell>
  );
}

// --------------------------------------------------------------------------- //
function FinanciadoresView() {
  const navigate = useNavigate();
  const toast = useToast();
  const [nuevo, setNuevo] = useState(false);
  const [nombre, setNombre] = useState("");
  const [tipo, setTipo] = useState("");
  const crear = useAccion(() => api.post("/financiadores/", { nombre: nombre.trim(), tipo }), {
    invalida: ["lista", "financiadores"],
    onSuccess: (financiador) => {
      toast.ok(`Financiador «${financiador.nombre}» creado.`);
      setNuevo(false);
      navigate(`/financiadores?financiador=${financiador.id}`);
    },
    onError: (error) => toast.deError(error, "No se pudo crear el financiador."),
  });

  return <>
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="text-xl font-bold tracking-tight">Financiadores</h2>
        <p className="mt-1 text-sm text-texto-suave">Obras sociales, prepagas y mutuales con acceso a HEN.</p>
      </div>
      <Button onClick={() => setNuevo(true)} className="gap-2"><Icon name="plus" size={15} /> Nuevo financiador</Button>
    </div>
    <TablaRecurso
      clave="fin" recurso="financiadores"
      vacio={{ titulo: "Todavía no hay financiadores", detalle: "Creá el primero para configurar planes y convenios." }}
      columnas={[
        { key: "nombre", label: "Financiador", render: (f) => <strong className="text-sm">{f.nombre}</strong> },
        { key: "tipo", label: "Tipo", render: (f) => ({ obra_social: "Obra social", mutual: "Mutual", otro: "Otro financiador" })[f.tipo] || f.tipo },
        { key: "planes_activos", label: "Planes", render: (f) => <span className="tabular-nums">{f.planes_activos ?? "—"}</span> },
        { key: "convenios_vigentes", label: "Convenios", render: (f) => <span className="tabular-nums">{f.convenios_vigentes ?? "—"}</span> },
        { key: "activo", label: "Estado", render: (f) => <Badge tone={f.activo ? "green" : "gray"}>{f.activo ? "Activo" : "Inactivo"}</Badge> },
        { key: "accion", label: "", fija: true, className: "text-right", render: (f) => <Button variant="secondary" size="sm" onClick={() => navigate(`/financiadores?financiador=${f.id}`)}>Ver</Button> },
      ]}
    />
    {nuevo && <Modal title="Nuevo financiador" onClose={() => setNuevo(false)} footer={<>
      <Button variant="secondary" onClick={() => setNuevo(false)}>Cancelar</Button>
      <Button disabled={crear.isPending || !nombre.trim() || !tipo} onClick={() => crear.mutate()}>{crear.isPending ? "Creando…" : "Crear financiador"}</Button>
    </>}>
      <div className="space-y-4">
        <Field label="Nombre *"><Input value={nombre} onChange={(e) => setNombre(e.target.value)} autoFocus maxLength={160} placeholder="Nombre del financiador" /></Field>
        <Field label="Tipo *"><Select value={tipo} onChange={(e) => setTipo(e.target.value)}><option value="">Seleccioná un tipo</option><option value="obra_social">Obra social</option><option value="mutual">Mutual</option><option value="otro">Otro financiador</option></Select></Field>
      </div>
    </Modal>}
  </>;
}

// --------------------------------------------------------------------------- //
function InstitucionesView() {
  const { setInstitucion } = useInstitucion();
  const navigate = useNavigate();
  const [texto, setTexto, busqueda] = useBusquedaUrl("q");
  const [diasUrl, setDias] = useFiltroUrl("dias", "7");
  const dias = diasUrl === "30" ? "30" : "7";
  const [estado, setEstado] = useFiltroUrl("estado", "");
  const [nueva, setNueva] = useState(false);
  const resumen = useQuery({
    queryKey: ["tablero-plataforma", dias],
    queryFn: () => api.get(`/instituciones/tablero-plataforma/?dias=${dias}`),
  });
  const datos = resumen.data;
  const indicadores = Object.fromEntries((datos?.indicadores || []).map((fila) => [fila.institucion, fila]));
  const filtros = [
    { value: "", label: datos ? `Todas (${datos.instituciones})` : "Todas" },
    { value: "en_alta", label: datos ? `En puesta en marcha (${datos.en_alta})` : "En puesta en marcha" },
  ];

  function entrar(inst) {
    setInstitucion(inst);
    navigate("/inicio");
  }

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Instituciones</h2>
          <p className="mt-1 text-sm text-texto-suave">
            Estado de la red: {datos ? plural(datos.instituciones, "institución", "instituciones") : "cargando…"}
            {datos?.actualizado && ` · actualizado ${new Date(datos.actualizado).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit" })}`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-md bg-superficie-2 p-1" role="group" aria-label="Período del tablero">
            {[7, 30].map((n) => <button key={n} type="button" onClick={() => setDias(String(n))}
              aria-pressed={dias === String(n)}
              className={`rounded px-3 py-1.5 text-xs ${dias === String(n) ? "bg-superficie font-semibold text-texto shadow-card" : "text-texto-suave hover:text-texto"}`}>
              {n} días
            </button>)}
          </div>
          <Button onClick={() => setNueva(true)} className="flex items-center gap-2 whitespace-nowrap">
            <Icon name="plus" size={15} /> Nueva institución
          </Button>
        </div>
      </div>

      {resumen.isError && <div role="alert" className="mt-4 rounded-lg border border-badge-error-fg/25 bg-badge-error-bg p-3 text-sm text-badge-error-fg">
        No se pudo cargar el resumen. <button type="button" onClick={() => resumen.refetch()} className="font-semibold underline">Reintentar</button>
      </div>}

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <TarjetaMetrica titulo="Instituciones activas" valor={datos?.activas} nota={datos ? `de ${datos.instituciones} en la plataforma` : "Cargando…"} />
        <TarjetaMetrica titulo="En puesta en marcha" valor={datos?.en_alta} nota="Configuración pendiente" />
        <TarjetaMetrica titulo="Atenciones de fila" valor={datos?.atendidos} nota={`Últimos ${dias} días`} />
        <TarjetaMetrica titulo="Ocupación de camas" valor={datos?.ocupacion} sufijo=" %" nota="Camas utilizables" />
        <TarjetaMetrica titulo="Personal activo" valor={datos?.personal_activo} nota="Personas habilitadas" />
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1.6fr)_minmax(270px,1fr)]">
        <section className="rounded-lg border border-borde bg-superficie p-4" aria-labelledby="titulo-serie">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id="titulo-serie" className="text-md font-bold">Atenciones de fila por día</h2>
            <span className="text-xs text-texto-suave">Últimos {dias} días · toda la red</span>
          </div>
          <GraficoAtenciones serie={datos?.serie || []} />
        </section>
        <section className="rounded-lg border border-borde bg-superficie" aria-labelledby="titulo-alertas">
          <div className="flex items-center justify-between border-b border-division px-4 py-3">
            <h2 id="titulo-alertas" className="text-md font-bold">Requiere atención</h2>
            {datos && <Badge tone={datos.alertas.length ? "amber" : "green"}>{datos.alertas.length}</Badge>}
          </div>
          {datos?.alertas.length ? <ul className="divide-y divide-division">
            {datos.alertas.map((alerta, i) => <li key={`${alerta.institucion}-${alerta.tipo}-${i}`} className="px-4 py-3">
              <button type="button" onClick={() => { setEstado(""); setTexto(alerta.institucion); }} className="text-left text-sm font-semibold hover:text-accent">{alerta.institucion}</button>
              <div className="mt-1 text-xs text-texto-suave">{alerta.detalle}</div>
            </li>)}
          </ul> : <p className="px-4 py-5 text-sm text-texto-suave">{datos ? "No hay alertas de ocupación alta ni demoras de alta." : "Cargando alertas…"}</p>}
        </section>
      </div>

      <div className="mb-3 mt-5 flex flex-wrap items-center gap-2">
        <Buscador valor={texto} onChange={setTexto} placeholder="Buscar institución" className="w-full sm:w-64" aria-label="Buscar institución" />
        <div className="flex flex-wrap gap-1 rounded-md bg-superficie-2 p-1" role="group" aria-label="Filtrar instituciones por estado">
          {filtros.map((filtro) => <button key={filtro.value} type="button" onClick={() => setEstado(filtro.value)}
            aria-pressed={estado === filtro.value}
            className={`rounded px-3 py-1.5 text-xs ${estado === filtro.value ? "bg-superficie font-semibold text-texto shadow-card" : "text-texto-suave hover:text-texto"}`}>
            {filtro.label}
          </button>)}
        </div>
      </div>

      <TablaRecurso
        clave="inst"
        recurso="instituciones"
        params={{ search: busqueda || undefined, estado: estado || undefined }}
        ordenInicial="nombre"
        vacio={{
          titulo: busqueda ? "Ninguna institución coincide" : "No hay instituciones",
          detalle: busqueda ? "Probá con otro nombre o CUIT." : "Creá la primera para empezar.",
        }}
        columnas={[
          {
            key: "institucion", label: "Institución", orden: "nombre", truncar: true, className: "px-2 text-xs",
            render: (i) => (
              <div className="flex items-center gap-3">
                <span className="flex size-9 flex-none items-center justify-center rounded-lg bg-accent-50 text-accent">
                  <Icon name="building" size={18} />
                </span>
                <span className="min-w-0"><span className="block truncate font-semibold">{i.nombre}</span><span className="block truncate text-xs text-texto-suave">{i.tipo || i.direccion || "Institución"}</span></span>
              </div>
            ),
          },
          {
            key: "estado", label: "Estado", className: "px-2 text-xs",
            render: (i) => <Badge tone={ESTADO_TONE[i.activa === false ? "inactiva" : i.estado] || "green"}>{i.activa === false ? "Inactiva" : i.estado_display || "Activa"}</Badge>,
          },
          {
            key: "ocupacion", label: "Ocupación", className: "px-2 text-xs",
            render: (i) => indicadores[i.id]?.ocupacion == null ? <span className="text-texto-suave">—</span> : (
              <div className="min-w-[72px] text-xs tabular-nums">
                {indicadores[i.id].ocupacion} %
                <div className="mt-1 h-1 rounded-pill bg-superficie-2">
                  <div className={`h-full rounded-pill ${indicadores[i.id].ocupacion >= 90 ? "bg-danger-fuerte" : "bg-accent-fuerte"}`}
                    style={{ width: `${indicadores[i.id].ocupacion}%` }} />
                </div>
              </div>
            ),
          },
          { key: "atendidos_hoy", label: "Atendidos hoy", className: "px-2 text-xs", render: (i) => <span className="tabular-nums">{indicadores[i.id]?.atendidos_hoy ?? "—"}</span> },
          { key: "espera", label: "Espera prom.", className: "px-2 text-xs", render: (i) => <span className="tabular-nums">{indicadores[i.id]?.espera_minutos == null ? "—" : `${Math.round(indicadores[i.id].espera_minutos)} min`}</span> },
          {
            key: "accion", label: "", className: "px-2 text-right", fija: true,
            render: (i) => (
              <Button variant="secondary" onClick={() => entrar(i)} className="inline-flex h-9 items-center gap-1.5 px-lg">
                Ingresar <Icon name="enter" size={15} />
              </Button>
            ),
          },
        ]}
      />

      {nueva && <NuevaInstitucionModal onClose={() => setNueva(false)} />}
    </>
  );
}

function TarjetaMetrica({ titulo, valor, nota, sufijo = "" }) {
  return <section className="min-w-0 rounded-lg border border-borde bg-superficie p-3">
    <h2 className="truncate text-[10px] text-texto-suave" title={titulo}>{titulo}</h2>
    <p className="mt-1 text-xl font-bold tabular-nums">{valor == null ? "—" : `${new Intl.NumberFormat("es-AR").format(valor)}${sufijo}`}</p>
    <p className="mt-1 truncate text-[10px] text-texto-suave" title={nota}>{nota}</p>
  </section>;
}

function GraficoAtenciones({ serie }) {
  if (!serie.length) return <p className="flex h-[148px] items-center justify-center text-sm text-texto-suave">Cargando serie…</p>;
  const maximo = Math.max(1, ...serie.map((dia) => dia.total));
  return <div className="mt-4 flex h-[148px] items-end gap-1.5" role="img" aria-label={`Atenciones diarias: ${serie.map((dia) => `${dia.fecha}: ${dia.total}`).join(", ")}`}>
    {serie.map((dia, indice) => <div key={dia.fecha} className="flex min-w-0 flex-1 flex-col items-center justify-end gap-2">
      <span title={`${dia.fecha}: ${dia.total} atenciones`} className="w-full max-w-16 rounded-t-[3px] bg-accent-fuerte" style={{ height: `${Math.max(3, Math.round(dia.total / maximo * 106))}px` }} />
      <span className="max-w-full truncate text-[10px] text-texto-tenue">
        {(serie.length <= 7 || indice % 5 === 0 || indice === serie.length - 1)
          ? new Date(`${dia.fecha}T12:00:00`).toLocaleDateString("es-AR", { day: "2-digit", month: diasDelMes(serie) })
          : "\u00a0"}
      </span>
    </div>)}
  </div>;
}

function diasDelMes(serie) { return serie.length > 7 ? "numeric" : "short"; }

function NuevaInstitucionModal({ onClose }) {
  const toast = useToast();
  const [f, setF] = useState({ nombre: "", tipo: "", cuit: "", direccion: "", admin: "" });
  const [tipoOpcion, setTipoOpcion] = useState("");
  const [busquedaAdmin, setBusquedaAdmin] = useState("");
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  // La búsqueda permite encontrar usuarios fuera de la primera página sin
  // cargar todo el padrón de la plataforma en el diálogo.
  const { filas: usuarios, total } = useLista("usuarios", {
    is_superuser: false, search: busquedaAdmin || undefined, pageSize: 100, ordering: "apellido",
  }, { placeholderData: undefined });

  const crear = useAccion(async () => {
    const inst = await api.post("/instituciones/", {
      nombre: f.nombre.trim(), tipo: f.tipo.trim(), cuit: f.cuit.trim(), direccion: f.direccion.trim(), estado: "en_alta",
    });
    let errorAdmin = null;
    if (f.admin) {
      try {
        await api.post("/membresias/", { usuario: Number(f.admin), institucion: inst.id, rol: "admin" });
      } catch (error) {
        errorAdmin = error;
      }
    }
    return { inst, errorAdmin };
  }, {
    invalida: ["lista", "tablero-plataforma"],
    onSuccess: ({ inst, errorAdmin }) => {
      toast.ok(`Institución «${inst.nombre}» creada.`);
      if (errorAdmin) toast.deError(errorAdmin, "No se pudo asignar al administrador; la institución sí quedó creada.");
      onClose();
    },
    onError: (e) => toast.deError(e, "No se pudo crear la institución."),
  });

  return (
    <Modal
      title="Nueva institución"
      width={520}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={crear.isPending || !f.nombre.trim() || !f.tipo.trim()} onClick={() => crear.mutate()}>
            {crear.isPending ? "Creando…" : "Crear institución"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <p className="text-sm text-texto-debil">Se crea en puesta en marcha. Pasa a activa cuando completes la configuración.</p>
        <Field label="Nombre *">
          <Input value={f.nombre} onChange={(e) => set("nombre", e.target.value)} autoFocus placeholder="Hospital Zonal Sur" />
        </Field>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Tipo *" hint="Catálogo de establecimientos.">
            <Select value={tipoOpcion} onChange={(e) => {
              setTipoOpcion(e.target.value);
              set("tipo", e.target.value === "Otro" ? "" : e.target.value);
            }}>
              <option value="">— Seleccioná un tipo —</option>
              {["Hospital", "Centro de salud", "Clínica", "Sanatorio", "Otro"].map((tipo) => <option key={tipo} value={tipo}>{tipo}</option>)}
            </Select>
          </Field>
          <Field label="CUIT (opcional)">
            <Input value={f.cuit} onChange={(e) => set("cuit", e.target.value)} maxLength={20} placeholder="30-12345678-9" />
          </Field>
        </div>
        {tipoOpcion === "Otro" && <Field label="Especificá el tipo *">
          <Input value={f.tipo} onChange={(e) => set("tipo", e.target.value)} placeholder="Tipo de institución" required />
        </Field>}
        <Field label="Dirección / localidad (opcional)" hint="La ubicación se guarda como texto; provincia y localidad aún no son campos separados.">
          <Input value={f.direccion} onChange={(e) => set("direccion", e.target.value)} placeholder="Lomas de Zamora, Buenos Aires" maxLength={255} />
        </Field>
        <div>
          <label htmlFor="buscar-admin-institucion" className="mb-1.5 block text-base font-semibold text-texto-suave">Administrador de la institución (opcional)</label>
          <Input id="buscar-admin-institucion" type="search" value={busquedaAdmin} onChange={(e) => { setBusquedaAdmin(e.target.value); set("admin", ""); }} placeholder="Buscar por nombre o email" className="mb-2" />
          <Select aria-label="Seleccionar administrador" value={f.admin} onChange={(e) => set("admin", e.target.value)}>
            <option value="">— Asignar luego —</option>
            {usuarios.map((u) => (
              <option key={u.id} value={u.id}>{u.nombre_completo || u.email} · {u.email}</option>
            ))}
          </Select>
          <p className="mt-1 text-sm text-texto-tenue">También podés dejarlo pendiente y configurar usuarios después.</p>
        </div>
        {total > usuarios.length && <p className="text-sm text-texto-debil">Se muestran {usuarios.length} de {total} usuarios. Escribí más datos para acotar la búsqueda.</p>}
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------- //
function UsuariosView() {
  const [texto, setTexto, busqueda] = useBusquedaUrl("q");
  const [editando, setEditando] = useState(null);

  // Los superusuarios se excluyen EN EL SERVIDOR: descontarlos en el cliente
  // recortaba la página ya paginada y dejaba el total mal.
  const params = { is_superuser: false, search: busqueda || undefined };
  const { total } = useLista("usuarios", { ...params, pageSize: 1 });

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Usuarios</h2>
          <p className="mt-1 text-sm text-texto-suave">{plural(total, "usuario", "usuarios")} · administración de plataforma</p>
        </div>
        <Button onClick={() => setEditando({})} className="flex items-center gap-2 whitespace-nowrap">
          <Icon name="plus" size={15} /> Nuevo usuario
        </Button>
      </div>
      <div className="mb-3 mt-5">
        <Buscador
          valor={texto}
          onChange={setTexto}
          placeholder="Buscar usuario…"
          className="w-full sm:w-64"
          aria-label="Buscar usuario"
        />
      </div>

      <TablaRecurso
        clave="usr"
        recurso="usuarios"
        params={params}
        ordenInicial="apellido"
        onRowClick={(u) => setEditando(u)}
        vacio={{
          titulo: busqueda ? "Ningún usuario coincide" : "No hay usuarios",
          detalle: busqueda
            ? "Probá con otro nombre o email."
            : "Creá el primero para asignarlo como admin de una institución.",
        }}
        columnas={[
          {
            key: "usuario", label: "Usuario", orden: "apellido", truncar: true,
            render: (u) => (
              <div className="flex items-center gap-2.5">
                <Avatar nombre={u.nombre_completo || u.email} i={u.id} size={32} />
                <div className="min-w-0">
                  <div className="truncate font-semibold">{u.nombre_completo || "—"}</div>
                  <div className="truncate text-sm text-texto-debil">{u.email}</div>
                </div>
              </div>
            ),
          },
          {
            key: "is_active", label: "Estado",
            render: (u) => <Badge tone={u.is_active ? "green" : "gray"}>{u.is_active ? "Activo" : "Inactivo"}</Badge>,
          },
          {
            key: "accion", label: "", className: "text-right",
            // Decorativo: la fila entera ya abre la edición.
            render: () => <Icon name="edit" size={15} className="inline text-texto-debil" aria-hidden="true" />,
          },
        ]}
      />

      {editando && <UsuarioModal usuario={editando} onClose={() => setEditando(null)} />}
    </>
  );
}

function UsuarioModal({ usuario, onClose }) {
  const toast = useToast();
  const esNuevo = !usuario.id;
  const instituciones = useLista("instituciones", { pageSize: 200 }, { enabled: esNuevo });
  const [f, setF] = useState({
    email: usuario.email || "",
    nombre: usuario.nombre || "",
    apellido: usuario.apellido || "",
    password: "",
    confirmarPassword: "",
    institucion: "",
    rol: "medico",
    is_active: usuario.is_active ?? true,
  });
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const passwordRequerida = esNuevo || !!f.password;
  const passwordCoincide = !passwordRequerida || (f.password && f.password === f.confirmarPassword);
  const longitudValida = !passwordRequerida || f.password.length >= 8;

  const guardar = useAccion(() => {
    const payload = { email: f.email, nombre: f.nombre, apellido: f.apellido, is_active: f.is_active };
    if (f.password) payload.password = f.password;
    if (esNuevo) {
      payload.institucion = Number(f.institucion);
      payload.rol = f.rol;
    }
    return esNuevo ? api.post("/usuarios/", payload) : api.patch(`/usuarios/${usuario.id}/`, payload);
  }, {
    onSuccess: () => { toast.ok(esNuevo ? "Usuario creado." : "Usuario actualizado."); onClose(); },
    onError: (e) => toast.deError(e, "No se pudo guardar el usuario."),
  });

  return (
    <Modal
      title={esNuevo ? "Nuevo usuario" : "Editar usuario"}
      width={520}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardar.isPending || !f.email || !f.nombre || (esNuevo && (!f.apellido || !f.institucion)) || !passwordCoincide || !longitudValida} onClick={() => guardar.mutate()}>
            {guardar.isPending ? "Guardando…" : esNuevo ? "Crear usuario" : "Guardar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        {esNuevo && <p className="text-sm text-texto-debil">La persona ingresará con su email y la contraseña temporal que le indiques.</p>}
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Nombre *"><Input value={f.nombre} onChange={(e) => set("nombre", e.target.value)} /></Field>
          <Field label={esNuevo ? "Apellido *" : "Apellido"}><Input value={f.apellido} onChange={(e) => set("apellido", e.target.value)} /></Field>
        </div>
        <Field label="Email *" hint={esNuevo ? "Se usa para ingresar." : undefined}>
          <Input type="email" value={f.email} onChange={(e) => set("email", e.target.value)} autoFocus placeholder="nombre@institucion.gob.ar" autoComplete="email" />
        </Field>
        {esNuevo && <>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Institución *">
              <Select value={f.institucion} onChange={(e) => set("institucion", e.target.value)}>
                <option value="">Seleccioná una institución</option>
                {instituciones.filas.map((inst) => <option key={inst.id} value={inst.id}>{inst.nombre}</option>)}
              </Select>
            </Field>
            <Field label="Rol *"><Select value={f.rol} onChange={(e) => set("rol", e.target.value)} disabled={!f.institucion}>
              {ROLES_INSTITUCION.map((rol) => <option key={rol.value} value={rol.value}>{rol.label}</option>)}
            </Select></Field>
          </div>
          <p className="text-xs text-texto-debil">La cuenta recibe acceso a esa institución con el rol elegido.</p>
          {instituciones.error && <EstadoError error={instituciones.error} onReintentar={instituciones.refetch} titulo="No se pudieron consultar las instituciones" />}
        </>}
        <Field label={esNuevo ? "Contraseña temporal *" : "Nueva contraseña (vacío = no cambiar)"}>
          <ClaveVisible valor={f.password} onChange={(valor) => set("password", valor)} />
        </Field>
        {f.password && <FortalezaClave valor={f.password} />}
        {passwordRequerida && <Field label="Confirmar contraseña *"
          error={f.confirmarPassword && f.password !== f.confirmarPassword ? "Las contraseñas no coinciden." : undefined}>
          <ClaveVisible valor={f.confirmarPassword} onChange={(valor) => set("confirmarPassword", valor)} />
        </Field>}
        <label className="flex items-center gap-2.5 text-md">
          <input type="checkbox" checked={f.is_active} onChange={(e) => set("is_active", e.target.checked)} /> Activo
        </label>
      </div>
    </Modal>
  );
}

function ClaveVisible({ valor, onChange }) {
  const [visible, setVisible] = useState(false);
  return <div className="relative">
    <Input type={visible ? "text" : "password"} value={valor} onChange={(e) => onChange(e.target.value)} autoComplete="new-password" className="pr-12" />
    <button type="button" onClick={() => setVisible((actual) => !actual)} aria-label={visible ? "Ocultar contraseña" : "Mostrar contraseña"} aria-pressed={visible}
      className="absolute right-0 top-0 flex size-11 items-center justify-center rounded-md text-texto-debil hover:text-accent focus-visible:outline-2 focus-visible:outline-accent">
      <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M2 12s3.6-6 10-6 10 6 10 6-3.6 6-10 6S2 12 2 12Z" /><circle cx="12" cy="12" r="2.5" />
        {visible && <path d="M3 21 21 3" />}
      </svg>
    </button>
  </div>;
}

function FortalezaClave({ valor }) {
  const puntos = [valor.length >= 8, /[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]/.test(valor) && /\d/.test(valor), valor.length >= 12].filter(Boolean).length;
  const etiqueta = puntos >= 3 ? "Fuerte" : puntos === 2 ? "Buena" : "Básica";
  return <div className="space-y-1 text-xs text-texto-debil" aria-live="polite">
    <div className="flex gap-1" role="meter" aria-label="Fortaleza orientativa de la contraseña" aria-valuemin={0} aria-valuemax={3} aria-valuenow={puntos} aria-valuetext={etiqueta}>
      {[1, 2, 3].map((punto) => <span key={punto} className={`h-1 flex-1 rounded-full ${puntos >= punto ? "bg-accent" : "bg-division"}`} />)}
    </div>
    <p>Fortaleza orientativa: {etiqueta}. Mínimo 8 caracteres; evitá claves comunes o parecidas a los datos de la persona.</p>
  </div>;
}
