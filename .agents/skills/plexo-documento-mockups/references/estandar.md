# Estándar editorial y visual

## Estructura del entregable

| Bloque | Contenido |
| --- | --- |
| Cabecera | PLEXO, tema, versión, fecha y estado del documento |
| Índice | Presentación, flujos F1… y pantallas P1…, con enlaces por fragmento |
| Presentación | Objetivo, alcance, qué cambió y qué queda fuera |
| Flujos | Título orientado al proceso, frase de propósito, diagrama y notas |
| Pantallas | Título orientado a la tarea, actor, flujo relacionado, mockup y notas |
| Evidencia y pendientes | Fuentes revisadas, validación disponible y decisiones abiertas |

Omitir secciones que no aporten al pedido, sin perder objetivo, flujos/pantallas pertinentes ni estado de lo mostrado. Los números facilitan la conversación: «En F2, este paso lleva a P4». Usar IDs `f1`, `p1`, etc.; no renumerar un documento existente sólo por orden estético.

## Comunicación

- Abrir con el resultado para quien usa el sistema: «Admisión identifica a la persona y registra el ingreso». Después explicar las reglas necesarias.
- Un título por proceso o tarea; un párrafo breve para orientar; notas al pie del bloque para excepciones y decisiones. Evitar párrafos extensos dentro del diagrama.
- En decisiones, nombrar las condiciones en cada salida. En recorridos entre roles, explicitar quién toma el siguiente paso. Cubrir rechazos, devoluciones o interrupciones cuando cambian la explicación.
- Usar estados de implementación separados de los estados del proceso. «En espera» puede ser un estado de una solicitud; no dice si esa función existe.

## Evidencia y estado

| Etiqueta | Cuándo usarla |
| --- | --- |
| Implementado | La fuente inspeccionada contiene la funcionalidad; citar archivo, función o PR. Aclarar si no se ejecutó. |
| Verificado | Se observó el comportamiento; indicar entorno, alcance y evidencia. No extrapolar a producción. |
| Propuesto | Diseño para discutir o construir; no presentarlo como disponible. |
| Pendiente | Falta trabajo o una decisión identificada. |
| Implementación sin verificar | No hay evidencia suficiente para afirmar disponibilidad. |

El estado del documento (borrador, en revisión, aprobado por una persona identificada) es independiente del estado del software. No atribuir aprobación humana sin evidencia.

## Sistema visual

Usar la referencia de Chaco para la composición: índice lateral, jerarquía clara, flujos antes de pantallas, mockups amplios y notas debajo. Adaptar marca, navegación y componentes a PLEXO. La plantilla contiene una selección de tokens tomada del repo; volver a contrastarla con los tokens vigentes al generar documentos.

Fondo claro, superficies blancas, bordes suaves, acento violeta y estados con texto. Tipografía del producto si hay assets locales disponibles; en su defecto, una pila de sistema sin descarga externa. La barra de navegación del documento y el menú del mockup son elementos distintos.

En móvil, pasar el índice al flujo normal y apilar pasos. Permitir scroll dentro de tablas anchas. Al imprimir, ocultar navegación, conservar títulos y notas, y evitar cortar tarjetas siempre que quepan en una página. No prometer un PDF paginado sin inspeccionar su salida.

La plantilla es un ejemplo ficticio genérico: sus pasos y pantallas no especifican reglas de PLEXO. Reemplazar todo el contenido de ejemplo antes de entregar un documento real.
