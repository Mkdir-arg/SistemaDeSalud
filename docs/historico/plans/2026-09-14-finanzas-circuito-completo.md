# Finanzas: circuito económico completo y permisos — 14/09/2026

## Decisiones del usuario
- El administrador institucional autoriza acceso sensible y tiene lectura financiera sensible por defecto dentro de su institución. No se conceden permisos clínicos ni otras acciones financieras por inferencia.
- El personal contable puede recibir acciones financieras y acceso sensible explícitos sin convertirse en administrador institucional.
- Control mensual reemplaza a Carga esperada. Monto de referencia opcional: comparar con aprobado sin cerrar la carga automáticamente.
- Reparto automático al guardar cambios; se aprobó confirmar el guardado y comenzar inmediatamente en segundo plano, mostrando estado hasta terminar. Sin esperar una ejecución periódica como mecanismo principal; se conserva recuperación tras fallas.
- Gastos y reportes son parte central del producto. Mostrar origen, distribución y pendientes sin sumar un gasto y su reparto dos veces.
- Configuración y consulta de costos directos deben tener pantallas para completar el recorrido sin API ni comandos.
- Permisos: edición sin desplazamiento al final, varias acciones en una operación. Icono $, lápiz que agrupa configuración e historial mensual.

## Criterios observables
1. Admin activo ve costos/gastos sensibles sólo en su institución; contador sólo según concesiones. Desactivar membresía elimina acceso; cambiar rol elimina valores por defecto del admin, no inventa accesos nuevos. Delegar sigue reservado a configuración institucional.
2. Concesión múltiple atómica y resumen explícito: todas las seleccionadas o ninguna, sin ampliar permisos existentes inadvertidamente.
3. Guardar una fuente o regla, aprobar, ajustar y completar actividad marca el resultado afectado para recalcular. Los resultados anteriores se identifican como pendientes de actualizar. Reintentos no duplican importes y cambios concurrentes no se pierden.
4. Reportes enlazan totales con registros filtrados. Gasto fuente, distribuido y saldo conservan la igualdad; datos restringidos/incompletos no se presentan como cero ni como total institucional completo.
5. Usuario configura prestación, componentes y vigencias; registra una atención y consulta desglose directo/compartido/faltantes en la app. Sin alterar costos históricos silenciosamente.
6. Control mensual muestra referencia, aprobado y diferencia; conserva cierre manual y su historial. Los conceptos provienen del catálogo de la institución, indicado en pantalla.

## Ejecución y límites
- Worktree y PR acumulativos originales; recuperar cambios del respaldo del 11/09 sin tocar el checkout principal.
- Reusar Django, PostgreSQL, API y componentes existentes. Sin nuevos paquetes de producción.
- Implementar en pasos con pruebas de API/permisos/cálculos, concurrencia/recuperación y navegador. No operar el circuito clínico reservado al usuario.
- Se preparan migraciones aditivas para monto de referencia y trabajo durable pendiente. No se aplican a las bases de la demo sin informar alcance y obtener aprobación específica; se validan en base de pruebas.
- No commit, push, merge ni despliegue implícitos. El diseño usa brainstorming; writing-plans no está disponible y este documento cumple el plan de ejecución local.
- Pendiente de aceptación: revisión del usuario y prueba del circuito completo. Pruebas automáticas no demuestran comprensión ni aceptación humana.

## Evidencia de implementación

- `docker exec sistemadesalud-finanzas-demo-backend-1 python manage.py test apps.finanzas --noinput`: 161 pruebas aprobadas en 62,520 segundos; base de pruebas independiente, eliminada al finalizar.
- Cobertura nueva: permisos institucionales/sensibles y altas múltiples; referencia y neto aprobado; auditoría y aislamiento de reportes; disparadores de creación, aprobación, ajustes, rechazo, reemplazo, reglas, cobertura y atención; reintentos, reservas vencidas y cambios durante cálculo; notificación PostgreSQL después del commit y dos consumidores reales compitiendo por un trabajo.
- Prueba con tres atenciones y reversión negativa: aprobado y distribuido conservan exactamente 100,01 y luego −100,01, sin sumar versiones históricas ni multiplicar por atribuciones.
- `docker exec sistemadesalud-finanzas-demo-backend-1 python manage.py makemigrations finanzas --check --dry-run`: sin migraciones faltantes.
- `docker compose config --quiet` y `git diff --check`: correctos.
- Frontend: `npx playwright test --config playwright.finanzas-ui.config.js` con `SALUD_URL=http://127.0.0.1:5178`: 9/9 pruebas Chromium aprobadas en 19,1 s, con API simulada. `npm run build`: 149 módulos, correcto (1,22 s). Estas pruebas no demuestran integración con la base de demo ni ejecutan actividad clínica del usuario.
- El test negativo de una atención retirada del listado reprodujo un modal que conservaba el detalle anterior. Se quitó el respaldo local obsoleto y se verificó que el detalle desaparece al dejar de existir en la respuesta actual. Casos cubiertos adicionalmente: permisos múltiples, usuario sólo con lectura de costos, configuración en tres pasos, navegación desde reportes, actualización pendiente/recuperada y móvil.
- La suite legacy de navegador se adaptó a las etiquetas nuevas, pero no se ejecutó contra una base real. No se ejecutó la suite de todo el backend: la validación completa fue de Finanzas. La instalación desde el lockfile informó ocho vulnerabilidades existentes; no se cambiaron dependencias ni lockfile.
- Después de terminar las pruebas backend, todos los contenedores de demo y práctica se detuvieron simultáneamente (exit 255, 12:28 del 14/09), sin una orden de parada del agente. Causa no confirmada. La última validación UI usó un Vite aislado, ya detenido. Ambos entornos siguen sin estar disponibles.

## Activación autorizada y siguiente gate

El usuario autorizó restaurar servicios, respaldar la base de demo, aplicar 0020/0021 y arrancar el servicio dedicado. Se completó el 14/09/2026: respaldo PostgreSQL custom fuera del worktree, restauración verificada en una base separada, ambas migraciones OK y servicio `sistemadesalud-finanzas-demo-repartos-1` saludable. Se reutilizó la imagen local ya validada del backend, con el código montado y ambas opciones de seed en cero.

El primer arranque atendió ocho gastos aprobados, cero trabajos pendientes y cero errores. Versiones de reparto: seis antes y nueve después; ocho vigentes. Ocho atribuciones vigentes, sin diferencias de importes ni cruces de institución/área/mes. Una solicitud repetida se procesó en 0,106 s y conservó el mismo número de versiones. Las huellas de contenido de usuarios, pacientes, casos, eventos, concesiones y gastos originales se conservaron idénticas tras la activación y las consultas.

El control inicial del agente sobre `saldo_no_atribuido_centavos` supuso erróneamente que ese campo almacenado tenía la misma semántica en todos los estados. El contrato existente lo persiste para `sin_actividad`; la API de detalle y el reporte derivan el saldo pendiente como neto menos atribuciones. Se corrigió la comprobación, no los datos ni el motor, y se contrastó la conservación según estado y la respuesta real. Dejar esta diferencia de nombres/semántica como punto concreto para la revisión completa, sin interpretar aquel primer assert como evidencia de importes perdidos.

Verificación real autenticada: resumen, calendario, repartos, costos por atención y enlace de resumen a gastos aprobados respondieron correctamente. API y web de demo/práctica respondieron HTTP 200. Finanzas no mostró errores de consola; permanecen advertencias de desarrollo de React Router y favicon 404 en login, ajenos a este cambio. No se ejecutaron altas/correcciones clínicas ni concesiones reales, ni se repitió la suite completa: la implementación no cambió en esta etapa, sólo activación y documentación.

La práctica en 8092 permanece en 0019 y la versión recuperada; la demo 8090 tiene el nuevo esquema y servicio activo. La revisión técnica completa y la aceptación/prueba del usuario siguen pendientes; ofrecer al usuario la primera revisión antes de realizar la revisión completa. Sin commit, push ni merge.
