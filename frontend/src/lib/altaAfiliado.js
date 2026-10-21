// Alta de afiliación por pasos: definición de campos, validación por paso y
// armado del POST al padrón. Sin React, para poder probarlo con node:test.
import { PARENTESCOS, REGIMENES } from "../components/financiadores/padronCampos.js";

const opciones = (valores) => Object.entries(valores).map(([id, nombre]) => ({ id, nombre }));
const TIPOS_DOCUMENTO = opciones({ DNI: "DNI", LE: "LE", LC: "LC", CI: "CI", PAS: "Pasaporte", OTRO: "Otro" });
const SEXOS = opciones({ F: "Femenino", M: "Masculino", X: "X" });

export const hoyAR = () => new Date().toLocaleDateString("en-CA", { timeZone: "America/Argentina/Buenos_Aires" });
export const soloDigitos = (valor) => String(valor ?? "").replace(/\D/g, "");

/** 20301234567 → 20-30123456-7, también mientras se escribe. */
export function formatoCuit(valor) {
  const d = soloDigitos(valor).slice(0, 11);
  return [d.slice(0, 2), d.slice(2, 10), d.slice(10)].filter(Boolean).join("-");
}

/** Dígito verificador de CUIT/CUIL (módulo 11). */
export function cuitValido(valor) {
  const d = soloDigitos(valor);
  if (d.length !== 11) return false;
  const suma = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2].reduce((total, peso, i) => total + peso * Number(d[i]), 0);
  const verificador = 11 - (suma % 11);
  if (verificador === 10) return false;
  return (verificador === 11 ? 0 : verificador) === Number(d[10]);
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const CODIGO_POSTAL = /^(\d{4}|[A-Za-z]\d{4}[A-Za-z]{3})$/;

export const PASOS = [
  { key: "identificacion", titulo: "Identificación", obligatorio: true },
  { key: "afiliacion", titulo: "Afiliación", obligatorio: true },
  { key: "contacto", titulo: "Contacto y domicilio", corto: "Contacto" },
  { key: "laboral", titulo: "Situación laboral" },
  { key: "revision", titulo: "Revisión" },
];

// `paso` ubica cada campo; `visible` decide si se muestra y si viaja en el POST.
export const CAMPOS_ALTA = [
  // Orden del wireframe: la grilla es de dos columnas y se completa fila por fila.
  { paso: 0, name: "tipo_documento", label: "Tipo de documento", required: true, options: TIPOS_DOCUMENTO },
  { paso: 0, name: "documento", label: "Número de documento", required: true, maxLength: 80, inputMode: "numeric" },
  { paso: 0, name: "cuil", label: "CUIL", maxLength: 13, inputMode: "numeric", placeholder: "20-30123456-7", hint: "11 números, sin guiones. Debe coincidir con el documento." },
  { paso: 0, name: "numero", label: "Número de afiliado", required: true, maxLength: 80, hint: "Como texto, con sus ceros." },
  { paso: 0, name: "nombres", label: "Nombres", required: true, maxLength: 160, autoComplete: "given-name", placeholder: "Ej.: María José" },
  { paso: 0, name: "apellidos", label: "Apellidos", required: true, maxLength: 160, autoComplete: "family-name", placeholder: "Ej.: González Pérez" },
  { paso: 0, name: "sexo", label: "Sexo registrado en el DNI", options: SEXOS },
  { paso: 0, name: "fecha_nacimiento", label: "Fecha de nacimiento", type: "date", hint: "No puede ser una fecha futura." },
  { paso: 1, name: "cobertura_habilitada", label: "Habilitar cobertura", boolean: true },
  { paso: 1, name: "plan", label: "Plan", requiredSi: (d) => d.cobertura_habilitada !== false, numeric: true },
  { paso: 1, name: "desde", label: "Fecha de afiliación", required: true, type: "date", hint: "Por defecto, hoy. Admite fechas retroactivas. Esta fecha no habilita cobertura por sí sola." },
  { paso: 1, name: "delegacion", label: "Delegación", required: true, maxLength: 100, placeholder: "Ej.: Sede Central" },
  { paso: 1, name: "motivo", label: "Motivo del alta", required: true, maxLength: 255, placeholder: "Ej.: adhesión voluntaria" },
  { paso: 1, name: "titular", label: "Titular", numeric: true, visible: (d) => d.grupo === "familiar", requiredSi: (d) => d.grupo === "familiar" },
  { paso: 1, name: "parentesco", label: "Parentesco", options: opciones(PARENTESCOS), visible: (d) => d.grupo === "familiar", requiredSi: (d) => d.grupo === "familiar" },
  { paso: 2, name: "telefono", label: "Teléfono", type: "tel", maxLength: 60, autoComplete: "tel", placeholder: "11 5555-0000", hint: "Con código de área, sin 0 ni 15." },
  { paso: 2, name: "email", label: "Correo electrónico", type: "email", maxLength: 254, autoComplete: "email", placeholder: "nombre@correo.com" },
  { paso: 2, name: "celular", label: "Otro teléfono", type: "tel", maxLength: 60, autoComplete: "tel", visible: (d) => d.otro_telefono || d.celular },
  { paso: 2, name: "provincia", label: "Provincia", maxLength: 100, autoComplete: "address-level1", placeholder: "Ej.: Buenos Aires" },
  { paso: 2, name: "partido", label: "Partido / Departamento", maxLength: 100, placeholder: "Ej.: Lanús" },
  { paso: 2, name: "localidad", label: "Localidad", maxLength: 100, autoComplete: "address-level2", placeholder: "Ej.: Lanús Oeste" },
  { paso: 2, name: "codigo_postal", label: "Código postal", maxLength: 20, autoComplete: "postal-code", hint: "4 números o CPA (ej.: B1824ABC)." },
  { paso: 2, name: "calle", label: "Calle", maxLength: 160, autoComplete: "address-line1" },
  { paso: 2, name: "altura", label: "Altura", maxLength: 20 },
  { paso: 2, name: "piso", label: "Piso", maxLength: 20 },
  { paso: 2, name: "departamento", label: "Departamento", maxLength: 20 },
  { paso: 3, name: "regimen", label: "Régimen", options: opciones(REGIMENES), hint: "Los campos de abajo cambian según el régimen elegido." },
  { paso: 3, name: "cuit_empleador", label: "CUIT del empleador", maxLength: 13, inputMode: "numeric", placeholder: "30-71234567-9", visible: (d) => d.regimen === "dependencia" },
  { paso: 3, name: "empleador", label: "Empleador (razón social)", maxLength: 160, visible: (d) => d.regimen === "dependencia" },
  { paso: 3, name: "actividad_laboral", label: "Actividad laboral", maxLength: 160, placeholder: "Ej.: operario, administrativo", visible: (d) => d.regimen === "dependencia" },
  { paso: 3, name: "telefono_laboral", label: "Teléfono laboral", type: "tel", maxLength: 60, placeholder: "11 4444-0000", visible: (d) => d.regimen === "dependencia" },
  { paso: 3, name: "email_laboral", label: "Correo laboral", type: "email", maxLength: 254, placeholder: "nombre@empresa.com", visible: (d) => d.regimen === "dependencia" },
  { paso: 3, name: "domicilio_laboral", label: "Domicilio laboral", maxLength: 255, placeholder: "Calle y altura", visible: (d) => d.regimen === "dependencia" },
  { paso: 3, name: "subsidio_desde", label: "Subsidio desde", type: "date", visible: (d) => d.regimen === "desempleo" },
  { paso: 3, name: "subsidio_hasta", label: "Subsidio hasta", type: "date", hint: "Debe ser igual o posterior a «Subsidio desde».", visible: (d) => d.regimen === "desempleo" },
];

export const visible = (campo, datos) => !campo.visible || Boolean(campo.visible(datos));
export const requerido = (campo, datos) => Boolean(campo.required || campo.requiredSi?.(datos));
export const camposDelPaso = (paso, datos) => CAMPOS_ALTA.filter((campo) => campo.paso === paso && visible(campo, datos));
const vacio = (valor) => valor == null || String(valor).trim() === "";

export const datosIniciales = () => ({ tipo_documento: "DNI", desde: hoyAR(), grupo: "titular", cobertura_habilitada: true });

/** ¿Cargó algo más que los valores por defecto? Decide si cancelar pide confirmación. */
export function tieneDatos(datos) {
  const base = datosIniciales();
  return Object.entries(datos).some(([k, v]) => !vacio(v) && (v !== false || k === "cobertura_habilitada") && String(v) !== String(base[k] ?? ""));
}

/** ¿El paso opcional tiene algo cargado? Sin datos se muestra «Pendiente», no «Completo». */
export const pasoConDatos = (paso, datos) => camposDelPaso(paso, datos).some((campo) => !vacio(datos[campo.name]));

/** Errores del paso como { campo: mensaje }, en el orden en que se muestran. */
export function validarPaso(paso, datos, hoy = hoyAR()) {
  const errores = {};
  for (const campo of camposDelPaso(paso, datos)) {
    const valor = datos[campo.name];
    if (requerido(campo, datos) && vacio(valor)) {
      errores[campo.name] = campo.name === "titular" ? "Buscá y elegí al titular." : campo.options || campo.numeric ? `Seleccioná ${campo.label.toLowerCase()}.` : `Completá ${campo.label.toLowerCase()}.`;
      continue;
    }
    if (vacio(valor)) continue;
    const texto = String(valor).trim();
    if (campo.maxLength && texto.length > campo.maxLength) errores[campo.name] = `Hasta ${campo.maxLength} caracteres.`;
    else if (campo.type === "email" && !EMAIL.test(texto)) errores[campo.name] = "Ingresá un correo válido, como nombre@correo.com.";
    else if (campo.name === "documento" && datos.tipo_documento === "DNI" && !/^\d{7,8}$/.test(soloDigitos(texto))) errores[campo.name] = "El DNI tiene 7 u 8 números.";
    else if (campo.name === "cuil") {
      if (soloDigitos(texto).length !== 11) errores.cuil = "El CUIL tiene 11 números.";
      else if (!cuitValido(texto)) errores.cuil = "El CUIL no es válido: revisá el dígito verificador.";
      else if (datos.tipo_documento === "DNI" && datos.documento && soloDigitos(texto).slice(2, 10) !== soloDigitos(datos.documento).padStart(8, "0")) errores.cuil = "El CUIL no coincide con el número de documento.";
    } else if (campo.name === "cuit_empleador") {
      if (soloDigitos(texto).length !== 11) errores.cuit_empleador = "El CUIT tiene 11 números.";
      else if (!cuitValido(texto)) errores.cuit_empleador = "El CUIT no es válido: revisá el dígito verificador.";
    } else if (campo.name === "fecha_nacimiento" && texto > hoy) errores[campo.name] = "No puede ser una fecha futura.";
    else if (campo.name === "desde" && texto > hoy) errores[campo.name] = "La fecha de afiliación no puede ser futura.";
    else if (campo.name === "codigo_postal" && !CODIGO_POSTAL.test(texto)) errores[campo.name] = "Ingresá 4 números o el CPA (ej.: B1824ABC).";
    else if (campo.name === "subsidio_hasta" && datos.subsidio_desde && texto < datos.subsidio_desde) errores[campo.name] = "Debe ser igual o posterior a «Subsidio desde».";
  }
  return errores;
}

/** Los obligatorios del alta viven en los pasos 1 y 2. */
export const obligatoriosCompletos = (datos) => PASOS.every((paso, i) => !paso.obligatorio || !Object.keys(validarPaso(i, datos)).length);

/** «Nombres Apellidos», como se lista en el padrón. */
export const nombreParaMostrar = (datos) => [datos.nombres, datos.apellidos].map((v) => String(v ?? "").trim()).filter(Boolean).join(" ");

/** Cuerpo del POST: sólo campos visibles y cargados; identificadores como texto sin separadores. */
export function cuerpoAlta(datos) {
  const body = { solo_crear: true, nombre: nombreParaMostrar(datos), cobertura_habilitada: datos.cobertura_habilitada !== false };
  for (const campo of CAMPOS_ALTA) {
    if (!visible(campo, datos)) continue;
    const valor = datos[campo.name];
    if (vacio(valor)) continue;
    const texto = String(valor).trim();
    body[campo.name] = campo.boolean ? Boolean(valor) : campo.numeric ? Number(valor) : ["cuil", "cuit_empleador"].includes(campo.name) ? soloDigitos(texto) : texto;
  }
  return body;
}

/** Paso al que pertenece un error del servidor, para llevar ahí al usuario. */
export function pasoDeCampo(nombre) {
  if (nombre === "nombre") return 0;
  return CAMPOS_ALTA.find((campo) => campo.name === nombre)?.paso ?? null;
}
