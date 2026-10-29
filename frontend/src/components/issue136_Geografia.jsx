import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useQuery } from "@tanstack/react-query";
import { api, simulacion } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { Button, Field, Input } from "@/components/ui";
import { NIVELES_GEO, cambiarGeo, nombreGeo, origenGeo } from "@/lib/issue136_geografia";
import { cargarCatalogoGeografico, filtrarCatalogoGeografico } from "@/lib/issue136_catalogo";

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
  const [pagina, setPagina] = useState(1);
  const campoRef = useRef(null);
  const panelRef = useRef(null);
  const [posicion, setPosicion] = useState(null);
  // El nombre ya elegido se muestra en el campo, pero al abrir se permite
  // recorrer todas las opciones, como en el selector de agendas.
  const termino = !valor?.pendiente && entrada.trim() === nombre.trim() ? "" : entrada.trim();
  useEffect(() => {
    setEntrada(nombre); setAbierto(false); setActivo(-1);
  }, [nombre, valor?.id, valor?.pendiente]);
  const provincia = nivel !== "provincia" ? geo.provincia?.id : null;
  const partido = nivel === "localidad" ? geo.partido?.id : null;
  // Descartar búsquedas del padre/ámbito anterior; el nombre confirmado se
  // sincroniza por separado para no salir del modo manual al escribir en él.
  useEffect(() => {
    setManual(false); setAbierto(false); setEntrada(nombreGeo(geo[nivel]));
    setPagina(1); setActivo(-1);
  }, [provincia, partido, ambito, organizacion]);
  const filtro = new URLSearchParams({ tipo: nivel });
  if (ambito && organizacion) { filtro.set("ambito", ambito); filtro.set("organizacion", String(organizacion)); }
  if (provincia) filtro.set("provincia", String(provincia));
  if (partido) filtro.set("partido", String(partido));
  const habilitada = nivel === "provincia" || Boolean(provincia) && (nivel !== "localidad" || Boolean(partido));
  const consulta = useQuery({
    queryKey: ["geografia-catalogo", user?.id, simulacion.get()?.id ?? null, ambito, organizacion, nivel, provincia, partido],
    queryFn: ({ signal }) => cargarCatalogoGeografico((numero) => {
      const params = new URLSearchParams(filtro);
      params.set("page", String(numero));
      return api.get(`/geografia/lugares/?${params}`);
    }, signal),
    enabled: Boolean(user?.id) && habilitada && !manual && !disabled,
    retry: false, staleTime: 5 * 60_000, gcTime: 10 * 60_000,
  });
  const buscando = habilitada && consulta.isPending;
  const filtradas = !habilitada ? [] : filtrarCatalogoGeografico(consulta.data || [], termino);
  const filas = filtradas.slice((pagina - 1) * 30, pagina * 30);
  const ofrecerManual = !buscando && filtradas.length === 0;
  const cantidadOpciones = filas.length + (ofrecerManual ? 1 : 0);
  // Portal fuera de los contenedores con scroll; el foco permanece en el campo.
  useLayoutEffect(() => {
    if (!abierto || manual || disabled) { setPosicion(null); return undefined; }
    const ubicar = () => {
      const campo = campoRef.current?.getBoundingClientRect();
      if (!campo || campo.bottom < 0 || campo.top > window.innerHeight) { setPosicion(null); return; }
      const abajo = window.innerHeight - campo.bottom - 12;
      const arriba = campo.top - 12;
      const altura = Math.min(panelRef.current?.scrollHeight || 240, 300);
      const invertir = abajo < altura && arriba > abajo;
      const maxHeight = Math.max(0, Math.min(300, invertir ? arriba : abajo));
      const width = Math.min(campo.width, window.innerWidth - 16);
      const nueva = {
        left: Math.max(8, Math.min(campo.left, window.innerWidth - width - 8)), width, maxHeight,
        top: invertir ? campo.top - Math.min(altura, maxHeight) - 4 : campo.bottom + 4,
      };
      setPosicion((previa) => previa && Object.keys(nueva).every((k) => previa[k] === nueva[k]) ? previa : nueva);
    };
    ubicar();
    const observador = new ResizeObserver(ubicar);
    if (campoRef.current) observador.observe(campoRef.current);
    if (panelRef.current) observador.observe(panelRef.current);
    window.addEventListener("resize", ubicar);
    window.addEventListener("scroll", ubicar, true);
    return () => {
      observador.disconnect();
      window.removeEventListener("resize", ubicar);
      window.removeEventListener("scroll", ubicar, true);
    };
  }, [abierto, manual, disabled]);
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
    if (!e.currentTarget.contains(e.relatedTarget) && !panelRef.current?.contains(e.relatedTarget)) {
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
      <Field label={ETIQUETAS[nivel]}><Input ref={campoRef} role="combobox" autoComplete="off" value={entrada}
        disabled={disabled} maxLength={100} placeholder="Escribí o elegí una opción"
        aria-expanded={abierto && !disabled} aria-controls={abierto && !disabled ? listaId : undefined}
        aria-autocomplete="list" aria-describedby={`${listaId}-ayuda`}
        aria-activedescendant={abierto && !disabled && activo >= 0 && activo < cantidadOpciones ? `${listaId}-${activo}` : undefined}
        onChange={(e) => { setEntrada(e.target.value); setPagina(1); setActivo(-1); setAbierto(true); }}
        onFocus={(e) => { e.target.select(); setAbierto(true); }}
        onClick={() => setAbierto(true)}
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
      {abierto && !disabled && createPortal(<div ref={panelRef}
        style={{ position: "fixed", zIndex: 100, left: 0, top: 0, width: 280, ...posicion, visibility: posicion ? "visible" : "hidden" }}
        className="overflow-y-auto rounded-md border border-borde bg-superficie shadow-dropdown">
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
        {consulta.error && <Button type="button" size="sm" variant="ghost" disabled={disabled} onMouseDown={(e) => e.preventDefault()} onClick={() => consulta.refetch()}>Reintentar catálogo</Button>}
        {!buscando && (pagina > 1 || filtradas.length > pagina * 30) && <div className="flex flex-wrap gap-2 border-t border-borde p-1">
          {pagina > 1 && <Button type="button" size="sm" variant="ghost" disabled={disabled} onMouseDown={(e) => e.preventDefault()} onClick={() => { setPagina((p) => p - 1); setActivo(-1); }}>Anteriores</Button>}
          {filtradas.length > pagina * 30 && <Button type="button" size="sm" variant="ghost" disabled={disabled} onMouseDown={(e) => e.preventDefault()} onClick={() => { setPagina((p) => p + 1); setActivo(-1); }}>Más resultados</Button>}
        </div>}
      </div>, document.body)}
      <p id={`${listaId}-ayuda`} className="min-h-4 text-xs text-texto-debil" aria-live="polite">
        {!habilitada ? (nivel === "partido" ? "Primero elegí una provincia." : "Primero elegí provincia y partido o departamento.")
          : nombre && origenGeo(valor) !== "Georef" ? origenGeo(valor) : ""}
      </p>
    </>}
  </div>;
}

export function GeografiaTexto({ value }) {
  return <div className="text-sm text-texto-debil">{NIVELES_GEO.map((n) => nombreGeo(value?.[n]) ? <p key={n}>{ETIQUETAS[n]}: {nombreGeo(value[n])}{origenGeo(value[n]) !== "Georef" && ` · ${origenGeo(value[n])}`}</p> : null)}</div>;
}
