# Issue #91 — Pacientes: padrón e historia clínica unificados

Origen: #86. Límite: reúne pantallas institucionales existentes; no concede acceso clínico al financiador.

## Decisiones confirmadas

1. **Rutas.** `/pacientes` (listado) y `/pacientes/:id` (detalle) son canónicas.
   `/padron` y `/historia` redirigen a `/pacientes` conservando la query (`q`, `nuevo`).
   `/padron/:id` y `/historia/:id` redirigen a `/pacientes/:id` conservando query (`tab`) y hash (`#entrada-N`).
   Los enlaces internos apuntan directo a `/pacientes`; las redirecciones sólo cubren accesos guardados.
2. **Columnas del listado.** Las del padrón actual para todos (paciente, edad, domicilio, cobertura,
   última atención, consentimiento, acciones «Ver ficha»/«Revelar»). Quien tiene `historia_clinica`
   ve además la columna **Alergias**. Condiciones y cantidad de entradas no se muestran en el listado.
3. **Alta.** Un único «+ Registrar paciente» en pantalla completa (`/pacientes?nuevo=1`, flujo actual
   del padrón con detección de duplicados); al crear, abre `/pacientes/:id`. Se elimina el modal
   «Crear registro» de historia. La historia clínica sigue naciendo con la primera atención.
4. **Estructura del detalle.** Cabecera de la ficha del padrón con «Editar datos» para todos; con
   `historia_clinica` se agregan «Registrar atención» y el aviso de alergia; «Abrir historia» desaparece.
   Pestañas: «Datos» (datos administrativos, cobertura administrativa, consentimiento) para todos;
   Evolución, Estudios, Recetas, Cobertura y Quién la miró sólo con `historia_clinica`.
   Métricas y panel lateral clínico (antecedentes, integridad) sólo en las pestañas clínicas.
   Sin `historia_clinica` se conserva el aviso de que la ficha no muestra datos clínicos.
5. **Pestaña inicial.** `?tab` de la URL se respeta; sin `?tab`, abre «Datos» para todos.
   La redirección de `/historia/:id` sin `?tab` agrega `?tab=evolucion`. Los enlaces internos que hoy
   van a la historia (caso, Mi trabajo, Accesos) apuntan a `/pacientes/:id?tab=evolucion`; los que iban
   a la ficha y el buscador del menú van sin pestaña. Sin `historia_clinica`, una pestaña clínica en
   la URL cae en «Datos» sin pedir datos clínicos.
6. **Menú y accesos.** Una única entrada «Pacientes» (`padron_admision`, ícono `idCard`) en OPERACIÓN
   debajo de «Turnos»; desaparece el grupo PACIENTES. Íconos contra Figma quedan para #89.
   Títulos de barra: «Pacientes» (listado) y «Paciente» (detalle). Inicio y Mi trabajo: acceso
   «Pacientes» a `/pacientes`. Tutorial: pasos de `/padron` y `/historia` pasan a `/pacientes` y
   el de historia muestra las pestañas clínicas del detalle.

## Invariantes (no cambian)

- Backend sin cambios: `ciudadanos` exige `padron_admision`; historia, entradas, estudios, recetas y
  `accesos-clinicos/de-paciente` conservan sus capacidades, `protege_lectura` y registro de accesos.
- El listado sigue enmascarando documento, nacimiento y domicilio; «Revelar» sigue auditado.
- La exportación conserva motivo obligatorio y variantes identificada/clínica sólo con `historia_clinica`.
- Sin `historia_clinica` la pantalla no pide `historias-clinicas`, `accesos-clinicos/de-paciente`
  ni `/ciudadanos/:id/cobertura/` (hoy sólo los pide HistoriaDetalle).
- Firmar, antecedentes, integridad, estudios y recetas mantienen sus componentes y comprobaciones actuales.
- Cambiar de institución sigue llevando a `/inicio`; un paciente de otra institución lo rechaza el backend.
- Paciente sin historia: pestañas clínicas vacías y «Registrar atención» crea la historia, como hoy.

## Plan de implementación (frontend)

1. `App.jsx`: rutas `/pacientes` y `/pacientes/:id` con `padron_admision`; redirecciones de
   `/padron`, `/padron/:id`, `/historia`, `/historia/:id` que conservan query y hash (y agregan
   `tab=evolucion` en `/historia/:id` sin `tab`). Las redirecciones no exigen capacidad propia: la
   ruta destino aplica la suya.
2. `pages/registros/Registros.jsx`: un solo modo (padrón) con columna Alergias condicionada;
   alta en `/pacientes?nuevo=1`; se elimina el modal «Crear registro» y la rama `modo`.
3. Detalle unificado `pages/registros/PacienteDetalle.jsx` reutilizando las piezas actuales de
   `PadronDetalle.jsx` y `HistoriaDetalle.jsx` (moverlas, no reescribirlas). La parte clínica se
   monta sólo con `historia_clinica`, para que sus consultas no se disparen sin permiso.
4. Enlaces internos: `Shell.jsx` (menú, títulos, buscador), `Inicio.jsx`, `MiTrabajo.jsx`,
   `CasoDetalle.jsx`, `auditoria/Accesos.jsx`, `tutorial/pasos.js`.
5. e2e: actualizar rutas en specs existentes; cubrir con API interceptada (config
   `financiadores-ui`) administrativo vs. médico, redirecciones y paciente sin historia.
6. Docs: `docs/ROLES-Y-PERMISOS.md` y `docs/funcionalidades/registros-clinicos/README.md`
   (y los que nombren `/padron` o `/historia` fuera de `docs/historico/`).

## Riesgos

- **Fuga de consultas clínicas** si la parte clínica se monta antes de comprobar la capacidad:
  el backend igual responde 403, pero la pantalla mostraría error y quedaría ruido en auditoría.
- **Doble registro de acceso**: hoy abrir ficha e historia son dos pantallas; unificadas, la lectura
  de la ficha no debe repetirse al cambiar de pestaña.
- **Enlaces con hash** (`#entrada-N`) que se pierdan en la redirección.
- **Conflictos con #89** (worktree `issue-89-ui-inicio`), que también toca `Shell.jsx` e `Inicio.jsx`.
- `HistoriaDetalle.jsx` tiene 1291 líneas: moverlo entero agranda el diff; se busca un diff por
  extracción, sin reescritura.

## Validación

- `npx vite build` (compilación del frontend).
- `npx playwright test -c playwright.financiadores-ui.config.js padron-cobertura-ui cobertura-clinica-ui`
  más el spec nuevo de pacientes (API interceptada, sin backend ni base).
- No se corre `historia-clinica.spec.js` ni `legales.spec.js`: necesitan stack con datos. Sin
  Railway, bases compartidas ni datos reales.
- Revisión manual del diff: capacidades, consultas por rol y enlaces.

## Criterios del issue → evidencia

| Criterio | Evidencia prevista |
|---|---|
| Un solo listado en navegación; rutas viejas resueltas | Menú en `Shell.jsx`; spec de redirecciones con query/hash |
| Búsqueda, filtros, apertura y pestañas clínicas | Specs de padrón/cobertura actualizados; spec nuevo con médico |
| Cada rol ve lo permitido; URL directa, cambio de institución, sin historia | Spec nuevo: administrativo sin pestañas ni pedidos clínicos; médico con pestañas; paciente sin historia. Cambio de institución: sin cambio de código, revisión manual |
| Comprobaciones y trazabilidad clínicas intactas | Backend sin cambios; componentes clínicos movidos sin modificar lógica |
