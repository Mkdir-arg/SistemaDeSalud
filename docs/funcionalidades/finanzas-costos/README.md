# Finanzas, costos y cobros

## Para qué sirve

Permite registrar y revisar los gastos del hospital, controlar que la carga mensual
esté completa, distribuir los gastos aprobados entre las atenciones elegibles, saber
cuánto cuesta una atención, y seguir el dinero que corresponde pagar y cobrar.

Cuatro magnitudes distintas que el módulo nunca suma entre sí:

| | Qué es | Qué **no** es |
|---|---|---|
| **Costo** | Lo que le sale al hospital prestar la atención | No es un precio ni un cargo al paciente |
| **Gasto** | Una erogación del hospital: electricidad, insumos, mantenimiento | No es el costo de una atención hasta que se reparte |
| **Cargo** | Lo que alguien debe por una prestación realizada | No es dinero cobrado |
| **Cobro** | Dinero efectivamente registrado | No es saldo disponible ni rentabilidad |

Lo que el módulo **no** es: contabilidad general, facturación fiscal, conciliación
bancaria, ni el costo total del hospital. Todavía pueden faltar fuentes que no
incorpora.

## Quién usa cada parte

- El personal administrativo carga gastos en las áreas autorizadas.
- Una persona con permiso de aprobación acepta o rechaza las cargas delegadas.
- Quien configura Finanzas define qué gastos se esperan y qué conceptos se
  distribuyen.
- El personal clínico registra la atención como parte de su trabajo habitual; los
  componentes financieros configurados se calculan automáticamente.
- Finanzas sigue las cuentas, registra los cobros y resuelve los saldos.

### Permisos

Finanzas **no se gobierna por roles ni por capacidades clínicas**, sino por
concesiones explícitas ligadas a una membresía, con su institución, sus áreas y si
alcanzan información sensible. Son dieciocho acciones:

| Grupo | Acciones |
|---|---|
| Costos | `ver_costos`, `configurar_componentes`, `corregir_costos`, `aprobar_costos` |
| Gastos | `ver_gastos`, `registrar_gastos`, `corregir_gastos`, `aprobar_gastos`, `configurar_gastos_esperados` |
| Reparto | `configurar_repartos` |
| Dinero | `ver_dinero`, `registrar_dinero`, `aprobar_dinero`, `corregir_dinero`, `configurar_cobros` |
| Cobertura | `registrar_aceptacion`, `resolver_cobertura` |
| Auditoría | `auditar_finanzas` |

> **Cambió el 18/09/2026.** El **administrador de institución hereda las dieciocho
> acciones** dentro de su institución, para todas las áreas e información sensible.
> Antes heredaba solamente `ver_costos` y `ver_gastos` y el resto se otorgaba a
> mano. Las heredadas se identifican como **Por rol** y no se revocan desde las
> casillas.

Cualquier otra persona las recibe de a una. Una persona de contabilidad puede
tenerlas sin convertirse en administradora ni obtener permisos clínicos; y poder
ver un gasto no concede acceso al registro financiero completo.

Se administran en **Administración → Usuarios → Editar usuario → Permisos
financieros**: sección plegable, hasta tres columnas, con **Guardar permisos
financieros** separado de los datos personales. Si alguna acción no es válida no se
aplica ninguna modificación; si otro administrador los cambió mientras tanto, se
exige volver a consultarlos.

Dos combinaciones que conviene conocer:

- Para el resumen de verificación de actividad hacen falta **los dos permisos**:
  configurar repartos y consultar gastos, en la misma institución y área.
  Configurar por sí solo muestra cantidades de atenciones, no importes.
- Operar dinero desde pantalla requiere también lectura de dinero del mismo alcance.

Cada consulta autorizada queda registrada en auditoría financiera. Si no se puede
guardar ese registro, el resumen no se entrega y se informa que hay que reintentar.

## Los cuatro momentos

| Momento | Qué ocurre |
|---|---|
| Abrir un caso | Se inicia el recorrido de atención. No genera por sí solo un costo |
| Completar la atención | Se conserva un registro financiero con paciente y área de origen, y se procesan los componentes directos disponibles |
| Aprobar un gasto | Se acepta una fuente de gasto del hospital. No altera silenciosamente los componentes directos previos |
| Repartir un gasto | Se distribuye su importe efectivo entre las atenciones elegibles. Se conserva el total exacto y el historial |

La firma posterior de la atención no duplica su registro financiero. Un costo
directo completo sólo cubre los componentes configurados: no implica que se conozca
el costo total del paciente ni del hospital.

## Las pestañas

`/finanzas` tiene siete pestañas, y cada una aparece según los permisos:

| Pestaña | Requiere | Qué muestra |
|---|---|---|
| Resumen | `ver_gastos` | El panorama del mes: gastos, pagos y cobros, costos por atención |
| Gastos registrados | `ver_gastos` | Cada gasto con su importe original, sus ajustes y el resultante |
| Gastos mensuales | `ver_gastos` | La lista de comprobación de lo que cada área espera cargar |
| Repartos | `ver_gastos` | La distribución de cada gasto aprobado entre atenciones |
| Costos por atención | `ver_costos` | Costo directo y compartido de cada atención, y su configuración |
| Pagos y cobros | `ver_dinero` | Cuentas, movimientos y devoluciones |
| Reportes | `ver_gastos` o `ver_dinero` | Comparación entre períodos y descarga en PDF |

Además, **Coberturas y copagos** (`/finanzas/coberturas`) es una pantalla aparte:
ver [Financiadores, cobertura y copagos](../financiadores-cobertura/README.md).

Los botones principales dependen de la pestaña; **Acciones de finanzas**, siempre a
la derecha, conserva las demás acciones autorizadas. Ocultar una acción por pestaña
no concede ni revoca permisos. Inicio ofrece un acceso rápido a Finanzas según
permisos efectivos.

## Resumen: el panorama del mes

Reúne tres bloques. **Cada uno consulta su propia fuente y falla por separado**: un
error o una restricción de permisos en uno no oculta ni convierte en cero a los
demás. Son magnitudes distintas del mismo período y **no se suman**: el Resumen no
publica un total común.

**Gastos** muestra cinco cifras: aprobados, por aprobar, distribuido, sin distribuir
y gastos mensuales pendientes. El aprobado ya contiene lo distribuido:
**aprobado = distribuido + sin distribuir**. Las cifras corresponden al mes, área y
permisos elegidos, no necesariamente a todo el hospital.

**Pagos y cobros** muestra cobros netos, pagos netos, su diferencia y la cantidad de
movimientos por aprobar, con un gráfico por área. Se cuentan por **fecha efectiva**
dentro del mes calendario seleccionado, no por mes económico: una cuenta puede
pertenecer a otro mes. La diferencia no es saldo disponible ni rentabilidad, y los
movimientos por aprobar están excluidos de los netos.

**Costos por atención** muestra las atenciones del mes, el costo directo conocido, el
gasto compartido atribuido y cuántas atenciones tienen componentes pendientes, con un
gráfico agrupable **por área o por prestación**. Las dos series se dibujan lado a
lado y nunca apiladas: el compartido explica un gasto aprobado que ya figura en el
bloque de Gastos, no es un costo adicional. La prestación proviene del catálogo
congelado al completarse cada atención; las que no tenían prestación configurada se
agrupan aparte y **no equivalen a costo cero**.

### Del gráfico a los registros

El bloque de gastos ofrece cuatro representaciones: **Barras**, **Dos niveles**,
**Evolución mensual** y **Listado**.

- Clic en una barra abre los gastos o repartos correspondientes, conservando mes,
  área, concepto y estado.
- El selector compara **Gastos** (aprobado y por aprobar) o **Distribución del
  aprobado** (distribuido y sin distribuir). Los dos niveles representan el mismo
  dinero: no se suman.
- **Ordenar** permite ver de mayor a menor importe, de menor a mayor o por
  área/concepto. Compara la suma de las dos series elegidas, no ambas comparaciones
  entre sí.
- Los colores interiores recorren una escala fría → cálida según la participación.
  Se recalculan con los filtros y no identifican permanentemente un concepto. **Rojo
  no significa error ni gasto indebido.** El exterior es neutro: sólido para
  aprobado/distribuido, rayado para por aprobar/sin distribuir.
- **Listado** conserva todas las cifras exactas y sus enlaces, y está disponible
  aunque falle la descarga del gráfico. Los dibujos usan una escala aproximada; el
  detalle y el listado conservan los centavos originales.
- Los ajustes negativos se muestran con su signo; no se dibujan como porciones
  positivas de los anillos.
- Si hay una distribución pendiente, no se dibuja como cero ni como resultado
  definitivo.
- Las animaciones se omiten si el dispositivo pide movimiento reducido.

### Evolución mensual

Consulta 6 o 12 meses hasta el mes económico seleccionado. Comienza con **todos los
conceptos visibles seleccionados**. Cada concepto tiene una línea y un color estable
que no cambia al variar el importe, el período o la selección. Usa el importe
aprobado con sus ajustes, sólo de áreas con control vigente en cada mes y dentro de
los permisos.

- Línea y puntos llenos: meses con carga declarada completa (o «no corresponde») y
  sin gastos pendientes de aprobación.
- Puntos huecos: importes provisionales porque falta completar carga o aprobación, o
  el mes sigue abierto. No se unen como tendencia confirmada.
- Sin control o sin carga: **se deja un hueco, no una caída ficticia a cero.** Un
  cero con carga declarada completa sí se muestra como dato.
- **Comparar con referencias** las dibuja con el mismo color y trazo discontinuo.
  Las referencias conservan todo el período aunque el filtro oculte gastos de
  algunos meses. Cero es válido; donde falta referencia no se inventa ni se arrastra.
- **Ver importes mensuales** conserva las cifras exactas aunque no pueda dibujarse el
  gráfico. Si cambian las áreas con control vigente cambia la cobertura del total:
  no interpretar esa variación como ahorro.
- Son pesos de cada mes, **sin ajuste por inflación**.

## Gastos mensuales

Es el nombre visible que reemplaza «Control mensual» y «Gastos esperados». Las claves
de API, modelos y permisos conservan sus nombres técnicos por compatibilidad; no son
dos funcionalidades distintas.

Es una lista de comprobación de los gastos que un área espera cargar cada mes durante
una vigencia. Por ejemplo: electricidad de Consultorios desde septiembre. Sirve para
detectar lo que falta **incluso cuando nadie cargó una factura**. Los conceptos salen
del catálogo de la institución; configurar este control no crea conceptos ni facturas.

El **monto de referencia** es opcional y permite comparar lo esperado con lo
aprobado: **diferencia = referencia − aprobado**. Positiva en verde, negativa en
rojo, cero neutro, siempre con importe y signo. Alcanzar exactamente la referencia
**no declara la carga completa**: podría faltar otra factura o haber un error
compensado por otro. `-` indica que no hay referencia.

Tres estados de carga:

- **Falta cargar**: no se declaró terminada la carga de ese concepto y mes.
- **Carga completa**: una persona autorizada informó que terminó de cargar.
- **No corresponde**: se declaró que no corresponde cargar ese concepto ese mes.

Puede haber carga completa y gastos todavía pendientes de aprobación. El estado de
carga **no es un requisito automático del reparto**.

**Agregar gasto mensual** establece lo esperado. El lápiz de cada fila reúne la
edición de vigencia y los historiales. Una nueva versión conserva la anterior; no se
usa para cargar la próxima factura ni hace falta una versión nueva cada mes. Los
conteos **Por aprobar** y **Aprobados** abren los gastos del mismo concepto, área y
mes, y no cuentan cargas reemplazadas.

## Gastos registrados

El listado distingue importe original, ajustes e importe resultante. Por ejemplo:
ARS 10.000 originales, ajuste de −ARS 250, resultado ARS 9.750.

Un **ajuste** modifica el valor efectivo mediante un registro adicional con motivo,
conservando el original. Un **reemplazo** crea una carga nueva vinculada a una
anterior pendiente o rechazada; se muestran las referencias de ambos. Un registro
reemplazado se conserva como evidencia histórica: no es otro gasto vigente para el
conteo ni para el reparto.

**Institucional — sin área asignada** identifica gastos del hospital completo. No
equivale a «todas las áreas».

## Aprobación

«Aprobado» comienza marcado si la persona tiene el permiso de aprobación en esa área
y nivel de sensibilidad; en un gasto nuevo se determina después de elegir área y
concepto, y puede desmarcarlo. Sin ese permiso queda pendiente, y **ser
administración central no aprueba por sí solo**.

Gastos y sus ajustes usan `aprobar_gastos`; dinero y reducciones, `aprobar_dinero`;
ajustes de costo, `aprobar_costos`.

| Registro de pago 30 sobre cuenta 100 | Pagado confirmado | Pendiente de la cuenta | Por aprobar | Disponible para otro pago |
| --- | --- | --- | --- | --- |
| Pendiente de aprobación | 0 | 100 | 30 | 70 |
| Aprobado | 30 | 70 | 0 | 70 |
| Rechazado | 0 | 100 | 0 | 100 |

Los pendientes se muestran aparte y **reservan sus límites**: no vuelven a sumarse
como pagado/cobrado ni permiten registrar dos veces el mismo pendiente. Rechazarlos
libera la reserva y conserva motivo, autoría e historia. Un registro ya aprobado no
se desmarca retroactivamente: se corrige con el movimiento o ajuste correspondiente.

Los ajustes pendientes o rechazados no afectan importes confirmados ni repartos. Los
históricos mantienen el efecto que ya tenían, sin inventar un aprobador. Resumen,
Gastos mensuales y Evolución muestran la cantidad de ajustes por aprobar **separada**
de los importes: una corrección pendiente no se suma ni se resta del confirmado.

## Reparto de gastos entre atenciones

Para distribuir un gasto hacen falta tres cosas: que el **gasto esté aprobado**, que
exista una **regla vigente** para ese concepto y ámbito, y que haya **atenciones
elegibles** en el período. Si falta alguna, se muestra el motivo y se conserva el
saldo sin distribuir.

### Ámbito: por área o institucional

Desde el 18/09/2026 el ámbito puede ser un **área** o la **institución completa**. Un
gasto institucional con regla institucional se reparte entre las atenciones elegibles
de **todas las áreas** de la institución, en proporción a su cantidad durante el
período. Un gasto de un área no se atribuye a atenciones de otra.

### Actividad verificada

La verificación combina un control técnico y una decisión humana:

1. **Control de registros**: el sistema comprueba que las atenciones terminadas que
   puede contrastar tengan su registro financiero y que las asociaciones sean
   coherentes con el ámbito y el mes. Este control se ejecuta **en cada cálculo** y
   si falla, no se habilita el reparto.
2. **Estado del ámbito**: desde el 18/09/2026 la actividad se considera **habilitada
   de forma implícita**, también para períodos históricos. Antes hacía falta una
   confirmación previa. Lo que existe hoy es una **excepción versionada** que puede
   bloquear o habilitar un ámbito a partir de un mes determinado.

El sistema no puede detectar atenciones anotadas sólo en papel o en otro programa: el
control técnico verifica coherencia interna, no completitud del mundo real.

Si hay una diferencia, **no debe registrarse nuevamente la atención** para intentar
eliminarla: hay que identificar el origen con soporte y corregirlo preservando la
evidencia. La interfaz no incluye una herramienta para recuperar registros
financieros ausentes.

Una persona autorizada para configurar repartos puede verificar la actividad sin
tener permiso para consultar gastos. En ese caso ve cantidades de atenciones y no
importes: no se los reemplaza por cero ni se le concede acceso financiero adicional.

### Cuándo se actualiza

Guardar un gasto, aprobarlo, ajustarlo o reemplazarlo solicita automáticamente el
cálculo. También lo hacen los cambios de reglas o de cobertura y las atenciones
nuevas del ámbito y mes. **El guardado confirma el registro; el cálculo comienza en
segundo plano**, sin dejar la pantalla abierta ni esperar un horario programado.

La pantalla distingue actualización pendiente, procesamiento, resultado actualizado y
error recuperable. Mientras hay cambios pendientes, el reporte no presenta la
distribución anterior como si estuviera al día. Si el servicio está detenido, el
trabajo se conserva para recuperarlo al volver. **«Actualizado» no significa «todo
distribuido»**: terminar el cálculo puede dejar un saldo sin distribuir con su motivo.

Si la actividad vuelve a tener diferencias después de haberse distribuido, el
siguiente procesamiento deja una versión pendiente y conserva la anterior sólo como
historia. Repetir un procesamiento sin cambios no crea otra versión.

El historial está separado de los repartos vigentes: **una versión anterior no se
suma a su reemplazo**. El saldo sin distribuir se obtiene del importe efectivo menos
lo atribuido, también al consultar versiones antiguas.

### Ver atenciones

La columna de atenciones despliega las atribuciones cuando la persona tiene los
permisos necesarios: referencias, fecha, área e importe; **nunca narrativa clínica**.
Sus totales corresponden al reparto completo, no sólo a la página abierta.

El enlace muestra el título de la atención original —por ejemplo, «Consulta
kinesiológica»— o, si falta, el nombre del circuito del caso; el número de caso queda
como referencia secundaria. El nombre y el enlace aparecen **sólo si el caso existe y
la persona tiene acceso clínico en esa institución**; no se muestran nombres de
pacientes. Si dice **Sin enlace**, la ayuda explica el límite: tener permisos
financieros no otorga acceso clínico.

Si una nueva consulta del detalle falla o el acceso se revoca, la pantalla retira los
importes anteriores y muestra el error. **No se debe interpretar un dato guardado en
la pantalla como confirmación de acceso o actualización vigente.**

## Costos por atención

Permite abrir el detalle de los componentes directos, sus valores, los importes
compartidos y los faltantes. **Una cifra conocida no se presenta como costo completo
cuando faltan datos.**

La configuración tiene tres pasos:

1. Elegir una atención publicada del circuito y asociarle una prestación financiera.
2. Definir qué componentes de costo utiliza, por ejemplo insumos o uso de equipo.
3. Registrar el valor y desde cuándo rige para cada componente.

Después, el personal realiza su atención habitual y Finanzas permite consultar su
costo. **Cambiar hoy la configuración no modifica silenciosamente los costos
históricos**, y los valores de referencia del control mensual no fijan el costo de una
atención.

Los valores actuales se destacan, los futuros se identifican y los históricos se
atenúan sin ocultarse. Preparar un cambio recupera el importe anterior —incluido
cero— y propone hoy como «Vigente desde». Una vigencia futura no invalida
anticipadamente la actual.

## Pagos y cobros

Separa lo que corresponde pagar o cobrar del dinero efectivamente registrado. **No
ejecuta transferencias ni conecta bancos.** Tres datos centrales: importe de la
cuenta, pagado/cobrado neto y pendiente.

1. **Desde un gasto aprobado**, crear explícitamente su cuenta por pagar e
   identificar al proveedor o responsable. Esto no vuelve a sumar el gasto ni
   registra dinero, y los gastos anteriores no se convierten automáticamente en
   deuda. Desde un gasto con cuenta y permiso de lectura se puede abrirla; no se
   ofrece crear una segunda.
2. **Para atenciones**, configurar expresamente si se cobran y su arancel. Arancel y
   costo interno son distintos. La regla se aplica a nuevas atenciones y cada cambio
   conserva la versión anterior. **Quién debe pagar no se configura por prestación**:
   varía según el paciente, así que se define por atención en **Cobros por completar**,
   o lo determina su cobertura. El paciente no se convierte automáticamente en pagador.
   Mientras falte el arancel o el responsable, la atención aparece en **Cobros por
   completar**, sin crear deuda ni pedir datos nuevos al profesional. Las políticas
   históricas que sí fijaron un responsable lo conservan: recuperar una atención vieja
   reproduce lo que regía ese día.
3. **Abrir la cuenta** y registrar importe, fecha real y referencia. Se permiten
   varios parciales, sólo hasta el pendiente: una cuenta de 100 con un pago de 30 deja
   70 pendientes.
4. **Para devolver dinero**, elegir el movimiento original, importe y motivo, e
   indicar si se mantiene la cuenta, si se reduce, o si esa reducción ya se registró.
   El resultado se ve antes de confirmar. Cargo de 100 cobrado completo: devolver 30
   manteniendo la cuenta deja 30 pendientes; reducir la cuenta a 70 y devolver 30 deja
   cero. Las reducciones existentes se vinculan sin repetirse.
5. **Consultar el dinero por fecha real** y abrir sus movimientos, incluso si la
   cuenta es de otro mes económico. Se muestran importes originales, devoluciones y
   netos.

Reducir o cancelar una cuenta **no devuelve dinero por sí solo**. Una devolución no
modifica automáticamente gastos, costos clínicos, repartos ni stock. Si cuenta y
gasto difieren se muestra un aviso para revisión explícita. No hay borrado ni edición
de originales.

Desactivar una prestación del catálogo de costos **no suspende por sí solo su cobro**:
hay que indicarlo en Configuración de cobros. Esa suspensión está disponible aunque la
prestación esté inactiva y sólo afecta futuras atenciones.

### Operaciones inciertas

Las operaciones monetarias llevan una **clave de reintento**. Ante una respuesta
incierta, reintentar el mismo formulario conserva esa clave, también al actualizar la
vista previa o volver a datos ya enviados. Cambiar el contenido económico representa
otra intención. **No cerrar y recrear una operación incierta sin consultar primero su
historial.** La devolución confirma la versión previsualizada: si otra persona cambió
la cuenta, hay que actualizar la vista previa.

Las respuestas monetarias se auditan; si falla la auditoría de una operación, ésta no
se guarda.

Una captura fallida puede recuperarse administrativamente desde el hecho de atención
durable, incluso si no llegó a crearse su registro de captura. Se conserva la
configuración aplicable a la fecha de atención y repetir la recuperación no duplica el
cargo. Las cuentas conservan la referencia de atención aunque ésta no tenga paciente
identificado; el pagador sigue siendo explícito e independiente.

## Reportes

Compara el mes elegido con el **mes anterior** o con el **mismo mes del año
anterior**, sobre una trayectoria de 6 o 12 meses, y descarga el informe en PDF.

- La variación es actual menos anterior. Sólo se calcula un porcentaje si ambos
  períodos tienen registros y la base anterior es positiva. **Una suba o baja no
  indica por sí sola una mejora.**
- Gastos y movimientos de dinero son magnitudes diferentes: no se suman.
- El desglose de dinero agrupa **cobros por área, prestación y financiador**, y pagos
  por área y concepto de gasto. Los copagos se muestran a nombre del paciente. El
  financiador proviene del vínculo de cobertura de la cuenta, **no de coincidencias de
  nombres**: sin ese vínculo queda sin identificar.
- Un **mes abierto** se compara de forma provisional y puede mostrar una baja
  aparente frente a uno cerrado. Terminar el mes o completar sus controles no
  garantiza que toda la carga esté registrada.
- El **PDF** incluye los gráficos, los totales y todas las filas que cumplen los
  filtros de cada tabla, aunque estén en otra página. Identifica los períodos, el
  alcance y la fecha de consulta, y se descarga sólo cuando las consultas autorizadas
  están completas. El botón está sólo dentro de Reportes.
- Los filtros de tabla no modifican los gráficos ni los totales.

Detalle del contrato de las cifras, la API y su verificación:
[`reporteria-ejecutiva.md`](reporteria-ejecutiva.md).

## Cómo consultar las tablas

- Mes y área actualizan automáticamente la vista. Las pestañas comparten tarjeta con
  mes y área; en pantallas angostas se acomodan en otra fila con desplazamiento
  horizontal.
- Las listas financieras, incluidos detalles e historiales, **no requieren
  desplazamiento horizontal**: el texto se acomoda en varias líneas y, cuando falta
  ancho, cada registro se presenta verticalmente conservando toda la información. En
  esa presentación, **Ordenar y filtrar columnas** abre los controles.
- **Gastos mensuales** cambia antes a esa presentación porque tiene más columnas: en
  pantallas intermedias muestra cada registro en dos columnas; en móvil, en una.
- El encabezado de cada columna de datos permite ordenar; la columna de acciones no.
- Los filtros de columna admiten selecciones o rangos según el tipo de dato, y se
  aplican al conjunto completo **antes de paginar**. Los filtros activos se muestran,
  pueden quitarse, y la vista filtrada queda en la dirección de la página.
- Al abrir **Sin distribuir** desde el resumen se muestran sólo repartos de gastos
  aprobados, no reemplazados, con saldo distinto de cero. Pueden aparecer saldos
  negativos por ajustes: excluirlos daría una explicación incompleta del total.
- **Gastos registrados** muestra el importe vigente; el original, los ajustes y sus
  motivos se consultan en **Detalle**.
- Las ayudas (?) se abren con mouse, teclado o toque sin desplazar los datos.
- Los códigos internos de conceptos, prestaciones y componentes se generan
  automáticamente si se omiten al crear. Una referencia manual sigue siendo opcional y
  los códigos existentes no se reemplazan al editar.

## Entidades y endpoints

| Bloque | Recursos |
|---|---|
| Costos | `hechos-costo`, `reportes-costos`, `prestaciones-costo`, `componentes-costo`, `valores-componentes`, `ajustes-costo` |
| Gastos | `gastos`, `ajustes-gasto`, `conceptos-gasto`, `expectativas-gasto` (y su acción `calendario`) |
| Reparto | `coberturas-actividad`, `reglas-reparto`, `repartos-gasto`, `procesamiento-finanzas` |
| Dinero | `obligaciones-financieras`, `movimientos-dinero`, `politicas-cobro`, `pendientes-cobro` |
| Reportes | `reportes-finanzas`, `reportes-dinero`, `reportes-costos` |
| Permisos y auditoría | `concesiones-financieras`, `accesos-financieros` |

`reportes-costos` es de sólo lectura y agrega las mismas atenciones que
`hechos-costo`, con el alcance de **ver costos** y el mismo registro de auditoría por
área y sensibilidad. Devuelve totales del mes y desgloses por área y por prestación;
no expone ciudadano, caso ni composición.

Los procesos de fondo son los servicios `repartos` (que escucha y procesa las
solicitudes) y `costos` (que recupera hechos pendientes). Reciben el aviso por
PostgreSQL después de confirmar el guardado y conservan el trabajo en base de datos.
Al iniciar y cada diez minutos hacen una conciliación de seguridad, que **no es el
disparador normal**. Detenerlos conserva las solicitudes pendientes y no borra nada.
Su latido se consulta en `/api/estado/`.

## Relación con cobertura y obras sociales

El circuito de financiadores **está implementado** y se conecta con este módulo: la
distribución del cobro de una prestación cubierta genera las obligaciones del
financiador y del paciente, que viven en `obligaciones-financieras` como cualquier
otra cuenta. El precio y el dinero siguen siendo de Finanzas; la cobertura, el cupo y
la reserva son del módulo de financiadores.

Ver [Financiadores, cobertura y copagos](../financiadores-cobertura/README.md).

## Límites conocidos

Sin anticipos, sobrepagos, movimientos libres, cajas o cuentas bancarias,
facturación fiscal, conciliación bancaria ni generación retrospectiva automática de
cargos. Otras bases de reparto distintas de la actividad, la contabilidad general y
el costo total institucional siguen fuera del alcance.

## Validación funcional

Comparar un área técnicamente completa y otra con diferencias; probar con un perfil
de área y con administración; seguir los conteos hasta sus registros; comprobar un
ajuste y un reemplazo; ordenar y filtrar con varias páginas; verificar que las
atribuciones sumen exactamente el importe del gasto y sus ajustes.

### Recorrido para practicar

Hacelo en una institución de prueba, sin información real de pacientes. El entorno
para esto es el **vacío** (`localhost:8081`); para ver el módulo ya cargado, el
entorno **demo** (`localhost:8082`) — ver [`docs/entornos/`](../../entornos/README.md).

1. **Preparar permisos.** Con administración institucional, otorgá a la persona de
   contabilidad las acciones y áreas que realmente necesita. Habilitá sensibles sólo
   cuando corresponda. Probá con esa persona que entra a Finanzas pero no obtiene por
   eso acceso al diseño clínico ni a otras instituciones.
2. **Configurar el costo directo antes de atender.** Elegí una atención publicada,
   agregá un componente y un valor vigente, por ejemplo ARS 1.500 por atención. Si no
   aparece ninguna atención publicada, primero hay que preparar y publicar el circuito
   clínico: Finanzas no lo publica ni lo modifica.
3. **Realizar una atención habitual.** Iniciá el caso y completá la atención. Abrí
   Costos por atención y luego Ver composición. Abrir el caso sin completar la
   atención no alcanza.
4. **Preparar el control y cargar un gasto.** Definí el concepto y área en Gastos
   mensuales, con una referencia opcional. Registrá el gasto y, si queda por aprobar,
   aprobalo con otro usuario autorizado. Compará referencia, aprobado y diferencia.
5. **Configurar la distribución.** Verificá el ámbito y su actividad; agregá la regla
   del concepto, en el mismo mes y ámbito. Al guardar, observá cómo pasa de
   actualización pendiente a resultado actualizado, y revisá la explicación si
   conserva saldo sin distribuir.
6. **Seguir el dinero.** Desde Resumen abrí los gastos que componen cada cifra y las
   atribuciones del reparto. Comprobá que aprobado sea distribuido más sin distribuir.
   Registrá un ajuste con motivo y esperá la actualización: debe cambiar el importe
   efectivo, conservar el original y no sumar el reparto histórico al vigente.

Dos comprobaciones importantes: un importe mal cargado no se vuelve correcto por
alcanzar la referencia, y un gasto de un área no debe atribuirse a atenciones de otra.
Si algo no coincide, anotá el mes, área y referencia del registro **antes** de cambiar
datos.

### Pruebas de interfaz

`frontend/e2e/finanzas-feedback.spec.js` es un recorrido autenticado que requiere
`FINANZAS_DEMO_PASSWORD` en el entorno local; su configuración es
`playwright.finanzas.config.js`. **Conserva expectativas de una versión anterior de la
interfaz y debe revisarse antes de usarlo como evidencia actual.** No confundirlo con
`playwright.finanzas-ui.config.js`, cuya suite usa respuestas HTTP simuladas y no
requiere credenciales ni escribe datos.

No guardar contraseñas en código ni en documentación.

## Escenario de referencia

El escenario ficticio **Hospital General Los Aromos** —un año de historia, de octubre
de 2025 a septiembre de 2026— lo siembra `seed_los_aromos` y vive en el entorno demo.
El recorrido de presentación de 25–30 minutos, con sus cifras, está en
[`guia-los-aromos.md`](guia-los-aromos.md).

`seed_los_aromos` es **exclusivamente manual**: exige PostgreSQL vacío, confirmación
y una contraseña externa; no borra ni mezcla datos existentes.

## Antecedentes

El diseño lote por lote —reparto por actividad, unidad monetaria, aprobaciones,
dinero, reportería y usabilidad— y el cierre de la demo del 15/09/2026 están
archivados en [`docs/historico/plans/`](../../historico/plans/) y
[`docs/historico/estado-post-demo-2026-09-15.md`](../../historico/estado-post-demo-2026-09-15.md).
