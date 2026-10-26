# Formato de sellos y suspensión de recetas · AUD-043 / AUD-045

Diseño aceptado por coordinación dentro del plan aprobado de #172. Implementación con primera validación PostgreSQL aprobada; refinamiento de presentación de versiones en curso. No se modifica la política de autoría ni se agrega migración, proveedor, dependencia o flag productivo.

## Contrato de formato

Las firmas nuevas escriben `salud-sha256-v2` en `sello_version`. El canónico es un array JSON posicional de los mismos nueve strings del formato previo: versión, historia, ciudadano, título, contenido, autor, matrícula, fecha UTC ISO, sello previo. Se serializa con `ensure_ascii=True` y `separators=(",", ":")`, codificado UTF-8 para SHA-256. Los controles quedan escapados; no se eliminan ni se normaliza Unicode. El formato conserva la equivalencia previa None/cadena vacía para campos opcionales: las entradas del modelo no distinguen ambos como contenido clínico.

`salud-sha256-v1` y `cauce-sha256-v1` conservan exactamente el algoritmo de unión por U+001F. Si coincide el hash, `ok=True` significa coincidencia con ese algoritmo legado: **no detecta traslados del separador entre campos**. `motivo` advierte esa limitación; no se declara autenticidad legal. Una versión desconocida devuelve `ok=False` y motivo de versión no soportada, sin error HTTP 500 ni ensayo de algoritmos alternativos. No se resellan ni corrigen silenciosamente filas históricas.

## Suspensión

Se conserva POST `/api/recetas/{id}/suspender/`, motivo obligatorio, primera respuesta 200 y repetición 400 con el mensaje existente. Dentro de una transacción se bloquea Historia→Receta, se relee estado y se valida permiso antes de persistir. Una receta/historia desaparecida tras la lectura inicial responde 404. Una sola suspensión crea una entrada firmada y sella en la misma transacción; fallar el sellado revierte tanto estado como asiento. La segunda solicitud, aun con otro motivo, no reescribe ni agrega un asiento. Quien necesite documentar un hecho posterior debe registrar una nueva entrada clínica por el flujo existente.

## Validación y entrega

El coordinador reprodujo el rojo: ocho métodos, siete fallos incluyendo subcasos; ambas suspensiones simultáneas respondían 200 y el canónico ambiguo coincidía. El módulo focal agrega controles/Unicode/fechas equivalentes, bytes legados, versión desconocida, mismos/distintos motivos, rollback y conservación de motivo/sello; se suma desaparición entre lectura y bloqueo. La convivencia se prueba con versiones reales v1→v2, no etiquetas inventadas.

Primera tanda verde de integración: `manage.py test apps.registros.test_formato_suspension_auditoria172 apps.registros.test_revision_borrador_auditoria172 apps.registros.test_concurrencia_firma_auditoria172 apps.registros.tests_api apps.registros.tests_integridad apps.agenda apps.portal.test_ventana_turnos_auditoria172 apps.portal.tests_red --noinput --verbosity 1`: **300 aprobadas, sin skips**, PostgreSQL exclusivo, 100,411 s. Incluye las nueve pruebas focales del formato/suspensión, revisiones/autoría previas, agenda completa y recorridos portal de datos/turnos. Los logs500 de la prueba de rollback son un fallo de sellado inyectado deliberadamente y esperado; no hubo errores del runner. Revisión independiente estática sin P1/P2 nuevos.

**Compatibilidad de release:** todos los lectores/verificadores deben soportar v2 antes de admitir nuevas escrituras v2. Esta entrega requiere actualización coordinada de procesos; no promete rolling deploy sin interrupción. Si se exige rollout gradual, separar previamente lector compatible de escritor es una decisión operacional pendiente. No se agrega flag sin esa decisión.

**Rollback:** luego de existir sellos v2 no volver a un lector v1 exclusivo: marcaría evidencia válida como alterada. Conservar lector v2 al revertir otra lógica; no convertir ni resellar v2 a v1. Detener escrituras durante una actualización/reversión coordinada si no se garantiza compatibilidad de todos los procesos. Backups y verificadores externos también necesitan lector v2.

Los sellos siguen siendo controles de integridad, no firma digital certificada. La conciliación de históricos ambiguos y posibles duplicados previos no se realiza ni se elimina evidencia automáticamente.

## Presentación y verificación final del corte

Se expone `sello_version` como campo de solo lectura y se prueba que POST/PATCH no permiten elegirlo. La pantalla diferencia v1 coincidente (histórico, ámbar), v2 coincidente (verde), algoritmo ausente/desconocido (gris) y hash distinto en formato conocido (rojo). El panel global usa «Hay problemas de verificación» o «No se detectaron diferencias» y explicita el límite histórico. Una versión desconocida no constituye por sí sola prueba de alteración.

El módulo focal ampliado (diez métodos, incluido el nuevo contrato API) pasó en las tandas550 y199, cuyos fallos únicos ajenos al formato quedaron identificados y corregidos mediante la posterior tanda48 de identidad/permisos. No se atribuye a esos cortes una aprobación total que no tuvieron. Build y CSS finales aprobados. Navegador real del corte final:19 controles, cuatro estados, panel mixto, escritorio/móvil, sin mocks de API ni errores JS; evidencias en `output/playwright/aud172-sellos-evidencia.json`. La fixture visual crea casos sintéticos nuevos; no resella ni altera historia previa. Sigue pendiente la aceptación humana de este bloque y la preparación de release compatible, sin despliegue autorizado.
