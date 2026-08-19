# Roles, responsabilidades y permisos

Actualizado: 2026-08-18

Este documento describe el modelo funcional de autoridad de Cauce: que roles existen, donde interactuan, que responsabilidades tienen, que funcionalidades habilitan y cuales son sus limites. No es un manual de capacitacion; es una especificacion funcional para analisis, implementacion, auditoria y gobierno del sistema.

## 1. Principio general

Cauce separa tres conceptos que en hospitales suelen mezclarse:

- Usuario: la persona que inicia sesion.
- Membresia: la relacion de esa persona con una institucion, con uno o mas roles y areas.
- Grupo de trabajo: el equipo operativo que puede tomar un paso concreto del flujo.

Regla funcional:

- El rol define que tipo de puertas abre el sistema.
- La institucion define en que establecimiento aplica.
- El area acota donde cumple funciones.
- El grupo define que pasos concretos del flujo puede operar.

Ejemplo: una persona puede ser medica en Guardia del Hospital A, jefa de area en Internacion del Hospital B y no tener ningun permiso en otro establecimiento.

## 2. Roles vigentes

### Superusuario de plataforma

No es una membresia institucional. Es un usuario tecnico/global con `is_superuser=True`.

Responsabilidades:

- Administrar la plataforma completa.
- Entrar a cualquier institucion.
- Ver el sistema como rol operativo para probar experiencias.
- Resolver soporte, configuracion inicial o contingencias de alto nivel.

Alcance:

- Tiene acceso total.
- Debe usarse solo para administracion de plataforma, soporte o auditoria tecnica.
- No representa un rol hospitalario cotidiano.

Riesgos:

- Puede atravesar todos los limites institucionales.
- Requiere controles fuertes de credenciales, trazabilidad y uso excepcional.

### Admin de institucion

Rol de conduccion institucional amplia.

Responsabilidades:

- Administrar usuarios, membresias, areas y estructura.
- Configurar flujos, formularios, agendas y recursos institucionales.
- Supervisar operacion.
- Auditar accesos clinicos.
- Operar si la institucion lo decide, aunque funcionalmente deberia delegar operacion diaria.

Funcionalidades:

- Estructura organizativa.
- Administracion de usuarios y roles.
- Diseno de flujos y formularios.
- Trabajo operativo.
- Historia clinica y legajos.
- Supervision y tablero.
- Registro de accesos.

Limites:

- Su alcance es la institucion donde tiene membresia activa.
- Si tiene varias membresias, sus permisos se calculan por institucion.

### Configurador

Rol de analisis/configuracion de procesos.

Responsabilidades:

- Diseñar circuitos de atencion.
- Crear y mantener formularios.
- Configurar flujos, nodos, conexiones, reglas, derivaciones y validaciones.
- Probar flujos antes de publicarlos.
- Mantener consistencia entre estructura, formularios y flujos.

Funcionalidades:

- Flujos.
- Mapa de flujos.
- Formularios.
- Editor visual.
- Ensayo/publicacion/versionado de flujos.

Limites:

- No administra usuarios ni estructura institucional, salvo que tambien tenga otro rol.
- No opera casos.
- No accede a historia clinica por este rol.
- No audita accesos.

### Jefe / Supervisor de area

Rol de conduccion operativa por area.

Responsabilidades:

- Supervisar casos de su area.
- Detectar demoras, esperas vencidas y saturacion.
- Reasignar casos a integrantes habilitados.
- Cambiar prioridad cuando corresponda.
- Cancelar casos con motivo.
- Auditar accesos clinicos en instituciones donde ejerce conduccion.
- Ordenar la operacion sin reemplazar necesariamente al profesional tratante.

Funcionalidades:

- Mi trabajo, bandeja, filas y casos.
- Historia clinica.
- Supervision.
- Tablero.
- Registro de accesos.
- Agenda, internacion, farmacia y red si el modulo esta gateado por trabajo.

Limites:

- La supervision se valida contra el area del caso.
- Reasignar exige que el destinatario tenga membresia activa y pueda tomar el paso actual.
- Audita como rol de conduccion, no como medico tratante.
- No configura estructura, usuarios, flujos ni formularios, salvo que tenga otro rol adicional.

### Administrativo

Rol de admision, mostrador y gestion operativa no clinica.

Responsabilidades:

- Registrar o buscar pacientes.
- Iniciar circuitos administrativos.
- Gestionar turnos, presencia, cancelaciones y ausencias.
- Operar filas y llamados si pertenece al grupo responsable.
- Acompañar derivaciones administrativas.
- Consultar historia clinica cuando el flujo operativo lo requiere y la institucion lo habilita por permisos.

Funcionalidades:

- Mi trabajo.
- Bandeja.
- Filas.
- Casos.
- Agenda y turnos.
- Historia clinica y busqueda de ciudadanos.
- Red y traslados como operador del establecimiento.
- Farmacia/internacion solo si la organizacion lo usa como rol operativo general y el usuario integra los grupos adecuados.

Limites:

- No firma atenciones medicas.
- No audita accesos clinicos.
- No diseña flujos ni formularios.
- No administra usuarios ni estructura.
- Puede quedar limitado por grupos responsables del nodo.

### Enfermeria

Rol asistencial operativo.

Responsabilidades:

- Realizar triage.
- Completar formularios de enfermeria.
- Operar filas y llamados.
- Registrar intervenciones asistenciales permitidas.
- Gestionar internacion, camas o insumos cuando el proceso lo requiera.
- Solicitar o registrar estudios/acciones segun flujo.

Funcionalidades:

- Mi trabajo.
- Bandeja.
- Filas.
- Casos.
- Historia clinica.
- Internacion y camas.
- Farmacia e insumos si participa del circuito.
- Agenda/red cuando la institucion lo organiza como tarea de trabajo.

Limites:

- Opera por grupo responsable.
- No firma atenciones configuradas para firma medica si el nodo exige rol medico.
- No audita accesos clinicos.
- No configura usuarios, estructura, flujos ni formularios.

### Medico / profesional

Rol asistencial profesional.

Responsabilidades:

- Atender casos asignados o tomables por su grupo.
- Firmar atenciones cuando el nodo lo habilita.
- Registrar evolucion, conducta, estudios y recetas.
- Consultar historia clinica.
- Tomar decisiones clinicas y derivar segun flujo.
- Participar en interconsultas y especialidades.

Funcionalidades:

- Mi trabajo.
- Bandeja.
- Filas.
- Casos.
- Historia clinica.
- Estudios y recetas.
- Interconsultas.
- Internacion, red o farmacia cuando el flujo lo vincula.

Limites:

- No audita a colegas.
- No supervisa casos de area, salvo que tambien sea jefe de area.
- No diseña flujos/formularios.
- No administra usuarios ni estructura.
- Debe integrar el grupo responsable cuando el nodo lo exige.

## 3. Capacidades del sistema

Las capacidades son permisos funcionales que habilitan bloques de la aplicacion. Los roles otorgan una o mas capacidades.

| Capacidad | Que habilita | Observacion |
|---|---|---|
| `config` | Estructura organizativa, usuarios, membresias, areas, boxes, camas, agendas base | Administracion institucional |
| `diseno` | Flujos, versiones, nodos, conexiones, formularios, campos | Configuracion de procesos |
| `trabajo` | Casos, filas, agenda operativa, farmacia, red, internacion y acciones de proceso | Operacion diaria |
| `registros` | Ciudadanos, historia clinica, entradas, estudios, recetas, consentimientos | Datos clinicos protegidos |
| `supervision` | Tablero, supervision, reasignacion, prioridad y cancelacion de casos | Conduccion por area |
| `auditoria` | Registro de accesos clinicos | En backend se resuelve por regla especifica: admin y jefe de area |

## 4. Matriz rol-capacidad

| Rol | config | diseno | trabajo | registros | supervision | auditoria |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Superusuario plataforma | Si | Si | Si | Si | Si | Si |
| Admin institucion | Si | Si | Si | Si | Si | Si |
| Configurador | No | Si | No | No | No | No |
| Jefe / Supervisor de area | No | No | Si | Si | Si | Si |
| Administrativo | No | No | Si | Si | No | No |
| Enfermeria | No | No | Si | Si | No | No |
| Medico / profesional | No | No | Si | Si | No | No |

Nota tecnica: en backend `auditoria` no forma parte de `ROL_CAPACIDADES`; se implementa con `PuedeAuditar`, que permite superusuario, admin y jefe de area. En frontend se refleja como capacidad de menu para no ofrecer pantallas que luego responderian 403.

## 5. Matriz por funcionalidad

| Funcionalidad | Admin | Configurador | Jefe area | Administrativo | Enfermeria | Medico |
|---|---|---|---|---|---|---|
| Seleccionar institucion | Si | Si | Si | Si | Si | Si |
| Administrar usuarios/membresias | Si | No | No | No | No | No |
| Configurar areas/subareas/grupos | Si | No | No | No | No | No |
| Configurar boxes/camas | Si | No | No | No | No | No |
| Cambiar estado operativo de cama | Si | No | Si | Si | Si | Si |
| Crear agendas y disponibilidades | Si | No | No | No | No | No |
| Operar turnos | Si | No | Si | Si | Si | Si |
| Diseñar formularios | Si | Si | No | No | No | No |
| Diseñar/publicar flujos | Si | Si | No | No | No | No |
| Ver mi trabajo/bandeja | Si | No | Si | Si | Si | Si |
| Tomar/avanzar caso | Si | No | Si* | Si* | Si* | Si* |
| Llamar/rellamar/ausente | Si | No | Si* | Si* | Si* | Si* |
| Reasignar/priorizar/cancelar caso | Si | No | Si** | No | No | No |
| Ver historia clinica | Si | No | Si | Si | Si | Si |
| Firmar entrada/atencion medica | Si | No | Segun rol/nodo | No | Segun nodo | Si |
| Emitir receta | Si | No | Si* | No/segun flujo | Si* | Si* |
| Solicitar estudio/interconsulta | Si | No | Si* | Segun flujo | Si* | Si* |
| Gestionar stock/farmacia | Si | No | Si | Si | Si | Si |
| Solicitar/operar traslado | Si | No | Si | Si | Si | Si |
| Ver tablero/supervision | Si | No | Si | No | No | No |
| Auditar accesos clinicos | Si | No | Si | No | No | No |

Notas:

- `Si*`: requiere pertenecer al grupo responsable del nodo actual si el nodo declara grupos.
- `Si**`: requiere supervisar el area del caso.
- La lectura de datos clinicos esta protegida por `registros`.
- La escritura de cada recurso se valida contra la institucion implicada.

## 6. Interaccion por modulo

### Identidad y administracion

Admin:

- Crea usuarios.
- Asigna membresias.
- Define roles por institucion.
- Asocia areas a membresias.
- Mantiene legajos profesionales.

Todos los roles:

- Inician sesion.
- Seleccionan institucion si tienen membresia activa.
- Ven menu segun capacidades.

### Estructura organizativa

Admin:

- Mantiene instituciones, areas, subareas, grupos, boxes y camas.
- Define equipos por area.
- Carga staff en grupos para que luego el motor pueda resolver quien trabaja en cada paso.

Roles operativos:

- Usan boxes para llamado.
- Usan camas desde internacion/casos.
- No modifican estructura salvo acciones operativas especificas, como estado de cama.

### Formularios

Admin y configurador:

- Crean y editan formularios.
- Definen campos.
- Reordenan campos.
- Revisan usos en flujos antes de eliminar o modificar.

Roles operativos:

- Completan formularios cuando el caso llega a un nodo de tipo formulario.
- No cambian el diseño del formulario.

### Flujos y motor

Admin y configurador:

- Diseñan flujos.
- Crean versiones.
- Configuran nodos, conexiones, reglas, grupos, areas y formularios.
- Publican versiones.
- Ensayan antes de poner en uso.

Roles operativos:

- Ejecutan el flujo a traves del caso.
- Solo pueden operar pasos que su rol/capacidad y grupo permitan.

Jefe de area:

- No diseña el flujo por su rol de jefatura.
- Supervisa casos ya en ejecucion.

### Casos, guardia y filas

Administrativo:

- Inicia o acompaña admision.
- Gestiona fila, llamado y turnos cuando pertenece al grupo responsable.

Enfermeria:

- Opera triage y pasos asistenciales de enfermeria.
- Puede llamar, tomar y avanzar casos de sus grupos.

Medico:

- Atiende y firma cuando corresponde.
- Solicita estudios, recetas, interconsultas y derivaciones segun flujo.

Jefe de area:

- Visualiza casos del area.
- Reasigna, prioriza y cancela.
- Interviene cuando hay demoras o bloqueos.

Admin:

- Tiene permisos amplios, pero funcionalmente deberia actuar como conduccion/configuracion.

### Agenda y turnos

Admin:

- Configura agendas, disponibilidades y base operativa.

Roles con `trabajo`:

- Reservan turnos.
- Confirman.
- Cancelan.
- Marcan ausente.
- Registran llegada.
- Cambian modalidad.
- Reprograman.

Regla clave:

- Registrar llegada puede abrir un caso si la agenda tiene flujo asociado.

### Internacion y camas

Admin:

- Configura camas, sectores y estructura base.

Roles con `trabajo`:

- Ven disponibilidad.
- Asignan cama desde caso si el nodo lo permite.
- Registran pase.
- Registran egreso de cama.
- Cambian estado operativo cuando la accion esta habilitada.

Jefe de area:

- Supervisa ocupacion y casos internados de su area.

### Farmacia e insumos

Admin:

- Configura catalogo de insumos y depositos.

Roles con `trabajo`:

- Registran ingresos, consumos, transferencias, ajustes y bajas si operan el modulo.
- Gestionan pedidos.
- Consultan alertas.
- Trazan lotes ante retiro sanitario.

Responsabilidad funcional:

- El consumo asociado a caso permite trazabilidad paciente-lote.

### Red estatal y traslados

Admin:

- Configura redes de instituciones.

Roles con `trabajo`:

- Solicitan traslado desde el origen.
- Aceptan o rechazan desde destino.
- Marcan en camino.
- Registran recibido.
- Registran no llegada.

Jefe de area:

- Puede intervenir como conduccion en priorizacion y seguimiento.

Regla clave:

- Los casos siguen perteneciendo a cada institucion; el traslado vincula origen y destino sin mezclar propiedad institucional.

### Registros clinicos

Roles con `registros`:

- Buscan ciudadanos.
- Consultan historia clinica.
- Registran entradas, estudios y recetas segun flujo y reglas del caso.

Medico:

- Es el rol natural para firma profesional medica.

Enfermeria:

- Registra actos de enfermeria y datos asistenciales si el flujo lo habilita.

Administrativo:

- Puede consultar o registrar datos administrativos del paciente, con cuidado de no asumir firma clinica.

### Auditoria y consentimiento

Admin y jefe de area:

- Ven registro de accesos clinicos.
- Responden ante reclamos de acceso indebido.
- Supervisan trazabilidad.

Roles con `registros`:

- Pueden generar accesos auditados al consultar datos clinicos.
- No necesariamente pueden ver el registro de auditoria.

Regla clave:

- Auditar es una funcion de conduccion, no de cualquier profesional asistencial.

### Interoperabilidad FHIR

Roles con permisos sobre registros/casos:

- Pueden estar implicados indirectamente cuando un cliente FHIR lee pacientes o episodios.

Admin/jefe:

- Auditan accesos originados por FHIR.

Configurador:

- Puede configurar un nodo de servicio para consultar un padron FHIR externo.

Regla clave:

- La fachada FHIR es de solo lectura y respeta permisos; no reemplaza el motor de Cauce.

### Operacion y monitoreo

Superusuario/equipo tecnico:

- Usa endpoints de salud y estado.
- Valida disponibilidad y procesos periodicos.

Admin institucional:

- Puede recibir informacion operativa, pero la gestion tecnica depende del despliegue.

## 7. Areas y grupos

El rol no alcanza para operar todo.

Areas:

- Acotan donde trabaja una membresia.
- Permiten supervision por area.
- Ordenan bandejas, filas, internacion y derivaciones.

Grupos:

- Son equipos dentro de un area.
- Se asignan a nodos del flujo.
- Definen quien puede tomar, llamar, rellamar, devolver, marcar ausente o avanzar un paso.

Regla del motor:

- Si un nodo no declara grupos, el paso queda abierto a los usuarios con capacidad suficiente.
- Si declara grupos, el usuario debe integrar al menos uno.

Ejemplo funcional:

- Grupo Admision: administrativos que hacen ingreso.
- Grupo Triage: enfermeria que clasifica.
- Grupo Medicos Guardia: profesionales que atienden y firman.
- Grupo Especialidad: medicos de trauma, cardio, salud mental, neurologia, etc.

## 8. Membresias multiples

Una persona puede tener:

- Varios roles en la misma institucion.
- Roles distintos en instituciones distintas.
- Areas distintas segun rol.

Reglas:

- Las capacidades se calculan como union de roles activos en la institucion seleccionada.
- La escritura se valida contra la institucion del objeto.
- El frontend muestra menu segun capacidades de la institucion activa.
- La auditoria se acota a instituciones donde el usuario tiene rol de conduccion.

Ejemplos:

- Medico + jefe_area en la misma institucion: atiende y supervisa.
- Configurador en Hospital A y medico en Hospital B: diseña en A, atiende en B.
- Jefe_area en Guardia pero no en Pediatria: supervisa casos de Guardia, no de Pediatria.

## 9. Reglas de seguridad funcional

- Todo usuario debe estar autenticado.
- La institucion activa define el contexto.
- La lectura general queda scopeada por membresia institucional.
- La lectura clinica sensible exige `registros`.
- La escritura exige la capacidad del recurso y la institucion implicada.
- El superusuario atraviesa restricciones por diseño tecnico.
- Los eventos relevantes deben dejar autor.
- La historia clinica y FHIR generan auditoria de lectura.
- El registro de accesos no puede ser visible para cualquier rol asistencial.

## 10. Mapa tecnico de permisos

Fuente backend:

- `backend/apps/accounts/models.py`: roles en `Membresia.Rol`.
- `backend/apps/common.py`: `ROL_CAPACIDADES`, `capacidades_de`, `CapacidadPermission`.
- `backend/apps/auditoria/views.py`: `PuedeAuditar` y roles que auditan.
- Viewsets: `capacidad_requerida`, `protege_lectura`, `capacidad_por_accion`.

Fuente frontend:

- `frontend/src/auth/InstitutionContext.jsx`: capacidades por rol para menu.
- `frontend/src/components/Shell.jsx`: navegacion visible por capacidad.
- `frontend/src/App.jsx`: rutas protegidas.

## 11. Endpoints y capacidades principales

| Bloque | Endpoints principales | Capacidad de escritura/uso |
|---|---|---|
| Usuarios y membresias | `usuarios`, `membresias`, `legajos` | `config` |
| Estructura | `instituciones`, `areas`, `subareas`, `grupos`, `boxes`, `camas` | `config` |
| Estado operativo de cama | accion `camas/{id}/estado` | `trabajo` |
| Formularios | `formularios`, `campos` | `diseno` |
| Flujos | `flujos`, `versiones-flujo`, `nodos`, `conexiones` | `diseno` |
| Casos y filas | `casos`, `items-fila`, `eventos-caso`, `valores-campo` | `trabajo` |
| Agenda | `agendas`, `disponibilidades`, `bloqueos-agenda`, `turnos` | config/trabajo segun recurso |
| Registros clinicos | `ciudadanos`, `historias-clinicas`, `entradas-historia`, `estudios`, `recetas`, `consentimientos` | `registros` |
| Farmacia | `insumos`, `depositos`, `lotes`, `stock`, `movimientos-stock`, `pedidos-stock` | config/trabajo segun recurso |
| Red | `redes`, `traslados` | config/trabajo segun recurso |
| Auditoria | `accesos-clinicos` | admin/jefe_area |
| FHIR | `/fhir/Patient`, `/fhir/Encounter`, `/fhir/Organization` | lectura protegida por permisos equivalentes |
| Monitoreo | `/api/health/`, `/api/estado/` | tecnico/autenticado segun endpoint |

## 12. Responsabilidades por rol en lenguaje operativo

| Rol | Responsable de | No deberia ser responsable de |
|---|---|---|
| Superusuario | Plataforma, soporte global, contingencia | Operacion diaria institucional |
| Admin institucion | Gobierno institucional del sistema | Reemplazar roles asistenciales como practica normal |
| Configurador | Modelar procesos y formularios | Atender pacientes o auditar datos clinicos |
| Jefe area | Ordenar, supervisar y auditar su area | Diseñar flujos o administrar usuarios |
| Administrativo | Admision, turnos, filas, gestion operativa | Firmar actos clinicos o auditar colegas |
| Enfermeria | Triage, cuidados, registros asistenciales | Firma medica si el nodo exige medico |
| Medico | Atencion, diagnostico, indicaciones, firma profesional | Administracion del sistema o auditoria institucional |

## 13. Roles que podrian aparecer en futuras versiones

Estos roles no estan implementados como roles separados. Hoy se resuelven combinando roles, areas y grupos.

- Farmacia: actualmente puede operar con `trabajo`; configuracion de catalogo/depositos requiere `config`.
- Regulador de red/derivaciones: hoy se opera con `trabajo` dentro de instituciones.
- Camillero/traslado interno: hoy podria modelarse como grupo dentro de un area.
- Auditor central estatal: hoy auditoria se limita a admin/jefe_area y superusuario.
- Solo lectura/reportes: hoy no existe rol de consulta pasiva.
- Profesional externo/interconsulta externa: hoy se modela con membresia institucional.

Recomendacion funcional:

- Crear nuevos roles solo si cambian responsabilidades, responsabilidades legales o limites de datos.
- Si solo cambia "quien toma este paso", usar grupos.
- Si cambia "en que establecimiento/area trabaja", usar membresias y areas.

## 14. Pendientes funcionales sobre autoridad

### Firma configurable por nodo

El flujo ya distingue quien puede operar un paso mediante grupos, pero la firma profesional sigue siendo una decision sensible que debe quedar clara por nodo y por tipo de acto.

Necesidad funcional:

- Permitir que un nodo declare que roles pueden firmar.
- Distinguir completar un formulario de firmar un acto clinico.
- Exigir matricula cuando corresponda.
- Permitir flujos donde firma medico, enfermeria, trabajo social u otro perfil profesional definido por la institucion.

Criterio recomendado:

- La capacidad `trabajo` habilita operar.
- El grupo habilita tomar el paso.
- La configuracion del nodo debe decidir quien firma y con que requisitos.

### Auditor central estatal

Hoy auditan superusuario, admin de institucion y jefe de area. Para un despliegue estatal puede requerirse un rol separado con alcance regional/provincial y permisos de solo auditoria.

### Rol de solo lectura/reportes

No existe un rol pasivo para consultar indicadores sin operar ni ver datos clinicos nominales. Puede ser necesario para gestion sanitaria.

## 15. Criterios para asignar roles

Preguntas de analisis:

- La persona configura el sistema o lo opera?
- Necesita ver datos clinicos?
- Necesita firmar actos clinicos?
- Conduce un area o solo trabaja en ella?
- Debe auditar accesos de otros?
- Trabaja en una institucion o en varias?
- Su restriccion real es por modulo o por paso del flujo?

Decision recomendada:

- Configura usuarios/estructura: admin.
- Diseña procesos/formularios: configurador.
- Ordena casos de un area: jefe_area.
- Hace admision/turnos/filas: administrativo.
- Hace triage/cuidados: enfermeria.
- Atiende/firma como profesional: medico.
- Necesita operar un paso especifico: agregarlo al grupo del nodo.

## 16. Referencias relacionadas

- `docs/funcionalidades/identidad-accesos/README.md`
- `docs/funcionalidades/estructura-organizativa/README.md`
- `docs/funcionalidades/flujos-motor/README.md`
- `docs/funcionalidades/casos-guardia-filas/README.md`
- `docs/funcionalidades/auditoria-consentimiento/README.md`
- `docs/funcionalidades/interoperabilidad-fhir/README.md`
