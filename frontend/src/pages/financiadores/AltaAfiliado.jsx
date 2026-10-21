import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "@/api/client";
import { errorFinanciador, filasDe, opcionesFinanciador, rutaFinanciador } from "@/api/financiadores";
import { useAuth } from "@/auth/AuthContext";
import { Ayuda, Button, Card, Field, Input, Modal, Select, Spinner, Textarea } from "@/components/ui";
import { EstadoVacio } from "@/components/ui/estados";
import { useToast } from "@/components/ui/toast";
import { Shell } from "@/components/Shell";
import { cn } from "@/lib/cn";
import { normalizarDocumento } from "@/lib/paciente";
import { NOMBRE_SISTEMA } from "@/lib/marca";
import { parametrosFicha, parametrosListado } from "@/lib/padronNavigation";
import { borrarBorradorAlta, guardarBorradorAlta, leerBorradorAlta } from "@/lib/borradorAlta";
import { CAMPOS_ALTA, PASOS, camposDelPaso, cuerpoAlta, datosIniciales, formatoCuit, obligatoriosCompletos, pasoConDatos, pasoDeCampo, requerido, tieneDatos, validarPaso } from "@/lib/altaAfiliado";
import { REGIMENES } from "@/components/financiadores/padronCampos";
import { ROLES, itemsFinanciador } from "./menuFinanciador";

const REVISION = PASOS.length - 1;
const ETIQUETAS_ESTADO = { completo: "Completo", actual: "En curso", revisar: "Revisar", pendiente: "Pendiente" };
const fecha = (valor) => valor ? String(valor).slice(0, 10).split("-").reverse().join("/") : "—";
const idCampo = (name) => `alta-${name}`;

export default function AltaAfiliado() {
  const { user } = useAuth();
  const [parametros] = useSearchParams();
  const plataforma = Boolean(user.is_superuser || Object.values(user.capacidades_por_institucion || {}).some((caps) => caps.includes("gobierno_plataforma")));
  const organizaciones = useQuery({ queryKey: ["financiadores", user.id, "organizaciones"], queryFn: async () => {
    const filas = [];
    for (let page = 1; ; page += 1) {
      const data = await api.get(`/financiadores/?page=${page}`);
      filas.push(...filasDe(data));
      if (!data.next) return filas;
    }
  }, gcTime: 0 });
  const seleccion = parametros.get("financiador");
  const organizacion = seleccion ? organizaciones.data?.find((item) => String(item.id) === seleccion) : plataforma ? null : organizaciones.data?.[0];
  const id = organizacion?.id;
  const volver = `/financiadores/padron?${parametrosListado(parametros, id || seleccion || "")}`;
  const menu = itemsFinanciador({ organizacion, plataforma, admin: plataforma || organizacion?.rol === "admin", sufijo: seleccion ? `?financiador=${encodeURIComponent(seleccion)}` : "" })
    .map((item) => item.key === "padron" ? { ...item, to: volver, end: false } : item);
  const puede = plataforma || ["admin", "operador"].includes(organizacion?.rol);
  const planes = useQuery({ queryKey: ["financiadores", user.id, id, "opciones-planes"], queryFn: () => opcionesFinanciador(id, "planes"), enabled: Boolean(id && puede), gcTime: 0 });

  if (plataforma && !seleccion && !organizaciones.isLoading && !organizaciones.error) return <Navigate to="/directorio?vista=financiadores" replace />;

  return <Shell plataforma={plataforma} financiador={{ nombre: organizacion?.nombre || NOMBRE_SISTEMA, titulo: "Nueva afiliación", rol: ROLES[organizacion?.rol] || "Financiador", items: menu }}><div className="mx-auto max-w-[72rem] space-y-5 p-lg sm:p-[30px] xl:p-[40px]">
    <div className="flex items-center justify-between gap-4 text-sm">
      <nav aria-label="Ubicación" className="min-w-0 text-texto-debil">{organizacion?.nombre && <>{organizacion.nombre} / </>}<Link className="hover:underline" to={volver}>Padrón de afiliados</Link> / <span aria-current="page">Nueva afiliación</span></nav>
      <Link className="ml-auto shrink-0 font-medium text-accent hover:underline" to={volver}>← Volver al padrón</Link>
    </div>
    {organizaciones.isLoading || planes.isLoading ? <Spinner label="Cargando…" />
      : organizaciones.error || planes.error ? <ErrorCarga error={organizaciones.error || planes.error} reintentar={() => (organizaciones.error ? organizaciones : planes).refetch()} />
      : !organizacion ? <Card><EstadoVacio titulo="No tenés acceso al financiador seleccionado" /></Card>
      : !puede ? <Card><EstadoVacio titulo="No tenés permiso para registrar afiliaciones" detalle="Pedile a la administración de tu organización el permiso de operación." /></Card>
      : <FormularioAlta key={`${user.id}:${id}`} usuarioId={user.id} organizacion={organizacion} planes={(planes.data || []).filter((plan) => plan.activo !== false)} parametros={parametros} volver={volver} />}
  </div></Shell>;
}

function ErrorCarga({ error, reintentar }) {
  return <div role="alert" className="rounded-md bg-badge-error-bg p-4 text-badge-error-fg"><p>{errorFinanciador(error)}</p><Button className="mt-3" size="sm" variant="secondary" onClick={reintentar}>Reintentar</Button></div>;
}

function FormularioAlta({ usuarioId, organizacion, planes, parametros, volver }) {
  const navigate = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  const [borradorInicial] = useState(() => leerBorradorAlta(usuarioId, organizacion.id));
  const [datos, setDatos] = useState(() => ({ ...datosIniciales(), ...borradorInicial?.datos }));
  const [paso, setPaso] = useState(() => Math.min(Math.max(Number(borradorInicial?.paso) || 0, 0), REVISION));
  const [visitados, setVisitados] = useState(() => new Set(borradorInicial?.visitados || [0]));
  const [errores, setErrores] = useState({});
  const [conErrores, setConErrores] = useState(() => new Set());
  const [errorServidor, setErrorServidor] = useState(null);
  const [desdeRevision, setDesdeRevision] = useState(false);
  const [confirmarSalida, setConfirmarSalida] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [duplicado, setDuplicado] = useState({ documento: "", id: null, verificando: false });
  const resumenRef = useRef(null);
  const tituloRef = useRef(null);
  const montado = useRef(false);
  const registrando = useRef(false);
  const completos = obligatoriosCompletos(datos);

  // Autoguardado: recargar la página o volver más tarde retoma el alta.
  useEffect(() => {
    if (!montado.current) { montado.current = true; return; }
    if (tieneDatos(datos)) guardarBorradorAlta(usuarioId, organizacion.id, { datos, paso, visitados: [...visitados] });
  }, [datos, paso, visitados, usuarioId, organizacion.id]);

  function cambiar(name, valor) {
    setDatos((previo) => ({ ...previo, [name]: valor }));
  }

  // Los errores se recalculan sólo con «Siguiente» o «Registrar». Field cambia de
  // estructura con y sin error: limpiarlo al escribir remonta el input y pierde el
  // foco, y limpiarlo al salir mueve el layout y se come el clic en «Siguiente».

  async function verificarDocumento(documento = datos.documento) {
    const valor = String(documento || "").trim();
    if (!valor) { setDuplicado({ documento: "", id: null, verificando: false }); return null; }
    if (duplicado.documento === valor && !duplicado.verificando) return duplicado.id;
    setDuplicado({ documento: valor, id: null, verificando: true });
    try {
      // Coincidencia exacta por índice único (financiador, documento): una fila como máximo.
      const data = await api.get(`${rutaFinanciador(organizacion.id, "padron")}?${new URLSearchParams({ documento: valor, page_size: 1 })}`);
      const existente = filasDe(data).find((fila) => normalizarDocumento(fila.documento) === normalizarDocumento(valor))?.id ?? null;
      setDuplicado({ documento: valor, id: existente, verificando: false });
      return existente;
    } catch {
      // Si la consulta falla, el servidor vuelve a validar el duplicado al registrar.
      setDuplicado({ documento: valor, id: null, verificando: false });
      return null;
    }
  }

  // `existente` llega de la verificación recién esperada: el estado `duplicado`
  // de este render todavía no la refleja.
  function erroresDe(i, existente = duplicado.documento === String(datos.documento || "").trim() ? duplicado.id : null) {
    const propios = validarPaso(i, datos);
    if (i === 0 && existente && !propios.documento) propios.documento = "duplicado";
    return propios;
  }

  function enfocar(ref) { requestAnimationFrame(() => ref.current?.focus()); }

  function mostrarErrores(i, propios) {
    setErrores(propios);
    setConErrores((previo) => new Set(previo).add(i));
    setPaso(i);
    enfocar(resumenRef);
  }

  function ir(destino) {
    setErrores({}); setErrorServidor(null);
    setVisitados((previo) => new Set(previo).add(destino));
    setPaso(destino);
    enfocar(tituloRef);
  }

  async function validarActual() {
    if (paso === REVISION) return {};
    return paso === 0 ? erroresDe(0, await verificarDocumento()) : erroresDe(paso);
  }

  async function siguiente() {
    const propios = await validarActual();
    if (Object.keys(propios).length) { mostrarErrores(paso, propios); return; }
    setConErrores((previo) => { const nuevo = new Set(previo); nuevo.delete(paso); return nuevo; });
    if (desdeRevision) { setDesdeRevision(false); ir(REVISION); return; }
    ir(paso + 1);
  }

  async function registrar() {
    // Ref y no estado: un doble clic entra dos veces antes del próximo render.
    if (registrando.current) return;
    registrando.current = true;
    const existente = await verificarDocumento();
    // Valida todo lo cargado; el primer paso con errores es donde se aterriza.
    for (let i = 0; i < REVISION; i += 1) {
      const propios = i === 0 ? erroresDe(0, existente) : erroresDe(i);
      if (Object.keys(propios).length) { registrando.current = false; mostrarErrores(i, propios); return; }
    }
    setEnviando(true); setErrorServidor(null);
    let resultado;
    try { resultado = await api.post(rutaFinanciador(organizacion.id, "padron"), cuerpoAlta(datos)); }
    catch (err) {
      registrando.current = false;
      setEnviando(false);
      setErrorServidor(err);
      const campos = Object.keys(err?.data && typeof err.data === "object" ? err.data : {});
      const destino = campos.map(pasoDeCampo).filter((i) => i != null).sort()[0];
      if (destino != null) { setConErrores((previo) => new Set(previo).add(destino)); setPaso(destino); }
      enfocar(resumenRef);
      return;
    }
    borrarBorradorAlta(usuarioId, organizacion.id);
    await Promise.all([qc.invalidateQueries({ queryKey: ["financiadores", usuarioId, organizacion.id] }), qc.invalidateQueries({ queryKey: ["financiador", usuarioId, organizacion.id] })]);
    toast.ok("Afiliación registrada. Queda con el trámite pendiente: completá la documentación y la credencial desde la ficha.");
    navigate(`/financiadores/padron/${resultado.id}?${parametrosFicha(parametros, organizacion.id, Number(parametros.get("padron_page") || 1))}`);
  }

  function guardarYSalir() {
    guardarBorradorAlta(usuarioId, organizacion.id, { datos, paso, visitados: [...visitados] });
    toast.ok("Borrador guardado. Lo retomás desde «Registrar afiliación».");
    navigate(volver);
  }

  function descartar() {
    borrarBorradorAlta(usuarioId, organizacion.id);
    navigate(volver);
  }

  function estadoPaso(i) {
    if (i === paso) return "actual";
    if (conErrores.has(i)) return "revisar";
    if (i === REVISION || !visitados.has(i)) return "pendiente";
    if (PASOS[i].obligatorio) return Object.keys(validarPaso(i, datos)).length ? "revisar" : "completo";
    return pasoConDatos(i, datos) && !Object.keys(validarPaso(i, datos)).length ? "completo" : "pendiente";
  }

  const fichaDuplicado = duplicado.id ? `/financiadores/padron/${duplicado.id}?${parametrosFicha(parametros, organizacion.id, Number(parametros.get("padron_page") || 1))}` : null;
  const listaErrores = Object.entries(errores).map(([name, mensaje]) => ({ name, label: CAMPOS_ALTA.find((c) => c.name === name)?.label || name, mensaje: mensaje === "duplicado" ? "ya existe un afiliado con este documento." : mensaje }));
  const opcional = paso > 1 && paso < REVISION;
  const campo = (name) => CAMPOS_ALTA.find((c) => c.name === name);
  const props = { datos, errores, errorServidor, cambiar };
  const controles = (nombres) => nombres.map(campo).filter((c) => !c.visible || c.visible(datos)).map((c) => <Control key={c.name} campo={c} {...props} />);

  return <>
    <div>
      <h1 className="text-cifra font-bold">Registrar afiliación</h1>
      <p className="mt-1 text-sm text-texto-suave">{paso === REVISION ? "Revisá los datos antes de registrar. Podés editar cualquier bloque." : "Completá los datos obligatorios (*) para registrar el alta. El resto podés cargarlo ahora o después desde la ficha del afiliado."}</p>
    </div>
    {borradorInicial?.guardado && <p role="status" className="rounded-md bg-superficie-2 p-3 text-sm">Retomaste el borrador guardado el {new Date(borradorInicial.guardado).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" })}. <button type="button" className="font-medium text-accent underline" onClick={() => setConfirmarSalida(true)}>Descartar borrador</button></p>}

    <Stepper paso={paso} estadoPaso={estadoPaso} alcanzable={(i) => (visitados.has(i) || completos) && !enviando} completos={completos} ir={(i) => { setDesdeRevision(false); ir(i); }} />

    {(listaErrores.length > 0 || errorServidor) && <div ref={resumenRef} tabIndex={-1} role="alert" className="rounded-lg border border-badge-error-fg/30 bg-badge-error-bg p-4 text-badge-error-fg outline-none">
      {listaErrores.length > 0 ? <>
        <p className="font-semibold">Revisá {listaErrores.length === 1 ? "1 campo" : `${listaErrores.length} campos`} antes de continuar</p>
        <ul className="mt-1 list-disc pl-5 text-sm">{listaErrores.map((e) => <li key={e.name}><a className="hover:underline" href={`#${idCampo(e.name)}`} onClick={(ev) => { ev.preventDefault(); document.getElementById(idCampo(e.name))?.focus(); }}>{e.label}: {e.mensaje} →</a></li>)}</ul>
      </> : <p>{errorFinanciador(errorServidor)}</p>}
    </div>}

    <fieldset disabled={enviando} className="min-w-0">
      {paso === REVISION ? <Revision datos={datos} planes={planes} editar={(i) => { setDesdeRevision(true); ir(i); }} /> : <Card className="space-y-5 p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 ref={tituloRef} tabIndex={-1} className="text-xl font-bold outline-none">{paso + 1}. {PASOS[paso].titulo}</h2>
          <p className="text-sm text-texto-debil">{opcional ? "Paso opcional" : <><Asterisco /> Campo obligatorio</>}</p>
        </div>

        {paso === 0 && <Grilla>{camposDelPaso(0, datos).map((c) => <Control key={c.name} campo={c} {...props}
          onBlur={c.name === "documento" ? () => verificarDocumento() : undefined}
          mensaje={c.name === "documento" && (errores.documento === "duplicado" || (duplicado.id && duplicado.documento === String(datos.documento || "").trim()))
            ? <>Ya existe un afiliado con este documento. <Link className="font-medium underline" to={fichaDuplicado}>Abrir su ficha →</Link></> : undefined} />)}</Grilla>}

        {paso === 1 && <>
          <div className="rounded-md border border-borde bg-superficie-2 p-4">
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-2 font-semibold"><input id={idCampo("cobertura_habilitada")} type="checkbox" checked={datos.cobertura_habilitada !== false} onChange={(event) => cambiar("cobertura_habilitada", event.target.checked)} className="size-4 accent-accent" />Habilitar cobertura junto con el registro</label>
              <Ayuda etiqueta="Ayuda sobre habilitación de cobertura">Las prestaciones siguen sujetas al plan, las fechas y las reglas de cobertura. Desmarcá esta opción si necesitás registrar a la persona sin habilitar cobertura.</Ayuda>
            </div>
            {datos.cobertura_habilitada === false && <p className="mt-2 text-sm text-texto-debil">Se guardará sólo el registro administrativo. Podés habilitar cobertura más adelante desde la ficha, con motivo del cambio.</p>}
          </div>
          <Grilla>{["plan", "desde", "delegacion", "motivo"].map((name) => <Control key={name} campo={campo(name)} {...props}
            opciones={name === "plan" ? planes.map((plan) => ({ id: plan.id, nombre: plan.nombre })) : undefined}
            hint={name === "plan" && !planes.length ? datos.cobertura_habilitada === false ? "Podés registrar sin plan y asignarlo más adelante." : "No hay planes activos. Creá uno en Planes o registrá sin habilitar cobertura." : undefined} />)}</Grilla>
          <Seccion titulo="Grupo familiar" detalle="Indicá si la persona es titular o se suma al grupo de otro afiliado.">
            <fieldset><legend className="mb-1.5 text-base font-semibold text-texto-suave">La persona es <Asterisco /></legend>
              <div className="flex flex-wrap gap-6">{[["titular", "Titular"], ["familiar", "Familiar de un titular existente"]].map(([valor, label]) => <label key={valor} className="flex items-center gap-2 text-md"><input type="radio" name="alta-grupo" value={valor} checked={datos.grupo === valor} onChange={() => cambiar("grupo", valor)} className="size-4 accent-accent" />{label}</label>)}</div>
            </fieldset>
            {datos.grupo === "familiar" && <Grilla>
              <BuscadorTitular organizacion={organizacion} seleccionado={datos.titular_sel} error={errores.titular || errorCampo(errorServidor, "titular")} onElegir={(fila) => { cambiar("titular", fila?.id ?? ""); cambiar("titular_sel", fila); if (fila) setErrores((previo) => { const resto = { ...previo }; delete resto.titular; return resto; }); }} />
              <Control campo={campo("parentesco")} {...props} />
            </Grilla>}
          </Seccion>
        </>}

        {paso === 2 && <>
          <Seccion titulo="Contacto">
            <Grilla>{controles(["telefono", "email", "celular"])}</Grilla>
            {!datos.otro_telefono && !datos.celular && <button type="button" className="text-sm font-semibold text-accent hover:underline" onClick={() => cambiar("otro_telefono", true)}>+ Agregar otro teléfono</button>}
          </Seccion>
          <Seccion titulo="Domicilio" detalle="Provincia, partido y localidad se cargan como texto.">
            <Grilla>{controles(["provincia", "partido", "localidad", "codigo_postal", "calle", "altura", "piso", "departamento"])}</Grilla>
          </Seccion>
        </>}

        {paso === 3 && <>
          <Grilla>{controles(["regimen"])}</Grilla>
          {datos.regimen === "dependencia" && <Seccion titulo="Datos del empleador"><Grilla>{controles(["cuit_empleador", "empleador", "actividad_laboral", "telefono_laboral", "email_laboral", "domicilio_laboral"])}</Grilla></Seccion>}
          {datos.regimen === "desempleo" && <Seccion titulo="Subsidio por desempleo"><Grilla>{controles(["subsidio_desde", "subsidio_hasta"])}</Grilla></Seccion>}
          {datos.regimen && !["dependencia", "desempleo"].includes(datos.regimen) && <p className="text-sm text-texto-debil">{REGIMENES[datos.regimen]}: sin datos adicionales.</p>}
        </>}
      </Card>}
    </fieldset>

    <Card className="flex flex-wrap items-center justify-between gap-4 px-6 py-4">
      <div className="flex min-w-0 flex-1 items-center gap-4">
        <Button type="button" variant="ghost" className="font-semibold text-accent" disabled={enviando} onClick={() => tieneDatos(datos) ? setConfirmarSalida(true) : navigate(volver)}>Cancelar</Button>
        <p className="min-w-[12rem] flex-1 text-sm text-texto-debil">{paso === REVISION ? "Al registrar, el afiliado queda en estado «Trámite pendiente» y podés gestionar la credencial desde su ficha."
          : opcional ? "Paso opcional: podés seguir sin completarlo o registrar el alta ahora."
          : paso === 0 ? "«Registrar» se habilita al completar los pasos 1 y 2. Los pasos 3 y 4 son opcionales."
          : "Al tocar «Siguiente» se valida solo este paso. El foco va al primer error."}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {paso === 0 && <Button type="button" variant="secondary" disabled={enviando || !tieneDatos(datos)} onClick={guardarYSalir}>Guardar borrador</Button>}
        {paso > 0 && <Button type="button" variant="secondary" disabled={enviando} onClick={() => { setDesdeRevision(false); ir(paso - 1); }}>← Anterior</Button>}
        {opcional && completos && <Button type="button" variant="secondary" disabled={enviando} onClick={registrar}>{enviando ? "Registrando…" : "Registrar ahora"}</Button>}
        {paso === REVISION
          ? <Button type="button" disabled={enviando || !completos} onClick={registrar}>{enviando ? "Registrando…" : "Registrar afiliación"}</Button>
          : <Button type="button" disabled={enviando} onClick={siguiente}>{desdeRevision ? "Volver a revisión →" : `Siguiente: ${PASOS[paso + 1].corto || PASOS[paso + 1].titulo} →`}</Button>}
      </div>
    </Card>

    {confirmarSalida && <ConfirmarDescarte pasos={[...visitados].filter((i) => i < REVISION).length} onSeguir={() => setConfirmarSalida(false)} onGuardar={guardarYSalir} onDescartar={descartar} />}
  </>;
}

function Stepper({ paso, estadoPaso, alcanzable, completos, ir }) {
  const avance = Math.round(((paso + 1) / PASOS.length) * 100);
  return <Card className="p-5">
    <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
      <p className="font-semibold">Paso {paso + 1} de {PASOS.length} · {PASOS[paso].titulo}</p>
      <p className={completos ? "font-medium text-badge-green-fg" : "text-texto-debil"}>{completos ? (paso === REVISION ? "Obligatorios completos ✓" : "Obligatorios completos ✓ · ya podés registrar") : "Obligatorios: pasos 1 y 2"}</p>
    </div>
    <div className="mt-3 h-1.5 overflow-hidden rounded-pill bg-division" role="progressbar" aria-label="Avance del alta" aria-valuemin={0} aria-valuemax={100} aria-valuenow={avance}>
      <div className="h-full rounded-pill bg-accent transition-[width]" style={{ width: `${avance}%` }} />
    </div>
    <ol aria-label="Pasos del alta" className="mt-4 flex items-center gap-3 overflow-x-auto">
      {PASOS.map((item, i) => {
        const estado = estadoPaso(i);
        const ultimo = i === PASOS.length - 1;
        return <li key={item.key} className={cn("flex min-w-0 items-center gap-3", !ultimo && "flex-1")}>
          <button type="button" disabled={!alcanzable(i)} aria-current={estado === "actual" ? "step" : undefined} onClick={() => ir(i)}
            className="flex shrink-0 items-center gap-2 rounded-md text-left focus-visible:outline-2 focus-visible:outline-accent disabled:cursor-default">
            <span aria-hidden="true" className={cn("flex size-7 shrink-0 items-center justify-center rounded-pill text-xs font-bold",
              estado === "completo" ? "bg-badge-green-fg text-superficie" : estado === "actual" ? "bg-accent text-sobre-accent" : estado === "revisar" ? "bg-badge-error-fg text-superficie" : "border border-texto-tenue text-texto-suave")}>{estado === "completo" ? "✓" : estado === "revisar" ? "!" : i + 1}</span>
            <span className="leading-tight"><span className={cn("block whitespace-nowrap text-sm", estado === "actual" ? "font-bold text-texto" : "font-medium text-texto-suave")}>{item.titulo}{item.obligatorio && " *"}</span>
              <span className={cn("block text-xs", estado === "revisar" ? "text-badge-error-fg" : "text-texto-debil")}>{ETIQUETAS_ESTADO[estado]}</span></span>
          </button>
          {!ultimo && <span aria-hidden="true" className={cn("h-0.5 min-w-4 flex-1 rounded-pill", estado === "completo" ? "bg-badge-green-fg" : "bg-division")} />}
        </li>;
      })}
    </ol>
  </Card>;
}

function Asterisco() {
  return <span aria-hidden="true" className="text-badge-error-fg">*</span>;
}

function Seccion({ titulo, detalle, children }) {
  return <section className="space-y-4 pt-2">
    <div className="border-b border-division pb-2"><h3 className="text-md font-semibold">{titulo}</h3>{detalle && <p className="text-sm text-texto-debil">{detalle}</p>}</div>
    {children}
  </section>;
}

function Grilla({ children }) {
  return <div className="grid gap-x-5 gap-y-4 sm:grid-cols-2">{children}</div>;
}

const errorCampo = (error, name) => {
  const valor = error?.data?.[name];
  return Array.isArray(valor) ? valor.join(" ") : typeof valor === "string" ? valor : undefined;
};

function Control({ campo, datos, errores, errorServidor, cambiar, opciones, hint, mensaje, onBlur }) {
  const { name, label, options, textarea, numeric, required, requiredSi, visible, paso, ayuda, hint: hintCampo, ...props } = campo;
  const obligatorio = requerido(campo, datos);
  const propio = errores[name] === "duplicado" ? undefined : errores[name];
  const error = mensaje || propio || errorCampo(errorServidor, name);
  const comunes = { id: idCampo(name), name, value: datos[name] ?? "", "aria-required": obligatorio || undefined, onBlur, className: "aria-[invalid=true]:border-badge-error-fg" };
  const lista = opciones || options;
  const esCuit = ["cuil", "cuit_empleador"].includes(name);
  const control = lista
    ? <Select {...comunes} onChange={(e) => cambiar(name, e.target.value)}><option value="">{obligatorio ? "Seleccionar" : "Sin informar"}</option>{lista.map((o) => <option key={o.id} value={o.id}>{o.nombre}</option>)}</Select>
    : textarea ? <Textarea {...comunes} {...props} rows={2} onChange={(e) => cambiar(name, e.target.value)} />
    : <Input {...comunes} {...props} onChange={(e) => cambiar(name, esCuit ? formatoCuit(e.target.value) : e.target.value)} />;
  return <div className={textarea ? "sm:col-span-2" : undefined}><Field label={<>{label}{obligatorio && <> <Asterisco /></>}</>} hint={hint || hintCampo} ayuda={ayuda} error={error}>{control}</Field></div>;
}

function BuscadorTitular({ organizacion, seleccionado, error, onElegir }) {
  const [texto, setTexto] = useState("");
  const [busqueda, setBusqueda] = useState("");
  useEffect(() => { const t = setTimeout(() => setBusqueda(texto.trim()), 300); return () => clearTimeout(t); }, [texto]);
  const resultados = useQuery({
    queryKey: ["financiadores", "alta-titular", organizacion.id, busqueda],
    queryFn: () => api.get(`${rutaFinanciador(organizacion.id, "padron")}?${new URLSearchParams({ search: busqueda, page_size: 8 })}`),
    enabled: busqueda.length >= 3, gcTime: 0, retry: false,
  });
  const filas = filasDe(resultados.data);
  const describir = (fila) => `${fila.nombre} · ${fila.tipo_documento || "DNI"} ${fila.documento} · ${fila.numero}`;
  const etiqueta = <>Titular <Asterisco /></>;
  if (seleccionado) return <Field label={etiqueta} error={error}>
    <div id={idCampo("titular")} tabIndex={-1} className="flex h-10 items-center justify-between gap-2 rounded-md border border-campo-borde bg-superficie-2 px-3 text-md">
      <span className="truncate">{describir(seleccionado)}</span><button type="button" className="text-sm font-semibold text-accent hover:underline" onClick={() => onElegir(null)}>Cambiar</button>
    </div>
  </Field>;
  return <div>
    <Field label={etiqueta} hint="Buscá por DNI, apellido o n.º de afiliado." error={error}>
      <Input id={idCampo("titular")} type="search" aria-required="true" value={texto} onChange={(e) => setTexto(e.target.value)} autoComplete="off" />
    </Field>
    {busqueda.length >= 3 && <div className="mt-1 rounded-md border border-division" aria-live="polite">
      {resultados.isLoading ? <p className="p-2 text-sm text-texto-debil">Buscando…</p>
        : resultados.error ? <p className="p-2 text-sm text-badge-error-fg">{errorFinanciador(resultados.error)}</p>
        : !filas.length ? <p className="p-2 text-sm text-texto-debil">Sin resultados.</p>
        : <ul>{filas.map((fila) => <li key={fila.id}><button type="button" className="w-full px-3 py-2 text-left text-sm hover:bg-superficie-2 focus-visible:bg-superficie-2" onClick={() => onElegir({ id: fila.id, nombre: fila.nombre, documento: fila.documento, tipo_documento: fila.tipo_documento, numero: fila.numero })}>{describir(fila)}</button></li>)}</ul>}
    </div>}
  </div>;
}

function Revision({ datos, planes, editar }) {
  const valor = (name) => {
    const campo = CAMPOS_ALTA.find((c) => c.name === name);
    const v = datos[name];
    if (v == null || v === "") return "—";
    if (name === "plan") return planes.find((p) => String(p.id) === String(v))?.nombre || "—";
    if (campo?.options) return campo.options.find((o) => String(o.id) === String(v))?.nombre || String(v);
    if (campo?.type === "date") return fecha(v);
    return String(v);
  };
  const domicilio = [[datos.calle, datos.altura].filter(Boolean).join(" "), [datos.piso && `${datos.piso}.º`, datos.departamento].filter(Boolean).join(" ")].filter(Boolean).join(", ");
  const localidad = [[datos.localidad, datos.partido, datos.provincia].filter(Boolean).join(", "), datos.codigo_postal && `CP ${datos.codigo_postal}`].filter(Boolean).join(" · ");
  const titular = datos.titular_sel ? `${datos.titular_sel.nombre} · ${datos.titular_sel.tipo_documento || "DNI"} ${datos.titular_sel.documento}` : "—";
  const bloques = [
    { paso: 0, filas: [["Documento", `${valor("tipo_documento")} ${datos.documento || ""}`.trim()], ["CUIL", valor("cuil")], ["Nombres", valor("nombres")], ["Apellidos", valor("apellidos")], ["Sexo registrado", valor("sexo")], ["Fecha de nacimiento", valor("fecha_nacimiento")], ["Número de afiliado", valor("numero")]] },
    { paso: 1, filas: [["Cobertura", datos.cobertura_habilitada === false ? "Sin habilitar · sólo registro administrativo" : "Habilitada · sujeta a reglas y vigencia"], ["Plan", valor("plan")], ["Fecha de afiliación", valor("desde")], ["Delegación", valor("delegacion")], ["Motivo del alta", valor("motivo")], ...(datos.grupo === "familiar" ? [["Titular", titular], ["Parentesco", valor("parentesco")]] : [["Titular", "— (es titular)"]])] },
    { paso: 2, filas: pasoConDatos(2, datos) ? [["Teléfono", [datos.telefono, datos.celular].filter(Boolean).join(" · ") || "—"], ["Correo", valor("email")], ["Domicilio", domicilio || "—"], ["Localidad", localidad || "—"]] : null },
    { paso: 3, filas: pasoConDatos(3, datos) ? [["Régimen", valor("regimen")], ...camposDelPaso(3, datos).filter((c) => c.name !== "regimen").map((c) => [c.label, valor(c.name)])] : null },
  ];
  return <div className="space-y-4">{bloques.map((bloque) => <Card key={bloque.paso} className="p-6" role="region" aria-labelledby={`revision-${bloque.paso}`}>
    <div className="flex items-center justify-between gap-2"><h2 id={`revision-${bloque.paso}`} className="text-lg font-bold">{bloque.paso + 1}. {PASOS[bloque.paso].titulo}</h2><button type="button" className="text-sm font-semibold text-accent hover:underline" onClick={() => editar(bloque.paso)} aria-label={`Editar ${PASOS[bloque.paso].titulo}`}>Editar</button></div>
    {bloque.filas ? <dl className="mt-4 grid gap-x-5 gap-y-4 text-sm sm:grid-cols-2 lg:grid-cols-4">{bloque.filas.map(([label, v]) => <div key={label}><dt className="text-xs text-texto-debil">{label}</dt><dd className="mt-0.5 whitespace-pre-wrap">{v}</dd></div>)}</dl>
      : <p className="mt-3 text-sm text-texto-debil">Sin datos cargados (opcional). Podés completarlo ahora o después desde la ficha.</p>}
  </Card>)}</div>;
}

function ConfirmarDescarte({ pasos, onSeguir, onGuardar, onDescartar }) {
  // El Modal enfoca el diálogo al montarse; después se pasa a la acción segura.
  useEffect(() => { const t = requestAnimationFrame(() => document.getElementById("alta-seguir-editando")?.focus()); return () => cancelAnimationFrame(t); }, []);
  return <Modal title="¿Descartar los datos cargados?" onClose={onSeguir} width={480} footer={<>
    <Button variant="ghost" className="font-semibold text-accent" onClick={onDescartar}>Descartar</Button>
    <Button variant="secondary" onClick={onGuardar}>Guardar borrador</Button>
    <Button id="alta-seguir-editando" onClick={onSeguir}>Seguir editando</Button>
  </>}>
    <p className="text-md text-texto-suave">Cargaste datos en {pasos === 1 ? "1 paso" : `${pasos} pasos`}. Si salís ahora, se perderán. Podés guardar un borrador y retomarlo desde «Registrar afiliación».</p>
  </Modal>;
}
