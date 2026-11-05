# OSTEL: catálogo sintético, validación local y homologación pendiente

## Derechos: cierre documental de la base no operativa — 04/11/2026

**La base de borradores, versiones, previsualización y simulación está implementada;
el resultado operativo de #143 sigue pendiente.** Este corte vincula capacidades,
evidencia y límites: no aprueba política, activa derechos ni cierra el issue.

### Alcance y referencia reproducible

El objeto de este cierre es el snapshot publicado
`8a3a1d8b87a25380c85e15519fc0683f09ef6c49`, no el HEAD de este worktree.
Los enlaces siguientes fijan ese commit para evitar que otra rama o cambios
posteriores alteren la evidencia. El plan está en ese snapshot; no se copia ni
recrea aquí `odd/tasks/ostel-operacion-integral.md`, ausente en esta base.
Esta actualización prevalece sobre las descripciones históricas de Derechos
del resto del documento sólo para el snapshot indicado; no acredita que sus
capacidades estén incorporadas a main ni actualiza otros frentes.

### Capacidad → evidencia → límite

| Capacidad técnicamente completa | Fuente del snapshot | Evidencia y límite |
| --- | --- | --- |
| Descriptor inmutable, ámbito y vigencia técnica | [derechos_borrador.py:16–76](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/backend/apps/financiadores/derechos_borrador.py#L16-L76) | Coincidencias en `[desde,hasta)` y conflicto explícito. No selecciona una regla ganadora ni fija inicio/corte prestacional. |
| Comparación de propuesta e historia no reescribible | [propuesta_derechos.py:19–40](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/backend/apps/financiadores/propuesta_derechos.py#L19-L40) | Una modificación requiere versión nueva; no se borra ni redefine la historia. Versionar no aprueba la regla. |
| Guardado, auditoría y trazabilidad | [borradores_derechos.py:39–92](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/backend/apps/financiadores/borradores_derechos.py#L39-L92) | Guarda nuevas versiones con autor, fecha, motivo y evento; revalida permisos. No activa derechos. |
| API administrativa y preview sin persistencia | [borradores_api.py:73–111](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/backend/apps/financiadores/borradores_api.py#L73-L111) | Ámbito desde organización autorizada; preview comparte la validación del servicio de guardado, sin guardar ni auditar. No hay aprobación/activación. |
| Simulación temporal configurada o alternativa | [simulacion_plazo_api.py:43–68](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/backend/apps/financiadores/simulacion_plazo_api.py#L43-L68) | Recupera la versión persistida e identifica el origen del plazo. Un límite calculado no determina una consecuencia asistencial. |
| Interfaz administrativa no operativa | [BorradoresDerechos.jsx:56–74](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/frontend/src/pages/financiadores/BorradoresDerechos.jsx#L56-L74) | Presenta acciones y límites de guardar/simular sin prometer aprobación ni activación. |

### Evidencia disponible y alcance del cierre

- **Pruebas existentes, inspeccionadas sin ejecución en este corte:**
  [test_derechos_padron_aislamiento.py:27–85](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/backend/apps/financiadores/test_derechos_padron_aislamiento.py#L27-L85)
  compara huellas del padrón, preserva familia/revisión/lote y exige rechazar
  `activar=True` sin cambios. No se afirma un resultado nuevo de su ejecución.
- **Resultado histórico registrado de G2a:** el
  [registro local de aceptación:1940–1966](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/docs/funcionalidades/financiadores-cobertura/ostel-aceptacion.md#L1940-L1966)
  documenta aislamiento con dos financiadores ficticios, suite API/regresiones
  y recorridos reales de escritorio, móvil y teclado. No se repitieron aquí.
- **Cierre documental:** T2a–T2k y G2a se reconocen como base técnica no operativa
  y caracterización sintética, conforme al
  [plan del snapshot:54–65](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/odd/tasks/ostel-operacion-integral.md#L54-L65).
  Esto no subsana las revisiones nativas históricas pendientes u omitidas
  registradas allí ni las convierte en aprobaciones.
- **Estados separados:** existe commit y publicación del snapshot de referencia;
  este corte documental queda local, sin commit ni publicación. No aporta prueba
  de CI, merge, despliegue, homologación ni aceptación humana. No modifica PR208,
  issues ni el trabajo de saneamiento.

### Qué permanece abierto y condición del siguiente corte operativo

La [matriz pendiente:300–315](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/odd/tasks/ostel-operacion-integral.md#L300-L315)
requiere fuente validada, causal, ámbito, fechas/calendario, evidencia, excepciones,
autoridad de confirmación/reversión y tratamiento de decisiones concurrentes.
Incluye alta/trámite, cese/gracia, desempleo, edad/certificado/CUD, mora de superador,
mora privada y otras causales. Los tres meses citados en el material recibido no
son una constante autorizada; FECVTO, CODPAR o ausencia en lote no habilitan cortes.

No se reitera el pedido ya enviado a OSTEL. Cuando exista validación de una fila
y sus ejemplos antes/en/después del límite, podrá delimitarse una implementación
operativa autorizada: conservar `afiliados_vigentes`, `seleccionar_afiliacion`,
guards e historial; probar efectos permitidos, rechazo sin cambios, reversión
y consumidores previos. No se define ahora un motor, nuevos permisos ni pruebas
de una política inventada. #143, su integración con #183/#185 y la aceptación
operativa permanecen abiertos.

**Verificación de este corte:** lectura de fuentes inmutables, revisión de enlaces
y rangos, preservación del documento previo y comprobación estructural del diff.
Al ser documentación pasiva, no hay un RED funcional significativo: no se
ejecutan tests, build, navegador, DB ni servidores. Risk: none.

### Actualización 05/11/2026: cierre técnico sin bloquearlo por deuda OSTEL

El usuario precisó el objetivo: «tu objetivo es cerrar el modulo esquivando las
deudas de OSTEL, dejando documentada tal deuda pero continuando con el cierre
profesional del modulo». La política pendiente deja de bloquear el cierre del
**configurador de reglas, historial, comparación, preview y simulación**.
No se presenta ese cierre técnico como cumplimiento operativo de todo #143.
La aplicación prestacional, aprobación normativa y activación permanecen como
deuda separada: no se inventan valores, estados, permisos ni un motor universal.

| Frente | Evidencia actual y acción de cierre |
| --- | --- |
| Funciones existentes | Auditoría estática del snapshot: transacciones, guardado idempotente, historia inmutable, preview sin escritura, aislamiento y tratamiento de respuestas tardías/escritura incierta ya tienen implementación y regresiones. No se agrega código ni se duplican pruebas sólo para aparentar avance. |
| Núcleo puro | Ejecución nueva de los tres módulos `tests_derechos_borrador`, `tests_propuesta_derechos` y `tests_simulacion_plazo`: 20 pruebas correctas con Python 3.12, sin Django, DB ni servidores. Se copiaron ocho archivos exactos del snapshot a un directorio temporal externo, se verificaron sus bytes y se retiró ese directorio al terminar. |
| Autoría en simulación de perfiles (DT2) | En el snapshot falta clasificar `BorradorReglaDerechos.creado_por`; no se arregla en paralelo. [PR210](https://github.com/Mkdir-arg/SistemaDeSalud/pull/210) ya fue integrado en su cadena. El [candidato observado de PR208](https://github.com/Mkdir-arg/SistemaDeSalud/blob/c28fc7e15738b9d743546c91cf52af4c0b8c010b/backend/apps/simulacion/contexto.py#L37) contiene la entrada específica. Se verificó el código publicado, no su ejecución global; no equivale a integración en main. |
| Vigencia de la evidencia pura | Se compararon por contenido los tres módulos productivos puros y sus tres módulos de prueba entre `8a3a1d8` y `c28fc7e15738b9d743546c91cf52af4c0b8c010b`: idénticos. Ese resultado no extiende las pruebas puras a API, persistencia o UI del candidato nuevo. |
| API, persistencia y consumidores | Pendiente ejecutar las regresiones existentes del candidato final: borradores, integridad, seguridad, simulación, aislamiento del padrón, cobertura/habilitación y clasificación global de autoría. El resultado histórico G2a no se presenta como ejecución nueva. |
| Interfaz y uso real | Pendiente confirmar el recorrido real del candidato final en escritorio, móvil y teclado, recuperación tras error/cambio de organización y demostración visible. Reutilizar el spec existente; no crear otro harness ni usar respuestas interceptadas como positivos reales. |
| Entrega | PR208 seguía abierto/borrador con comprobaciones en curso al consultarlo. No se afirma CI verde, merge a main, despliegue, revisión nativa aprobada ni aceptación humana. Este documento continúa local y no publicado. |

**Criterio de cierre técnico:** las funciones existentes deben superar sus
comprobaciones aplicables sobre un candidato identificado que incluya la
corrección de autoría; la documentación debe indicar alcance, operación segura,
evidencia y limitaciones. Entrega, revisión y aceptación se registran por separado.
La deuda normativa no obliga a agregar funcionalidades antes de ese cierre, pero
tampoco permite omitir fallos técnicos o declarar comprobaciones no ejecutadas.

**Continuación necesaria:** preparar un entorno local aislado para las pruebas
de persistencia y navegador, con PostgreSQL descartable y exclusivamente datos
ficticios, sin `.env`, bases existentes, procesos ajenos ni acceso a saneamiento.
El alcance inicial excluía DB/servidores; se requiere autorización específica
para esta comprobación antes de iniciarlos. No se atribuye este límite a OSTEL.
Esta actualización sólo modifica documentación y ejecuta pruebas puras existentes;
no cambia código productivo ni concede aprobación/activación de derechos.

### Resultado del cierre técnico local — 05/11/2026

**Cierre técnico local verificado del configurador, versiones, comparación,
preview, trazabilidad y simulación**, sobre PR208
`c28fc7e15738b9d743546c91cf52af4c0b8c010b`. El usuario autorizó expresamente
PostgreSQL descartable, datos ficticios, servidores loopback y navegador real.
Esta evidencia resuelve los pendientes de comprobación local de la tabla
anterior; no convierte la deuda normativa ni la aceptación humana en completas.

| Comprobación | Resultado observado |
| --- | --- |
| API/PostgreSQL y consumidores | 121 pruebas existentes correctas en 33,821 s: borradores API/seguridad/servicios/integridad/aislamiento, simulación API y pura, propuestas, cobertura/habilitación y clasificación de autoría. No se duplicaron pruebas ni se cambió producto. |
| Build frontend | Correcto en 5,19 s con dependencias del lockfile y configuración externa sin archivos de entorno. |
| Navegador real | 27 recorridos existentes correctos en 48,1 s: escritorio, móvil, teclado, guardado persistido, preview, simulación, trazabilidad y recuperación ante errores. El candidato de PR208 tiene 27 casos; no se le atribuyen los 29 de G2a en otra rama. |
| Positivos y negativos | Los positivos usan API/PostgreSQL reales ficticios. Los casos 403/503 y respuestas tardías inyectadas prueban manejo de transporte/interfaz, no revocación real de permisos. La seguridad de API se comprueba en su suite propia. |
| Comprobación del padre | Clasificación global de campos de autoría ejecutada nuevamente: correcta. Capturas de pantalla completa y modal inspeccionadas en escritorio y móvil: sin recorte horizontal; modal móvil con desplazamiento vertical. |
| Demostración | Chromium con ventana visible y datos ficticios, en `http://127.0.0.1:63832/financiadores/borradores?financiador=1`. Simulación HTTP 200 con referencia 2030-01-01, evaluación 2030-01-08 y siete días: límite 2030-01-08, «en el límite», sin guardar nuevas filas. Pantalla restablecida a escritorio para probarla. |
| Integridad y aislamiento | Los 922 archivos de fuente del candidato conservan sus huellas. Copia y venv externas; dotenv deshabilitado en el launcher y Vite sin archivos de entorno. Sólo contenedor propio, PostgreSQL en loopback/tmpfs, fixture dedicada y credenciales ficticias gestionadas internamente sin mostrarlas. |

**Reproducibilidad y límites del entorno.** Se usó Python 3.12 y se instaló
únicamente el `requirements.txt` existente en el venv externo; su restricción
abierta `Django>=5.0` resolvió Django 6.1.3. Por tanto, no se afirma paridad exacta
de dependencias Python con producción/CI. Frontend: `npm ci --ignore-scripts
--no-audit --no-fund`, sin modificar manifiestos ni lockfile.

El primer build falló antes de compilar por una ruta interna inexistente del
plugin React en la configuración externa del verificador. Una corrección acotada
para resolver exports publicados y codificar el favicon resolvió ese fallo;
se conserva el log original, sin atribuirlo a producto. No hubo corrección de
fuentes. La inspección directa de ventanas por CUA no estuvo disponible
(`Module not found: @oai/cua/tinyskyAlt`); se inspeccionaron capturas y se confirmó
la ventana nativa abierta. La demo visible no sustituye aceptación humana.

**Localización de evidencia y recursos propios.** Directorio temporal externo
`salud-derechos-cierre-4nnht4kp` bajo el temporal del usuario: logs `regression.log`,
`parent-spotcheck.log`, `build-setup-failed.log`, `build.log` y `browser.log`;
capturas `demo-desktop-top.png`, `demo-desktop-modal.png` y
`demo-mobile-modal.png`. Comandos y conservación de recursos en
`odd/tasks/derechos-cierre-tecnico.md`. Se retienen sólo recursos propios para
la demo; son temporales, no almacenamiento duradero de evidencia cruda.

**Entrega separada:** documentación todavía local, sin commit ni publicación.
PR208 sigue abierto/borrador sobre el mismo candidato; CI backend estaba en curso
en la última consulta, aunque las otras comprobaciones visibles habían terminado
correctamente. No se afirma revisión nativa aprobada, merge, deploy ni aceptación.
El cierre local no resuelve todo #143: activación/aplicación prestacional y
contratos OSTEL permanecen documentados como deuda externa. No se tocaron
saneamiento, bases existentes ni datos reales. Risk: none (cambio documental).

### Aceptación y transferencia de deuda — 05/11/2026

El usuario aceptó el cierre técnico y autorizó commits, push y merge; confirmó
«todo completo» al aclarar que PR208 también incluye los demás frentes OSTEL.
[PR208](https://github.com/Mkdir-arg/SistemaDeSalud/pull/208) fue integrado en main
con los seis checks correctos, sin bypass, mediante el commit
`c4816271f66a1fe68beba89f1591fc6c86c70c5e`. La aceptación no valida normativa.

- [#143](https://github.com/Mkdir-arg/SistemaDeSalud/issues/143) permanece abierto
  y pasa a **In QA** en Tareas I-Core para el configurador, versiones, preview,
  trazabilidad y simulación. El cuerpo conserva el alcance histórico y documenta
  expresamente lo que falta; no marca como cumplidos sus criterios normativos.
- [#216](https://github.com/Mkdir-arg/SistemaDeSalud/issues/216) es la continuación
  prestacional **Blocked** por respuesta/validación externa, con los criterios
  para retomar reglas, activación, aplicación/reversión e integración #183/#185.
  La información ya fue solicitada; no reiterar el pedido ni inventar valores.
- El acta y su registro se entregan como cambio documental separado, sin alterar
  el candidato funcional verificado. La autorización de merge no autoriza un
  despliegue manual ni acredita el resultado de automatizaciones posteriores.

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
