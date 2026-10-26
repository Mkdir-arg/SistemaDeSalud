---
name: plexo-documento-mockups
description: Crear o actualizar documentos HTML de PLEXO para explicar trabajo realizado mediante flujos, procesos y mockups de pantallas, con índice navegable y notas funcionales. Usar para propuestas funcionales y presentaciones de avances; no para implementar funcionalidades en la aplicación.
---

# Documentos de flujos y mockups de PLEXO

Crear un documento que permita recorrer un proceso y entender qué cambió, quién interviene y qué ve cada actor. Escribir en español para lectores no técnicos, con frases concretas y vocabulario del producto. El HTML es una explicación visual; no demuestra que las funciones estén implementadas.

## Contexto y fuentes

- Identificar la raíz del repo y leer sus instrucciones aplicables. Reutilizar el alcance y los criterios ya confirmados; preguntar sólo por vacíos materiales.
- Revisar el diff, issue o documentación que origina el pedido y los componentes afectados. No inventar trabajo realizado, permisos, reglas clínicas ni resultados de validación.
- Para estilo vigente, consultar `frontend/src/styles/tokens.css`, `frontend/src/assets/marca/` y el shell/componente pertinente. `diseño/` contiene un prototipo histórico: no tomarlo como identidad actual.
- Leer [el estándar](references/estandar.md) y adaptar [la plantilla](assets/documento.html). La referencia editorial es https://mkdir-arg.github.io/Chaco-Back/mockups/dispositivos-v2.html#f5: conservar su organización en flujos y pantallas, no su marca ni sus reglas de negocio. La plantilla local permite trabajar sin consultar ese sitio cada vez.

## Producir el documento

1. Expresar objetivo, destinatario, alcance y cambios en pocas frases. Separar hechos comprobados, propuestas y pendientes. Si faltan evidencias, indicar «Disponibilidad sin confirmar».
2. Enumerar los procesos que explican el trabajo. Para cada uno, definir actor, disparador, pasos, decisiones, alternativas relevantes y resultado observable. Mostrar diagramas HTML/CSS o SVG integrados, con un recorrido textual equivalente.
3. Vincular cada flujo `F1…` con sus pantallas `P1…`. Incluir pantallas suficientes para explicar los estados relevantes: por ejemplo, listado, detalle, formulario, vacío o error, sólo cuando correspondan al alcance.
4. Para funciones existentes, capturar la aplicación con sus componentes, shell y estilos reales, usando datos sintéticos. No sustituir esas capturas por una recreación HTML. Esperar a que carguen estilos, fuentes e imágenes y terminen las transiciones. Indicar si el entorno utiliza respuestas simuladas: la captura acredita la interfaz, no la persistencia ni la disponibilidad productiva. Para funciones futuras, explicar el flujo y señalar que la pantalla está pendiente; crear un mockup propuesto sólo cuando el pedido lo requiera y rotularlo como tal. Si no se puede capturar la aplicación, declarar el faltante sin fabricar una captura.
5. Añadir notas breves sobre lo que sucede, las reglas y los pendientes. Usar estados comprensibles como «Incorporado», «En desarrollo» y «Por completar», sin confundirlos con estados del trámite. Simplificar repeticiones y detalles que no ayuden al lector a entender el cambio o tomar una decisión. Mantener las fuentes técnicas en el informe de entrega: el documento no debe citar PR, issues, nombres de archivos ni enlazar al repositorio. No convertir hipótesis en requisitos aprobados.
6. Guardar por defecto en `docs/mockups/<tema>-v<N>.html`, salvo convención o destino solicitado. Actualizar el mismo archivo si se pide una corrección; crear una nueva versión sólo cuando se solicita o cambia la versión del entregable. Preservar IDs existentes para no romper enlaces compartidos.

## Verificar y entregar

- Usar únicamente datos sintéticos; no incluir credenciales, datos de pacientes, secretos ni capturas con información real.
- Mantener un HTML que abra por `file://`, con CSS y diagramas integrados, sin CDN, API, analítica ni dependencias nuevas. Si se incorpora un logo, integrarlo o entregar sus assets locales con rutas válidas. No usar el mockup para llamar a servicios reales.
- Dar al índice lateral contraste propio, grupos claros, foco visible y señal de sección activa. Conservar legibles la marca y los enlaces en pantallas bajas; en móvil, usar una navegación compacta. Consultar el estándar para los detalles visuales.
- Comprobar IDs únicos, enlaces internos válidos, ausencia de restos del ejemplo, fecha/versión correctas y correspondencia F↔P. Los estados deben tener texto, no sólo color.
- Abrirlo en un navegador disponible: revisar escritorio, ancho móvil e impresión. Verificar notas, desplazamiento local de tablas, etiquetas de diagramas y legibilidad de las capturas a tamaño ampliado. Comprobar que las imágenes estén cargadas y que la navegación no oculte marca, enlaces o contenido. Si no se pudo revisar visualmente, declararlo; una inspección del HTML no equivale a esa prueba.
- Entregar ruta del HTML, resumen de lo explicado, fuentes que sustentan los estados de implementación, verificaciones realizadas y pendientes. No publicar, commitear ni desplegar salvo autorización del usuario.

## Ejemplo de invocación

«Usá $plexo-documento-mockups para explicar lo trabajado en [módulo o issue], con los flujos del proceso y las pantallas vinculadas. Destinatario: [audiencia].»
