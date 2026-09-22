# Modelo de datos

> El mapa de entidades del sistema: **93 modelos en 13 apps**. Verificado contra el
> código el 22/09/2026.
>
> No reemplaza a `models.py`, que es la fuente. Sirve para ubicarse: qué existe, de
> qué cuelga y qué regla lo gobierna.

El modelo del entregable de diseño, `diseño/docs/05-modelo-de-datos.md`, es de junio
y cubre cinco apps. Este lo reemplaza.

---

## El principio que ordena todo

**Plantilla** frente a **caso**:

```
Flujo ──> VersionFlujo ──> Nodo ──> Conexion        ← definición: lo que se diseña
                │
                └──> Caso ──> EventoCaso            ← ejecución: lo que corre
```

El configurador dibuja una `VersionFlujo` con sus nodos. Un `Caso` es una instancia
de **una versión concreta**: publicar una nueva no altera los casos en curso. El
motor usa la misma definición para dibujar el lienzo y para renderizar las pantallas
que opera el personal.

El segundo principio: **todo cuelga de una `Institucion`** y nada se mezcla entre
instituciones. La única excepción es la `Red`, que existe justamente para vincularlas.

---

## 1. Identidad y organización

### `accounts`

| Modelo | Qué es |
|---|---|
| `Usuario` | Login por email. Es el `AUTH_USER_MODEL` |
| `Membresia` | **La pieza central de permisos**: relaciona usuario + institución + rol, con sus áreas. Una persona puede tener varias, con roles distintos en instituciones distintas |
| `LegajoProfesional` | Matrícula y especialidad del profesional |

Los permisos **no viven en el usuario**: viven en la membresía. Un rol abre puertas
en *una* institución. Ver [`ROLES-Y-PERMISOS.md`](ROLES-Y-PERMISOS.md).

### `instituciones`

```
Institucion
  └── Area
        ├── Subarea
        ├── Grupo ──(integrantes)── Membresia
        ├── Box
        └── Cama ──> EstadiaCama
```

| Modelo | Regla que lo gobierna |
|---|---|
| `Institucion` | **No se borra.** La auditoría clínica y los flujos la protegen; la única baja es la de estado |
| `Area` | La unidad funcional principal: flujo, supervisión, agenda y derivaciones se acotan acá |
| `Grupo` | Equipo dentro de un área. Sólo admite personas de esa área. Es lo que un nodo declara para restringir quién opera ese paso |
| `Box` | Libre u ocupado por un caso. Llamar ocupa; marcar ausente libera |
| `Cama` | Una cama ocupada **siempre** tiene caso asociado |
| `EstadiaCama` | Un pase cierra la estadía anterior y abre una nueva |

---

## 2. Definición del proceso

### `formularios`

`Formulario` → `Campo`. Un formulario se reutiliza en varios pasos; la pantalla de
detalle muestra dónde se usa antes de modificarlo.

### `flujos`

| Modelo | Notas |
|---|---|
| `Flujo` | Pertenece a la institución, a un área o a una subárea. Fijar la subárea **deriva el área** para que los filtros sigan funcionando |
| `VersionFlujo` | Estados: borrador, publicada, reemplazada, archivada. Tiene tipo de circuito: guardia o programado |
| `Nodo` | **13 tipos**: inicio, formulario, decisión, acción, atención, derivar, espera de fila, asignar cama, espera por tiempo, estado, notificación, integración, fin |
| `Conexion` | Lleva la condición de una decisión: campo · operador · valor. Sin condición es la rama por defecto |

La configuración de un nodo (`Nodo.config`) decide cosas que cambian el permiso:
qué grupos lo operan, **quién puede firmar** una atención y si exige matrícula, y si
el paso exige la aceptación del copago antes de avanzar.

### `casos`

| Modelo | Qué es |
|---|---|
| `Caso` | La instancia en ejecución. Concentra estado, prioridad, nodo actual, área y asignación |
| `ValorCampo` | Lo completado en cada formulario del recorrido |
| `ItemFila` | La cola de un nodo de espera. Orden por prioridad y llegada |
| `EventoCaso` | **La línea de tiempo.** Es evidencia funcional y clínica: quién hizo qué y cuándo |
| `Notificacion` | Aviso personal in-app. No se acota por institución: es del usuario |

---

## 3. Registros clínicos

### `registros`

```
Ciudadano ──> HistoriaClinica ──> EntradaHistoria
     │                        ├──> Estudio ──> ArchivoClinico
     │                        └──> Receta
     └──> ConsentimientoDatos
```

| Regla | |
|---|---|
| Documento único | No vacío, único por institución |
| Dos permisos distintos | `Ciudadano` y `ConsentimientoDatos` se leen con `padron_admision`; el resto exige `historia_clinica` |
| Sello encadenado | Cada `EntradaHistoria` firmada lleva autor, matrícula y un sello que encadena con la anterior. Es lo que permite demostrar que la historia no se alteró |
| Archivos | Los adjuntos clínicos **no se sirven por `/media`**: salen por un endpoint que valida permisos |

---

## 4. Operación

### `agenda`

`Agenda` → `Disponibilidad` · `Bloqueo` · `Turno`. La agenda y sus disponibilidades
son configuración (`config_institucional`); operar turnos y bloqueos es `turnos`.

Estados del turno: reservado, confirmado, presente, ausente, cancelado. **Ausente no
libera el horario**: la oportunidad de atención se perdió.

### `farmacia`

```
Insumo ──> Lote
Deposito ──> Existencia <── Lote
         └─> Movimiento          (ingreso · consumo · transferencia · ajuste · baja)
         └─> Pedido ──> LineaPedido
```

**La existencia es resultado de los movimientos**, no al revés: los movimientos son
inmutables y son la evidencia. Un consumo puede imputarse a un caso, y eso es lo que
permite responder «se retira este lote, a quién se le aplicó».

### `red`

`Red` agrupa instituciones; `Traslado` vincula dos. Estados: solicitado, aceptado,
rechazado, en camino, recibido, cancelado, fallido.

**Los casos siguen perteneciendo a cada institución**: aceptar abre un caso nuevo del
lado del destino, no mueve el original.

### `auditoria`

| Modelo | Qué es |
|---|---|
| `AccesoClinico` | Quién leyó qué dato clínico, de qué paciente, desde qué institución, cuándo y con cuántos resultados. Incluye lo que entra por FHIR |
| `Latido` | El pulso de los procesos de fondo. Es lo que contesta `/api/estado/` |

---

## 5. Dinero

### `finanzas` — 27 modelos

Es la app más grande. Conviene leerla en cinco bloques.

**Permisos y auditoría**

| Modelo | |
|---|---|
| `ConcesionFinanciera` | **18 acciones**, ligadas a una membresía, con sus áreas y si alcanzan información sensible. Finanzas no se gobierna por capacidades |
| `AccesoFinanciero` | Registro de cada consulta financiera autorizada, por área y sensibilidad |

**Costos por atención**

`Prestacion` → `DefinicionComponente` → `ValorComponente` (vigente desde).
Al completarse una atención se crea un `HechoAtencionCosteable`, con sus
`ComponenteEsperadoHecho` e `ImputacionCosto`. `PendienteCosteo` es lo que el
proceso de fondo recupera.

> Cambiar hoy un valor **no modifica los costos históricos**: cada hecho conserva lo
> que regía el día de la atención.

**Gastos**

`ConceptoGasto` → `Gasto`, con `ExpectativaGasto` (lo que un área espera cargar cada
mes) e `IndicacionCargaGasto` (si esa carga se declaró completa).

**Reparto**

`CoberturaActividadCosteable` (si el ámbito está habilitado) + `ReglaRepartoActividad`
→ `RepartoGasto` → `AtribucionReparto`. `TrabajoReparto` es la cola durable que
procesa el servicio de fondo.

El ámbito puede ser un área o **la institución completa**.

**Cobros y dinero**

`PoliticaCobro` (si se cobra y cuánto) → `SnapshotCobroAtencion` → `PendienteCobro`
→ `ObligacionFinanciera` → movimientos.

`RegistroFinancieroAprobable` y `RegistroDineroInmutable` son las bases que imponen
dos invariantes: lo pendiente de aprobación reserva su límite pero no cuenta como
confirmado, y **un movimiento de dinero no se edita ni se borra**: se corrige con
otro movimiento.

### `financiadores` — 23 modelos

```
Financiador ──> MembresiaFinanciador        (sus usuarios, aparte de las del hospital)
    ├──> Plan ──> ReglaCobertura            (porcentaje · cupo · período · vigencia)
    ├──> Afiliado ──> HistorialAfiliacion
    │        └──> VinculoCiudadano ──> registros.Ciudadano
    ├──> Convenio ──> ArancelConvenio       (excepción al arancel del hospital)
    └──> ConsumoExterno                     (uso fuera de Salud, informado)

casos.Caso ──> AfiliacionCaso ──> ReservaCobertura ──> DistribucionCobro
                                         │                  └──> ResolucionSaldo
                                         └──> UsoAutorizacion ──> SolicitudAutorizacion
```

| Invariante | |
|---|---|
| Identidad | `PrestacionComun` es el catálogo de referencia; `VinculoPrestacion` lo relaciona con la prestación del hospital. **Nunca por coincidencia de nombre** |
| Afiliación del caso | `AfiliacionCaso` se conserva durante ese caso aunque la afiliación cambie o venza |
| Cupo | Se calcula sobre consumos externos + reservas activas. Se comparte entre hospitales y es independiente por financiador |
| Reserva | Pasa a consumo **una sola vez**. Reintentos y recuperación no duplican |
| Distribución | Las partes suman exactamente el arancel por la cantidad. La del paciente se obtiene **por diferencia** |
| Evidencia | `EventoCobertura` audita sin datos de la historia clínica |

### `fhir`

**No tiene modelos.** Es una fachada de sólo lectura que proyecta `Ciudadano`,
`Caso`, `Institucion` y las afiliaciones vigentes como `Patient`, `Encounter`,
`Organization` y `Coverage`.

---

## Cómo leerlo desde el código

La lista autoritativa la da Django, no un `grep`: varios modelos heredan de bases
propias (`RegistroDineroInmutable`, `RegistroFinancieroAprobable`) y un `grep` de
`models.Model` se los saltea.

```bash
docker compose exec backend python -c "
from django.apps import apps
for cfg in apps.get_app_configs():
    if cfg.name.startswith('apps.'):
        print(cfg.label, sorted(m.__name__ for m in cfg.get_models()))
"
```

El esquema de la API es la vista externa de todo esto:
<http://localhost:8000/api/docs/>.

Las migraciones son el historial real: `backend/apps/<app>/migrations/`. Finanzas va
por la 26 y financiadores por la 7.
