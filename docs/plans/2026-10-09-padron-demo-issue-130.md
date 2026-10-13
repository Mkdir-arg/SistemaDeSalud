# Plan y estado: padrón de afiliados para la demo — issue #130

Estado al 12/10/2026: implementación y demo local verificadas. Pasaron 159 pruebas PostgreSQL sin omisiones, siete recorridos Playwright reales y diez pruebas Node. El usuario autorizó ahora commits, PR, revisión técnica con fixes, merge y despliegue. La aceptación funcional humana permanece pendiente. La guía local registra los accesos y el ensayo; el PR registrará las comprobaciones de integración.

Decisión más reciente del usuario (literal en esencia): incluir todo lo posible del padrón y, para los datos sensibles, elegir la forma cómoda y escalable. Las decisiones concretas que siguen en «Decisiones delegadas» son **recomendación del equipo bajo esa delegación**; no se atribuye al usuario el razonamiento detrás de cada una.

Fecha: 2026-10-09. Issue: https://github.com/Mkdir-arg/SistemaDeSalud/issues/130.
Base verificada: `29886cf26e668c67a224a30145260e0fc62ace81` (`origin/main`).
Worktree: `C:/Users/Juanito/orca/workspaces/SistemaDeSalud/issue-130-padron-demo`.
Branch: `juanikitro/issue-130-padron-demo`. Run Orca: `run_c1d0fcb75361`.

## Resultado que se busca

Para la demo de la semana del 12 al 18 de octubre, demostrar en el portal del financiador un padrón ampliado, operable y persistente: consultar/editar una ficha, navegar el grupo familiar, revisar el legajo y sus vencimientos, distinguir trámites/bajas de derechos efectivos, filtrar el listado e importar una muestra con errores verificables. No se presupone fecha exacta ni aceptación comercial.

La obra social evalúa un sistema completo. Esta entrega aborda el padrón, incluida la cobranza **administrativa informada** del afiliado (modalidad de pago, banco, CBU y CUIT del titular de la cuenta, estado informado); no demuestra recaudación, motor de cuotas, deuda, liquidaciones, recuperos ni contabilidad. Los tres PDF y la matriz de brechas del issue son las fuentes de requisitos; no sustituyen la validación normativa de reglas o layouts externos.

## Evidencia que condiciona la implementación

- `Afiliado` usa identidad estable por financiador + documento; el mismo documento normalizado se cruza con pacientes y casos. No sustituir esa clave por CUIL o por tipo/documento en esta entrega.
- `desde` y `finalizado_en` gobiernan cobertura, autorizaciones y acceso clínico. Las fechas y estados administrativos nuevos deben ser independientes.
- Hay importación v1 firmada, incremental y recuperable. Omitir no da bajas; importar no reactiva finalizados ni crea pacientes hospitalarios.
- El historial existente no registra todas las correcciones patronímicas: un cambio de nombre puede guardarse sin historial. La ampliación debe cubrir esos cambios sin perder la línea de plan/vigencia.
- Las pruebas actuales de interfaz del financiador interceptan la API. Sirven para regresiones de UI; no acreditan persistencia real.
- Familia/parentesco y CUD pueden revelar información de salud. Ocultar un control visual no protege API, historial ni JSON de importaciones.

## Corte recomendado y alternativas

**Recomendación del equipo:** ampliar el módulo y ficha existentes con campos tipados aditivos, historial extendido, grupo familiar de un nivel y legajo administrativo; incluir importación v2 compatible con v1 y un recorrido contra backend real.

Alternativa breve: consulta ampliada y corrección básica, conservando importación v1 y sin transiciones de legajo/baja. Reduce trabajo, pero pierde criterios explícitos del issue y no permite considerarlo implementado.

Alternativa más amplia: adjuntos binarios, cortes prestacionales automáticos e integraciones de cobro reales. Agrega almacenamiento, retención y cambios asistenciales/operativos. Requiere decisiones adicionales y no se recomienda como primer corte de demo. (Los permisos sensibles nuevos sí entran en el corte, ver «Decisiones delegadas».)

En almacenamiento, se recomienda extender `Afiliado` y `HistorialAfiliacion` en lugar de agregar una ficha 1:1 y auditoría administrativa paralelas. Gana reutilización y filtros directos; aumenta el tamaño de los modelos existentes y exige mantener diferenciados los tipos de historial. Revisar esta decisión si nuevos requisitos de grupos, legajos o permisos exceden esta separación.

## Contratos y alcance propuestos

### Datos e identidad

Campos aditivos, inicialmente opcionales para el legado: tipo de documento, CUIL, nombres/apellidos, sexo, nacimiento, nacionalidad y estado civil; domicilio estructurado, CP, localidad/partido/provincia, teléfono/celular/correo. Contacto y domicilio laboral opcionales deben poder informarse sin bloquear altas anteriores.

CUIL informado: validación algorítmica, coherencia con DNI cuando corresponda y unicidad dentro del financiador. Una discrepancia se rechaza o pasa a revisión según su naturaleza; nunca se fusiona automáticamente. Conservar número/documento como texto y sus ceros. No inferir grupo o parentesco a partir del sufijo del número. Colisiones de documento entre tipos siguen como limitación de la identidad actual: no ocultarlas ni resolverlas inventando IDs.

Régimen: dependencia, monotributo, pasivo, desempleo y adherente; empleador, actividad y período de subsidio aplicables. Plan base/superador/privado con tipo explícito; alta administrativa, delegación y comienzo de derechos conservando la semántica de `desde`.

### Familia y auditoría

Vínculo explícito al titular del mismo financiador, de un nivel. Prohibir auto-vínculos, ciclos y familiares de familiares. Constraints compatibles con el legado y validación transaccional de ambas filas bloqueadas en orden estable; demostrar concurrencia en PostgreSQL. Dar baja al titular no da baja automáticamente a sus familiares.

Extender `HistorialAfiliacion` con cambios anterior/nuevo, origen y lote, preservando instantáneas existentes y atribución al usuario real en simulación. El historial de plan/vigencia sigue disponible aunque existan muchas ediciones administrativas; el historial completo se pagina aparte. No incluir valores sensibles en el historial general ni en motivos de auditoría accesibles a otros roles.

Edición parcial con motivo y conflicto de versión cuando otra persona modificó el afiliado. Invalidar las consultas de listado y ficha; navegar entre familiares no conserva detalles/modales/autorizaciones del integrante anterior.

### Legajo, bajas y condiciones sensibles

Propuesta para esta demo: registrar tipo/estado del documento, presentación, verificación, vencimiento y referencia al original. **Sin guardar archivos PDF/imágenes.** La ficha debe decir “Presentación registrada; sin archivo adjunto”. Registrar credencial emitida externamente (tipo y fecha), sin presentarlo como emisión digital propia.

Transición de trámite explícita y auditada. Requisitos para completar trámite pendientes de confirmar; propuesta mínima: ninguna documentación registrada pendiente/observada y credencial informada. No considerar automáticamente completos los legajos antiguos sin datos.

Separar estado administrativo de derecho efectivo. Registrar solicitud/baja efectiva/fin prestacional informado y motivo. Baja futura = programada; baja efectiva puede coexistir con derechos vigentes. La fecha de fin informada **no ejecuta corte automático**. La UI muestra el derecho actual calculado por las reglas existentes y advierte si falta finalizar; no promete una gracia legal calculada ni “cobertura plena”. Reactivación conserva el historial de cualquier novedad administrativa que se retire.

CUD, DBT y crónicas en recurso protegido, con correcciones trazables y auditoría mínima sin detalles sensibles en eventos generales. Acceso por el permiso nuevo **condiciones de salud** (ver «Permisos sensibles»); se descartó reutilizar la designación de autorizaciones para no acoplarla a estos datos. Sin ampliar consultas a historia clínica.

Sin ese permiso, la API no entrega diagnóstico, alerta CUD ni parentesco revelador de discapacidad. Para v2 de demo, rechazar el parentesco sensible en XLSX y cargarlo por el flujo protegido: `Importacion.filas` conserva valores crudos y el enmascaramiento de pantalla no basta. La limitación debe verse en plantilla/errores/guion; no reemplazar el parentesco silenciosamente.

### Cobranza administrativa informada

Bloque protegido por afiliado: modalidad de pago (lista corta y cerrada, p. ej. débito por CBU, descuento por recibo, transferencia, ventanilla), banco, CBU y CUIT del titular de la cuenta, estado administrativo informado con fecha y fuente. Todo el bloque, incluida la modalidad, queda bajo el permiso de cobranza.

- CBU como texto de 22 dígitos con validación de los dos dígitos verificadores; CUIT con validación algorítmica. El CUIT de la cuenta puede diferir del CUIL del afiliado (cuenta de un tercero o del titular del grupo); no se fuerza la coincidencia.
- El estado de cobranza es **informado**: no lo calcula el sistema, no hay cuotas, deuda, vencimientos de pago ni conciliación. La UI lo rotula como «informado» con fecha y fuente.
- El estado administrativo **nunca** modifica `desde`/`finalizado_en` ni corta derechos, autorizaciones o acceso clínico. Una mora informada no ejecuta suspensión.
- Sin integraciones reales (bancos, débito automático, AFIP/ARCA, RENAPER); la validación es local.

### Permisos sensibles

Dos permisos nuevos e independientes en `MembresiaFinanciador`: **condiciones de salud** (CUD, DBT, crónicas, parentesco revelador) y **cobranza** (bloque anterior).

- Predicado: financiador activo + membresía activa + permiso concedido. Default **denegado** para todas las membresías, incluidas las de admin existentes al migrar.
- Independientes entre sí, de `resuelve_autorizaciones` y de `puede_consultar_historia_clinica`. No amplían ni reutilizan el acceso a historia clínica.
- Lectura con el permiso; escritura con el permiso y un rol con escritura (el auditor puede tener lectura, nunca escritura). Plataforma sin acceso por defecto.
- Sólo un admin del financiador concede o revoca; la concesión queda auditada con autor real.
- En «Ver como» aplican los permisos del perfil simulado; la autoría es del usuario real.

### Invariantes del contrato (para la revisión focal)

1. Sin permiso, la API **omite** el bloque sensible (no `null`, no valor parcial enmascarado) y expone `permisos: {salud, cobranza}` para que la UI decida qué mostrar.
2. Ningún valor sensible o bancario aparece en listado, búsqueda, filtros, ordenamiento, historial general, motivos, logs, mensajes de error de validación ni `Importacion.filas`. No se busca ni filtra por CBU, CUIT de cuenta ni diagnóstico.
3. Los cambios protegidos se auditan en un registro visible sólo con el mismo permiso (anterior/nuevo); el historial general registra a lo sumo «datos protegidos actualizados», sin valores ni nombre del dato de salud.
4. La edición protegida no revela existencia de datos a quien no tiene el permiso por cambios de versión o conteos de historial: usar versión propia del bloque o no incrementar la versión general.
5. Importación v2: bancarios y sensibles fuera de la plantilla; un encabezado sensible o bancario se rechaza **antes** de persistir filas, porque `Importacion.filas` guarda los valores crudos.
6. Legajo sólo con metadata (tipo, estado, fechas, referencia al original); sin `FileField`, upload ni almacenamiento de archivos.
7. Ninguna regla nueva (cobranza, legajo, trámite, baja administrativa) modifica derechos efectivos de forma automática.

### Listado e importación

Buscar por DNI/documento, CUIL, apellido y número. Filtrar en servidor por plan, estado administrativo, derecho actual y rangos de altas/bajas; conservar paginación, URL y aliases de filtros antiguos. Estados con texto y color, además de las fechas/motivo accesibles.

Plantilla v2 firmada y versionada: identidad, contacto, régimen, titular/parentesco ordinario, trámite y credencial. Mantener v1 válida. Celda nueva vacía = no informar; no borrar datos existentes. Titular debe existir o estar en fila válida anterior del lote; revalidar al confirmar y explicar el orden en plantilla/guía.

Vista previa sin efectos; filas conflictivas a revisión o rechazo; sólo válidas aplicadas; reintentos sin duplicar identidades ni efectos. No habilitar un override de identidad por reutilizar el mecanismo de consumos. Excluir bajas/reactivaciones, condiciones sensibles y bancarios del archivo de demo.

## Trabajo por agentes y propiedad

| Etapa | Responsable propuesto | Propiedad y salida |
|---|---|---|
| 1. Contrato y migración | Codex backend | Modelos, validaciones, permisos, servicios y pruebas focales; contrato publicado en este plan |
| 2. API e importación | Codex backend | Listado/ficha/edición/familia/legajo/historial y v2 compatible; sin efectos prestacionales nuevos |
| 3. Interfaz | Codex frontend, tras contrato mínimo | Ficha por bloques, edición, familia, filtros, estados y errores; sólo archivos de frontend |
| 4. Datos y ensayo | Codex validación | Loader no destructivo, muestra XLSX y guion; base nueva y pruebas reales |
| 5. Revisión | Claude | Diff integrado, invariantes, permisos/migraciones y regresiones; fixes vuelven al propietario |
| 6. Aceptación | Usuario/responsable de demo | Revisar recorrido, entender límites, evaluar fallos y aceptar resultado demostrado |

Sin editores concurrentes sobre el mismo archivo. La autorización más reciente incluye commit/push, PR, revisión con fixes, merge y despliegue. Se preservan los datos de la demo y los cambios concurrentes de otros checkouts.

Áreas probables: `backend/apps/financiadores/{models,services,vigencias,permisos,serializers,views,importaciones}.py`, migración aditiva y tests; páginas `PortalFinanciadores`, `FichaAfiliado`, `ImportacionFinanciador`, helpers API y e2e; guía en `docs/entornos/guia-demo-padron.md`.

## Entorno y validación del ensayo autorizado

Proyecto Docker nuevo `salud-padron-130`; PostgreSQL 16 con base `padron130`, volúmenes/red propios, sin puerto de BD al host. App compilada en `127.0.0.1:8230`, API en `127.0.0.1:8130`; revalidar disponibilidad antes de iniciar. Compose base y overlay exclusivo `docker-compose.padron130.yml`, siempre `-p`/`-f`/`--env-file` explícitos, sin overlay demo ni override desarrollo existentes. Comandos en `docs/entornos/guia-demo-padron.md`.

Entorno demo local, seeds globales desactivados, sin RENAPER/correo/integraciones reales. Arrancar sólo db/backend/frontend. Env y cuentas temporales fuera del repo; no imprimir contraseñas/tokens ni adjuntarlos a evidencia. Loader acotado a base nueva, rechaza producción y no borra datos.

La autorización solicitada abarca: construir el stack nuevo, instalar dependencias existentes del lockfile y navegador de pruebas si faltan, migrar únicamente su base, cargar datos ficticios y correr checks/pruebas focalizadas más el build necesario para la demo. La autorización posterior incluye desplegar el código integrado y actualizar la demo. No autoriza borrar volúmenes o reinicializar bases existentes. La migración es aditiva; los datos ficticios del padrón se cargan sólo en su base dedicada.

Checks: migraciones consistentes y aplicación sobre base descartable; tests de financiadores afectados y regresiones de identidad/vigencia/HC/FHIR; concurrencia de vínculos en PostgreSQL; UI focal; Playwright contra backend real sin mocks, con preflight que falla si faltan datos/credenciales/health. Tests con mocks y runtime se reportan separados. No suite global de demo compartida ni éxito por tests enteramente omitidos.

## Recorrido y evidencia de aceptación

Dataset: doce afiliados ficticios del financiador A y uno del B; titular, cónyuge, menor, estudiante, discapacidad, cinco regímenes, en trámite, baja administrativa con continuidad, finalizado, futuro y legado incompleto. Ningún dato de persona real; no exigir Ciudadano o cuenta del portal para estar en el padrón. Fecha del ensayo se registra en metadata, sin falsear sólo el reloj del navegador.

1. Cuatro búsquedas encuentran el mismo ID; filtros y retorno al listado mantienen contexto.
2. Editar contacto, guardar, recargar y verificar en sesión nueva y GET real; historial muestra autor/motivo/anterior/nuevo.
3. Navegar titular/familia y comprobar negativas de auto-vínculo, cruce de financiador y ciclo.
4. Mostrar cinco regímenes, datos condicionales y ausencia explícita de datos del legado.
5. Registrar presentación/vencimiento y credencial; transición auditada de trámite, mostrando que no hay adjunto.
6. Distinguir baja programada, administrativa y finalización prestacional; alertas sin cortes automáticos.
7. Cuenta con permiso de salud ve condiciones; cuenta con permiso de cobranza ve el bloque bancario; una cuenta con sólo uno no ve el otro; sin permisos no reciben campos, parentesco sensible, bancarios ni exportaciones indebidas. Un estado de cobranza en mora informada no cambia el derecho actual.
8. Importar muestra con válidas, CUIL inválido, conflicto de identidad, familiar sin titular e intento de reactivación; preview sin cambios, confirmar sólo válidas y repetir sin efectos duplicados.
9. Correcciones conservan plan/vínculos/cupos/autorizaciones/cargos históricos; auditor no escribe y B no obtiene datos de A.

Evidencia por criterio: SHA, ambiente, comandos/resultados, IDs ficticios y capturas sin secretos. El responsable recorre la demo antes de declararla lista. Pruebas verdes no equivalen a aceptación ni comprensión humana.

## Decisiones delegadas (recomendación del equipo bajo delegación del usuario)

Aprobado por el usuario: alcance «todo lo posible del padrón» y delegación de la forma de proteger datos sensibles. Bajo esa delegación, el equipo eligió:

- Corte con importación v2 compatible con v1, legajo por metadatos sin archivos y credencial registrada externamente.
- Estados/fechas administrativos sin corte prestacional automático; finalización explícita; legado sin nuevos obligatorios.
- Cobranza administrativa informada (modalidad, banco, CBU, CUIT del titular de la cuenta, estado informado) dentro del corte, sin motor de cuotas ni integraciones.
- Dos permisos nuevos independientes (salud y cobranza) por membresía activa, denegados por defecto, sin expandir historia clínica. Motivo: es la forma que escala a más roles sin acoplar autorizaciones a datos sensibles; se pierde la comodidad de que los admin existentes vean los datos sin una concesión explícita.
- Familia de un nivel, identidad legada y validación de CUIL informado; no inferir numeración familiar sin muestra del cliente.

Revisitar si el cliente pide cuotas/deuda reales, roles por campo más finos que dos permisos o adjuntos.

## Pendiente de autorización o definición

- Entorno Docker y paquete de validación aislados descritos arriba: **sin autorización**. No hay checks de runtime aprobados.
- Día concreto, responsable comercial y regla exacta del legajo/numeración. No activar reglas normativas a partir de los PDF.
- Brechas declaradas de este corte: adjuntos, emisión propia de credencial, cortes/gracia automáticos, motor de cuotas/deuda e integraciones de cobro reales.
- Comprensión y aceptación del usuario no demostradas.

Reversión: antes de incorporación, conservar respaldo de datos nuevos; retirar escrituras nuevas manteniendo lectura e históricos. Una migración inversa destruye las columnas/tablas añadidas y sólo puede ensayarse sobre datos descartables. Nunca usarla como recuperación automática de un entorno con datos reales.

## Estado de esta sesión

Claude completó análisis de dominio/riesgos y una segunda revisión a pedido del coordinador. Codex completó UX, dataset, guion y validación propuesta. El coordinador integró diferencias y este plan; baja futura y fuga de parentesco sensible quedan explícitas.

Actualización 2026-10-09: tras la decisión del usuario, Claude refinó alcance, cobranza, permisos e invariantes del contrato. Codex entregó backend, interfaz y datos ficticios con propiedad separada; el coordinador leyó sus reportes, integró guías/entorno y preservó las limitaciones de evidencia. No se hizo aún la revisión técnica completa del diff: la elección de primera lectura se consultó al usuario y sigue pendiente de respuesta.

Entrega de backend: `task_4aa6ec56ed1a` / `ctx_53f1385a028a`, completada y terminal liberada. Entrega de datos ficticios: `task_412c50a6244d` / `ctx_7f09708f67dd`, completada y terminal liberada. Interfaz: `task_5f2f2e2107d6` / `ctx_dad4b383878f`, completada y terminal liberada. La revisión integrada completa y el ensayo siguen pendientes; el issue permanece abierto.

### Evidencia focal ejecutada

Desde `backend`, settings `config.settings_financiadores_test`: SQLite efímero, sin heredar la BD de desarrollo. Las tandas se solapan; no sumar sus cantidades como casos únicos.

| Comprobación | Resultado |
|---|---|
| API padrón, importaciones, vigencias, ficha, clasificación de simulación | 124 casos: 121 aprobados y 3 omitidos por necesitar PostgreSQL |
| API padrón, importaciones, historia del financiador, clínica, historial y legado | 132 casos: 131 aprobados y 1 omitido por necesitar PostgreSQL |
| Loader ficticio y muestra firmada, `apps.financiadores.tests_seed_padron_demo` | 19 aprobados; guarda de destino sustituida sólo dentro de tests de escritura |
| Guardas de URL/configuración PostgreSQL, `config.test_postgres_test_guard` | 3 aprobados, sin conexión PostgreSQL |
| Payloads parciales, campos, errores, vencimientos y navegación frontend | 10 pruebas Node aprobadas, ninguna omitida |
| Sintaxis frontend e imports locales | 19 archivos parseados y 87 imports resueltos; no build ni React ejecutado |
| `manage.py check` y `makemigrations --check --dry-run` con settings aislado | Sin problemas; sin cambios de modelos pendientes |
| Overlay YAML y sintaxis PowerShell de la guía | Válidos; no ejecutan Docker ni los comandos de la guía |

Comandos de las dos tandas de regresión, ejecutados con `--settings=config.settings_financiadores_test --noinput --verbosity 1`:

```text
python manage.py test apps.financiadores.test_padron130 apps.financiadores.test_concurrencia_padron130 apps.financiadores.test_importaciones apps.financiadores.test_api apps.financiadores.test_vigencias apps.financiadores.test_ficha_afiliado apps.simulacion.tests.ClasificacionDeCamposTests
python manage.py test apps.financiadores.test_padron130 apps.financiadores.test_importaciones apps.financiadores.test_ficha_historia apps.financiadores.test_clinica apps.financiadores.test_historial apps.financiadores.test_legado
```

Desde la raíz del worktree, las diez pruebas de frontend se ejecutaron con:

```text
node --test frontend/src/lib/padronNavigation.test.mjs frontend/src/lib/padronEdicion.test.mjs frontend/src/components/financiadores/padronCampos.test.mjs
```

Archivos principales para la revisión: backend `padron.py` (`registrar_ficha`, `editar_ficha`, `editar_protegido`, `guardar_legajo`), `permisos.py`, `importaciones.py` y migraciones 0010/0011; frontend `FichaPadronAdministrativa.jsx`, `RecursoProtegidoPadron.jsx`, `CrearAfiliadoPadron.jsx`, `FichaAfiliado.jsx` y `PortalFinanciadores.jsx`. El contrato HTTP se publicó primero en `C:/Users/Juanito/AppData/Local/Temp/padron-130-api-contract.json`, versión 130.1, y sus adiciones se coordinaron por buzón.

La aplicación de migraciones sobre SQLite de tests no prueba su aplicación/concurrencia sobre PostgreSQL. Tres casos nuevos de concurrencia quedaron escritos y omitidos explícitamente en SQLite, incluido importación versus edición familiar. Tampoco se ejecutaron FHIR específico, build, navegador real, instalación de dependencias, seed manual, Docker, migración inversa, commit, push o deploy.

Hubo dos inspecciones iniciales de variables de entorno que mostraron tokens internos de Orca en salidas locales de herramientas; el coordinador lo advirtió sin reproducir valores. Los workers reportan que no copiaron esos valores a código, guías, manifiestos o reportes. No enumerar variables de entorno ni adjuntar esas salidas como evidencia.

Skills: `orchestration` y `orca-cli` para coordinación y aislamiento con procedencia real; `brainstorming` en la propuesta UX para comparar cortes y explicitar aceptación; `domain-modeling` para distinguir estados administrativos, finalización y cobranza informada en `CONTEXT.md`; `vercel-react-best-practices` para separar consultas/estado/componentes; `playwright` para preparar pruebas reales explícitas sin ejecutar instalaciones. No se usó `frontend-design`: el portal ya tiene patrones que se conservaron. No se validó comprensión o aceptación del usuario y no se afirma que el issue ni la demo estén terminados.
