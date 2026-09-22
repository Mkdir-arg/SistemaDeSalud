# Rol: Administrativo

> Mostrador, admisión y gestión operativa. Hace correr los casos, atiende la fila y
> mantiene la ficha administrativa del paciente.
> **No ve la historia clínica.**
> Técnicamente: membresía con rol `administrativo`.

**Usuario de demo:** `guardia.adm@hospital.gob.ar` / `demo1234`

---

## 1. En una frase

Recibe al paciente, lo registra o lo encuentra en el padrón, abre o continúa su
caso, lo llama de la fila y lo deriva — sin acceder a lo que el profesional escribe
sobre él.

## 2. Qué ve al entrar

Entra directo a su institución. Su menú muestra **Inicio**, **Casos**, **Turnos
programados**, **Red y traslados**, **Padrón de pacientes**, **Legajo profesional** y
**Coberturas y copagos**.

No ve Estructura, Administración, Flujos, Formularios, Tablero, Supervisión,
Internación, Farmacia ni Historia clínica.

> Bandeja y Filas no están en el menú a propósito: son la cola de lo que le toca
> **ahora** y se operan desde **Mi trabajo**, en Inicio. «Casos» sí está en el menú,
> porque responde otra pregunta: buscar un caso que **no** es su tarea pendiente
> —llama el paciente y pregunta, hay que revisar algo de ayer—.

## 3. Funcionalidades

#### 🟦 Inicio — Mi trabajo
- **Mis casos**, lo **tomable** por sus grupos y las **esperas vencidas**.
- **Tomar** un caso sin asignar. **Continuar** uno propio.
- **+ Nuevo caso**: elegir un flujo publicado y un paciente.

#### Ejecución del caso (`/casos/:id`)
- **Stepper** de progreso y **panel del paso actual**, que se dibuja desde la
  definición del nodo: formulario a completar, espera de fila para llamar, espera por
  tiempo para reactivar.
- **Línea de tiempo**: quién hizo qué y cuándo.
- **Cobertura del caso**: elegir la afiliación al ingresar —verificada, pendiente o
  particular—, consultar cuánto cubre el financiador y cuánto queda a cargo del
  paciente, y registrar su aceptación si tiene ese permiso.
- El motor resuelve solo las decisiones y derivaciones según las reglas del flujo.

#### Filas de espera
- Cola ordenada por prioridad y llegada. **Llamar al siguiente**, rellamar, devolver
  a la cola, marcar ausente. Llamar ocupa un box; marcar ausente lo libera.

#### Turnos programados
- Reservar, confirmar, cancelar, marcar ausente, cambiar modalidad y reprogramar.
- **Registrar la llegada**, que abre un caso si la agenda tiene flujo asociado.

#### Red y traslados
- Solicitar un traslado desde un caso, cancelarlo, marcarlo en camino; y del lado
  destino, aceptar, rechazar o recibir.

#### Padrón de pacientes
- Listado con buscador por nombre o documento. **+ Crear registro**.
- **Ficha administrativa**: documento, código, fecha de nacimiento, domicilio, alta
  en padrón, cobertura y consentimiento de tratamiento de datos.

#### Legajo profesional
- Su propia actividad: casos atendidos, llamados de fila, movimientos recientes.

## 4. Permisos

| Acción | Administrativo |
|---|---|
| Operar casos: tomar, iniciar, avanzar, llamar, devolver, marcar ausente | ✅ |
| Crear casos a partir de flujos publicados | ✅ |
| Crear pacientes y mantener la ficha administrativa | ✅ |
| Registrar y revocar el consentimiento de datos | ✅ |
| Operar turnos y traslados | ✅ |
| Elegir la afiliación del caso y consultar cobertura | ✅ |
| **Ver historia clínica, evolución, alergias, estudios o recetas** | ❌ |
| **Solicitar estudios** | ❌ |
| **Emitir recetas** | ❌ |
| **Operar internación o el stock de farmacia** | ❌ |
| Firmar una atención | ❌ |
| Ver el tablero o supervisar | ❌ |
| Diseñar flujos o formularios | ❌ |
| Administrar usuarios o estructura | ❌ |

Capacidades: `trabajo`, `registros`, `padron_admision`, `turnos`, `casos_operar`,
`filas`, `traslados_red`.

## 5. La distinción que más se malinterpreta

**Padrón no es historia clínica.** Son dos capacidades separadas
(`padron_admision` y `historia_clinica`) justamente para que el mostrador pueda
identificar a una persona, tomarle los datos y abrirle el caso sin leer lo que el
médico escribió. El administrativo tiene la primera y no la segunda.

Si la institución necesita que alguien de admisión vea la historia clínica, eso no se
resuelve con este rol: hay que darle otro.

## 6. Administrativo vs. médico

Comparten casi todo el mundo operativo. Lo que los distingue: el médico **firma
atenciones, prescribe, solicita estudios y ve la historia clínica**. Ver
[`10-medico.md`](10-medico.md).
