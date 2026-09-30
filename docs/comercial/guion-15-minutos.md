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
| 9–12 | Paciente | ninguna: la app para pacientes |
| 12–15 | Financiador | `admin@mutualdelvalle.test`, en ventana privada |

## Antes de empezar

1. **Ventana 1:** entrá con `admin@salud.local`. Caés en **Instituciones**: en la fila de
   **Hospital Central**, **Ingresar**.
2. **Ventana 2, privada:** entrá con `admin@mutualdelvalle.test`. Dos pestañas de una misma
   ventana comparten la sesión; por eso tiene que ser otra ventana.
3. **App para pacientes:** abrí `/demo/app-clinica` en el celular o en el modo celular del
   navegador.
4. Si ensayaste, pedí que recarguen el entorno **con la misma ancla**. Lo que se opera en el
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

En la app para pacientes:

1. **Empezar** (o *Ingresar*) → DNI **34521521**. La app reconoce a **Martina Sosa** y pide un
   código de 6 dígitos: escribí cualquiera. **Sí, soy yo**.
2. **Inicio:** **señalá** el turno de hoy (Clínica médica con la Dra. Paula Ríos) y el aviso de
   un resultado listo.
3. **Sacar otro turno →** Pediatría → Dra. Laura Molina → un horario → **Continuar**. **Señalá**
   *A pagar en la clínica*: copago de OSDE 210, $ 3.500. **Decí:** «El paciente sabe cuánto va a
   pagar antes de confirmar».
4. Volvé al inicio → **Dar presente** → **Dar presente**. **Señalá** *Estás en la fila 3.º* y
   el aviso de a qué consultorio lo van a llamar. **Decí:** «Avisa que llegó sin pasar por
   recepción y espera donde quiere».
5. **Resultados →** *Análisis de sangre completo*.

**Nota interna, no para decir:** la app es una versión de demostración, con datos propios.
Martina Sosa y OSDE 210 no son los pacientes ni las coberturas de Central, y lo que se hace ahí
no escribe en el hospital. No digas que es la misma persona que viste en Central. Si
preguntan por la puesta en marcha, contestá: «El acceso definitivo y la integración con la
historia clínica y los turnos de su institución se definen en la implementación».

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
- **Internación:** si te piden mostrarla, no uses la vista *Todos*: en esta carga una paciente
  figura en dos camas a la vez y aparece una tarjeta roja «Conflicto». Filtrá por Pediatría.
- **Un número no coincide:** revisá institución, área, mes y filtros antes de citarlo. Si sigue
  sin coincidir, no lo cites.

Para recorridos más largos: [guion comercial completo](../entornos/guia-demo-comercial.md) y
[recorrido de financiadores](../entornos/guia-demo-financiadores.md). Para dejarle al comprador:
[recorrido del comprador](recorrido-comprador.md).
