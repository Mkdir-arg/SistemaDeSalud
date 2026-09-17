# Financiadores, cobertura y cobros

Fecha: 15/09/2026. Estado: 27 decisiones funcionales confirmadas y recomendaciones Q01–Q13 aprobadas («en todas las preguntas, sigue tu recomendacion»). Implementación local autorizada; activación con datos reales pendiente de revisión del resultado.

Continuación: [plan de implementación y materiales](financiadores/README.md), [consultas acumuladas](financiadores/consultas-pendientes.md) y [validación de la preparación](financiadores/validacion-preparacion.md).

## Objetivo expresado por el usuario

Priorizar obras sociales, mutuales, otros financiadores y pagos directos de pacientes por consultas no cubiertas. El usuario del financiador debe poder ingresar y cargar su parametría: organización, planes y prestaciones cubiertas, incluyendo límites de cantidad y porcentajes. El hospital necesita determinar cuánto corresponde cobrarle al financiador por las prestaciones realizadas.

El usuario amplió el alcance para que el financiador también pueda informar, por afiliado, consumos realizados en instituciones ajenas a I-Core Salud y descontarlos del cupo compartido. D8 define esa capacidad y D9 agrega prestación, fecha y cantidad con carga masiva mediante una plantilla de Excel personalizada; no depende de una integración automática externa. D17 incorpora un padrón propio del financiador, con carga masiva y sencilla, aun antes de la primera atención de sus afiliados en Salud.

Este recorrido orienta la primera entrega. Todavía se deben acordar las reglas que convierten una cobertura en un cargo, los permisos y los criterios observables de los casos parciales, desconocidos o rechazados. La configuración de cobertura no implica por sí sola facturación fiscal, liquidación aceptada ni transferencia de dinero.

## Fuentes verificadas

- Repositorio local: `Mkdir-arg/SistemaDeSalud`, HEAD `a6bf26c` al iniciar, sin cambios locales previos. Se inspeccionó código; no se consultaron datos de la demo.
- [Vista Tareas Salud](https://github.com/users/Mkdir-arg/projects/1/views/19): el filtro consultado por API es `(proyecto:Salud or repo:Mkdir-arg/SistemaDeSalud)`.
- Se recuperaron los 296 elementos del proyecto; 43 coinciden con ese filtro. Hay 38 issues del repositorio en la vista y cinco issues de `Chaco-Back` marcados Salud. El repositorio tiene además el issue #32, que no aparece entre esos 38 elementos de la vista.
- Los cinco issues adicionales (#361–#365 de `Chaco-Back`) tratan filtros de tablero/supervisión, legajo profesional, visualización de tiempos e ingreso de pacientes. Sus descripciones no agregan requisitos de financiadores.
- Se recuperaron descripciones y comentarios de los issues abiertos y cerrados del repositorio. Se contrastaron los análisis centrales y se buscaron menciones relacionadas en el resto; una coincidencia con «cobertura» de pruebas o de reparto no equivale a cobertura de salud.
- Los issues #13–#20 permanecen abiertos y en Roadmap. Ese estado no refleja aún la prioridad expresada en esta conversación.
- El documento `docs/analisis/2026-08-21-costos-obra-social-canal-paciente.md`, citado por esos issues, no está en este checkout ni apareció en el historial local disponible de esa ruta. Los análisis publicados contienen requisitos y preguntas; no se reconstruyen las supuestas decisiones humanas del documento ausente.

## Mapa de issues

| Tema | Issues | Relación con el objetivo |
| --- | --- | --- |
| Identidad del financiador | [#13](https://github.com/Mkdir-arg/SistemaDeSalud/issues/13), [#14](https://github.com/Mkdir-arg/SistemaDeSalud/issues/14) | Financiadores, planes, convenios, afiliaciones, usuarios y aislamiento por organización. D17 amplía la carga hospitalaria de afiliaciones con un padrón gestionado masivamente por el financiador. |
| Cobertura | [#15](https://github.com/Mkdir-arg/SistemaDeSalud/issues/15), [#16](https://github.com/Mkdir-arg/SistemaDeSalud/issues/16) | Reglas por prestación/categoría, plan, vigencia, copago, topes y asignación del responsable. D8 amplía el cálculo del cupo con consumos externos informados. |
| Portal del financiador | [#19](https://github.com/Mkdir-arg/SistemaDeSalud/issues/19), [#20](https://github.com/Mkdir-arg/SistemaDeSalud/issues/20) | Pantallas de parametría, usuarios, convenios, autorizaciones y consulta de consumos. D8 agrega la carga de consumos externos; no habilita editar los cargos de hospitales de Salud. |
| Autorizaciones | [#17](https://github.com/Mkdir-arg/SistemaDeSalud/issues/17), [#18](https://github.com/Mkdir-arg/SistemaDeSalud/issues/18) | Solicitud, observación, aprobación, rechazo, vencimiento y relación con continuidad asistencial. Alcance de primera entrega por decidir. |
| Catálogo y aranceles | [#9](https://github.com/Mkdir-arg/SistemaDeSalud/issues/9), [#10](https://github.com/Mkdir-arg/SistemaDeSalud/issues/10) | Base de prestaciones y valores; existe política mínima de cobro separada del costo. D16 agrega un catálogo común de referencia. Falta concretar su vínculo con las prestaciones locales y el contrato de aranceles por convenio. |
| Hechos y cargos | [#11](https://github.com/Mkdir-arg/SistemaDeSalud/issues/11), [#12](https://github.com/Mkdir-arg/SistemaDeSalud/issues/12) | Origen asistencial del cargo y consulta por paciente/caso. Reutilizar lo implementado. |
| Cobros y seguimiento | [#33](https://github.com/Mkdir-arg/SistemaDeSalud/issues/33), [#38](https://github.com/Mkdir-arg/SistemaDeSalud/issues/38), [#39](https://github.com/Mkdir-arg/SistemaDeSalud/issues/39) | Obligaciones, parciales, reintegros y reportes existentes; falta enlazar al financiador estructurado. |
| Relacionados según alcance | #21–#26; #29–#31; #35 | Canal/portal del paciente, contratos entre módulos, procesos e integraciones, cajas/cuentas. No convertirlos en dependencias obligatorias sin necesidad concreta. |

## Contraste con el código actual

| Evidencia | Comportamiento observado | Consecuencia para el plan |
| --- | --- | --- |
| `backend/apps/registros/models.py`, `Ciudadano` | El ciudadano pertenece a una institución; `obra_social` es texto libre. | Ese texto no prueba afiliación ni cobertura. Definir identidad, procedencia y tratamiento entre instituciones. |
| `backend/apps/accounts/models.py`, `Membresia`; `backend/apps/common.py` | Roles y filtros de acceso asociados a instituciones. | El acceso del financiador exige un contrato propio; no otorgarle acceso hospitalario amplio como atajo. |
| `frontend/src/auth/InstitutionContext.jsx` | Organización activa expresada como institución; capacidades institucionales recibidas del servidor. | Extender el contexto requiere asegurar que no se mezclen capacidades ni datos entre organizaciones. |
| `backend/apps/finanzas/models_cobros.py`, `PoliticaCobro` | Política histórica con arancel, vigencia y contraparte textual por prestación. | No resuelve planes, convenios, copagos ni pagador a partir del paciente. |
| `backend/apps/finanzas/cobros.py`, `capturar_cobros_atencion` | Captura desde hecho durable, con políticas vigentes y registradas antes de la atención; bloqueos y reintentos. | Preservar el corte histórico y evitar doble cargo al incorporar cobertura. |
| `PendienteCobro` | Un pendiente por hecho/prestación y una obligación asociada. | Dividir entre financiador y paciente requiere resolver este contrato; no alcanza con agregar un porcentaje a la pantalla. |
| `backend/apps/finanzas/models.py`, `ObligacionFinanciera` | Deuda con origen, moneda ARS y contraparte textual, separada del movimiento de dinero. | Reutilizar obligaciones/movimientos, definir su vínculo estructurado y preservar originales. |
| Directorio `backend/apps` | Existe `finanzas`; no hay aplicaciones `costos` ni `financiadores`. | Adaptar los nombres y puntos de integración propuestos por los issues antiguos. |

El [cierre post-demo](../funcionalidades/finanzas-costos/estado-post-demo-2026-09-15.md) documenta validaciones anteriores y límites. Sus resultados no fueron ejecutados de nuevo en esta sesión. Tampoco los checkpoints de demo que aún figuran en GitHub prueban el estado de un servicio actual.

## Decisiones confirmadas

### D1. Carga hospitalaria de aranceles acordados

El usuario confirmó: «El hospital cargará el arancel previamente acordado con el financiador».

Cuando existe un precio excepcional acordado fuera del sistema, el hospital lo carga y el financiador lo consulta, según la opción presentada y la propuesta de #20. No se incorpora un circuito de negociación y aceptación de precios dentro de Salud. D2 aclara que este acuerdo excepcional no es necesario para aplicar el arancel general del hospital.

Criterio observable: el hospital puede registrar el arancel acordado para una prestación y su financiador; el usuario de ese financiador puede consultar el arancel correspondiente. Los permisos específicos, vigencias y condiciones para utilizarlo al generar un cargo siguen por definir.

### D2. Arancel general por defecto y acordado como excepción

El usuario confirmó: «usamos el arancel general del hospital por defecto. ese arancel acordado es como para excepciones, por default es el mismo que pone el hospital».

Para la prestación, se utiliza el arancel específico acordado con el financiador cuando corresponde; en ausencia de esa excepción se utiliza el arancel general del hospital. No se exige duplicar el arancel general en una lista de cada financiador ni dejar pendiente el importe sólo porque no exista un precio excepcional.

Criterios observables:

- Con arancel general de $10.000 y sin excepción para el financiador, la base de cálculo de cobertura es $10.000.
- Con arancel general de $10.000 y una excepción aplicable de $8.000, la base de cálculo de cobertura es $8.000.
- El arancel seleccionado es la base de cálculo; la cobertura determina qué parte corresponde al financiador. D6/D7 definen la aceptación y el remanente a cargo del paciente.

Esta aclaración corrige la interpretación previa del agente, que trataba el acuerdo específico como requisito para disponer de un precio. El comportamiento coincide con la propuesta de respaldo al arancel general de #16. Quedan pendientes las vigencias, granularidad de excepciones y el tratamiento de una prestación que tampoco tenga arancel general.

### D3. Porcentaje y tope de cantidad combinables

El usuario confirmó que una cobertura puede combinar porcentaje y cantidad, ante el ejemplo «cubre el 80 % de hasta 6 radiografías por año», con límite de cantidad opcional.

Criterios observables:

- Una misma regla permite expresar el porcentaje cubierto y un máximo de prestaciones por período.
- La configuración permite representar el ejemplo de 80 % y seis radiografías por año, sin obligar a elegir entre porcentaje o cantidad.
- El límite de cantidad puede omitirse: esa regla no impone un tope de usos. Las demás condiciones de cobertura conservan su significado.

El ejemplo confirma que ambas condiciones pueden coexistir; el ámbito del conteo se define en D4, el resultado al superar el máximo en D5 y los períodos calendario en D15. D7 atribuye el remanente al paciente con aceptación por prestación e importe.

### D4. Cupo compartido entre hospitales

El usuario confirmó: «el cupo es compartido», ante la alternativa de compartir el límite del afiliado entre hospitales de Salud o conceder un cupo independiente en cada hospital.

Criterio observable: con un límite de seis radiografías en el período y cuatro usos en el Hospital A, el mismo afiliado dispone de dos usos en el Hospital B. Cambiar de hospital no reinicia ni multiplica el cupo.

Consecuencias técnicas a resolver al diseñar:

- Reconocer al mismo afiliado entre instituciones con una identidad fiable. #14 vincula afiliaciones al ciudadano institucional y #16 cuenta por afiliación; implementar literalmente esos vínculos no alcanza para cumplir el cupo compartido. No se decidió aún modificar la identidad clínica ni unificar historias clínicas.
- D16 establece el catálogo común al que se vinculan las prestaciones hospitalarias para consumir el cupo correspondiente. Falta concretar esas vinculaciones y sus controles.
- Probar que dos hospitales no puedan aplicar simultáneamente el último uso disponible. El momento de reserva/consumo y la liberación por cancelación siguen por definir.
- Consultar el saldo necesario para evaluar la cobertura sin conceder acceso clínico a otra institución.
- D8 incorpora la carga por el financiador de usos realizados fuera de Salud. La ausencia de esa carga no demuestra ausencia de consumos externos; no se presupone una integración automática ni que el saldo registrado sea exhaustivo.

### D5. Cupo agotado: prestación no cubierta

El usuario eligió «no cubierta» para la prestación que excede el cupo, frente a la alternativa de solicitar una autorización excepcional al financiador. Se confirma la propuesta de la pregunta abierta 3 de #16.

Criterios observables:

- Con seis radiografías cubiertas ya consumidas en el período y un tope de seis, la siguiente figura como «No cubierta» con motivo de cupo agotado, independientemente del hospital donde se solicite.
- Esa regla no atribuye al financiador el importe de la prestación excedente ni inicia automáticamente una solicitud de autorización excepcional por agotamiento del cupo.

Esta decisión define el resultado de cobertura. D6 precisa la aceptación necesaria para cobrar al paciente. El momento de creación del cargo y lo que sucede si no acepta o no puede responder siguen pendientes. Tampoco se decidió detener o cancelar una atención por ese resultado.

### D6. Aceptación de pago por prestación e importe

El usuario confirmó: «por prestación, mostrando el importe que pagará», al definir qué aceptación permite cobrar una prestación no cubierta.

Criterios observables:

- Antes de aceptar el pago particular, se identifica la prestación y se muestra el importe que pagará el paciente.
- La aceptación queda registrada para esa prestación y ese importe; una aceptación general al ingresar no la reemplaza.
- Aceptar el pago de una prestación no acepta automáticamente otras prestaciones del mismo caso ni importes diferentes.

Esta decisión sustituye la asunción de #16 que tomaba la aceptación una sola vez por caso. No se ha actualizado el issue en GitHub; el cambio de requisito queda documentado aquí.

La forma de registrar la aceptación, sus responsables, un eventual cambio de importe y el tratamiento de rechazo o imposibilidad de responder siguen por definir. D7 extiende expresamente la misma aceptación a los copagos. La aceptación tampoco prueba que el dinero ya se haya cobrado ni que la prestación se haya realizado.

### D7. Copago a cargo del paciente con aceptación específica

El usuario confirmó: «a cargo del paciente como copago, con la misma aceptación por prestación e importe».

Criterio observable: para una prestación de $10.000 con cobertura del 80 %, se identifica una parte de $8.000 correspondiente al financiador y un copago de $2.000 correspondiente al paciente. Se informa ese copago al paciente y se registra su aceptación para esa prestación e importe conforme a D6.

La aceptación se refiere a los $2.000 que pagará el paciente. El tratamiento de rechazo o imposibilidad de responder sigue pendiente; no se presume que rechazar el copago lo traslade automáticamente al financiador o al hospital.

### D8. Consumos externos informados por el financiador

El usuario pidió que la obra social pueda indicar, por paciente, consumos realizados en hospitales ajenos a Salud, cuya actividad no se encuentra registrada en el sistema.

Resultado requerido: el financiador puede cargar esos consumos de sus afiliados para que se consideren en el cupo compartido. Complementa D4 y conserva D5: una vez agotado el cupo computable, la siguiente prestación queda no cubierta.

Criterios observables:

- Con un límite de seis radiografías para el período, tres usos en hospitales de Salud y dos usos externos informados por el financiador para la misma cobertura, queda un uso disponible.
- Ese saldo se aplica al mismo afiliado en todos los hospitales de Salud; el consumo externo se descuenta una vez, no una vez por hospital.
- Se puede distinguir un consumo externo informado de una prestación registrada por un hospital de Salud. Informar actividad ajena a Salud para el cupo no acredita un servicio realizado por un hospital de Salud ni crea un cargo a cobrar por éste.

Cambio de alcance: #20 describe los consumos del financiador como sólo lectura. El pedido actual incorpora una acción nueva para informar actividad externa; la consulta de consumos y cargos de hospitales de Salud conserva su alcance de lectura. No se modificaron los issues de GitHub.

D9 confirma el registro con prestación, fecha y cantidad, y la carga masiva mediante Excel. No se utilizará una simple declaración de total acumulado como sustituto de esos datos.

Aspectos a resolver antes de implementar:

- Quiénes dentro del financiador pueden cargar o corregir información, sobre qué afiliados, y cómo se registra la autoría.
- Período al que pertenece el consumo frente a fecha de carga, correcciones, reintentos y prevención de duplicados con otros registros externos o internos.
- D14 define la conservación de decisiones/cargos registrados ante declaraciones tardías, la actualización del cupo para evaluaciones posteriores y la señalización de discrepancias. Queda definir su resolución administrativa y el tratamiento de prestaciones aún en curso.
- Concurrencia entre una carga externa y el uso del último cupo en un hospital.
- Qué información necesita ver el hospital para explicar el saldo sin acceder a documentación clínica externa innecesaria.

### D9. Detalle de consumo externo y carga masiva mediante Excel

El usuario confirmó «prestación, fecha y cantidad» y pidió una carga masiva mediante un Excel personalizado, para informar varias prestaciones utilizadas por varias personas en una sola operación y facilitar la puesta al día del sistema.

Criterios observables:

- Cada consumo externo identifica al afiliado y contiene prestación, fecha del consumo y cantidad. La fecha de carga es un dato distinto de la fecha del consumo.
- Una plantilla de Excel permite preparar un lote con distintos afiliados y distintas prestaciones. Un mismo afiliado puede aparecer en varias filas para informar consumos diferentes.
- Los consumos aceptados del archivo alimentan el mismo cupo compartido de D4/D8. La carga masiva conserva la separación entre consumo externo y cargos por prestaciones de hospitales de Salud.
- El resultado permite conocer qué consumos fueron registrados y cuáles requieren corrección, conforme a la importación parcial con resumen y detalle de rechazos confirmada en D10. No se considera aceptable descartar filas sin informar su resultado.

La estructura definitiva del archivo y el comportamiento de la importación siguen en diseño. No se creó una plantilla final, un endpoint ni una nueva dependencia de producción.

Decisiones y validaciones necesarias para el lote:

- D12 exige número de afiliado y documento para identificar a la persona. Precisar el identificador de la prestación y la referencia del consumo, sin depender de coincidencias aproximadas de nombres. Preservar identificadores como texto, incluidos ceros iniciales.
- D11 define que el «Excel personalizado» se adapta a las prestaciones de cada financiador. Quedan por definir columnas y ayudas antes de generar el archivo final. No se presupone aceptar cualquier Excel existente ni construir un mapeador arbitrario de columnas.
- D10 confirma el tratamiento de filas inválidas: resumen previo, importación de las válidas y detalle de las rechazadas para corregirlas. Definir los estados y la confirmación de resultados del lote.
- Reconocer reintentos, archivos repetidos o parcialmente superpuestos sin descontar dos veces el mismo consumo. La combinación afiliado/prestación/fecha/cantidad no demuestra por sí sola que dos filas representen el mismo hecho; puede haber consumos legítimos iguales.
- Distinguir importación repetida de corrección de un consumo ya informado; conservar autoría, procedencia del lote y resultado explicable.
- Validar en servidor financiador, afiliado, prestación, fecha y cantidad aunque el Excel incluya listas o restricciones. La información de organización que traiga el archivo no concede permisos.
- Definir límites de filas/tamaño y volumen habitual antes de decidir si hace falta procesamiento en segundo plano; no se agrega una cola por anticipado.
- Definir el comportamiento ante fallos de procesamiento o una respuesta perdida, incluyendo qué registros llegaron a aplicarse.

Inspección técnica: la búsqueda dirigida de dependencias y código no encontró `openpyxl`, `xlsx`, `pandas`, `calamine`, `read_excel` ni `load_workbook` como implementación de importación Excel en el backend. Las únicas coincidencias con pandas son comentarios sobre exportación CSV. `backend/requirements.txt` existe; no se cambió. La elección de librería y el contrato del archivo deben concretarse antes de proponer una dependencia.

Skill `xlsx` revisada por el nuevo alcance: su flujo está destinado a entregar un archivo de planilla. En esta etapa se documenta el contrato de importación; no se aplica todavía su flujo de generación/recálculo ni se genera un archivo con columnas aún no acordadas.

### D10. Importación parcial con resumen y detalle de rechazos

El usuario confirmó: «importar las válidas después de mostrar un resumen, y entregar el detalle de las filas rechazadas para corregirlas».

Criterios observables:

- Antes de aplicar los consumos se presenta un resumen de la validación del archivo.
- Ante 500 filas con 495 válidas y cinco inválidas, se permite importar las 495 válidas; las cinco inválidas quedan sin aplicar.
- El resultado identifica las filas rechazadas y sus motivos para que el usuario pueda corregirlas.
- Se puede comprobar qué filas se registraron efectivamente; mostrar una fila como válida en la revisión previa no equivale a informar que ya se importó.

La decisión permite rechazar filas por errores de datos sin bloquear las restantes. No define aún cómo tratar fallos técnicos a mitad de ejecución, cambios de datos entre revisión y aplicación, ni cómo reconocer filas repetidas al corregir y reenviar un archivo. Esos contratos deben resolverse para evitar duplicar consumos o informar registros que no llegaron a persistirse.

### D11. Plantilla de Excel por catálogo del financiador

El usuario aclaró que el Excel debe ser personalizado porque las obras sociales no ofrecen cobertura para las mismas prestaciones.

Resultado requerido: la plantilla de cada obra social contempla su selección del catálogo común de prestaciones confirmado en D16, manteniendo la posibilidad de informar varios afiliados y distintos consumos en un mismo archivo.

Criterios observables:

- Si el financiador A incluye consultas y radiografías, y B incluye consultas y ecografías, sus plantillas presentan las prestaciones correspondientes a cada uno.
- El catálogo utilizado para ayudar a completar el archivo corresponde al financiador para el que se prepara la carga.
- Al importar, Salud comprueba el alcance del financiador y la validez de las prestaciones; modificar las celdas o usar otra plantilla no permite atribuir consumos a una organización ajena.

Aspectos pendientes: representación exacta del catálogo en el Excel, identificación estable de cada prestación, validación por plan y fecha del consumo, y tratamiento de plantillas antiguas o prestaciones que dejaron de ofrecerse. Que una prestación figure en el catálogo del financiador no demuestra por sí solo que todos sus planes la cubran para cualquier fecha.

Recomendación de presentación del agente, aún no formato cerrado: conservar columnas de carga uniformes y personalizar el catálogo de selección y una hoja de referencia por financiador. Evita obligar a mantener un formato de importación distinto por cada obra social; el usuario podrá revisar la plantilla concreta antes de implementarla.

### D12. Número de afiliado y documento obligatorios en el Excel

El usuario confirmó «si, ambos» ante la propuesta de exigir número de afiliado y documento para identificar a cada persona del archivo, dentro de la obra social que realiza la carga.

Criterios observables:

- Cada fila de consumo externo debe incluir ambos datos, además de prestación, fecha y cantidad definidos en D9.
- Una fila sin número de afiliado o sin documento se informa como rechazada con el dato faltante; las demás filas siguen la política de importación parcial de D10.
- La validación contrasta que ambos datos correspondan a la misma persona dentro del financiador de la carga. Una discrepancia no se resuelve atribuyendo el consumo automáticamente a quien coincida con uno solo de los datos.

Los datos de identificación se preservan como texto. Esta decisión no prueba que el número de afiliado sea individual en todos los financiadores ni resuelve cómo dar de alta una afiliación que aún no exista en Salud. La identidad compartida entre hospitales, la normalización del documento y el tratamiento de coincidencias ambiguas deben concretarse en el diseño.

Datos del Excel confirmados: número de afiliado, documento, prestación, fecha del consumo y cantidad obligatorios; referencia externa del consumo opcional según D13.

### D13. Referencia externa opcional y control de duplicados

Tras consultar la complejidad de exigir una referencia única por consumo, el usuario confirmó que sea opcional, con protección de reintentos y revisión de posibles duplicados. La disponibilidad de referencias en todas las obras sociales no se presume.

Criterios observables:

- La ausencia de referencia externa no rechaza por sí sola una fila que reúne los datos obligatorios de D12.
- Si se informa la misma referencia del mismo financiador con los mismos datos, se reconoce el consumo ya registrado y no se descuenta nuevamente el cupo. Reutilizar la referencia con datos distintos debe informarse como conflicto, sin sobrescribir el consumo previo automáticamente.
- Reintentar la misma importación no vuelve a aplicar sus consumos confirmados.
- Sin referencia, las coincidencias con otros consumos se presentan como posibles duplicados para revisión. No se descartan automáticamente coincidencias de persona, prestación, fecha y cantidad, porque también pueden corresponder a usos legítimos diferentes.

Comparación utilizada durante la entrevista:

| Alternativa | Trabajo para la obra social | Consecuencia para Salud |
| --- | --- | --- |
| Referencia externa obligatoria | Si ya existe en su sistema, puede copiarla/exportarla; si no, debe crear y conservar un código por consumo. | Permite reconocer reenvíos por una identidad estable del consumo dentro del financiador. Sigue siendo necesario validar que la referencia no se reutilice con datos distintos. |
| Referencia externa opcional | Permite cargar las cinco columnas ya confirmadas; se agrega la referencia cuando está disponible. | Requiere tratar cargas con y sin referencia. Las coincidencias ambiguas sin referencia necesitan revisión humana; no hay una garantía automática de detectar todo duplicado entre archivos nuevos. |

Recomendación del agente aceptada por el usuario: referencia externa opcional para no exigir un dato que algunas obras sociales tal vez no tengan, complementada con protección de reintentos del mismo lote y revisión de posibles duplicados al informar consumos similares en otro archivo.

La alternativa opcional reduce requisitos de carga, pero agrega lógica y revisión de ambigüedades respecto de contar siempre con una referencia fiable. No se presenta como una solución sin costo ni como deduplicación infalible.

Evidencia de reutilización: `backend/apps/finanzas/dinero.py` ya contiene claves de operación y `_repetido`, que distinguen un reintento de una clave reutilizada con otra solicitud. Es un patrón existente para inspirar el control de reintentos del importador; no identifica consumos externos ni resuelve por sí solo archivos distintos o superpuestos. El mecanismo concreto de importación, las coincidencias que se señalarán y los permisos para resolverlas siguen pendientes.

### D14. Información tardía: conservar lo registrado y señalar discrepancias

El usuario confirmó: «conservar lo registrado, actualizar el cupo para las siguientes evaluaciones y señalar la discrepancia».

Escenario que se sometió a decisión: el hospital realiza una prestación que Salud indica como cubierta; después, el financiador informa consumos externos anteriores del mismo período que muestran que el cupo ya estaba agotado.

Criterios observables:

- La carga tardía conserva la decisión de cobertura, el cargo y la aceptación registrados para la prestación ya realizada; no los recalcula ni reasigna automáticamente.
- El consumo externo se incorpora al período que corresponde a su fecha y actualiza el cupo que se utiliza en las siguientes evaluaciones de ese período.
- Se señala la discrepancia para revisión administrativa, permitiendo explicar la decisión original y la información incorporada después.
- Si los usos conocidos pasan a superar el tope, se conserva esa información y se señala el exceso; no se descartan consumos para que el saldo aparente coincidir con el límite.
- Un consumo de un período anterior no se descuenta del período actual simplemente porque se haya cargado hoy. D15 define los períodos mensuales y anuales como calendario.

La decisión impide trasladar automáticamente al paciente una deuda que no aceptó. No establece quién asume finalmente una diferencia discutida entre hospital y financiador ni autoriza ajustes automáticos: responsables, acciones y trazabilidad de la revisión siguen por definir. También queda por resolver la información tardía que llega mientras una prestación aún está en preparación o tiene cupo reservado, ya que el escenario acordado se refiere a actividad realizada y registrada.

### D15. Cupos por meses y años calendario

El usuario eligió «meses y años calendario» frente a la alternativa de períodos móviles.

Criterios observables:

- Un tope mensual cuenta los consumos del mes calendario de la prestación; se renueva al comenzar el mes siguiente.
- Un tope anual cuenta los consumos del año calendario de la prestación; se renueva el 1 de enero.
- Si un afiliado utilizó sus seis radiografías anuales en diciembre, comienza enero con el cupo del año nuevo disponible, sujeto a las demás condiciones de cobertura y sus consumos de ese nuevo año.
- Un consumo externo de diciembre informado en enero se atribuye a diciembre y a su año correspondiente. La fecha de importación no lo convierte en un consumo del nuevo período.

Se excluyen los períodos móviles del alcance inicial acordado. En el diseño se precisará el corte de fecha de los hechos asistenciales y la zona horaria aplicable para que un mismo uso no caiga en períodos diferentes según quién lo consulte. Esta decisión no resuelve cambios de plan, correcciones de cupos ni límites combinados simultáneos.

### D16. Catálogo común de prestaciones administrado por plataforma

El usuario eligió «catalogo comun» frente a la alternativa de nomencladores propios de cada financiador con equivalencias entre organizaciones. La opción presentada incluye administración del catálogo por plataforma, selección de prestaciones por cada financiador y vinculación de prestaciones locales de los hospitales.

Criterios observables:

- Plataforma mantiene las prestaciones de referencia compartidas de Salud.
- Cada financiador selecciona de ese catálogo las prestaciones que incluye en su oferta; sus planes configuran la cobertura correspondiente.
- Cada hospital puede vincular sus prestaciones locales con la referencia común. Dos prestaciones locales equivalentes consumen el cupo de la misma prestación de referencia para el afiliado.
- La plantilla personalizada del financiador de D11 utiliza su selección del catálogo común.
- Compartir la referencia de una prestación no unifica su precio: se conservan los aranceles generales de cada hospital y las excepciones acordadas de D1/D2.

Comparación expuesta al usuario: el catálogo común facilita la configuración y el conteo compartido, pero requiere mantenerlo y validar las vinculaciones locales. Los nomencladores propios de cada financiador exigirían mantener más equivalencias entre organizaciones. Es la recomendación del agente elegida por el usuario; no se atribuyen otras razones personales a la decisión.

Evidencia actual: `finanzas.Prestacion` conserva código y nombre por institución, con unicidad sólo para institución/código. #16 presupone un código externo que ese modelo todavía no representa. El diseño debe concretar la referencia común, preservar los códigos locales existentes y definir qué ocurre con prestaciones sin vincular; no se decidió deducir equivalencias por nombres parecidos.

Quedan pendientes el conjunto inicial del catálogo, permisos detallados, altas/correcciones/versiones, granularidad de prestaciones y categorías, y la representación de sus identificadores en el Excel. La elección funcional del catálogo común no aprueba aún un esquema de datos ni una migración.

### D17. Padrón propio del financiador con carga masiva y sencilla

El usuario confirmó «si, masivamente y de manera simple» ante la posibilidad de que la obra social cargue y mantenga su padrón de afiliados antes de que esas personas sean atendidas en un hospital de Salud.

Criterios observables:

- El financiador puede registrar y mantener afiliaciones de personas que todavía no tienen una atención en un hospital de Salud.
- Puede incorporar múltiples afiliados en una sola carga, sin dar de alta uno por uno para después informar sus consumos externos.
- Cuando una persona se atiende en un hospital, se puede vincular el paciente institucional con la afiliación existente del financiador, conforme a las reglas de identificación que se concreten.
- La operación masiva identifica el resultado de las filas y los problemas a corregir; el recorrido debe permitir que un operador prepare y revise el lote sin intervención técnica.

Recomendación de recorrido del agente para reutilizar lo ya acordado: plantilla de Excel para el padrón, resumen previo de altas/actualizaciones/errores y detalle de filas a corregir, con el mismo patrón visible de las cargas de consumos. Las columnas específicas del padrón y el tratamiento de cambios siguen por cerrar; no se propone un sistema nuevo de importación configurable para cualquier formato.

Cambio respecto de #14: ese análisis parte de afiliaciones cargadas por el administrativo hospitalario. El padrón propio habilita que el financiador prepare la información antes de cualquier atención en Salud. Es información administrativa de afiliación; no crea por sí sola casos, atenciones ni historias clínicas hospitalarias.

Decisiones y riesgos pendientes:

- D18 resuelve que los archivos aportan altas/actualizaciones de las filas presentes y no realizan bajas.
- Acordar columnas mínimas y validación de plan/vigencias, además de la identificación por número de afiliado y documento. Los planes del archivo deben corresponder al financiador de la carga.
- Definir vigencia de cambios, correcciones y reactivaciones, preservando la posibilidad de explicar la afiliación y cobertura usadas en una atención previa. D18 excluye las bajas del importador; un eventual circuito separado de bajas y el vencimiento de afiliaciones siguen sin definirse.
- Resolver discrepancias entre lo declarado por hospital y financiador, coincidencias ambiguas, cambios de documento/número de afiliado y permisos para corregirlos.
- La capacidad de cargar padrón no decide que una fila de consumo pueda dar de alta automáticamente una afiliación inexistente; falta fijar ese comportamiento y los datos que requiere.
- Determinar volumen habitual y límites seguros; no se eligió aún procesamiento asíncrono ni una nueva infraestructura.

### D18. Importación incremental del padrón sin bajas

El usuario eligió «La recomendada sin dar bajas» ante las alternativas de agregar/actualizar las personas incluidas o reemplazar el padrón completo.

La carga agrega o actualiza las afiliaciones de las filas válidas incluidas. No da de baja a quienes no aparecen ni incorpora una operación de baja en la planilla. Esta precisión limita la recomendación anterior del agente, que también proponía bajas expresamente indicadas.

Criterios observables:

- Si el padrón tiene 1.000 afiliados y el archivo contiene 20 existentes y 5 nuevos válidos, se actualizan los 20 y se agregan los 5; los otros 980 permanecen sin cambios.
- La omisión de una persona no elimina su afiliación ni modifica su vigencia.
- Una carga no se interpreta como reemplazo completo del padrón ni ejecuta bajas.
- El resumen previo muestra altas, actualizaciones y errores para revisar, conforme al recorrido propuesto en D17.

Esta decisión corresponde al comportamiento de la importación. No establece afiliaciones perpetuas ni aprueba un circuito alternativo de bajas: los vencimientos y la gestión separada de una afiliación que deja de corresponder siguen pendientes. D19 define la conservación de consumos al cambiar de plan; falta concretar desde cuándo rigen esos cambios.

### D19. Cambio de plan con conservación de consumos dentro del financiador

El usuario aceptó la recomendación de conservar los consumos acumulados al cambiar de plan dentro de la misma obra social y agregó: «eso me hace pensar qué pasa si alguien se cambia de obra social».

El cambio de plan no reinicia el contador. Para las siguientes evaluaciones se aplica el límite del nuevo plan y se descuentan los usos computables de la misma prestación acumulados en el período dentro de ese financiador, incluidos los consumos externos informados.

Criterios observables:

- Un afiliado que utilizó cuatro radiografías en el año y pasa a un plan con límite anual de diez dispone de seis usos adicionales.
- Los consumos del plan anterior permanecen computables aunque se hayan realizado en otro hospital de Salud o informado como externos.
- Actualizar el plan mediante una carga del padrón no ofrece un cupo completo ignorando los usos previos del período.

Comparación con #16: su RN5 propone contar cargos de la misma afiliación y prestación. D19 exige continuidad de consumos entre planes, aunque el diseño represente sus vigencias con registros distintos. No se ha aprobado un esquema técnico para esa continuidad.

La decisión alcanza al cambio de plan dentro del mismo financiador. D20 resuelve el cambio a otra obra social y D21 conserva la afiliación elegida en los casos en curso. El acumulado se conserva cuando corresponda evaluar el nuevo plan; actualizar el padrón no sustituye automáticamente la afiliación fijada en un caso. Siguen pendientes la fecha de vigencia del cambio, los cambios retroactivos y la transición entre planes con distinta periodicidad o agrupación de prestaciones.

### D20. Cupos independientes entre financiadores y continuidad al regresar

El usuario respondió «Confirmo» a la propuesta de mantener cupos independientes entre obras sociales, conservando lo consumido si vuelve a una anterior durante el mismo período.

Criterios observables:

- Una persona que consumió cuatro de seis radiografías anuales con A y pasa a B, cuyo plan permite diez, dispone de diez con B desde el inicio de su cobertura si no tiene consumos computables previos en B durante ese período.
- Si regresa a A dentro del mismo año y conserva un límite de seis, sus cuatro usos anteriores siguen contando y dispone de dos. Crear otra afiliación o cambiar su número no debe reiniciar ese acumulado.
- Los consumos computables internos y externos permanecen atribuidos al financiador correspondiente; no se trasladan automáticamente al nuevo.
- Los cargos anteriores mantienen su responsable original. El alta en B no concede a sus usuarios acceso automático a consumos o información de A.

Se confirma una regla funcional de Salud, no una afirmación sobre obligaciones legales o condiciones de contratos externos. #14 contempla afiliaciones vigentes e históricas, incluso varias simultáneas; #16 propone contar usos por afiliación, pero no resuelve expresamente un traspaso de cupos entre financiadores.

Esta decisión no da de baja la afiliación anterior por importación ni autoriza a B a modificar el padrón de A. D21 define la continuidad de los casos en curso con la afiliación fijada al ingreso. Siguen pendientes las fechas de inicio/finalización, quién las acredita, la elección entre afiliaciones simultáneas y el vínculo de identidad que permite reconocer el regreso sin exponer datos entre organizaciones.

### D21. Conservar la afiliación del ingreso durante el caso, conforme a #16

Ante la alternativa de cambiar automáticamente de financiador durante un caso o conservar la afiliación inicial, el usuario indicó: «implementa la que mas siga con la regla del issue #16».

Se adopta RN1 y el flujo de afiliación vencida de #16, contrastados nuevamente en GitHub en esta respuesta: la afiliación se fija en la admisión y el caso la conserva, aunque cambie o venza después. Una corrección expresa deja un evento y no modifica cargos previos. Se descarta la recomendación anterior del agente de cambiar automáticamente la afiliación del caso según la fecha de cada prestación.

Criterios observables para la implementación:

- Un caso iniciado con A el día 10 continúa evaluándose con la afiliación a A si la persona pasa a B el día 15; no cambia automáticamente a B.
- Si la afiliación fijada vence, el legajo la muestra vencida y el caso conserva esa afiliación.
- Una corrección explícita de la afiliación queda registrada con evento y se usa para las evaluaciones posteriores; los cargos previos conservan su responsable e importe.
- Una actualización de padrón no sustituye de manera implícita la afiliación elegida para el caso ni pierde la información necesaria para identificar esa elección.
- Conservar la afiliación no congela las reglas ni concede cobertura incondicional: RN3 de #16 evalúa las reglas vigentes a la fecha del hecho; los cupos siguen acumulándose conforme a D19/D20 y sigue siendo aplicable el requisito de convenio de RN8.

Alcance y dependencias:

- D19 conserva el acumulado cuando corresponda evaluar un nuevo plan. D21 determina que un cambio en el padrón no aplica ese nuevo plan automáticamente a los casos que conservan otra afiliación.
- La elección sigue la regla del issue aun cuando la afiliación figure vencida. Su aislamiento debe contemplar la consulta administrativa de casos en curso y cargos históricos sin conceder acceso clínico; #14/#20 todavía requieren concretar ese acceso tras el vencimiento.
- El código consultado conserva `Ciudadano.obra_social` como texto y no tiene una afiliación estructurada vinculada a `Caso`. La regla queda especificada para su implementación junto con esa base, sus permisos y el historial; esta actualización documental no implementa el comportamiento en la aplicación.
- No se aprueba por esta elección un esquema de datos, una migración ni permisos nuevos. Debe preservarse la identidad de la afiliación elegida frente a actualizaciones del padrón, sin deducirla retrospectivamente del texto actual del paciente.

### D22. Importe sin aceptación: desglose claro y rechazo del hospital

El usuario respondió «si, pero dejando esto bien claro y pudiendo rechazarse» a la propuesta de conservar la parte cubierta por el financiador y atribuir al hospital el importe sin aceptación del paciente, cuando la prestación se realiza.

El usuario aclaró «opcion 2»: el hospital debe poder rechazar hacerse cargo de ese importe. Quedan identificados el actor y el objeto del rechazo. El flujo completo de resolución del saldo y el momento en que se decide todavía no están cerrados; no se presume una asunción automática e irrevocable por el hospital.

La presentación debe distinguir el importe cubierto por el financiador, el copago y la parte que correspondería al hospital ante la falta de aceptación. Debe quedar claro que no se genera deuda al paciente por un importe que no aceptó.

Criterios observables confirmados:

- Se distingue el importe total, la parte cubierta por el financiador, el copago y el importe que asumiría el hospital ante la falta de aceptación.
- El hospital dispone de una acción para rechazar asumir ese importe.
- El rechazo hospitalario no cuenta como aceptación del paciente ni aumenta automáticamente la parte cubierta por el financiador.
- La acción se refiere a la responsabilidad económica del hospital; no equivale a rechazar realizar la prestación.

Cambio respecto de #16: el flujo sin convenio atribuye al hospital el importe sin aceptación. D22 agrega una decisión hospitalaria de rechazo y exige definir qué sucede con el saldo resultante. No se puede resolver sólo con el cambio del responsable a «institución» propuesto por el issue.

El momento del rechazo también importa: la pregunta original se refería a una prestación realizada. D23 define el saldo pendiente en ese escenario y D24 identifica al personal autorizado y el registro de su decisión; quedan por concretar las opciones para resolverlo. No se ha autorizado cancelar atenciones, borrar prestaciones realizadas, trasladar unilateralmente el saldo al financiador ni generar una deuda al paciente por un rechazo hospitalario. La continuidad asistencial y la diferencia entre rechazo e imposibilidad de responder siguen por concretar.

### D23. Saldo rechazado por el hospital pendiente de resolución administrativa

El usuario confirmó que, si la prestación ya se realizó y el hospital rechaza asumir el importe que el paciente no aceptó pagar, ese saldo queda como «Pendiente de resolución administrativa».

Criterios observables:

- Se conserva la parte cubierta por el financiador según la evaluación correspondiente.
- El importe rechazado permanece visible e identificado para su resolución administrativa; no desaparece por el rechazo.
- No se genera automáticamente deuda al paciente ni se traslada ese importe al financiador.
- Para una prestación realizada de $10.000, con $8.000 cubiertos por el financiador y $2.000 de copago no aceptado que el hospital rechaza asumir, se muestran $8.000 correspondientes al financiador y $2.000 pendientes de resolución administrativa.
- El saldo pendiente no se presenta como dinero cobrado ni como deuda ya atribuida a un tercero.

Límites y trabajo pendiente:

- Es un estado funcional para explicar el importe aún sin resolución; no constituye por sí solo un movimiento de dinero, una condonación ni una asunción definitiva por el hospital.
- D24 define quién puede aceptar o rechazar la asunción y gestionar los pendientes, con registro de motivo, usuario y fecha. D25 define las formas de resolución admitidas. Falta concretar el respaldo documental y los casos de resolución parcial; no se autoriza a asignar arbitrariamente el saldo a un paciente o financiador.
- El diseño debe distinguir este saldo de los pagos/cobros pendientes de aprobación que ya existen en Finanzas. Debe conservar la prestación y su distribución de importes, y evitar duplicar cargos o perder trazabilidad al resolverlo.
- No se ha implementado todavía el estado ni elegido su representación en modelos, API, permisos o reportes.

### D24. Decisiones a cargo de Finanzas con permiso explícito y registro

El usuario confirmó: «personal de Finanzas designado por cada hospital, con permiso explícito y registro de motivo, usuario y fecha».

Criterios observables:

- Aceptar o rechazar que el hospital asuma un importe y gestionar los pendientes corresponde al personal de Finanzas que esa institución designe y autorice expresamente.
- Ser administrativo, pertenecer al hospital o poder consultar información financiera no concede por sí solo esas facultades.
- Cada decisión registra el motivo, el usuario que decidió y la fecha; esos datos acompañan la decisión y no se omiten del registro.
- La autorización se aplica dentro del hospital y del alcance permitido; una concesión de un hospital no habilita a decidir sobre saldos de otro.

Evidencia para reutilizar: `finanzas.ConcesionFinanciera` ya permite otorgar acciones financieras a membresías institucionales activas, y `finanzas/permisos.py` acota su alcance por institución y área. Se propone utilizar ese mecanismo existente. La designación funcional de personal de Finanzas no exige crear un nuevo rol general de usuario.

La acción exacta, su relación con los permisos financieros actuales y la forma de guardar las decisiones se concretarán en el diseño técnico. Esta decisión no concede permisos a usuarios reales; D25 define las resoluciones funcionales acordadas para los saldos pendientes.

### D25. Cierre por asunción hospitalaria o aceptación documentada del pago

El usuario confirmó las dos formas de resolución propuestas: el hospital acepta asumir el importe o el paciente/financiador acepta expresamente pagarlo con respaldo documentado para esa prestación e importe.

Criterios observables:

- Finanzas autorizado conforme a D24 puede cerrar la revisión registrando que el hospital acepta asumir el saldo, con motivo, usuario y fecha.
- También puede registrar la aceptación expresa de pago del paciente o financiador, respaldada documentalmente y referida a la prestación e importe. La facultad de registrar la resolución no reemplaza esa aceptación.
- Si no existe ninguna de esas aceptaciones, el saldo permanece pendiente de resolución administrativa.
- Se conservan la decisión inicial, su historial y los cargos previos; una aceptación posterior no los sobrescribe.
- Cerrar la revisión determina el tratamiento del importe. Los pagos y cobros se registran por separado cuando ocurren, sin considerar cobrado un importe por su sola aceptación.

Quedan por concretar el tipo de respaldo admitido, su conservación y acceso, la posible resolución parcial y el vínculo entre resolución y cargo para impedir una doble atribución. El diseño debe respetar D6/D7 para la aceptación del paciente y evitar que una aceptación documental del financiador amplíe por sí sola el acceso a datos de otras organizaciones. No se ha implementado este circuito ni se presupone una integración con sistemas externos.

### D26. Reserva de cupo al confirmar la prestación

El usuario confirmó reservar el cupo al confirmar que se realizará la prestación, convertir la reserva en consumo al registrar su realización y liberarla si se cancela. La consulta de cobertura sólo muestra disponibilidad.

Criterios observables:

- Consultar la cobertura no reduce el cupo ni crea una reserva.
- Al confirmar una prestación para su realización, se reserva el uso correspondiente y se reduce la disponibilidad para otras confirmaciones.
- Si sólo queda un uso y dos hospitales intentan confirmarlo al mismo tiempo, sólo una confirmación obtiene la reserva. No se promete ese mismo uso a ambos hospitales.
- Registrar la realización transforma la reserva en consumo sin descontar el uso dos veces.
- Cancelar la prestación aún no realizada libera su reserva para nuevas evaluaciones.

Evidencia y dependencias:

- RN5 de #16 cuenta cargos no anulados de la misma afiliación y prestación; no define una reserva entre consulta y realización. D26 incorpora ese compromiso previo para el cupo compartido definido en D4.
- `finanzas/cobros.py` ya bloquea el hecho y su captura de cobro. Ese bloqueo no coordina por sí solo el cupo de un afiliado entre hospitales: el diseño debe proteger el recurso compartido, también frente a reintentos e importaciones externas.
- La reserva corresponde al cupo de cobertura. No se ha decidido que reservar un horario en Agenda genere por sí solo esta reserva.
- Quedan pendientes las reservas abandonadas, la identificación exacta del momento de confirmación, los cambios de período/reglas/arancel, los consumos externos tardíos o simultáneos y la interacción con el importe aceptado por el paciente.
- Se debe precisar qué muestra una segunda evaluación cuando el último uso está reservado, y el tratamiento de prestaciones ya realizadas que luego se corrigen o anulan financieramente. La liberación por cancelación antes de realizar no decide esos casos.
- No se ha implementado la reserva ni aprobado su esquema de datos, vencimiento o mecanismo de coordinación.

### D27. Revisión de reservas antiguas sin vencimiento automático

El usuario eligió «mostrar las reservas antiguas y liberarlas tras confirmar que la prestación no se realizó».

Criterios observables:

- Las reservas abiertas antiguas se muestran para revisión del hospital.
- La antigüedad por sí sola no libera el cupo.
- Se permite liberar la reserva tras confirmar que la prestación no se realizó; una demora en registrar una prestación realizada no basta para liberarla.
- La liberación devuelve disponibilidad sin crear un consumo ni un cargo.

Se acepta el trabajo de revisión como consecuencia de esta elección. Falta definir el criterio de antigüedad, el personal autorizado para confirmar la no realización y cómo resolver una declaración errónea cuando después llega evidencia de realización. La confirmación de no realización debe volver a comprobarse frente al estado vigente al liberar, para evitar carreras con el registro de realización. No se ha implementado la revisión ni modificado un proceso periódico.

## Decisiones que la entrevista debe resolver

Se tratarán de a una, según sus dependencias. La lista siguiente registra cuestiones abiertas, no respuestas aprobadas.

1. **Arancel y convenio:** D1/D2 resuelven quién carga la excepción y el uso del arancel general por defecto. Queda definir qué ocurre si falta también el general, las vigencias, granularidad de excepciones y cuándo puede utilizarse el precio para atribuir un cargo; #14 deja abierta la definición del alta y aceptación del convenio como relación entre organizaciones.
2. **Reglas del plan:** D3 confirma porcentaje de cobertura y tope opcional de cantidad combinables; D4 confirma cupo compartido entre hospitales; D5 determina «no cubierta» al agotarlo; D8/D9 incluyen consumos externos con prestación, fecha y cantidad, y carga masiva por Excel; D10/D11 confirman importación parcial y catálogo personalizado por financiador; D13 define referencia opcional y controles de duplicados; D14 conserva lo registrado ante información tardía; D15 define meses y años calendario; D16 establece el catálogo común; D19 conserva consumos al cambiar de plan dentro del financiador; D20 separa cupos entre financiadores y conserva los usos al regresar; D26 reserva al confirmar, consume al registrar la realización y libera al cancelar antes de realizar. Precisar identidad compartida del afiliado, vinculaciones de prestaciones, vigencias de cambios de plan y financiador, reservas abandonadas y cambios de período, correcciones de prestaciones realizadas, mecanismos de reintento y resolución administrativa de discrepancias.
3. **Publicación y vigencias:** autoridad para activar/cambiar reglas, excepciones por convenio y explicación del histórico. #20 menciona reglas por convenio, pero el orden de especificidad de #16 no las sitúa explícitamente.
4. **Afiliación y elegibilidad:** D12 exige número de afiliado y documento en el Excel; D17 confirma padrón propio del financiador con carga masiva y sencilla; D18 limita la importación a altas/actualizaciones, sin bajas ni cambios por omisión; D21 conserva la afiliación del ingreso en casos en curso y permite corrección registrada sin modificar cargos previos. Precisar verificación y conflictos entre fuentes, columnas de padrón, vigencias y vencimientos, eventual gestión separada de bajas, múltiples afiliaciones y continuidad entre instituciones. Una afiliación copiada por derivación no equivale a validación del financiador.
5. **Responsabilidad del paciente:** D6 exige aceptación por prestación e importe y D7 la aplica al copago a cargo del paciente. D22 exige desglose claro y permite que el hospital rechace asumir el importe no aceptado; D23 lo conserva pendiente de resolución administrativa si la prestación ya se realizó; D24 asigna las decisiones a Finanzas designado y autorizado por el hospital, con motivo, usuario y fecha; D25 permite cerrar por asunción hospitalaria o aceptación documentada del pago por paciente/financiador. Precisar el respaldo admitido, resoluciones parciales, el momento de la decisión, quién registra la aceptación del paciente, cambios de importe y el flujo ante imposibilidad de responder.
6. **Cobertura desconocida:** distinguir una denegación expresa de una regla ausente, información incompleta o evaluación fallida. #16 propone «sin regla = no cubierta»; evaluar esa consecuencia antes de implementarla.
7. **Autorizaciones y continuidad:** decidir el primer alcance y aclarar «guardia» frente a prioridad `URGENTE`. #17 habla de toda guardia; #18 describe una guarda por prioridad. No asumir que son conjuntos equivalentes.
8. **Deuda y consumos:** momento y evidencia que habilitan el cargo al financiador, cantidades, reparto de importes, revisión, ajustes posteriores, rechazo y registro de cobro. #19/#20 excluyen liquidación, conciliación y facturación del portal descrito.
9. **Acceso a históricos:** #14/#20 condicionan acceso a afiliación/convenio vigentes; #20 exceptúa solicitudes pendientes de afiliación vencida. Precisar consulta de cargos pendientes después del vencimiento o cierre.
10. **Operación y aceptación:** roles, mínima información visible, prueba de aislamiento, volúmenes esperados, primer escenario demostrable y necesidad real de integración con sistemas externos.

## Estado de la entrevista

- El usuario pidió verificar primero las respuestas que ya estén descritas en issues. Se aplica: consultar evidencia antes de trasladarle una pregunta de hecho.
- Su modelo inicial coincide con #19/#20 y #14/#16: parametría del financiador y datos suficientes para que el hospital determine el importe a cobrarle.
- D1/D2 confirman que el hospital carga los aranceles: el general se aplica por defecto y un acuerdo específico funciona como excepción.
- D3 confirma que una misma regla puede combinar porcentaje y tope opcional de cantidad.
- D4 confirma el cupo compartido para el mismo afiliado entre hospitales de Salud. Sus implicancias de identidad, concurrencia y acceso mínimo se registran como cuestiones de diseño, no como una arquitectura ya aprobada.
- D5 confirma «no cubierta» cuando se agota el cupo. La responsabilidad del paciente y la continuidad asistencial se mantienen como decisiones separadas.
- D6 confirma aceptación por prestación con el importe a pagar informado, en reemplazo de la aceptación general por caso de #16.
- D7 confirma copago a cargo del paciente con la misma aceptación por prestación e importe.
- D8 incorpora consumos externos informados por el financiador para sus afiliados y computables en el cupo compartido. Se actualizó el alcance respecto de la consulta de consumos de sólo lectura de #20.
- D9 confirma prestación, fecha y cantidad, y agrega la carga masiva por Excel de consumos de varias personas y prestaciones. D12 completa la identificación del afiliado. Identificadores de prestación/consumo, permisos, reintentos y volumen siguen por concretar.
- D10 confirma resumen previo, importación de filas válidas y detalle de rechazadas para corregirlas.
- D11 confirma la personalización de la plantilla según el catálogo de prestaciones de cada financiador. La interfaz concreta de la planilla sigue en diseño.
- D12 confirma número de afiliado y documento obligatorios por fila, dentro del financiador de la carga.
- D13 confirma referencia externa opcional, protección de reintentos y revisión de posibles duplicados. Se registraron los costos y límites de esa elección; no demuestra detección automática de todos los duplicados entre archivos.
- D14 confirma que las cargas tardías conservan lo registrado, actualizan el cupo para las siguientes evaluaciones y señalan discrepancias para revisión.
- D15 confirma meses y años calendario, con renovación mensual o el 1 de enero.
- D16 confirma catálogo común administrado por plataforma, selección por financiador y vinculación de prestaciones hospitalarias.
- D17 confirma padrón propio del financiador, con carga masiva y sencilla, antes de la primera atención en Salud. Se propone reutilizar el recorrido de plantilla Excel, resumen y errores ya acordado para consumos.
- D18 confirma archivos incrementales que agregan/actualizan las filas incluidas, sin realizar bajas. Se corrigió la recomendación previa para excluir también las bajas expresas del importador.
- D19 confirma la conservación del consumo acumulado del período al cambiar de plan dentro del mismo financiador. Ejemplo: cuatro radiografías utilizadas y un nuevo plan con límite anual de diez dejan seis disponibles.
- D20 confirma cupos independientes entre financiadores y conservación del consumo si la persona regresa a uno anterior durante el mismo período. Los cargos previos conservan su responsable y el nuevo financiador no obtiene acceso automático a datos del anterior.
- D21 adopta la regla de #16: el caso conserva la afiliación del ingreso incluso si cambia o vence; las correcciones dejan evento y no modifican cargos previos. El usuario eligió seguir el issue frente a la recomendación anterior del agente.
- D22 confirma desglose visible y posibilidad de que el hospital rechace asumir el importe no aceptado por el paciente. El usuario eligió expresamente la opción 2; esa decisión no equivale a cancelar una prestación.
- D23 confirma que el importe rechazado por el hospital, si la prestación ya se realizó, queda «Pendiente de resolución administrativa», visible y sin traslado automático al paciente o financiador. D25 define sus opciones de resolución; su representación técnica sigue pendiente.
- D24 confirma que decide personal de Finanzas designado por cada hospital, con permiso explícito y registro de motivo, usuario y fecha. Se identificó el mecanismo de concesiones financieras existente para reutilizar en el diseño.
- D25 confirma las dos formas de cierre: el hospital asume el importe o existe aceptación expresa y documentada de pago del paciente/financiador para esa prestación e importe. Sin aceptación permanece pendiente; se conserva el historial y se separa el cobro efectivo.
- D26 confirma reserva al confirmar que se realizará la prestación, conversión a consumo al registrar su realización y liberación al cancelarla. Consultar cobertura no reserva y dos hospitales no pueden obtener simultáneamente el último uso.
- D27 confirma mostrar las reservas antiguas y liberarlas tras confirmar que la prestación no se realizó, sin vencimiento automático. Faltan el umbral de antigüedad y el personal autorizado; el SLA de autorizaciones de #18 no establece un plazo para estas reservas.
- El usuario cambió el modo de trabajo: continuar automáticamente, acumular las preguntas para su regreso y detenerse únicamente cuando no sea posible seguir sin respuestas. Las recomendaciones posteriores se documentan como propuestas, sin convertir la ausencia de respuesta en aceptación.
- La entrevista en vivo se reemplaza temporalmente por investigación, diseño y preparación de material revisable. Las decisiones D1–D27 conservan prioridad sobre propuestas anteriores de los issues.
- No se aprobó aún un esquema de datos, una migración, un mecanismo de publicación ni el alcance completo de autorizaciones.
- El glosario se inicia en [CONTEXT.md](../../CONTEXT.md). No se redactan ADR con razones atribuidas al usuario antes de discutir las alternativas y consecuencias.

## Validación de esta etapa

Consulta de GitHub en lectura, inspección dirigida del código y documentación, y comprobación de los archivos documentales agregados. En la continuación autónoma se renovó el relevamiento de 39 issues, se preparó el plan por lotes, se ejecutó un simulador de 16 pasos en memoria y se generaron tres planillas de muestra con datos ficticios; los resultados y límites se detallan en la validación vinculada arriba. No se ejecutaron tests del backend, build, migraciones, servicios ni operaciones sobre datos reales. No se actualizaron issues ni estados del proyecto ni se integró comportamiento productivo.

Skill: `grill-with-docs`, mediante `grilling` y `domain-modeling`. Se usa para recuperar hechos, resolver decisiones una a una y registrar lenguaje/acuerdos antes de implementar.

En la continuación autónoma también se aplicaron `brainstorming` para comparar arquitectura y preparar el diseño, `prototype` para el simulador descartable de estados y `xlsx` para las planillas revisables. La instrucción del usuario de acumular preguntas reemplaza las pausas de entrevista de esas skills; no representa respuestas implícitas a las preguntas acumuladas.
