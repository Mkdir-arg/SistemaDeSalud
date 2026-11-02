# OSTEL: catálogo sintético, validación local y homologación pendiente

## Reconciliación 30/10/2026: identidad y familia (#181/#142)

El orden vigente está en [#141](https://github.com/Mkdir-arg/SistemaDeSalud/issues/141).
PR186, PR200 y PR196 están incorporados; #184 permanece In QA, sin aceptación
integral inferida. Registro local: `odd/tasks/ostel-operacion-integral.md`.

- **Confirmado en las fuentes documentadas:** NUMERO individual, CUIL de la
  persona, NROAFI compartible; CUILTIT referencia al titular, que se referencia
  a sí mismo. El formato requiere 40 columnas. No falta CUILTIT.
- **Decisión aprobada el 30/10:** conservar CODPAR separado, sin perder relaciones
  que no caben en `Afiliado.parentesco` (`conyuge`, `hijo`, `hija`, `conviviente`,
  `otro`). El diccionario de consulta no es una equivalencia aprobada. Los 56
  valores de fixtures son muestras de rangos, no todo el catálogo.
- **Primer incremento local T1a:** `SaludPadron.codpar_ostel` conserva hasta 40
  caracteres literales (incluidos ceros y espacios), separado del parentesco
  genérico. Hay códigos que revelan discapacidad: sólo se consulta/edita mediante
  el endpoint protegido `padron/{id}/salud/`, con designación de salud y el rol
  existente. No se agrega al padrón/exportación general.
- El PATCH requiere revisión y motivo; omitir el campo conserva su valor y
  enviar `""` lo vacía explícitamente con historial protegido. Se rechazan valores
  no textuales y de más de 40 caracteres, sin cambiar datos ni revisión. El
  catálogo no se homologa: registrar un código no prueba que sea válido para
  prestaciones ni modifica `parentesco_sensible`, familia o cobertura.
- Migración aditiva `0017_saludpadron_codpar_ostel`: vacío por defecto, sin
  reconstrucción desde lotes anteriores. Una reversión elimina estos nuevos
  valores; no es una recuperación segura después de usarlos. En un incidente,
  conservar datos y reparar hacia adelante antes de considerar una reversión.
- **Límites T1a:** no hay formulario nuevo ni copia automática desde importación.
  El importador general y el bloque de salud tienen permisos distintos; no se
  agregó un bypass. El acceso preexistente a filas originales de importación
  requiere tratamiento propio antes de ampliar ese flujo. No se construyen
  familias ni se deriva elegibilidad.
- T1a: RED observado (400 por campo desconocido), luego GREEN en PostgreSQL
  descartable autorizado; chequeo de migraciones sin cambios faltantes.
  Verificador independiente: 79 tests y tres probes aprobados, comparación
  baseline/candidato de seis respuestas API equivalentes (excepto el campo nuevo
  intencional y valores volátiles). Incorporados los probes de preservación y
  rechazo de tipos: suite final de 81 tests OK (14.411 s), incluidos padrón,
  importación y concurrencia. No constituye entrega publicada ni aceptación.
- Revisión nativa consentida del commit `e0aec12`: riesgo y confiabilidad sin
  hallazgos; cierre confirmado el 30/10/2026. Fue inspección de parches inmutables,
  no otra ejecución de pruebas. La decisión D2 posterior separa la importación
  administrativa del paso protegido descrito a continuación.

### T1d: propuesta y confirmación de vínculo familiar

La importación administrativa no ensambla familias. Después de aplicar las filas
necesarias, un editor del padrón puede confirmar cada vínculo explícitamente:

1. `GET /api/financiadores/{financiador}/padron/{afiliado}/familia-ostel/?importacion=123&fila=1`
   consulta una propuesta sin escribir. Devuelve `titular`, `revision` del
   integrante y `revision_titular`; no devuelve identificadores personales.
2. `POST` al mismo recurso con `importacion`, `fila` y los tres valores recibidos
   confirma el vínculo. La respuesta 200 es la ficha administrativa habitual.
   La consulta usa permiso de lectura; la confirmación requiere escritura.

`fila` es el ordinal estable del lote. Sólo se resuelve CUILTIT contra un CUIL
original único del mismo lote/financiador, con ambas filas aplicadas y sus
identidades actuales coincidentes. La fila titular debe autorreferenciarse y
seguir siendo raíz; no se usa NROAFI ni se busca un titular fuera de ese lote.
El orden no importa, pero un titular aún pendiente en otra tanda de 100 filas
requiere terminar su aplicación antes de proponer el vínculo.

- Fuentes incompletas, ambiguas, con baja, discordancias o ciclos requieren
  revisión: 400; recursos inexistentes o ajenos: 404; permisos insuficientes: 403.
  Una revisión obsoleta de cualquiera de las dos fichas devuelve 409. Ante
  conflicto se consulta otra propuesta, sin actualizar revisiones a ciegas.
- No se reemplaza otro titular ni se convierte una raíz con integrantes en
  dependiente. El parentesco queda pendiente si estaba vacío; una clasificación
  existente se conserva. Repetir un vínculo coincidente con revisiones actuales
  no genera otra modificación. Los rechazos no cambian datos ni historial.
- La confirmación revalida bajo locks del lote, financiador y ambas fichas por
  PK; reutiliza `editar_ficha` y registra lote/filas en el historial. No modifica
  fuente original, CODPAR, salud, plan ni derechos de cobertura.

El corte T1d es API local, no aceptación operativa. No hay backfill
ni migración. Retirar la acción impide nuevos vínculos, pero no revierte los ya
confirmados: conservar su historial y corregirlos explícitamente si corresponde.
Verificación independiente: 99 regresiones, cinco probes de rechazo/concurrencia
y ocho observaciones previas equivalentes al baseline. Probes incorporados;
repetición local final: 104 tests OK, con PostgreSQL descartable autorizado.
Incluye `test_familia_ostel` y `test_concurrencia_familia_ostel`; runner completo y
estado de revisión nativa en el registro de trabajo. No acredita UI, CI ni deploy.

### T1e: confirmación desde la pantalla de importación

En **Aplicadas**, la acción **Vincular familia** abre una propuesta para esa fila.
El diálogo muestra integrante, titular propuesto y procedencia del lote, sin
agregar CUIL ni valores CODPAR. **Cancelar** no escribe; **Confirmar vínculo**
envía las revisiones recibidas. El detalle anterior de la fila sigue disponible.
La propuesta puede rechazarse si esa fila es titular, falta evidencia o existe
otro vínculo: la pantalla no intenta corregirlo ni elegir otra persona.

Después de un conflicto se descarta la propuesta. Una respuesta perdida muestra
incertidumbre, no una afirmación de rollback: **Consultar propuesta** obtiene
revisiones actuales y la persona decide si confirma nuevamente. No hay reintento
automático del POST. Confirmar no modifica clasificación ni cobertura.

Se reutilizan el modal accesible y los tokens visuales existentes. Escape cierra
sólo el diálogo superior y devuelve el foco; durante la petición no puede cerrarse
ni cambiarse el lote. El tablero de filas mantiene scroll horizontal local.
Runner real focal: `npx --no-install playwright test --config playwright.importacion-real.config.js familia-ostel-real.spec.js`.
Requiere `SALUD_FAMILIA_MANIFEST` generado por `e2e/fixtures/preparar_familia_ostel.py`
en un temporal propio, settings PostgreSQL descartables y ambos servidores locales.
El manifiesto contiene credenciales ficticias efímeras: no imprimir ni publicar.
No ejecutar la suite general con su siembra de volumen para esta comprobación.
La demostración local no constituye publicación ni aceptación humana.

Verificación T1e: seis recorridos Playwright locales aprobados, incluidos móvil,
teclado, 409 real y pérdida de respuesta después del commit. Un 403 inyectado
verifica sólo la reacción visual, no una nueva prueba de revocación de permisos.
El verificador independiente compiló la UI y ejecutó cuatro regresiones de
importación tanto en baseline como en candidato, todas aprobadas. No hubo CI.

### T1b: copia explícita de una fila aplicada al bloque de salud

El operador conserva el circuito administrativo existente. Importar un lote no
rellena `codpar_ostel`. Un usuario con designación activa de salud y rol editor
puede ejecutar `POST /api/financiadores/{financiador}/padron/{afiliado}/salud/codpar-ostel/`
con `{"importacion": 123, "fila": 1, "revision": 1}` (identificadores ilustrativos).
La revisión es la del bloque de salud, no la del lote ni la ficha administrativa.
La respuesta 200 tiene el mismo formato que la consulta protegida de salud.

- El lote debe ser OSTEL versión 3, tipo padrón, del mismo financiador; `fila` es
  el ordinal estable almacenado, no la posición de la lista ni el número Excel.
- Sólo se admite una fila aplicada cuyo afiliado persistido coincida con el
  solicitado. Nunca se vuelve a resolver identidad por números o documentos.
- Se copia exclusivamente `original.CODPAR`, como texto literal no vacío de hasta
  40 caracteres. Los códigos numéricos de Excel no se convierten automáticamente:
  requieren corrección explícita de la fuente o el circuito manual protegido.
- La procedencia (lote, hoja, fila Excel) queda en el motivo del historial de
  salud. No se escribe código, motivo ni contenido sensible en eventos generales.
- Repetir con la revisión actual y el mismo valor no crea otro cambio. Una
  revisión obsoleta devuelve 409; origen/entrada inválidos, 400; sin designación o
  rol editor, 403; recurso ajeno/inaccesible, 404. Los rechazos no cambian datos.
- No se alteran el lote original, familia, parentesco genérico, derechos ni otros
  campos de salud. La transacción bloquea el lote y reutiliza los locks de
  membresía/afiliado, revisión e historial de `editar_protegido`.

Verificación local: RED 404 del nuevo recurso, luego GREEN del circuito API real
con importación sintética sin designación y copia designada.
La validación de campos inesperados inicialmente generaba un error interno por
una estructura incorrecta de errores del serializer; corregida y cubierta con
rechazos 400 sin mutaciones. Verificador independiente: 87 regresiones y tres
probes aprobados; nueve respuestas de interfaces anteriores equivalentes al
baseline. Probes incorporados: revocación durante espera del lote, dos copias
concurrentes y destino de otro financiador. Repetición del padre: 90 tests OK
(31.171 s). Carrera copia/aplicación administrativa inspeccionada, no ejecutada.
Commit local `4212293`; revisión nativa omitida por decisión del usuario el
30/10/2026 sólo para este candidato. La verificación independiente se conserva;
no se presenta como aprobación nativa ni publicación.

Sin nueva pantalla: no se ejecutó navegador ni se acredita aceptación operativa.
Permanece la exposición preexistente de filas originales en la consulta general
de importaciones; este paso protegido no la corrige ni amplía sus permisos.
Rollback T1b: retirar acción, serializer y servicio de copia; conservar el campo
protegido T1a y sus datos/historial. No hay migración en este corte.

Comando de regresión (sólo base de pruebas autorizada):
`python -B manage.py test apps.financiadores.test_codpar_importacion apps.financiadores.test_codpar_ostel apps.financiadores.test_padron130 apps.financiadores.test_ostel_importacion apps.financiadores.test_concurrencia_padron130 --settings=config.settings_financiadores_postgres_test --noinput --keepdb --verbosity 0`.
- **Límite:** todavía no se construyen familias automáticamente; no inferir
  parentesco por NROAFI, sexo por código, ni derechos por relación familiar.
- **Verificado en `cae9e16`:** `python -B -m unittest
  backend.apps.financiadores.tests_ostel_scenarios -v`, 22 pruebas OK, sin DB.
  Prueba generador y lector, no persistencia familiar, concurrencia ni aceptación.
- **PR197:** abierto/draft en `a7cc182`, cinco checks exitosos consultados el
  30/10. No se integró; sus resultados históricos no prueban la rama actual.

### T1c: vínculo conocido, clasificación pendiente (D3 aprobada)

`titular` identifica el vínculo; `parentesco` lo clasifica. Desde la decisión del
30/10/2026 se admite `titular` presente con `parentesco=""`: clasificación pendiente,
no ausencia de vínculo ni equivalencia a `otro`. Se conserva CODPAR por separado
en salud, sin derivar clasificación genérica, sexo, derechos ni elegibilidad.

- PATCH de ficha puede registrar el titular sin clasificación, clasificarlo
  después o vaciar explícitamente la clasificación sin eliminar el vínculo.
- `parentesco` no vacío sin titular sigue rechazado. Mensaje actualizado:
  «Se requiere un titular para informar parentesco.» Para desvincular un integrante
  clasificado se deben vaciar explícitamente ambos campos en la misma edición.
- Se conservan revisión optimista, historial, permisos, mismo financiador,
  estructura de un nivel y rechazo de ciclos. No se modifican locks ni esquema.
- La importación genérica XLSX v2 acepta el vínculo con clasificación pendiente;
  una celda vacía sigue significando omisión, no borrado de una clasificación
  existente. Su resolución por orden de filas no cambia en este corte.
- Consulta familiar, listado y exportación conservan titular conocido y
  clasificación vacía. La pantalla existente identifica la raíz por ID y presenta
  «Parentesco sin informar» para el integrante; no se modificó frontend.

Este corte habilita la representación, **no ensambla familias OSTEL por CUILTIT**.
Ese siguiente incremento debe resolver el lote completo independientemente de su
orden y detener referencias ambiguas sin modificar familias existentes por
inferencia. Tampoco actualiza masivamente datos ni aplica derechos.

Verificación: RED observado al intentar registrar titular sin parentesco; después
GREEN del mismo caso con revisión e historial. Pruebas API, servicio de importación
y exportación XLSX sobre datos ficticios. Verificación independiente: 115 tests,
dos probes de concurrencia con clasificación pendiente y 14 observaciones previas
equivalentes al baseline; sin bloqueantes. Probes incorporados a las regresiones:
repetición del padre de 117 tests OK (26.547 s). Revisión nativa consentida y cerrada
para `0e2eb40`: riesgo y confiabilidad sin hallazgos, sólo inspección de parches
inmutables. La revisión no autoriza publicación ni sustituye aceptación.
Recorrido navegador no disponible: este worktree no tiene dependencias frontend
instaladas; no se instaló ni inició ese entorno. No hay aceptación humana ni deploy.
Una reversión del nuevo guard volvería a rechazar ediciones de vínculos pendientes
ya creados: conservar esos datos y planificar reparación, nunca borrarlos para
restaurar la regla anterior.

## Actualización 26/10/2026: entrega con CUILTIT

OSTEL agregó CUILTIT como columna 40 y entregó un diccionario de códigos.
Decisiones del usuario:

- CUILTIT es obligatorio: un archivo de 39 columnas no crea lote.
- El lote conserva las 40 columnas.
- Al aplicar, OSTEL actualiza la ficha (sexo, fecha de nacimiento y domicilio),
  con historial.
- CODPROV se traduce como ISO 3166-2:AR. Es un supuesto pendiente de confirmación.
- El diccionario se carga en `CodigoFinanciador` con `cargar_diccionario_ostel`.

Las familias no se arman todavía: #181 las construirá a partir de CUILTIT y CODPAR.
Donde las secciones siguientes digan que falta CUILTIT, rige esta actualización.

Detalle, supuestos y pendientes: `docs/plans/2026-10-26-issue186-avance.md`.

## Estado vigente — 21/10/2026: habilitación elegida por lote

El usuario confirmó separación explícita entre registro y habilitación de cobertura:
por defecto se realizan juntos, sin paso extra; la excepción permite registrar sin
habilitar. La decisión posterior elimina la excepción obligatoria para OSTEL:
todos los formatos de padrón presentan «Habilitar cobertura», marcado por defecto.
La elección rige sólo las altas nuevas y queda fijada en el lote. Importaciones
sobre personas existentes conservan su habilitación; una diferencia con la opción
elegida se reporta como conflicto y bloquea esa fila hasta confirmar con motivo
que se conserva el valor actual. No se permiten cambios masivos de cobertura por importación.
El selector «Contenido del archivo» se elimina. La evidencia de baja encontrada
en las filas sigue bloqueada, las ausencias no tienen efecto y las diferencias
entre fuentes requieren revisión. Las reglas de prestaciones aún esperan a OSTEL;
marcar el checkbox no garantiza autorización de prestaciones ni interpreta FECVTO.
Las secciones fechadas anteriores describen entregas y bloqueos históricos.

El 21/10/2026 el usuario informó **«probado»** después de la entrega del checkbox
por lote y sus conflictos. Se registra esa comprobación local, sin atribuirle
casos individuales, dispositivos o resultados que no detalló. No acredita
homologación de OSTEL ni aceptación productiva.
La guía reproducible está en [Prueba local](ostel-prueba-local.md).
La implementación está commiteada localmente: `e752896` incorpora esta última
decisión y `f8299e1` su documentación, sobre las entregas anteriores.
Push, CI, merge y despliegue siguen sin acreditarse para esta entrega.

Implementación de esta decisión: `importacion_cobertura.py` comparte la detección
de discrepancias; el formato OSTEL usa su subsanación existente y la plantilla del
sistema permite confirmar motivos por fila. Ambos revalidan el estado observado.
La clave de reintento incluye la opción elegida; cambiarla exige revisar un lote
nuevo. Los lotes anteriores sin opción conservan su contrato original. No hay
migración nueva ni cambio de permisos. Consumos externos no habilitan afiliaciones.

Validación de esta actualización: 43 pruebas de backend pasaron entre los módulos
de importación (una prueba adicional de concurrencia omitida por requerir
PostgreSQL); nueve pruebas Playwright con API simulada pasaron. Una comprobación
con navegador/API/SQLite reales verificó checkbox predeterminado, ausencia del
selector de contenido, conflicto de cobertura, revisión con motivo, aplicación y
conservación de la habilitación existente. La concurrencia se registra separadamente abajo.

### Medición integral de volumen — 21/10/2026

Una ejecución aislada con 5.754 altas ficticias válidas mediante DRF APIClient,
endpoints reales, ORM e historial en SQLite `:memory:` terminó sin conflictos ni
errores: 5.754 personas, todas con la habilitación seleccionada, y reintento final
sin duplicación. No se usó ni modificó la base de la demo manual.

- XLSX: 603.317 bytes; previsualización: 10,843 s.
- Aplicación: 327,766 s en 58 llamadas; mediana 5,673 s y máximo 7,387 s por llamada.
- Cuerpos JSON de aplicación acumulados: 234.182.643 bytes (223,33 MiB), porque
  cada tanda devuelve el lote completo. Es un hallazgo de rendimiento a resolver
  o aceptar explícitamente antes de publicar, no una medición de tráfico de red.
- Evidencia y script reproducible: carpeta temporal
  `C:/Users/Juanito/AppData/Local/Temp/ostel-benchmark-357cb486` (`result.json`,
  `benchmark.py`, `README.md`).

Límites: una ejecución sin objetivo de rendimiento acordado; altas válidas, sin
mezcla de conflictos; sin transporte HTTP, navegador, disco, rendimiento
PostgreSQL ni carga multiusuario. El proceso incluye DB en memoria y harness;
su pico observado de 641,8 MiB no representa RAM atribuible a producción. Se midió
el árbol de trabajo con cambios concurrentes de permisos, no un commit aislado.

### Concurrencia PostgreSQL aislada — 21/10/2026

Con autorización expresa del usuario se ejecutaron tres pruebas en PostgreSQL 16
local temporal, con datos ficticios: dos confirmaciones simultáneas de un lote
OSTEL generan una persona; dos lotes con la misma identidad y opciones de
cobertura contrarias generan una aplicación y una revisión, conservando la
habilitación del ganador; dos confirmaciones de consumo generan un consumo.
Las tres pasaron: 1,810 s de tests, 39,875 s totales incluidas migraciones. Tras incorporar los dos casos OSTEL al repositorio se repitieron las tres: aprobadas sin omisiones, 1,912 s de tests y 42,356 s totales. Evidencia de repetición: `postgres-repo-tests.log` y `postgres-repo-result.json`, con limpieza confirmada.

La imagen ya estaba local; el contenedor se limitó a 512 MiB y 1 CPU, puerto
127.0.0.1:55439 y almacenamiento tmpfs. Se verificó su ID, se detuvo y eliminó
únicamente ese contenedor y se borró el archivo temporal de credenciales. No se
tocó la demo ni una base real. Evidencia: `postgres-result.json` y
`postgres-tests.log` en la misma carpeta temporal del benchmark. Los dos casos
OSTEL se incorporaron a `backend/apps/financiadores/test_ostel_concurrencia.py` y son descubribles por la suite PostgreSQL existente de CI. La ejecución local no acredita un resultado de CI.
Comando desde `backend`, con `SALUD_TEST_POSTGRES_URL` apuntando exclusivamente a la base temporal autorizada: `python -B manage.py test apps.financiadores.test_ostel_concurrencia apps.financiadores.test_importaciones.ImportacionesConcurrenciaTests --settings=config.settings_financiadores_postgres_test --noinput --verbosity 2`.

Esto no acredita todos los escritores concurrentes, CI del commit publicado,
rendimiento PostgreSQL con 5.754 registros ni comportamiento de producción.

Implementación local: campo `cobertura_habilitada` con default y db_default true;
`numero_interno` separado de `numero` (NROAFI), único no vacío por financiador;
migración 0013. Los registros existentes mantienen comportamiento y datos. La UI
integra un checkbox en el alta y una edición auditada en ficha; el estado sólo
administrativo se muestra, filtra y exporta. Operador/admin gestionan; auditor lee.
No se modificó la excepción de plataforma del guard general, tratada en #170.

`ostel_importacion.py` usa lotes versión 3 en el historial común. Previsualiza,
marca conflictos, permite corregir/excluir con motivo y revisión optimista, y
aplica las válidas en tandas de hasta 100. La confirmación revalida identidad y
revisión; no repite filas aplicadas. Cambiar el destinatario obliga a mostrar sus
valores antes de aceptar, aunque su contador de revisión coincida con el anterior.
Los duplicados internos bloquean todas sus filas hasta resolución explícita.
Una baja informada o una fuente marcada como bajas no puede forzarse como alta.

Mapeo administrativo habilitado: NUMERO, NROAFI, NRODOC, CUIL y APENOM. Las fechas
y códigos administrativos seleccionados quedan como evidencia original del lote;
no se convierten en cobertura, planes, familia, condición laboral ni bajas. El
resto de las 39 columnas sigue disponible en el archivo original, no se copia
indiscriminadamente al lote ni al padrón. FECING no se asigna a `desde` prestacional;
en un alta sólo administrativa `desde` es la fecha local de registro y no habilita
prestaciones. No se hace importación real ni se reconstruyen personas reales en tests.

Nuevos usos prestacionales consultan la habilitación: selección, evaluación,
reservas, autorizaciones, acceso vigente, legado, preparación y FHIR a través del
resumen administrativo. Los hechos financieros congelan esa decisión para que una
habilitación posterior no la cambie retrospectivamente y las reservas previas
conserven compromisos. No se borra ni cancela historia al deshabilitar.

Revisión por estándares/especificación y revisión adversarial: se corrigieron
lectura por dimensiones XLSX no confiables, sobrescritura entre fuentes sin
revisión, pérdida de borrador y cambio de destinatario con igual revisión.
`brainstorming` delimitó el diseño aprobado; `interface-design` integró la excepción
sin paso extra; `code-review` separó estándares y contrato; `systematic-debugging`
atribuyó los fallos observados antes de corregirlos.

Riesgos y despliegue pendiente: la migración 0013 se aplicó también a la base
SQLite ficticia del entorno local, con respaldo previo; no a una base productiva.
No desplegar ni volver a una versión que ignore el flag después de crear registros
administrativos: podría habilitarlos implícitamente. Revertir el esquema también
perdería esa distinción y NUMERO; no es un rollback seguro automático. Ante un
problema, detener la carga y conservar datos/habilitaciones para reparación hacia
adelante. La medición de 5.754 altas ficticias consta arriba; rendimiento de
producción y transporte HTTP/navegador siguen pendientes. La comprobación del usuario consta arriba;
no hay aceptación por caso registrada ni homologación productiva. No se cargaron
datos reales ni se publicó esta implementación.

### Evidencia anterior de la implementación administrativa (21/10)

Estos resultados corresponden a la entrega previa al entorno persistente y al
checkbox por lote. Sus límites de navegador, servidores y aceptación no reemplazan
el estado vigente y la comprobación del usuario registrados arriba.

- API/importación/cobertura: `python -B manage.py test apps.financiadores.test_ostel_importacion apps.financiadores.test_ostel_api apps.financiadores.test_importaciones apps.financiadores.test_habilitacion_cobertura --settings=config.settings_financiadores_test --verbosity 0`: 52 pruebas, sin fallos, 1 omitida PostgreSQL.
- Ampliación padrón/consulta/exportación/FHIR: 87 pruebas, un fallo de catálogo por campo nuevo ausente. Se agregó columna y se reejecutaron el test afectado y las 13 pruebas administrativas: 14 aprobadas. No se repitieron los 86 casos que ya habían pasado.
- Cobertura, recuperación y autorizaciones revisadas por el agente: 91 existentes (85 aprobadas, 6 omitidas PostgreSQL); 9 nuevas aprobadas tras corregir un fixture que utilizaba un rol de plataforma no autorizado para solicitudes manuales.
- Frontend: 26 pruebas Node aprobadas entre alta, preferencias, tabla y campos. Se corrigió la agrupación de la columna nueva tras el fallo correspondiente.
- Navegador Playwright con API interceptada: 7 recorridos distintos aprobados (ayuda, preferencia/plantilla, historial vacío, retomar lote, aplicación/subsanación, alta habitual, descarte de alta). El test de alta se actualizó al payload booleano explícito y pasó en la reejecución. No es prueba integral navegador/API/DB real.
- `makemigrations financiadores --check --dry-run --settings=config.settings_financiadores_test`: sin cambios faltantes. `git diff --check`: sin errores.
- Los servidores efímeros de Playwright usaron loopback y datos ficticios. No se inició backend de desarrollo ni se aplicó migración a una base real.
- Pendiente: concurrencia PostgreSQL, desempeño con el volumen real, aceptación visual/humana, CI y despliegue. Los tests no demuestran comprensión ni aceptación humana.

Faltantes OSTEL vigentes: (1) CUILTIT para familia; (3) tipo/fecha efectiva de
movimientos, porque diferencias de archivo no bastan para clasificarlos; (5)
TIPODOC/MOTIVO/NROREF, planes y coseguro, incluyendo contradicción A/P y CC respecto
de octubre; (6) condición asociada a FECVTO; (7) revisión de casos individuales.
Los puntos 2 y 4 ya no bloquean esta carga identificatoria administrativa: la
política fue definida por el usuario y no se calculan derechos médicos.


## Historial de entregas y decisiones (20–21/10/2026)

Todo lo que sigue conserva el estado de cada etapa. Las menciones a ausencia de
commits, circuito operativo o aceptación humana, y a la obligación de importar
OSTEL sin cobertura, describen etapas anteriores; no son el contrato vigente. Para
comportamiento, evidencia y pendientes actuales, consultar «Estado vigente».

Fecha: 2026-10-20. Alcance parcial de [#185](https://github.com/Mkdir-arg/SistemaDeSalud/issues/185),
basado en el issue, [#142](https://github.com/Mkdir-arg/SistemaDeSalud/issues/142),
[#180](https://github.com/Mkdir-arg/SistemaDeSalud/issues/180) y el
[contrato de importación existente](README.md#importaciones).
Base inspeccionada: `a91faf46290e3f71eb59fc81ba78f04b809d8d39`.

**Actualización 20/10/2026 tras respuestas de OSTEL:** definiciones parciales
registradas en la matriz al final. Catálogo ampliado a 27 escenarios, 32 lotes
y 64 XLSX; las menciones a 20/23/46 en entregas anteriores son históricas.
La UI vigente es **Importar Excel → formato OSTEL → Revisar archivo**; el botón
independiente citado en recorridos antiguos fue retirado.

**Estado: evidencia del generador disponible; circuito integral y aceptación
humana pendientes.** Publicación técnica en [PR draft #186](https://github.com/Mkdir-arg/SistemaDeSalud/pull/186);
Roadmap sin cambios. Este documento no
homologa códigos, define derechos ni autoriza incorporar datos al padrón.

## Alcance y plan ejecutable

1. Construir filas ficticias de 39 columnas, sin consultar fuentes nominales.
2. Mantener escenarios independientes y lotes ordenados para pruebas entre archivos.
3. Probar estructura, anomalías deliberadas, determinismo y serialización XLSX.
4. Separar esta evidencia de la validación futura del lector, mapeo y aplicación.

Se reutiliza `openpyxl` ya declarado en `backend/requirements.txt`. No se
reutiliza el seed de demo ni el importador porque arrastran Django y contratos
distintos. El generador no importa `ostel_prevalidacion.py`; sus pruebas de
contrato ahora consumen el lector real tras la entrega documentada de #180.
Este tramo #185 no añade dependencias, persistencia, permisos ni frontend.

## Uso reproducible

Desde `backend`, ejecutar únicamente las pruebas propias:

```powershell
python -B -m unittest apps.financiadores.tests_ostel_scenarios -v
```

API local de fixtures en `apps.financiadores.ostel_synthetic`:

- `COLUMNAS`: encabezado ordenado, idéntico al esquema solicitado.
- `generar_escenarios()`: tupla de `Escenario(codigo, lotes)`.
- Cada `Lote(nombre, filas)` contiene tuplas de 39 celdas en ese orden.
- `generar_xlsx(lote, hoja="Hoja1")`: bytes XLSX; admite también `afimotook`.
  No escribe en disco. Se puede usar `BytesIO` o un directorio temporal.
- `exportar_temporales()`: escribe 64 XLSX y `manifiesto.json` en una carpeta temporal nueva y
  devuelve su ruta. No sobrescribe archivos; no modifica el repositorio.

El manifiesto enumera los 27 escenarios y sus 32 lotes en ambas hojas:
ruta relativa, orden de lote dentro de cada escenario, hoja, SHA-256 de los
bytes exportados, cantidad de filas físicas sin encabezado y coordenadas Excel
de filas con datos. Es un inventario de **entradas esperadas**, no un informe
de ejecución del lector ni de aceptación. `aceptacion_ostel` permanece pendiente.
El orden sirve para reproducir una secuencia; no establece precedencia de
fuentes ni demuestra cuál archivo es cronológicamente posterior.
El hash identifica ese archivo concreto; puede variar entre exportaciones por
los metadatos XLSX aunque sus valores sean iguales. No usarlo como identidad
de persona, clave de movimiento ni mecanismo de deduplicación de negocio.

### Prueba manual local

Desde `backend`, generar el paquete completo:

```powershell
$carpetaOstel = python -B -m apps.financiadores.ostel_synthetic
Get-ChildItem -LiteralPath $carpetaOstel
```

Abrir los archivos de esa carpeta con Excel. Para ofrecerlos también en el
navegador local, ejecutar en una terminal:

```powershell
python -B -m http.server 8765 --bind 127.0.0.1 --directory "$carpetaOstel"
```

Abrir `http://127.0.0.1:8765`. Es un listado local de descargas, no la
aplicación del padrón ni una pantalla de importación. Detener con Ctrl+C.
La carpeta temporal queda disponible hasta que se elimine explícitamente.
No publicar ese servidor ni apuntarlo a una carpeta con datos reales.

Recorrido sugerido:

1. Elegir `Hoja1` y abrir `base/entrada.xlsx`: ver 39 columnas y una persona
   marcada como ficticia.
2. Abrir `numero_compartido/entrada.xlsx`: comparar ambas identidades.
3. Abrir `filas_vacias/entrada.xlsx`: datos en filas 3 y 5, vacías 2, 4 y 6.
   La última vacía conserva su posición mediante formato, sin dato inventado.
4. Comparar los dos archivos de `baja_repetida`, luego los de
   `posible_reingreso`, respetando sus prefijos `01` y `02`.
5. Abrir `lote_parcial/entrada.xlsx` y contrastarlo con la matriz de abajo.
6. Repetir un caso desde `afimotook`: sólo cambia el nombre de hoja.

Este recorrido comprueba los estímulos generados. No subirlos al importador
actual como si el mapeo OSTEL estuviera aprobado. El checksum se verifica con
las pruebas, no por inspección visual de Excel.

Ejemplo sin generar archivos persistentes, desde Python con `backend` en la ruta:

```python
from io import BytesIO
from openpyxl import load_workbook
from apps.financiadores.ostel_synthetic import generar_escenarios, generar_xlsx

casos = {caso.codigo: caso for caso in generar_escenarios()}
lote = casos["numero_compartido"].lotes[0]
libro = load_workbook(BytesIO(generar_xlsx(lote, hoja="afimotook")))
try:
    assert libro.active.max_column == 39
finally:
    libro.close()
```

Determinismo significa mismos valores, tipos y orden en cada llamada, sin
semilla aleatoria, reloj ni estado externo. No se promete igualdad binaria
de los ZIP XLSX (metadatos del contenedor). Las fechas nativas se recuperan
como `datetime` a medianoche al leer XLSX; los textos no se convierten a fechas.
No concatenar todos los escenarios en una sola carga: reutilizan identidades
deliberadamente y sólo los lotes de un mismo escenario forman una secuencia.

## Procedencia y límites de los estímulos

Todas las identidades se construyen desde cero: nombres `PERSONA FICTICIA
OSTEL`, documentos calculados desde `99018500`, afiliaciones `FIC185-...`,
domicilios explícitamente ficticios y correos `example.invalid`. Teléfonos
vacíos. No se leyeron Downloads, planillas nominales ni PDFs originales;
las referencias a ellos proceden de los issues. No se copiaron ni anonimizaron
personas. Un número generado puede coincidir por azar con uno existente:
no se afirma que el rango esté reservado ni se consulta un registro real.

`SINTETICO`, `PLAN-FICTICIO`, `EMP-FICTICIA`, `BAJA-FICTICIA`, `00`, `01`,
`AAA` y `ZZZ` son estímulos, no equivalencias de catálogos aprobadas.
En los casos familiares, `NROREF` coincide deliberadamente con el `NROAFI`
de otra fila; esto permite comprobar presencia textual. OSTEL debe confirmar
la clave real, su alcance y el significado de los sufijos antes del mapeo.
La fila base es un control estructural, **no una afiliación aprobada para importar**.
Un checksum correcto tampoco acredita CUIL asignado, identidad ni afiliación.

## Catálogo y expectativas separadas

Fila Excel 1 es el encabezado. Las expectativas de esta tabla describen
los datos generados; no son resultados ya obtenidos de #180 ni del importador.

| Escenario | Datos y expectativa técnica comprobable hoy | Decisión pendiente de OSTEL |
|---|---|---|
| `base` | Una fila, 39 columnas, CUIL de 11 dígitos con checksum correcto y documento coincidente | Obligatoriedad y homologación de todos los códigos |
| `numero_compartido` | Filas 2–3: mismo NROAFI; APENOM, documento y CUIL distintos | Clave de identidad, alcance del número y tratamiento de coincidencias |
| `referencia_presente` | Fila 3 referencia textualmente NROAFI de fila 2, terminado en AAA | Significado de NROREF y vínculo familiar |
| `referencia_ausente` | Fila 2 tiene referencia no presente en el archivo | Búsqueda en padrón previo, revisión o rechazo; no inferir inexistencia global |
| `referencia_no_aaa` | Referencia presente a un número terminado en ZZZ | Si es admisible y qué significa; no convertirlo automáticamente en titular |
| `cuil_invalido` | Documento coincide con el cuerpo del CUIL; sólo el dígito verificador está alterado | Severidad, corrección y procedimiento operativo |
| `documento_discordante` | Checksum correcto, pero cuerpo documental distinto de NRODOC | Fuente de identidad autoritativa y resolución de discrepancias |
| `filas_vacias` | Cinco filas físicas: Excel 2, 4 y 6 vacías; Excel 3 y 5 con datos; exclusión comprobada con lector real | No requiere definir negocio para contar vacías |
| `tipos_mixtos` | NROAFI texto `000185`, entero 185 y decimal 185.5; documentos texto, entero y booleano; fechas nativa, texto ISO e inválida | Conversiones permitidas y severidades; no normalizar en la fixture |
| `baja_repetida` | `01_baja` y `02_repeticion` tienen exactamente la misma fila | Idempotencia, clave de movimiento y efecto sobre historial/derechos |
| `posible_reingreso` | Primer archivo con baja 2026-06-30; segundo con misma identidad, ingreso 2026-08-01 y baja vacía | Si es reingreso, corrección o nuevo período; ninguna reactivación inferida |
| `vencimiento_lejano` | FECVTO = 2099-12-31 | Centinela, vigencia real u otro significado; no fijar umbral |
| `baja_anterior_ingreso` | FECBAJ = 2025-12-31, menor que FECING = 2026-01-01 | Rechazo, advertencia o interpretación histórica |
| `lote_parcial` | Tres personas: control estructural, CUIL inválido coincidente con documento y fechas conflictivas | Aplicación parcial frente a atomicidad, revisión, reintentos y resumen |
| `referencia_ambigua` | Dos personas distintas comparten NROAFI; una tercera usa ese valor en NROREF | Clave familiar inequívoca; no elegir la primera coincidencia |
| `fila_repetida` | Dos filas idénticas en un mismo archivo | No confundir duplicado técnico con persona repetida o movimiento ya aplicado |
| `codigos_sin_homologar` | NUMERO `000042` y códigos explícitamente ficticios en TIPO, TIPODOC, CODPAR, MOTIVO e INCAPA | Diccionario, equivalencias, obligatoriedad y severidad |
| `contactos_ausentes` | Misma identidad control, domicilio y contactos vacíos | No inventar valores ni exigir completitud sin una regla aprobada |
| `texto_literal` | NROAFI con espacios, ceros y Ñ; NUMERO con ceros y NROREF con Unicode | Normalización permitida y validez del identificador |
| `fuentes_discordantes` | Dos archivos con misma identidad y FECING; difieren en plan y presencia de baja | Fecha de corte, foto/movimientos, corrección y fuente prevalente; no asumir que el segundo gana |

El lote parcial mezcla calidades de entrada; no acredita que alguna fila sea
aplicable. FECBAJ y FECVTO no provocan bajas ni restricciones en estas fixtures.

## Evidencia de esta entrega

Comando focalizado indicado arriba: **19 pruebas aprobadas** el 2026-10-20
(17 del generador y 2 de contrato con el lector real).
Sin Django, DB, Docker ni suite completa. Las pruebas de serialización usan
memoria y la exportación usa una carpeta temporal eliminada al terminar.
No se versionan binarios. El servidor de descargas para prueba manual es
independiente de esas pruebas y no aplica datos.

Revisión: se reprodujo la pérdida de filas vacías finales en XLSX; se corrigió
con formato en una celda vacía, sin cambiar valores. Se agregó cobertura de
vacías finales, lotes completamente vacíos y exportación sin sobrescritura.
La revisión estática de calidad y especificación no encontró otros bloqueantes.

| Criterio del tramo autorizado | Evidencia |
|---|---|
| 39 columnas en orden y catálogo completo | `test_esquema_exacto_y_cobertura` |
| Repetibilidad y aislamiento de cambios accidentales | `test_determinismo_e_inmutabilidad` |
| Identidades marcadas y contactos no operativos | `test_identidades_marcadas_y_sin_contactos_operativos`; procedencia revisable en `_persona` |
| Número compartido y referencias excepcionales | `test_numero_compartido_con_personas_distintas`, `test_referencias` |
| Checksum inválido frente a discrepancia documental | `test_checksum_y_discrepancia_son_estimulos_distintos` |
| Vacías y tipos preservados | `test_vacias_y_tipos_sin_normalizacion` |
| Baja repetida y posible reingreso | `test_secuencias_entre_archivos` |
| Fechas conflictivas y mezcla parcial | `test_fechas_y_lote_parcial` |
| Dos hojas y todos los lotes XLSX | `test_xlsx_ambas_hojas_todos_los_casos`: 23 lotes × 2 hojas |
| Errores de uso y texto literal | `test_exportador_rechaza_hoja_y_ancho_incorrectos`, `test_texto_literal_no_formula` |
| Vacías finales, lote de sólo vacías y lote sin filas | `test_xlsx_ambas_hojas_todos_los_casos`, `test_xlsx_solo_filas_vacias_y_lote_sin_filas` |
| Paquete manual de 46 XLSX y manifiesto sin sobrescritura, hashes y coordenadas comprobados contra los archivos leídos | `test_exportacion_temporal_completa_sin_sobrescritura` |
| Referencia ambigua frente a duplicación exacta | `test_referencia_ambigua_no_equivale_a_fila_duplicada` |
| Códigos opacos, contactos vacíos, ceros, espacios y Unicode | `test_codigos_contactos_y_texto_sin_inferencias` y round-trip XLSX |
| Fuentes discordantes sin precedencia ni reingreso inferidos | `test_fuentes_discordantes_no_sugieren_orden_temporal` |
| Manifiesto, coordenadas y celdas frente al lector real en ambas hojas | `ContratoLectorOSTELTests.test_manifiesto_y_celdas_de_los_46_archivos_con_lector_real` |
| Relectura independiente de bajas/reingreso/fuentes discordantes | `ContratoLectorOSTELTests.test_lecturas_independientes_sin_consolidar_movimientos` |

Las pruebas del generador verifican la construcción; las dos de contrato
comprueban los conteos y celdas del lector, no aplicación de movimientos
ni aceptación funcional. La prueba de marcas ficticias no demuestra
por sí sola procedencia: ésta se sustenta en la construcción local sin entradas.

## Qué bloquea el mensaje enviado a OSTEL

Fuente: mensaje aportado por el usuario en esta sesión. No hay respuesta de
OSTEL incorporada. Se reutiliza este documento como registro de pendientes,
sin crear un tracker paralelo. La implementación de #180 quedó entregada por
su agente el 20/10/2026 y no se modifica aquí. Se consume su contrato publicado
en [la entrega de #180](../../plans/2026-10-20-ostel-prevalidacion.md#integración-web-alcance-ampliado-y-contrato-con-185).

| Punto enviado | Preparado sin respuesta | Qué no debe implementarse por inferencia |
|---|---|---|
| 1. Diccionario de columnas/códigos | Esquema literal, valores opacos, ceros y tipos preservados | Mapear NUMERO/NROAFI/NROREF, regímenes, planes, parentesco, incapacidad o motivos |
| 2. Identificación y grupo familiar | Número compartido, documentos discordantes, referencias presente/ausente/no AAA/ambigua | Clave de persona, fusión de identidades, titularidad o vinculación familiar |
| 3. Significado de fechas | Fechas nativas/textuales, baja anterior y vencimiento lejano | Inicio/fin de cobertura, centinelas y rechazo de fechas por regla de negocio |
| 4. Alcance/corte de archivos | Baja repetida, posible reingreso y fuentes discordantes reproducibles | Asumir fotografía/movimientos, fecha de corte, prevalencia, reactivación o borrado de ausentes |
| 5. Estados y primera entrega | Separación explícita entre entrada técnica y aplicación | Traducir estados a derechos, restringir cobertura o otorgar facultades para autorizar cambios |

Los datos agregados del mensaje (por ejemplo, diez coincidencias entre fuentes)
no se reconstruyen ni se derivan a identidades sintéticas. Cada caso es inventado
desde cero y sólo reproduce la clase de problema.

Los temas no bloqueantes para esta preparación —pantallas/filtros/reportes,
legajo/adjuntos, credenciales, completitud de contactos, frecuencia/responsable
e integraciones— siguen abiertos para etapas posteriores. No son autorización
para añadir UI, almacenamiento, emisores o conexiones externas ahora.

## Continuación tras finalizar el agente de #180

Se monitorizó su terminal mediante Orca hasta observar su informe final,
sin interrumpirlo ni editar sus archivos. Skills `orchestration` y `orca-cli`
permitieron comprobar la entrega antes de continuar.

**Ejecutado en esta sesión de #185:** generación, conservación XLSX, manifiesto
y pruebas directas contra `prevalidar_ostel`, sin copia del lector ni mocks
de sus resultados. Lector versionado en `c6e90ad`, escenarios ampliados en
`6cf71dd`. El mock usado en exportación sólo redirige la carpeta temporal.

El ensayo técnico queda concretado así:

1. Fijar revisión del generador y del lector; generar un paquete nuevo y conservar
   su manifiesto. Una carpeta descargada antes puede contener sólo 14 escenarios.
2. Pasar cada XLSX por el lector sin normalizar previamente sus valores
   (ejecutado para los 46 archivos).
3. Comparar hoja, orden/encabezados y coordenadas de filas no vacías con el
   manifiesto. Comparar valores y tipos con el formato de salida real del lector;
   no asumir que devolverá fechas Python o celdas de openpyxl.
   Se verificaron textos, números XML, booleanos y serial/formato de fechas.
4. Distinguir repetición exacta (`fila_repetida`) de número compartido y referencia
   ambigua: ningún conteo técnico debe convertirse en deduplicación de personas.
5. Comprobar que baja repetida y fuentes discordantes se leen como archivos
   independientes. No exigir consolidación ni cambio de estado en la prevalidación.
6. Localizar diferencias por caso/hoja/fila/columna mediante subtests, y
   dejar interpretación y aplicación pendientes. No exigir al lector técnico
   que rechace códigos, checksum, referencias o fechas por reglas no acordadas.

Resultado: no se observaron diferencias; sólo `fila_repetida` produjo una anomalía,
fila 3 duplicada de fila 2, sin eliminarla. Los estímulos de negocio permanecen
sin interpretación. Las secuencias de baja repetida, posible reingreso y fuentes
discordantes se leen independientemente; releer el primer archivo devuelve el
mismo resultado. Esto no demuestra idempotencia de movimientos persistidos.

**Evidencia reportada por el agente #180, no reejecutada aquí:** 27 pruebas
(20 de lector y 7 de API), cargas de los 46 archivos mediante navegador/API,
cinco casos adicionales, permisos de carga y ausencia de altas de afiliados/lotes
en SQLite aislada. Se inspeccionaron sus pruebas y la documentación; los registros
y capturas locales están referenciados en su entrega. La API sí registra eventos
de auditoría: “no aplica padrón” no significa “no escribe nada”.

La UI entregada está en `http://127.0.0.1:5189/financiadores/padron`,
acción **Revisar Excel OSTEL**; su disponibilidad depende de los procesos locales.
Los accesos y el reinicio están documentados por #180. No se copiaron ni leyeron
contraseñas en esta sesión. Esta UI es la revisión técnica, no el importador.

Pruebas hostiles y de límites del lector son responsabilidad de #180; no se
duplican aquí. Persistencia de movimientos, concurrencia de escrituras,
permisos del circuito integral y comparación tabla/exportación siguen pendientes;
su aprobación no se deduce de la prevalidación. No se ejecutaron DB, navegador,
suite completa, CI ni deploy en esta continuación de #185.

Al recibir respuestas, completar en este documento para cada punto: respuesta
textual/referencia, fecha, responsable OSTEL, regla acordada, escenarios afectados,
resultado esperado aprobado y dudas restantes. Después vincular implementación,
evidencia observada, versión probada y aceptación humana. No marcar como
aceptado un resultado esperado que sólo haya propuesto el agente.

## Validación integral todavía no ejecutada

Dependencias: #180/#181, circuitos de lotes y bajas, vista operativa, decisiones
de #142/#143 y aceptación de OSTEL. No se simula que esos contratos existan.

Cuando estén acordados, usar los escenarios como entradas y registrar:

1. **Prevalidación:** contrato técnico de los 46 archivos verificado directamente
   contra #180; API y UI reportadas por su responsable. Pendiente la aceptación
   manual del usuario y OSTEL, sin convertir la lectura en autorización de carga.
2. **Mapeo:** equivalencias y obligatoriedad aprobadas por OSTEL; clasificación
   explícita de cada anomalía sin atribuir derechos por inferencia.
3. **Persistencia/importación:** comparar antes/después, filas aplicadas,
   rechazadas y pendientes, trazas e historial; probar repetición, carga parcial
   y errores intermedios según la atomicidad que se apruebe.
4. **Concurrencia:** dos cargas/correcciones sobre la misma identidad; demostrar
   que no hay duplicación ni pérdida de actualizaciones.
5. **Permisos/aislamiento:** roles autorizados y denegados, financiadores
   distintos y ausencia de exposición en reportes/logs.
6. **Tabla/exportación:** mismos filtros, identidad, fechas, cantidades y estados
   después de aplicar movimientos; verificar las diferencias autorizadas.
7. **OSTEL:** recorrido con responsable humano, resultado observado y decisión
   explícita sobre cada expectativa. Registrar desacuerdos y pendientes.

Salvo la prevalidación descrita, esos puntos no se ejecutaron: requieren contratos y circuitos disponibles,
definiciones humanas y autorización de entornos fuera del alcance actual.
Tampoco hay evidencia de capacidad con volúmenes reales ni de seguridad de
archivos hostiles; corresponden a pruebas específicas del lector y operación.

## Registro histórico de aceptación del generador

| Elemento | Estado |
|---|---|
| Entrega técnica del generador y pruebas | Verificada localmente en el alcance descrito |
| Contrato generador → lector #180 | 46 archivos verificados; 19 pruebas propias aprobadas |
| API/UI de prevalidación | Evidencia del agente #180 inspeccionada; no reejecutada aquí |
| Reglas de identidad, familia, fechas y movimientos | Pendientes de OSTEL |
| Persistencia, concurrencia, permisos, tabla/exportación | No ejecutados en esta entrega |
| Responsable humano, fecha, versión y escenarios aceptados | Sin registrar |
| Comprensión y aceptación humana | No demostradas; no inferidas por pruebas unitarias |
| Circuito integral #185 | No resuelto |

Para la revisión humana, leer `generar_escenarios`, `_persona` y la tabla de
expectativas. Proponer al menos dos fallos plausibles del circuito y contrastarlos
con evidencia antes de recomendar su incorporación. Ejemplos de riesgos aún
abiertos: fusionar personas por NROAFI y reactivar derechos al ver una baja vacía.
El generador contiene estímulos para ambos, pero aún no existe aquí una prueba
de protección del circuito. Mantener como deuda pendiente la homologación de
reglas, los resultados observados y el entendimiento humano; no crear otro tracker.


## Respuestas OSTEL recibidas el 20/10/2026 y avance autorizado

Fuente: respuestas 1–4 y 5 reproducidas por el usuario en la continuación
conjunta #180/#185. Fecha de recepción en esta sesión: 20/10/2026. Emisor:
OSTEL según el usuario; persona responsable y fecha original no informadas.
No se atribuye aprobación de una implementación a estas respuestas.

### Matriz de reglas, evidencia y aceptación pendiente

| Referencia | Regla informada | Escenario / resultado observable preparado | Pendiente |
|---|---|---|---|
| 1–2, identidad | NUMERO identifica individualmente; CUIL identifica a la persona; NROAFI puede compartirse | `identidad_individual`: dos personas conservan CUIL y NUMERO distintos con igual NROAFI | Política de identidad ante datos faltantes, CUIL cambiado o contradicciones; no fusionar por una sola coincidencia |
| 1–2, contradicciones | No se informó precedencia entre CUIL y NUMERO discordantes | `cuil_distinto_mismo_numero`, `numero_distinto_mismo_cuil`: preservar ambas filas | Resolución humana y severidad; el lector técnico no detecta conflictos de identidad |
| 1, categoría | A = activo; P = pasivo; no representan cobertura vigente/en trámite/baja | `categorias_sin_cobertura`: A con FECBAJ y P sin FECBAJ, ambos CC | No derivar derecho ni estado de cobertura de TIPO |
| 1, plan | Plan CC unificado; modalidades con/sin coseguro; sin afiliados sin coseguro actualmente según OSTEL | Conservar CC sin asignar modalidad | Campo/código que distingue modalidad y reglas aplicables |
| 1, otros campos | CODEMP empresa/entidad; INCAPA indicador S/N | Conservar valores; `cambio_empresa` cambia exclusivamente CODEMP | Catálogo de empresas, TIPODOC, MOTIVO y significado de NROREF |
| 2, familia | CUILTIT referencia CUIL del titular; titular CUIL = CUILTIT; CODPAR expresa relación | `parentescos_confirmados`: 56 códigos de extremos de rangos, conservados literalmente | CUILTIT ausente en las 39 columnas; no usar NROREF ni NROAFI como sustituto |
| 3, fechas | FECING ingreso; FECBAJ baja; FECVTO vencimiento de una condición, no necesariamente baja | Escenarios previos de fechas y posible reingreso siguen siendo entradas sin aplicación | Campo de vigencia efectiva, condición que vence, excepciones |
| 4, casos | Baja anterior puede pertenecer a otro período; coincidencia puede ser reingreso | `posible_reingreso`, `baja_anterior_ingreso`, `fuentes_discordantes` | Confirmación individual; no afirmar errores ni reingresos ciertos |
| 5, alta | Futuros Afiliados precede al padrón definitivo; cierre mensual; alta/cobertura primer día hábil siguiente | Criterio funcional documentado; sin conversión de fechas | Representación en exportación, calendario aplicable y relación exacta con FECING |
| 5, baja | Registro de fin de mes y proceso durante cierre | Preservar fechas originales | Inclusividad del último día y bajas fuera de fin de mes observadas |
| 5, movimientos | Alta nueva, alta temprana laboral, cambio de empresa, cambio laboral, baja y reingreso son distintos | `cambio_empresa`: misma identidad y fechas con empresa distinta; no crear alta | Campo/tipo de movimiento, fecha efectiva, prioridad de fuentes y correcciones |
| 1 y 5, categoría vs condición laboral | A/P expresa activo/pasivo; no se informó código para relación de dependencia/monotributo | `cambio_categoria`: sólo TIPO cambia; no se etiqueta como cambio laboral ni alta | Exportación del cambio laboral; no equiparar categoría y condición laboral |

Diccionario de parentescos informado, sin inferir familias ni validar elegibilidad:

| Códigos | Relación |
|---|---|
| AAA | Titular |
| CO1–CO2 / CC1–CC3 | Cónyuge / concubina-o |
| H01–H15 / HJ1–HJ6 | Hijo-a / hijastro-a |
| ME1–ME8 / IN1–IN5 | Mayor que estudia / hijo incapacitado |
| MD1–MD5 / MG1–MG6 | Mayor de 25 años con discapacidad / menor en guarda |
| PA1–PA2 / PP1–PP2 | Padre-madre / padres políticos |
| HE1–HE6 / TI1–TI3 | Hermano-a / tío-a |
| SO1–SO4 / AB1 / NI1–NI8 | Sobrino-a / abuelo-a / nieto-a |
| MF1–MF5 / OT1–OT5 | Miembro familiar / otros |
| XC1–XC2 / XQ1–XQ2 | Cónyuge adjunto / concubina-o adjunto |
| XH1–XH9 / XJ1–XJ6 | Hijo-a adjunto / hijastro-a adjunto |
| XI1–XI6 / XM1–XM6 | Incapacitado adjunto / estudiante adjunto |
| XG1–XG6 / XE1–XE6 | Menor en guarda adjunto / hermano-a adjunto |
| XP1–XP2 / XN1 / XO1 | Padre-madre adjunto / nieto-a adjunto / otros adjuntos |
| XD1–XD2 | Mayor de 25 años con discapacidad adjunto |

### Evidencia real separada de fixtures

En lectura local de los cinco archivos aportados por el usuario se reprodujeron
10 coincidencias por CUIL, también coincidentes por NUMERO. En todas, FECING en
el archivo de octubre es posterior a FECBAJ en la fuente de bajas. Se encontraron
80 filas con FECBAJ anterior a FECING y 330 con FECVTO desde 2040 (corte exploratorio,
no regla OSTEL), con fechas hasta 2047. Son observaciones, no errores confirmados.
El informe nominal quedó fuera del repositorio, en Downloads del usuario;
ningún identificador real se incorporó a fixtures, tests o documentación.
No se confirmó el significado de ausencias ni la precedencia entre archivos.

### Alcance implementado mientras se espera

Se agregaron siete escenarios independientes, sin reemplazar los veinte técnicos
anteriores. Los ejemplos antiguos de NROREF y sufijos AAA se conservan como
estímulos opacos: **no representan la regla familiar confirmada**. Los códigos
ficticios de las fixtures técnicas no se convirtieron globalmente en códigos válidos.
El escenario de parentescos cubre extremos de cada rango, no cada código interior.
Las fechas se preservan; no se introduce calendario laboral ni cálculo de derechos.

La ayuda del formato explica identidad, categoría, vencimiento y ausencia de
CUILTIT. No se incorporó un motor de revisión administrativa ni comparación entre
archivos a la UI: requieren decisiones de identidad, severidad y presentación.
El lector/API siguen siendo técnicos; cero anomalías no significa aprobación
administrativa. No cambian plantilla, esquema, importador, permisos ni persistencia.

Aceptación principal de este tramo: preservar hechos confirmados y contradicciones
en fixtures y documentación sin convertirlos en movimientos aplicados. Las pruebas
comprueban identidad y fechas de los nuevos escenarios y su lectura literal en
ambas hojas, además de la relectura independiente de secuencias. No demuestran
idempotencia persistida, concurrencia, aplicación ni vigencia real de cobertura.


### Validación local de esta continuación

- Desde `backend`: `python -B -m unittest apps.financiadores.tests_ostel_scenarios apps.financiadores.test_ostel_prevalidacion -q`: 42 pruebas aprobadas. Incluye generación temporal y contraste de los 64 XLSX con el lector real, sin Django/DB.
- Desde `frontend`: `node --test src/pages/financiadores/formatosImportacion.test.js`: 6 pruebas aprobadas. Verifican preferencias/registro; no prueban visualmente el nuevo texto de ayuda.
- `git diff --check`: sin errores de whitespace.
- No ejecutados: API con DB, navegador, suite completa, build, PostgreSQL ni CI. No se cambiaron contratos de API o persistencia; la ayuda queda pendiente de comprobación visual.
- Sin dependencias nuevas, servidores, importaciones de datos reales, commits, push ni cambios externos. Revisión técnica completa y aceptación humana pendientes; no se declara comprensión del usuario validada ni se recomienda incorporación.

Skills: `brainstorming` se usó para delimitar el alcance autorizado y reutilizar
el generador/flujo existente, evitando convertir respuestas parciales en reglas
operativas. No se creó otro plan/tracker ni se reabrieron decisiones de UI.


## Decisiones del usuario y revisión del 21/10/2026

### Decisiones aprobadas antes de implementar el circuito operativo

- Primera entrega: padrón administrativo. Derechos de cobertura fuera de alcance,
  pendientes de reglas de OSTEL. Documentado también en el módulo del lector.
- Aplicar filas válidas y conservar problemáticas gestionables; no rechazar todo
  el lote por conflictos individuales. Identidades contradictorias requieren
  revisión humana, sin fusión forzada.
- UI solicitada: resumen de válidas/aplicadas/pendientes, detalle del conflicto,
  corrección explícita y revalidación antes de confirmar. Flujo futuro dentro de
  Importar Excel y el historial común; no crear botón o circuito por financiador.
- Responsable funcional elegido tras inspección: operador del financiador; admin
  como respaldo, auditor sólo lectura. `requerir_financiador(escritura=True)` y la
  confirmación actual ya permiten operador/admin. No se cambiaron permisos.
  El acceso de plataforma del guard general existe y se trata por separado en
  #170: esta asignación no significa que hoy sólo esos dos roles puedan escribir.
- El usuario delegó revisión técnica completa; comprobación visual posterior.

### Acoplamiento que exige decisión de arquitectura

`importaciones.aplicar_importacion` llama a `registrar_afiliado`, escribiendo
`numero`, `documento`, `nombre`, `plan` y `desde`. `cobertura.seleccionar_afiliacion`
verifica `finalizado_en`, `desde` y plan, y puede crear una selección verificada;
`administrativa`, `acceso`, `autorizaciones` y `legado` usan condiciones similares.
No existe actualmente una separación explícita de registro administrativo y
habilitación prestacional. Un plan vacío tampoco bloquea selección.

Recomendación del agente, pendiente de decisión del usuario: separar habilitación
prestacional en el modelo y revisar todos los consumidores, con migración y
compatibilidad de afiliaciones existentes. Alternativa: mantener preparación y
subsanación en lotes sin aplicar al padrón definitivo. No se introdujo ninguno
de estos cambios mientras se espera la elección. Debe precisarse también cómo
conservar NUMERO interno y NROAFI compartido: Afiliado sólo tiene un campo numero.

El importador existente ya aplica válidas por fila y conserva errores, pero la
subsanación del padrón requiere corregir y recargar archivo; no tiene editor de
conflictos. No presentar esas capacidades como el nuevo circuito OSTEL terminado.

### Puntos OSTEL: qué puede resolverse y qué permanece

1. CUILTIT sigue pendiente: falta en las 39 columnas; sin él no se vincula familia.
2. Ya no se espera respuesta de OSTEL para elegir política operativa. Propuesta
   pendiente de confirmación del usuario: octubre como base elegida explícitamente;
   bajas como evidencia, ausencias sin efecto y ninguna sobrescritura automática
   entre fuentes con conflicto o antigüedad incierta. No es semántica confirmada
   por OSTEL ni se implementó aún.
3. Respuesta parcial: podemos comparar CODEMP, TIPO, identidad y fechas para
   señalar cambios. No podemos afirmar alta nueva frente a historia incompleta,
   reingreso definitivo, alta ARCA ni cambio laboral: no hay tipo de movimiento
   ni fecha efectiva explícitos para todos ellos. Mantener esa pregunta por su
   impacto en la clasificación automática, sin impedir la revisión administrativa.
4. No esperar reglas de cobertura para diseñar el padrón administrativo. Conservar
   fechas informadas sin calcular días hábiles, extender cobertura ni aplicar
   bajas/reingresos automáticos. Las reglas prestacionales quedan fuera de esta
   entrega, no se consideran resueltas.
5. Relectura local de cinco Excel, sin importación ni escritura sobre fuentes:
   TIPODOC contiene códigos 1–5; MOTIVO contiene códigos administrativos sin
   equivalencias proporcionadas; NROREF no adquiere significado por coincidencia.
   **Discrepancia:** octubre tiene 2.224 A y 3.530 P, no todos A. COD_PLAN contiene
   BLANCO, GAMA, DELTA+, BASICO, KRONO+, OTROS, GALENO, SANCOR, QUANT+, SWISS,
   ENSAL y MEDICU, sin CC. Confirmar si el archivo es anterior al cambio, si se
   refiere a otra exportación, y cómo traducir esos valores al esquema actual.
   No recodificar a CC ni usar TIPO para inferir cobertura o modalidad de coseguro.
6. FECVTO sigue pendiente: se conserva como dato, sin transformarlo en baja ni
   caducidad de cobertura; falta saber qué condición vence.
7. Casos individuales siguen pendientes: los diez cruces son compatibles con
   reingreso, pero no lo prueban. Las fechas inusuales requieren explicación.

### Revisión del avance previo

Skill `code-review`: revisión estática por dos ejes independientes (estándares y
especificación) del diff local contra HEAD 25849b7. Ambos sin hallazgos bloqueantes
para el tramo de fixtures/documentación/ayuda. Las pruebas de identidad comprueban
estímulos, no bloqueo operativo ni integridad persistida. Aplicación parcial OSTEL,
editor de conflictos y separación de cobertura siguen pendientes. La inspección
actual encontró el acoplamiento prestacional descrito arriba; no se recomienda
incorporar una importación administrativa usando directamente el escritor actual.
No se reejecutaron tests en esta revisión: los cambios de este turno son textos y
documentación. No hay validación visual, PostgreSQL, migración, CI ni deploy.


### Base de parametrización no operativa — T2a (02/11/2026)

`backend/apps/financiadores/derechos_borrador.py` permite construir descriptores
inmutables con código, versión positiva, fuente explícita, financiador, régimen,
plan opcional e intervalo técnico `[desde, hasta)`. `hasta=None` no tiene fin.
No se modifica `ReglaCobertura`, el padrón ni los selectores de afiliación.

`previsualizar_borradores` recibe descriptores y contexto explícito de consulta;
devuelve coincidencias ordenadas y `conflicto` si hay más de una, incluso si
una es general y otra específica del plan. No elige precedencia ni la versión
más alta. Plan vacío en la regla abarca todos los planes; plan vacío en la
consulta sólo coincide con reglas generales. Duplicados también son conflicto.
El resultado conserva cada descriptor completo (versión/fuente/ámbito/vigencia).
El mismo descriptor puede consultarse en fechas anteriores sin alterarlo.

Esta consulta **no es una evaluación de derechos ni una vista de impacto sobre
personas**. El régimen es una clave literal, no un catálogo alternativo; no se
comprueba existencia del financiador, régimen o plan ni pertenencia del plan en
DB. Los identificadores deben ser resueltos por una futura integración protegida.
El filtro de ámbito no sustituye permisos. La fuente es referencia informativa,
no prueba de vigencia normativa. No hay persistencia ni garantía de unicidad de
versiones entre ejecuciones. No hay API, pantalla, activación ni reglas ejecutables.
No se admiten parámetros arbitrarios (por ejemplo `activar`, scripts o expresiones).

Pendiente: plazos/causales/acciones controlados con ejemplos aprobados, persistencia
versionada, auditoría, autorización, historial de decisiones, previsualización de
impacto real y aprobación antes de activar. Esas garantías no serán parámetros
desactivables. No conectar el borrador al motor actual mientras falte ese contrato.
Los límites del intervalo son técnicos para consultar borradores, no fechas de
corte asistencial ni interpretación de FECVTO. OSTEL ya recibió la consulta normativa.

Verificación pura (sin Django, DB, servidores ni datos reales):

```powershell
python -B -m unittest backend.apps.financiadores.tests_derechos_borrador backend.apps.financiadores.tests_ostel_scenarios -v
```

Rollback de T2a: retirar el módulo nuevo, su prueba y esta sección; los motores
y datos anteriores no dependen de ellos. Pruebas locales no acreditan CI,
despliegue ni aceptación de las reglas por OSTEL.


### Comparación de propuestas conservando historia — T2b (02/11/2026)

`comparar_borradores` en `propuesta_derechos.py` recibe el historial y la
propuesta completa en memoria, junto al contexto de consulta de T2a. Devuelve
las versiones nuevas y las coincidencias antes/después, sin aprobar ni escribir.

- Cada clave `(financiador, régimen, plan, código, versión)` debe ser única.
- La propuesta debe conservar todas las versiones previas con datos idénticos.
  Cambiar fuente, fechas o ámbito exige una nueva versión, nunca sobrescribir.
- Una versión nueva debe superar el máximo anterior de su ámbito/código;
  no se exige consecutividad. Este contador no afirma vigencia normativa.
- Todas las entradas deben corresponder al financiador explícito. Se valida
  consistencia de entradas, no sesión, permisos ni pertenencia real del plan.
- Superposiciones siguen visibles como conflicto; no se recorta una versión
  abierta ni se elige una ganadora. La misma propuesta es determinista sin
  importar el orden de sus entradas. Una propuesta idéntica no añade versiones.

La comprobación protege sólo las dos instantáneas suministradas: el llamador
podría omitir historia en ambas y la función no tiene cómo detectarlo. No
sustituye historial persistido, auditoría, bloqueo de concurrencia, firma de
aprobación ni vista de impacto sobre personas. No hay parámetros de plazos,
causales o acciones médicas, ni cambios de derechos. Una futura activación
requiere el contrato pendiente y controles operativos, no sólo esta validación.

Runner puro adicional: `python -B -m unittest backend.apps.financiadores.tests_propuesta_derechos -v`.
Regresión: ejecutar también `tests_derechos_borrador` y `tests_ostel_scenarios`.
Rollback: retirar `propuesta_derechos.py`, `tests_propuesta_derechos.py` y esta
sección; T2a y los motores anteriores permanecen intactos.


### Persistencia de borradores, sin activación — T2c (02/11/2026)

`borradores_derechos.guardar_borradores` conserva una propuesta completa mediante
`BorradorReglaDerechos` (migración aditiva 0018), con autor, fecha y motivo por
versión. Reutiliza el comparador puro, el guard de financiador y `auditar`.
`consultar_borradores` devuelve los descriptores persistidos del financiador.
No existe endpoint, pantalla, registro admin ni conexión con el motor de derechos.

La escritura requiere admin del financiador bajo el guard de configuración
existente; operador/auditor sólo consultan con membresía habilitada. No se crea
una concesión ni se modifica el helper de permisos. Se revalida el guard después
de tomar el lock del financiador. Planes existentes y del mismo financiador se
bloquean por PK; el régimen reutiliza el catálogo de Afiliado. Un plan inactivo
puede ser referenciado como borrador: no se habilita ninguna prestación por eso.

La transacción recarga historia real, rechaza omisiones/reescrituras, valida la
propuesta e inserta sólo versiones nuevas, cada una con evento de auditoría.
Fallo de auditoría revierte todas las inserciones de esa propuesta. Reintento
idéntico no duplica filas/eventos; propuestas concurrentes contradictorias no
pueden reemplazar la versión ganadora. El lock por financiador simplifica el
orden a cambio de serializar propuestas distintas del mismo financiador.

El servicio no ofrece edición ni borrado. Las constraints cubren identidad de
versión (incluso plan nulo), contador positivo e intervalo válido; no constituyen
un almacenamiento inmutable contra SQL u ORM privilegiados. No hay backfill ni
cambio de estado de afiliados. El motivo no debe contener identificadores
personales, secretos ni datos clínicos. Fuente informada no acredita norma vigente.

Pruebas seriales sólo en PostgreSQL descartable autorizado y con settings
`config.settings_financiadores_postgres_test`: `apps.financiadores.test_borradores_derechos`,
con regresiones `test_cobertura` y `test_habilitacion_cobertura`. Sin datos reales.
No se acredita aceptación normativa, CI, despliegue ni activación mediante tests.
Antes de activar faltan reglas/ejemplos aprobados, impacto real y aprobación
explícita; este almacenamiento no sustituye esos pasos ni los vuelve opcionales.


### API administrativa de borradores — T2d (02/11/2026)

`/api/financiadores/{id}/borradores-derechos/` expone sólo GET y POST:
GET consulta descriptores completos del financiador; POST guarda una propuesta
completa mediante el servicio T2c, sin aprobar ni activar derechos. La URL fija
el financiador; no se acepta un financiador embebido ni campos arbitrarios.
Admin configura borradores; operador/auditor consultan según guard existente.
Sin sesión: 401; sin membresía visible: 404; escritura no autorizada: 403.

POST requiere `propuesta`, `motivo`, `regimen`, `plan_id` (entero o null), `fecha`.
Cada descriptor contiene `codigo`, `version`, `fuente`, `regimen`, `plan_id`,
`desde`, `hasta` (opcional/null). Fechas ISO `YYYY-MM-DD`; fuente explícita,
versión positiva y catálogo de régimen actual. No se admiten `activar`,
`aprobado`, expresiones, parámetros libres ni campos desconocidos, incluso
anidados. Un plan debe existir y pertenecer al financiador de la URL.

Respuesta 200: `nuevas`, `antes` y `despues`; cada vista tiene `coincidencias`
y `conflicto`. GET devuelve `{"borradores": [...]}` sin paginar porque el
comparador requiere la historia completa, no una página parcial. Un reintento
idéntico devuelve `nuevas=[]` sin duplicar auditoría. Historia incompleta,
reescritura o entradas inválidas: 400 sin cambios; consultar nuevamente antes
de reconstruir/reintentar la propuesta. No hay actualización/borrado por ID.

Antes/después es una consulta técnica de borradores **tras guardar**, no una
aprobación, previsualización de impacto en personas ni activación. No se persiste
una política médica nueva por introducir un descriptor. La auditoría de cada
versión sigue en EventoCobertura; esta ruta no expone un nuevo visor de eventos.
APIClient ejerce rutas HTTP reales con PostgreSQL ficticio, no navegador ni UI.
OpenAPI identifica los serializers de entrada/salida y ambos métodos.

Runner: `apps.financiadores.test_borradores_api` con settings PostgreSQL de L24;
regresiones de servicios/integridad/cobertura. Rollback: retirar `borradores_api`,
su mixin/import de FinanciadorViewSet, tests y esta sección, conservando T2c.
T2c quedó sin revisión nativa por «autorizo»; esa decisión no alcanza a T2d.


### Pantalla administrativa de borradores — T2e (02/11/2026)

Menú del financiador → **Borradores de derechos**, separado de reglas vigentes.
Administración consulta el historial completo y registra una nueva versión con
código/versión/fuente/régimen/plan/intervalo técnico/motivo y fecha de consulta.
Operador/auditor sólo consultan. No hay edición, borrado, aprobación ni activación.
Cada versión muestra «No operativo»; guardar no cambia derechos ni valida norma.
La pantalla no expone autoría que el DTO de consulta todavía no ofrece.

Reutiliza tokens, componentes, catálogo REGIMENES, API y opciones de planes del
portal. Lista/formulario en escritorio, una columna móvil; controles etiquetados,
foco de teclado y fechas ISO sin transformación de zona horaria. Los intervalos
son técnicos: no representan fecha de corte prestacional. No introducir datos
clínicos, identificadores personales ni secretos en fuente/motivo.

Las consultas tienen clave usuario/financiador y el componente se reinicia al
cambiar de organización. No hay refetch de foco que sustituya silenciosamente
la historia mientras se prepara una versión. El guardado envía esa historia
completa y un descriptor nuevo al servicio existente, que decide la validez.
Botón y ref bloquean envíos simultáneos. Tras error/conflicto o respuesta perdida,
se exige «Volver a consultar» antes de otro intento; no se reintenta POST solo.
Una respuesta perdida puede haber confirmado la escritura: revisar la lista.

Pruebas reales: `frontend/playwright.borradores-real.config.js`, fixture propia
`e2e/fixtures/preparar_borradores_derechos.py`, `SALUD_BORRADORES_MANIFEST` sólo
ficticio en temporal externo. Requiere entorno loopback/API/PostgreSQL autorizado
ya iniciado; no ejecuta siembra general ni usa .env. Comando desde frontend:
`node node_modules/@playwright/test/cli.js test --config playwright.borradores-real.config.js`.
El caso de pérdida aborta la respuesta sólo después de un POST real confirmado;
es prueba de recuperación UI, no simulación de rollback del servidor.

Rollback: retirar sección/import/rama del portal, componente y spec/config/fixture
nuevos; conservar API T2d y versiones/auditoría existentes. T2d quedó sin revisión
nativa por autorización específica; no extiende la decisión a esta UI. Navegador
visible demuestra una fixture, no aceptación de negocio ni despliegue.


### Nombre del módulo y objetivo operativo — T2f (02/11/2026)

El nombre visible aprobado es **Reglas de derechos**; **Borrador** es el estado
de las versiones actuales, no del derecho de una persona. Se conservan la ruta
`/financiadores/borradores`, el endpoint `borradores-derechos` y los nombres
técnicos para no romper contratos; este cambio sólo modifica la presentación.
Todos los registros del modelo BorradorReglaDerechos son borradores por diseño;
no se agrega un selector que permita declararlos aprobados/vigentes desde la UI.

La base funciona para registrar/consultar versiones con ámbito, fechas, fuente,
autor y auditoría. **No es todavía el motor de decisión de derechos.** Faltan la
configuración de condiciones/acciones controladas, su evaluación determinista,
la aprobación/activación autorizadas y los casos de negocio validados por OSTEL.
Las garantías ya acordadas de aislamiento, historia y auditoría no se desactivan
como parámetros. No se declara el módulo terminado por guardar metadatos.

Para declarar una regla operativa, deberá haber ejemplos acordados antes/en/
después de sus límites, prueba de efectos autorizados y de rechazo sin efectos,
trazabilidad de versión/fuente, aprobación explícita y verificación integrada.
Un cambio de nombre o pruebas verdes de esta base no sustituyen esos requisitos.
El material normativo ya fue solicitado; este cambio no inventa valores ni activa
bajas, gracia o mora. La aceptación de negocio sigue separada de la validación técnica.


### Primer mecanismo ejecutable: umbral temporal — T2g (02/11/2026)

`backend/apps/financiadores/simulacion_plazo.py` ofrece `simular_plazo`: calcula
una fecha de referencia explícita más un número configurable de **días corridos**.
Devuelve la posición de la evaluación **antes / en / después** del límite. No
elige inclusividad prestacional ni traduce esa posición en habilitación o baja.
No usa reloj del sistema ni infiere referencias desde FECVTO, ausencia o inicio.

Reutiliza `previsualizar_borradores` para ámbito/vigencia técnica del descriptor.
Si no coincide, devuelve `sin_coincidencia`; si falta fecha de referencia o
identificador de evidencia, `requiere_evidencia`, ambos sin límite calculado.
Datos de tipo/rango inválidos se rechazan con ValueError, incluso con referencia
ausente. No hay expresiones, callbacks ni ejecución de reglas arbitrarias.

La salida inmutable contiene todos los insumos (descriptor/fuente/versión,
financiador/régimen/plan de consulta, plazo, fechas, referencia de evidencia) y
el resultado calculado, sin guardarlos en DB. La evidencia es una referencia
informada: no certifica que un documento sea válido o que un evento haya ocurrido.
Una referencia futura se compara literalmente, no acredita derechos anticipados.

Ejemplo **completamente ficticio**, ejecutable desde la raíz sin Django/DB:

```python
from datetime import date
from backend.apps.financiadores.derechos_borrador import BorradorDerechos
from backend.apps.financiadores.simulacion_plazo import simular_plazo
regla = BorradorDerechos("ficticia", 3, "Fuente ficticia", 10,
                         "dependencia", None, date(2029, 1, 1))
r = simular_plazo(regla, dias_corridos=7, financiador_id=10,
    regimen="dependencia", plan_id=None, fecha=date(2030, 1, 8),
    referencia=date(2030, 1, 1), evidencia="REF-FICTICIA")
# r.estado == "calculado", r.limite == date(2030, 1, 8), r.relacion == "en"
```

El plazo es explícito por simulación: aún no se persiste/versiona como parámetro
de una regla activa. Cero es admisible para comprobar coincidencia de fechas,
no un valor de negocio aprobado. No se convierte una mención normativa de meses
a una cantidad fija de días; otros calendarios requieren implementación expresa.
No se modifica el padrón, se activa una regla ni se emite una decisión de derechos.
La pantalla actual aún no llama a este mecanismo; no se presenta como recorrido
integrado ni como motor completo. Tampoco sustituye autenticación/aislamiento
operativo: el contexto de la función es suministrado por su llamador.

Runner: `python -B -m unittest backend.apps.financiadores.tests_simulacion_plazo -v`.
Regresiones puras: `tests_derechos_borrador`, `tests_propuesta_derechos` y
`tests_ostel_scenarios`. Rollback: retirar módulo/prueba y esta sección, sin
alterar servicios anteriores ni sus datos.


### Simulación desde una versión guardada — T2h (02/11/2026)

En **Reglas de derechos**, cada versión ofrece **Simular plazo**. El diálogo
recibe días corridos explícitos, fecha de evaluación y referencia/evidencia
opcionales. El servidor calcula con la fuente/metadatos de la versión guardada;
el cliente sólo selecciona su identidad. La respuesta muestra límite y posición
antes/en/después, o evidencia pendiente/sin coincidencia. Cambiar insumos borra
el resultado anterior; cerrar no guarda nada y devuelve el foco al disparador.

POST `/api/financiadores/{id}/borradores-derechos/simular-plazo/` es una consulta
con cuerpo JSON, **no una escritura**. Requiere membresía de lectura existente:
operador/auditor pueden simular, sin adquirir permiso para crear versiones.
Campos: `regla={codigo,version,regimen,plan_id}`, `dias_corridos`, `fecha`, y
`referencia`/`evidencia` opcionales/null. Datos de fuente, autor, financiador o
activación embebidos y demás campos desconocidos se rechazan. Regla inexistente
en ese financiador: 400; organización no visible: 404; sin sesión: 401.

La respuesta contiene todos los insumos y descriptor recuperado, estado,
`limite` y `relacion`. No modifica versiones, auditoría, afiliados ni derechos.
Ejemplo ficticio: referencia 2030-01-01 + 7 días → 2030-01-08; fecha evaluada
2030-01-08 queda **en** el límite. Cambiar a 9 días → 2030-01-10. No se decide
si ese día conserva/corta prestaciones. El plazo sigue siendo un insumo de
simulación, no un parámetro normativo activado o persistido en la versión.
La evidencia informada no certifica documentación ni ocurrencia del evento.

Pruebas reales: `test_simulacion_plazo_api` en PostgreSQL ficticio dedicado y
spec de borradores con administrador/auditor, móvil/teclado, cambio de insumos
sin resultado viejo y foco al cerrar; más regresiones anteriores. Sin nueva
migración, dependencias ni siembra general. OpenAPI documenta el POST de consulta.
Rollback: retirar mixin/import de simulación, módulo API, diálogo y acción UI,
pruebas nuevas/esta sección, conservando el mecanismo puro T2g y registros previos.

### Plazo guardado por versión — T2i (02/11/2026)

La administración puede guardar **Plazo en días corridos (opcional)** junto con
una nueva versión. Vacío significa sin configurar; cero es un valor explícito.
Cambiar el plazo exige otra versión: ni la simulación ni un reenvío pueden
sobrescribir la historia. Se reutilizan autorización, locks y auditoría existentes.

1. Abrir **Reglas de derechos** y registrar una versión con fuente, motivo y plazo
   ficticios. Guardar no aprueba ni activa derechos.
2. Recargar y abrir **Simular plazo**: **Usar plazo configurado** viene marcado
   únicamente si la versión tiene ese dato. El servidor recupera el valor guardado.
3. Desmarcarlo y probar otro número: el resultado identifica **alternativa simulada**.
   Al volver a consultar la versión, conserva su plazo original.

Contrato aditivo: `plazo_dias_corridos` es nullable y opcional en la propuesta.
Los descriptores sin plazo siguen omitiendo el campo en sus respuestas anteriores.
En el POST de simulación, omitir `dias_corridos` usa exclusivamente la configuración
guardada; si no existe, devuelve 400 sin asumir un valor. Enviarlo explícitamente
(incluso cero) calcula una alternativa; `null` explícito sigue siendo inválido.
La respuesta agrega `origen_plazo` (`configurado` o `simulado`) y conserva los
insumos, descriptor, estado y límite. No acepta expresiones ni acciones arbitrarias.

La migración aditiva `0019_borrador_plazo_dias` no asigna defaults ni rellena
versiones históricas: quedan NULL. Valida rango entero no negativo hasta el máximo
técnico representable por `date`; la suma también debe caber en ese rango. No es
un máximo de negocio ni se convierte una unidad normativa en días.
No se configura cuándo dar una baja, gracia o mora, no se valida evidencia y no
se escriben derechos. Es un parámetro funcional para simulación versionada,
no un motor operativo completo ni una política aprobada por OSTEL.

Verificación: pruebas puras, API real con PostgreSQL dedicado y migración desde0018;
registros anteriores idénticos salvo el nuevo NULL, rechazo sin escritura/auditoría,
versiones inmutables, cero explícito/configurado y recorrido real desktop/móvil/teclado.
Runner: los módulos `tests_derechos_borrador`, `tests_propuesta_derechos`,
`test_borradores_api`, `test_simulacion_plazo_api` y `test_borradores_plazo_migracion`;
frontend: `node node_modules/@playwright/test/cli.js test --config playwright.borradores-real.config.js`
con fixture ficticia dedicada. Resultados observados y estado de revisión: [L30](../../../odd/tasks/ostel-operacion-integral.md).
Rollback: retirar esta capacidad de UI/API/DTO y revertir0019 sólo tras conservar
los nuevos parámetros; una reversión de esquema los pierde. No revertir datos
históricos ni reactivar derechos como parte de ese procedimiento.

### Vista previa de propuesta sin guardar — T2j (02/11/2026)

**Previsualizar propuesta**, en Nueva versión, consulta qué versiones se agregarían
y las coincidencias antes/después para el régimen, plan y fecha indicados.
Muestra los conflictos sin seleccionar un ganador. Esta acción no guarda,
audita ni activa versiones, y no calcula personas o prestaciones afectadas.
Editar un campo o volver a consultar borra la vista; una respuesta pendiente
de otro financiador no se incorpora al formulario actual. El guardado continúa
como acción separada, incluida la vía anterior sin previsualización.

POST `/api/financiadores/{id}/borradores-derechos/previsualizar/` requiere
administración y reutiliza el mismo cuerpo estricto/resultado del POST de guardado:
`propuesta`, `motivo`, `regimen`, `plan_id`, `fecha` → `nuevas`, `antes`, `despues`.
Se compara con la historia real y se validan propiedad/existencia de todos los
planes, motivo y versiones inmutables. Lectores no administradores:403;
organización no visible:404; sin sesión:401. No admite campos arbitrarios.

La consulta no bloquea ni reserva datos: puede quedar obsoleta si otro
administrador agrega una versión. Guardar recalcula y valida bajo los locks
existentes (financiador, revalidación de permiso, planes ordenados) y puede rechazar
una propuesta vieja. No sustituye aprobación de activación ni validación OSTEL.
El helper compartido evita divergencia de motivos/planes/comparación;
no se llama al guardado en modo dry-run ni se revierten escrituras para previsualizar.

Verificación: API pública (sin mutaciones, permisos, planes ajenos, conflictos,
preview→guardar y rechazo de historia obsoleta), regresiones de guardado/concurrencia
y recorridos reales desktop/móvil/teclado, edición/recarga y respuesta tardía.
Runners: `test_borradores_api`, `test_borradores_derechos`, `test_borradores_integridad`
y el spec real de borradores. Resultados y límites en L31 del documento de tareas.
Rollback: retirar endpoint/acción/vista y sus pruebas; restaurar validación inline
del guardado si se retira el helper. Sin migración ni datos que revertir.

### Convivencia con el padrón familiar — T4a (02/11/2026)

La configuración no operativa de derechos se verificó junto con una familia
ficticia incorporada por importación y confirmada desde su evidencia aplicada.
Se reutiliza `FamiliaOstelFixture`, sin construir otro importador ni otro circuito
para confirmar vínculos.

- **Previsualizar:** devuelve la propuesta y conserva la huella completa,
  incluidas versiones y auditoría; no incorpora ni habilita afiliados.
- **Guardar versión:** conserva afiliados, titular, revisiones, habilitación,
  historial y lote; agrega sólo la versión y su evento `crear_borrador_derechos`,
  sin reescribir eventos anteriores.
- **Simular:** administrador, operador y auditor consultan plazo guardado7 o
  alternativa0 sin mutaciones; el vínculo familiar y su revisión siguen iguales.
- **Rechazar:** campos de activación y escrituras de lectores no administradores
  conservan íntegros padrón, configuración y auditoría.

Nuevo runner focal: `python -B manage.py test apps.financiadores.test_derechos_padron_aislamiento
--settings=config.settings_financiadores_postgres_test --noinput --keepdb --verbosity 0`.
Dos pruebas OK1.321s en PostgreSQL ficticio dedicado. Regresión de coexistencia con
API de reglas/simulación, cobertura/habilitación y catálogo sintético:104pruebas
OK18.593s. No hay cambio productivo que requiera un RED previo; se agrega evidencia
sobre comportamiento existente. No se vuelve a ejecutar todo el recorrido UI T1.

**Límite de esta evidencia:** familia mínima de dos personas, SaludPadron vacío
preservado, sin medición de volumen, CI, datos reales, nueva aceptación visual
ni aceptación humana. No acredita el circuito completo de #185 ni reglas
operativas de #143/#183. La información normativa ya solicitada a OSTEL sigue
pendiente; no se reemplaza con datos de prueba ni fechas administrativas.
Rollback de este corte: retirar únicamente el nuevo módulo de pruebas y esta
sección, sin tocar datos, migraciones ni funcionalidad existente.

### Trazabilidad consultable de versiones — T2k (02/11/2026)

**Ver trazabilidad** abre la consulta de quién registró cada versión, cuándo y
con qué motivo. Administrador, operador y auditor conservan su permiso existente
de lectura. El servicio de configuración no consulta perfiles, personas ni datos clínicos:
el autor se identifica por su ID interno, sin nombre/email. La fuente informada
sigue siendo una declaración; el registro no acredita normativa ni aprobación.

GET `/api/financiadores/{id}/borradores-derechos/historial/` devuelve
`{historial: [{regla, creado_por_id, creado, motivo}]}`. `regla` es el mismo
DTO de configuración de las consultas anteriores; `creado` se transporta como
fecha/hora ISO UTC y la UI muestra hora local conservando el atributo `datetime`.
Los metadatos proceden del registro original, no del usuario que consulta.
Se preservan por separado cuando otra persona registra una versión nueva.

El endpoint no acepta escrituras (405), no agrega eventos de auditoría ni cambia
versiones/derechos. Usa el guard de lectura y el ámbito de la URL: organización
no visible o membresía revocada404, sin sesión401. GET/POST anteriores mantienen
sus cuerpos, permisos y respuestas; no se modifica ninguna migración.

La consulta carga al abrir, con clave React Query por usuario/financiador y sin
retención deliberada de caché inactiva (gcTime0). Escape devuelve el foco. Se puede volver a consultar;
una carga o un error oculta datos anteriores, y la respuesta pendiente de otro
ámbito no se incorpora al diálogo actual. No hay acciones de aprobar o activar.

Pruebas: autoría/motivo/hora persistidos entre escritores, roles/aislamiento,
rechazo de métodos de escritura y ausencia de mutaciones, contratos anteriores;
navegador real desktop/móvil/teclado, respuesta tardía y fallo/reintento de lectura.
Runners `test_borradores_api`, `test_borradores_derechos`,
`test_derechos_padron_aislamiento` y spec real de borradores; resultados en L33.
Rollback: retirar acción/serializers/servicio de historial y diálogo/botón nuevos,
conservando lectores previos y metadatos persistidos. No hay datos que revertir.

### Contraste técnico de autorizaciones médicas — T6a / #147 (02/11/2026)

**La base existente es reutilizable; no demuestra conformidad con el circuito
médico de OSTEL.** El contraste contra el árbol local `f4dcf01` completa una parte
del análisis, no las definiciones de negocio ni la aceptación de [#147](https://github.com/Mkdir-arg/SistemaDeSalud/issues/147).
El issue referencia SISTEMAS OS Y PREPAGAS MODULOS.pdf (p.1 módulo2 y p.2) y
Resumen Mod Padron.pdf (p.1). Son fuentes documentadas previamente; no se volvió
a acceder a los originales ni se corroboró normativa en este corte.

#### Matriz requisito → base → frontera pendiente

| Requisito recibido en #147 | Base observada | Falta antes de implementar para OSTEL |
| --- | --- | --- |
| Derecho, plan, prestación, PMO y topes en línea | `ReglaCobertura` en `models.py:120–136` configura plan/prestación o categoría, porcentaje, cupo, período mes/año y exigencia de autorización. `cobertura.py:32–37,82–92` cuenta usos externos/reservados/realizados y elige regla específica/general. | Catálogo/versión PMO y correspondencia con prestaciones, prescripción aplicable y excepciones. Regla técnica de cobertura no equivale a PMO homologado ni a la política de gracia/mora pendiente. |
| Solicitud y revisión de Auditoría Médica | `api_autorizaciones.py:56–75` recibe afiliado, institución, prestación común, cantidad, justificación, urgencia y clave; resolver acepta observar/aprobar/rechazar, motivo, texto de evidencia, número externo, cantidad y vigencias. `autorizaciones.py:251–290` reutiliza permiso de resolver, lock, revalidación, revisión, idempotencia y evento. | Actores aprobados, evidencia mínima de prescripción, visibilidad/corrección/retención, motivos, urgencias, plazos, vigencia y renovación. El texto libre existente no es un documento de prescripción validado. |
| Autorización, prestación realizada y liquidación | `ReservaCobertura` (`models.py:388–412`) relaciona caso/prestación, estado, hecho y uso de autorización. `test_uso_autorizaciones.py:30–66` especifica pasos distintos: aprobación, reserva, hecho realizado y captura financiera. | Contrato para usos parciales/repetidos, prestación ya realizada, cambios de plan/convenio y conciliación con liquidaciones. Autorización no acredita prestación realizada, factura, liquidación ni pago. |

Rutas de código bajo `backend/apps/financiadores/`. Pruebas existentes localizadas,
no ejecutadas nuevamente en este corte: `test_cobertura.py`,
`test_autorizaciones_manuales.py` (ManualApiTests/ManualCircuitoTests),
`test_autorizaciones.py` y `test_uso_autorizaciones.py`.
No se atribuye al árbol actual una prueba histórica de otro commit.

#### Decisión de acceso clínico, todavía no aprobada

La bandeja declara no serializar historia clínica del caso. Sin embargo,
`SolicitudAutorizacionSerializer` (`api_autorizaciones.py:90–112`) ya devuelve
texto libre de `evidencia` dentro del circuito administrativo. Esto no prueba
que exista una filtración ni que ese texto contenga datos clínicos reales;
tampoco demuestra que ampliar ese campo a prescripciones sea seguro.
No se accedió a solicitudes o personas reales para este análisis.

Propuesta para decisión humana: **una futura prescripción clínica sólo será
visible para usuarios expresamente designados de Auditoría Médica; operación
y auditoría administrativa verán únicamente su estado administrativo**.
Ventaja: no concede acceso clínico por pertenecer al financiador. Costo: exige
un circuito diferenciado para revisión médica. Riesgo residual: aún deben
acordarse evidencia mínima, correspondencia de capacidades y trazabilidad de
accesos antes de implementar. La propuesta no modifica permisos ni el campo
actual, y no se considera aceptada por la autorización general de continuidad.

#### Cortes mínimos condicionados al contrato

1. Validar el catálogo/versionado y correspondencias PMO recibidos; sin equivalencias
   inferidas ni constantes regulatorias inventadas.
2. Tras decidir el acceso y la evidencia mínima, especificar la prescripción y
   sus controles de lectura/corrección usando las capacidades existentes que correspondan.
3. Acordar usos/vigencias y vínculo con la prestación realizada antes de diseñar
   su relación con liquidaciones. No convertir una autorización en prueba financiera.

Estos son siguientes cortes propuestos, no tareas de negocio aprobadas para
codificar. La información ya solicitada a OSTEL sigue pendiente; no se vuelve
a pedir que el usuario la solicite. T2/#143 y T3/#183 conservan sus límites.

Validación de este corte: lectura integral de #147, mapa CodeGraph y un spot check
de serializers/servicio; readback y enlaces/rutas existentes. No cambia código,
DB, UI, migraciones ni dependencias: RED/GREEN y pruebas funcionales nuevas no
aplican. Sin CI, despliegue, aceptación médica o conformidad normativa.
Rollback: retirar esta sección y el registro T6a del seguimiento, sin efectos en datos.
