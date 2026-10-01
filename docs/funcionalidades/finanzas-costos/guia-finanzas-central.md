# Hospital Central · guía de presentación

Finanzas y costos · recorrido de 25–30 minutos.

> **Fechas relativas desde el issue #65.** La carga (`seed_entorno_demo`) arma doce meses que
> terminan el día en que se corre: donde esta guía dice «septiembre» o «agosto», leé «el mes en
> curso» y «el mes anterior». Los importes de esos dos meses son los mismos; los de meses anteriores
> siguen la estación del año en que caen. Los enlaces con `?mes=2026-09` apuntan a septiembre: cambiá
> el mes en la pantalla. Las fechas exactas y los identificadores (`#gasto`, `#caso`) cambian en cada
> carga, y el resumen del comando imprime los usuarios. Ver [`entornos/README.md`](../../entornos/README.md).

Institución, personas, proveedores e historia completamente ficticios. Es una muestra de actividad de tres servicios, no un censo de toda la operación hospitalaria. Los importes son ejemplos verosímiles, no información de un hospital real ni referencias de precios de mercado.

> Las cifras describen el mes en curso recién cargado. Para ubicar cada registro, usá los filtros de la pantalla y el nombre del paciente; los identificadores cambian en cada carga. Si después registrás o aprobás operaciones, los importes cambian y el historial permite explicar por qué.

## Antes de empezar · 2 minutos

Abrí el **entorno demo**, [localhost:8082](http://localhost:8082) — ver [`docs/entornos/README.md`](../../entornos/README.md). Ingresá con **Dirección de Hospital Central**, `admin.central@hospital.gob.ar`, y comprobá que diga **Hospital Central**. Usá la clave configurada en `DEMO_PASSWORD`.

> El escenario se carga con `seed_finanzas_central` después de la estructura y los roles de Central. Elegí el mes en curso en la pantalla; los enlaces de septiembre son un ejemplo. En **Gastos** filtrá por área y concepto; en **Pagos y cobros** buscá la contraparte; en **Casos → Todos** buscá el nombre del paciente para obtener su número de caso. Para obras sociales, ver [`guia-demo-financiadores.md`](../../entornos/guia-demo-financiadores.md).

La dirección tiene administración institucional y permisos financieros explícitos. Mariela Quintero (`m.quintero@hospital.gob.ar`) carga información sin aprobarla. Los perfiles clínicos son Nora Villegas, Julio Barreto y Carolina Espinosa, sin permisos financieros. `config.central@hospital.gob.ar` configura el escenario. Para mantener una sesión abierta y entrar con otro perfil, usá una ventana privada.

Abrí [Finanzas y costos · septiembre](http://localhost:8082/finanzas?mes=2026-09&tab=resumen), elegí **Todas las áreas e institucional** y cerrá filtros o ventanas que hayan quedado del ensayo. El recorrido principal sólo consulta: no requiere guardar, aprobar, rechazar ni cambiar configuraciones.

También podés entrar desde la tarjeta **Finanzas y costos** de **Inicio**; se muestra sólo cuando el perfil tiene acceso financiero. Las acciones superiores cambian con la pestaña: **Registrar gasto** y **Agregar gasto mensual** en **Gastos**; **Agregar gasto mensual** también en **Gastos mensuales**; configuración de costos en **Costos por atención**, de repartos en **Distribución** y de cobros en **Pagos y cobros**. **Nuevo concepto** aparece junto a las acciones relacionadas con conceptos, si tenés permiso. El botón con icono **Acciones de finanzas**, al extremo derecho de la cabecera, reúne las demás acciones permitidas.

**Frase de apertura:** “Vamos a seguir qué gastos conocemos, cómo se relacionan con las atenciones y qué se pagó o cobró realmente. Son preguntas diferentes.”

| Lo que mostramos | Qué significa | Qué no significa |
| --- | --- | --- |
| Gasto aprobado | Gasto registrado más sus ajustes aprobados | Que ya esté pagado |
| Costo directo | Componentes configurados para una atención | Precio que debe pagar el paciente |
| Reparto | Parte de un gasto compartido asignada a atenciones | Otro gasto que deba sumarse al original |
| Arancel y cuenta | Valor administrativo y obligación de pagar o cobrar | Dinero ya ingresado o salido |
| Pago o cobro confirmado | Movimiento aprobado, con fecha efectiva | Saldo bancario o rentabilidad |

Mostrar el valor de los reportes · 4 minutos

**Pantalla:** [Resumen · septiembre](http://localhost:8082/finanzas?mes=2026-09&tab=resumen).

1. Señalá **Gastos aprobados**, **Por aprobar**, **Distribuido entre atenciones** y **Sin distribuir**. “Distribuido + sin distribuir explican el aprobado; no son otros gastos”. Los ajustes por aprobar se informan aparte y todavía no cambian los importes.
2. En **Barras**, seleccioná una categoría para abrir los gastos que explican el número. Volvé a Resumen; cambiá a **Listado** si querés leer cifras exactas.
3. Abrí **Evolución mensual**, elegí **12 meses** y dejá **Completos y provisionales**. Compará octubre de 2025 a septiembre de 2026; destacá un concepto y probá **Comparar con referencias**.
4. Mostrá septiembre como mes en curso. Luego abrí [agosto](http://localhost:8082/finanzas?mes=2026-08&tab=resumen) para contrastar un mes anterior; al terminar volvé a septiembre.

**Qué decir:** “Una baja en septiembre no demuestra ahorro: todavía está abierto. Los puntos provisionales también pueden indicar cargas o aprobaciones pendientes. Comparamos pesos de cada mes, sin ajustar por inflación.”

**Resultado esperado:** septiembre muestra **$750.000 aprobados**, **$45.000 por aprobar**, **$750.000 distribuidos** y **$0 sin distribuir**, más un ajuste por aprobar informado por separado. Los gráficos llevan a sus registros; el estado de completitud acompaña al importe. Una referencia es orientativa, no gasto ejecutado ni presupuesto aprobado. Sin carga no equivale a cero.

## 2. Explicar carga, revisión e historia · 4 minutos

**Pantallas:** [Gastos · Consultorios de clínica médica](http://localhost:8082/finanzas?mes=2026-09&tab=gastos) y [Gastos mensuales · Consultorios de clínica médica](http://localhost:8082/finanzas?mes=2026-09&tab=calendario).

1. Elegí el mes en curso y **Consultorios de clínica médica**; en la columna **Gasto**, filtrá el concepto **Electricidad**. Abrí **Detalle** en el gasto aprobado de **$120.000**: tiene un ajuste de **−$10.000 pendiente de aprobación**. El importe vigente aprobado sigue siendo **$120.000**.
2. Señalá el original, estado, motivo e historial. No apruebes el ajuste durante el recorrido principal. Las correcciones conservan el registro original; un reemplazado no se suma como otro gasto vigente.
3. Cerrá el detalle y usá **Ver cuenta existente** en esa fila para anticipar la relación con pagos. Volvé al listado; no intentes crear otra cuenta para ese gasto.
4. En **Gastos mensuales**, mostrale al público qué conceptos debe informar cada área, referencia y estado de carga. Esta configuración fija la obligación de informar; no genera gastos, cuentas ni pagos automáticamente. Abrí el detalle de un concepto y su historial si necesitás explicar una vigencia.

**Qué decir:** “Cargar, aprobar y declarar la carga completa son decisiones diferentes. Que referencia menos aprobado dé positivo no garantiza ahorro: puede faltar información.”

**Resultado esperado:** el ajuste pendiente aparece como pendiente, sin restar $10.000 al confirmado. Declarar completa una carga no aprueba sus gastos ni verifica todas las atenciones.

## 3. Mostrar qué se configura una vez · 4 minutos

**Pantalla:** acciones superiores de la pestaña correspondiente o **Acciones de finanzas**, junto al título. Sólo abrí y cerrá; no guardes cambios.

- **Agregar gasto mensual:** mostrará área, concepto, vigencia y referencia opcional. Explicá que la obligación de informar se mantiene durante su vigencia; no hace falta configurarla todos los meses. No genera gastos, cuentas ni pagos automáticamente. Cerrá sin guardar.
- **Configurar costos por atención:** elegí una **Atención configurada**, un componente y sus **Valores y vigencias**. “Esto determina lo que contamos una vez al completar una atención; no cobra dinero”. Las versiones conservan historia; un cambio no reescribe silenciosamente los costos ya registrados.
- **Configurar cobros por atención:** mostrá una política con arancel y responsable. Las políticas de este escenario generan cargos; una cuenta sin movimientos no es una atención gratuita. “El costo interno y el arancel no son lo mismo, y el paciente no es automáticamente quien paga”. Para explicar la alternativa sin cargo, abrí **Cambiar para futuras atenciones**, mostrale el selector **¿Esta atención se cobra? → No: atención sin cobro** y volvé **sin guardar**. Los cambios rigen para futuras atenciones, no generan cargos retrospectivos.
- **Configurar repartos:** mostrá **Áreas verificadas** y **Reglas activas**. Una regla indica qué concepto se distribuye; la verificación confirma el registro financiero y la declaración de cobertura de actividad del área.

**Códigos de referencia:** en nuevos conceptos, prestaciones y componentes se generan automáticamente. Si necesitás uno propio, está en **Opciones avanzadas**. Los códigos existentes se conservan; los números de factura o comprobante siguen siendo referencias externas que se cargan manualmente. No crees registros sólo para mostrarlo.

**Permisos:** las acciones visibles dependen del perfil, área y sensibilidad. Registrar no concede aprobar, y consultar finanzas no concede acceso clínico. En **Administración → Usuarios → Editar usuario**, la sección **Permisos financieros** está debajo de **Membresías**, plegada inicialmente. Al desplegarla, muestra hasta tres columnas según el espacio disponible, con los permisos existentes marcados y sus alcances disponibles para consultar. Plegarla no descarta cambios sin guardar. Las lecturas heredadas del administrador se identifican como **Por rol** y no se revocan desde ese checklist. **Guardar permisos financieros** es independiente de guardar los datos generales del usuario. No cambies permisos para demostrarlo.

## 4. Seguir una atención hasta sus costos y repartos · 5 minutos

**Pantallas:** [Costos por atención · Consultorios de cardiología](http://localhost:8082/finanzas?mes=2026-09&tab=costos) y [Distribución · Consultorios de cardiología](http://localhost:8082/finanzas?mes=2026-09&tab=repartos).

1. En **Casos → Todos**, buscá **Nicolás Agüero** por nombre y anotá el número del caso de la consulta cardiológica. En **Costos por atención**, elegí el mes en curso y **Consultorios de cardiología**; ingresá ese número en **Número de caso**.
2. Abrí **Ver composición**. Mostrá **Componentes directos** por **$23.500** —trabajo profesional $22.000 e insumos $1.500— y **Gastos compartidos atribuidos** por **$92.500** —electricidad $32.500, limpieza $42.500 y mantenimiento $17.500—. Revisá **Alcance y pendientes**. No sumes el total del gasto original otra vez a todas las atenciones que lo comparten.
3. En la composición, abrí un gasto compartido para mostrar su origen. También podés anotar el concepto y encontrarlo en **Gastos** con el mes y el área seleccionados. Después abrí **Distribución**, filtrá ese concepto y desplegá **Ver … atenciones**.
4. Usá **Ver historial** sólo para explicar versiones. Las versiones antiguas no se suman al resultado actual. Si aparece **Actualización pendiente**, esperá la actualización; no describas la distribución anterior como vigente.
5. Si querés mostrar el lado clínico, abrí el caso de Nicolás desde **Casos → Todos** con Julio Barreto en una sesión separada. Mirá una atención ya completada; no hace falta completar otra. El registro financiero deriva de la atención completada, sin nuevas preguntas económicas al profesional.

**Ejemplo de información incompleta:** buscá **Sergio Páez** en **Casos → Todos**, anotá el número de su caso de Radiología ambulatoria e ingresalo en **Costos por atención** con esa área seleccionada. Tiene un componente sin valor y el responsable del cobro por completar. Mostrá los pendientes sin resolverlos durante el recorrido; no son cero ni deuda atribuida a esa persona.

**Qué decir:** “Directos completos significa completos para los componentes configurados. No promete el costo total del paciente ni del hospital. Un reparto distribuye costo interno: no crea una cuenta por cobrar ni un pago.”

**Resultado esperado:** se puede ir de atención a composición y de reparto a fuente, conservando el alcance de cada número. Un faltante se ve como pendiente, no como costo cero.

## 5. Cerrar el circuito con pagos y cobros · 6 minutos

**Pantalla:** [Pagos y cobros · septiembre](http://localhost:8082/finanzas?mes=2026-09&tab=dinero). Volvé a **Todas las áreas e institucional**.

### A. Una cuenta por pagar, sin confundir gasto con dinero

En **Pagos y cobros**, seleccioná septiembre, **Consultorios de clínica médica** y **Por pagar**. En **Buscar cuentas**, escribí **Cooperativa Eléctrica del Bosque** y abrí **Ver cuenta** en la fila de **$120.000**. La tabla muestra la contraparte, no el concepto del gasto; cotejá el **Gasto de origen #** del detalle con el número de la fila de Electricidad en **Gastos**.

| Dato de la cuenta de septiembre | Importe inicial |
| --- | ---: |
| Importe actual de la cuenta | $120.000 |
| Pagado neto confirmado | $60.000 |
| Pago por aprobar | $20.000 |
| Pendiente confirmado | $60.000 |
| Disponible para registrar otro pago | $40.000 |

**Qué decir:** “Todavía debemos $60.000. Hay $20.000 cargados que esperan aprobación; no los damos por pagados, pero los reservamos para no cargarlos dos veces. Por eso puedo registrar otros $40.000.”

Mostrá el movimiento pendiente y sus acciones **Aprobar movimiento** / **Rechazar movimiento**, sin ejecutarlas. Abrí **Registrar pago** para mostrar el campo **Aprobado**, marcado de entrada para la dirección; desmarcarlo deja el registro pendiente. Cerrá sin guardar. Un perfil sin permiso de aprobación registra pendiente aunque normalmente la carga venga aprobada.

### B. Un cargo por cobrar con responsable explícito

En **Pagos y cobros**, seleccioná septiembre, **Consultorios de cardiología** y **Por cobrar**. Buscá **Mutual del Valle** y abrí la cuenta de **$45.000**. Cotejá la **Atención de origen #** del detalle con el **Registro #** que aparece en **Costos por atención** al buscar el caso de Nicolás Agüero. La responsable explícita es la mutual, no Nicolás: el listado muestra el nombre de la contraparte.

| Dato de la cuenta de Consultorios de cardiología | Importe inicial |
| --- | ---: |
| Importe actual de la cuenta | $45.000 |
| Cobrado neto confirmado | $15.000 |
| Cobro por aprobar | $10.000 |
| Pendiente confirmado | $30.000 |
| Disponible para registrar otro cobro | $20.000 |

Abajo, en **Cobros por completar**, mostrá una atención con arancel o responsable faltante. Abrí **Completar cobro** y cerrá sin guardar. “Primero se completa la información administrativa para crear la cuenta; eso todavía no registra un cobro”. Este bloque incluye todos los meses del área seleccionada.

### C. Dos fechas que responden preguntas distintas

1. Cambiá el **Mes económico** a agosto. En **Pagos y cobros**, seleccioná **Consultorios de clínica médica** y **Por pagar**; buscá **Cooperativa Eléctrica del Bosque** y abrí la cuenta de **$110.000**. Mostrará pagos de **$50.000 en agosto** y **$60.000 en septiembre**.
2. Dejá **Mes de pagos y cobros** en septiembre y abrí **Ver movimientos del período**. El pago de $60.000 aparece en septiembre aunque su cuenta sea de agosto.
3. Señalá **Cobros netos $150.000**, **Pagos netos $610.000** y **Diferencia del período −$460.000**. Abrí **Ver importes originales y devoluciones**: hay **$155.000 de cobros originales** y **$5.000 devueltos**; por eso el cobro neto es $150.000.

**Qué decir:** “Una cosa es a qué mes corresponde el gasto o cargo; otra, cuándo entró o salió el dinero. Esta diferencia no es caja disponible ni ganancia”. No hay anticipos, excedentes ni movimientos sin cuenta vinculada en este alcance.

**Devoluciones, si surge la pregunta:** buscá **Patricia Bustos** en **Casos → Todos**, anotá su número de caso y encontrá el **Registro #** en **Costos por atención**. En **Pagos y cobros**, seleccioná septiembre, **Consultorios de clínica médica** y **Por cobrar**; buscá **Mutual del Valle**, abrí la cuenta de **$25.000** y cotejá su **Atención de origen #** con ese registro. Tenía un cargo de **$30.000**; la devolución de **$5.000** con reducción dejó cuenta y cobrado neto en **$25.000**, sin pendiente. Mostrá el historial, no crees otra devolución. Las devoluciones se vinculan a un movimiento aprobado y muestran su efecto antes de confirmar. Pueden mantener la cuenta o acompañar su reducción; una reducción anterior se vincula sin descontarla por segunda vez. No modifican automáticamente el gasto original ni los costos.

## 6. Cierre · 2 minutos

Volvé a [Resumen · septiembre](http://localhost:8082/finanzas?mes=2026-09&tab=resumen), con todas las áreas.

**Frase de cierre:** “Podemos explicar los gastos y sus pendientes, distribuir lo que corresponde, conocer componentes del costo de atención y seguir cuentas y dinero por separado, con historia y permisos. Donde falta información, el sistema lo muestra: no inventa una cifra”.

Antes de presentar, comprobá que puedas explicar dos casos: por qué un pago pendiente no baja todavía la deuda y por qué el reparto no se suma al gasto original. Si algo no coincide, revisá mes, área, filtros, perfil e historial antes de cargar de nuevo.

## Acciones opcionales de ensayo

No son necesarias para recorrer el módulo. Las cifras anteriores describen la carga inicial; después de guardar una acción, dejá de presentarlas como estado inicial. Antes de repetir el ensayo, revisá el historial de la cuenta.

**Sin cambios — explorar una carga:** en la cuenta de Nicolás, abrí **Registrar cobro**, ingresá `5000` en **Importe en ARS**, desmarcá **Aprobado** y leé la explicación. Cerrá sin confirmar. Los valores siguen en $15.000 confirmados, $10.000 por aprobar, $30.000 pendientes y $20.000 disponibles.

**Con cambio — aprobar una sola vez el pago existente de $20.000:** en la cuenta de electricidad de septiembre, verificá que ese movimiento siga pendiente. Pulsá **Aprobar movimiento** y **Confirmar aprobación**. El pagado neto pasa a **$80.000**, el pendiente a **$40.000**, la reserva queda en **$0** y el disponible sigue en **$40.000**. El gasto sigue en **$120.000**; su ajuste de −$10.000 continúa pendiente. En el resumen de dinero de septiembre, los pagos netos pasan a **$630.000** y la diferencia a **−$480.000**. Esta acción conserva historial y no se deshace desmarcando una casilla. Si ya fue aprobada, sólo explicá su historial; no crees otro pago para repetirla.

Si una confirmación demora o se pierde la respuesta, revisá el historial antes de volver a cargar. No recargues ni cierres un formulario incierto para recrear la misma operación a ciegas.

## Ficha de casos y comprobación inicial

Los identificadores cambian en cada carga. Buscá los registros en pantalla por mes, área, concepto, contraparte o paciente y comprobá los importes antes de presentarlos.

| Caso a mostrar | Dónde localizarlo | Clave para explicarlo |
| --- | --- | --- |
| Electricidad, Consultorios de clínica médica, septiembre | [Gastos](http://localhost:8082/finanzas?mes=2026-09&tab=gastos): área y concepto Electricidad; **Ver cuenta existente** en el gasto de $120.000 | Aprobado $120.000, pago pendiente $20.000 y ajuste de gasto pendiente −$10.000 son estados distintos |
| Electricidad, Consultorios de clínica médica, agosto | [Gastos](http://localhost:8082/finanzas?mes=2026-08&tab=gastos): área y concepto Electricidad; **Ver cuenta existente** en el gasto de $110.000 | Cuenta de agosto con un pago de $60.000 efectuado en septiembre |
| Nicolás Agüero, Consultorios de cardiología, 10/09 | **Casos → Todos**: buscá al paciente; copiá el número de caso a **Costos por atención** y anotá el **Registro #**. En **Pagos y cobros**, buscá Mutual del Valle y cotejá la **Atención de origen #** de la cuenta de $45.000 del área | Costo directo $23.500, compartido $92.500 y arancel $45.000; quien paga es Mutual del Valle |
| Patricia Bustos, Consultorios de clínica médica | **Casos → Todos**: buscá a la paciente y obtené su número de caso. En **Costos por atención**, anotá el **Registro #**; en **Pagos y cobros**, buscá Mutual del Valle y cotejá la **Atención de origen #** de la cuenta de $25.000 del área | Cargo original $30.000; devolución con reducción de $5.000; cuenta y cobrado neto $25.000 |
| Sergio Páez, Radiología ambulatoria, 14/09 | **Casos → Todos**: buscá al paciente; copiá el número de caso a **Costos por atención** | Falta un valor de costo y definir al responsable del cobro; no inventar datos ni asignar deuda al paciente |

En el estado inicial, el mes en curso tiene **7 atenciones financieras**. La historia preparada abarca los doce meses que terminan en el mes de la carga. Los totales esperados de esta guía son de septiembre con todas las áreas, salvo indicación expresa.

**Documento imprimible:** abrí `guia-finanzas-central.html` en el navegador y usá **Ctrl+P**; puede guardarse como PDF. No necesita otro servidor.
