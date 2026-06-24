# Modelo de datos

Dos mundos: **definición** (lo que diseña el configurador) y **ejecución** (lo que corre con datos reales), más **organización** y **registros**. Todo cuelga de una `Institución`; nada se mezcla entre instituciones.

## 1. Organización (Parte 1 + 2)

```
Institución
  id, nombre, tipo, estado(activa|en_alta|inactiva), contacto
  (autocontenida — sin agrupador por encima)

Área
  id, institucion_id, nombre, nivel(area|subarea),
  area_padre_id (null si es área de primer nivel),
  responsable_id (→ Usuario/Legajo), descripcion, estado
  REGLA: si nivel=subarea ⇒ area_padre_id != null
  REGLA: el área padre no puede tener padre (máx. 3 niveles con la institución)

AsignaciónStaff
  area_id, profesional_id (→ LegajoProfesional), rol_en_el_area(jefe|medico|administrativo)
  (staff explícito por nivel; sin herencia automática)
```

## 2. Definición (plantilla)

```
Flujo
  id, institucion_id, nombre, estado(borrador|publicado|archivado),
  version, pertenencia { nivel(institucion|area|subarea), area_id?, compartir_hacia_abajo:bool },
  estados: [ EstadoFlujo ]            // lista configurable, marca los de cierre

EstadoFlujo
  id, flujo_id, nombre, es_cierre:bool, orden

Nodo
  id, flujo_id, tipo, posicion {x,y}, propiedades (según tipo)

Conexión
  id, flujo_id, nodo_origen_id, nodo_destino_id, regla? (condición), etiqueta?

Campo  (dentro de un nodo Formulario/Atención)
  id, nodo_id, etiqueta, tipo, obligatorio:bool, orden,
  origen(manual|historia_clinica|legajo_ciudadano),
  valor_default?, ayuda?, opciones?[], validaciones?{ rango, formato, longitud }

VersiónFlujo
  id, flujo_id, version, estado, autor_id, fecha, nota
  (publicar una versión NO afecta casos en curso con versiones anteriores)
```

### Tipos de nodo (10)
| tipo | entradas/salidas | genera pantalla en ejecución | propiedades clave |
|---|---|---|---|
| `inicio` | 0 / 1 | no | estado inicial |
| `formulario` | 1 / 1 | **sí** | campos[] |
| `decision` | 1 / N | solo si manual | ramas[] (condición→destino) + rama por defecto; modo auto/manual |
| `accion` | 1 / 1 | no | tipo de acción (notificar, registrar) |
| `derivar` | 1 / 1 | no | flujo destino + área/sub-área destino; estado al derivar |
| `estado` | 1 / 1 | no | estado a asignar |
| `espera_fila` | 1 / 2 (atendido + ausente) | **sí** (operador) | nombre, orden FIFO+urgencia, área/operador, n° de turno |
| `espera_tiempo` | 1 / 1 | no | intervalo (fijo o relativo a un campo fecha), tope repeticiones, reactivación |
| `atencion` | 1 / 1 | **sí** | campos[] + escribe entrada en HC firmada; requisito de credencial |
| `fin` | 1 / 0 | no | estado final + etiqueta de resultado |

### Reglas (en Decisión)
Una condición compara un **campo** con un **valor**: operadores `= ≠ > < ≥ ≤ contiene`. Combinables con **Y / O**. El selector de campo ofrece solo campos cargados en pasos anteriores **+ datos de la historia clínica**. Cada salida condicional tiene su condición; hay una salida **por defecto** (no eliminable).

## 3. Ejecución (instancia)

```
Caso
  id, institucion_id, flujo_id, flujo_version,
  nodo_actual_id, estado_actual, area_asignada_id, administrativo_asignado_id?,
  paciente_id? (→ HistoriaClinica/Ciudadano), fecha_inicio, fecha_cierre?

DatoCargado
  id, caso_id, campo_id, valor, nodo_id (paso donde se cargó)

EventoHistorial   (trazabilidad — inmutable)
  id, caso_id, tipo(iniciado|dato|ingreso_fila|llamado|devuelto|ausente|
        derivacion|cambio_estado|atencion|espera_programada|cierre),
  descripcion, usuario_id, fecha_hora

ItemFila          (estado operativo de espera_fila)
  id, caso_id, nodo_id, turno(A-042), posicion, urgente:bool, ingreso_at, estado(en_espera|llamado|atendido|ausente)
```

## 4. Registros (longitudinales, sobreviven al caso)

```
Ciudadano (sistema externo — solo se referencia)
  id, documento, nombre, fecha_nac, domicilio, contacto

HistoriaClinica
  ciudadano_id (= identidad), antecedentes(alergias, condiciones, medicación, última visita)

EntradaHC = Atención     (nace de un nodo Atención dentro de un caso)
  id, paciente_id (→ HistoriaClinica), profesional_id (→ LegajoProfesional),
  caso_id, nodo_id, tipo(atencion|estudio|medicacion|diagnostico|entrega),
  titulo, contenido, fecha_hora        // INMUTABLE: se corrige con una entrada nueva

LegajoProfesional
  id, usuario_id, nombre, matricula, vigencia, especialidad, rol, areas[], estado
  // su "actividad" = las EntradaHC que generó + llamados de fila + casos atendidos

AccesoHC (auditoría)
  id, historia_id, usuario_id, accion(lectura|escritura), caso_id, fecha_hora
```

### El puente: la Atención
Una **Atención** (= nodo `atencion` ejecutado) produce una `EntradaHC` que pertenece simultáneamente a:
- la **historia clínica** del paciente (entrada nueva),
- el **legajo profesional** del que la ejecutó (actividad),
- la **trazabilidad** del caso (evento).

Los dos legajos no se vinculan directamente: se cruzan a través de cada Atención. Relación muchos-a-muchos mediada por el encuentro.

### Regla práctica de "dónde vive un dato"
- Vale para otros casos futuros del mismo **paciente** → Historia clínica.
- Es del **profesional** (credenciales/actividad) → Legajo profesional.
- Identidad de la persona → **Ciudadano** (externo); se referencia, no se duplica.
- Solo sirve para mover **este** trámite → el Caso (muere con él; la trazabilidad queda).

## 5. Conexiones clave con el módulo Flujos
- **Campos vinculados:** un Campo con `origen = historia_clinica | legajo_ciudadano` se trae de solo lectura / valor inicial.
- **Elegibilidad:** un nodo (típicamente Atención) puede exigir una condición del Legajo profesional (ej. matrícula vigente).
- **Reglas con datos clínicos:** las Decisiones pueden referenciar datos de la HC además de los cargados en el caso.
- **Derivaciones:** el caso pasa al inicio del flujo destino **conservando sus datos** y aparece en la bandeja "sin asignar" del área destino.
