# I-Core Salud para quien lo vende

> Qué es, qué mostrar, qué contestar y qué no prometer.
> Verificado contra el sistema el **22/09/2026**. No hay una sola línea de código acá.

---

## 1. Qué es, en una frase

Un sistema donde el hospital **dibuja su propio circuito de atención como un
diagrama** —admisión, triage, sala de espera, atención, derivación, internación— y
ese mismo diagrama pasa a ser el sistema que usa el personal.

## 2. Por qué eso importa

El software de gestión hospitalaria se compra y después hay que adaptarlo. Cambiar
un paso del circuito —agregar un formulario, sumar una especialidad, cambiar quién
llama al paciente— es un pedido a un proveedor, una cotización y meses de espera.

Acá el circuito **se configura en días y lo cambia el hospital**. No es una promesa:
es lo que se demuestra en vivo en la pantalla del editor, y es el momento más fuerte
de la demo.

La otra frase que funciona: **nadie programa una pantalla a mano.** El sistema dibuja
las pantallas leyendo el diagrama.

## 3. Qué mostrar

Todo está preparado. No hace falta improvisar ni armar datos.

| Tenés… | Usá |
|---|---|
| 45–50 minutos | [Guion de demo comercial](entornos/guia-demo-comercial.md) completo |
| 20 minutos | Del mismo guion, los bloques **1, 4 y 6** |
| Una reunión sobre obras sociales | [Recorrido de financiadores](entornos/guia-demo-financiadores.md), 20 min |
| Una reunión sobre costos y gastos | [Recorrido de Los Aromos](funcionalidades/finanzas-costos/guia-los-aromos.md), 25–30 min |

Cada guion dice **con qué usuario entrar en cada bloque, qué pantalla abrir, qué
señalar y qué frase decir**. Están escritos mirando la aplicación, botón por botón.

**Antes de cualquier reunión**, leé las dos últimas secciones del guion comercial:
[«Lo que conviene no mostrar»](entornos/guia-demo-comercial.md) y «Antes de
presentar». Hay cosas que están a medias y conviene no abrirlas por accidente.

> No uses `DEMO.md`: ése describe el entorno de desarrollo, con otros puertos y otros
> usuarios. El tuyo es el entorno demo, en el puerto 8082.

Todo lo que se muestra es **ficticio**: instituciones, personas, obras sociales,
importes y convenios. Decilo una vez al principio.

## 4. Qué está construido

En lenguaje de negocio, sin condicionales. Todo esto funciona y se puede mostrar:

| | Qué resuelve |
|---|---|
| **Circuitos de atención** | El hospital diseña su proceso y el sistema lo ejecuta. Versionado: cambiar el circuito no rompe los casos en curso |
| **Guardia** | Admisión, triage con prioridad, sala de espera ordenada por gravedad, llamado por box, pantalla de TV para la sala |
| **Especialidades y estudios** | Derivación entre áreas, estudios de laboratorio e imágenes con ida y vuelta, interconsultas |
| **Internación** | Censo de camas por sector, asignación desde el caso, pases y egresos |
| **Turnos programados** | Agendas por profesional o recurso, cupos, bloqueos, reprogramación, ausentismo, presencial o virtual |
| **Historia clínica** | Evolución, estudios, recetas, antecedentes y alergias, con firma profesional |
| **Farmacia e insumos** | Stock por depósito y lote, pedidos entre depósitos, alertas de faltante y vencimiento, y **trazabilidad de lote hasta el paciente** |
| **Red de establecimientos** | Derivación entre hospitales, con aceptación, ambulancia y recepción en destino |
| **Costos y gastos** | Cuánto cuesta cada atención, qué gasta cada área, y reparto de los gastos entre las atenciones |
| **Cobros y obras sociales** | Convenios, cobertura por prestación, cupos, copago del paciente y seguimiento de lo que se debe cobrar |
| **Auditoría** | Quién consultó qué historia clínica y cuándo. Sellado de integridad de la historia |
| **Multi-institución** | Una plataforma gobernando varios efectores con madurez distinta |

## 5. Qué contestar por lo que no está

> Esta tabla venía del plan comercial y **tenía tres respuestas que hoy son falsas**:
> negaba turnos y farmacia, que están construidos, y pedía no ofrecer FHIR, que
> funciona. Corregido el 22/09/2026 contra el sistema.

| Si preguntan por… | Respuesta |
|---|---|
| **Turnos programados** | **Está construido.** Agendas, cupos, bloqueos, reprogramación y ausentismo. Se puede mostrar |
| **Farmacia** | **Está construido**, incluida la trazabilidad de lote hasta el paciente |
| **Facturación** | «I-Core no reemplaza el facturador: se integra con el que ya tienen.» Es la respuesta honesta *y* la coherente con el posicionamiento |
| **Obras sociales** | Cobertura, cupos, copago y cobros **están construidos**. Lo que no hay es facturación fiscal ni conciliación bancaria |
| **Historia clínica completa** | Mostrar la que hay: evolución, estudios, recetas, antecedentes. Es real y alcanza |
| **Integración con nuestro sistema** | Hay API completa y una fachada FHIR de lectura funcionando (pacientes, episodios, instituciones, cobertura). **El conector concreto se define en el relevamiento del piloto** |
| **Firma digital** | La firma por rol y matrícula **está y es real**: queda registrado quién firmó y con qué matrícula. La firma criptográfica con certificado (Ley 25.506) **no está implementada**; está identificado dónde iría y hace falta que el cliente elija certificador y dispositivo. No decir «está listo, sólo falta el certificado» |
| **Reportes de gestión** | Hay reportes económicos comparables con descarga en PDF. **No hay todavía** tableros de indicadores por región o provincia |
| **¿Cuántos hospitales lo usan hoy?** | La verdad. El diferencial no es la base instalada: es que el proceso se configura en días, y eso se demuestra en vivo |

### Tres cosas que tenés que decidir vos

No las completo porque son decisiones comerciales, no técnicas:

- **¿Se ofrece la integración FHIR como parte de la venta, o sólo se menciona como
  capacidad?** Existe y funciona como lectura. No hay conector a un sistema concreto
  ni especificación publicada. Ofrecerla compromete un relevamiento.
- **¿Qué se promete sobre datos productivos?** El circuito de obras sociales está
  construido y probado con un piloto de dos hospitales y dos financiadores, pero
  **nunca operó con datos reales**. Eso es un mini-piloto y conviene cotizarlo aparte.
- **¿Cuál es el paquete de entrada hoy?** El plan comercial original decía «Guardia
  primero, turnos y farmacia después». Ya están las tres. Si el paquete de entrada
  sigue siendo Guardia es una decisión de precio, no una limitación del producto.

## 6. Lo que conviene no prometer

- **Que opera hoy en un hospital real.** No hay base instalada. El sistema está
  completo en su núcleo, pero el despliegue productivo todavía no se hizo y falta
  decidir dónde se hospeda.
- **Contabilidad general.** No es un ERP contable ni lo pretende.
- **Un plazo de implementación.** Depende del circuito que tenga el cliente, y eso
  se sabe en el relevamiento.

## 7. Si te preguntan algo que no está acá

Dos lugares, en este orden:

1. [Qué hace cada módulo](funcionalidades/README.md) — está en lenguaje técnico, pero
   cada ficha arranca con un «para qué sirve» que se entiende.
2. [Estado del proyecto](ESTADO-DEL-PROYECTO.md) — qué está construido, qué falta y
   qué no está validado.

Y si la respuesta cambia lo que se promete, preguntá antes de contestar. Una respuesta
improvisada en una reunión se transforma en una entrega comprometida.
