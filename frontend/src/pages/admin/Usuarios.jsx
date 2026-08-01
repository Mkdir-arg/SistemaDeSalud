import { useMemo, useState } from "react";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useInstitucion } from "@/auth/InstitutionContext";
import { Icon } from "@/components/icons";
import { Avatar, Badge, Button, Card, ConfirmDialog, Field, Input, Modal, Select } from "@/components/ui";
import { EstadoError, EstadoVacio, SkeletonTabla } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { plural } from "@/lib/format";

const ROLES = [
  { value: "admin", label: "Admin de institución" },
  { value: "configurador", label: "Configurador" },
  { value: "jefe_area", label: "Jefe / Supervisor de área" },
  { value: "administrativo", label: "Administrativo" },
  { value: "enfermeria", label: "Enfermería" },
  { value: "medico", label: "Médico / profesional" },
];

export default function Usuarios() {
  const { institucion } = useInstitucion();
  const [editando, setEditando] = useState(null);

  /*
   * Las personas salen de las membresías de ESTA institución.
   *
   * Antes se pedían membresías + /usuarios/ + /areas/ y se cruzaban acá; como
   * `/usuarios/` pagina de a 25, cualquier persona que no entrara en esa página
   * desaparecía de la lista aunque tuviera acceso. La membresía ya trae nombre y
   * email, así que el cruce sobra.
   */
  const membresias = useLista(
    "membresias",
    { institucion: institucion?.id, pageSize: 200 },
    { enabled: !!institucion },
  );
  const areas = useLista("areas", { institucion: institucion?.id, pageSize: 100 }, { enabled: !!institucion });

  const filas = useMemo(() => {
    const nombreArea = Object.fromEntries(areas.filas.map((a) => [a.id, a.nombre]));
    const por = new Map();
    for (const m of membresias.filas) {
      if (!por.has(m.usuario)) {
        por.set(m.usuario, {
          id: m.usuario,
          nombre: m.usuario_nombre,
          email: m.usuario_email,
          activo: m.activo,
          roles: new Set(),
          areas: new Set(),
        });
      }
      const f = por.get(m.usuario);
      f.roles.add(m.rol_display || m.rol);
      (m.areas || []).forEach((aid) => nombreArea[aid] && f.areas.add(nombreArea[aid]));
    }
    return [...por.values()]
      .map((x) => ({ ...x, roles: [...x.roles], areas: [...x.areas] }))
      .sort((a, b) => (a.nombre || a.email).localeCompare(b.nombre || b.email, "es"));
  }, [membresias.filas, areas.filas]);

  return (
    <div className="px-lg py-[26px] sm:px-[30px]">
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-lg px-[22px] py-[18px]">
          <div>
            <h1 className="text-xl font-bold">Usuarios</h1>
            <div className="text-sm text-texto-debil">
              {plural(filas.length, "persona con acceso", "personas con acceso")} al sistema
            </div>
          </div>
          <Button onClick={() => setEditando({})} className="flex items-center gap-2">
            <Icon name="plus" size={15} /> Crear usuario
          </Button>
        </div>

        {membresias.error ? (
          <EstadoError error={membresias.error} onReintentar={membresias.refetch} />
        ) : membresias.isLoading ? (
          <SkeletonTabla filas={6} columnas={5} />
        ) : filas.length === 0 ? (
          <EstadoVacio
            titulo="No hay usuarios con acceso a esta institución"
            detalle="Creá uno y asignale una membresía para que pueda entrar."
            icono="users"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-md">
              <thead className="bg-superficie-2">
                <tr>
                  {["Usuario", "Rol(es)", "Área(s)", "Estado", ""].map((h) => (
                    <th key={h} scope="col" className="whitespace-nowrap border-t border-division px-[22px] py-2.5 text-left text-sm font-semibold text-texto-debil">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filas.map((f) => (
                  <tr
                    key={f.id}
                    onClick={() => setEditando({ id: f.id, email: f.email, nombre_completo: f.nombre })}
                    tabIndex={0}
                    onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); setEditando({ id: f.id, email: f.email, nombre_completo: f.nombre }); } }}
                    className="cursor-pointer border-t border-division hover:bg-superficie-2 focus-visible:bg-superficie-2"
                  >
                    <td className="px-[22px] py-3">
                      <div className="flex min-w-0 items-center gap-2.5">
                        <Avatar nombre={f.nombre || f.email} i={f.id} size={32} />
                        <div className="min-w-0">
                          <div className="truncate font-semibold">{f.nombre || "—"}</div>
                          <div className="truncate text-sm text-texto-debil">{f.email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-[22px] py-3 text-texto-medio">{f.roles.join(" · ") || "—"}</td>
                    <td className="px-[22px] py-3 text-texto-medio">{f.areas.join(", ") || "—"}</td>
                    <td className="px-[22px] py-3">
                      <Badge tone={f.activo ? "green" : "gray"}>{f.activo ? "Activo" : "Inactivo"}</Badge>
                    </td>
                    <td className="px-[22px] py-3 text-right text-texto-debil">
                      <Icon name="edit" size={15} aria-hidden="true" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {editando && <UsuarioModal usuario={editando} onClose={() => setEditando(null)} />}
    </div>
  );
}

function UsuarioModal({ usuario, onClose }) {
  const toast = useToast();
  const esNuevo = !usuario.id;
  const [form, setForm] = useState({
    email: usuario.email || "",
    nombre: usuario.nombre || "",
    apellido: usuario.apellido || "",
    password: "",
    is_active: usuario.is_active ?? true,
  });
  const [nuevaMemb, setNuevaMemb] = useState({ institucion: "", rol: "administrativo" });
  const [aQuitar, setAQuitar] = useState(null);
  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  const instituciones = useLista("instituciones", { pageSize: 100 });
  const membresias = useLista("membresias", { usuario: usuario.id }, { enabled: !!usuario.id });

  const institucionElegida = nuevaMemb.institucion || String(instituciones.filas[0]?.id || "");

  const guardar = useAccion(
    () => {
      const payload = {
        email: form.email, nombre: form.nombre, apellido: form.apellido, is_active: form.is_active,
      };
      if (form.password) payload.password = form.password;
      return esNuevo ? api.post("/usuarios/", payload) : api.patch(`/usuarios/${usuario.id}/`, payload);
    },
    {
      onSuccess: () => { toast.ok(esNuevo ? "Usuario creado." : "Usuario actualizado."); onClose(); },
      onError: (e) => toast.deError(e, "No se pudo guardar el usuario."),
    },
  );

  const agregar = useAccion(
    () => api.post("/membresias/", {
      usuario: usuario.id, institucion: institucionElegida, rol: nuevaMemb.rol,
    }),
    {
      onSuccess: () => toast.ok("Membresía agregada."),
      onError: (e) => toast.deError(e, "No se pudo agregar la membresía."),
    },
  );

  const quitar = useAccion((m) => api.del(`/membresias/${m.id}/`), {
    onSuccess: () => { toast.ok("Membresía quitada."); setAQuitar(null); },
    onError: (e) => toast.deError(e, "No se pudo quitar la membresía."),
  });

  const nombreInst = (id) => instituciones.filas.find((i) => i.id === id)?.nombre || `#${id}`;

  return (
    <Modal
      title={esNuevo ? "Nuevo usuario" : "Editar usuario"}
      width={520}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardar.isPending || !form.email || !form.nombre} onClick={() => guardar.mutate()}>
            {guardar.isPending ? "Guardando…" : "Guardar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Email *">
          <Input type="email" value={form.email} onChange={(e) => set("email", e.target.value)} autoFocus />
        </Field>
        <div className="flex gap-3">
          <Field label="Nombre *"><Input value={form.nombre} onChange={(e) => set("nombre", e.target.value)} /></Field>
          <Field label="Apellido"><Input value={form.apellido} onChange={(e) => set("apellido", e.target.value)} /></Field>
        </div>
        <Field label={esNuevo ? "Contraseña" : "Nueva contraseña (dejar vacío para no cambiar)"}>
          <Input type="password" value={form.password} onChange={(e) => set("password", e.target.value)} />
        </Field>
        <label className="flex items-center gap-2.5 text-md">
          <input type="checkbox" checked={form.is_active} onChange={(e) => set("is_active", e.target.checked)} /> Activo
        </label>

        {/* Las membresías son lo que da acceso, así que se administran acá mismo.
            No aparecen al crear: primero tiene que existir el usuario. */}
        {!esNuevo && (
          <div className="border-t border-division pt-3.5">
            <h3 className="mb-2.5 text-base font-bold text-texto-suave">Membresías</h3>
            <div className="mb-3 flex flex-col gap-2">
              {membresias.filas.length === 0 && (
                <div className="text-base text-texto-tenue">Sin membresías: todavía no puede entrar a ninguna institución.</div>
              )}
              {membresias.filas.map((m) => (
                <div key={m.id} className="flex items-center justify-between gap-3 text-base">
                  <span>{nombreInst(m.institucion)} · <strong>{m.rol_display}</strong></span>
                  <button
                    onClick={() => setAQuitar(m)}
                    className="rounded-md px-2 py-0.5 text-sm font-semibold text-danger hover:bg-badge-error-bg"
                  >
                    Quitar
                  </button>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <Select
                value={institucionElegida}
                onChange={(e) => setNuevaMemb((p) => ({ ...p, institucion: e.target.value }))}
                aria-label="Institución de la nueva membresía"
              >
                {instituciones.filas.map((i) => <option key={i.id} value={i.id}>{i.nombre}</option>)}
              </Select>
              <Select
                value={nuevaMemb.rol}
                onChange={(e) => setNuevaMemb((p) => ({ ...p, rol: e.target.value }))}
                aria-label="Rol de la nueva membresía"
              >
                {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
              </Select>
              <Button
                variant="secondary"
                onClick={() => agregar.mutate()}
                disabled={agregar.isPending || !institucionElegida}
                className="whitespace-nowrap"
              >
                {agregar.isPending ? "…" : "+ Agregar"}
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Quitar una membresía deja a la persona sin acceso: se pregunta. */}
      {aQuitar && (
        <ConfirmDialog
          title="¿Quitar la membresía?"
          confirmar="Quitar"
          peligroso
          cargando={quitar.isPending}
          onConfirmar={() => quitar.mutate(aQuitar)}
          onClose={() => setAQuitar(null)}
        >
          Pierde el acceso a <strong>{nombreInst(aQuitar.institucion)}</strong> como{" "}
          {aQuitar.rol_display}. El usuario y su historial no se borran.
        </ConfirmDialog>
      )}
    </Modal>
  );
}
