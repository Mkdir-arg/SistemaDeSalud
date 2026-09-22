# Rol: Configurador

> El que **diseña los procesos**. Arma los flujos y formularios que después el motor
> ejecuta. **No opera casos, no ve pacientes y no toca la estructura.**
> Técnicamente: membresía con rol `configurador`.

**Usuario de demo:** `config.central@hospital.gob.ar` / `demo1234`

---

## 1. En una frase

Dibuja un proceso como diagrama —pasos, formularios, decisiones, derivaciones— y lo
publica; esa misma definición es la que el motor usa para generar las pantallas que
opera el personal. **Nadie programa una pantalla a mano.**

## 2. Qué ve al entrar

Entra directo a su institución. Su menú tiene **tres entradas**: Flujos, Mapa de
flujos y Formularios. No ve Estructura, Administración, Casos, Padrón, Historia
clínica, Internación, Farmacia, Red ni Finanzas.

> Es el rol más acotado en cuanto a menú y el más profundo en su mundo: el editor de
> flujos es la pantalla más rica del sistema.

## 3. Funcionalidades

#### Flujos (listado)
- Estado —publicado, borrador, reemplazado, archivado—, versión, casos activos y
  última edición, con filtros por estado y área.
- **Crear flujo**: nombre y ámbito (institución, área o subárea) → nace una **v1 en
  borrador** con un nodo Inicio.
- **Duplicar** y **abrir en el editor**.

#### Editor de flujos (`/flujos/:id`)
- **Lienzo** con grilla de puntos, zoom y paneo. Es deliberadamente distinto del
  mundo de ejecución: si la pantalla de ejecución parece un diagrama, está mal.
- **Trece tipos de nodo**: Inicio · Formulario · Decisión · Acción · Atención ·
  Derivar · Espera de fila · **Asignar cama** · Espera por tiempo · Estado ·
  **Notificación** · **Integración** · Fin.
- Arrastrar nodos —la posición se guarda— y conectarlos con flechas.
- **Panel de propiedades** por nodo: área y **grupos responsables**, qué formulario
  pide, área de destino de una derivación, sector de la cama, duración de la espera,
  estado que aplica, o el padrón FHIR externo que consulta un nodo de integración.
- **Constructor de reglas** en las decisiones: *campo · operador · valor*
  (`=`, `≠`, `>`, `<`, contiene) para bifurcar. Una conexión sin condición es la
  rama por defecto.
- **Quién firma cada atención**: el nodo declara los roles habilitados —médico,
  enfermería, administrativo o jefe de área— y si la firma exige matrícula. Si no lo
  declara, rige el default seguro: médico con matrícula.
- **Validar**: lista de errores y avisos —flujo sin Inicio o sin Fin, derivación sin
  área, decisión con campo inexistente, nodos sin salida, roles de firma que el
  sistema no reconoce—.
- **Publicar**: sólo si no hay errores. Marca las versiones anteriores como
  reemplazadas. Un caso en curso sigue corriendo sobre **su** versión.
- **Probar**: simula un caso recorriendo el flujo **sin crear datos reales**. Carga
  valores en los formularios, evalúa las decisiones con esos valores y avanza paso a
  paso hasta el Fin, resaltando el nodo actual.
- **Reproducir**: anima un token viajando por el camino de la última simulación.

#### Mapa de flujos
- Vista panorámica de cómo se encadenan los procesos de la institución.

#### Formularios
- Listado y constructor con **vista previa en vivo**: así lo verá quien lo complete.
- Campos con tipo —texto corto o largo, número con unidad y rango, fecha, selección
  única, archivo—, obligatoriedad, opciones y orden.
- **Duplicar** un formulario, **reordenar** campos y consultar **dónde se usa** antes
  de modificarlo o eliminarlo.

## 4. Permisos

| Acción | Configurador |
|---|---|
| Diseñar flujos, validar y publicar versiones | ✅ |
| Crear formularios y campos | ✅ |
| Ver el mapa de flujos | ✅ |
| Operar casos, filas, turnos, internación, farmacia, traslados | ❌ |
| Ver el padrón o la historia clínica | ❌ |
| Gestionar estructura organizativa, usuarios o membresías | ❌ |
| Ver el tablero o supervisar | ❌ |
| Operar Finanzas | ❌ salvo concesiones explícitas |

Capacidades: `diseno` y `diseno_flujos`. Nada más.

## 5. Notas

- **Diseña el proceso pero no la organización.** Puede asignar un área o un grupo a
  un nodo, pero no crear esa área ni ese grupo: eso es `config_institucional`, del
  admin de institución.
- Los flujos publicados no se editan directamente: se trabaja con versiones.
- Configurador construye el **qué** (la plantilla); el personal operativo ejecuta el
  **cómo** (los casos reales).
