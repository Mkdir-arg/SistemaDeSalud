# Implementación local de financiadores y cobertura

Fecha: 15/09/2026. Base: `a6bf26c`. El usuario aprobó D1–D27 y todas las recomendaciones Q01–Q13. Cambios locales, sin commit, publicación ni migraciones sobre bases reales.

Último incremento: [cobertura en el circuito clínico](circuito-clinico.md), después de [vigencias, acceso histórico y auditoría](vigencias-y-auditoria.md). Admisión y los puestos acceden al panel desde el caso; la historia del paciente tiene su pestaña de cobertura. Siguen pendientes reportes de actividad completos, conciliación y, posteriormente, autorizaciones previas. No se cerraron issues de GitHub.

## Recorrido disponible

1. Plataforma crea el financiador y da acceso al primer administrador. Una cuenta nueva recibe un enlace de activación de un solo uso para compartir por el canal habitual; Cauce no envía mensajes automáticamente. Una cuenta existente conserva su contraseña.
2. El administrador configura planes y reglas por prestación o categoría del catálogo común. El padrón admite afiliados sin plan, números familiares y documentos con ceros iniciales.
3. El financiador descarga su plantilla personalizada, revisa el resumen y confirma las filas válidas. Puede descargar errores, corregirlos y retomar una importación interrumpida. También registra consumos externos y correcciones.
4. El hospital habilita cobertura explícitamente, vincula sus prestaciones al catálogo común y acepta/proporciona convenios. El arancel general sigue en la configuración de cobros existente; sólo las excepciones acordadas usan un registro adicional.
   El financiador consulta los aranceles vigentes de sus convenios activos, con origen general o acordado, vigencia y estados pendientes. Esa lectura utiliza el mismo cálculo de precio que la evaluación de cobertura; no reserva cupo.
5. Desde el detalle del caso, el hospital elige la afiliación, consulta el reparto, registra la aceptación del paciente por prestación e importe y confirma la reserva. La consulta sola no ocupa cupo. `/finanzas/coberturas` conserva configuración y seguimiento administrativo.
6. El registro clínico genera el hecho durable y convierte la reserva en consumo. Las partes exigibles se integran en las obligaciones existentes de Finanzas. No se registra dinero cobrado automáticamente.
7. Los saldos sin aceptación permanecen pendientes. El personal designado puede rechazar la asunción, asumirlos o registrar un acuerdo documentado con el paciente/financiador. Aranceles y afiliaciones pendientes tienen acciones específicas para completar datos.

## Decisiones que conviene revisar en el código

- `backend/apps/financiadores/models.py`: organizaciones, identidades estables, historial, reglas, reservas, consumo externo y revisión administrativa.
- `permisos.py`: membresías propias del financiador; una membresía de lectura no amplía las áreas del rol clínico. Las decisiones financieras exigen concesiones explícitas.
- `cobertura.py`: precedencia de reglas, meses/años calendario, firma de cotización, bloqueo del afiliado y aceptación ligada al importe mostrado.
- `cobros.py`: reparto, protección de reservas confirmadas, recuperación desde el hecho original, conservación de evaluaciones y prohibición de duplicar obligaciones.
- `importaciones.py`: parser XLSX, límites, personalización, aplicación parcial e idempotencia por fila/lote/referencia.
- `views.py` y `api_hospital.py`: cada operación deriva y valida su ámbito en el servidor.
- `frontend/src/pages/financiadores/`: portal separado del contexto hospitalario y pantalla de cobertura para el hospital.

## Reglas operativas importantes

- El cupo pertenece al afiliado dentro del financiador. No se reinicia al cambiar de hospital, plan, número de afiliado o al corregir explícitamente su documento.
- Un cambio de financiador crea un ámbito independiente; volver al anterior conserva su consumo del período.
- Corregir la afiliación del caso exige resolver antes sus reservas abiertas. Las correcciones de una prestación ya realizada se registran aparte y no sustituyen la selección del caso.
- Los consumos externos tardíos preservan reservas, cargos y aceptaciones anteriores; señalan discrepancias y afectan la disponibilidad siguiente.
- Las reservas no vencen automáticamente. El valor inicial de antigüedad es **7 días**, configurable entre 1 y 365; sólo modifica la bandeja de revisión.
- El personal de Finanzas no certifica por su solo rol que una prestación no se realizó. La liberación exige personal clínico autorizado, confirmación y motivo.
- Completar un arancel exige `resolver_cobertura` y `configurar_cobros`. Resolver un saldo no crea una entrada de caja.
- Un hospital activado no vuelve al cobro legado por falta de selección de afiliación o por un error de evaluación.
- Una excepción con importe vacío registra expresamente el retorno al arancel general; no representa una negociación pendiente. La evaluación guarda el origen del precio y ese retorno. Si falta el arancel general y no hay uno acordado, el resultado es «Arancel pendiente».
- Las autorizaciones previas y esperas clínicas de L7 continúan fuera de esta primera entrega. No se bloquea atención clínica por un problema de cobertura.

## Importación y conservación

Se incorporan `openpyxl>=3.1.5,<4` y `defusedxml>=0.7.1,<1`. Los valores iniciales son límites técnicos conservadores, no estimaciones de demanda aportadas por el usuario:

| Límite | Valor inicial | Ajuste en settings |
| --- | --- | --- |
| Archivo comprimido | 5 MiB | `FINANCIADORES_XLSX_MAX_BYTES` |
| Contenido expandido | 25 MiB | `FINANCIADORES_XLSX_MAX_EXPANDIDO` |
| Entradas ZIP | 128 | `FINANCIADORES_XLSX_MAX_ENTRADAS` |
| Filas | 2.000 | `FINANCIADORES_XLSX_MAX_FILAS` |
| Lectura | 30 segundos, control cooperativo | `FINANCIADORES_XLSX_MAX_SEGUNDOS` |
| Confirmación por llamada | 100 filas / 10 segundos | Procesamiento recuperable en el servicio |

Se valida la firma de la plantilla y el catálogo vigente del financiador. Los identificadores se tratan como texto. Fórmulas, macros y estructuras incompatibles se rechazan; la exportación de errores fuerza texto literal.

Se guardan las filas y resultados necesarios para continuar/corregir, no el archivo original ni una URL pública. Las descargas requieren acceso vigente y generan auditoría. No se programa una purga automática sin una política de conservación definida por la organización.

Las filas viven en JSON en el lote. Este diseño evita un trabajador nuevo y permite recuperación con los límites actuales; si la demanda exige lotes considerablemente mayores, corresponde medir y normalizar filas antes de elevar esos límites.

## Activación y reversión

Las migraciones son aditivas. No convierten `Ciudadano.obra_social` en una afiliación verificada ni modifican obligaciones anteriores. No asignan permisos a usuarios existentes.

Antes del piloto: aplicar migraciones en el entorno autorizado, configurar catálogo/vínculos, convenio, padrón, reglas, aranceles y concesiones; verificar el recorrido con la configuración del destino y acordar la política de conservación. Luego habilitar el hospital explícitamente.

Para detener nuevas operaciones, deshabilitar la configuración del hospital y los accesos de escritura que corresponda. Las reservas ya comprometidas, hechos, revisiones y deudas permanecen recuperables. No revertir destructivamente las migraciones ni liberar reservas por un apagado del módulo.

## Comandos de validación

Desde `backend`, usando un entorno con `requirements.txt` instalado:

```powershell
python manage.py check --settings=cauce.settings_financiadores_test
python manage.py makemigrations --check --dry-run --settings=cauce.settings_financiadores_test
python manage.py test apps.financiadores --settings=cauce.settings_financiadores_test --noinput
python manage.py test apps.accounts apps.casos apps.finanzas apps.financiadores --settings=cauce.settings_financiadores_test --noinput
python manage.py spectacular --settings=cauce.settings_financiadores_test --file esquema.yml --fail-on-warn
```

`settings_financiadores_test` fuerza SQLite en memoria y no hereda una base real. La regresión amplia incluye pruebas antiguas que inspeccionan `FOR UPDATE`; necesitan PostgreSQL y no pueden certificarse mediante SQLite.

Para las pruebas concurrentes se agregó `settings_financiadores_postgres_test`. Exige `CAUCE_TEST_POSTGRES_URL` apuntando exclusivamente a `localhost`, `127.0.0.1` o `::1`, base `cauce_financiadores_test`; rechaza otros destinos. El servidor local dedicado debe existir antes:

```powershell
python manage.py test apps.financiadores --settings=cauce.settings_financiadores_postgres_test --noinput
python manage.py test apps.accounts apps.casos apps.finanzas apps.financiadores --settings=cauce.settings_financiadores_postgres_test --noinput
```

Desde `frontend`:

```powershell
npx playwright test --config playwright.financiadores-ui.config.js
npm run build
```

## Evidencia de demostración real

Se levantaron Django y Vite sólo en loopback, con una SQLite temporal y personas ficticias. El navegador inició sesión en el portal, creó plan/regla/afiliación, descargó una plantilla, importó una fila válida y una rechazada, confirmó una y descargó errores.

En el hospital, la evaluación mostró arancel **100**, financiador **80**, paciente **20**. Se aceptó el copago y se confirmó una reserva. La realización ficticia se registró invocando el servicio clínico del backend en esa misma base temporal. El navegador verificó reserva realizada/resuelta y las dos cuentas por cobrar: **80 y 20, con dinero registrado 0**. Esta evidencia verifica navegador/API/datos; la realización dentro del motor clínico completo no se recorrió desde el navegador.

Un segundo recorrido real verificó actividad hospitalaria, corrección de documento conservando la identidad, activación de una cuenta nueva, ingreso como auditor de sólo lectura, desactivación y afiliación actual del caso. El pase definitivo no presentó errores JS/HTTP. Las capturas y archivos ficticios quedaron en `%TEMP%\\cauce-financiadores-live-ui`.

## Resultados de validación

- Regresión completa en PostgreSQL 16: `apps.accounts apps.casos apps.finanzas apps.financiadores`: **761 pruebas aprobadas, sin omisiones**, 150,306 s. Incluye pruebas de concurrencia con conexiones independientes, recuperación y conservación histórica. Se utilizó una instancia descartable en loopback, sin datos ni volúmenes reales.
- Después de incorporar la consulta de aranceles y las últimas comprobaciones de aislamiento/activación: `apps.financiadores apps.casos.test_permisos_barrida apps.casos.test_esquema`, **128 pruebas aprobadas, sin omisiones**, 40,330 s, también en PostgreSQL. Este pase volvió a ejecutar todo el módulo con el cálculo de precio compartido. La regresión completa anterior no incluye este último incremento de sólo lectura.
- El pase previo con SQLite detectó dos fallos de integración (anotaciones OpenAPI y registro explícito de permisos), corregidos, y dos comprobaciones de `FOR UPDATE` que requieren PostgreSQL. El pase completo de PostgreSQL cerró esas comprobaciones sin alterar sus pruebas para ocultar el problema.
- `check`, `makemigrations --check --dry-run` y generación OpenAPI con `--fail-on-warn`: sin errores, cambios de modelo pendientes ni avisos de esquema.
- Interfaz: **24 pruebas Playwright aprobadas**, 21,0 s; compilación Vite correcta, 747 módulos, 2,75 s. La suite usa API simulada; el recorrido real descrito arriba es una verificación adicional separada. La nueva pestaña de aranceles tiene pruebas HTTP PostgreSQL y de interfaz simulada, sin un tercer recorrido manual integrado.
- Revisión cruzada: los agentes detectaron y se corrigieron defectos de normalización de documentos, alcance por membresía/área, captura recuperable, conservación de discrepancias y selección del circuito. Claude realizó una revisión final de sólo lectura; su observación condicional sobre arancel nulo motivó documentar expresamente la reversión al general y registrar el origen del precio. No se cambió la regla acordada por el usuario.
- Dependencias instaladas en entornos locales de validación: Python temporal con Django 5.2.15 / DRF 3.16.1 y `npm ci --ignore-scripts` respetando el lockfile. No se actualizaron dependencias existentes ni se modificó el lockfile de frontend.

Las pruebas concurrentes se ejecutaron sobre PostgreSQL: protegen el último cupo entre hospitales y los reintentos de importación. Las advertencias por archivos estáticos ausentes pertenecen al entorno de pruebas del backend; la interfaz se compiló por separado. No se ejecutaron migraciones en una base real ni se incorporaron datos reales.

Al terminar se detuvieron Django/Vite temporales y la instancia descartable PostgreSQL. Permanecen los cambios locales y artefactos de prueba; no se hizo commit, push ni despliegue. `git diff --check` y la revisión de sintaxis Python/UTF-8/espacios finales de los 55 archivos de texto modificados o nuevos no encontraron errores.

### Criterios y evidencia

| Resultado observable | Implementación | Evidencia focal |
| --- | --- | --- |
| Cada financiador configura únicamente su organización | `views.py`, `permisos.py`, portal | `ApiFinanciadoresTests`, pruebas UI de roles y recorrido real de auditor |
| Padrón masivo sin bajas y consumo externo personalizado | `services.py`, `importaciones.py` | `ImportacionesTests`, archivo real con una fila aplicada y otra rechazada |
| Precio general, excepción y retorno al general coherentes | `cobertura.arancel_aplicable`, API de aranceles | `ConsultaFinanciadorTests`, `EvaluacionCoberturaTests`, 4 pruebas UI de aranceles |
| Cupo compartido y períodos calendario | `cantidades_periodo`, `reservar` | `EvaluacionCoberturaTests`, `CoberturaConcurrenciaTests` sobre PostgreSQL |
| Cambiar plan/hospital no reinicia el cupo | identidad estable e historial en `services.py` | `EvaluacionCoberturaTests`, `PadronYPermisosTests` |
| Aceptación por prestación e importe; deuda sin inventar dinero | `reservar`, `cobros.distribuir` | `ReservasYCargosTests`, recorrido real 100/80/20 y cobrado 0 |
| Consumos tardíos preservan lo comprometido y señalan discrepancias | `registrar_consumo_externo`, captura de reservas | `ReservasYCargosTests`, prueba concurrente de consumo/captura |
| Liberar reservas sólo tras confirmar no realización | `liberar`, permisos del área | `ReservasYCargosTests`, `PadronYPermisosTests` |
| Rechazar, asumir o acordar un saldo con trazabilidad | `resolver_saldo`, concesiones explícitas | `ReservasYCargosTests`, `RecuperacionCoberturaApiTests` |
| Un fallo financiero no pierde la atención ni duplica deuda | contexto durable, `completar_pendiente`, revisión/recuperación | `CompletarPendientesTests`, `RecuperacionCoberturaApiTests`, `HistorialCoberturaTests` |

Las pruebas automatizadas verifican las reglas anteriores; la aceptación del piloto y la revisión del equipo hospitalario siguen pendientes. No se midió carga con volúmenes reales ni se definió una política legal de conservación.

## Skills y revisión del alcance

- `grill-with-docs` con `domain-modeling`: convirtió la entrevista en reglas, glosario, alternativas y decisiones trazables; las recomendaciones pendientes se adoptaron por instrucción del usuario.
- `brainstorming`: ordenó el alcance de la primera entrega y la separación de autorizaciones previas.
- `xlsx`: guio las planillas personalizadas y el tratamiento seguro de identificadores, fórmulas y errores.
- `interface-design` y `playwright`: mantuvieron los componentes de Cauce y verificaron recorridos de usuario simulados y reales.
- `systematic-debugging`: se usó para distinguir fallos de integración, restricciones de SQLite y procesos locales desactualizados.

## Revisión e incorporación

La aprobación de recomendaciones habilitó implementación y pruebas locales. No se presenta como validación de comprensión de todos los detalles técnicos ni como aceptación de incorporación. Antes del piloto quedan la revisión del resultado y las políticas operativas de la organización. No quedan decisiones funcionales bloqueantes de Q01–Q13 para esta primera entrega; L7 sigue como incremento posterior.

## Corrección de coherencia visual del portal

El usuario pidió conservar la estructura visual de Cauce y aprobó corregir el portal el 15/09/2026. Los issues #19/#20 requieren una rama de menú propia dentro de Cauce; no piden otra interfaz. La separación del primer portal fue una decisión de implementación del agente, corregida aquí.

- `frontend/src/components/Shell.jsx`: se reutilizan sidebar, encabezado, usuario, colapso, cajón móvil y tema. El contexto de financiador provee su organización, rol, selector y enlaces; el hospital conserva sus controles.
- `frontend/src/pages/financiadores/PortalFinanciadores.jsx`: se retiran el encabezado independiente y las pestañas globales. Las secciones pasan al menú lateral, con el espaciado y los componentes existentes.
- `frontend/src/App.jsx`: rutas de sección bajo `/financiadores`; `/financiadores` conserva la entrada a Planes. La organización seleccionada viaja en la URL para conservarla al recargar y navegar atrás/adelante.
- `frontend/src/api/finanzas.js`: opción `enabled` del hook de permisos, con valor predeterminado verdadero. El portal lo desactiva para no consultar permisos hospitalarios. También se omiten búsqueda de pacientes, notificaciones clínicas, instituciones y tareas hospitalarias dentro de ese contexto, incluso para usuarios mixtos.
- `frontend/e2e/financiadores-ui.spec.js`: navegación adaptada a enlaces y casos nuevos de aislamiento de contextos, rol auditor por URL directa, contexto al recargar, menú colapsado y navegación móvil.

Esta corrección no modifica backend, datos de demostración, membresías ni permisos del servidor. `interface-design` se aplicó para verificar coherencia con los componentes reales de Cauce; `playwright` para inspeccionar la demo en escritorio, móvil y ambos temas. El diseño aprobado se implementó directamente, sin otra ronda de preguntas ni nuevas dependencias.

Validación: **28/28 pruebas de interfaz aprobadas**, 28,0 s; `npm run build` correcto, 747 módulos, 2,82 s. Se inspeccionaron capturas reales de aranceles, padrón y navegación móvil en `%LOCALAPPDATA%\Cauce\demos\financiadores-main2\revision-ui`. No se repitieron las pruebas de backend porque este ajuste no cambió su comportamiento.

El ingreso hospitalario real conservó su menú, búsqueda de pacientes, notificaciones y bandeja de coberturas con los datos ficticios existentes. Claude revisó el cambio comparándolo con copias previas de estos cinco archivos, en modo de sólo lectura, sin hallar regresiones; fue una revisión estática, separada de las pruebas y de la inspección visual. La demo sigue activa en el mismo puerto y conserva sus datos.
