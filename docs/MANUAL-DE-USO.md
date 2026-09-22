# Manual de uso

> Para quien va a trabajar con el sistema todos los días: admisión, enfermería,
> profesionales y jefaturas de área.
>
> No hace falta saber nada de informática para leer esto.

Si buscás la especificación técnica, no es este documento:
[`docs/INDICE-FUNCIONAL.md`](INDICE-FUNCIONAL.md).

---

## 1. Lo primero que conviene entender

El sistema **no tiene pantallas fijas**. Cada hospital dibuja su propio circuito de
atención —admisión, triage, sala de espera, atención, derivación— y el sistema arma
las pantallas a partir de ese dibujo.

Por eso dos hospitales con I-Core Salud no se ven igual, y por eso **lo que ves en tu
pantalla depende del paso en el que esté el paciente**, no de un menú fijo.

Dos palabras que vas a leer todo el tiempo:

- **Caso**: el recorrido de un paciente por el circuito. Se abre cuando llega y
  avanza paso a paso hasta cerrarse.
- **Paso**: dónde está ese caso ahora. Determina qué podés hacer y quién puede
  hacerlo.

## 2. Entrar

Vas a la dirección que te dio tu institución y entrás con tu correo y tu contraseña.

Si trabajás en **más de una institución**, el sistema te va a preguntar en cuál
querés trabajar. Todo lo que hagas a partir de ahí queda dentro de esa institución.
Para cambiar, volvés al directorio desde la barra lateral.

**Lo que ves en el menú depende de tu rol.** Si te falta una opción que necesitás, no
es una falla: es un permiso que tiene que darte quien administra el sistema en tu
institución.

## 3. Tu pantalla de todos los días: Inicio

**Mi trabajo** es donde empieza el día. Reúne tres cosas:

| | Qué es |
|---|---|
| **Mis casos** | Lo que ya está asignado a vos |
| **Sin asignar** | Lo que podés tomar, según los equipos a los que pertenecés |
| **Esperas vencidas** | Lo que lleva más tiempo del esperado y hay que mirar |

**Tomar** un caso lo pone a tu nombre. **Continuar** lo abre donde quedó.

> Bandeja y Filas no están en el menú a propósito: son la cola de lo que te toca
> **ahora**, y se operan desde acá. «Casos», que sí está en el menú, sirve para otra
> cosa: buscar un caso que **no** es tu tarea pendiente —llama el paciente y
> pregunta, hay que revisar algo de ayer—.

## 4. Admisión: recibir a un paciente

1. **Buscalo en el padrón** por apellido o documento. Casi siempre ya está.
2. Si no está, **Crear registro**. Con el documento alcanza para empezar.
3. **Nuevo caso**: elegís el circuito que corresponde y el paciente.

El caso arranca y va al primer paso del circuito. A partir de ahí lo toma quien
corresponda.

### Padrón no es historia clínica

Son dos cosas distintas y con permisos distintos:

- **Padrón de pacientes**: los datos administrativos. Documento, domicilio, fecha de
  nacimiento, cobertura, consentimiento.
- **Historia clínica**: lo que el profesional escribió. Evolución, alergias,
  estudios, recetas.

**Si sos administrativo, ves el padrón y no la historia clínica.** Está puesto así a
propósito: podés identificar a la persona y abrirle el caso sin leer lo que el médico
escribió sobre ella.

### La cobertura

Al ingresar el caso elegís con qué cobertura se atiende: una **afiliación verificada**
de la obra social, una **pendiente de verificar**, o **atención particular**.

Esa elección **queda fija para ese caso**, aunque después la afiliación cambie o
venza. Corregirla se puede, queda registrado, y no modifica lo ya cobrado.

## 5. Enfermería: triage

En el paso de triage completás el formulario y **clasificás al paciente**. Esa
clasificación fija la prioridad con la que va a esperar.

Todos van a **una única sala de espera**, y la cola se ordena por esa prioridad: el
profesional llama siempre al de mayor prioridad primero, no al que llegó antes.

Por eso el triage no es un trámite: **es lo que decide el orden de atención**.

## 6. Llamar y atender

Desde tu **puesto**, ocupás un box y llamás al siguiente.

- **Llamar** muestra al paciente en la pantalla de la sala de espera y ocupa tu box.
- **Rellamar** vuelve a mostrarlo, si no apareció.
- **Ausente** lo saca de la cola y **libera el box**.
- **Devolver a la cola** lo reintegra, si hace falta.

Durante la atención, el panel te muestra **lo que corresponde a ese paso**: un
formulario a completar, la atención a registrar, un estudio a pedir. No tenés que
buscar nada en un menú.

### Registrar la atención

Título, contenido y firma. Queda como una entrada en la historia clínica del
paciente, con tu nombre y tu matrícula.

**Quién puede firmar lo decide cada paso del circuito**, no tu cargo: la
configuración del nodo dice qué roles firman y si hace falta matrícula. Si no lo
dice, firma el médico con matrícula. Además tenés que tener asignada el área donde
está el caso.

### Conducta

Al terminar, el circuito te ofrece las salidas que tenga definidas: alta,
observación, internación o derivación a una especialidad. El sistema resuelve solo a
dónde va el caso según lo que elijas.

## 7. Estudios e interconsultas

Cuando pedís un estudio, el caso **queda esperando** y se abre el trabajo del lado
del laboratorio o de imágenes. Cuando vuelve con el resultado, **te llega una
notificación** y el caso se reactiva donde estaba.

No tenés que ir a buscarlo.

## 8. Internación

El tablero de camas muestra el estado real de cada una: libre, ocupada, en higiene o
bloqueada.

- **Asignar cama** desde el caso.
- **Pase** de sector o de cama: cierra la estadía anterior y abre una nueva.
- **Egreso**: libera la cama y registra el motivo.

Una cama ocupada **siempre** tiene un caso asociado. Al liberarla puede pasar por
higiene antes de volver a estar disponible.

## 9. Turnos programados

Reservar, confirmar, cancelar, marcar ausente, cambiar entre presencial y virtual, y
reprogramar.

**Registrar la llegada** del paciente abre su caso, si la agenda tiene un circuito
asociado. Es el equivalente a la admisión para un turno programado.

Dos cosas que conviene saber:

- **Marcar ausente no libera el horario.** La oportunidad de atención se perdió, y el
  sistema lo refleja así a propósito.
- **Bloquear una agenda no cancela los turnos**: te muestra cuáles quedan afectados
  para que los gestiones.

## 10. Farmacia e insumos

Ingresos, consumos, transferencias entre depósitos, ajustes y bajas.

**Imputá el consumo al caso** cuando sea de un paciente. Es lo que después permite
responder la pregunta que importa: «se retira este lote, ¿a quién se le aplicó?».

Los pedidos entre depósitos pueden entregarse **parcialmente**; lo pendiente queda
visible.

## 11. Derivar a otro establecimiento

Desde el caso, **solicitar traslado**. El establecimiento de destino lo acepta,
rechaza o lo recibe.

Los casos **siguen perteneciendo a cada hospital**: aceptar una derivación abre un
caso nuevo del lado del destino, no mueve el tuyo.

Sólo el origen puede solicitar, cancelar y marcar «en camino». Sólo el destino puede
aceptar, rechazar y recibir.

## 12. Notificaciones

La campana de la barra superior avisa cuando:

- Vuelve un estudio o una interconsulta que pediste.
- Te reasignan un caso.
- Llega un caso urgente a un paso de tu equipo.
- Cancelan un caso del que eras responsable.

Marcar como leída no cambia nada del caso: **es un aviso, no el estado real**.

## 13. Jefatura de área

Si conducís un área, además tenés:

- **Tablero**: casos por paso, mapa del circuito, dónde se acumulan las demoras.
- **Supervisión**: reasignar un caso a otra persona, priorizarlo como urgente o
  cancelarlo con motivo.
- **Registro de accesos**: quién consultó la historia clínica de quién.

Priorizar como urgente **también reordena la fila** si el paciente está esperando.

## 14. Cosas que el sistema no te deja hacer, y por qué

No son fallas. Están puestas así:

| No podés… | Porque |
|---|---|
| Borrar una atención firmada | La historia clínica es evidencia. Se corrige con otra entrada, y las dos quedan |
| Editar o borrar un movimiento de dinero | Se corrige con otro movimiento, y el original se conserva |
| Ocupar una cama sin caso | Una cama ocupada sin paciente es disponibilidad falsa |
| Avanzar un paso que no es tuyo | Si el paso declara un equipo responsable, tenés que integrarlo |
| Ver pacientes de otra institución | Todo se acota a la institución en la que estás trabajando |
| Cobrarle un copago a alguien que no lo aceptó | Hace falta su aceptación de esa prestación y ese importe |

## 15. Cuando algo no funciona

- **«No tengo esta opción en el menú»** → es un permiso. Lo resuelve quien administra
  el sistema en tu institución.
- **«No puedo avanzar el paso»** → el mensaje dice qué falta: datos del formulario,
  una autorización de la obra social o la aceptación del paciente.
- **«El paciente no aparece»** → probá por documento en vez de por apellido. Si es su
  primera vez en este hospital, hay que crearle el registro.
- **«Dice que otra persona modificó esto»** → alguien tocó el mismo registro mientras
  vos editabas. Volvé a consultarlo: no se aplicó nada.
- **«Quedó esperando y no vuelve»** → avisá a soporte técnico. Hay un proceso que
  reactiva las esperas cada dos minutos y puede estar detenido.

---

## Para quien arma la capacitación

Las capturas de cada pantalla están en `diseño/docs/captures-manual/` (tomadas a
mano, para material impreso) y `diseño/docs/captures-app/` (generadas desde la
aplicación, útiles para mantenerlas al día).

El escenario de guardia completo, con pacientes, colas y camas cargadas, sirve para
practicar sin tocar datos reales: [`docs/entornos/`](entornos/README.md).
