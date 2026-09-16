# Cauce

Lenguaje del sistema para los procesos asistenciales y su gestión administrativa.

## Finanzas y cobertura

**Financiador**:
Organización, como una obra social, mutual o prepaga, que asume el pago de prestaciones según las condiciones de cobertura aplicables. Sus usuarios son las personas que operan en su nombre.

**Afiliación**:
Vínculo administrativo de una persona con un financiador que identifica sus condiciones de cobertura.

**Afiliación del caso**:
Afiliación elegida al ingresar a un caso asistencial. Se conserva durante ese caso aunque luego cambie o venza; una corrección expresa queda registrada y no modifica cargos anteriores.

**Padrón de afiliados del financiador**:
Conjunto de afiliaciones administrado por el financiador. Incluye personas que todavía no fueron atendidas en un hospital de Cauce.

**Carga incremental del padrón**:
Incorporación o actualización de las afiliaciones incluidas en una carga. No realiza bajas y conserva las afiliaciones omitidas.

**Plan**:
Conjunto identificado de condiciones de cobertura ofrecido por un financiador.

**Cobertura de salud**:
Condiciones que determinan qué prestaciones financia un plan o financiador y con qué límites de cantidad o participación en el importe.
_Evitar_: Cobertura de actividad, que en el reparto de costos expresa otro concepto.

**Porcentaje de cobertura**:
Porción del arancel aplicable que cubre el financiador según la regla del plan.

**Tope de cantidad**:
Número máximo de prestaciones cubiertas bajo una regla durante el período definido. Es opcional y puede combinarse con un porcentaje de cobertura.

**Período de cobertura**:
Mes o año calendario en el que se cuentan los usos sujetos a un tope. El cupo mensual se renueva al comenzar cada mes y el anual el 1 de enero.

**Cupo disponible**:
Cantidad de prestaciones cubiertas que le quedan al afiliado bajo un tope, considerando usos en Cauce, consumos externos y reservas activas. Se comparte entre hospitales y es independiente por financiador: cambiar de hospital o plan conserva los consumos del período, y regresar a un financiador conserva su acumulado previo.

**Reserva de cupo de cobertura**:
Uso del cupo comprometido al confirmar que se realizará una prestación, que reduce la disponibilidad para otras confirmaciones. Se convierte en consumo al registrarse la realización y se libera si se cancela; consultar la cobertura no constituye una reserva.

**Reserva antigua**:
Reserva de cobertura aún abierta que requiere revisión del hospital. Se libera tras confirmar que la prestación no se realizó; su antigüedad por sí sola no produce el vencimiento.

**Consumo externo informado**:
Uso de cobertura de un afiliado en una institución ajena a Cauce, declarado por el financiador con prestación, fecha y cantidad para computarlo en el cupo correspondiente.

**Identificación del afiliado**:
Combinación del número de afiliado y el documento de la persona dentro de un financiador. Permite contrastar a quién corresponde un consumo informado.

**Lote de consumos externos**:
Conjunto de consumos externos presentado por un financiador en una misma carga. Puede incluir varias prestaciones y varios afiliados.

**Referencia externa del consumo**:
Identificador de origen que permite reconocer un consumo del financiador cuando se informa nuevamente. Es un dato opcional.

**Posible duplicado**:
Consumo informado que coincide con otro en datos relevantes y requiere revisión para distinguir un reenvío de un uso diferente.

**Discrepancia de cobertura por información tardía**:
Situación en que un consumo informado tarde muestra que una prestación se había registrado como cubierta cuando el cupo ya estaba agotado. Conserva la decisión original y requiere revisión.

**Catálogo común de prestaciones**:
Conjunto de prestaciones de referencia de Cauce, administrado por plataforma. Permite reconocer una misma prestación entre hospitales y financiadores.

**Catálogo de prestaciones del financiador**:
Selección del catálogo común que forma parte de la oferta de cobertura de un financiador. Sus planes pueden establecer condiciones de cobertura diferentes para esas prestaciones.

**Prestación no cubierta**:
Prestación para la que la cobertura evaluada no asigna un importe al financiador. El agotamiento del cupo es uno de sus motivos.

**Prestación**:
Servicio asistencial identificable, como una consulta o una radiografía, al que pueden aplicarse condiciones de cobertura y un arancel.

**Costo interno**:
Valor de los recursos utilizados para prestar la atención.
_Evitar_: Arancel, cargo, cobro.

**Arancel**:
Precio aplicable a una prestación. Es distinto de lo que le cuesta a la institución realizarla.

**Arancel general del hospital**:
Precio definido por el hospital para una prestación, aplicable por defecto a los financiadores.

**Arancel acordado**:
Precio de una prestación convenido entre un hospital y un financiador como excepción al arancel general del hospital.

**Aceptación de pago particular**:
Conformidad del paciente para pagar una prestación identificada, tras informarle el importe a su cargo. Se refiere a esa prestación y a ese importe.

**Copago**:
Parte del arancel a cargo del paciente en una prestación con cobertura parcial del financiador. Su pago requiere la aceptación de esa prestación y del importe informado.

**Rechazo de asumir un importe**:
Decisión del hospital de no hacerse cargo de la parte del arancel que el paciente no aceptó pagar. No constituye una aceptación del paciente ni una cancelación de la prestación.

**Saldo pendiente de resolución administrativa**:
Importe de una prestación realizada que el paciente no aceptó pagar y que el hospital rechazó asumir. Permanece identificado para resolver su tratamiento, sin atribuirlo automáticamente al paciente o al financiador ni considerarlo cobrado.

**Responsable de resolución administrativa**:
Persona de Finanzas designada por un hospital, con autorización expresa para decidir si esa institución asume un importe y gestionar los saldos pendientes de resolución administrativa.

**Resolución de un saldo pendiente**:
Decisión registrada que cierra la revisión porque el hospital asume el importe o porque el paciente o financiador acepta expresamente pagarlo, con respaldo para la prestación y el importe. Conserva el historial; el cobro se registra cuando ocurre.

**Cargo**:
Importe atribuido a un responsable de pago por una prestación realizada.
_Evitar_: Cobro, costo interno.

**Cobro**:
Entrada de dinero registrada para cancelar total o parcialmente un cargo.
_Evitar_: Cargo, cobertura.

**Finalización de afiliación**:
Fin explícito de la afiliación vigente de una persona. Impide elegirla para nuevos casos y conserva la afiliación fijada en los casos anteriores, su identidad y los consumos del período.

**Reactivación de afiliación**:
Restablecimiento explícito de una afiliación finalizada. Conserva la identidad y los consumos anteriores; no ocurre por incluir a la persona en una importación.

**Cierre de convenio**:
Fin del acuerdo vigente entre un hospital y un financiador. Conserva las prestaciones y cargos registrados; una nueva relación requiere otro convenio.

**Acceso histórico pendiente**:
Consulta limitada del financiador a operaciones propias que todavía requieren atención o resolución económica, aunque haya terminado la afiliación o el convenio. Un saldo del paciente no habilita por sí solo ese acceso.
