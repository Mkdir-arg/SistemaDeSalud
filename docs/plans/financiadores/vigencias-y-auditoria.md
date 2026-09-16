# Vigencias, acceso histórico y auditoría

## Alcance aprobado

El usuario aprobó implementar el primer bloque recomendado tras revisar los issues #14, #16 y #20: completar vigencias y administración de planes, restringir actividad hospitalaria histórica y hacer sus accesos visibles en auditoría. Se reutilizan las decisiones D21 y Q04: afiliación fija por caso y acceso histórico mínimo a pendientes propios. La integración en admisión/puesto/legajo y las autorizaciones previas siguen como bloques posteriores.

## Reglas y resultado observable

- Administrador de financiador: edita nombre/estado de planes sin cambiar identidad ni código. Inactivar un plan impide nuevas asignaciones; conserva casos y reglas existentes.
- Administrador u operador del financiador: finaliza afiliación con motivo, actor y momento; puede reactivarla expresamente con un plan activo o sin plan. Ambas acciones son efectivas al confirmar. No se introducen bajas retroactivas ni programadas. El padrón manual y Excel rechazan actualizaciones de afiliaciones finalizadas; nunca reactivan ni dan bajas por omisión.
- Cada parte puede cerrar un convenio activo; sólo la contraparte puede rechazar una propuesta. Plataforma puede resolver propuestas. La aceptación sólo aplica a propuestas pendientes. Cada nuevo acuerdo tiene otro registro: los aranceles del anterior conservan su relación original. Hay como máximo un convenio activo o propuesto por par.
- Cerrar un convenio conserva reservas y cargos. Una realización posterior reevalúa el convenio y renueva la aceptación si cambió la condición. Un hecho anterior se recupera con el convenio vigente en su momento. Sin convenio no hay cobertura ni deuda automática del paciente.
- Con convenio y afiliación vigentes, el financiador ve su actividad hospitalaria mínima. Fuera de vigencia, sólo reservas cubiertas pendientes de realización, evaluaciones propias pendientes y obligaciones propias con saldo o movimientos/ajustes por aprobar. Una distribución resuelta no implica cobro. Un copago pendiente no justifica mantener acceso si la parte del financiador ya está saldada.
- El padrón y los consumos externos propios de la obra social no son datos aportados por un hospital y siguen disponibles para administrar su organización.
- Actividad y contador de discrepancias usan el mismo alcance. La paginación ocurre después de acotar los registros.
- Por cada persona e institución efectivamente mostradas en una página de actividad se registra un acceso tipo `financiador`, con usuario, momento y referencias de reservas. Se usa la persona/institución original del hecho cuando existe. El hospital ve sólo su auditoría. Si falla ese registro, la consulta administrativa no entrega los datos; la lectura clínica mantiene su comportamiento previo.

Las concreciones de cierre inmediato, nuevo registro por convenio y criterio económico de pendiente son recomendaciones de implementación del agente dentro del bloque aprobado, no razonamientos retrospectivos atribuidos al usuario.

## Datos, concurrencia y reversión

Migraciones nuevas: `financiadores.0005` agrega evidencia de finalización y restringe la unicidad a convenios abiertos; `auditoria.0003` agrega el tipo de acceso. Los registros anteriores permanecen vigentes: no se inventan cierres ni fechas de aceptación para acuerdos legados.

Finalización/reactivación y actualización de padrón se serializan sobre la identidad del afiliado. Confirmación de reserva y cierre de convenio revalidan bajo bloqueo. Las propuestas se serializan por financiador y una restricción de base impide dos convenios abiertos. La auditoría de actividad y el cálculo de visibilidad no reservan cupo ni registran dinero.

Para detener el circuito se deshabilita su configuración/acceso sin borrar evidencia. No revertir ciegamente la migración de convenios: después de registrar varios acuerdos históricos por par, la antigua restricción de unicidad no puede restaurarse sin tratar esos datos. Este bloque no se aplica a bases reales ni publica cambios.

## Validación

Validado el 15/09/2026:

- PostgreSQL 16 aislado: `apps.financiadores apps.auditoria apps.casos.test_permisos_barrida apps.casos.test_esquema`, **244/244**, sin omisiones, 58,974 s. Incluye seis pruebas concurrentes con conexiones reales: cuatro anteriores y dos nuevas (cierre contra reserva, baja contra actualización de padrón).
- Luego se agregaron cinco escenarios: `apps.financiadores.test_vigencias apps.financiadores.test_concurrencia_vigencias`, **37/37 PostgreSQL**, sin omisiones, 10,403 s. El archivo de vigencias también pasó **35/35 SQLite**. No se volvió a correr la regresión global de todas las apps.
- El pase inicial ampliado de SQLite ejecutó 212 pruebas: tres errores en `auditoria.tests_respaldo` por `SHOW server_version`, exclusivo de PostgreSQL, y cuatro pruebas concurrentes omitidas. Esos módulos se verificaron correctamente en el pase PostgreSQL posterior; no se alteraron pruebas de respaldo para ocultar el problema de entorno.
- `makemigrations --check --dry-run` sin cambios pendientes; OpenAPI `--fail-on-warn` sin avisos; `git diff --check` sin errores. Las comprobaciones de sistema de Django pasaron durante las pruebas.
- `npx playwright test --config playwright.financiadores-ui.config.js`: **36/36**, 41,3 s, con API simulada. Tras ajustar opciones y fechas se repitieron las cuatro pruebas afectadas: **4/4**, 6,4 s. `npm run build`: correcto, 747 módulos, 7,31 s.
- Navegador real sobre demo SQLite: inicio de sesión del segundo financiador, finalización explícita, actividad histórica de dos hospitales, reactivación, cierre de convenio y auditoría hospitalaria filtrada. Se comprobó que no aparece el hospital excluido por el filtro y se inspeccionó la navegación móvil. Cero errores JavaScript del recorrido. La primera ejecución del guion tuvo un selector de texto invertido («Pendiente histórico» frente a «Histórico pendiente»); se corrigió el guion y pasó completo.
- Revisión independiente de Claude, limitada a lectura de este incremento: sin hallazgos accionables. No ejecutó pruebas ni certifica aceptación humana.

La demo se actualizó con respaldo previo y conserva los datos existentes. La instancia PostgreSQL de pruebas es descartable y no usa volúmenes del proyecto. No hubo migraciones productivas, commit ni push.

### Archivos y comprobaciones de aceptación

| Criterio | Implementación | Evidencia |
| --- | --- | --- |
| Baja/reactivación sin reiniciar cupo ni reabrir por Excel | `vigencias.py`, `services.py`, `importaciones.py` | `VigenciasAfiliacionTests`, prueba concurrente de baja/padrón, navegador |
| Cierre/rechazo según estado y contraparte; sin alterar pasado | `vigencias.py`, `cobertura.py`, `cobros.py`, migración 0005 | pruebas de convenio, recuperación histórica con nuevo arancel y cierre contra reserva |
| Acceso histórico basado en deuda propia real | `acceso.py`, `views.py` | pruebas de pagos, copago, resolución posterior, reintegro, ajuste y resumen |
| Hospital puede auditar las personas consultadas | `auditoria/models.py`, `auditoria/mixins.py`, `acceso.py`, pantalla Accesos | pruebas de página/hospital/paciente original, fallo de auditoría y navegador |
| Acciones comprensibles dentro de Cauce | `PortalFinanciadores.jsx`, `CoberturasHospital.jsx` | 36 pruebas UI, recorrido HTTP real, capturas escritorio/móvil |

Se usaron `domain-modeling` para precisar finalización/reactivación e históricos, `interface-design` para reutilizar Cauce y `playwright` para guiar la inspección del navegador. El CLI de Playwright no estaba instalado en la caché: se utilizó la biblioteca ya instalada en el proyecto, sin nuevas dependencias. `systematic-debugging` guio la separación de errores de entorno y del guion de comprobación.
