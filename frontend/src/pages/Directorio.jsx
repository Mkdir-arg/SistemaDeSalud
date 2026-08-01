import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useAuth } from "@/auth/AuthContext";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import { Logo } from "@/components/Logo";
import { Avatar, Badge, Button, Field, Input, Modal, Mono, Select } from "@/components/ui";
import { Buscador, useBusquedaUrl, useFiltroUrl } from "@/components/ui/filtros";
import { TablaRecurso } from "@/components/ui/tabla";
import { useToast } from "@/components/ui/toast";
import { plural } from "@/lib/format";

const ESTADO_TONE = { activa: "green", en_alta: "amber", inactiva: "gray" };


const NAV = [
  { key: "instituciones", label: "Instituciones", icon: "building" },
  { key: "usuarios", label: "Usuarios", icon: "users" },
];

/**
 * Shell de plataforma: lo que ve el super admin antes de entrar a una institución.
 *
 * Tiene su propio armazón (no usa `Shell`) porque acá todavía no hay institución
 * en contexto y el menú es otro: se administra la plataforma, no un hospital.
 */
export default function Directorio() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  // En la URL: así «mandame el listado de usuarios» es un link.
  const [vista, setVista] = useFiltroUrl("vista", "instituciones");

  return (
    <div className="flex min-h-screen bg-fondo">
      <aside className="sticky top-0 flex h-screen w-60 flex-none flex-col border-r border-borde bg-superficie">
        <div className="flex items-center gap-2.5 px-[18px] pb-3.5 pt-[18px]">
          <Logo size={34} />
          <div>
            <div className="text-xl font-extrabold tracking-tight">Cauce</div>
            <div className="text-micro font-bold tracking-wider text-texto-tenue">PLATAFORMA</div>
          </div>
        </div>

        <nav className="flex flex-col gap-0.5 px-3 py-2">
          {NAV.map((n) => {
            const activo = vista === n.key;
            return (
              <button
                key={n.key}
                onClick={() => setVista(n.key)}
                aria-current={activo ? "page" : undefined}
                className={
                  "flex items-center gap-2.5 rounded-md px-3 py-2.5 text-left text-md font-semibold " +
                  (activo
                    ? "bg-accent-fuerte text-sobre-accent"
                    : "text-texto-medio hover:bg-superficie-2")
                }
              >
                <Icon name={n.icon} size={17} /> {n.label}
              </button>
            );
          })}
        </nav>

        <div className="flex-1" />

        <div className="flex items-center gap-2.5 border-t border-division p-3.5">
          <Avatar nombre={user?.nombre_completo || user?.email} size={34} />
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold">{user?.nombre_completo || user?.email}</div>
            <div className="text-xs text-texto-tenue">Super admin</div>
          </div>
          <button
            onClick={() => { logout(); navigate("/login"); }}
            aria-label="Cerrar sesión"
            title="Cerrar sesión"
            className="flex text-texto-debil hover:text-texto"
          >
            <Icon name="power" size={17} />
          </button>
        </div>
      </aside>

      <main className="flex h-screen min-w-0 flex-1 flex-col">
        <header className="flex h-16 flex-none items-center gap-lg border-b border-borde bg-superficie px-[26px]">
          {/* No es un encabezado: el título real de la página es el grande de
              abajo. Marcar los dos como heading dejaba «Instituciones» repetido
              dos veces seguidas en el índice de un lector de pantalla. */}
          <div className="text-xl font-bold">{vista === "instituciones" ? "Instituciones" : "Usuarios"}</div>
          <div className="inline-flex items-center gap-1.5 rounded-pill bg-accent-50 px-3 py-1.5 text-sm font-semibold text-accent">
            <Icon name="building" size={14} /> Alcance: todas las instituciones
          </div>
        </header>

        <div className="flex-1 overflow-auto p-[30px]">
          {vista === "instituciones" ? <InstitucionesView /> : <UsuariosView />}
        </div>
      </main>
    </div>
  );
}

/** Cabecera común de las dos vistas: título, conteo real y acciones. */
function Encabezado({ titulo, detalle, children }) {
  return (
    <div className="mb-[18px] flex flex-wrap items-center justify-between gap-lg">
      <div>
        <h1 className="text-cifraLg font-extrabold tracking-tight">{titulo}</h1>
        <div className="mt-0.5 text-base text-texto-debil">{detalle}</div>
      </div>
      <div className="flex items-center gap-2.5">{children}</div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
function InstitucionesView() {
  const { setInstitucion } = useInstitucion();
  const navigate = useNavigate();
  const [texto, setTexto, busqueda] = useBusquedaUrl("q");
  const [nueva, setNueva] = useState(false);

  // Sólo para el conteo del subtítulo: `TablaRecurso` trae su propia página.
  const { total } = useLista("instituciones", { pageSize: 1 });

  function entrar(inst) {
    setInstitucion(inst);
    navigate("/inicio");
  }

  return (
    <>
      <Encabezado
        titulo="Instituciones"
        detalle={`${plural(total, "institución", "instituciones")} en la plataforma · super admin`}
      >
        <Buscador
          valor={texto}
          onChange={setTexto}
          placeholder="Buscar institución…"
          className="w-70"
          aria-label="Buscar institución"
        />
        <Button onClick={() => setNueva(true)} className="flex items-center gap-2 whitespace-nowrap">
          <Icon name="plus" size={15} /> Nueva institución
        </Button>
      </Encabezado>

      <TablaRecurso
        clave="inst"
        recurso="instituciones"
        params={{ search: busqueda || undefined }}
        ordenInicial="nombre"
        vacio={{
          titulo: busqueda ? "Ninguna institución coincide" : "No hay instituciones",
          detalle: busqueda ? "Probá con otro nombre o CUIT." : "Creá la primera para empezar.",
        }}
        columnas={[
          {
            key: "institucion", label: "Institución", orden: "nombre", truncar: true,
            render: (i) => (
              <div className="flex items-center gap-3">
                <span className="flex size-9 flex-none items-center justify-center rounded-lg bg-accent-50 text-accent">
                  <Icon name="building" size={18} />
                </span>
                <span className="font-semibold">{i.nombre}</span>
              </div>
            ),
          },
          { key: "tipo", label: "Tipo", render: (i) => <span className="text-texto-debil">{i.tipo || "—"}</span> },
          { key: "areas_count", label: "Áreas", render: (i) => <Mono>{i.areas_count}</Mono> },
          { key: "staff", label: "Staff", render: (i) => <Mono>{i.staff}</Mono> },
          {
            key: "estado", label: "Estado",
            render: (i) => <Badge tone={ESTADO_TONE[i.estado] || "green"}>{i.estado_display || "Activa"}</Badge>,
          },
          {
            key: "accion", label: "", className: "text-right",
            render: (i) => (
              <Button onClick={() => entrar(i)} className="inline-flex h-9 items-center gap-1.5 px-lg">
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

function NuevaInstitucionModal({ onClose }) {
  const toast = useToast();
  const [f, setF] = useState({ nombre: "", tipo: "", cuit: "", admin: "" });
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  // Candidatos a admin. Se piden 100 y ordenados: con los 25 de la primera página
  // el desplegable ocultaba usuarios sin decirlo. Si aún así hay más, se avisa en
  // vez de mentir con una lista recortada.
  const { filas: usuarios, total } = useLista("usuarios", {
    is_superuser: false, pageSize: 100, ordering: "apellido",
  });

  const crear = useAccion(async () => {
    const inst = await api.post("/instituciones/", {
      nombre: f.nombre, tipo: f.tipo, cuit: f.cuit, estado: "en_alta",
    });
    if (f.admin) {
      await api.post("/membresias/", { usuario: Number(f.admin), institucion: inst.id, rol: "admin" });
    }
    return inst;
  }, {
    onSuccess: (inst) => { toast.ok(`Institución «${inst.nombre}» creada.`); onClose(); },
    onError: (e) => toast.deError(e, "No se pudo crear la institución."),
  });

  return (
    <Modal
      title="Nueva institución"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={crear.isPending || !f.nombre} onClick={() => crear.mutate()}>
            {crear.isPending ? "…" : "Crear"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Nombre *">
          <Input value={f.nombre} onChange={(e) => set("nombre", e.target.value)} autoFocus placeholder="Hospital Central" />
        </Field>
        <Field label="Tipo">
          <Input value={f.tipo} onChange={(e) => set("tipo", e.target.value)} placeholder="Hospital general" />
        </Field>
        <Field label="CUIT">
          <Input value={f.cuit} onChange={(e) => set("cuit", e.target.value)} placeholder="30-12345678-9" />
        </Field>
        <Field label="Admin de la institución">
          <Select value={f.admin} onChange={(e) => set("admin", e.target.value)}>
            <option value="">— Asignar luego —</option>
            {usuarios.map((u) => (
              <option key={u.id} value={u.id}>{u.nombre_completo || u.email} · {u.email}</option>
            ))}
          </Select>
        </Field>
        <div className="text-sm text-texto-debil">
          {total > usuarios.length
            ? `Se listan ${usuarios.length} de ${total} usuarios. Si no está el que buscás, asignalo después desde Usuarios.`
            : "El admin se gestiona desde Usuarios. Será el responsable de esta institución."}
        </div>
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
      <Encabezado
        titulo="Usuarios"
        detalle={`${plural(total, "usuario", "usuarios")} · candidatos a admin de institución`}
      >
        <Buscador
          valor={texto}
          onChange={setTexto}
          placeholder="Buscar usuario…"
          className="w-70"
          aria-label="Buscar usuario"
        />
        <Button onClick={() => setEditando({})} className="flex items-center gap-2 whitespace-nowrap">
          <Icon name="plus" size={15} /> Nuevo usuario
        </Button>
      </Encabezado>

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
  const [f, setF] = useState({
    email: usuario.email || "",
    nombre: usuario.nombre || "",
    apellido: usuario.apellido || "",
    password: "",
    is_active: usuario.is_active ?? true,
  });
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const guardar = useAccion(() => {
    const payload = { email: f.email, nombre: f.nombre, apellido: f.apellido, is_active: f.is_active };
    if (f.password) payload.password = f.password;
    return esNuevo ? api.post("/usuarios/", payload) : api.patch(`/usuarios/${usuario.id}/`, payload);
  }, {
    onSuccess: () => { toast.ok(esNuevo ? "Usuario creado." : "Usuario actualizado."); onClose(); },
    onError: (e) => toast.deError(e, "No se pudo guardar el usuario."),
  });

  return (
    <Modal
      title={esNuevo ? "Nuevo usuario" : "Editar usuario"}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardar.isPending || !f.email || !f.nombre} onClick={() => guardar.mutate()}>
            {guardar.isPending ? "…" : "Guardar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Email *">
          <Input type="email" value={f.email} onChange={(e) => set("email", e.target.value)} autoFocus placeholder="admin@institucion.gob.ar" />
        </Field>
        <div className="flex gap-3">
          <Field label="Nombre *"><Input value={f.nombre} onChange={(e) => set("nombre", e.target.value)} /></Field>
          <Field label="Apellido"><Input value={f.apellido} onChange={(e) => set("apellido", e.target.value)} /></Field>
        </div>
        <Field label={esNuevo ? "Contraseña" : "Nueva contraseña (vacío = no cambiar)"}>
          <Input type="password" value={f.password} onChange={(e) => set("password", e.target.value)} />
        </Field>
        <label className="flex items-center gap-2.5 text-md">
          <input type="checkbox" checked={f.is_active} onChange={(e) => set("is_active", e.target.checked)} /> Activo
        </label>
      </div>
    </Modal>
  );
}
