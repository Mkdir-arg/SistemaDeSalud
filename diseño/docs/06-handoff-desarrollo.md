# Handoff de desarrollo

Guía para llevar este prototipo a producción. El prototipo de diseño (`*.dc.html`) es la **fuente de verdad visual**; este documento traduce qué construir y en qué orden.

## 1. Naturaleza del prototipo

- Los `.dc.html` son prototipos de **diseño** (HTML + un runtime liviano de render declarativo). **No son el código de producción** ni un backend.
- Sirven como: referencia visual pixel-a-pixel, especificación de interacción y catálogo de estados. Tomá de ahí estilos exactos (colores, espaciados, copys) — están centralizados en `docs/02-sistema-de-diseno.md`.

## 2. Stack sugerido

| Capa | Sugerencia | Por qué |
|---|---|---|
| Frontend | React + TypeScript + Vite | Componentes; el diseño ya está pensado en componentes |
| Estilos | CSS variables (tokens de `02-sistema-de-diseno.md`) + CSS Modules / Tailwind con tema custom | Tokens ya definidos |
| Lienzo del diseñador | React Flow (xyflow) | Nodos, conexiones, zoom, paneo, minimapa de fábrica |
| Forms / runtime | Render dirigido por la definición del flujo (form schema → UI) | Es el corazón: "el diseño se vuelve pantalla" |
| Backend | API REST/GraphQL + Postgres | Multi-tenant por institución |
| Auth | Roles por institución (RBAC) | Ver matriz de permisos |

> El lienzo (React Flow) y el motor de render de formularios son las dos piezas con mayor riesgo técnico: prototipar primero.

## 3. Multi-tenant

- Toda entidad operativa/definición cuelga de `institucion_id`. Filtrar **siempre** por la institución del contexto.
- Super admin: scope global (directorio, alta, "ingresar a"). Admin de institución: scope fijo a su institución.
- La identidad del ciudadano vive en un **sistema externo**; integrarlo por `ciudadano_id` (no duplicar datos demográficos).

## 4. El motor (lo distintivo)

Una sola **definición de flujo** alimenta dos renders:
1. **Diagrama** (diseñador): nodos + conexiones sobre el lienzo.
2. **Pantallas de ejecución**: el motor recorre la definición y, según el `tipo` de nodo actual, renderiza la pantalla correspondiente (formulario, decisión manual, fila, atención) — sin pantallas hardcodeadas.

Estados del motor por caso: `nodo_actual_id` + `estado_actual`. Avance:
- `formulario`/`atencion`: valida obligatorios → asienta `DatoCargado` (y `EntradaHC` si es atención) → pasa al siguiente nodo.
- `decision`: si automática, evalúa reglas (datos del caso + HC) y toma la rama; si manual, pide destino.
- `derivar`: mueve el caso al inicio del flujo/área destino conservando datos.
- `espera_fila`: retiene; avanza por acción del operador (atendido) o sale por "ausente".
- `espera_tiempo`: agenda reactivación; estado "En espera programada"; un job lo reactiva al vencer.
- `estado`: cambia `estado_actual`. `fin`: cierra.

Cada transición escribe un `EventoHistorial` inmutable.

## 5. Orden de construcción sugerido

1. **Fundaciones:** tokens/tema, layout shell (sidebar + header + contexto), auth/roles, modelo `Institución`/`Área`.
2. **Definición:** CRUD de `Flujo` + diseñador (React Flow) con los 10 nodos, panel de propiedades, validación viva, versionado.
3. **Constructor de formularios** + render dirigido por schema (con campos vinculados a HC/ciudadano). Esto desbloquea ejecución.
4. **Motor de ejecución:** instanciar casos, avanzar por nodos, bandeja, ejecución de caso (stepper + expediente), derivaciones.
5. **Fila** (operador) y **espera por tiempo** (jobs/scheduler).
6. **Registros:** Historia clínica (entradas inmutables + auditoría) y Legajo profesional; enganchar el nodo Atención.
7. **Trazabilidad** (timeline desde `EventoHistorial`) + **Casos** (consulta).
8. **Estructura organizativa** (árbol 3 niveles, staff, pertenencia de flujos) + **Administración** (usuarios/áreas).
9. **Mapa de flujos**, **simulación ("Probar")**, **historial de versiones** comparar/restaurar.

## 6. Superficie de API (orientativa)

```
# Plataforma (super admin)
GET    /instituciones
POST   /instituciones
GET    /instituciones/:id

# Definición (scope institución)
GET    /flujos?area=&estado=
POST   /flujos
GET    /flujos/:id            # nodos + conexiones + estados
PUT    /flujos/:id
POST   /flujos/:id/publicar   # valida; 422 con lista de problemas si hay errores
GET    /flujos/:id/versiones
POST   /flujos/:id/simular    # recorrido en seco con datos ficticios

# Ejecución
GET    /casos?area=&estado=&asignacion=
POST   /casos                 # instancia un flujo
GET    /casos/:id             # estado + datos acumulados + paso actual
POST   /casos/:id/avanzar     # completa el paso actual (payload de campos)
POST   /casos/:id/derivar
GET    /casos/:id/historial   # timeline inmutable
GET    /filas/:nodo_id        # cola; POST /filas/:id/llamar | /finalizar | /devolver | /ausente

# Registros
GET    /historias/:ciudadano_id        # antecedentes + entradas
POST   /historias/:id/entradas         # Atención (inmutable, firmada)
GET    /legajos/:profesional_id        # credenciales + actividad

# Organización / admin
GET/POST /areas      (árbol, con validación de 3 niveles)
POST     /areas/:id/staff
GET/POST /usuarios
```

## 7. Reglas de negocio a no perder

- Validación al publicar (nodo sin salida, decisión sin rama por defecto, formulario sin campos, derivar sin destino, atención que usa campo inexistente, credencial requerida sin campo de origen). Publicar bloqueado con errores; advertencias no bloquean.
- Publicar versión nueva **no afecta casos en curso**.
- HC y timeline **inmutables**; correcciones = entrada nueva.
- Acceso a HC gobernado por legajo profesional + **auditoría** de todo acceso.
- Jerarquía organizativa **fija en 3 niveles**.
- Derivar **conserva los datos** del caso.

## 8. Accesibilidad / calidad
- Targets táctiles ≥ 44px; foco visible (anillo indigo); contraste AA en texto sobre fondos.
- Estados vacíos, de carga y de error para cada tabla/lista (el prototipo muestra el estado "lleno"; falta diseñar vacío/carga si se quiere).
- i18n: copys en español rioplatense; externalizar strings.

## 9. Fuera de alcance de este entregable (futuro)
Notificaciones, reportes/métricas, acceso del beneficiario/ciudadano, integraciones externas (más allá del legajo ciudadano), display público de turnos en sala, vista agregada de supervisión por responsable de área.
