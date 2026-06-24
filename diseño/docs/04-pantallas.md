# Especificación de pantallas

Todas las pantallas viven **dentro del contexto de una institución** salvo las del super admin (§0). Modo visual indicado en cada una: **[DISEÑO]** lienzo · **[EJECUCIÓN]** sistema de gestión · **[ADMIN]** gestión.

## 0. Plataforma (super admin) [ADMIN]

### 0.1 Directorio de instituciones (raíz)
Tabla de todas las instituciones. Columnas: Institución (ícono + nombre) · Tipo · Áreas · Staff · Estado (Activa/En alta/Inactiva) · acción **Ingresar**. Buscador + botón **Nueva institución**. Header con "Alcance: todas las instituciones".

### 0.2 Alta de institución
Formulario: nombre, tipo (Hospital general / Centro de salud / Hospital pediátrico), estado inicial, dirección/contacto. Sección **Primer administrador** (nombre, email) → será el admin de institución. Cancelar / Crear.

### 0.3 Panel de la institución (Inicio)
Encabezado: ícono + nombre + tipo + estado + botón **Ver demo**. Fila de métricas (Áreas / Sub-áreas / Staff / Casos activos). Grilla de accesos a las secciones (Flujos, Formularios, Bandeja, Casos, Historia clínica, Estructura organizativa). Header de contexto conmutable: "Volver al directorio".

---

## 1. Flujos (listado) [DISEÑO/ADMIN]
Tabla filtrable por **área** y estado. Columnas: Flujo · **Área** (nivel al que pertenece, con chip de color) · Estado (badge) · Versión · Casos activos · Última edición (fecha · autor). Botón **Nuevo flujo**. Acciones por fila: Abrir, Duplicar, Historial, Archivar. Datos: Ingreso de paciente (Institución, Publicado v3, 12) · Visita de seguimiento (Asistencia social, Publicado v2, 23) · Derivación a especialista (Cardiología, Borrador v1) · Estudios de hemodinamia (Hemodinamia, Publicado v1, 5).

## 2. Diseñador de flujos (pantalla estrella) [DISEÑO]
Editor de tres columnas sobre lienzo con grilla.

- **Toolbar:** nombre editable · badge de estado · versión (→ historial) · deshacer/rehacer · auto-organizar · encajar a pantalla · validación (chip "N errores" / "Sin errores") · **Probar** (simulación) · **Reproducir** (animación del flujo) · Guardar borrador · **Publicar** (deshabilitado con errores). *La toolbar envuelve a 2 filas en pantallas angostas.*
- **Izquierda — Paleta:** 10 tipos de nodo arrastrables (ver `05-modelo-de-datos.md §nodos`), con ícono y color. Búsqueda de nodos.
- **Centro — Lienzo:** nodos como cajas con resumen ("Formulario · 6 campos", "Decisión · 2 ramas", "Derivar → Cardiología") + punto de validez (verde/ámbar/rojo). Selección con anillo de acento; conexiones por flechas; etiqueta de condición en ramas de Decisión. Minimapa + zoom. Soporta bucles (conexión a un paso anterior).
- **Derecha — Panel de propiedades / solapa Problemas:**
  - *Propiedades* cambia según nodo (formulario → campos; decisión → reglas; derivar → destino; estado → estado; espera de fila → orden/área/salidas; espera por tiempo → intervalo; atención → campos + escribe en HC + credencial requerida).
  - *Problemas (N)*: lista viva de errores/advertencias; clic en uno → enfoca (pulse) el nodo culpable; Publicar bloqueado con errores.

**Ejemplo cargado (Ingreso de paciente):** `Inicio → Formulario "datos del paciente" → Estado "En espera" → Espera de fila "Sala de admisión" → Atención "evaluación inicial" → Decisión "¿a qué área?"` → ramas `si urgente → Derivar a Guardia` · `por defecto → Derivar a Cardiología`.

## 3. Constructor de formularios [DISEÑO]
Dos zonas. **Editor (izq):** lista ordenable de campos (etiqueta, tipo, obligatorio) + "Agregar campo"; al seleccionar un campo se editan sus propiedades (etiqueta, obligatorio, **origen del dato** — manual / Historia clínica / Legajo ciudadano, valor por defecto, ayuda, opciones, validaciones). Toggle "Asentar en la Historia clínica" (convierte el paso en Atención). **Previsualización en vivo (der):** el formulario tal como lo verá el administrativo, actualizándose al editar. Campos vinculados se muestran de solo lectura/valor inicial con su badge de origen.

## 4. Bandeja de tareas [EJECUCIÓN]
Pestañas **Mis casos** / **Sin asignar** (de mi área). Tabla: Caso (ID + flujo) · Paso actual · Estado (badge) · Área · Antigüedad · acción (**Tomar** / **Continuar**). Filtros (flujo, estado, área) + buscador. Antigüedad alta resaltada en rojo.

## 5. Ejecución de un caso [EJECUCIÓN]
Encabezado (ID, flujo, estado, paso). **Stepper** horizontal de progreso. Cuerpo: bloque **Historia clínica · antecedentes** (solo lectura) + bloque **datos ya cargados** (expediente acumulativo) + el **paso actual** renderizado (formulario, o decisión manual con opciones como botones). Panel lateral con info del caso + **profesional que atiende** y su credencial. Pie: **Continuar/Enviar**, "Guardar y salir". Valida obligatorios; si es derivación automática resuelve la regla, si es manual pide destino.

## 6. Pantalla del operador de fila [EJECUCIÓN]
Encabezado de la fila (nombre + cantidad en espera + tiempo promedio). **Atendiendo ahora**: caso actual con datos clave y tres acciones — **Finalizar y continuar** (salida principal) · **Devolver a la fila** · **Marcar ausente** (salida "ausente" → cierre). Lista **En espera**: posición, turno (A-042), hora de ingreso, antigüedad; próximo resaltado. Botón grande **Llamar al siguiente**. Acción opcional: llamar fuera de orden (queda registrado).

## 7. Historia clínica [EJECUCIÓN/REGISTROS]
- **Listado (tabla):** Paciente (avatar + documento) · Obra social · Condiciones/Alergias (chips) · Entradas · Última. Buscador + **Crear registro**.
- **Detalle:** encabezado del paciente con identidad **referenciada del legajo ciudadano externo**. Fila de métricas. Botón **Nueva atención**. Pestañas: **Evolución** (timeline de entradas: Atención/Estudio/Medicación/Diagnóstico/Entrega con autor y caso) · **Estudios** · **Recetas** · **Archivos** · **Legajo** (datos + auditoría de accesos). Entradas inmutables.

## 8. Legajo profesional [EJECUCIÓN/REGISTROS]
Encabezado: profesional, matrícula + vigencia, especialidad, áreas. Métricas (casos atendidos, pacientes vistos, llamados de fila, última actividad). Tabla de **actividad reciente** (fecha · paciente · acción · caso) — cada Atención enlaza a una entrada de la HC.

## 9. Estructura organizativa [ADMIN]
Dos columnas. **Árbol (izq):** Institución → Áreas → Sub-áreas, cada nodo con ícono + nombre + contador; selección resaltada; **+** crea área en la raíz. **Ficha (der):** nombre + badge (Área/Sub-área) + responsable + acciones (Editar, Asignar profesional). Pestañas: **Datos** · **Staff** (profesionales con rol, sin herencia) · **Procesos** (flujos del nivel, Propio/Heredado) · **Sub-áreas** (solo si el nivel es Área; con "Nueva sub-área"). Modales: alta/edición (el nivel lo determina dónde se crea) y asignar profesional (selector del legajo + rol).

## 10. Administración [ADMIN]
- **Usuarios:** tabla (nombre, email, rol(es), área(s), estado) + crear/editar.
- **Áreas:** tabla (área, usuarios, flujos asociados) + crear.

## 11. Casos (consulta) [EJECUCIÓN]
Tabla de todos los casos de la institución (ID, flujo, paso, estado, área, asignación). Clic → trazabilidad.

## 12. Detalle / Trazabilidad de un caso [EJECUCIÓN]
Solo lectura. Encabezado (ID, flujo, estado, fechas). **Timeline inmutable**: cada evento (paso, dato, ingreso a fila/turno, llamado, ausente, derivación, cambio de estado, atención, espera programada, cierre) con quién y cuándo. Panel de **datos acumulados** agrupados por paso.

## 13. Historial de versiones [DISEÑO]
Lista de versiones (v3/v2/v1) con estado, fecha, autor, nota, casos en curso por versión, y acciones Ver / Comparar / Restaurar. Aviso clave: **publicar una versión nueva no afecta a los casos en curso** (cada caso termina con la versión con la que empezó).

## 14. Mapa de flujos [DISEÑO]
Vista de red: cada flujo es un bloque, las derivaciones son flechas entre flujos (etiquetadas). Clic en un bloque → abre el diseñador. Sirve para ver cómo se encadenan los procesos de la institución.

## 15. Modo simulación ("Probar") [EJECUCIÓN dentro de DISEÑO]
El configurador recorre su flujo con datos ficticios viendo las **pantallas de ejecución reales** (con cara de sistema), sin publicar ni crear casos. Barra "MODO PRUEBA · no se guarda", indica el paso, permite reiniciar. El ejemplo de Ingreso recorre: Datos → Sala de admisión (fila) → Evaluación inicial (Atención→HC) → ¿A qué área? → Resultado.

## 16. Reproducir flujo (animación) [DISEÑO]
Botón "Reproducir" en la toolbar: un token (caso) viaja por los nodos del lienzo resaltando cada paso, con barra de control (pausar / reiniciar / cerrar) y caption del paso actual. Disponible para ambos flujos (incluido el bucle de Visita de seguimiento).
