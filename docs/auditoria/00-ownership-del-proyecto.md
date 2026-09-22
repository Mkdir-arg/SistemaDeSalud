# Ownership del proyecto

> Documento progresivo construido mediante una revisión interactiva de ownership. Las respuestas de la persona que aprende orientan las preguntas y permiten comprobar su modelo mental, pero no son por sí mismas fuente de verdad. Cada afirmación se clasifica según la evidencia disponible al momento de escribirla: **Confirmado** exige una referencia del repositorio; **Inferido** es una síntesis razonada todavía no validada; **Pendiente de confirmar** requiere más evidencia.

## 1. Qué problema resuelve

- **Confirmado:** el sistema gestiona la atención de pacientes como **casos trazables**. Un caso concentra su estado, prioridad, nodo actual, área, asignación, datos completados, fila, llamados, eventos y vínculo con la historia clínica. Referencia: `docs/funcionalidades/casos-guardia-filas/README.md`.
- **Confirmado:** el caso permite coordinar un circuito entre equipos —por ejemplo admisión, triage, atención médica, estudios, interconsultas, internación y alta— en vez de operar módulos aislados. Referencia: `docs/ESCENARIO-GUARDIA.md`.
- **Confirmado:** los flujos publicados modelan y ejecutan esos circuitos; una versión del flujo determina el recorrido del caso y el nodo actual determina las acciones disponibles. Referencia: `docs/funcionalidades/flujos-motor/README.md`.
- **Inferido:** el valor operativo principal es reducir la pérdida de contexto y descoordinación entre etapas de atención, preservando trazabilidad y priorización. Debe validarse con usuarios reales y objetivos institucionales.

## 2. Usuarios y actores

- **Confirmado:** los equipos operativos incluyen administrativos de admisión, enfermería y médicos/profesionales; actúan sobre los pasos asignados del caso. Referencias: `docs/funcionalidades/casos-guardia-filas/README.md`, `docs/ROLES-Y-PERMISOS.md`.
- **Confirmado:** un configurador institucional diseña circuitos, formularios, nodos, conexiones, reglas, derivaciones y validaciones; no opera casos por ese rol. Referencia: `docs/ROLES-Y-PERMISOS.md`.
- **Confirmado:** un jefe o supervisor de área gestiona excepciones operativas, como reasignar, repriorizar o cancelar casos según su alcance. Referencia: `docs/ROLES-Y-PERMISOS.md`.
- **Confirmado:** el paciente puede aparecer en una pantalla pública de llamado, pero no ejecuta el flujo. Referencia: `docs/funcionalidades/casos-guardia-filas/README.md`.
- **Confirmado:** la autorización combina membresía activa en la institución dueña del caso, capacidades derivadas del rol y, cuando el nodo las declara, pertenencia a sus grupos responsables. Referencias: `backend/apps/accounts/models.py`, `backend/apps/common.py`, `backend/apps/flujos/models.py`.

## 3. Casos de uso principales

- **Confirmado:** crear e iniciar casos; tomar, llamar, rellamar, devolver a fila, marcar ausente y avanzar por el flujo. Referencia: `docs/funcionalidades/casos-guardia-filas/README.md`.
- **Confirmado:** gestionar guardia mediante admisión, triage, prioridad, fila, conducta médica y desenlaces de alta, observación, derivación o internación. Referencia: `docs/ESCENARIO-GUARDIA.md`.
- **Confirmado:** ejecutar estudios e interconsultas como subprocesos cuyo resultado permite que el caso retome la atención solicitante. Referencias: `docs/ESCENARIO-GUARDIA.md`, `docs/funcionalidades/flujos-motor/README.md`.
- **Confirmado:** configurar, ensayar, publicar y versionar flujos de atención. Referencia: `docs/funcionalidades/flujos-motor/README.md`.

## 4. Mapa de alto nivel

- **Pendiente de confirmar:** se reconstruirá con evidencia de frontend, API, motor de dominio, persistencia, procesos periódicos e integraciones.

## 5. Componentes principales

- **Pendiente de confirmar:** se identificarán por responsabilidad, no sólo por carpetas o tecnologías.

## 6. Dominio y entidades

- **Confirmado:** un flujo es un circuito versionado; un nodo es un paso de su grafo y puede representar, entre otros, un formulario, atención, decisión, espera, derivación, cama, notificación, integración o fin. Referencia: `backend/apps/flujos/models.py`.
- **Confirmado:** un área es una unidad organizativa configurable por institución; un grupo es un equipo de personas dentro de un área. No son sinónimos de rol o permiso. Referencia: `backend/apps/instituciones/models.py`.
- **Confirmado:** los roles vigentes están predefinidos en el código; las áreas y los grupos son configurables por institución. Referencias: `backend/apps/accounts/models.py`, `backend/apps/instituciones/models.py`.

## 7. Flujos críticos

- **Confirmado:** Guardia es el flujo inicial de referencia: admisión, triage, fila priorizada, conducta médica y desenlaces de alta, observación, derivación o internación. Referencia: `docs/ESCENARIO-GUARDIA.md`.
- **Confirmado:** la configuración y publicación de flujos es transversal; una versión determina el recorrido y las acciones de los casos que se ejecutan sobre ella. Referencia: `docs/funcionalidades/flujos-motor/README.md`.
- **Pendiente de confirmar:** se reconstruirán de manera interactiva los demás flujos prioritarios, su frecuencia de uso y su criticidad clínica/operativa.

## 8. Integraciones externas

- **Pendiente de confirmar:** se inspeccionarán contratos, configuración y puntos de fallo antes de afirmar dependencias externas.

## 9. Persistencia y datos

- **Pendiente de confirmar:** se documentarán fuentes de verdad, entidades y límites de consistencia tras inspeccionar modelos y migraciones relevantes.

## 10. Decisiones técnicas importantes detectadas

- **Confirmado:** los flujos publicados se trabajan mediante versiones y no deberían editarse directamente. Referencia: `docs/funcionalidades/flujos-motor/README.md`.
- **Pendiente de confirmar:** falta identificar las decisiones de despliegue, trabajos periódicos, almacenamiento e integraciones y sus consecuencias.

## 11. Riesgos conocidos

- **Confirmado:** aún no se detectó un riesgo P0 que justifique crear un issue en esta sesión.
- **Confirmado:** una prioridad de triage incorrecta altera el orden real de la fila y puede demorar atención urgente; además distorsiona los tiempos y estados usados en supervisión. Referencias: `backend/apps/casos/models.py`, `backend/apps/casos/views.py`.
- **Confirmado:** si un nodo operativo no declara grupos responsables, puede ser operado por cualquier usuario que tenga la capacidad amplia aplicable dentro de la institución. El riesgo es de configuración de flujo y de falta de separación operativa, no un bloqueo del motor. Referencias: `docs/ROLES-Y-PERMISOS.md`, `backend/apps/flujos/models.py`.
- **Pendiente de confirmar:** se evaluarán riesgos de datos clínicos, continuidad operativa e integraciones después de reconstruir sus recorridos reales.

## 12. Preguntas abiertas

- **Pendiente de confirmar:** ¿el proyecto adoptará un nomenclador estatal único para tipos de área, sectores y servicios? Referencia: `docs/funcionalidades/estructura-organizativa/README.md`.

## 13. Cosas que todavía necesito comprender

- **Pendiente de confirmar:** mapa técnico completo y circulación de datos.
- **Pendiente de confirmar:** entidades, invariantes y transiciones del dominio.
- **Pendiente de confirmar:** flujos críticos fuera del escenario inicial de Guardia.
- **Pendiente de confirmar:** dependencias externas, fallos operativos y mecanismo de despliegue.

## 14. Glosario del proyecto

- **Caso — Confirmado:** unidad trazable de atención de un paciente que conserva estado, prioridad, nodo actual, asignación, datos y eventos.
- **Flujo — Confirmado:** circuito de atención versionado que define el recorrido de un caso.
- **Nodo — Confirmado:** paso de un flujo; el caso ocupa un nodo actual y éste define las acciones disponibles.
- **Institución — Confirmado:** establecimiento que delimita la membresía y el alcance de las operaciones.
- **Membresía — Confirmado:** vínculo activo entre una persona, una institución, uno o más roles y áreas.
- **Rol — Confirmado:** perfil predefinido que aporta capacidades funcionales, como `casos_operar` o `reportes`.
- **Capacidad — Confirmado:** permiso funcional amplio otorgado por un rol; no identifica por sí solo qué paso concreto puede operar una persona.
- **Área — Confirmado:** unidad organizativa configurable dentro de una institución, por ejemplo Guardia o Internación.
- **Grupo de trabajo — Confirmado:** equipo configurable dentro de un área que puede declararse responsable de nodos específicos, por ejemplo Triage.
