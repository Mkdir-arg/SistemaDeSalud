import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "@/api/client";
import { errorFinanciador, filasDe, opcionesFinanciador, rutaFinanciador } from "@/api/financiadores";
import { useAuth } from "@/auth/AuthContext";
import { Button, Card, Field, Input, Modal, Select, Spinner, Textarea } from "@/components/ui";
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

  return <Shell plataforma={plataforma} financiador={{ nombre: organizacion?.nombre || NOMBRE_SISTEMA, titulo: "Nueva afiliación", rol: ROLES[organizacion?.rol] || "Financiador", items: menu }}><div className="space-y-6 p-lg sm:p-[30px] xl:p-[40px]">
    <nav aria-label="Ubicación" className="text-sm text-texto-debil"><Link className="font-medium text-accent hover:underline" to={volver}>Padrón de afiliados</Link> / Nueva afiliación</nav>
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

  return <>
    <div>
      <h1 className="text-cifra font-bold">Registrar afiliación</h1>
      <p className="mt-1 text-sm text-texto-suave">{paso === REVISION ? "Revisá los datos antes de registrar. Podés editar cualquier bloque." : "Completá los datos obligatorios (*) para registrar el alta. El resto podés cargarlo ahora o después desde la ficha del afiliado."}</p>
    </div>
    {borradorInicial?.guardado && <p role="status" className="rounded-md bg-superficie-2 p-3 text-sm">Retomaste el borrador guardado el {new Date(borradorInicial.guardado).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" })}. <button type="button" className="font-medium text-accent underline" onClick={() => setConfirmarSalida(true)}>Descartar borrador</button></p>}

    <Card className="p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm">
        <p className="font-semibold">Paso {paso + 1} de {PASOS.length} · {PASOS[paso].titulo}</p>
        <p className={completos ? "font-medium text-badge-green-fg" : "text-texto-debil"}>{completos ? "Obligatorios completos · ya podés registrar" : "Obligatorios: pasos 1 y 2"}</p>
      </div>
      <ol aria-label="Pasos del alta" className="grid gap-2 sm:grid-cols-5">
        {PASOS.map((item, i) => {
          const estado = estadoPaso(i);
          const alcanzable = visitados.has(i) || completos;
          return <li key={item.key}>
            <button type="button" disabled={!alcanzable || enviando} aria-current={i === paso ? "step" : undefined} onClick={() => { setDesdeRevision(false); ir(i); }}
              className={cn("flex w-full items-start gap-2 rounded-md border p-2 text-left text-sm disabled:cursor-not-allowed",
                estado === "actual" ? "border-accent bg-accent-50" : estado === "revisar" ? "border-badge-error-fg/40 bg-badge-error-bg" : "border-division hover:bg-superficie-2")}>
              <span aria-hidden="true" className={cn("flex size-6 shrink-0 items-center justify-center rounded-pill text-xs font-bold",
                estado === "completo" ? "bg-accent-fuerte text-sobre-accent" : estado === "actual" ? "border-2 border-accent text-accent" : estado === "revisar" ? "bg-badge-error-fg text-superficie" : "border-2 border-borde text-texto-tenue")}>{estado === "completo" ? "✓" : estado === "revisar" ? "!" : i + 1}</span>
              <span><span className="block font-semibold">{item.titulo}{item.obligatorio && " *"}</span>
                <span className={cn("block text-xs", estado === "revisar" ? "text-badge-error-fg" : "text-texto-debil")}>{ETIQUETAS_ESTADO[estado]}</span></span>
            </button>
          </li>;
        })}
      </ol>
    </Card>

    <Card className="space-y-5 p-5">
      {(listaErrores.length > 0 || errorServidor) && <div ref={resumenRef} tabIndex={-1} role="alert" className="rounded-md bg-badge-error-bg p-3 text-badge-error-fg outline-none">
        {listaErrores.length > 0 ? <>
          <p className="font-semibold">Revisá {listaErrores.length === 1 ? "1 campo" : `${listaErrores.length} campos`} antes de continuar</p>
          <ul className="mt-1 list-disc pl-5 text-sm">{listaErrores.map((e) => <li key={e.name}><a className="underline" href={`#${idCampo(e.name)}`} onClick={(ev) => { ev.preventDefault(); document.getElementById(idCampo(e.name))?.focus(); }}>{e.label}</a>: {e.mensaje}</li>)}</ul>
        </> : <p>{errorFinanciador(errorServidor)}</p>}
      </div>}
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 ref={tituloRef} tabIndex={-1} className="text-lg font-semibold outline-none">{paso + 1}. {PASOS[paso].titulo}</h2>
        <p className="text-sm text-texto-debil">{paso === REVISION ? "" : opcional ? "Paso opcional" : "* Campo obligatorio"}</p>
      </div>

      <fieldset disabled={enviando} className="space-y-5">
        {paso === 0 && <Grilla>{camposDelPaso(0, datos).map((campo) => <Control key={campo.name} campo={campo} datos={datos} errores={errores} errorServidor={errorServidor} cambiar={cambiar}
          onBlur={campo.name === "documento" ? () => verificarDocumento() : undefined}
          mensaje={campo.name === "documento" && errores.documento === "duplicado" || (campo.name === "documento" && duplicado.id && duplicado.documento === String(datos.documento || "").trim())
            ? <>Ya existe un afiliado con este documento. <Link className="font-medium underline" to={fichaDuplicado}>Abrir su ficha</Link></> : undefined} />)}</Grilla>}

        {paso === 1 && <>
          <Grilla>{camposDelPaso(1, datos).filter((c) => !["titular", "parentesco"].includes(c.name)).map((campo) => <Control key={campo.name} campo={campo} datos={datos} errores={errores} errorServidor={errorServidor} cambiar={cambiar}
            opciones={campo.name === "plan" ? planes.map((plan) => ({ id: plan.id, nombre: plan.nombre })) : undefined}
            hint={campo.name === "plan" && !planes.length ? "No hay planes activos. Creá uno en Planes antes de registrar." : undefined} />)}</Grilla>
          <section className="space-y-3 border-t border-division pt-4" aria-labelledby="alta-grupo">
            <div><h3 id="alta-grupo" className="font-semibold">Grupo familiar</h3><p className="text-sm text-texto-debil">Indicá si la persona es titular o se suma al grupo de otro afiliado.</p></div>
            <fieldset><legend className="mb-1.5 text-base font-semibold text-texto-suave">La persona es *</legend>
              <div className="flex flex-wrap gap-4">{[["titular", "Titular"], ["familiar", "Familiar de un titular existente"]].map(([valor, label]) => <label key={valor} className="flex items-center gap-2 text-md"><input type="radio" name="alta-grupo" value={valor} checked={datos.grupo === valor} onChange={() => cambiar("grupo", valor)} />{label}</label>)}</div>
            </fieldset>
            {datos.grupo === "familiar" && <Grilla>
              <BuscadorTitular organizacion={organizacion} seleccionado={datos.titular_sel} error={errores.titular || errorCampo(errorServidor, "titular")} onElegir={(fila) => { cambiar("titular", fila?.id ?? ""); cambiar("titular_sel", fila); if (fila) setErrores((previo) => { const resto = { ...previo }; delete resto.titular; return resto; }); }} />
              <Control campo={CAMPOS_ALTA.find((c) => c.name === "parentesco")} datos={datos} errores={errores} errorServidor={errorServidor} cambiar={cambiar} />
            </Grilla>}
          </section>
        </>}

        {paso === 2 && <>
          <section className="space-y-3"><h3 className="font-semibold">Contacto</h3>
            <Grilla>{camposDelPaso(2, datos).filter((c) => ["telefono", "celular", "email"].includes(c.name)).map((campo) => <Control key={campo.name} campo={campo} datos={datos} errores={errores} errorServidor={errorServidor} cambiar={cambiar} />)}</Grilla>
            {!datos.otro_telefono && !datos.celular && <Button type="button" size="sm" variant="ghost" onClick={() => cambiar("otro_telefono", true)}>+ Agregar otro teléfono</Button>}
          </section>
          <section className="space-y-3 border-t border-division pt-4"><div><h3 className="font-semibold">Domicilio</h3><p className="text-sm text-texto-debil">Provincia, partido y localidad se cargan como texto.</p></div>
            <Grilla>{camposDelPaso(2, datos).filter((c) => !["telefono", "celular", "email"].includes(c.name)).map((campo) => <Control key={campo.name} campo={campo} datos={datos} errores={errores} errorServidor={errorServidor} cambiar={cambiar} />)}</Grilla>
          </section>
        </>}

        {paso === 3 && <>
          <Grilla><Control campo={CAMPOS_ALTA.find((c) => c.name === "regimen")} datos={datos} errores={errores} errorServidor={errorServidor} cambiar={cambiar} hint="Los campos de abajo cambian según el régimen elegido." /></Grilla>
          {datos.regimen === "dependencia" && <section className="space-y-3 border-t border-division pt-4"><h3 className="font-semibold">Datos del empleador</h3>
            <Grilla>{camposDelPaso(3, datos).filter((c) => c.name !== "regimen").map((campo) => <Control key={campo.name} campo={campo} datos={datos} errores={errores} errorServidor={errorServidor} cambiar={cambiar} />)}</Grilla></section>}
          {datos.regimen === "desempleo" && <section className="space-y-3 border-t border-division pt-4"><h3 className="font-semibold">Subsidio por desempleo</h3>
            <Grilla>{camposDelPaso(3, datos).filter((c) => c.name !== "regimen").map((campo) => <Control key={campo.name} campo={campo} datos={datos} errores={errores} errorServidor={errorServidor} cambiar={cambiar} />)}</Grilla></section>}
          {datos.regimen && !["dependencia", "desempleo"].includes(datos.regimen) && <p className="text-sm text-texto-debil">{REGIMENES[datos.regimen]}: sin datos adicionales.</p>}
        </>}

        {paso === REVISION && <Revision datos={datos} planes={planes} editar={(i) => { setDesdeRevision(true); ir(i); }} />}
      </fieldset>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-division pt-4">
        <div className="flex flex-wrap items-center gap-3">
          <Button type="button" variant="ghost" disabled={enviando} onClick={() => tieneDatos(datos) ? setConfirmarSalida(true) : navigate(volver)}>Cancelar</Button>
          <p className="text-sm text-texto-debil">{paso === REVISION ? "Al registrar, el afiliado queda con el trámite pendiente y podés gestionar la credencial desde su ficha."
            : opcional ? "Paso opcional: podés seguir sin completarlo o registrar el alta ahora."
            : "«Siguiente» valida sólo este paso. «Registrar» se habilita al completar los pasos 1 y 2."}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {paso < 2 && <Button type="button" variant="secondary" disabled={enviando || !tieneDatos(datos)} onClick={guardarYSalir}>Guardar borrador</Button>}
          {paso > 0 && <Button type="button" variant="secondary" disabled={enviando} onClick={() => { setDesdeRevision(false); ir(paso - 1); }}>Anterior</Button>}
          {opcional && completos && <Button type="button" variant="secondary" disabled={enviando} onClick={registrar}>{enviando ? "Registrando…" : "Registrar ahora"}</Button>}
          {paso === REVISION
            ? <Button type="button" disabled={enviando || !completos} onClick={registrar}>{enviando ? "Registrando…" : "Registrar afiliación"}</Button>
            : <Button type="button" disabled={enviando} onClick={siguiente}>{desdeRevision ? "Volver a revisión" : `Siguiente: ${PASOS[paso + 1].titulo}`}</Button>}
        </div>
      </div>
    </Card>

    {confirmarSalida && <ConfirmarDescarte pasos={[...visitados].filter((i) => i < REVISION).length} onSeguir={() => setConfirmarSalida(false)} onGuardar={guardarYSalir} onDescartar={descartar} />}
  </>;
}

function Grilla({ children }) {
  return <div className="grid gap-4 sm:grid-cols-2">{children}</div>;
}

const errorCampo = (error, name) => {
  const valor = error?.data?.[name];
  return Array.isArray(valor) ? valor.join(" ") : typeof valor === "string" ? valor : undefined;
};

function Control({ campo, datos, errores, errorServidor, cambiar, opciones, hint, mensaje, onBlur }) {
  const { name, label, options, textarea, numeric, required, requiredSi, visible, paso, hint: hintCampo, ...props } = campo;
  const obligatorio = requerido(campo, datos);
  const propio = errores[name] === "duplicado" ? undefined : errores[name];
  const error = mensaje || propio || errorCampo(errorServidor, name);
  const comunes = { id: idCampo(name), name, value: datos[name] ?? "", "aria-required": obligatorio || undefined, onBlur };
  const lista = opciones || options;
  const esCuit = ["cuil", "cuit_empleador"].includes(name);
  const control = lista
    ? <Select {...comunes} onChange={(e) => cambiar(name, e.target.value)}><option value="">{obligatorio ? "Seleccionar" : "Sin informar"}</option>{lista.map((o) => <option key={o.id} value={o.id}>{o.nombre}</option>)}</Select>
    : textarea ? <Textarea {...comunes} {...props} rows={2} onChange={(e) => cambiar(name, e.target.value)} />
    : <Input {...comunes} {...props} onChange={(e) => cambiar(name, esCuit ? formatoCuit(e.target.value) : e.target.value)} />;
  return <div className={textarea ? "sm:col-span-2" : undefined}><Field label={`${label}${obligatorio ? " *" : ""}`} hint={hint || hintCampo} error={error}>{control}</Field></div>;
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
  const describir = (fila) => `${fila.nombre} · ${fila.tipo_documento || "Doc."} ${fila.documento} · ${fila.numero}`;
  if (seleccionado) return <Field label="Titular *" error={error}>
    <div id={idCampo("titular")} tabIndex={-1} className="flex items-center justify-between gap-2 rounded-md border border-campo-borde bg-superficie-2 px-3 py-2 text-md">
      <span>{describir(seleccionado)}</span><Button type="button" size="sm" variant="ghost" onClick={() => onElegir(null)}>Cambiar</Button>
    </div>
  </Field>;
  return <div>
    <Field label="Titular *" hint="Buscá por DNI, apellido o n.º de afiliado (mínimo 3 caracteres)." error={error}>
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
  const bloques = [
    { paso: 0, filas: [["Documento", `${valor("tipo_documento")} ${datos.documento || ""}`.trim()], ["CUIL", valor("cuil")], ["Apellidos", valor("apellidos")], ["Nombres", valor("nombres")], ["Fecha de nacimiento", valor("fecha_nacimiento")], ["Sexo registrado", valor("sexo")], ["Número de afiliado", valor("numero")]] },
    { paso: 1, filas: [["Plan", valor("plan")], ["Inicio de cobertura", valor("desde")], ["Delegación", valor("delegacion")], ["Motivo del alta", valor("motivo")], ...(datos.grupo === "familiar" ? [["Titular", datos.titular_sel?.nombre || "—"], ["Parentesco", valor("parentesco")]] : [["Grupo familiar", "Es titular"]])] },
    { paso: 2, filas: pasoConDatos(2, datos) ? [["Teléfono", [datos.telefono, datos.celular].filter(Boolean).join(" · ") || "—"], ["Correo", valor("email")], ["Domicilio", domicilio || "—"], ["Localidad", localidad || "—"]] : null },
    { paso: 3, filas: pasoConDatos(3, datos) ? [["Régimen", valor("regimen")], ...camposDelPaso(3, datos).filter((c) => c.name !== "regimen").map((c) => [c.label, valor(c.name)])] : null },
  ];
  return <div className="space-y-4">{bloques.map((bloque) => <section key={bloque.paso} className="rounded-md border border-division p-4" aria-labelledby={`revision-${bloque.paso}`}>
    <div className="flex items-center justify-between gap-2"><h3 id={`revision-${bloque.paso}`} className="font-semibold">{bloque.paso + 1}. {PASOS[bloque.paso].titulo}</h3><Button type="button" size="sm" variant="ghost" onClick={() => editar(bloque.paso)} aria-label={`Editar ${PASOS[bloque.paso].titulo}`}>Editar</Button></div>
    {bloque.filas ? <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">{bloque.filas.map(([label, v]) => <div key={label}><dt className="text-texto-debil">{label}</dt><dd className="mt-1 whitespace-pre-wrap font-medium">{v}</dd></div>)}</dl>
      : <p className="mt-2 text-sm text-texto-debil">Sin datos cargados (opcional). Podés completarlo ahora o después desde la ficha.</p>}
  </section>)}</div>;
}

function ConfirmarDescarte({ pasos, onSeguir, onGuardar, onDescartar }) {
  // El Modal enfoca el diálogo al montarse; después se pasa a la acción segura.
  useEffect(() => { const t = requestAnimationFrame(() => document.getElementById("alta-seguir-editando")?.focus()); return () => cancelAnimationFrame(t); }, []);
  return <Modal title="¿Descartar los datos cargados?" onClose={onSeguir} width={520} footer={<>
    <Button variant="danger" onClick={onDescartar}>Descartar</Button>
    <Button variant="secondary" onClick={onGuardar}>Guardar borrador</Button>
    <Button id="alta-seguir-editando" onClick={onSeguir}>Seguir editando</Button>
  </>}>
    <p className="text-md text-texto-suave">Cargaste datos en {pasos === 1 ? "1 paso" : `${pasos} pasos`}. Si descartás, se pierden. Podés guardar un borrador y retomarlo desde «Registrar afiliación».</p>
  </Modal>;
}
