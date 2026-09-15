# Retoques de UX previos a la demo

Diseño confirmado por el usuario el 15/09/2026. No autoriza borrar o sembrar
datos, recalcular históricos, cambiar reglas de autorización ni publicar commits.

## Resultado observable

- Acciones de cabecera junto al título: registro y alta mensual en Gastos
  registrados, configuración de costos en Costos por atención, repartos en
  Repartos y cobros en Pagos y cobros. Las otras acciones autorizadas quedan
  en un menú accesible de más acciones. Nunca incluye acciones prohibidas.
- Un solo término visible: Gastos mensuales. La configuración sigue indicando
  qué debe informarse; no registra gastos, cuentas ni pagos automáticamente.
- Códigos internos de conceptos, prestaciones y componentes generados por el
  servidor al omitirlos. Opción avanzada manual; los existentes no cambian.
  Referencias de facturas/comprobantes no se inventan.
- Valores: vigente hoy destacado, programados diferenciados, históricos
  atenuados pero legibles y fechas ordenadas. Un sucesor futuro no vuelve
  histórico antes de tiempo al valor que corresponde hoy.
- Cambiar valor precarga el importe anterior; altas y cambios proponen fecha/hora local actual.
  Mantiene validación de intervalos y conservación del historial.
- Inicio ofrece Finanzas según los mismos permisos efectivos del módulo.
- Editar usuario incluye Permisos financieros debajo de Membresías, con
  acciones existentes marcadas. Conserva institución, membresía, áreas y
  sensibilidad por acción. Lectura heredada del administrador se identifica
  como Por rol y no se presenta como revocable. Cambios guardados en bloque,
  sin aplicar parcialmente un error ni pisar una edición concurrente.

## Dirección visual

Personal hospitalario que registra, aprueba y consulta gastos, costos,
atenciones, vigencias y repartos. Se conserva la tipografía, escala y paleta
existente: superficies claras/oscuras del tema, texto de tinta, gris para
historia, verde de estado vigente, ámbar para pendientes y azul informativo.
La señal distintiva es separar configuración mensual, gasto registrado y
dinero, sin presentar sus importes como equivalentes.
Se sustituye la botonera global por acciones contextuales; la historia con
igual peso que lo vigente por estados explícitos; las concesiones dispersas
por un checklist con alcance inspeccionable. Sin rediseño decorativo.

## Implementación y verificación

1. Acciones, terminología y acceso de Inicio; pruebas HTTP simuladas por UI.
2. Costos/intervalos y códigos; pruebas de formularios y API sin datos reales.
3. Editor integrado y guardado atómico de permisos; validaciones de alcance,
   revocación, herencia por rol, membresía inactiva y conflictos concurrentes.
4. Integración, build de frontend, pruebas financieras relevantes en base de
   test aislada y comprobación visual sin registrar operaciones en 8090.

Riesgos: permisos de distintas membresías no se deben sumar para fabricar
un alcance; códigos únicos deben resistir altas concurrentes; fechas locales
no deben convertirse en el día UTC equivocado; todos los textos deben
conservar la diferencia entre importe orientativo y gasto aprobado.

## Resultado de implementación y validación

Implementado en la cabecera de Finanzas, formularios de gasto/costos, Inicio y
editor compartido de permisos (Administración y Editar usuario). El servidor
genera códigos en las altas y guarda el bloque explícito por membresía con
control de versión. La guía Los Aromos, Markdown y HTML, refleja estos cambios.

- PostgreSQL de pruebas: `apps.finanzas apps.accounts`, 334 pruebas OK (145,478 s).
- Después del último endurecimiento del bloqueo: `apps.finanzas.test_editor_permisos
  apps.finanzas.tests.ConcesionFinancieraApiTests apps.finanzas.test_permisos_contables`,
  33 pruebas OK (14,322 s). Incluye dos guardados simultáneos: uno aplica y otro
  recibe conflicto. Se corrigió el cierre de conexiones del propio test concurrente.
- Ambos comandos se ejecutaron mediante `manage.py shell` y `call_command('test', ...)`,
  fijando NAME a `finanzas_ux_validation` y TEST.NAME a
  `test_finanzas_ux_demo_20260915`. La base temporal se retiró; `cauce` no fue destino.
- Frontend: `npx playwright test --config playwright.finanzas-ui.config.js
  --output C:/Users/Juanito/AppData/Local/Temp/finanzas-ux-integrada-final-20260915`,
  114 pruebas OK (2,5 min), API simulada. Cubre acciones, alcances, errores,
  formularios, vigencias, gráficos y dinero; no registra operaciones en la demo.
- `npm run build -- --outDir C:/Users/Juanito/AppData/Local/Temp/cauce-build-ux-20260915-225100`:
  OK, 743 módulos. `manage.py makemigrations --check --dry-run`: sin cambios.
- `git diff --check`: OK. `localhost:8090`: HTTP 200, servicios sin reiniciar.

Una corrida preliminar de UI tuvo una expectativa textual anterior al cambio y
una pérdida de modal coincidente con recargas de Vite durante ediciones. La
expectativa se actualizó; los casos se repitieron tres veces y la suite final,
con frontend sin ediciones simultáneas, pasó completa.

Pendiente: primera revisión del usuario, solicitada por él antes de la revisión
final del conjunto. Las pruebas no sustituyen su aceptación ni acreditan su
entendimiento. No se hicieron escrituras de ensayo en los datos de la demo,
revisión global final, commits, push ni merge.

## Feedback durante la primera pasada

El usuario pidió estos ajustes locales adicionales:

- Desplegable con el mismo estilo primario que Registrar gasto, siempre último
  y al extremo derecho; título y nombre accesible: Acciones de finanzas.
- Agregar gasto mensual también visible en Gastos mensuales. Nuevo concepto
  visible donde haya una acción autorizada que use conceptos de gasto:
  registro, configuración mensual o reparto. Sin ampliar permisos.
- Editar usuario pasa de 720 a 1040 px como máximo, respetando el ancho móvil.
  Permisos financieros se pliega inicialmente y conserva la edición al
  cerrar/abrir. La grilla se adapta a tres, dos o una columna según el espacio.
  Cada alcance continúa plegable por acción y el guardado sigue separado.

Se conservan tokens y comportamiento de foco del panel financiero; su estilo
primario es opcional y no cambia los botones de ayuda ni los filtros.

Validación de este feedback: 77 pruebas UI OK (1,8 min), mediante
`npx playwright test --config playwright.finanzas-ui.config.js finanzas-acciones-demo.spec.js finanzas-permisos-demo.spec.js finanzas-ui.spec.js --output C:/Users/Juanito/AppData/Local/Temp/finanzas-botonera-columnas-final-20260915`.
Se compararon estilos calculados con Registrar gasto, posición derecha en
seis pestañas y dos anchos, distribución real 3/2/1 columnas, navegación por
teclado y conservación del formulario al plegarlo. Capturas de escritorio y
móvil inspeccionadas. `git diff --check` OK; 8090 responde HTTP 200.
Sin cambios de backend ni datos: no se repitió la suite backend ni el build
completo para este ajuste exclusivamente visual.

### Segunda corrección del editor de usuario

Nombre, apellido y nueva contraseña comparten fila en escritorio; en móvil se
apilan. Las acciones financieras se distribuyen en pilas independientes de
ancho adaptable: desplegar o marcar una sólo desplaza su propia columna, no
las tarjetas de las otras. El formulario y sus validaciones no cambian.

Se retiraron el botón global de permisos, su estado y el componente antiguo
ConcesionesFinancieras.jsx. Usuarios importa directamente el editor integrado;
los endpoints y permisos del backend se conservan. Las tres pruebas que usaban
el acceso antiguo ahora recorren Editar usuario.

Validación: 15 pruebas seleccionadas OK (21 s) con
`npx playwright test --config playwright.finanzas-ui.config.js finanzas-permisos-demo.spec.js finanzas-ui.spec.js --grep 'permiso|contable recibe|checklist|nombre apellido|detalle no permite' --output C:/Users/Juanito/AppData/Local/Temp/finanzas-usuario-columnas-independientes-20260915`.
Incluye posición relativa de todas las tarjetas de las otras columnas antes y
después de marcar y plegar; alineación de campos, móvil, persistencia de edición,
herencia, conflictos y ausencia del acceso retirado. Capturas inspeccionadas.
`git diff --check` OK. Sin escrituras sobre datos de demo ni cambios de backend;
no se repitieron build completo ni pruebas backend para esta corrección local.
