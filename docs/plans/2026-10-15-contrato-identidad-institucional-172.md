# Contrato propuesto: identidad institucional y sesiones — AUD-001/009

Fecha inicial: 15/10/2026. Estado al16/10: **flujo institucional y primer corte de sesiones durables aprobados, implementados y validados localmente**. Detalle de evidencia en el plan principal; sin incorporación ni despliegue.

## Decisiones confirmadas y alcance

El titular administra sus credenciales. El administrador institucional puede iniciar recuperación, pero no elegir/conocer la contraseña ni recibir el enlace. Un bloqueo institucional cambia solamente la pertenencia local. Cambiar/restablecer contraseña revoca las sesiones anteriores. `accounts.Usuario` y `portal.CuentaPaciente` permanecen separados: ninguna ruta `/api/mi/*` recupera una identidad institucional.

El dueño aprobó las rutas y el flujo de invitación, recuperación, reautenticación y verificación del email nuevo. La aprobación del flujo no define por sí sola un esquema de sesiones durables ni una infraestructura de correo. Las vigencias y el perfil conservador de edición se propusieron posteriormente; registrar su decisión concreta antes de habilitar configuración productiva. El despacho durable frente a cola volátil requiere elección explícita en el documento de correo. No hay proveedor, gasto ni despliegue autorizados.

## Evidencia disponible y reutilización

- `accounts.Usuario` ya posee email único, hash de contraseña, `is_active` global y pertenencias `Membresia.activo`. Reutilizar hashing/check de Django y `validate_password`; no crear una segunda identidad.
- `/api/usuarios/me/` es GET. El modal administrativo actualmente manda email/activo y permite elegir contraseña tanto en alta como actualización. No existe autoservicio/recuperación institucional equivalente.
- Los helpers de capacidad aceptan institución; comprobar autoridad en la institución objetivo, sin sumar administración A con pertenencia B.
- Python local, inspección estática sin Django setup ni DB: Django **5.2.15**, SimpleJWT **5.5.1**. Requirements no fija estas versiones: **no son evidencia de la imagen Docker ni de producción**. Verificar versiones/código efectivo antes de aplicar configuración.
- Evidencia adicional comunicada por el coordinador: imagen actual con Python **3.12.15**, Django **6.1.2**, SimpleJWT **5.5.1**; inspección de fuente instalada confirma la comparación de huella en `JWTAuthentication.get_user` y su ausencia en `TokenRefreshSerializer.validate`. Es evidencia del coordinador, no una ejecución propia de este agente; no se emitieron tokens en esa comprobación. La inspección del generador reset descrita aquí corresponde a Django local y debe contrastarse con esa imagen antes de implementarlo.
- En ese SimpleJWT, `CHECK_REVOKE_TOKEN` añade una huella del hash de contraseña al emitir tokens y `JWTAuthentication.get_user` la compara. **`TokenRefreshSerializer.validate` no compara esa huella**: su regla de usuario activo y la rotación no bastan para rechazar el refresh anterior a un cambio. La propuesta requiere comprobar explícitamente esa huella también en refresh, conservando la regla de autenticación de simulación existente.
- `PasswordResetTokenGenerator` de Django vincula el token a usuario, hash de contraseña, email, último login y tiempo. Permite reset sin tabla nueva si se valida y cambia la contraseña dentro de un bloqueo/transacción sobre el usuario. No usar `PasswordResetForm` sin adaptación: el formulario estándar excluye contraseñas inutilizables, necesarias para invitaciones.
- Portal sirve como referencia de límites, mensajes no enumerables y enlaces en fragmento. Su correo actual usa un hilo no durable: puede perder mensajes al reiniciar; no atribuirle entrega garantizada ni reutilizar sus enlaces/cuentas.

## Contrato mínimo propuesto

Las rutas nuevas se proponen bajo `/api/auth/`. Respuestas de credenciales no incluyen contraseña, hash, token de recuperación ni email sensible de terceros. Operaciones de identidad rechazan una sesión de simulación, incluso cuando el actor real sea superusuario; no permitir modificar credenciales de una cuenta de referencia ni caer silenciosamente al actor real.

| Ruta / método | Actor y petición | Resultado propuesto |
|---|---|---|
| `POST /api/usuarios/` (existente, contrato modificado) | Admin de institución objetivo; `{email,nombre,apellido,institucion,rol}`. Rechazar `password`, privilegios y bloqueo global explícitos. | Crear identidad con contraseña inutilizable y membresía transaccional; iniciar invitación al email del titular. `201` con datos administrativos, nunca enlace. Si email ya existe, no reasignar identidad ni crear membresía automáticamente. |
| `PATCH/PUT /api/usuarios/{id}/` (existente) | Admin no modifica email/password/is_active de otra persona. Nombre/apellido dependen de decisión pendiente; alcance por institución administrada y cuenta objetivo. | Campo prohibido produce error explícito y **ningún cambio parcial**. Evitar perder actualización legítima porque UI envía campos bloqueados sin modificarlos: corregir payload junto al backend. |
| `DELETE /api/usuarios/{id}/` (existente) | Admin institucional no elimina identidad global. | Denegado. Baja local por membresía; política de eliminación global/retención fuera de este contrato. |
| `PATCH /api/membresias/{id}/` (existente) | Admin con capacidad efectiva en la institución de esa membresía; `{activo:false}`. | Revocar acceso local tras commit, preservar restantes instituciones y la identidad. No cambiar `Usuario.is_active` ni invalidar JWT global por baja local. |
| `POST /api/usuarios/{id}/iniciar-recuperacion/` (nueva) | Admin en institución que administra y en la que el destinatario tiene pertenencia; cuerpo vacío. Privilegiados requieren regla aprobada. | `202` genérico. Enlace solo al email actual almacenado; actor, destino institucional y solicitud quedan auditados sin token. Sin parámetros para cambiar destinatario. |
| `POST /api/auth/recuperacion/` (nueva) | Público; `{email}`. | `202` idéntico para email inexistente/inactivo/no elegible y existente; no revelar identidad ni resultado SMTP. Cuenta de referencia no elegible. |
| `POST /api/auth/restablecer/` (nueva) | Público; `{uid,token,nueva_password}`. Token incluye propósito de invitación o recuperación, separado de otros enlaces. | Releer y bloquear usuario, validar token/vigencia/propósito, `validate_password`, guardar nuevo hash. `204`; no entregar sesión. Token deja de servir por cambio de hash. Invitar y recuperar comparten servicio, sin habilitar cuenta globalmente inactiva. |
| `POST /api/auth/cambiar-password/` (nueva) | Usuario real autenticado; `{password_actual,nueva_password}`. | Verificar contraseña actual, bloquear/releer, validar y guardar. `204`; cerrar todas las sesiones, incluida la actual, y solicitar nuevo login. |
| `POST /api/auth/cambio-email/` (nueva) | Usuario real autenticado; `{password_actual,nuevo_email}`. | Reautenticar; `202` genérico e iniciar verificación al nuevo email. **No cambiar email todavía**. Avisar al email actual sin secretos, según política aprobada. |
| `POST /api/auth/confirmar-email/` (nueva) | `{uid,token,nuevo_email}`; token firmado vincula usuario, email actual/nuevo, estado de contraseña, propósito y vencimiento. | Validar bajo lock y aplicar email con unicidad de DB; errores no enumeran propietario del destino. `204`; notificar email anterior/nuevo. Sin tabla pendiente si se acepta la semántica descrita debajo. |
| `POST /api/auth/token/` y `POST /api/auth/token/refresh/` (existentes) | Contrato de payload actual; ampliar validación de huella/estado sin reemplazar autenticador de simulación. | Después de cambiar contraseña, access y refresh anteriores fallan en siguiente solicitud. Token legacy sin huella se rechaza al activar el mecanismo: cierre de sesión planificado. |

No usar un nuevo email suministrado por el admin como destinatario de recuperación. Recuperación no cambia email. Si el titular perdió acceso al correo, hace falta procedimiento humano excepcional de identidad, autoridad y auditoría: no resolverlo permitiendo al admin reemplazarlo libremente.

## Invitación y email sin esquema nuevo: límites deliberados

Recomendación inicial: cuenta invitada activa con contraseña **inutilizable**, sin sesión emitida y con membresía normal; solo el enlace puede establecer la primera clave. Reenviar invitación exige actor autorizado y no altera contraseña de cuentas ya activadas. El estado inutilizable no representa bloqueo global: `is_active=False` sigue excluido de recuperación/activación ordinaria.

Los tokens de invitación/recuperación usarían un generador de Django con salt/propósito institucional propio. Sin persistencia de emisión, varios enlaces pueden permanecer válidos hasta primer canje/cambio de estado o vencimiento; **no prometer que solo el último correo sirve**. Bloquear usuario antes de validar evita doble canje concurrente con la misma contraseña inicial. Si se exige revocación individual de enlace, solo-último o historial durable de invitación, se necesita estado adicional y decisión específica.

Para verificar email nuevo se necesita un token con propósito y destino vinculados; un token de reset estándar por sí solo no autoriza cualquier `nuevo_email`. Puede implementarse mediante generación/validación firmada con estado actual, sin almacenar pendiente. Tras cambiar email, el enlace viejo falla porque cambia el estado vinculado. Unicidad simultánea debe convertirse en error controlado; no capturar excepción de integridad dentro de la transacción para continuar usándola. Cada propósito tiene vigencia explícita y no acepta tokens de otro flujo.

La dirección pública institucional debe ser configuración confiable, no `Host` del request. Enlace con fragmento y SPA que lo borra tras consumo; nunca logs, analytics o errores con token. No reutilizar `PORTAL_URL_BASE` por proximidad sin establecer contrato institucional separado.

## Revocación: qué resuelve el camino sin migración

**Cambio/reset de contraseña:** huella de contraseña en access y refresh, comprobada con estado del usuario leído del servidor. Añadir validación de refresh, porque la biblioteca local no la hace. No registrar ni devolver hash de contraseña; la huella JWT es mecanismo de revocación de biblioteca, no un hash utilizable para autenticar. Evaluar exposición de claims antes de adoptar.

**Baja de membresía:** JWT autentica persona, no un derecho permanente sobre cada institución. El permiso/queryset debe consultar membresía activa en cada solicitud; acciones mutantes revalidan bajo la transacción cuando corresponda. El token puede seguir funcionando en B y `/usuarios/me/` debe reflejar baja A. La UI limpia caché A y no muestra datos anteriores durante el cambio. Este contrato niega solicitudes nuevas tras commit; no puede retirar bytes ya entregados ni deshacer una operación que adquirió autoridad antes de la baja. Si se exige cancelar operaciones en vuelo, hace falta contrato y locks adicionales por servicio.

**Carrera cambio de contraseña/refresh:** refresh que comenzó antes del cambio puede responder después, pero debe conservar la huella anterior; su access/refresh también quedarán rechazados. Nunca regenerar huella actual para legitimar un refresh antiguo. Probar ambos órdenes con conexiones independientes.

**Logout individual, compromiso sin cambio de clave y replay de rotación:** el camino anterior NO los resuelve. Guardar tokens solo en cliente y rotarlos sin blacklist no revoca servidor. Para cerrar AUD-009 completo se requiere una segunda decisión: sesión institucional durable con identificador/revocación y política de familia de refresh, o mecanismo equivalente demostrado. Blacklist de refresh solamente no revoca access ya emitido. No añadir tabla ni habilitar app de blacklist silenciosamente; son cambios de esquema/operación que requieren aprobación y un diseño acotado. Hasta entonces, no declarar AUD-009 cerrado ni presentar logout como revocación remota.

Recomendación: entregar primero propiedad de identidad y revocación por contraseña sin modelo nuevo, después cerrar logout/replay mediante el estado durable aprobado. No rotar `SECRET_KEY` ni rehashear contraseñas como truco para simular logout.

## Correo y abuso

Reutilizar SMTP configurado, sin proveedor nuevo. `202` significa solicitud aceptada, **no entrega garantizada**. La creación/invitación persiste aunque falle correo; reenvío permite recuperar. Mostrar ese estado en UI sin revelar enlaces. Emisión después de commit, timeout SMTP y logs sanitizados; no lanzar envío si la creación revierte.

El hilo actual del portal no debe convertirse en garantía institucional: una caída puede perder el envío. Dos alternativas por aprobar: entrega de mejor esfuerzo con reenvío y riesgo visible, o intención durable con reintentos/observabilidad reutilizando patrones del proyecto, que puede requerir esquema. El flujo no es apto para onboarding productivo hasta verificar envío real y recuperación ante fallo. No afirmar email entregado porque la API responda o porque locmem contenga un mensaje.

Rutas públicas combinan límites por origen y por identidad normalizada; iniciación administrativa además por actor/destinatario. Reautenticación limita intentos; cuenta inexistente usa trabajo de hashing comparable cuando corresponda. No responder distinto por SMTP y no hacer envío síncrono solo para emails existentes, lo que agregaría un canal temporal evidente. No prometer tiempo constante absoluto. Reutilizar patrón de cache compartido, comprobar tolerancia multiworker e IP de proxy confiable: SimpleRateThrottle no garantiza contador atómico. Tasas y tolerancia de NAT/abuso son pendientes, no números inventados.

## UI y compatibilidad

- Modal de usuarios: quitar contraseña y checkbox de activo global para admin; alta indica invitación. El botón de recuperación nunca muestra token ni permite editar destino. Gestionar bloqueo local desde membresías.
- Login institucional: sustituir ayuda estática por solicitud de recuperación; vistas de invitación/reset y verificación de email separadas de `/mi/*`.
- Cuenta propia: cambio de contraseña/email con contraseña actual; al cambiar contraseña limpiar tokens/caché y mostrar nuevo login. No ejecutar como cuenta simulada.
- Coordinar nueva alta con consumidores existentes: clientes que mandan `password` deben recibir error explícito y migrar al contrato de invitación. No mantener temporalmente una vía privilegiada sin autorización que permita al admin seguir eligiendo claves.
- Los seeds sintéticos y creación por management command no se convierten por accidente en APIs públicas; no cambiar sus contratos como parte del modal. Revisar Django Admin en AUD-042: sus vías de cambio directo siguen siendo una excepción pendiente de política, no una garantía cerrada por arreglar REST.

## Pruebas de aceptación propuestas

1. Admin A/miembro B no cambia identidad B, no crea en B, no borra cuenta global ni desactiva B con bloqueo A. Persona compartida y superusuario compartido incluidos. PATCH mixto no aplica campos parcialmente. La gestión legítima de membresías A funciona.
2. Alta no acepta password del admin; hash inutilizable y cero sesión antes del enlace; correo solo al titular, sin enlace en respuesta/logs. Primer canje establece clave validada y segundo canje falla, incluso con dos conexiones PG.
3. Recuperación no revela existencia por status/cuerpo/errores SMTP; límites se aplican a nombres existentes y no existentes; admin ajeno no inicia recuperación de B. No se puede cambiar destinatario ni consumir token del portal.
4. Cambio propio exige password actual; cuenta de referencia/simulación rechazada; nueva password pasa validadores. Con JWT real anterior: GET, refresh y simulación fallan después del commit; nuevo login funciona. Incluir refresh concurrente y tokens legacy.
5. Baja A con token real conserva B y login global, deniega rutas A y elimina datos A del contexto/caché del navegador. Revalidar permisos de servicios, no solo `/me/`.
6. Email pendiente no cambia login; destino vinculado al token no puede sustituirse; vencimiento, token de otro propósito, doble confirmación, unicidad concurrente y enlace emitido antes de reset fallan de forma controlada.
7. Rollback no envía invitación; fallo/reinicio de correo tiene conducta y reenvío visibles. Ensayo SMTP autorizado prueba entrega/recepción, además de tests de buzón sintético.
8. Cuando se apruebe sesión durable: logout, replay, familia comprometida, varias pestañas/dispositivos, carreras refresh/logout y limpieza/retención deben tener pruebas adicionales antes de cerrar AUD-009.

## Incorporación, reversión y decisiones pendientes

Implementar por contratos pequeños: contención AUD-001 → invitación/recuperación propia → cambio de contraseña y revocación access/refresh → verificación de email → sesiones durables según decisión. No mezclar con cambios del portal ni cerrar AUD-009 antes de su última garantía aplicable.

Activar huella invalida JWT legacy: anunciar nuevo login y verificar todos los autenticadores, incluida simulación. Desactivar luego esa validación puede volver a aceptar tokens comprometidos todavía vigentes: no es rollback seguro. Ante fallo contener temporalmente autenticación/cambio, conservar validación y corregir; restaurar código antiguo no debe reabrir edición global de credenciales. Nuevos emails/passwords confirmados no se revierten automáticamente al hacer rollback de aplicación.

Antes de implementación el dueño debe decidir: (a) API y onboarding propuestos; (b) administración de nombre/apellido y excepciones de plataforma/Admin; (c) vigencias, varios enlaces válidos y reautenticación/email; (d) cierre global o por dispositivo y estado durable; (e) garantía de correo, presupuesto y tasas; (f) latencia de revocación/operaciones en vuelo y comunicación de cierre legacy. No se ejecutaron Django, DB, Docker, tests ni servicios para esta propuesta.


## Propuesta original AUD-009 — 15/10/2026, resuelta en el apartado siguiente

El dueño autorizó continuar el trabajo tras la propuesta de revocación durable. Esto no registra todavía una decisión humana sobre el diseño específico, replay o retención. La consulta sobre replay está pendiente; las siguientes opciones son recomendaciones de agentes.

**Primer corte propuesto, backend institucional:** `SesionInstitucional` en PostgreSQL, separada de `portal.CuentaPaciente`/`SesionPortal`, con UUID `sid`, usuario, creación, revocación y huella del JTI refresh vigente con su vencimiento; no guardar tokens completos. Login crea sesión y tokens transaccionalmente. Access y refresh incorporan `sid`; el autenticador institucional comprueba la sesión durable además del usuario y la huella de contraseña existentes. La autenticación de simulación debe hacer la misma comprobación sobre el actor real antes de sustituirlo por la cuenta de referencia. No basta con reemplazar únicamente el autenticador JWT principal.

Refresh de un solo uso: bloquear **Usuario→Sesión**, validar revocación/contraseña/JTI vigente y persistir el JTI sustituto antes de confirmar la respuesta. Logout revoca la sesión de ese login; solicitudes posteriores al commit rechazan sus access y refresh. Pestañas que comparten tokens comparten sesión, sin afirmar identificación de dispositivo físico. Conservar la revocación global por cambio/reset de contraseña. No introducir duración absoluta nueva silenciosamente: las vigencias actuales son la referencia para el contrato detallado.

| Política de reutilización del refresh | Ganancia y coste | Estado |
|---|---|---|
| Rechazar el refresh consumido y mantener válida la sesión del ganador | Evita que una carrera legítima de pestañas destruya al ganador; una familia comprometida exige cierre explícito o cambio/reset de contraseña. | Recomendación del agente de seguridad por continuidad operativa. |
| Revocar toda la familia ante reutilización | Contiene una familia posiblemente comprometida; una carrera legítima entre pestañas también puede cerrar la sesión durante una atención. | Recomendación del coordinador por seguridad; requiere aceptar ese coste y contrastar coordinación entre pestañas. |

**La elección corresponde al dueño y sigue pendiente.** En cualquiera de las opciones, un mismo refresh no obtiene dos renovaciones válidas. Probar refresh/refresh y refresh/logout con dos conexiones PostgreSQL, pérdida de respuesta tras rotación, contraseña, sesión revocada y simulación. La revocación aplica a solicitudes autenticadas después del commit; no cancela retroactivamente operaciones ya en vuelo.

Activar la exigencia de `sid` rechazará JWT legacy: requiere nuevo login planificado. Las cookies de Django y `SessionAuthentication` son una frontera distinta, también utilizada por Admin; no atribuirles revocación por logout JWT ni deshabilitarlas sin decisión expresa. No hay purga automática ni plazo de retención productivo decidido; especificar conservación y limpieza antes de habilitar producción. Una fila ausente o revocada nunca vuelve a autorizar tokens anteriores.

**Segundo corte pendiente: revocación institucional sin afectar otras instituciones.** La propuesta requiere una generación durable usuario/institución y una fotografía por sesión: retirar A invalida A, conserva B y reactivar A no rehabilita tokens anteriores. Refresh no recaptura esa fotografía. El esquema y los cambios que incrementan la generación todavía necesitan contrato específico. La inspección encontró consultas de membresías en aproximadamente 23 módulos, además de helpers/scopes de `common.py`; revisar las vías API/Admin/inlines/M2M y los accesos directos antes de afirmar cobertura. El primer corte no modifica esos permisos ni cierra esa parte de AUD-009.

### Decisión del dueño y alcance de ejecución — 16/10/2026

El dueño eligió expresamente **«conservar la renovación válida»** y autorizó continuar. Esto resuelve la consulta de replay anterior: refresh consumido se rechaza sin revocar al ganador. Ratificó avanzar tras explicitar sesión durable PostgreSQL, cierre de ese login, invalidación de todas las credenciales previas por cambio/reset de contraseña, vigencias actuales y nuevo login obligatorio para JWT legacy sin identificador de sesión. La retención y limpieza se definirán antes de producción; no se añade purga automática.

Detalle técnico del agente dentro de ese alcance: `POST /api/auth/logout/` recibe únicamente `{refresh}` y responde204 al cerrar o repetir el cierre con el token terminal vigente. Valida firma, propósito, propietario, sesión y JTI; no utiliza cookies ni una identidad simulada. Rechaza refresh consumido/expirado/inválido con401, conservando la renovación válida. Esto evita que el mismo token rechazado en refresh pueda cerrar al ganador por otra ruta. El cliente espera su renovación en vuelo, captura el token vigente y distingue confirmación remota de limpieza local; un fallo no se presenta como revocación acreditada.

La autenticación ordinaria y la de simulación validan la sesión del actor real antes de resolver identidad efectiva. El orden de bloqueo para login/refresh/logout se mantiene Usuario→Sesión. Revocación se verifica al autenticar solicitudes posteriores al commit; no cancela operaciones que ya estaban en vuelo. Cookies Django/Admin y revocación institucional durable siguen siendo fronteras separadas: este corte no sustituye su contrato ni la matriz de permisos.

Implementación: backend `443adfe`, frontend `6e70327`;325 pruebas PostgreSQL,25 Node y validación navegador/HTTP reales documentados con comandos y límites en el plan principal. Logout local por inactividad/propagación permanece distinto del cierre remoto explícito. La activación productiva y la aceptación humana siguen pendientes; no se declara AUD-009 completamente cerrado.
