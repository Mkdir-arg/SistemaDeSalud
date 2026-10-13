import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/api/client";
import { errorFinanciador, filasDe, rutaFinanciador } from "@/api/financiadores";
import { parametrosFamiliar } from "@/lib/padronNavigation";
import { Button, Card, Field, Input, Spinner } from "@/components/ui";
import FormularioPadron from "./FormularioPadron";
import { CAMPOS_FAMILIA, PARENTESCOS } from "./padronCampos";

export default function FamiliaPadron({ ruta, persona, scope, organizacion, parametros, puedeEditar, actualizado, integrado = false, onEdicion, onOcupado }) {
  const [editar, setEditar] = useState(false);
  useEffect(() => { onEdicion?.(editar ? "familia" : null); }, [editar, onEdicion]);
  const [texto, setTexto] = useState("");
  const [buscar, setBuscar] = useState("");
  const [seleccionado, setSeleccionado] = useState(null);
  useEffect(() => { const timer = setTimeout(() => setBuscar(texto.trim()), 250); return () => clearTimeout(timer); }, [texto]);
  const familia = useQuery({ queryKey: [...scope, "familia", persona.id], queryFn: () => api.get(`${ruta}familia/`), gcTime: 0, retry: false });
  const titulares = useQuery({ queryKey: [...scope, "buscar-titular", buscar], queryFn: () => api.get(`${rutaFinanciador(organizacion.id, "padron")}?${new URLSearchParams({ search: buscar, estado: "todos", page: 1 })}`), enabled: editar && buscar.length >= 2, gcTime: 0, retry: false });
  const titular = familia.data?.titular;
  const opciones = filasDe(titulares.data).filter((item) => item.id !== persona.id && !item.titular);
  if (titular && titular.id !== persona.id && !opciones.some((item) => item.id === titular.id)) opciones.unshift(titular);
  if (seleccionado && !opciones.some((item) => item.id === seleccionado.id)) opciones.unshift(seleccionado);
  const integrantes = familia.data?.integrantes || [];
  const query = parametrosFamiliar(parametros);
  return <section aria-label="Grupo familiar" className="space-y-3"><div hidden={integrado && Boolean(editar)}><div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-lg font-semibold">Grupo familiar</h2>{puedeEditar && familia.isSuccess && <Button variant="secondary" onClick={() => { setTexto(""); setBuscar(""); setSeleccionado(null); setEditar(true); }}>Editar vínculo familiar</Button>}</div>
    <p className="text-sm text-texto-debil">Vínculo explícito de un nivel. El titular debe pertenecer a este financiador. Una baja del titular no da de baja a los familiares automáticamente.</p>
    <Card className="p-4">{familia.isLoading ? <Spinner label="Consultando familia…" /> : familia.error ? <p role="alert">{errorFinanciador(familia.error)} <Button variant="ghost" onClick={() => familia.refetch()}>Reintentar</Button></p> : <>
      <p className="mb-3 text-sm">{titular ? `Titular: ${titular.nombre} · ${titular.numero}` : "Sin titular vinculado; no se infiere por el número de afiliado."}</p>
      {!integrantes.length ? <p className="text-sm text-texto-debil">No hay integrantes vinculados.</p> : <ul className="space-y-2">{integrantes.map((item) => <li key={item.id} className="text-sm">{String(item.id) === String(persona.id) ? <span className="font-semibold">{item.nombre} (ficha actual)</span> : <Link className="font-medium text-accent hover:underline" to={`/financiadores/padron/${item.id}?${query}`}>{item.nombre}</Link>} · {item.numero} · {item.id === titular?.id ? "Titular" : PARENTESCOS[item.parentesco] || "Parentesco sin informar"}</li>)}</ul>}
    </>}</Card>
    </div>
    {editar && <FormularioPadron integrado={integrado} onOcupado={onOcupado} titulo="Editar vínculo familiar" descripcion="Sin titular y sin parentesco retira el vínculo. El parentesco protegido se administra en condiciones de salud." inicial={persona} campos={[{ ...CAMPOS_FAMILIA[0], onSelect: (id) => setSeleccionado(opciones.find((item) => String(item.id) === String(id)) || null), options: opciones.map((item) => ({ id: item.id, nombre: `${item.numero} · ${item.documento} · ${item.nombre}` })) }, CAMPOS_FAMILIA[1]]} antesCampos={<div className="sm:col-span-2"><Field label="Buscar titular" hint="Ingresá al menos dos caracteres del documento, número, CUIL o nombre."><Input value={texto} onChange={(event) => setTexto(event.target.value)} /></Field>{titulares.error && <p role="alert">{errorFinanciador(titulares.error)}</p>}{titulares.isFetching && <p className="text-sm">Buscando…</p>}{titulares.data?.next && <p className="text-sm">Hay más resultados. Precisá la búsqueda.</p>}{buscar.length >= 2 && titulares.isSuccess && !opciones.length && <p className="text-sm">No hay titulares para esta búsqueda.</p>}</div>} guardar={(cambios, motivo) => api.patch(ruta, { ...cambios, revision: persona.revision, motivo })} recargar={async () => { setEditar(false); await actualizado(); }} onClose={() => setEditar(false)} onGuardado={async () => { setEditar(false); await actualizado(); }} />}
  </section>;
}
