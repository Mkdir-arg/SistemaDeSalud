---
name: plexo-documento-mockups
description: Crear o actualizar documentos HTML de PLEXO para explicar trabajo realizado mediante flujos, procesos y mockups de pantallas, con índice navegable y notas funcionales. Usar para propuestas funcionales y presentaciones de avances; no para implementar funcionalidades en la aplicación.
---

# Documentos de flujos y mockups de PLEXO

Crear un documento que permita recorrer un proceso y entender qué cambió, quién interviene y qué ve cada actor. Escribir en español, con frases concretas y vocabulario del producto. El HTML es una explicación visual; no demuestra que las funciones estén implementadas.

## Contexto y fuentes

- Identificar la raíz del repo y leer sus instrucciones aplicables. Reutilizar el alcance y los criterios ya confirmados; preguntar sólo por vacíos materiales.
- Revisar el diff, issue o documentación que origina el pedido y los componentes afectados. No inventar trabajo realizado, permisos, reglas clínicas ni resultados de validación.
- Para estilo vigente, consultar `frontend/src/styles/tokens.css`, `frontend/src/assets/marca/` y el shell/componente pertinente. `diseño/` contiene un prototipo histórico: no tomarlo como identidad actual.
- Leer [el estándar](references/estandar.md) y adaptar [la plantilla](assets/documento.html). La referencia editorial es https://mkdir-arg.github.io/Chaco-Back/mockups/dispositivos-v2.html#f5: conservar su organización en flujos y pantallas, no su marca ni sus reglas de negocio. La plantilla local permite trabajar sin consultar ese sitio cada vez.

## Producir el documento

1. Expresar objetivo, destinatario, alcance y cambios en pocas frases. Separar hechos comprobados, propuestas y pendientes. Si faltan evidencias, indicar «Implementación sin verificar».
2. Enumerar los procesos que explican el trabajo. Para cada uno, definir actor, disparador, pasos, decisiones, alternativas relevantes y resultado observable. Mostrar diagramas HTML/CSS o SVG integrados, con un recorrido textual equivalente.
3. Vincular cada flujo `F1…` con sus pantallas `P1…`. Incluir pantallas suficientes para explicar los estados relevantes: por ejemplo, listado, detalle, formulario, vacío o error, sólo cuando correspondan al alcance.
4. Reproducir en las pantallas el shell y los patrones reales de PLEXO. Distinguir visualmente el diagrama explicativo de la interfaz que opera el personal. Si la vista es una propuesta, rotularla. Las interacciones ilustrativas deben identificarse como simuladas y funcionar localmente si se incluyen.
5. Añadir notas debajo de cada bloque: qué sucede, qué regla aplica y qué falta resolver. Evitar jerga técnica salvo cuando sea necesaria para el destinatario. No convertir hipótesis en requisitos aprobados.
6. Guardar por defecto en `docs/mockups/<tema>-v<N>.html`, salvo convención o destino solicitado. Actualizar el mismo archivo si se pide una corrección; crear una nueva versión sólo cuando se solicita o cambia la versión del entregable. Preservar IDs existentes para no romper enlaces compartidos.

## Verificar y entregar

- Usar únicamente datos sintéticos; no incluir credenciales, datos de pacientes, secretos ni capturas con información real.
- Mantener un HTML que abra por `file://`, con CSS y diagramas integrados, sin CDN, API, analítica ni dependencias nuevas. Si se incorpora un logo, integrarlo o entregar sus assets locales con rutas válidas. No usar el mockup para llamar a servicios reales.
- Comprobar IDs únicos, enlaces internos válidos, ausencia de restos del ejemplo, fecha/versión correctas y correspondencia F↔P. Los estados deben tener texto, no sólo color.
- Abrirlo en un navegador disponible: revisar escritorio, ancho móvil e impresión. Verificar que se lean las notas, las tablas tengan desplazamiento local y los diagramas no corten etiquetas. Si no se pudo revisar visualmente, declararlo; una inspección del HTML no equivale a esa prueba.
- Entregar ruta del HTML, resumen de lo explicado, fuentes que sustentan los estados de implementación, verificaciones realizadas y pendientes. No publicar, commitear ni desplegar salvo autorización del usuario.

## Ejemplo de invocación

«Usá $plexo-documento-mockups para explicar lo trabajado en [módulo o issue], con los flujos del proceso y las pantallas vinculadas. Destinatario: [audiencia].»
