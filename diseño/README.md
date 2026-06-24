# Cauce — Constructor y motor de flujos

> Un editor visual donde se **diseña** un proceso como diagrama (pasos, formularios, decisiones) y ese mismo diagrama se **ejecuta**: otros usuarios completan casos reales que avanzan paso a paso, se derivan entre áreas y quedan registrados. Pensado para procesos tipo hospital o trámites del Estado.

---

## 1. Visión en una frase

El configurador arma un diagrama de flujo; el motor lee esa misma definición para (a) dibujar el lienzo y (b) renderizar las pantallas que opera el personal. **Nadie programa una pantalla a mano.**

## 2. El principio que ata todo

| Concepto | Qué es | Vive |
|---|---|---|
| **Plantilla** (flujo) | La definición que diseña el configurador | Mundo definición |
| **Caso** | Una instancia de esa plantilla corriendo con datos reales | Mundo ejecución |

Lo que diseña el configurador es una plantilla. Lo que corre con datos reales es un caso. El motor usa la misma definición para ambos mundos.

## 3. Las dos experiencias visuales (regla de oro)

El sistema tiene **dos modos que NO deben parecerse**:

- **Diseño** = lienzo gráfico tipo diagrama de flujo (draw.io / n8n / Miro): canvas con grilla de puntos, nodos arrastrables, flechas, zoom, paneo.
- **Ejecución** = software de gestión serio (ERP / expediente electrónico): formularios prolijos, tablas, badges de estado, stepper de progreso. **Sin lienzo ni grilla.**

> Si la pantalla de ejecución parece un diagrama, está mal. Si el diseñador parece un formulario lineal, está mal.

## 4. Capas del sistema

```
Plataforma (super admin)
  └── Institución  (Hospital Central, Centro de Salud Norte, …)   ← contexto, autocontenida
        ├── Área   (Admisión, Cardiología, Asistencia social)
        │     └── Sub-área (Hemodinamia, Consultorios externos)
        ├── Flujos / Formularios   (pertenecen a un nivel organizativo)
        ├── Casos / Bandejas / Filas
        └── Registros: Historia clínica · Legajo profesional
```

Las instituciones son **independientes** (no se agrupan en jurisdicciones ni redes). El super admin es el nivel más alto; el directorio de instituciones es la raíz.

## 5. Archivos de este entregable

| Archivo | Qué es |
|---|---|
| `Cauce - Procesos.dc.html` | **El prototipo completo** — todas las pantallas, interactivo |
| `Demo del sistema.dc.html` | Video animado tipo pitch (9 escenas, autoplay) |
| `Sistema de diseno.dc.html` | Página visual del sistema de diseño (paleta, tipografía, componentes) |
| `docs/01-manual-de-marca.md` | Identidad, voz y tono, logo, color, tipografía |
| `docs/02-sistema-de-diseno.md` | Tokens y componentes (especificación para código) |
| `docs/03-arquitectura-y-roles.md` | Capas, roles/permisos, navegación, IA |
| `docs/04-pantallas.md` | Especificación pantalla por pantalla |
| `docs/05-modelo-de-datos.md` | Entidades, relaciones, reglas |
| `docs/06-handoff-desarrollo.md` | Stack sugerido, orden de construcción, superficie de API |
| `docs/HANDOFF.md` | **Instrucciones para implementar tal cual** (leer primero) |
| `docs/tokens.css` | Design tokens como CSS variables (copiar tal cual) |
| `docs/tokens.json` | Design tokens en JSON (alimenta tailwind.config / tema) |
| `docs/captures/` | **Capturas congeladas de cada pantalla** — fuente de verdad visual |

## 6. Cómo ver el prototipo

Los `.dc.html` son archivos autocontenidos (solo dependen del runtime `support.js` incluido). Abrir `Cauce - Procesos.dc.html` en un navegador moderno.

- **Selector de rol** (header): Super admin / Configurador / Administrativo / Admin de institución. Cambia el menú y el mundo visual.
- **Ingresar a una institución** desde el directorio (super admin) o entrar directo (admin de institución).
- **Ver demo**: botón en el panel de inicio de la institución → abre el video animado.

## 7. Los tres usuarios

| Usuario | Qué hace | Mundo |
|---|---|---|
| **Configurador** | Diseña flujos y formularios | Diseño (lienzo) |
| **Administrativo / profesional** | Ejecuta casos, completa y deriva | Ejecución (sistema) |
| **Admin de institución / Super admin** | Gestiona instituciones, usuarios, áreas | Administración |

---

Hecho como prototipo de diseño de alta fidelidad. Ver `docs/06-handoff-desarrollo.md` para arrancar el desarrollo.
