# Matriz de permisos y alcance institucional (#172, AUD-039)

Fecha: 19/10/2026. Base: `b6c0266` más los cambios de este corte (AUD-042). Estado: **evidencia parcial**. La matriz no se cierra con este documento: lo que no tiene prueba figura como hueco y no se dio por cubierto.

## Cómo se armó

- **Fuente:** `backend/config/api.py` (67 viewsets del router) y las rutas extra de `backend/config/urls.py`. Las columnas salen de los atributos de cada viewset (`permission_classes`, `capacidad_requerida`, `capacidad_por_accion`, `protege_lectura`, `institucion_path`) y de `get_extra_actions()`. No se agregaron reglas de negocio: donde el código no declara una regla, se anota como hueco.
- **Guardia estructural:** `apps.test_matriz_permisos_auditoria172` recorre todos los viewsets y falla si alguno no declara control de permiso y alcance institucional, o si no figura en una lista de exenciones justificada dentro de la prueba. También falla si una exención queda vencida. Es estructural: no prueba que el control en código sea correcto.
- **Evidencia HTTP A/B:** un actor de la institución A con todas las capacidades institucionales (rol `admin`) contra objetos de B. Así, el rechazo se debe al alcance y no al rol.

## Leyenda

- **Permiso:** clases además de `IsAuthenticated`. «solo IsAuthenticated» indica que la autorización está en el código del viewset (ver `PERMISO_EN_CODIGO` en la prueba).
- **Capacidad:** la que exige `CapacidadPermission` para escribir; con «protege lectura = sí», también para leer. Con «no», cualquier miembro activo de la institución lee.
- **Alcance:** `institucion_path` aplicado por `InstitucionScopedMixin`. «—» indica alcance propio en `get_queryset`/`list` (`ALCANCE_EN_CODIGO`) o sin queryset institucional (`SIN_ALCANCE_EN_QUERYSET`).
- **Cobertura A/B:** prueba que demuestra que A no lista, abre ni modifica objetos de B. «solo FK» indica que la prueba solo rechaza referencias a B en altas o ediciones, no que A lea o edite objetos de B.

## API: viewsets del router

| Recurso `/api/…` | Permiso | Capacidad | Protege lectura | Alcance | Acciones extra | Cobertura A/B |
|---|---|---|---|---|---|---|
| `financiadores` | solo IsAuthenticated | — | no | — | aceptar_convenio, activar (AllowAny), actividad, aranceles, catalogo, catalogo_comun, cerrar_convenio, confirmar_importacion, consumos, convenios, corregir_consumo, corregir_identidad, editar_plan, factura_adjunto, factura_detalle, facturas, ficha_afiliado, ficha_afiliado_autorizaciones, ficha_historia_casos, ficha_historia_evoluciones, finalizar_afiliacion, importaciones, instituciones, padron, padron_cobranza, padron_cobranza_historial, padron_detalle, padron_exportar, padron_familia, padron_historial, padron_legajo, padron_salud, padron_salud_historial, planes, plantilla, plazo_autorizacion, reactivar_afiliacion, rechazar_convenio, rechazos, reglas, resumen, usuarios | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `autorizaciones-cobertura` | solo IsAuthenticated | — | no | — | anular, contexto, manual, opciones_manual, reenviar, resolver | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `coberturas` | solo IsAuthenticated | — | no | — | aceptar_convenio, afiliacion, afiliados, arancel, cerrar_convenio, completar, configurar, convenio, evaluar, liberar, opciones, rechazar_convenio, recuperables, recuperar, reservar, resolver, revisar_contexto, vincular_prestacion | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `seguimiento-cobros` | solo IsAuthenticated | — | no | — | — | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `usuarios` | CapacidadPermission | config_institucional, gobierno_plataforma | no | — | iniciar_recuperacion, legajo, me | accounts.tests.PadronPorInstitucionTests, LegajoPorInstitucionTests |
| `membresias` | CapacidadPermission | config_institucional, gobierno_plataforma | no | `institucion` | — | test_aislamiento_ab_auditoria172 (lista, detalle, PATCH, DELETE) |
| `legajos` | CapacidadPermission | config_institucional | sí | — | — | accounts.tests.LegajoAjenoTests (lista, PATCH, alta) |
| `instituciones` | CapacidadPermission | gobierno_plataforma | no | `id` | metricas, puesta_en_marcha, reset_escuela, tablero, tablero_plataforma | **hueco** |
| `areas` | CapacidadPermission | config_institucional | no | `institucion` | tablero | **hueco** |
| `subareas` | CapacidadPermission | config_institucional | no | `area__institucion` | — | **hueco** |
| `grupos` | CapacidadPermission | config_institucional | no | `area__institucion` | — | **hueco** |
| `boxes` | CapacidadPermission | config_institucional | no | `area__institucion` | liberar, ocupar | **hueco** |
| `camas` | CapacidadPermission | config_institucional · por acción: estado: internacion | no | `area__institucion` | estado, tablero | instituciones.test_camas (solo FK) |
| `estadias-cama` | CapacidadPermission | internacion | no | `cama__area__institucion` | — | **hueco** |
| `formularios` | CapacidadPermission | diseno_flujos | no | `institucion` | duplicar, reordenar, usos | formularios.tests (solo FK) |
| `campos` | CapacidadPermission | diseno_flujos | no | `formulario__institucion` | — | **hueco** |
| `flujos` | CapacidadPermission | diseno_flujos | no | `institucion` | duplicar, mapa | flujos.tests (solo FK) |
| `versiones-flujo` | CapacidadPermission | diseno_flujos | no | `flujo__institucion` | archivar, ensayo, nueva_version, publicar, validar | **hueco** |
| `nodos` | CapacidadPermission | diseno_flujos | no | `version__flujo__institucion` | pantalla | casos.test_permisos.CreateHijoScopeTests (alta); flujos.tests (FK) |
| `conexiones` | CapacidadPermission | diseno_flujos | no | `version__flujo__institucion` | — | **hueco** |
| `casos` | CapacidadPermission | casos_operar | no | `institucion` | asignar, ausente, avanzar, cama, cancelar, cobertura, cobertura_afiliacion, cobertura_confirmar, cobertura_evaluar, continuar_autorizacion, devolver, egreso_cama, estudio, eventos, iniciar, interconsulta, llamar, pase, priorizar, receta, rellamar, tomar | casos.tests_api.ScopeInstitucionTest (lista, detalle); test_aislamiento_ab_auditoria172 (priorizar, cancelar) |
| `valores-campo` | CapacidadPermission | casos_operar | no | `caso__institucion` | — | test_aislamiento_ab_auditoria172 (lista, ?caso, detalle) |
| `items-fila` | CapacidadPermission | filas | no | `caso__institucion` | mover | test_aislamiento_ab_auditoria172 (lista, detalle, PATCH, DELETE, mover) |
| `eventos-caso` | CapacidadPermission | casos_operar | no | `caso__institucion` | — | test_aislamiento_ab_auditoria172 (lista, detalle, PATCH, DELETE) |
| `notificaciones` | solo IsAuthenticated | — | no | — | leer, resumen | **hueco** |
| `ciudadanos` | CapacidadPermission | padron_admision | sí | `institucion` | cobertura, configuracion_cobertura, exportar | test_aislamiento_ab_auditoria172 (lista, detalle, PATCH, DELETE); registros.tests_api (revelación) |
| `historias-clinicas` | CapacidadPermission | historia_clinica | sí | `ciudadano__institucion` | verificar | test_aislamiento_ab_auditoria172 (lista, detalle, PATCH, DELETE) |
| `entradas-historia` | CapacidadPermission | historia_clinica | sí | `historia__ciudadano__institucion` | — | test_aislamiento_ab_auditoria172 (lista, detalle, PATCH, DELETE) |
| `estudios` | CapacidadPermission | historia_clinica · por acción: create: solicitud_estudios, update: solicitud_estudios, partial_update: solicitud_estudios, confirmar_archivo: config_institucional | sí | `historia__ciudadano__institucion` | confirmar_archivo | test_aislamiento_ab_auditoria172 (lista, detalle, PATCH, DELETE, confirmar-archivo) |
| `recetas` | CapacidadPermission | historia_clinica · por acción: create: prescripcion, suspender: prescripcion | sí | `historia__ciudadano__institucion` | suspender | test_aislamiento_ab_auditoria172 (lista, detalle, PATCH, DELETE, suspender) |
| `agendas` | CapacidadPermission | config_institucional | no | `institucion` | dia, proximos_libres, semana | agenda.tests_api (solo FK) |
| `disponibilidades` | CapacidadPermission | config_institucional | no | `agenda__institucion` | — | **hueco** |
| `bloqueos-agenda` | CapacidadPermission | turnos | no | `agenda__institucion` | — | **hueco** |
| `turnos` | CapacidadPermission | turnos | no | `agenda__institucion` | ausente, cancelar, confirmar, llegada, modalidad, registrar_pasado, reprogramar | agenda.tests_api (solo FK de paciente) |
| `insumos` | CapacidadPermission | config_institucional | no | `institucion` | — | **hueco** |
| `depositos` | CapacidadPermission | config_institucional | no | `institucion` | — | **hueco** |
| `lotes` | CapacidadPermission | farmacia_stock | no | `insumo__institucion` | — | **hueco** |
| `stock` | CapacidadPermission | farmacia_stock | no | `deposito__institucion` | — | **hueco** |
| `movimientos-stock` | CapacidadPermission | farmacia_stock | no | `insumo__institucion` | ajuste, baja, consumo, ingreso, transferencia, trazar_lote | farmacia.tests_api.StockDeOtroHospitalTests (acciones de escritura) |
| `pedidos-stock` | CapacidadPermission | farmacia_stock | no | `origen__institucion` | alertas, entregar, preparar, rechazar | farmacia.test_pedidos_auditoria172, farmacia.tests_api (rechazar, DELETE, alta, alertas) |
| `redes` | CapacidadPermission | gobierno_plataforma | no | — | camas, tablero | **hueco** |
| `traslados` | CapacidadPermission | traslados_red | no | — | aceptar, cancelar, destinos, en_camino, no_llego, rechazar, recibido, solicitar | red.tests_api.TrasladosAPITests (no-llego, solicitar) |
| `accesos-clinicos` | PuedeAuditar | — | no | — | de_paciente | auditoria.tests (lista); test_aislamiento_ab_auditoria172 (de-paciente) |
| `consentimientos` | CapacidadPermission | padron_admision | sí | `ciudadano__institucion` | evidencia | test_aislamiento_ab_auditoria172 (lista, detalle, evidencia, PATCH, DELETE) |
| `obligaciones-financieras` | solo IsAuthenticated | — | no | — | aprobar_ajuste, movimientos, rechazar_ajuste, reducir | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `movimientos-dinero` | solo IsAuthenticated | — | no | — | aprobar, previsualizar_reintegro, rechazar, reintegrar | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `politicas-cobro` | PermisoCobros | — | no | — | — | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `pendientes-cobro` | PermisoCobros | — | no | — | recuperables, recuperar, resolver | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `reportes-dinero` | solo IsAuthenticated | — | no | — | comparativa | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `accesos-financieros` | PuedeAuditarFinanzas | — | no | `institucion` | — | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `reportes-finanzas` | solo IsAuthenticated | — | no | — | comparativa, evolucion | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `procesamiento-finanzas` | solo IsAuthenticated | — | no | — | — | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `hechos-costo` | PuedeVerCostosPaciente | — | no | `institucion` | corregir_snapshot | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `reportes-costos` | solo IsAuthenticated | — | no | — | — | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `concesiones-financieras` | CapacidadPermission | config_institucional | sí | `membresia__institucion` | editar_membresia, mias (solo IsAuthenticated), otorgar_multiples | finanzas.tests (lista, detalle, DELETE, alta/PATCH) |
| `prestaciones-costo` | PuedeConfigurarCatalogoCostos | — | no | `institucion` | atenciones_disponibles | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `componentes-costo` | PuedeConfigurarCatalogoCostos | — | no | `prestacion__institucion` | — | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `conceptos-gasto` | PuedeGestionarConceptosGasto | — | no | `institucion` | — | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `valores-componentes` | PuedeGestionarValoresComponentes | — | no | `componente__prestacion__institucion` | — | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `ajustes-costo` | PuedeCorregirCosto | — | no | `imputacion__hecho__institucion` | aprobar, rechazar | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `gastos` | PuedeVerGastos | — | no | `institucion` | aprobar, rechazar | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `ajustes-gasto` | PuedeCorregirGastos | — | no | `gasto__institucion` | aprobar, rechazar | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `expectativas-gasto` | CapacidadPermission | — | no | `institucion` | calendario, indicaciones, indicar | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `coberturas-actividad` | PuedeConfigurarRepartos | — | no | `institucion` | verificacion | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `reglas-reparto` | PuedeConfigurarRepartos | — | no | `institucion` | — | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `repartos-gasto` | PuedeVerRepartos | — | no | `gasto__institucion` | atribuciones | no relevado en este corte (dominio financiero; ver `PERMISOS_FINANCIEROS` en `casos.test_permisos_barrida`) |
| `simulaciones` | SoloSuperusuario | — | no | — | catalogo, finalizar | simulacion.tests (solo superusuario; A/B no aplica) |

## Rutas fuera del router (`config/urls.py`)

| Ruta | Control | Alcance | Cobertura |
|---|---|---|---|
| `/admin/` | Staff con permisos de modelo de Django | AUD-042: instituciones con `config_institucional` activo; el superusuario no se limita | `apps.test_admin_alcance_auditoria172` |
| `/api/health/` | Pública | Sin datos (estado de la base) | — |
| `/api/estado/` | `IsAuthenticated` | Global: estado de procesos, sin datos clínicos | **hueco de regla:** cualquier usuario autenticado lo ve |
| `/api/esquema/`, `/api/docs/` | `PuedeVerElEsquema` (abierto con DEBUG; con sesión en producción) | Global, sin datos | No relevado en este corte |
| `/api/auth/token/`, `refresh/`, `recuperacion/`, `restablecer/`, `confirmar-email/` | Públicas por diseño (credenciales o token) | — | `accounts.test_identidad_administrativa_auditoria172`, `accounts.test_credenciales_auditoria172` (en SQLite fallan por la outbox; ver validación) |
| `/api/auth/logout/`, `cambiar-password/`, `cambio-email/` | JWT propio | Cuenta propia | Mismas pruebas |
| `/api/archivos/` (subida) | `IsAuthenticated` + `historia_clinica` en la institución indicada | Institución del cuerpo | `apps.test_aislamiento_ab_auditoria172` (subir a B: 403) |
| `/api/archivos/descargar/<ruta>` | `historia_clinica` en la institución del archivo | Institución del archivo | `casos.tests_api.SubirArchivoTest`, `registros.test_descarga_archivo_auditoria172` |
| `/media/uploads/<ruta>` | Siempre 404 | — | Existente |
| `/api/mis-tareas/` | `IsAuthenticated` | Grupos del usuario; `?institucion=` | **hueco:** sin prueba A/B |
| `/api/puestos/<nodo>/` | `casos_operar` en la institución del flujo, más grupos | Institución del flujo | `apps.test_aislamiento_ab_auditoria172` (paso de B: 403) |
| `/api/pantalla/<token>/` | Pública por token impredecible | El nodo del token | **hueco:** sin prueba de alcance del token |
| `/api/mi/…` (portal del paciente) | Identidad de paciente, separada de `Usuario` | Cuenta del paciente | No relevado en este corte |
| `/fhir/` | Capacidad efectiva por institución | Institución | `fhir.tests`, `fhir.test_capacidades_institucionales_auditoria172` |

## Django Admin (AUD-042)

| Admin | Alcance | Notas |
|---|---|---|
| Instituciones, áreas, subáreas, grupos, boxes | Instituciones administradas | El staff no crea instituciones |
| Usuarios, membresías, legajos | Personas o membresías de esas instituciones; sin cuentas de referencia | Una cuenta que también pertenece a otra institución, o es estatal, queda en solo lectura; los roles estatales solo los asigna quien tiene gobierno de plataforma |
| Casos, eventos, filas, valores (inline) | `caso__institucion` | |
| Flujos, versiones, nodos | `…flujo__institucion` | Siguen en solo lectura |
| Formularios, campos | `…institucion` | La congelación no cambia |
| Ciudadanos, historias, estudios, recetas, archivos | `…ciudadano__institucion` / `institucion` | Firmas, autoría y readonly de archivos sin cambios |
| Fallos de auditoría | `institucion`; los fallos sin institución solo los ve el superusuario | La acción «Marcar como revisado» solo alcanza lo visible |
| Simulación (cuentas, sesiones, operaciones) | `institucion`; sin institución, solo el superusuario | Solo lectura |
| `auth.group`, portal (`CuentaPaciente`, `EventoPortal`) | **Sin alcance** | **Hueco/decisión:** los grupos de Django son globales, y la cuenta del portal es del paciente, no de una institución |

Lo cubren `apps.test_admin_alcance_auditoria172` (lista, cambio, borrado, historial, acciones bulk, choices de FK y M2M, filtros laterales, POST forjado, cuenta compartida, cuentas de referencia, staff sin `config_institucional` y superusuario), más la guardia que exige el mixin en cada `ModelAdmin` e inline registrado.

## Nivel de campo

- **AUD-008, valores de formularios de caso:** `ValorCampo` no tiene clasificación por campo. `Campo.origen` está declarado y documentado como sin uso. `CasoDetalleSerializer.valores`, `/api/valores-campo/` y la exportación CSV entregan los valores a cualquier miembro activo de la institución del caso (`protege_lectura = False`), incluidos roles que, según `docs/roles`, no operan casos (configurador, reportes, auditor). No hay regla escrita sobre qué valor es clínico ni quién lo ve. **Hueco de regla:** se deja sin implementar. Las opciones están en el reporte de este corte.
- Los eventos de caso ya no copian el valor de integraciones (corte AUD-007/008 anterior). El resto de los eventos no se clasificó.

## Huecos explícitos

1. **Sin prueba A/B** (marcados como «hueco» en la tabla): instituciones, áreas, subáreas, grupos, boxes, camas (solo FK), estadías de cama, campos, versiones de flujo, conexiones, disponibilidades, bloqueos, insumos, depósitos, lotes, stock y redes. Todos declaran `institucion_path` o alcance propio. Falta la evidencia HTTP.
2. **Agenda:** turnos y agendas solo prueban FK. No hay prueba de lista, detalle ni acciones (`cancelar`, `reprogramar`) sobre objetos de B.
3. **Casos:** se probaron `priorizar` y `cancelar`; faltan `avanzar`, `devolver`, `ausente` y las demás acciones del motor sobre casos de B.
4. **Lectura abierta a miembros:** casos, valores, eventos y filas no exigen capacidad para leer. Según `docs/roles`, configurador y reportes «no ven casos». Si eso es una regla de datos y no solo de menú, falta implementarla. **Decisión pendiente** (ver AUD-008).
5. **Dominio financiero:** financiadores, coberturas, autorizaciones y los 22 recursos de finanzas declaran su barrera, y `test_permisos_barrida` comprueba el 403 sin concesión. La matriz A/B de este corte no los relevó.
6. **`/api/mis-tareas/`, `/api/pantalla/<token>/`, `/api/estado/` y el portal `/api/mi/`:** sin prueba A/B ni regla explícita de alcance.
7. **Admin sin alcance:** `auth.group` y el Admin del portal (decisión pendiente). La acción de recuperación del Admin no recibe la institución, así que un staff institucional siempre ve «no admite recuperación» (comportamiento previo, sin cambios).
8. **Membresías en el Admin:** las áreas de una membresía se acotan a las instituciones administradas, pero no se valida que pertenezcan a la misma institución de la membresía, como hace la API.

## Mantenimiento

Agregar un viewset sin capacidad ni alcance hace fallar `apps.test_matriz_permisos_auditoria172`. Agregar un `ModelAdmin` sin el mixin hace fallar `apps.test_admin_alcance_auditoria172`. Las exenciones se justifican en esas pruebas. Para regenerar la tabla: recorrer `config.api.router.registry` con los mismos atributos.

**Actualización 19/10 (decisión del dueño sobre AUD-008):** `CasoViewSet`, `ValorCampoViewSet` y `EventoCasoViewSet` pasan a `protege_lectura = True` con `casos_operar`: configurador, reportes, auditor y plataforma ya no leen casos, valores ni eventos; los roles operativos sí. Esto cierra el hueco 4 y la lectura de AUD-008. La clasificación por campo (administrativo/clínico) queda como evolución posible, no implementada.
