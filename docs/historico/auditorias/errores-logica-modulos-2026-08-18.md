# Auditoria de errores logicos por modulo

Fecha: 2026-08-18

Alcance: revision estatica de documentacion funcional, rutas frontend, routers backend, permisos, serializers, viewsets y motores de los modulos principales. No se hicieron cambios de codigo en esta pasada.

No se pudieron ejecutar las pruebas automatizadas completas desde el primer entorno porque faltaba Django. Se encontro `.venv` en `backend/`, pero la corrida focalizada `apps.farmacia apps.casos apps.red apps.auditoria` excedio 120 segundos y quedo inconclusa.

## Resumen ejecutivo

Se detectaron errores o riesgos logicos principalmente en cuatro zonas:

- Integridad entre instituciones en flujos/casos.
- Referencias cruzadas no validadas en el diseñador de flujos.
- Estados `cancelado` no excluidos de algunos conteos/validaciones.
- Ambiguedad funcional en entregas parciales de farmacia.

## Hallazgos criticos

### 1. Derivaciones internas pueden apuntar a areas o flujos de otra institucion

Severidad: critica.

Evidencia:

- `backend/apps/casos/motor.py:642` toma `area_destino_id` desde `nodo.config`.
- `backend/apps/casos/motor.py:656` busca `VersionFlujo` por `flujo_destino_id`.
- No aparece validacion equivalente a `area.institucion_id == caso.institucion_id` ni `ver_destino.flujo.institucion_id == caso.institucion_id` en ese bloque.

Impacto funcional:

- Un flujo de la institucion A puede derivar un caso hacia un area o flujo de la institucion B si la configuracion queda mal cargada o manipulada por API.
- El caso nuevo se crea con `institucion=caso.institucion`, pero puede quedar parado sobre una version de flujo o area ajena.
- Esto rompe scope institucional, bandejas, supervision, auditoria y reportes.

Riesgo sanitario/operativo:

- Casos que aparecen en areas incorrectas.
- Equipos que no pueden tomar el caso porque los grupos/areas pertenecen a otra institucion.
- Trazabilidad interinstitucional falsa.

Recomendacion:

- En el motor, validar siempre que `area_destino` y `flujo_destino` pertenezcan a la institucion del caso para derivaciones internas.
- En el serializer/editor, validar tambien al guardar configuracion del nodo.
- Agregar tests de API directa, no solo de UI.

### 2. Estudios derivados e interconsultas aceptan `area_id` de otra institucion

Severidad: critica.

Evidencia:

- `backend/apps/casos/views.py:344` y `backend/apps/casos/views.py:366` buscan `Area.objects.filter(pk=area_id).first()`.
- `backend/apps/casos/views.py:347` llama `motor.solicitar_estudio_derivado`.
- `backend/apps/casos/views.py:370` llama `motor.solicitar_interconsulta`.
- `backend/apps/casos/motor.py:1129` busca una version publicada con `flujo__area=area_destino`.

No se valida que el area destino pertenezca a la misma institucion del caso.

Impacto funcional:

- Un medico/enfermeria de una institucion puede abrir un subcaso asociado a un area de otra institucion.
- El subcaso se crea con la institucion del caso origen, pero con flujo/area potencialmente ajenos.
- Puede dejar al caso origen en espera de un equipo que no lo ve o no corresponde.

Recomendacion:

- Validar en view y motor: `area_destino.institucion_id == caso.institucion_id`.
- Si se desea interconsulta interinstitucional, debe pasar por `red/traslados` u otro circuito explicito, no por subproceso interno.

### 3. Conexiones del flujo pueden unir nodos de otra version/institucion

Severidad: critica.

Evidencia:

- `backend/apps/flujos/serializers.py:50` define `ConexionSerializer`.
- Solo expone `version`, `origen`, `destino`, `etiqueta`, `condicion`; no se ve validacion de que `origen.version_id == version.id` y `destino.version_id == version.id`.
- `backend/apps/flujos/views.py:48-60` solo valida que la version sea borrador.

Impacto funcional:

- Una conexion guardada en la version A puede tener destino en un nodo de la version B.
- Al avanzar, el motor puede mover un caso a un nodo que no pertenece a su version.
- El grafo publicado puede verse coherente en UI pero ejecutar saltos imposibles.

Recomendacion:

- Validar en `ConexionSerializer.validate`.
- Rechazar si origen o destino no pertenecen a la version indicada.
- Agregar constraint/test para API directa.

## Hallazgos altos

### 4. Nodos pueden referenciar formularios o grupos de otra institucion

Severidad: alta.

Evidencia:

- `backend/apps/flujos/serializers.py:28` define `NodoSerializer`.
- Expone `formulario`, `grupos` y `config` sin validaciones institucionales visibles.
- La permission del nodo se calcula por `version__flujo__institucion`, pero no por las referencias internas del nodo.

Impacto funcional:

- Un nodo de la institucion A podria usar un formulario de la institucion B.
- Un nodo podria asignar grupos responsables de otra area/institucion.
- El caso puede quedar inoperable porque los usuarios locales no integran esos grupos.
- Puede filtrar nombres de grupos/formularios ajenos si se serializan detalles.

Recomendacion:

- Validar que `formulario.institucion_id == version.flujo.institucion_id`.
- Validar que todos los grupos pertenezcan a areas de la misma institucion.
- Validar tambien referencias dentro de `config`: `area_destino_id`, `flujo_destino_id`, `guardar_en`, etc.

### 5. Flujo puede declararse en una institucion y apuntar a area/subarea ajena

Severidad: alta.

Evidencia:

- `backend/apps/flujos/serializers.py:132` tiene `validate`.
- `backend/apps/flujos/serializers.py:136` solo valida coherencia entre `subarea` y `area`.
- No se ve validacion de `area.institucion_id == institucion.id` ni de `subarea.area.institucion_id == institucion.id`.

Impacto funcional:

- Un flujo puede quedar registrado como perteneciente a una institucion pero asociado a un area de otra.
- Afecta filtros, mapa de flujos, derivaciones, supervision y seleccion de flujos por area.

Recomendacion:

- Agregar validacion institucional en `FlujoSerializer.validate`.
- Cubrir altas y updates.

### 6. Subprocesos cancelados pueden dejar un caso padre esperando para siempre

Severidad: alta.

Evidencia:

- `backend/apps/casos/motor.py:1182` en `_retornar_al_origen` calcula pendientes con `.exclude(estado=Caso.Estado.CERRADO)`.
- En `cancelar_caso`, la logica equivalente excluye correctamente `CERRADO` y `CANCELADO`.

Escenario:

1. Caso padre abre dos subprocesos bloqueantes.
2. Se cancela uno.
3. Se cierra el otro.
4. `_retornar_al_origen` ve el subproceso cancelado como "pendiente" porque solo excluye cerrados.
5. El caso padre puede quedar en espera indefinidamente.

Recomendacion:

- Cambiar `_retornar_al_origen` para excluir `estado__in=[CERRADO, CANCELADO]`.
- Agregar test con dos subprocesos: uno cancelado y otro cerrado.

### 7. Traslados aceptados eligen "un flujo publicado del area" por orden tecnico

Severidad: alta.

Evidencia:

- `backend/apps/red/motor.py:232` filtra `VersionFlujo` por `flujo__area=area`.
- El bloque usa orden tecnico por flujo/version y no una marca funcional de "flujo receptor de traslados".

Impacto funcional:

- Si un area tiene mas de un flujo publicado, el traslado puede abrirse en un circuito incorrecto.
- La UI de flujos distingue origen manual/derivado, pero el motor de red no parece usar esa intencion funcional.

Recomendacion:

- Definir criterio explicito de flujo receptor: por configuracion del area, por tipo de inicio (`derivado`/`ambos`) o por seleccion obligatoria al aceptar.
- No elegir por `flujo_id`.

### 8. Estudios/interconsultas tambien eligen flujo por orden tecnico

Severidad: alta.

Evidencia:

- `backend/apps/casos/motor.py:1129` filtra `VersionFlujo` por `flujo__area=area_destino`.

Impacto funcional:

- Una interconsulta a "Imagenes" o "Laboratorio" puede abrir el flujo equivocado si el area tiene varios procesos publicados.
- El problema se agrava porque el caso origen queda bloqueado esperando retorno.

Recomendacion:

- Hacer que la accion pida flujo destino o que el area tenga un flujo receptor por defecto.
- Validar que el flujo elegido acepte derivacion/subproceso.

## Hallazgos medios

### 9. Institucionales con `config` podrian crear instituciones nuevas

Severidad: media/alta, segun modelo de gobierno.

Evidencia:

- `backend/apps/instituciones/views.py:85` define `InstitucionViewSet`.
- `backend/apps/common.py:65` resuelve institucion de payload.
- `backend/apps/common.py:130` permite create si el usuario tiene la capacidad en la institucion resuelta; si no se resuelve, cae a capacidades del usuario.

Con `institucion_path = "id"`, al crear una institucion no hay institucion padre. Si un admin institucional tiene `config`, podria pasar el permiso de alta global.

Impacto funcional:

- Un admin de hospital podria crear otro establecimiento.
- En gestion estatal, el alta de instituciones suele ser atribucion central, no institucional.

Recomendacion:

- Definir si crear instituciones es solo superusuario/plataforma.
- Si es asi, sobreescribir `create` o permission para `InstitucionViewSet`.

Estado 2026-08-20: cerrado en Bloque 2. `InstitucionViewSet` exige `gobierno_plataforma` para escritura, conserva lectura acotada para usuarios institucionales y permite alcance global solo a superusuario o autoridad de plataforma.

### 10. Casos cancelados cuentan como activos en algunos modulos

Severidad: media.

Evidencia:

- `backend/apps/instituciones/views.py:105` calcula `casos_activos` excluyendo solo `CERRADO`.
- `backend/apps/flujos/serializers.py:161` hace lo mismo.
- `backend/apps/flujos/views.py:350` impide retirar una version si hay casos no cerrados, incluyendo cancelados.

Impacto funcional:

- Tableros o metricas pueden inflar activos.
- Un flujo podria no poder archivarse aunque solo tenga casos cancelados.
- Contradice otras zonas del codigo que ya excluyen `CERRADO` y `CANCELADO`.

Recomendacion:

- Normalizar la definicion de "activo": excluir `CERRADO` y `CANCELADO`.
- Crear helper o queryset compartido para evitar divergencias.

### 11. Entrega parcial de farmacia queda cerrada como entregada

Severidad: media/producto.

Evidencia:

- `backend/apps/farmacia/motor.py:343` valida `cant > linea.pedido_cant`, pero no `cant + linea.entregado`.
- `backend/apps/farmacia/motor.py:351` acumula `linea.entregado += cant`.
- `backend/apps/farmacia/motor.py:354` cierra siempre el pedido como `ENTREGADO`.

Impacto funcional:

- El sistema conserva el faltante por linea, pero el pedido queda cerrado.
- Si la intencion es permitir entregas parciales sucesivas, el estado deberia quedar pendiente/preparado/parcial.
- Si la intencion es cerrar con faltante, el comentario y el estado `PREPARADO` generan ambiguedad.

Recomendacion:

- Decidir regla de producto:
  - Cerrar siempre: renombrar/explicar "entregado con faltante".
  - Permitir completar: no cerrar si alguna linea tiene faltante.
- Validar `cant + entregado <= pedido_cant` si se permiten entregas sucesivas.

## Observaciones de menor severidad

### 12. Auditoria como capacidad no esta modelada igual en backend y frontend

Severidad: baja.

El backend resuelve auditoria con `PuedeAuditar` y roles de conduccion. El frontend la presenta como capacidad para mostrar menu. Funcionalmente esta bien documentado, pero conviene mantenerlo muy visible para que nadie agregue `auditoria` a `ROL_CAPACIDADES` sin revisar alcance.

### 13. La fachada FHIR parece bien acotada, pero depende de permisos equivalentes

Severidad: baja/media.

La fachada FHIR esta planteada como solo lectura y auditada. La revision no encontro un bug puntual, pero por criticidad conviene mantener tests que aseguren:

- Medico sin `registros` no lee `Patient`.
- Rol sin `trabajo` no lee `Encounter`.
- Lecturas por FHIR generan `AccesoClinico`.

## Ampliacion del barrido profundo

Los siguientes hallazgos se suman al primer barrido. Se enumeran como errores o riesgos logicos detectados, no como plan de implementacion.

## Hallazgos criticos adicionales

### 14. `CasoViewSet` permite escribir estado y posicion del caso por CRUD generico

Severidad: critica.

Evidencia:

- `backend/apps/casos/views.py` define `CasoViewSet(BaseModelViewSet)`.
- `backend/apps/casos/serializers.py` expone `institucion`, `version`, `estado`, `prioridad`, `nodo_actual`, `area_actual`, `asignado_a`, `origen` y `estudio`.
- `perform_create` guarda el caso y asegura historia, pero no fuerza el circuito de motor.

Impacto funcional:

- Un usuario con capacidad operativa podria crear casos en versiones no publicadas.
- Podria cambiar estado, paso actual, area o asignacion sin evento.
- Se rompe trazabilidad, responsabilidad del equipo, tiempos de espera y coherencia del flujo.

Recomendacion:

- Quitar escritura generica de campos de estado/posicion.
- Dejar alta minima y acciones de motor como unica forma de mutar el caso.

### 15. `ValorCampoViewSet` permite alterar datos cargados sin pasar por el paso del flujo

Severidad: critica.

Evidencia:

- `ValorCampoSerializer` expone `caso`, `campo`, `nodo` y `valor`.
- `ValorCampoViewSet` hereda CRUD generico.
- `_guardar_valores` guarda claves recibidas sin rechazar campos ajenos al formulario del nodo.

Impacto funcional:

- Se pueden modificar datos clinicos u operativos ya cargados.
- Se pueden inyectar campos de otros formularios o instituciones.
- Decisiones posteriores pueden ejecutarse con datos no cargados en el paso real.

Recomendacion:

- Hacer el endpoint read-only.
- Validar en el motor que todo `campo_id` pertenezca al formulario del nodo actual.
- Si se corrige un valor, debe existir accion formal con autor y motivo.

### 16. `EventoCasoViewSet` permite falsificar la linea de tiempo

Severidad: critica.

Evidencia:

- `EventoCasoSerializer` expone `caso`, `titulo`, `detalle`, `autor` y `nodo`.
- `EventoCasoViewSet` usa CRUD generico con capacidad `trabajo`.

Impacto funcional:

- Se pueden crear, editar o borrar eventos de trazabilidad.
- La linea de tiempo deja de ser prueba confiable de quien hizo que y cuando.

Recomendacion:

- Hacer eventos read-only.
- Crear notas manuales por accion especifica, con autor y fecha del servidor.

### 17. `ItemFilaViewSet` todavia permite POST generico de items de cola

Severidad: critica/alta.

Evidencia:

- `ItemFilaViewSet` restringe PATCH y DELETE, pero mantiene `post`.
- `ItemFilaSerializer` expone `caso`, `nodo`, `urgente`, `orden`, `atendido`, `ausente` y `box`.

Impacto funcional:

- Se pueden crear items de cola falsos o duplicados.
- Un caso puede aparecer en una fila que no corresponde a su nodo actual.
- Se puede alterar el orden operativo sin evento.

Recomendacion:

- Quitar POST generico.
- Crear cola solo desde el motor.
- Evitar mas de un item activo por caso/nodo.

### 18. Updates genericos validan el objeto actual pero no siempre el destino institucional

Severidad: critica transversal.

Evidencia:

- `CapacidadPermission.has_object_permission` valida contra la institucion del objeto actual.
- Varios serializers exponen FKs que definen scope: `institucion`, `area`, `subarea`, `version`, `formulario`, `deposito`, `areas`, `miembros`.

Impacto funcional:

- Un usuario autorizado sobre un objeto de la institucion A podria intentar moverlo a un padre de la institucion B por PATCH.
- Se generan objetos visibles en un contexto y dependientes de otro.

Recomendacion:

- Hacer read-only en update los FKs de scope.
- Revalidar destino en `perform_update`.
- Crear acciones explicitas de mudanza si son negocio real.

### 19. El modelo de capacidades es demasiado amplio para salud

Severidad: critica funcional/privacidad.

Evidencia:

- `trabajo` habilita casos, filas, agenda operativa, farmacia, internacion y red.
- `registros` mezcla padron, historia clinica, estudios, recetas y consentimientos.
- `administrativo`, `enfermeria`, `medico` y `jefe_area` comparten permisos clinicos amplios.

Impacto funcional:

- Roles administrativos pueden quedar con acceso clinico completo.
- Roles asistenciales pueden operar stock, internacion o traslados sin permiso especifico.
- El menu y la API no distinguen dominios sanitarios con responsabilidades legales distintas.

Recomendacion:

- Dividir capacidades por dominio: padron, historia clinica, prescripcion, turnos, casos, filas, internacion, farmacia, traslados, auditoria y gobierno.

### 20. Reserva de turno usa objeto incompatible para chequear permiso

Severidad: critica.

Evidencia:

- `TurnoViewSet.create` busca `Agenda` y `Ciudadano` por id global.
- Luego ejecuta `self.check_object_permissions(request, agenda)`.
- El `institucion_path` del viewset describe un `Turno` (`agenda__institucion`), no una `Agenda`.

Impacto funcional:

- La validacion puede degradar a "tiene trabajo en alguna institucion".
- Un usuario podria reservar en agenda ajena si conoce ids.
- Puede generarse un turno con agenda y ciudadano de instituciones distintas.

Recomendacion:

- Validar agenda y ciudadano contra la misma institucion y contra capacidades del usuario de forma explicita.

### 21. Subida de archivos no tiene alcance funcional ni permisos por dominio

Severidad: critica/alta.

Evidencia:

- `SubirArchivoView` acepta archivo de cualquier usuario autenticado.
- Devuelve URL absoluta.
- El archivo no queda asociado en ese momento a institucion, historia, caso o proposito.

Impacto funcional:

- Adjuntos clinicos pueden quedar accesibles si el storage es publico.
- No queda claro quien puede subir que tipo de documento ni bajo que institucion.

Recomendacion:

- Exigir permiso por uso.
- Guardar metadatos de institucion, usuario, proposito y objeto propietario.
- Usar storage privado o endpoint protegido.

Estado 2026-08-19: mitigado en Fase 7 para el circuito clinico. Las nuevas subidas exigen `institucion` existente y capacidad `historia_clinica`, se guardan bajo `uploads/<institucion>/...`, devuelven `ruta` interna y se descargan por endpoint protegido. En desarrollo se bloquea `/media/uploads/...` para no servir adjuntos clinicos por ruta estatica. Quedan abiertos metadatos completos de propietario/proposito, validacion MIME/tamanio, antivirus y tratamiento de archivos historicos ya servidos por `/media`.

### 22. Backup SQL comprimido dentro del arbol del backend

Severidad: critica de configuracion/privacidad.

Evidencia:

- Se detecto un archivo `.sql.gz` bajo una ruta temporal dentro de `backend/C.../Users/.../Temp/...`.
- `git ls-files` lo lista como archivo versionado.

Impacto funcional:

- Puede contener datos personales, clinicos, usuarios, hashes o configuracion sensible.
- Si esta en historial Git, borrarlo del working tree no alcanza.

Recomendacion:

- Retirarlo del repo.
- Limpiar historial si contiene datos sensibles.
- Agregar ignores para dumps y backups.
- Definir politica de backups fuera del repositorio.

Estado 2026-08-19: corregido en Bloque 1. El archivo `.sql.gz` fue eliminado del working tree y queda como baja en el diff. Se agregaron reglas `.gitignore` para dumps SQL, respaldos, temporales y rutas `backend/C*/Users/`. Si el archivo contenia datos reales, sigue pendiente limpiar historial Git remoto/local antes de publicar.

## Hallazgos altos adicionales

### 23. Agenda permite referencias incompatibles

Severidad: alta.

Evidencia:

- `AgendaSerializer.validate` valida modalidad y tipo/profesional, pero no todos los cruces institucionales.

Impacto funcional:

- Una agenda podria apuntar a area, profesional o flujo incompatible con la institucion.
- La llegada del paciente puede abrir casos en circuito incorrecto.

Recomendacion:

- Validar area, profesional y flujo contra la misma institucion.

### 24. Disponibilidad no valida vigencia ni duracion efectiva

Severidad: media/alta.

Evidencia:

- `DisponibilidadSerializer` valida horario y solapamiento, pero no `vigente_desde <= vigente_hasta`.
- Tampoco asegura que duracion/paso produzcan turnos dentro de la franja.

Impacto funcional:

- La agenda puede quedar configurada con franjas que no generan turnos o vigencias imposibles.

Recomendacion:

- Validar rango de vigencia y cantidad efectiva de turnos.

### 25. Campos de formulario pueden cambiar de formulario

Severidad: alta.

Evidencia:

- `CampoSerializer` expone `formulario`.

Impacto funcional:

- Valores historicos asociados al campo cambian de significado.
- Decisiones y reportes pueden leer datos bajo otro formulario.

Recomendacion:

- Hacer `formulario` read-only en update.
- Duplicar o migrar formalmente si se necesita reutilizar.

### 26. Permiso de puesto depende solo de grupo y no de membresia activa

Severidad: alta.

Evidencia:

- `PuestoDetalleView` valida `nodo.grupos.filter(miembros=user).exists()`.
- No se ve validacion directa de membresia activa o area vigente en ese punto.

Impacto funcional:

- Si una membresia se desactiva pero el usuario queda en el grupo, podria conservar acceso al puesto.
- Nodos sin grupo quedan con semantica ambigua en otras operaciones: abierto para cualquiera con capacidad.

Recomendacion:

- Usar una regla comun que cruce grupo, membresia activa, institucion y area.
- Definir explicitamente si un nodo sin grupo es abierto.

### 27. Usuario institucional puede modificar `is_staff`

Severidad: alta.

Evidencia:

- `UsuarioSerializer` expone `is_staff` como escribible.
- `is_superuser` es read-only, pero `is_staff` sigue siendo bandera de plataforma/admin Django.

Impacto funcional:

- Un admin institucional podria habilitar acceso staff fuera del gobierno de plataforma.

Recomendacion:

- Hacer `is_staff` editable solo por superusuario o capacidad de gobierno de plataforma.

### 28. Password se cambia dentro del serializer general de usuario

Severidad: media/alta.

Evidencia:

- `UsuarioSerializer` acepta `password` en create/update.

Impacto funcional:

- El reset de password queda mezclado con edicion general.
- Falta flujo explicito de auditoria, motivo y notificacion.

Recomendacion:

- Separar accion `reset-password`.
- Auditar quien resetea y a quien.

### 29. Farmacia sigue dependiendo de `trabajo`

Severidad: alta.

Evidencia:

- Movimientos y pedidos de farmacia usan capacidad `trabajo`.

Impacto funcional:

- Roles operativos no farmaceuticos pueden quedar habilitados para stock, ajustes, bajas o transferencias.

Recomendacion:

- Crear capacidad `farmacia_stock`.

### 30. Internacion/camas sigue dependiendo de `trabajo`

Severidad: alta.

Evidencia:

- Acciones operativas de camas dependen de `trabajo`.

Impacto funcional:

- Usuarios con trabajo general pueden cambiar estados o gestionar camas sin dominio especifico.

Recomendacion:

- Crear capacidad `internacion` y validar area/sector.

### 31. Red/traslados sigue dependiendo de `trabajo`

Severidad: alta.

Evidencia:

- `TrasladoViewSet` usa capacidad `trabajo`.

Impacto funcional:

- Operar traslados interinstitucionales queda mezclado con operacion general.

Recomendacion:

- Crear capacidad `traslados_red` y separar permisos de origen/destino.

Estado 2026-08-20: mitigado. Los traslados ya usan `traslados_red`; el ABM de redes sanitarias queda reservado a `gobierno_plataforma`, mientras los establecimientos conservan lectura de las redes donde participan.

### 32. Rutas frontend se protegen por institucion, no por capacidad

Severidad: alta UX/privacidad.

Evidencia:

- `Protected` valida sesion e institucion.
- El menu oculta por `puedeVer`, pero la ruta directa puede renderizar pantalla.

Impacto funcional:

- El usuario puede abrir una pantalla no autorizada por URL directa y recien despues recibir 403 o datos vacios.

Recomendacion:

- Agregar guard de ruta por capacidad.

### 33. Capacidades duplicadas en frontend y backend

Severidad: alta de mantenibilidad/permisos.

Evidencia:

- Backend define `ROL_CAPACIDADES`.
- Frontend define `CAPS_POR_ROL`.

Impacto funcional:

- Menu y API pueden divergir.
- Al dividir permisos por dominio, el riesgo crece.

Recomendacion:

- Exponer capacidades efectivas desde backend.

### 34. Institucion guardada puede quedar desalineada con el usuario actual

Severidad: media/alta.

Evidencia:

- `InstitutionContext` inicializa institucion desde `localStorage`.
- No se verifica inmediatamente si esa institucion pertenece al usuario actual.

Impacto funcional:

- En estaciones compartidas puede mostrarse contexto institucional incorrecto.
- El backend protege datos, pero la experiencia queda confusa y riesgosa.

Recomendacion:

- Al cambiar usuario, validar instituciones permitidas y limpiar la guardada si no corresponde.

### 35. Buscador global de pacientes no distingue padron de historia clinica

Severidad: media/alta.

Evidencia:

- `BuscadorPacientes` consulta ciudadanos desde la barra superior.
- La accion lleva a historia clinica.

Impacto funcional:

- Roles de admision pueden necesitar buscar pacientes sin tener permiso para historia completa.
- Roles sin registros ven un buscador que falla silenciosamente.

Recomendacion:

- Hacer que el buscador respete capacidades: padron administrativo vs historia clinica.

### 36. Bundle principal grande y sin code splitting por rutas

Severidad: media UX/performance.

Evidencia:

- `npm run build` advierte chunk principal mayor a 500 kB.
- No se encontraron `React.lazy`, `lazy(` ni `Suspense`.

Impacto funcional:

- Primera carga mas lenta en equipos o redes hospitalarias.
- Pantallas pesadas se cargan aunque el rol nunca las use.

Recomendacion:

- Aplicar lazy loading por rutas grandes.

### 37. Carpeta accidental `backend/backend`

Severidad: media configuracion.

Evidencia:

- Se detectaron archivos bajo `backend/backend/apps/agenda/management/...`.

Impacto funcional:

- Puede confundir imports, deploy, empaquetado o busquedas.

Recomendacion:

- Confirmar si tiene uso real y eliminarla si es accidental.

Estado 2026-08-19: corregido en Bloque 1. Los dos `__init__.py` vacios bajo `backend/backend/apps/agenda/management/...` fueron eliminados y `/backend/backend/` queda ignorado para evitar nuevas copias accidentales.

### 38. Pantalla publica por token no tiene politica de expiracion/rotacion

Severidad: media privacidad.

Evidencia:

- La pantalla publica de llamados se protege por token.

Impacto funcional:

- Si el token se filtra, el acceso puede quedar vigente hasta rotacion manual.
- Expone nombres/tickets de pacientes llamados.

Recomendacion:

- Definir politica de rotacion o vigencia de token.

## Observaciones actualizadas del barrido

- Camas/internacion, agenda, stock y red ya no deben considerarse "sin hallazgo fuerte": el barrido profundo detecto riesgos de permisos, scope o configuracion en esos modulos.
- FHIR sigue sin hallazgo logico puntual en esta pasada, pero debe conservar pruebas de permisos equivalentes y auditoria.
- La UI visual tiene buena base de tokens, skeletons, foco visible y modo oscuro; los errores detectados son principalmente de autorizacion, navegacion, rendimiento inicial y claridad de permisos.

## Avance de implementacion - Fase 3 validadores de configuracion

Fecha: 2026-08-19.

Estado: implementado y testeado en los modulos alcanzados por la fase.

Hallazgos cerrados o mitigados:

- **Hallazgo 3 - Conexiones de flujo entre versiones.** `ConexionSerializer` valida que `origen.version_id` y `destino.version_id` coincidan con `conexion.version_id`. La version queda read-only en update.
- **Hallazgo 4 - Nodos con formulario o grupos ajenos.** `NodoSerializer` valida formulario y grupos contra la institucion del flujo. La version del nodo queda read-only en update.
- **Hallazgo 5 - Flujo con area/subarea ajena.** `FlujoSerializer` valida area y subarea contra la institucion del flujo. Institucion, area y subarea quedan read-only en update.
- **Hallazgo 18 - FKs de alcance movibles por update generico.** Se congelaron FKs de scope en agenda, disponibilidad, bloqueo, flujo, nodo, conexion, campo, formulario, cama, area, subarea, box, grupo, deposito, insumo, lote, pedido, membresia y legajo profesional.
- **Hallazgo 20 - Reserva de turno con permiso/objeto incompatible.** `TurnoViewSet.create` valida capacidad `turnos` contra la institucion real de la agenda y el motor rechaza pacientes de otra institucion.
- **Hallazgo 23 - Agenda con referencias incompatibles.** `AgendaSerializer` valida area, profesional con membresia activa y flujo contra la misma institucion; una agenda profesional requiere profesional asignado.
- **Hallazgo 24 - Disponibilidad con vigencia/duracion incoherente.** `DisponibilidadSerializer` valida duracion positiva y vigencia coherente.
- **Hallazgo 25 - Campo movible entre formularios.** `Campo.formulario` queda read-only en update.
- **Hallazgo 27 - `is_staff` editable por API institucional.** `UsuarioSerializer` marca `is_staff` como read-only.
- **Riesgo de configuracion en camas.** `CamaSerializer` valida que la subarea/sector pertenezca al area; area y subarea quedan read-only en update.
- **Riesgo de configuracion en depositos.** `DepositoSerializer` valida que el area pertenezca a la institucion; institucion y area quedan read-only en update.
- **Riesgo de membresias con areas ajenas.** `MembresiaSerializer` valida que todas las areas pertenezcan a la institucion; usuario e institucion quedan read-only en update.

Pruebas ejecutadas:

- `.venv\\Scripts\\python.exe manage.py test apps.agenda` - OK, 138 tests, 1 skipped.
- `.venv\\Scripts\\python.exe manage.py test apps.flujos` - OK, 46 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.formularios` - OK, 30 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.accounts apps.instituciones.test_camas apps.farmacia.tests_api` - OK, 63 tests.

Pendientes relacionados:

- Validar ids internos dentro de `Nodo.config` para derivaciones, integraciones y guardado en campos. El caso mas sensible (`area_destino_id` y `flujo_destino_id`) sigue ligado al motor de casos y a los hallazgos 1, 2, 7 y 8.
- Definir acciones explicitas de mudanza si el negocio necesita mover agendas, camas, depositos, flujos, campos o nodos ya creados.
- Completar politica de gobierno de plataforma, backups y archivos clinicos fuera de esta fase.

## Avance de implementacion - Fase 4 UX, permisos frontend y performance

Fecha: 2026-08-19.

Estado: implementado y verificado con build/auditoria frontend.

Hallazgos cerrados o mitigados:

- **Hallazgo 32 - Rutas frontend protegidas solo por institucion.** Las rutas protegidas declaran capacidad requerida y muestran acceso denegado si el usuario no la tiene, sin montar la pantalla funcional.
- **Hallazgo 33 - Capacidades duplicadas en frontend/backend.** El frontend consume capacidades efectivas de `/api/usuarios/me/`; la matriz local queda solo para la simulacion del super admin.
- **Hallazgo 34 - Institucion guardada desalineada.** `InstitutionContext` limpia la institucion de `localStorage` si no existe en las capacidades del usuario actual, evitando contexto visual heredado en estaciones compartidas.
- **Hallazgo 35 - Buscador global de pacientes.** La topbar no muestra ni ejecuta el buscador clinico sin `historia_clinica`.
- **Hallazgo 36 - Bundle principal grande.** Se agrego code splitting por rutas con `React.lazy`/`Suspense`. El chunk principal quedo en ~300.8 kB, por debajo del umbral de 500 kB; pantallas pesadas quedaron en chunks separados.
- **Super admin / ver como rol.** El selector `Ver como` quedo visible en el `Shell` cuando el super admin esta dentro de una institucion.

Checks ejecutados:

- `npm run build` - OK.
- `npm run auditar` - OK, 233 clases revisadas, sin huerfanas ni colisiones.

Pendientes relacionados:

- Crear una ficha administrativa de padron para usuarios con `padron_admision` sin `historia_clinica`. Cuando exista, el buscador superior podria degradar a busqueda administrativa en vez de ocultarse.
- Agregar prueba E2E especifica de estacion compartida: usuario A deja institucion guardada, usuario B inicia sesion y el contexto se limpia si no corresponde.

## Avance de implementacion - Fase 5 derivaciones, subprocesos y casos activos

Fecha: 2026-08-19.

Estado: implementado y testeado en la superficie funcional alcanzada.

Hallazgos cerrados o mitigados:

- **Hallazgo 1 - Derivaciones internas con area/flujo de otra institucion.** El motor valida `area_destino_id` y `flujo_destino_id` dentro de `Nodo.config` al ejecutar el nodo `Derivar`. Si el area no pertenece al caso, si el flujo no pertenece a la institucion, si no esta publicado o si no pertenece al area derivada, la transaccion falla sin crear eventos ni casos derivados parciales.
- **Hallazgo 2 - Estudio derivado/interconsulta a area ajena.** `solicitar_estudio_derivado` y `solicitar_interconsulta` usan `version_receptora_para_area(area, institucion=caso.institucion)`, por lo que rechazan areas de otra institucion y no dejan estudios/eventos parciales por el `atomic`.
- **Hallazgos 7 y 8 - Flujo receptor elegido por orden tecnico.** Casos internos y traslados de red dejan de elegir por `-flujo_id`. El area receptora debe tener exactamente un flujo publicado cuyo Inicio acepte `derivado` o `ambos`. Si todos son `manual` o hay mas de un receptor, se informa error de configuracion.
- **Hallazgo 6 - Subprocesos cancelados bloquean retorno.** `_retornar_al_origen` ahora excluye `Caso.ESTADOS_FINALIZADOS` (`cerrado`, `cancelado`) cuando decide si quedan subprocesos pendientes.
- **Hallazgos 10 y 13 - Cancelados contados como activos.** Se agrego `Caso.ESTADOS_FINALIZADOS` y se aplica en listado/detalle de flujos, archivo de version publicada y metricas rapidas de institucion.
- **Traslados de red.** `aceptar` crea el caso destino solo con un flujo receptor funcionalmente habilitado, manteniendo la pertenencia del area al establecimiento destino.

Pruebas ejecutadas:

- `.venv\\Scripts\\python.exe manage.py test apps.casos.tests.EstudioDerivadoTests apps.casos.tests.DerivacionEntreFlujosTests` - OK, 10 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.red.tests.RespuestaTests` - OK, 13 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.flujos.tests.ArchivarFlujoTests apps.flujos.tests.VolumenDelDisenoTests apps.instituciones.test_camas.MetricasInstitucionTests` - OK, 11 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.casos.tests apps.casos.tests_api` - OK, 137 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.red.tests.RespuestaTests apps.red.tests.SolicitudTests apps.red.tests.DestinosTests` - OK, 23 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.instituciones.test_camas` - OK, 12 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.flujos` - OK, 47 tests.

Notas de verificacion:

- La corrida monolitica `apps.casos apps.flujos apps.red apps.instituciones.test_camas` excedio el timeout disponible; tambien excedieron timeout las corridas completas separadas de `apps.casos` y `apps.red` en paralelo. Se reemplazaron por lotes focalizados, archivo completo de casos/API, flujos completo, instituciones/camas completo y clases principales de red.

Pendientes relacionados:

- Revisar otros IDs embebidos en `Nodo.config` que no sean derivacion entre areas/flujos, especialmente integraciones externas, `guardar_en` y politicas de endpoint remoto.
- Definir desde producto como se administra la ambiguedad de receptores: hoy el motor falla y exige dejar un unico receptor funcional por area.

## Avance de implementacion - Fase 6 farmacia, entregas parciales y pedidos

Fecha: 2026-08-19.

Estado: implementado y testeado.

Hallazgos cerrados o mitigados:

- **Hallazgo 11 - Entrega parcial de farmacia queda cerrada como entregada.** `Pedido.Estado` incorpora `parcial`; `entregar_pedido` marca `parcial` cuando queda faltante y `entregado` solo cuando todas las lineas alcanzan `pedido_cant`.
- **Cantidad acumulada.** La entrega se valida contra `pedido_cant - entregado`, por lo que una segunda entrega no puede superar el pendiente real de la linea.
- **Entrega vacia.** Una entrega sin cantidades positivas devuelve error y no cambia el estado.
- **Copia vieja/doble envio.** El motor compara el estado de la copia recibida con la fila bloqueada; si cambio, corta la operacion y pide recargar.
- **Cierre de pedido.** `resuelto` se setea al completar todas las lineas o al rechazar el pedido; en estado `parcial` queda `None` porque el pedido sigue abierto.

Pruebas ejecutadas:

- `.venv\\Scripts\\python.exe manage.py test apps.farmacia.tests.PedidoTests apps.farmacia.tests_api.FarmaciaAPITests` - OK, 31 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.farmacia` - OK, 80 tests.

Pendientes relacionados:

- Definir si el estado `preparado` se usara en una etapa futura de picking/preparacion fisica; esta fase no agrega flujo de preparacion, solo corrige deuda de entrega parcial.

## Avance de implementacion - Fase 7 archivos clinicos y privacidad

Fecha: 2026-08-19.

Estado: implementado y testeado.

Hallazgos cerrados o mitigados:

- **Hallazgo 21 - Subida de archivos sin alcance funcional ni permisos por dominio.** `SubirArchivoView` exige usuario autenticado, `institucion` y capacidad `historia_clinica` en esa institucion.
- **Institucion inexistente.** La subida rechaza ids de institucion inexistentes antes de crear rutas `uploads/<id>/...`.
- **URL publica de media.** Las nuevas subidas ya no devuelven `/media/uploads/...`; devuelven `ruta` interna y URL `/api/archivos/descargar/uploads/<institucion>/...`.
- **Servidor estatico de desarrollo.** `/media/uploads/...` devuelve 404, por lo que el archivo clinico nuevo solo sale por el endpoint protegido.
- **Descarga sin control institucional.** `DescargarArchivoView` valida que la ruta pertenezca a `uploads/<institucion>/...` y exige `historia_clinica` en esa institucion antes de servir el binario.
- **Frontend de casos.** Los campos archivo y los adjuntos de estudio envian la institucion del caso; se persiste la `ruta` protegida en lugar de perder la referencia guardando solo el nombre.
- **Frontend de historia clinica.** Los estudios con referencia interna se descargan por `fetch` con `Authorization`; los textos heredados se siguen mostrando como referencia simple.

Pruebas ejecutadas:

- `.venv\\Scripts\\python.exe manage.py test apps.casos.tests_api.SubirArchivoTest` - OK, 8 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.casos.tests_api` - OK, 49 tests.
- `npm run build` - OK.
- `npm run auditar` - OK, 234 clases revisadas.

Pendientes relacionados:

- Definir modelo persistente de archivo clinico con `institucion`, usuario, proposito y objeto propietario.
- Agregar validacion MIME/tamanio por tipo documental y antivirus.
- Revisar archivos historicos ya generados bajo `/media` y decidir migracion u ocultamiento fuera del servidor publico de desarrollo.

## Avance de implementacion - Bloque 1 higiene de repositorio y respaldos

Fecha: 2026-08-19.

Estado: implementado y revisado.

Hallazgos cerrados o mitigados:

- **Hallazgo 22 - Backup SQL comprimido dentro del arbol del backend.** El dump `backend/C.../Users/.../Temp/.../cauce-20260814-133512.sql.gz` fue eliminado del working tree y queda como baja en el diff.
- **Hallazgo 37 - Carpeta accidental `backend/backend`.** Se eliminaron los archivos vacios trackeados bajo esa copia accidental.
- **Prevencion de recaidas.** `.gitignore` ahora excluye dumps SQL, backups, temporales, `backend/C*/Users/` y `/backend/backend/`.

Review del bloque:

- `git check-ignore -v` confirma cobertura para `.sql`, `.sql.gz`, `.dump`, `.backup`, `.bak`, `.sqlite3.gz` y rutas `backend/C*/Users/`.
- `git diff --check` no reporta errores; solo avisos CRLF normales del entorno Windows.
- Nota: `git ls-files` sigue listando archivos eliminados hasta que se haga commit; despues del commit de baja ya no apareceran en el arbol versionado.

Pendientes relacionados:

- Si el dump contenia datos reales, limpiar historial Git antes de compartir/publicar el repositorio.
- Definir destino externo de respaldos operativos y responsables de restauracion.

## Avance de implementacion - Bloque 2 gobierno estatal/plataforma

Fecha: 2026-08-20.

Estado: implementado y revisado.

Hallazgos cerrados o mitigados:

- **Hallazgo 9 - Institucionales podian crear instituciones nuevas.** La escritura de instituciones exige `gobierno_plataforma`; un admin institucional ya no crea ni edita establecimientos desde su permiso local.
- **Gobierno de redes sanitarias.** El ABM de redes queda reservado a plataforma; los hospitales siguen viendo las redes donde participan.
- **Roles estatales explicitos.** `Membresia.Rol` incorpora `plataforma`, `auditor` y `reportes`; solo superusuario o autoridad de plataforma puede asignar `plataforma`/`auditor`.
- **Directorio estatal.** La autoridad de plataforma puede listar usuarios, crear usuarios sin membresia institucional inmediata y asignar membresias de alta institucional.
- **Auditoria estatal.** `auditor` y `plataforma` tienen alcance global sobre registros de acceso clinico, sin permisos clinicos u operativos adicionales.
- **Frontend de plataforma.** El landing envia a directorio a usuarios con `gobierno_plataforma`; el contexto permite que esa capacidad global no dependa de estar parado en el mismo efector de su membresia.

Review del bloque:

- `.venv\\Scripts\\python.exe -m py_compile apps/common.py apps/accounts/views.py apps/accounts/serializers.py apps/instituciones/views.py apps/red/views.py apps/auditoria/views.py` - OK.
- `.venv\\Scripts\\python.exe manage.py test apps.accounts.tests.GobiernoPlataformaTests apps.instituciones.tests.GobiernoPlataformaInstitucionTests apps.red.tests_api.TrasladosAPITests.test_un_admin_institucional_no_crea_redes_sanitarias apps.red.tests_api.TrasladosAPITests.test_plataforma_crea_y_ve_todas_las_redes apps.auditoria.tests.QuienLoPuedeVerTests.test_auditor_y_plataforma_tienen_alcance_estatal` - OK, 13 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.accounts.tests` - OK, 25 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.instituciones.tests` - OK, 7 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.red.tests_api` - OK, 24 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.auditoria.tests` - OK, 33 tests.
- `.venv\\Scripts\\python.exe manage.py makemigrations --check --dry-run` - OK, sin cambios pendientes.
- `git diff --check` - OK; solo avisos CRLF normales del entorno Windows.
- `npm run build` - OK.
- `npm run auditar` - OK, 234 clases revisadas.

Pendientes relacionados:

- Definir pantallas reales de `reportes` para indicadores agregados no nominales.
- Decidir si habra niveles regional/provincial dentro de `gobierno_plataforma` o si alcanza con alcance estatal unico.
- El cambio agrega una migracion de choices de rol; debe aplicarse antes de usar los nuevos roles en datos reales.

## Avance de implementacion - Bloque 3 firma profesional configurable por nodo

Fecha: 2026-08-20.

Estado: implementado y revisado.

Hallazgos cerrados o mitigados:

- **Firma profesional por configuracion del nodo.** Los nodos de atencion pueden declarar `config.firma_roles` con los roles habilitados para firmar y `config.firma_matricula` para exigir o no matricula.
- **Compatibilidad hacia atras.** Si la configuracion no existe, viene vacia o llega rota en tiempo de ejecucion, el sistema vuelve al criterio historico: firma de `medico` con matricula.
- **Validacion previa a publicar/ensayar.** `validar_version` informa error cuando un nodo declara roles de firma desconocidos, evitando que una mala configuracion quede oculta hasta la atencion.
- **Control asistencial efectivo.** El motor sigue validando rol, pertenencia al area del caso y matricula cuando corresponde; el superusuario conserva bypass tecnico para soporte.
- **Editor visual.** El disenador de flujos ya expone seleccion de roles firmantes y switch de exigencia de matricula para nodos de atencion.

Review del bloque:

- `.venv\\Scripts\\python.exe -m py_compile apps/casos/motor.py apps/casos/tests.py` - OK.
- `.venv\\Scripts\\python.exe manage.py test apps.casos.tests.FirmaConfigurableTests` - OK, 11 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.flujos.tests.EnsayoTests.test_un_limite_del_motor_se_informa_con_el_nodo_donde_pasa apps.flujos.tests.EnsayoTests.test_una_atencion_con_fila_pide_llamar_antes_de_atender` - OK, 2 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.casos.tests` - OK, 95 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.flujos.tests` - OK, 47 tests.

Pendientes relacionados:

- Definir si se agregaran otros perfiles profesionales firmantes mas alla de `medico`, `enfermeria`, `administrativo` y `jefe_area`.
- Si el producto requiere firma digital legal/certificado, modelarla como una capa separada de esta autorizacion funcional de firma.

## Avance de implementacion - Bloque 4 padron administrativo separado de historia clinica

Fecha: 2026-08-20.

Estado: implementado y revisado.

Hallazgos cerrados o mitigados:

- **Hallazgo 35 - Buscador global no distinguia padron de historia clinica.** El buscador superior ahora funciona con `historia_clinica` o con `padron_admision`; si el usuario no tiene historia, navega a `/padron/<id>` y no a la historia clinica.
- **Ficha administrativa de padron.** Se agregaron `/padron` y `/padron/:id` como superficie separada para admision: identidad, documento, cobertura, domicilio y consentimiento.
- **Historia clinica protegida.** La ficha de padron no renderiza evolucion, alergias, estudios ni recetas; el boton de historia solo aparece si la persona tiene `historia_clinica`.
- **CSV por permiso.** La exportacion de `CiudadanoViewSet` usa columnas administrativas cuando el usuario no tiene `historia_clinica`, sin columnas de condiciones, alergias, entradas ni ultima atencion.
- **FK de alcance.** `Ciudadano.institucion` ya no se puede mover por PATCH comun; una migracion real de padron queda fuera como accion funcional explicita.

Review del bloque:

- `.venv\\Scripts\\python.exe -m py_compile apps/common.py apps/registros/views.py apps/registros/serializers.py apps/registros/tests_api.py` - OK.
- `.venv\\Scripts\\python.exe manage.py test apps.registros.tests_api.PermisosGranularesRegistrosTests` - OK, 5 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.registros.tests_api` - OK, 43 tests.
- `.venv\\Scripts\\python.exe manage.py makemigrations --check --dry-run` - OK, sin cambios pendientes.
- `npm run build` - OK.
- `npm run auditar` - OK, 235 clases revisadas.
- `git diff --check` - OK; solo avisos CRLF normales del entorno Windows.

Pendientes relacionados:

- Si el negocio necesita fusionar duplicados o mover pacientes entre instituciones, crear una accion auditada con motivo y validacion de origen/destino.
- Evaluar si `registros` legacy puede retirarse totalmente cuando todas las rutas consuman capacidades granulares.

## Avance de implementacion - Bloque 5 metadata y validaciones de archivos clinicos

Fecha: 2026-08-20.

Estado: implementado y revisado.

Hallazgos cerrados o mitigados:

- **Metadata persistente.** Se agrego `ArchivoClinico` con institucion, ruta, nombre original, content type, tamano, SHA-256, proposito, objeto propietario opcional, usuario que subio y fecha.
- **Validacion de adjuntos.** `POST /api/archivos/` rechaza archivos vacios, demasiado grandes, tipos no permitidos, extension incompatible y contenido que no coincide con el tipo declarado.
- **Tipos permitidos.** Se admiten PDF, JPEG, PNG, WebP y texto plano. El maximo por defecto es 10 MB y puede configurarse con `ARCHIVO_CLINICO_MAX_BYTES`.
- **Descarga con metadata.** `GET /api/archivos/descargar/...` usa la metadata cuando existe para resolver institucion, nombre original y content type; conserva fallback por ruta para archivos historicos.
- **Trazabilidad.** La respuesta de subida devuelve `content_type`, `tamano` y `sha256`, ademas de `nombre`, `ruta` y `url` protegida.

Review del bloque:

- `.venv\\Scripts\\python.exe -m py_compile apps/common.py apps/registros/models.py apps/registros/admin.py apps/casos/tests_api.py` - OK.
- `.venv\\Scripts\\python.exe manage.py test apps.casos.tests_api.SubirArchivoTest` - OK, 11 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.casos.tests_api` - OK, 52 tests.
- `.venv\\Scripts\\python.exe manage.py makemigrations --check --dry-run` - OK, sin cambios pendientes.
- `git diff --check` - OK; solo avisos CRLF normales del entorno Windows.

Pendientes relacionados:

- Integrar antivirus/escaneo asincronico si el entorno productivo lo requiere.
- Migrar u ocultar archivos historicos sin metadata que ya existan bajo `/media`.
- Definir politica de retencion y purga para archivos clinicos segun normativa local.

## Avance de implementacion - Bloque 6 IDs embebidos en Nodo.config e integraciones

Fecha: 2026-08-20.

Estado: implementado y revisado.

Hallazgos cerrados o mitigados:

- **Integraciones con `guardar_en` invalido.** `validar_version` ahora rechaza integraciones que guardan en un campo inexistente, mal tipado o de otra institucion.
- **Disponibilidad de campos real.** Una decision solo considera disponible un campo cargado por formularios del flujo o por una integracion valida de la misma institucion.
- **Defensa en ejecucion.** Flujos historicos ya publicados con `guardar_en` roto no generan `ValorCampo` contra FKs invalidas; el motor registra falla de integracion.
- **Prioridad por formulario.** `prioridad_campo` debe pertenecer al formulario del nodo y ser `seleccion_unica`; si no, la version muestra error antes de publicar/ensayar.

Review del bloque:

- `.venv\\Scripts\\python.exe -m py_compile apps/casos/motor.py apps/casos/test_validacion_y_ensayo.py` - OK.
- `.venv\\Scripts\\python.exe manage.py test apps.casos.test_validacion_y_ensayo` - OK, 14 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.flujos.tests` - OK, 47 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.casos.tests apps.casos.test_validacion_y_ensayo` - OK, 109 tests.
- `.venv\\Scripts\\python.exe manage.py makemigrations --check --dry-run` - OK, sin cambios pendientes.
- `git diff --check` - OK; solo avisos CRLF normales del entorno Windows.

Pendientes relacionados:

- Si se agregan nuevos tipos de nodo con IDs en `config`, deben declararse en `validar_version` con la misma regla: existencia, institucion y compatibilidad funcional.
- Evaluar si `objeto_tipo/objeto_id` de archivos clinicos debe validarse contra propietarios concretos cuando el upload empiece a recibir ese dato desde la UI.

## Avance de implementacion - Bloque 7 agenda, bloqueos y reserva de turnos

Fecha: 2026-08-20.

Estado: implementado y revisado.

Hallazgos cerrados o mitigados:

- **Bloqueos parciales de agenda.** Los bloqueos ahora se evaluan por solape entre el rango bloqueado y la duracion completa del turno, no solo por la hora de inicio.
- **Grilla coherente.** `horarios_del_dia` oculta horarios libres que solapan un bloqueo parcial y mantiene visibles los turnos ya dados en horarios bloqueados para que el mostrador pueda reprogramarlos o avisar.
- **Lista de turnos afectados.** `turnos_en_rango` devuelve turnos vigentes que solapan el bloqueo aunque hayan empezado antes del rango bloqueado.
- **Reserva/reprogramacion.** `_valida_horario` rechaza reservas que empiezan antes del bloqueo pero terminan dentro del rango bloqueado.
- **Origen de turno controlado.** El motor rechaza valores de `origen` fuera de `mostrador`, `telefono` o `derivacion`, evitando indicadores de demanda con categorias libres.
- **Parsing de sobreturno por API.** `POST /api/turnos/` interpreta correctamente `sobreturno=false` cuando llega como texto de formulario y rechaza valores ambiguos.

Review del bloque:

- `.venv\\Scripts\\python.exe -m py_compile apps/agenda/models.py apps/agenda/motor.py apps/agenda/views.py apps/agenda/tests.py apps/agenda/tests_api.py` - OK.
- `.venv\\Scripts\\python.exe manage.py test apps.agenda.tests.DisponibilidadTests apps.agenda.tests.ReservaTests apps.agenda.tests_api.AgendaAPITests.test_bloquear_parcial_devuelve_los_turnos_que_solapan apps.agenda.tests_api.AgendaAPITests.test_sobreturno_false_en_texto_no_se_toma_como_true apps.agenda.tests_api.AgendaAPITests.test_no_guarda_turno_con_origen_invalido` - OK, 18 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.agenda` - OK, 146 tests, 1 omitido esperado.
- `.venv\\Scripts\\python.exe manage.py makemigrations --check --dry-run` - OK, sin cambios pendientes.

Pendientes relacionados:

- Si se agregan turnos de duracion excepcionalmente larga fuera del modelo de agenda diaria, revisar la ventana de busqueda de turnos afectados por bloqueo.
- Definir si `origen` debe ampliarse con canales digitales formales; si se agrega, debe entrar como choice y no como texto libre.

## Avance de implementacion - Bloque 8 puestos, grupos y membresia activa

Fecha: 2026-08-20.

Estado: implementado y revisado.

Hallazgos cerrados o mitigados:

- **Regla operativa comun de grupos.** Se agrego `grupos_operativos_de(usuario, institucion)` para no depender de la relacion directa `Usuario.grupos`, que puede quedar vieja cuando se desactiva una membresia o un grupo.
- **Tomar, llamar y operar casos.** `usuario_puede_tomar` exige usuario activo, grupo activo, area activa, membresia activa y coincidencia entre institucion de la membresia e institucion real del area.
- **Mis tareas y puestos.** `MisTareasView` y `PuestoDetalleView` ahora exigen autenticacion, capacidad `casos_operar` en la institucion y pertenencia operativa al grupo responsable.
- **Notificaciones a equipos.** Los avisos por grupo solo llegan a usuarios activos con membresia activa en el area/institucion del grupo.
- **Configuracion de grupos.** `GrupoSerializer` rechaza miembros sin membresia activa en el area, oculta integrantes no operativos y los contadores de staff solo cuentan usuarios activos con membresia activa.
- **Diseno de flujos.** `NodoSerializer` rechaza grupos inactivos o de areas inactivas; `validar_version` impide publicar versiones con grupos responsables inactivos. Los detalles de responsables no muestran grupos inactivos heredados.
- **Datos inconsistentes por carga directa.** El motor cruza la institucion de la membresia con la institucion del area, evitando que una membresia mal vinculada desde otra institucion habilite operar un puesto.

Review del bloque:

- `.venv\\Scripts\\python.exe -m py_compile apps/casos/motor.py apps/casos/serializers.py apps/casos/views.py apps/casos/tests.py apps/casos/tests_api.py apps/instituciones/serializers.py apps/instituciones/tests.py apps/flujos/serializers.py apps/flujos/tests.py apps/casos/test_validacion_y_ensayo.py` - OK.
- `.venv\\Scripts\\python.exe manage.py test apps.casos.tests.ResponsabilidadTests apps.casos.tests.NotificacionNodoTests apps.casos.tests.TiemposTests apps.casos.tests_api.PuestosConMembresiaActivaTests apps.instituciones.tests.GruposOperativosTests apps.flujos.tests.NodoGruposTests apps.casos.test_validacion_y_ensayo.GruposResponsablesTests` - OK, 32 tests.
- `.venv\\Scripts\\python.exe manage.py test apps.casos.tests apps.casos.tests_api apps.casos.test_validacion_y_ensayo apps.instituciones.tests apps.flujos.tests` - OK, 229 tests.

Pendientes relacionados:

- Definir una accion administrativa auditada para limpiar miembros historicos de grupos cuando se da de baja una membresia.
- Revisar reportes historicos si producto necesita diferenciar "miembro historico del grupo" de "operador vigente".

## Modulos sin hallazgo logico fuerte luego del barrido ampliado

- FHIR no mostro un bug funcional puntual en esta pasada, pero debe conservar pruebas de permisos equivalentes y auditoria de lectura clinica.
- Monitoreo/healthcheck no mostro un bug logico puntual en esta pasada.
- Los demas modulos tienen al menos un hallazgo de permisos, configuracion, alcance institucional o UX documentado arriba.

## Propuesta de orden de correccion

1. Cerrar escritura generica de `Caso`, `ValorCampo`, `EventoCaso` e `ItemFila`.
2. Retirar dump SQL del repositorio y definir politica de backups.
3. Blindar integridad institucional en motor de casos, derivaciones y agenda.
4. Validar serializers del diseñador: Flujo, Version, Nodo, Conexion, Formulario y Campo.
5. Hacer read-only o revalidar FKs de scope institucional en update.
6. Dividir capacidades sanitarias por dominio.
7. Corregir reserva de turnos con agenda/paciente/institucion coherentes.
8. Separar padron administrativo de historia clinica.
9. Endurecer subida y descarga de archivos clinicos. Cerrado/mitigado en Fase 7 para el circuito clinico.
10. Separar permisos de farmacia, internacion y red.
11. Corregir retorno de subprocesos cancelados.
12. Definir flujo receptor explicito para traslados, estudios e interconsultas.
13. Normalizar "caso activo" excluyendo cancelados.
14. Decidir semantica de entrega parcial en farmacia. Cerrado en Fase 6.
15. Agregar guards de ruta por capacidad y capacidades efectivas desde backend.
16. Corregir institucion guardada en frontend y buscador global de pacientes.
17. Aplicar code splitting en pantallas pesadas.

## Pruebas recomendadas

- Configurar nodo `derivar` con `area_destino_id` de otra institucion: debe fallar al guardar o ejecutar.
- Configurar nodo `derivar` con `flujo_destino_id` de otra institucion: debe fallar.
- Solicitar interconsulta a area de otra institucion: debe devolver 400.
- Crear conexion con `version=A`, `origen=A`, `destino=B`: debe devolver 400.
- Crear nodo con formulario/grupo de otra institucion: debe devolver 400.
- Cerrar el ultimo subproceso cuando otro fue cancelado: el caso padre debe reactivarse.
- Archivar flujo con solo casos cancelados: debe permitirse si no hay casos activos reales.
- Entrega parcial de pedido: cubierto en Fase 6 con estado `parcial` y reentrega hasta completar.
- PATCH directo de caso intentando cambiar `estado`, `nodo_actual`, `area_actual` o `asignado_a`: debe fallar o ignorarse.
- Crear caso con version no publicada: debe fallar.
- Crear caso con ciudadano de otra institucion: debe fallar.
- POST/PATCH/DELETE directo de valores de formulario: debe fallar.
- Avanzar caso con `campo_id` ajeno al formulario del nodo: debe fallar.
- POST/PATCH/DELETE directo de eventos de caso: debe fallar.
- POST directo de item de fila: debe fallar.
- Reservar turno con agenda de otra institucion: debe fallar.
- Reservar turno con ciudadano de otra institucion: debe fallar.
- Usuario sin permiso clinico no debe abrir historia por ruta directa ni disparar consultas sensibles.
- Admin institucional no debe poder activar `is_staff`.
- Reset de password debe quedar auditado.
- Subida/descarga de archivo clinico debe exigir permiso e institucion. Cubierto en Fase 7 para nuevas subidas clinicas.
- `git ls-files` no debe listar dumps SQL ni carpetas duplicadas accidentales.
- Build frontend debe conservar auditor de clases limpio y chunks dentro del limite definido.
