# Demo Hospital General Los Aromos — diseño confirmado

El usuario confirmó el 15/09/2026 reemplazar los datos de localhost:8090 por un escenario completamente ficticio y verosímil, activar las correcciones ya validadas y dejar una única instancia local. Autorizó detener la práctica8092 y su guía8093, conservando archivos de trabajo. No autoriza commits, push, merge ni eliminación de worktrees.

## Resultado observable

- Una institución, Hospital General Los Aromos, con Clínica médica, Cardiología y Diagnóstico por imágenes, equipo y pacientes ficticios. Correos reservados para pruebas.
- Historia económica de octubre2025 a septiembre2026; septiembre es un mes en curso. Gastos, costos directos, repartos, aranceles, cuentas y dinero son magnitudes distintas y no se suman como si fueran independientes cuando representan la misma fuente.
- Predominio de aprobados, algunos pendientes y pagos parciales para presentar. Políticas anteriores a atenciones sintéticas; no modificar la regla productiva ni generar deuda histórica desde una política actual.
- Perfil principal de administración financiera, sin superusuario, y auxiliares clínicos. Concesiones explícitas del escenario nuevo, sin cambiar el mecanismo de permisos.
- Guía imprimible de20–30 minutos: pantalla, acción, explicación y resultado esperado con los datos reales del escenario ficticio.
- Respaldo nuevo de base, archivos y configuración antes del reemplazo; recuperación ensayada en PostgreSQL aislado. Sólo se retiran los datos del entorno8090 autorizado; los respaldos y worktrees se conservan.

## Ejecución

1. Registrar el estado y revisar montajes exactos. Preparar la carga en staging y la guía en paralelo.
2. Crear respaldo con servicios escritores detenidos y comprobar restauración aislada; conservar código/configuración.
3. Ensayar carga desde una base vacía migrada; comprobar cronología, integridad, saldos, permisos y recorrido.
4. Integrar los archivos corregidos sin pisar diferencias ajenas. Reemplazar el conjunto de datos de8090 y deshabilitar semillas genéricas automáticas.
5. Activar backend/frontend/recuperador/repartos de la misma versión. Detener8092/8093 sin borrar sus datos ni código.
6. Validar UI→API→PostgreSQL, revisar cifras y guía final. Dejar casos del recorrido listos para presentar.

## Límites

No se incorporan funcionalidades nuevas, dependencias, reglas financieras ni migraciones adicionales. Los artefactos de validación y credenciales locales no se versionan. Las pruebas automáticas y el ensayo no sustituyen el análisis y la aceptación del usuario antes de presentar.

## Resultado — activado y poblado el15/09

- Única aplicación local en localhost:8090, con su API8010 y procesos de costos/repartos del mismo worktree.8092/8093 apagados; archivos y volumen de práctica conservados. Los contenedores y redes temporales de ensayo se retiraron; Vite18990 detenido tras comprobar su PID.
- Datos anteriores retirados después de restaurar/verificar respaldo:84tablas,36.086filas con huellas idénticas. Base/código/Compose/entorno/adjuntos bajo `C:/Users/Juanito/.codex/finanzas-los-aromos-20260915/respaldo-anterior`. No había adjuntos. SHA256 de base anterior: `429EF7371028B85920EA5D15105C7ECC42C424EEFD3B906364F2F85259A2AEAE`.
- Carga definitiva:1institución,3áreas,6usuarios no superusuarios,30pacientes,170atenciones completadas mediante motor y3casos abiertos;110gastos,277cuentas,277movimientos. De octubre2025 a septiembre2026. Electricidad estacional, limpieza escalonada y mantenimiento irregular; son muestras de tres servicios, no el volumen ni presupuesto completo de un hospital.
- Se creó una semilla manual con base vacía, confirmación explícita, contraseña por entorno, bloqueo exclusivo y transacción. No borra ni mezcla datos ni se ejecuta al arrancar. Si falla la escritura del manifiesto después de confirmar la base, indica que no se repita la carga.
- Septiembre inicial:750.000gastos aprobados,45.000poraprobar,750.000atribuidos,0sindistribuir;115.000costos directos conocidos;610.000pagos,150.000cobros netos. Permanecen ajuste−10.000, pago20.000, cobro10.000, un componente sin valor y un responsable de cobro por completar. Ningún pendiente técnico de reparto.
- Nuevos perfiles con concesiones explícitas. Elena Rivas es administradora institucional, no superusuaria; ese rol incluye clínica. Los médicos no reciben permisos financieros. No se modificó el mecanismo productivo de permisos.
- Guía principal de25–30min sin escrituras, con consultas, cifras, diferencias de dominio y dos ensayos opcionales separados: [Markdown](../../funcionalidades/finanzas-costos/guia-los-aromos.md) / [HTML imprimible](../../funcionalidades/finanzas-costos/guia-los-aromos.html). Credenciales sólo en el archivo local `acceso/acceso-local.txt`, fuera del repo.

### Evidencia y límites

- `python manage.py test apps.finanzas --noinput --verbosity 0` sobre código integrado y PostgreSQL16 aislado:283OK,98,737s. `python manage.py test apps.finanzas.test_seed_los_aromos --noinput --verbosity 1`:7OK; corrida final con variaciones históricas18,561s. Reproduce rollback, guardas, no duplicación, cronología, conciliación y estacionalidad. No es una corrida de la suite de todo el repositorio.
- Verificación independiente READ ONLY de fuente y de8090:8.889comprobaciones,0errores. La restauración definitiva coincidió en84tablas/4.219filas antes de iniciar servicios. Las lecturas auditadas y los latidos posteriores agregan actividad técnica esperada. Manifiestos y reportes en `validacion/escenario-entrega.json`, `validacion/validacion-entrega.json` y `validacion/validacion-8090.json` de la carpeta operativa local.
- Vite742módulos compilados; `makemigrations --check --dry-run`: sin cambios; `git diff --check`: sin errores. Ningún cambio de dependencias/lockfile.
- Navegador Chromium→API real→PostgreSQL: aprobación pago20.000; pago10.000pendiente que reservó sin cambiar confirmados y rechazo que liberó; devolución5.000con reducción conjunta produjo cuenta115.000/neto75.000/pendiente40.000. Gasto100 abrió su cuenta266 existente. Aprobado marcado después de elegir área/concepto autorizados. Componentes, vigencias, políticas, cobertura, reportes, historial y control mensual comprobados.
- Lucía completó caso171: costo16.000 y cargo30.000 a Mutual del Valle, sin preguntas financieras; cola de repartos procesada. Su intento de consultar reporte de dinero recibió403. El ensayo económico/clínico se retiró restaurando la carga inicial:3casos abiertos y reservas originales listos para el usuario. Copia del ensayo conservada en `validacion/ensayo-real.dump`.
- Dump de entrega: `validacion/los-aromos-entrega.dump`, SHA256 `BDF1A7D1145671115CA67E445F987945F7A245800F130207FBDC50A8CE05D1E6`. No restaurar automáticamente después de nuevas operaciones: primero respaldarlas y pedir decisión.
- UI real de escritorio y móvil390 sin errores JavaScript ni desbordamiento horizontal en las pantallas inspeccionadas. Se distinguió esperar el guardado/refresco de leer una vista previa. El primer servidor temporal no publicó su puerto en la red interna; se retiró y el ensayo real se hizo en8090 antes de restaurar la carga limpia, sin cambiar la aplicación.
- No se ejecutaron CI, Firefox/Safari, carga de producción ni todas las integraciones ajenas a Finanzas. Sin commit/push, merge o cierre de issues. La descripción remota del PR no representa necesariamente este estado local.

Skills: `brainstorming` reutilizó el escenario aprobado y documentó límites antes de reemplazar datos; `systematic-debugging` separó fallos de fixtures/conexión del producto; `playwright` contrastó el guion con controles y resultados reales. Tres agentes separaron semilla, guía y validación; la integración y el ensayo final quedaron a cargo de raíz. La comprensión/aceptación del usuario sigue pendiente de su repaso previo a la demo.
