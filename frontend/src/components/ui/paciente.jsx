import { useState } from "react";

import { api } from "@/api/client";
import { useAccion, useLista } from "@/api/queries";
import { Button, Field, Input } from "@/components/ui";
import { Buscador } from "@/components/ui/filtros";
import { useToast } from "@/components/ui/toast";

/**
 * Buscar un paciente y, si no existe, crearlo en el momento.
 *
 * Estaba repetido casi igual en tres lugares (ingresar paciente, nuevo caso,
 * estado de un paciente), cada uno con su propio debounce y su propio manejo de
 * «sin resultados». Acá vive una sola vez.
 *
 * Busca SIEMPRE contra el servidor: el padrón de un hospital no entra en un
 * desplegable, y traerlo entero para filtrar en el navegador es el patrón que
 * esta migración viene sacando de todas las pantallas.
 */
export function BuscadorPaciente({ institucionId, onElegir, permitirCrear = true, autoFocus = true }) {
  const toast = useToast();
  const [texto, setTexto] = useState("");
  const [creando, setCreando] = useState(null); // datos precargados del nuevo

  const q = useLista(
    "ciudadanos",
    { institucion: institucionId, search: texto.trim() || undefined, pageSize: 8 },
    { enabled: texto.trim().length > 0 },
  );

  const crear = useAccion(
    (datos) => api.post("/ciudadanos/", { institucion: institucionId, ...datos }),
    { onError: (e) => toast.deError(e, "No se pudo crear el paciente.") },
  );

  if (creando) {
    return (
      <div className="flex flex-col gap-2">
        <p className="text-base text-texto-debil">Nuevo paciente</p>
        <Input placeholder="Nombre *" value={creando.nombre} autoFocus
          onChange={(e) => setCreando({ ...creando, nombre: e.target.value })} />
        <Input placeholder="Apellido" value={creando.apellido}
          onChange={(e) => setCreando({ ...creando, apellido: e.target.value })} />
        <Input placeholder="Documento" value={creando.documento}
          onChange={(e) => setCreando({ ...creando, documento: e.target.value })} />
        <div className="mt-1 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setCreando(null)}>Volver</Button>
          <Button
            disabled={!creando.nombre.trim() || crear.isPending}
            onClick={() => crear.mutate(
              {
                nombre: creando.nombre.trim(),
                apellido: creando.apellido.trim(),
                documento: creando.documento.trim(),
              },
              { onSuccess: (c) => { setCreando(null); onElegir(c); } },
            )}
          >
            {crear.isPending ? "Creando…" : "Crear y continuar"}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <Field label="Buscar paciente">
        <Buscador valor={texto} onChange={setTexto} placeholder="Nombre, apellido o documento…" autoFocus={autoFocus} />
      </Field>

      {!texto.trim() ? (
        <p className="text-base text-texto-tenue">
          Escribí para buscar al paciente{permitirCrear ? ". Si no existe, lo creás al toque." : "."}
        </p>
      ) : (
        <div className="overflow-hidden rounded-md border border-borde">
          {q.isLoading ? (
            <p className="p-3.5 text-md text-texto-tenue">Buscando…</p>
          ) : q.filas.length > 0 ? (
            <ul>
              {q.filas.map((c) => (
                <li key={c.id}>
                  <button
                    onClick={() => onElegir(c)}
                    className="w-full border-t border-division px-3.5 py-2.5 text-left first:border-t-0 hover:bg-superficie-2"
                  >
                    <span className="block text-md font-semibold">{c.nombre} {c.apellido}</span>
                    <span className="block text-sm text-texto-tenue">
                      {c.documento ? `Doc. ${c.documento}` : "Sin documento"}
                      {c.obra_social ? ` · ${c.obra_social}` : ""}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-2.5 p-3.5">
              <span className="text-md text-texto-debil">Sin coincidencias para «{texto.trim()}»</span>
              {permitirCrear && (
                <Button
                  size="sm"
                  onClick={() => {
                    // Precarga lo escrito: si buscaste «Juan Pérez», ya viene el
                    // nombre partido y no hay que volver a tipearlo.
                    const partes = texto.trim().split(/\s+/);
                    setCreando({ nombre: partes[0] || "", apellido: partes.slice(1).join(" "), documento: "" });
                  }}
                >
                  + Crear nuevo
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** Ficha compacta del paciente elegido, con opción de cambiarlo. */
export function PacienteElegido({ paciente, onCambiar }) {
  return (
    <div className="flex items-center gap-3 rounded-md border border-borde bg-superficie-2 p-3.5">
      <div className="min-w-0 flex-1">
        <div className="text-lg font-bold">{paciente.nombre} {paciente.apellido}</div>
        <div className="text-base text-texto-tenue">
          {paciente.documento ? `Doc. ${paciente.documento}` : "Sin documento"}
          {paciente.obra_social ? ` · ${paciente.obra_social}` : ""}
        </div>
      </div>
      {onCambiar && (
        <button onClick={onCambiar} className="text-base font-semibold text-accent hover:underline">
          Cambiar
        </button>
      )}
    </div>
  );
}
