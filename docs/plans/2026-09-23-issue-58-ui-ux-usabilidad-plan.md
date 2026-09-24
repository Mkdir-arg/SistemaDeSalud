# Issue #58 — Plan de UI, UX y usabilidad

Estado: alcance definido con respuestas del usuario y decisiones delegadas; pendiente implementación y validación. Las políticas provisionales no constituyen aprobación jurídica ni aceptación funcional.
Fecha: 23/09/2026.
Base inspeccionada: `485749718e04bd21427a3950f98fbd439e301d2b`, coincidente con `origin/main` consultado por `git ls-remote`.

## 1. Objetivo y alcance

Implementar en un único PR los fixes del [issue #58](https://github.com/Mkdir-arg/SistemaDeSalud/issues/58), incorporando su [comentario](https://github.com/Mkdir-arg/SistemaDeSalud/issues/58#issuecomment-5799390733). Trazar H-01 a H-43, el problema de arranque local y la corrección documental. La única exclusión solicitada es la limpieza de staging.

El resultado observable propuesto: usuarios de los distintos roles encuentran sus tareas, entienden estados y errores, completan formularios con teclado, y confirman conscientemente las operaciones irreversibles. Los controles relacionados con datos se aplican también en servidor.

No se considera resuelto un hallazgo porque tenga una fila en este plan. Cada uno debe terminar con evidencia de corrección o evidencia de que ya está resuelto/no reproduce. Se incorporó el [informe original de 16 páginas](https://github.com/user-attachments/files/32574517/Auditoria.UX.UI.de.I-Core.Salud.pdf), adjuntado en el [comentario posterior](https://github.com/Mkdir-arg/SistemaDeSalud/issues/58#issuecomment-5799899816). Se extrajo su texto y se inspeccionaron visualmente las páginas 8 y 9 para precisar H-21 y H-41.

El primer comentario confirma profesional obligatorio en agendas profesionales, formateo de esperas, compromiso de motivo/enmascarado al exportar y marca actual I-Core Salud. Las respuestas posteriores del usuario cierran turnos, soporte, altas por contraseña y separación de HEN; delegan las decisiones restantes. La sección 3 distingue decisiones explícitas, decisiones técnicas delegadas y validaciones humanas aún pendientes.

### Alternativas

1. **Elegida: un PR por bloques funcionales, con UI y backend necesario.** Cubre el pedido y permite revisar cada bloque. Incluye cambios de datos/contratos para atención retrospectiva, exportación, consentimiento y tipos de campo; no es un PR exclusivamente visual.
2. PR limitado a cambios visuales. Más pequeño, pero no completa H-16, H-26, H-32, H-36 ni una regla efectiva para H-37. No satisface por sí solo «cubrir todo».
3. Varios PR por dominio. Facilita revisión y rollback, pero cambia la entrega solicitada. No es la opción propuesta.

Los bloques pueden implementarse de forma incremental en la misma rama. El PR completo no debe declarar cierre de #58 sin evidencia de sus criterios; la limpieza excluida debe conservar seguimiento y evitar un cierre automático accidental. La revisión de políticas y aceptación por usuarios continúa pendiente; se informa separada de la terminación técnica.

## 2. Qué confirmó el código y qué corrige este análisis

| Evidencia actual | Consecuencia para el plan |
|---|---|
| `api/client.js` usa `data.detail` o `Error ${status}`; el toast favorece ese mensaje | Resolver errores en el punto compartido, conservar `status` y `data`, y conectar errores por campo con formularios. No estimarlo como dos líneas aisladas. |
| `api/financiadores.js:errorFinanciador` ya interpreta errores por campo | Reutilizar/consolidar ese comportamiento. La afirmación «toda la app» del issue es demasiado amplia; hay una solución parcial existente. |
| `instituciones/views.py:metricas` omite los filtros que sí usa `InstitucionSerializer.get_staff` | Corregir el conteo a personas únicas con membresía y usuario activos. Comparar solo universos equivalentes: un área o una tabla filtrada no tienen por qué igualar el total institucional. |
| `lib/format.js:antiguedad` recibe fecha ISO, no minutos | Extraer/reutilizar la conversión de duración; no pasarle directamente la espera promedio numérica. |
| `Directorio` funciona sin institución; `Shell` carga permisos, instituciones y tareas | Incorporar un contexto explícito de plataforma en el armazón compartido, aislando las consultas institucionales. Envolver el Directorio directamente no alcanza. |
| `PageHeader` no pinta su prop `title`: el título está en `TopBar` | Resolver una única fuente de título por ruta/contexto, manteniendo subtítulo y acciones. Reemplazar encabezados sin revisar esto puede perder títulos. |
| El contador de Inicio suma tareas y filas de `/mis-tareas/` | No usarlo como si representara «sin asignar» de Bandeja; comprobar fuente y alcance de ese contador. |
| `CasoDetalle` envía la atención a `/casos/:id/avanzar/`; Historia usa `/entradas-historia/` | «Guardar borrador» no puede ser un mero cambio de etiqueta en el caso: hoy esa acción también avanza el flujo. |
| Las entradas sin firma admiten PATCH y firma posterior; las firmadas rechazan modificación | Reutilizar el circuito de borrador/firma existente. Una operación de guardar sin avanzar desde el caso necesita definir asociación y evitar entradas duplicadas. |
| El motivo de cancelación es opcional en UI y aceptado vacío por servidor | Validarlo antes de efectos en motor/API, además del campo obligatorio. |
| `UsuarioSerializer` permite contraseña ausente y crea una contraseña inutilizable | Decidir la modalidad de alta antes de convertir ausencia de contraseña en error global; puede afectar otros consumidores. |
| `FormularioDetalle` y el modelo tienen seis tipos, incluido archivo | H-39 necesita especificar cuáles faltan. El editor de opciones sí usa separación por comas y es una mejora concreta. |
| Consentimiento guarda autor/fecha/modo, pero no adjunto ni versión del texto | H-36 completo tiene efecto de datos y posiblemente migración, acceso a archivos y conservación. |
| `repartos` usa `entrypoint: ["python"]` | No ejecuta `backend/entrypoint.sh`; agregarle `EJECUTAR_MIGRACIONES=0` no corrige una carrera de migraciones. `tiempos` y `respaldos` sí requieren revisar el default. |
| Desactivar migraciones en el entrypoint no espera al migrador | El arranque limpio exige verificar orden/readiness, además de quitar migradores simultáneos. |

La inspección de este turno fue estática. Las mediciones de navegador y las 1779 pruebas del issue son evidencia previa, atribuida a ese issue, no ejecuciones nuevas.

## 3. Decisiones cerradas y criterios técnicos delegados

El usuario pidió elegir lo coherente con el sistema para 1, 3, 4, 7 y 8; las definiciones correspondientes de esta sección son del agente bajo esa delegación. Responsables de política y aceptación funcional siguen pendientes por decisión explícita del usuario. Eso no impide definir e implementar técnicamente, pero no permite afirmar revisión jurídica ni aceptación humana.

### 3.1 Firma y borrador — decisión delegada

- En Historia: firma destildada; «Guardar borrador» guarda una entrada editable; «Firmar y registrar» exige confirmación y matrícula conforme al circuito existente.
- En Caso: firma destildada; «Registrar sin firmar y avanzar» mantiene el efecto de `/avanzar/`; al marcar firma, «Firmar, registrar y avanzar» exige confirmación. El diálogo explica ambos efectos.
- Mostrar el vínculo a la entrada generada para editar/firmar el borrador con permisos existentes. No crear una segunda entrada al firmarlo. Registrar sin firma no modifica la política actual de avanzar.
- Se descarta agregar ahora un guardado del paso sin avance: requiere un ciclo de borradores asociado al nodo que no existe y no es necesario para corregir la firma accidental. Esta entrega no llamará «Guardar borrador» a una acción que avanza el caso.

### 3.2 Atención retrospectiva — decisión explícita y aplicación al dominio

**Usuario:** permitida a quienes pueden dar turnos futuros, sin antigüedad máxima, motivo obligatorio; representa una atención ya ocurrida.

- Acción diferenciada «Registrar atención realizada». Si se elige un horario pasado en la reserva ordinaria, mostrar este circuito y pedir confirmación; no convertir silenciosamente una reserva en atención.
- Mismo permiso `turnos`, mismo ámbito institucional. Inicio real en el pasado según hora del servidor, paciente, agenda, duración y motivo de carga obligatorios. El motivo no reemplaza la razón clínica del turno.
- Agregar estado terminal `realizado` y procedencia de carga retrospectiva a Turno; usar `inicio` para la fecha real, `creado/creado_por` y `resuelto_at/resuelto_por` para la fecha/autor de registro actual. Agregar `motivo_registro` separado si no existe un campo inequívoco. No falsificar autor ni fecha de una entrada clínica.
- No abrir un caso operativo, llamar `registrar_llegada`, crear colas, enviar recordatorios, consumir reservas de cobertura ni generar costos/cargos automáticamente. No representa una nota clínica firmada: es constancia administrativa de una atención realizada.
- Las reglas de disponibilidad/cupos actuales no pueden impedir registrar una atención histórica real: permitir agenda existente aunque esté inactiva hoy, sin modificarla ni reactivarla, avisando esa condición. Mantener coincidencia institucional y datos válidos. Registrar duración explícita sin inferirla de franjas actuales.
- Ajustar restricción de cupo y consultas para excluir la carga retrospectiva de la ocupación de reservas; no usar sobreturno ficticio ni una posición falsa para sortear el constraint.
- Si ya existe un turno del mismo paciente/agenda/inicio, identificarlo antes de escribir: completar el pendiente como realizado cuando no tiene caso operativo, o mostrar el registro ya realizado; si tiene caso, no cerrar ese caso implícitamente. Resolver asociación compatible o rechazar con explicación y enlace al caso existente.
- Bajo bloqueo de agenda, deduplicar e implementar reintento idempotente; clave de operación estable y rechazo de reutilización con otro contenido. Es un cambio de contrato/datos, con migración y pruebas de concurrencia.
- Mostrar estas cargas separadas de reservas/presentes en indicadores; evitar contabilizarlas como ausencias, pendientes o hechos financieros recuperables. Una fecha arbitrariamente antigua sigue siendo válida; no introducir filtros de UI que contradigan «sin antigüedad máxima».

### 3.3 Exportación — política técnica provisional delegada

Fuente: `apps/common.py:ROL_CAPACIDADES`, `CiudadanoViewSet.get_columnas_csv` y auditoría existente. Las capacidades se calculan para la institución concreta, nunca por unión de permisos de instituciones diferentes. Usuarios inactivos/membresías inactivas no habilitan acceso.

| Perfil efectivo en la institución | Exportación permitida |
|---|---|
| Sin `padron_admision` ni `historia_clinica` | Sin descarga nominal: incluye plataforma, auditor, reportes, configurador y financiador por esos roles solos. Tener acceso a auditoría no da acceso al padrón. |
| Solo `padron_admision` | Padrón administrativo minimizado: referencia interna, iniciales de nombre/apellido, documento con últimos cuatro caracteres, año de nacimiento y estado de consentimiento; sin domicilio ni datos clínicos. No es anonimización. |
| `historia_clinica` + `padron_admision` | Puede pedir padrón identificado y exportación clínica con las columnas ya autorizadas actualmente. Descarga minimizada por defecto; selección explícita de datos identificatorios/clínicos con confirmación y motivo. No se amplía a notas/adjuntos completos. |
| Admin institucional o superusuario | Mismas variantes anteriores según su acceso existente, una institución por operación; acceso completo siempre explícito y auditado. |

- Mantener identificación nominal en la consulta operativa de pacientes para evitar errores asistenciales. El enmascarado por perfil se aplica a la extracción masiva; el perfil administrativo sigue sin recibir campos clínicos. Cambiar lectura individual sería otro contrato y degradaría admisión.
- Registrar motivo de 10–500 caracteres, alcance, filtros, variante, cantidad, actor y momento en servidor. Conservar motivo como metadata protegida del evento, accesible con las reglas actuales de auditoría. Mantener el plazo protegido que el repositorio ya aplica al registro de accesos; no agregar borrado automático.
- Endpoint POST de exportación del recurso, con justificación en cuerpo y respuesta de archivo; adaptar el mixin para registrar una sola exportación estricta. El GET anterior no puede permitir eludir motivo/enmascarado: rechazarlo con indicación de usar el nuevo contrato, documentando compatibilidad.
- Exigir institución explícita para evitar mezclar políticas en un CSV. Revalidar permisos en servidor, independientemente de «Ver como» o columnas visibles.
- Persistir el evento antes de transmitir bytes; si falla auditoría, no entregar archivo. Prevenir fórmula CSV en valores controlados por usuario y evitar datos clínicos en URL/logs.
- Política provisional deliberadamente más restrictiva para extracción administrativa masiva. La revisión humana podrá ajustar esa matriz sin reescribir la consulta clínica. Responsable de validación de política: pendiente.

### 3.4 Consentimiento — decisión técnica provisional delegada

- Mantener `padron_admision`, institución del paciente, autor/fecha del servidor y registros append-only; la revocación crea un registro nuevo. La atención no se bloquea por falta de consentimiento.
- Método sin preselección. Guardar alcance, identificador de versión y copia inmutable del texto efectivamente comunicado, o documento que lo contiene. No inventar un texto legal aprobado ni sembrar una versión ficticia.
- Para escrito/digital: pedir documento PDF o imagen de evidencia y referencia de su versión. Para verbal: pedir el texto comunicado, alcance y constancia del método; no exigir grabaciones. En ambos casos exigir contenido real aportado por quien registra; la UI no lo certifica jurídicamente.
- Reutilizar `ArchivoClinico`, almacenamiento privado y validación de contenido/tamaño; propósito específico `consentimiento`, ligado al registro y paciente. PDF/JPEG/PNG/WebP, máximo 10 MiB por archivo o límite vigente más restrictivo.
- Subida/descarga de evidencia de consentimiento con `padron_admision` y mismo ámbito/paciente, de modo que admisión pueda operar. Implementar endpoints/protección específica por propósito; **no** dar a administrativos acceso a archivos de estudios o historia por ampliar el endpoint genérico.
- Evitar archivos huérfanos al fallar validación/DB y reutilización de adjuntos de otra persona/institución. Auditar descargas. No ofrecer borrado/edición de evidencia ya vinculada.
- Para revocar: motivo, método y alcance explícitos, referencia al consentimiento cuando existe; no exigir conseguir un adjunto para hacer efectiva la revocación. Adjuntar prueba disponible sin sobrescribir la original.
- Históricos quedan sin backfill ficticio, rotulados «Evidencia anterior sin versión/adjunto» donde corresponda. Conservar evidencia junto con su registro, sin nueva purga automática, conforme al tratamiento protegido del sistema; revisión de retención y validez jurídica pendiente.

### 3.5 Soporte y altas por contraseña — decisiones explícitas

- Recuperación asistida por soporte. En Login, enlace a instrucciones accesibles que expliquen cómo contactar al soporte/administración de la institución, qué identificar y qué no enviar (contraseña/datos clínicos). Mostrar correo/URL real solo cuando exista configuración; no inventar un mailto ni afirmar que se envió una solicitud.
- Documento funcional en identidad/accesos: verificación de identidad por el procedimiento institucional, cambio por administrador autorizado mediante los mecanismos existentes y comunicación por canal seguro. El dato operativo de contacto queda pendiente de configuración, sin bloquear la página de instrucciones.
- **Tentativa futura documentada:** recuperación automática por correo. Condiciones de inicio: proveedor/remitente y URL oficiales, tokens de un solo uso con expiración, respuestas que no revelen existencia de cuentas, límites de intentos, revocación de sesiones y pruebas de entrega. No habilitar envío automático ni crear otro issue sin pedido.
- Todas las altas humanas por contraseña, incluidas las de plataforma/institución; contraseña obligatoria y confirmada antes de habilitar ingreso. Reutilizar validadores de Django para longitud mínima actual (8), similitud, contraseñas comunes y enteramente numéricas. Explicar requisitos cumplidos, sin un medidor de fortaleza ficticio.
- Cubrir alta por activación de financiadores: puede seguir verificando acceso por invitación existente, pero debe terminar estableciendo contraseña antes de permitir login. No romper usuarios históricos o de pruebas/servicios por imponer la regla indiscriminadamente en `create_user`.
- PATCH sin contraseña conserva la actual; si se envía una nueva, validar. `name` y autocomplete adecuados en email/nombre/apellido/password para evitar autofill cruzado.

### 3.6 Cinco tipos nuevos por retorno — decisión delegada

Se agregan a los seis existentes; no sustituyen Número/Fecha/Archivo.

| Tipo / código | Retorno | Contrato y aceptación |
|---|---|---|
| Sí/No / `booleano` | Preguntas binarias sin variantes «sí/si/1/true» | Selección explícita sin default; vacío distinto de false. API boolean, persistencia textual canónica `true`/`false`; requerido acepta false. |
| Selección múltiple / `seleccion_multiple` | Síntomas, antecedentes y opciones simultáneas | Array de opciones admitidas, sin duplicados, con orden canónico; vacío `[]`. Persistencia JSON canónica dentro de `ValorCampo.valor`; no separar por comas. |
| Hora / `hora` | Horas de eventos/cuidados sin inventar fecha | `HH:mm` 24 h, sin zona horaria ni fecha implícita; límites 00:00–23:59. Orden por minutos del día. |
| Correo electrónico / `email` | Datos de contacto validados con poco desarrollo | Validación de formato en cliente/servidor con validadores existentes; espacios externos fuera, dominio normalizado, sin convertirlo en identidad del usuario ni enviar correos. |
| Teléfono / `telefono` | Contacto sin datos numéricos truncados | Texto, no número: conservar cero inicial, permitir + inicial y separadores habituales; 7–15 dígitos, sin imponer país. Mostrar el valor normalizado y no prometer verificación de titularidad. |

- Cambio de choices y migración; serializers aceptan solo el contrato definido; backend valida pertenencia del campo al formulario y opciones, requerido, formato y límite de longitud. Probar API directa, no solo controles HTML.
- Una interpretación por tipo para captura, preview, detalle del caso, ensayos y condiciones. Mantener TextField actual con normalización tipada al borde; no migrar todos los valores históricos a JSON.
- Condiciones: booleanos comparan booleanos; múltiples usan pertenencia exacta, no substring de JSON; hora se compara por minutos; email/teléfono admiten igualdad/vacío y búsqueda textual solo si es coherente. Rechazar operadores incompatibles al validar/publicar, antes de ejecutar un caso.
- Los seis tipos actuales conservan semántica y formatos. Tipos con datos quedan bloqueados. Opciones históricas y condiciones no pueden quedar apuntando a un valor eliminado sin una validación explícita.
- Probar guardar/recargar/editar/renderizar/decidir para cada tipo, incluidos false, [], Unicode, comas en opciones, formatos inválidos y edición de formularios usados. Esta es la definición de implementación completa de H-39.

### 3.7 Navegación por responsabilidad — decisión delegada

Mantener una estructura común con grupos colapsables y capacidades existentes; variar orden inicial por perfil, conservando rutas, búsqueda y navegación por teclado. Con roles combinados usar unión de capacidades dentro de la institución; recordar la expansión sin ocultar la ruta activa.

| Perfil | Primeras tareas/grupo |
|---|---|
| Administrativo | Mi trabajo/Inicio, Bandeja, Agenda y Padrón |
| Médico / Enfermería | Mi trabajo, Bandeja, Casos e Historia; mostrar recursos asistenciales solo si su capacidad existe |
| Jefe de área | Supervisión, Bandeja y Tablero; luego operación/registros |
| Admin institucional | Inicio con puesta en marcha, Administración y Estructura; operación siempre accesible |
| Configurador | Flujos, Formularios y Mapa |
| Plataforma | Instituciones, Usuarios y gobierno de red; no búsquedas clínicas por este rol |
| Auditor | Registro de accesos; no padrón/HC por este rol |
| Reportes | Solo destinos agregados que realmente autorice la API; no mostrar Tablero nominal por el nombre «reportes» |
| Superusuario | Contexto plataforma por defecto; al entrar a hospital navegación de administración, con vista previa claramente rotulada |
| Financiador | Menú propio por sus roles existentes, dentro del armazón común y de la organización seleccionada |

Bandeja sigue primera en TRABAJO. Mantener separadas operación, registros, configuración y finanzas; grupos sin destinos autorizados no aparecen. La búsqueda global de pacientes se muestra en contexto operativo/registro autorizado y se retira del contexto de plataforma/configuración. «Ver como» solo describe una vista de navegación, nunca una simulación de permisos.

### 3.8 Marca, fuentes y pendientes humanos

- Marca actual confirmada: I-Core Salud. Migración futura creada como [issue #59](https://github.com/Mkdir-arg/SistemaDeSalud/issues/59), asignada a `juanikitro`, incorporada al tablero `Tareas I-Core`, vista `Tareas Salud`, con campo `Proyecto: Salud` y estado Backlog. Se verificó su tarjeta en el navegador.
- Dominio/cuentas deben mantener coherencia con I-Core Salud durante esta entrega; acciones de DNS/cuentas siguen siendo ejecución operativa separada del código, sin autorizar cambios de infraestructura productiva desde este plan.
- El PDF ya resuelve la información faltante. H-21: aristas sobre nodos, etiquetas solapadas/truncadas y falta de alternativa textual. H-41: vacíos genéricos, paginación con cero registros y ayudas «?» sin nombre. H-40 compara Nuevo caso con Turnos, además del buscador global.
- Pendientes declarados por el usuario: responsable de validar políticas y responsable/perfiles de aceptación funcional. No se inventan responsables ni se marca su revisión como realizada.

## 4. Secuencia de implementación del PR

### Bloque 0 — Base y aceptación

- Crear rama de trabajo desde main verificado; preservar otros worktrees y datos locales.
- Usar las decisiones de la sección 3 y el PDF original como criterios de implementación. Conservar trazabilidad entre cada subhallazgo y su prueba, incluyendo los detalles que el issue había resumido.
- Inventariar rutas afectadas y escenarios de los nueve roles con `docs/ROLES-Y-PERMISOS.md`; validar API con usuarios reales de prueba, no con «Ver como».
- Preparar escenarios sintéticos: membresías duplicadas/inactivas, usuarios inactivos, nombres largos, pacientes con nombre similar, paginación, espera >30 días, cobertura habilitada/deshabilitada, financiador ausente y derivaciones entre flujos.
- Usar las herramientas existentes: React, Router, React Query, `Field`, `ConfirmDialog`, `BuscadorPaciente`, tablas y Playwright. No incorporar una biblioteca de formularios, diseño o diagramación sin necesidad demostrada.

### Bloque 1 — Errores, validación y correcciones locales

H-30, H-35, H-14, H-13, H-28, H-34, H-43, H-19 y H-33b.

Archivos principales: `frontend/src/api/client.js`, `api/financiadores.js`, `components/ui/toast.jsx`, `components/ui.jsx`, `lib/format.js`, `pages/Dashboard.jsx`, `pages/admin/Areas.jsx`, `pages/registros/Registros.jsx`, `pages/Directorio.jsx`, `pages/diseno/FlujoEditor.jsx`, `backend/apps/instituciones/views.py`.

1. Normalizar `detail`, `non_field_errors`, arrays y objetos de validación; mantener datos originales para el formulario. Ante HTML, cuerpo vacío, red caída o fallo interno, presentar una explicación segura en español, sin HTML, JSON crudo ni trazas.
2. Extender el patrón existente de `Field` para error visible, `aria-invalid` y asociación de ayuda/error mediante `aria-describedby`. Mantener compatibilidad con los consumidores actuales; focus al primer error y resumen cuando corresponda. Toast para resultado de operación, error en línea para corregir campos.
3. Aplicar el patrón a todos los formularios inventariados en las pantallas de este issue; enumerar los consumidores alcanzados en el PR para que «un solo patrón» sea comprobable.
4. Corregir staff con filtros de activos y `distinct`; comprobar el universo de los conteos en Administración/Estructura y rotularlo cuando sea distinto.
5. Agregar formato para duración numérica y reutilizarlo en las esperas. Mantener minutos en el contrato/ordenamiento; mostrar minutos/horas/días, sin números negativos o `NaN`.
6. Unificar fechas visibles mediante los helpers existentes/ampliados. Distinguir fecha civil (`YYYY-MM-DD`) de instante con zona horaria para evitar corrimiento de un día. Conservar formatos nativos/API y exportaciones que formen parte de contratos.
7. Corregir ruta a Administración, placeholder de documento sin DNI de demo, «En configuración» y estado posterior a publicación. Corregir plurales («1 consulta», «vencida/s») y abreviaturas ambiguas («0/12 dados», «Espera prom.») con contexto, conservando títulos de calendario apropiados como «septiembre de 2026».
8. H-43 incluye el tipo de institución: selector con catálogo de sugerencias del dominio (Hospital, Centro de salud, Clínica, Sanatorio y Otro con detalle), preservando valores históricos y sin recodificar instituciones existentes por texto. Esta lista es ayuda de captura, no una clasificación oficial nueva.

Criterio de salida: la validación de agenda profesional se muestra junto al profesional y es entendible; ningún error HTTP genérico desplaza un mensaje útil en las pantallas alcanzadas; staff y formatos responden correctamente a los escenarios límite.

### Bloque 2 — Acceso y accesibilidad

H-01 a H-08, H-25 y H-32.

Archivos: `pages/Login.jsx`, `api/client.js`, `components/Shell.jsx`, `components/ui.jsx`, `components/icons.jsx`, pantallas con encabezados propios, `pages/admin/Usuarios.jsx`, `pages/Directorio.jsx`, `backend/apps/accounts/serializers.py`.

- Mantener campos de acceso inicialmente vacíos; probar autofill sin desactivar gestores de contraseñas.
- Persistencia desmarcada por defecto en UI y coherente con el default del cliente; comprobar ambos almacenes y limpieza al cambiar de opción/cerrar sesión.
- H-02 completo: bloqueo de la interfaz tras 15 minutos sin interacción humana, aviso dos minutos antes y reautenticación para continuar; tiempo configurable según operación. Polling/refrescos no cuentan como actividad. Limpiar tokens al bloquear, ocultar datos y mantener solo en memoria el borrador de la pestaña para recuperarlo si reingresa la misma persona en el mismo ámbito; otra identidad lo descarta. No persistir borradores clínicos en almacenamiento del navegador. Este bloqueo protege el equipo compartido; no afirmar revocación anticipada de un JWT ya emitido: la API conserva su vencimiento existente (60 minutos de access y 7 días de refresh) salvo un cambio de autenticación separado y explícito.
- H1 «Iniciá sesión», eslogan como párrafo; un H1 significativo por ruta protegida, incluido error/sin permisos cuando corresponda.
- Skip-link enfocable que lleve al contenido, foco visible, navegación por teclado y foco restaurado tras modales.
- H-06: el informe mide 4,56:1 en subtítulo/ayuda del ingreso; ya cumple su umbral AA. Mejorar margen de legibilidad sin presentarlo como incumplimiento confirmado. H-07: atenuar el grafo decorativo para que no cruce el texto, mejorar descripciones de 12 px y reducir el peso del panel promocional frente al acceso, con copy útil a roles operativos. Medir contraste sobre el degradado y texto; criterio de diseño 4,5:1 para texto normal, 3:1 para grande/controles y foco de al menos 2 px, con mediciones registradas.
- Mostrar/ocultar contraseña con `aria-pressed`, nombre accesible y objetivo de 44 px; retirar puntos de placeholder y sustituir `$` por icono SVG accesible según su función.
- Recuperación por soporte mediante instrucciones accesibles y contacto real cuando esté configurado; documentar la futura recuperación por correo según §3.5.
- Alta de usuarios: `autocomplete="new-password"`, confirmación, política legible y validación de servidor según decisión. Revisar también el alta desde Directorio; no cambiar accidentalmente edición o activación de financiadores.

Criterio de salida: acceso y altas se completan con teclado; no hay persistencia tácita; las contraseñas rechazadas se explican sin exponerlas y los encabezados no se duplican.

### Bloque 3 — Navegación y estructura compartida

H-10, H-11, H-12, H-18, H-23, H-24, H-27 y H-29.

Archivos: `App.jsx`, `components/Shell.jsx`, `pages/Directorio.jsx`, `pages/financiadores/PortalFinanciadores.jsx`, `components/ui/tabla.jsx`, contexto institucional y helpers de permisos solo donde sea necesario.

- Incorporar el Directorio al armazón compartido con modo plataforma explícito. Reutilizar tema, cabecera, navegación móvil y salida. Impedir consultas clínicas/financieras institucionales sin institución; probar incluso si quedó una selección anterior guardada.
- Conservar compatibilidad de `?vista=instituciones|usuarios`; usar enlaces reales (`Link`/`NavLink`) para navegación, back/forward y abrir en otra pestaña. No cambiar rutas públicas solo para alinear etiquetas.
- Una única acción de salida visible en el contexto correspondiente; título, breadcrumbs y acciones sin duplicaciones.
- Agregar Bandeja primero en TRABAJO cuando esté autorizada. Actualizar el comentario que documentaba la decisión opuesta. Contador de sin asignar obtenido de fuente y ámbito correctos, invalidado al asignar/avanzar/cambiar institución; no calcular desde una página parcial ni equipararlo al contador de Inicio.
- Portal vacío: distinguir sin organizaciones creadas, sin asignación, selección inexistente/no accesible, carga y error. Ofrecer el CTA existente a quien administra y evitar diez destinos equivalentes vacíos, preservando funcionalidades globales que sí correspondan, como catálogo.
- Simplificar agrupación por tarea/rol con capacidades existentes. Etiquetar «Ver como» como vista previa de navegación: no valida ni reduce permisos del servidor.
- Acción final de tabla accesible a 1150 px y en móvil: columna fija cuando corresponde, ancho mínimo, fondo y foco visibles, sin tapar información ni romper selección/scroll.
- Vocabulario acordado para Instituciones, Administración, Estructura, Red/traslados y Coberturas hospitalarias frente a reglas del financiador. Actualizar ayuda y documentación afectada sin alterar códigos del dominio.
- H-34 completo: checklist de puesta en marcha en Inicio con estado calculado y enlaces a áreas, usuarios, asignación de profesionales, agendas/horarios y flujos publicados. Separar rutas de agenda profesional/recurso; no exigir profesional para recurso. Acciones solo con permiso, explicación de dependencias y destino correcto; si no hay flujo operativo, «Operar» explica qué falta y ofrece configurarlo a quien corresponda. No usar cantidad de registros como garantía de configuración válida.
- Revisar las flechas de cabecera: volver atrás, cambiar institución y colapsar menú deben tener iconos/nombres distintos, y un destino seguro al entrar por URL directa. Ayudas «?» con nombre específico, foco y contenido accesible.

Criterio de salida: una persona puede entrar/salir de plataforma, hospital y financiador sin perder contexto, con enlaces navegables y sin peticiones de otro ámbito. El menú facilita encontrar tareas con roles reales.

### Bloque 4 — Operación clínica y acciones irreversibles

H-15, H-16, H-17, H-20, H-31, H-36, H-37, H-38, H-40 y H-41.

Archivos: `lib/dominio.js`, `components/ui/paciente.jsx`, `components/Shell.jsx`, `pages/ejecucion/Casos.jsx`, `CasoDetalle.jsx`, `Agenda.jsx`, `Bandejas.jsx`, `Farmacia.jsx`, `pages/Supervision.jsx`, `pages/registros/HistoriaDetalle.jsx`, `pages/financiadores/CoberturaCaso.jsx`, y backend de casos/agenda/registros.

- Usar estados persistidos como fuente. El stepper representa una etapa y debe decirlo; no inventar progreso para un cancelado, que hoy puede caer en índice 0. Evitar redefinir la máquina de estados para solucionar una etiqueta.
- Motivo de cancelación obligatorio tras `trim`, visible en historial y validado antes de cancelar/liberar recursos. Conservar atomicidad y reglas sobre camas, reservas y subcasos; repetir/cancelar diálogo no debe producir efectos duplicados.
- Prioridad legible sin truncar «Normal».
- Reutilizar `BuscadorPaciente` en Nuevo caso y Turnos y el comportamiento accesible del buscador de barra: consulta al servidor, teclado, loading/error/sin resultados, selección inequívoca e institución. Preservar aislamiento por usuario/institución y descartar respuestas tardías tras un cambio de contexto. Alinear creación de paciente con los permisos existentes. H-17 también exige no preseleccionar silenciosamente el flujo: elección explícita o sugerencia por área que la persona confirme, limitada a versiones publicadas habilitadas. No introducir almacenamiento de «pacientes recientes» sin necesidad.
- Firma destildada en ambos puntos. Confirmación con paciente, autor y consecuencia irreversible; no enviar la mutación al abrir/cancelar el diálogo. En Historia: guardar borrador, reabrir y firmar. En Caso: aplicar la decisión sobre borrador/avance y probar reintentos para evitar duplicados. Conservar sellado y restricciones de matrícula/autoría.
- Cancelar/publicar/firmar bloquean doble envío y muestran el resultado sin ocultar errores relevantes.
- Estados vacíos distinguen módulo deshabilitado, módulo sin configurar, sin pendientes, sin coincidencias, falta de permisos y error técnico. H-20 afecta también `CoberturasHospital` y Finanzas: no mostrar la tabla completa de reservas vacías cuando el circuito está deshabilitado ni afirmar «Repartos actualizados» sin actividad observada. Mostrar fecha/estado conocido y una ayuda con nombre. No confundirlo con afiliación ausente o cobertura pendiente ni bloquear atención clínica por presentación.
- Turnos pasados: implementar §3.2 en UI/motor/API con hora del servidor. Mantener bloqueo, cupos y sobreturnos en reservas futuras; no imponer franjas actuales a la constancia histórica. Probar cruce de hora actual, medianoche, fechas antiguas, agenda inactiva, turno/caso previo y reintento. En todos los turnos, elegir paciente solo selecciona: mostrar resumen paciente/agenda/fecha/modalidad antes de confirmar la reserva; hoy `onElegir` muta directamente.
- Consentimiento: implementar §3.4 con migración aditiva y protección específica de adjuntos administrativos. Probar históricos sin nueva metadata, revocación, fallos de subida y archivos sin registro asociado.
- H-41: en todas las secciones del portal, unificar vacíos pedagógicos, paginación y ayudas con nombre accesible. Con cero registros no ofrecer Anterior/Siguiente activos ni una página imposible. Diferenciar cero total de cero por filtro, conservar filtros al paginar y comprobar 0/1/varias páginas, carga y error. Reutilizar tabla/paginador existentes donde su contrato lo permita; no reescribir el portal completo.

Criterio de salida: no se firma/cancela por accidente; acciones y etiquetas describen el efecto real sobre el caso; no se pierde aislamiento de pacientes ni se altera el circuito financiero por arreglar la presentación.

### Bloque 5 — Diseñadores y mapa

H-21, H-22, H-33, H-39 y H-42.

Archivos: `pages/diseno/FlujoEditor.jsx`, `MapaFlujos.jsx`, `FormularioDetalle.jsx`, `components/ui/toast.jsx`, backend de formularios/flujos y validación del motor si se aprueban tipos nuevos.

- Reemplazar el toast local por el compartido manteniendo acciones, mensajes y persistencia de errores accionables; no cambiar las duraciones globales basándose en la medición errónea del issue.
- Publicación: confirmar flujo, versión, alcance y resumen verificable de cambios. Reutilizar metadata/datos disponibles; no fabricar un diff histórico si no existe fuente comparable. Revalidar al publicar, prevenir doble envío y reflejar estado publicado coherente, sin «lista para publicar».
- Un único aviso de solo lectura y explicación accionable del circuito sin definir, respetando el significado real de esa configuración.
- H-22 incluye validación desactualizada tras borrar un nodo: invalidar resultados al cambiar el grafo, marcar «Cambios pendientes de validar» y revalidar antes de publicar. Un resultado tardío de una revisión anterior no puede sustituir al actual.
- Medir canvas con/sin panel de propiedades y validación. Corregir solo si reproduce el problema; documentar las dimensiones medidas.
- Editor de opciones por filas: agregar, quitar y ordenar; evitar opciones vacías/duplicadas y permitir comas dentro de una opción sin romper el array. Preservar identificadores/valores ya usados y evaluar impacto de quitar o renombrar opciones sobre condiciones y respuestas históricas.
- Implementar los cinco tipos de §3.6 en modelo/serializer, captura, preview, validación, condiciones y tests juntos. Conservar la prohibición de cambiar tipo con valores cargados.
- H-21: el layout ya organiza por niveles; mejorar tamaños/espaciado y ruteo de aristas alrededor de nodos, con carriles para ciclos/retornos. Probar diamante, muchas derivaciones, ciclos, nombres largos y enlaces externos. No prometer un grafo arbitrario sin cruces; sí aristas sin atravesar cajas/etiquetas y nodos distinguibles. Nombre completo disponible con teclado/puntero y vista alternativa de lista con origen/destino/enlaces equivalentes, accesible por lector. Mantener el algoritmo actual salvo limitación demostrada; no introducir librería de layout por defecto.
- H-42 completo: además del toast único, mensajes explícitos («Horario guardado: lunes de 08:00 a 12:00»), ubicación sin tapar acciones, y al avanzar/cerrar llevar foco al encabezado/resumen actualizado sin desplazar formularios con errores. Stepper cerrado muestra finalización (check y texto accesible), no un «5» que parece pendiente; respetar movimiento reducido y no anunciar cancelación como éxito de atención.

### Bloque 6 — Exportación responsable

H-26. Archivos: `pages/registros/Registros.jsx`, `components/ui/tabla.jsx`, `api/client.js`, `backend/apps/registros/views.py`, `backend/apps/auditoria/mixins.py`, modelo/serializer de auditoría si el contrato aprobado lo exige.

- Diálogo previo con alcance/filtros, columnas exportadas y motivo obligatorio. No agregar fricción global a todas las tablas sin distinguir el padrón.
- Motivo validado y persistido por servidor junto a la auditoría existente, sin duplicar eventos. Usar POST con justificación en cuerpo según §3.3, actualizar cliente/OpenAPI y rechazar bypass del GET anterior. Es un cambio explícito de contrato.
- Enmascarado/omisión en el CSV del servidor; probar acceso directo al endpoint anterior para impedir bypass. No basta ocultar columnas en pantalla.
- Mantener alcance institucional, filtros y paginación/exportación completa coherentes; probar fallos de auditoría y confirmar que no se entrega un archivo cuando el registro obligatorio falla.
- Agregar campo estructurado de motivo de hasta 500 caracteres a auditoría; `detalle` actual tiene máximo 300 y no debe sobrecargarse/truncarse. Mantener separados filtros, motivo y variante de exportación. Migración aditiva con motivo ausente para registros anteriores.
- Revisión específica de permisos, pruebas cruzadas entre instituciones y compatibilidad del contrato anterior. Si hay cambios de esquema, migración aditiva con tratamiento explícito de históricos.

Criterio de salida: exportación por UI y por API satisface la misma política, conserva trazabilidad y no filtra datos completos a usuarios restringidos.

### Bloque 7 — Arranque y documentación

- Corregir el arranque local identificado en §5 del issue. Desactivar migración en servicios que realmente ejecutan el entrypoint migrador y asegurar que consumidores del esquema esperen la finalización del backend/migrador. Reutilizar readiness disponible; verificar que el healthcheck funcione con la configuración efectiva.
- `repartos` requiere análisis del orden de arranque, no atribuirle migraciones que su entrypoint no ejecuta. Revisar también `costos`, que ya tiene la variable pero puede arrancar antes de tener esquema.
- Probar volumen vacío y arranque posterior en proyecto Compose aislado con puertos/volúmenes propios y sin tocar staging ni bases compartidas. Es una validación de infraestructura a autorizar para la fase de implementación.
- Actualizar `docs/ESTADO-DEL-PROYECTO.md`: registrar que #58 reportó suite corregida sobre `4857497`, con fecha/fuente; reemplazar luego por resultados del SHA final del PR cuando existan. No presentar el dato previo como una ejecución nueva.
- Actualizar documentación de roles, navegación, datos y pruebas solo en lo afectado. Alinear referencias visibles I-Core Salud; preservar `cauce-sha256-v1` y `urn:cauce:id`. Dominio/cuentas y accesos para auditora quedan como pasos operativos con responsable/validación, sin ejecutarlos desde este análisis.

## 5. Matriz completa de cobertura

| ID | Tratamiento y aceptación principal | Bloque |
|---|---|---|
| H-01 | Verificar campos vacíos y autofill; registrar como ya explicado, sin un fix ficticio | 2 |
| H-02 | Persistencia opt-in, bloqueo por inactividad y límites JWT explícitos | 2 |
| H-03 | Instrucciones accionables de soporte; correo automático documentado como futuro | 2 |
| H-04 | Foco visible y comprobable con teclado | 2 |
| H-05 | H1 de acceso y jerarquía semántica | 2 |
| H-06 | Mejorar margen del contraste secundario de login (el 4,56:1 reportado ya cumple) | 2 |
| H-07 | Grafo decorativo sin cruzar texto, legibilidad y peso del panel de login | 2 |
| H-08 | Visibilidad de contraseña accesible, sin placeholder engañoso | 2 |
| H-09 | I-Core Salud actual; HEN separado en #59, asignado y clasificado Salud | 7 |
| H-10 | Bandeja visible por capacidad, contador correcto | 3 |
| H-11 | Portal sin organizaciones con acción útil y navegación pertinente | 3 |
| H-12 | Acción de tabla visible y operable a 1150 px y móvil | 3 |
| H-13 | Esperas legibles en minutos/horas/días | 1 |
| H-14 | Staff activo único, comparación de ámbitos equivalentes | 1 |
| H-15 | Estado y etapa coherentes, incluida cancelación | 4 |
| H-16 | Cancelación exige motivo en UI/API y prioridad legible | 4 |
| H-17 | Paciente por buscador común y elección explícita del flujo | 4 |
| H-18 | Vocabulario consistente entre menú, cabecera, ayuda y rutas existentes | 3 |
| H-19 | «En configuración», sin cambiar el código de estado | 1 |
| H-20 | Coberturas/Finanzas distinguen deshabilitado, sin actividad, actualizado y error | 4 |
| H-21 | Aristas/etiquetas legibles, nombres completos y alternativa textual del mapa | 5 |
| H-22 | Aviso único, circuito explicado, altura medida y validación invalidada al editar | 5 |
| H-23 | Directorio integrado y títulos coherentes | 3 |
| H-24 | Navegación real y salida sin duplicación | 3 |
| H-25 | Skip-link, un H1 por ruta e iconografía adecuada | 2 |
| H-26 | Motivo persistido y matriz provisional de §3.3 exigida por servidor | 6 |
| H-27 | Orden por responsabilidad, grupos colapsables y «Ver como» explícito | 3 |
| H-28 | Fechas sin corrimientos, plurales y microcopy inequívoco | 1 |
| H-29 | Tema oscuro y búsqueda de pacientes adecuada al contexto | 3 |
| H-30 | Errores útiles, conservando detalle por campo | 1 |
| H-31 | Firma voluntaria confirmada; borrador en Historia y avance explícito en Caso | 4 |
| H-32 | Todas las altas por contraseña, validación efectiva y autofill correcto | 2 |
| H-33 | Confirmación al publicar y feedback final no contradictorio | 1 y 5 |
| H-34 | Checklist de puesta en marcha con dependencias/enlaces correctos | 1 y 3 |
| H-35 | Patrón de validación inline accesible en formularios inventariados | 1 |
| H-36 | Método explícito, evidencia/versionado real y política provisional de §3.4 | 4 |
| H-37 | Atención retrospectiva con motivo, sin límite y sin efectos de reserva; confirmación al reservar | 4 |
| H-38 | Sin configurar/sin pendientes/error diferenciados | 4 |
| H-39 | Editor de opciones y cinco tipos completos según §3.6 | 5 |
| H-40 | Búsqueda incremental común en Nuevo caso y Turnos | 4 |
| H-41 | Vacíos, paginación 0/1/N y ayudas accesibles del portal | 4 |
| H-42 | Toast único, mensajes específicos, foco tras avance y stepper terminado | 5 |
| H-43 | Documento sin identidad demo, catálogo sugerido de instituciones y plurales | 1 |
| §5 | Arranque sin migradores concurrentes ni consumidores prematuros | 7 |
| Estado del proyecto | Evidencia de tests con fecha, SHA y procedencia correctos | 7 |
| §6 | Limpieza pendiente de staging excluida por pedido | Excluido |

## 6. Validación y evidencia requerida

### Pruebas focalizadas durante implementación

- Frontend: aprovechar Playwright existente. Pruebas con API simulada para errores, accesibilidad, selección, diálogos, estados vacíos y navegación; no interpretarlas como prueba del servidor.
- Backend: suites/clases focalizadas de instituciones, accounts, casos, registros, agenda, auditoría, formularios/flujos y cobertura según el bloque. PostgreSQL para concurrencia/ordenamiento, no sustituir por SQLite.
- En cancelación, firma, publicación y reservas: probar rechazo, cancelación del diálogo, doble clic, respuesta perdida y cambio concurrente del estado. Un toast correcto no prueba idempotencia.
- Exportación: inspeccionar archivo recibido y evento persistido con roles reales, incluyendo petición directa, filtros y otra institución.
- Consentimiento: comprobar autor/fecha/versión, nuevo registro al revocar, históricos y acceso al adjunto desde otro usuario/institución.
- Navegador: 1440×1000, 1150×900 y 390 px; temas claro/oscuro; teclado, zoom y foco; nombres largos y suficiente volumen para paginación. Comprobar contraste con valores calculados.
- Nueve roles institucionales documentados para visibilidad; recorridos completos con perfiles representativos de plataforma, administración, admisión, profesional, auditoría y financiador, manteniendo las dos familias de roles diferenciadas.

### Comandos existentes para el cierre del PR

No se ejecutaron en este análisis. En la implementación se elegirán specs/clases focales por bloque; el cierre transversal requiere las comprobaciones oficiales correspondientes:

```powershell
# Desde frontend, con dependencias y entorno de prueba preparados:
npm run build
npm run auditar
npm run e2e -- e2e/sesion.spec.js e2e/shell.spec.js e2e/directorio.spec.js e2e/foco-modal.spec.js
npm run e2e -- e2e/agenda.spec.js e2e/caso-detalle.spec.js e2e/historia-clinica.spec.js e2e/bandejas.spec.js e2e/editor.spec.js e2e/diseno.spec.js
npx playwright test --config playwright.financiadores-ui.config.js

# Desde backend, con base exclusiva de prueba y configuración de docs/PRUEBAS.md:
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py spectacular --fail-on-warn --file NUL
python manage.py test apps.instituciones apps.accounts apps.casos apps.registros apps.agenda apps.auditoria apps.formularios apps.flujos --noinput
```

Las nuevas pruebas de cada fix deben quedar incluidas en la selección final. La configuración E2E general usa datos sembrados y ejecuta operaciones; no apuntarla al staging compartido. Los comandos no autorizan crear/resembrar bases existentes.

`docs/PRUEBAS.md` exige evitar dos corridas simultáneas sobre la misma base y procesos de fondo compitiendo por PostgreSQL. Preparar entorno aislado; no detener servicios compartidos automáticamente.

CI existente: `calidad` ejecuta build, auditor de clases, checks Django y OpenAPI; `backend` ejecuta migraciones al día y suite completa cuando cambia backend. Playwright no corre en CI actualmente: adjuntar evidencia local reproducible del SHA final o acordar expresamente un cambio de CI. No inventar un lint/typecheck que package.json no define.

### Condiciones de aceptación del PR

1. Matriz H-01–H-43 con estado y evidencia, sin omitir refinamientos ni declarar corregido lo no reproducido.
2. Decisiones de la sección 3 implementadas y contratos documentados cuando cambien; distinguir las provisionales de las validadas por responsables humanos.
3. Regresión frontend y backend correspondiente aprobada sobre el SHA final; registrar controles no ejecutados y motivo.
4. Recorridos reales y accesibilidad verificados; capturas complementan pruebas, no las sustituyen.
5. Revisión del diff y aceptación humana de las consecuencias sobre firma, avance, turnos, exportación y consentimiento. Antes de revisión final, ofrecer primera lectura al usuario. Antes de incorporar, revisar con él los cambios, dos fallos plausibles, detección y reversión, según AGENTS.md.
6. Separar evidencia local, CI remoto, preparación operativa y aceptación humana. Ninguna implica automáticamente las otras.

## 7. Riesgos y reversión

| Riesgo | Detección/mitigación |
|---|---|
| Shell consulta otro ámbito o rompe el acceso sin institución | Matriz plataforma/hospital/financiador, captura de peticiones, navegación directa y cambio de contexto |
| Guardar borrador avanza el caso o duplica una atención al retomarlo | Prueba de estado persistido, ID de entrada y secuencia guardar/recargar/firmar/avanzar |
| Política aplicada solo en la interfaz | Pruebas directas de API para motivo, enmascarado, pasado, cancelación y contraseña |
| Errores centralizados revelan HTML/detalles internos o pierden campos | Respuestas malformadas, errores anidados, 400/401/403/409/5xx y red |
| Nueva metadata de consentimiento o exportación incompatible con históricos | Migración aditiva, fixtures anteriores, lectura con campos ausentes y política explícita de compatibilidad |
| Una mejora del diseñador invalida condiciones/respuestas anteriores | Fixtures con formularios ya usados y flujos publicados, edición de opciones y tipos bloqueados |
| Un cliente anterior interpreta mal `realizado`, booleanos o múltiples | Desplegar servidor/cliente compatibles y probar lectura de históricos/nuevos valores. Versionar/documentar contrato antes de emitir esos datos; un rollback a código previo no es automáticamente compatible. |
| Workers arrancan antes de existir tablas aunque ya no migren | Primer arranque con volumen aislado vacío, logs por servicio y segundo arranque |

Reversión propuesta: revert de los bloques puramente visuales cuando sean compatibles. Para nuevos estados/tipos/metadata, preparar una versión de aplicación que mantenga lectura de los datos nuevos aunque deje de permitir su alta; conservar columnas/evidencia. No revertir automáticamente el constraint de cupos si ya hay cargas retrospectivas incompatibles con la restricción anterior. No borrar registros de consentimiento, auditoría, historias ni archivos como parte de una reversión. Revertir software tampoco deshace firmas, cancelaciones, publicaciones ni exportaciones ya ejecutadas: las pruebas se realizan con datos sintéticos.

## 8. Estado de esta entrega

La implementación está en la rama `feat/issue-58-ui-ux`, en un worktree aislado. «Implementado» en esta tabla describe código y pruebas focales, no aceptación integral ni despliegue. Las rutas debajo de `frontend/src` y `backend/apps` señalan los bloques principales para revisar. No se hicieron cambios de datos de staging.

| Hallazgo | Estado y evidencia local | Verificación pendiente |
|---|---|---|
| H-01 | Observado: Login inicia con email y contraseña vacíos y `autocomplete` correcto en Chromium limpio. | Autofill con gestor real. |
| H-02 | Implementado en `auth/AuthContext.jsx` y `api/client.js`: almacenamiento opt-in, bloqueo y aislamiento de borrador. Chromium con reloj simulado verificó aviso, bloqueo, reanudación y rechazo de otra identidad; una comprobación posterior verificó el descarte de JWT locales anteriores sin opt-in. | Dos pestañas, ámbito distinto y borrador real. |
| H-03 | Implementado en Login y `docs/funcionalidades/identidad-acceso/`: soporte y propuesta futura por correo. | Configurar contacto operativo real. |
| H-04 | Implementado: foco visible en login y controles compartidos. | Recorrido completo con teclado y zoom. |
| H-05 | Implementado: un H1 por ruta, con títulos internos H2. | Barrido de rutas con lector. |
| H-06 | Implementado: subtítulo de Login con color calculado ~7,05:1 sobre el fondo claro. | Contraste del tema completo y otros estados. |
| H-07 | Implementado en Login: panel y grafo decorativo ajustados. | Revisar 390, 1150 y 1440 px con zoom. |
| H-08 | Implementado: contraseña con control de visibilidad nombrado y autofill correcto. | Teclado y gestor de credenciales. |
| H-09 | Separado en [#59](https://github.com/Mkdir-arg/SistemaDeSalud/issues/59), asignado a `juanikitro`, proyecto Salud. Esta entrega conserva I-Core Salud. | Seguimiento del issue separado. |
| H-10 | Implementado: bandeja en Shell por capacidad, conteo del servidor y recarga. | Roles reales y cambio de institución. |
| H-11 | Implementado: portal sin organizaciones con CTA y catálogo global. Chromium simulado verificó vacío y navegación. | Cuenta real sin financiador. |
| H-12 | Implementado: acción fija en tabla. Chromium simulado verificó botón visible a 1150 y 390 px sin desborde del documento. | Datos reales y navegación por teclado. |
| H-13 | Implementado en `lib/format.js`: antigüedad legible. | Bordes de minutos, horas y días. |
| H-14 | Implementado en instituciones: unicidad de staff activo en ámbitos equivalentes. | Datos históricos reales. |
| H-15 | Implementado en casos: estado y etapa, incluso cancelación. | Recorrido de casos históricos. |
| H-16 | Implementado en UI y motor: motivo obligatorio y prioridad legible. | Doble envío y concurrencia reales. |
| H-17 | Implementado en Bandejas: buscador común y flujo publicado elegido explícitamente. | Recorrido de creación por rol. |
| H-18 | Implementado en Shell y cabeceras: vocabulario alineado. | Lectura editorial de todas las rutas. |
| H-19 | Implementado: etiqueta «En configuración» sin mutar estado interno. | Verificar pantallas antiguas. |
| H-20 | Implementado en CoberturasHospital y Finanzas: vacíos y estado de repartos con actividad conocida. | Circuito real habilitado/deshabilitado y error. |
| H-21 | Implementado en MapaFlujos: carriles, nombres completos y lista alternativa; mock con diamante y ciclo. | Grafos grandes, enlaces externos y lector. |
| H-22 | Implementado en FlujoEditor: validación invalidada tras cambios y aviso consolidado. | Respuesta tardía con red simulada. |
| H-23 | Implementado: Directorio usa el Shell de plataforma. | Perfil de plataforma real. |
| H-24 | Implementado: navegación real, retorno y una salida. | Historia de navegador y acceso directo. |
| H-25 | Implementado: salto a contenido, H1 único e iconos. | Lector y teclado transversal. |
| H-26 | Implementado: exportación POST con motivo, variante y auditoría estricta en `registros/views.py`. | Inspeccionar CSV y evento con roles reales. |
| H-27 | Implementado: orden por rol, grupos plegables y aviso «Ver como». | Todos los roles institucionales. |
| H-28 | Implementado: fecha sin corrimiento, plurales y textos. | Fechas en husos y días límite. |
| H-29 | Implementado: tema oscuro y búsqueda de pacientes acotada por contexto. | Contraste y respuesta tardía tras cambiar ámbito. |
| H-30 | Implementado: errores útiles en cliente sin perder errores por campo. | Respuestas 400/401/403/409/5xx y red. |
| H-31 | Implementado: firma voluntaria, avance explícito desde Caso y enlace a cada entrada sin firmar del caso para editarla o firmarla en Historia. | Historial y caso completos con rol clínico. |
| H-32 | Implementado en cuentas y UI: altas por contraseña y validación. | Activación con enlace real y autofill. |
| H-33 | Implementado: confirmación de publicación y feedback coherente. | Doble clic y respuesta perdida. |
| H-34 | Implementado: endpoint de puesta en marcha y checklist en Inicio. Pruebas focales de instituciones pasaron. | Instalación nueva real. |
| H-35 | Implementado: patrón de errores inline en formularios intervenidos. | Inventario completo de formularios con teclado. |
| H-36 | Implementado: método, versión, evidencia protegida y revocación en registros. | Revisión legal, storage real y retención. |
| H-37 | Implementado: atención pasada con duración real y motivo, sin límite de antigüedad ni reserva de cupo; agenda inactiva visible, turno pendiente reutilizado desde la grilla, caso previo enlazado y clave idempotente. Pasaron 44 pruebas focales en PostgreSQL y un test de dos reintentos simultáneos; todas las migraciones aplicaron en la base de prueba aislada. | Datos históricos reales y aceptación operativa. |
| H-38 | Implementado: vacíos diferenciados en MiTrabajo y Fila; Fila filtrada por institución. Prueba focal de ámbito pasó. | Roles y áreas reales. |
| H-39 | Implementado: booleano, selección múltiple, hora, email y teléfono en editor/API/motor; opciones tipadas y normalizadas; pruebas focales. | Formularios publicados e históricos. |
| H-40 | Implementado: buscador compartido en caso, Turnos y barra. | Respuestas tardías y permisos reales. |
| H-41 | Implementado: vacíos, ayudas nombradas y paginación en secciones del portal; mock verificó 0/1/N y recuperación tras 404 de página. | API y datos reales. |
| H-42 | Implementado: toast único, mensajes precisos, deshacer acotado al editor y su versión, foco al avanzar y stepper finalizado. | Flujo completo y movimiento reducido. |
| H-43 | Implementado: tipo sugerido de institución y documento sin identidad demo. | Valores históricos e instituciones reales. |

Comprobaciones recientes: `npm run build`, `python manage.py check`, `git diff --check` y `docker compose config --quiet` pasaron. Chromium con API simulada cubrió el mapa de diamante/ciclo, tabla a 1150/390 px, login limpio, bloqueo por inactividad con identidad distinta y catálogo global con 0/1/N páginas y 404 de página. Se ejecutaron 92 pruebas focales sobre PostgreSQL temporal, incluidas migraciones desde cero y dos reintentos concurrentes de una atención pasada; el contenedor y su red se retiraron. También se ejercitó en Chromium real el descarte de JWT antiguos sin opt-in. Quedan pendientes recorridos con roles y datos históricos reales, CI del SHA final y aceptación humana. No se ejecutaron QA/HML, migraciones sobre una base de uso real ni limpieza de staging. El contacto operativo de soporte y la política legal siguen pendientes de responsables humanos; las reglas actuales son provisionales y explícitas.

Los commits de esta rama se preparan para revisión en PR. No se recomienda merge ni despliegue hasta completar las verificaciones y revisión indicadas en §6.
