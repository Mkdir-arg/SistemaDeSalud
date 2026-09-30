import { useState } from "react";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { useAuth } from "@/auth/AuthContext";
import CoberturaAdministrativa, { AvisoCoberturaCaso } from "@/components/financiadores/CoberturaAdministrativa";
import { Badge, Button, Card, Field, Input, Modal, Mono, Textarea } from "@/components/ui";
import { EstadoError } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { fechaHora } from "@/lib/format";

function fecha(iso) {
  if (!iso) return "-";
  const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : String(iso);
}

function Dato({ label, children }) {
  return (
    <div>
      <div className="text-sm font-semibold uppercase tracking-wider text-texto-tenue">{label}</div>
      <div className="mt-1 min-h-6 text-md font-semibold text-texto-suave">{children || "-"}</div>
    </div>
  );
}

export function DatosPaciente({ c, id, sinHistoriaClinica }) {
  return (
      <div className="grid items-start gap-5 lg:grid-cols-[1fr_22rem]">
        <div className="flex flex-col gap-5">
          <Card className="p-5">
            <h2 className="mb-4 text-xs font-bold uppercase tracking-wider text-texto-debil">
              Datos administrativos
            </h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <Dato label="Documento">{c.documento || "Sin documento"}</Dato>
              <Dato label="Código">{c.codigo ? <Mono>{c.codigo}</Mono> : "-"}</Dato>
              <Dato label="Fecha de nacimiento">{fecha(c.fecha_nacimiento)}</Dato>
              <Dato label="Domicilio">{c.domicilio || "-"}</Dato>
              <Dato label="Alta en padrón">{fechaHora(c.creado)}</Dato>
            </div>
          </Card>
          <CoberturaAdministrativa paciente={c} />
        </div>

        <div className="flex flex-col gap-3.5">
          <Consentimiento ciudadanoId={id} estado={c.consentimiento} />
          {sinHistoriaClinica && <Card className="p-4 text-sm text-texto-debil">
            Esta ficha no muestra evolución, alergias, estudios ni recetas. Para consultar datos clínicos se requiere permiso de historia clínica.
          </Card>}
        </div>
      </div>
  );
}

export function EditarPacienteModal({ paciente, onClose, onListo }) {
  const toast = useToast();
  const coberturaHabilitada = paciente.cobertura_administrativa?.habilitada === true;
  const [f, setF] = useState({
    nombre: paciente.nombre || "",
    apellido: paciente.apellido || "",
    documento: paciente.documento || "",
    fecha_nacimiento: paciente.fecha_nacimiento || "",
    obra_social: paciente.obra_social || "",
    domicilio: paciente.domicilio || "",
  });
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const guardar = useAccion(
    () => {
      const { obra_social, ...datos } = f;
      return api.patch(`/ciudadanos/${paciente.id}/`, {
        ...datos,
        ...(!coberturaHabilitada ? { obra_social } : {}),
        fecha_nacimiento: f.fecha_nacimiento || null,
      });
    },
    {
      invalida: ["lista", "detalle"],
      onSuccess: () => { toast.ok("Datos actualizados."); onListo(); },
      onError: (e) => toast.deError(e, "No se pudo actualizar el padrón."),
    },
  );

  return (
    <Modal
      title="Editar datos administrativos"
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardar.isPending || !f.nombre.trim()} onClick={() => guardar.mutate()}>
            {guardar.isPending ? "Guardando..." : "Guardar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Nombre *"><Input value={f.nombre} onChange={(e) => set("nombre", e.target.value)} autoFocus /></Field>
          <Field label="Apellido"><Input value={f.apellido} onChange={(e) => set("apellido", e.target.value)} /></Field>
        </div>
        <Field label="Documento"><Input value={f.documento} onChange={(e) => set("documento", e.target.value)} /></Field>
        <Field label="Fecha de nacimiento"><Input type="date" value={f.fecha_nacimiento || ""} onChange={(e) => set("fecha_nacimiento", e.target.value)} /></Field>
        {coberturaHabilitada ? <AvisoCoberturaCaso /> : (
          <Field label="Cobertura declarada (sin verificar)"><Input value={f.obra_social} onChange={(e) => set("obra_social", e.target.value)} /></Field>
        )}
        <Field label="Domicilio"><Input value={f.domicilio} onChange={(e) => set("domicilio", e.target.value)} /></Field>
      </div>
    </Modal>
  );
}

export const MODO = { escrito: "Escrito", verbal: "Verbal", digital: "Digital" };

function Consentimiento({ ciudadanoId, estado }) {
  const toast = useToast();
  const [pidiendo, setPidiendo] = useState(null);
  const [historial, setHistorial] = useState(false);
  const sinRegistro = estado == null;

  return (
    <Card className="p-[18px]">
      <h2 className="mb-3 text-xs font-bold uppercase tracking-wider text-texto-debil">
        Consentimiento de datos
      </h2>

      {sinRegistro ? (
        <div className="text-md text-texto-debil">
          Sin registro de consentimiento.{" "}
          <span className="text-texto-medio">No consta que se haya pedido; no es lo mismo que una negativa.</span>
        </div>
      ) : (
        <>
          <Badge tone={estado.otorgado ? "green" : "amber"}>
            {estado.otorgado ? "Otorgado" : "Revocado"}
          </Badge>
          <div className="mt-2 text-sm text-texto-debil">
            {fechaHora(estado.momento)}
            {estado.modo ? ` - ${MODO[estado.modo] || estado.modo}` : ""}
          </div>
          {estado.alcance && (
            <div className="mt-1 text-sm text-texto-medio">
              <span className="text-texto-debil">{estado.otorgado ? "Alcance: " : "Motivo de la revocación: "}</span>
              {estado.alcance}
            </div>
          )}
          <button
            onClick={() => setHistorial((v) => !v)}
            className="mt-2 text-sm font-semibold text-accent hover:underline"
          >
            {historial ? "Ocultar historial" : "Ver historial"}
          </button>
          {historial && <HistorialConsentimientos ciudadanoId={ciudadanoId} />}
        </>
      )}

      <div className="mt-3.5 flex flex-wrap gap-2">
        {(sinRegistro || !estado.otorgado) && (
          <Button className="text-sm" onClick={() => setPidiendo("otorgar")}>Registrar consentimiento</Button>
        )}
        {!sinRegistro && estado.otorgado && (
          <Button variant="secondary" className="text-sm" onClick={() => setPidiendo("revocar")}>
            Registrar revocación
          </Button>
        )}
      </div>

      <div className="mt-3 text-xs text-texto-debil">
        La atención de urgencia no depende del consentimiento. Acá se deja constancia, no se bloquea nada.
      </div>

      {pidiendo && (
        <ConsentimientoModal
          ciudadanoId={ciudadanoId}
          otorgar={pidiendo === "otorgar"}
          referidoId={estado?.id}
          onClose={() => setPidiendo(null)}
          onListo={() => { toast.ok("Consentimiento registrado."); setPidiendo(null); }}
        />
      )}
    </Card>
  );
}

function HistorialConsentimientos({ ciudadanoId }) {
  const toast = useToast();
  const q = useLista("consentimientos", { ciudadano: ciudadanoId, pageSize: 50 });

  async function descargar(c) {
    try {
      await api.download(`/consentimientos/${c.id}/evidencia/`, `consentimiento-${c.id}`);
    } catch (error) {
      toast.deError(error, "No se pudo descargar la evidencia.");
    }
  }

  if (q.isLoading) return <div className="mt-2 text-sm text-texto-debil">Buscando historial...</div>;
  if (q.error) return <EstadoError error={q.error} onReintentar={q.refetch} />;
  if (!q.filas.length) return <div className="mt-2 text-sm text-texto-debil">Sin registros.</div>;

  return (
    <><ol className="mt-2.5 flex flex-col gap-2.5 border-t border-division pt-2.5">
      {q.filas.map((c) => (
        <li key={c.id} className="text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={c.otorgado ? "green" : "amber"}>{c.otorgado ? "Otorgado" : "Revocado"}</Badge>
            <span className="text-texto-debil">{fechaHora(c.momento)}</span>
          </div>
          <div className="mt-0.5 text-texto-debil">
            {c.modo_display || MODO[c.modo] || c.modo}
            {c.tomado_por_nombre ? ` - lo tomo ${c.tomado_por_nombre}` : ""}
          </div>
          {c.alcance && <div className="text-texto-medio">{c.otorgado ? "Alcance: " : "Motivo: "}{c.alcance}</div>}
          {c.version_texto && <div className="text-texto-debil">Versión del texto: {c.version_texto}</div>}
          {c.texto_comunicado && <div className="whitespace-pre-wrap text-texto-debil">Texto comunicado: {c.texto_comunicado}</div>}
          {c.motivo_revocacion && <div className="text-texto-debil">Motivo de revocación: {c.motivo_revocacion}</div>}
          {c.evidencia ? <button onClick={() => descargar(c)} className="font-semibold text-accent underline">
            Descargar evidencia
          </button> : !c.version_texto && <div className="text-texto-tenue">Evidencia anterior sin versión ni adjunto.</div>}
        </li>
      ))}
    </ol>
    {q.total > q.filas.length && <div className="mt-2 text-xs text-texto-debil">
      Se muestran los {q.filas.length} más recientes de {q.total}.
    </div>}</>
  );
}

export function ConsentimientoModal({ ciudadanoId, otorgar, referidoId, onClose, onListo }) {
  const toast = useToast();
  const { user } = useAuth();
  const [modo, setModo] = useState("");
  const [alcance, setAlcance] = useState("");
  const [version, setVersion] = useState("");
  const [texto, setTexto] = useState("");
  const [motivo, setMotivo] = useState("");
  const [archivo, setArchivo] = useState(null);
  const exigeArchivo = otorgar && ["escrito", "digital"].includes(modo);
  const archivoValido = !archivo || archivo.size <= 10 * 1024 * 1024;
  const valido = modo && alcance.trim() && archivoValido &&
    (otorgar
      ? version.trim() && (modo !== "verbal" || texto.trim()) && (!exigeArchivo || archivo)
      : motivo.trim() && referidoId);

  const guardar = useAccion(
    () => {
      const datos = new FormData();
      datos.append("ciudadano", String(ciudadanoId));
      datos.append("otorgado", String(otorgar));
      datos.append("modo", modo);
      datos.append("alcance", alcance.trim());
      if (otorgar) {
        datos.append("version_texto", version.trim());
        if (texto.trim()) datos.append("texto_comunicado", texto.trim());
      } else {
        datos.append("motivo_revocacion", motivo.trim());
        datos.append("consentimiento_referido", String(referidoId));
      }
      if (archivo) datos.append("evidencia_archivo", archivo);
      return api.multipart("/consentimientos/", datos);
    },
    {
      invalida: ["lista", "detalle"],
      onSuccess: onListo,
      onError: (e) => toast.deError(e, "No se pudo registrar el consentimiento."),
    },
  );

  return (
    <Modal
      title={otorgar ? "Registrar consentimiento" : "Registrar revocación"}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancelar</Button>
          <Button disabled={guardar.isPending || !valido} onClick={() => guardar.mutate()}>
            {guardar.isPending ? "Registrando..." : "Registrar"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <Field label="Tipo y alcance *" hint="Describí qué tratamiento de datos se consintió o se revoca.">
          <Textarea
            value={alcance}
            onChange={(e) => setAlcance(e.target.value)}
            placeholder="Describí el alcance comunicado"
          />
        </Field>
        <fieldset>
          <legend className="mb-2 text-sm font-semibold text-texto-suave">Método *</legend>
          <div className="grid gap-2">
            {Object.entries(MODO).map(([valor, etiqueta]) => <label key={valor}
              className="flex cursor-pointer items-start gap-2.5 rounded-md border border-borde bg-superficie px-3 py-2.5 text-sm hover:border-accent-100">
              <input type="radio" name="metodo-consentimiento" value={valor} checked={modo === valor}
                onChange={() => { setModo(valor); setArchivo(null); }} className="mt-0.5 accent-accent" />
              <span><strong className="block text-texto-suave">{etiqueta}</strong>
                <span className="text-texto-debil">{valor === "verbal" ? "Transcribí el texto comunicado." : "Adjuntá el documento aceptado."}</span>
              </span>
            </label>)}
          </div>
        </fieldset>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Fecha y hora"><Input value="Se asigna al registrar" readOnly /></Field>
          <Field label="Responsable"><Input value={user?.nombre_completo || user?.email || "Sesión actual"} readOnly /></Field>
        </div>
        {otorgar ? <>
          <Field label="Versión del texto comunicado *" hint="Identificador real del documento o texto usado; no se genera automáticamente.">
            <Input value={version} onChange={(e) => setVersion(e.target.value)} maxLength={100} />
          </Field>
          {modo === "verbal" && <Field label="Texto comunicado verbalmente *">
            <Textarea value={texto} onChange={(e) => setTexto(e.target.value)} />
          </Field>}
        </> : <Field label="Motivo de la revocación *">
          <Textarea value={motivo} onChange={(e) => setMotivo(e.target.value)} />
        </Field>}
        {modo && <Field label={exigeArchivo ? "Documento de evidencia *" : "Evidencia adjunta (opcional)"}
          hint="PDF o imagen JPEG, PNG o WebP, hasta 10 MiB.">
          <Input key={modo} type="file" accept=".pdf,.jpg,.jpeg,.png,.webp" onChange={(e) => setArchivo(e.target.files?.[0] || null)} />
        </Field>}
        {!archivoValido && <p role="alert" className="text-sm text-badge-error-fg">El archivo supera los 10 MiB permitidos.</p>}
      </div>
    </Modal>
  );
}
