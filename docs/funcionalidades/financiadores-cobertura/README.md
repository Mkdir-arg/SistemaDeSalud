# Financiadores, cobertura y copagos

## Para qué sirve

Permite que una obra social, mutual o prepaga opere dentro de I-Core Salud con su
propia organización y sus propios usuarios, y que un hospital con convenio sepa,
**antes de realizar una prestación**, cuánto cubre el financiador, cuánto queda a
cargo del paciente y si todavía hay cupo disponible.

El vocabulario de este módulo está fijado en [`CONTEXT.md`](../../../CONTEXT.md):
afiliación, plan, cobertura, cupo, reserva, copago, cargo, cobro y saldo pendiente
tienen ahí una definición exacta y los sinónimos que conviene evitar. Este
documento describe el sistema; ese, el lenguaje.

Tres separaciones sostienen todo el módulo y conviene tenerlas presentes:

- **Arancel ≠ costo ≠ cargo ≠ cobro.** El arancel es el precio de la prestación;
  el costo es lo que le sale al hospital hacerla; el cargo es lo que alguien debe;
  el cobro es dinero que entró.
- **Cobertura ≠ deuda.** Usar cupo no crea deuda, y crear un cargo no consume cupo.
- **Consultar ≠ reservar.** Preguntar cuánto cubre no compromete nada; confirmar sí.

## Actores

- **Usuario del financiador**, con membresía propia de su organización: `admin`,
  `operador` o `auditor`. No es una membresía hospitalaria.
- **Administrativo de admisión** del hospital, que elige la afiliación del caso.
- **Personal clínico** del hospital, que consulta cobertura y confirma prestaciones.
- **Finanzas del hospital**, que sigue los cobros y resuelve los saldos.
- **Plataforma**, que da de alta las organizaciones y administra el catálogo común.

## Alcance implementado

### Portal del financiador

Ocho secciones en `/financiadores/:seccion`, más el catálogo común para plataforma:

| Sección | Qué permite |
|---|---|
| Planes | Crear y editar los planes de la organización. Un plan inactivo no se asigna a nuevas afiliaciones; las existentes se conservan |
| Cobertura | Reglas versionadas: porcentaje, tope de cantidad, período mensual o anual, desde cuándo rigen y si la prestación requiere autorización |
| Aranceles | Consultar el arancel general del hospital y la excepción acordada, cuando existe. El hospital es quien los carga |
| Padrón | Alta y actualización de afiliaciones, corrección de identidad, finalización y reactivación, con su historial |
| Consumos externos | Informar uso de cobertura fuera de Salud, de a uno o por archivo, y corregir cantidades |
| Autorizaciones | Resolver, observar o rechazar solicitudes, con designación expresa |
| Actividad en hospitales | Consultar y exportar la actividad de su cobertura, con filtros y totales |
| Convenios | Proponer, aceptar, rechazar y cerrar convenios; fijar el plazo de respuesta a autorizaciones |
| Usuarios | Administrar los operadores de la propia organización (sólo `admin`) |

### Lado hospital

Pantalla **Coberturas y copagos** (`/finanzas/coberturas`), con cuatro pestañas
según permisos:

- **Reservas y saldos**: reservas abiertas, antiguas y saldos a resolver, con
  filtros combinables por texto, prestación, estado, saldo y antigüedad.
- **Seguimiento de cobros**: cuentas por cobrar, pendientes administrativos y
  atenciones sin captura de cargos, exportables con auditoría.
- **Evaluar una prestación**: buscar un caso por paciente, documento o número y
  ver estado, importes y la siguiente acción.
- **Configuración**: habilitar el circuito para el hospital y fijar a partir de
  cuántos días una reserva se considera antigua; vincular prestaciones del
  hospital al catálogo común; proponer y aceptar convenios; cargar aranceles
  acordados.

### En el caso

- Elegir la afiliación al ingresar: verificada, pendiente o atención particular.
- Consultar cobertura de una prestación: arancel, porcentaje, cupo disponible,
  importe del financiador y del paciente, y el motivo de cada cifra.
- Registrar la aceptación del paciente del importe a su cargo.
- Confirmar, que reserva el cupo; registrar la realización, que lo consume; o
  liberar la reserva si la prestación no se hizo.
- Solicitar una autorización cuando la regla la exige, y seguir su estado.
- Ver el historial de cobertura del paciente.

### Importaciones

Dos contratos, con plantilla descargable y validación en el archivo:

| Tipo | Columnas |
|---|---|
| `padron` | N.º de afiliado · Documento · Nombre y apellido · Plan · Vigente desde |
| `consumos` | N.º de afiliado · Documento · Prestación · Fecha de prestación · Cantidad · Referencia externa |

El circuito es: subir → **resumen previo** → confirmar. Cada fila termina
`aplicada`, `rechazada`, en `revision` (posible duplicado) o `error_tecnico`
(reintentable). El lote informa las cuatro categorías por separado y se puede
descargar el listado de rechazos.

## Estados

| Objeto | Estados |
|---|---|
| Convenio | `propuesto` · `activo` · `rechazado` · `finalizado` |
| Afiliación en el caso | `verificada` · `pendiente` · `particular` |
| Reserva de cobertura | `reservada` · `realizada` · `liberada` |
| Distribución del cobro | `pendiente` (de resolución administrativa) · `resuelta` · `arancel_pendiente` · `evaluacion_pendiente` · `autorizacion_pendiente` · `sin_cobro` |
| Solicitud de autorización | `pendiente` · `observada` · `aprobada` · `rechazada` · `vencida` · `anulada` |
| Uso de una autorización | `comprometido` · `consumido` · `liberado` |

El historial de una afiliación registra `actualizacion`, `finalizacion` o
`reactivacion`, siempre con motivo y autor.

## Reglas de negocio

### Qué regla se aplica

La búsqueda es por precedencia, y se detiene en la primera que encuentra:

1. Plan del afiliado + esa prestación.
2. Plan del afiliado + la categoría de la prestación.
3. Financiador + esa prestación.
4. Financiador + la categoría de la prestación.

Si no hay ninguna, la prestación no está cubierta por esa cobertura.

### Cómo se calcula el importe

- El arancel aplicable es el **arancel acordado del convenio** si existe para esa
  prestación y fecha; si no, el **arancel general del hospital**. Una excepción sin
  importe devuelve explícitamente al arancel general.
- `total = arancel × cantidad`.
- `importe del financiador = arancel × cantidad cubierta × porcentaje / 100`.
- `importe del paciente = total − importe del financiador`. La parte del paciente
  se obtiene **por diferencia**, para que las dos partes sumen exactamente el total.
- Redondeo decimal a dos posiciones, mitad hacia arriba. No se usan `float`.
- Si el hospital declaró que no cobra esa prestación, los tres importes son cero.
  Eso no es lo mismo que no tener cobertura.

### Cupo

- El cupo disponible considera los usos en Salud, los consumos externos informados
  y las **reservas activas** del período; se comparte entre hospitales y es
  independiente por financiador.
- El período se cuenta por la **fecha de la prestación**, no por la de importación.
  El cupo mensual se renueva cada mes; el anual, el 1 de enero.
- Consultar la cobertura **no reserva**. Confirmar sí.
- La reserva pasa a consumo **una sola vez**: reintentos, doble clic y recuperación
  no duplican cupo ni obligaciones.
- Dos confirmaciones concurrentes no obtienen el mismo último uso: la decisión se
  serializa sobre la fila del afiliado y se revalida dentro de la transacción, no
  al mostrar el resumen.
- Una reserva antigua **no vence por tiempo**. Se libera después de confirmar que
  la prestación no se realizó. El hospital define a partir de cuántos días
  considerarla antigua.
- Agotar el cupo es distinto de no poder evaluar por falta de datos o por un error
  técnico: **un fallo técnico no se convierte en deuda del paciente**.

### Afiliación del caso

- La afiliación elegida al ingresar **se conserva durante ese caso**, aunque
  después cambie o venza. Una corrección expresa queda registrada y no modifica
  cargos anteriores.
- No se puede corregir la afiliación de un caso con reservas abiertas: primero hay
  que resolverlas.
- Finalizar una afiliación impide elegirla para casos nuevos y conserva la
  identidad, los casos anteriores y los consumos del período. Reactivarla conserva
  el acumulado previo; incluir a la persona en una importación **no la reactiva**.
- Una carga incremental del padrón no da de baja a nadie: las afiliaciones
  omitidas se conservan.
- No se unifican legajos por coincidencia aproximada de nombre o documento.

### Copago, saldos y resolución

- El copago se cobra al paciente sólo con su **aceptación de esa prestación y ese
  importe**. Una condición distinta exige volver a explicarla.
- Si el paciente no acepta y el hospital rechaza asumir el importe, queda un
  **saldo pendiente de resolución administrativa**: identificado, sin atribuirse
  automáticamente a nadie y **sin considerarse cobrado**.
- Resolverlo exige `resolver_cobertura` y registra quién decidió, con qué motivo y
  con qué respaldo. Una resolución no registra por sí sola un cobro.
- Reducir o cancelar una cuenta no devuelve dinero por sí solo.

### Privacidad y alcance

- El financiador ve prestación, fecha, cantidad e importe propio. **No accede a la
  historia clínica.**
- Un financiador no consulta el padrón ni los consumos de otro, ni siquiera para
  detectar un cambio de cobertura.
- Un usuario con varios ámbitos elige una organización concreta; cada URL,
  exportación, búsqueda y operación masiva vuelve a verificar ese ámbito en el
  servidor. Conocer un identificador válido no concede acceso.
- Cerrar un convenio conserva las prestaciones y los cargos registrados. El acceso
  histórico queda limitado a las operaciones propias que aún requieren resolución
  económica; un saldo del paciente no lo habilita por sí solo.
- Las consultas y exportaciones autorizadas dejan evidencia administrativa, sin
  datos de la historia clínica.

## Pantallas y rutas

- `/financiadores/:seccion?` — portal del financiador.
- `/financiadores/activar` — alta de la cuenta de un usuario invitado, sin sesión.
- `/finanzas/coberturas` — «Coberturas y copagos» del hospital.
- Panel de cobertura, aceptación y autorizaciones dentro de `/casos/:id`.
- Afiliaciones vigentes en la ficha del padrón, `/padron/:id`.

## Entidades y endpoints

| Recurso | Acciones principales |
|---|---|
| `financiadores` | `planes`, `editar-plan`, `reglas`, `catalogo`, `padron`, `corregir-identidad`, `finalizar-afiliacion`, `reactivar-afiliacion`, `consumos`, `corregir-consumo`, `convenios`, `aceptar-convenio`, `rechazar-convenio`, `cerrar-convenio`, `plazo-autorizacion`, `aranceles`, `actividad`, `instituciones`, `usuarios`, `activar`, `importaciones`, `confirmar-importacion`, `plantilla`, `rechazos`, `resumen` |
| `coberturas` | `opciones`, `configurar`, `vincular-prestacion`, `convenio`, `aceptar-convenio`, `cerrar-convenio`, `rechazar-convenio`, `arancel`, `afiliados`, `afiliacion`, `evaluar`, `reservar`, `liberar`, `resolver`, `completar`, `recuperables`, `revisar-contexto`, `recuperar` |
| `autorizaciones-cobertura` | `contexto`, `resolver`, `reenviar`, `anular` |
| `seguimiento-cobros` | Cuentas por cobrar, pendientes administrativos y atenciones sin captura |
| Acciones del caso | `casos/{id}/cobertura`, `cobertura-afiliacion`, `cobertura-evaluar`, `cobertura-confirmar` |

Modelos en `backend/apps/financiadores/models.py`: `Financiador`,
`MembresiaFinanciador`, `PrestacionComun`, `VinculoPrestacion`, `Plan`,
`ReglaCobertura`, `Convenio`, `Afiliado`, `HistorialAfiliacion`,
`VinculoCiudadano`, `AfiliacionCaso`, `ConfiguracionHospital`, `ArancelConvenio`,
`ReservaCobertura`, `ConsumoExterno`, `DistribucionCobro`, `ResolucionSaldo`,
`Importacion`, `EventoCobertura`, `RevisionContexto`, `SolicitudAutorizacion`,
`EventoAutorizacion`, `UsoAutorizacion`.

## Permisos

- **Del lado del financiador**: `MembresiaFinanciador` con rol `admin`, `operador`
  o `auditor`. `auditor` es sólo lectura; `admin` agrega usuarios, planes y
  convenios. Resolver autorizaciones exige además una **designación expresa**: ni
  administrar la organización ni ser plataforma alcanza por sí solo.
- **Del lado del hospital**: concesiones financieras explícitas, con su institución,
  sus áreas y su alcance sensible. Las que usa este circuito son
  `registrar_aceptacion`, `resolver_cobertura`, `configurar_cobros`, `ver_dinero`
  y `registrar_dinero`. El administrador de institución las hereda todas dentro de
  su institución.
- Operar sobre un caso exige además `casos_operar` y pertenecer al área del caso.

Ver [`docs/ROLES-Y-PERMISOS.md`](../../ROLES-Y-PERMISOS.md) §3.1 y §3.2.

## Integraciones

- **Casos**: la afiliación y las reservas cuelgan del caso; el hecho asistencial
  sigue siendo de Casos.
- **Finanzas**: la distribución del cobro genera las obligaciones y los cobros. El
  precio y el dinero siguen viviendo en Finanzas.
- **Registros clínicos**: el vínculo explícito entre afiliado y paciente
  hospitalario; las afiliaciones vigentes se muestran separadas de la obra social
  declarada como texto libre.
- **FHIR**: recurso `Coverage`, buscado por la referencia local del paciente.
- **Red y traslados**: la identidad del paciente se contrasta contra las variantes
  legadas del documento antes de vincular fichas en el destino.

## Límites conocidos

- No hay facturación fiscal ni conciliación bancaria.
- No se dan bajas de padrón por archivo: la finalización es explícita.
- El catálogo común lo administra plataforma; la equivalencia entre una prestación
  del hospital y una del catálogo es **explícita**, nunca inferida por nombre.
- La operación real con datos productivos no está validada: lo verificado es el
  piloto integral con dos hospitales, dos financiadores y exportaciones de 5.000
  filas.

## Puntos a validar

- Documentos, numeración familiar y cambios de identificadores en el padrón.
- Antigüedad y permisos para liberar reservas antiguas en operación real.
- Volumen y contención de la serialización por afiliado con datos de producción.
- Circuito de aceptación del paciente fuera del mostrador, si se decide abrirlo.

## Antecedentes

El diseño completo —arquitectura elegida y alternativas descartadas, invariantes
de cálculo, identidad y privacidad, y la secuencia de lotes L0–L7— está archivado
en [`docs/historico/plans/financiadores/`](../../historico/plans/financiadores/README.md).
Es la referencia para entender **por qué** se modeló así antes de cambiarlo.

Para ver el circuito funcionando, el recorrido verificado de 20 minutos está en
[`docs/entornos/guia-demo-financiadores.md`](../../entornos/guia-demo-financiadores.md).
