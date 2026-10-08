import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate, useOutletContext } from "react-router-dom";

import {
  erroresFormulario, mensajePortal, usePerfilPortal, useSalir, useValidarIdentidad,
} from "@/api/portal";
import { fechaCalendario, fechaHora, plural } from "@/lib/format";
import { Boton, Cabecera, Fila, Paso, Pie, Tarjeta, TEXTO } from "./ui";

import { Alerta, Cargando, CampoTexto, formatoDni, Pantalla, PasoDeLaCuenta, Resultado, soloDigitos } from "./comun";

// Pantallas con sesión del portal. Las de validación viven detrás de
// `PasoDeLaCuenta`, que lleva a la persona a la que le corresponde según lo que
// le falta completar; `MiCuenta`, dentro del marco de la app.

const LARGO_TRAMITE = 11;
const SEXOS = [["F", "Femenino"], ["M", "Masculino"], ["X", "X"]];

function BotonSalir() {
  const navigate = useNavigate();
  const salir = useSalir();
  const cerrar = () => salir.mutate(undefined, {
    onSettled: () => navigate("/mi/ingresar", { replace: true, state: { aviso: "Cerraste sesión." } }),
  });
  return <Boton variante="texto" onClick={cerrar} disabled={salir.isPending}>Cerrar sesión</Boton>;
}

/** Pasa por acá después de ingresar o al volver de un enlace: decide la pantalla. */
export function Continuar() {
  return <PasoDeLaCuenta>{() => null}</PasoDeLaCuenta>;
}

/** Validar la identidad contra RENAPER con los datos del DNI. */
export function ValidarIdentidad() {
  return <PasoDeLaCuenta>{(cuenta) => <FormularioIdentidad cuenta={cuenta} />}</PasoDeLaCuenta>;
}

const MOTIVOS = new Set(["no_coincide", "validacion_bloqueada", "documento_en_uso", "servicio_no_disponible", "email_sin_verificar"]);
const vigente = (iso) => Boolean(iso) && new Date(iso) > new Date();

function FormularioIdentidad({ cuenta }) {
  const qc = useQueryClient();
  const validar = useValidarIdentidad();
  const [datos, setDatos] = useState(() => ({
    documento: cuenta.documento || "",
    sexo: cuenta.sexo || "", numero_tramite: "",
  }));
  const codigo = validar.error?.data?.codigo;

  // Ya estaba validada (otra pestaña): se relee la cuenta y la puerta la lleva a su pantalla.
  useEffect(() => {
    if (codigo === "ya_validada") qc.invalidateQueries({ queryKey: ["portal", "cuenta"] });
  }, [codigo, qc]);

  const enviar = (e) => {
    e?.preventDefault();
    // Solo DNI, sexo y trámite: el nombre y el apellido salen de RENAPER, no los tipea la persona.
    validar.mutate(datos, {
      // Los intentos que quedan y el bloqueo viven en la cuenta: se relee.
      onError: (error) => { if (["no_coincide", "validacion_bloqueada"].includes(error?.data?.codigo)) qc.invalidateQueries({ queryKey: ["portal", "cuenta"] }); },
    });
  };

  if (validar.isPending) return <Pantalla><Cabecera titulo="Validar identidad" />
    <Cargando texto="Validando tu identidad con RENAPER…" />
  </Pantalla>;
  if (codigo === "ya_validada") return <Cargando texto="Cargando tu cuenta…" />;
  if (MOTIVOS.has(codigo)) return <NoSePudo error={validar.error} onRevisar={() => validar.reset()} onReintentar={enviar} />;
  if (vigente(cuenta.validacion_bloqueada_hasta)) return <Bloqueada hasta={cuenta.validacion_bloqueada_hasta} />;

  const { campos, general } = erroresFormulario(validar.error, ["documento", "sexo", "numero_tramite"]);
  const cambiar = (clave, limpiar = (v) => v) => (e) => setDatos((d) => ({ ...d, [clave]: limpiar(e.target.value) }));
  const completo = datos.documento.length >= 7 && datos.sexo && datos.numero_tramite.length === LARGO_TRAMITE;
  const intentos = cuenta.intentos_restantes;
  return <Pantalla><Cabecera titulo="Validar identidad" />
    <Paso numero={2} total={2} />
    <form onSubmit={enviar} className="flex flex-1 flex-col" noValidate>
      <h2 className="mt-5 text-xl font-bold">Confirmá que sos vos</h2>
      <p className={`mt-2 ${TEXTO.cuerpo}`}>Con tu DNI y su número de trámite consultamos a RENAPER, el registro nacional de las personas. El número de trámite tiene que ser el de tu DNI más reciente.</p>
      <CampoTexto etiqueta="Número de documento" inputMode="numeric" autoComplete="off" placeholder="Ej.: 34.521.521"
        value={formatoDni(datos.documento)} onChange={cambiar("documento", (v) => soloDigitos(v).slice(0, 8))} error={campos.documento} />
      <fieldset className="mt-5">
        <legend className="text-xs font-medium text-texto-medio">Sexo, como figura en tu DNI</legend>
        <div className="mt-2 grid grid-cols-3 gap-2">
          {SEXOS.map(([valor, texto]) => <label key={valor} className={`flex h-11 cursor-pointer items-center justify-center rounded-md border text-sm font-medium has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-accent ${datos.sexo === valor ? "border-accent bg-accent-50 text-accent" : "border-campo-borde bg-superficie text-texto-medio"}`}>
            <input type="radio" name="sexo" value={valor} checked={datos.sexo === valor} onChange={cambiar("sexo")} className="sr-only" />{texto}
          </label>)}
        </div>
        {campos.sexo && <p className="mt-1.5 text-xs text-badge-error-fg">{campos.sexo}</p>}
      </fieldset>
      <CampoTexto etiqueta="Número de trámite" inputMode="numeric" autoComplete="off" placeholder="11 números" maxLength={LARGO_TRAMITE}
        ayuda={`Son ${LARGO_TRAMITE} números. Tiene que ser el de tu DNI más reciente: si lo renovaste, cambió.`}
        value={datos.numero_tramite} onChange={cambiar("numero_tramite", (v) => soloDigitos(v).slice(0, LARGO_TRAMITE))} error={campos.numero_tramite} />
      <details className="mt-3 rounded-md border border-borde bg-superficie p-3 text-xs text-texto-medio">
        <summary className="cursor-pointer font-semibold text-accent">¿Dónde encuentro el número de trámite?</summary>
        <p className="mt-2 leading-relaxed">En el DNI tarjeta está en el frente, en el dato «Trámite N.º» (también puede figurar como «N.º de trámite»). Es un número largo, distinto del número de documento. Copialo sin puntos ni espacios.</p>
      </details>
      {typeof intentos === "number" && <p className={`mt-4 ${TEXTO.nota}`}>Te {intentos === 1 ? "queda" : "quedan"} {plural(intentos, "intento", "intentos")} para validar.</p>}
      <Alerta>{general}</Alerta>
      <Pie>
        <Boton type="submit" disabled={!completo}>Validar identidad</Boton>
        <BotonSalir />
      </Pie>
    </form>
  </Pantalla>;
}

function Bloqueada({ hasta }) {
  return <Pantalla><Cabecera titulo="Validar identidad" />
    <Resultado icono="reloj" tono="aviso" titulo="Superaste los intentos" acciones={<BotonSalir />}>
      <p>Por seguridad, pausamos la validación de tu identidad{hasta ? <> hasta el <strong className="text-texto">{fechaHora(hasta)}</strong></> : ""}.</p>
      <p>Mientras tanto, buscá tu DNI más reciente para tener a mano el número de trámite.</p>
    </Resultado>
  </Pantalla>;
}

/** «No se pudo validar», con el motivo según el código del backend. */
function NoSePudo({ error, onRevisar, onReintentar }) {
  const { codigo, intentos_restantes: intentos, bloqueada_hasta: hasta } = error.data;
  const revisar = <Boton onClick={onRevisar}>Revisar los datos</Boton>;
  if (codigo === "validacion_bloqueada") return <Bloqueada hasta={hasta} />;
  const motivos = {
    no_coincide: {
      titulo: "No se pudo validar",
      texto: <>
        <p>No pudimos confirmar tu identidad con esos datos. Revisá el número de documento, el sexo y, sobre todo, el número de trámite: tiene que ser el de tu DNI más reciente.</p>
        {typeof intentos === "number" && <p className="font-semibold text-texto">Te {intentos === 1 ? "queda" : "quedan"} {plural(intentos, "intento", "intentos")}.</p>}
      </>,
      acciones: <>{revisar}<BotonSalir /></>,
    },
    documento_en_uso: {
      titulo: "Ese DNI ya tiene una cuenta",
      texto: <><p>Ese documento ya está validado en otra cuenta del portal. Le avisamos por email a esa cuenta.</p><p>Si el DNI es tuyo y no reconocés esa cuenta, comunicate con la institución.</p></>,
      acciones: <>{revisar}<BotonSalir /></>,
    },
    servicio_no_disponible: {
      titulo: "No pudimos consultar a RENAPER",
      texto: <p>El servicio de validación no está respondiendo. No cuenta como intento: probá de nuevo en un rato.</p>,
      acciones: <><Boton onClick={() => onReintentar()}>Reintentar</Boton><Boton variante="secundario" onClick={onRevisar}>Revisar los datos</Boton></>,
    },
    email_sin_verificar: {
      titulo: "Primero verificá tu email",
      texto: <p>Para validar tu identidad, antes tenés que abrir el enlace que te mandamos por correo.</p>,
      acciones: <Boton to="/mi/reenviar-verificacion">Pedir el correo de nuevo</Boton>,
    },
  }[codigo];
  return <Pantalla><Cabecera titulo="Validar identidad" />
    <Resultado titulo={motivos.titulo} tono={codigo === "servicio_no_disponible" ? "aviso" : "error"} acciones={motivos.acciones}>
      <div role="alert" className="space-y-2">{motivos.texto}</div>
    </Resultado>
  </Pantalla>;
}

/** Mi cuenta: los datos que validó RENAPER y cerrar sesión. Vive dentro de la app (#122), que le pasa la cuenta. */
export function MiCuenta() {
  const cuenta = useOutletContext();
  const perfil = usePerfilPortal();
  const p = perfil.data;
  return <>
    <Cabecera titulo="Mi cuenta" atras="/mi/inicio" />
    {perfil.isPending ? <Cargando texto="Cargando tus datos…" />
      : perfil.isError ? <Alerta>{mensajePortal(perfil.error, "No pudimos cargar tus datos.")}</Alerta>
        : <Tarjeta className="overflow-hidden">
          {[["Nombre y apellido", `${p.nombre} ${p.apellido}`], ["Documento", formatoDni(p.documento)], ["Fecha de nacimiento", p.fecha_nacimiento ? fechaCalendario(p.fecha_nacimiento) : null], ["Email", cuenta.email]]
            .filter(([, v]) => v).map(([k, v], i, filas) => <Fila key={k} titulo={k} detalle={<span className="break-words">{v}</span>} ultimo={i === filas.length - 1} />)}
        </Tarjeta>}
    <p className={`mt-4 ${TEXTO.nota}`}>Ves tus turnos, estudios y cobertura de todas las instituciones de la red donde te atendiste con este documento.</p>
    <Pie><BotonSalir /></Pie>
  </>;
}
