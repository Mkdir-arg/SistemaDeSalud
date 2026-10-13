const texto = (name, label, maxLength = 160) => ({ name, label, maxLength });
const fecha = (name, label) => ({ name, label, type: "date", nullable: true });
const opciones = (name, label, valores) => ({ name, label, options: Object.entries(valores).map(([id, nombre]) => ({ id, nombre })) });
export const REGIMENES = { dependencia: "Relación de dependencia", monotributo: "Monotributo", pasivo: "Jubilado / pensionado", desempleo: "Desempleo", adherente: "Adherente" };
export const TRAMITES = { pendiente: "Pendiente", en_revision: "En revisión", observado: "Observado", completo: "Completo" };
export const ADMINISTRATIVOS = { activo: "Activo administrativamente", en_tramite: "En trámite", baja_programada: "Baja programada", baja_administrativa: "Baja administrativa" };
export const PARENTESCOS = { conyuge: "Cónyuge", hijo: "Hijo", hija: "Hija", conviviente: "Conviviente", otro: "Otro" };
export const TIPOS_PLAN = { base: "Base", superador: "Superador", privado: "Privado" };

export const BLOQUES_PADRON = [
  { titulo: "Identidad", campos: [texto("numero", "Número de afiliado", 80), texto("documento", "Documento", 80), texto("nombre", "Nombre para mostrar"), opciones("tipo_documento", "Tipo de documento", { DNI: "DNI", LE: "LE", LC: "LC", CI: "CI", PAS: "Pasaporte", OTRO: "Otro" }), texto("cuil", "CUIL", 11), texto("nombres", "Nombres"), texto("apellidos", "Apellidos"), opciones("sexo", "Sexo", { F: "Femenino", M: "Masculino", X: "X" }), fecha("fecha_nacimiento", "Fecha de nacimiento"), texto("nacionalidad", "Nacionalidad", 80), texto("estado_civil", "Estado civil", 40)] },
  { titulo: "Contacto", campos: [texto("telefono", "Teléfono", 60), texto("celular", "Celular", 60), { ...texto("email", "Correo electrónico", 254), type: "email" }] },
  { titulo: "Domicilio", campos: [texto("calle", "Calle"), texto("altura", "Altura", 20), texto("piso", "Piso", 20), texto("departamento", "Departamento", 20), texto("codigo_postal", "Código postal", 20), texto("localidad", "Localidad", 100), texto("partido", "Partido", 100), texto("provincia", "Provincia", 100)] },
  { titulo: "Régimen y trabajo", campos: [opciones("regimen", "Régimen", REGIMENES), texto("empleador", "Empleador"), texto("cuit_empleador", "CUIT del empleador", 11), texto("actividad_laboral", "Actividad laboral"), texto("domicilio_laboral", "Domicilio laboral", 255), texto("telefono_laboral", "Teléfono laboral", 60), { ...texto("email_laboral", "Correo laboral", 254), type: "email" }, fecha("subsidio_desde", "Subsidio desde"), fecha("subsidio_hasta", "Subsidio hasta")] },
  { titulo: "Trámite y credencial", descripcion: "La credencial se registra como emitida externamente. Completar el trámite requiere documentación aceptada y credencial informada; el servidor verifica los requisitos.", campos: [fecha("alta_administrativa", "Alta administrativa"), texto("delegacion", "Delegación", 100), opciones("estado_tramite", "Estado del trámite", TRAMITES), texto("credencial_tipo", "Tipo de credencial externa", 80), fecha("credencial_fecha", "Fecha de credencial externa")] },
  { titulo: "Baja administrativa", descripcion: "Estas fechas informadas no finalizan derechos ni ejecutan un corte prestacional. La cobertura conserva su finalización explícita existente.", campos: [opciones("causa_baja", "Causa de baja administrativa", { cese_laboral: "Cese laboral", traspaso: "Traspaso", fallecimiento: "Fallecimiento", edad: "Edad", renuncia: "Renuncia", mora: "Mora informada", judicial: "Judicial", otra: "Otra" }), fecha("solicitud_baja", "Solicitud de baja"), fecha("baja_efectiva", "Baja administrativa efectiva"), fecha("fin_prestacional_informado", "Fin prestacional informado"), texto("motivo_baja", "Motivo de baja administrativa", 255)] },
];

export const CAMPOS_FAMILIA = [{ name: "titular", label: "ID del titular", numeric: true }, opciones("parentesco", "Parentesco", PARENTESCOS)];
const booleanoOpcional = (name, label) => ({ ...opciones(name, label, { true: "Sí", false: "No" }), tristate: true });
export const CAMPOS_SALUD = [booleanoOpcional("cud", "CUD informado"), texto("cud_numero", "Número de CUD", 80), fecha("cud_presentado_en", "Presentación de CUD"), fecha("cud_vencimiento", "Vencimiento de CUD"), texto("cud_referencia", "Referencia del original CUD", 255), booleanoOpcional("dbt", "DBT informada"), { ...texto("cronicas", "Condiciones crónicas informadas", 1000), textarea: true }, opciones("parentesco_sensible", "Parentesco protegido", { discapacidad: "Discapacidad" })];
export const CAMPOS_COBRANZA = [opciones("situacion", "Situación de cuenta informada", { sin_informar: "Sin informar", al_dia: "Al día (informado)", deuda: "Deuda (informada)", plan_pago: "Plan de pago (informado)", exento: "Exento (informado)" }), texto("fuente", "Fuente de la información"), fecha("informado_en", "Fecha de información"), opciones("modalidad", "Modalidad de pago", { efectivo: "Efectivo", transferencia: "Transferencia", debito_cbu: "Débito CBU", tarjeta: "Tarjeta", cupon: "Cupón", recibo_sueldo: "Recibo de sueldo" }), { name: "dia_vencimiento", label: "Día de vencimiento informado", numeric: true, type: "number", min: 1, max: 31 }, texto("cupon", "Referencia de cupón externo", 120), texto("proveedor_cupon", "Proveedor de cupón externo", 80), texto("banco", "Banco informado", 120), texto("cbu", "CBU", 22), texto("cuit_titular", "CUIT del titular de cuenta", 11), texto("titular_cuenta", "Titular de la cuenta"), texto("emisor_tarjeta", "Emisor de tarjeta (sin número ni código)", 80)];
export const TIPOS_LEGAJO = { dni: "Documento de identidad", cuil: "CUIL", domicilio: "Domicilio", laboral: "Laboral", estudio: "Estudio", matrimonio: "Matrimonio", nacimiento: "Nacimiento" };
export const ESTADOS_LEGAJO = { pendiente: "Pendiente", presentado: "Presentado", observado: "Observado", verificado: "Verificado", exento: "Exento" };
export const CAMPOS_LEGAJO = [opciones("tipo", "Tipo de presentación", TIPOS_LEGAJO), opciones("estado", "Estado de presentación", ESTADOS_LEGAJO), fecha("presentado_en", "Fecha de presentación"), fecha("verificado_en", "Fecha de verificación"), fecha("vence_en", "Vencimiento"), texto("referencia", "Referencia al original", 255)];

export function valorCampoPadron(campo, valor) {
  if (valor == null || valor === "") return "Sin informar";
  if (typeof valor === "object") return Object.entries(valor).map(([name, dato]) => {
    const detalle = CAMPOS_LEGAJO.find((item) => item.name === name) || { name, label: name };
    return `${detalle.label}: ${valorCampoPadron(detalle, dato)}`;
  }).join("\n");
  if (campo.options) return campo.options.find((opcion) => String(opcion.id) === String(valor))?.nombre || String(valor);
  if (campo.type === "date") return String(valor).split("-").reverse().join("/");
  return String(valor);
}
