# Padrón: ficha administrativa y exportación XLSX

Alcance confirmado por coordinación el 13/10/2026: una plantilla visible vigente,
Editar con ficha administrativa completa y exportación XLSX de todas las filas
filtradas y ordenadas con las columnas elegidas. Este trabajo complementa el
contrato 130.1 y se integra con la sesión de tabla; no cambia modelos ni permisos.

## Diseño aplicado

- La plantilla visible pide `version=2` y se descarga como `plantilla-padron.xlsx`.
  La API y la importación v1 continúan disponibles internamente.
- Editar consulta el detalle actual, incluidos sus permisos; la fila del listado
  no se usa como ficha. Reutiliza los bloques existentes en un único diálogo.
  Cada bloque se guarda explícitamente con motivo y revisión capturada al abrir
  su formulario. Un 409 conserva el borrador y bloquea reenvíos hasta recarga.
- Familia, legajo, salud y cobranza conservan sus recursos y validaciones.
  No se promete una transacción conjunta. Las fechas administrativas no alteran
  derechos; Finalizar/Reactivar siguen como acciones explícitas del padrón.
- Listado y exportación consumen `consultar_padron` del trabajo de tabla.
  El listado pagina el queryset ya ordenado sin pasar por `lista()`, que fuerza
  orden por pk para otros recursos. El catálogo administrativo compartido define
  las columnas permitidas y sus etiquetas. La descarga nunca incluye salud,
  cobranza, bancos, parentesco protegido ni acciones.
- La descarga lee como máximo 5001 filas para comprobar el límite de 5000.
  Un exceso devuelve error para acotar filtros; no trunca resultados. El archivo
  se genera con openpyxl ya existente, en modo write-only. Cadenas e
  identificadores se escriben con tipo texto, nunca fórmulas o enlaces externos.
  Fechas son celdas fecha, null queda vacío y controles XML inválidos se eliminan.
  Un texto demasiado largo se rechaza antes del truncamiento de Excel.
- El evento `exportar_padron` registra usuario, organización, fecha, formato,
  cantidad y claves validadas. Si todas las claves no caben en el motivo de 255
  caracteres, se guarda cantidad de columnas y SHA-256 de la lista ordenada.
  No incluye búsqueda libre ni datos de personas. Si falla auditoría no se
  entrega archivo. La respuesta incluye `no-store`; el middleware puede agregar
  `private`. El evento no demuestra entrega efectiva ni auditoría inmutable.
- La UI usa consulta aplicada y columnas visibles; no exporta la página ni
  parámetros de navegación. Una respuesta de descarga llegada tras desmontar
  la vista o cambiar consulta no dispara descarga en el navegador.

## Justificación recomendada por el agente

Reutilizar ficha, formularios y recursos reduce duplicación de validaciones y
permisos. Guardar por bloque mantiene la semántica existente y evita crear una
transacción entre recursos distintos. XLSX conserva tipos de identificadores de
forma explícita; CSV no se añade a este alcance. El límite y la generación previa
a la auditoría permiten fallo cerrado sin colas, almacenamiento ni streaming.
Estas razones describen la recomendación técnica del agente, no un razonamiento
humano retrospectivo.

## Evidencia y límites

Pruebas focales cubren plantilla v1/v2, edición parcial/revisión/409, permisos,
aislamiento organizacional, historial existente, equivalencia listado/exportación,
columnas y orden, más filas que página, límites 5000/5001, fórmulas/XML/Unicode,
identificadores largos, null/fechas y fallo de auditoría. Reabrir XLSX verifica
tipos y contenido. Esquema OpenAPI se valida con `spectacular --fail-on-warn`.

La evidencia ejecutada y comandos exactos se entregan en el reporte externo de
implementación. SQLite y UI interceptada no prueban concurrencia PostgreSQL ni
persistencia runtime. El coordinador integra los commits y valida el recorrido
real de ambos trabajos antes de actualizar la demo. No se modificó su base
persistente, no hubo seed ni despliegue. Aceptación final humana pendiente.
