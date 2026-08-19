# Soluciones logicas propuestas por funcionalidad

Fecha: 2026-08-18  
Base: `docs/auditorias/loop-funcionalidades-logica-2026-08-18.md`  
Objetivo: transformar los hallazgos de logica en reglas funcionales implementables y testeables.

## Principio rector

En un sistema sanitario multi-institucion, un identificador valido no alcanza. Toda referencia debe cumplir tres condiciones:

1. **Existe.**
2. **Pertenece al mismo contexto institucional o a una red autorizada.**
3. **Es funcionalmente compatible con la accion.**

Ejemplos:

- Un area existe, pero no sirve si es de otro hospital.
- Un flujo esta publicado, pero no sirve si no esta marcado como receptor de derivaciones.
- Una cama existe, pero no sirve si su sector pertenece a otra area.
- Un profesional existe, pero no sirve si no tiene membresia activa donde atiende.

## 1. Identidad, usuarios, membresias y roles

### Problema: membresia con areas de otra institucion

Regla funcional:

- Una membresia pertenece a una unica institucion.
- Todas las areas asignadas a esa membresia deben pertenecer a esa misma institucion.
- Si el rol es `admin`, puede no tener areas asignadas o tener areas informativas, pero nunca de otra institucion.
- Si el rol es operativo por area, al menos un area deberia ser obligatoria si el producto espera responsabilidad acotada.

Solucion propuesta:

- Agregar validacion en `MembresiaSerializer.validate`.
- Rechazar cualquier area cuyo `area.institucion_id != membresia.institucion_id`.
- Evaluar regla adicional: roles como `medico`, `enfermeria`, `jefe_area` y `administrativo` requieren areas; `admin` puede no requerirlas.

Mensaje sugerido:

```text
El area indicada no pertenece a la institucion de la membresia.
```

Tests:

- Crear membresia de Hospital A con area de Hospital B devuelve 400.
- Actualizar membresia existente agregando area de otra institucion devuelve 400.
- Admin institucional sin areas se acepta si esa es la regla definida.

### Problema: legajo profesional global sin gobierno claro

Regla funcional:

- El legajo profesional representa una habilitacion sensible.
- Debe definirse si es global, provincial/estatal o institucional.

Solucion recomendada:

- Si el legajo es **global o estatal**: solo superusuario o rol estatal debe crearlo/modificarlo.
- Si el legajo es **institucional**: agregar institucion al modelo o una tabla de habilitaciones por institucion.

Decision pendiente:

- Definir si una matricula sirve para toda la plataforma o si cada efector valida su propio legajo.

Tests:

- Admin de Hospital A no modifica legajo global si no tiene rol estatal.
- Usuario estatal si puede gestionar legajos globales.

## 2. Instituciones, areas, subareas, grupos, boxes y camas

### Problema: cama con subarea que no pertenece al area

Regla funcional:

- Una cama pertenece a un area.
- Si tiene subarea/sector, ese sector debe pertenecer al mismo area.
- Una cama no puede quedar visible en un area y tabulada en un sector de otra.

Solucion propuesta:

- Agregar validacion en `CamaSerializer.validate`.
- Si `subarea` viene informada, exigir `subarea.area_id == area.id`.

Mensaje sugerido:

```text
El sector indicado no pertenece al area de la cama.
```

Tests:

- Crear cama de Clinica Medica con subarea de Cirugia devuelve 400.
- Actualizar cama moviendola a un area sin cambiar sector incompatible devuelve 400.
- Crear cama sin subarea sigue funcionando.

### Problema: metricas cuentan cancelados como activos

Regla funcional:

- Un caso activo es todo caso que no esta `cerrado` ni `cancelado`.
- Esta definicion debe ser unica para tableros, metricas, archivado y alertas.

Solucion propuesta:

- Crear helper comun, por ejemplo:

```python
ESTADOS_NO_ACTIVOS = [Caso.Estado.CERRADO, Caso.Estado.CANCELADO]
```

o un manager/queryset:

```python
Caso.objects.activos()
```

- Reemplazar `.exclude(estado=CERRADO)` por `.exclude(estado__in=ESTADOS_NO_ACTIVOS)`.

Tests:

- Caso cancelado no suma en metrica rapida institucional.
- Caso cancelado no bloquea archivado de flujo si no hay otros activos.
- Tablero institucional y metrica rapida devuelven el mismo conteo de activos.

### Problema: alta de instituciones disponible para admins institucionales

Regla funcional:

- Crear/modificar instituciones no es configuracion interna de un hospital; es gobierno de plataforma o gestion estatal.

Solucion propuesta:

- Introducir una capacidad separada, por ejemplo `plataforma` o `gobierno`.
- Reservar `InstitucionViewSet.create` y, probablemente, cambios criticos como `estado`, `tipo`, `cuit`, a esa capacidad.
- Mantener `config` institucional para areas, boxes, camas, grupos y parametros internos.

Tests:

- Admin de Hospital A no puede crear Hospital B.
- Rol estatal/plataforma puede crear instituciones.
- Admin institucional puede editar solo configuracion permitida de su institucion, si esa es la regla.

## 3. Formularios dinamicos

### Estado: no se detecto falla critica

Regla funcional a conservar:

- El formulario pertenece a una institucion.
- Si se asigna a un area, el area debe pertenecer a esa institucion.
- Los campos pertenecen al formulario y heredan su institucion.

Solucion preventiva:

- Mantener validacion actual.
- Agregar tests de regresion para area ajena y campo en formulario ajeno.

Tests:

- Formulario de Hospital A con area de Hospital B devuelve 400.
- Campo creado sobre formulario de otra institucion devuelve 403.

## 4. Flujos, versiones, nodos y conexiones

### Problema: conexiones entre nodos de distinta version

Regla funcional:

- Una conexion une dos nodos de la misma version de flujo.
- La conexion tambien debe pertenecer a esa misma version.

Solucion propuesta:

- Agregar validacion en `ConexionSerializer.validate`.
- Exigir:

```text
origen.version_id == version.id
destino.version_id == version.id
```

Mensaje sugerido:

```text
La conexion solo puede unir nodos de la misma version.
```

Tests:

- Conexion version V1 con origen V2 devuelve 400.
- Conexion version V1 con destino V2 devuelve 400.
- Conexion interna de V1 se acepta.

### Problema: nodo referencia formulario o grupos de otra institucion

Regla funcional:

- Un nodo hereda la institucion de `version.flujo.institucion`.
- El formulario del nodo debe pertenecer a esa institucion.
- Los grupos responsables deben pertenecer a areas de esa institucion.
- La configuracion del nodo debe validar ids internos segun el tipo de nodo.

Solucion propuesta:

- Agregar validacion en `NodoSerializer.validate`.
- Resolver `institucion = version.flujo.institucion`.
- Para `formulario`: exigir `formulario.institucion_id == institucion.id`.
- Para `grupos`: exigir todos los `grupo.area.institucion_id == institucion.id`.
- Para `tipo == derivar`: validar `area_destino_id` y `flujo_destino_id`.

Tests:

- Nodo con formulario de otra institucion devuelve 400.
- Nodo con grupo de otra institucion devuelve 400.
- Nodo derivar a area de otra institucion devuelve 400.

### Problema: flujo con area ajena a la institucion

Regla funcional:

- Un flujo pertenece a una institucion.
- Si tiene area, esa area debe pertenecer a la misma institucion.
- Si tiene subarea, debe pertenecer al area del flujo.

Solucion propuesta:

- Extender `FlujoSerializer.validate`.
- Exigir:

```text
area.institucion_id == institucion.id
subarea.area_id == area.id
```

Tests:

- Flujo de Hospital A con area de Hospital B devuelve 400.
- Flujo con subarea de otra area devuelve 400.

### Problema: receptor de derivacion elegido por orden tecnico

Regla funcional:

- Un area puede tener muchos flujos publicados, pero no todos necesariamente reciben derivaciones.
- La recepcion debe ser explicita.

Soluciones posibles:

- Opcion A: campo en `Flujo`, por ejemplo `recibe_derivaciones = true`.
- Opcion B: nodo Inicio con `config.origen = "derivado"` o `"ambos"` como criterio obligatorio.
- Opcion C: obligar a que la derivacion indique `flujo_destino_id`.

Recomendacion:

- Usar opcion B si ya existe `origen_inicio`, y exigir que el flujo receptor tenga inicio compatible.
- Si hay mas de un flujo compatible, devolver error y pedir seleccion explicita.

Tests:

- Area con un solo flujo receptor recibe correctamente.
- Area con dos flujos receptores devuelve error de ambiguedad.
- Flujo manual no recibe derivaciones.

## 5. Casos, motor asistencial, filas y derivaciones internas

### Problema: derivacion interna cruza instituciones

Regla funcional:

- Una derivacion interna mueve un caso dentro de la misma institucion.
- Si el caso debe ir a otra institucion, debe usarse traslado/red.

Solucion propuesta:

- En el motor, antes de cambiar `area_actual` o `version`, validar:

```text
area_destino.institucion_id == caso.institucion_id
flujo_destino.institucion_id == caso.institucion_id
```

- Si no cumple, devolver error funcional que indique usar traslado.

Mensaje sugerido:

```text
La derivacion interna solo puede hacerse dentro de la misma institucion. Para otro establecimiento, usa traslado por red.
```

Tests:

- Nodo derivar a area de otra institucion falla.
- Nodo derivar a flujo de otra institucion falla.
- Derivacion interna dentro de la misma institucion sigue funcionando.

### Problema: estudio derivado/interconsulta cruza instituciones

Regla funcional:

- Estudio derivado e interconsulta son subprocesos internos.
- Deben quedar en la misma institucion del caso origen.

Solucion propuesta:

- En las acciones de vista o en el motor, validar que `area_destino.institucion_id == caso.institucion_id`.
- Mejor ubicar la regla en el motor para que ningun endpoint futuro la saltee.

Tests:

- Interconsulta a area de otra institucion devuelve 400.
- Estudio derivado a area de otra institucion devuelve 400.

### Problema: subcaso cancelado bloquea retorno al padre

Regla funcional:

- Un caso padre espera solo subcasos abiertos/reales.
- Subcasos cerrados y cancelados no deben bloquear retorno.

Solucion propuesta:

- Cambiar la condicion de hermanos pendientes a:

```python
.exclude(estado__in=[Caso.Estado.CERRADO, Caso.Estado.CANCELADO])
```

Tests:

- Padre con dos subcasos: uno cancelado y otro cerrado retorna.
- Padre con un subcaso abierto no retorna.
- Cancelar ultimo subcaso retorna al padre si corresponde.

## 6. Agenda, disponibilidad, bloqueos y turnos

### Problema: agenda mezcla institucion, area, profesional y flujo

Regla funcional:

- Una agenda pertenece a una institucion.
- Su area debe ser de esa institucion.
- Su profesional, si existe, debe tener membresia activa en esa institucion.
- Si la agenda esta asociada a un area, el profesional deberia pertenecer a esa area o tener rol que habilite toda la institucion.
- Su flujo, si existe, debe ser de la misma institucion y compatible con el area.

Solucion propuesta:

- Agregar validacion en `AgendaSerializer.validate`.
- Exigir:

```text
area.institucion_id == institucion.id
flujo.institucion_id == institucion.id
flujo.area_id == area.id, si el flujo es de area
profesional con membresia activa en institucion
```

Decision pendiente:

- Definir si un profesional admin/medico institucional puede atender en cualquier area o solo en areas asignadas.

Tests:

- Agenda de Hospital A con area de Hospital B devuelve 400.
- Agenda con flujo de otra institucion devuelve 400.
- Agenda profesional con usuario sin membresia activa devuelve 400.
- Llegada de turno abre caso en institucion/area/flujo coherentes.

## 7. Internacion y camas

### Problema: cama configurada en sector incoherente

Regla funcional:

- La internacion opera sobre camas estructuralmente coherentes.
- El motor no deberia recibir una cama cuya area y sector se contradicen.

Solucion propuesta:

- Resolver en `CamaSerializer`, como regla de configuracion.
- Agregar chequeo defensivo en motor si se quiere mayor seguridad.

Tests:

- No se puede asignar cama con subarea ajena.
- Movimiento de cama entre sectores exige sector del mismo area.

## 8. Farmacia, stock, lotes y pedidos

### Problema: deposito con area de otra institucion

Regla funcional:

- Un deposito pertenece a una institucion.
- Si esta asociado a un area, el area debe pertenecer a la misma institucion.

Solucion propuesta:

- Agregar validacion en `DepositoSerializer.validate`.

Mensaje sugerido:

```text
El area del deposito pertenece a otra institucion.
```

Tests:

- Deposito de Hospital A con area de Hospital B devuelve 400.
- Deposito central sin area se acepta.

### Problema: entrega parcial cierra pedido como entregado

Regla funcional a definir:

- Una entrega menor al pedido puede significar:
  - **Cierre con faltante informado**, o
  - **Entrega parcial con saldo pendiente**.

Solucion recomendada:

- Si farmacia no hara entregas sucesivas: renombrar/logicar estado como `cerrado_con_faltante` o registrar `faltante_cerrado`.
- Si farmacia si hara entregas sucesivas: agregar estado `parcial` y cerrar como `entregado` solo cuando `sum(entregado) == sum(pedido_cant)`.

Regla sugerida para hospital:

- Usar tres estados:

```text
pendiente
parcial
entregado
rechazado
```

- Al entregar:
  - Si no se entrega nada: mantener pendiente o rechazar con motivo.
  - Si se entrega algo pero queda faltante: pasar a parcial.
  - Si todo queda cubierto: pasar a entregado.

Tests:

- Pedido 10, entrega 4 queda `parcial`.
- Pedido parcial acepta segunda entrega hasta completar.
- Pedido completado queda `entregado`.
- No se puede entregar mas que el faltante, no solo mas que lo pedido original.

## 9. Red sanitaria y traslados

### Problema: gobierno de redes ambiguo

Regla funcional:

- Una red sanitaria es una configuracion suprainstitucional.
- Un hospital no deberia decidir unilateralmente que otro hospital forma parte de su red.

Soluciones posibles:

- Opcion A: ABM de redes solo para rol estatal/plataforma.
- Opcion B: un hospital puede proponer red, pero los demas efectores deben aceptar pertenencia.
- Opcion C: redes se cargan desde autoridad regional y los hospitales solo las consultan.

Recomendacion:

- Para sistema estatal, usar opcion A o C.
- Crear capacidad `gobierno_red` o `plataforma`.
- Dejar `config` institucional para configuracion interna del efector.

Tests:

- Admin institucional no crea red con otros efectores.
- Rol estatal crea red con multiples instituciones.
- Hospital participante puede ver red, pero no modificar instituciones de la red.

### Problema: flujo receptor de traslado elegido por orden tecnico

Regla funcional:

- Al aceptar traslado, el destino debe abrir el caso en un flujo receptor definido.

Solucion propuesta:

- Reutilizar la solucion de flujos receptores:
  - flujo con inicio compatible con derivado/traslado,
  - o campo explicito `recibe_traslados`.
- Si hay mas de un receptor, `aceptar` debe recibir `flujo_destino_id`.

Tests:

- Area destino sin flujo receptor devuelve error claro.
- Area destino con un receptor abre caso.
- Area destino con dos receptores exige seleccion.

## 10. Registros clinicos, historia, estudios, recetas y consentimiento

### Riesgo residual: consentimiento con institucion del payload

Regla funcional:

- El consentimiento pertenece al ciudadano y a su institucion.
- La institucion no deberia ser una segunda verdad editable si ya se deriva del ciudadano.

Solucion propuesta:

- Hacer `institucion` read-only en `ConsentimientoDatosSerializer`, o
- Validar que si viene informada coincida con `ciudadano.institucion`.

Recomendacion:

- Preferir read-only y setear siempre desde `ciudadano.institucion`.

Tests:

- Consentimiento con ciudadano A e institucion B devuelve 400 o ignora institucion payload segun regla.
- Consentimiento sin institucion se guarda con institucion del ciudadano.

## 11. Auditoria y privacidad

### Estado: mantener regla actual

Regla funcional:

- La auditoria se escribe automaticamente.
- Nadie debe editar o borrar accesos clinicos desde API.
- La lectura de auditoria corresponde a conduccion, auditoria institucional o plataforma.
- Si falla el registro de auditoria, no se bloquea la atencion clinica, pero debe quedar log tecnico.

Solucion preventiva:

- Crear prueba de cobertura para nuevos endpoints clinicos.
- Mantener lista central de recursos sensibles.

Archivos clinicos - estado 2026-08-19:

- Implementado en Fase 7: la subida exige `institucion` y capacidad `historia_clinica`.
- Implementado en Fase 7: la descarga usa endpoint protegido y valida permiso sobre la institucion embebida en `uploads/<institucion>/...`.
- Implementado en Fase 7: `/media/uploads/...` queda bloqueado en desarrollo para adjuntos clinicos.
- Implementado en Fase 7: el frontend sube adjuntos con la institucion del caso y descarga estudios mediante `fetch` con token.
- Pendiente: metadatos persistentes de archivo, validacion MIME/tamanio, antivirus y migracion/ocultamiento de historicos servidos por `/media`.

Tests:

- Endpoint clinico nuevo sin auditoria falla test de cobertura.
- Medico sin rol de conduccion no puede listar auditoria.
- Archivo clinico sin institucion o con institucion inexistente devuelve 400; usuario sin `historia_clinica` devuelve 403; descarga desde otra institucion devuelve 403; `/media/uploads/...` devuelve 404.

## 12. Interoperabilidad FHIR

### Estado: mantener regla actual

Regla funcional:

- `metadata` puede ser publico porque no expone datos clinicos.
- Todo recurso clinico FHIR debe exigir autenticacion, capacidad equivalente a API interna y auditoria.
- Organization puede no auditarse si no contiene dato clinico de paciente.

Solucion preventiva:

- Al agregar recurso FHIR, exigir plantilla minima:
  - scope por instituciones del usuario,
  - capacidad requerida,
  - auditoria si toca paciente/caso/historia,
  - manejo de ids FHIR malformados.

Tests:

- Recurso FHIR nuevo niega usuario sin capacidad.
- Recurso FHIR clinico genera `AccesoClinico`.
- Id malformado no devuelve 500.

## 13. Tableros, supervision y metricas

### Problema: definicion no uniforme de caso activo

Regla funcional:

- `activo` debe significar lo mismo en todo el sistema.
- Propuesta: activo = no cerrado y no cancelado.

Solucion propuesta:

- Centralizar estados activos/no activos en modelo o helper.
- Usar el helper en:
  - metricas institucionales,
  - tablero institucional,
  - tablero de area,
  - conteo de flujos,
  - bloqueo de archivado,
  - red/saturacion si aplica.

Tests:

- Misma institucion, mismos casos: todos los endpoints devuelven el mismo activo.
- Caso cancelado no aparece en carga viva.
- Caso cerrado no aparece en carga viva.

## 14. Addendum del barrido profundo

Base ampliada: `docs/auditorias/barrido-completo-logica-config-uiux-2026-08-18.md`.

Este addendum suma reglas transversales detectadas despues del primer loop. No reemplaza los puntos anteriores: los vuelve mas estrictos donde el problema no es de un modulo aislado sino de frontera de dominio.

### 14.1. Mutaciones sanitarias solo por motor

Regla funcional:

- Un episodio asistencial no debe poder cambiar de estado, paso, cola, valores o timeline por CRUD generico.

Solucion propuesta:

- `CasoViewSet`: lectura + alta minima + acciones del motor.
- `ValorCampoViewSet`: read-only, o escritura solo mediante accion formal de correccion.
- `EventoCasoViewSet`: read-only; notas manuales por accion especifica con autor del servidor.
- `ItemFilaViewSet`: sin POST generico; la fila se crea al llegar al nodo por motor.

Tests:

- PATCH directo de `estado`, `nodo_actual`, `area_actual` o `asignado_a` no cambia el caso.
- POST/PATCH/DELETE directo de valores/eventos/fila devuelve 405 o 403.
- Los caminos validos por `iniciar`, `avanzar`, `llamar`, `devolver`, `ausente`, `cancelar` siguen dejando eventos.

### 14.2. FKs de alcance no se mueven por PATCH comun

Regla funcional:

- Si un FK define institucion, area, formulario, version, deposito, cama o grupo responsable, no debe poder cambiarse como una edicion comun.

Solucion propuesta:

- Marcar como read-only en update los FKs de scope.
- Revalidar destino institucional en `perform_update` para los casos donde el campo siga siendo editable.
- Crear acciones explicitas de mudanza solo cuando el negocio lo necesite.

Tests:

- Objeto de institucion A no puede apuntarse a padre de institucion B.
- Campo con valores no puede cambiar de formulario.
- Nodo no puede cambiar de version.
- Conexion no puede unir nodos de versiones distintas.

### 14.3. Capacidades por dominio sanitario

Regla funcional:

- `trabajo` y `registros` son demasiado amplias para operar hospitales y datos clinicos.

Solucion propuesta:

- Dividir capacidades en `padron_admision`, `historia_clinica`, `prescripcion`, `solicitud_estudios`, `turnos`, `casos_operar`, `filas`, `internacion`, `farmacia_stock`, `traslados_red`, `config_institucional`, `diseno_flujos`, `auditoria` y `gobierno_plataforma`.
- Exponer capacidades efectivas desde backend.
- El frontend no debe duplicar el mapa de roles.

Tests:

- Administrativo puede admitir/turnar sin leer historia completa.
- Farmacia mueve stock sin operar casos clinicos.
- Medico prescribe sin administrar usuarios.
- Jefe de area supervisa su area sin recibir permisos globales de farmacia o red.

### 14.4. Agenda y contexto institucional

Regla funcional:

- Un turno pertenece a una agenda, a un paciente y a una institucion coherentes.

Solucion propuesta:

- `TurnoViewSet.create` debe traer agenda y ciudadano acotados a la institucion autorizada.
- No usar `check_object_permissions` con objetos de modelo distinto al que describe `institucion_path`.
- Validar profesional, area y flujo de agenda contra la misma institucion.

Tests:

- Usuario de A no reserva en agenda de B.
- Agenda A con paciente B devuelve 400.
- Profesional sin membresia activa no queda asignado a agenda.

### 14.5. Gobierno de usuarios y staff

Regla funcional:

- `is_staff` y resets de password son gobierno de plataforma o administracion auditada, no edicion comun de usuario.

Solucion propuesta:

- `is_staff` read-only para admin institucional.
- Accion separada `reset-password` con auditoria, motivo y notificacion.

Tests:

- Admin institucional no puede activar `is_staff`.
- Reset de password queda auditado.

### 14.6. UI/UX autorizada por servidor

Regla funcional:

- El menu no alcanza como control de acceso UX. Cada ruta debe saber su capacidad requerida.

Solucion propuesta:

- Agregar `RequireCap`.
- Usar capacidades efectivas devueltas por backend.
- Validar institucion guardada contra el usuario actual.
- Ocultar o degradar el buscador de pacientes segun permiso.
- Aplicar lazy loading por rutas pesadas.

Tests:

- URL directa a una seccion sin permiso muestra acceso denegado sin disparar consultas sensibles.
- Cambio de usuario limpia institucion local no autorizada.
- Build mantiene auditor de clases limpio.

### 14.7. Configuracion sensible

Regla funcional:

- Backups, dumps y media clinica no viven ni se sirven como archivos publicos del repositorio.

Solucion propuesta:

- Remover el dump `.sql.gz` versionado y limpiar historial si contiene datos.
- Agregar ignore para dumps y temporales.
- Usar storage privado o endpoint autenticado para archivos clinicos. Fase 7 implemento endpoint protegido para nuevas subidas/descargas clinicas.
- Revisar y eliminar la carpeta duplicada `backend/backend` si no tiene uso real.

Tests:

- `git ls-files` no lista dumps SQL ni carpetas duplicadas accidentales.
- Archivo clinico se descarga solo por endpoint autenticado y autorizado.

## Orden de implementacion recomendado

1. **Frontera institucional en motor de casos y derivaciones.** Es lo mas sensible: evita cruces asistenciales fuera de red.
2. **Validaciones de flujos/nodos/conexiones.** Evita que el diseno cree grafos imposibles o peligrosos.
3. **Validaciones de configuracion institucional.** Membresias, camas, depositos y agendas.
4. **Subcasos cancelados.** Bug puntual de continuidad asistencial.
5. **Caso activo unico.** Corrige metricas y decisiones de archivado.
6. **Gobierno estatal/plataforma.** Instituciones, redes y legajos.
7. **Farmacia parcial.** Requiere decision funcional antes del codigo.
8. **Archivos clinicos protegidos.** Mitigado en Fase 7 para nuevas subidas/descargas; quedan politicas avanzadas de archivo.

## Criterio de aceptacion global

Una solucion se considera cerrada cuando:

- La regla esta implementada en el backend, preferentemente en serializer/motor y no solo en la UI.
- Existe test para API directa, no solo flujo de pantalla.
- El mensaje de error es entendible por usuario funcional.
- La documentacion de la funcionalidad queda actualizada.
- No rompe los caminos validos existentes: misma institucion, misma area, flujo compatible, rol autorizado.
