# Auditoría de testing

## Resumen ejecutivo

**Respuesta corta:** sí, para cambios acotados del backend hay una confianza razonable; no alcanza todavía para declarar la misma confianza sobre una entrega completa que involucre UI, procesos periódicos o competencia real entre usuarios.

La principal red de seguridad es una suite Django/DRF extensa y ejecutable: **1.016 tests, todos verdes, en 252 s** contra PostgreSQL temporal. Protege reglas del motor, validaciones, aislamiento institucional, permisos y buena parte de las APIs. No se observó una estrategia guiada por porcentaje de coverage.

La confianza baja en los límites entre componentes: la E2E es una demo mutable y serial, no se ejecuta en CI; no hay prueba con dos transacciones reales compitiendo; los jobs se prueban como comandos pero no como servicios programados; y el padrón FHIR externo se simula con mocks. Son los cuatro gaps principales.

No se hicieron preguntas: el repositorio define Guardia como escenario funcional de referencia y permite priorizar sin introducir supuestos de negocio adicionales.

## Alcance y limitaciones

Auditoría read-only de rutas, UI, modelos, motor, comandos, documentación funcional, tests, mocks y configuración local/CI. Se ejecutó únicamente la suite backend porque usa una base de tests creada y destruida por Django.

No se ejecutó la E2E: `frontend/e2e/setup.js` declara que consume pacientes de la fila de la demo compartida y que la corrida no es idempotente. No se modificó código, tests, configuración ni datos.

No se infiere coverage: no hay configuración ni reporte de coverage en el repositorio. La ausencia de cobertura cuantificada no es por sí misma un hallazgo.

## Estrategia actual

- **Backend:** `django.test.TestCase` y `rest_framework.test.APITestCase`, con persistencia real en PostgreSQL temporal. Mezcla pruebas de reglas de dominio con integración HTTP interna; hay pocas pruebas unitarias puras.
- **Regresión funcional:** los módulos de casos, filas, camas, agenda, farmacia, traslados, registros, flujos, FHIR y auditoría tienen suites específicas. Los nombres prueban reglas observables, no sólo implementación.
- **E2E:** Playwright define 235 pruebas en 24 archivos; usa un solo worker y ejecución serial por compartir la misma demo. Incluye UI, accesibilidad visual, sesión y recorridos guiados.
- **Contratos:** la API interna publica OpenAPI y hay pruebas del esquema. No hay evidencia de un contrato versionado contra el padrón FHIR externo.
- **Rendimiento:** hay tests de volumen/N+1 para casos, flujos, red y registros. No se observó una medición de tiempo de suite o presupuestos de duración en CI.

## Estado de la suite

| Capa | Evidencia | Estado |
| --- | --- | --- |
| Backend Django/DRF | `docker compose exec -T backend python manage.py test --verbosity 1` | 1.016 verdes en 252,334 s |
| E2E Playwright | `docker compose exec -T frontend npm run e2e -- --list` | 235 declaradas; no ejecutadas por mutar la demo |
| Unitarias puras | Hay algunas `SimpleTestCase` y mocks, pero no una capa separada predominante | Parcial |
| Integración HTTP/DB | `APITestCase` sobre endpoints y BD temporal | Fuerte |
| Contrato externo | Mocks de `urlopen` para padrón FHIR | Parcial |
| Coverage | Sin configuración encontrada | No evaluable, fuera de objetivo |

Las advertencias HTTP y de fallos simulados que aparecieron durante la suite corresponden a casos negativos esperados. También apareció la advertencia de Django por falta de `/app/staticfiles/`; no falló la suite, pero agrega ruido al diagnóstico.

## Flujos críticos inferidos

1. **Guardia:** admisión, triage, prioridad, fila/box, conducta, alta, observación, derivación, estudio/interconsulta de ida y vuelta e internación.
2. **Acceso clínico y multinstitución:** identidad, membresía activa, rol/capacidad, área/grupo responsable y alcance de datos clínicos.
3. **Camas y farmacia:** asignación/egreso, stock, lotes, consumos, transferencias y pedidos.
4. **Agenda y traslados:** reserva/confirmación/ausencia y circuito de derivación entre efectores.
5. **Diseño de flujos y formularios:** publicación inmutable, versionado, grafo válido y compatibilidad de los casos en curso.
6. **Procesos de soporte:** reloj de tiempos, recordatorios, saturación de red, respaldos verificados y FHIR.

## Matriz de cobertura de riesgo

| Flujo | Riesgo | Tests actuales | Comportamiento protegido | Gap | Tipo recomendado | Prioridad |
| --- | --- | --- | --- | --- | --- | --- |
| Guardia, fila, derivación e internación | P0: prioridad o transición clínica incorrecta | Motor/API de `casos`, filas exclusivas, camas, E2E de fila y detalle | Validaciones, obligatoriedad de box, orden de fila, subprocesos, tiempos y transiciones | No hay evidencia de un recorrido completo, descartable y obligatorio que encadene todos los actores | E2E de aceptación aislada | P1 |
| Acceso clínico, roles y dos instituciones | P0: exposición u operación fuera de alcance | `accounts`, `casos`, `registros`, `auditoria`, `fhir` y barrida de permisos | 401/403, alcance institucional, inmutabilidad y capacidades | No se confirmó una matriz generada desde las capacidades; el riesgo residual es de cambios en rutas/acciones nuevas | Mantener integración API y sumar caso al introducir permisos/rutas | Cubierto en backend |
| Camas, llamadas y stock | P0: doble asignación, doble llamado o descuento duplicado | Reglas de motor, guardas, API y transacciones | `atomic`, bloqueos declarados, estados inmutables, saldo y trazabilidad | No hay `TransactionTestCase` ni dos conexiones reales compitiendo por el mismo recurso | Integración concurrente contra PostgreSQL | P1 |
| Jobs: tiempos, recordatorios, saturación y respaldo | P1: caso detenido, aviso perdido o respaldo no recuperable | Tests de comandos, `latidos`, mock de subprocess y E2E de aviso de proceso detenido | Lógica de vencimiento, no duplicación de avisos, rotación y recuperación de errores | No se prueba el ciclo de servicios Compose ni la detección de una falla real del job | Integración de proceso/health en entorno efímero | P1 |
| Padrón FHIR e interfaz FHIR | P1: interoperabilidad rota o degradada silenciosamente | API FHIR, serialización, filtros y `tests_cliente.py` con mocks | Formato local, autorización y manejo de timeout/401/JSON inválido | Sin contrato ejecutable contra ejemplos/versiones acordadas del padrón externo | Contract test por fixtures versionadas | P2 |
| Editor, formularios y publicación | P1: configuración válida visualmente pero no ejecutable | `flujos`, `formularios`, ensayos y E2E del editor | Grafo, borradores/publicadas, clonación, rollback de ensayo y validación de campos | Varias E2E pueden omitirse por datos de demo | Fixture de escenario de diseño estable | P2 |

## Gaps principales

1. **P1 — E2E repetible y obligatoria para Guardia.** La suite actual comprueba partes valiosas, pero depende de una demo con más de 100 casos y consume la fila. No es una barrera de regresión confiable para cada cambio.
2. **P1 — Concurrencia real.** El código usa bloqueos y transacciones, pero las pruebas actuales no ejercitan contención entre dos transacciones/usuarios sobre cama, fila, pedido o stock.
3. **P1 — Jobs como servicio operativo.** La lógica se prueba; falta probar que cada comando se ejecute, falle de forma visible y se reporte desde el proceso programado.
4. **P2 — Contrato del padrón FHIR.** Los mocks cubren errores del cliente, no compatibilidad continua con el contrato externo.

## Tests frágiles o de bajo valor

- La E2E contiene ocho omisiones condicionales vinculadas a la forma de la demo (cola, versiones, triage, cama ocupada, responsables). Son honestas, pero reducen la garantía cuando una precondición falta.
- `frontend/e2e/_tmp_caso7.spec.js` y `_tmp_turnos.spec.js` se cargan como parte de la suite y crean/alteran agendas. Son pruebas temporales y con nombres no orientados a una garantía estable.
- Capturas, contraste y ausencia de desborde aportan valor visual, pero no reemplazan un recorrido clínico transaccional.
- El E2E se ejecuta en serie por diseño. Evita interferencia, pero una prueba que deja la demo en otro estado puede afectar a las siguientes y volver difícil repetir una falla.

## Integraciones y procesos asíncronos

`correr_tiempos` usa `select_for_update(skip_locked=True)` y existen pruebas de reactivación/alerta. Farmacia, camas y fila también usan `transaction.atomic` y bloqueos explícitos. Esto es una fortaleza de implementación; no es evidencia suficiente de comportamiento bajo contención real.

El Compose corre `correr_tiempos`, `recordar_turnos` y `alertar_saturacion` en un bucle que continúa tras un error. La aplicación tiene latidos y la UI prueba el aviso de proceso detenido, pero no se verificó una integración que provoque y observe ese fallo desde el servicio.

El cliente de padrón FHIR maneja timeout, 401 y JSON inválido mediante mocks. La API FHIR propia tiene pruebas de recurso, filtros y permisos. No se halló un sandbox, fixture compartida por proveedor ni un acuerdo de versiones del padrón externo.

## Fixtures y mocks

No se encontraron factories, fixtures declarativas, `pytest` ni librerías de contratos. El backend construye datos de forma explícita en los `setUp`, lo cual deja las reglas legibles pero hace costosa la preparación de escenarios complejos.

La demo E2E se valida, no se recrea automáticamente: `setup.js` falla con instrucciones para sembrarla. Los mocks se concentran en bordes apropiados (HTTP FHIR, `subprocess` de respaldos, caída de BD/latidos); su limitación es que no verifican la compatibilidad con el sistema externo real.

## CI

No hay configuración de CI versionada ni workflows activos/recent runs devueltos por GitHub CLI. El endpoint clásico de protección de `main` devolvió 404; eso no descarta rulesets de GitHub, pero no aporta una barrera verificable.

Por lo tanto, hoy no hay evidencia de que los 1.016 tests ni las 235 E2E sean requisitos de integración. La primera mejora debería ejecutar el backend y un corte E2E aislado en CI, sin transformar esta auditoría en una meta de coverage.

## Fortalezas

- Suite backend amplia, verde y ejecutable en un tiempo aceptable para CI.
- Pruebas negativas de permisos, validaciones, métodos no permitidos e inmutabilidad.
- Riesgos de multinstitución cubiertos en varios módulos, no sólo en login.
- Reglas críticas implementadas con transacciones y bloqueos, acompañadas por tests funcionales de motor.
- Pruebas de volumen/N+1 para pantallas y consultas relevantes.
- E2E con chequeo temprano de salud y precondiciones, trazas y capturas ante fallas.

## Riesgos no confirmados

- Prioridad operativa real entre Guardia, internación, farmacia, agenda y red fuera del escenario de referencia.
- SLA, versionado y garantía disponible del padrón FHIR externo.
- Existencia de rulesets de GitHub no expuestos por el endpoint clásico.
- Comportamiento de bloqueos bajo la carga y configuración PostgreSQL de producción.
- Restauración de un respaldo contra una base de volumen y esquema reales; las pruebas de comando no sustituyen un ejercicio operativo.

## Issues derivados

Se proponen cuatro issues, todos centrados en protección de comportamiento y no en porcentajes de coverage:

1. E2E descartable de Guardia y ejecución en CI.
2. Pruebas concurrentes reales para recursos exclusivos.
3. Verificación de jobs programados y sus fallos observables.
4. Contrato versionado para la integración de padrón FHIR.

## Issues

- [#5 — Hacer repetible y obligatoria la aceptación E2E de Guardia](https://github.com/Mkdir-arg/SistemaDeSalud/issues/5)
- [#6 — Probar contención real en cama, fila y stock](https://github.com/Mkdir-arg/SistemaDeSalud/issues/6)
- [#7 — Verificar los jobs programados como procesos observables](https://github.com/Mkdir-arg/SistemaDeSalud/issues/7)
- [#8 — Versionar el contrato del padrón FHIR externo](https://github.com/Mkdir-arg/SistemaDeSalud/issues/8)
