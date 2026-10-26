# Estándar editorial y visual

## Estructura del entregable

| Bloque | Contenido |
| --- | --- |
| Cabecera | PLEXO, tema, versión, fecha y estado del documento |
| Índice | Presentación, flujos F1… y pantallas P1…, con enlaces por fragmento |
| Presentación | Objetivo, alcance, qué cambió y qué queda fuera |
| Flujos | Título orientado al proceso, frase de propósito, diagrama y notas |
| Pantallas | Título orientado a la tarea, actor, flujo relacionado, captura real y notas; propuesta sólo si fue solicitada |
| Alcance y pendientes | Qué se observó, límites de la demostración y decisiones abiertas, en lenguaje funcional |

Omitir secciones que no aporten al pedido, sin perder objetivo, flujos/pantallas pertinentes ni estado de lo mostrado. Los números facilitan la conversación: «En F2, este paso lleva a P4». Usar IDs `f1`, `p1`, etc.; no renumerar un documento existente sólo por orden estético.

## Comunicación

- Abrir con el resultado para quien usa el sistema: «Admisión identifica a la persona y registra el ingreso». Después explicar las reglas necesarias.
- Un título por proceso o tarea; un párrafo breve para orientar; notas al pie del bloque para excepciones y decisiones. Evitar párrafos extensos dentro del diagrama.
- En decisiones, nombrar las condiciones en cada salida. En recorridos entre roles, explicitar quién toma el siguiente paso. Cubrir rechazos, devoluciones o interrupciones cuando cambian la explicación.
- Usar estados de implementación separados de los estados del proceso. «En espera» puede ser un estado de una solicitud; no dice si esa función existe.
- Escribir para quien opera o evalúa PLEXO. Sustituir «PR borrador» por «En desarrollo» y explicar el efecto funcional, sin trasladar al lector el seguimiento técnico. Eliminar avisos repetidos y detalles sin utilidad para esa audiencia.
- Extraer los hechos de las fuentes, pero no incluir en el documento referencias a PR, issues, rutas, nombres de archivos ni enlaces al repositorio. Conservar esa trazabilidad en el informe de entrega al solicitante.

## Evidencia y estado

| Etiqueta | Cuándo usarla |
| --- | --- |
| Incorporado | La funcionalidad está añadida a la base inspeccionada. Aclarar si sólo se revisó su existencia, sin probar su funcionamiento. |
| En desarrollo | Hay trabajo iniciado que todavía no está incorporado a esa base. |
| Por completar | Falta trabajo o una decisión; no implica fecha ni compromiso aprobado. |
| Propuesta | Diseño solicitado para discutir o construir; no presentarlo como disponible. |
| Disponibilidad sin confirmar | No hay evidencia suficiente para afirmar que la función pueda usarse. |

El estado del documento (borrador, en revisión, aprobado por una persona identificada) es independiente del estado del software. No atribuir aprobación humana sin evidencia.

Describir aparte qué se probó y en qué entorno. Una captura de la aplicación con respuestas simuladas muestra su interfaz real, pero no demuestra escritura en una base ni funcionamiento en producción.

## Capturas de la aplicación

Capturar las vistas existentes directamente en PLEXO, con sus estilos completos y datos ficticios. Esperar la carga de fuentes e imágenes y el final de transiciones para evitar ventanas translúcidas o contenido incompleto. Revisar visualmente cada captura antes de integrarla.

Integrar las imágenes en el HTML o entregarlas como assets locales. Mantener su proporción y una forma de verlas a tamaño legible, especialmente en móvil. Explicar la tarea y el límite relevante al pie, sin repetir una advertencia extensa en cada bloque.

Si la pantalla no existe o no puede capturarse, dejar constancia del pendiente. Los diagramas explican los flujos futuros. Un diseño solicitado debe distinguirse como «Propuesta», nunca como captura de una función existente.

## Sistema visual

Usar la referencia de Chaco para la composición: índice lateral, jerarquía clara, flujos antes de pantallas, imágenes amplias y notas debajo. Adaptar marca, navegación y componentes a PLEXO. La plantilla contiene una selección de tokens tomada del repo; volver a contrastarla con los tokens vigentes al generar documentos.

Fondo claro, superficies blancas, bordes suaves, acento violeta y estados con texto. Tipografía del producto si hay assets locales disponibles; en su defecto, una pila de sistema sin descarga externa. La barra de navegación del documento y el menú del mockup son elementos distintos.

Dar al sidebar un fondo oscuro del sistema visual y texto claro, con títulos de grupo, espaciado consistente y estados de hover, foco y sección activa reconocibles también sin color. Evitar una lista larga de enlaces sin jerarquía. En alturas reducidas, permitir desplazarse por el índice sin comprimir ni ocultar la marca; si usa flex, reservar altura para la cabecera y limitar el área desplazable.

En móvil, pasar el índice al flujo normal con un control desplegable accesible y apilar pasos. Permitir scroll dentro de tablas anchas. Al imprimir, ocultar navegación y controles de ampliación, conservar títulos, imágenes y notas, y evitar cortar tarjetas siempre que quepan en una página. No prometer un PDF paginado sin inspeccionar su salida.

La plantilla es un ejemplo ficticio genérico: sus pasos y pantallas no especifican reglas de PLEXO. Reemplazar todo el contenido de ejemplo antes de entregar un documento real.
