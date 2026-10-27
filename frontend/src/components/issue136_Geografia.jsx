import { useEffect, useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { Button, Field, Input } from "@/components/ui";
import { NIVELES_GEO, cambiarGeo, nombreGeo, origenGeo } from "@/lib/issue136_geografia";

const ETIQUETAS = { provincia: "Provincia", partido: "Partido / Departamento / Comuna", localidad: "Localidad" };

export default function Geografia({ value, onChange, ambito, organizacion, disabled = false }) {
  const { user } = useAuth();
  const estado = useQuery({ queryKey: ["geografia-estado", user?.id], queryFn: () => api.get("/geografia/estado/"), retry: false, gcTime: 0 });
  return <div className="space-y-3" aria-label="Ubicación territorial">
    <p className="text-sm text-texto-debil">Elegí provincia, luego partido o departamento y localidad. Podés escribir para buscar.</p>
    {estado.data?.error && <p role="status" className="text-sm text-texto-debil">{estado.data.actualizado ? "Se está usando el último catálogo disponible; su actualización no se completó." : "El catálogo inicial todavía no está disponible. Podés cargar los lugares manualmente."}</p>}
    <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,16rem),1fr))] gap-3">{NIVELES_GEO.map((nivel) => <Nivel key={nivel} nivel={nivel} geo={value || {}} disabled={disabled} ambito={ambito} organizacion={organizacion} onChange={(v) => onChange(cambiarGeo(value || {}, nivel, v))} />)}</div>
  </div>;
}

function Nivel({ nivel, geo, onChange, ambito, organizacion, disabled }) {
  const { user } = useAuth();
  const valor = geo[nivel];
  const nombre = nombreGeo(valor);
  const listaId = useId();
  const [manual, setManual] = useState(false);
  const [entrada, setEntrada] = useState(nombre);
  const [abierto, setAbierto] = useState(false);
  const [activo, setActivo] = useState(-1);
  const [texto, setTexto] = useState("");
  const [pagina, setPagina] = useState(1);
  // El nombre ya elegido se muestra en el campo, pero al abrir se permite
  // recorrer todas las opciones, como en el selector de agendas.
  const termino = !valor?.pendiente && entrada.trim() === nombre.trim() ? "" : entrada.trim();
  useEffect(() => {
    const id = setTimeout(() => setTexto(termino), 250);
    return () => clearTimeout(id);
  }, [termino]);
  useEffect(() => {
    setEntrada(nombre); setAbierto(false); setActivo(-1);
  }, [nombre, valor?.id, valor?.pendiente]);
  const provincia = nivel !== "provincia" ? geo.provincia?.id : null;
  const partido = nivel === "localidad" ? geo.partido?.id : null;
  // Descartar búsquedas del padre/ámbito anterior; el nombre confirmado se
  // sincroniza por separado para no salir del modo manual al escribir en él.
  useEffect(() => {
    setManual(false); setAbierto(false); setEntrada(nombreGeo(geo[nivel]));
    setTexto(""); setPagina(1); setActivo(-1);
  }, [provincia, partido, ambito, organizacion]);
  const filtro = new URLSearchParams({ tipo: nivel, search: texto, page: String(pagina) });
  if (ambito && organizacion) { filtro.set("ambito", ambito); filtro.set("organizacion", String(organizacion)); }
  if (provincia) filtro.set("provincia", String(provincia));
  if (partido) filtro.set("partido", String(partido));
  const habilitada = nivel === "provincia" || Boolean(provincia) && (nivel !== "localidad" || Boolean(partido));
  const consulta = useQuery({ queryKey: ["geografia", user?.id, ambito, organizacion, nivel, provincia, partido, texto, pagina],
    queryFn: () => api.get(`/geografia/lugares/?${filtro}`), enabled: habilitada && abierto && !manual && !disabled, retry: false, gcTime: 0 });
  // No permitir elegir resultados de la búsqueda anterior durante el debounce.
  const buscando = habilitada && (texto !== termino || consulta.isFetching || consulta.isPending);
  const filas = !habilitada || buscando || consulta.error ? [] : consulta.data?.results || [];
  const ofrecerManual = !buscando && filas.length === 0;
  const cantidadOpciones = filas.length + (ofrecerManual ? 1 : 0);
  useEffect(() => {
    if (abierto && activo >= 0) document.getElementById(`${listaId}-${activo}`)?.scrollIntoView({ block: "nearest" });
  }, [activo, abierto, listaId]);
  const cerrar = () => { setAbierto(false); setEntrada(nombre); setActivo(-1); setPagina(1); };
  const elegir = (fila) => {
    if (disabled) return;
    setEntrada(fila.nombre); setAbierto(false); setActivo(-1); setPagina(1);
    if (fila.id !== valor?.id || valor?.pendiente) onChange(fila);
  };
  const cargarManual = () => {
    setManual(true); setAbierto(false);
    const candidato = entrada.trim() || nombre;
    if (candidato) onChange({ manual: candidato });
  };
  return <div className="min-w-0 space-y-2" onBlur={(e) => {
    if (!e.currentTarget.contains(e.relatedTarget)) {
      // Borrar el campo y salir reemplaza la acción «Quitar». Una búsqueda
      // no vacía abandonada sigue restaurando la selección confirmada.
      if (!manual && !entrada.trim() && nombre) onChange(null);
      cerrar();
    }
  }}>
    {valor?.pendiente && <div role="alert" className="text-sm text-badge-amber-fg">Cambió una unidad anterior. Elegí nuevamente este lugar o confirmá su carga manual desde los resultados.</div>}
    {manual ? <>
      <Field label={`${ETIQUETAS[nivel]} · carga manual`}><Input maxLength={100} value={nombreGeo(valor)} disabled={disabled} onChange={(e) => onChange(e.target.value.trim() ? { manual: e.target.value } : null)} /></Field>
      <p className="text-xs text-texto-debil">Manual · sin verificar. Se reutiliza sólo en tu organización. Ingresá el nombre del lugar, sin datos personales ni calle y altura.</p>
      <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={() => { setManual(false); cerrar(); }}>Buscar en catálogo</Button>
    </> : <>
      <Field label={ETIQUETAS[nivel]}><Input role="combobox" autoComplete="off" value={entrada}
        disabled={disabled} maxLength={100} placeholder="Escribí o elegí una opción"
        aria-expanded={abierto && !disabled} aria-controls={abierto && !disabled ? listaId : undefined}
        aria-autocomplete="list" aria-describedby={`${listaId}-ayuda`}
        aria-activedescendant={abierto && !disabled && activo >= 0 && activo < cantidadOpciones ? `${listaId}-${activo}` : undefined}
        onChange={(e) => { setEntrada(e.target.value); setPagina(1); setActivo(-1); setAbierto(true); }}
        onFocus={(e) => { e.target.select(); setAbierto(true); }}
        onKeyDown={(e) => {
          if (e.key === "Escape" && abierto) { e.preventDefault(); e.stopPropagation(); cerrar(); }
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault(); setAbierto(true);
            setActivo((i) => Math.max(0, Math.min(cantidadOpciones - 1, i + (e.key === "ArrowDown" ? 1 : -1))));
          }
          if (e.key === "Enter") {
            e.preventDefault();
            if (abierto && filas[activo]) elegir(filas[activo]);
            else if (abierto && ofrecerManual && activo === filas.length) cargarManual();
            else setAbierto(true);
          }
        }} /></Field>
      {abierto && !disabled && <div className="rounded-md border border-borde bg-superficie shadow-dropdown">
        {buscando ? <p role="status" className="p-3 text-sm text-texto-debil">Buscando…</p>
          : !habilitada ? <p role="status" className="p-3 text-sm text-texto-debil">Elegí las unidades anteriores para buscar en el catálogo, o cargá este lugar manualmente.</p>
          : consulta.error ? <p role="status" className="p-3 text-sm text-texto-debil">No se pudo consultar el catálogo. Podés cargar el lugar manualmente.</p>
          : filas.length === 0 ? <p role="status" className="p-3 text-sm text-texto-debil">No hay coincidencias.</p> : null}
        <div id={listaId} role="listbox" aria-label={ETIQUETAS[nivel]} aria-busy={buscando}
          className="max-h-48 overflow-y-auto">
          {filas.map((f, i) => <div id={`${listaId}-${i}`} key={f.id} role="option" aria-selected={i === activo}
            onMouseDown={(e) => e.preventDefault()} onClick={() => elegir(f)}
            className={`cursor-pointer break-words px-3 py-2 text-sm hover:bg-superficie-2 ${i === activo ? "bg-superficie-2" : ""}`}>
            {f.nombre}{f.origen === "manual" && <span className="text-texto-debil"> · Manual · sin verificar</span>}
          </div>)}
          {ofrecerManual && <div id={`${listaId}-${filas.length}`} role="option" aria-label="Cargar manualmente" aria-selected={activo === filas.length}
            onMouseDown={(e) => e.preventDefault()} onClick={cargarManual}
            className={`cursor-pointer break-words px-3 py-2 text-sm font-semibold text-accent hover:bg-superficie-2 ${activo === filas.length ? "bg-superficie-2" : ""}`}>
            Cargar manualmente
          </div>}
        </div>
        {consulta.error && <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={() => consulta.refetch()}>Reintentar catálogo</Button>}
        {!buscando && !consulta.error && (pagina > 1 || consulta.data?.next) && <div className="flex flex-wrap gap-2 border-t border-borde p-1">
          {pagina > 1 && <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={() => { setPagina((p) => p - 1); setActivo(-1); }}>Anteriores</Button>}
          {consulta.data?.next && <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={() => { setPagina((p) => p + 1); setActivo(-1); }}>Más resultados</Button>}
        </div>}
      </div>}
      <p id={`${listaId}-ayuda`} className="min-h-4 text-xs text-texto-debil" aria-live="polite">
        {!habilitada ? (nivel === "partido" ? "Primero elegí una provincia." : "Primero elegí provincia y partido o departamento.")
          : abierto ? "Elegí un resultado para confirmar." : nombre && origenGeo(valor) !== "Georef" ? origenGeo(valor) : ""}
      </p>
    </>}
  </div>;
}

export function GeografiaTexto({ value }) {
  return <div className="text-sm text-texto-debil">{NIVELES_GEO.map((n) => nombreGeo(value?.[n]) ? <p key={n}>{ETIQUETAS[n]}: {nombreGeo(value[n])}{origenGeo(value[n]) !== "Georef" && ` · ${origenGeo(value[n])}`}</p> : null)}</div>;
}
