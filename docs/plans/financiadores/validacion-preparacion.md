# Validación de la preparación y continuidad

Fecha: 15/09/2026. Repositorio de referencia: `a6bf26c`. Este informe corresponde a documentación, muestras y prototipo; no declara implementado ni validado el módulo productivo.

**Informe histórico:** después de esta preparación el usuario aprobó Q01–Q13 y se implementó el módulo. Ver [estado de implementación y evidencia actual](estado-implementacion.md). El simulador y las planillas de muestra de este informe no reemplazan la implementación ni las plantillas emitidas por la API.

## Resultado concreto

- Se conservaron las 27 decisiones funcionales del usuario y se registró su instrucción de continuar sin esperar respuestas.
- Se prepararon arquitectura comparada, modelo lógico, contratos candidatos, estados, secuencia L0–L7, migración/activación/reversión y matriz de aceptación.
- Las preguntas se agruparon en Q01–Q13, con recomendaciones, riesgos y el lote que depende de cada respuesta.
- Se generaron tres Excel de muestra, con catálogos diferentes y padrón incremental sin bajas.
- Se preparó un prototipo descartable de cupos en memoria y se capturaron 16 pasos de demostración.

## Investigación verificada

Se renovó la lectura de los 39 issues del repositorio; #13–#20 conservaron sus descripciones respecto del relevamiento inicial. La vista del proyecto y los ítems adicionales de Salud se habían contrastado durante ese relevamiento. Se inspeccionaron los puntos de integración de afiliación, permisos, captura de cobros, hechos durables y trabajos financieros.

Hallazgos que condicionan la implementación:

1. `Ciudadano.obra_social` sigue siendo texto y `Caso` no tiene afiliación estructurada.
2. `PendienteCobro` admite una obligación; la nueva distribución necesita un contrato distinto que preserve el legado.
3. El hecho económico se crea junto al hecho clínico y la captura financiera tiene recuperación. No trasladar toda la coordinación de reservas a un callback sin origen durable.
4. Los bloqueos por hecho no bastan para el cupo compartido entre hospitales.
5. Hay concesiones financieras explícitas y una cola durable de reparto reutilizables como patrones; no hace falta presumir una plataforma de permisos o de jobs nueva.

## Ejecuciones realizadas

Desde la raíz del repositorio:

```powershell
python docs/plans/financiadores/crear_plantillas_demo.py
python backend/apps/finanzas/prototipo_cupo_cobertura.py --demo
```

El generador reabre cada Excel y comprueba hoja de carga vacía, identificador textual con ceros y ausencia de celdas con fórmulas. Las verificaciones adicionales inspeccionaron ZIP, nombres definidos, validaciones, referencias y fechas. Resultado: tres libros válidos; dos listas distintas de prestaciones y una de planes; tres validaciones por libro de consumos y dos en el padrón.

Un control adicional del nombre definido comparó inicialmente el sufijo literal `C7`, sin contemplar la referencia absoluta `$C$7`, y falló por esa condición del verificador. Se repitió resolviendo hoja y coordenadas con el lector de Excel: los tres rangos apuntan correctamente a la columna C, filas 6–7. También se comprobó ausencia de macros y enlaces externos en los paquetes ZIP. No fue necesario cambiar las planillas por ese control.

Se analizó la sintaxis de ambos scripts mediante `ast.parse`, el UTF-8 y los espacios finales de los archivos de texto, los enlaces locales y los 16 objetos JSON de la traza. La primera captura por un pipeline de PowerShell convirtió incorrectamente tildes de la salida de Python; se regeneró directamente en UTF-8 y se fijó la codificación de salida de los scripts. La traza final conserva los caracteres originales.

### Qué muestra el prototipo

| Recorrido observado | Resultado |
| --- | --- |
| Último uso: H1 reserva y H2 intenta después | Queda una reserva; H2 no obtiene otra en esa simulación secuencial |
| Reserva marcada antigua | Sigue reservada; el tiempo no libera |
| Intento de liberar sin confirmar no realización | Estado conservado; pide la confirmación |
| Liberación confirmada y nueva reserva | El uso vuelve a estar disponible y puede reservarse de nuevo |
| Realización y repetición | Un consumo; repetir no agrega otro |
| Cambio de límite del plan dentro de A | Conserva el acumulado de A |
| Consulta de B y regreso a A | Cupos independientes; A conserva sus usos |
| Consumo externo tardío con reserva abierta | Expone Q01 y no decide automáticamente la cobertura del compromiso |
| Consumo externo posterior a una realización | Conserva la realización anterior y muestra exceso |

Traza: [simulación de cupos](simulacion-cupos-demo.jsonl). Sin `--demo`, el mismo comando abre una consola que muestra el estado tras cada acción. Se hizo una comprobación de arranque, comandos y salida de esa consola mediante entrada controlada.

**Límites del prototipo:** una persona, una prestación, un año fijo, operaciones secuenciales y memoria local. No modela fechas reales, afiliación fija del caso, roles, importación, dinero ni condiciones contractuales. No demuestra contención de base de datos, seguridad, integración clínica o idempotencia de una API de confirmación. No es código para habilitar en producción. Después de revisar Q01 y el modelo de estados, retirar el prototipo o sustituirlo por implementación y pruebas reales; no importarlo desde servicios productivos.

## Validación no realizada

- Tests Django, migraciones, servicios, contención PostgreSQL y E2E: no se cambió comportamiento integrado y no se utilizaron bases o servicios reales. Los comandos y escenarios futuros están en [contratos y validación](contratos-y-validacion.md).
- Build/lint global del frontend: no se modificaron componentes o rutas.
- Importación en I-Core Salud: ese importador todavía no existe.
- Prueba visual/manual en Excel o LibreOffice: pendiente; la revisión de estructura no acredita usabilidad ni compatibilidad visual completa.
- Aceptación humana: pendiente para el regreso del usuario. La ejecución del prototipo y la generación de archivos no demuestran comprensión ni aprobación del diseño.

## Archivos y estado de la sesión

- [Glosario](../../../CONTEXT.md): términos confirmados, sin modelo técnico.
- [Decisiones D1–D27](../2026-09-15-financiadores-cobertura-y-cobros.md): relevamiento y evolución de la entrevista.
- [Plan](README.md), [preguntas](consultas-pendientes.md) y [contratos](contratos-y-validacion.md): propuestas para implementación.
- [Planillas](plantillas/README.md), generador y traza: artefactos de revisión.
- [Prototipo](../../../backend/apps/finanzas/prototipo_cupo_cobertura.py): ejecutable aislado, sin importación desde la aplicación.

Los archivos permanecen locales y sin commit. No se cambiaron dependencias de producción, permisos, datos, servicios, rutas ni modelos integrados; no se publicaron issues, comentarios o PR.

Skills aplicadas: `grill-with-docs` conserva decisiones/glosario; `brainstorming` compara diseños; `prototype` hace visible el conflicto de estados; `xlsx` prepara planillas verificables. Sus pausas de conversación se adaptaron a la instrucción del usuario de acumular consultas.

## Próximo paso y límite de avance

Revisar primero Q01–Q06, junto con el recorrido de primera entrega y el modelo propuesto. La implementación estructural necesita decidir la identidad del afiliado, quién confirma su padrón, qué promete una reserva y qué alcance clínico se habilita; no hay evidencia para decidirlos en nombre del usuario. Q07–Q13 se resuelven antes de los lotes que dependen de ellas.

La preparación independiente queda realizada. Al retomar, partir de estos archivos y del estado local, sin repetir el relevamiento completo de issues. Por la extensión de la conversación, puede continuarse en una sesión nueva usando este documento y el plan como resumen.
