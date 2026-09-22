# Auditoria iterativa de logica por funcionalidad

Fecha: 2026-08-18  
Foco: errores de logica funcional en modulos del sistema de salud, gestion hospitalaria y gestion estatal.  
Alcance: documentacion funcional existente y codigo backend. No reemplaza los documentos de capacitacion.

## Criterio de lectura

Esta pasada busca inconsistencias de negocio: pertenencia institucional, estados imposibles, permisos que no representan responsabilidad real, conteos que cambian el significado del dato, y caminos alternativos que saltean reglas del motor.

Prioridades:

- **Critica**: puede cruzar datos/operacion entre instituciones, romper continuidad asistencial o dejar casos bloqueados.
- **Alta**: genera datos operativos falsos, stock incorrecto, agenda/camas inconsistentes o permisos demasiado amplios.
- **Media**: ambiguedad funcional, metrica confusa o deuda de validacion con impacto acotado.
- **Baja**: mejora preventiva o prueba faltante sin bug confirmado.

## Resumen ejecutivo

El sistema tiene buenas defensas en historia clinica, auditoria, FHIR, agenda de turnos y varios motores operativos: hay reglas explicitas, estados read-only y acciones de dominio. El patron de riesgo aparece en configuraciones que aceptan referencias por id sin validar la frontera institucional: membresias con areas ajenas, camas con sectores ajenos, flujos/nodos/conexiones cruzados, agendas con area/profesional/flujo de otra institucion, y derivaciones internas a otra institucion.

Los hallazgos mas urgentes son:

- Derivaciones internas y subprocesos pueden apuntar a areas/flujos de otra institucion.
- Conexiones y nodos de flujo pueden mezclar versiones, formularios o grupos que no pertenecen al mismo flujo/institucion.
- La cancelacion de un subcaso puede dejar al caso padre esperando para siempre.
- Membresias y camas aceptan relaciones M2M/FK institucionalmente incoherentes.
- Redes e instituciones tienen un modelo de gobierno estatal ambiguo: el codigo las describe como configuracion de plataforma, pero el permiso `config` puede quedar en manos institucionales.

## Loop por funcionalidad

### 1. Identidad, usuarios, membresias y roles

Archivos revisados:

- `backend/apps/accounts/serializers.py`
- `backend/apps/accounts/views.py`
- `backend/apps/common.py`

Hallazgos:

- **Alta - membresia con areas de otra institucion.** `MembresiaSerializer` expone `institucion` y `areas` sin `validate`; se observa en `backend/apps/accounts/serializers.py:12` y `backend/apps/accounts/serializers.py:27`. El viewset se scopea por `institucion` (`backend/apps/accounts/views.py:143`), pero eso solo valida la institucion principal de la membresia. Una API directa podria crear una membresia del Hospital A con areas del Hospital B. Impacto: permisos por area, grupos, filas y filtros pueden asignar responsabilidad asistencial cruzada.

- **Alta - legajo profesional sin institucion_path.** `LegajoProfesionalViewSet` declara `capacidad_requerida = "config"` pero no `institucion_path` (`backend/apps/accounts/views.py:151` a `backend/apps/accounts/views.py:163`). Como el legajo no esta atado a una institucion concreta, un admin institucional puede gestionar datos profesionales globales si tiene `config` en alguna institucion. Puede ser intencional si el legajo es unico nacional, pero requiere regla funcional explicita.

Recomendacion:

- Validar que todas las `areas` de una membresia pertenezcan a `institucion`.
- Definir si `LegajoProfesional` es global, provincial o institucional. Si es institucional, agregar FK/scope. Si es global, limitar escritura a plataforma/estado.

Pruebas sugeridas:

- Crear membresia A con area B devuelve 400.
- Usuario con `config` en A no modifica legajo global si no es superusuario o rol estatal definido.

### 2. Estructura institucional, areas, subareas, grupos, boxes y camas

Archivos revisados:

- `backend/apps/instituciones/serializers.py`
- `backend/apps/instituciones/views.py`
- `backend/apps/common.py`

Hallazgos:

- **Critica/Alta - camas con subarea ajena al area.** `CamaSerializer` expone `area` y `subarea` (`backend/apps/instituciones/serializers.py:85` y `backend/apps/instituciones/serializers.py:96`) sin validar que `subarea.area_id == area.id`. El viewset se autoriza por `area__institucion` (`backend/apps/instituciones/views.py:554` a `backend/apps/instituciones/views.py:568`), pero el sector puede pertenecer a otra area o institucion. Impacto: tablero de camas, ocupacion por sector e internacion pueden mostrar una cama del area A dentro del sector B.

- **Media - metrica rapida de institucion cuenta cancelados como activos.** `metricas` usa `.exclude(estado=Caso.Estado.CERRADO)` (`backend/apps/instituciones/views.py:105`), mientras el tablero usa correctamente `~Q(estado__in=[CERRADO, CANCELADO])` (`backend/apps/instituciones/views.py:130`). Impacto: la tarjeta rapida puede inflar carga activa.

  Estado 2026-08-19: corregido en Fase 5. `metricas` usa `Caso.ESTADOS_FINALIZADOS` y se agrego test de regresion.

- **Alta - alta de instituciones puede quedar disponible para admins institucionales.** `InstitucionViewSet` usa `capacidad_requerida = "config"` e `institucion_path = "id"` (`backend/apps/instituciones/views.py:85` a `backend/apps/instituciones/views.py:89`). En create, `_institucion_de_payload` devuelve `None` para `path == "id"` (`backend/apps/common.py:69` a `backend/apps/common.py:72`), y el permiso queda como "tener config en alguna membresia". Si crear efectores es funcion estatal/plataforma, esta puerta es demasiado amplia.

Sin falla fuerte detectada:

- `GrupoSerializer` valida que sus miembros pertenezcan al area del grupo (`backend/apps/instituciones/serializers.py:39` a `backend/apps/instituciones/serializers.py:55`).
- `BoxViewSet` separa configuracion de ocupacion/liberacion y valida quien libera.

Recomendacion:

- Agregar `validate` en `CamaSerializer`.
- Unificar definicion de "activo" excluyendo `CANCELADO` en metricas.
- Separar capacidad de plataforma/estado para crear instituciones.

Pruebas sugeridas:

- Crear cama de area A con subarea B devuelve 400.
- `metricas.casos_activos` no cuenta cancelados.
- Admin institucional no crea institucion si no tiene rol estatal/plataforma.

### 3. Formularios dinamicos

Archivos revisados:

- `backend/apps/formularios/serializers.py`
- `backend/apps/formularios/views.py`

Hallazgos:

- **Sin bug critico confirmado.** `FormularioSerializer` valida que el area pertenezca a la institucion (`backend/apps/formularios/serializers.py:127` a `backend/apps/formularios/serializers.py:135`).

Riesgo residual:

- Campos de formulario dependen de `formulario__institucion` en el viewset, lo cual esta bien para create si el formulario se resuelve correctamente. Mantener pruebas de payload con formulario ajeno.

Pruebas sugeridas:

- Crear formulario de institucion A con area B devuelve 400.
- Crear campo en formulario de otra institucion devuelve 403.

### 4. Diseno de flujos, versiones, nodos y conexiones

Archivos revisados:

- `backend/apps/flujos/serializers.py`
- `backend/apps/flujos/views.py`
- `backend/apps/casos/motor.py`

Hallazgos:

- **Critica - conexiones pueden mezclar versiones.** `ConexionSerializer` expone `version`, `origen` y `destino` sin validar que origen y destino pertenezcan a la misma version (`backend/apps/flujos/serializers.py:50`). La proteccion sobre borrador controla la version editada, no garantiza que los endpoints sean de esa version. Impacto: grafo inconsistente, avance a nodo externo y publicacion visualmente valida pero logicamente rota.

- **Critica - nodos pueden referenciar formularios/grupos de otra institucion.** `NodoSerializer` expone `formulario`, `grupos` y `config` sin validacion institucional (`backend/apps/flujos/serializers.py:28`). Impacto: un paso de flujo puede pedir un formulario ajeno, asignar responsables de otra area o guardar `area_destino_id`/`flujo_destino_id` cruzados.

- **Alta - flujo puede tener area ajena a institucion.** `FlujoSerializer.validate` solo comprueba coherencia entre `subarea` y `area` (`backend/apps/flujos/serializers.py:132` a `backend/apps/flujos/serializers.py:137`), pero no que `area.institucion_id == institucion.id`. Impacto: flujo registrado en institucion A pero ejecutado con area B.

- **Media - conteo de casos activos en flujos incluye cancelados.** `get_casos_activos` excluye solo cerrados (`backend/apps/flujos/serializers.py:153` a `backend/apps/flujos/serializers.py:161`), y el bloqueo de archivado tambien excluye solo cerrados (`backend/apps/flujos/views.py:350`). Impacto: flujos con casos cancelados pueden parecer activos o no archivables.

Recomendacion:

- Validar en serializers la pertenencia de version, nodos, formulario, grupos, area, subarea e institucion.
- Excluir `CANCELADO` de conteos y bloqueo de archivado si funcionalmente cancelado equivale a no activo.
- Agregar validacion de `config` por tipo de nodo, especialmente `derivar`.

Pruebas sugeridas:

- Conexion con `origen.version != version` devuelve 400.
- Nodo con formulario de otra institucion devuelve 400.
- Flujo con area de otra institucion devuelve 400.
- Flujo con solo casos cancelados se puede archivar si esa es la regla esperada.

### 5. Casos, motor asistencial, filas y derivaciones internas

Archivos revisados:

- `backend/apps/casos/motor.py`
- `backend/apps/casos/views.py`

Hallazgos:

- **Critica - derivacion interna puede cruzar instituciones.** En el nodo `derivar`, el motor lee `area_destino_id` (`backend/apps/casos/motor.py:642`) y `flujo_destino_id` (`backend/apps/casos/motor.py:653` a `backend/apps/casos/motor.py:658`) sin comprobar que pertenezcan a la misma institucion del caso. Impacto: un caso de un efector puede pasar a un area/flujo de otro efector sin pasar por traslado/red.

  Estado 2026-08-19: corregido en Fase 5. El motor valida area y flujo destino contra la institucion del caso y falla la transaccion si la configuracion cruza efectores.

- **Critica - estudio derivado e interconsulta pueden cruzar instituciones.** Las acciones de vista toman `Area.objects.filter(pk=area_id).first()` (`backend/apps/casos/views.py:344` y `backend/apps/casos/views.py:366`) y luego llaman al motor (`backend/apps/casos/views.py:347`, `backend/apps/casos/views.py:370`). `_derivar_subproceso` busca flujo publicado del area destino (`backend/apps/casos/motor.py:1129` a `backend/apps/casos/motor.py:1130`) sin validar institucion. Impacto: subcasos clinicos cruzados fuera del circuito de red.

  Estado 2026-08-19: corregido en Fase 5. Estudios derivados e interconsultas usan `version_receptora_para_area(area, institucion=caso.institucion)`.

- **Critica - subcaso cancelado puede bloquear retorno del caso padre.** `_retornar_al_origen` verifica hermanos pendientes con `.exclude(pk=sub.pk).exclude(estado=Caso.Estado.CERRADO).exists()` (`backend/apps/casos/motor.py:1182`). En cambio `cancelar_caso` usa correctamente `.exclude(estado__in=[CERRADO, CANCELADO])` (`backend/apps/casos/motor.py:1221`). Si un padre espera dos subprocesos, se cancela uno y se cierra el otro, el cancelado sigue contando como pendiente y el padre puede quedar en espera permanente.

  Estado 2026-08-19: corregido en Fase 5. `_retornar_al_origen` excluye `Caso.ESTADOS_FINALIZADOS` y hay test con un subcaso cancelado y otro cerrado.

- **Alta - receptor de subproceso elegido por orden tecnico.** `_derivar_subproceso` elige version publicada con `.order_by("-flujo_id", "-numero").first()` (`backend/apps/casos/motor.py:1129` a `backend/apps/casos/motor.py:1130`). Si un area tiene mas de un flujo publicado, no hay criterio funcional de recepcion.

  Estado 2026-08-19: corregido en Fase 5. El area receptora debe tener exactamente un flujo publicado cuyo Inicio acepte `derivado` o `ambos`.

Sin falla fuerte detectada:

- Las operaciones de cama dentro del motor validan estado y pertenencia antes de asignar, mover o liberar.
- Hay protecciones para filas, box y estados finales.

Recomendacion:

- En toda derivacion interna exigir `area_destino.institucion_id == caso.institucion_id`.
- Si hay `flujo_destino_id`, exigir que sea de la misma institucion y que acepte origen derivado.
- En retorno al padre, excluir `CANCELADO`.
- Definir una unica regla de "flujo receptor" por area: bandera explicita, tipo de inicio, prioridad o seleccion obligatoria.

Pruebas sugeridas:

- Nodo derivar a area de otra institucion devuelve error.
- Interconsulta/estudio a area de otra institucion devuelve error.
- Cancelar un subcaso no bloquea retorno del padre cuando los demas estan cerrados/cancelados.
- Area con dos flujos publicados no se elige por id tecnico sin criterio funcional.

### 6. Agenda, disponibilidad, bloqueos y turnos

Archivos revisados:

- `backend/apps/agenda/serializers.py`
- `backend/apps/agenda/views.py`
- `backend/apps/agenda/motor.py`

Hallazgos:

- **Alta - agenda puede mezclar institucion, area, profesional y flujo.** `AgendaSerializer.validate` solo valida coherencia tipo/profesional y modalidad (`backend/apps/agenda/serializers.py:100` a `backend/apps/agenda/serializers.py:116`). No valida que `area.institucion_id == institucion.id`, que el `flujo` pertenezca a la misma institucion/area, ni que el profesional tenga membresia activa en esa institucion/area. El motor de llegada usa esos datos para abrir caso (`backend/apps/agenda/motor.py:413` a `backend/apps/agenda/motor.py:428`). Impacto: un turno de la institucion A puede abrir caso con area/flujo/profesional de B.

Sin falla fuerte detectada:

- `TurnoSerializer` hace read-only los campos que deben pasar por motor: estado, agenda, ciudadano, inicio, modalidad y enlace.
- `DisponibilidadSerializer` valida franjas superpuestas y cupos.

Recomendacion:

- Agregar validacion institucional en `AgendaSerializer`.
- Si la agenda es profesional, exigir membresia activa y, si aplica, area asignada.
- Si tiene flujo, exigir flujo publicado compatible con esa agenda/area.

Pruebas sugeridas:

- Agenda de institucion A con area B devuelve 400.
- Agenda profesional con usuario sin membresia activa devuelve 400.
- Agenda con flujo de otra institucion devuelve 400.

### 7. Internacion y gestion de camas

Archivos revisados:

- `backend/apps/casos/motor.py`
- `backend/apps/instituciones/serializers.py`
- `backend/apps/instituciones/views.py`

Hallazgos:

- **Alta - configuracion de cama con sector incoherente.** Es el mismo hallazgo de estructura, pero su impacto operativo cae en internacion: la cama puede ser asignable como del area A y tabulada como sector B.

Sin falla fuerte detectada:

- Las acciones operativas del motor para asignar, pasar de sector y dar alta validan estados y pertenencia institucional.
- `CamaViewSet.estado` evita liberar una cama ocupada por PATCH y deriva cambios al motor.

Recomendacion:

- Corregir `CamaSerializer` y agregar prueba de internacion para sector ajeno.

Pruebas sugeridas:

- Cama con subarea de otra area no se crea.
- Asignacion de cama de otra institucion falla.
- Alta de cama deja estadia cerrada y cama en higiene/libre segun regla.

### 8. Farmacia, stock, lotes y pedidos

Archivos revisados:

- `backend/apps/farmacia/serializers.py`
- `backend/apps/farmacia/motor.py`

Hallazgos:

- **Alta - deposito puede asociar area de otra institucion.** `DepositoSerializer` expone `institucion` y `area` (`backend/apps/farmacia/serializers.py:23` a `backend/apps/farmacia/serializers.py:27`) sin validar que `area.institucion_id == institucion.id`. Impacto: stock de un hospital puede aparecer asociado al botiquin/area de otro.

- **Media/Alta - entrega parcial cierra pedido siempre.** `entregar_pedido` permite entregar menos que lo pedido, acumula `linea.entregado` (`backend/apps/farmacia/motor.py:340` a `backend/apps/farmacia/motor.py:351`), pero luego marca siempre `pedido.estado = ENTREGADO` (`backend/apps/farmacia/motor.py:354`). Si "entregado" significa cierre con faltante registrado, esta bien pero el nombre de estado deberia reflejar cierre parcial. Si se esperan entregas sucesivas, es bug porque cierra el pedido antes de completar.

  Estado 2026-08-19: corregido en Fase 6. Se agrego estado `parcial`, la entrega incompleta mantiene el pedido abierto y la segunda entrega puede completar el faltante.

Sin falla fuerte detectada:

- `PedidoSerializer` valida origen/destino misma institucion y renglones con insumos propios.
- `transferir`, `consumir`, `baja` y lotes tienen validaciones de stock, vencimiento, controlados y trazabilidad.

Recomendacion:

- Agregar `validate` en `DepositoSerializer`.
- Decidir estado funcional para entregas parciales: `parcial`, `cerrado_con_faltante` o permitir reentregas hasta completar. Cubierto en Fase 6 con estado `parcial` y reentregas hasta completar.

Pruebas sugeridas:

- Deposito de institucion A con area B devuelve 400.
- Pedido de 10 con entrega 4 queda en estado esperado y muestra faltante 6.
- Intentar una segunda entrega sobre pedido parcial se comporta segun regla definida.

### 9. Red sanitaria, traslados y tablero de red

Archivos revisados:

- `backend/apps/red/serializers.py`
- `backend/apps/red/views.py`
- `backend/apps/red/motor.py`

Hallazgos:

- **Alta - gobierno de redes ambiguo.** `RedViewSet` documenta que las redes son configuracion de plataforma, pero usa `capacidad_requerida = "config"` (`backend/apps/red/views.py:16` a `backend/apps/red/views.py:30`). `RedSerializer` expone `instituciones` sin validacion adicional (`backend/apps/red/serializers.py:6` a `backend/apps/red/serializers.py:16`). Un usuario con configuracion institucional podria crear/modificar una red que incluye efectores ajenos, si el producto no reserva esto a un rol estatal.

- **Alta - flujo receptor de traslado elegido por orden tecnico.** Al aceptar un traslado, el motor elige version publicada del area con `.order_by("-flujo_id", "-numero").first()` (`backend/apps/red/motor.py:214` a `backend/apps/red/motor.py:233`). Si hay mas de un flujo publicado en el area, el destino operativo queda determinado por ids.

  Estado 2026-08-19: corregido en Fase 5. `aceptar` usa el mismo selector funcional de flujo receptor que estudios/interconsultas.

Sin falla fuerte detectada:

- `solicitar` valida que el destino este en red, caso cerrado/cancelado, area destino del destino y capacidades del lado origen.
- Las acciones `aceptar`, `rechazar`, `cancelar`, `en_camino`, `recibido` y `no_llego` validan lado operativo y capacidad por institucion.

Recomendacion:

- Definir rol estatal/plataforma para ABM de redes o limitar edicion a redes donde la institucion tenga autoridad.
- Hacer explicito el flujo receptor de traslado.

Pruebas sugeridas:

- Admin de hospital A no crea red incluyendo hospital B si no tiene rol estatal.
- Aceptar traslado hacia area con dos flujos publicados exige seleccion o usa flujo marcado como receptor.

### 10. Registros clinicos, historia, estudios, recetas y consentimiento

Archivos revisados:

- `backend/apps/registros/serializers.py`
- `backend/apps/registros/views.py`

Hallazgos:

- **Sin bug critico confirmado en esta pasada.** El modulo tiene defensas fuertes: historia no cambia de ciudadano, entradas firmadas no se editan, autor sale de sesion, recetas no se editan por PATCH, suspensiones dejan asiento, consentimiento se agrega y no se edita.

Riesgo residual:

- `ConsentimientoDatosSerializer` expone `institucion`, pero `ConsentimientoDatosViewSet` se scopea por `ciudadano__institucion` y en create rellena institucion si falta. Conviene validar que si `institucion` viene en payload coincida con `ciudadano.institucion`, para evitar doble verdad.
- Archivos clinicos: mitigado en Fase 7 para nuevas subidas. `SubirArchivoView` exige institucion existente y `historia_clinica`; `DescargarArchivoView` sirve solo por endpoint protegido y con permiso en la institucion embebida en la ruta; `/media/uploads/...` queda bloqueado en desarrollo. Quedan metadatos persistentes, MIME/tamanio, antivirus y tratamiento de historicos bajo `/media`.

Pruebas sugeridas:

- Consentimiento para ciudadano A con institucion B devuelve 400 o ignora institucion del payload de forma explicita.
- Entrada/estudio/receta sobre historia de otra institucion devuelve 403.
- Subida de archivo sin institucion o con institucion inexistente devuelve 400; usuario sin `historia_clinica` devuelve 403; descarga desde otra institucion devuelve 403; `/media/uploads/...` devuelve 404.

### 11. Auditoria y privacidad

Archivos revisados:

- `backend/apps/auditoria/views.py`
- `backend/apps/auditoria/mixins.py`

Hallazgos:

- **Sin bug critico confirmado.** Auditoria esta planteada como escritura automatica del sistema, con lectura restringida a conduccion y superusuario. Hay proteccion para que una falla de auditoria no bloquee atencion clinica, decision funcional razonable en guardia.

Riesgo residual:

- Mantener tests que garanticen que nuevos endpoints clinicos usan `AuditaLecturaClinica` o `registrar_acceso`.

Pruebas sugeridas:

- Un medico sin rol de conduccion no lista accesos clinicos.
- Todo nuevo endpoint clinico sensible genera acceso auditable.

### 12. Interoperabilidad FHIR

Archivos revisados:

- `backend/apps/fhir/views.py`
- `backend/apps/fhir/tests.py`

Hallazgos:

- **Sin bug critico confirmado.** `metadata` es publico a proposito (`backend/apps/fhir/views.py:201` a `backend/apps/fhir/views.py:209`) y los recursos clinicos requieren autenticacion y capacidad (`backend/apps/fhir/views.py:308`, `backend/apps/fhir/views.py:349`, `backend/apps/fhir/views.py:426`, `backend/apps/fhir/views.py:446`). Las pruebas incluyen restricciones por capacidad y auditoria.

Riesgo residual:

- Si se agregan nuevos recursos FHIR, deben heredar el mismo patron: scope por instituciones del usuario, capacidad equivalente a API interna y auditoria si hay dato clinico.

Pruebas sugeridas:

- Repetir test de cobertura de capacidad para cada nuevo recurso FHIR.
- Verificar que busquedas por id malformado devuelven 400/404 controlado, no 500.

### 13. Tableros, supervision y metricas

Archivos revisados:

- `backend/apps/instituciones/views.py`
- `backend/apps/red/motor.py`
- `backend/apps/flujos/views.py`
- `backend/apps/flujos/serializers.py`

Hallazgos:

- **Media - definicion no uniforme de activo.** Tableros principales excluyen cancelados, pero metricas rapidas y conteos de flujo excluyen solo cerrados. Impacto: diferencias entre tarjetas, tablero y restricciones de archivado.

  Estado 2026-08-19: corregido en Fase 5. Flujos, archivo de version publicada y metricas rapidas usan `Caso.ESTADOS_FINALIZADOS`.

- **Baja/Media - decisiones de atribucion estan bien documentadas pero requieren tests de regresion.** Los tableros distinguen `area_actual` para carga viva y `version__flujo__area` para produccion historica. Es correcto y valioso, pero fragil si se toca.

Recomendacion:

- Crear helper comun `Caso.activos()` o constante de estados activos para evitar divergencias.
- Agregar tests que comparen metricas de institucion, area y flujos con casos cancelados.

Pruebas sugeridas:

- Un caso cancelado no aparece como activo en ninguna metrica.
- Un caso derivado mantiene produccion historica en el area del flujo original.

## Matriz de correccion sugerida

Orden recomendado:

1. **Frontera institucional en derivaciones y subprocesos**: `casos/motor.py`, `casos/views.py`.
2. **Integridad de grafo de flujos**: `flujos/serializers.py` y publicacion.
3. **Validaciones institucionales de configuracion**: membresias, camas, depositos, agendas.
4. **Subcasos cancelados y retorno al padre**: `_retornar_al_origen`.
5. **Definicion unica de activo**: tableros, flujos, metricas.
6. **Gobierno estatal/plataforma**: crear instituciones y redes.
7. **Estados de entrega parcial en farmacia**. Cerrado en Fase 6.
8. **Archivos clinicos protegidos**. Cerrado/mitigado en Fase 7 para nuevas subidas y descargas.

## Resultado de verificacion

Se intento ejecutar tests del backend con el interprete del entorno virtual:

- `.venv\Scripts\python.exe manage.py test apps.farmacia apps.casos apps.red apps.auditoria --noinput`

La corrida no termino dentro del tiempo disponible de la herramienta. Por eso esta auditoria queda como analisis estatico con evidencias de codigo; los fixes deben acompaniarse con pruebas unitarias/regresion por cada hallazgo critico.
