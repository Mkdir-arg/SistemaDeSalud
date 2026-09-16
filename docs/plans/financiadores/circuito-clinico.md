# Cobertura en admisión, atención e historia del paciente

Incremento del 16/09/2026, sobre las decisiones D1–D27 y recomendaciones aprobadas. Cambios locales; sin dependencias, modelos ni migraciones adicionales en este bloque.

## Resultado observable

- Al ingresar un paciente desde «Mi trabajo», se abre el caso con su panel de cobertura antes del formulario asistencial. Se elige explícitamente una afiliación verificada, una declaración pendiente o atención particular, con motivo, usuario y fecha.
- El padrón elegible se busca con el documento del paciente del caso en el servidor. No se selecciona automáticamente un financiador ni se reemplaza la afiliación cuando cambia su padrón.
- Las prestaciones del paso actual muestran el arancel y las partes del financiador y del paciente. Consultar no ocupa cupo ni crea deuda. El importe se confirma mediante una cotización firmada, válida por 30 minutos y revisada al confirmar.
- La aceptación exige el permiso financiero existente y un consentimiento explícito por prestación e importe. Confirmar sin aceptación permite continuar; al realizar, el saldo del paciente queda pendiente, sin asignarle deuda automáticamente.
- Una reserva abierta se puede reevaluar antes de realizar la prestación. Renovarla exige declarar que aún no se realizó y volver a aceptar el importe. El reemplazo es atómico: la anterior queda liberada con motivo de reemplazo y conserva su evaluación y aceptación; la nueva reserva utiliza el cupo excluyendo la anterior. Un consumo externo tardío mantiene el compromiso ya registrado y su discrepancia.
- Al registrar la atención, la reserva pasa a realizada y genera las obligaciones exigibles. El motor conserva la atención si falla la captura financiera; queda su recuperación administrativa.
- La pestaña «Cobertura» de la historia del paciente muestra las selecciones y correcciones por caso, paginadas y restringidas al hospital y las áreas operables. No expone el libro de cobros. Las lecturas quedan auditadas con la política clínica existente.

La afiliación se registra después de abrir el caso: el ingreso y la atención no dependen de completar un trámite financiero. Se reutiliza la pantalla del caso a la que llegan «Mi trabajo» y los puestos, sin incorporar un nuevo tipo de campo al diseñador.

## Archivos y contratos principales

- `backend/apps/financiadores/clinica.py`: ámbito del caso, datos de lectura, cotización, confirmación y reemplazo de reservas. Muestra primero todas las reservas abiertas, incluso antiguas, más los últimos 50 registros cerrados y 20 selecciones de afiliación. El límite corresponde al historial cerrado; no oculta trabajo pendiente.
- `api_clinica.py`: acciones `/casos/{id}/cobertura/`, `cobertura-afiliacion/`, `cobertura-evaluar/`, `cobertura-confirmar/`; historial `/ciudadanos/{id}/cobertura/`. Respuestas privadas sin caché HTTP.
- `apps/casos/views.py`: usa el mixin de cobertura e inicializa el área del caso con la del flujo al crear el ingreso. La prueba real detectó que antes quedaba vacía: un operador restringido al área recibía 403 en cobertura y el hecho financiero perdía el área de origen.
- `apps/casos/motor.py:avanzar`: bloquea y relee el caso antes de completar el paso. Una confirmación que llega después encuentra el paso actualizado; si confirma primero, la atención captura esa reserva. Una instancia vieja no sobrescribe una actualización concurrente.
- `cobertura.py:seleccionar_afiliacion`: conserva cada selección, agrega su evento a la trazabilidad del caso y actualiza su fecha para descartar formularios viejos.
- `frontend/src/pages/financiadores/CoberturaCaso.jsx` y `HistorialCoberturaPaciente.jsx`: panel y pestaña reutilizando componentes de Cauce. Al cambiar contexto, afiliación o permisos se descartan cotización y consentimiento. Los errores financieros dejan disponible el formulario clínico.
- Integraciones pequeñas en `CasoDetalle.jsx`, `HistoriaDetalle.jsx`, `MiTrabajo.jsx` y nombre legible del recurso en `lib/auditoria.js`. El detalle del caso también corrige el desborde de su columna en móvil.

## Evidencia

El pase de 39 pruebas nuevas de `test_clinica.py` y `test_concurrencia_clinica.py` pasó en PostgreSQL: ingreso HTTP real con operador limitado al área, rechazo de hospital/grupo/área ajenos, cotización alterada o vencida, cambio de paso/arancel/regla, aceptación explícita, renovación sin duplicar cupo, reintento idempotente, conservación histórica, paginación y reserva antigua visible. Tres carreras comprueban atención contra confirmación en ambos órdenes y dos renovaciones simultáneas.

Después de la revisión independiente, se reforzó el recorrido de ingreso para exigir una firma real con matrícula y se agregó el rechazo de atención cuando el profesional no tiene área asignada. Ambas comprobaciones pasaron en SQLite (2/2, 0,244 s); no modificaron código de producción. El conjunto nuevo quedó en 40 pruebas. Esos dos escenarios de firma/asignación no se repitieron en PostgreSQL y no incluyen concurrencia.

Interfaz: 48 pruebas Playwright aprobadas (12 nuevas del circuito y 36 del portal), usando API simulada. La prueba móvil mide los bordes reales del panel además del ancho del documento. Compilación Vite y comprobaciones de migraciones/esquema correctas.

Regresión final: **689/689 pruebas aprobadas en PostgreSQL 16, sin omisiones, 81,593 s**. Comandos ejecutados:

```text
python manage.py test apps.casos apps.financiadores apps.registros apps.auditoria apps.finanzas.test_cobros --settings=cauce.settings_financiadores_postgres_test --verbosity=0
python manage.py check --settings=cauce.settings_financiadores_test
python manage.py makemigrations --check --dry-run --settings=cauce.settings_financiadores_test
python manage.py spectacular --validate --fail-on-warn --file <temporal>/cauce-circuito-openapi.yaml --settings=cauce.settings_financiadores_test
npx --no-install playwright test --config=playwright.financiadores-ui.config.js
npm run build
```

Se usó PostgreSQL local descartable, sin volúmenes de datos reales. Los primeros intentos detectaron limitaciones de `FOR UPDATE` en SQLite y expectativas de pruebas que se estaban ajustando al contrato de renovación; la regresión final pasó en PostgreSQL con el contrato definitivo. No se ejecutó toda la suite global del repositorio ni se validó infraestructura productiva. Los errores inyectados por pruebas de recuperación son deliberados y no indican fallos del pase final.

Recorrido adicional con navegador, API y SQLite de demo reales, sin interceptar respuestas ni invocar el servicio de realización desde un script:

1. Usuario `consulta@demo.local` ingresa a Clara desde «Mi trabajo», selecciona su afiliación, consulta y acepta el copago; completa la atención desde su formulario.
2. Caso **7**: obligación del financiador **$8.000**, del paciente **$2.000**, reserva realizada y caso cerrado. La historia muestra la selección y su motivo.
3. Ingresa a Diego con una afiliación declarada pendiente y completa la atención desde el mismo formulario.
4. Caso **8**: prestación realizada, caso cerrado, evaluación pendiente y ninguna obligación financiera. Ambos hechos conservan el área de origen.

La consulta directa a la base dedicada corroboró esos importes y estados. Capturas y scripts en `%LOCALAPPDATA%/Cauce/demos/financiadores-main2/revision-circuito/` y su directorio padre. El ensayo inicial que expuso el área vacía quedó cancelado con motivo, sin borrar su trazabilidad ni registrar prestación.

## Límites y continuidad

- La visibilidad del historial usa el área actual del caso, igual que la operación clínica existente. Una derivación puede cambiar quién puede consultarlo.
- La corrección del área se aplica a nuevos ingresos por API. No se hizo un backfill de casos históricos sin área; esos casos requieren revisión administrativa antes de ampliar accesos o imputaciones.
- Antes del piloto, revisar las asignaciones de área de los profesionales. La revisión de Claude detectó que el alta sin área permitía omitir la comprobación clínica existente. Se conserva `_exigir_firmante`: atender requiere asignación explícita al área, incluso al guardar sin firma. No se adoptó su alternativa condicional de equiparar una membresía sin áreas con acceso clínico a todas, porque ampliaría permisos. La matrícula sigue siendo necesaria sólo al firmar. El alcance financiero sí usa la concesión explícita del área; ahora funciona también en ingresos por API al conservar su área correcta.
- No se libera una reserva por antigüedad ni por cerrar esta pantalla. Cancelaciones y prestaciones no realizadas conservan su revisión explícita del circuito anterior.
- La realización completa corresponde a las prestaciones configuradas en el nodo, como en el motor existente. No se incorpora selección clínica de cantidades o realización parcial en este incremento.
- Próximo bloque: actividad del financiador con filtros y exportación, conciliación de prestaciones/deuda/cobros y seguimiento de pendientes. Autorizaciones previas continúan como L7 posterior.
- Reversión del incremento: retirar las integraciones de pantalla y rutas nuevas conserva reservas, afiliaciones y obligaciones del módulo anterior; no ejecutar una migración inversa ni liberar reservas automáticamente.

Skills: `interface-design` mantuvo la interfaz de Cauce; `playwright` guio los recorridos reales y simulados; `systematic-debugging` permitió distinguir fallos del fixture, del diseño móvil y del alta real. Claude realizó una revisión independiente de sólo lectura y una segunda revisión de la corrección del alta. Sus observaciones sobre áreas y visibilidad de reservas se explicitan arriba: se mantienen los permisos clínicos y todas las reservas pendientes visibles. La revisión técnica no representa aceptación del piloto ni comprobación de comprensión por parte del usuario.
