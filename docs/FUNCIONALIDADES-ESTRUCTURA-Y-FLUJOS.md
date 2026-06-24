# Funcionalidades — Estructura organizativa y ámbito de flujos

> Documento de funcionalidades incrementales sobre **estructura organizativa**
> (áreas, sub-áreas, grupos de staff) y **alcance de los flujos**.
> Última actualización: **2026-06-24**.

Complementa `ESTADO-DEL-PROYECTO.md`. Resume **qué hace** cada funcionalidad,
**dónde vive** en el código (backend y frontend) y **qué reglas** la gobiernan.

---

## Resumen

| # | Funcionalidad | Backend | Frontend |
|---|---|---|---|
| 1 | Estructura: tabla de áreas + ficha en panel (drawer) | `/areas/`, `/subareas/` | Pantalla `/estructura` |
| 2 | Ámbito de un flujo (institución / área / sub-área) | `Flujo.subarea` + `ambito` | Crear flujo, listado y editor |
| 3 | Grupos de staff por área | modelo `Grupo` + `/grupos/` | Pestaña **Grupos** del área |
| 4 | Aviso de pertenencia a grupos | (deriva de `Grupo.integrantes`) | Pestaña **Staff** y modal **Gestionar** |

---

## 1. Estructura: tabla de áreas + ficha en panel (drawer)

La pantalla `/estructura` ([`Areas.jsx`](../frontend/src/pages/admin/Areas.jsx)) es
una **tabla de áreas** (nombre, responsable, staff, sub-áreas) y, al hacer clic en
una fila, abre un **panel lateral (drawer)** con la **ficha del área**. La ficha
tiene un botón **Editar** y un botón de acción **contextual según la solapa**:
Datos / Staff / Grupos / Sub-áreas.

> Antes era un árbol con papelera al pasar el mouse; se rediseñó a tabla + drawer
> para ahorrar espacio y quitar la redundancia con el menú de Flujos (se eliminó la
> solapa "Procesos" de la ficha).

### Eliminar áreas y sub-áreas
- **Áreas:** acción de papelera en cada fila de la tabla; abre un modal de
  confirmación (`EliminarModal`).
- **Sub-áreas:** se eliminan desde la **ficha propia** de la sub-área (ver abajo).
- **Backend:** `AreaViewSet` / `SubareaViewSet` son `ModelViewSet`, `DELETE` ya
  estaba soportado. Eliminar un área borra en cascada sus sub-áreas (`CASCADE`); el
  modal lo advierte. Si el backend rechaza el borrado, el modal muestra el detalle
  del error en lugar de fallar en silencio.

### Solapa Staff — asignar y **quitar** profesionales
- Lista los profesionales del área (membresías cuyo `areas` incluye esta área) con
  rol y badges de grupos que integra.
- **Asignar profesional** (acción contextual): elige persona + **función en el área**
  (Administrativo / Médico). Si ya tiene esa función en la institución, se le suma el
  área; si no, crea la membresía.
- **Quitar:** saca esta área de la membresía de la persona; si era su **única** área,
  elimina la membresía completa (`PATCH`/`DELETE /membresias/{id}/`).

### Solapa Sub-áreas — **ficha propia** de cada sub-área
- Las sub-áreas se listan como tarjetas con su **contador de flujos**.
- Al hacer clic en una sub-área se entra a su **ficha**: **Renombrar**
  (`PATCH /subareas/{id}/`), lista de **flujos vinculados** (los flujos cuyo
  `subarea` apunta a ella) y **Eliminar sub-área** (con confirmación inline).

**Piezas de diseño reutilizables:**
- Icono `trash` en [`components/icons.jsx`](../frontend/src/components/icons.jsx).
- Variante `danger` del `Button` en [`components/ui.jsx`](../frontend/src/components/ui.jsx).
- Token de color `danger` (`#B42318`) en [`theme.js`](../frontend/src/theme.js).
- Componente `Table` y panel `drawer` (overlay fijo a la derecha) en `Areas.jsx`.

---

## 2. Ámbito de un flujo: institución / área / sub-área

Un flujo puede ser un **proceso general** (de toda la institución o de un área) o
un **proceso específico de una sub-área**.

### Modelo — [`backend/apps/flujos/models.py`](../backend/apps/flujos/models.py)

Se agregó `Flujo.subarea` (FK opcional a `instituciones.Subarea`, `SET_NULL`). Las
tres jerarquías quedan así:

| Ámbito | `area` | `subarea` | Significado |
|---|---|---|---|
| `institucion` | nula | nula | Proceso de toda la institución |
| `area` | seteada | nula | Proceso general del área |
| `subarea` | (derivada) | seteada | Proceso específico de la sub-área |

Reglas en el modelo:
- `save()` **deriva el área** desde la sub-área: si se fija `subarea`, `area` se
  completa con `subarea.area`. Así los filtros y listados por área siguen
  funcionando aunque el flujo sea de una sub-área.
- Propiedad `ambito` → `"institucion" | "area" | "subarea"`.

### API — serializer y viewset

- [`flujos/serializers.py`](../backend/apps/flujos/serializers.py): el
  `FlujoSerializer` expone `subarea`, `subarea_nombre`, `ambito` y `ambito_label`
  (ej. *"Cardiología › Hemodinamia"*). `validate()` rechaza una sub-área que **no
  pertenezca** al área indicada.
- [`flujos/views.py`](../backend/apps/flujos/views.py): `FlujoViewSet` filtra por
  `subarea` (`/api/flujos/?subarea=3`) y la incluye en `select_related`.
- **Migración:** `flujos/0002_flujo_subarea`.

### Frontend

- **Crear flujo** ([`pages/diseno/Flujos.jsx`](../frontend/src/pages/diseno/Flujos.jsx)):
  el modal "Nuevo flujo" muestra el selector de sub-área **solo si** el área
  elegida tiene sub-áreas, con una leyenda dinámica del alcance
  (institución / general del área / específico de la sub-área).
- **Listado:** la columna de área muestra el ámbito como `Área › Sub-área`.
  Duplicar un flujo conserva su sub-área.
- **Editor** ([`pages/diseno/FlujoEditor.jsx`](../frontend/src/pages/diseno/FlujoEditor.jsx)):
  el encabezado muestra `ambito_label` junto al título.

> Nota: el ámbito se define al **crear** el flujo. Cambiarlo después (mover un
> flujo de un nivel a otro) es un pendiente: el backend ya lo soporta vía
> `PATCH /flujos/{id}/`, falta la UI.

---

## 3. Grupos de staff por área

Un **grupo** es un equipo de trabajo dentro de un área (ej. *"Guardia mañana"*,
*"Comité de ablación"*) que agrupa personas del área. Pensados para usarse luego
como destinatarios en los flujos.

**Decisiones de diseño:**
- Alcance: **por área** (cada grupo pertenece a un área).
- Miembros: **solo personas del área** (con membresía en la institución y esa
  área asignada).
- Sin rol/función: el grupo es nombre + integrantes.

### Modelo — [`backend/apps/instituciones/models.py`](../backend/apps/instituciones/models.py)

```python
class Grupo(models.Model):
    area = FK(Area, CASCADE, related_name="grupos")
    nombre = CharField(max_length=150)
    descripcion = TextField(blank=True)
    miembros = M2M("accounts.Usuario", related_name="grupos")
    activo = BooleanField(default=True)
    creado = DateTimeField(auto_now_add=True)
    # unique_together = (area, nombre)
```

- **Migración:** `instituciones/0005_grupo`.
- **Admin:** `GrupoAdmin` con selector horizontal de miembros
  ([`instituciones/admin.py`](../backend/apps/instituciones/admin.py)).

### API — [`instituciones/serializers.py`](../backend/apps/instituciones/serializers.py) · [`views.py`](../backend/apps/instituciones/views.py)

- `GrupoViewSet` → `/api/grupos/`, filtrable por `area` y `activo`
  (`/api/grupos/?area=1`), con scope por institución (`area__institucion`).
- `GrupoSerializer`:
  - Lectura: campo `integrantes` con `{id, nombre, email}` de cada miembro.
  - Escritura: `miembros` (lista de IDs).
  - `validate()` rechaza miembros que **no pertenezcan al área** del grupo
    (verifica contra `Membresia` de esa institución + área).

### Frontend — [`pages/admin/Areas.jsx`](../frontend/src/pages/admin/Areas.jsx)

Nueva pestaña **Grupos** en la ficha de cada área, con acción contextual
**"Crear grupo"**.

- `GruposTab`: lista los grupos del área; cada tarjeta muestra nombre,
  descripción, cantidad de integrantes y sus avatares.
- `GrupoModal`: crear grupo (nombre + descripción).
- `MiembrosModal` (botón **Gestionar**): checklist del staff del área para
  agregar/quitar integrantes. Solo aparecen las personas asignadas al área —
  alineado con la validación del backend.
- `EliminarGrupoModal`: borrado con confirmación.
- `useStaffDeArea(area)`: hook que arma la lista de personas elegibles
  (una por usuario) a partir de las membresías cuya lista de áreas incluye el área.

---

## 4. Aviso de pertenencia a grupos

Para evitar confusiones al armar equipos, la pertenencia a grupos se muestra en
dos lugares (solo informativo, no bloquea):

- **Pestaña Staff** (`StaffTab`): cada persona que integra uno o más grupos del
  área muestra un badge azul — `👥 <grupo>` si es uno, `👥 N grupos` si son
  varios. El tooltip lista todos.
- **Modal Gestionar** (`MiembrosModal`): al editar los integrantes de un grupo,
  cada persona que ya está en **otro** grupo del área muestra un badge ámbar
  (`👥 En otro grupo` / `En N grupos`) con tooltip de cuáles.

Ambos cálculos derivan de `Grupo.integrantes` ya cargado (sin pedidos extra al
backend): `StaffTab` consulta `/grupos/?area=X` junto con las membresías, y
`MiembrosModal` reutiliza la lista de grupos de `GruposTab`.

---

## Próximos pasos

- [ ] **Usar grupos en los flujos:** que un nodo (tarea / derivación) pueda
      asignarse a un `Grupo`, de modo que cualquier integrante tome el caso.
- [ ] **Cambiar el ámbito de un flujo** ya creado desde la UI (mover entre
      institución / área / sub-área). El backend ya lo soporta.
