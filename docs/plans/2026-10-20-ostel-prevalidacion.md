# OSTEL: tramo local de prevalidación técnica (#180)

**Estado vigente 21/10:** además del lector técnico, la continuación autorizada implementa importación OSTEL con aplicación parcial y subsanación. Ambos formatos de padrón tienen «Habilitar cobertura» marcado por defecto; la elección sólo afecta altas nuevas. Las personas existentes conservan su habilitación y cualquier discrepancia con la elección del lote bloquea la fila hasta revisión con motivo. Se retiró el selector de contenido; las bajas siguen como evidencia no aplicable. Implementación local commiteada (`e752896`, documentación `f8299e1`), migración 0013 aplicada a SQLite ficticia y comprobación del usuario «probado», sin detalle por escenario. Ver [Estado vigente](../funcionalidades/financiadores-cobertura/ostel-aceptacion.md) y [Prueba local](../funcionalidades/financiadores-cobertura/ostel-prueba-local.md) para alcance, evidencia y límites. PostgreSQL/concurrencia, volumen integral, CI y publicación siguen pendientes; OSTEL aún debe responder.

## Historial técnico anterior al cierre local

Las secciones siguientes conservan las condiciones de cada entrega anterior.
Sus menciones a revisión técnica sin aplicación, ausencia de commits o
aceptación humana pendiente no describen el estado vigente indicado arriba.

**Estado de la ampliación autorizada el 20/10/2026:** lector integrado a
**Importar Excel → Formato del archivo**, con registro extensible de formatos,
plantilla por formato y preferencia local por usuario. Se retiró el botón
independiente “Revisar Excel OSTEL”. Entorno web local disponible para aceptación.
Las secciones iniciales registran la primera entrega del lector puro; el
contrato de integración y la evidencia actual están al final de este documento.

**Continuación tras respuestas parciales de OSTEL:** se actualizaron la ayuda
del formato y la matriz de aceptación de #185. Se agregaron siete escenarios
ficticios (27 escenarios, 32 lotes, 64 XLSX en total) sobre identidad,
contradicciones, categorías, parentescos y cambios administrativos. El lector,
API, plantilla e importador conservan su contrato técnico. Las definiciones y
los bloqueos vigentes están en la sección «Respuestas OSTEL recibidas el
20/10/2026 y avance autorizado» de `ostel-aceptacion.md`.

## Alcance y plan ejecutado

Solicitud explícita del usuario: desarrollar en el worktree Padron un lector
puro sin DB para las 39 columnas OSTEL. No requiere nuevas decisiones de
homologación. Base inspeccionada: `a91faf46290e3f71eb59fc81ba78f04b809d8d39`.

1. Leer el issue y los controles de `importaciones.py`, sin modificarlo.
2. Implementar una función sobre bytes con controles ZIP/XML y diagnóstico por
   posición, sin importar Django, modelos, permisos ni el importador.
3. Probar con entradas ficticias propias, incluidos 5.754 y 7.486 registros en
   archivos separados. No depender de los archivos del otro agente.

Se eligió una función pura frente a un servicio: no hay estado, persistencia ni
colaboradores que justifiquen un servicio. Los controles actuales no son
reutilizables por importación directa sin cargar la capa Django. Se reproducen
sus comprobaciones de tamaño, compresión, entradas duplicadas, DTD/entidades,
macros, objetos y relaciones externas usando las dependencias ya instaladas.
Esta duplicación acotada queda explícita; una extracción compartida sería otro
cambio, fuera de la autorización actual.

## Contrato local

`prevalidar_ostel(contenido: bytes) -> Resultado`.

- Entrada en memoria; no abre rutas, escribe archivos, usa red ni conecta DB.
- Reconoce `Hoja1` y `afimotook`, por separado o juntas. Las hojas desconocidas
  generan anomalías sin copiar sus nombres al diagnóstico.
- Compara exactamente las 39 cabeceras de la fila 1, en orden. No normaliza,
  renombra ni homologa columnas. Aun con cabeceras incorrectas, conserva filas
  por posición: no se deben interpretar como campos homologados.
- `filas[hoja]` contiene filas no vacías con número original y celdas ordenadas.
  Cada celda conserva valor XML, tipo XLSX, formato numérico, texto y atributos
  de fórmula. Estilos y textos compartidos se resuelven por las relaciones del
  workbook, incluyendo rutas internas alternativas.
  Textos compartidos y rich text se resuelven a su texto sin recortarlo.
  No conserva estilos visuales, anotaciones ni toda la estructura del archivo.
- Números y seriales de fecha siguen como texto XML; no se convierten a float
  ni fecha. Un texto `000123` se conserva; un número `123` con formato `000000`
  conserva ambos componentes. No se reconstruyen ceros ya perdidos en origen.
- Una fila vacía sólo tiene valores ausentes/cadenas vacías y ninguna fórmula.
  Espacios, cero, booleanos y fórmulas sin resultado cuentan como contenido.
- Los duplicados son repeticiones de celdas no vacías con igual posición,
  valor, tipo, formato y fórmula dentro de una hoja. Las filas con fórmulas
  compartidas, matriciales u otras dependientes de contexto se excluyen del
  diagnóstico de duplicados, porque no se evalúan referencias. No identifican
  personas ni implican movimientos repetidos; no se deduplican ni eliminan.
- Las anomalías contienen código, hoja reconocida, fila/columna (base 1) y,
  para duplicados, fila original. Incluyen estructura, fórmulas, errores Excel
  y tipos XML incompatibles. Números: sintaxis ASCII; fechas XML: soporte ISO
  de openpyxl ya instalado, sin convertir el valor retornado. Los índices de
  texto compartido/estilo inválidos abortan con hoja, fila y columna seguras.
  No hay reglas por campo OSTEL, ni inferencias
  sobre TIPODOC, TIPO, NROREF, FECVTO, MOTIVO, parentesco o derechos.
- `resumen` contiene conteos sin valores personales. `filas` es contenido
  privado, excluido del repr del resultado: no debe loguearse ni serializarse
  indiscriminadamente. El módulo no emite logs.
- Un paquete ilegible/inseguro o fuera de límites lanza
  `ArchivoOstelInvalido`, sin resultado parcial ni valores del archivo.
  Un resultado sin anomalías NO autoriza una importación.

## Límites y comprobaciones

Límites exclusivamente locales, sin cambiar configuración: 5 MiB comprimidos,
25 MiB declarados descomprimidos, 128 entradas ZIP, 10.000 posiciones de datos
por hoja y 256 columnas inspeccionables. Se ignora la dimensión declarada de
la hoja; se verifican coordenadas reales y orden estricto de filas.
Columnas adicionales con contenido se conservan y reportan.

Se cargan árboles XML en memoria bajo el límite descomprimido. Ese límite no
equivale a un límite de RAM ni de CPU: los objetos Python consumen más memoria.
No se ofrece aislamiento de proceso ni timeout estricto. Antes de exponerlo
como API o aceptar carga masiva se necesita otra evaluación operativa.

Validación autorizada, desde `backend`:

```powershell
python -B -m unittest apps.financiadores.test_ostel_prevalidacion -v
```

20 pruebas focalizadas pasaron: preservación textual y formatos, vacíos y duplicados,
ambas hojas, ambos volúmenes separados con 39 celdas por fila, encabezados,
columnas adicionales, fórmulas/errores/tipos XML, dimensiones incorrectas,
archivos inválidos, límites, XML/DTD, relaciones externas, macros/objetos,
entradas duplicadas, compresión no admitida, shared strings, coordenadas e
independencia de Django, tipos XML inválidos, fechas ISO, fórmulas compartidas,
diagnósticos de índices y rutas alternativas de partes. No son una
certificación exhaustiva del formato OOXML.

No se ejecutaron suites completas, servidores, Docker, DB, carga de archivos
reales ni integración. No hubo nuevas dependencias, migraciones, API, permisos,
commit, push, PR, deploy ni mutaciones del issue/Project. El issue sigue
pendiente: mantener Roadmap; homologación y posterior integración no resueltas.

## Entrega y aceptación pendiente

Cambios limitados al módulo, sus pruebas y este documento. Skills utilizadas:
`brainstorming` para acotar función versus servicio, `systematic-debugging`
para corregir fallos observados y `code-review` para revisar estándares y
cumplimiento por separado. Cinco hallazgos fueron reproducidos y corregidos:
literales numéricos, fechas XML, coordenadas de índices inválidos, falsos
duplicados de fórmulas compartidas y rutas de partes. La revisión posterior
no detectó bloqueantes en esas correcciones; el revisor de estándares ejecutó
además sus tres pruebas de regresión. Se consultó `xlsx` y se descartó
porque el entregable es código Python, no una planilla.

La comprensión/aceptación humana no se infiere de las pruebas. Antes de
incorporación quedan la revisión humana y la discusión de modos de fallo.
No se recomienda merge ni despliegue en este tramo.

## Prueba manual local

El lector no tiene pantalla ni API integrada. La consola de demostración vive
en el módulo de pruebas y usa el Python y las dependencias ya disponibles.
No requiere instalar paquetes, iniciar Django, abrir puertos ni crear DB.
Genera todos los XLSX ficticios en memoria; no lee archivos recibidos.

Desde PowerShell:

```powershell
Set-Location 'C:\Users\Juanito\orca\workspaces\SistemaDeSalud\Padron\backend'
python -B -m apps.financiadores.test_ostel_prevalidacion --demo
```

Elegir un caso, verificar el resultado y usar `0` para salir:

| Caso | Resultado observable esperado |
| --- | --- |
| 1 | Una fila, cero anomalías; `000123`, `00000123` y `000009` intactos. FECVTO y MOTIVO sin interpretar. |
| 2 | Dos filas con datos, una vacía excluida; fila 4 duplicada de fila 2. |
| 3 | Encabezado incorrecto en fila 1, columna 1; se conserva la fila de datos. |
| 4 | Fórmula en fila 2/columna 1 y error Excel en fila 2/columna 2; no se ejecuta fórmula. |
| 5 | Rechazo de archivo inválido; la consola continúa disponible. |
| 6 | Hoja1 con 5.754 filas, sin duplicados ni anomalías técnicas. |
| 7 | afimotook con 7.486 filas, sin duplicados ni anomalías técnicas. |

La muestra de valores sólo se imprime para el caso 1 generado internamente;
el lector productivo no registra valores. No existe opción de abrir archivos
reales en esta consola. Es una prueba del lector, no del flujo web de padrón.

## Integración web: alcance ampliado y contrato con #185

El usuario autorizó ampliar el alcance hasta resolver #180, incluyendo UI/API,
y confirmó crear una base SQLite local aislada, cuentas ficticias y servidores
limitados a `127.0.0.1`. Se reutilizan los permisos de carga existentes: operador,
administrador y plataforma según el control actual; auditor no puede cargar.
No se agregan permisos, migraciones de esquema ni dependencias.

Acceso actual: **Padrón de afiliados → Importar Excel → OSTEL**. Es una revisión
efímera dentro del flujo común. La pantalla conserva el diseño del portal y
muestra conteos por hoja, duplicados y anomalías con coordenadas. Cambiar el
archivo borra el resultado previo; cerrar durante una petición está permitido.
Los nombres de columnas del detalle se identifican como esquema esperado.

Endpoint: `POST /api/financiadores/{id}/prevalidar-ostel/`, autenticación habitual,
`multipart/form-data`, campo `archivo`. Comprueba ámbito antes de leer la carga,
extensión XLSX y máximo de 5 MiB; el lector mantiene sus límites internos.

Respuesta 200:

```json
{
  "resumen": {
    "filas_no_vacias": {"Hoja1": 2},
    "duplicados_exactos": 1,
    "anomalias": 1
  },
  "columnas": ["TIPO", "NROAFI"],
  "anomalias_por_codigo": {"fila_duplicada": 1},
  "anomalias": [
    {"codigo": "fila_duplicada", "hoja": "Hoja1", "fila": 3,
     "columna": null, "fila_original": 2}
  ],
  "detalle_truncado": false,
  "limite_detalle": 500
}
```

`columnas` está abreviado sólo en este ejemplo; se devuelven las 39. La respuesta
no incluye valores de celdas, nombres recibidos ni filas nominales.
`Cache-Control: private, no-store`. El detalle se acota a 500 anomalías y el
resumen incluye todas; la UI informa explícitamente cuando existe truncado.
Errores de archivo: 400, campo `archivo`. Falta de sesión: 401. Auditor: 403.
Financiador ajeno o membresía inactiva: 404, conservando el contrato actual.

La única escritura funcional es el evento de auditoría `prevalidar_ostel`
con usuario y financiador, sin archivo, nombre ni celdas. No crea `Afiliado` ni
`Importacion`. Si la auditoría falla, no se entrega el resultado. Django puede
usar un archivo temporal durante la recepción multipart; no se conserva como
documento, lote o adjunto.

Contrato consumido de #185, sin modificar sus archivos: `generar_escenarios()`,
`generar_xlsx(lote, hoja=...)`, `COLUMNAS`, `Lote` y `exportar_temporales()`.
Catálogo verificado en la revisión `6cf71dd`: 20 escenarios, 23 lotes, 46
archivos al combinar ambas hojas. `fila_repetida` genera una anomalía técnica;
CUIL discordante, referencias, bajas y demás estímulos funcionales no se
homologan ni se rechazan por reglas inventadas. Los lotes siguen independientes.

### Evidencia de integración

Pruebas focalizadas, SQLite temporal de tests:

```powershell
cd C:\Users\Juanito\orca\workspaces\SistemaDeSalud\Padron\backend
python -B manage.py test apps.financiadores.test_ostel_api apps.financiadores.test_ostel_prevalidacion --settings=config.settings_financiadores_test --verbosity 1
```

El módulo API cubre todo el catálogo #185, preservación de sus textos,
permisos/ámbito, rechazo de archivos, detalle truncado y fallo de auditoría.
Verifica que no se creen afiliados ni lotes. Resultado del comando: **27 pruebas
aprobadas** (20 del lector y 7 de integración API). `git diff --check` sin errores
de espacios; advertencia de conversión LF/CRLF del documento en Windows.

Navegador Chromium real → Vite → Django → SQLite aislada:

- Login de operador y carga por UI de los 46 archivos: 200 y conteos esperados.
- Cinco archivos propios adicionales: cabecera incorrecta, fórmula, ZIP inválido
  (400), 5.754 filas y 7.486 filas con 39 columnas.
- Cambio de archivo elimina resultados anteriores; auditor sin acción de carga.
- Sin errores JavaScript observados. Capturas de escritorio y móvil; sin
  desbordamiento horizontal global a 390 px.
- Escape permite cerrar una petición pendiente. Sólo este caso de espera usa
  respuesta interceptada; las 51 cargas anteriores usan backend real.
- Comprobación directa de la base aislada después de las pruebas: cero
  afiliados, cero lotes de importación y 52 eventos de prevalidación (incluye
  la primera prueba de humo y la repetición para capturas).

Skills: `interface-design` para integrar el diálogo al portal;
`code-review` para revisión independiente de seguridad y cumplimiento;
`systematic-debugging` para ajustar expectativas con la evidencia real.
Se corrigió el bloqueo del cierre mientras la petición estaba pendiente.

### Entorno local entregado

- Web: `http://127.0.0.1:5189/financiadores/padron`
- Backend: `http://127.0.0.1:8139`
- Directorio aislado: `C:\Users\Juanito\AppData\Local\Temp\salud-ostel-180-zd1jg1g3`
- Credenciales: `accesos-locales.json` dentro del directorio, cuentas operador
  y auditor. Contraseñas generadas sólo para este entorno, fuera del repositorio.
- XLSX de #185: `C:\Users\Juanito\AppData\Local\Temp\ostel-185-ficticio-ief2br9b`
- Casos técnicos adicionales: `pruebas-adicionales` dentro del directorio aislado.
- Evidencia: `evidencia-navegador.json`, capturas `ostel-*.png` y script
  reproducible `verificar-navegador.cjs`, dentro del directorio aislado.
- Reinicio: ejecutar `iniciar-backend.ps1` e `iniciar-frontend.ps1` en terminales
  separadas. Se detienen con Ctrl+C. No arrancar una segunda instancia en los
  mismos puertos mientras estén activos.
- Dependencias frontend existentes reutilizadas mediante junction local de
  `node_modules`; caché Vite separada dentro del directorio aislado. Sin instalación
  ni cambios de lockfile.

Recorrido de aceptación: ingresar como operador, abrir “Importar Excel”, elegir OSTEL,
seleccionar `Hoja1/filas_vacias/entrada.xlsx` y verificar dos filas; luego
`Hoja1/fila_repetida/entrada.xlsx` y verificar un duplicado. Probar un archivo
adicional inválido y confirmar que se puede corregir/reintentar. Cambiar al
auditor y verificar que la carga no está disponible.

### Límites y cierre

La implementación técnica de #180 queda disponible para aceptación humana.
No se declara validado el circuito completo de #185: homologación, aplicación
de movimientos, concurrencia de escrituras y consistencia funcional entre
fuentes pertenecen a las tareas posteriores.

La verificación es local con datos ficticios y SQLite; no acredita carga con
personas reales, capacidad productiva, límites estrictos de RAM/CPU, CI ni
despliegue. No se corrieron suites completas ni Docker, ni se modificaron bases
existentes. No se realizaron commit, push, PR, deploy ni cambios al issue/Project.
La aceptación y comprensión humanas siguen pendientes; mantener Roadmap hasta
que el usuario indique la incorporación correspondiente.

## Selector extensible y preferencia frontend

Solicitud posterior del usuario: unificar los formatos bajo “Importar Excel”,
preparar el código para N formatos y recordar la selección del usuario.

- `frontend/src/pages/financiadores/formatosImportacion.js` es el registro
  declarativo: identificador estable, nombre, tipos de carga, modo de operación,
  parámetros/nombre de plantilla y recursos API. No se agregan condicionales
  por obra social al selector.
- `ImportacionFinanciador.jsx` conserva un único modal y selector.
  `ImportacionSistema.jsx` reutiliza el flujo completo anterior; los recursos
  de revisión, confirmación, historial y rechazos vienen del descriptor.
  `RevisionTecnicaExcel.jsx` reutiliza el contrato de resumen técnico.
- `backend/apps/financiadores/formatos_importacion.py` registra generadores.
  `GET plantilla/?tipo=padron&formato=ostel` descarga un XLSX vacío con Hoja1,
  39 encabezados y columnas formateadas como texto. Sin `formato`, se conserva
  la plantilla del sistema, sus versiones y sus controles anteriores.
- Persistencia: `localStorage`, clave
  `salud.formato-importacion.v1:{usuarioId}:{tipo}`. Sólo se guarda el ID del
  formato, sin archivo, registros ni resultado. Se comparte entre financiadores
  del mismo usuario, pero no entre usuarios ni entre Padrón y Consumos.
- Si el ID guardado desaparece o no admite ese tipo, se usa el predeterminado.
  Si el almacenamiento está bloqueado, la pantalla funciona e informa que no
  podrá recordar la preferencia.
- Cambiar de formato desmonta el flujo anterior y descarta sus estados locales.
  El selector se bloquea durante una operación/descarga pendiente. Las descargas
  no bloquean el cierre; la aplicación de importaciones conserva su bloqueo
  previo. La revisión técnica permite cerrar aun durante una petición.
- OSTEL sólo admite padrón y revisión técnica. No tiene confirmación de carga.

Para incorporar otro formato: implementar y registrar su generador de plantilla
y su adaptador backend; agregar su descriptor frontend, indicando un flujo
compatible (`revision` o `importacion`) y sus recursos. Un adaptador de revisión
debe devolver el contrato técnico documentado arriba; uno con aplicación debe
cumplir el contrato existente de lotes/confirmación y tener homologación aprobada.
El registro no convierte automáticamente columnas ni define reglas de negocio.

Validación de este cambio:

1. `node --test src/pages/financiadores/formatosImportacion.test.js`: seis pruebas
   aprobadas, incluyendo aislamiento por usuario/tipo, storage bloqueado,
   valores inválidos y registro con 30 entradas.
2. Ocho pruebas de `apps.financiadores.test_ostel_api` aprobadas; incluye descarga
   de plantilla actual de padrón/consumos, plantilla OSTEL vacía y permisos.
3. Tres regresiones Playwright existentes aprobadas: preview/aplicación,
   recuperación de duplicados y descarga de plantilla vigente. API interceptada
   en estas tres regresiones, conforme a su configuración existente.
4. Navegador con backend real: descarga de ambas plantillas, revisión OSTEL,
   limpieza al cambiar formato, preferencia al cerrar/abrir y recargar,
   separación Padrón/Consumos, storage bloqueado y ausencia de errores JS.
   Se interceptó sólo la descarga pendiente para verificar cierre con Escape.

Evidencia nueva en el directorio local: `verificar-formatos.cjs`,
`evidencia-formatos.json` y `selector-formatos-ostel.png`. El script anterior
`verificar-navegador.cjs` documenta el acceso separado previo y ya no corresponde
al recorrido actual. No se modificaron archivos del agente de #185.

Skills aplicadas: `brainstorming` para acotar el registro al diseño aprobado y
`code-review` para detectar la regresión de cierre durante descargas. Corregida
y verificada en navegador. Sin nuevas dependencias, migraciones, commits ni
mutaciones externas. La aplicación local sigue en los mismos puertos.


## Corrección de calidad de interfaz y revisión integral

A pedido del usuario se revisaron los cambios backend y frontend contra el flujo
existente. El nombre del financiador ficticio estaba concatenado con instrucciones
de la importación predeterminada; ahora se identifica como “Financiador” en el
contenedor común. La explicación extensa se movió al componente existente `Ayuda`
junto a “Prepará el archivo”. Ambos formatos comparten terminología y jerarquía;
OSTEL mantiene visible que sólo permite revisión técnica. No se renombró la
organización ni se cambiaron reglas de importación.

La revisión `code-review` separó contratos backend y consistencia frontend. No
identificó defectos backend adicionales confirmados. Detectó falta de cobertura
permanente del selector: se agregaron dos casos al Playwright existente para
ayuda/Escape, distinción del contexto, plantilla seleccionada, descarte de archivo
y preferencia al reabrir/recargar.

Comprobaciones de esta revisión: 28 tests backend focalizados (lector + API),
6 tests de preferencias, 5 regresiones Playwright con API interceptada, todas
aprobadas. Se repitió el script local con API real para descarga/revisión,
persistencia, cambio de formato y storage bloqueado; sin errores JS. Capturas
`selector-sistema.png` y `selector-ayuda.png` inspeccionadas visualmente.
No se ejecutó suite completa, CI ni validación PostgreSQL. Sin cambios de datos,
permisos, dependencias o contratos. Homologación y aceptación humanas pendientes.


## Ajustes de interfaz mientras se esperan definiciones de OSTEL

Se elimina el financiador del modal por redundante. El aviso explica en lenguaje
simple que es posible revisar archivos, pero aún no importar afiliados porque
falta confirmar la interpretación de campos y códigos con OSTEL.

El historial y su consulta ahora pertenecen a `ImportacionFinanciador`, fuera de
los flujos de formato. Es común al contexto/tipo de carga, sin filtro por formato.
`ImportacionSistema` recibe el lote seleccionado y conserva revisión/confirmación.
Los lotes actuales pertenecen al importador del sistema: abrirlos desde OSTEL
muestra ese flujo, sin sobrescribir la preferencia guardada para archivos nuevos.
Un futuro formato que cree lotes deberá acordar cómo identificar su formato en
el contrato backend; no se agrega ahora un campo ni una inferencia semántica.

La paginación se muestra sólo si hay otra página o se necesita volver a una
anterior, nunca en un historial vacío inicial, carga pendiente o error.
Regresiones focalizadas: ocho pruebas Playwright (API interceptada), seis de
preferencias, aprobadas. Recorrido con backend local real aprobado y captura
inspeccionada. Sin modificaciones backend ni nueva ejecución de su suite.
Skill brainstorming aplicada para acotar la corrección al diseño ya acordado.
Sin commits, publicación, cambios de permisos ni datos reales.


## Cierre de sesión y continuación conjunta #180 / #185

El usuario autorizó commitear el trabajo local y abrir una sesión Codex nueva en
este mismo worktree. Esa sesión debe esperar la respuesta de OSTEL antes de
continuar la implementación. No se autorizó push, merge, deploy ni cerrar issues.

Se contrastó el cierre de la sesión #185: generador terminado, circuito integral
pendiente; su evidencia antigua de UI no acredita la interfaz corregida. El
20/10 se ejecutó nuevamente `python -B -m unittest
apps.financiadores.tests_ostel_scenarios -q`: 19 pruebas aprobadas contra el lector
actual. Esto verifica el contrato técnico de los 46 archivos, no importación de
movimientos ni aceptación humana. La referencia a “Revisar Excel OSTEL” en el
documento de #185 es histórica: el recorrido vigente es Importar Excel → formato
OSTEL → Revisar archivo. No se modificaron archivos del agente #185.

Continuación: incorporar la respuesta textual/referencia de OSTEL en la matriz
existente de `docs/funcionalidades/financiadores-cobertura/ostel-aceptacion.md`,
distinguir definiciones confirmadas y pendientes, y acordar resultados esperados
antes de implementar mapeo/aplicación. No inferir que responder una parte resuelve
todas las decisiones de identidad, familia, fechas, estados, corte y precedencia.
El objetivo de producto sigue siendo un único flujo de importar/revisar/confirmar
con formatos extensibles, preferencia frontend e historial común; nunca botones
o funciones por financiador.
