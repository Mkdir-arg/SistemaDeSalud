# Manual de marca — Cauce

## 1. La marca

**Nombre:** Cauce.
**Qué evoca:** un cauce es el recorrido por donde fluye el agua. La metáfora: los procesos institucionales fluyen por un cauce diseñado — ordenado, trazable, que llega a destino. Serio, público, de infraestructura.

**Descriptor:** *Constructor y motor de flujos.*
**Promesa (tagline):** *Dibujás el proceso. El sistema lo ejecuta.*
**Cierre de pitch:** *Del diagrama al expediente.*

## 2. Personalidad

| Es | No es |
|---|---|
| Institucional, confiable, sobrio | Lúdico, "startup-y", recargado |
| Moderno y claro | Anticuado / burocrático gris |
| Con identidad propia | Genérico de plantilla |
| Denso pero legible | Minimalista vacío |

Equilibrio: **institucional pero moderno**. Sirve a hospitales y organismos del Estado: tiene que transmitir solidez sin parecer un sistema legado de los 2000.

## 3. Voz y tono

- **Español rioplatense**, voseo ("Dibujás", "Arrastrás", "Completá").
- Claro y directo. Frases cortas. Sin jerga técnica de cara al usuario.
- Tono **funcional** en la operación (capacitación: "Tomá el caso", "Continuar"), **comercial** solo en el pitch/demo.
- Etiquetas de UI en **mayúscula inicial**, no en mayúsculas sostenidas (excepto micro-rótulos de sección: "NODOS", "REGISTROS").
- Estados y acciones siempre en infinitivo o sustantivo claro: "Publicar", "Guardar borrador", "Derivar y continuar".

## 4. Logo

Marca tipográfica **"Cauce"** (Inter, 700–800, tracking ajustado −0.2 a −1.5px según tamaño) acompañada de un **isotipo**: tres nodos conectados por líneas — un nodo de entrada a la izquierda y dos ramas a la derecha, evocando un flujo que se bifurca.

**Construcción del isotipo (SVG):**
```svg
<svg viewBox="0 0 16 16">
  <circle cx="3.5" cy="8" r="2.2" fill="#fff"/>
  <circle cx="12.5" cy="3.5" r="2.2" fill="#fff" opacity=".85"/>
  <circle cx="12.5" cy="12.5" r="2.2" fill="#fff" opacity=".85"/>
  <path d="M5.4 7.1 10.8 4.2M5.4 8.9 10.8 11.8" stroke="#fff" stroke-width="1.3"/>
</svg>
```

**Contenedor:** cuadrado con esquinas redondeadas (`border-radius` 7–8px en chico, 20px en grande), fondo **Indigo 600 (#3949C0)**, isotipo en blanco.

**Usos:**
- Lockup horizontal: isotipo + "Cauce" + descriptor en gris.
- Tamaño mínimo del isotipo: 24px. Área de respeto: ≥ 50% del lado del contenedor.
- Sobre fondo oscuro: contenedor mantiene indigo, isotipo blanco. Nunca invertir a indigo sobre indigo.

## 5. Color

### Color de marca
| Token | Hex | Uso |
|---|---|---|
| **Indigo 600** | `#3949C0` | Acento primario: acciones, selección, logo, foco |
| **Indigo 700** | `#2D3A9E` | Hover de acciones primarias |
| **Indigo 50** | `#ECEEFB` / `#EEF0FB` | Fondos suaves de acento, chips |
| **Indigo 100** | `#C7CDF2` | Bordes de acento |

El indigo es el único color "de marca". Todo lo demás es neutro o semántico.

### Neutros (escala slate)
| Token | Hex | Uso |
|---|---|---|
| Ink | `#14161C` | Texto principal / barras oscuras |
| Slate 900 | `#1F2430` | Títulos |
| Slate 700 | `#344054` | Texto fuerte |
| Slate 600 | `#475467` | Texto secundario |
| Slate 500 | `#667085` | Texto terciario |
| Slate 400 | `#98A0AE` | Texto sutil / placeholders |
| Slate 300 | `#A4ABB8` | Micro-rótulos |
| Border | `#E7E9EE` · `#E2E5EA` | Bordes de tarjetas / inputs |
| Divider | `#EEF0F3` · `#F1F2F5` | Separadores internos |
| Surface | `#FFFFFF` | Tarjetas, paneles |
| Canvas | `#F4F5F7` | Fondo de app |
| Subtle | `#FAFBFC` · `#FBFBFD` | Fondos de fila/encabezado, lienzo |

### Estados semánticos (badges)
| Estado | Fondo | Texto | Punto |
|---|---|---|---|
| Neutro / Recibido / Borrador | `#EEF0F3` | `#475467` | gris |
| Info / En evaluación | `#E8EEFB` | `#2D3A9E` | indigo |
| Ámbar / Derivado / En espera | `#FBF0DD` | `#A96A12` | ámbar |
| Verde / Publicado / Atendido / Activo | `#E6F5EC` | `#1B7A4E` | verde |
| Gris / Cerrado / Archivado / Inactivo | `#F0F1F3` | `#9098A6` | gris medio |
| Error | `#FCEBEB` | `#B42318` | rojo |

### Colores de categoría de nodo (solo modo diseño)
Cada tipo de nodo tiene su color para distinguirlo en el lienzo. Son colores **funcionales**, no de marca; lo importante es que sean consistentes y distinguibles.

| Nodo | Sólido | Tinte | Borde | Texto |
|---|---|---|---|---|
| Inicio | `#1F8A5B` | `#E9F6EF` | `#BBE3CD` | `#16794B` |
| Formulario | `#3949C0` | `#ECEEFB` | `#C7CDF2` | `#2D3A9E` |
| Decisión | `#C98A2B` | `#FBF2E0` | `#EBD7AC` | `#A96A12` |
| Acción | `#2B8FD6` | `#E6F1FB` | `#BBD9F2` | `#1C6BA8` |
| Derivar | `#0E8893` | `#E3F4F4` | `#B2DFE0` | `#0B6A72` |
| Espera de fila | `#16B1C9` | `#E2F6F9` | `#B6E4EC` | `#0C7C8E` |
| Espera por tiempo | `#0E9E8E` | `#E2F5F1` | `#B3E2D9` | `#0A6E62` |
| Atención | `#D14B8F` | `#FCEAF2` | `#F2C4DA` | `#A8316E` |
| Estado | `#5B7A99` | `#EEF2F6` | `#CDD8E2` | `#3F586F` |
| Fin | `#475467` | `#EFF1F4` | `#D0D5DD` | `#344054` |

## 6. Tipografía

- **Familia principal:** **Inter** (400 / 500 / 600 / 700 / 800). Neutra, eficiente, institucional.
- **Monoespaciada:** **JetBrains Mono** (500) — para IDs de caso (`#1042`), versiones (`v3`), matrículas, turnos (`A-042`).

Escala de uso (px):

| Rol | Tamaño | Peso |
|---|---|---|
| Display / pitch | 46–62 | 800 |
| Título de pantalla | 27–34 | 700–800 |
| Título de sección / card | 14–18 | 700 |
| Cuerpo | 13–15 | 400–500 |
| Etiqueta de campo | 12.5–13 | 600 |
| Micro-rótulo (caps) | 10.5–11 | 700, tracking 0.5–1px |
| Dato sutil | 11.5–12.5 | 400–500 |

> En decks/slides el texto nunca baja de 24px; en documentos el mínimo es 12pt. La app es de uso intensivo: densidad media-alta, pero nada por debajo de ~11px y nunca como única jerarquía.

## 7. Iconografía

- Estilo **lineal (outline)**, `stroke-width` 1.5–1.6, `viewBox` 0 0 18/20.
- Esquinas suaves, sin relleno salvo el isotipo y micro-indicadores.
- Cada tipo de nodo tiene un ícono propio (formulario = documento con líneas, decisión = rombo, derivar = flecha→barra, espera de fila = lista, atención = corazón/pulso, etc.).
- **Sin emojis** en la UI.

## 8. Forma y profundidad

- **Radios:** inputs/botones 8–10px · tarjetas 12–14px · nodos del lienzo 13–14px · contenedores grandes 16–18px · pills 999px.
- **Sombras:** sutiles y frías. Tarjeta en reposo `0 1px 3px rgba(16,24,40,.07)`; elevada/hover `0 6px 18px rgba(16,24,40,.1)`; overlay/modal `0 24px 60px rgba(16,24,40,.28)`.
- **Bordes finos** (1px) como recurso principal de separación; la sombra es secundaria.
- Mucho espacio en blanco; superficies blancas sobre canvas gris.

## 9. Qué evitar

- Gradientes llamativos, emojis decorativos, contenedores con borde de acento a la izquierda.
- Fuentes sobreusadas fuera de Inter (Roboto, Arial). 
- Que el modo ejecución tome cualquier cosa del lenguaje "lienzo" (grilla, nodos, flechas).
- Inventar colores nuevos fuera de esta paleta: si hace falta un matiz, derivarlo en el mismo tono.
