# Demo local del padrón lista para probar

Preparada el 12/10/2026 y actualizada el 13/10/2026 para el PR #133. URL: http://127.0.0.1:8230/financiadores/padron?financiador=1&estado=todos.

Entrar con `admin@padron130.example.test`. La contraseña y las seis cuentas están en el archivo local `C:\Users\Juanito\AppData\Local\Temp\hen-padron130-20261012\accesos.txt`. Es un archivo privado fuera del repositorio. Para comparar permisos, cerrar sesión y usar operador, salud, cobranza, auditor u organización B.

La aplicación queda encendida en el proyecto Docker `salud-padron-130`. Backend: http://127.0.0.1:8130/api/health/. Base PostgreSQL `padron130`, sin puerto expuesto al host. Los únicos servicios iniciados son db, backend y frontend; los puertos de la aplicación están ligados a 127.0.0.1. No se utilizaron otros proyectos ni bases compartidas.

## Qué probar

1. Buscar por DNI, CUIL, apellido o número; abrir «Filtros administrativos» para filtrar por régimen, trámite o fechas.
2. Abrir el titular P130-A-01, editar contacto con motivo, recargar y consultar la historia administrativa.
3. Navegar sus familiares; abrir P130-A-04 para legajo y vencimientos. El legajo registra presentaciones sin archivos adjuntos. Para observar un documento con trámite completo, pasar primero el trámite a «En revisión».
4. Comparar la baja administrativa y derechos actuales en P130-A-09; revisar mora informada en P130-A-06 con la cuenta de cobranza.
5. Usar los perfiles separados: operador no recibe salud/cobranza, auditor consulta sin escribir y B no accede a A.
6. Descargar la plantilla vigente o importar `C:\Users\Juanito\AppData\Local\Temp\hen-padron130-20261012\muestra.xlsx`. La muestra tiene dos filas válidas y cuatro rechazadas. Ya se aplicó durante el ensayo: repetir conserva los datos y no agrega duplicados.
7. Abrir «Columnas visibles», mostrar documento, CUIL o contacto, ocultarlos y restaurar la vista. Ordenar desde los encabezados y usar los filtros. Estado permite ver finalizadas y futuras; «Reactivar» conserva su acción explícita. Los filtros de texto se aplican al terminar de escribir, sin acumular una consulta ni una entrada de historial por tecla.
8. Pulsar «Editar» en una fila: abre la ficha administrativa completa en un solo diálogo. Cada bloque conserva motivo, revisión y guardado independiente; un conflicto no sobrescribe el cambio de otra persona. Familia, legajo, salud y cobranza mantienen sus reglas y permisos.
9. Elegir columnas y pulsar «Exportar XLSX». Descarga todos los resultados filtrados y ordenados, no sólo la página visible. Documentos e identificadores conservan texto y ceros. El límite es 5.000 filas; el exceso exige acotar filtros y no genera un archivo parcial. No incluye salud ni cobranza. Mientras hay criterios pendientes de aplicar, la descarga está bloqueada.

Se crearon trece afiliados ficticios iniciales (doce A y uno B), cuatro planes y seis cuentas. El recorrido de importación agregó dos afiliados A: quedan quince en total. Los ensayos de contacto y legajo restauran sus datos de partida y conservan el historial de prueba. El loader no resiembra ni restablece tus futuras ediciones.

## Validación realizada

Actualización del PR #133, sobre el código integrado `ce7d2ed` (backend idéntico a `92c1175`):

- 553 pruebas de financiadores y guarda de destino sobre PostgreSQL dedicado: pasan, sin omisiones. La base de tests se destruyó al finalizar; la base de la demo conserva sus quince afiliados, cuatro planes y seis membresías.
- 25 pruebas Node de edición, navegación, campos, estado/columnas y auditor CSS pasan; 12 recorridos de componente con datos ficticios e interceptores pasan. Los jobs de CI existentes ejecutan ahora estos checks del padrón.
- Los siete recorridos reales anteriores vuelven a pasar en 16,6 segundos, sin interceptar el backend. Se conservan firma/compatibilidad de importación, idempotencia, persistencia, 409, permisos y auditoría.
- Se reprodujeron y corrigieron las dos observaciones menores de la revisión final: un refresco de la misma consulta ya no cancela un XLSX iniciado y la búsqueda de afiliados en facturas recorta espacios antes de consultar. Seis pruebas focales de navegador con API interceptada pasan en 9,4 segundos; incluyen cambio de organización, borradores pendientes y descarga durante el refresco.
- Dos ensayos adicionales con navegador, API y PostgreSQL reales verifican: XLSX de catorce filas frente a una página de diez, ocho columnas elegidas, identificadores textuales sin fórmulas, rechazo de datos protegidos y otras organizaciones, edición desde el diálogo con historial y restauración exclusiva del campo del ensayo; finalizadas/futuras visibles, Reactivar accesible, once caracteres escritos producen un único GET, historial del navegador estable, exportación bloqueada durante el borrador y plantilla visible sin etiquetas de versión.
- Imágenes backend/frontend y build Vite pasan. El auditor revisa los tres chunks CSS y sus 282 clases; siete fixtures prueban que sigue rechazando clases ausentes, colisiones y builds viejos.

Los ensayos usan exclusivamente cuentas y afiliados ficticios. La auditoría de creación, cambios e importación se consulta desde «Historia administrativa»; salud/cobranza tienen historiales separados. La descarga deja un evento de generación autorizada, sin búsquedas ni datos personales; ese evento no demuestra recepción del archivo ni inmutabilidad. El formato técnico firmado sigue compatible internamente con archivos anteriores.

La incorporación a `main`, CI del head final y publicación en producción se informan en el PR; esta guía acredita la demo local. No se añadieron migraciones ni permisos. Para revertir este cambio se revierte el código del PR y se reconstruyen las aplicaciones; no se revierten las migraciones del padrón anterior ni se borran volúmenes o datos.

Evidencia histórica de la preparación inicial:

- Construcción de las imágenes backend y frontend; build Vite pasó.
- Migraciones aplicadas sólo sobre la nueva base `padron130`; `check` y `makemigrations --check --dry-run` pasaron.
- 159 pruebas Django sobre PostgreSQL dedicado `test_salud_financiadores_test`: todas pasan, sin omisiones. El runner destruyó esa base de tests. Incluye carrera entre desactivación/asignación de plan, dos altas exclusivas del mismo documento, revisión concurrente, familia, importaciones, permisos, seed y compatibilidad.
- Siete recorridos Playwright contra el frontend/backend/PostgreSQL reales: todos pasan. Contacto persistente en sesión nueva, conflicto 409, roles/organizaciones, fechas y derechos, búsqueda/filtros, legajo/trámite e importación XLSX con repetición.
- Diez pruebas Node de campos, edición y navegación pasan; `git diff --check` pasa. La portada y ambos health HTTP responden 200 después del último ensayo.
- Los tres fallos iniciales de Playwright se debían a selectores de la prueba y nombre de descarga: se corrigieron abriendo los filtros, usando roles accesibles de desplegables y verificando el nombre real más la cabecera ZIP del XLSX. No se interceptó la API.
- Claude revisó el código y los ajustes finales en dos tareas supervisadas. Los hallazgos P2 quedaron atendidos, sin nuevos P1/P2. Ambos workers se liberaron al terminar. Run `run_5d0066141173`; informes privados sin claves en Temp: `padron130-claude-review-20261012.md` y `padron130-claude-recheck-20261012.md`.

La aceptación del usuario y la obra social está pendiente de su prueba. No se realizó validación integral de los otros módulos. La cobranza es información declarada; no calcula deuda ni ejecuta débitos o cortes. No hay integraciones ARCA/ANSES/bancarias, emisión de credenciales ni adjuntos binarios. En Excel, los valores de parentesco deben seguir las opciones de la plantilla; confirmar vuelve a validar y puede rechazar relaciones familiares que cambiaron desde el preview.

## Arrancar de nuevo conservando tus datos

Desde `C:\Users\Juanito\orca\workspaces\SistemaDeSalud\issue-130-padron-demo`, con Docker Desktop iniciado:

```powershell
$padron130Args = @('compose', '-p', 'salud-padron-130',
    '--env-file', (Join-Path $env:TEMP 'hen-padron130-20261012.env'),
    '-f', 'docker-compose.yml', '-f', 'docker-compose.padron130.yml')
docker @padron130Args up -d db backend frontend
```

Para detener la demo conservando la base, usar `docker @padron130Args stop`. No borrar volúmenes ni ejecutar seeds globales. El env temporal contiene claves exclusivas de este ensayo; conservarlo localmente para reiniciar.

## Cambios de esta continuación

Se aplicó el parche revisado: `services.py`, `padron.py`, `views.py`, `test_padron130.py` y `CrearAfiliadoPadron.jsx`. Alta exclusiva rechaza duplicados sin cambiar la afiliación y conserva el POST incremental legado; el alta básica conserva el motivo. La asignación de plan bloquea/revalida el plan y rechaza afiliaciones finalizadas.

Se añadieron dos pruebas PostgreSQL en `test_concurrencia_padron130.py` y tres regresiones adicionales en `test_padron130.py`. `LegajoPadron.jsx` explica el orden de revisión; `FichaPadronAdministrativa.jsx` deshabilita cambiar el plan finalizado; `FichaAfiliado.jsx` distingue fecha de afiliación e instantánea del plan. Se corrigieron los selectores/descarga en `issue130-padron-real.spec.js`. La guía y los datos documentan el runtime ejecutado.

El checkout es `juanikitro/issue-130-padron-demo`, base `29886cf26e668c67a224a30145260e0fc62ace81`, El PR y su historial Git registran los commits y la incorporación; el ensayo descrito aquí acredita el runtime local. La aceptación de negocio no se infiere de los checks.

## Compatibilidad del despliegue — PR #131

Las columnas nuevas no nulas mantienen defaults en PostgreSQL y en Python. La migración `0012_padron_legacy_db_defaults` actualiza las instalaciones que ya ensayaron 0010/0011, sin editar esas migraciones ni borrar datos. Para una instalación todavía en 0009, Django usa el reemplazo `0010_padron_expansion_compatible`: ejecuta las tres migraciones en una sola transacción. Así las columnas y sus defaults quedan visibles conjuntamente antes de promover el nuevo backend. Conservar todos los archivos originales y el reemplazo; no eliminar migraciones durante este despliegue.

Cinco pruebas usan los modelos históricos anteriores para insertar afiliados, planes, membresías, historial y lotes sobre el esquema nuevo. Verifican compatibilidad de escritores y defaults sin permisos sensibles implícitos. El ensayo PostgreSQL ampliado pasó 165 pruebas, sin omisiones.

La plataforma no administra las designaciones de salud/cobranza, incluso cuando tiene una membresía real. La designación de otro administrador del financiador conserva el acceso explícito; los administradores ordinarios mantienen su operatoria. Las pruebas cubren rechazo de autoconcesión y concesión a otra cuenta sin crear usuarios ni emitir activaciones, ausencia de efectos, revocación y designación independiente.

El esquema OpenAPI usa nombres distintos para los enums de sexo del padrón y del paciente; el enum previo del paciente conserva su nombre. La generación estricta sin avisos pasa. Las pruebas de UI actualizadas verifican la corrección parcial con revisión y la clasificación opcional del plan.

El 13/10/2026 se reprodujeron dos deadlocks en PostgreSQL: contacto frente a familia y escritura protegida frente a revocación. Los cuatro locks nuevos del financiador usan `no_key=True`: siguen serializando cambios estructurales y designaciones, pero permiten confirmar las claves foráneas de auditoría antes de liberar afiliados o membresías. Las dos regresiones verifican persistencia, revocación y posterior acceso denegado. La batería ampliada pasó 177 pruebas (168 del padrón y sus guardas más nueve regresiones de entorno, esquema y checklist), sin omisiones; los siete recorridos reales Playwright volvieron a pasar sobre las imágenes actualizadas, conservando los quince afiliados. `makemigrations --check --dry-run` no detectó cambios.

En la revisión de seguimiento se reprodujo el mismo ciclo al confirmar importaciones v1 y v2: `select_related("financiador")` también bloqueaba el financiador mediante el `FOR UPDATE` del lote. La consulta ahora usa `of=("self",)`, conservando el lock del lote para idempotencia y el lock explícito de familia. Dos regresiones PostgreSQL capturaron `DeadlockDetected` antes del parche. Después, v1 escribe y conserva el contacto concurrente; v2 rechaza exactamente la preview obsoleta y sólo aplica tras generar otra, conservando el contacto y el control de revisión. Pasaron 33 pruebas de importación/concurrencia y la batería ampliada de 179 pruebas, sin omisiones. Lotes distintos del mismo financiador pueden intercalarse; las restricciones de identidad, los locks por afiliado/familia y la revisión v2 conservan las invariantes.
