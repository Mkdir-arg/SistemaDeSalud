# Roles, responsabilidades y permisos

Actualizado: 2026-09-22 (verificado contra `main` en `fca71e3`)

Este documento describe el modelo funcional de autoridad de I-Core Salud: que roles existen, donde interactuan, que responsabilidades tienen, que funcionalidades habilitan y cuales son sus limites. No es un manual de capacitacion; es una especificacion funcional para analisis, implementacion, auditoria y gobierno del sistema.

## 1. Principio general

Salud separa tres conceptos que en hospitales suelen mezclarse:

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

### Autoridad estatal / plataforma

Es una membresia institucional con rol `plataforma`. No equivale a `is_superuser`: es un rol funcional para gobierno estatal de la red.

Responsabilidades:

- Crear y actualizar instituciones.
- Definir redes sanitarias entre establecimientos.
- Administrar el directorio estatal de usuarios y membresias necesarias para el alta institucional.
- Asignar roles estatales (`plataforma` y `auditor`) cuando corresponda.
- Auditar accesos clinicos con alcance estatal.

Funcionalidades:

- Directorio de plataforma.
- ABM de instituciones.
- ABM de redes sanitarias.
- Usuarios y membresias del directorio estatal.
- Registro de accesos clinicos.

Limites:

- No recibe permisos clinicos u operativos por ser plataforma.
- No reemplaza a los roles asistenciales dentro de un hospital.
- No convierte al usuario en superusuario Django ni en staff tecnico.

### Auditor estatal

Es una membresia institucional con rol `auditor`, orientada a control y cumplimiento.

Responsabilidades:

- Leer el registro de accesos clinicos con alcance estatal.
- Responder auditorias, reclamos o requerimientos de control.
- Ver trazabilidad sin modificar datos asistenciales ni configuracion.

Funcionalidades:

- Registro de accesos clinicos.

Limites:

- No crea, edita ni borra registros de auditoria.
- No administra instituciones, usuarios ni redes.
- No opera casos ni accede a historia clinica por este rol.

### Reportes / solo lectura

Rol `reportes`, pensado para consulta pasiva de indicadores no nominales.

Responsabilidades:

- Consultar reportes o tableros agregados cuando existan pantallas no nominales.
- Acompanhar gestion sanitaria sin operar procesos.

Limites:

- No opera casos, turnos, farmacia, internacion ni red.
- No habilita historia clinica ni auditoria de accesos por si mismo.
- Los reportes que muestren datos nominales deben exigir una capacidad mas especifica.

### Admin de institucion

Rol de conduccion institucional amplia.

Responsabilidades:

- Administrar usuarios, membresias, areas y estructura.
- Configurar flujos, formularios, agendas y recursos institucionales.
- Supervisar operacion.
- Auditar accesos clinicos.
- Otorgar permisos financieros a quien corresponda.
- Operar si la institucion lo decide, aunque funcionalmente deberia delegar operacion diaria.

Alcance financiero:

- Desde el 18/09/2026 **hereda todas las acciones financieras** dentro de su institucion, para todas las areas e informacion sensible. Antes heredaba solo las dos lecturas. Ver §3.1.

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
- Mantener la ficha administrativa del paciente y su consentimiento.

Funcionalidades:

- Mi trabajo.
- Bandeja.
- Filas.
- Casos.
- Agenda y turnos.
- Padron de pacientes: alta, busqueda y ficha administrativa.
- Red y traslados como operador del establecimiento.

Limites:

- **No ve la historia clinica.** Tiene `padron_admision` y no `historia_clinica`: accede a la ficha administrativa, no a la evolucion, alergias, estudios ni recetas. Si la institucion necesita que la vea, hay que darle otro rol.
- **No opera farmacia ni internacion**: no tiene `farmacia_stock` ni `internacion`.
- No firma atenciones medicas.
- No solicita estudios ni emite recetas.
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
- **No emite recetas**: no tiene `prescripcion`. Si puede solicitar estudios.
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
- **No opera el stock de farmacia**: no tiene `farmacia_stock`, que si tiene enfermeria. Puede imputar consumo desde el caso cuando el flujo lo vincula.
- No diseña flujos/formularios.
- No administra usuarios ni estructura.
- Debe integrar el grupo responsable cuando el nodo lo exige.

## 3. Capacidades del sistema

Las capacidades son permisos funcionales que habilitan bloques de la aplicacion. Los roles otorgan una o mas capacidades. Se definen en `backend/apps/common.py` y son veinte, en cuatro familias.

### Capacidades legadas (bloques amplios)

| Capacidad | Que habilita |
|---|---|
| `config` | Administracion institucional en sentido amplio |
| `diseno` | Configuracion de procesos en sentido amplio |
| `trabajo` | Operacion diaria en sentido amplio |
| `registros` | Datos del ciudadano en sentido amplio; tambien habilita el legajo propio |
| `supervision` | Tablero, supervision de area, reasignacion, prioridad y cancelacion de casos |

Siguen vigentes porque varios roles las conservan, pero **ya no son las que gobiernan las rutas ni los endpoints**: eso lo hacen las capacidades de dominio.

### Capacidades de dominio (las que usan rutas y endpoints)

| Capacidad | Que habilita | Observacion |
|---|---|---|
| `config_institucional` | Areas, subareas, grupos, boxes, camas, usuarios, membresias, legajos, agendas, disponibilidades, insumos y depositos | Es la que abre `/estructura` y `/administracion` |
| `diseno_flujos` | Flujos, versiones, nodos, conexiones, formularios y campos | Abre `/flujos`, `/mapa` y `/formularios` |
| `casos_operar` | Casos, valores de campo y eventos del caso | Abre `/casos`, `/bandeja` y `/puesto/:id` |
| `filas` | Items de fila | Abre `/filas` |
| `turnos` | Turnos y bloqueos de agenda | Abre `/agenda`; crear la agenda y sus disponibilidades es `config_institucional` |
| `internacion` | Estadias de cama y la accion `camas/{id}/estado` | Abre `/internacion` |
| `farmacia_stock` | Lotes, existencias, movimientos y pedidos | Abre `/farmacia`; el catalogo de insumos y depositos es `config_institucional` |
| `traslados_red` | Traslados entre establecimientos | Abre `/red`; crear la red es `gobierno_plataforma` |
| `padron_admision` | Alta, busqueda y ficha administrativa de pacientes, y sus consentimientos | Abre `/padron`. No habilita evolucion, alergias, estudios ni recetas |
| `historia_clinica` | Historia clinica, entradas, estudios y recetas como lectura clinica | Abre `/historia`. Genera auditoria de acceso |
| `prescripcion` | Crear y suspender recetas | Se suma a `historia_clinica`, que sigue siendo necesaria para leerlas |
| `solicitud_estudios` | Crear y actualizar estudios | Se suma a `historia_clinica` |
| `reportes` | Reportes agregados / solo lectura | No debe exponer datos clinicos nominales sin otra capacidad |
| `gobierno_plataforma` | Instituciones, redes sanitarias y directorio estatal | Capacidad **global**, no acotada a un hospital puntual |

### Capacidad de interfaz

| Capacidad | Que habilita | Observacion |
|---|---|---|
| `auditoria` | Registro de accesos clinicos, `/accesos` | Es una capacidad de menu/ruta. El alcance real lo decide `PuedeAuditar`: solo `admin`, `jefe_area`, `auditor` y `plataforma`, y los dos ultimos con alcance estatal |

### 3.1 Permisos financieros: un sistema aparte

Finanzas **no se gobierna por capacidades**. Usa concesiones explicitas (`ConcesionFinanciera`), ligadas a una membresia, con su institucion, sus areas y si alcanzan informacion sensible. Un rol clinico no las otorga y una concesion no concede acceso clinico.

Son dieciocho acciones:

| Acciones | Que habilitan |
|---|---|
| `ver_costos`, `configurar_componentes`, `corregir_costos`, `aprobar_costos` | Costos por atencion: consultar, configurar componentes y valores, corregir y aprobar ajustes |
| `ver_gastos`, `registrar_gastos`, `corregir_gastos`, `aprobar_gastos`, `configurar_gastos_esperados` | Gastos: consultar, cargar, ajustar, aprobar y configurar los gastos mensuales esperados |
| `configurar_repartos` | Reglas de reparto y estado de actividad del ambito |
| `ver_dinero`, `registrar_dinero`, `aprobar_dinero`, `corregir_dinero`, `configurar_cobros` | Pagos y cobros: consultar, registrar, aprobar, reducir/reintegrar y definir que se cobra |
| `registrar_aceptacion` | Registrar la aceptacion del paciente de un copago identificado |
| `resolver_cobertura` | Resolver saldos pendientes de resolucion administrativa |
| `auditar_finanzas` | Leer el registro de accesos financieros |

**El administrador de institucion las hereda todas**, para todas las areas e informacion sensible, dentro de su institucion y sin que se creen concesiones duplicadas. Es una decision aprobada el 18/09/2026: antes solo heredaba `ver_costos` y `ver_gastos`. Las lecturas heredadas se identifican en pantalla como **Por rol** y no se revocan desde las casillas.

Se administran en **Administracion -> Usuarios -> Editar usuario -> Permisos financieros**.

### 3.2 Acceso de financiadores: otra membresia

Un usuario de obra social **no tiene membresia institucional**. Tiene una `MembresiaFinanciador` con su propio rol, que no se mezcla con los roles del hospital:

| Rol del financiador | Que puede |
|---|---|
| `admin` | Todo lo del operador, mas administrar los usuarios de su organizacion, los planes y los convenios |
| `operador` | Configurar cobertura, mantener padron, cargar consumos externos y consultar actividad |
| `auditor` | Solo lectura sobre su organizacion |

Ademas, resolver autorizaciones exige una **designacion expresa** (`resuelve_autorizaciones`) sobre un rol `admin` u `operador`: ni ser administrador de la organizacion ni ser plataforma alcanza por si solo.

Un usuario con varios ambitos elige una organizacion concreta, y cada consulta vuelve a verificar ese ambito en el servidor.

## 4. Matriz rol-capacidad

Las capacidades exactas que otorga cada rol, tal como estan en `ROL_CAPACIDADES`.

| Rol | Capacidades |
|---|---|
| Superusuario de plataforma | Todas, por diseño tecnico. Atraviesa el limite institucional |
| Autoridad estatal / plataforma | `gobierno_plataforma`, `reportes`, `auditoria` |
| Auditor estatal | `auditoria` |
| Reportes / solo lectura | `reportes` |
| Admin de institucion | Todas menos `gobierno_plataforma` |
| Configurador | `diseno`, `diseno_flujos` |
| Jefe / Supervisor de area | `trabajo`, `registros`, `supervision`, `auditoria`, `padron_admision`, `historia_clinica`, `prescripcion`, `solicitud_estudios`, `turnos`, `casos_operar`, `filas`, `internacion`, `farmacia_stock`, `traslados_red` |
| Administrativo | `trabajo`, `registros`, `padron_admision`, `turnos`, `casos_operar`, `filas`, `traslados_red` |
| Enfermeria | `trabajo`, `registros`, `padron_admision`, `historia_clinica`, `solicitud_estudios`, `turnos`, `casos_operar`, `filas`, `internacion`, `farmacia_stock`, `traslados_red` |
| Medico / profesional | `trabajo`, `registros`, `padron_admision`, `historia_clinica`, `prescripcion`, `solicitud_estudios`, `turnos`, `casos_operar`, `filas`, `internacion`, `traslados_red` |

Tres diferencias que suelen sorprender y estan puestas a proposito:

- El **administrativo no tiene `historia_clinica`**: ve el padron y la ficha administrativa, no la evolucion. Tampoco tiene `internacion` ni `farmacia_stock`.
- La **enfermeria tiene `farmacia_stock` y el medico no**: quien consume el insumo en la sala es enfermeria.
- El **medico tiene `prescripcion` y la enfermeria no**; la enfermeria si puede `solicitud_estudios`.

Notas tecnicas:

- `gobierno_plataforma` es global; las demas se evaluan contra la institucion seleccionada.
- `auditoria` se expone como capacidad efectiva para menu/ruta, pero el alcance real lo decide `PuedeAuditar`.
- Ningun rol otorga permisos financieros, salvo la herencia completa del admin de institucion descrita en §3.1.

## 5. Matriz por funcionalidad

| Funcionalidad | Capacidad | Admin | Configurador | Jefe area | Administrativo | Enfermeria | Medico |
|---|---|---|---|---|---|---|---|
| Seleccionar institucion | — | Si | Si | Si | Si | Si | Si |
| Administrar usuarios/membresias | `config_institucional` | Si | No | No | No | No | No |
| Configurar areas/subareas/grupos/boxes/camas | `config_institucional` | Si | No | No | No | No | No |
| Cambiar estado operativo de cama | `internacion` | Si | No | Si | **No** | Si | Si |
| Ver internacion y estadias | `internacion` | Si | No | Si | **No** | Si | Si |
| Crear agendas y disponibilidades | `config_institucional` | Si | No | No | No | No | No |
| Operar turnos y bloqueos | `turnos` | Si | No | Si | Si | Si | Si |
| Diseñar formularios | `diseno_flujos` | Si | Si | No | No | No | No |
| Diseñar/publicar flujos | `diseno_flujos` | Si | Si | No | No | No | No |
| Ver mi trabajo/bandeja | `casos_operar` | Si | No | Si | Si | Si | Si |
| Tomar/avanzar caso | `casos_operar` | Si | No | Si* | Si* | Si* | Si* |
| Llamar/rellamar/ausente | `filas` | Si | No | Si* | Si* | Si* | Si* |
| Reasignar/priorizar/cancelar caso | `supervision` | Si | No | Si** | No | No | No |
| Gestionar padron/admision y consentimientos | `padron_admision` | Si | No | Si | Si | Si | Si |
| Ver historia clinica | `historia_clinica` | Si | No | Si | **No** | Si | Si |
| Firmar entrada/atencion medica | `historia_clinica` + regla del motor | Si | No | Segun rol/nodo | No | Segun nodo | Si |
| Emitir receta | `prescripcion` | Si | No | Si* | No | **No** | Si* |
| Solicitar estudio/interconsulta | `solicitud_estudios` | Si | No | Si* | **No** | Si* | Si* |
| Gestionar stock/farmacia | `farmacia_stock` | Si | No | Si | **No** | Si | **No** |
| Mantener catalogo de insumos y depositos | `config_institucional` | Si | No | No | No | No | No |
| Solicitar/operar traslado | `traslados_red` | Si | No | Si | Si | Si | Si |
| Crear redes sanitarias | `gobierno_plataforma` | No | No | No | No | No | No |
| Ver tablero/supervision | `supervision` | Si | No | Si | No | No | No |
| Auditar accesos clinicos | `auditoria` + `PuedeAuditar` | Si | No | Si | No | No | No |
| Operar Finanzas | concesion financiera | Si*** | No | No | No | No | No |
| Operar cobertura y copagos | concesion financiera | Si*** | No | No | No | No | No |

Notas:

- `Si*`: requiere pertenecer al grupo responsable del nodo actual si el nodo declara grupos.
- `Si**`: requiere supervisar el area del caso.
- `Si***`: por la herencia del admin de institucion (§3.1). Cualquier otro rol necesita concesiones explicitas: se otorgan de a una y **no dependen del rol**. Una persona de contabilidad puede tenerlas sin ser administradora ni obtener permisos clinicos.
- La ficha administrativa usa `padron_admision`; la lectura clinica usa `historia_clinica`.
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

- La fachada FHIR es de solo lectura y respeta permisos; no reemplaza el motor de Salud.

### Finanzas y costos

Admin de institucion:

- Hereda todas las acciones financieras de su institucion.
- Otorga y quita permisos financieros a las demas personas, con su area y su alcance sensible.

Persona con concesiones explicitas (contabilidad, administracion del area):

- Carga gastos, los aprueba si tiene esa accion, configura gastos mensuales esperados y reglas de reparto.
- Registra pagos y cobros, los aprueba y registra reducciones o reintegros.
- Configura que prestaciones se cobran, su arancel y quien paga.

Personal clinico:

- Registra la atencion como parte de su trabajo. Los componentes de costo configurados se calculan solos.
- No obtiene por eso acceso al registro financiero.

Reglas clave:

- Ningun rol clinico concede permisos financieros, y ninguna concesion financiera concede acceso clinico.
- Cada consulta financiera autorizada deja evidencia por area y nivel de sensibilidad.

### Financiadores y cobertura

Usuario del financiador (`admin` / `operador` / `auditor` de su organizacion):

- Configura planes y reglas de cobertura, mantiene el padron, informa consumos externos y consulta su actividad en los hospitales.
- Resuelve autorizaciones solo con designacion expresa.

Administrativo del hospital:

- Elige la afiliacion del caso al ingresar y ve la verificacion y la vigencia.

Personal clinico del hospital:

- Antes de la prestacion ve arancel, cobertura, copago y disponibilidad; registra la aceptacion del paciente y confirma la reserva.

Finanzas del hospital:

- Ve la distribucion del importe, las obligaciones y los cobros; rechaza asumir un importe y resuelve los saldos pendientes.

Reglas clave:

- El hospital y el financiador ven cada uno lo suyo. El financiador accede a prestacion, fecha, cantidad e importe propio; no a la historia clinica.
- Un financiador no consulta el padron ni los consumos de otro.

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
- `backend/apps/auditoria/views.py`: `PuedeAuditar`, `ROLES_QUE_AUDITAN` y `ROLES_AUDITORIA_GLOBAL`.
- `backend/apps/finanzas/models.py`: acciones en `ConcesionFinanciera.Accion`.
- `backend/apps/finanzas/permisos.py`: `tiene_concesion_financiera`, `instituciones_admin_financiero` y el alcance por area y sensibilidad.
- `backend/apps/financiadores/permisos.py`: `requerir_financiador`, `puede_resolver_autorizaciones` y `requerir_hospital`.
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
| Auditoria | `accesos-clinicos`, `consentimientos` | `auditoria` + `PuedeAuditar`; los consentimientos, `padron_admision` |
| Costos y gastos | `hechos-costo`, `gastos`, `ajustes-gasto`, `ajustes-costo`, `conceptos-gasto`, `prestaciones-costo`, `componentes-costo`, `valores-componentes`, `expectativas-gasto` | concesion financiera segun la accion |
| Reparto | `coberturas-actividad`, `reglas-reparto`, `repartos-gasto`, `procesamiento-finanzas` | `configurar_repartos`; consultar importes exige ademas `ver_gastos` |
| Dinero | `obligaciones-financieras`, `movimientos-dinero`, `politicas-cobro`, `pendientes-cobro` | `ver_dinero`, `registrar_dinero`, `aprobar_dinero`, `corregir_dinero`, `configurar_cobros` |
| Reportes financieros | `reportes-finanzas`, `reportes-dinero`, `reportes-costos` | solo lectura, con el alcance de la concesion correspondiente |
| Auditoria financiera | `accesos-financieros`, `concesiones-financieras` | `auditar_finanzas` / `config_institucional` |
| Portal del financiador | `financiadores` y sus acciones (`planes`, `reglas`, `padron`, `consumos`, `convenios`, `aranceles`, `actividad`, `usuarios`, `importaciones`, `catalogo`) | `MembresiaFinanciador` de esa organizacion |
| Cobertura del hospital | `coberturas` (`opciones`, `configurar`, `convenio`, `arancel`, `afiliados`, `afiliacion`, `evaluar`, `reservar`, `liberar`, `resolver`, `completar`, `recuperar`) | concesion financiera de la institucion |
| Autorizaciones | `autorizaciones-cobertura` (`contexto`, `resolver`, `reenviar`, `anular`) | hospital: concesion financiera. Financiador: designacion expresa |
| Seguimiento de cobros | `seguimiento-cobros` | `ver_dinero` de la institucion |
| Cobertura en el caso | `casos/{id}/cobertura`, `cobertura-afiliacion`, `cobertura-evaluar`, `cobertura-confirmar` | `casos_operar` en el area del caso, mas la concesion que exija la accion |
| FHIR | `/fhir/Patient`, `/fhir/Encounter`, `/fhir/Organization`, `/fhir/Coverage` | lectura protegida por permisos equivalentes; `Coverage` exige `padron_admision` |
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

Estos roles no estan implementados como roles separados. Hoy se resuelven combinando roles, areas y grupos, salvo los roles estatales ya incorporados (`plataforma`, `auditor`, `reportes`).

- Farmacia: hoy se opera con `farmacia_stock`, que tienen `admin`, `jefe_area` y `enfermeria`; el catalogo de insumos y depositos exige `config_institucional`.
- Regulador de red/derivaciones: hoy se opera con `traslados_red` dentro de cada institucion; crear la red exige `gobierno_plataforma`.
- Finanzas: no es un rol sino un conjunto de concesiones explicitas (§3.1). Una persona de contabilidad las recibe sin convertirse en administradora.
- Usuario de obra social: no es un rol institucional sino una `MembresiaFinanciador` (§3.2).
- Camillero/traslado interno: hoy podria modelarse como grupo dentro de un area.
- Auditor central estatal: implementado como `auditor`, con alcance estatal de auditoria y sin operacion clinica.
- Solo lectura/reportes: implementado como `reportes`; requiere pantallas agregadas no nominales para tener uso pleno.
- Profesional externo/interconsulta externa: hoy se modela con membresia institucional.

Recomendacion funcional:

- Crear nuevos roles solo si cambian responsabilidades, responsabilidades legales o limites de datos.
- Si solo cambia "quien toma este paso", usar grupos.
- Si cambia "en que establecimiento/area trabaja", usar membresias y areas.

## 14. Pendientes funcionales sobre autoridad

### Firma configurable por nodo

El flujo distingue quien puede operar un paso mediante grupos y quien puede firmar mediante configuracion del nodo. En nodos de atencion, `Nodo.config` puede declarar:

- `firma_roles`: roles habilitados para firmar, actualmente `medico`, `enfermeria`, `administrativo` y `jefe_area`.
- `firma_matricula`: si la firma exige legajo/matricula profesional.

Regla implementada:

- La capacidad operativa habilita trabajar en el caso.
- El grupo responsable habilita tomar el paso.
- La configuracion del nodo decide quien firma y si necesita matricula.
- Si no hay configuracion valida, el sistema conserva el default seguro: firma de `medico` con matricula.
- La validacion de version advierte roles de firma desconocidos antes de publicar o ensayar el flujo.

Pendiente posible:

- Si el alcance legal lo requiere, agregar firma digital/certificado como capa separada de esta autorizacion funcional.

### Auditor central estatal

Implementado como rol `auditor`. Audita accesos clinicos con alcance estatal y no puede modificar el registro ni operar datos asistenciales.

### Rol de solo lectura/reportes

Implementado como rol `reportes`. La capacidad existe, pero debe usarse con pantallas agregadas no nominales; si un reporte muestra pacientes, historia o profesionales identificables, necesita una capacidad mas especifica.

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
- `docs/funcionalidades/registros-clinicos/README.md`
- `docs/funcionalidades/finanzas-costos/README.md`
- `docs/funcionalidades/financiadores-cobertura/README.md`
