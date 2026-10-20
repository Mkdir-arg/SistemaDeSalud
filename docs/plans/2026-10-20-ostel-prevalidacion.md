# OSTEL: tramo local de prevalidación técnica (#180)

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
