# Financiadores, cobertura y cobros — plan de implementación

Estado: implementación autorizada sobre `a6bf26c` el 15/09/2026. D1–D27 y las recomendaciones Q01–Q13 están aprobadas por el usuario («en todas las preguntas, sigue tu recomendacion»). L1–L6 forman la primera entrega; L7 es posterior.

El núcleo de cobertura, el portal, la integración al circuito clínico, la consulta/exportación de actividad y el seguimiento hospitalario con exportación de cuentas y pendientes están implementados en el PR borrador [#41](https://github.com/Mkdir-arg/SistemaDeSalud/pull/41). La demo conserva datos ficticios. Siguen pendientes la revisión del piloto y L7; no se consideran cerrados los issues #13/#15/#19. El texto de diseño que sigue conserva la secuencia original; resultados y límites vigentes están en [estado de implementación](estado-implementacion.md).

## Lectura y entregables

- [Implementación, operación y validación actual](estado-implementacion.md).
- [Seguimiento hospitalario: cuentas, cobros, pendientes y CSV auditado](seguimiento-hospitalario.md).
- [Actividad: filtros, totales y exportación auditada](actividad-y-exportacion.md).
- [Cobertura en el circuito clínico y la historia del paciente](circuito-clinico.md).
- [Vigencias, acceso histórico y auditoría: incremento implementado](vigencias-y-auditoria.md).
- [Demo local: accesos, datos ficticios y recorrido](demo-local.md).
- [Decisiones y relevamiento de issues](../2026-09-15-financiadores-cobertura-y-cobros.md).
- [Decisiones sobre las consultas acumuladas](consultas-pendientes.md): recomendaciones Q01–Q13 aprobadas y su alcance.
- [Contratos, estados y validación](contratos-y-validacion.md).
- [Planillas de ejemplo](plantillas/README.md): consumos de dos financiadores y padrón; formato propuesto, datos ficticios.
- [Simulador de cupos](../../../backend/apps/finanzas/prototipo_cupo_cobertura.py): ejecutable local en memoria, sin integración con Cauce.
- [Resultados y límites de la preparación](validacion-preparacion.md).

## 1. Primera entrega demostrable

Un usuario de una obra social ingresa a su organización, prepara planes y cobertura sobre el catálogo común, carga su padrón y comunica consumos externos. Un hospital con convenio identifica al afiliado, determina el arancel, explica el reparto, reserva cobertura y registra una prestación. Finanzas puede cobrar a los responsables y gestionar un importe que nadie aceptó asumir, con historial.

Recorrido de aceptación propuesto:

1. Plataforma prepara dos hospitales y dos financiadores de prueba en un entorno aislado. Cada organización ve únicamente sus datos autorizados.
2. El hospital publica su arancel general; una excepción por convenio puede reemplazarlo. La obra social consulta esos valores.
3. El financiador configura 80 % de cobertura y seis radiografías por año calendario; carga afiliados antes de su primera atención.
4. Importa consumos externos: revisa el resumen, aplica las filas válidas y obtiene las rechazadas. Reenviar el mismo lote no duplica usos.
5. Hospital A confirma una radiografía: el importe del paciente se muestra por prestación y se registra su aceptación. La confirmación reserva un uso.
6. Hospital B observa la disponibilidad reducida. Dos confirmaciones concurrentes no obtienen el mismo último uso.
7. Al registrar la realización, la reserva se convierte en consumo y se generan únicamente las obligaciones que correspondan. El costo interno y el dinero conservan su tratamiento existente.
8. Si el hospital rechaza asumir un copago no aceptado de una prestación realizada, el importe queda pendiente. Finanzas autorizado registra una de las resoluciones D25.
9. El financiador consulta consumos e importes de su cobertura; el hospital ve pendientes, cargos y cobros sin duplicar totales.

La automatización completa de autorizaciones previas se planifica como un incremento posterior a esa base, sujeto a Q06. No se presentará una modalidad que requiere autorización como aprobada si ese circuito aún no existe.

## 2. Qué se reutiliza y qué cambia

| Base verificada | Uso previsto | Cambio necesario |
| --- | --- | --- |
| `registros.Ciudadano`: documento y `obra_social` textual por hospital | Conservar legajos locales e histórico textual | Identidad administrativa del afiliado dentro del financiador y vínculo explícito con el paciente hospitalario |
| `accounts.Membresia` institucional; capacidades desde servidor | Mantener accesos hospitalarios existentes | Membresía del financiador separada, como propone #14 |
| `finanzas.Prestacion`, código único dentro del hospital | Mantener códigos y asociaciones locales | Vinculación explícita con catálogo común; nunca equivalencia inferida por nombre |
| `PoliticaCobro`, versiones y corte por fecha de registro | Base candidata del arancel general y decisión hospitalaria de cobrar | Excepción por convenio; separar precio, cobertura y responsable |
| `SnapshotCobroAtencion` y hecho durable | Ancla de captura y recuperación | Seleccionar un único circuito de cobro para cada origen, sin ejecutar simultáneamente legado y cobertura |
| `PendienteCobro`: una obligación por hecho/prestación | Conservar lectura y recuperación de históricos | Distribución en varias partes y saldo sin responsable definido |
| `ObligacionFinanciera`, cobros, reducciones, reintegros | Reutilizar el circuito de deuda/dinero | Vínculos estructurados al financiador o paciente y a la parte de la distribución |
| `ConcesionFinanciera`, alcance por institución/área | Permisos de decisiones hospitalarias D24 | Definir acciones exactas; nunca atribuir facultades por el nombre del rol |
| Cola durable de repartos y comandos existentes | Patrón de procesamiento recuperable | Un trabajo de importación distinto; no convertir un reparto financiero en importación |
| `InstitutionContext`, rutas protegidas y React Query | Reutilizar autenticación y componentes | Selección tipada de organización, barreras de rutas y claves de caché con su ámbito |

Hallazgo de integración: `casos/motor.py::_registrar_atencion` crea un hecho económico en la transacción clínica. `finanzas/services.py::registrar_atencion_completada` intenta capturar cobros con recuperación ante fallo. El `on_commit` observado corresponde al intento de costeo directo: no debe suponerse que toda captura financiera ya es asíncrona.

## 3. Arquitectura propuesta y alternativas

| Alternativa | Beneficio | Costo / riesgo |
| --- | --- | --- |
| **Un módulo `apps.financiadores` dentro del monolito, integrado con Finanzas** — recomendado | Aísla padrón, planes, cobertura y acceso del financiador; conserva transacciones PostgreSQL y servicios existentes | Nuevo esquema de datos y límites de responsabilidad que deben aprobarse |
| Concentrar también membresías, padrón y reglas en `apps.finanzas` | Menos puntos de alta inicial | Mezcla identidad, configuración, acceso externo, deuda y dinero en un módulo ya grande |
| Organización genérica para todo el sistema o servicio separado | Mayor generalización | Reescritura de permisos/rutas o transacciones entre servicios; costo y riesgo desproporcionados para esta entrega |

La propuesta no introduce otro motor de flujos, un registro clínico global, una plataforma genérica de importaciones ni una nueva cola de infraestructura. El precio y el dinero siguen en Finanzas; el hecho asistencial sigue en Casos. Esta arquitectura fue aprobada en Q02.

### Modelo lógico propuesto

Los nombres de esta tabla pertenecen al diseño inicial. Los modelos y migraciones implementados están en `backend/apps/financiadores`.

| Concepto / entidad candidata | Responsabilidad y condición principal |
| --- | --- |
| `Financiador`, `MembresiaFinanciador` | Organización y acceso de sus usuarios, independiente de una membresía hospitalaria |
| `AfiliadoFinanciador` | Identidad administrativa estable dentro de ese financiador; no representa una historia clínica global |
| `Afiliacion` con historial de vigencias | Relaciona identidad, número de afiliado y plan; cambiar o volver de plan no crea un cupo nuevo |
| Vínculo paciente hospitalario–afiliado | Relación explícita y verificable; no fusiona ciudadanos de hospitales distintos |
| `Plan`, `ReglaCobertura` versionada | Coberturas por prestación/categoría y fecha; contenido publicado no se reescribe silenciosamente |
| `Convenio` e historial | Relación autorizada hospital–financiador y vigencia; arancel excepcional a cargo del hospital |
| `PrestacionReferencia` y vínculo local | Catálogo común y equivalencias explícitas de prestaciones hospitalarias |
| Afiliación seleccionada del caso e historial de correcciones | Conserva la selección del ingreso D21; cambios del padrón no la sustituyen |
| `EvaluacionCobertura` | Evidencia inmutable de afiliación, regla, arancel, cantidad, fecha, reparto y motivos usados |
| `ReservaCupo`, registro de consumos | Reserva, consumo interno, consumo externo y correcciones trazables; no confundir deuda con uso de cobertura |
| `LoteImportacion`, resultados de filas | Dos contratos concretos: padrón y consumos; resumen, confirmación, reintentos y errores |
| Distribución de cobro y sus partes | Financiador, paciente, hospital o pendiente de resolución; cada obligación se vincula a su parte |
| Resolución administrativa y respaldo | Cierra pendientes según D25, con autorización D24 y evidencia; no registra por sí sola un cobro |

Para conservar las obligaciones históricas inmutables se recomienda un vínculo nuevo desde la parte de distribución a `ObligacionFinanciera`, sin reemplazar el responsable textual de obligaciones existentes. El campo legado `PendienteCobro.obligacion` mantiene su semántica para los registros anteriores.

### Identidad y privacidad

La unidad del cupo propuesta es **persona reconocida dentro del financiador + prestación común + período aplicable**. El plan define el límite; no forma parte de una identidad que reinicie el acumulado. El hospital tampoco forma parte del límite compartido.

No se unifican legajos por coincidencia aproximada de nombre o documento. Q03 define documentos, numeración familiar y cambios de identificadores. El financiador B no puede consultar el padrón o los consumos de A para detectar un cambio de cobertura: cada uno conserva únicamente su identidad y acumulado propios.

Un usuario con varios ámbitos elige una organización concreta. Toda URL, exportación, archivo, búsqueda, consulta de cupo y operación masiva vuelve a verificar ese ámbito en el servidor. Conocer un identificador válido no concede acceso. Cambiar de organización invalida o separa consultas y resultados pendientes en la interfaz.

## 4. Invariantes de cálculo y de datos

1. **Arancel ≠ costo ≠ deuda ≠ cobro.** Una asunción hospitalaria no crea una deuda del hospital consigo mismo ni un segundo gasto que duplique el costo asistencial.
2. La suma de las partes de una distribución coincide con el arancel aplicable por la cantidad realizada. La suma no vuelve a incluir el saldo original cuando se registra una resolución.
3. Sólo las partes con responsable válido y condiciones cumplidas generan obligaciones positivas. Una parte de cero no genera una obligación, cuyo modelo actual exige importe positivo.
4. Un consumo externo modifica cobertura, no crea actividad ni deuda de un hospital de Cauce.
5. La reserva pasa a consumo una sola vez. Reintentos, doble clic y recuperación no duplican cupo ni obligaciones.
6. Las consultas de cobertura no reservan. Una reserva antigua no vence por tiempo; se revisa según D27.
7. Concurrencia: revalidar dentro de la transacción que decide, no sólo al mostrar el resumen o la cotización.
8. El caso conserva la afiliación seleccionada. Se conserva el histórico al corregirla y se siguen evaluando reglas a la fecha del hecho según #16.
9. Mes/año se determinan por la fecha de la prestación, no por la de importación. La zona configurada en Cauce es `America/Argentina/Buenos_Aires`.
10. Una carga tardía conserva las decisiones realizadas y señala discrepancias D14. Q01 conserva también las reservas confirmadas y marca la discrepancia.
11. No se representan importes con `float`. #16 propone redondeo decimal a dos posiciones, mitad hacia arriba; calcular una parte y obtener la otra por diferencia para conservar el total.
12. Agotar cupo es distinto de no poder evaluar por un error o falta de datos. Un fallo técnico no se transforma en deuda al paciente.
13. El histórico conserva valores y nombres relevantes aunque cambien el catálogo, las reglas, el arancel, el afiliado o el convenio.

### Transacciones y recuperación propuestas

- Comenzar coordinando por la fila estable del afiliado dentro del financiador: bloquearla, releer consumos y reservas aplicables, decidir y escribir. Evita crear un servicio externo de bloqueo y coordina topes mensuales/anuales y cambios de plan. El costo es serializar brevemente distintas prestaciones del mismo afiliado; revisar después con datos de volumen.
- Todos los escritores de cupo usan ese mismo protocolo: confirmación, realización, liberación, carga externa y correcciones. Bloquear sólo el hecho de un hospital no resuelve la competencia entre hospitales.
- Fijar un orden único de bloqueos. La integración debe revisar los bloqueos ya tomados por Casos para evitar que un proceso tome «caso → afiliado» y otro «afiliado → caso». No cerrar la implementación sin una prueba PostgreSQL con dos conexiones.
- Crear el hecho durable en el circuito existente. Un fallo en liquidación de partes queda recuperable desde su origen; no se elimina la atención. Si había reserva, mantenerla ocupada hasta reconciliar el consumo evita ofrecer el uso de nuevo mientras se recupera.
- La fila de importación se confirma con su efecto o queda sin aplicar; procesar filas en unidades recuperables. El lote informa aplicadas, rechazadas, por revisar y pendientes técnicas por separado.
- La confirmación y los reintentos conservan una clave y su contenido canónico. Clave repetida con otro contenido es conflicto, no una modificación encubierta.

## 5. Experiencia de uso

### Portal del financiador

| Pantalla | Tarea principal | Información y acciones |
| --- | --- | --- |
| Organización | Completar información propia permitida | Datos administrativos; alta de organización e invitación inicial según #14 |
| Planes y cobertura | Configurar qué cubre y desde cuándo | Prestaciones del catálogo común, porcentaje, tope y período; revisión de cambios antes de publicar |
| Afiliados | Mantener padrón | Búsqueda, plan e historial, plantilla, resumen de altas/actualizaciones y errores; sin bajas por Excel |
| Consumos externos | Poner al día el uso fuera de Cauce | Carga individual o Excel personalizado; resumen y resultados por fila |
| Convenios y aranceles | Consultar condiciones con hospitales | Arancel general y excepción aplicable; el hospital carga los valores |
| Consumos en Cauce | Explicar el uso de su cobertura | Prestación, fecha, cantidad e importe propio autorizado; acceso mínimo, sin historia clínica |
| Usuarios | Administrar operadores propios | Roles y permisos limitados a su financiador |
| Autorizaciones | Incremento posterior Q06 | Solicitudes y justificación mínima cuando el circuito completo esté habilitado |

Las pantallas parten de tareas concretas; se reutilizan tabla, filtros, paginación, modales y mensajes del producto. El operador no necesita conocer nombres de modelos, transacciones ni tareas internas.

### Hospital

- Admisión: elegir afiliación estructurada o particular, visualizar verificación y vigencia; conservar esa selección en el caso.
- Antes de la prestación: mostrar arancel, cobertura, copago, disponibilidad y motivos. La aceptación del paciente identifica prestación e importe; una condición distinta exige volver a explicarla.
- Confirmación: el resultado del servidor determina si se obtuvo la reserva. La pantalla no muestra éxito antes de esa respuesta.
- Realización/cancelación: conservar el hecho asistencial y convertir/liberar la reserva según D26.
- Finanzas: distribución del importe, obligaciones y cobros; rechazar asunción, revisar pendientes y registrar respaldo de la resolución.
- Reservas antiguas: mostrar cantidad, fecha, hospital y estado verificable; liberar tras confirmar no realización. Q10 define antigüedad y permisos.

## 6. Secuencia de implementación

Cada lote termina en un recorrido verificable; no se considera completo por crear tablas o endpoints. La secuencia es una propuesta de entregas, no una orden de publicar PR o desplegar.

| Lote | Resultado observable | Áreas probables | Dependencias de decisión / salida |
| --- | --- | --- | --- |
| **L0 — contratos** | Diseño, preguntas, muestras y escenarios revisables | Estos documentos, prototipo y plantillas | Q01–Q06 para habilitar los primeros cambios estructurales |
| **L1 — organización y catálogo** | Usuario del financiador entra a su ámbito, ve sólo su organización y configura planes sobre catálogo común | Nuevo módulo; `accounts`, `common`, rutas, `InstitutionContext`, `App` | Q02/Q03; pruebas negativas de acceso incluyendo usuarios mixtos |
| **L2 — padrón y convenios** | Padrón previo a atención, carga incremental sin bajas, relación autorizada con hospital y selección en caso | Afiliaciones, convenio, importación de padrón, ficha administrativa | Q03/Q04/Q05/Q07; un archivo parcial no retira afiliaciones |
| **L3 — reglas y evaluación** | Simular cobertura explica porcentaje, cantidad, precio y motivos sin reservar | Reglas versionadas, arancel excepcional, evaluación, puesto hospitalario | Q01/Q05/Q08/Q11; precedencia determinista y pruebas de importes |
| **L4 — cupo y consumos externos** | Último uso protegido; consumos externos y reservas antiguas explicados | Servicios de cupo, importación, confirmación, realización y liberación | Q01/Q07/Q08/Q10; contención PostgreSQL y recuperación |
| **L5 — reparto y cobros** | Deuda correcta a cada responsable y resolución de saldo rechazado | `models_cobros`, `cobros`, `dinero`, permisos, cuenta y reportes | Q09/Q11; no duplicar circuito legado ni totales; auditar D24/D25 |
| **L6 — cierre demostrable** | Recorrido completo con dos hospitales y financiadores, archivos con errores y reintentos | E2E, accesos históricos, observabilidad, documentación operativa | Matriz de aceptación y revisión humana de Q pendientes |
| **L7 — autorizaciones previas** | Solicitar, observar, aprobar/rechazar, vencer y resolver continuidad | #17/#18/#20, Casos y notificaciones existentes | Q06; no activar una espera clínica sin su contrato completo |

### Trazabilidad a GitHub

- L1/L2: [#13](https://github.com/Mkdir-arg/SistemaDeSalud/issues/13), [#14](https://github.com/Mkdir-arg/SistemaDeSalud/issues/14), catálogo [#9](https://github.com/Mkdir-arg/SistemaDeSalud/issues/9)/[#10](https://github.com/Mkdir-arg/SistemaDeSalud/issues/10).
- L3/L4: [#15](https://github.com/Mkdir-arg/SistemaDeSalud/issues/15), [#16](https://github.com/Mkdir-arg/SistemaDeSalud/issues/16); D8–D20 y D26/D27 amplían ese alcance.
- Portal transversal L1–L6: [#19](https://github.com/Mkdir-arg/SistemaDeSalud/issues/19), [#20](https://github.com/Mkdir-arg/SistemaDeSalud/issues/20). Separar escritura de consumos externos de la lectura de hechos hospitalarios.
- L5/L6: [#11](https://github.com/Mkdir-arg/SistemaDeSalud/issues/11), [#12](https://github.com/Mkdir-arg/SistemaDeSalud/issues/12), [#33](https://github.com/Mkdir-arg/SistemaDeSalud/issues/33), [#38](https://github.com/Mkdir-arg/SistemaDeSalud/issues/38), [#39](https://github.com/Mkdir-arg/SistemaDeSalud/issues/39).
- L7: [#17](https://github.com/Mkdir-arg/SistemaDeSalud/issues/17), [#18](https://github.com/Mkdir-arg/SistemaDeSalud/issues/18). #6/#29/#30/#31 aportan riesgos de concurrencia, contratos y recuperación; no son prerrequisitos para reescribir esos subsistemas.
- #21–#26 no se convierten en dependencias de la primera entrega por necesitar una aceptación de pago; no se asumió que deba realizarse desde WhatsApp o el portal del paciente.

La consulta renovada contiene 39 issues abiertos y mantiene #13–#20 con el contenido de la auditoría inicial. La vista de proyecto fue verificada en el relevamiento original; los cinco ítems de Chaco-Back no agregan requisitos de financiadores. No se modificaron issues ni estados de GitHub.

## 7. Migración, activación y reversión propuestas

1. Migraciones aditivas, sin eliminar `Ciudadano.obra_social`, las políticas ni obligaciones existentes. No transformar texto legado ambiguo en afiliación verificada.
2. Preparar un comando de diagnóstico de legado que sólo informe candidatos y conflictos. La carga real o backfill se revisa con su reporte y se ejecuta únicamente en el entorno autorizado.
3. Preservar la ruta de cobro histórica. Marcar el modo de captura en el origen nuevo antes de procesarlo; recuperaciones y reintentos respetan ese modo aunque cambie la habilitación del hospital.
4. Antes de activar, verificar catálogo vinculado, convenio, reglas, padrón, arancel, permisos y soporte de recuperación. Una configuración incompleta se muestra explícitamente.
5. Piloto por hospital/convenio, con cuentas de prueba aisladas y aceptación observable. Nunca agregar automáticamente concesiones financieras a usuarios existentes.
6. Reversión operativa: detener nuevas confirmaciones/importaciones del circuito nuevo, mantener lectura, reservas y recuperación de hechos ya comprometidos, y resolver pendientes. Desactivar una pantalla no libera cupos ni borra deudas.
7. No ejecutar una migración inversa destructiva para salir de un incidente. Las decisiones financieras ya emitidas y las reservas activas exigen reconciliación antes de retirar cualquier estructura.

## 8. Autorización y límites de ejecución

Q01–Q13 fueron resueltas adoptando las recomendaciones documentadas. Se implementan el módulo separado dentro del monolito, la identidad estable, las reservas protegidas, las importaciones parciales y la resolución administrativa explícita.

Las migraciones se preparan y verifican con bases aisladas. La activación con datos reales y la incorporación final requieren revisar el resultado concreto. La aprobación de recomendaciones no se presenta como comprobación de comprensión de cada detalle técnico.
