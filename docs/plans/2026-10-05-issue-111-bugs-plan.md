# Issue #111: corrección integral en un solo PR

Estado: correcciones implementadas y validadas localmente en PostgreSQL y navegador; publicación de PR autorizada. CI, integración contra main actualizado y aceptación humana pendientes.

Fuente: https://github.com/Mkdir-arg/SistemaDeSalud/issues/111

Base contrastada el 05/10/2026: `main` y checkout local en `f494edacfc5c2d9d7429ed73baeb3fbc9f52d0d1`. El checkout estaba limpio antes de agregar este documento. Se leyó el issue, sus referencias pertinentes, código, pruebas y configuración; no se ejecutaron reproducciones, suites, cargas ni servicios.

## Resultado y estrategia

Entregar un solo PR que cubra B1–B7, F1–F6 y D1–D2, incluidos todos los subpuntos. Cada punto debe quedar corregido y verificado, o descartado mediante evidencia cuando el problema dependa del entorno. Una derivación a otro issue requiere una decisión explícita y significa que ese punto no fue resuelto por este PR.

Recomendación: cambios pequeños por causa, agrupados en commits revisables dentro del mismo PR. Primero privacidad y auditoría; después consistencia de autorizaciones y simulación; luego UI y datos; finalmente validación integrada. La alternativa de reescribir serializers, navegación o seeds completos aumenta el riesgo y dificulta atribuir regresiones. Dividir en varios PR contradice el alcance solicitado.

Usar los criterios del issue como aceptación principal. Los casos adicionales de este plan son comprobaciones propuestas para asegurar esos resultados. Antes de implementar deben resolverse las decisiones de B5 y de orden del menú descritas abajo.

Límites: reutilizar helpers y contratos actuales, evitar dependencias nuevas y cambios de esquema salvo necesidad demostrada. No modificar datos clínicos históricos ni registros auditados. No ejecutar cargas en entornos compartidos. Los specs obsoletos y el guion comercial siguen fuera del alcance, como establece el issue. Actualizar pruebas pertinentes que cambien por estos arreglos sí forma parte del PR.

## 1. Privacidad, ficha y trazabilidad

### B2 — Aislamiento entre pacientes, primera prioridad

La lectura de evoluciones filtra por caso y firma, pero no por propietario de la historia. El conteo tiene la misma omisión. `HistoriaFija` impide cambiar la historia de una entrada existente, pero `EntradaHistoriaSerializer` permite asociar un caso de otro paciente.

- En `financiadores/views.py`, agregar la condición de identidad a la lectura y al `Count` usando el ciudadano del caso. Ambos deben devolver el mismo conjunto de entradas firmadas.
- En `registros/serializers.py`, validar el par efectivo historia/caso en creación y actualización parcial; combinar atributos recibidos con los existentes y conservar la validación de `HistoriaFija`. No hacer obligatorio un caso para entradas que legítimamente carecen de él. Rechazar casos sin paciente o ajenos cuando se asocian a una historia.
- No reparar masivamente entradas históricas inconsistentes: deben quedar excluidas de la lectura del financiador.
- Pruebas: entrada ajena firmada creada deliberadamente fuera del serializer, exclusión del contenido y del conteo, rechazo por POST/PATCH, asociación válida y entrada sin caso. Conservar alcance por convenio/afiliación, borradores ocultos y rechazo de roles no autorizados.

Extender `apps.financiadores.test_ficha_historia` y las pruebas de entradas clínicas existentes. Mantener auditoría estricta: si falla, no entregar contenido clínico.

### B1 — Autorizaciones manuales en la ficha

`FichaAutorizacionSerializer` accede a `prestacion.nombre` sin tolerar la ausencia de prestación institucional. La bandeja ya usa `comun.nombre` como alternativa.

- Reutilizar esa resolución de nombre con el menor cambio local. Evitar sustituir indiscriminadamente el serializer por el de bandeja: sus campos, contexto y capacidades son diferentes.
- Preservar los campos de la respuesta de ficha y la consulta optimizada existente.
- Extender `test_ficha_afiliado` con solicitudes manuales, institucionales y mezcla de ambas, incluyendo pendientes; comprobar nombre, respuesta 200 y exclusión de solicitudes de otro afiliado/financiador.

### B3 — Motivo completo y detalle confiable

El registrador de accesos ya acepta `motivo`; `/accesos` sólo lo muestra para exportaciones.

- Guardar el texto validado completo en `AccesoClinico.motivo` y sólo `entradas=<ids>` en `detalle`. Separar el cálculo de los bloques de ids de la longitud del motivo.
- Mostrar el motivo de estos accesos en `pages/auditoria/Accesos.jsx`, sin interpretarlo como filtros ni extraer ids del texto libre.
- Pruebas: espacios, tildes, signos, texto que contiene `; entradas=`, longitud máxima, suficientes ids para varios bloques y auditoría fallida. Todos los ids deben quedar registrados sin truncamiento y el motivo debe repetirse completo en cada bloque.
- Agregar comprobación de UI del motivo completo en ambos temas. No reinterpretar registros históricos ni modificar el parser de todos los recursos sin necesidad.

### B5 — Atribución de lecturas manuales: decisión confirmada

Se confirma en código que la solicitud manual nace sin ciudadano y que las dos rutas de lectura auditan esa FK. La relación administrativa afiliado/solicitud no prueba por sí sola una identidad clínica hospitalaria. La documentación funcional indica que el hospital no recibe estas solicitudes en su bandeja; hay que resolver expresamente su visibilidad en auditoría.

Decisiones solicitadas y confirmadas antes de implementar (detalle en la evidencia):

1. Cómo atribuir una lectura cuando no existe un ciudadano hospitalario identificado con certeza.
2. Qué puede ver el hospital elegido de una solicitud que todavía no recibió.

Recomendación del agente: mantener siempre la traza de solicitud/afiliado y financiador; vincular ciudadano únicamente mediante una identidad inequívoca en la institución correcta. Con coincidencia ausente o ambigua, no inventar paciente, no crear historia clínica y no buscar globalmente para exponer otras instituciones. Definir cómo consultar esa traza administrativa sin ciudadano. Primero comprobar si los campos, relaciones y filtros existentes bastan; cualquier ampliación de contrato o almacenamiento necesita decisión previa.

Pruebas según la decisión: identidad única, inexistente, ambigua, documento normalizado, mismo documento en otra institución, listado y ficha, y permisos de auditoría del hospital. B5 no queda completo sólo por conservar un acceso sin persona.

## 2. Gestión de usuarios y coherencia del backend

### B4 — Proteger las cuentas de referencia

`simulacion/perfiles.py` ya aporta `DOMINIO` y `es_cuenta_referencia`, que considera tanto dominio como relación `CuentaReferencia`. La gestión del financiador no los aplica.

- Excluir cuentas técnicas del listado y del cómputo de administradores reales; rechazar su creación/edición por correo desde esta gestión antes de escribir.
- Mantener el bloqueo transaccional del financiador al cambiar administradores. Probar que dos degradaciones simultáneas no eliminan a todos los admins reales.
- Inspeccionar y probar las rutas equivalentes de membresías institucionales; aplicar la misma protección donde se reproduzca el acceso indebido, preservando el comando legítimo que prepara cuentas técnicas.
- Comprobar si alterar `resuelve_autorizaciones` evita la validación de sesión. Si se confirma, validar ese atributo contra el perfil canónico y rechazar una sesión alterada. No convertir al operador simulado en operador designado mediante una decisión implícita.
- Pruebas: cuentas registradas y cuentas del dominio reservado, intento directo aunque no figuren en UI, último admin real, segundo admin real, modificación de capacidades y simulación válida.

Extender `test_api`, pruebas de membresías y `apps.simulacion.tests`. B4 se resuelve aquí; no se propone derivarlo a #451.

### B6 — Cinco subpuntos

| Subpunto | Acción mínima y evidencia |
|---|---|
| Enumeración de afiliados | Resolver el id dentro del financiador autorizado. Igualar estado y cuerpo públicos para id ajeno e inexistente; probar ambos sin revelar existencia. |
| Reenviar | Alinear `puede_reenviar` con las precondiciones reales del servicio: convenio vigente, afiliación, estado y plazo. Mantener la revalidación transaccional al ejecutar; probar vencimiento y convenio activo fuera de fecha. |
| Adjunto deshabilitado | Devolver 404 en la lectura cuando la capacidad está apagada; probar también adjunto ausente, permisos y lectura habilitada. Preservar la semántica de carga. |
| Consulta de casos | Medir SQL y plan de ejecución en PostgreSQL con volumen representativo. Si se confirma el costo, preseleccionar casos candidatos del afiliado y conservar la selección de afiliación actual más reciente, convenio y pendientes históricos. No basta mover `filter` antes de `annotate`, ni añadir índices sin evidencia. |
| Import sin uso | Eliminar `PermissionDenied` si sigue sin referencias; verificar con el chequeo estático disponible, acotado a archivos afectados. |

Reutilizar `test_autorizaciones_manuales`, `test_autorizaciones`, `test_facturas`, `test_ficha_historia` y fixtures de volumen existentes. Una optimización debe demostrar mismos resultados y mejor plan; si el riesgo no se reproduce, documentar SQL, volumen y límites del ensayo.

### B7 — Concurrencia en PostgreSQL

- Reproducir las consultas paralelas reales del Inicio del financiador, con conexiones independientes y auditoría activa, en PostgreSQL 16 dedicado. Un test secuencial o la UI con API interceptada no sirve para este punto.
- Observar respuestas, errores de base de datos y trazas persistidas. Ensayar además el recorrido desde el navegador sobre ese backend.
- Si no aparece el fallo, documentar requests, concurrencia, repetición y motor; descartar B7 para PostgreSQL sin afirmar que se corrigió SQLite.
- Si aparece, identificar el bloqueo/transacción causal y corregirlo con una regresión concurrente. Conservar el protocolo de bloqueos y la auditoría obligatoria; no ocultar el fallo ni agregar reintentos generales por intuición.

## 3. UI: todos los puntos y subpuntos

| ID | Cambio propuesto | Aceptación y regresión |
|---|---|---|
| F1 | Reparar texto y comentarios dañados de `Shell.jsx`; buscar U+FFFD y controles inesperados en `frontend/src`. | Selector legible en ambos temas; revisión de cada coincidencia, evitando conversión masiva de archivos. |
| F2 | En `AgendaSemana.jsx`, ajustar escala temporal y geometría: actualmente 15 minutos equivalen a 10 px, pero el bloque exige al menos 14 px. | Bloques y etiquetas legibles sin solaparse para intervalos 15/20/30 minutos; clic, bloqueos y arrastre siguen correspondiendo a la misma hora. Probar agendas de Vega y Méndez. |
| F3 | Usar primero `align="right"`, ya disponible en `Ayuda`, en Inicio. | Popover entero dentro del viewport a 1440 px y en móvil; ambos temas, apertura, cierre y Escape. Ampliar el componente sólo si la prueba demuestra que la alineación no basta. |
| F4a | Tildes en el rechazo de acceso de `App.jsx`. | Médico simulado recibe el mensaje correcto. |
| F4b | Fechas y períodos legibles en Facturas y Reservas/saldos; presentar reservas recientes primero con orden del servidor compatible con paginación. | No desplazar fechas por UTC; verificar filtros, navegación y orden entre páginas. |
| F4c | Ficha: etiquetas de estado, pluralización, rol legible y estado vacío para cero evoluciones. | 0/1/varias evoluciones; con cero no pedir motivo ni enviar lectura clínica; conservar motivo obligatorio para contenido. |
| F4d | Singular/plural en `PaginasAutorizacion`, reutilizando `plural`. | 0/1/varias solicitudes y paginación existente. |
| F4e | Nombre de agenda sin repetir especialidad ni mostrar `profesional` crudo. | Mantener distinción entre agendas profesionales y de recursos, sin cambiar identificadores ni búsqueda. |
| F5a | Explicar campos obligatorios y motivo del botón deshabilitado al aprobar. | Fechas vacías, invertidas y válidas; mensajes asociados a campos. No inventar vigencias automáticas. |
| F5b | Deshabilitar «Llamar siguiente» cuando el perfil efectivo no puede llamar, también en otras superficies que ofrecen esa acción. | Superadmin directo deshabilitado; rol simulado autorizado puede operar; rechazo backend intacto. |
| F5c | Orden DIRECCIÓN/OPERACIÓN basado en perfil efectivo. | Acordar qué perfiles requieren DIRECCIÓN primero; conservar permisos y testear simulación y usuario real equivalente. |
| F5d | Permitir volver al tablero autorizado de Instituciones desde el contexto hospitalario. | `test@salud.local` vuelve y reingresa; revisar `Entrada` en `App.jsx` y Shell, sin conceder gobierno de plataforma a otros usuarios. |
| F5e | Manejar paciente no disponible en el contexto actual en `PacienteDetalle.jsx`. | Mensaje contextual para 404 sin revelar si existe en otro hospital; 500/red conservan mensaje técnico apropiado; ningún dato anterior permanece visible al cambiar institución. |
| F6 | Fondo/texto de la miniatura app en `Presentacion.jsx` con contraste suficiente. | Medir al menos 4,5:1 para ambos textos en ambos temas, incluida la peor zona del degradado si se mantiene. |

Mantener helpers de formato y etiquetas existentes. Probar fechas de calendario cerca de medianoche y cambio de mes; las fechas sin hora no deben tratarse como instantes UTC.

La geometría de F2 y el contraste de F6 requieren comprobaciones visuales/medidas, además de aserciones de texto. No basta que el elemento esté visible.

## 4. Datos de demo

### D1 — Un paciente por situación activa compatible

La carga viva de `seed_volumen` elige mediante `random.choice` sobre todo el padrón, después del histórico y de asegurar trabajo por área. Ese mecanismo permite reutilizar pacientes que ya tienen actividad abierta. Rastrear además si el recorrido histórico dejó internaciones abiertas antes de asignar escenas actuales.

- Seleccionar pacientes disponibles para cada escena, considerando casos vivos existentes, filas y estadías. Mantener coherencia por episodio: las transiciones legítimas guardia→internación no se prohíben por contar dos casos relacionados.
- Evitar paciente repetido en una fila y ocupaciones simultáneas incompatibles; si el padrón no alcanza, ampliar el conjunto ficticio de forma determinista en lugar de reutilizar ocupados o omitir escenas silenciosamente.
- Evitar nombres completos idénticos en pacientes de camas distintas de esta demo. No usar el nombre como identidad ni imponer unicidad de nombres al modelo real.
- Conservar casos históricos repetidos legítimos y cubrir cada área necesaria para el recorrido.
- Ampliar `CargaCompletaTests`: tras toda la carga, comprobar filas, guardia, espera de internación y estadías abiertas por ciudadano/episodio; probar carga chica y completa, repetición con la misma ancla y rollback si falla un paso.

### D2 — Cada subpunto debe verificarse

- Mostrar prioridad cuando altera la posición de la fila y conservar el orden clínico; generar tiempos de espera acordes al escenario actual, sin cambiar la regla de prioridad real.
- Variar cantidades, fechas y prestaciones de los seis meses del financiador de manera determinista. Preservar los casos financieros que demuestran cupos, autorizaciones, deuda y pago.
- Revisar la concentración de actividad de hoy en Central; repartir escenarios actuales e históricos sin vaciar el trabajo operativo ni adulterar métricas productivas.
- Dejar la agenda de entrada con disponibilidad el día de demostración. Probar lunes, fin de semana y fecha anclada; distinguir seed de selección UI antes de cambiar horarios profesionales.
- Distribuir fechas de facturas `DEMO-` según estados y períodos coherentes; mantener vencimientos e importes consistentes. Origen: `sembrar_facturas_demo` en `seed_financiadores.py`.
- Dejar actividad y/o ocupación coherente en Pediatría, con edades apropiadas para el escenario.
- Revisar la clasificación/configuración de «Ingreso a Guardia» para evitar «Circuito no definido» sin ocultar configuración realmente ausente.
- Para el aviso de repartos, comprobar worker y latido reales del stack aislado. Si el proceso estaba apagado, validar con el proceso activo y documentar la causa de entorno; no fabricar actividad ni esconder la alerta.

Extender pruebas del seed y verificar tableros usando las consultas reales. Usar ancla controlada: los escenarios futuros y las vigencias de autorizaciones caducan o cambian al avanzar el reloj.

## 5. Ejecución eficiente y estructura del PR

1. Confirmar las decisiones pendientes, actualizar la base antes de empezar y mantener este worktree aislado. Convertir cada subpunto anterior en una casilla de la descripción del PR; no crear otro tracker.
2. Fijar reproducciones pequeñas de B2/B1/B3/B4 y correr sólo esos módulos. Corregir cada causa y verificar antes de avanzar.
3. Resolver B5 según la decisión, completar B6 y ensayar B7 con PostgreSQL desde temprano para descubrir bloqueos antes de terminar la UI.
4. Corregir UI reutilizando componentes/helpers; aplicar F2/F3 con evidencia geométrica y probar consumidores afectados.
5. Corregir seeds, ampliar invariantes y realizar una sola carga integral aislada por escenario necesario. Reutilizarla para navegador y concurrencia; correr suites de backend por separado de workers.
6. Hacer revisión integral, ejecutar checks oficiales pertinentes y adjuntar evidencia de todos los puntos. Mantener el PR como draft si falta B5, PostgreSQL, navegación real, verificación visual o aceptación.

Commits propuestos, ajustables según el diff final:

- `fix(financiadores): aislar evoluciones y completar auditoria de accesos`
- `fix(simulacion): proteger cuentas de referencia y admins reales`
- `fix(financiadores): corregir contratos de autorizaciones y adjuntos`
- `fix(ui): corregir agenda ayudas y navegacion contextual`
- `fix(demo): generar escenarios activos coherentes`
- `test(demo): verificar regresiones integradas del issue 111` si queda evidencia transversal que no corresponde a los commits anteriores.

Cada commit funcional incluye sus pruebas; no concentrar toda la cobertura al final. Un PR con `Closes #111` sólo cuando todas las casillas estén satisfechas. Título sugerido: `fix: corregir bugs de financiadores, interfaz y demo (#111)`.

## 6. Validación y evidencia de cierre

Backend, desde `backend/`, en un entorno de pruebas configurado y autorizado:

```powershell
python manage.py test apps.financiadores.test_ficha_historia apps.financiadores.test_ficha_afiliado apps.financiadores.test_autorizaciones_manuales apps.financiadores.test_api apps.financiadores.test_facturas apps.simulacion.tests --noinput
```

Agregar las clases de entradas clínicas/membresías afectadas y el ensayo concurrente nuevo. Para PostgreSQL dedicado ya existe `config.settings_financiadores_postgres_test`; exige URL local a `salud_financiadores_test` y usa `test_salud_financiadores_test`. Verificar que ninguna otra corrida use esa base antes de reutilizarla, o configurar otro nombre aislado. No imprimir credenciales.

```powershell
python manage.py test apps.demo.tests --settings=config.settings_financiadores_postgres_test --noinput
```

Navegador con API interceptada, desde `frontend/`, usando sólo specs pertinentes:

```powershell
npx playwright test -c playwright.financiadores-ui.config.js e2e/autorizaciones-ui.spec.js e2e/padron-cobertura-ui.spec.js e2e/simulacion-ui.spec.js e2e/inicio-ui.spec.js e2e/landing-ui.spec.js e2e/pacientes-ui.spec.js
```

La configuración actual tiene un solo proyecto de escritorio: las pruebas nuevas deben cubrir explícitamente tema claro/oscuro y viewports necesarios. Agenda y auditoría necesitan integrarse en una configuración aislada pertinente; no afirmar cobertura con un spec que no entra en `testMatch`.

Recorrido real sobre PostgreSQL sembrado: login de comprador, retorno a Instituciones, cambio de institución, agendas de Vega/Méndez, autorización manual→ficha, aprobación→auditoría hospitalaria, fila→internación y dashboards. Añadir roles reales y simulados autorizados/denegados. La API interceptada prueba presentación, pero no permisos, persistencia, worker ni concurrencia.

Gates del PR: workflows existentes `backend.yml` y `calidad.yml`, para suite completa PostgreSQL, migraciones consistentes, build, auditor de clases y OpenAPI. No ejecutar suites completas locales ni levantar/parar Docker o workers compartidos sin autorización; el código y el plan pueden prepararse antes. Una carga demo borra la base: sólo realizarla con autorización y destino aislado verificado. No hay autorización de deploy ni merge en esta solicitud.

Reporte por punto: criterio observable, prueba/recorrido, resultado real, entorno/SHA y evidencia faltante. No usar las 1943 pruebas SQLite citadas por el issue como evidencia de este futuro PR. `docs/PRUEBAS.md` contiene diagnósticos históricos de main: verificar vigencia antes de atribuir fallas actuales.

Antes de recomendar incorporación, revisar con el usuario qué cambió, posibles fallas, detección y reversión. Solicitar al menos dos modos de falla plausibles al cerrar la implementación. Este plan no demuestra comprensión humana ni aceptación de decisiones pendientes.

## Riesgos y reversión

- Privacidad: lectura/conteo divergentes, asociaciones por documento ambiguas y datos de otra institución retenidos en caché. Mitigar con pruebas negativas y cambio explícito de contexto.
- Simulación: esconder cuentas del listado no evita edición directa ni elevación de capacidades; probar endpoints y validación de sesión.
- Concurrencia: los checks de último admin y las lecturas auditadas necesitan PostgreSQL y conexiones independientes.
- Seeds: ajustar volumen puede romper escenarios financieros o dejar áreas vacías; verificar invariantes tras toda la carga.
- Reversión: código por commits lógicos; evitar restaurar una vulnerabilidad de privacidad como rollback rutinario. La nueva carga ficticia se puede reconstruir en su base aislada. No revertir o reescribir auditorías históricas. Si se requiere una migración o cambio de contrato, redefinir y aprobar su reversión antes de implementarlo.

## Implementación y evidencia — 05/10/2026

Decisiones confirmadas por el usuario: B5 atribuye por coincidencia única de
documento normalizado en la institución elegida, permite auditoría hospitalaria
sin incorporar la manual a su bandeja y no crea pacientes. F5c muestra DIRECCIÓN
antes que OPERACIÓN para perfiles simulados y usuarios reales equivalentes.

| Puntos | Implementación | Evidencia disponible / faltante |
| --- | --- | --- |
| B1 | Nombre de prestación manual desde el catálogo común cuando no existe prestación institucional. | Prueba HTTP de ficha manual 200 y nombre correcto. |
| B2 | Lectura y conteo por ciudadano del caso; validación historia/caso en POST y PATCH. | Pruebas negativas de entrada ajena, borradores y casos sin asociación válida; positivos conservados. |
| B3 | Motivo completo en `AccesoClinico.motivo`; detalle contiene sólo ids, dividido en bloques. | Pruebas de motivos con separadores, consulta de 160 entradas y visualización del motivo. |
| B4 | Cuentas reservadas ocultas e ineditables en gestión de usuarios/membresías; no cuentan como último admin real; capacidad canónica validada. | Pruebas API y de referencia alterada. Introspección propia preservada. Dos bajas concurrentes en PostgreSQL producen 201/400 y conservan un admin real. |
| B5 | Helper común de atribución de consultas manuales para bandeja y ficha. | Pruebas documento con separadores, vacío/NN, otro hospital, sin paciente nuevo y traza hospitalaria sin solicitud en bandeja. Coincidencia canónica apoyada en normalización y unicidad de `Ciudadano`. |
| B6 | Afiliado ajeno/no existente devuelve el mismo 404; adjunto GET deshabilitado 404; reenvío considera convenio vigente y plazo; candidatos del afiliado antes de las subconsultas de casos; import sin uso eliminado. | Pruebas de contrato/vigencia. EXPLAIN ANALYZE sobre 20.642 casos: mismos ids, mediana 102,981→0,629 ms y 20.642→4 iteraciones correlacionadas. Tres muestras por versión; datos sintéticos revertidos mediante transacción. Resultado local, sin promesa general de latencia. |
| B7 | Ensayo de seis lecturas simultáneas con auditorías completas. | PostgreSQL: seis HTTP 200, seis eventos y cuatro auditorías clínicas; Inicio real completa diez lecturas paralelas con 200. El bloqueo de escritura observado en SQLite no se atribuye al worker ni se evita suprimiendo auditorías. |
| F1 | Caracteres corruptos reparados en Shell. | Selector de institución probado en ambos temas. |
| F2 | Escala compartida de grilla/bloques ampliada para intervalos 15/20 min. | Medición geométrica sin solapamiento y clic al día en ambas agendas y temas. |
| F3 | Ayuda alineada y ajuste compartido a los bordes del viewport. | Geometría 1440 y 390 px, claro/oscuro. |
| F4 | Acentos, formatos de fecha/mes, reservas recientes primero, etiquetas/plurales, rol financiador, casos sin evoluciones y selector de agendas. | Pruebas de fechas de calendario, cero/una evolución, motivo y selector. Orden de reservas inspeccionado. Ficha manual y agendas verificadas contra el backend real; no hay recorrido real específico del orden de reservas. |
| F5 | Fechas obligatorias e invertidas explicadas/bloqueadas; superusuario no llama; orden acordado; retorno autorizado al directorio; 404 contextual de paciente. | Navegador con API interceptada para fechas y llamada. Recorridos reales: comprador vuelve al directorio/reingresa, perfil simulado ordena menú, otro hospital devuelve 404 contextual; consulta clínica simulada conserva autoría del root. |
| F6 | Miniatura de app usa tokens de contraste sólido. | Contraste medido ≥4,5:1 claro/oscuro; ambos textos heredan los mismos tokens. |
| D1 | Pacientes disponibles para escenas activas, ampliación ficticia si faltan; nombres demo diferenciados por institución. | Carga integral y recarga con igual ancla verifican invariantes. Seis regresiones de padrón pequeño/higiene prueban filas, camas, guardia/internación y edades. La primera validación exigía nombres únicos entre hospitales; se corrigió ese criterio para el listado institucional. |
| D2 | Prioridad alta visible, esperas recientes; cantidades mensuales y fechas de facturas variadas; histórico reciente distribuido; agenda inicial disponible según fecha; pediatría y clasificación de Guardia. | Carga real de 120 casos/30 días: cantidades mensuales variadas, ocho fechas de factura por organización, espera máxima de 124 min al medir y menor internado en Pediatría. Se corrigió la higiene acumulada que podía impedir el pase pediátrico, limitada a la institución. Worker real con latido y Finanzas sin aviso de inactividad; no se ocultó el aviso. |

Última tanda de backend: **162 aprobadas en PostgreSQL, sin omisiones**, en
83,705 segundos. Comando desde `backend/`, con `SALUD_TEST_POSTGRES_URL` apuntando
a la base aislada autorizada (credenciales fuera del repo):

```powershell
$env:DJANGO_SSL_REDIRECT = 'false'
$env:PYTHONIOENCODING = 'utf-8'
python manage.py test apps.financiadores.test_issue111 apps.financiadores.test_ficha_historia apps.financiadores.test_ficha_afiliado apps.financiadores.test_autorizaciones_manuales apps.financiadores.test_facturas apps.financiadores.test_api apps.simulacion.tests apps.registros.tests_integridad apps.demo.test_issue111 --settings=config.settings_financiadores_postgres_test --noinput
```

Carga integral/recarga, rollback y concurrencia: **32 aprobadas** en PostgreSQL,
803,198 segundos. Esta tanda precedió al último ajuste de higiene; dicho ajuste
se verificó después en las seis regresiones incluidas en la tanda de 162 y en
un seed parcial real. Comando:

```powershell
python manage.py test apps.financiadores.test_ficha_historia apps.financiadores.test_issue111 apps.demo.tests --settings=config.settings_financiadores_postgres_test --noinput
```

La tanda inicial amplia tuvo una falla por el criterio de nombres entre hospitales
mencionado arriba; las tandas posteriores corrigieron el criterio y pasaron.

Navegador: **30 aprobadas**, desde `frontend/`:

```powershell
npx playwright test -c playwright.issue111.config.js e2e/issue111-ui.spec.js
```

La configuración nueva utiliza puerto 5199 y artefactos en `%TEMP%/hen-issue111-ui`.
El puerto habitual 5187 estaba siendo usado por otro worktree; no se detuvo ese
servicio. Las pruebas de interfaz interceptan la API, por lo que no prueban
persistencia, permisos del backend ni concurrencia. Sintaxis JSX comprobada con
esbuild; `git diff --check` sin errores.

Recorrido con backend/worker/PostgreSQL reales: **7 aprobadas**, con puerto 5219,
backend 8119 y artefactos temporales. `HEN_111_REAL_PASSWORD` y
`HEN_111_REAL_METADATA` se cargan del entorno aislado; el spec se omite si faltan.
No se graban trazas con credenciales. Comando:

```powershell
npx playwright test -c playwright.issue111-real.config.js
```

El último ensayo corrigió un selector de test que esperaba un título inexistente;
las diez respuestas de Inicio ya eran 200 antes de corregirlo. Build de Vite
aprobado (`npm run build`), auditor de clases aprobado (`npm run auditar`, 275
clases sin huérfanas/colisiones), OpenAPI aprobado con `--fail-on-warn` y
`makemigrations --check --dry-run` sin cambios.

Todo se ejecutó en un contenedor PostgreSQL 16 nuevo `hen-issue111-20261005-pg`,
puerto local 55419 y datos ficticios. Los casos sintéticos del ensayo SQL se
revirtieron. Para el seed pediátrico parcial posterior a preparar cuentas técnicas,
se apartaron sus enlaces de grupos sólo en la fixture y se restauraron en `finally`:
el comando parcial existente puede seleccionar un actor técnico incompatible si
se ejecuta después de preparar referencias. La carga integral sigue su orden normal.
Las esperas reportadas son relativas al momento de la carga; envejecen con el reloj.

Evidencia temporal: `hen-111-postgres-regressions.log`,
`hen-111-postgres-final.log`, `hen-111-real-browser-final.log`,
`hen-111-build.log` y `hen-issue111-runtime/sql-metrics-final.json`, bajo `%TEMP%`.
No se ejecutó la suite completa de todos los módulos ni CI de GitHub. No hay
validación humana de todas las pantallas; el orden de reservas sólo tiene
evidencia de implementación y no un recorrido integrado propio.

Se intentaron dos specs existentes: `inicio-ui` falla por la expectativa de
«Personal activo» de una cuenta sin supervisión, y `autorizaciones-ui` espera el
botón «Ver solicitud 91», cuyo nombre actual es «Revisar». Son fixtures/selectores
obsoletos del alcance excluido por el issue. No se modificaron esos specs; las
regresiones del issue tienen pruebas propias con contratos actuales.

## Handoff

- Áreas cambiadas: financiadores/autorizaciones/auditoría, protección de cuentas de referencia, serializer de entradas clínicas, Shell/UI compartida, agenda/fila, fichas/facturas/reservas, paciente, landing y seeds. Nuevas regresiones en `backend/apps/financiadores/test_issue111.py`, `backend/apps/demo/test_issue111.py` y `frontend/e2e/issue111-ui.spec.js`; documentación funcional de cobertura actualizada.
- Validación autorizada y ejecutada: PostgreSQL/Docker dedicado, concurrencia, integridad, carga/recarga, medición SQL y siete recorridos reales con worker. Servicios propios detenidos al concluir; fixture aislada conservada. No se tocaron servicios/bases compartidos.
- Revisión técnica realizada; el usuario autorizó continuar después de la oferta de primera revisión. Sigue pendiente su explicación de la causa/corrección clínica y de dos modos de falla. Pruebas y revisión técnica no demuestran comprensión ni aceptación humana.
- Skill aplicada: `systematic-debugging` para reproducir causas antes de corregir y separar evidencia SQLite/PostgreSQL/API simulada. `playwright` para validación de navegador; se usaron specs del runner existente porque implementar el plan incluye esas pruebas. Se consultó `using-superpowers` para selección; `brainstorming` no aplicada por tratarse de correcciones con criterios ya definidos.
- Sin migraciones ni dependencias nuevas. Build, OpenAPI y auditor aprobados. Suite completa y CI pendientes de la futura publicación del PR.
- Estado de sesión: publicación en un solo PR autorizada después de la validación. Base de las pruebas: `f494eda`; `origin/main` al publicar: `d2f6212`. PR en borrador hasta comprobar integración y CI; todavía no se recomienda incorporar ni cerrar #111.
