# PLEXO | Guía de uso y evaluación para OSTEL

**Demo:** https://cauce-web-production.up.railway.app/
**Edición:** octubre de 2026.

Esta guía acompaña al equipo de OSTEL en el uso de PLEXO: desde la gestión de
afiliados y autorizaciones hasta su relación con distintos prestadores. El
recorrido les permitirá probar las herramientas y registrar los ajustes que
necesitan para su operación habitual. Todos los prestadores, personas,
documentos, planes, importes y condiciones de los ejemplos son ficticios.
**El escenario no representa acuerdos, cartilla ni condiciones reales de OSTEL.**
No carguen información real de afiliados en este ejercicio.

## 1. Qué van a encontrar

OSTEL tiene un padrón único y convenios separados con tres instituciones.
La red permite mostrar que una obra social trabaja con distintos prestadores,
sin convertirse ella misma en un hospital ni mezclar las historias clínicas.

| Prestador ficticio | Operación preparada | Acuerdo ilustrativo con OSTEL |
|---|---|---|
| Sanatorio del Parque · Demo OSTEL | Consultas, radiografías, internación, farmacia y finanzas | Consulta $28.000; radiografía $45.000; respuesta de autorización en 48 horas |
| Centro Ambulatorio del Sur · Demo OSTEL | Consultas, turnos, farmacia de apoyo, derivaciones y finanzas | Consulta $22.000; convenio independiente |
| Diagnóstico Norte · Demo OSTEL | Radiografías, turnos, insumos y finanzas | Radiografía $38.000; respuesta de autorización en 72 horas |

Hay dos planes de ejemplo. Base cubre 80% de consultas, con hasta 6 al año,
y 70% de radiografías, con hasta 2 al año. Plus cubre 100% de consultas, con
hasta 12 al año, y 90% de radiografías, con hasta 4 al año. Las radiografías
requieren autorización previa. Los límites corresponden al año calendario.

**Lo que conviene comprobar:** el mismo afiliado puede atenderse en dos
instituciones con aranceles diferentes. El consumo de su cupo se acumula
entre los prestadores. Cambiar de institución no lo reinicia.

## 2. Cómo entrar y elegir el contexto

Las contraseñas se entregan por un canal separado. No están en esta guía.
Si un acceso falla, soliciten al responsable de la demo verificar su usuario
y la contraseña vigente.

| Acceso | Usuario | Para qué sirve |
|---|---|---|
| Evaluación completa | consultora@ostel.demo.test | Cambiar entre OSTEL y las tres instituciones ficticias; recorrer configuración y operación |
| Administración de OSTEL | admin@ostel.demo.test | Planes, padrón, convenios, usuarios y datos protegidos habilitados |
| Autorizaciones | autorizaciones@ostel.demo.test | Responder solicitudes; sin acceso habilitado a salud o cobranza del padrón |
| Salud del padrón | salud@ostel.demo.test | Revisar datos de salud declarados del padrón con permiso específico |
| Cobranza del padrón | cobranza@ostel.demo.test | Revisar la situación de cobranza informada con permiso específico |
| Auditoría de OSTEL | auditor@ostel.demo.test | Consultar y contrastar la vista de sólo lectura |
| Portal del paciente | paciente@ostel.demo.test | Entrar desde el acceso de pacientes; consultar turnos y registros propios de Martín Pereyra |

Para cada institución también hay personal propio:

| Institución | Administración | Profesional | Enfermería |
|---|---|---|---|
| Sanatorio | adm@sanatorio.ostel.demo.test | medico@sanatorio.ostel.demo.test | enfermeria@sanatorio.ostel.demo.test |
| Ambulatorio | adm@ambulatorio.ostel.demo.test | medico@ambulatorio.ostel.demo.test | enfermeria@ambulatorio.ostel.demo.test |
| Diagnóstico | adm@diagnostico.ostel.demo.test | medico@diagnostico.ostel.demo.test | enfermeria@diagnostico.ostel.demo.test |

Usen el selector de organización para elegir OSTEL o el prestador sobre el que
van a trabajar. Para comparar dos perfiles simultáneos, usen perfiles de
navegador separados o una ventana privada: las pestañas normales comparten sesión.

El acceso de evaluación concentra permisos para facilitar el recorrido, sólo
en el escenario ficticio. No representa los permisos que debería tener cada
persona en una implantación real. Usen los perfiles específicos para evaluar
la separación de responsabilidades. Los datos históricos de la demo siguen
existiendo; estos accesos no reciben acceso global a otras organizaciones.

## 3. Primer recorrido: del afiliado a dos prestadores

1. Ingresen como **consultora**, elijan **OSTEL · Demostración** y abran el padrón.
2. Busquen a **Martín Pereyra**, número **OSTEL-D001-00**. Revisen su plan Base,
   sus datos administrativos y los integrantes de su familia.
3. Consulten su actividad: tiene una consulta realizada en el Sanatorio y otra
   en el Centro Ambulatorio. Comparen prestador, prestación e importe propio.
4. Cambien al **Sanatorio del Parque**, abran Pacientes y busquen a Martín.
   Revisen la atención firmada de esa institución.
5. Cambien al **Centro Ambulatorio del Sur** y repitan. Hay otra ficha
   institucional y otra atención; no una historia clínica completa compartida.
6. Desde una atención nueva de consulta, seleccionen su afiliación y evalúen
   cobertura. En el ejemplo inicial quedan **4 de las 6 consultas
   anuales**: ya usó una en cada institución. Consultar no reserva cupo.
7. Comparen los aranceles: $28.000 y $22.000. Con el plan Base, el 80% corresponde
   al financiador y el 20% al paciente. Registrar la distribución no significa cobrar.

**Resultado esperado:** una afiliación estable, dos prestadores, dos aranceles
y un cupo compartido. Si antes completaron nuevas atenciones o reservas, la
disponibilidad ya puede ser menor: ese cambio es parte del ejercicio.

## 4. Padrón, familias, legajo e importaciones

Con **admin@ostel.demo.test**, abran el padrón de OSTEL. Hay **24 afiliados**,
organizados en seis grupos familiares: Pereyra, Benítez, Sosa, Acosta, Vega y Medina.
Cada grupo incluye titular, cónyuge, menor e hijo estudiante.

- Abran **Julián Pereyra**: su trámite está en revisión y tiene una presentación
  de estudios pendiente de verificar. Registrar una presentación no adjunta un archivo.
- Revisen un afiliado con trámite completo: tiene documentación verificada y
  credencial externa informada. Esto no implica emisión oficial de credenciales.
- Prueben filtros, búsqueda, ordenamiento y exportación del padrón. Comparen
  el resultado exportado con los filtros aplicados.
- Para importar, descarguen una plantilla desde esta misma demo, completen
  una muestra ficticia y revisen la previsualización antes de confirmar.
  La importación incorpora o actualiza filas; omitir una persona no le da de baja.
- Comparen **salud**, **cobranza** y **autorizaciones**: los permisos sobre
  datos protegidos se otorgan por separado.

**Ejemplos para conversar:** Martín Vega tiene una declaración ficticia de salud.
Martín Medina tiene una baja administrativa informada y continuidad prestacional
declarada. Su situación de cobranza indica deuda informada. Ninguna de estas
declaraciones constituye por sí sola un corte automático de cobertura ni una
cuenta corriente calculada.

## 5. Autorizaciones: trabajo de ambos lados

En OSTEL, entren como **autorizaciones** y abran las solicitudes. Hay ejemplos
de Sanatorio del Parque y Diagnóstico Norte para estas personas de la familia Benítez:

| Persona | Situación inicial | Ejercicio |
|---|---|---|
| Martín Benítez | Pendiente | Revisar el pedido y aprobarlo o rechazarlo con motivo |
| Lucía Benítez | Observada | Desde el prestador, completar el respaldo y reenviar |
| Camila Benítez | Rechazada | Revisar el motivo y el estado conservado del caso |
| Julián Benítez | Aprobada y utilizada | Consultar la autorización y la prestación realizada |

Después de aprobar una solicitud, vuelvan al prestador correspondiente y
continúen la atención. No confundan aprobar la autorización con realizar
la práctica o registrar su cobro: son hechos distintos.

Las solicitudes vencen según el convenio, a las 48 o 72 horas desde su creación.
Si encuentran una solicitud vencida, revisen su historial y creen una nueva
desde otro caso para continuar la práctica.

## 6. Cobertura, copagos y consumos externos

En el prestador, abran **Coberturas y copagos** y luego un caso ambulatorio.
Revisen afiliación, cobertura evaluada, importe, aceptación y reservas.

- **Martín Sosa:** tiene seis consultas externas informadas en el año. Al
  evaluar una nueva consulta aparece el cupo agotado en ambos prestadores.
  Es un consumo declarado por la obra social, no una atención clínica inventada
  dentro de estos hospitales.
- Para otra persona, evalúen una consulta con cobertura parcial; registren la
  aceptación del copago antes de realizarla. La reserva compromete cupo y se
  convierte en consumo al completar la prestación.
- Revisen los cargos y saldos resultantes. Un saldo pendiente requiere la
  resolución administrativa correspondiente; no debe interpretarse como cobrado.

## 7. Turnos, atención, filas e historia clínica

Elijan un prestador con el usuario **consultora** o su personal propio.

1. En **Agenda**, hay disponibilidades de lunes a viernes y turnos futuros.
   Reserven, confirmen o reprogramen un turno de prueba.
2. En **Casos** y **Filas**, seleccionen una atención pendiente y llamen al paciente.
3. Registren una evolución y completen la atención con el profesional de esa
   institución. La firma requiere una matrícula, ya cargada para los perfiles de prueba.
4. Desde **Pacientes**, consulten los registros que dejó la atención.
5. Revisen el historial del caso y las notificaciones asociadas a la operación.

Cada profesional trabaja con su institución y sus áreas. La cuenta de OSTEL
no equivale a un médico del hospital. El acceso del financiador a evoluciones
clínicas tiene un alcance propio y exige motivo; no habilita la historia
clínica completa de todos los hospitales.

## 8. Internación y farmacia

En **Sanatorio del Parque**, abran **Internación**. Hay ocho camas: una ocupada
con una estadía abierta, cinco libres, una en higiene y una bloqueada por
mantenimiento. El paciente internado de ejemplo es **Martín Acosta**.

Revisen su caso y la cama asignada. Pueden probar el circuito de evolución,
pase o egreso según las acciones que ofrezca el caso. Una cama en higiene o
bloqueada no está disponible para una nueva asignación.

En **Farmacia**, revisen depósitos, stock y lotes de demostración. Hay pedidos
pendientes de reposición, un insumo por debajo del mínimo y un consumo
imputado al caso del paciente internado. Prueben preparar y entregar un
pedido, y consulten la trazabilidad del lote.

El stock de la demo no representa un vademécum ni protocolos farmacológicos
de OSTEL. Los centros ambulatorio y de diagnóstico tienen depósitos de apoyo;
la internación está concentrada en el sanatorio.

## 9. Red y derivaciones

En **Centro Ambulatorio del Sur → Red**, revisen las solicitudes hacia el
Sanatorio. Encontrarán ejemplos solicitado, aceptado y rechazado.

Prueben responder una solicitud desde el Sanatorio y consulten el cambio
desde el Centro Ambulatorio. Aceptar genera el caso del destino con su ficha
institucional. La cobertura del nuevo caso se elige expresamente: el traslado
no traslada automáticamente una decisión económica ni comparte toda la historia.

La red de derivaciones y el convenio con OSTEL son relaciones diferentes:
pertenecer a una red no activa un convenio de cobertura.

## 10. Finanzas y comprobantes

En cada prestador, abran **Finanzas** con su administración o con **consultora**.
Revisen los costos por atención, los gastos y **Pagos y cobros** del período de
los ejemplos; ajusten el filtro de mes si fuera necesario.
Hay un gasto ficticio de insumos por **$150.000**, una obligación por ese monto
y un pago parcial aprobado de **$50.000**. El saldo pendiente es **$100.000**.

Las consultas y radiografías realizadas dejan sus registros económicos. Revisen
cuánto corresponde al financiador y cuánto al paciente; esos cargos no se
consideran cobros hasta registrar el movimiento correspondiente.

En OSTEL, revisen **Facturas**: hay dos comprobantes recibidos por cada
prestador. Son registros administrativos ficticios, sin adjuntos ni emisión
fiscal. No se vinculan automáticamente a una liquidación ni a los movimientos
de dinero del ejemplo.

## 11. Configuración, control y portal del paciente

- **Estructura y usuarios:** revisen las áreas, grupos y pertenencias de cada
  institución. Modifiquen sólo datos ficticios del escenario.
- **Flujos y formularios:** los circuitos ya están publicados. Para experimentar,
  creen una nueva versión o un flujo de prueba; eviten alterar el recorrido
  compartido antes de que otras personas lo completen.
- **Auditoría:** después de consultar una historia clínica, revisen el registro
  de acceso dentro del alcance del perfil. Una consulta y una modificación son
  evidencias diferentes.
- **Portal del paciente:** cierren la sesión institucional y usen el acceso de
  pacientes con **paciente@ostel.demo.test**. Martín Pereyra tiene identidad
  ficticia prevalidada, turnos y estudios de muestra en dos instituciones.
  Los estudios de ejemplo no incluyen archivos descargables. La identidad
  del paciente está preparada para que puedan ingresar sin realizar un trámite
  de validación personal.

Para evaluar intercambios con otros sistemas, identifiquen qué información
necesitan enviar o recibir, con quién y en qué momento de su operación.

## 12. Qué está disponible y qué requiere otro trabajo

El recorrido cubre padrón y familias, legajo, planes, convenios, aranceles,
autorizaciones, cobertura y cupos, atención y turnos, registros clínicos,
internación, farmacia, traslados, costos, gastos, pagos, cobros y comprobantes
administrativos.

**Circuitos que requieren un alcance adicional:** emisión de comprobantes fiscales,
contabilidad general, conciliación bancaria, cálculo de aportes o deuda de
afiliación, liquidación integral de prestadores, reintegros completos,
SURGE e intercambio real con ARCA, ANSES o SSSalud. Si alguno forma parte de su
operación, inclúyanlo en el relevamiento para analizarlo con el equipo de PLEXO.

Las necesidades que identifiquen permitirán acordar alcance, prioridades y
resultados esperados para una adaptación a OSTEL.

## 13. Cómo registrar las necesidades reales

Para cada tarea, anoten el resultado con este formato:

| Dato | Qué registrar |
|---|---|
| Obra social y perfil | Quién realiza la tarea y con qué responsabilidad |
| Tarea y frecuencia | Qué intenta resolver y cuántas veces lo hace |
| Ejemplo ficticio | Afiliado, prestador o caso utilizado, sin datos reales |
| Resultado | Se pudo completar / requiere ajuste / no está disponible |
| Diferencia con su operación | Campo, regla, permiso, aprobación, archivo o paso faltante |
| Criterio de aceptación | Qué deberían observar para considerar resuelta la necesidad |
| Prioridad | Impide operar / importante / mejora deseable |

Usen tareas concretas: dar de alta una familia, autorizar una práctica, atender
en dos prestadores, revisar un cupo o registrar un pago. Si algo no coincide,
anoten organización, pantalla, acción y resultado observado. No incluyan
contraseñas ni información real de afiliados.

## 14. Si cambia algo durante la evaluación

La demo conserva lo que ustedes operan. Autorizar una práctica, consumir
cupo, pagar una cuenta o cambiar una contraseña modifica los ejemplos iniciales.
**Las pruebas no se reinician automáticamente.**

Si un ejemplo ya fue utilizado, continúen con otro afiliado o creen un caso nuevo.
Si necesitan volver a comenzar, coordinen con el responsable de la demo la
preparación de nuevos ejemplos.

Al terminar, comparen las tareas completadas y las diferencias registradas con
la consultora. Ese relevamiento servirá para acordar la adaptación a la operación
real de cada obra social.
