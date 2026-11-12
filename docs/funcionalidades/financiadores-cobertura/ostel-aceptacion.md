# OSTEL: catálogo sintético, validación local y homologación pendiente

## Autorizaciones médicas: trazabilidad del corte estudiado — 05/11/2026

**S17–S21 tienen circuito técnico implementado y evidencia local histórica;
el contrato clínico y la aceptación integral de #147 siguen pendientes.**
Esta sección cierra la reconciliación documental, no el issue ni la homologación.

### Fuente y alcance

El corte estudiado es `8a3a1d8b87a25380c85e15519fc0683f09ef6c49`.
Esta rama de cierre parte del snapshot exacto. La matriz se recuperó del
worktree analítico basado en `cae9e16`, preservando aquí el documento completo
del snapshot. Las referencias fijan la evidencia estudiada, no acreditan una
instalación en funcionamiento. No se modificó saneamiento.

Las decisiones se consultan en las
[Specs S17–S21 del corte](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/odd/tasks/ostel-operacion-integral.md#L28-L36).
La siguiente matriz las identifica sin reemplazar sus textos originales.

### Requisito → capacidad → evidencia → límite

| Decisión | Capacidad y guarda existentes en el corte | Evidencia existente | Estado y límite |
| --- | --- | --- | --- |
| S17: visibilidad reservada | Designación `auditoria_medica` por financiador; un rol administrativo o plataforma no sustituye la capacidad. El DTO administrativo informa estado, no el documento. | [Guarda de lectura](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/backend/apps/financiadores/permisos.py#L62-L78); `test_metadatos_no_aparecen_en_bandeja_historial_ni_descarga_generica` y `test_permisos_revocados_y_ambitos_ajenos_sin_bytes` en [pruebas de prescripción](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/backend/apps/financiadores/test_prescripciones_autorizacion.py). | Implementado; no concede historia clínica general ni asigna usuarios reales. |
| S18: ingreso institucional y consulta médica | La institución presenta con la solicitud; Auditoría Médica designada descarga; la resolución exige su permiso independiente. | `test_presentacion_privada_con_solicitud_y_descarga_medica_auditada` y `test_plataforma_no_sustituye_al_presentante_institucional` en las pruebas anteriores; [recorrido real](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/frontend/e2e/prescripciones-autorizacion-real.spec.js#L106-L167). | Implementado; no impone aprobación médica exclusiva ni precedencia normativa nueva. |
| S19: adjunto privado PDF/imagen | Documento separado de la justificación administrativa; validación técnica de formato, firma y tamaño; reintento idéntico sin duplicación ni reemplazo. | `test_formato_firma_tamano_y_unico_archivo_antes_de_escribir` y `test_reintento_mismos_bytes_y_clave_no_duplica_y_no_reemplaza` en las pruebas de prescripción. | Representación implementada; validación técnica no acredita suficiencia clínica. No convertir el adjunto opcional en obligatorio por inferencia. |
| S20: almacenamiento privado simple | Alias dedicado; sin fallback general; almacenamiento local fuera de `MEDIA_ROOT`, o prefijo separado en el bucket privado ya configurado. | [Servicio y rechazo de media pública](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/backend/apps/financiadores/prescripciones_autorizacion.py#L32-L83); `test_alias_ausente_no_recurre_al_almacenamiento_general` y `test_storage_fuera_de_media_no_expone_documento_por_rutas_normalizadas`. | Implementado; no demuestra configuración remota, backup ni política de conservación aprobada. |
| S21: aprobar/rechazar la misma solicitud | Reutiliza el resolver existente; lectura y resolución se designan y revocan por separado. Conserva ID, revisión, historial e idempotencia, sin crear dictamen paralelo. | `test_evaluacion_medica_aprueba_la_solicitud_existente_sin_registrar_atencion`, su caso de rechazo y `test_lectura_y_resolucion_se_designan_y_revocan_independientemente` en [pruebas de designación](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/backend/apps/financiadores/test_auditoria_medica.py); recorrido real anterior. | Implementado y caracterizado en T6h; aprobar no crea una atención nueva ni demuestra pago. Si ya hay una atención realizada pendiente de autorización, la resolución puede completar su distribución financiera; conservar ese circuito existente. |

### Evidencia disponible y aceptación pendiente

[T6h/L42](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/odd/tasks/ostel-operacion-integral.md#L681-L691)
registra ejecución local histórica de API y navegador real sobre datos ficticios:
aprobación en escritorio, rechazo en móvil y descarga por teclado con bytes
exactos. La comprobación inicialmente bloqueada por Docker quedó completada;
no corresponde mantener ese impedimento histórico como faltante de T6h.
Los negativos con transporte inyectado conservan su límite explícito: no son
prueba positiva del backend.

La matriz inicial se comprobó estructuralmente. En la continuación del 05/11
se añadieron dos caracterizaciones API de presentación privada → observación →
reenvío → aprobación/rechazo en `test_prescripciones_autorizacion.py`. Verifican
mismo ID, original y plazo, revisión obsoleta sin cambios, reintento exacto y
revocación independiente de lectura/resolución. Los 48 h de la fixture son un
valor técnico ficticio, no una vigencia ni política clínica aprobadas.

La primera ejecución detectó una expectativa demasiado amplia del test: cada
respuesta del ámbito financiador audita `consultar_autorizaciones` en
`EventoCobertura`, incluso en un reintento. Se mantuvo el dominio intacto y se
exigió exactamente una consulta nueva, sin tocar la auditoría productiva ni
relajar los rechazos. No hubo cambio de producto ni RED artificial.

Focal: dos caracterizaciones aprobadas (0,795 s). Suite de prescripciones,
designaciones, autorizaciones, manuales y usos: 82 tests en 8,269 s, sin fallos,
10 omitidos por necesitar PostgreSQL/bloqueos reales. Runner externo con entorno
saneado, dotenv deshabilitado, SQLite en memoria y almacenamiento ficticio;
base efímera destruida al terminar. Se reutilizaron dependencias instaladas,
sin cambios globales ni instalaciones. Advertencia: `backend/staticfiles`
ausente; no se investigó ni modificó saneamiento.

Ese límite de entorno fue levantado por autorización explícita posterior.
Se creó PostgreSQL 16 Alpine propio, con datos efímeros y puerto sólo loopback;
se migró exclusivamente su base ficticia. La misma suite ejecutó 82 tests en
37,381 s sin fallos ni omisiones, incluidas concurrencia y revocación. Se
reutilizaron dependencias Python instaladas y `npm ci` desde el lockfile, sin
modificar manifiestos/versiones ni instalar globalmente.

El runner de prescripciones existente se amplió con dos escenarios nuevos, sin
cambiar los siete anteriores: observación → reenvío → aprobación/rechazo en
escritorio/móvil. Exigen conservar ID, original descargado con bytes exactos,
plazo no vacío, revisiones e historial, y mantienen separación de capacidades.
Las 48 h de respuesta son ficticias y no se homologan como política OSTEL.
Focal visible: 2 recorridos en 23,3 s. Suite final: 11 recorridos en 45,7 s sin
fallos ni omisiones. Positivos reales contra API/PostgreSQL/almacenamiento
ficticios; los negativos inyectados conservan su alcance de transporte.
Capturas escritorio/móvil inspeccionadas, reenvío/resolución y descarga por
teclado. No hay cambios de UI/producto.

El Chrome del sistema no pudo arrancar para automatización; se usó el Chromium
1234 ya instalado, correspondiente al Playwright del lockfile. Los ajustes de
lanzadores quedaron fuera del repositorio: entorno saneado, dotenv deshabilitado,
Vite sin envFile y cwd externo, cache/resultados propios. No acceso a `.env`,
secretos, bases existentes/remotas ni recursos de saneamiento. Se conserva la
advertencia preexistente de staticfiles; no se investigó como parte de este corte.
La validación técnica local no cierra los contratos clínicos ni la aceptación
humana, y no acredita CI, merge ni despliegue.

La evidencia anterior no acredita CI, merge, despliegue, disponibilidad actual,
revisión nativa pendiente ni aceptación humana. Publicación del snapshot y
existencia de otro PR acumulado tampoco acreditan esos estados.

### Contratos que impiden el cierre integral

| Pendiente | Condición mínima de cierre |
| --- | --- |
| Criterios clínicos/PMO | Catálogo/versionado, correspondencias con prestaciones y criterios/excepciones aprobados. Las reglas técnicas de cobertura existentes no son PMO homologado. |
| Evidencia mínima y obligatoriedad | Definir cuándo se exige prescripción, qué debe acreditar y cómo se determina suficiencia; no inventar contenido clínico. |
| Vigencias, renovación y circuito | Acordar condiciones aplicables, motivos y excepciones; no deducir plazos ni exclusividad médica de los permisos técnicos. |
| Conservación y reemplazo | Acordar política y circuito autorizado de corrección/reemplazo. El reintento idempotente no es reemplazo; no agregar borrado ni plazos automáticos. |
| Prestación y liquidación | Contrato para usos parciales/repetidos, cambios de plan y conciliación de prestación realizada; autorización no equivale a hecho asistencial ni deuda financiera. |
| Aceptación funcional/clínica | Recorrido validado por OSTEL con reglas representativas aprobadas y evidencia de integración; no sustituirlo por pruebas sintéticas. |

Se conserva el límite de uso: motivo/evidencia administrativa sólo contiene
referencias de revisión, no transcripciones clínicas reservadas. La privacidad
del archivo no constituye una garantía semántica sobre el texto libre ni prueba
que haya ocurrido una filtración.

Seguimiento: [#147](https://github.com/Mkdir-arg/SistemaDeSalud/issues/147) y
[consolidación del corte](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/docs/funcionalidades/financiadores-cobertura/ostel-aceptacion.md#L1740-L1752).
No se reitera la información ya solicitada a OSTEL. Queda cerrado únicamente
el mapa documental de S17–S21; no se cierran issues, se crean tareas paralelas
ni se habilita código de negocio nuevo mientras falten sus contratos.

## Lectura por corte: Novedades — 04/11/2026

La [matriz de Novedades](#matriz-de-evidencia-de-novedades--04112026) al final
contrasta #183 contra `8a3a1d8b87a25380c85e15519fc0683f09ef6c49`. Las secciones
históricas conservan su fecha: no describen por sí solas ese snapshot ni prueban
que sus cambios estén incorporados en este checkout.

Frontera vigente de Novedades: [cierre genérico y deuda OSTEL](#novedades-frontera-de-cierre-genérico-aprobada--05112026).
El circuito genérico tiene implementación y pruebas locales; no implica habilitar
efectos OSTEL, homologación, aceptación humana ni despliegue.

## Derechos: cierre documental de la base no operativa — 04/11/2026

**La base de borradores, versiones, previsualización y simulación está implementada;
el resultado operativo de #143 sigue pendiente.** Este corte vincula capacidades,
evidencia y límites: no aprueba política, activa derechos ni cierra el issue.

### Alcance y referencia reproducible

El objeto de este cierre es el snapshot publicado
`8a3a1d8b87a25380c85e15519fc0683f09ef6c49`, no el HEAD de este worktree.
Los enlaces siguientes fijan ese commit para evitar que otra rama o cambios
posteriores alteren la evidencia. El plan se consulta en ese snapshot. Estaba ausente en la base inicial de
análisis; ahora se conserva el integrado por PR208, sin copiar ni recrear
`odd/tasks/ostel-operacion-integral.md`.
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

**Recibo de entrega:** [PR217](https://github.com/Mkdir-arg/SistemaDeSalud/pull/217)
integrado en main como `b823fac22e39adc99e778c22722c3ea8d44961d7`, con sus checks
Frontend y OpenAPI correctos. Commits del acta: `2e58bcf` y reconciliación
`44ec765`. Tras la aceptación se apagaron los servicios/Chromium de prueba
propios y se eliminó su contenedor descartable; la demo temporal anterior ya no
está disponible. Las capturas y logs externos se retienen como evidencia temporal.
No se ordenó un despliegue manual; no se acredita ningún resultado automático
de despliegue sin observación independiente.


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
En los escenarios históricos `referencia_*`, `NROREF` coincide deliberadamente
con el `NROAFI` de otra fila para comprobar presencia textual. Se conservan como
estímulos opacos, no como la regla familiar confirmada; la aclaración del
06/11/2026 y los nuevos casos `nroref_*` se documentan al final.
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

## Matriz de evidencia de Novedades — 04/11/2026

**#183 está parcialmente construido. Esta matriz cierra el inventario documental,
no el circuito operativo ni la aceptación del issue.** No corresponde reconstruir
la importación, el historial ni la gestión manual de vigencia ya existentes.

### Fuente y alcance

- Solicitud: «implementa el proximo corte recomendado». Se materializa la matriz
  recomendada de los seis criterios de #183; no se cambia negocio.
- Snapshot: `8a3a1d8b87a25380c85e15519fc0683f09ef6c49`, leído con `git show`.
  HEAD al iniciar: `cae9e16`. Su diferencia no es un faltante del producto estudiado.
- Requisitos: [#183](https://github.com/Mkdir-arg/SistemaDeSalud/issues/183),
  dependiente de [#143](https://github.com/Mkdir-arg/SistemaDeSalud/issues/143).
  Ambos estaban abiertos en la consulta del análisis previo; no se cambia su estado.
- Los enlaces de código fijan el snapshot. Las pruebas citadas fueron **leídas,
  no ejecutadas en este corte**. «Resuelto» sólo califica la garantía indicada;
  «parcial» no permite cerrar el criterio completo.

### Contraste de criterios

| Criterio de #183 | Capacidad y evidencia del snapshot | Estado y límite |
| --- | --- | --- |
| 1. Conservar fechas/códigos originales; no equiparar FECVTO con corte | [Importador:306–332](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/backend/apps/financiadores/ostel_importacion.py#L306-L332) conserva las 40 columnas en `original`. `test_ostel_importacion.py:124–135` comprueba que subsanar no reemplaza el CUIL original. | Resuelto como conservación de evidencia; no implica interpretación normativa ni que esa prueba puntual cubra todas las columnas. |
| 2. Persona coincidente frente a evento duplicado; episodios históricos | [Validación:220–240](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/backend/apps/financiadores/ostel_importacion.py#L220-L240) rechaza identidades contradictorias y reingresos implícitos. `test_ostel_importacion.py:366–376` comprueba que repetir una carga no duplica personas. | Parcial: identidad de persona no es identidad de acontecimiento. Falta conciliar eventos repetidos, reingresos distintos y rectificaciones de episodios. |
| 3. Previsualizar conflictos antes de finalizar/reactivar | La validación anterior exige comparar diferencias y revisar cambios del padrón. `test_ostel_importacion.py:397–406` impide aplicar diferencias entre fuentes sin revisión. [Servicios manuales:120–152](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/backend/apps/financiadores/vigencias.py#L120-L152) finalizan ahora y reactivan desde hoy. | Parcial: comparación administrativa y confirmación manual no son conciliación temporal. Falta previsualizar conflictos del acontecimiento/episodio bajo T2. |
| 4. Autor, motivo e historia; correcciones sin borrar antecedentes | [Subsanación:350–402](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/backend/apps/financiadores/ostel_importacion.py#L350-L402) registra correcciones; [historial común:120–126](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/backend/apps/financiadores/padron.py#L120-L126) conserva delta, autor, motivo, origen y lote. | Resuelto para corrección administrativa existente; parcial para rectificar acontecimientos todavía no implementados. Reutilizar historial, no crear otro paralelo. |
| 5. Baja administrativa separada de derechos; sin gracia/mora automática | [Padrón:80–107](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/backend/apps/financiadores/padron.py#L80-L107) valida fechas y calcula estado administrativo. `test_padron130.py:247–255` mantiene vigente una afiliación con baja administrativa programada. | Resuelta esa separación; pendiente traducir novedades a derechos bajo contrato aprobado. Finalizar manualmente sí cambia vigencia: no confundirlo con informar una fecha o simular. |
| 6. Repetidos, orden inverso, reingreso, rectificación y fechas inconsistentes | Hay validación cronológica administrativa, revisión optimista y reintentos sin duplicar personas. `test_ostel_importacion.py:359–364` bloquea bajas aun tras intentar subsanar. | Parcial: esas piezas no resuelven secuencias de acontecimientos ni prueban precedencias temporales y episodios efectivos. El faltante no se deduce sólo de tests ausentes. |

Las referencias abreviadas a pruebas corresponden a `backend/apps/financiadores/`
en el mismo snapshot, no necesariamente a los archivos del HEAD de este worktree.

### Invariantes y precisión de la evidencia

- **Ausencia en lote no produce baja.** [Aplicación OSTEL:407–449](https://github.com/Mkdir-arg/SistemaDeSalud/blob/8a3a1d8b87a25380c85e15519fc0683f09ef6c49/backend/apps/financiadores/ostel_importacion.py#L407-L449)
  procesa filas presentes válidas; no finaliza ausentes. `test_importaciones.py:209–219`
  comprueba conservación de la persona omitida y cantidad de afiliados en el
  importador genérico; no afirma igualdad completa de vigencia, revisión e
  historial ni prueba por sí sola el adaptador OSTEL.
- **Evidencia de baja no es una orden ejecutable.** Fuente de bajas, ESTADO B o
  FECBAJ informada bloquean la fila; subsanar no permite forzar su aplicación.
- **Gestión manual no es conciliación histórica.** Finalizar/reactivar conserva
  identidad y registra historia, pero usa ahora/hoy; no recibe fecha efectiva
  externa ni selecciona un episodio para rectificar.

### Cierre posible y siguiente dependencia

Quedan documentadas las capacidades entregadas y sus límites. No se cierra #183,
no se activan derechos y no se reitera el pedido de información ya pendiente.
El circuito funcional depende de T2/#143: contrato validado de causales, fechas
efectivas, precedencia/rectificación, efectos, evidencia y autoridad de aplicación.
No se inventan identificadores de eventos, episodios ni políticas.

Si se autoriza caracterización ejecutable posterior, revisar las pruebas existentes
y añadir sólo el faltante concreto: por ejemplo, comprobar por API OSTEL que la
omisión preserva también vigencia, revisión e historial, con aislamiento entre dos
financiadores ficticios. Reutilizar `test_ostel_importacion.py`, sus constructores
y endpoints; sin cambios productivos ni repetición de G2a. Es evidencia propuesta,
no ejecutada ni una tarea operativa iniciada. Si falla, diagnosticar antes de ampliar alcance.

### Verificación y límites de este corte documental

Lectura de fuentes y aserciones del snapshot, referencias ancladas a su SHA y
revisión estructural del diff. RED/GREEN, tests funcionales, build y navegador no
aplican a esta modificación pasiva; no se ejecutan DB, fixtures ni servidores.
Sin cambios productivos, permisos, esquema, dependencias ni archivos de saneamiento.
Commit, push, PR, CI, merge, deploy y aceptación humana no se acreditan con esta
matriz. Risk: none.

## Novedades: caracterización administrativa — 05/11/2026

El usuario aprobó avanzar por el plan hasta un bloqueo o intervención humana.
Se ejecuta el primer corte de pruebas propuesto arriba, sin cambiar código
productivo, reglas, permisos, modelos ni proveedores. Seguimiento y reproducción:
`odd/tasks/novedades-cierre.md`, T1–T5.

### Garantías caracterizadas por API

Se extiende `ImportacionAdministrativaTests` en `test_ostel_importacion.py`,
reutilizando `preview`, `corregir`, `aplicar`, `_persona` y `generar_xlsx`.
Dos financiadores ficticios tienen afiliados con los mismos identificadores y
lotes/historia no vacíos. Las instantáneas comparan filas completas, sin excluir
fechas, revisión ni campos de vigencia.

| Caso | Efecto observado que debe preservar la prueba |
| --- | --- |
| Omisión y corrección explícita | Se corrige y aplica el nombre de una persona presente; la omitida y las personas/historia/lotes de B permanecen idénticos durante preview, subsanación y aplicación. Repetir la aplicación conserva todos los afiliados e historia. |
| Bajas y posible reingreso | Fuente `bajas`, ESTADO B y FECBAJ informada no generan filas válidas; subsanación devuelve400. Una afiliación finalizada expresamente no se reactiva por volver a aparecer: subsanación puede devolver200, pero conserva la fila en revisión con error explícito. Aplicar produce cero filas aplicadas. Padrón/historia de A/B y lotes de B intactos. |
| Revisión desactualizada | Tras revisar un lote, una edición válida por API cambia el padrón; aplicar la propuesta anterior mantiene la fila pendiente, aplica cero filas y preserva el estado posterior a esa edición, sin historia de una aplicación inexistente. |

**HTTP200 no significa que una novedad esté aplicada.** El caso de reingreso
confirma un resultado administrativo pendiente, no un defecto ni permiso para
reactivar. La corrección del lote puede tener trazabilidad propia legítima;
la huella no exige que el lote de A permanezca intacto cuando se revisa.

### Alcance y entorno

- Evidencia nueva del checkout real `cae9e16` más estas pruebas. Importador y
  servicios manuales coinciden con `8a3a1d8`; modelos/padrón difieren. No se acredita
  integración del snapshot completo ni del trabajo de saneamiento.
- SQLite en memoria, migraciones reales y datos ficticios. Launcher temporal
  externo con entorno limpio, carga `.env` anulada antes de importar settings y
  conexiones de red bloqueadas. No Docker, bases existentes, credenciales ni
  cambios de dependencias. SQLite no prueba locks/concurrencia de PostgreSQL.
- Caracterización de conducta existente: no se fabrica RED. Los fallos iniciales
  fueron del test nuevo: `_persona` devuelve tupla, y subsanar un reingreso no
  exige HTTP400 si mantiene el bloqueo. Se corrigieron las expectativas, no el producto.
- Resultados finales y estado de revisión/commit: Log del seguimiento. No hay
  cambio visual: navegador/build no aplican; no CI, publicación, merge ni deploy.

### Bloqueo del siguiente corte

T2 continúa esperando el contrato aprobado de #143/#183: identidad de evento y
episodio, duplicado frente a rectificación, precedencia de fuentes, fecha efectiva,
efecto autorizado y autoridad de aplicación/corrección. La lectura de ambos issues
y sus comentarios el05/11 no aporta esa validación; #183 ratifica expresamente
que planificación/pruebas sintéticas no habilitan inferir bajas o reingresos.
No se reitera el pedido ya pendiente, no se construye un modelo provisional ni se
inician T3–T5. El módulo permanece abierto. Risk: none (sólo pruebas y documentación).

## Novedades: frontera de cierre genérico aprobada — 05/11/2026

Esta sección reemplaza el bloqueo general del apartado anterior, no su evidencia.
El usuario confirmó cerrar el circuito técnico genérico y documentar lo que no se
hará hasta resolver la deuda OSTEL. La falta de reglas del financiador no debe
impedir registrar, comparar y resolver administrativamente evidencia sin efectos
prestacionales. **La aprobación de este alcance no prueba que esté implementado.**

### Resultado técnico que se construirá

Un recorrido dentro del portal del financiador: registrar una propuesta para una
persona de su padrón, conservar datos originales y fuente/referencia, comparar con
el estado actual, señalar coincidencias/conflictos y conciliar o descartar con
motivo e historia consultable. Una rectificación será una propuesta nueva enlazada
al antecedente, no una sobrescritura. No se crea un importador universal ni otro
motor de derechos.

En este circuito, **«conciliada sin aplicación» significa evidencia revisada, no
cambio del padrón, reactivación, cobertura ni aprobación normativa**. La interfaz
y las respuestas deberán mantener esa distinción. Los servicios manuales de
vigencia existentes quedan separados e intactos.

### Deuda OSTEL: lo que no se implementa ni habilita en este cierre

| Deuda pendiente | Conducta expresamente excluida hasta validación | Condición para retomarla |
| --- | --- | --- |
| Semántica de FECING/FECBAJ/FECVTO y fecha efectiva | Transformar esas fechas informadas en inicio/corte prestacional o ejecutar novedades por calendario. | Fuente y ejemplos de límites de fecha aprobados para cada efecto. |
| Causales, duplicado normativo, precedencia entre fuentes | Homologar MOTIVO/ESTADO por semejanza, elegir automáticamente la última fuente o interpretar coincidencia de persona como un mismo acontecimiento. | Catálogo y precedencias validados; identificación del acontecimiento confirmada. |
| Episodios y rectificaciones históricas efectivas | Reconstruir vigencias por inferencia, reactivar por reaparición o borrar/reemplazar antecedentes aplicados. | Contrato de episodios, alcance de rectificación y mecanismo aprobado de corrección/reversión. |
| Gracia, mora, subsidio, excepciones y autoridad | Calcular/activar restricciones, suspensiones o extensiones de derechos; cambiar planes o conceder permisos reales por inferencia. | Reglas aprobadas de #143 y autoridad explícita; ejemplos antes/en/después y excepciones. |
| Efectos sobre familia, atención, autorizaciones o dinero | Propagar una conciliación administrativa a familiares, prestaciones, reservas, autorizaciones, cargos, aportes o pagos. | Contrato específico del efecto y aceptación de sus consumidores, separado de la conciliación documental. |
| Otras fuentes o integraciones no contratadas | Crear formatos/equivalencias universales o integrar organismos externos para suplir la información ausente. | Fuente seleccionada y contrato real; autorización independiente de integración. |

La documentación de esta deuda no equivale a resolverla ni a cerrar los efectos
pendientes de #143/#183. No se vuelve a solicitar la misma información a OSTEL.

### Diseño técnico y reutilización

- Usar el contenedor existente `Importacion` con tipo reservado `novedades`,
  serializer/rutas propios y un contrato JSON validado. No requiere nueva tabla
  ni un modelo provisional de episodios. Guardar propuesta no escribe afiliados.
- La historia de decisiones pertenece a la propuesta y a `auditar` existente;
  `HistorialAfiliacion` sólo registra cambios reales del padrón. No crear historia
  ficticia de afiliación para una decisión sin efectos.
- Aislar la nueva variante: el listado/serializer/confirmación de importaciones
  previas no reconocen automáticamente ese tipo. Antes de admitir propuestas,
  impedir que una ruta legacy las interprete como consumos o padrón. Conservar
  resultados de formatos existentes mediante regresiones diferenciales.
- Reutilizar membresías, permisos, paginación, componentes del portal y guardas
  de organización. Reintentos exactos no duplican propuesta/decisión; reutilizar
  una clave con contenido distinto debe fallar. Una referencia coincidente es
  advertencia/conflicto explícito, no una decisión normativa automática.
- Validar concurrencia/revisión antes de resolver; preview y decisiones no deben
  alterar vigencia, afiliados, historial de afiliación, reservas ni consumos. La
  persistencia en JSON simplifica el esquema a costa de exigir validación estricta
  en el servicio; PostgreSQL debe comprobar los locks reales.

### Criterio de cierre y entrega

El cierre técnico exige API y recorrido visible completos de registro, listado,
comparación, conciliación/descarte e historia, permisos/aislamiento y pruebas de
rechazo, idempotencia y concurrencia. Debe verificarse escritorio, móvil, teclado y
respuestas tardías al cambiar de organización. No es suficiente escribir esta
sección o probar sólo el simulador. Homologación OSTEL, aceptación humana,
publicación, CI, merge y despliegue mantienen evidencia separada.

Estado técnico local de este nuevo alcance: circuito genérico implementado,
verificado y revisado. No equivale a publicación, aceptación humana ni homologación
OSTEL. Seguimiento: `odd/tasks/novedades-cierre.md`, L7–L12.

### Uso del circuito genérico

1. En el portal del financiador, abrir **Novedades**. Operación/administración
   puede registrar una propuesta seleccionando una persona existente; auditoría
   puede consultar, pero no registrar ni resolver.
2. Informar fuente, referencia/código opcionales, fecha informada opcional,
   descripción administrativa y motivo. No incluir contenido clínico. La fecha
   se representa en ISO; los textos de evidencia conservan su literalidad.
3. Consultar evidencia original, persona al registrar, padrón actual e historia.
   Si hay referencia repetida o cambió la revisión del padrón, comparar antes de
   confirmar. Una coincidencia no fusiona personas ni establece precedencia legal.
4. Registrar motivo y conciliar **sin aplicar efectos**, o descartar. La decisión
   es terminal y conserva el registro. Una revisión desactualizada se rechaza;
   actualizar la comparación antes de intentarlo nuevamente.
5. Para rectificar, crear una propuesta enlazada al antecedente. No se borra ni
   se cambia la decisión anterior automáticamente. Consultar luego la historia
   persistida y filtrar por estado en el listado paginado.

### Contrato de API y garantías

Todas las rutas se ubican bajo `/api/financiadores/{id}/`, con autenticación y
pertenencia al financiador verificadas en servidor:

| Ruta | Operación y resultado |
| --- | --- |
| `GET novedades/` | Listado paginado; filtros `estado` y `afiliado`. Sólo su organización. |
| `POST novedades/` | `clave` UUID, `afiliado`, `fuente`, `descripcion`, `motivo`; opcionales `referencia`, `codigo`, `fecha_informada`, `rectifica`.201 al crear,200 en reintento exacto; clave con contenido diferente400. Campos ajenos al contrato400. |
| `GET novedades/{novedad}/` | Original, persona inicial/actual, revisión, coincidencias, conflictos, estado e historia. Sin modificar padrón. |
| `POST novedades/{novedad}/resolver/` | `accion` conciliar/descartar, `revision`, `revision_padron`, `motivo` y `confirmar_conflictos` cuando corresponda.200 tras decidir; reintento exacto no duplica historia/auditoría. Otra decisión sobre una propuesta terminal o revisión obsoleta400. |

Las respuestas incluyen `efectos_aplicados=false`. La misma referencia externa
en otra organización no aparece como coincidencia. IDs de personas, propuestas o
antecedentes ajenos se rechazan sin revelar sus datos. Sin sesión401; auditor
que intenta escribir403. Las rutas de importación anteriores no listan ni aplican
contenedores Novedades; sus formatos previos mantienen sus propios contratos.

La concurrencia se serializa dentro del financiador y se revalida la revisión de
la persona antes de decidir; no se toma un snapshot obsoleto como permiso. Se
registran actor, fecha, motivo y comparación al decidir en la historia de la
propuesta; no se crea una actualización ficticia de `HistorialAfiliacion`.

### Evidencia local y límites vigentes

Las pruebas públicas incluyen datos hospitalarios existentes, reservas y consumos
no vacíos para comprobar no interferencia. Se comprobaron registro/reintento,
literalidad, rectificación, decisiones, revisiones, aislamiento, permisos y
concurrencia real en PostgreSQL; los recorridos reales incluyen escritorio,
móvil, teclado y respuestas demoradas al cambiar de organización. Resultados y
comandos completos, más pendientes de verificación independiente/revisión, en L10
del seguimiento. Capturas inspeccionadas; ninguna prueba sustituye aceptación humana.

Verificación final propia:213pruebas en PostgreSQL sin omisiones, incluidos los
casos concurrentes;8recorridos reales y build aislado satisfactorios. Verificación
independiente en copia temporal:10casos del módulo y5probes públicos, sin bloqueo
reproducido; paridad de respuestas legacy comprobada contra baseline. Los probes
de rechazo/ámbito/auditoría se incorporaron como regresiones y el módulo final
pasó14casos. Verificación independiente no equivale a revisión nativa aprobada.

Demo ficticia visible preparada en `http://127.0.0.1:5299/financiadores/novedades`,
con API y PostgreSQL propios de pruebas. Su disponibilidad es temporal; no es
producción ni aceptación humana. Estado al preparar la revisión: revisión nativa
pendiente; todavía sin nuevo commit de entrega ni publicación.

No hay migración, dependencia nueva, integración externa, cobro/pago ni ejecutor
de derechos. La deuda OSTEL de la tabla anterior sigue explícitamente excluida.
La entrega será un solo eslabón con excepción de tamaño elegida por el usuario;
no se autorizaron push, PR, merge ni deploy.

### Cierre técnico local verificado

El circuito genérico queda completo localmente: registro y consulta por
organización, originales preservados, comparación y conflictos explícitos,
conciliación sin aplicación o descarte motivados, rectificación por nueva evidencia
enlazada e historia persistida. Permisos, idempotencia, revisiones y concurrencia
fueron comprobados; no se conectó ningún ejecutor de derechos.

La revisión nativa concedida por el usuario terminó sin hallazgos en sus cuatro
miradas y se cerró mediante el acuse oficial. El commit de implementación
`bee25130b31cbe727e457e3855572350e0ee76d5` conserva exactamente el árbol revisado.
Este añadido posterior es únicamente registro documental del resultado.

Una auditoría adicional verificó paginación real con once propuestas ficticias,
filtros de estado/persona/organización, padrón intacto y recorrido de teclado sin
salir del diálogo. La demo visible es temporal y sólo contiene datos ficticios.
No constituye aceptación humana, homologación ni prueba de producción.

La tabla de deuda OSTEL anterior sigue vigente: no se interpretan reglas aún no
validadas ni se automatizan efectos prestacionales o financieros. Ese pendiente
no reabre el circuito técnico genérico ni se oculta como funcionalidad terminada.
No se publicaron cambios ni se ejecutaron CI, merge o despliegue en este cierre.


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

#### Decisión de acceso clínico confirmada, implementación pendiente

La bandeja declara no serializar historia clínica del caso. Sin embargo,
`SolicitudAutorizacionSerializer` (`api_autorizaciones.py:90–112`) ya devuelve
texto libre de `evidencia` dentro del circuito administrativo. Esto no prueba
que exista una filtración ni que ese texto contenga datos clínicos reales;
tampoco demuestra que ampliar ese campo a prescripciones sea seguro.
No se accedió a solicitudes o personas reales para este análisis.

Decisión confirmada por el usuario («confirmo»): **una futura prescripción clínica sólo será
visible para usuarios expresamente designados de Auditoría Médica; operación
y auditoría administrativa verán únicamente su estado administrativo**.
Ventaja: no concede acceso clínico por pertenecer al financiador. Costo: exige
un circuito diferenciado para revisión médica. Riesgo residual: aún deben
acordarse evidencia mínima, correspondencia de capacidades y trazabilidad de
accesos antes de implementar. La propuesta no modifica permisos ni el campo
actual. La aceptación proviene de esa confirmación específica, no de la autorización general de continuidad.

#### Cortes mínimos condicionados al contrato

1. Validar el catálogo/versionado y correspondencias PMO recibidos; sin equivalencias
   inferidas ni constantes regulatorias inventadas.
2. Con el acceso confirmado y tras acordar la evidencia mínima, especificar la prescripción y
   sus controles de lectura/corrección usando las capacidades existentes que correspondan.
3. Acordar usos/vigencias y vínculo con la prestación realizada antes de diseñar
   su relación con liquidaciones. No convertir una autorización en prueba financiera.

El acceso S17 está confirmado. Los restantes contratos son propuestas pendientes,
no una aprobación de reglas de prescripción o PMO para codificar. La información ya solicitada a OSTEL sigue pendiente; no se vuelve
a pedir que el usuario la solicite. T2/#143 y T3/#183 conservan sus límites.

Validación de este corte: lectura integral de #147, mapa CodeGraph y un spot check
de serializers/servicio; readback y enlaces/rutas existentes. No cambia código,
DB, UI, migraciones ni dependencias: RED/GREEN y pruebas funcionales nuevas no
aplican. Sin CI, despliegue, aceptación médica o conformidad normativa.
Rollback: retirar esta sección y el registro T6a del seguimiento, sin efectos en datos.

### Designación explícita de Auditoría Médica — T6b (02/11/2026)

La decisión S17 se implementa primero como **configuración de acceso por
financiador**, sin asignar personas reales ni inventar un registro de prescripción.
Existe una bandera separada `auditoria_medica`: denegada por defecto, también en
la base de datos. Ningún rol ni permiso previo se convierte automáticamente en
esta designación. La migración `0020_membresia_auditoria_medica` conserva los demás datos y asigna `False` al
campo nuevo; un escritor anterior que lo omite también queda sin designación.

#### Gestión y consulta de capacidad

- POST `/api/financiadores/{id}/usuarios/` acepta `auditoria_medica` opcional,
  siguiendo las convenciones booleanas existentes. Sólo un administrador activo
  propio del financiador, sin gobierno de plataforma en la identidad real,
  puede asignarla o revocarla. Se reutilizan lock de financiador, revalidación
  sensible y `auditar` en la misma transacción; no se crea otra API de concesiones.
- Omitir el campo conserva el valor guardado. `false` revoca explícitamente.
  GET `usuarios` y la respuesta POST agregan la bandera; las peticiones anteriores
  mantienen sus efectos y el texto anterior de auditoría. Una petición que
  incluye la bandera agrega su valor al motivo del evento de membresía.
- El alta del administrador inicial no acepta designaciones adicionales,
  incluso enviadas en `false`, ni toma una membresía previamente designada.
  No se admite otorgar Auditoría Médica a una cuenta de plataforma.
- La API de financiadores agrega `consulta_prescripciones` para el usuario
  actual: sólo `true` con usuario, financiador y membresía activos y la bandera
  explícita de ese financiador. Otro ámbito no hereda la designación.
  Plataforma —también como autor real de una identidad simulada— no obtiene
  la capacidad. Los identificadores ambiguos se deniegan en el helper.
- La designación es adicional al rol administrativo de la membresía. Un usuario
  con rol base `auditor` sólo es Auditoría Médica si fue designado expresamente;
  ese rol por sí solo no basta. La designación no habilita resolver solicitudes,
  salud/cobranza del padrón ni historia clínica general.

La administración T6b se entregó primero por API; T6c incorpora la gestión visual
descrita a continuación, sin cambiar el contrato de acceso.
El helper `requerir_consultar_prescripciones` queda preparado para exigir esta
capacidad en el futuro lector clínico. **No existe todavía ese endpoint ni
almacenamiento de contenido:** estas pruebas no demuestran visibilidad de una
prescripción real, validez médica o PMO. La designación no acredita matrícula ni
idoneidad; el responsable del financiador debe designar a las personas que correspondan.
No se alteran el campo `evidencia` ni los permisos de historia clínica existentes.

Pruebas focales: `test_auditoria_medica` sobre PostgreSQL dedicado (6 pruebas,
1.349 s); incluye migración `0019` → `0020`, conservación de campos, defaultDB para
escritor anterior, asignación/omisión/revocación/auditoría, no herencia,
roles/aislamiento/inactividad, bootstrap y plataforma. Regresión con
`test_padron130` y `test_permisos_plataforma`: 73 pruebas OK en 10.561 s. Resultados
independientes y límites posteriores en L35 del seguimiento.

Sin cambios de frontend: browser/build no corresponden a este corte backend.
No se asignan usuarios reales, ni se activan derechos o flujos normativos.
Rollback: preservar designaciones antes de revertir `0020` (se pierde la columna);
retirar la capacidad/API/guard de este corte, sin restituir acceso clínico
implícito ni cambiar los permisos previos de otros propósitos.

Verificación adicional T6b:225 pruebas independientes OK en 57.438 s, chequeo de
migraciones limpio y 44 observaciones anteriores equivalentes salvo los dos
campos nuevos declarados. Probes de rollback por fallo de auditoría,
revocación del administrador durante espera de lock, JWT real de simulación
plataforma y usuario cacheado desactivado en DB fueron incorporados a regresión.
Repetición focal: 10 pruebas OK en 3.613 s; suite padre: 77 pruebas OK en 14.565 s.

También pasó un escenario **HTTP real en loopback 8232**, exclusivamente con
un financiador y dos cuentas totalmente ficticios nuevos: denegado por defecto,
designación explícita, capacidades anteriores sin cambios, autodesignación
rechazada y revocación comprobada. La bandera de la cuenta ficticia quedó `False`.
Se aplicó `0020` sólo a la base local descartable autorizada; sin usuarios reales.
Fixture externa retenida `ostel-auditoria-http-u_1qlquo`, sin tokens en documentación.
No es un recorrido UI ni una prueba de lectura de contenido clínico.

### Gestión visual de la designación — T6c (02/11/2026)

En **Usuarios**, la administración real del financiador puede marcar o quitar
**Designar para Auditoría Médica de este financiador** al invitar una persona
o cambiar su acceso. La lista muestra la designación persistida. El rol base,
resolver autorizaciones y los bloques de padrón siguen siendo independientes.
El texto de ayuda distingue configurar acceso de consultar prescripciones:
este corte no almacena ni muestra contenido clínico.

Se reutilizan el formulario, POSTusuarios, errores, bloqueo de envío y consultas
por usuario/financiador existentes. Sin capacidad sensible explícita, el control
no se construye y el cuerpo no envía auditoria_medica; el alta inicial de
administrador permanece sin designaciones sensibles. El backend continúa siendo
la autoridad de permisos. Cancelar o cambiar organización no guarda el borrador.

Verificación: frontera real navegador→API→persistencia con fixture exclusiva
@example.invalid en PostgreSQL descartable y loopback. RED observado por control
ausente; GREEN escritorio/móvil: alta false, concesión por teclado, recarga,
cambio de rol sin perder designación, revocación y recarga. Auditoría administrativa
no accede a Usuarios; cancelación/cambio de organización no trasladan valores.
Un primer negativo esperaba incorrectamente Usuarios para auditor; la navegación
existente lo redirige a Inicio y se corrigió sólo esa expectativa del test.
Runner: SALUD_BORRADORES_MANIFEST=<fixture ficticia externa> node
node_modules/@playwright/test/cli.js test --config playwright.auditoria-medica-real.config.js
(desde frontend). No prueba contenido clínico, CI, despliegue ni aceptación humana.
Verificación independiente Sol/medium: cuatro recorridos reales OK, build del
candidato en scratch OK y dos probes negativos de UI OK. Diferencial contra
8e87731: ocho escenarios de alta/edición con capacidad falsa/verdadera conservaron
payloads, controles anteriores y errores, excepto el campo aditivo declarado.
Capacidad falsa/403 son inyecciones de UI, no pruebas reales de plataforma o bootstrap.
Probes incorporados a regresión: seis recorridos finales OK (12.5 s).
Capturas desktop/móvil inspeccionadas; demostración visible en Usuarios local
con cuentas ficticias, sin guardar una nueva designación. No equivale a aceptación.
Scratch externo ostel_t6c_verify_lbqlnvjc retenido. Puerto5192 ocupado preservado;
baseline propio5198 detenido con0listeners. API8232/frontend5189 conservados.
Rollback: retirar control, indicador y pruebas T6c; conservar API y designaciones T6b.
Risk: item2 (gestión de una designación sensible).

### Ingreso institucional confirmado — T6d (03/11/2026)

**Corte histórico:** la representación propuesta abajo quedó resuelta por S19
y la evaluación por S21; T6e–T6h documentan su implementación y prueba local.
La expresión «pendiente» de este contraste no describe el estado vigente.

El usuario confirmó que **la institución prestadora incorpora la prescripción
al solicitar autorización; Auditoría Médica la consulta y registra su evaluación**.
Se mantiene la visibilidad S17: operación y auditoría administrativa sólo estado,
sin conceder historia clínica general. La decisión confirma actores y momento,
no una representación ni un contrato de evaluación todavía inexistentes.

| Existente | Límite para este circuito |
| --- | --- |
| Solicitud institucional JSON (`api_autorizaciones.py:47–54`) | No admite prescripción; conservar lock, idempotencia, caso/afiliación/convenio y eventos de `autorizaciones.py:118–169`. |
| Archivo clínico privado y asociación Caso/Estudio (`common.py:363–576`, `registros/adjuntos.py:63–128`) | Permiso de historia clínica institucional; ni el upload ni su descarga son automáticamente un lector de Auditoría Médica por solicitud/financiador. El ID genérico del objeto no prueba pertenencia. |
| Receta de historia clínica (`registros/models.py:324–347`) | Registro de tratamiento distinto; no es por defecto el documento presentado a autorización. |
| Resolución observar/aprobar/rechazar y evidencia (`api_autorizaciones.py:337–340`) | No se redefine como opinión médica por cambiar el nombre de un campo. |

**Decisión material pendiente:** qué presenta la institución: adjunto privado
PDF/imagen (recomendado para conservar el documento recibido), vínculo a una
Receta clínica existente o captura específica de datos/texto. La elección define
qué se guarda y valida; no se tratará la justificación o evidencia libre actual
como prescripción. Tampoco se inventan campos normativos, plazos de retención
ni permisos de reemplazo. Una futura lectura exigirá aislamiento de solicitud y
financiador más el guard específico ya implementado; no acceso genérico a historia.

Contraste read-only con CodeGraph sincronizado y un spotcheck del upload común.
No se ejecutaron pruebas ni se modificaron código, DB, archivos clínicos o servicios.
No hay nueva prueba de visibilidad de contenido ni aceptación de #147.
La documentación y glosario registran S18; código pendiente de esta decisión.

### Adjunto privado con solicitud institucional — T6e (03/11/2026)

**Estado actual:** S20 autoriza la configuración privada simple de T6f descrita
abajo. La carga continúa fallando cerrada si se configura dentro de MEDIA_ROOT
o falta el alias dedicado. Configuración y API fueron verificadas localmente con archivos ficticios;
no se habilitaron documentos reales. El ingreso visual, aún ausente en ese corte,
quedó completado localmente en T6g y la resolución se verificó en T6h.

Formato confirmado por el usuario: **PDF/imagen privado**, no texto de
justificación ni enlace implícito a la historia clínica. El documento se recibe
junto a una nueva solicitud institucional y queda ligado a ella; no hay acción
de reemplazo/borrado ni obligatoriedad prestacional nueva. No cambia resolver.

| Interfaz | Contrato |
| --- | --- |
| `POST /api/autorizaciones-cobertura/con-prescripcion/` | Multipart: `caso`, `prestacion`, `intento`, `cantidad`, `justificacion`, `clave` y exactamente un archivo `prescripcion`. Sólo personal autorizado para operar el caso de la institución; plataforma y simulación de plataforma no sustituyen al presentante. |
| `GET /api/autorizaciones-cobertura/<id>/prescripcion/?financiador=<id>` | Solicitud visible de ese financiador, usuario/membresía/financiador activos y designación explícita de Auditoría Médica. Descarga autenticada, auditada estrictamente antes de transmitir, attachment/nosniff/private-no-store. |
| Bandeja/detalle administrativo | Sólo agrega `prescripcion_estado: presentada` si hay documento; no nombre, ruta, hash, contenido ni URL. Sin documento conserva exactamente los campos previos. |
| JSON institucional, manual, observar/aprobar/rechazar | Interfaces existentes conservadas; no se consideran registros de opinión médica por esta entrega. |

Se reutilizan `solicitar`, el lock de Caso, controles de afiliación/convenio/paso,
claves e historia. Misma clave y bytes devuelve el resultado previo; cambiar el
archivo o agregarlo retroactivamente con la clave de una solicitud JSON se rechaza.
Registro uno-a-uno separado (`0021`), sin migrar datos anteriores. La validación
común comprueba tamaño (máximo existente, por defecto10MiB), MIME, extensión y firma;
sólo PDF/JPEG/PNG/WebP, no texto ni SVG. No implica análisis antivirus ni validez médica.

Storage privado existente, sin proveedor/configuración nuevo ni URLs públicas.
Las claves opacas bajo `uploads/prescripciones/` son rechazadas por la descarga
clínica genérica, pero **ese prefijo no basta para garantizar privacidad**.
La revisión demostró que, con el storage local anterior dentro de MEDIA_ROOT,
`/media/x/../uploads/prescripciones/<uuid>.pdf` y la variante `%2e%2e` entregaban
el PDF ficticio anónimamente: el guard literal se ejecutaba antes de normalizar.
La carga ahora rechaza FileSystemStorage dentro de MEDIA_ROOT con503 antes de
cualquier escritura. Se necesita storage dedicado fuera de toda media pública. No se crea un
ArchivoClinico que habilite acceso más amplio. Se conserva el original binario,
no su nombre potencialmente sensible. La institución no recibe por este corte
un permiso nuevo de lectura del contenido en el servidor; conserva su fuente y
consulta el estado. No se amplía historia clínica ni designan personas reales.

Fallo en persistencia/auditoría revierte expediente/eventos/metadatos y compensa
únicamente el nuevo objeto almacenado. Si falla esa limpieza, se conserva el error
de la operación y no existe metadato que lo haga descargable por la API; requiere
atención técnica, sin borrar otros objetos. No hay política de retención inventada.

RED observado: nueva acción inexistente405; luego plataforma201 en lugar de403,
corregido con identidad real antes del ingreso. GREEN9casos nuevos y regresión
institucional/manual/designación:58pruebas OK16.705s, dry-migrations limpio.
Primer comando de regresión nombró erróneamente test_autorizaciones_manual
(singular, módulo inexistente); corregido sólo el comando a *_manuales y repetido.
Un negativo de financiador ajeno omitió rol en su fixture, causó403 en vez de404;
corregido sólo el rol explícito ficticio. Verificador independiente:58tests/dry-check y18observacionesHTTP previas
JSON/manual/bandeja/detalle/resolver equivalentes al baseline. Detectó además
campo desconocido ignorado y nueva FK de autoría sin clasificar: se corrigieron
sólo el serializer multipart y el registro de autoría nuevo. La clasificación
global sigue fallando únicamente por BorradorReglaDerechos.creado_por, idéntico
al baseline; no se presenta ese chequeo como verde ni se amplía el arreglo.
Recheck único focal: desconocidos400 sin mutación, FS público503 sin escritura,
FS privado fuera de MEDIA_ROOT201 y descarga médica200 con bytes exactos;
rutas anónimas directa/../%2e%2e404. Este override es sólo de prueba: no cambia
la configuración real. Probes incorporados a regresión,12tests padre3.296s OK.
Scratch externo ostel_t6e_verify_rkjmuv8k retenido. Al cierre de T6e aún no se había autorizado la configuración privada real;
S20/T6f resuelve esa autorización y su configuración se verifica por separado.
No nueva ronda del candidato anterior.
No es todavía una prueba HTTP/UI; no se declara completo el flujo visual.

Runner backend: PYTHON_DOTENV_DISABLED=1, ENTORNO=desarrollo,
DJANGO_SETTINGS_MODULE=config.settings_financiadores_postgres_test y
SALUD_TEST_POSTGRES_URL del PostgreSQL dedicado loopback, `manage.py test`
con test_prescripciones_autorizacion/test_autorizaciones/test_autorizaciones_manuales/
test_auditoria_medica, serial, `--keepdb --noinput`.
Rollback: retirar endpoints/servicio/estado nuevo y revertir0021 sólo tras preservar
metadatos y objetos; no perder documentos almacenados ni revertir autorizaciones.
Risk: items1 (persistencia),2 (documento clínico),4 (ingreso/idempotencia bajo lock).

### Almacenamiento privado simple — T6f (03/11/2026)

El usuario autorizó «entonces autorizo, manteniendolo simple». Se extiende la
fábrica existente: **no hay servicio, proveedor, bucket ni credenciales nuevos**.

| Entorno | Configuración de prescripciones |
| --- | --- |
| Disco local | Alias Django `prescripciones`, predeterminado `backend/privado/prescripciones`, fuera de `MEDIA_ROOT` y ya excluido de Git. Puede ubicarse en otro volumen mediante `SALUD_PRESCRIPCIONES_ADJUNTOS_DIR`; rutas relativas se resuelven desde backend. Si cae dentro de MEDIA_ROOT, configuración rechazada. |
| Bucket privado ya configurado | Mismo backend/opciones del bucket existente, prefijo `prescripciones/`. No se accede al proveedor en estas pruebas ni se cambian variables remotas. |
| Archivo | Sólo clave relativa opaca `<uuid>.<ext>` en la base; descarga por API con permiso y auditoría. No se publica URL de storage. |
| Infraestructura | Incluir la carpeta/prefijo en respaldo y restauración junto a los metadatos DB; en disco de un despliegue, requiere persistencia del volumen. Esta entrega local no certifica backup ni durabilidad de producción. |

Ingreso, compensación y descarga usan el mismo alias, nunca `default` como
fallback. Si falta, o es FileSystemStorage dentro de MEDIA_ROOT, devuelve503.
Los alias anteriores `default` y `facturas` y las llamadas de fábrica con dos
argumentos conservan sus resultados. Sin migraciones de documentos existentes,
limpieza masiva, cambios de `.env`, dependencias o configuración remota.

RED: argumento de configuración nuevo ausente en ambos modos de fábrica.
GREEN:8tests de configuración y13API,70regresión institucional/manual/designación
OK16.993s; dry-migrations limpio. Las opcionesS3 se validan sólo con valores
sintéticos y construcción del backend, sin conexión ni lectura de credenciales.
El primer ajuste de fixture apuntó desde backend a un path con prefijo backend
repetido: no editó archivos y causó pruebas con alias faltante503; se corrigió
únicamente el path del script y se actualizaron los overrides al alias dedicado.
Verificación independiente T6f PASS:70pruebas17.269s/dry-check limpio, dos
probes de configuración fría1.481s y seis modos de fábrica con stdout/stderr/exit
idénticos a9453288. Configuración predeterminada, absoluta y relativa válidas;
carpeta pública rechaza inicio. Sin override positivo de STORAGES: el alias nace
de settings reales en proceso nuevo, escribe un PDF ficticio fuera de media,
403 sin designación y200 con designación/auditoría/bytes exactos. Alias ausente
o público503 en lectura/escritura, sin archivo ni huella cambiada. Rutas anónimas
canónicas/normalizables404; escapes externos400 de safe_join, todos sin bytes.
Spotcheck padre de los dos probes1.476s OK. Regresiones incorporadas sin historia
Git ni paths fijos:22tests3.554s OK; configuración fría sin conexiones al proveedor.
Scratch externo ostel_t6f_verify__e1nbodc retenido. Dos ajustes del harness:
APITransactionTestCase evita cierre de conexión de FileResponse en APITestCase;
expectativa de escape externo corregida a400. Ningún cambio productivo posterior.
El chequeo global de clasificación ya conocido sigue pendiente sólo por la FK
BorradorReglaDerechos.creado_por preexistente; no se declara que pasó.
No browser/build aplicables a este corte backend; UI institucional/médica pendiente.
Risk: items2/5 (aislamiento y configuración); integra T6e1/2/4 sin ampliar permisos.

### Solicitud y descarga desde las pantallas existentes — T6g (03/11/2026)

La institución puede adjuntar **Prescripción (opcional)** al solicitar autorización
desde el caso. Se conserva el JSON anterior cuando no hay archivo; con archivo
se usa la acción multipart privada. Cancelar retira el archivo; un error no lo
borra ni dispara reintento automático. La misma presentación conserva su clave,
y cambiar archivo genera otra. No se agrega una obligatoriedad médica al circuito.

El detalle institucional/administrativo muestra **Prescripción presentada**,
sin enlace de contenido. Sólo el financiador con `consulta_prescripciones` explícita
ve **Descargar prescripción**, con nombre genérico. Ese indicador no sustituye el
permiso del servidor. No cambia resolver ni permite registrar un dictamen nuevo.
Ingreso/descarga reutilizan `api.multipart`/`api.download` existentes, sin tocar
el cliente compartido. Una referencia al contenedor DOM vigente y la identidad
solicitud/ámbito impiden entregar una descarga cuando su detalle ya fue desmontado.

Fixture persistente separada del runner Django: sólo PostgreSQL ficticio local,
settings exactos, salida temporal y usuarios únicos@example.invalid. Reutiliza
AutorizacionSetup sólo como construcción ORM (sin _pre_setup, flush o seedgeneral),
con códigos de catálogo únicos, clínico del área y lector médico sin membresía
institucional. Resolver de operación permanece distinto de la designación médica.
Un expediente se precarga para negativos de lectura; los positivos crean desde UI.
Los manifiestos y archivos privados quedan fuera de Git, sin imprimir credenciales.

RED real observado por ausencia del campo. GREEN propio:6recorridos15.2s,
escritorio/móvil, carga con respuesta201 y descarga200 de bytes idénticos,
contenido ausente para institución/operación, teclado, cancelación→JSON anterior,
rechazo403 inyectado sin descarga, respuesta real demorada descartada tras cerrar,
y respuesta perdida después del commit con reintento explícito de misma clave/
archivo/solicitud. Los negativos de transporte son inyecciones, no reemplazan
los positivos HTTP/PG/FS reales. El PDF positivo ahora se genera con jsPDF ya
instalado (sin nueva dependencia); repetición escritorio4.5s OK con PDF válido.
Independiente Sol/medium PASS: build3.62s,6recorridos reales16.2s y23checks
mock/diferencial/negativo20.9s; baseline5cee72c22checks19.4s. JSON/resolver/reenviar/
anular conservan cuerpo, ruta, ámbito y texto anterior, excluyendo sólo UUID
aleatorio y campo opcional declarado. Mock no equivale a persistencia/E2E.
Negativo adicional: doble clic produce1GET y cambiar al antecedente descarta la
respuesta anterior. Incorporado al test existente junto con regresión de anular,
sin duplicar su fixture ni leer Git desde tests;20regresiones mock padre19.2s OK.
Tres componentes productivos idénticos al snapshot del verificador; sin correcciones.
Capturas escritorio/móvil inspeccionadas por padre; diálogo desplazable, botón
legible y sin desborde horizontal. Demo visible local62061, financiador ficticio13,
lector médico sin permiso de resolver y PDF válido listo para descargar. No aceptación.
Los procesos mock propios del verificador en5198 se detuvieron con0listeners;
un arranque de baseline encontró su candidato todavía vivo y se corrigió sólo
la identificación/terminación de ese proceso. Padres5189/8232 preservados.
Scratch externo ostel_t6g_verify__s2hd0ro retenido; ninguna configuración remota.

Ejecución: preparar un escenario nuevo con `preparar_prescripciones_autorizacion.py`
bajo settings PostgreSQL dedicados; pasar su manifiesto como
`SALUD_PRESCRIPCIONES_MANIFEST` a
`node node_modules/@playwright/test/cli.js test --config playwright.prescripciones-real.config.js`.
Cada ejecución positiva usa un manifiesto nuevo; no elimina expedientes previos.
No equivale a despliegue, aceptación humana ni validación médica del documento.
Risk: items2/4 (visibilidad sensible y respuestas asíncronas).

Límite de privacidad: este almacenamiento protege las prescripciones nuevas;
no migra ni endurece los demás adjuntos de `default`/MEDIA_ROOT. La ruta estática
de desarrollo preexistente y su normalización necesitan tratamiento separado;
no se afirma privacidad global de otros archivos ni se inspeccionaron archivos reales.

El runner de prescripciones es explícitamente manual: no hereda el arranque del
escenario de importación aunque exista SALUD_IMPORTACION_E2E_AISLADO=1.
RED de configuración observado, guardia y regresión importada137ms OK; lectura
negativa UI1.6s y spotcheck de respuesta demorada1.8s OK. No se ejecuta el importador
ni se modifican sus configuraciones. Los servidores/fixture se preparan por separado.

### Evaluación médica y resolución de la solicitud

Decisión del usuario (03/11/2026): «aprobar/rechazar la solicitud». No se agrega
un dictamen paralelo: la evaluación utiliza la resolución existente, con su
revisión, motivo, evidencia, cantidad/vigencia cuando corresponde e historial.
La aprobación no registra una prestación realizada ni crea un cargo.

La configuración existente permite asignar por separado a un miembro operador
la designación de Auditoría Médica y el permiso de resolver autorizaciones.
Ambos deben asignarse explícitamente; consultar la prescripción no concede
resolución. El rol genérico auditor sigue siendo de lectura. Los resolutores
administrativos existentes conservan su permiso, pero no acceden al documento.
Este corte no impone aprobación médica exclusiva ni criterios PMO automáticos.
No copiar contenido clínico reservado en motivo/evidencia compartidos: usar
referencias administrativas de la revisión, conservando el original privado.

La comprobación inicialmente bloqueada por Docker quedó completada (T6h/L42).
API: ambas designaciones y revocación independiente, lector sin resolución403
sin cambios persistidos, aprobación/rechazo de la misma solicitud, reintentos sin
duplicación, historial/revisión y ausencia de atención/cargos/reservas nuevas.
Tres regresiones1.361s y suite65pruebas23.462s OK; refuerzo focal2pruebas1.885s.
No cambia el código productivo: son caracterizaciones del contrato existente,
sin RED artificial ni nuevo motor, rol o autorización implícita.

Navegador real: escritorio/aprobación y móvil/rechazo24.3s, PDF descargado por
teclado con bytes exactos, consulta institucional posterior con estado terminal,
lector médico sin resolución y resolutor administrativo sin contenido clínico.
Siete pruebas anteriores19.6s OK. El nuevo recorrido no intercepta respuestas
positivas: usa API/PostgreSQL/almacenamiento privado ficticios. Los negativos
de transporte de la suite anterior mantienen sus inyecciones explícitas.
Capturas de ambas resoluciones inspeccionadas; demo visible con solicitud
ficticia aprobada y descarga médica disponible. No aceptación humana ni despliegue.
Se conserva el permiso administrativo anterior; no se exige revisión médica
exclusiva como una nueva regla de negocio. Sin cambios productivos, build o
diferencial de contratos compartidos no aplican. Risk: none.

## Pendientes consolidados para continuidad — 03/11/2026

Este estado consolida los avances posteriores a las secciones históricas. T6b–T6h
completan localmente designación, ingreso privado, descarga y resolución de la
misma solicitud; no sigue pendiente decidir su representación ni crear otro
dictamen. Esto no completa el contrato clínico/PMO de #147 ni acredita aceptación.

| Tema | Ubicación de seguimiento | Pendiente real / condición de cierre |
| --- | --- | --- |
| Identidad/familias | #181, #142 | Homologación de equivalencias no confirmadas y aceptación operativa del contrato implementado; sin autofusión ni inferir familia por NROAFI. |
| Derechos | #143 | Fuente validada, causales, fechas, gracia, mora, bajas y excepciones; implementar aplicación operativa sólo con reglas aprobadas. Configurar/simular ya funciona sin cambiar derechos. |
| Novedades | #183 | Completar circuito bajo contrato de derechos, con evidencia, historia y aislamiento; ausencia de registros no produce baja. |
| Autorizaciones médicas | #147 | Validar criterios clínicos/PMO, evidencia mínima, vigencias, conservación/reemplazo y aceptación OSTEL; no inferir aprobación médica exclusiva ni criterios automáticos. |
| Aportes/recaudación | #144 | Esperar respuesta OSTEL: layouts/versiones y reglas de identificación, conciliación, imputación y reversas. No confundir declarado con dinero recibido. |
| Cuenta corriente/cuotas | #145 | Esperar respuesta OSTEL: cálculo de cuota/diferencia, saldo, vencimiento, canales, rendiciones y emisión fiscal. Registro manual alternativo rechazado por el usuario. |
| Liquidaciones | #149 | Acordar contrato de liquidación a prestadores y casos verificables; no sustituirlo por cuentas hospitalarias existentes. |
| Reintegros médicos | #148 | Acordar circuito/evidencia y contrato; distinguir reintegro médico de devolución financiera. |
| Tesorería/contabilidad | #153 | Definir contratos y trazabilidad ligados a eventos financieros; dependiente de los frentes anteriores, sin pagos reales. |
| Intercambio SSSalud | #146 | Sólo si se confirma necesidad operativa y layout oficial; no inventar un formato. |
| QA funcional | #184, #185 | PR196 incorporado, no aceptación integral; completar integración de módulos y aceptación humana sin equiparar pruebas locales con homologación. |
| Coordinación/entrega | #141 | Revisar/publicar por unidades, CI observado, cierre de pendientes y autorización separada de merge/deploy; no cerrar issues por tests verdes. |

### Deudas técnicas y de seguimiento — #185

- **DT1 — Media anterior:** reproducir sólo con archivos ficticios el acceso anónimo
  por normalización de rutas en desarrollo; endurecer sin romper descargas
  autorizadas. Los documentos nuevos usan almacenamiento privado separado;
  no se inspeccionaron adjuntos reales ni se afirma protección global.
  Saneamiento local: reproducido y corregido; detalle y límites abajo. Pendiente
  revisión nativa del cambio; verificación independiente/diferencial completada.
- **DT2 — Clasificación de autoría:** corregir la clasificación pendiente de
  BorradorReglaDerechos.creado_por y comprobar la prueba global correspondiente.
  Es un fallo preexistente conocido, no queda oculto por las suites focales verdes.
  Saneamiento local: clasificación global y regresión pública ahora pasan;
  verificación independiente/diferencial completada y revisión nativa pendiente,
  sin backfill de autoría.
- **DT3 — Estado documental:** resúmenes T6a–T6g reconciliados con S17–S21/T6h;
  conservar el Log histórico y verificar que futuras transiciones actualicen el resumen.
- **DT4 — Recuperación de seguimiento:** archivo local íntegro; espejo completo de
  memoria pendiente por límite de capacidad. Resolver sin truncar ni perder la
  versión anterior; no declarar sincronización si no se verificó el contenido completo.
  Recuperación soportada local: fragmentos JSON verificables y manifiesto de
  concatenación/SHA256 bajo el tema de memoria
  `odd/ostel-operacion-integral/saneamiento-20261103/mirror`;309 se conserva histórico.
- **DT5 — Revisión nativa:** varios cortes carecen de revisión completada por el
  impedimento registrado. No fabricar aprobación, repetir reportes/declines,
  reusar linajes consumidos ni modificar el modo global. Cerrar sólo mediante
  una recuperación soportada; si no está disponible, declarar el límite.
- **DT6 — Integración y entrega:** reunir prueba integral proporcional y CI del
  corte publicado; mantener separados commit/PR, CI, despliegue y aceptación.
  Deploy e infraestructura remota requieren autorización específica.

### Continuidad genérica sin información nueva de OSTEL

Analizar, estudiar y planificar capacidades reutilizables por otras obras sociales,
partiendo de lo existente y explicitando dependencias, reglas pendientes y pruebas.
Esta autorización de planificación no habilita nuevos modelos de negocio, tasas,
layouts, cobros, pagos ni efectos asistenciales. No reabrir la alternativa manual
de aportes rechazada. La espera específica #144/#145 sigue vigente; el saneamiento
técnico no depende de que OSTEL responda.

### Saneamiento DT1 — barrera de media DEBUG (03/11/2026)

Reproducido con PDF ficticio: la ruta literal clínica devolvía404, pero rutas
normalizadas devolvían200 y los mismos bytes. El bloqueo ahora compara el destino
resuelto con MEDIA_ROOT/uploads antes de delegar a Django. Cubre alias de separadores,
mayúsculas y nombres Windows, sin sustituir el guard de la descarga autenticada.
No migra archivos ni endurece buckets, proxies o servidores externos.

Regresión persistente:13variantes anónimas404; archivo/metadatos/auditoría sin cambios;
media pública normalizada y condicional304 preservada; descarga clínica autorizada
con bytes exactos y auditoría. Suite propia de archivos/prescripciones24OK; verificador
independiente en snapshots aislados confirma diferencial sin cambios no solicitados.
Rollback acotado: wrapper/ruta DEBUG y su nueva regresión; revertirlo REINTRODUCE
la exposición anónima observada. Risk: items2/3. No publicar sin autorización.

### Saneamiento DT2 — autoría de borradores (03/11/2026)

Clasificación global y POST simulado reprodujeron el mismo defecto: el campo
BorradorReglaDerechos.creado_por no pertenecía a CAMPOS_AUTORIA y guardaba la
cuenta de referencia, no a quien actuó. Una entrada reutiliza el pre_save existente;
sin migración, backfill, cambios de membresías ni activación de derechos.

Regresión por API: historial/autoría real, evento y operación simulada, aislamiento,
reintento sin nuevas versiones y contexto limpio; fuera de simulación conserva autor.
Suite propia de simulación/borradores71OK. Integración independiente95OK y repetición
padre95OK tras incorporar variantes/invariantes a las regresiones. Diferencial contra
ee390819: sólo cambian el acceso anónimo indebido y el autor simulado incorrecto.
No hubo UI nueva ni recorrido browser en este corte backend; no repetir pruebas de UI
históricas como si fueran actuales. Advertencia no bloqueante:staticfiles local ausente.
Rollback: entrada de clasificación y nueva regresión; vuelve el defecto de atribución
y el fallo global. Risk: items2/3; revisión nativa todavía no aprobada.

### DT6 — evidencia de entrega, no publicación del saneamiento

PR208 OPEN/DRAFT en HEAD documental9f2d76e. Frontend/OpenAPI/portal real/UI interceptada
SUCCESS; finanzas FAILURE al cargar familia-ostel-real.spec.js sin SALUD_FAMILIA_MANIFEST;
backend todavía IN_PROGRESS en la última consulta. El fallo de finanzas ocurre antes
del recorrido de familias: no prueba un defecto financiero, pero CI NO está verde.
El config de importación incluye esa prueba y el workflow sólo prepara el manifiesto
de importación. Corregir su preparación/separación de runners requiere otra unidad
acotada de tooling; no se cambia ni se excluye silenciosamente un test en este corte.
Estos fixes locales no están en ese PR; no acreditan CI propio, merge, deploy ni
aceptación humana. Revisión histórica DT5 sigue pendiente de binding/recuperación
soportados, sin repetir reporte/decline ni tocar proveedor/global.

### DT6a — preparación combinada de CI autorizada (03/11/2026)

Con S26, `python tests/importacion_real.py preparar` prepara ahora importación
y familias mediante las dos fixtures existentes, en la misma base efímera del job.
Familias usa una carpeta temporal propia derivada del directorio de importación:
`ostel-familia-ui-<nombre-del-directorio-importación>/manifiesto.json`.
El workflow exporta SALUD_FAMILIA_MANIFEST con ese destino antes de ejecutar
Playwright; ambas suites siguen seleccionadas, sin skip ni testMatch reducido.

La preparación rechaza directorios existentes y la base existente antes de sembrar.
La limpieza valida los dos manifiestos antes de borrar cualquiera; elimina sólo
sus credenciales ficticias y conserva XLSX, directorios y PostgreSQL. No cambia
la CLI preparar/servidor/limpiar ni los guards locales y de entorno anteriores.

RED público: faltaba el tercer subprocess de preparación y la limpieza ignoraba
un manifiesto familiar ajeno. GREEN:11regresiones del runner, incluidas preparación
de ambas fixtures/entorno aislado, directorio familiar ocupado y limpieza acotada
idempotente. Son pruebas con fronteras subprocess/PG simuladas, NO un job CI real.
El servicio local autorizado ya contiene la base dedicada: no se resetea para
forzar el arranque de CI; frontend/node_modules ausente, sin instalar dependencias.
Verificación independiente/diferencial completada sobre la orquestación y sus
guards, con fronteras externas simuladas. Se corrigió un defecto hallado por
el verificador: un directorio familiar enlazado podía redirigir la limpieza si
no se proporcionaba SALUD_FAMILIA_MANIFEST. Ahora se rechaza el destino resuelto
distinto antes de borrar cualquiera de los archivos. Regresión RED→GREEN y
rechequeo real de enlaces Windows: ambos hashes conservados, cero conexiones DB.
Suite final12OK sin skips y spotcheck padre aprobado. CI remoto de estos cambios
requiere publicación autorizada; revisión nativa DT5 no se da por aprobada.
Rollback: retirar orquestación/manifiesto familiar del runner/workflow y sus
regresiones reintroduce el fallo de descubrimiento de familias. Risk:items2/5.

### DT6b — staticfiles en pruebas de prescripciones (03/11/2026)

**Estado vigente04/11:** regresión clínica local completada con PostgreSQL y
STATIC_ROOT poblado:25pruebas OK. El bloqueo de entorno descrito abajo es histórico;
no equivale a CI remoto, despliegue ni aceptación integral.

Con S27 se conserva el alias staticfiles configurado al reemplazar STORAGES
en las pruebas, incluidos sus overrides negativos. No se cambia almacenamiento,
middleware ni configuración productiva. Los aliases clínicos que cada negativo
omite siguen ausentes: no se mezclan todos los storages originales.

Causa reproducida: con archivos de nombre versionado presentes en STATIC_ROOT,
WhiteNoise consulta staticfiles_storage al inicializar su caché. CI los genera
con collectstatic, pero local no tenía esa carpeta; por eso las suites anteriores
no mostraron el error. La nueva regresión comparte fixture con la clase clínica,
realiza GET real de CSS ficticio versionado y comprueba bytes idénticos200
con ambos aliases clínicos y faltando cada uno. La ausencia intencional produce
InvalidStorageError para ese alias; no se suprimen middleware ni validaciones.

RED observado: mismo InvalidStorageError de staticfiles que CI, sin crear ni abrir
DB. GREEN: regresión estática sin DB, tres variantes de fixture. No se ejecutó
la suite clínica completa en el corte03/11: PostgreSQL dedicado en53474 agotaba connect_timeout3;
Docker CLI devolvióHTTP500. La prueba inicial que esperaba DB fue interrumpida.
No se reinicia Docker ni se alteran contenedores, puertos, datos o dependencias.
Estado parcial hasta recuperar ese entorno y repetir la suite; CI remoto no
acreditado, cambios sin publicar. La fixture de turnos permanece fuera de S27.
Rollback: revertir sólo fixture y nueva regresión reintroduce el error de estáticos
en pruebas; no cambia comportamiento productivo. Risk:none (sólo pruebas).

Reintento04/11: Docker ya respondía, pero el contenedor dedicado estaba detenido.
Se inició sólo ese contenedor tras verificar imagen y binding loopback, sin
reiniciar Docker/global ni crear/resetear bases o contenedores. Puerto activo64010;
suite de prescripciones y regresiones de descarga/media25OK4.745s con estáticos
ficticios versionados en temporal externo. Esto verifica también los negativos
clínicos antes bloqueados; no altera la fixture de turnos ni publica estos fixes.

### DT6c — inicios de turnos ficticios sin colisión de calendario (04/11/2026)

Con S28 se corrige sólo la generación de nuevas citas en seed_ostel_demo.
Los desfases por prestador/práctica no bastaban: al saltar fines de semana,
el mismo paciente podía obtener el mismo inicio en dos agendas. El fallo depende
del reloj: se reprodujo con miércoles07local, no con martes07 ni horario normal.

La fixture conserva los desfases y utiliza proximos_libres/reservar existentes;
recuerda los inicios ya elegidos por documento ficticio y escoge el primer candidato
compatible. Solicitar un candidato más que los inicios ya usados permite elegir
sin un número arbitrario de reintentos. No se cambian guardas, bloqueos, motor,
JSON/CLI, derechos o criterios clínicos. Repetir un escenario existente no migra
ni reprograma sus citas; los datos anteriores se preservan.

Prueba pública determinista RED→GREEN:12reservas futuras y repetición inmutable.
Suite demo16OK; diferencial contra f14b747: a14local se conservan las reservas,
cantidades y estructura JSON; a07local sólo una cita cambia, manteniendo las12
y eliminando el inicio duplicado. Son pruebas PostgreSQL ficticias bajo TestCase,
no una siembra manual sobre una demo o base operativa.

Integración de ocho módulos saneados124OK35.891s, sin skips, con estáticos externos
y PGdedicado. No sustituye ejecución de CI remoto, navegador o aceptación humana.
El PR208 anterior continúa con backend/finanzas rojos y no contiene estos fixes;
publicar/mergear/desplegar requiere autorización separada. Revisión nativa histórica
DT5 sin cierre, sin alterar proveedor/global. Rollback: retirar el filtro local
y la regresión de reloj reintroduce las colisiones de la fixture, no cambia el motor
de reservas. Risk:none (datos ficticios nuevos, contratos y guardas intactos).

## Aceptación y publicación de Novedades — 05/11/2026

El usuario aceptó el circuito técnico genérico y autorizó commit, push, PR, merge y despliegue sobre la demo existente. La deuda normativa pendiente se sigue por [#219](https://github.com/Mkdir-arg/SistemaDeSalud/issues/219), dependiente de #143. #183 conserva la trazabilidad del cierre genérico; su movimiento a QA no homologará efectos OSTEL.

La integración sobre main72b2533 conserva borradores de derechos y simulación de plazos, además de Novedades. Verificación independiente sobre árbol staged inmutable:270pruebas PostgreSQL/15módulos, cero omitidas; paridad del listado legacy en cuatro filtros; spotcheck del padre correcto. Build aislado correcto. Sin cambios de esquema ni seeds remotos. Publicación/CI/merge/despliegue se registrarán separadamente cuando se observen.

La primera CI de PR#220 detectó una colisión de identificadores OpenAPI entre listado y detalle. Se documenta el listado con identificador explícito y regresión; no cambia las rutas ni los efectos administrativos. La prueba local reprodujo el fallo antes de corregirlo.

## Familias: integración selectiva y homologación pendiente — 05/11/2026

- El corte de privacidad oculta CODPAR en las respuestas administrativas v3, incluidas las incrementales y la tabla de revisión. La fuente persistida conserva sus40columnas y la copia de salud protegida; v1/v2 y la huella no cambian.
- Procedencia: #214 y #221, con CI verde antes de integrar a continuidad. Se trasladan sólo los hunks de Familias sobre main, preservando las pruebas y fuentes de Novedades. El candidato de main requiere su propio CI antes de merge/deploy.
- Aceptación técnica local registrada, sin equivaler a homologación OSTEL. Siguen pendientes identificador estable/visible, equivalencias TIPODOC/CODPAR/NROREF y aceptación operativa con las fuentes aprobadas ya solicitadas en #142/#181. No inferir vínculos de NROAFI ni activar derechos.
- Seguimiento de integración/deploy y separación de tareas: `odd/tasks/familias-cierre.md`. La nueva tarea de continuidad conservará los criterios normativos pendientes; la original pasa a QA sólo por el corte técnico explícito.

## Escenarios NROREF tras la aclaración OSTEL — 06/11/2026

Fuente: respuesta OSTEL documentada el 06/11 en #142 y #181. NUMERO identifica
el registro interno y se conserva en reingresos/cambios de empresa; NROREF
referencia el NUMERO del titular, con excepciones históricas. No confirma el
número visible, los catálogos completos ni la precedencia ante discrepancias.

Plan implementado: conservar los 27 escenarios anteriores sin cambiar valores
ni orden y agregar cuatro casos independientes mediante los helpers existentes.
El catálogo actual tiene 31 escenarios. Ninguno confirma vínculos ni derechos.

| Escenario nuevo | Evidencia ficticia preservada | Límite |
|---|---|---|
| `nroref_numero_coherente` | Titular NUMERO/NROREF `000001`; familiar NUMERO `000002`, NROREF `000001` y CUILTIT coherente | Los ceros no se pierden; NROAFI sigue siendo otro campo |
| `nroref_numero_ausente` | Una fila refiere al NUMERO y CUIL de un titular ausente del lote | No inventar titular ni inferir inexistencia global |
| `nroref_numero_ambiguo` | Dos identidades distintas tienen NUMERO `000001`, referenciado por una tercera | Dato inconsistente de revisión, no permiso para elegir o fusionar |
| `nroref_cuiltit_discordantes` | NROREF apunta al NUMERO de una fila; CUILTIT al CUIL de otra | No corregir el original ni decidir cuál prevalece |

Verificación local: un RED por cada caso ausente y su GREEN posterior; suite
completa `python -B -m unittest apps.financiadores.tests_ostel_scenarios -q`
aprobada, incluyendo lector real, round-trip XLSX de ambas hojas y exportación
con manifiesto. Contraste externo contra main af5cc9b: los 27 casos previos,
su orden, columnas, hojas y errores de ancho permanecen iguales. No se agregan
tests que dependan de git history ni archivos generados al repositorio.

Sin cambios en lector/importador, resolver CUILTIT→CUIL, API/UI, permisos o
persistencia. No se ejecutaron pruebas API/DB, suite global de backend, CI ni
deploy en este corte; no requieren levantar un entorno local para comprobar el
contrato del generador. No se afirma que producción ya envíe discrepancias a
una auditoría nueva: estos casos sólo preparan evidencia para su futura revisión.

#223 puede separar la semántica recibida de número visible, catálogos,
excepciones, precedencia y aceptación operativa pendientes. No se actualizó el
issue ni su estado mediante este corte local. Risk: none.

### Caracterización de límites financieros — 04/11/2026

Solicitud: «implementa el proximo corte recomendado». Corte local basado en
`8a3a1d8b87a25380c85e15519fc0683f09ef6c49`, limitado a pruebas y esta evidencia;
sin cambios productivos, contratos nuevos ni cierre funcional de T7–T11.

`backend/apps/financiadores/test_limites_financieros.py` reutiliza `CoberturaSetup`,
los servicios actuales de reserva/atención y `registrar_movimiento`. Dos financiadores
ficticios tienen planes, afiliados con identificadores repetidos entre ámbitos y
borradores no operativos. La base de comparación contiene cobertura y documentos
existentes, dos obligaciones hospitalarias de 20 y 80 y un movimiento de 5, todos
ficticios: no son tasas, cuotas ni importes propuestos para OSTEL.

| Interfaz observada | Resultado comprobado |
| --- | --- |
| PATCH de cobranza protegida | Cambia únicamente el bloque declarado, su revisión/historial y el evento de auditoría esperado. Declarar deuda no modifica derechos, cobertura ni dinero. |
| POST/PATCH de factura documental | Crea/edita únicamente el documento y su evento. Conserva el documento del otro financiador y no genera obligaciones ni movimientos. |
| POST de factura duplicada | HTTP 400; documentos, historial y dominio financiero/asistencial comparado intactos. |
| Acceso/edición y vínculos cruzados | HTTP 404/400 según el contrato existente; sin efectos persistidos en ninguno de los financiadores. Incluye cobranza protegida y vínculos de convenio/afiliado. |

Las instantáneas comparan valores completos y ordenados de todos los modelos de
`finanzas` y `financiadores`, no sólo sus conteos. Los eventos anteriores permanecen
idénticos y se comprueba el evento nuevo exacto en las operaciones exitosas. No se
afirma cobertura de tablas clínicas externas a esas aplicaciones ni de concurrencia
nueva. No hay RED artificial: es caracterización de comportamiento ya implementado.

Verificación local sobre PostgreSQL 16 descartable propio, en loopback y tmpfs,
mediante Python 3.14 ya disponible. Lanzador externo con entorno saneado y carga
de dotenv deshabilitada antes de importar settings; sin leer `.env`, credenciales
existentes ni bases operativas. No se agregaron dependencias ni se cambiaron settings.

- Focal: `python -B manage.py test apps.financiadores.test_limites_financieros
  --settings=config.settings_financiadores_postgres_test --noinput`: 4 pruebas OK.
- Regresión conjunta: el módulo nuevo más `apps.financiadores.test_facturas`,
  `apps.financiadores.test_padron130`, `apps.financiadores.test_cobertura`,
  `apps.financiadores.test_uso_autorizaciones`, `apps.financiadores.test_borradores_api`
  y `apps.finanzas.test_dinero`, con los mismos settings: 167 pruebas OK.
- Advertencia preexistente: carpeta `backend/staticfiles/` ausente; sin fallo de
  pruebas. Los rechazos HTTP y errores inyectados de las regresiones son esperados.
- Evaluación nativa del corte: medium/under_budget, revisión no debida; sin START
  ni aprobación nativa. `.atl/` preexistente excluido de la selección.
- Limpieza: el intento automático del 04/11 fue bloqueado; las bases de test sí
  fueron eliminadas por el runner. El 05/11, con autorización explícita de los tres
  puntos de cierre, se verificó la identidad del contenedor propio y el contenido
  exacto de la carpeta temporal. Se detuvo/eliminó `salud-finanzas-corte-01a1a7cc`
  y se retiró únicamente `salud-finanzas-characterization-01a1a7cc/run.py` y su
  carpeta vacía; sin tocar otros recursos ni saneamiento.
- Sin build ni navegador: no cambia producto ni interfaz visual. Sin CI remoto,
  publicación, merge, deploy ni aceptación humana. La evidencia no homologa aportes,
  saldos, liquidaciones, reintegros médicos, tesorería ni intercambio oficial.

Se conserva S22: #144/#145 esperan la respuesta OSTEL ya solicitada, sin registro
manual alternativo. Los contratos de #149/#148/#153 y la condición de #146 siguen
pendientes. Risk: none (sólo pruebas y documentación; interfaces productivas intactas).

Reversión del corte: retirar exclusivamente `test_limites_financieros.py` y esta
sección documental. No hay migraciones, datos operativos ni cambios productivos
que revertir. La validación del 04/11 es evidencia local histórica, no CI remoto.

Integración sobre `main` (06/11/2026): el PR #212 apuntaba a la rama de continuidad
`juanikitro/salud-continuidad-generica-20261103`, cuyo corte `8a3a1d8` es anterior a
los fixes de CI ya integrados en `main` (`3a7bf96`, alias `staticfiles` en
`test_prescripciones_autorizacion`; `dbffea3`, fixture de familias del runner OSTEL).
Esa base vieja explicaba los fallos remotos de los jobs `test` y Finanzas. Este corte
se rebasó solo sobre `main`: no depende de `8a3a1d8` (usa únicamente `CoberturaSetup`),
por lo que las pruebas G2a de esa base y su sección documental siguen fuera de `main`
y de este PR. La mención a `test_borradores_api` en la regresión del 04/11 refiere a
esa base histórica.

Verificación del 06/11/2026 sobre `main` más el corte:
- Local (SQLite): `test_limites_financieros`, `test_prescripciones_autorizacion`,
  `test_cobertura`, `test_facturas` y `finanzas.test_dinero`: 108 pruebas OK y 5 skips
  de concurrencia propios de SQLite.
- CI remoto del PR #212: pasaron `test` (suite completa de backend), Finanzas con
  navegador, Django y PostgreSQL 16, Frontend, Esquema OpenAPI y App del paciente.
- Operativa de CI: después del force-push y del cambio de base a `main`, GitHub no
  creó corridas para el commit nuevo. El push llegó con la base anterior todavía
  configurada, y el cambio de base (evento `edited`) no dispara los workflows. Se
  dispararon cerrando y reabriendo el PR (evento `reopened`).

Pendiente fuera de este PR: el commit `8a3a1d8` de la rama de continuidad
`juanikitro/salud-continuidad-generica-20261103` no está integrado en `main` y no
tiene PR propio. Contiene las pruebas G2a de `test_borradores_api.py`,
`frontend/e2e/borradores-derechos-real.spec.js`, su sección de este documento y el
avance en `odd/tasks/ostel-operacion-integral.md`. Ni #212 ni #213 lo necesitan.
Integrarlo o descartarlo es una decisión del usuario y queda abierta.

## Decisión explícita de cobertura desde una novedad — API Derechos

Conciliar conserva su contrato: registra una decisión administrativa y
`efectos_aplicados` permanece en `false`. La acción separada
`POST /api/financiadores/{id}/novedades/{novedad_id}/habilitacion-cobertura/`
recibe `revision`, `revision_padron`, `cobertura_habilitada` y `motivo`.
El booleano se elige explícitamente; ningún código o fecha informada lo decide.
Habilitar no reactiva una afiliación finalizada ni garantiza una prestación.

La acción exige novedad conciliada, organización y afiliado coincidentes, permiso
actual de escritura y ambas revisiones vigentes. Antes de una aplicación nueva,
rechaza si el padrón cambió desde el snapshot original, la fuente/referencia se
repite o el antecedente ya fue rectificado. Un rechazo no deja escrituras parciales.
Reconoce primero el reintento idéntico aplicado: ni una rectificación posterior
ni una nueva edición del padrón provocan que ese reintento vuelva a aplicar efectos.
Una solicitud diferente sobre la misma decisión se rechaza.

Reutiliza `editar_ficha` para validación, permisos y auditoría. Cuando cambia el
booleano, `HistorialAfiliacion.lote` enlaza el evento a la novedad y conserva autor,
motivo y valores anterior/nuevo. Un no-op devuelve `sin_cambios` sin inventar una
transición. Rectificar crea otra novedad; no reescribe la evidencia de la original.
El lock del financiador usa `NO KEY UPDATE`, compatible con el `KEY SHARE` de la
FK de auditoría durante una edición concurrente del padrón.

Las evaluaciones futuras consumen el booleano existente. No cambian reglas de
cobertura, fechas, planes, familias, autorizaciones, reservas ni hechos históricos.
No se agregan modelos ni migraciones. No se activan reglas de borrador.

### Verificación de la API

- Focal final: `test_novedades` y `test_habilitacion_cobertura`, 33 pruebas,
  resultado OK con 5 skips de concurrencia SQLite; repetido por el orquestador.
- PostgreSQL 16 dedicado: 15 pruebas iniciales de novedades/padrón; tras corrección,
  5 de novedades, incluida la concurrencia con PATCH. Recheck independiente del
  caso: PATCH 200, acción 400, sin deadlock.
- Probes públicos independientes: conflictos/rectificación rechazados con 400 y
  hash persistido intacto; replay 200 sin escrituras tras edición y rectificación.
- Diferencial de APIs previas aprobado, salvo campos opcionales nuevos y timestamps.
- Suite completa candidata/base: mismos 1 fallo y 3 errores; no está verde.
  Causas verificadas: manifest estático de admin, dos pruebas PostgreSQL ejecutadas
  contra SQLite y orden de reglas en historial de borradores. No se corrigen aquí.
