# OSTEL: catálogo sintético y aceptación pendiente

Fecha: 2026-10-20. Alcance parcial de [#185](https://github.com/Mkdir-arg/SistemaDeSalud/issues/185),
basado en el issue, [#142](https://github.com/Mkdir-arg/SistemaDeSalud/issues/142),
[#180](https://github.com/Mkdir-arg/SistemaDeSalud/issues/180) y el
[contrato de importación existente](README.md#importaciones).
Base inspeccionada: `a91faf46290e3f71eb59fc81ba78f04b809d8d39`.

**Estado: evidencia del generador disponible; circuito integral y aceptación
humana pendientes.** Publicación técnica en [PR draft #186](https://github.com/Mkdir-arg/SistemaDeSalud/pull/186);
Roadmap sin cambios. Este documento no
homologa códigos, define derechos ni autoriza incorporar datos al padrón.

## Alcance y plan ejecutable

1. Construir filas ficticias de 39 columnas, sin consultar fuentes nominales.
2. Mantener escenarios independientes y lotes ordenados para pruebas entre archivos.
3. Probar estructura, anomalías deliberadas, determinismo y serialización XLSX.
4. Separar esta evidencia de la validación futura del lector, mapeo y aplicación.

Se reutiliza `openpyxl` ya declarado en `backend/requirements.txt`. No se
reutiliza el seed de demo ni el importador porque arrastran Django y contratos
distintos. El generador no importa `ostel_prevalidacion.py`; sus pruebas de
contrato ahora consumen el lector real tras la entrega documentada de #180.
Este tramo #185 no añade dependencias, persistencia, permisos ni frontend.

## Uso reproducible

Desde `backend`, ejecutar únicamente las pruebas propias:

```powershell
python -B -m unittest apps.financiadores.tests_ostel_scenarios -v
```

API local de fixtures en `apps.financiadores.ostel_synthetic`:

- `COLUMNAS`: encabezado ordenado, idéntico al esquema solicitado.
- `generar_escenarios()`: tupla de `Escenario(codigo, lotes)`.
- Cada `Lote(nombre, filas)` contiene tuplas de 39 celdas en ese orden.
- `generar_xlsx(lote, hoja="Hoja1")`: bytes XLSX; admite también `afimotook`.
  No escribe en disco. Se puede usar `BytesIO` o un directorio temporal.
- `exportar_temporales()`: escribe 46 XLSX y `manifiesto.json` en una carpeta temporal nueva y
  devuelve su ruta. No sobrescribe archivos; no modifica el repositorio.

El manifiesto enumera los 20 escenarios y sus 23 lotes en ambas hojas:
ruta relativa, orden de lote dentro de cada escenario, hoja, SHA-256 de los
bytes exportados, cantidad de filas físicas sin encabezado y coordenadas Excel
de filas con datos. Es un inventario de **entradas esperadas**, no un informe
de ejecución del lector ni de aceptación. `aceptacion_ostel` permanece pendiente.
El orden sirve para reproducir una secuencia; no establece precedencia de
fuentes ni demuestra cuál archivo es cronológicamente posterior.
El hash identifica ese archivo concreto; puede variar entre exportaciones por
los metadatos XLSX aunque sus valores sean iguales. No usarlo como identidad
de persona, clave de movimiento ni mecanismo de deduplicación de negocio.

### Prueba manual local

Desde `backend`, generar el paquete completo:

```powershell
$carpetaOstel = python -B -m apps.financiadores.ostel_synthetic
Get-ChildItem -LiteralPath $carpetaOstel
```

Abrir los archivos de esa carpeta con Excel. Para ofrecerlos también en el
navegador local, ejecutar en una terminal:

```powershell
python -B -m http.server 8765 --bind 127.0.0.1 --directory "$carpetaOstel"
```

Abrir `http://127.0.0.1:8765`. Es un listado local de descargas, no la
aplicación del padrón ni una pantalla de importación. Detener con Ctrl+C.
La carpeta temporal queda disponible hasta que se elimine explícitamente.
No publicar ese servidor ni apuntarlo a una carpeta con datos reales.

Recorrido sugerido:

1. Elegir `Hoja1` y abrir `base/entrada.xlsx`: ver 39 columnas y una persona
   marcada como ficticia.
2. Abrir `numero_compartido/entrada.xlsx`: comparar ambas identidades.
3. Abrir `filas_vacias/entrada.xlsx`: datos en filas 3 y 5, vacías 2, 4 y 6.
   La última vacía conserva su posición mediante formato, sin dato inventado.
4. Comparar los dos archivos de `baja_repetida`, luego los de
   `posible_reingreso`, respetando sus prefijos `01` y `02`.
5. Abrir `lote_parcial/entrada.xlsx` y contrastarlo con la matriz de abajo.
6. Repetir un caso desde `afimotook`: sólo cambia el nombre de hoja.

Este recorrido comprueba los estímulos generados. No subirlos al importador
actual como si el mapeo OSTEL estuviera aprobado. El checksum se verifica con
las pruebas, no por inspección visual de Excel.

Ejemplo sin generar archivos persistentes, desde Python con `backend` en la ruta:

```python
from io import BytesIO
from openpyxl import load_workbook
from apps.financiadores.ostel_synthetic import generar_escenarios, generar_xlsx

casos = {caso.codigo: caso for caso in generar_escenarios()}
lote = casos["numero_compartido"].lotes[0]
libro = load_workbook(BytesIO(generar_xlsx(lote, hoja="afimotook")))
try:
    assert libro.active.max_column == 39
finally:
    libro.close()
```

Determinismo significa mismos valores, tipos y orden en cada llamada, sin
semilla aleatoria, reloj ni estado externo. No se promete igualdad binaria
de los ZIP XLSX (metadatos del contenedor). Las fechas nativas se recuperan
como `datetime` a medianoche al leer XLSX; los textos no se convierten a fechas.
No concatenar todos los escenarios en una sola carga: reutilizan identidades
deliberadamente y sólo los lotes de un mismo escenario forman una secuencia.

## Procedencia y límites de los estímulos

Todas las identidades se construyen desde cero: nombres `PERSONA FICTICIA
OSTEL`, documentos calculados desde `99018500`, afiliaciones `FIC185-...`,
domicilios explícitamente ficticios y correos `example.invalid`. Teléfonos
vacíos. No se leyeron Downloads, planillas nominales ni PDFs originales;
las referencias a ellos proceden de los issues. No se copiaron ni anonimizaron
personas. Un número generado puede coincidir por azar con uno existente:
no se afirma que el rango esté reservado ni se consulta un registro real.

`SINTETICO`, `PLAN-FICTICIO`, `EMP-FICTICIA`, `BAJA-FICTICIA`, `00`, `01`,
`AAA` y `ZZZ` son estímulos, no equivalencias de catálogos aprobadas.
En los casos familiares, `NROREF` coincide deliberadamente con el `NROAFI`
de otra fila; esto permite comprobar presencia textual. OSTEL debe confirmar
la clave real, su alcance y el significado de los sufijos antes del mapeo.
La fila base es un control estructural, **no una afiliación aprobada para importar**.
Un checksum correcto tampoco acredita CUIL asignado, identidad ni afiliación.

## Catálogo y expectativas separadas

Fila Excel 1 es el encabezado. Las expectativas de esta tabla describen
los datos generados; no son resultados ya obtenidos de #180 ni del importador.

| Escenario | Datos y expectativa técnica comprobable hoy | Decisión pendiente de OSTEL |
|---|---|---|
| `base` | Una fila, 39 columnas, CUIL de 11 dígitos con checksum correcto y documento coincidente | Obligatoriedad y homologación de todos los códigos |
| `numero_compartido` | Filas 2–3: mismo NROAFI; APENOM, documento y CUIL distintos | Clave de identidad, alcance del número y tratamiento de coincidencias |
| `referencia_presente` | Fila 3 referencia textualmente NROAFI de fila 2, terminado en AAA | Significado de NROREF y vínculo familiar |
| `referencia_ausente` | Fila 2 tiene referencia no presente en el archivo | Búsqueda en padrón previo, revisión o rechazo; no inferir inexistencia global |
| `referencia_no_aaa` | Referencia presente a un número terminado en ZZZ | Si es admisible y qué significa; no convertirlo automáticamente en titular |
| `cuil_invalido` | Documento coincide con el cuerpo del CUIL; sólo el dígito verificador está alterado | Severidad, corrección y procedimiento operativo |
| `documento_discordante` | Checksum correcto, pero cuerpo documental distinto de NRODOC | Fuente de identidad autoritativa y resolución de discrepancias |
| `filas_vacias` | Cinco filas físicas: Excel 2, 4 y 6 vacías; Excel 3 y 5 con datos; exclusión comprobada con lector real | No requiere definir negocio para contar vacías |
| `tipos_mixtos` | NROAFI texto `000185`, entero 185 y decimal 185.5; documentos texto, entero y booleano; fechas nativa, texto ISO e inválida | Conversiones permitidas y severidades; no normalizar en la fixture |
| `baja_repetida` | `01_baja` y `02_repeticion` tienen exactamente la misma fila | Idempotencia, clave de movimiento y efecto sobre historial/derechos |
| `posible_reingreso` | Primer archivo con baja 2026-06-30; segundo con misma identidad, ingreso 2026-08-01 y baja vacía | Si es reingreso, corrección o nuevo período; ninguna reactivación inferida |
| `vencimiento_lejano` | FECVTO = 2099-12-31 | Centinela, vigencia real u otro significado; no fijar umbral |
| `baja_anterior_ingreso` | FECBAJ = 2025-12-31, menor que FECING = 2026-01-01 | Rechazo, advertencia o interpretación histórica |
| `lote_parcial` | Tres personas: control estructural, CUIL inválido coincidente con documento y fechas conflictivas | Aplicación parcial frente a atomicidad, revisión, reintentos y resumen |
| `referencia_ambigua` | Dos personas distintas comparten NROAFI; una tercera usa ese valor en NROREF | Clave familiar inequívoca; no elegir la primera coincidencia |
| `fila_repetida` | Dos filas idénticas en un mismo archivo | No confundir duplicado técnico con persona repetida o movimiento ya aplicado |
| `codigos_sin_homologar` | NUMERO `000042` y códigos explícitamente ficticios en TIPO, TIPODOC, CODPAR, MOTIVO e INCAPA | Diccionario, equivalencias, obligatoriedad y severidad |
| `contactos_ausentes` | Misma identidad control, domicilio y contactos vacíos | No inventar valores ni exigir completitud sin una regla aprobada |
| `texto_literal` | NROAFI con espacios, ceros y Ñ; NUMERO con ceros y NROREF con Unicode | Normalización permitida y validez del identificador |
| `fuentes_discordantes` | Dos archivos con misma identidad y FECING; difieren en plan y presencia de baja | Fecha de corte, foto/movimientos, corrección y fuente prevalente; no asumir que el segundo gana |

El lote parcial mezcla calidades de entrada; no acredita que alguna fila sea
aplicable. FECBAJ y FECVTO no provocan bajas ni restricciones en estas fixtures.

## Evidencia de esta entrega

Comando focalizado indicado arriba: **19 pruebas aprobadas** el 2026-10-20
(17 del generador y 2 de contrato con el lector real).
Sin Django, DB, Docker ni suite completa. Las pruebas de serialización usan
memoria y la exportación usa una carpeta temporal eliminada al terminar.
No se versionan binarios. El servidor de descargas para prueba manual es
independiente de esas pruebas y no aplica datos.

Revisión: se reprodujo la pérdida de filas vacías finales en XLSX; se corrigió
con formato en una celda vacía, sin cambiar valores. Se agregó cobertura de
vacías finales, lotes completamente vacíos y exportación sin sobrescritura.
La revisión estática de calidad y especificación no encontró otros bloqueantes.

| Criterio del tramo autorizado | Evidencia |
|---|---|
| 39 columnas en orden y catálogo completo | `test_esquema_exacto_y_cobertura` |
| Repetibilidad y aislamiento de cambios accidentales | `test_determinismo_e_inmutabilidad` |
| Identidades marcadas y contactos no operativos | `test_identidades_marcadas_y_sin_contactos_operativos`; procedencia revisable en `_persona` |
| Número compartido y referencias excepcionales | `test_numero_compartido_con_personas_distintas`, `test_referencias` |
| Checksum inválido frente a discrepancia documental | `test_checksum_y_discrepancia_son_estimulos_distintos` |
| Vacías y tipos preservados | `test_vacias_y_tipos_sin_normalizacion` |
| Baja repetida y posible reingreso | `test_secuencias_entre_archivos` |
| Fechas conflictivas y mezcla parcial | `test_fechas_y_lote_parcial` |
| Dos hojas y todos los lotes XLSX | `test_xlsx_ambas_hojas_todos_los_casos`: 23 lotes × 2 hojas |
| Errores de uso y texto literal | `test_exportador_rechaza_hoja_y_ancho_incorrectos`, `test_texto_literal_no_formula` |
| Vacías finales, lote de sólo vacías y lote sin filas | `test_xlsx_ambas_hojas_todos_los_casos`, `test_xlsx_solo_filas_vacias_y_lote_sin_filas` |
| Paquete manual de 46 XLSX y manifiesto sin sobrescritura, hashes y coordenadas comprobados contra los archivos leídos | `test_exportacion_temporal_completa_sin_sobrescritura` |
| Referencia ambigua frente a duplicación exacta | `test_referencia_ambigua_no_equivale_a_fila_duplicada` |
| Códigos opacos, contactos vacíos, ceros, espacios y Unicode | `test_codigos_contactos_y_texto_sin_inferencias` y round-trip XLSX |
| Fuentes discordantes sin precedencia ni reingreso inferidos | `test_fuentes_discordantes_no_sugieren_orden_temporal` |
| Manifiesto, coordenadas y celdas frente al lector real en ambas hojas | `ContratoLectorOSTELTests.test_manifiesto_y_celdas_de_los_46_archivos_con_lector_real` |
| Relectura independiente de bajas/reingreso/fuentes discordantes | `ContratoLectorOSTELTests.test_lecturas_independientes_sin_consolidar_movimientos` |

Las pruebas del generador verifican la construcción; las dos de contrato
comprueban los conteos y celdas del lector, no aplicación de movimientos
ni aceptación funcional. La prueba de marcas ficticias no demuestra
por sí sola procedencia: ésta se sustenta en la construcción local sin entradas.

## Qué bloquea el mensaje enviado a OSTEL

Fuente: mensaje aportado por el usuario en esta sesión. No hay respuesta de
OSTEL incorporada. Se reutiliza este documento como registro de pendientes,
sin crear un tracker paralelo. La implementación de #180 quedó entregada por
su agente el 20/10/2026 y no se modifica aquí. Se consume su contrato publicado
en [la entrega de #180](../../plans/2026-10-20-ostel-prevalidacion.md#integración-web-alcance-ampliado-y-contrato-con-185).

| Punto enviado | Preparado sin respuesta | Qué no debe implementarse por inferencia |
|---|---|---|
| 1. Diccionario de columnas/códigos | Esquema literal, valores opacos, ceros y tipos preservados | Mapear NUMERO/NROAFI/NROREF, regímenes, planes, parentesco, incapacidad o motivos |
| 2. Identificación y grupo familiar | Número compartido, documentos discordantes, referencias presente/ausente/no AAA/ambigua | Clave de persona, fusión de identidades, titularidad o vinculación familiar |
| 3. Significado de fechas | Fechas nativas/textuales, baja anterior y vencimiento lejano | Inicio/fin de cobertura, centinelas y rechazo de fechas por regla de negocio |
| 4. Alcance/corte de archivos | Baja repetida, posible reingreso y fuentes discordantes reproducibles | Asumir fotografía/movimientos, fecha de corte, prevalencia, reactivación o borrado de ausentes |
| 5. Estados y primera entrega | Separación explícita entre entrada técnica y aplicación | Traducir estados a derechos, restringir cobertura o otorgar facultades para autorizar cambios |

Los datos agregados del mensaje (por ejemplo, diez coincidencias entre fuentes)
no se reconstruyen ni se derivan a identidades sintéticas. Cada caso es inventado
desde cero y sólo reproduce la clase de problema.

Los temas no bloqueantes para esta preparación —pantallas/filtros/reportes,
legajo/adjuntos, credenciales, completitud de contactos, frecuencia/responsable
e integraciones— siguen abiertos para etapas posteriores. No son autorización
para añadir UI, almacenamiento, emisores o conexiones externas ahora.

## Continuación tras finalizar el agente de #180

Se monitorizó su terminal mediante Orca hasta observar su informe final,
sin interrumpirlo ni editar sus archivos. Skills `orchestration` y `orca-cli`
permitieron comprobar la entrega antes de continuar.

**Ejecutado en esta sesión de #185:** generación, conservación XLSX, manifiesto
y pruebas directas contra `prevalidar_ostel`, sin copia del lector ni mocks
de sus resultados. Lector versionado en `c6e90ad`, escenarios ampliados en
`6cf71dd`. El mock usado en exportación sólo redirige la carpeta temporal.

El ensayo técnico queda concretado así:

1. Fijar revisión del generador y del lector; generar un paquete nuevo y conservar
   su manifiesto. Una carpeta descargada antes puede contener sólo 14 escenarios.
2. Pasar cada XLSX por el lector sin normalizar previamente sus valores
   (ejecutado para los 46 archivos).
3. Comparar hoja, orden/encabezados y coordenadas de filas no vacías con el
   manifiesto. Comparar valores y tipos con el formato de salida real del lector;
   no asumir que devolverá fechas Python o celdas de openpyxl.
   Se verificaron textos, números XML, booleanos y serial/formato de fechas.
4. Distinguir repetición exacta (`fila_repetida`) de número compartido y referencia
   ambigua: ningún conteo técnico debe convertirse en deduplicación de personas.
5. Comprobar que baja repetida y fuentes discordantes se leen como archivos
   independientes. No exigir consolidación ni cambio de estado en la prevalidación.
6. Localizar diferencias por caso/hoja/fila/columna mediante subtests, y
   dejar interpretación y aplicación pendientes. No exigir al lector técnico
   que rechace códigos, checksum, referencias o fechas por reglas no acordadas.

Resultado: no se observaron diferencias; sólo `fila_repetida` produjo una anomalía,
fila 3 duplicada de fila 2, sin eliminarla. Los estímulos de negocio permanecen
sin interpretación. Las secuencias de baja repetida, posible reingreso y fuentes
discordantes se leen independientemente; releer el primer archivo devuelve el
mismo resultado. Esto no demuestra idempotencia de movimientos persistidos.

**Evidencia reportada por el agente #180, no reejecutada aquí:** 27 pruebas
(20 de lector y 7 de API), cargas de los 46 archivos mediante navegador/API,
cinco casos adicionales, permisos de carga y ausencia de altas de afiliados/lotes
en SQLite aislada. Se inspeccionaron sus pruebas y la documentación; los registros
y capturas locales están referenciados en su entrega. La API sí registra eventos
de auditoría: “no aplica padrón” no significa “no escribe nada”.

La UI entregada está en `http://127.0.0.1:5189/financiadores/padron`,
acción **Revisar Excel OSTEL**; su disponibilidad depende de los procesos locales.
Los accesos y el reinicio están documentados por #180. No se copiaron ni leyeron
contraseñas en esta sesión. Esta UI es la revisión técnica, no el importador.

Pruebas hostiles y de límites del lector son responsabilidad de #180; no se
duplican aquí. Persistencia de movimientos, concurrencia de escrituras,
permisos del circuito integral y comparación tabla/exportación siguen pendientes;
su aprobación no se deduce de la prevalidación. No se ejecutaron DB, navegador,
suite completa, CI ni deploy en esta continuación de #185.

Al recibir respuestas, completar en este documento para cada punto: respuesta
textual/referencia, fecha, responsable OSTEL, regla acordada, escenarios afectados,
resultado esperado aprobado y dudas restantes. Después vincular implementación,
evidencia observada, versión probada y aceptación humana. No marcar como
aceptado un resultado esperado que sólo haya propuesto el agente.

## Validación integral todavía no ejecutada

Dependencias: #180/#181, circuitos de lotes y bajas, vista operativa, decisiones
de #142/#143 y aceptación de OSTEL. No se simula que esos contratos existan.

Cuando estén acordados, usar los escenarios como entradas y registrar:

1. **Prevalidación:** contrato técnico de los 46 archivos verificado directamente
   contra #180; API y UI reportadas por su responsable. Pendiente la aceptación
   manual del usuario y OSTEL, sin convertir la lectura en autorización de carga.
2. **Mapeo:** equivalencias y obligatoriedad aprobadas por OSTEL; clasificación
   explícita de cada anomalía sin atribuir derechos por inferencia.
3. **Persistencia/importación:** comparar antes/después, filas aplicadas,
   rechazadas y pendientes, trazas e historial; probar repetición, carga parcial
   y errores intermedios según la atomicidad que se apruebe.
4. **Concurrencia:** dos cargas/correcciones sobre la misma identidad; demostrar
   que no hay duplicación ni pérdida de actualizaciones.
5. **Permisos/aislamiento:** roles autorizados y denegados, financiadores
   distintos y ausencia de exposición en reportes/logs.
6. **Tabla/exportación:** mismos filtros, identidad, fechas, cantidades y estados
   después de aplicar movimientos; verificar las diferencias autorizadas.
7. **OSTEL:** recorrido con responsable humano, resultado observado y decisión
   explícita sobre cada expectativa. Registrar desacuerdos y pendientes.

Salvo la prevalidación descrita, esos puntos no se ejecutaron: requieren contratos y circuitos disponibles,
definiciones humanas y autorización de entornos fuera del alcance actual.
Tampoco hay evidencia de capacidad con volúmenes reales ni de seguridad de
archivos hostiles; corresponden a pruebas específicas del lector y operación.

## Registro de aceptación

| Elemento | Estado |
|---|---|
| Entrega técnica del generador y pruebas | Verificada localmente en el alcance descrito |
| Contrato generador → lector #180 | 46 archivos verificados; 19 pruebas propias aprobadas |
| API/UI de prevalidación | Evidencia del agente #180 inspeccionada; no reejecutada aquí |
| Reglas de identidad, familia, fechas y movimientos | Pendientes de OSTEL |
| Persistencia, concurrencia, permisos, tabla/exportación | No ejecutados en esta entrega |
| Responsable humano, fecha, versión y escenarios aceptados | Sin registrar |
| Comprensión y aceptación humana | No demostradas; no inferidas por pruebas unitarias |
| Circuito integral #185 | No resuelto |

Para la revisión humana, leer `generar_escenarios`, `_persona` y la tabla de
expectativas. Proponer al menos dos fallos plausibles del circuito y contrastarlos
con evidencia antes de recomendar su incorporación. Ejemplos de riesgos aún
abiertos: fusionar personas por NROAFI y reactivar derechos al ver una baja vacía.
El generador contiene estímulos para ambos, pero aún no existe aquí una prueba
de protección del circuito. Mantener como deuda pendiente la homologación de
reglas, los resultados observados y el entendimiento humano; no crear otro tracker.
