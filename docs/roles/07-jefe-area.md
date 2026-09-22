# Rol: Jefe / supervisor de área

> Ordena la operación de **su** área: ve el trabajo, lo reasigna, lo prioriza, lo
> cancela y audita quién miró qué. Es el único rol que supervisa sin administrar.
> Técnicamente: membresía con rol `jefe_area`, acotada a una o más áreas.

**Usuario de demo:** `guardia.jefe@hospital.gob.ar` / `demo1234`

---

## 1. En una frase

Es quien responde cuando la guardia se traba: mira dónde se acumulan los casos, a
quién se le asignaron, qué paciente espera de más, y mueve las cosas de lugar.

## 2. Qué ve al entrar

Entra directo a su institución. Ve **TRABAJO** y **REGISTROS** completos, más el
Tablero y Supervisión. **No ve SISTEMA**: ni Estructura ni Administración.

> Esa exclusión está puesta a propósito. El Tablero se abre con `supervision` y no
> con `config_institucional` justamente para que el jefe de Guardia pueda mirar su
> propia espera promedio sin quedar habilitado a dar de alta usuarios del hospital.

## 3. Funcionalidades

#### 🟦 Inicio — Mi trabajo
- Sus tareas asignadas, lo tomable por sus grupos y las esperas vencidas.

#### 📊 Tablero
- Métricas del área: casos por paso, mapa del flujo, top de demoras.
- Avisa si un proceso de fondo se detuvo, y dice qué se rompe si eso pasa.

#### 👥 Supervisión
- Casos del área con su estado, paso, antigüedad y asignación.
- **Reasignar** a otra persona: exige que el destinatario tenga membresía activa y
  pueda tomar el paso actual.
- **Priorizar** como urgente: también reordena la fila si el caso está esperando.
- **Cancelar** un caso, con motivo. Avisa al responsable asignado.

#### 🗂️ TRABAJO
- **Casos**, **Turnos programados**, **Internación**, **Farmacia e insumos** y
  **Red y traslados**, con las mismas acciones que el personal de su área.
- Opera pasos del flujo si integra el grupo responsable del nodo.

#### 🩺 REGISTROS
- **Padrón de pacientes** e **Historia clínica** completas.
- **Legajo profesional** propio.
- **Registro de accesos**, acotado a las instituciones donde conduce.

## 4. Permisos

| Acción | Jefe de área |
|---|---|
| Ver el tablero y supervisar su área | ✅ |
| Reasignar, priorizar y cancelar casos | ✅ (de su área) |
| Operar casos, filas, turnos, internación, farmacia, traslados | ✅ |
| Ver historia clínica, solicitar estudios, emitir recetas | ✅ |
| Auditar accesos clínicos | ✅ (de su institución) |
| Firmar una atención | Según lo que declare el nodo |
| Diseñar o publicar flujos y formularios | ❌ |
| Administrar usuarios, membresías o estructura | ❌ |
| Operar Finanzas | ❌ salvo concesiones explícitas |

Capacidades: `trabajo`, `registros`, `supervision`, `auditoria`, `padron_admision`,
`historia_clinica`, `prescripcion`, `solicitud_estudios`, `turnos`, `casos_operar`,
`filas`, `internacion`, `farmacia_stock`, `traslados_red`.

## 5. Notas

- **Supervisa sólo su área.** Jefe en Guardia y no en Pediatría supervisa casos de
  Guardia, no de Pediatría.
- Es el rol con más capacidades operativas después del admin de institución, y a la
  vez el que no puede tocar la configuración. Esa combinación es intencional.
- Si además necesita operar Finanzas, hay que darle concesiones financieras
  explícitas: el rol no las incluye.
