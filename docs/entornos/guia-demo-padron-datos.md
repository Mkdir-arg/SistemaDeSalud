# Datos ficticios del padrón — issue 130

Esta guía describe `seed_padron_demo`, su manifiesto y los casos del ensayo. La
preparación de Compose, secretos, migraciones y arranque pertenece a
[guia-demo-padron.md](guia-demo-padron.md), del coordinador.
**Carga y runtime ejecutados el 12/10/2026.** Ver la
[guía local vigente](guia-demo-padron-local.md): trece afiliados iniciales y dos
adicionales de la importación probada, seis cuentas y siete recorridos reales.

## Destino y garantías

El comando exige simultáneamente `ENTORNO=demo`, PostgreSQL y `NAME=padron130`
exacto en la conexión Django. Desarrollo, producción, SQLite, `test_padron130`
y otras bases se rechazan. El nombre del proyecto Compose o un archivo env no
reemplazan estas comprobaciones.

En el primer uso, `Financiador`, `Afiliado`, `Usuario` y `Ciudadano` deben estar
vacíos. Un superusuario creado automáticamente también impide la carga: desactivar
los seeds globales del entorno aislado antes de arrancar, sin borrar datos para
sortear la guarda. No se crean pacientes, instituciones, cuentas de pacientes,
portales hospitalarios, casos, prestaciones, convenios ni cargos.

`DEMO_PASSWORD` debe provisionarse externamente en el proceso del backend, mediante
el archivo temporal de secretos del entorno. No hay valor por defecto y se rechaza
la contraseña pública heredada de demo. No copiar el secreto en comandos,
historiales, capturas, manifiestos o reportes. La primera carga usa esa clave para
los seis usuarios; no se reutiliza `clave_demo()` porque permite un default.

Las escrituras de base se realizan dentro de una transacción única. Un lock
advisory transaccional de PostgreSQL serializa ejecuciones simultáneas de este
loader antes de consultar el marcador, incluso con una base vacía. No coordina
escritores ajenos: realizar la primera carga antes del ensayo y sin otras cargas.
Una falla anterior a la confirmación revierte todos los registros nuevos.

No hay `flush`, borrados, resiembra ni actualización de un escenario existente.
La finalización se marca con el grupo sin permisos `padron130-v1`; las trece
instantáneas iniciales de `HistorialAfiliacion`, con origen `demo_padron130`,
conservan los IDs y números originales. El marcador se crea al final de la
misma transacción. No quitarlo ni editar esas instantáneas para rehacer la demo.

Al repetir, se reconstruye el manifiesto desde esas referencias y se devuelve
`existente: true`. Se conservan números/contactos editados, claves cambiadas,
roles, permisos y datos protegidos. No se exige otra contraseña para esa lectura.
Afiliados y planes agregados durante el ensayo en A/B son permitidos; el manifiesto
sigue enumerando solamente los trece casos originales. Se rechazan nuevos
financiadores, usuarios ajenos o pacientes incluso si existe el marcador.
Un marcador incompleto se rechaza; no hay reparación automática.

## Comando de carga del runtime autorizado

Una vez autorizado y preparado **el stack nuevo** por el coordinador, desde la
raíz de este worktree, conservar `$padron130Args` definido en la guía de ejecución
(proyecto `salud-padron-130`, env temporal `hen-padron130.env`):

```powershell
docker @padron130Args exec -T backend python manage.py seed_padron_demo --manifiesto /tmp/padron130-manifiesto.json --muestra-xlsx /tmp/padron130-muestra.xlsx
```

Las dos opciones son independientes y opcionales. Exigen archivos nuevos en un
directorio existente fuera del repositorio/código de la aplicación; no sobrescriben
archivos. Sin `--manifiesto`, la salida estándar devuelve JSON no secreto. Para
repetir conservando lo existente, ejecutar el mismo comando sin las opciones de
archivo, o elegir rutas nuevas.

Los archivos se escriben después de confirmar la transacción de base. Si el
filesystem falla, el comando informa que la carga ya quedó completa: repetir con
otra ruta nueva exporta los registros existentes. Base y filesystem no forman una
única transacción; un archivo exportado correctamente puede quedar si falla el otro.

```powershell
$padron130Artifacts = Join-Path $env:TEMP 'hen-padron130-artifacts'
if (Test-Path -LiteralPath $padron130Artifacts) { throw 'El directorio ya existe; elegir uno nuevo para no sobrescribir artefactos.' }
New-Item -ItemType Directory -Path $padron130Artifacts -ErrorAction Stop | Out-Null
docker @padron130Args cp backend:/tmp/padron130-manifiesto.json (Join-Path $padron130Artifacts 'manifiesto.json')
docker @padron130Args cp backend:/tmp/padron130-muestra.xlsx (Join-Path $padron130Artifacts 'muestra.xlsx')
```

El coordinador debe confirmar el nombre actual del proyecto/archivo env antes de
ejecutar. No usar los proyectos de demo compartida ni sus comandos de resiembra.

## Manifiesto para el recorrido real

Esquema versión 1: `escenario=padron130-v1`, `fecha_carga` ISO, `financiadores`
con claves A/B y `{id,nombre}`, `usuarios` con `{id,email,nombre,rol}`, `planes`
con IDs por código y `afiliados` por caso con `{id,numero,nombre,financiador_id}`.
`existente` sólo está en la salida estándar, no en el archivo persistido.

No incluye documentos personales, CUIL/CUIT, CBU, diagnósticos, condiciones ni
contraseñas. `integrante_5` es una clave neutra: el manifiesto no identifica una
condición de salud. `PADRON130_MANIFEST` apunta al JSON externo para e2e;
`PADRON130_PASSWORD` se provisiona por separado con la contraseña actual del ensayo.
Estas variables de e2e no sustituyen `DEMO_PASSWORD` del loader.

Las identidades ficticias, números de afiliado y correos son determinísticos.
Los IDs numéricos los asigna la base: consumirlos desde el manifiesto.
`fecha_carga` corresponde al registro inicial en la zona horaria de Django.
Las fechas usan `timezone.localdate()`/`timezone.now()` reales en el primer uso;
no se cambia el reloj del navegador ni del servidor. Repetir otro día no mueve
fechas ni devuelve al estado inicial los casos consumidos.

## Perfiles y alcance

Todos los correos usan el dominio reservado `padron130.example.test`, con el
nombre de cuenta de la tabla en minúsculas. Ninguno es superusuario ni staff.

| Cuenta del manifiesto | Organización | Rol | Salud | Cobranza | Escritura |
|---|---|---|---|---|---|
| admin | A | admin | Sí, concedido explícitamente | Sí, concedido explícitamente | Sí |
| operador | A | operador | No | No | Sólo bloques generales |
| salud | A | operador | Sí | No | General y salud |
| cobranza | A | operador | No | Sí | General y cobranza |
| auditor | A | auditor | Sí | Sí | Ninguna, aunque pueda leer bloques protegidos |
| orgB | B | admin | No | No | Sólo padrón general de B |

Las seis concesiones de bloques protegidos se registran explícitamente en eventos
administrativos con autor admin A ficticio. Esta habilitación pertenece sólo al
escenario: no cambia defaults de migraciones o de nuevas membresías. No concede
autorizaciones ni acceso a historia clínica. Cada perfil de A debe recibir rechazo
al pedir B y orgB debe recibir rechazo al pedir A; ocultar enlaces no acredita esto.

## Doce afiliados de A y uno de B

| Caso / número inicial | Datos preparados | Expectativa observable |
|---|---|---|
| titular / P130-A-01 | Dependencia, plan base, contacto, empleador, credencial externa y DNI verificado | Activo, derechos vigentes; grupo de cuatro familiares; buscar por documento/CUIL/apellido/número devuelve el mismo ID |
| conyuge / P130-A-02 | Vínculo explícito al titular | Navegación de familia conserva organización y contexto; no reutiliza datos del integrante anterior |
| menor / P130-A-03 | Hijo de 14 años relativos a la carga | Mismo titular, sin inferir parentesco por sufijo del número |
| estudiante / P130-A-04 | Hijo de 22 años; estudio presentado y vencido ayer; trámite en revisión | Vencimiento y trámite visibles, sin archivo adjunto; no completar antes de verificar/documentar lo requerido |
| integrante_5 / P130-A-05 | Hijo adulto; condición/parentesco adicional sólo en recurso protegido | Usuario salud/admin/auditor ve CUD, DBT y condición ficticia; operador/cobranza no los recibe |
| monotributo / P130-A-06 | Actividad independiente, plan superador; deuda informada y débito ficticio | Mora informada con fuente/fecha; derechos vigentes, sin suspensión automática |
| pasivo / P130-A-07 | 68 años, régimen pasivo, plan superador | Régimen distinto, no inventar empleador obligatorio |
| desempleo / P130-A-08 | Período de subsidio y baja efectiva en 30 días | Baja programada; fin informado posterior, sin corte automático |
| continuidad / P130-A-09 | Adherente, plan privado, baja administrativa efectiva hace 10 días | Baja administrativa y derechos vigentes coexisten; fin informado a 50 días no ejecuta finalización |
| legado / P130-A-10 | Sólo identidad legada, plan y desde | CUIL/contacto/legajo/credencial no informados; no completar por heurística |
| finalizado / P130-A-11 | Finalización prestacional explícita hace 10 días | Derechos finalizados; importación no lo reactiva |
| futuro / P130-A-12 | Desde a 30 días; trámite administrativo completo | Derechos futuros separados del trámite; no mostrar vigencia actual |
| orgB / P130-B-01 | Mismo documento ficticio que el titular A, identidad distinta por financiador | Un afiliado B; ningún vínculo familiar ni acceso cruzado a A |

La mora se guarda como `situacion=deuda`, con fuente y fecha declaradas. No hay
motor de cuotas, saldo, conciliación, débito real ni validación bancaria externa.
Los CBU de los tres casos de cobranza son texto de 22 dígitos, con ambos
verificadores locales válidos y banco sintético 000. CUIT/CUIL cumplen el algoritmo
local; el CUIT de cuenta pertenece al tercero ficticio y puede diferir del CUIL.
No enviarlos a bancos, ARCA, RENAPER u otros servicios.

El legajo contiene sólo metadatos: presentación, verificación, vencimiento y
referencia al original. Mostrar «Presentación registrada; sin archivo adjunto».
La credencial es un registro de emisión externa ficticia, no emisión del sistema.
La condición sensible y su vencimiento están exclusivamente en `SaludPadron`;
no se registra CUD como documento general del legajo.

## Muestra XLSX firmada y casos de importación

`--muestra-xlsx` usa en runtime la misma función `generar_plantilla` del servidor,
para A/admin y versión 2, con la clave de firma actual de ese entorno. Conserva
LEEME, Planes, encabezados y `_contexto`; sólo llena seis filas de Carga. No
crea importaciones ni modifica afiliados. No guardar el binario en Git ni copiar
una plantilla antigua de otra organización/entorno; la alternativa manual es
descargar `GET /api/financiadores/{A}/plantilla/?tipo=padron&version=2` autenticado.

| Fila Excel | Caso | Resultado esperado en preview |
|---|---|---|
| 2 | Titular ficticio nuevo, P130-IMPORT-01 | Válida |
| 3 | Familiar ficticio nuevo, titular_documento referido a la fila 2 | Válida, sólo por titular existente o fila válida anterior |
| 4 | Verificador de CUIL inválido | Rechazada, sin alta |
| 5 | CUIL ya usado por otro documento; tipo OTRO para aislar la colisión | Rechazada, exige resolver identidad sin fusión ni override |
| 6 | Familiar cuyo titular no existe en A ni en fila anterior | Rechazada, sin vínculo ni alta |
| 7 | Intento de cargar el afiliado finalizado | Rechazada, sin reactivación |

En el escenario inicial, preview devuelve dos válidas y cuatro rechazadas,
manteniendo 13 afiliados. Confirmar el mismo lote agrega exactamente dos (14 en
A, uno en B). Repetir esa confirmación no agrega afiliados ni historial. No
equivale a crear un lote nuevo con otra clave o corregir el archivo. La muestra
está pensada para el estado inicial; ediciones de identidad o consumos anteriores
del ensayo pueden modificar su resultado. El seed no los revierte.

No hay campos bancarios, de salud, bajas o reactivación en la muestra. Probar
encabezado bancario/salud en una copia de la plantilla debe rechazar el archivo
antes de guardar filas; no usar datos sensibles reales para la negativa.
El parentesco sensible se registra por el recurso protegido, no por XLSX.

## Recorrido y evidencia

1. Entrar como admin A, registrar fecha/IDs desde el manifiesto y verificar
   búsquedas, cinco regímenes y filtros administrativos/prestacionales separados.
2. Editar contacto con motivo, recargar y verificar con un GET real y otra sesión;
   revisar historial con autor/cambios. Una versión vieja debe devolver conflicto.
3. Recorrer titular/familia. Intentos de auto-vínculo, familiar de familiar y cruce
   A/B deben fallar en API. No inferir relaciones por número.
4. Revisar el trámite del estudiante y el legado; registrar/verificar metadatos,
   sin enlace ficticio a descarga de archivos. Transición explícita y auditada.
5. Comparar continuidad, baja programada, futuro y finalizado con sus derechos;
   mostrar el límite de fecha informada sin corte automático.
6. Comparar perfiles operador/salud/cobranza/auditor y requests reales: rechazo
   del bloque sin permiso y de toda escritura del auditor; revisar también
   historial, búsqueda, exportaciones e importación. No aceptar sólo ocultación UI.
7. Importar muestra, comprobar preview sin altas, confirmar sólo las válidas y
   repetir el mismo lote. Probar que el finalizado sigue finalizado.
8. Repetir el loader sin rutas de archivo: misma identidad y claves/contactos
   editados; ningún reset. Cargar evidencia sin claves, tokens o bloques sensibles.

Estos son criterios a demostrar; esta guía y los tests escritos no prueban que
las respuestas API/UI reales los cumplan. El coordinador debe revisar el diff
integrado y el responsable aceptar el ensayo antes de declararlo listo.

## Pruebas focales

El 2026-10-09, con autorización del coordinador, se ejecutó el comando SQLite
de abajo: **19 tests OK**, 1,558 segundos de tests, system check sin problemas;
BD efímera de tests destruida al finalizar. Incluyó una muestra firmada temporal
en tests, preview con dos válidas/cuatro rechazadas y confirmación idempotente.
Es evidencia indirecta del loader/servicios, no del ensayo PostgreSQL ni de la
interfaz real; no se generaron artefactos del entorno de demo.

Desde `backend`, con las dependencias existentes y settings aislado:

```powershell
python manage.py test apps.financiadores.tests_seed_padron_demo --settings=config.settings_financiadores_test --noinput
```

Este settings usa SQLite en memoria y no hereda la base de desarrollo. Los tests
de escritura sustituyen sólo la guarda de destino para usar la BD de tests; la
guarda de demo/PostgreSQL/nombre exacto se prueba separadamente sin acceder a BD.
Esto no prueba el lock real de PostgreSQL ni concurrencia entre procesos.

Para la BD de tests PostgreSQL local y dedicada, previamente provisionada por el
coordinador, `SALUD_TEST_POSTGRES_URL` externa debe cumplir la guarda del settings:

```powershell
python manage.py test apps.financiadores.tests_seed_padron_demo --settings=config.settings_financiadores_postgres_test --noinput
```

Ese segundo comando crea/usa `test_salud_financiadores_test`, nunca `padron130`.
No provisionar ni migrar bases compartidas para estos tests. La prueba multi-proceso
del advisory lock y el recorrido Playwright real siguen pendientes; ejecutar con
el manifiesto/password externos y el comando exacto que entregue el worker UI.

Cobertura escrita: destinos rechazados, clave obligatoria/default prohibido,
identificadores algorítmicos, archivos sin sobrescritura, vacío inicial, rollback,
trece casos/organizaciones, matriz de permisos, conservación de ediciones y claves,
datos ajenos/incompletos, manifest sin sensibles, plantilla runtime, preview y
confirmación idempotente. No se ejecutaron seed manual, Docker, migraciones sobre
PostgreSQL, pruebas de BD real, instalaciones, suite completa, build, commit ni
push. Sólo los tests invocaron el loader con la guarda de destino sustituida
sobre SQLite efímero.
