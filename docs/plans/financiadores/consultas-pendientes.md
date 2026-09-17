# Recomendaciones aprobadas Q01–Q13

El 15/09/2026 el usuario indicó: **«en todas las preguntas, sigue tu recomendacion»**. Quedan aprobadas las recomendaciones Q01–Q13 siguientes para la implementación local. Los textos de preguntas y bloqueos se conservan como antecedentes, ya resueltos por esa elección. Los acuerdos D1–D27 permanecen en [el relevamiento](../2026-09-15-financiadores-cobertura-y-cobros.md).

No quedan respuestas pendientes de Q01–Q13. La secuencia original distinguía L1–L6 y una entrega posterior L7; ambas están implementadas, con contratos y límites actuales en [continuidad implementada](continuidad-implementada.md). Volúmenes reales, plazos legales de conservación y configuración de cada hospital siguen siendo datos operativos no informados: no se inventan purgas ni demanda. Esta aprobación funcional no autoriza migraciones sobre datos reales ni despliegues. Las preguntas y sus textos «Bloquea» que siguen son antecedentes históricos, no bloqueos actuales.

## Q01 — Una reserva confirmada y un consumo externo tardío

**Situación:** quedan seis usos anuales, cinco consumidos y uno reservado por un hospital. La obra social informa después un consumo externo anterior que agota el cupo. D14 protege las decisiones realizadas; D26 agregó una reserva previa que todavía no tiene una regla para este conflicto.

**Decisión:** ¿se conserva esa reserva y se señala la discrepancia, o se vuelve a evaluar y puede perder la cobertura antes de realizarse?

**Recomendación:** conservar la reserva confirmada y señalar la discrepancia, extendiendo explícitamente la protección de D14 a ese compromiso. Mantiene lo informado al hospital, pero puede superar el límite conocido y requerir una resolución con el financiador. La alternativa evita confirmar cobertura por encima del límite actualizado, a costa de cambiar lo informado y obtener una nueva aceptación si aparece un copago. Ninguna se implementará como supuesto oculto.

**Bloquea:** el efecto de cargas tardías sobre reservas y la promesa que hace la confirmación en L3/L4. El simulador deja este caso sin resolución automática para mostrarlo.

## Q02 — Base del módulo y arquitectura

**Decisión:** ¿adoptamos el módulo `financiadores` dentro del monolito, con membresías propias y conexión a los servicios actuales de Finanzas, como describe el [plan](README.md)?

**Recomendación:** esa separación. Reutiliza Django/PostgreSQL y la deuda existente; evita una reescritura general del concepto de organización. Exige modelos nuevos, límites de permisos y migraciones aditivas. La alternativa de concentrar todo en Finanzas reduce altas iniciales pero mezcla más responsabilidades; un servicio separado agrega coordinación e infraestructura.

**Antes de incorporar:** revisar el modelo propuesto, el alcance de cada organización y cómo se recupera un cobro sin duplicarlo. La aprobación funcional no acredita todavía comprensión del diseño técnico ni autoriza datos/migraciones reales.

**Bloquea:** esquema definitivo y cambios de autenticación/organización de L1. Los borradores de contratos y archivos pueden completarse antes.

## Q03 — Identidad del afiliado

**Datos necesarios:** ¿el número de afiliado es individual o puede compartirse por grupo familiar? ¿Qué documentos admitimos además de DNI argentino y cómo se informa un cambio de documento/número?

**Recomendación:** identidad estable dentro de cada financiador, con ambos identificadores confirmados en D12; vinculación explícita al ciudadano de cada hospital. Un mismo número familiar no identifica por sí solo a una persona. Las coincidencias ambiguas requieren revisión; no fusionar por nombres parecidos. Los cambios de número no reinician cupos ni alteran el caso histórico.

**Bloquea:** claves únicas, normalización, tratamiento de menores/extranjeros y vinculación entre hospitales en L1/L2. La plantilla no elimina ceros iniciales ni crea un registro clínico global.

## Q04 — Autoridad del padrón y acceso histórico

**Situación:** el hospital declara plan A, pero el padrón del financiador dice B, o no encuentra al afiliado. #14 partía de carga hospitalaria; D17 agregó un padrón propio.

**Decisiones:** ¿qué fuente confirma la cobertura y quién puede corregir el conflicto? ¿El financiador conserva acceso mínimo a sus cargos pendientes y casos que mantienen su afiliación aunque ésta haya vencido?

**Recomendación:** el financiador confirma su padrón; el hospital puede registrar una declaración pendiente de verificar. Ante conflicto, mostrar «Afiliación pendiente de verificación» y no inventar cobertura ni deuda al paciente. Una fila de consumo de un afiliado inexistente se rechaza para corregir el padrón antes, sin crear una afiliación incompleta. Para históricos, conservar acceso sólo a sus operaciones pendientes y al mínimo necesario, con auditoría; no prolongar acceso a la historia clínica ni al padrón de otra obra social.

**Bloquea:** elegibilidad, importador y permisos históricos en L2/L6. Requiere resolver la tensión entre #14/#20 y la continuidad D21.

## Q05 — Fechas, cambios de plan y cambio de período

**Situaciones:** una reserva del 30 de septiembre se realiza el 1 de octubre; un plan o arancel cambia entre confirmación y realización; una atención realizada ayer se registra hoy.

**Decisiones:** ¿qué fecha acredita la realización y qué compromiso conserva la reserva cuando cambian período, regla o precio?

**Recomendación:** fecha efectiva de prestación separada de fecha de registro; revalidar período y condiciones antes de realizar si cambiaron, mostrando cualquier nuevo importe y renovando su aceptación. Para una prestación ya realizada, preservar la decisión registrada y derivar correcciones a revisión. La afiliación del caso permanece según D21. No aplicar automáticamente a casos abiertos un plan que cambió en el padrón.

**Costo:** una revalidación puede dejar sin disponibilidad en el nuevo período; congelar precio/cobertura desde la reserva implica un compromiso contractual distinto y no equivale a RN3 de #16. El campo actual `HechoAtencionCosteable.ocurrida_en` se establece al registrar, por lo que el contrato requiere una decisión explícita.

**Bloquea:** intervalos, snapshots y evaluación definitiva en L3/L4. Las fechas y columnas de vigencia en el Excel de padrón son propuestas hasta resolverlo.

## Q06 — Primera entrega y continuidad asistencial

**Decisiones:** ¿la primera entrega debe incluir el circuito completo de autorización previa, o lo construimos después del recorrido de parametría–consumo–cobro? ¿La excepción a la espera aplica a toda Guardia o sólo a prioridad `URGENTE`?

**Recomendación:** primera entrega informativa y de gestión financiera, siguiendo #16; autorizaciones completas en L7. Resolver la distinción Guardia/URGENTE antes de programar una espera, porque #17 y #18 no usan la misma condición. Una denegación financiera, error de evaluación o rechazo de asunción no cancela automáticamente una atención.

**Bloquea:** alcance de L6/L7 y cualquier cambio que detenga el motor. Para la primera demostración usar planes sin autorización previa; una modalidad aún no soportada no se mostrará como cubierta.

## Q07 — Volumen de Excel y dependencias

**Datos necesarios:** cantidad habitual/máxima de afiliados y consumos por archivo, frecuencia de actualización, tamaño aproximado y número de operadores simultáneos.

**Recomendación:** `.xlsx` con columnas estables, catálogo personalizado y dos importadores concretos. Procesamiento recuperable por filas/lotes, con límites publicados antes de subir. Definir esos límites con los volúmenes; no prometer que cien mil filas caben en una petición HTTP ni crear infraestructura nueva sin necesidad.

Para producción se propone evaluar `openpyxl` con protección XML y límites de ZIP/filas/tamaño/tiempo. La documentación oficial advierte que requiere protección adicional frente a determinadas expansiones XML: [seguridad de openpyxl](https://openpyxl.readthedocs.io/en/stable/#security). El entorno local ya tenía `openpyxl 3.1.5` y `defusedxml` para generar artefactos; no se agregaron al backend ni se eligió una versión productiva.

**Bloquea:** capacidad, modalidad de procesamiento y dependencias de L2/L4. Las planillas de muestra no fijan el límite de producción.

## Q08 — Posibles duplicados y corrección de consumos externos

**Decisiones:** ¿qué usuarios del financiador pueden confirmar que dos filas iguales sin referencia son consumos distintos? ¿Cómo corrigen un consumo ya importado con fecha/cantidad/persona equivocadas?

**Recomendación:** revisión explícita por operador autorizado del financiador, con motivo. No aplicar silenciosamente una coincidencia ambigua. Corregir mediante un registro vinculado que deje visible el original y su efecto corregido, sin borrar el lote ni reescribir decisiones hospitalarias. Volver a validar el período y señalar discrepancias cuando corresponda.

**Bloquea:** revisión de duplicados, permisos de corrección y efectos de reversión en L4. D13 ya confirma referencia opcional y reintentos protegidos; no se vuelve a preguntar eso.

## Q09 — Respaldo de aceptación y resoluciones parciales

**Decisiones:** ¿qué evidencia debe respaldar la aceptación del paciente y un acuerdo posterior del financiador: documento adjunto, aceptación registrada en mostrador, acción autenticada en portal u otra? ¿Se puede resolver sólo una parte del saldo y mantener el resto pendiente?

**Recomendación:** primera entrega con registro identificado de prestación/importe y respaldo documental cuando se resuelva por acuerdo posterior, sin introducir firma digital externa. Finanzas decide según D24; quien registra la aceptación inicial debe tener autorización hospitalaria específica. Admitir resolución total inicialmente simplifica control y auditoría; si los acuerdos parciales son frecuentes, incluirlos desde el contrato inicial en lugar de simularlos con dos cargos.

**Bloquea:** contrato de aceptación, adjuntos, estados y división del saldo en L5. Registrar una aceptación y registrar el dinero recibido continúan separados.

## Q10 — Reservas antiguas y declaración de no realización

**Decisiones:** ¿a partir de qué antigüedad se destacan y quién puede confirmar que no se realizó la prestación?

**Recomendación:** umbral configurable por hospital, usado sólo para mostrar pendientes. Confirmación de no realización por personal autorizado del área que puede verificar la prestación, dejando actor/fecha/motivo; Finanzas puede revisar su efecto económico. No asumir que un permiso financiero permite certificar un hecho asistencial. La liberación no vence automáticamente, conforme a D27.

**Bloquea:** permiso y filtro de revisión en L4. Una realización que llega durante o después de una liberación exige preservar ambos registros y revisión; no borrar la evidencia que contradiga la declaración.

## Q11 — Falta de arancel o de regla

**Situaciones:** la prestación no tiene arancel general ni excepción; el hospital desactivó explícitamente el cobro; una regla no existe; el evaluador falla.

**Recomendación:** conservar la decisión hospitalaria de no cobrar cuando la política lo indica; no usar la cobertura para activar cobros. Si debería cobrarse pero falta precio, mostrar «Arancel pendiente» sin inventar cero ni importe a pagar. Seguir #16 para ausencia real de regla: «No cubierta — sin regla aplicable». Para información incompleta o fallo técnico: «Pendiente de evaluación», sin convertirlo en denegación o deuda al paciente.

**Decisión:** confirmar esas diferencias y el tratamiento del cupo de una prestación sin arancel/cobro, ya que costo, uso de cobertura y facturación no son equivalentes.

**Bloquea:** evaluación y emisión de obligaciones de L3/L5.

## Q12 — Alcance del límite y cantidades parciales

**Situaciones:** el plan limita «Radiografías» y el catálogo tiene códigos diferentes; se solicitan tres unidades pero quedan dos cubiertas; se realiza una prestación pagada enteramente por el paciente.

**Recomendación:** comenzar con topes por prestación común, sin una bolsa compartida entre categorías salvo que se confirme esa necesidad. Cuando haya varias unidades de una misma prestación, separar unidades cubiertas y excedentes y mostrar el importe total del paciente antes de aceptar. Contar consumos de cobertura, no toda actividad clínica ni cualquier cargo anulado; la devolución de dinero por una prestación realizada no demuestra que no se consumió cobertura.

**Decisión:** confirmar si se necesitan bolsas entre códigos, cantidades internas mayores a una y qué tipos de consumo afectan el tope. Si el alcance inicial es una unidad por ejecución, debe quedar explícito y validarse.

**Bloquea:** clave de agregación, fraccionamiento y correcciones en L3/L4. #16 cuenta cargos no anulados, lo que requiere ajustar el modelo al separar uso, cobro y reintegro.

## Q13 — Conservación y acceso a archivos

**Datos necesarios:** política organizacional para conservar planillas originales, filas rechazadas y respaldos de aceptación; usuarios habilitados para descargarlos y condiciones de acceso de afiliaciones vencidas.

**Recomendación:** acceso privado por organización y permiso, descargas auditadas, errores con los datos mínimos para corregirlos y retención acorde con la política que indique el responsable. No publicar adjuntos ni fijar años de conservación por una suposición del agente. Conservar la evidencia necesaria de decisiones y efectos aunque se retire un archivo según esa política.

**Bloquea:** almacenamiento definitivo de archivos, expiración de descargas y operación de L2/L5/L6.

## Propuestas que ya tienen respaldo en issues y no necesitan otra entrevista por defecto

Se incorporan al diseño como base de los issues, sujetas a la revisión conjunta; no se atribuyen a una confirmación nueva del usuario:

- #14: plataforma crea el financiador e invita al primer administrador; no hay autorregistro. Las invitaciones no se envían durante esta preparación.
- #14: convenio entre hospital y financiador con propuesta/aceptación, y posibilidad de alta directa por plataforma; falta concretar pantallas, no inventar negociaciones de arancel dentro de I-Core Salud.
- #14/#16: varias afiliaciones posibles, elección de una para el caso; no combinar automáticamente financiadores complementarios.
- #20: admin del financiador gestiona configuración/usuarios; operador y auditor tienen alcances distintos. No se otorga historia clínica por ser auditor de la obra social.
- #16: especificidad plan+prestación → plan+categoría → financiador+prestación → financiador+categoría → default del convenio. Para evitar una regla adicional ambiguamente situada de #20, cualquier excepción por convenio fuera de ese default debe definirse antes de habilitarla.
- D1/D2/D21 prevalecen sobre cualquier propuesta incompatible: arancel del hospital, excepción opcional y afiliación fija por caso.

## Revisión al regreso

Q01–Q13 quedaron resueltas adoptando las recomendaciones. Al regreso corresponde revisar el [resultado implementado y validado](estado-implementacion.md), sus fallos posibles y la reversión antes del piloto. Las pruebas no demuestran por sí solas la comprensión o aceptación humana del resultado.
