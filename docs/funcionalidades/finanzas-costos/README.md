# Finanzas y costos

## Para qué sirve

Permite registrar y revisar gastos del hospital, controlar la carga mensual y distribuir gastos aprobados entre las atenciones elegibles del área. Los valores de costo no crean cargos al paciente ni pagos.

**Cierre posterior a la demo del 15/09/2026:** ver el [estado, revisión y continuidad del módulo](estado-post-demo-2026-09-15.md). Esa síntesis distingue lo entregado de las limitaciones y de la nueva prioridad: cobros a pacientes, conexión con obras sociales e ingreso de sus usuarios. El feedback adicional de interfaz queda diferido por pedido del usuario.

### Pagos y cobros — lote #38 activo en la demo

**Estado al 15/09/2026:** las correcciones de la revisión están integradas en el worktree `sistemadesalud-finanzas-costos` y activadas en localhost:8090. El usuario autorizó sustituir los datos anteriores por el escenario ficticio Hospital General Los Aromos. La [guía de presentación](guia-los-aromos.md) explica el recorrido y sus cifras iniciales; también hay una [versión imprimible](guia-los-aromos.html).

**Seguridad de la sustitución:** antes de retirar los datos anteriores se respaldaron código, configuración, base y adjuntos. La restauración PostgreSQL 16 reprodujo las huellas de 84 tablas y 36.086 filas. La carga nueva tiene usuarios, concesiones financieras explícitas, cuentas y movimientos sintéticos; no provienen de personas reales. La siembra no modifica las reglas del sistema: prepara los perfiles del escenario sobre el esquema ya migrado. El incremento de código sí incluye las migraciones financieras 0022–0024 y las reglas de aprobación autorizadas. Los detalles históricos de validación y recuperación están en el [plan de la demo](../../plans/2026-09-15-demo-los-aromos-design.md); el estado de publicación se registra en el [cierre post-demo](estado-post-demo-2026-09-15.md).

La pestaña **Pagos y cobros** separa lo que corresponde pagar/cobrar del dinero efectivamente registrado. No ejecuta transferencias ni conecta bancos. Tres datos centrales: importe de la cuenta, pagado/cobrado neto y pendiente.

1. **Desde un gasto aprobado**, crear explícitamente su cuenta por pagar e identificar al proveedor o responsable. Esto no vuelve a sumar el gasto ni registra dinero. Los gastos anteriores no se convierten automáticamente en deuda.
2. **Para atenciones**, configurar expresamente si se cobran, su arancel y quién debe pagar. Arancel y costo interno son distintos. La regla se aplica a nuevas atenciones; cada cambio conserva la versión anterior. El paciente no se convierte automáticamente en pagador. Si falta arancel o responsable, aparece en **Cobros por completar**, sin crear deuda ni pedir datos nuevos al profesional.
3. **Abrir la cuenta**, registrar importe, fecha real y referencia del pago/cobro realizado. Se permiten varios parciales, sólo hasta el pendiente. Una cuenta de 100 y un pago de 30 dejan 70 pendientes.
4. **Para devolver dinero**, elegir el movimiento original, importe y motivo. Indicar si se mantiene lo que corresponde pagar/cobrar, si se reduce, o si esa reducción ya se registró. Ver el resultado antes de confirmar. Cargo de 100 cobrado completo: devolver 30 manteniendo la cuenta deja 30 pendientes; reducir la cuenta a 70 y devolver 30 deja cero. Las reducciones existentes se vinculan sin repetirse.
5. **Consultar el dinero por fecha real** y abrir sus movimientos, incluso si la cuenta es de otro mes económico. Se muestran importes originales, devoluciones y netos. Cobros netos menos pagos netos no es saldo disponible, rentabilidad ni costo hospitalario.

Reducir o cancelar una cuenta no devuelve dinero por sí solo. Una devolución no modifica automáticamente gastos, costos clínicos, repartos ni stock. Si cuenta y gasto difieren, se muestra un aviso para revisión explícita. No hay borrado o edición de originales.

Permisos nuevos: `ver_dinero`, `registrar_dinero`, `corregir_dinero` y `configurar_cobros`, usando institución, área y sensibilidad. No se otorgan automáticamente, tampoco por ser administrador institucional. Configurar cobros permite identificar prestaciones, no leer sus componentes/valores de costo ni modificarlos. Operar desde pantalla requiere también lectura de dinero del mismo alcance.

### Aprobación simple de gastos y dinero

«Aprobado» comienza marcado si la persona tiene el permiso de aprobación en esa área y nivel de sensibilidad. En un gasto nuevo se determina después de elegir área y concepto. Puede desmarcarlo. Sin ese permiso queda pendiente; ser administración central no aprueba por sí solo. Gastos y sus ajustes usan `aprobar_gastos`; dinero y reducciones, `aprobar_dinero`; ajustes de costo, `aprobar_costos`. Los permisos se administran en Administración → Usuarios → Editar usuario → Permisos financieros; el escenario nuevo los concede explícitamente a sus perfiles ficticios.

| Registro de pago30 sobre cuenta100 | Pagado confirmado | Pendiente de la cuenta | Por aprobar | Disponible para otro pago |
| --- | --- | --- | --- | --- |
| Pendiente de aprobación | 0 | 100 | 30 | 70 |
| Aprobado | 30 | 70 | 0 | 70 |
| Rechazado | 0 | 100 | 0 | 100 |

Los pendientes se muestran aparte y reservan sus límites: no vuelven a sumarse como pagado/cobrado ni permiten registrar dos veces el mismo pendiente. Rechazarlos libera la reserva y conserva motivo, autoría e historia. Aprobar/rechazar se hace desde el detalle; una devolución con reducción conjunta tiene una sola decisión. Un registro ya aprobado no se desmarca retroactivamente: se corrige con el movimiento o ajuste correspondiente.

Los ajustes de gasto/costo pendientes o rechazados no afectan importes confirmados ni repartos. Los ajustes históricos mantienen el efecto que ya tenían, sin inventar un aprobador. Resumen, Gastos mensuales y Evolución muestran la cantidad de ajustes de gasto por aprobar separada de los importes: una corrección pendiente no se suma ni se resta del confirmado. Revisá y decidí cada corrección desde su historial. La configuración y los costos automáticos al completar atención no agregan otra aprobación manual.

Las operaciones monetarias llevan una clave de reintento. Ante respuesta incierta, reintentar el mismo formulario conserva esa clave, también al actualizar la vista previa o volver a datos ya enviados. Cambiar el contenido económico representa otra intención. No cerrar y recrear una operación incierta sin consultar primero su historial. La devolución confirma la versión previsualizada: si otra persona cambió la cuenta, debe actualizarse la vista previa. Las respuestas monetarias se auditan; si falla la auditoría de una operación, ésta no se guarda.

Desde un gasto con cuenta y permiso de lectura de dinero se puede abrir esa cuenta; no se ofrece crear una segunda. Las reservas sin pendientes se resumen para priorizar las acciones. Una reducción preexistente conserva su aprobación aunque se vincule después una devolución pendiente; sólo una reducción creada junto a esa devolución comparte su decisión.

Desactivar una prestación del catálogo de costos no suspende por sí solo su cobro: en Configuración de cobros indicá que no se cobra. Esa suspensión está disponible aunque la prestación se encuentre inactiva y sólo afecta futuras atenciones.

**Límites:** sin anticipos, sobrepagos, movimientos libres, cajas/cuentas, obras sociales, facturación fiscal, conciliación bancaria ni generación retrospectiva automática de cargos. Una captura fallida puede recuperarse administrativamente desde el hecho de atención durable, incluso si no llegó a crearse su registro de captura. Se conserva la configuración aplicable a la fecha de atención y repetir la recuperación no duplica el cargo. El usuario confirmó que no hay históricos productivos que requieran distinguirse de estas capturas: no se agregó una migración ni un proceso de reconstrucción masiva. Las cuentas conservan referencia de atención aunque ésta no tenga paciente identificado; el pagador sigue siendo explícito e independiente.

API del lote: `obligaciones-financieras`, `movimientos-dinero`, `politicas-cobro`, `pendientes-cobro` y `reportes-dinero`. Diseño, condiciones de activación y pruebas: [plan del lote de dinero](../../plans/2026-09-14-dinero-demo-design.md).

## Quién usa cada parte

- El personal administrativo carga gastos en las áreas autorizadas.
- Una persona con permiso de aprobación acepta o rechaza las cargas delegadas.
- Quien configura Finanzas define qué gastos se esperan y qué conceptos se distribuyen.
- El personal clínico registra la atención como parte de su trabajo habitual. Los componentes financieros configurados se calculan automáticamente.
- Consultar importes sensibles y detalles por atención requiere los permisos correspondientes; poder ver un gasto no concede automáticamente acceso al registro financiero completo.

El administrador de la institución tiene por defecto lectura de costos y gastos, incluidos los sensibles, **sólo dentro de su institución**. Es quien autoriza qué otras personas pueden acceder a información sensible. No recibe por eso todas las acciones de carga, aprobación o configuración: esas acciones se otorgan explícitamente. Una persona de contabilidad puede tenerlas sin convertirse en administradora ni obtener permisos clínicos.

En **Editar usuario → Permisos financieros** se eligen las acciones; las existentes aparecen marcadas y cada una conserva sus áreas y alcance sensible. La sección es plegable y usa hasta tres columnas independientes. **Guardar permisos financieros** guarda el bloque separado de los datos personales: si alguna acción no es válida, no se aplica ninguna modificación; si otro administrador cambió los permisos, se exige volver a consultarlos. Las lecturas heredadas del administrador se identifican como **Por rol** y no son revocables desde estas casillas. Ya no existe el botón ni el modal global anterior.

Para consultar el resumen de verificación de actividad se necesitan **ambos permisos: configurar repartos y consultar gastos**, en la misma institución y área. Configurar por sí solo no permite consultar totales. Los importes sensibles requieren que ambos permisos los habiliten; de lo contrario, no se incluyen en el resumen general. Cada consulta autorizada queda registrada en auditoría. Si no se puede guardar ese registro, el resumen no se entrega y se informa que hay que reintentar.

## Cuatro momentos distintos

| Momento | Qué ocurre |
| --- | --- |
| Abrir un caso | Se inicia el recorrido de atención. No genera por sí solo un costo de atención. |
| Completar la atención | Se conserva un registro financiero asociado a esa atención, con paciente y área de origen. Se procesan los componentes directos disponibles. |
| Aprobar un gasto | Se acepta una fuente de gasto del hospital. No altera silenciosamente los componentes directos previos. |
| Repartir un gasto | Se distribuye su importe efectivo entre atenciones elegibles. Se conserva el total exacto y el historial de resultados anteriores. |

La firma posterior de la atención no duplica su registro financiero. Un costo directo completo sólo cubre los componentes configurados; no implica que se conozca el costo total del paciente o del hospital.

## Gastos mensuales

Es el nombre visible que reemplaza «Control mensual» y «Gastos esperados». Las claves de API, modelos y permisos históricos conservan sus nombres técnicos por compatibilidad; no son dos funcionalidades distintas.

Es una lista de comprobación de los gastos que un área espera cargar cada mes durante una vigencia. Por ejemplo: electricidad de Consultorios desde septiembre. Sirve para detectar lo que todavía falta, incluso cuando nadie cargó una factura. Los conceptos disponibles salen del catálogo de gastos de la institución seleccionada; configurar este control no crea conceptos ni facturas.

El **monto de referencia** es opcional. Permite comparar lo esperado con el importe aprobado, que incluye ajustes, y ver la diferencia: **referencia menos aprobado**. Por ejemplo, referencia ARS 100.000 y aprobado ARS 95.000 muestran una diferencia de ARS 5.000; si lo aprobado es ARS 105.000, la diferencia es −ARS 5.000. El signo positivo indica que lo aprobado está por debajo de la referencia; el negativo, que la supera. Alcanzar exactamente la referencia **no declara la carga completa**: podría faltar otra factura o existir un error compensado por otro.

- **Falta cargar:** no se declaró terminada la carga de ese concepto y mes.
- **Carga completa:** una persona autorizada informó que terminó de cargar lo esperado.
- **No corresponde:** se declaró que no corresponde cargar ese concepto para ese mes.

Puede haber carga completa y gastos todavía pendientes de aprobación. Actualmente el estado de carga no es un requisito automático del reparto.

**Agregar gasto mensual** establece lo que se espera. El lápiz de cada fila reúne la edición de vigencia y los historiales. Una nueva versión modifica esa configuración conservando la anterior; no se usa para cargar la próxima factura ni se necesita una versión nueva cada mes. Las correcciones conservan concepto y área.

Los conteos **Por aprobar** y **Aprobados** abren los gastos correspondientes al mismo concepto, área y mes. No cuentan cargas reemplazadas.

## Gastos registrados

El listado distingue importe original, ajustes e importe resultante. Por ejemplo: ARS 10.000 originales, ajuste de −ARS 250, resultado ARS 9.750.

Un ajuste modifica el valor efectivo mediante un registro adicional con motivo, conservando el original. Un reemplazo crea una nueva carga vinculada a una anterior pendiente o rechazada. Se muestran las referencias de ambos para seguir el cambio. Un registro reemplazado se conserva como evidencia histórica; no es otro gasto vigente para el conteo o el reparto.

## Actividad verificada y repartos

La verificación combina dos condiciones:

1. **Control de registros:** se comprueba que las atenciones terminadas que el sistema puede contrastar tengan el registro financiero correspondiente y que las asociaciones sean coherentes con el área y el mes.
2. **Confirmación del área:** una persona autorizada confirma desde qué mes se registra aquí toda la actividad. El sistema no puede detectar atenciones anotadas sólo en papel o en otro programa.

La confirmación del área no es aprobación de gastos. Para distribuir se necesita también un gasto aprobado y una regla vigente para el concepto y área. Si no hay atenciones elegibles o falta alguna condición, se muestra el motivo y se conserva el saldo sin distribuir.

Una persona autorizada para configurar repartos puede verificar la actividad y registrar la configuración sin tener permiso para consultar gastos. En ese caso verá cantidades de atenciones, pero no importes: no se los reemplaza por cero ni se le concede acceso financiero adicional.

Si hay una diferencia, no debe registrarse nuevamente la atención para intentar eliminarla. Se debe identificar el origen con soporte y corregirlo preservando la evidencia. La interfaz actual no incluye una herramienta para recuperar registros financieros ausentes.

La columna de atenciones permite desplegar las atribuciones cuando el usuario tiene los permisos necesarios. El detalle muestra referencias, fecha, área e importe; no incluye narrativa clínica. Sus totales corresponden al reparto completo, no sólo a la página abierta.

El historial está separado de los repartos vigentes: una versión anterior no se suma a su reemplazo.

### Cuándo se actualiza

Guardar un gasto, aprobarlo, ajustarlo o reemplazarlo solicita automáticamente el cálculo. También lo hacen los cambios de reglas/cobertura y las nuevas atenciones del área y mes. **El guardado confirma el registro; el cálculo comienza en segundo plano**, sin que tengas que dejar abierta la pantalla ni esperar un horario programado.

La pantalla distingue actualización pendiente, procesamiento, resultado actualizado y error recuperable. Mientras hay cambios pendientes, el reporte no presenta la distribución anterior como si estuviera al día. Si el servicio está detenido, el trabajo se conserva para recuperarlo al volver. Si falta una condición para repartir, terminar el cálculo puede dejar un saldo sin distribuir con su motivo: “actualizado” no significa “todo distribuido”.

Si la actividad vuelve a tener diferencias después de haberse distribuido, el siguiente procesamiento debe dejar una nueva versión pendiente, conservando la anterior sólo como historia. Repetir un procesamiento sin cambios no crea otra versión. El saldo sin distribuir del listado y del detalle se obtiene del importe efectivo menos lo atribuido, también al consultar versiones antiguas.

Si una nueva consulta del detalle de un gasto falla o el acceso se revoca, la pantalla retira los importes anteriores y muestra el error. No se debe interpretar un dato guardado en la pantalla como confirmación de acceso o actualización vigente.

## Resumen y costos por atención

**Resumen** es el panorama del mes y reúne tres bloques, cada uno con sus cifras, su gráfico y su enlace a la pestaña correspondiente: **Gastos**, **Pagos y cobros** y **Costos por atención**. Cada bloque consulta su propia fuente y falla por separado: un error o una restricción de permisos en uno no oculta ni convierte en cero a los demás. Los tres son magnitudes distintas del mismo período y **no se suman entre sí**; el Resumen no publica un total común. Para comparar contra otro período y exportar a PDF está la pestaña **Reportes**.

En **Gastos** se muestran aprobados, por aprobar, lo distribuido y el saldo sin distribuir, con desglose por área y concepto y enlaces a los registros. El aprobado ya contiene lo distribuido: **aprobado = distribuido + sin distribuir**; no se suman las tres cifras como si fueran gastos distintos. Las cifras corresponden al mes, área y permisos elegidos, no necesariamente a todo el hospital.

En **Pagos y cobros** se muestran cobros netos, pagos netos, su diferencia y la cantidad de movimientos por aprobar, con un gráfico de cobros contra pagos por área. Se cuentan por **fecha efectiva** dentro del mes calendario seleccionado, no por mes económico: una cuenta puede pertenecer a otro mes. La diferencia no es saldo disponible ni rentabilidad, y los movimientos por aprobar están excluidos de los netos.

En **Costos por atención** se muestran las atenciones del mes, el costo directo conocido, el gasto compartido atribuido y cuántas atenciones tienen componentes directos pendientes, con un gráfico que agrupa **por área o por prestación**. Las dos series se dibujan lado a lado y nunca apiladas: el compartido explica un gasto aprobado que ya figura en el bloque de Gastos, no es un costo adicional. La prestación proviene del catálogo congelado al completarse cada atención; las que no tenían prestación configurada se agrupan aparte y no equivalen a costo cero.

El administrador institucional puede consultar todos los gastos registrados de su institución, incluidos los sensibles. Eso no constituye un costo integral del hospital: todavía pueden faltar fuentes que el módulo no incorpora. Esta aclaración está en el (?) junto a la descripción superior, sin ocupar una tarjeta adicional.

Las pestañas comparten tarjeta con mes y área. En pantallas angostas se acomodan en otra fila y permiten desplazamiento horizontal. Los detalles de gastos y controles muestran primero área, mes y estado; luego los importes y su desglose; al final, ajustes, seguimiento o historiales, según corresponda.

**Costos por atención** permite abrir el detalle de los componentes directos, sus valores, los importes compartidos y los faltantes. Una cifra conocida no se presenta como costo completo cuando faltan datos. La configuración de costos directos tiene tres pasos:

1. Elegir una atención publicada del circuito y asociarle una prestación financiera.
2. Definir qué componentes de costo utiliza, por ejemplo insumos o uso de equipo.
3. Registrar el valor y desde cuándo rige para cada componente.

Después, el personal realiza su atención habitual y Finanzas permite consultar su costo. Cambiar hoy la configuración no modifica silenciosamente los costos históricos. Los valores de referencia del control mensual tampoco fijan el costo de una atención.

## Cómo consultar las tablas

### Resumen: del gráfico a los registros

Al entrar se muestran **barras horizontales** por área y concepto. En el selector junto a Barras/Dos niveles/Listado, **Gastos** muestra aprobado y por aprobar, por separado. **Distribución del aprobado** muestra cuánto se distribuyó y cuánto quedó sin distribuir: ambos explican el aprobado, no se suman otra vez como gastos nuevos. La cabecera conserva su disposición al cambiar de vista; en Listado el mismo espacio indica “Todas las medidas”.

Las barras y los anillos se llenan suavemente en 350 ms. La animación se omite si tu dispositivo pide movimiento reducido; las consultas automáticas sin cambios no vuelven a animar las barras.

- Hacé clic en una barra para abrir los gastos o repartos correspondientes, conservando mes, área, concepto y estado.
- **Ordenar** permite ver las barras de mayor a menor importe, de menor a mayor o por área/concepto. Compara la suma de las dos series elegidas: aprobado + por aprobar en Gastos; distribuido + sin distribuir en Distribución del aprobado. No suma ambas comparaciones entre sí.
- **Dos niveles** usa el centro completo, sin textos internos: el interior identifica área y concepto; el exterior divide su importe entre aprobado/por aprobar o distribuido/sin distribuir. Los dos niveles representan el mismo dinero, no se suman. Clic interior abre registros del concepto; clic exterior agrega el filtro de estado. En escritorio, los conceptos están a la izquierda y el gráfico a la derecha; en móvil, el gráfico va arriba. La lista se ordena de mayor a menor participación, sin scroll interno, con nombres, porcentajes aproximados e importes completos; permite las mismas acciones con teclado. Al señalar o enfocar un concepto se resaltan sus sectores.
- Los colores interiores recorren una escala propia fría → cálida (azul, violeta, magenta, naranja y rojo). Mayor participación usa el extremo cálido; menor, el frío. Se agregan intermedios según cuántas participaciones distintas haya y los importes iguales comparten color. Se recalculan con los filtros; no identifican permanentemente un concepto. Rojo no significa error ni gasto indebido. El exterior es neutro: sólido para aprobado/distribuido y rayado para por aprobar/sin distribuir. Su leyenda y los importes evitan depender sólo del color.
- Los gráficos aprovechan la altura restante de la pantalla. No se agrandan por una altura fija del viewport. Si hay muchos conceptos, controles o poco espacio, la página puede crecer para mantenerlos legibles; no se ocultan categorías para hacerlas caber.
- **Listado** conserva todas las cifras exactas y sus enlaces. Está disponible aunque falle la descarga del gráfico. Los dibujos usan una escala aproximada; el detalle al pasar el mouse y el listado conservan los centavos originales.
- Los ajustes negativos se muestran con su signo en barras y listado. No se dibujan como porciones positivas de los anillos.
- Si hay una distribución pendiente, no se dibuja como cero ni como resultado definitivo. Podés seguir consultando los gastos guardados.
- El estado **Repartos actualizados / Actualización pendiente** está debajo de mes y área, dentro de la misma tarjeta. El mensaje informativo y la fecha de última ejecución están en su (?). Los errores y avisos de servicio detenido permanecen visibles.

En **Repartos → Ver atenciones**, el detalle abre y cierra gradualmente (sin animación si tu dispositivo pide movimiento reducido). El enlace muestra el título de la atención original —por ejemplo, “Consulta kinesiológica”— o, si falta, el nombre del circuito del caso. El número de caso queda como referencia secundaria. El nombre y el enlace aparecen sólo si el caso existe y tenés acceso clínico en esa institución; no se muestran nombres de pacientes ni narrativa clínica. Si dice **Sin enlace**, el (?) explica el límite: tener permisos financieros no otorga acceso clínico. Usá **Volver** para regresar con los filtros financieros conservados.

### Listados y filtros

- Mes y área actualizan automáticamente la vista.
- Las listas financieras, incluidos detalles e historiales, no requieren desplazamiento horizontal: el texto se acomoda en varias líneas y, cuando falta ancho, cada registro se presenta verticalmente. Se conserva toda la información. En esa presentación, **Ordenar y filtrar columnas** abre los controles de orden y filtro.
- **Control mensual** cambia antes a esa presentación porque tiene más columnas: en pantallas intermedias muestra cada registro en dos columnas de datos; en móvil, en una. En pantallas amplias conserva la tabla. Las cantidades siguen abriendo los gastos correspondientes y **Administrar** conserva sus acciones e historiales.
- El encabezado de cada columna de datos permite ordenar. La columna de acciones no se ordena.
- Los filtros de columna admiten selecciones o rangos según el tipo de dato. Se aplican al conjunto completo, antes de paginar.
- Los filtros activos se muestran y pueden quitarse. La vista filtrada queda en la dirección de la página.
- Al abrir **Sin distribuir** desde el resumen, se muestran sólo repartos de gastos aprobados, no reemplazados, con saldo pendiente distinto de cero. Se conservan mes, área y concepto cuando corresponde. También pueden aparecer saldos negativos por ajustes: excluirlos daría una explicación incompleta del total. El filtro **Saldo sin distribuir** puede quitarse.
- Las ayudas (?) se abren con mouse, teclado o toque sin desplazar los datos.
- Importes, diferencias y causas de bloqueo permanecen visibles cuando son necesarios para decidir.
- **Gastos registrados** muestra el importe vigente. El original, los ajustes y sus motivos se consultan en **Detalle**. Un gasto reemplazado sigue identificado como no vigente; su historial no desaparece. Los filtros de enlaces antiguos siguen visibles y se pueden quitar aunque su columna ya no esté en la lista.
- En **Gastos mensuales**, **-** indica que no hay referencia. La diferencia es referencia menos aprobado: positiva en verde, negativa en rojo y cero neutro, siempre con su importe y signo. Estar por debajo de la referencia no garantiza ahorro ni carga completa: todavía pueden faltar cargas o aprobaciones.
- **Institucional — sin área asignada** identifica gastos del hospital completo. No equivale a todas las áreas ni distribuye automáticamente el importe entre ellas.

## Pantallas y límites

### Acciones, referencias y vigencias

Inicio ofrece un acceso rápido a Finanzas según permisos efectivos. En Finanzas, los botones principales dependen de la pestaña; **Acciones de finanzas**, siempre a la derecha, conserva las demás acciones autorizadas. **Agregar gasto mensual** está disponible fuera del menú en Gastos registrados y Gastos mensuales. **Nuevo concepto** acompaña las acciones relacionadas con conceptos cuando la persona puede configurarlos. Ocultar una acción por pestaña no concede ni revoca permisos.

Los códigos internos de conceptos, prestaciones y componentes se generan automáticamente si se omiten al crear. Una referencia manual sigue siendo opcional para una necesidad de identificación propia; los códigos existentes no se reemplazan silenciosamente al editar.

En costos por atención, los valores actuales se destacan; los futuros se identifican y los históricos se atenúan sin ocultarse. Preparar un cambio de valor recupera el importe anterior, incluido cero, y propone hoy como «Vigente desde». Una vigencia futura no invalida anticipadamente la actual y una edición no reescribe el histórico.

### Evolución de los gastos mensuales

En **Resumen → Evolución mensual**, junto a **Barras / Dos niveles / Listado**, se consultan 6 o 12 meses hasta el mes económico seleccionado. Es una vista alternativa, no una tarjeta adicional debajo. Sigue disponible aunque no haya gastos en el mes final. “Gastos fijos” se interpreta aquí como los conceptos configurados en **Gastos mensuales**; no se agrega otra clasificación.

#### Histórico actual y pruebas de interfaz

El recorrido autenticado `frontend/e2e/finanzas-feedback.spec.js` requiere `FINANZAS_DEMO_PASSWORD` en el entorno local. No guardar la clave en código ni documentación. Su configuración es `playwright.finanzas.config.js`; no confundirlo con `playwright.finanzas-ui.config.js`, cuya suite usa respuestas HTTP simuladas y no requiere credenciales ni escribe datos en la demo. El recorrido autenticado conserva expectativas de una versión anterior de la interfaz y debe revisarse antes de usarlo como evidencia actual.

Seleccioná **Hospital General Los Aromos**, mes **septiembre de 2026**, y abrí **Resumen → Evolución mensual → 12 meses**. La [guía actual](guia-los-aromos.md) describe las áreas, gastos, atenciones, repartos y movimientos ficticios de octubre de 2025 a septiembre de 2026. Sus cifras son las iniciales de la carga: pueden variar con los ejercicios del usuario.

El escenario anterior «Hospital Demo Finanzas / Consultorio escuela» fue sustituido con autorización; no está disponible como conjunto actual en 8090. `historico_demo.py` permanece como herramienta histórica manual, no como inicializador ni como instrucción para volver a cargar esa base. `seed_los_aromos` también es exclusivamente manual: exige PostgreSQL vacío, confirmación y una contraseña externa; no borra ni mezcla datos existentes.

#### Cómo interpretar la comparación

El gráfico comienza con **todos los conceptos visibles seleccionados**, sin limitar su cantidad. Cada concepto tiene una línea y un color estable: no cambia al variar el importe, el período o la selección. Usa el importe aprobado, incluidos sus ajustes, sólo de áreas con control vigente en cada mes y dentro de tus permisos. Todas las líneas comparten la escala en pesos; un concepto de mucho mayor importe puede hacer que los demás se vean más planos.

**Conceptos** permite buscar, marcar/desmarcar, **Mostrar todos** y **Quitar todos**. Las etiquetas permiten quitar un concepto con × o destacarlo pulsando su nombre; los demás se atenúan, no se suman ni desaparecen. Volver a pulsarlo restaura el énfasis normal.

**Estado de los meses** permite ver carga y aprobación completas, meses incompletos/abiertos, o ambos (por defecto). Se evalúa por concepto y mes: agosto puede estar completo para Electricidad y provisional para Mantenimiento. El gráfico, su detalle al pasar por un mes y **Ver importes mensuales** respetan el filtro; no se suman importes pendientes de aprobación. Los meses sin carga siguen sin dibujarse como cero, aunque su situación pueda consultarse en el listado.

**Comparar con referencias** muestra las de todos los conceptos seleccionados que tengan alguna referencia en el período, sin selector individual. Se distinguen por el mismo color y trazo discontinuo; un punto pequeño permite ver una referencia aislada. **Las referencias siempre conservan todo el período**, aunque el filtro oculte gastos de algunos meses. Cero es válido; donde falta referencia no se inventa ni arrastra un valor. Si ningún concepto seleccionado tiene referencia, el botón está deshabilitado. Un concepto sin referencia conserva sus gastos. Si se oculta el importe de un mes por estado, el detalle y listado lo indican y conservan su referencia cuando corresponde.

Cambiar entre 6 y 12 meses conserva la selección explícita. Si un concepto no está disponible en el nuevo período, se informa sin reemplazarlo; al ampliar nuevamente, recupera su selección. En modo **Mostrar todos** se incluyen también los conceptos que aparezcan al ampliar. Cambiar institución, área o mes económico reinicia la vista con todos los conceptos del nuevo contexto.

- Línea y puntos llenos: meses anteriores con carga declarada completa (o no corresponde) y sin gastos pendientes de aprobación. El color identifica el concepto, no su estado.
- Puntos huecos: importes provisionales porque falta completar carga/aprobación o el mes sigue abierto. No se unen como una tendencia confirmada.
- Sin control o sin carga: se deja un hueco, no una caída ficticia a cero. Un cero con carga declarada completa sí se muestra como dato.
- **Ver importes mensuales** conserva cifras exactas, estado y cantidad de controles de cada concepto y mes, incluso si no puede dibujarse el gráfico. Si cambian las áreas con control vigente, cambia también la cobertura del total: no interpretar automáticamente esa variación como ahorro.
- Clic en un punto o importe abre **Gastos registrados** con mes, concepto, aprobación y el filtro de gastos mensuales configurados. Este filtro excluye gastos del mismo concepto en áreas sin control para ese mes; puede quitarse desde los filtros activos.

Son pesos de cada mes, sin ajuste por inflación. La referencia no es un pago, un gasto aprobado ni una garantía de carga completa. El gráfico no modifica gastos, controles ni repartos.

La pantalla administrativa es `/finanzas`. La atención se completa desde `/casos/:id`. Finanzas incluye resumen de gastos, control mensual, gastos registrados, repartos y costos por atención con configuración y detalle. La auditoría financiera sigue disponible por API.

Fuentes principales: `hechos-costo`, `gastos`, `expectativas-gasto/calendario`, `coberturas-actividad`, `reglas-reparto`, `repartos-gasto`, `reportes-finanzas`, `reportes-dinero`, `reportes-costos`, `procesamiento-finanzas` y `accesos-financieros`.

`reportes-costos` es de sólo lectura y agrega las mismas atenciones que `hechos-costo`, con el alcance de **ver costos** y el mismo registro de auditoría financiera por área y sensibilidad. Devuelve totales del mes y desgloses por área y por prestación; no expone ciudadano, caso ni composición. `reportes-dinero` agrega además el desglose por área del mismo neteo que ya calculaba para el total.

El incremento incluye el primer reparto por actividad, reportes operativos y el lote #38 de pagos/cobros/reintegros vinculados activo en Los Aromos. Otras bases de reparto, contabilidad general y costo total institucional siguen fuera. La nueva prioridad de obras sociales todavía no está implementada.

### Antecedente histórico: activación local del 14/09/2026

Lo siguiente describe aquella intervención, **no el estado actual de datos ni de puertos**. Fue seguida por la sustitución autorizada del escenario el 15/09. No usar estas cifras ni la referencia a 8092 como guía de la demo actual.

La ampliación está activa en **http://localhost:8090/finanzas**. Con autorización del usuario se respaldó la base, se verificó una restauración completa en una base separada, se aplicaron las migraciones aditivas 0020 (referencia opcional) y 0021 (trabajo de reparto), y se activó el servicio `repartos`. Se conservaron usuarios, pacientes, casos, eventos, concesiones y gastos originales, comprobando cantidades y huellas de contenido antes y después. No se creó actividad clínica.

La **práctica anterior en http://localhost:8092** conserva su versión fija y sus datos; no incorpora automáticamente esta ampliación. Su disponibilidad no se volvió a validar durante este último pase. Para revisar las pantallas nuevas usá 8090.

La primera pasada atendió ocho gastos aprobados sin errores. Una solicitud adicional sobre una fuente sin cambios se procesó en aproximadamente 0,1 segundos y no generó otra versión del reparto. Se comprobó en navegador el resumen, la navegación a gastos filtrados, el control mensual, los repartos y el detalle de costos por atención, con respuestas reales de la API.

Si sólo aparecen opciones de consulta, revisá las acciones otorgadas en **Administración → Usuarios → Editar usuario → Permisos financieros**. La lectura sensible predeterminada del administrador no le concede automáticamente las acciones de carga o configuración. La activación no otorgó ni quitó concesiones: el usuario conserva el control de esa configuración.

El servicio usa PostgreSQL para recibir el aviso después de confirmar el guardado y conserva el trabajo en base de datos. Al iniciar y cada diez minutos hace una conciliación de seguridad; esa recuperación **no es el disparador normal**. Debe monitorearse el latido del servicio. Detenerlo conserva las solicitudes pendientes; no borra gastos ni repartos anteriores. Antes de migrar una base usada por personas se requiere respaldo y aprobación.

La revisión técnica del 14/09 encontró errores que se corrigieron en el código y se validaron en pruebas aisladas. Con la aprobación posterior del usuario se reinició únicamente el proceso de repartos y se recreó únicamente el de costos con el arranque corregido, sin nuevas migraciones, siembras, eliminación de datos ni cambios de permisos. Esta activación local no equivale a aprobación de producción ni a aceptación funcional.

Comprobación posterior: ambos procesos financieros activos, ocho trabajos de reparto procesados, cero pendientes y cero errores de reparto. El recuperador de costos completó sus pasadas sin encontrar hechos pendientes. No se crearon atenciones artificiales para demostrarlo: la prueba de tu propio circuito sigue siendo importante. Los demás servicios y la práctica de 8092 no se modificaron ni se volvieron a validar en este pase.

Las nuevas consultas agregadas del resumen y del estado de procesamiento dejan evidencia por las áreas y niveles de sensibilidad realmente consultados. Así, el auditor autorizado de un área puede encontrar sus consultas aunque no se haya elegido un filtro explícito de área. Las consultas vacías no inventan áreas y la evidencia histórica no se reescribe.

## Validación funcional

Comparar un área técnicamente completa y otra con diferencias; probar perfil de área y administración; seguir conteos a sus registros; comprobar un ajuste y un reemplazo; ordenar y filtrar con varias páginas; verificar que las atribuciones sumen exactamente el importe del gasto y sus ajustes.

### Recorrido para practicar después de la activación

Hacelo en una institución de prueba, sin información real de pacientes. El usuario realiza la configuración y las atenciones; no hace falta que soporte cree ejemplos por él.

1. **Preparar permisos.** Con administración institucional, otorgá a la persona de contabilidad las acciones y áreas que realmente necesita. Habilitá sensibles sólo cuando corresponda. Probá con esa persona que puede entrar a Finanzas pero no obtiene por eso acceso al diseño clínico ni a otras instituciones.
2. **Configurar el costo directo antes de atender.** Elegí una atención publicada, agregá un componente y un valor vigente, por ejemplo ARS 1.500 por atención. Si no aparece ninguna atención publicada, primero hay que preparar y publicar el circuito clínico; Finanzas no lo publica ni lo modifica.
3. **Realizar una atención habitual.** Con el usuario y la tarea habilitados por ese circuito, iniciá el caso y completá la atención. Abrí Costos por atención y luego Ver composición. Buscá el componente configurado y sus faltantes; abrir el caso sin completar la atención no alcanza.
4. **Preparar el control y cargar un gasto.** Definí el concepto y área en Gastos mensuales, con una referencia opcional. Registrá el gasto y, si queda por aprobar, aprobalo con otro usuario autorizado. Compará referencia, aprobado y diferencia. Aunque la diferencia sea cero, la indicación de carga sigue siendo una decisión explícita.
5. **Configurar la distribución.** Verificá el área y su actividad real; luego agregá la regla del concepto, en el mismo mes y área. Si el control encuentra diferencias, no dupliques las atenciones: revisá la causa con soporte. Al guardar, observá cómo pasa de actualización pendiente a resultado actualizado y revisá la explicación si conserva saldo sin distribuir.
6. **Seguir el dinero.** Desde Resumen abrí los gastos que componen cada cifra y las atribuciones del reparto. Comprobá que aprobado sea distribuido más sin distribuir. Registrá un ajuste con motivo y esperá la actualización: debe cambiar el importe efectivo, conservar el original y no sumar el reparto histórico al vigente.

Dos comprobaciones importantes: un importe mal cargado no se vuelve correcto por alcanzar la referencia; y un gasto de un área no debe atribuirse a atenciones de otra. Si algo no coincide, anotá el mes, área y referencia del registro antes de cambiar datos.
