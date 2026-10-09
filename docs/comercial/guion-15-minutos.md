# Guion de demo en 15 minutos

Para quien presenta. Recorre clínica (configuración y uso), paciente y financiador.
Verificado el **30/09/2026** contra el commit `b4294fd` más los cambios del #88, en un entorno
local cargado con `seed_entorno_demo --ancla 2026-10-01T08:00`. **Ensayalo en el entorno de la
demo antes de presentar:** si ahí falla un paso, vale lo que ves ahí.

Todo es ficticio: instituciones, personas, obras sociales e importes. El enlace y la clave se
entregan por el canal de la demo; no están en este documento.

| Min | Bloque | Cuenta |
|---|---|---|
| 0–1 | Apertura | — |
| 1–4 | Clínica: configuración | `admin@salud.local` en Hospital Central |
| 4–9 | Clínica: uso | la misma |
| 9–12 | Paciente | `andrea.paniagua@paciente.test`, en el portal del paciente, y `cardio.med@hospital.gob.ar` para llamarla |
| 12–15 | Financiador | `admin@mutualdelvalle.test`, en ventana privada |

## Antes de empezar

1. **Ventana 1:** entrá con `admin@salud.local`. Caés en **Instituciones**: en la fila de
   **Hospital Central**, **Ingresar**.
2. **Ventana 2, privada:** entrá con `admin@mutualdelvalle.test`. Dos pestañas de una misma
   ventana comparten la sesión; por eso tiene que ser otra ventana.
3. **Portal del paciente:** en el celular, o en el modo celular del navegador, abrí `/mi` →
   **Ingresar** y entrá con `andrea.paniagua@paciente.test` y la clave de la demo. Su
   sesión es aparte: no se mezcla con la del hospital aunque estén en el mismo navegador.
4. **Ventana 3, privada:** entrá con `cardio.med@hospital.gob.ar` (Laura Méndez, cardióloga de
   Central) y dejala en **Operación → Filas**, área Cardiología. Es la que llama a Andrea.
5. Si ensayaste, pedí que recarguen el entorno **con la misma ancla**. Lo que se opera en el
   ensayo queda con la hora real y desordena los datos.

## 0–1 · Apertura

**Decí:** «Les voy a mostrar tres miradas sobre la misma plataforma: la del hospital, la del
paciente y la de quien paga. Todos los nombres e importes son ficticios».

## 1–4 · Clínica: configuración

**Configuración → Flujos →** *Ingreso a Guardia*.

- **Señalá** el diagrama: Admisión administrativa → Triage de enfermería → Sala de espera →
  Conducta médica. Cada caja dice qué equipo la atiende.
- **Decí:** «El hospital dibuja su circuito y ese mismo diagrama es el sistema que usa el
  personal».
- **Señalá** el aviso amarillo: la versión publicada no se edita porque sostiene casos en curso;
  para cambiarla se saca una versión nueva. **Decí:** «Cambiar el circuito no rompe las
  atenciones que ya empezaron».
- **No toques** *Sacar una versión nueva* ni *Publicar*: crean o publican una versión de Central.

## 4–9 · Clínica: uso

**1. Operación → Fila de espera** (`/filas`), área Guardia · 1,5 min

- **Señalá** el orden: primero el caso **urgente** (Sergio Molina en esta carga), después el
  resto por llegada, con la espera de cada uno.
- Hay un aviso: el superadmin ve la fila pero **no puede llamar**; eso lo hace alguien del área.
  **Señalá** los botones *Llamar siguiente* de cada consultorio sin tocarlos. **Decí:** «Cada
  consultorio llama desde acá y el paciente ve el llamado en la pantalla de la sala».

**2. Pacientes → Historia clínica →** *Gustavo Aguirre* · 1,5 min

- **Señalá** las entradas con la etiqueta **Firmada**: cada una lleva profesional y matrícula.
- **Mostrá** las pestañas *Estudios* y *Recetas*, y *Quién la miró*.
- **Señalá** *Integridad → Verificar la historia*. **Decí:** «Si alguien cambia una entrada
  firmada, la historia lo detecta».

**3. Seguimiento → Casos →** el caso abierto de **Andrea Paniagua** · 2 min

Buscalo por nombre: el número cambia en cada carga. Es una *Radiografía ambulatoria de tórax*
de Consultorios externos, abierta hoy a las 08:01.

- En **Cobertura del caso**, **señalá** la afiliación verificada contra el padrón: Mutual del
  Valle, Plan Integral, afiliada MV00011.
- En *Prestaciones del paso actual*, **Consultar cobertura**. En esta carga da ARS 35.000 de
  importe, **ARS 24.500 a cargo del financiador** (70 %) y **ARS 10.500 a cargo del paciente**,
  con 2 usos disponibles del cupo anual. Consultar no reserva cupo.
- **Decí:** «Antes de hacer la prestación, la administrativa sabe cuánto paga la obra social y
  cuánto el paciente».
- Bajá a *Autorizaciones de este caso*: hay una solicitud **Pendiente** a Mutual del Valle. **Decí:**
  «Esa solicitud la vamos a ver del otro lado en un rato».

## 9–12 · Paciente

En el portal del paciente, con **Andrea Paniagua**: la misma persona del caso de radiografía.

1. **Inicio:** **señalá** su próximo turno (el primer horario libre a partir de tres días después de la carga; en
   la carga verificada, el lunes a las 08:00), en
   *Dra. Méndez · Cardiología*, **Hospital Central**. **Decí:** «Es la misma paciente que vimos en
   el hospital, con sus datos reales, de todas las instituciones donde se atendió».
2. En la tarjeta del turno, **Confirmar asistencia** y, en el turno, **Confirmar asistencia**. Pasá a la ventana 1, **Operación → Turnos**, y
   abrí ese día en la agenda de la Dra. Méndez: el turno dice **Confirmado por el paciente**.
   **Decí:** «Lo que hace el paciente llega al hospital en el acto. Nadie tuvo que llamarlo».
   No lo canceles: se consume el escenario.
3. **Resultados:** **señalá** la *Radiografía de tórax* «Solicitado el …, todavía sin resultado»,
   que es la del caso, y el *Hemograma completo* con resultado **Normal** → el ícono de descarga. **Decí:**
   «Baja el archivo que cargó el hospital, no un resumen armado aparte».
4. **Cobertura:** **señalá** Mutual del Valle, Plan Integral, **MV00011**, *Confirmada por tu
   institución*. **Decí:** «Es la misma afiliación que verificó la administrativa».
5. **Sala de espera:** Andrea está esperando en Cardiología. Dejá esa pantalla abierta en el
   celular y pasá a la ventana 3: en **Box 1**, **Llamar siguiente** (en esta carga llama a Luis
   Gómez, que está antes); en **Box 2**, **Llamar siguiente**: es Andrea. En menos de 10 segundos
   el celular muestra **Te están llamando · Box 2 · Hospital Central**. **Decí:** «Espera donde
   quiere; el aviso le llega al teléfono». Después, en cada caso, **Volver a la cola**: deja la
   demo como estaba.

**Si preguntan:** para crear su cuenta, el paciente valida la identidad con los datos del DNI
contra RENAPER. Sacar turno desde el portal todavía no está disponible.

## 12–15 · Financiador

Pasá a la **ventana privada** de `admin@mutualdelvalle.test`. El superadmin no puede entrar al
portal del financiador: no pertenece a ninguno y `/financiadores` lo devuelve al inicio.

1. **Autorizaciones → Pendientes:** **señalá** a **Andrea Paniagua**, la misma radiografía que
   quedó pendiente en Hospital Central, y a Carina Ojeda. **Decí:** «Lo que el hospital pidió
   llega acá, y la mutual lo responde con su propio acceso». Podés abrir *Revisar*, pero **no
   respondas**: se consume el escenario.
2. **Padrón de afiliados:** **señalá** los afiliados vigentes con su número (MV00001, MV00002…)
   y *Importar Excel*. **Decí:** «El padrón es de la mutual; el hospital lo consulta al admitir».
3. **Actividad en hospitales → Mes actual:** **señalá** el *Importe asignado* (en esta carga,
   ARS 86.900), las prestaciones realizadas y la reserva abierta. **Decí:** «La mutual ve lo que
   se hizo con sus afiliados en cada hospital, sin entrar a la historia clínica».

**Cierre (en una frase):** «La misma atención, vista por el hospital que la hace, el paciente que
la recibe y el financiador que la paga».

## Si algo no coincide

- **Esperas negativas o fechas futuras:** la carga está anclada al 01/10 a las 08:00. Antes de
  esa hora los datos quedan adelantados.
- **El financiador entra en *Planes* y no en *Inicio*:** es lo esperable hoy (lo cambia el #92).
  Andá directo a *Autorizaciones*.
- **Andrea no tiene autorización pendiente:** la respondieron en un ensayo. Mostrá a Carina Ojeda.
- **El turno de Andrea ya figura confirmado o cancelado:** lo usaron en un ensayo. Pedí que corran
  `seed_portal_demo`: le da un turno reservado nuevo sin tocar el resto de la carga.
- **Andrea no aparece en la fila de Cardiología, o el portal dice «No estás en una sala de
  espera»:** la atendieron o la dieron por ausente en un ensayo, o pasaron más de 24 horas desde la
  carga. `seed_portal_demo` la vuelve a poner en la sala. Si la llamaron y no la devolvieron a la
  cola, el portal sigue mostrando el llamado hasta 8 horas: **Volver a la cola** en su caso.
- **Internación:** si te piden mostrarla, no uses la vista *Todos*: en esta carga una paciente
  figura en dos camas a la vez y aparece una tarjeta roja «Conflicto». Filtrá por Pediatría.
- **Un número no coincide:** revisá institución, área, mes y filtros antes de citarlo. Si sigue
  sin coincidir, no lo cites.

Para recorridos más largos: [guion comercial completo](../entornos/guia-demo-comercial.md) y
[recorrido de financiadores](../entornos/guia-demo-financiadores.md). Para dejarle al comprador:
[recorrido del comprador](recorrido-comprador.md).
