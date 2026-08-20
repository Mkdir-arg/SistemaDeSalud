# Barrido completo de logica, configuracion y UI/UX

Fecha: 2026-08-18  
Estado: analisis previo a desarrollo  
Base revisada: documentacion funcional existente, routers, viewsets, serializers, motores, permisos, contexto de roles y frontend React.

## 1. Resumen ejecutivo

El sistema ya tiene varias decisiones correctas para salud: motores de negocio para casos, agenda, farmacia y red; historia clinica con sellado; lectura clinica auditada; estados vacios y errores consistentes en frontend; tokens visuales semanticamente nombrados; foco visible y soporte de modo oscuro.

El riesgo principal detectado en esta pasada no esta en una pantalla puntual, sino en la diferencia entre:

- lo que el producto espera que pase por motores y acciones controladas;
- lo que algunos endpoints genericos todavia permiten escribir directo.

En salud, eso es critico porque un dato operativo no es solo una fila: cambia responsabilidad sanitaria, trazabilidad, historia legal, stock, cama, agenda o privacidad.

Prioridad recomendada:

1. Cerrar escrituras genericas de casos, valores de formulario, eventos e items de fila.
2. Separar capacidades por dominio, porque `trabajo` y `registros` hoy son demasiado amplias.
3. Validar en update los FKs que definen institucion o area, no solo al crear.
4. Resolver configuracion sensible: backup SQL dentro del repositorio y carpeta duplicada `backend/backend`.
5. Agregar guards de ruta y capacidades del servidor en frontend.
6. Mejorar performance percibida con code splitting de pantallas pesadas.

## 2. Metodologia ejecutada

Se reviso:

- `backend/apps/common.py`: permisos, capacidades, scoping institucional y subida de archivos.
- `backend/apps/casos`: viewsets, serializers y motor de avance.
- `backend/apps/agenda`: reserva, serializers, disponibilidad y turnos.
- `backend/apps/registros`: historia clinica, recetas, estudios, consentimientos y padron.
- `backend/apps/farmacia`: stock, movimientos y pedidos.
- `backend/apps/red`: traslados entre instituciones.
- `backend/apps/instituciones`, `flujos`, `formularios`, `accounts`.
- `frontend/src/App.jsx`, `InstitutionContext.jsx`, `Shell.jsx`, pantallas principales y tokens de diseno.

Validaciones corridas:

- `npm run build`: correcto. Advertencia: bundle principal `index-BNohJR9I.js` de 782.22 kB, mayor al umbral de 500 kB.
- `npm run auditar`: correcto despues del build. Resultado: 233 clases revisadas, sin clases huerfanas ni colisiones.
- Busqueda de lazy imports: no se encontraron `React.lazy`, `lazy(` ni `Suspense`.
- Se detecto con `git ls-files` un dump SQL comprimido versionado bajo `backend/C.../cauce-20260814-133512.sql.gz`.

## 3. Hallazgos criticos

### 3.1. `CasoViewSet` permite escritura generica que evita el motor

Severidad: critica.

Evidencia:

- `backend/apps/casos/views.py`: `CasoViewSet(BaseModelViewSet)` usa CRUD generico.
- `backend/apps/casos/serializers.py`: `CasoSerializer` expone como escribibles `institucion`, `version`, `estado`, `prioridad`, `nodo_actual`, `area_actual`, `asignado_a`, `origen` y `estudio`.
- `perform_create` solo hace `serializer.save()` y `motor.asegurar_historia(caso)`.

Impacto:

- Un usuario con capacidad `trabajo` puede crear un caso con version borrador, archivada o de otra institucion.
- Puede cambiar estado por PATCH sin pasar por `iniciar`, `avanzar`, `cancelar`, `priorizar`, `derivar`, `cama` o `traslado`.
- Puede mover el caso a un nodo o area que no corresponde al flujo.
- Se rompen eventos, tiempos de paso, responsabilidad del equipo, bandejas y auditoria operativa.

Solucion logica:

- Convertir `CasoViewSet` en endpoint de lectura mas acciones, o limitar escritura generica a un serializer de alta minima.
- Campos escribibles al crear: `institucion`, `version`, `ciudadano`, `prioridad` y, si aplica, un motivo/origen controlado.
- Campos read-only siempre: `estado`, `nodo_actual`, `area_actual`, `asignado_a`, `origen`, `estudio`.
- Validar en create:
  - `version.estado == publicada`.
  - `version.flujo.institucion_id == institucion_id`.
  - `ciudadano.institucion_id == institucion_id`.
  - el nodo Inicio permite origen manual si viene de alta manual.
- Toda mutacion posterior debe pasar por acciones del motor.

Pruebas esperadas:

- POST `/casos/` con version borrador devuelve 400.
- PATCH `/casos/{id}/` intentando cambiar `estado` o `nodo_actual` no tiene efecto o devuelve 400.
- POST con ciudadano de otra institucion devuelve 400.
- Crear e iniciar caso deja evento de inicio y `paso_desde` consistente.

### 3.2. `ValorCampoViewSet` permite modificar datos de formulario por fuera del paso

Severidad: critica.

Evidencia:

- `ValorCampoSerializer` expone `caso`, `campo`, `nodo`, `valor`.
- `ValorCampoViewSet` hereda `BaseModelViewSet` con capacidad `trabajo`.
- El motor valida numericos del formulario del nodo, pero `_guardar_valores` no rechaza claves de campos que no pertenecen al formulario del nodo.

Impacto:

- Se puede editar informacion clinica u operativa ya cargada sin evento.
- Se pueden inyectar campos de formularios de otro flujo o institucion.
- Una decision posterior puede tomar un valor fabricado.
- La historia funcional del caso deja de ser confiable.

Solucion logica:

- Hacer `ValorCampoViewSet` read-only o eliminar escritura generica.
- Guardar valores solo desde `motor.avanzar`.
- En el motor, rechazar cualquier `campo_id` que no pertenezca a `nodo.formulario.campos`.
- Si se necesita corregir un valor, crear una accion formal de correccion con autor, motivo, valor anterior y nuevo.

Pruebas esperadas:

- POST/PATCH/DELETE directo sobre `/valores-campo/` devuelve 405 o 403.
- `avanzar` con campo ajeno al formulario devuelve 400.
- Correccion posterior deja evento visible en timeline.

### 3.3. `EventoCasoViewSet` permite falsificar trazabilidad

Severidad: critica.

Evidencia:

- `EventoCasoSerializer` expone `caso`, `titulo`, `detalle`, `autor` y `nodo`.
- `EventoCasoViewSet` usa CRUD generico con capacidad `trabajo`.

Impacto:

- Un operador podria crear eventos retrospectivos, cambiar autor o borrar hechos.
- La linea de tiempo deja de servir como soporte legal y operativo.
- Se puede ocultar una cancelacion, una derivacion o una espera real.

Solucion logica:

- Convertir eventos en lectura solamente.
- Los eventos deben nacer desde motores o acciones controladas.
- Si se quiere permitir nota manual, crear `casos/{id}/nota/` con:
  - autor tomado de `request.user`;
  - tipo `nota_manual`;
  - sin posibilidad de editar autor, fecha o nodo tecnico.

Pruebas esperadas:

- POST/PATCH/DELETE en `/eventos-caso/` devuelve 405.
- Accion `nota` crea evento con autor del token.

### 3.4. `ItemFilaViewSet` permite crear items de cola por POST

Severidad: alta/critica.

Evidencia:

- `ItemFilaViewSet` restringe PATCH/DELETE, pero mantiene `post`.
- `ItemFilaSerializer` expone `caso`, `nodo`, `urgente`, `orden`, `atendido`, `ausente`, `box`.

Impacto:

- Se pueden crear pacientes falsos o duplicados en una cola.
- Se puede poner un caso en un nodo que no es el actual.
- Se puede manipular prioridad visual u orden sin evento.

Solucion logica:

- Cambiar `http_method_names` a `["get", "head", "options"]`.
- Crear items de fila solo desde el motor cuando el caso llega al nodo correspondiente.
- Agregar una restriccion funcional: un caso no debe tener mas de un item activo por nodo.

Pruebas esperadas:

- POST `/items-fila/` devuelve 405.
- Dos avances simultaneos no generan dos items activos.

### 3.5. El permiso valida el objeto actual, pero no siempre el destino del update

Severidad: critica transversal.

Evidencia:

- `CapacidadPermission.has_object_permission` resuelve la institucion del objeto existente.
- En updates genericos, serializers de varios modulos exponen FKs que definen scope: `institucion`, `area`, `subarea`, `formulario`, `version`, `deposito`, `miembros`, `areas`.

Ejemplos afectados:

- `AreaSerializer`: `institucion`.
- `SubareaSerializer`, `BoxSerializer`, `GrupoSerializer`, `CamaSerializer`: `area` o `subarea`.
- `FormularioSerializer`: `institucion`, `area`.
- `CampoSerializer`: `formulario`.
- `FlujoSerializer`: `institucion`, `area`, `subarea`.
- `NodoSerializer`: `version`, `formulario`, `grupos`.
- `ConexionSerializer`: `version`, `origen`, `destino`.
- `DepositoSerializer`, `InsumoSerializer`, `MembresiaSerializer`.

Impacto:

- Un admin/configurador con permiso sobre un objeto de la institucion A podria intentar moverlo por PATCH a un padre de la institucion B.
- Aunque algunos serializers ya validan parte de la coherencia, no hay una regla transversal que impida cambios de scope despues de creado.

Solucion logica:

- FKs que definen pertenencia institucional deben ser read-only en update.
- Si una mudanza es negocio valido, crear accion explicita `mover` con doble validacion de origen y destino.
- En `perform_update`, revalidar la institucion destino con `capacidades_de(user, destino_id)`.
- Agregar validadores de coherencia por serializer donde falten.

Pruebas esperadas:

- PATCH de objeto de A apuntando a padre de B devuelve 400/403.
- PATCH de `Campo.formulario` con valores existentes devuelve 400.
- PATCH de `Nodo.version` a otra version/institucion devuelve 400.

### 3.6. Roles y capacidades estan demasiado comprimidos para salud

Severidad: critica de diseno funcional.

Evidencia:

- `ROL_CAPACIDADES` concentra todo en `config`, `diseno`, `trabajo`, `registros`, `supervision`.
- `administrativo`, `medico`, `enfermeria` y `jefe_area` comparten `registros`.
- `trabajo` habilita agenda, casos, filas, farmacia, internacion y red.

Impacto:

- Un administrativo puede ver historia clinica completa si tiene `registros`.
- Roles clinicos y administrativos quedan habilitados para dominios que no siempre corresponden: stock, camas, traslados, turnos, casos.
- La UI refleja esa amplitud: todo lo operativo aparece bajo `trabajo`.

Solucion logica:

Separar capacidades por dominio:

- `padron_admision`: alta y busqueda administrativa de pacientes.
- `historia_clinica`: lectura de historia y evolucion.
- `prescripcion`: recetas y suspension.
- `solicitud_estudios`: pedir e informar estudios.
- `turnos`: agenda y reservas.
- `casos_operar`: tomar y avanzar casos.
- `filas`: llamar, reencolar y mover pacientes.
- `internacion`: cama, pase y egreso.
- `farmacia_stock`: ingreso, consumo, transferencia, ajuste, baja.
- `traslados_red`: solicitar, aceptar y cerrar traslados.
- `config_institucional`: estructura, usuarios, membresias.
- `diseno_flujos`: flujos, formularios, nodos y conexiones.
- `auditoria`: accesos clinicos y monitoreo.
- `gobierno_plataforma`: instituciones/redes globales, backups y staff/admin flags.

Mapa inicial sugerido:

- `administrativo`: `padron_admision`, `turnos`, ingreso de casos administrativos.
- `enfermeria`: `casos_operar`, `filas`, lectura clinica acotada, signos/triage, internacion segun area.
- `medico`: `casos_operar`, `historia_clinica`, `prescripcion`, `solicitud_estudios`.
- `farmacia`: rol nuevo con `farmacia_stock`.
- `camas`: rol nuevo o capacidad asignable para `internacion`.
- `derivador_red`: rol/capacidad para `traslados_red`.
- `jefe_area`: supervision mas capacidades operativas de su area, no necesariamente todas las de la institucion.
- `admin`: configuracion institucional, no necesariamente lectura clinica total por defecto.

Pruebas esperadas:

- Administrativo sin `historia_clinica` no puede abrir historia completa.
- Farmacia no puede avanzar casos clinicos si solo tiene stock.
- Enfermeria sin `farmacia_stock` no puede ajustar inventario.
- Jefe de area no puede operar cama o traslado fuera de su area si no tiene capacidad.

## 4. Hallazgos altos por modulo

### 4.1. Agenda y turnos

#### Reserva de turno usa permisos con objeto incompatible

Severidad: critica.

Evidencia:

- `TurnoViewSet.create` busca `Agenda` y `Ciudadano` por id global.
- Luego ejecuta `self.check_object_permissions(request, agenda)`, pero el `institucion_path` del viewset describe un `Turno` (`agenda__institucion`), no una `Agenda`.

Impacto:

- La validacion puede degradar a "tiene trabajo en alguna institucion".
- Un usuario podria reservar en agenda de otra institucion si conoce ids.
- `registrar_llegada` podria abrir caso en la institucion de la agenda con ciudadano de otro padron.

Solucion logica:

- En `create`, traer agenda acotada a instituciones/capacidades del usuario.
- Traer ciudadano acotado a la misma institucion de la agenda.
- Reemplazar `check_object_permissions` por validacion explicita:
  - `trabajo/turnos` en `agenda.institucion_id`;
  - `ciudadano.institucion_id == agenda.institucion_id`.

Pruebas esperadas:

- Usuario de A no reserva en agenda de B.
- Agenda A con ciudadano B devuelve 400.

#### Agenda permite referencias incompatibles

Severidad: alta.

Evidencia:

- `AgendaSerializer.validate` valida tipo/profesional y modalidad presencial, pero no cruces completos.

Riesgos:

- `area` de otra institucion.
- `profesional` sin membresia activa en esa institucion o area.
- `flujo` de otra institucion o area.
- agenda virtual/mixta sin politica clara de enlace.

Solucion logica:

- Validar `area.institucion_id == institucion_id`.
- Validar profesional con membresia activa en institucion/area.
- Validar `flujo.institucion_id == institucion_id`.
- Si agenda es virtual o mixta, definir si `enlace_virtual` es obligatorio en agenda o en turno.

#### Disponibilidad no valida rango de vigencia ni duracion efectiva

Severidad: media.

Solucion logica:

- Validar `vigente_desde <= vigente_hasta`.
- Validar que `duracion_min` y `paso_min` generen al menos un turno dentro de la franja.

### 4.2. Flujos y formularios

#### Nodos y conexiones exponen referencias cruzadas sin validacion suficiente

Severidad: critica/alta.

Riesgos:

- Nodo en version A con formulario de institucion B.
- Nodo con grupos de otra area/institucion.
- Conexion cuya version no coincide con origen/destino.
- Conexion entre nodos de otra version.

Solucion logica:

- Validar en serializers:
  - `nodo.formulario.institucion == nodo.version.flujo.institucion`;
  - grupos pertenecen al area/institucion del flujo;
  - `origen.version_id == destino.version_id == conexion.version_id`.
- Mantener validacion del grafo en publicar, pero bloquear inconsistencias al guardar.

#### Campos de formulario se pueden mover de formulario

Severidad: alta.

Impacto:

- Valores historicos asociados a `Campo` cambian de significado si el campo se mueve.
- Decisiones y reportes pueden empezar a leer un dato bajo otro formulario.

Solucion logica:

- `Campo.formulario` read-only en update.
- Si se requiere reutilizar un campo, duplicarlo.
- Si hay migracion formal, registrar equivalencia y no modificar el campo historico.

### 4.3. Registros clinicos y privacidad

#### `registros` mezcla padron administrativo con historia clinica

Severidad: critica.

Impacto:

- El buscador, la historia, recetas, estudios y consentimientos quedan bajo la misma llave.
- No hay separacion entre "necesito identificar/admitir al paciente" y "necesito leer evolucion clinica".

Solucion logica:

- Separar `padron_admision` de `historia_clinica`.
- Mantener auditoria de lectura clinica para historia, recetas, estudios y consentimientos.
- Definir vistas resumidas para mesa de entrada sin datos clinicos sensibles.

#### Subida de archivos no tiene scope funcional

Severidad: alta.

Evidencia:

- `SubirArchivoView` acepta cualquier usuario autenticado y devuelve URL absoluta del archivo guardado.
- No se vincula el archivo a caso, institucion, historia o consentimiento en el momento de subir.

Impacto:

- Archivos clinicos pueden quedar publicables por URL si el storage es publico.
- No hay autorizacion por dominio ni trazabilidad del archivo antes de asociarlo.
- Riesgo de extensiones/contenido no esperado.

Solucion logica:

- Exigir capacidad segun uso: formulario clinico, estudio o documento administrativo.
- Guardar metadatos: institucion, usuario, proposito, objeto propietario.
- Usar storage privado y URLs firmadas o endpoint protegido.
- Validar tipo, extension, tamanio por tipo documental y considerar antivirus.

Estado 2026-08-19: mitigado en Fase 7 para archivos clinicos. La subida exige `institucion` existente y capacidad `historia_clinica`; guarda bajo `uploads/<institucion>/...`; devuelve `ruta` interna y URL de API protegida; la descarga pasa por endpoint autenticado/autorizado. En desarrollo se bloquea explicitamente `/media/uploads/...` para que los adjuntos clinicos no salgan por el servidor estatico. Quedan como mejora posterior los metadatos completos de proposito/objeto propietario, validacion profunda de MIME/tamanio y antivirus.

### 4.4. Farmacia e insumos

Estado observado:

- Movimientos de stock ya evitan POST generico y pasan por acciones.
- Hay validacion explicita de institucion entre insumo y depositos en acciones.

Riesgos pendientes:

- `trabajo` sigue siendo demasiado amplio para stock.
- `Deposito` e `Insumo` exponen FKs de institucion/area como update generico.
- Entregas parciales de pedidos necesitan semantica clara: preparado/parcial/entregado.

Solucion logica:

- Introducir `farmacia_stock`.
- `Deposito.area` debe pertenecer a `Deposito.institucion`.
- `Insumo.institucion` read-only en update.
- Modelar pedido con estados separados: `pendiente`, `preparado`, `parcial`, `entregado`, `rechazado`.

### 4.5. Internacion y camas

Riesgos:

- Cambios de estado de cama usan capacidad `trabajo`.
- `Cama.area` y `Cama.subarea` pueden requerir validacion mas estricta en update.
- Operaciones de pase/egreso deben alinearse con capacidad especifica de internacion, no con toda operacion.

Solucion logica:

- Crear capacidad `internacion`.
- Validar `subarea.area_id == area_id`.
- Restringir acciones de cama a usuarios con rol/capacidad del area.
- Auditar pase y egreso como eventos clinico-operativos.

### 4.6. Red y traslados

Estado observado:

- El motor de red valida que destino este en una red compartida.
- Valida que `area_destino` pertenezca al establecimiento destino.
- El ciclo no usa update generico.

Riesgo pendiente:

- `trabajo` habilita traslados, lo que puede abrirlo a roles demasiado amplios.

Solucion logica:

- Crear capacidad `traslados_red`.
- Separar permisos por lado:
  - origen: solicitar, cancelar, en camino;
  - destino: aceptar, rechazar, recibido;
  - ambos: no llego, con reglas de estado.

### 4.7. Usuarios, staff y gobierno estatal

#### Admin institucional puede modificar `is_staff`

Severidad: alta.

Evidencia:

- `UsuarioSerializer` expone `is_staff` como escribible; `is_superuser` es read-only.
- `UsuarioViewSet` requiere `config`, no necesariamente gobierno de plataforma.

Impacto:

- Un admin institucional podria habilitar acceso al admin Django.
- Aunque no tenga permisos de modelo, es una bandera de plataforma que no deberia gestionarse desde administracion hospitalaria comun.

Solucion logica:

- `is_staff` read-only para administradores institucionales.
- Solo `gobierno_plataforma` o superusuario puede cambiarlo.
- Separar reset de contrasena de actualizacion general de usuario.

#### Password en serializer de usuario permite reset directo

Severidad: media/alta.

Riesgo:

- Puede ser funcionalmente deseado, pero debe ser un flujo explicito con auditoria.

Solucion logica:

- Accion `reset-password` con motivo, notificacion y evento de auditoria.
- No mezclar cambio de password con PATCH general de usuario.

## 5. UI/UX y diseno

### 5.1. Rutas protegidas no estan protegidas por capacidad

Severidad: media/alta.

Evidencia:

- `Protected` valida usuario e institucion, pero no capacidad.
- El menu filtra por `puedeVer`, pero una URL directa puede renderizar la pantalla.

Impacto:

- El usuario ve una pantalla que despues falla con 403 o queda vacia.
- En contexto hospitalario esto se percibe como sistema roto, no como falta de permiso.

Solucion logica:

- Crear wrapper `RequireCap`.
- Cada ruta declara capacidad requerida.
- Si falta permiso, mostrar pagina de acceso denegado antes de disparar consultas.

Pruebas esperadas:

- Usuario sin `historia_clinica` navega a `/historia` y ve estado de permiso sin llamadas clinicas.
- Usuario sin `farmacia_stock` navega a `/farmacia` y no carga endpoints de stock.

### 5.2. Capacidades duplicadas en frontend y backend

Severidad: media/alta.

Evidencia:

- `InstitutionContext.jsx` define `CAPS_POR_ROL`.
- Backend define `ROL_CAPACIDADES`.

Impacto:

- El menu puede mostrar u ocultar algo distinto de lo que la API permite.
- Al ampliar capacidades por dominio, la divergencia va a crecer.

Solucion logica:

- Backend debe devolver capacidades efectivas por institucion en `/usuarios/me/` o endpoint equivalente.
- Frontend debe renderizar por capacidades del servidor.

### 5.3. Institucion guardada no se valida contra el usuario actual

Severidad: media/alta para estaciones compartidas.

Evidencia:

- `InstitutionContext` inicializa institucion desde `localStorage`.
- No se ve una limpieza inmediata al cambiar de usuario.

Impacto:

- En una computadora compartida, un login nuevo puede heredar contexto visual de otra institucion.
- Backend protege datos, pero la experiencia confunde y puede mostrar nombre/contexto institucional incorrecto hasta que fallen roles o consultas.

Solucion logica:

- Al cambiar `user`, cargar instituciones permitidas.
- Si la institucion guardada no pertenece al usuario, limpiarla.
- Guardar institucion en el mismo storage que el modo de sesion, o limpiarla al logout.

### 5.4. Buscador de pacientes global en topbar

Severidad: media.

Evidencia:

- `BuscadorPacientes` se muestra en desktop dentro del Shell.
- Consulta `/ciudadanos/`, que requiere capacidad de registros.

Impacto:

- Roles sin lectura clinica ven un buscador que puede fallar silenciosamente.
- Si se separa padron de historia, el buscador debe decidir si busca pacientes administrativos o historias clinicas.

Solucion logica:

- Ocultar o degradar el buscador segun capacidad.
- Si el usuario tiene solo `padron_admision`, resultado debe llevar a ficha administrativa.
- Si tiene `historia_clinica`, puede llevar a historia.

### 5.5. Super admin y "ver como rol" no es claramente operable

Severidad: baja/media.

Evidencia:

- Existe `vista` y `setVista`, pero en Shell se ve principalmente como disparador de demo/tutorial.

Impacto:

- La simulacion de rol puede existir tecnicamente, pero no es una herramienta clara de validacion funcional.

Solucion logica:

- Si se conserva, crear selector visible "Ver como" para super admin.
- Si era solo de demo, sacar `vista` de permisos reales para evitar estados ocultos.

### 5.6. Bundle principal grande y sin code splitting

Severidad: media UX/performance.

Evidencia:

- `npm run build` advierte chunk JS principal de 782.22 kB.
- No se encontraron imports lazy.

Impacto:

- Primera carga mas lenta en hospitales con redes internas, VPN o equipos viejos.
- Pantallas pesadas como editor de flujos, farmacia, historia o dashboard entran en el costo inicial aunque no se usen.

Solucion logica:

- Aplicar `React.lazy` por rutas grandes.
- Usar `Suspense` con skeleton de pagina.
- Priorizar lazy loading para `FlujoEditor`, `Farmacia`, `HistoriaDetalle`, `Dashboard`, `Agenda`.

### 5.7. Fortalezas UI detectadas

No todo es deuda. Puntos positivos a preservar:

- Tokens semanticos y soporte de marca blanca.
- Modo oscuro con variables semanticas.
- Foco visible global.
- `prefers-reduced-motion`.
- Estados vacios y errores reutilizables.
- Skeletons para tablas.
- Menu responsive con cajon movil y colapso escritorio.
- Auditor de clases limpio.

## 6. Configuracion y operacion

### 6.1. Backup SQL comprimido dentro del repositorio

Severidad: critica de seguridad/configuracion.

Evidencia:

- `git ls-files` lista un archivo bajo `backend/C.../Users/mkdir/AppData/Local/Temp/x/cauce-20260814-133512.sql.gz`.
- El archivo pesa 234,533 bytes.

Impacto:

- Puede contener datos personales, datos clinicos, usuarios, hashes o configuracion.
- Si esta versionado, no alcanza con borrarlo del working tree: queda en historial.

Solucion logica:

- No abrir ni distribuir el dump.
- Removerlo del repositorio y del historial si corresponde.
- Rotar secretos si el dump contiene configuracion sensible.
- Agregar patrones a `.gitignore`: dumps, `.sql`, `.sql.gz`, backups temporales.
- Definir politica de backup fuera del repo: cifrado, retencion, acceso y auditoria.

Estado 2026-08-19: corregido en Bloque 1. El dump `.sql.gz` fue eliminado del working tree y queda como baja en el diff; `.gitignore` cubre dumps SQL, respaldos, temporales y rutas `backend/C*/Users/`. Si tuvo datos reales, queda pendiente limpiar historial Git antes de publicar o compartir el repositorio.

### 6.2. Carpeta accidental `backend/backend`

Severidad: media.

Evidencia:

- `git ls-files` lista `backend/backend/apps/agenda/management/...`.

Impacto:

- Puede confundir imports, empaquetado, herramientas de deploy o busquedas.
- Puede esconder comandos o archivos duplicados.

Solucion logica:

- Verificar si tiene uso real. Si no, eliminarla.
- Agregar test/check de estructura para detectar carpetas duplicadas.

Estado 2026-08-19: corregido en Bloque 1. Se eliminaron los archivos vacios trackeados bajo `backend/backend/...` y se agrego `/backend/backend/` a `.gitignore`.

### 6.3. Media files en desarrollo y URLs absolutas

Severidad: alta si se replica en produccion.

Evidencia:

- En `DEBUG`, `urls.py` sirve `MEDIA_URL`.
- `SubirArchivoView` devuelve URL absoluta.

Solucion logica:

- Produccion debe usar storage privado.
- No exponer media clinica por ruta publica.
- Centralizar descarga en endpoint con permisos y auditoria.

## 7. Orden recomendado de solucion

### Fase 1 - Blindaje de reglas criticas

- Cerrar escritura generica de `Caso`, `ValorCampo`, `EventoCaso`, `ItemFila`.
- Revalidar destino institucional en updates de FKs criticos.
- Validar `TurnoViewSet.create` con agenda y ciudadano en misma institucion.
- Retirar dump SQL del repo y definir ignore/politica.

Avance 2026-08-19:

- Implementado: `Caso` conserva alta por `POST /api/casos/`, pero bloquea `PATCH`, `PUT` y `DELETE`; el alta usa serializer minimo y no permite setear estado, paso actual, asignacion, origen ni estudio.
- Implementado: el alta de caso exige paciente, version publicada, version de la misma institucion y paciente de la misma institucion.
- Implementado: `ValorCampo` y `EventoCaso` quedaron como endpoints solo lectura; se escriben desde el motor.
- Implementado: `ItemFila` sigue permitiendo `mover/`, pero bloquea el `POST /api/items-fila/` generico.
- Implementado: el motor rechaza valores de campos que no pertenezcan al formulario del nodo actual.
- Cubierto con tests: mutaciones genericas indebidas, alta contra version no publicada, cruces de institucion, endpoints read-only y campo ajeno al formulario.
- Pendiente de esta fase: validaciones de FKs criticos fuera de casos/fila (`TurnoViewSet.create`, dumps/politica de repo y referencias institucionales transversales).

### Fase 2 - Capacidades por dominio

- Diseñar y migrar capacidades granulares.
- Exponer capacidades efectivas desde backend.
- Actualizar UI para usar capacidades del servidor.
- Agregar pruebas por rol y por modulo.

Avance 2026-08-19:

- Implementado: la matriz de roles del backend ahora distingue capacidades de dominio (`padron_admision`, `historia_clinica`, `prescripcion`, `solicitud_estudios`, `turnos`, `casos_operar`, `filas`, `internacion`, `farmacia_stock`, `traslados_red`, `config_institucional`, `diseno_flujos`, `gobierno_plataforma`) y conserva las capacidades legacy solo como compatibilidad.
- Implementado: `/api/usuarios/me/` devuelve `roles_por_institucion` y `capacidades_por_institucion`, incluyendo capacidades UI como `auditoria` solo para roles habilitados.
- Implementado: el frontend dejo de calcular permisos reales con una copia local de roles. Menues y rutas protegidas consumen las capacidades del servidor; si falta capacidad, la ruta muestra acceso denegado.
- Implementado: el buscador superior de pacientes queda disponible solo con `historia_clinica` y ya no dispara consultas clinicas cuando esa capacidad falta.
- Implementado: flujos/formularios requieren `diseno_flujos`; estructura, usuarios, agendas base y catalogos institucionales requieren `config_institucional`; turnos requiere `turnos`; farmacia operativa requiere `farmacia_stock`; internacion/camas operativas requiere `internacion`; red/traslados requiere `traslados_red`.
- Implementado: registros se separo por responsabilidad. Padron/admision permite buscar o cargar pacientes y consentimientos; historia clinica protege historia, entradas, estudios y recetas; prescripcion protege emitir/suspender recetas; solicitud de estudios protege alta/informe de estudios.
- Implementado: el serializer de pacientes oculta alergias, condiciones, conteos, recetas activas y ultima atencion cuando el usuario solo tiene `padron_admision`.
- Cubierto con tests: perfil con capacidades por institucion, barrida global de permisos por accion, registros con frontera padron/historia/prescripcion/estudios, auditoria de accesos, FHIR, agenda, farmacia, red, instituciones/camas y build frontend.
- Pendiente de esta fase: revisar si `registros` legacy puede retirarse totalmente de la matriz y evaluar code splitting para reducir el bundle principal. La pantalla administrativa de padron separada se implemento en Bloque 4.

Avance 2026-08-20 - Bloque 2:

- Implementado: roles estatales `plataforma`, `auditor` y `reportes`.
- Implementado: `gobierno_plataforma` funciona como capacidad global para gobierno de instituciones, redes sanitarias y directorio estatal.
- Implementado: la escritura de instituciones y redes queda reservada a plataforma/superusuario.
- Implementado: solo superusuario o autoridad de plataforma puede asignar roles estatales `plataforma` y `auditor`.
- Implementado: `auditor` y `plataforma` auditan accesos clinicos con alcance estatal, sin recibir permisos clinicos u operativos.
- Implementado: el frontend reconoce autoridad de plataforma para entrar al Directorio y trata `gobierno_plataforma`/auditoria estatal como capacidades globales.
- Cubierto con tests: `apps.accounts.tests`, `apps.instituciones.tests`, `apps.red.tests_api`, `apps.auditoria.tests`, `makemigrations --check --dry-run`, `npm run build` y `npm run auditar`.

### Fase 3 - Validadores de configuracion

- Completar validadores de agenda, disponibilidad, flujo, nodo, conexion, formulario, campo, cama, deposito y membresia.
- Hacer read-only FKs de scope en update.
- Agregar acciones explicitas de traslado/mudanza cuando sean negocio real.

Avance 2026-08-19:

- Implementado: agenda valida que area y flujo pertenezcan a la misma institucion; las agendas profesionales requieren profesional con membresia activa; institucion y area quedan read-only en update.
- Implementado: disponibilidad valida duracion positiva, vigencia coherente y no permite mover la franja a otra agenda por update; bloqueos tampoco cambian de agenda por update.
- Implementado: reserva de turnos valida capacidad `turnos` contra la institucion de la agenda y el motor rechaza paciente de otra institucion.
- Implementado: flujos validan area/subarea contra institucion; institucion, area y subarea quedan read-only en update.
- Implementado: nodos validan formulario y grupos contra la institucion del flujo; la version del nodo queda read-only en update.
- Implementado: conexiones validan que origen y destino pertenezcan a la version de la conexion; la version queda read-only en update.
- Implementado: campos no cambian de formulario por PATCH; formularios no cambian de institucion por PATCH. El area del formulario sigue editable, pero validada dentro de la misma institucion.
- Implementado: camas validan que el sector/subarea pertenezca al area y no cambian area/subarea por update; areas, subareas, boxes y grupos congelan sus FKs de alcance en update.
- Implementado: depositos validan area contra institucion; insumos no cambian de institucion, lotes no cambian de insumo y pedidos no cambian origen/destino por update.
- Implementado: membresias validan que todas sus areas pertenezcan a la institucion; usuario e institucion quedan read-only en update. Legajos no cambian de usuario por update.
- Implementado: `is_staff` queda read-only en el serializer general de usuarios.
- Cubierto con tests: `apps.agenda`, `apps.flujos`, `apps.formularios`, `apps.accounts`, `apps.instituciones.test_camas` y `apps.farmacia.tests_api`.
- Pendiente fuera de esta fase: acciones explicitas de mudanza si el negocio las necesita; validacion profunda de ids dentro de `Nodo.config` para derivaciones internas ya corresponde a la fase de motor de casos/traslados.

Avance 2026-08-20 - Bloque 3:

- Implementado/revisado: los nodos de atencion pueden configurar `firma_roles` y `firma_matricula`.
- Implementado/revisado: el motor valida rol, pertenencia al area y matricula segun la configuracion del nodo.
- Implementado/revisado: configuraciones vacias o mal tipadas caen al default seguro de firma medica con matricula.
- Implementado: `validar_version` marca como error los roles de firma desconocidos para que no queden ocultos hasta la atencion real.
- Implementado/revisado: el editor visual de flujos expone roles firmantes y exigencia de matricula en nodos de atencion.
- Cubierto con tests: `apps.casos.tests.FirmaConfigurableTests`, tests focalizados de ensayo, `apps.casos.tests` y `apps.flujos.tests`.
- Pendiente fuera de este bloque: firma digital legal/certificado si el alcance normativo del producto lo requiere.

Avance 2026-08-20 - Bloque 7:

- Implementado/revisado: agenda calcula bloqueos por solape completo entre bloqueo y turno, no solo por hora de inicio.
- Implementado/revisado: la grilla no ofrece horarios libres que solapan bloqueos parciales y mantiene visibles los turnos afectados ya dados.
- Implementado/revisado: reserva y reprogramacion rechazan horarios que pisan parcialmente un bloqueo.
- Implementado/revisado: la respuesta de bloqueo lista turnos afectados por solape aunque el turno haya empezado antes del rango bloqueado.
- Implementado/revisado: `origen` de turno se valida contra choices y `sobreturno=false` como texto no se interpreta como verdadero.
- Cubierto con tests: focalizados de motor/API, `apps.agenda` completo, `py_compile` y `makemigrations --check --dry-run`.

### Fase 4 - UX y performance

- Guard de rutas por capacidad.
- Buscador de pacientes segun permisos.
- Validacion de institucion guardada por usuario.
- Code splitting por pantallas grandes.
- Mejorar descubribilidad de herramientas de super admin.

Avance 2026-08-19:

- Implementado: las rutas protegidas ya usan guard por capacidad efectiva del backend. Si falta capacidad, se muestra acceso denegado antes de renderizar la pantalla.
- Implementado: las pantallas de ruta se cargan con `React.lazy`/`Suspense`, con fallback dentro del `Shell` para no perder marco de navegacion mientras carga el chunk.
- Implementado: el bundle principal bajo de ~782 kB a ~300.8 kB; pantallas pesadas como `FlujoEditor`, `Areas`, `Agenda`, `Farmacia`, `CasoDetalle`, `Dashboard` e `HistoriaDetalle` quedan en chunks separados.
- Implementado: `InstitutionContext` valida la institucion guardada contra las capacidades del usuario actual y la limpia si no pertenece a ese usuario. No limpia durante `loading`, para no romper refresh con sesion valida.
- Implementado: el buscador superior de pacientes queda condicionado por `historia_clinica`; usuarios sin esa capacidad no disparan consultas clinicas desde la topbar.
- Implementado: el super admin tiene selector visible `Ver como` dentro del contexto institucional para alternar entre vista completa, configurador y administrativo.
- Cubierto con checks: `npm run build` OK y `npm run auditar` OK, 233 clases revisadas, sin clases huerfanas ni colisiones.
- Cerrado en Bloque 4: la pantalla administrativa de padron separada de historia clinica existe y el buscador superior degrada a busqueda administrativa con `padron_admision`, navegando a ficha no clinica.

Avance 2026-08-20 - Bloque 4:

- Implementado: rutas `/padron` y `/padron/:id` con guard `padron_admision`.
- Implementado: la lista de padron usa columnas administrativas y navega a ficha administrativa; `/historia` conserva columnas clinicas y guard `historia_clinica`.
- Implementado: la ficha administrativa permite editar identidad/cobertura/domicilio y gestionar consentimiento sin renderizar evolucion, estudios, recetas ni alergias.
- Implementado: el buscador superior busca pacientes con `padron_admision`; si no hay `historia_clinica`, abre `/padron/:id`.
- Implementado: la exportacion CSV del padron no muestra columnas clinicas cuando falta `historia_clinica`.
- Implementado: `Ciudadano.institucion` queda bloqueado por PATCH comun.
- Cubierto con tests/checks: `apps.registros.tests_api.PermisosGranularesRegistrosTests`, `apps.registros.tests_api`, `makemigrations --check --dry-run`, `npm run build`, `npm run auditar` y `git diff --check`.

### Fase 5 - Derivaciones, subprocesos y casos activos

- Validar `area_destino_id` y `flujo_destino_id` declarados dentro de `Nodo.config`.
- Evitar que estudios derivados, interconsultas y traslados elijan flujo receptor por orden tecnico.
- Reactivar correctamente el caso padre cuando un subproceso fue cancelado y los restantes finalizaron.
- Normalizar la definicion operativa de "caso activo": activo es todo estado no finalizado; `cerrado` y `cancelado` son finales.
- Agregar regresiones sobre derivaciones cruzadas, flujo receptor manual/ambiguo, retorno de subprocesos y conteos.

Avance 2026-08-19:

- Implementado: el motor de casos rechaza nodos `Derivar` cuyo `area_destino_id` pertenezca a otra institucion o cuyo `flujo_destino_id` apunte a otra institucion.
- Implementado: el flujo destino explicito debe estar publicado, pertenecer al area derivada y aceptar derivaciones desde el nodo Inicio (`origen=derivado` o `origen=ambos`; ausencia de config mantiene compatibilidad como `ambos`).
- Implementado: estudios derivados e interconsultas usan un selector funcional de flujo receptor por area. Si no hay flujo publicado, si todos son solo `manual`, o si hay mas de un receptor funcional, el motor falla con error de negocio en vez de elegir por ID.
- Implementado: aceptar un traslado de red usa el mismo selector de flujo receptor que casos internos, manteniendo el caso destino dentro del establecimiento y area correctos.
- Implementado: `_retornar_al_origen` excluye `cerrado` y `cancelado` al decidir si quedan subprocesos pendientes.
- Implementado: `Caso.ESTADOS_FINALIZADOS` centraliza los estados finales y se aplica en conteos de flujos, archivo de version publicada y metricas rapidas de institucion.
- Cubierto con tests: derivacion interna a area ajena, derivacion a flujo ajeno, flujo destino solo manual, interconsulta con receptor manual/ambiguo, estudio derivado a area ajena, subproceso cancelado que no bloquea retorno, traslado aceptado contra flujo solo manual, archivo con casos cancelados y conteo de activos sin cancelados.
- Checks ejecutados: `apps.casos.tests.EstudioDerivadoTests apps.casos.tests.DerivacionEntreFlujosTests` OK, `apps.red.tests.RespuestaTests` OK, `apps.flujos.tests.ArchivarFlujoTests apps.flujos.tests.VolumenDelDisenoTests apps.instituciones.test_camas.MetricasInstitucionTests` OK, `apps.casos.tests apps.casos.tests_api` OK, `apps.red.tests.RespuestaTests apps.red.tests.SolicitudTests apps.red.tests.DestinosTests` OK, `apps.instituciones.test_camas` OK y `apps.flujos` OK.
- Nota de verificacion: la corrida monolitica `apps.casos apps.flujos apps.red apps.instituciones.test_camas` y las corridas completas separadas de `apps.casos`/`apps.red` excedieron el timeout del comando; se reemplazaron por lotes focalizados y por archivos/clases de la superficie tocada.
- Cerrado en Bloque 6: `guardar_en` de integraciones y `prioridad_campo` se validan contra campos reales, institucion y compatibilidad funcional. Quedan politicas de integraciones externas nuevas y propietarios de archivos clinicos cuando la UI envie ese dato.

Avance 2026-08-20 - Bloque 6:

- Implementado: `validar_version` rechaza `guardar_en` inexistente, mal tipado o de otra institucion.
- Implementado: las decisiones solo consideran disponible un campo si lo carga un formulario del flujo o una integracion valida.
- Implementado: `_llamar_externo` valida defensivamente el campo destino antes de crear `ValorCampo`.
- Implementado: `prioridad_campo` debe pertenecer al formulario del nodo y ser de seleccion unica.
- Cubierto con tests: `apps.casos.test_validacion_y_ensayo`, `apps.flujos.tests`, `apps.casos.tests apps.casos.test_validacion_y_ensayo`, `makemigrations --check --dry-run` y `git diff --check`.

### Fase 6 - Farmacia: entregas parciales y pedidos

- Definir semantica operativa de entrega parcial.
- Evitar que una entrega incompleta cierre el pedido como entregado.
- Permitir entregas sucesivas hasta completar el faltante.
- Validar cantidad acumulada por renglon y proteger contra copias viejas/doble envio.

Avance 2026-08-19:

- Implementado: `Pedido.Estado` incorpora `parcial`.
- Implementado: `entregar_pedido` deja el pedido en `parcial` cuando todavia hay faltantes y solo marca `entregado` cuando todas las lineas llegaron a la cantidad pedida.
- Implementado: una entrega vacia ya no cierra el pedido.
- Implementado: la cantidad entregada se valida contra el pendiente real de cada linea (`pedido_cant - entregado`), no contra el total original.
- Implementado: el motor detecta si el pedido cambio de estado entre la copia recibida y la fila bloqueada, para cortar doble envio sobre una copia vieja.
- Implementado: un pedido parcial se puede completar en una segunda entrega; al completarse se setea `resuelto`.
- Implementado: rechazar un pedido ahora setea `resuelto`, incluyendo el caso de cerrar un faltante luego de una entrega parcial.
- Cubierto con tests: entrega parcial queda abierta, segunda entrega completa, exceso acumulado falla, entrega vacia no cierra, copia vieja no vuelve a entregar, API devuelve `parcial` y luego `entregado`.
- Checks ejecutados: `apps.farmacia.tests.PedidoTests apps.farmacia.tests_api.FarmaciaAPITests` OK, 31 tests; `apps.farmacia` OK, 80 tests.
- Pendiente fuera de esta fase: si producto necesita preparacion fisica previa, definir flujo de uso real de `preparado` en UI/API. Hoy `parcial` cubre deuda de reposicion y `entregado` cierre completo.

### Fase 7 - Archivos clinicos y privacidad

- Endurecer subida de adjuntos clinicos con institucion obligatoria y permiso por dominio.
- Evitar que nuevas subidas devuelvan enlaces publicos `/media/uploads/...`.
- Agregar descarga por endpoint protegido con control de capacidad `historia_clinica` en la institucion del archivo.
- Ajustar frontend para enviar la institucion del caso al subir y descargar estudios por `fetch` con token.
- Conservar compatibilidad visual para referencias antiguas que solo guardaban texto.

Avance 2026-08-19:

- Implementado: `SubirArchivoView` exige autenticacion, `institucion` y capacidad `historia_clinica` en esa institucion.
- Implementado: los archivos nuevos se guardan bajo `uploads/<institucion>/<uuid>.<ext>` y la API devuelve `nombre`, `ruta` y `url` protegida.
- Implementado: `DescargarArchivoView` valida ruta, institucion embebida y permiso antes de servir el binario.
- Implementado: `api.upload` recibe institucion; `CasoDetalle` adjunta la institucion del caso en campos archivo y estudios.
- Implementado: `HistoriaDetalle` descarga archivos internos mediante `api.downloadArchivo`, enviando `Authorization` y evitando enlaces directos que fallan con JWT.
- Cubierto con tests: upload con URL protegida, descarga autorizada, bloqueo de `/media/uploads/...`, bloqueo por falta de institucion, bloqueo por institucion inexistente, bloqueo a usuario sin `historia_clinica`, bloqueo de descarga desde otra institucion y subida sin archivo.
- Checks ejecutados: `apps.casos.tests_api.SubirArchivoTest` OK, 8 tests; `apps.casos.tests_api` OK, 49 tests; `npm run build` OK; `npm run auditar` OK.
- Cerrado en Bloque 5: modelo de metadatos de archivo clinico con propietario/proposito opcional, validacion MIME/tamanio/extension/firma y SHA-256.
- Pendiente fuera de esta fase: antivirus y migracion/ocultamiento de archivos historicos que ya existan bajo `/media`.

Avance 2026-08-20 - Bloque 5:

- Implementado: `ArchivoClinico` persiste institucion, ruta, nombre original, content type, tamano, SHA-256, proposito, propietario opcional, usuario y fecha.
- Implementado: la subida de archivos rechaza archivos vacios, mayores al maximo, tipos no permitidos, extension incompatible y contenido que no coincide con el tipo declarado.
- Implementado: tipos permitidos PDF, JPEG, PNG, WebP y texto plano; maximo configurable con `ARCHIVO_CLINICO_MAX_BYTES`.
- Implementado: la descarga usa metadata cuando existe y mantiene fallback para rutas historicas `uploads/<institucion>/...`.
- Cubierto con tests: `apps.casos.tests_api.SubirArchivoTest`, `apps.casos.tests_api`, `makemigrations --check --dry-run` y `git diff --check`.

### Bloque 1 - Higiene de repositorio y respaldos

- Eliminar dump SQL versionado bajo ruta temporal.
- Eliminar archivos vacios de la carpeta accidental `backend/backend`.
- Agregar `.gitignore` preventivo para dumps, respaldos, temporales y copias anidadas.
- Revisar el diff y confirmar que no queden errores de whitespace.

Avance 2026-08-19:

- Implementado: baja del dump `backend/C.../Users/.../Temp/.../cauce-20260814-133512.sql.gz`.
- Implementado: baja de `backend/backend/apps/agenda/management/__init__.py` y `backend/backend/apps/agenda/management/commands/__init__.py`.
- Implementado: `.gitignore` excluye `*.sql`, `*.sql.gz`, `*.dump`, `*.backup`, `*.bak`, `*.sqlite3.gz`, `backend/C*/Users/`, `backend/**/Temp/` y `/backend/backend/`.
- Review ejecutada: `git check-ignore -v` confirma reglas preventivas; `git diff --check` no reporta errores.
- Pendiente fuera del codigo: si el dump tenia datos reales, limpiar historial Git antes de compartir/publicar el repo.

### Bloque 8 - Puestos, grupos y membresia activa

- Centralizar la regla de grupo operativo para no usar `Usuario.grupos` directo en bandejas, acciones ni permisos de puesto.
- Exigir usuario activo, grupo activo, area activa y membresia activa en la institucion/area del grupo.
- Evitar que bajas de membresia sigan habilitando `MisTareasView`, `PuestoDetalleView`, acciones de caso o notificaciones.
- Validar en diseno que un nodo no quede asignado a grupos inactivos.
- Ocultar de serializers operativos los integrantes/responsables que ya no cuentan como vigentes.

Avance 2026-08-20:

- Implementado: `motor.grupos_operativos_de` es la regla comun para tomar casos, listar mis tareas y abrir detalle de puesto.
- Implementado: notificaciones, `GrupoSerializer`, `NodoSerializer`, `CasoSerializer` y `validar_version` filtran o rechazan grupos/miembros inactivos segun corresponda.
- Implementado: los contadores de staff por area/institucion solo cuentan usuarios activos con membresia activa.
- Cubierto con tests: `ResponsabilidadTests`, `NotificacionNodoTests`, `PuestosConMembresiaActivaTests`, `GruposOperativosTests`, `NodoGruposTests`, `GruposResponsablesTests` y suite amplia de casos/instituciones/flujos.
- Checks ejecutados: py_compile OK; set enfocado OK, 32 tests; set amplio OK, 229 tests.

## 8. Checklist de pruebas funcionales nuevas

- Caso no se puede cerrar/cancelar/reasignar por PATCH.
- Caso no se crea con version no publicada.
- Caso no se crea con version, ciudadano o area de otra institucion.
- Valor de formulario no se puede editar por endpoint generico.
- Avanzar con campo ajeno al formulario falla.
- Evento de caso no se puede crear/editar/borrar manualmente.
- Item de fila no se crea por POST directo.
- Reserva de turno cruza agenda/ciudadano/institucion correctamente.
- Admin institucional no puede marcar `is_staff`.
- Usuario sin `historia_clinica` no ve historia ni dispara llamadas clinicas por ruta directa.
- Usuario con `padron_admision` ve solo ficha administrativa.
- Farmacia requiere `farmacia_stock`.
- Internacion requiere `internacion`.
- Traslados requiere `traslados_red`.
- Nodo `Derivar` no acepta area ni flujo de otra institucion.
- Estudio derivado/interconsulta no aceptan area de otra institucion.
- Flujo receptor de derivacion debe aceptar `derivado` o `ambos`; `manual` no recibe casos derivados.
- Si un area tiene mas de un flujo receptor publicado, la derivacion debe fallar y pedir configuracion explicita.
- Subproceso cancelado no bloquea el retorno del caso padre cuando los demas finalizaron.
- Casos cancelados no cuentan como activos ni bloquean archivar versiones.
- Entrega parcial de farmacia deja el pedido en `parcial`.
- Segunda entrega de farmacia completa el faltante y recien ahi marca `entregado`.
- Entrega vacia no cierra pedidos.
- Entrega acumulada por encima de lo pendiente falla.
- Subida de archivo clinico exige institucion y `historia_clinica`.
- Descarga de archivo clinico bloquea usuarios sin permiso en la institucion del archivo.
- Dump SQL no aparece en `git ls-files`.
- Build frontend mantiene auditor de clases limpio.

## 9. Cierre funcional

La conclusion de esta pasada es que el sistema esta maduro en intencion funcional, pero necesita endurecer sus fronteras. Las reglas importantes existen en motores y comentarios; el siguiente paso es impedir que los endpoints genericos las rodeen.

La solucion no es agregar controles aislados pantalla por pantalla. La solucion correcta es:

- motores como unica puerta de mutacion sanitaria;
- serializers que validan pertenencia institucional;
- capacidades finas por dominio;
- frontend que muestra permisos efectivos del servidor;
- configuracion sensible fuera del repositorio.
