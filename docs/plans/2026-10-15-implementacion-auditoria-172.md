# Plan de implementación de la auditoría #172

Estado: **implementación en curso; commits y apertura de PR autorizados**, con evidencia por corte en los apartados de avance. Fecha: 15/10/2026. La incorporación y producción siguen separadas. Los apartados históricos conservan las autorizaciones y resultados de su momento; el último corte prevalece para el estado actual.

## Objetivo y alcance

Cumplir las 54 acciones de la [auditoría #172](https://github.com/Mkdir-arg/SistemaDeSalud/issues/172): confirmar o refutar los escenarios, corregir los defectos reproducidos, conservar las garantías existentes y demostrar seguridad, integridad, recuperación y capacidad frente a objetivos acordados.

Una acción puede terminar corregida y validada, refutada con evidencia, conservada y validada o con riesgo residual aceptado explícitamente por su responsable. Una hipótesis refutada no requiere código; una aceptación de riesgo no equivale a corrección ni a certificación para producción. Las acciones que bloqueen datos reales, recuperación u operación concurrente deben resolverse antes de habilitar ese uso, salvo aceptación expresa y documentada por la autoridad correspondiente.

Este documento autoriza cero recursos o gastos por sí mismo. La solicitud actual cubre preparar el plan; la implementación y las operaciones se habilitan con el alcance aprobado. No incluye publicar cambios, mergear, desplegar ni contratar infraestructura automáticamente.

## Base y evidencia de planificación

- Base local y `main` remoto consultado el 15/10/2026: `c6f101b089ee4950e6133390bd4c888a280f31b5`; coincide con el corte auditado.
- Rama: `juanikitro/Auditor`. Los dos entregables originales de auditoría están sin seguimiento y se preservan sin modificaciones.
- Fuentes principales: informe e inventario del 14/10 en `docs/plans`, `CONTEXT.md`, `docs/PRUEBAS.md`, workflows existentes y lectura focal de código por tres agentes.
- Las comprobaciones de planificación fueron de solo lectura. No se ejecutaron Django, tests, builds, Docker, bases, seeds, carga, fallos ni restauraciones. La consulta remota acredita el SHA, no CI aprobado ni funcionamiento.
- La auditoría tiene 54 entradas: 33 P1, 20 P2 y 1 P3. Mezcla hallazgos estáticos, hipótesis y controles a conservar. Cada mecanismo debe reproducirse antes de declararlo confirmado en runtime.
- La planificación no sustituye una auditoría legal ni la evaluación de un despliegue real.

## Enfoque y alternativas

**Recomendación: entregas verticales pequeñas sobre el monolito actual.** Cada paquete incluye reproducción, corrección mínima, regresión, revisión y evidencia. Se ejecutan en paralelo solamente los trabajos cuyos archivos, contratos y recursos no se superponen. La integración se realiza secuencialmente sobre una base conocida.

Alternativas consideradas:

1. Una corrección masiva de los 54 puntos: menor coordinación inicial, pero mezcla permisos, migraciones y operación; dificulta revisar, atribuir fallos y revertir. Se descarta como estrategia de entrega.
2. Rehacer arquitectura y adoptar servicios antes de corregir: puede resolver futuras necesidades, pero agrega costo y complejidad sin demanda medida. Se descarta como punto de partida.
3. Paquetes incrementales con una línea de seguridad/integridad y otra de recuperación/operación: permite avanzar con evidencia y restringir cambios estructurales a necesidades comprobadas. Es la propuesta.

No se incorporan caché de identidad, pooler, nuevas colas, réplicas, microservicios ni herramientas de carga como decisiones implícitas. Se reutilizan capacidades institucionales, servicios transaccionales, colas durables y pruebas existentes donde encajen.

## Criterios observables propuestos para aprobar el programa

1. Ningún rol obtiene o modifica información de otra institución o paciente fuera de su autorización; se prueban casos permitidos y denegados, no solamente respuestas 403.
2. Firma clínica, grafo publicado, existencias, pedidos, ocupaciones, turnos, cupos y operaciones económicas mantienen sus invariantes frente a concurrencia y reintentos.
3. Un fallo o timeout no deja efectos externos incoherentes, operaciones duplicadas ni borrados parciales ocultos; cada excepción tiene política explícita y trazabilidad.
4. Base y archivos se recuperan en un entorno nuevo y dentro de los límites de pérdida y tiempo aprobados. Una copia creada no demuestra recuperación.
5. Instalación, migración y actualización son reproducibles, con configuración productiva validada y procedimiento de reversión ensayado.
6. La carga objetivo cumple latencias, errores, frescura, margen y disponibilidad acordados, con métricas del generador y del servidor. No se equiparan usuarios registrados con concurrentes.
7. Los 54 IDs tienen disposición, responsable y evidencia por SHA; los controles existentes y compatibilidades relevantes permanecen cubiertos.

El dueño aprobó el enfoque. Los acuerdos funcionales y objetivos cuantitativos posteriores se registran debajo; las decisiones pendientes se definen antes del paquete que las necesita y no bloquean la preparación independiente.

## Decisiones acordadas con el dueño el 15/10/2026

Esta sección registra aprobaciones de la conversación y prevalece sobre las preguntas abiertas de la tabla D1–D9 donde haya una respuesta expresa. No es una ADR retrospectiva ni afirma que los cambios estén implementados.

### Identidad, autoridad y trazabilidad

- La persona administra su email y contraseña. El administrador institucional puede iniciar una recuperación sin conocer ni elegir la contraseña; el superadministrador atiende recuperaciones excepcionales con trazabilidad.
- Bloquear una pertenencia institucional no bloquea la cuenta en otras instituciones. Al revocar acceso o cambiar contraseña deben cerrarse las sesiones afectadas; definir técnicamente el alcance de revocación para no convertir un bloqueo local en bloqueo global.
- Superadministradores y administradores institucionales, o roles explícitamente equivalentes, pueden realizar operaciones de administración y contingencia en su ámbito, con excepciones: no modificar registros ya firmados, borrar auditoría ni actuar como autor de otro profesional. Las correcciones conservan autoría e historial. Esto no autoriza ampliar permisos a roles indeterminados ni convertir un administrador institucional en autoridad global.
- Si falla exclusivamente el registro de acceso clínico, se permite continuar la atención, se genera alerta operativa y se identifica el fallo para tratarlo. No se comunica auditoría exitosa cuando no existió.
- Un archivo clínico tiene un único paciente y estudio/recurso propietario; no se comparte entre pacientes o estudios. Los archivos sin pertenencia demostrada pueden ser revisados/asociados por los administradores autorizados dentro de su ámbito, conservando evidencia y sin inferir dueño automáticamente.

### Clínica y formularios

- Dos profesionales no deben sobrescribir el mismo borrador. Ante edición concurrente se debe prevenir la pérdida de cambios y presentar conflicto explícito; firma, sello e historial no retroceden.
- El dueño permite cambios en formularios publicados únicamente si no alteran el flujo ni la confianza en los datos. Esto fija el objetivo, pero todavía requiere clasificar con ejemplos qué cambios son inocuos y cuáles modifican significado o comportamiento. No se interpreta como autorización para editar libremente formularios ya usados ni para introducir versionado nuevo sin diseño.

### Boxes, turnos y farmacia

- Un profesional ocupa un solo box y nadie toma uno ocupado.
- El dueño pide detectar una posible ocupación olvidada tras **3 horas de inactividad**, considerando si hay pacientes por tomar que no están siendo tomados, y favorecer que los boxes sin uso comiencen vacíos cada día.
- La propuesta aprobada en esta conversación es avisar y permitir liberación confirmada por persona autorizada; no liberar automáticamente por ausencia de clicks. La señal exacta de actividad, destinatario del aviso y tratamiento de cambio de día quedan por definir antes de P07. No vaciar boxes a medianoche sin distinguir actividad real o atención en curso.
- El paciente puede cancelar con **24 horas exactas o más** de anticipación. La falta de confirmación genera aviso a un usuario capaz de gestionarlo; por sí sola no se aprobó cancelar el turno. Definir destinatario y momento del aviso antes de implementarlo; conservar reglas de mostrador hasta contrastarlas con documentación/código.
- Necesidad futura solicitada: permitir configurar mensajes de **WhatsApp** para confirmación/recordatorio de turnos. Se documenta como evolución futura, sin integrar proveedor, contratar servicio ni enviar mensajes en este alcance.
- Rechazar un pedido parcialmente entregado afecta solo el saldo pendiente; conserva entregas y movimientos anteriores.
- Se permite eliminar únicamente pedidos en borrador sin movimientos; después se conserva la evidencia y se cancela/rechaza lo pendiente. Contrastar el concepto de borrador con estados actuales antes de añadir un estado nuevo.

### Primera instalación y objetivos de servicio

- Una institución y **menos de 25 personas simultáneas**. No usar los escenarios exploratorios de 1.000–10.000 activos como condición de aceptación de esta primera instalación.
- Habrá pacientes reales. No hay compromisos adicionales de alojamiento/retención declarados; eso no demuestra ausencia de obligaciones aplicables. Las políticas necesarias siguen pendientes de definición por responsable competente antes de habilitar ese uso.
- El dueño será responsable de fallos operativos. Presupuesto, región y servicios de AWS aún no están definidos; no se autoriza contratación ni gasto.
- Objetivo inicial aceptado: pantallas habituales utilizables en **hasta 2 segundos para el 95 % de las operaciones**, medido con navegador y backend reales bajo la mezcla acordada. Falta especificar recorridos/dataset y condiciones de medición.
- Objetivo inicial aceptado: **pérdida máxima de 15 minutos** de datos y **recuperación en hasta 1 hora** ante caída completa. Deben comprobarse DB y media y explicitar qué efectos externos cubre la recuperación. Son objetivos a evaluar, no capacidad demostrada ni promesa de infraestructura actual.
- La prioridad es minimizar interrupciones; no se aprobó un porcentaje de disponibilidad ni se prometió downtime cero. La elección de infraestructura queda sujeta a evidencia, presupuesto y operación sostenible.

### Integraciones y decisiones aún abiertas

- Actualmente no hay integración externa funcionando. El dueño desea FHIR y RENAPER disponibles desde el inicio y una UX que explique configuración, disponibilidad, resultado y errores.
- Investigar en sesión independiente qué documenta e implementa el repositorio sobre FHIR: fachada propia frente a cliente saliente, permisos, uso, pruebas y requisitos pendientes de integradores. El deseo de funcionamiento no sustituye un proveedor concreto, credenciales ni aceptación real.
- La integración real con RENAPER necesita investigación y acceso autorizado al proveedor; no habilitar simulación como si fuera validación real.
- Permanecen abiertas las políticas de retención/datos, proxies confiables, límites por acción/NAT, proveedores y garantías de efectos externos, presupuesto/topología, destinatarios de avisos y detalles operativos anteriores. Resolver cada una antes de su paquete, sin reabrir decisiones ya aprobadas.

## Decisiones que no se deben inventar

| Decisión | Qué debe acordarse | Paquetes que condiciona |
|---|---|---|
| D1 Identidad y sesiones | Quién administra email, contraseña y estado de una cuenta compartida; delegación; cuándo debe revocarse una sesión y qué latencia de revocación es aceptable. | P02, P03 |
| D2 Auditoría y operación excepcional | Comportamiento clínico si falla el registro de acceso, alertas/reconciliación, proxies confiables y alcance necesario del staff de soporte. La política clínica actual no se endurece silenciosamente. | P03, P04, P11 |
| D3 Contratos clínicos y formularios | Tratamiento de conflictos de edición/firma, suspensión repetida y estabilidad/versionado de formularios publicados. | P04, P05 |
| D4 Adjuntos e historia existente | Vínculo autoritativo archivo-paciente-recurso y acceso a adjuntos históricos sin dueño demostrable; no inferirlo por nombre ni resellar historia antigua. | P03, P04, P13 |
| D5 Operación y farmacia | Exclusividad/transferencia de boxes, política portal frente a mostrador, rechazo después de entrega parcial, claves de operación y conservación de pedidos. | P06, P07 |
| D6 Servicio y demanda | Simultaneidad, mezcla de operaciones, volumen, latencias y frescura por recorrido, error admisible, disponibilidad y mantenimiento. | P10, P12, P14 |
| D7 Recuperación y operación | Pérdida máxima admisible y tiempo de recuperación para DB/archivos/efectos; amenazas cubiertas, responsables, guardia, región, proveedores y presupuesto. | P08, P09, P11, P14 |
| D8 Datos y obligaciones | Accesos excepcionales, retención, cifrado y alcance frente a administradores de DB/host; confirmar obligaciones con responsable competente. | P13, P14 |
| D9 Efectos externos | Idempotencia efectiva del proveedor, consultas de estado, resultado incierto, conciliación y compensación; qué garantías son posibles y qué riesgo residual requiere aceptación. | P05-E, P10 |

En decisiones arquitectónicas con alternativas se presentan ganancias, pérdidas y condición de revisión. La comprensión y aceptación del dueño se verifican conforme a AGENTS antes de recomendar incorporación; pruebas aprobadas no la sustituyen.

## Paquetes de trabajo y cobertura de los 54 IDs

Los paquetes son unidades de coordinación. Se dividen en PRs pequeños por mecanismo y sus pruebas; no se crea un PR gigante por fila. La prioridad individual del inventario se conserva aunque la numeración refleje dependencias.

| Paquete | IDs cubiertos | Entregable mínimo | Evidencia de salida / dependencia |
|---|---|---|---|
| **P00 Base y trazabilidad** | AUD-031, AUD-039 | Revalidar corte, matriz de acciones/objetos/campos y evidencia; relacionar ID con reproducción, decisión, cambio, prueba y riesgo. Extender los documentos existentes. | 54 IDs sin omisiones; faltantes de cobertura explícitos. La matriz adversarial se completa a través de todos los paquetes, no se cierra con este inventario. |
| **P01 Laboratorio aislado** | Habilita AUD-031 y validaciones de todos los paquetes | Configuración de pruebas sin carga de `.env` real, PostgreSQL exclusivo, media/caché/puertos propios, proveedores sintéticos y escenario reproducible. Adaptar el patrón de `docker-compose.padron130.yml` sin usar sus recursos. | Identidad y aislamiento comprobados antes de escribir; rechazo de destinos no autorizados. Crear settings específicos: los nombres sugeridos por la auditoría todavía no existen. Requiere autorización del entorno. |
| **P02 Identidad y sesión** | AUD-001, AUD-009, AUD-010, AUD-030 | Autoridad explícita sobre cuentas globales, revocación verificable, límites de login/acciones costosas y manejo correcto de cambio institucional/sesión. | API A/B con roles mixtos, cuenta compartida/privilegiada/inactiva; alta, PATCH y login; token viejo y refresh/replay concurrentes tras revocación; solicitudes atrasadas al cambiar institución. Límites probados multiworker, con proxies confiables y tasas/NAT acordados; caché compartida no acredita atomicidad. D1/D2/D6; P01. |
| **P03 Privacidad, archivos y acceso** | AUD-002, AUD-003, AUD-004, AUD-007, AUD-008, AUD-044, AUD-046, AUD-050 | Evitar credenciales en descargas externas, auditar descarga directa, neutralizar CSV, retirar datos sensibles de logs/eventos, IP confiable, FHIR por capacidad institucional y asociación autoritativa de adjuntos. | Navegador y API reales; matriz institución/paciente A/B, URL externa, cabeceras falsas, fórmulas, eventos y logs sintéticos. Verificar datos/totales/enlaces FHIR, no solo permiso de entrada. D2/D4; P01. Separar adjuntos y su eventual migración de las correcciones locales. |
| **P04 Integridad clínica y Admin** | AUD-041, AUD-042, AUD-043, AUD-045 | Relectura bajo bloqueo antes de editar/firmar, Admin sin bypass, formato canónico versionado y suspensión de receta coherente. | Dos conexiones PG: editar/firmar, firmar/firmar y suspender/suspender; Admin GET/POST/delete/inlines/bulk con ámbitos A/B; sellos históricos siguen verificables. D2/D3/D4; P01. |
| **P05 Motor y publicación** | AUD-011, AUD-012 | Aplicar un protocolo de bloqueo de versión a publicar y a todos los escritores del grafo; política de formularios publicados. | Publicar vs crear/editar/borrar nodos y conexiones; ejecutar casos existentes después de modificar un formulario. Se decide snapshot/versionado antes de alterar modelo o contrato. D3; P01. |
| **P05-E Integraciones externas** | AUD-005, AUD-006 | Revalidación de destinos/redirects y consistencia de efectos externos; detalle más abajo. | Egreso rechazado antes de contactar destino prohibido; rollback, caída/reinicio y respuesta incierta cumplen las garantías aprobadas y dejan trabajo conciliable. Ausencia de duplicados solo si el proveedor permite demostrarla. P01 y D9. |
| **P06 Farmacia e idempotencia** | AUD-013, AUD-014, AUD-052, AUD-053, AUD-054 | Unicidad de stock sin lote, orden de locks, rechazo serializado, identidad durable de operaciones y conservación de pedido/líneas con movimientos. | PG con transferencias opuestas, entregar/rechazar y parcial/parcial; timeout posterior al commit; misma clave/contenido mueve stock una vez, contenido diferente rechaza y clave nueva permite entrega nueva. DELETE no pierde evidencia. D5; P01. Diagnosticar duplicados antes de constraint; sin fusionar stock automáticamente. |
| **P07 Boxes y portal** | AUD-048, AUD-049 | Ocupación/liberación coherentes y política temporal revalidada sobre turno bloqueado, diferenciada por canal. | Dos usuarios/mismo box, mismo usuario/dos boxes, liberación obsoleta; reprogramar vs cancelar/confirmar y umbral temporal exacto. D5; P01. |
| **P08 Backup seguro y salud funcional** | AUD-015, AUD-016, AUD-018 | Snapshot verificable, tratamiento explícito de conteos/errores, restauración de verificación en DB exclusiva y salud de trabajos nunca ejecutados/repartos. | Fallo de dump/restore/conteo no informa éxito; conteos bajo escrituras se interpretan con consistencia; nunca toca DB ajena. Proceso vivo pero sin ejecutar se detecta. P01; D7 para umbrales. |
| **P09 Recuperación integral** | AUD-017 | Copia recuperable de DB y media fuera del dominio de falla, custodia, retención y procedimiento de recuperación. | Restaurar DB+archivos en destino vacío; comprobar archivos, permisos, referencias, antigüedad, pérdida y tiempo. Depende P08 y D7/D8; proveedor, servicio y gasto por aprobar. |
| **P10 Tareas, conexiones y recursos** | AUD-019, AUD-020, AUD-027, AUD-028, AUD-029, AUD-034 | Reencolado/reintentos medidos, presupuesto DB/timeouts/mantenimiento, mínimos privilegios/límites, correo recuperable, límites compartidos verificados y gestión de huérfanos/cuotas. | Reinicio tras reserva/commit, contención de conexiones, envío fallido, concurrencia de límites y carga fallida; sin borrar archivos válidos. Cualquier nueva cola persistente, permiso, dependencia o esquema se decide antes. P01; D6/D7/D8 según mecanismo. |
| **P11 Release y configuración productiva** | AUD-023, AUD-024, AUD-025, AUD-026, AUD-036 | Migración única por release, cadena TLS/rutas FHIR, versiones reproducibles, configuración incompleta rechazada y diseño operativo sostenible. | Arranque con configuración inválida falla; proxy y FHIR reales; instalación desde cero; dos réplicas no migran simultáneamente; actualización con compatibilidad anterior/nueva. Disponibilidad real depende del diseño y ensayo autorizados, no solo de editar Compose. D2/D7; P01/P08. |
| **P12 Rendimiento medido** | AUD-021, AUD-022, AUD-051 | Presupuesto de polling/cancelación, exportaciones/historias acotadas y medición de búsqueda global de identidad. Optimizar solo el cuello confirmado. | Fan-out real de navegador, cancelación efectiva, páginas grandes y exportaciones; EXPLAIN autorizado y p95/p99. No cambiar equivalencias de documentos ni cachear pertenencias sin contrato. P01, D6; repetir mediciones después de cambios P02–P11 relevantes. |
| **P13 Compatibilidad y garantías transversales** | AUD-032, AUD-035, AUD-037, AUD-038, AUD-040 | Política de datos/amenazas; ensayo legacy, volumen y actualización progresiva; conservar fronteras sensibles, locks, idempotencia, trabajo durable y separación demo/paciente real. | Dataset sintético con estados históricos y lectores v1/v2; accesos sensibles, último cupo/último stock, simulación vencida y tokens cruzados. Sin datos reales ni migraciones irreversibles implícitas. D4/D8; transversal a los paquetes afectados. |
| **P13-D Reset de escuela** | AUD-047 | Aislar reset por entorno e identidad estable del escenario, excluir cuentas compartidas y garantizar rollback completo ante relaciones protegidas. | En sandbox: un 409 por PROTECT conserva todos los conteos/relaciones; producción rechaza la acción; renombrar institución o compartir prefijo de cuenta no habilita borrado ajeno. P01; coordinar con P11. Bloqueante temprano, no una mejora a dejar para el final. |
| **P14 Capacidad y aceptación operativa** | Consolida AUD-020, AUD-031, AUD-035, AUD-036, AUD-039 | Ensayo integral de demanda, ráfagas, duración prolongada, fallos, recuperación y runbooks en la topología elegida. | Objetivos D6/D7 cumplidos, invariantes intactas, colas recuperadas y costo dentro del tope. Depende de correcciones aplicables, P09/P11/P12/P13 y autorización explícita de carga/fallos/costos. |
| **P15 Limpieza verificada** | AUD-033 | Retirar únicamente referencias obsoletas demostradas y creadas/inventariadas en el alcance. | Búsqueda de consumidores y validación focal; sin limpieza estética ni borrado de pruebas por nombre. Puede ejecutarse fuera de la ruta crítica. |

## Secuencia y ruta crítica

1. **Preparación:** aprobar criterios principales, confirmar responsables y habilitar P00. Definir y aprobar P01 antes de ejecutar bases o servicios. Reutilizar la auditoría y el issue como registro; no crear otro tracker.
2. **Reproducción y decisiones tempranas:** obtener evidencia de los bloqueantes de P02–P08. Resolver D1–D5 para sus respectivos contratos. Registrar hipótesis refutadas sin parches innecesarios.
3. **Primera ola de correcciones:** privacidad local y FHIR; identidad; firma/Admin; seguridad de backup. Con laboratorio aislado, esos dominios pueden avanzar en paralelo si no comparten archivos.
   Incluir P13-D temprano: el número del paquete no posterga el reset de escuela ni su frontera de seguridad.
4. **Segunda ola:** grafos/formularios, farmacia, boxes/portal e integraciones externas. Priorizar los bloqueantes según exposición y evidencia, sin esperar a terminar mejoras de rendimiento.
5. **Preparación operativa:** tareas, release/configuración, copia externa y compatibilidad. Definir D6–D8 en paralelo con el desarrollo; su ausencia no justifica inventar infraestructura.
6. **Medición y ajuste:** medir primero; aplicar ajustes focales; repetir el mismo escenario. Ejecutar aceptación de capacidad/recuperación solamente con objetivos y presupuesto aprobados.
7. **Cierre:** revisión integral de los 54 IDs, evidencia por revisión integrada, aceptación funcional y de riesgos; decisión separada de incorporación y despliegue.

Camino crítico probable: P00 → P01 → contratos y correcciones bloqueantes → integración/compatibilidad → recuperación y release ensayados → carga/operación → aceptación. La evaluación inicial de P09/P11 comienza antes para descubrir dependencias externas; no necesita esperar a todas las correcciones.

### Integraciones externas: subpaquete explícito P05-E

**AUD-005 y AUD-006** se ejecutan como subpaquete separado: revalidar destinos y redirects en cada salto, restringir egreso y evitar que un efecto externo quede confirmado antes del commit local o se duplique tras reintentos.

Reutilizar patrones existentes de trabajo durable e identidad de operación cuando encajen; no trasladar un modelo financiero a otro dominio por comodidad. Definir resultado incierto, idempotencia del proveedor, reintento, conciliación y compensación. Una tarea `on_commit` por sí sola no garantiza entrega durable ni resuelve respuesta externa incierta.

Aceptación: destino interno/redirect no autorizado rechazado; rollback local no dispara efecto; caída tras commit no pierde trabajo; timeout después de efecto remoto activa consulta de estado, replay idempotente o conciliación según D9; fallos dejan estado recuperable y observable. Si el proveedor no permite demostrar ausencia de duplicados, la integración no se habilita con esa garantía: se requiere contención o aceptación explícita del riesgo. Proveedor simulado en P01 y prueba contractual del proveedor real solo cuando esté autorizada. Depende de P01, D9 y revisión de seguridad; puede necesitar migración/contrato y aprobación específica.

## Coordinación de agentes

Un coordinador mantiene dependencias, integración y cobertura. Hasta tres agentes especialistas activos a la vez, según independencia real:

- Seguridad/identidad/privacidad.
- Integridad clínica/motor/farmacia.
- Operación/recuperación/rendimiento.

La fase de planificación ya utilizó esos tres agentes en lectura focal. En implementación, el coordinador asigna propiedad por archivos y paquete; un agente no modifica archivos asignados a otro. `backend/apps/common.py`, `backend/config/settings.py`, modelos compartidos, migraciones y `frontend/src/api/client.js` requieren dueño único o turnos explícitos. Si hay colisión, se reduce paralelismo.

La implementación aprobada usa worktrees independientes administrados por Orca cuando se necesiten; base/volumen/media/caché por worker y pruebas PG serializadas hasta demostrar aislamiento. La topología debe respetar un presupuesto total de conexiones, no multiplicarlo por agente sin control. No detener workers ajenos ni usar/borrar `test_salud` compartida.

Antes de modificar bloqueos, cada dominio mantiene una tabla breve de recursos/orden por recorrido y revisa todos los llamadores afectados. Los bloqueos de Historia/Entrada/Receta, VersionFlujo/grafo y Pedido/Existencia no se diseñan función por función de manera aislada. Usar un bloqueo de Traslado no acredita por sí solo exclusión con escritores de Caso: incluir ese cruce en AUD-038.

El agente implementador no aprueba solo su propio cambio. Otro agente revisa el diff completo contra escenario, contrato, pruebas y alcance. La revisión cruzada es una verificación técnica; no demuestra comprensión del dueño. No se presupone disponibilidad de Claude en esta sesión: si se usa un segundo agente Codex se informa como tal, sin atribuirle revisión de Claude.

## Protocolo de cada entrega

1. Revalidar HEAD y estado, leer mecanismo mínimo y registrar escenario/predicción. La reproducción de la auditoría no se trata como conclusión actual sin comprobarla.
2. Confirmar aceptación funcional y decisiones materiales del paquete. Antes de incorporar, ofrecer revisión inicial al dueño conforme a AGENTS; si declina se realiza revisión técnica completa.
3. Escribir la prueba de regresión que demuestra el fallo o documentar el experimento pendiente. No corregir por intuición; no añadir tests que solo repliquen implementación.
4. Aplicar el menor cambio sobre helpers y servicios existentes, incluyendo UI de conflicto cuando el nuevo rechazo de negocio lo requiera.
5. Ejecutar prueba focal y negativas/edge cases relevantes. Después, revisión independiente. Resolver discrepancias materiales explícitamente.
6. Registrar riesgos de migración, consumidores, observabilidad y recuperación. Revalidar la evidencia al integrar cambios de otros paquetes.
7. Antes del cierre no trivial, revisar con el dueño al menos dos modos de fallo plausibles y su mitigación; antes de recomendar incorporación, confirmar su comprensión de cambio, detección y reversión. Si declina, registrar la comprensión pendiente sin inventar validación humana.
8. Commit, push, PR, merge y deploy se realizan únicamente dentro de la autorización acordada. Commits con Conventional Commits. La evidencia de CI corresponde al SHA exacto, no a una versión anterior.

## Validación y evidencia

### Pirámide de pruebas

- Funciones puras: CSV, canonicalización, validación IP/URL y decisiones deterministas.
- API/Django: permisos efectivos, serialización, Admin, sesiones, aislamiento y compatibilidad.
- PostgreSQL 16: dos conexiones con barreras de sincronización para reproducir el interleaving; transacciones reales, timeouts acotados y comprobación de filas/auditoría. No usar solo sleeps ni aceptar skips en SQLite como evidencia.
- Navegador con backend real: login/cambio institucional, conflictos clínicos, adjuntos/portal, reintentos y resultados visibles. Mocks pueden cubrir UX pero no aislamiento o integridad.
- Proxy/servicios: TLS, cabeceras, rutas FHIR, proveedores fallidos y procesamiento durable.
- Operación: instalación, migración, copia y restauración DB+media, recuperación de tareas y fallos autorizados.
- Capacidad: generador y servidor instrumentados, dataset y mezcla aprobados, carga estable/rampa/ráfaga/duración y margen bajo los fallos acordados.

### Comandos y CI

Se reutilizan `backend.yml`, `calidad.yml`, `e2e-ui.yml` y `e2e-portal.yml`. El backend ya usa PostgreSQL 16; el E2E del portal usa backend real con SQLite, por lo que hay que agregar cobertura PG donde el criterio dependa de concurrencia. Revisar filtros por rutas para no omitir contratos afectados por cambios fuera de `backend/`.

Comandos existentes, **no ejecutados en esta planificación**:

```text
# backend: añadir --settings=<módulo aislado validado> en la ejecución aprobada
python manage.py test <módulo_o_clase_focal> --noinput
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py check --deploy
python manage.py spectacular --fail-on-warn --file <artefacto_temporal>

# frontend
npm run build
npm run auditar
npx playwright test -c playwright.portal-app.config.js
```

La suite completa `python manage.py test --noinput`, build y demás comprobaciones globales se ejecutan en los hitos de integración autorizados y antes de la aceptación final; no por cada edición. Las suites focales van por paquete. `check --deploy` requiere configuración productiva sintética apropiada; no se fuerzan settings inseguros para obtener verde. Las suites navegador necesitan su escenario exclusivo.

Cada evidencia registra ID, criterio, SHA, entorno/versiones, datos sintéticos/semilla, comando o experimento, resultado esperado/observado y límites. Se conserva evidencia sanitizada, nunca tokens ni contenido clínico real. Un bloqueo ambiental se informa como no validado, no como prueba aprobada.

## Migración, compatibilidad y reversión

- Preflight de datos antes de constraints de stock, vínculos de archivos o claves de operación; las ambigüedades se reportan sin fusionar, borrar ni inventar relaciones.
- Para cambios persistentes, favorecer expansión compatible → actualización de lectores/escritores → verificación → contracción posterior solo si hace falta y está autorizada. No asumir rollback de código compatible con cualquier migración.
- Mantener lectura de sellos históricos por versión; no recalcularlos como si fueran originales.
- Claves de operación y trabajo externo requieren política de retención y compatibilidad con clientes anteriores, no solo un campo nuevo.
- Antes de una entrega con migración: estimar locks/tiempo, probar dataset histórico sintético y verificar si exige ventana o impide actualización progresiva.
- Revertir un fix de seguridad no debe reabrir la exposición. Si no hay reversión segura, contener la operación afectada y avanzar con corrección; documentar la limitación.
- Restauración completa es último recurso y tiene consecuencias sobre escrituras posteriores y efectos externos; no se presenta como reversión automática.

## Criterios de autorización y cierre

Tres decisiones separadas:

1. **Plan y contratos:** aprobar enfoque, criterios observables y decisiones D1–D5 del primer lote; las restantes se resuelven antes de su dependencia.
2. **Ejecución y validación:** autorizar ediciones y entorno sintético con nombres, puertos, recursos, duración y límite de costo concretos; incluir qué pruebas globales y operaciones se permiten. Bases, Docker, migraciones aplicadas, fallos y servicios externos no se deducen de aprobar el documento.
3. **Incorporación y producción:** decidir commit/push/merge y, después, despliegue por separado, con revisión, comprensión, recuperación y evidencia del SHA integrado. No se solicita aceptación de una infraestructura todavía sin diseñar/cotizar.

No se declara completado el programa por número de PRs ni por tests verdes. Deben quedar cerrados los escenarios obligatorios, aprobados los riesgos residuales, ensayada la recuperación, medidos los objetivos operativos y aceptados los recorridos funcionales. Si una parte no puede validarse, se informa qué uso continúa bloqueado.

## Estimación y siguiente entrega

No se suman los días orientativos del CSV: comparten mecanismos y omiten parte de integración, validación y decisiones. El máximo paralelismo útil es tres especialistas más coordinación; no equivale a dividir el plazo por tres.

Después de P00/P01 y de reproducir un paquete representativo de seguridad, uno de concurrencia y uno de recuperación, estimar por paquete: implementación, pruebas, revisión, integración, incertidumbre y espera externa. Publicar un rango con supuestos; no comprometer calendario antes de conocer el entorno y los contratos.

Primera entrega propuesta: laboratorio definido y aprobado; matriz inicial de los 54 IDs; reproducciones de AUD-001/002/003/041/046/050 y AUD-015/016 según aislamiento disponible; decisión de contratos D1/D2/D4 y orden de bloqueos clínicos. Ninguna de esas reproducciones se da por ejecutada por aparecer en el plan.

## Avance local de implementación — 15/10/2026

- El dueño autorizó comenzar la implementación después de aprobar enfoque y decisiones anteriores. Continúan separados los permisos de ejecución operativa, publicación y despliegue.
- **AUD-002: corrección local y regresión focal preparadas; pendiente de revisión y validación de navegador.** En `frontend/src/api/client.js`, `downloadArchivo` valida destino canónico antes de construir cabeceras: origen de la API configurada y endpoint propio de descarga. Bloquea redirects en petición inicial y reintento. Referencias externas o inválidas muestran error; no se intenta abrirlas con credenciales.
- `frontend/src/api/client.test.mjs` carga el módulo real completo con `node:vm`, `import.meta.env` sintético, storage/DOM y fetch sustituidos. Seis casos focales, sin red: destino externo, ruta inválida, referencias propias, origen API configurado, refresh/reintento y error de redirect. No equivale a navegador real ni demuestra headers HTTP efectivos contra servidor externo.
- Reproducción previa: la prueba de URL externa falló porque la descarga se completaba en vez de rechazarse; la de redirect mostró ausencia de política restrictiva. Tras el cambio: `node --experimental-vm-modules --test src/api/client.test.mjs` desde `frontend/`: **6 aprobadas, 0 fallidas**, Node local 24.13.0. El runner requiere flag de módulos VM experimentales, solo en pruebas. Agregado como paso focal a `.github/workflows/calidad.yml`; CI no ejecutado en esta fase.
- Compatibilidad a comprobar: claves y URLs del endpoint propio permanecen admitidas; referencias históricas a otros orígenes o rutas se rechazan. Inventariar esos enlaces y revisar configuración de proxy/origen en AUD-024/050 sin restaurar envío de credenciales a destinos no autorizados.
- No se considera AUD-002 cerrado: faltan revisión independiente autorizada, navegador HTTP real, aceptación funcional y contraste de dos modos de fallo con el dueño antes de incorporación. No hubo commit/push/merge/deploy.
- **P01: laboratorio preparado en archivos; no ejecutado.** Configuración independiente en `docker-compose.auditoria172.yml`, Dockerfile/ignore específicos y settings con guarda de destino. Proyecto `salud-auditoria172`, PostgreSQL 16, volúmenes propios, sin puertos publicados ni mounts de datos ajenos. El build no carga settings ni ejecuta collectstatic; runtime sin root. Procedimiento y límites en [laboratorio](2026-10-15-laboratorio-auditoria-172.md).
- Validación reportada por el agente implementador de P01: `python -B -m unittest config.test_auditoria172_guard -v` desde `backend`: **3 tests OK**, solo stdlib; AST de tres archivos Python sin errores. No ejecuta Django, no prueba red Docker, no valida conexión PG ni constituye revisión independiente. Compose/build/pull/arranque y escrituras sintéticas pendientes de autorización operativa. Recursos iniciales: DB 512 MiB/1 CPU y backend 1 GiB/2 CPU, más Docker/build; disco sin cuota.
- **Actualización posterior:** el dueño autorizó revisión completa por otro agente y construcción/arranque del laboratorio. La revisión independiente no encontró P1/P2 accionables y reejecutó 6 Node + 3 stdlib, todas aprobadas. Se construyó imagen propia y arrancó PostgreSQL 16.15; `manage.py check` y comprobaciones runtime de identidad, UID, dotenv/proveedores y escritura de volúmenes aprobadas. Se ejecutaron **16 tests focales** en PostgreSQL (guardas, estudios clínicos y separación de tokens), todos aprobados y sin skips; la base exclusiva de tests se creó/migró/eliminó correctamente. Detalle, versiones y límites en el runbook P01. La DB queda saludable; backend bajo demanda, sin servidor web ni puertos publicados. AUD-002 sigue pendiente de navegador, validación de referencias backend y aceptación; no se recomienda incorporación todavía.
- **Continuación autorizada:** el dueño explicó correctamente la restricción de credenciales/redirects y pidió continuar. No respondió el contraste de dos modos de fallo solicitado; no se toma esa omisión como comprensión o aceptación demostrada de los riesgos pendientes.
- **AUD-004, corrección local validada por API:** se promovió la función existente `texto_csv_seguro` a `apps/csv_seguro.py`, manteniendo la importación anterior de financiadores como compatibilidad. El exportador común protege textos, etiquetas y celdas compuestas sin alterar números escalares/fechas/booleanos. Reproducción previa: cuatro pruebas con 15 subfallos por fórmulas no neutralizadas; después, 16 tests de helper y CSV por API aprobados. Compatibilidad de exportaciones de financiadores comprobada en la tanda conjunta. Pendiente apertura real en Excel/LibreOffice; no declarar comportamiento de esas aplicaciones a partir de csv.reader.
- **AUD-047, contención parcial validada:** solo superusuario y entorno demo; captura de ProtectedError fuera de atomic; exclusión de cuentas ajenas/compartidas/sin pertenencia/privilegiadas; eliminación de selección global de accesos por usuario. Tests comprueban rollback de paciente, usuario, membresía, auditoría, área, flujo, versión, caso, insumo, depósito, existencia y movimiento, incluidas relaciones y cantidades. Mantiene el control heredado por nombre: no resuelve todavía identidad estable del escenario ni concurrencia con cambios de membresía; AUD-047 continúa abierto. La limpieza sintética local de demo heredada no autoriza borrar auditoría real.
- **AUD-007/008, redacción de nuevos logs/eventos:** tres logs FHIR ya no contienen URL/query/identificador ni contenido del proveedor; conservan estado/tipo de fallo. Motor guarda respuesta en ValorCampo pero el evento general solo identifica el campo, sin valor. Rojo previo en imagen real: 4 tests con 10 subfallos. No se reescribieron logs/eventos históricos. **Riesgo residual AUD-008/039:** CasoDetalleSerializer expone valores; falta demostrar permisos por institución/rol/clasificación del campo antes de afirmar protección del dato original. Eliminar su copia del evento no cierra esa frontera.
- **Validación conjunta de esta continuación:** `manage.py test` con `apps.test_csv_seguro`, `apps.casos.tests_api.ExportacionCSVTests`, `apps.instituciones.tests.ResetEscuelaTests`, `apps.instituciones.test_reset_escuela_auditoria172`, dos tests CSV de `ActividadReporteTests`, `apps.financiadores.test_exportacion_seguimiento`, `apps.fhir.test_privacidad_cliente` y `apps.casos.test_privacidad_integracion`: **55 tests aprobados**, sin skips, en PostgreSQL exclusivo. Se reconstruyó imagen tras cada conjunto de cambios y se serializaron corridas. Se mantienen los límites de estáticos del laboratorio; no hubo suite global ni pruebas manuales de navegador/planilla.
- Revisión independiente de AUD-004/047 y AUD-007/008 sin P1/P2 nuevos en los diffs; mantiene explícitas las limitaciones anteriores. No hay commit/push/merge/deploy ni aceptación funcional integral.
- **AUD-001/009:** investigación confirmó ausencia de autoservicio/recuperación institucional; el portal usa otra identidad y no se reutilizará para Usuario. [Contrato propuesto](2026-10-15-contrato-identidad-institucional-172.md) preparado para decisión, sin código nuevo de API. Fuente instalada de SimpleJWT 5.5.1 en imagen confirma que comprobar huella de contraseña solo en access no rechaza refresh antiguo: se requiere validación explícita adicional y contrato de sesiones. Nuevos endpoints/semántica de invitación y estado durable no se introducen sin aprobación.
- **AUD-046, corrección de alcance FHIR validada:** Patient y Encounter usan capacidad efectiva en cada institución, mediante `capacidades_por_institucion_de`; el filtro antecede read/search/total/paginación. Se conserva Organization, superusuario, membresías activas y 404 no enumerativo. Rojo inicial: seis tests con seis subfallos por datos B expuestos a médico A/configurador B. Ocho regresiones nuevas incluyen roles invertidos, inactivos/globales, concesión/revocación y filtros. `manage.py test apps.fhir --noinput --verbosity 1`: **110 tests aprobados**, sin skips, en PG. Revisión independiente sin P1/P2 nuevos. No es aceptación con integrador real ni certificación FHIR.
- **AUD-011, CRUD de grafo serializado con publicación:** el mixin existente ahora bloquea/relee VersionFlujo para crear/actualizar/eliminar Nodo y Conexion; publicación/clonación ordenan locks por PK. Se conserva edición de notas y rotación de token operacional de pantalla. Rojo: siete tests PG, cuatro fallos (borrado nodo/conexión, creación/edición conexión después de publicación). Verde: módulo nuevo más `apps.flujos.tests`, **56 tests aprobados**, sin skips; revisión independiente sin P1/P2 nuevos.
- Se investigó además la hipótesis de PATCH de metadatos de versión con instancia anterior a publicación: **el control ya existía**. No se corrigió por intuición. Se añadieron dos regresiones de concurrencia (nota permitida sin revertir estado y clasificación rechazada tras publicación); módulo ampliado de **9 tests aprobado** en PG. Cubre escritor validado antes de publicación y retomado tras su commit. No demuestra por sí solo todas las intercalaciones, Django Admin/AUD-042 ni estabilidad de formularios/AUD-012.
- **Actualización de autorización:** el dueño aprobó el nuevo flujo institucional de invitación/recuperación/cambios propios por correo. Se inició implementación de API, servicios y pantallas. La persistencia del despacho, vigencias productivas y sesiones durables requieren sus decisiones específicas; no se infieren del flujo aprobado.
- **AUD-001/009, primera integración local:** alta administrativa con contraseña inutilizable e invitación al titular; cambios de credenciales/estado global/privilegios rechazados; alcance de escritura por institución administrada y recuperación sin destinatario alternativo. Rutas públicas de recuperación/canje y privadas de cambio propio separadas del portal. Pantallas y navegación integradas; cliente público sin JWT, cookies, simulación ni renovación de sesión. Las referencias de token se retiran del fragmento antes de efectos y el canje exige submit explícito.
- **Revocación por contraseña reproducida y corregida:** cuatro tests previos mostraron dos fallos (access antiguo/legacy aceptados) y un error (refresh de usuario eliminado daba 500). Se habilitó la comprobación nativa de huella para access y un serializer de refresh que comprueba la huella/regla de usuario bajo lock antes de renovar. El nuevo contrato obliga a volver a iniciar sesión con tokens legacy sin huella cuando se despliegue; no hubo despliegue. No acredita logout por dispositivo, anti-replay de refresh ni revocación durable de pertenencias.
- Primera tanda integrada: **36 pruebas aprobadas** de identidad administrativa, credenciales y revocación por contraseña; después **94 aprobadas** de cuentas existentes y simulación. PostgreSQL exclusivo, correo locmem y configuración explícita en fixtures. Son cortes anteriores a los hallazgos de revisión; las correcciones posteriores se vuelven a probar. Frontend: **12 pruebas Node aprobadas**, sin dependencias ni red. Compilación, navegación real y SMTP pendientes; CI no ejecutado.
- La revisión independiente detectó tres P2 antes de cierre: autoridad de plataforma incompatible con invitación, carrera de emails equivalentes por mayúsculas y ausencia de límites en recuperación administrativa. Se corrigen y agregan regresiones, sin afirmar que la primera tanda verde resolvía esas intercalaciones. Ninguna cola ni worker productivo se introdujo implícitamente; faltando configuración las rutas nuevas y el alta por invitación responden 503 antes de aceptar cambios. El adapter de prueba consume inmediatamente y no acredita privacidad temporal ni entrega durable.
- **Integración revisada:** corregidos además dos fallos detectados después: el modal de usuarios de `Directorio.jsx` seguía enviando contraseña/estado global y bloqueaba altas/ediciones con 400; ahora usa invitación, recuperación y payload permitido. Un enlace de recuperación anterior al cambio de email A→B→A podía revivir; el generador incluye ahora `Usuario.actualizado`, igual que la confirmación de email. Configuración de URL institucional limitada al origen, pues el router actual no tiene basename. Campos de password eliminados del esquema administrativo, manteniendo rechazo explícito del cuerpo original.
- **AUD-003, auditoría de descarga directa:** `DescargarArchivoView` registra inicio autorizado con actor real/simulación, institución y PK del archivo. No infiere paciente desde referencias libres de estudios/casos. Descarga legacy conservada: objeto_id vacío y huella técnica SHA-256 de la ruta en detalle, etiquetada `legacy`, sin copiar ruta ni nombre. `Cache-Control: private, no-store`. Fallos de registro conservan la atención y usan el log de errores existente; no constituye alerta entregada a un operador ni conciliación durable (contrato D2 pendiente). La pertenencia autoritativa al paciente sigue pendiente de AUD-050; este cambio no corrige aquella autorización.
- Reproducción AUD-003: ocho pruebas, seis fallos esperados por ausencia de registro/caché y dos denegaciones correctas. El primer ensayo detectó además doble cierre del stream en el helper de prueba; corregido sin modificar conexiones productivas. Revisión independiente posterior sin P1/P2 nuevos en el diff.
- **Último corte integrado:** `manage.py test apps.accounts apps.simulacion apps.registros.test_descarga_archivo_auditoria172 apps.casos.tests_api.SubirArchivoTest apps.registros.tests_api.EstudiosTests apps.auditoria.tests_retencion.ConsentimientoTests apps.portal.tests.AislamientoDeTokensTests --noinput --verbosity 1`: **187 aprobadas, sin skips**, PostgreSQL exclusivo. Incluye cuentas y simulación existentes, nuevas credenciales/revocación/concurrencia, descargas, subidas, estudios, consentimientos y separación de tokens del portal. Doce pruebas Node aprobadas y `spectacular --fail-on-warn` con exit 0; diff-check sin errores. No sumar tandas previas como cobertura única. Sin suite completa, build frontend, navegador, SMTP real ni aceptación funcional integral. Decisiones de persistencia de correo y autorización de instalación/build solicitadas; no se asume respuesta por silencio. No hay commit/push/merge/deploy.

## Continuación: autoría, boxes y navegador real

Los estados anteriores describen sus respectivos cortes. El dueño autorizó la validación visual y confirmó expresamente: **«Solo el autor edita y firma»**. Se aplica también al superadministrador y al actor real de una simulación; los borradores históricos sin autor quedan en solo lectura. No se implementó firma colaborativa ni sustitución de autor.

- **AUD-041/042, alcance parcial:** `EntradaHistoriaViewSet` bloquea historia y entrada, relee firma/permisos y valida el payload dentro de la transacción. Una escritura que esperaba una firma ya confirmada devuelve 409 sin alterar texto, autor ni sello. Solo el autor real edita/firma. Admin revalida los cambios de inline bajo locks y protege borrados de historias/pacientes con entradas firmadas o ajenas. La desaparición concurrente de una historia permitida devuelve 404, en lugar del 500 reproducido. No demuestra cobertura de todos los modelos de Admin ni evita todavía escrituras obsoletas entre dos pestañas del mismo autor: contrato de revisión obligatoria consultado, pendiente de decisión.
- **AUD-048, ocupación:** `instituciones/views.py` serializa por usuario y boxes en orden de PK. Tomar un box ocupado devuelve 409 sin perder el anterior; transferirse a uno libre es atómico. Liberar, PATCH y DELETE releen ocupación; los boxes ocupados no se borran. API/Admin impiden borrar áreas ocupadas, y se prohíbe la eliminación física de instituciones, coherente con `docs/roles/02-plataforma.md`. Incluye protección frente a cascadas de Admin y respuestas 404 ante borrados concurrentes. No implementa todavía avisos de tres horas, revisión humana ni inicio diario vacío; duración de ocupación no se presenta como prueba de inactividad.
- **Reproducción y pruebas PG:** las primeras 21 pruebas mostraron sobrescritura de firma, cambios de sello y apropiación de box; las regresiones de cascadas fallaron antes de su corrección. Tanda integrada de **143 aprobadas sin skips**: `manage.py test apps.instituciones.test_boxes_auditoria172 apps.instituciones.tests apps.registros.test_concurrencia_firma_auditoria172 apps.registros.tests_api apps.registros.tests_integridad --noinput --verbosity 1`. Después del caso adicional de historia borrada, tanda final de **36 aprobadas sin skips**: `manage.py test apps.instituciones.test_boxes_auditoria172 apps.registros.test_concurrencia_firma_auditoria172 --noinput --verbosity 1`. Son tandas solapadas; no sumarlas. Esquema OpenAPI final con `--fail-on-warn`: exit 0.
- **Validación visual de identidad:** Chromium real contra Vite, API y PostgreSQL sintéticos, sin interceptar respuestas locales: **40 controles aprobados**, ocho capturas, cero excepciones JavaScript. Alta/invitación, recuperación, cambio de contraseña, rechazo de access/refresh anteriores, cierre/bloqueo entre pestañas, bloqueo por inactividad y cambio/confirmación de email. Vista de escritorio y móvil sin desborde horizontal. El buzón es un archivo privado del laboratorio, sin SMTP ni proveedor externo. Evidencia sanitizada: `output/playwright/aud172-identidad-evidencia.json`.
- La validación detectó dos defectos corregidos: `max-w-lg` colisionaba con una clase de espaciado y estrechaba el formulario; se usó un ancho existente explícito. Al cerrar sesión, un receptor de BroadcastChannel de la propia ventana podía abrir la pantalla de bloqueo en vez del login; se marca el cierre antes de publicar y se restablece al iniciar sesión. La prueba comprobó también que el bloqueo por inactividad siguiera funcionando.
- **Autoría en UI:** `HistoriaDetalle.jsx` oculta acciones sobre entradas ajenas/sin autor, revalida modales con el actor real y conserva la vista de lectura. Otra reproducción visual mostró texto anterior en el modal de firma al editar y abrirlo inmediatamente; ahora se resuelve la entrada vigente por ID. Ensayo final con paciente sintético nuevo: **14 controles aprobados**, firma sobre contenido actualizado, autor/sello conservados, intentos administrativos ajenos rechazados por API, escritorio/móvil y cero excepciones JS. Evidencia: `output/playwright/aud172-clinica-evidencia.json`. Esto no sustituye el contrato pendiente de revisión entre pestañas.
- **Frontend:** instalación con lockfile existente, sin modificarlo; build final aprobado. `node scripts/auditar-clases.mjs`: 287 clases, sin colisiones ni huérfanas. `node --experimental-vm-modules --test src/api/client.test.mjs src/auth/credencialesInstitucionales.test.mjs`: 12 aprobadas. Se ajustó la suite E2E clínica existente, pero no se ejecutó su configuración global porque exige otro escenario demo; la evidencia visual citada usa el laboratorio exclusivo, no ese setup ni respuestas API simuladas.

Persisten las decisiones de revisión de borrador y despacho durable de correo; no se agregaron por silencio nuevas tablas, contratos ni workers productivos. Siguen pendientes sesiones durables, propiedad autoritativa de archivos, conciliación de auditoría, proveedores reales y otros IDs del inventario. No hay suite global, prueba de carga/recuperación, CI, commit, push, merge ni despliegue. La comprensión y aceptación funcional del dueño siguen pendientes; otra revisión y pruebas verdes no las sustituyen.

## Decisiones aprobadas: revisión de borrador y outbox

El dueño aprobó expresamente ambas recomendaciones: impedir sobrescritura entre pestañas del mismo autor y guardar correo pendiente en PostgreSQL con un worker. La aprobación incluye el contrato de revisión y la tabla/proceso de outbox, sin contratar proveedor ni desplegar producción.

La revisión será un token opaco derivado del estado completo del asiento. Cada PATCH deberá aportar `revision_esperada`, comprobada contra la entrada fresca bajo el lock existente; una revisión obsoleta dará 409 sin guardar ni firmar. La pantalla conservará el texto local y pedirá revisar explícitamente el estado del servidor antes de continuar. La firma conservará el texto/revisión leídos hasta que el profesional elija leer y usar una versión nueva. El token identifica un estado, no un contador: si se restaura exactamente el mismo estado A después de A→B→A, vuelve a coincidir; no se afirma detectar toda edición intermedia ni se introduce otra columna para ese propósito.

La outbox debe insertarse dentro de la misma transacción de alta/cambio; no se persiste mediante un callback posterior al commit. Recuperación pública encola la misma solicitud sin resolver identidad y el consumidor relee elegibilidad/permisos. El worker reservará trabajo mediante lease y locks, diferenciará descarte permanente de fallo de envío, recuperará reservas vencidas y usará reintentos acotados. No se guardarán tokens ni cuerpos SMTP en el payload. La garantía es al menos una vez: un crash después del envío y antes de confirmar puede duplicarlo. Configuración y políticas productivas seguirán siendo explícitas; el laboratorio usará buzón de archivos y valores sintéticos, sin SMTP.

Revisión de borrador implementada: `revision_borrador.py`, serializer, PATCH y hidden field de Admin. Falta de revisión devuelve 400; revisión de otro estado devuelve 409, después de comprobar firma y autoría. Rojo previo: dos tests, tres fallos esperados (PATCH aceptaba revisión ausente/falsa y GET no exponía revisión). Verde: `manage.py test apps.registros.test_revision_borrador_auditoria172 apps.registros.test_concurrencia_firma_auditoria172 apps.registros.tests_api apps.registros.tests_integridad --noinput --verbosity 1`: **108 aprobadas**, sin skips, PostgreSQL, 51,401 s. Incluye diez pruebas nuevas de revisión y carreras PG entre dos ediciones del mismo autor.

Frontend captura revisión junto al texto local, compara versión servidor sin reemplazar inputs y exige adopción explícita. Firma mantiene snapshot hasta lectura explícita de la nueva versión. Build aprobado, auditor CSS 287 clases sin incidencias y doce tests Node aprobados. Navegador real con dos pestañas del mismo autor: **18 controles aprobados**, tres capturas, escritorio/móvil y cero excepciones JS, sin respuestas API simuladas. Tanto edición como firma recibieron 409 reales y solo continuaron tras revisión explícita; sello y autor se conservaron. Evidencia sanitizada: `output/playwright/aud172-revision-evidencia.json`. Dos intentos iniciales fallaron por setup: sesión sin «recordar» y selección institucional ausentes en la segunda pestaña; se corrigió el fixture sin parchear producto. La suite E2E general sigue sin ejecutarse por su dependencia de demo; las nuevas pruebas de GET fallido con 503 de esa suite no se presentan como ejecutadas.

**Correo durable implementado y validado localmente:** modelo/migración `accounts.0007_correo_institucional_outbox`, módulo `correo_outbox.py` y comando `procesar_correo_institucional`. Alta y solicitud se confirman/revierten juntas; la recuperación pública no consulta identidad en el request. Worker con leases/UUID/locks PG, backoff, máximo de intentos, vencimiento y códigos sanitizados. SMTP5xx es terminal; errores temporales reintentables. Estado agregado y purga manual de payloads terminales; el latido del worker se integra al estado operativo solo si la outbox está habilitada. La salud del proceso no equivale a recepción del correo.

`manage.py test apps.accounts apps.simulacion --noinput --verbosity 1`: **161 aprobadas sin skips**, 56,437 s; incluye 17 nuevas de persistencia, rollback, público sin lookup, leasing multiworker, recuperación de reserva, errores y minimización. Ensayo con API/DB/worker reales del laboratorio: **10 controles aprobados**; solicitudes aceptadas con worker detenido sobreviven al reinicio de API y después se procesan, con descarte de destinatario inexistente. Regresión visual de identidad posterior a activar la outbox: **40 controles aprobados**, ocho capturas y cero excepciones JS. Correos exclusivamente en archivos privados sintéticos, sin proveedor real. `makemigrations --check --dry-run`: sin cambios faltantes; OpenAPI `--fail-on-warn`: exit 0; diff-check sin errores. Revisiones independientes de backend de revisión y outbox sin P1/P2 nuevos.

API y worker visuales comparten ahora imagen `sha256:2f610b36919d1b1f742eb982a97e691e8122beecf9bb0a678720f3bd0ce89afc`, posterior a ambos paquetes. La base de test fue eliminada; solo permanece la DB sintética del laboratorio. Quedan por definir configuración/recepción de proveedor, tasas y vigencias productivas, custodia/retención del payload y atención de alertas. Las decisiones de revisión y opción B ya están resueltas, no se vuelven a solicitar. No hay commit/push/merge/despliegue ni cierre de la auditoría completa. La aceptación humana/comprensión de estos nuevos bloques sigue pendiente; los resultados automáticos no la acreditan.

## Aceptación y siguiente bloque

El dueño respondió «acepto y continua» al resultado local de revisión/outbox. Se registra la aceptación de ese bloque y la autorización de continuar, sin atribuirle un ejercicio de explicación de fallos que no realizó. No equivale a aceptación de producción ni cierre del inventario.

Se investigan AUD-043/045 (formato de sello versionado y suspensión de receta), AUD-049 (ventanas del portal contra estado bloqueado) y AUD-052/054 (rechazo/conservación de pedidos). Se mantienen firmas históricas sin resellar, las reglas de mostrador, las entregas y movimientos existentes. El modelo actual de pedidos no tiene borrador: la definición de eliminación de pendientes se consultó al dueño antes de introducirla; el resto del paquete puede avanzar independientemente. Ningún estado nuevo de pedido, clave de operación ni esquema de stock se deduce de esta continuación.

**Primer resultado del bloque:** 300 tests aprobados sin skips de clínica, agenda y portal en PostgreSQL, comando exacto en `2026-10-15-integridad-clinica-172.md`. AUD-043 escribe formato JSON inequívoco v2 con lectores v1 byte-compatibles; AUD-045 serializa Historia→Receta y conserva una única suspensión. AUD-049 usa política de canal existente y reloj posterior al lock: cancelar con >=24 h exactas, confirmar en futuro, sin imponer esa restricción al mostrador. Rojo inicial de 043/045: ocho métodos, siete fallos incluyendo subcasos. Rojo conjunto farmacia/portal: 17 métodos, 13 fallos y dos errores del helper de aserción portal por acceder a `codigo` ausente; corregido el helper para afirmar status antes de inspeccionar el cuerpo. No fueron dos excepciones productivas. Casos de reprogramación y tiempo actual quedaron verdes en la tanda de 300.

Revisión cruzada de farmacia encontró un P2 adicional: DELETE de un pendiente tras la lectura de rechazo causaba `Pedido.DoesNotExist` y HTTP500. Se reprodujo en un test separado con un error esperado, antes de traducirlo a `ErrorStock`/400. Los guards directos de conservación siguen siendo una corrección parcial mientras el dueño define pendientes sin efectos y se resuelven padres/Admin. No se afirma cerrar AUD-054.

Se prepara además la contención de redirects de AUD-005 en los dos transportes existentes (motor genérico y consulta FHIR), conservando allowlist y deshabilitación por defecto. El ensayo usa HTTP real de loopback interno al contenedor, sin proveedor ni salida externa. DNS, puertos, subdominios y egreso no se dan por resueltos por bloquear redirects; continúan sujetos a configuración/proveedor.

### Corte validado: clínica, portal, pedidos y redirects

| ID | Resultado local y límite |
|---|---|
| AUD-043 | Nuevos sellos v2 inequívocos, lectura v1 sin alterar bytes, desconocidos no verificables. API expone `sello_version` readonly; UI distingue histórico/actual/incompatible/alterado y el panel informa problemas de verificación sin acusar alteración por versión desconocida. No resella historia ni elimina ambigüedad de v1. Release requiere lectores v2 compatibles. |
| AUD-045 | Suspensión serializada Historia→Receta, una transición/asiento/sello, repetición400 y desaparición404. Rollback probado con fallo de sellado inyectado. No cambia el tratamiento heredado de autoría en simulación ni cierra la matriz AUD-039. |
| AUD-049 | Política portal y reloj actuales bajo lock; >=24h cancelación, futuro para confirmar, listado y acción coherentes. Mostrador conservado. Aviso por falta de confirmación sigue dependiendo de destinatario/momento pendientes. |
| AUD-052 | Rechazo comparte lock/relectura con preparación/entrega; cierra saldo pendiente y conserva cantidades/movimientos. PATCH no restaura estado ni devuelve líneas precargadas antiguas. No resuelve replay de entrega parcial (AUD-053). |
| AUD-054 | DELETE directo409 tras actividad/estado no pendiente, incluyendo incoherencias legacy de entregado/resuelto/movimiento. **Parcial:** dueño aún debe definir pendientes sin efectos; cascadas de padres y Admin no están cerradas. No hay estado borrador ni constraint nueva. |
| AUD-005 | Ambos transportes rechazan301/302/303/307/308 antes de interpretar Location; cierran origen y sanitizan excepción. **Parcial:** conserva política inicial de hosts/puertos/DNS/proxy/egreso, sin proveedor real habilitado. |

Validación serial en PostgreSQL:

- Tanda de **300 aprobadas** de clínica/agenda/portal, citada arriba. Tanda de **105** farmacia+redirects antes del fix005: farmacia pasó; 17 fallos de redirects incluyendo subcasos. El contador de destino se aisló después por subcaso: el rojo demuestra saltos explotables, no que todos los POST307/308 previos los siguieran.
- Después de los cambios, `manage.py test apps.casos apps.fhir apps.farmacia apps.registros.test_formato_suspension_auditoria172 --noinput --verbosity 1`: **550 ejecutadas, un fallo**, sin errores/skips, 145,763 s. El único fallo fue la barrida de permisos: create de usuarios devolvía503 por configuración antes de verificar permisos. Redirects, FHIR, farmacia y formato/suspensión pasaron en esa tanda. No se presenta toda la tanda como aprobada.
- La corrección de orden expuso una expectativa incorrecta en una prueba nueva de acción de detalle: el permiso de objeto se decide al resolver el queryset, no en `initial`. Tanda intermedia de **199**, un fallo de esa expectativa, sin otros fallos/errores/skips. Recuperación administrativa ahora resuelve/autoriza el objeto scopeado antes de configuración; create verifica capacidades antes de configuración y tasas. Recuperación pública mantiene encolado sin lookup. No se modificó `CapacidadPermission` ni la matriz de roles para hacer pasar tests.
- Corte final: `manage.py test apps.accounts.test_identidad_administrativa_auditoria172 apps.accounts.test_credenciales_auditoria172 apps.casos.test_permisos_barrida --noinput --verbosity 1`: **48 aprobadas sin skips**, 30,915 s. Roles denegados reciben403 en create y404 uniforme al objeto administrativo fuera de ámbito; admin sin configuración recibe503 sin crear/enviar. Los resultados de 199/550 no se renombran como una nueva corrida verde completa; sus restantes pruebas pasaron en aquellos cortes y el cambio final se verificó focalmente.
- Build frontend aprobado, auditor CSS287 sin colisiones/huérfanas. OpenAPI `--fail-on-warn` exit0 y `makemigrations --check --dry-run` sin cambios pendientes. No se modificaron dependencias ni lockfile. Las regresiones E2E de renderer/panel se agregaron a la suite existente, pero esa suite general no se ejecutó por requerir el escenario demo.
- Navegador real sobre API/PostgreSQL del corte final: **19 controles aprobados**, desktop/mobile, cuatro tipos de sello y panel mixto; clases y colores compilados comprobados, sin overflow horizontal ni excepciones JS. Fixture nueva exclusivamente sintética con fallos controlados, sin tocar registros anteriores; sin respuestas API simuladas. Evidencia `output/playwright/aud172-sellos-evidencia.json` y capturas `aud172-sellos-desktop.png` / `aud172-sellos-mobile.png`.

Revisiones cruzadas de 043/045,049,005 y orden de identidad sin P1/P2 abiertos en esos deltas. El P2 de desaparición en rechazo se reprodujo y corrigió; el P2 de etiquetas globales de verificación también se corrigió. Persisten las fronteras parciales listadas, no son aceptación de riesgos por parte del dueño.

Imagen final de tests focales48/API/worker: `sha256:007e39fb108b33f1a702a300544cb95d66cfbb5ab6f5b4ced421cbd54126db98`. Los cortes300/550/199 corresponden a imágenes anteriores, con límites y resultados anteriores descritos. Base `test_auditoria172` eliminada; base sintética saludable. API y worker fueron recreados juntos para usar el lector v2; correo reanudado y sin pendientes/errores al consultar. Sin suite global, CI, carga, restore, proveedor externo, commit, push, merge ni despliegue productivo.

### Decisión de conservación y entrega en Git

El dueño decidió: «conservarlos todos y cerrarlos mediante rechazo». Incluye pedidos PENDIENTE sin efectos; no se introduce una excepción de borrador. Se impide DELETE y se protegen los depósitos referidos por pedidos. Rechazar conserva cantidades ya entregadas y movimientos; no se ejecuta un cierre masivo de pedidos históricos. El objetivo es mantener la trazabilidad, sin reconstruir entregas ni alterar stock por el rechazo.

También autorizó commits sistemáticos en una rama y la apertura de PR. Rama de trabajo: `juanikitro/auditoria-172-implementacion`, creada desde `c6f101b089ee4950e6133390bd4c888a280f31b5`; `main` remoto coincidía al iniciar este corte. Los commits se separan por laboratorio, identidad/correo, seguridad, clínica, operación y pedidos. El PR será borrador mientras siga parcial el inventario; no cerrará automáticamente #172. No hay autorización de merge ni despliegue productivo.

Las capturas y JSON de navegador siguen como artefactos locales ignorados en `output/playwright/`, conforme al criterio existente de no versionar corridas de Playwright; las pruebas y la evidencia resumida sí se versionan. Los scripts temporales privados y archivos de entorno no se incluyen en Git. Las validaciones históricas no se presentan como CI ni se atribuyen a un SHA posterior sin una nueva ejecución.
