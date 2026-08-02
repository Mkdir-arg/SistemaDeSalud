# Plan de versiones — NODO Salud

> Hoja de ruta de producto alineada al plan comercial de ICORE. Documento vivo.
> Creado: **2026-07-31**.

> ⚠️ **Superado el 2026-07-31 por [`PLAN-DESARROLLO.md`](PLAN-DESARROLLO.md).** Se
> decidió desarrollar la aplicación punta a punta en vez de salir con una ruta
> demo-first. Este documento se conserva por dos partes que siguen vigentes: el
> **mapeo de los paquetes comerciales contra lo construido** y la **tabla de
> respuestas para lo que no está construido** (final del documento). El cronograma
> de acá abajo ya no aplica.

Complementa [`ESTADO-DEL-PROYECTO.md`](ESTADO-DEL-PROYECTO.md) (qué hay hecho) y
[`FUNCIONALIDADES.md`](FUNCIONALIDADES.md) (catálogo completo).

## Contexto que define este plan

| Variable | Definición |
|---|---|
| **Objetivo de la primera etapa** | Vender y demostrar. **No** implementar todavía. |
| **Equipo** | Una persona (Mati) + Claude. Sin frentes paralelos. |
| **Plazo** | 4-6 semanas para tener las dos demos listas. |
| **Paquetes comerciales objetivo** | Guardia (existe) · Clínica (~50%) · Red (~20%) |

### Principio rector

> **Rebanadas finas pero reales. Nunca maquetas.**

Todo lo que se muestre en una demo se va a pedir en la implementación. Una pantalla
mockeada que impresiona en la reunión se transforma en deuda de entrega el día que
firman. Por eso cada versión de acá abajo construye **menos alcance del que pide el
plan comercial, pero funcionando de verdad** sobre el motor que ya existe.

Corolario para la venta: **no se demuestra lo que no está construido.** Turnos,
farmacia y facturación no aparecen en ninguna pantalla hasta la v3.

---

## Resumen de versiones

| Versión | Nombre | Cuándo | Objetivo |
|---|---|---|---|
| **v1.0** | Demo vendible: Guardia | Semanas 1-2 | Que la demo que ya existe se pueda mostrar sin excusas |
| **v1.1** | Demo Ministro: la red | Semanas 3-4 | Vista multicentro para la conversación con un ministerio |
| **v1.2** | Demo Clínica: la cama | Semanas 5-6 | Censo de camas + corte gerencial (la única pieza nueva de dominio) |
| **v2.0** | Piloto productivo | Gatillada por la 1ª venta | Endurecer para operar de verdad en un cliente |
| **v3.0** | Clínica completa | Post-venta | Turnos, farmacia, facturación (el Paquete 2 real) |
| **v4.0** | Red real | Post-venta | Derivación entre establecimientos, traslados, alertas |

Las versiones **v1.x tienen fecha**. Las **v2+ no**: se disparan cuando hay un
contrato que las pague. Poner fechas a v2+ hoy sería planificar sobre una venta que
todavía no existe.

---

# v1.0 — Demo vendible: Guardia
**Semanas 1-2 (3 al 14 de agosto de 2026)**

## Objetivo
El Paquete 1 ya está construido. Esta versión **no agrega funcionalidad de dominio**:
hace que se pueda mostrar. Hoy no se puede.

## El bloqueador que justifica esta versión

`seed_guardia` crea la institución, las áreas, el staff, los grupos, los boxes, los
formularios y los 8 flujos publicados — pero **borra los casos y no crea ninguno**
([`seed_guardia.py:85`](../backend/apps/casos/management/commands/seed_guardia.py#L85)).

Consecuencia concreta: hoy la demo abre con **bandejas vacías, filas vacías y un
tablero sin datos**. Las tres pantallas que más venden (el tablero de tiempos, la
fila con urgentes al frente y la pantalla de TV de llamados) se ven vacías. La demo
actual solo funciona si alguien camina un caso a mano en vivo, que es exactamente lo
que no hay que hacer frente a un ministro.

## Alcance

| # | Entregable | Detalle | Días |
|---|---|---|---|
| 1 | **Generador de datos con historia** | Comando `seed_demo_rico`: ~40 pacientes, ~300 casos recorridos por los 8 flujos con **timestamps retroactivos** (90 días), distribución realista de triage, casos activos en cada paso, colas con urgentes. Requiere backdatear `auto_now_add` (update posterior a la creación). | 3 |
| 2 | **Despliegue público estable** | URL fija con Postgres gestionado, HTTPS, seed reproducible y botón de reset. Sin esto no hay demo remota ni link para dejarle al cliente. | 1 |
| 3 | **Pase de pulido sobre el camino de demo** | Solo las pantallas que se muestran: Tablero, Mi trabajo, Fila, Detalle de caso, Pantalla de TV, Editor de flujos. Estados vacíos, textos, alineación a las capturas. | 3 |
| 4 | **Guion de demo «Dueño de clínica»** | Recorrido escrito de 12-15 min con usuarios, orden de pantallas, qué decir en cada una y las 3 preguntas difíciles con su respuesta. | 1 |
| 5 | **Reset de un comando** | Que la demo se pueda dejar impecable en 30 segundos entre reunión y reunión. | 0,5 |

## Qué NO incluye
Nada de dominio nuevo. Ni camas, ni turnos, ni multicentro, ni integraciones.

## Criterio de terminado
Un tercero que no conoce el sistema abre la URL, entra con `guardia.med`, y ve una
guardia con pacientes esperando, un tablero con curvas de 90 días y una TV de
llamados funcionando — **sin que nadie haya cargado nada antes**.

---

# v1.1 — Demo Ministro: la red
**Semanas 3-4 (17 al 28 de agosto de 2026)**

## Objetivo
El plan comercial pide una demo específica de «Ministro de Salud». Hoy no existe:
el tablero es **por institución** (`/instituciones/{id}/tablero/`) y el directorio
es una tabla administrativa, no una vista de conducción.

Esta es la brecha más grande entre el pitch y el producto, y también la más barata
de cerrar en su versión honesta: la arquitectura multi-institución ya está hecha
(instituciones autocontenidas, scope transversal en toda la API). Falta **agregar y
mostrar**, no rediseñar.

## Alcance

| # | Entregable | Detalle | Días |
|---|---|---|---|
| 1 | **Tablero multicentro** | Endpoint nuevo que agrega las métricas que ya calcula el tablero por institución, ahora sobre N establecimientos: casos activos, en cola, urgentes, espera y atención promedio. Reusa la lógica existente. | 3 |
| 2 | **Panel de establecimientos con semáforo** | Grilla de tarjetas por establecimiento con indicador de saturación (verde/ámbar/rojo según cola y espera vs. umbral). Es el «mapa sanitario» en su versión defendible: **sin georreferencia inventada**. | 2 |
| 3 | **Indicadores comparados** | Ranking simple entre establecimientos por espera, resolución y volumen. Es lo que un ministro mira primero. | 2 |
| 4 | **Datos demo de 3-4 establecimientos** | Extender el generador de v1.0 a varias instituciones con perfiles distintos (uno saturado, uno normal, uno chico). Sin esto el tablero multicentro se ve tan vacío como el actual. | 2 |
| 5 | **Guion de demo «Ministro de Salud»** | Recorrido de conducción: red → establecimiento saturado → guardia de ese establecimiento → caso concreto. El zoom de lo macro a lo micro es el argumento. | 1 |

## Qué NO incluye
- **Mapa georreferenciado.** Un mapa de la provincia con puntitos es caro y no
  agrega argumento por encima del semáforo. Se difiere a v4.
- **Derivación entre establecimientos.** Hoy la derivación es siempre
  intra-institución ([`motor.py:372`](../backend/apps/casos/motor.py#L372)). Cambiarlo
  toca el motor y el modelo de permisos: es v4, no una demo.
- **Alertas por saturación.** El semáforo se ve; no notifica. v4.
- **Traslados.** No existe el dominio. v4.

## Criterio de terminado
Se puede contar la historia completa «veo la red → detecto un establecimiento
saturado → entro → veo por qué → veo el caso» sin salir del producto.

---

# v1.2 — Demo Clínica: la cama
**Semanas 5-6 (31 de agosto al 11 de septiembre de 2026)**

## Objetivo
La única pieza de dominio nueva de todo el plan de 6 semanas. Se elige **camas** y
no turnos/facturación por tres razones:

1. Es la que **más aparece en las tres demos** (guardia decide internar, clínica vive
   de la ocupación, la red pregunta por disponibilidad).
2. Es la más barata de las cuatro faltantes del Paquete 2.
3. Ya hay un flujo de Internación funcionando al que engancharse — no se construye
   desde cero.

Turnos, farmacia y facturación **quedan afuera y no se demuestran**.

## Alcance

| # | Entregable | Detalle | Días |
|---|---|---|---|
| 1 | **Modelo de camas** | `Cama` por área/sector con estado (libre / ocupada / limpieza / fuera de servicio) y la ocupación vinculada al caso internado. | 2 |
| 2 | **Enganche con el flujo de Internación** | El nodo «Asignar cama» pasa a asignar una cama real; el alta la libera. Sin esto son dos sistemas paralelos. | 2 |
| 3 | **Tablero de ocupación** | Vista de sector con camas, ocupante y días de estada. % de ocupación al tablero de la institución y al multicentro. | 3 |
| 4 | **Corte gerencial del tablero** | Sobre el tablero operativo que ya existe: volumen por área, ocupación, tiempos, tendencia. Sin datos económicos (no hay facturación). | 2 |
| 5 | **Ensayo y buffer** | Ensayo cronometrado de las dos demos + arreglo de lo que salga. | 2 |

## Qué NO incluye
Turnos/agenda, farmacia, insumos, facturación, obras sociales.

## Criterio de terminado
Un paciente entra por guardia, se interna, ocupa una cama real, y esa cama se ve en
el tablero de ocupación, en el tablero gerencial y en el multicentro.

## ⚠️ Esta es la versión que se recorta si algo se atrasa
Si las semanas 1-4 se estiran, **v1.2 se cae completa** y se sale a vender con
Guardia + Red. Es preferible a llegar con las tres demos a medio terminar. La
decisión de recorte hay que tomarla al cierre de la semana 4, no en la semana 6.

---

# v2.0 — Piloto productivo
**Sin fecha. Se dispara con la primera venta.**

Todo lo de acá abajo es lo que separa una demo de un sistema que opera un hospital.
No se construye antes de tener un contrato: es trabajo caro que no ayuda a vender.

| Bloque | Qué incluye | Por qué |
|---|---|---|
| **Integración** | OpenAPI/Swagger, API pública documentada, y evaluación de HL7/FHIR según el cliente | El mensaje comercial promete «integración con sistemas existentes» y **hoy no hay nada**: ni conectores, ni especificación. Es la primera pregunta del área de sistemas de cualquier organismo. Es el hueco más grave del pitch actual. |
| **Normativa** | Revisión de Ley 26.529 (historia clínica) y 25.326 (datos personales), auditoría de accesos, política de retención | Ítem de pliego en cualquier licitación pública. Hay trazabilidad por evento y firma restringida a médicos, pero nunca se auditó contra la norma. |
| **Operación real** | Reactivación automática de esperas por tiempo (cron), backups, monitoreo, manejo de errores, límites de carga | Hoy una espera por tiempo (observación en guardia) se destraba **a mano**. |
| **Reportes** | Exportación CSV/PDF de tableros y casos | No existe ninguna exportación en el sistema. Un director pide el reporte en papel. |
| **Endurecimiento** | Prueba con volumen real, performance, permisos de escritura revisados extremo a extremo | Nunca se probó fuera de datos de demo. |
| **Puesta en producción** | Ambiente del cliente, migración de datos, capacitación | — |

**Estimación gruesa:** 6-10 semanas de una persona, muy dependiente del cliente
concreto (un ministerio con licitación pesa el doble que una clínica privada).

---

# v3.0 — Clínica completa (el Paquete 2 real)
**Sin fecha. Post-venta.**

Los cuatro faltantes duros del Paquete 2 del plan comercial:

| Módulo | Alcance | Estimación |
|---|---|---|
| **Turnos / agenda** | Modelo de agenda por profesional, disponibilidad, reserva, sobreturnos, ausentismo. **No existe nada hoy** (el `turno` actual es un número de ticket de fila). | 4-6 semanas |
| **Camas completo** | Sobre la base de v1.2: censo, movimientos, pases entre sectores, higiene, bloqueos | 2-3 semanas |
| **Farmacia e insumos** | Stock, pedidos, consumo por caso, alertas de faltante | 4-6 semanas |
| **Facturación** | Prestaciones, obras sociales, nomencladores, facturación y débitos | 8-12 semanas |

**Facturación es el más caro del plan entero y el que más se parece a un HIS
tradicional.** Recomendación explícita: **no venderlo**. Integrarse contra el
facturador que el cliente ya tiene es más rápido, más barato y coherente con el
posicionamiento («NODO no reemplaza todo: ordena, integra»).

---

# v4.0 — Red real (el Paquete 3 real)
**Sin fecha. Post-venta.**

| Módulo | Alcance | Estimación |
|---|---|---|
| **Derivación entre establecimientos** | Un caso viaja de un hospital a otro conservando historia y trazabilidad. Toca el motor, el modelo de permisos y el scope por institución. | 3-4 semanas |
| **Traslados** | Solicitud, móvil, seguimiento, tiempos | 3-4 semanas |
| **Disponibilidad de camas en red** | Camas de v1.2/v3.0 consolidadas y consultables entre establecimientos | 2 semanas |
| **Alertas por saturación** | Reglas por umbral y notificación real (hoy solo hay notificaciones in-app por poll) | 2 semanas |
| **Mapa sanitario georreferenciado** | El mapa de verdad, si el cliente lo pide | 2-3 semanas |
| **Reportes ejecutivos** | Exportación, reportes programados, envío | 2 semanas |

---

## Cómo responder en una reunión por lo que no está

El riesgo de una estrategia demo-first es que alguien pregunte por un módulo que no
existe y la respuesta improvisada comprometa una entrega. Respuestas acordadas:

| Si preguntan por… | Respuesta |
|---|---|
| **Turnos** | «No está en el paquete de entrada. Se incorpora en la segunda fase, después del piloto de guardia.» **Nunca** «lo tenemos». |
| **Facturación** | «NODO no reemplaza el facturador: se integra con el que ya tienen.» Es la respuesta honesta *y* la coherente con el posicionamiento. |
| **Integración con nuestro sistema** | «La API está construida y el sistema es modular; el conector se define en el relevamiento del piloto.» Es cierto: hay API REST completa. Lo que no hay es conector ni especificación publicada — no ofrecer HL7/FHIR hasta v2. |
| **Historia clínica completa** | Mostrar la que hay (evolución, estudios, recetas, antecedentes). Es real y alcanza para guardia. |
| **¿Cuántos hospitales lo usan hoy?** | La verdad. El diferencial no es la base instalada: es que el proceso **se configura en días, no se programa en meses** — y eso se demuestra en vivo en el editor de flujos. |

---

## Lo que este plan asume y conviene revisar

1. **Que la primera venta es de Guardia.** Si aparece primero una oportunidad de red
   o de clínica, el orden v1.1/v1.2 se invierte, no el contenido.
2. **Que 6 semanas son 6 semanas de una persona.** Cualquier soporte, urgencia o
   viaje comercial sale del mismo presupuesto de tiempo. El buffer real del plan es
   v1.2 completa.
3. **Que la demo se hace sobre datos ficticios.** Si algún cliente pide demo con sus
   propios datos, eso es un mini-piloto y hay que cotizarlo aparte.
