import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { Button, Field, Input, Select } from "@/components/ui";
import { NIVELES_GEO, cambiarGeo, nombreGeo, origenGeo } from "@/lib/issue136_geografia";

const ETIQUETAS = { provincia: "Provincia", partido: "Partido / Departamento / Comuna", localidad: "Localidad" };

export default function Geografia({ value, onChange, ambito, organizacion, disabled = false }) {
  const { user } = useAuth();
  const estado = useQuery({ queryKey: ["geografia-estado", user?.id], queryFn: () => api.get("/geografia/estado/"), retry: false, gcTime: 0 });
  return <div className="space-y-3" aria-label="Ubicación territorial">
    <p className="text-sm text-texto-debil">Buscá en el catálogo de Salud. Si no encontrás el lugar, podés cargarlo manualmente; se reutilizará sólo dentro de tu organización.</p>
    {estado.data?.error && <p role="status" className="text-sm text-texto-debil">{estado.data.actualizado ? "Se está usando el último catálogo disponible; su actualización no se completó." : "El catálogo inicial todavía no está disponible. Podés cargar los lugares manualmente."}</p>}
    <div className="grid gap-3 sm:grid-cols-3">{NIVELES_GEO.map((nivel) => <Nivel key={nivel} nivel={nivel} geo={value || {}} disabled={disabled} ambito={ambito} organizacion={organizacion} onChange={(v) => onChange(cambiarGeo(value || {}, nivel, v))} />)}</div>
  </div>;
}

function Nivel({ nivel, geo, onChange, ambito, organizacion, disabled }) {
  const { user } = useAuth();
  const valor = geo[nivel];
  const [manual, setManual] = useState(false);
  const [busqueda, setBusqueda] = useState("");
  const [texto, setTexto] = useState("");
  const [pagina, setPagina] = useState(1);
  useEffect(() => {
    const id = setTimeout(() => { setTexto(busqueda); setPagina(1); }, 250);
    return () => clearTimeout(id);
  }, [busqueda]);
  const provincia = nivel !== "provincia" ? geo.provincia?.id : null;
  const partido = nivel === "localidad" ? geo.partido?.id : null;
  const filtro = new URLSearchParams({ tipo: nivel, search: texto, page: String(pagina) });
  if (ambito && organizacion) { filtro.set("ambito", ambito); filtro.set("organizacion", String(organizacion)); }
  if (provincia) filtro.set("provincia", String(provincia));
  if (partido) filtro.set("partido", String(partido));
  const habilitada = nivel === "provincia" || Boolean(provincia) && (nivel !== "localidad" || Boolean(partido));
  const consulta = useQuery({ queryKey: ["geografia", user?.id, ambito, organizacion, nivel, provincia, partido, texto, pagina],
    queryFn: () => api.get(`/geografia/lugares/?${filtro}`), enabled: habilitada && !manual, retry: false, gcTime: 0 });
  const filas = consulta.data?.results || [];
  const cargaManual = manual;
  return <div className="space-y-2">
    <p className="text-sm font-semibold">{ETIQUETAS[nivel]}</p>
    {nombreGeo(valor) && <p className="break-words text-sm" aria-live="polite">{nombreGeo(valor)} <span className="text-texto-debil">· {origenGeo(valor)}</span></p>}
    {valor?.pendiente && <div role="alert" className="text-sm text-badge-amber-fg">Cambió una unidad anterior. Elegí nuevamente este lugar o confirmá su carga manual.
      <Button type="button" size="sm" variant="secondary" onClick={() => { setManual(true); onChange({ manual: nombreGeo(valor) }); }} disabled={disabled}>Conservar como manual</Button></div>}
    {cargaManual ? <>
      <Field label={`${ETIQUETAS[nivel]} · carga manual`}><Input maxLength={100} value={nombreGeo(valor)} disabled={disabled} onChange={(e) => onChange(e.target.value.trim() ? { manual: e.target.value } : null)} /></Field>
      <p className="text-xs text-texto-debil">Manual · sin verificar. Ingresá sólo el nombre del lugar, sin datos personales ni calle y altura.</p>
      <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={() => setManual(false)}>Buscar en catálogo</Button>
    </> : <>
      <Field label={`Buscar ${ETIQUETAS[nivel].toLocaleLowerCase("es-AR")}`}><Input type="search" value={busqueda} disabled={disabled || !habilitada} maxLength={100} onChange={(e) => setBusqueda(e.target.value)} /></Field>
      <Field label={`Elegir ${ETIQUETAS[nivel].toLocaleLowerCase("es-AR")}`}><Select disabled={disabled || !habilitada || consulta.isFetching} value="" onChange={(e) => {
        const fila = filas.find((f) => String(f.id) === e.target.value);
        if (fila) { setManual(false); onChange(fila); }
      }}><option value="">{consulta.isFetching ? "Buscando…" : "Seleccionar resultado"}</option>{filas.map((f) => <option key={f.id} value={f.id}>{f.nombre}{f.origen === "manual" ? " · Manual · sin verificar" : ""}</option>)}</Select></Field>
      {!habilitada && <p className="text-xs text-texto-debil">Elegí las unidades anteriores para buscar, o ingresá este lugar manualmente.</p>}
      {consulta.error && <p role="status" className="text-sm text-texto-debil">No se pudo consultar el catálogo. Podés cargar el lugar manualmente.</p>}
      {consulta.error && <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={() => consulta.refetch()}>Reintentar catálogo</Button>}
      {habilitada && !consulta.isFetching && !consulta.error && filas.length === 0 && <p role="status" className="text-sm text-texto-debil">No hay coincidencias. Podés cargar el lugar manualmente.</p>}
      <div className="flex gap-2">{pagina > 1 && <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={() => setPagina((p) => p - 1)}>Anteriores</Button>}{consulta.data?.next && <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={() => setPagina((p) => p + 1)}>Más resultados</Button>}</div>
      <Button type="button" size="sm" variant="secondary" disabled={disabled} onClick={() => { setManual(true); if (nombreGeo(valor)) onChange({ manual: nombreGeo(valor) }); }}>Cargar manualmente</Button>
    </>}
    {nombreGeo(valor) && <Button type="button" size="sm" variant="ghost" disabled={disabled} onClick={() => { setManual(false); onChange(null); }}>Quitar {ETIQUETAS[nivel].toLocaleLowerCase("es-AR")}</Button>}
  </div>;
}

export function GeografiaTexto({ value }) {
  return <div className="text-sm text-texto-debil">{NIVELES_GEO.map((n) => nombreGeo(value?.[n]) ? <p key={n}>{ETIQUETAS[n]}: {nombreGeo(value[n])} · {origenGeo(value[n])}</p> : null)}</div>;
}
