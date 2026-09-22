# Ensayo integral del piloto

## Alcance

Continuación del recorrido aprobado en el [plan](README.md): verificar contratos
existentes con datos ficticios, sin agregar funcionalidades ni modificar la demo.

1. Dos financiadores usan plantillas personalizadas del catálogo común; la carga
   de padrón conserva a los omitidos y la de consumos aplica válidas tras confirmar,
   entrega rechazos y admite reintentos sin duplicar usos.
2. Dos hospitales comparten el cupo de una misma persona dentro del financiador.
   Antes de realizar, se muestran el arancel general y el copago por prestación.
   La aceptación expresa habilita el cargo del paciente; su ausencia deja un
   pendiente administrativo y permite completar la atención.
3. La finalización clínica crea los cargos correspondientes una sola vez; Finanzas
   registra un cobro parcial y los reportes distinguen importe asignado de saldo.
   Un consumo tardío señala discrepancia conservando lo acordado. La resolución
   del copago exige designación expresa, motivo y respaldo de la aceptación.
4. Usuarios hospitalarios y de financiadores no acceden a organizaciones ajenas.
5. Las exportaciones entregan 5.000 filas completas y rechazan 5.001, con auditoría
   y sumas exactas. Medir tiempo, consultas y tamaño en PostgreSQL local; las cifras
   son una referencia de laboratorio, no una garantía de rendimiento en producción.

## Aislamiento y validación

- Prueba de integración HTTP en la base efímera del runner de Django; autenticación
  de usuarios reales del fixture, sin sustituir servicios de negocio por mocks.
- Ensayo de volumen optativo, fuera del descubrimiento normal `test*.py`. Las filas
  sintéticas preparan el volumen; la integración anterior valida cómo se originan.
- PostgreSQL 16 desechable, base `salud_financiadores_test`, puerto local 55438.
  Conservar localhost:5188/8766 y cualquier otro entorno existente.
- Ejecutar las regresiones pertinentes si el ensayo descubre cambios necesarios.
  No incorporar dependencias, migraciones ni nuevas tablas para estas verificaciones.

## Evidencia

Ejecutado el 16/09/2026 en PostgreSQL 16 desechable. No se modificaron reglas de
negocio, pantallas, modelos, migraciones ni dependencias durante este incremento.

### Recorrido integrado

[`test_piloto.py`](../../../../backend/apps/financiadores/test_piloto.py) recorre la
API sin mocks de negocio. La autenticación se inyecta con `APIClient`; los permisos
se evalúan sobre membresías y concesiones reales, sin usar superusuario para operar.
El fixture prepara hospitales, convenios y aranceles; planes/reglas de la mutual,
importaciones, selección, evaluación, aceptación, realización, dinero y reportes
se ejercitan por los endpoints del producto.

| Criterio | Resultado comprobado |
| --- | --- |
| Plantillas propias y carga parcial | La OS ofrece consulta; la mutual, consulta y radiografía. Padrón y consumos incluyen filas válidas y rechazadas; preview no aplica, descarga entrega errores y confirmar otra vez conserva cantidades y resumen. El afiliado omitido sigue vigente. |
| Cupo compartido | Cuatro consultas externas dejan dos usos: hospital A consume uno y B el último. La siguiente consulta aparece no cubierta por $100, con aceptación antes de generar deuda del paciente. |
| Arancel y responsabilidad | Consulta A: $80 a OS + $20 al paciente; B: $160 + $40. Misma persona en mutual conserva seis usos independientes y cobertura del 70 %. |
| Atención sin aceptación | La consulta de mutual finaliza; genera $70 al financiador y deja $30 pendientes, sin deuda del paciente. Repetir el avance de un caso cerrado no agrega cargos. |
| Cobro y separación de reportes | Cobro parcial de $30 repetido con la misma clave crea un único movimiento. Hospital A: $270 asignados, $30 cobrados y $240 pendientes; B: $200 pendientes. La OS informa $240 originales entre ambos hospitales; mutual $70. CSV hospitalario concilia con JSON. |
| Aislamiento | La mutual no descarga lotes ni actividad de la OS; hospital A no consulta ni cobra cuentas de B; el financiador no entra al caso clínico ni al seguimiento hospitalario. |
| Consumo tardío | Un uso externo adicional marca discrepancia, conserva evaluación, aceptación, cobertura e importes anteriores y deja cero disponibles para la siguiente evaluación. |
| Resolución administrativa | Tener permiso de cobro no habilita resolver. Tras la concesión expresa, rechazar la asunción conserva el pendiente; aceptar luego $30 con respaldo genera una única cuenta y conserva motivo/autor. Hospital A queda con $300 asignados y $270 pendientes, sin nuevo movimiento de dinero. |

Desde `backend`, con `SALUD_TEST_POSTGRES_URL` apuntando exclusivamente a la
instancia desechable local y a la base `salud_financiadores_test`:

```powershell
python manage.py test apps.financiadores.test_piloto apps.financiadores.test_concurrencia_clinica apps.financiadores.test_concurrencia_vigencias apps.financiadores.test_cobertura --settings=config.settings_financiadores_postgres_test --noinput
```

**56/56 aprobadas, sin omisiones, 26,742 s**. Incluye las carreras reales del último
cupo entre hospitales, consumo externo contra confirmación/realización y vigencias.
Tras ampliar las aserciones de reintentos y resolución administrativa se repitió
`apps.financiadores.test_piloto`: **1/1 aprobada, 3,628 s**. El primer recorrido del
piloto también pasó en SQLite; la evidencia de concurrencia corresponde a PostgreSQL.

### Volumen real del archivo

```powershell
python manage.py test apps.financiadores.validacion_volumen --settings=config.settings_financiadores_postgres_test --noinput
```

**1/1 aprobada, 20,579 s**. El ensayo crea 5.001 personas/cuentas, 25.005 movimientos
y 10.002 ajustes ficticios mediante `bulk_create`. La preparación tomó 6,296 s y no
está incluida en los tiempos siguientes. No se ejecuta al descubrir `test*.py`.

| Endpoint / resultado | Tiempo | Archivo | Sentencias SQL |
| --- | ---: | ---: | ---: |
| Hospital: 5.000 cuentas | 0,386 s | 967.373 bytes | 6 |
| Financiador: 5.000 personas distintas | 6,727 s | 883.197 bytes | 5.008 |
| Hospital: 5.001, HTTP 400 | 0,284 s | Sin CSV | — |
| Financiador: 5.001, HTTP 400 | 2,234 s | Sin CSV | — |

Se comprobaron los nueve saldos por cuenta y sus sumas exactas, documentos/cuentas
distintos, importe asignado original sin descontar pagos ni ajustes, 5.000 accesos
personales auditados y auditoría hospitalaria de las 5.000 filas. El exceso no agrega
auditoría de exportación ni entrega archivo parcial; ningún reporte cambia el dinero.

**Observación de rendimiento:** el financiador escribe 5.000 accesos individuales y
un evento de exportación. Es la causa observable del mayor número de sentencias.
No se reemplazó el registrador central de auditoría por otro camino de escritura.
Si la latencia acordada para el piloto o una base remota lo requieren, el siguiente
ajuste técnico recomendado es agrupar esas escrituras conservando cada evidencia
individual y el rechazo íntegro ante fallo de auditoría.
Se registró como [issue #42](https://github.com/Mkdir-arg/SistemaDeSalud/issues/42),
con medición reproducible y criterios de aceptación.

La implementación posterior del issue y su comparación de cinco ejecuciones
por tamaño están en [auditoría por lotes](auditoria-por-lotes.md). Conserva las
evidencias personales y reduce los INSERT; los resultados anteriores describen
la versión previa a esa mejora.

Estos tiempos corresponden a `APIClient` dentro de `TestCase`: no incluyen red HTTP,
descarga del navegador ni el commit externo definitivo de una transacción productiva.
No son una prueba de carga con usuarios concurrentes ni una garantía de producción.

### Demo y revisión

Se volvió a ejecutar `verificar-exportacion-seguimiento.cjs` sobre la demo real
`http://127.0.0.1:5188`: descarga de cuentas/pendientes, filtros, encabezados HTTP,
captura vacía por API y vista móvil correctos, sin errores JavaScript. Los CSV y las
capturas permanecen en `revision-exportacion` del directorio de la demo. Sólo se
agregaron accesos auditados; se conservaron pacientes, afiliaciones, cupos y dinero.

Claude revisó el recorrido y no encontró defectos materiales. Se incorporaron sus
dos observaciones menores: comprobar el resumen al reconfirmar la importación y
aclarar que la aceptación habilita el cargo, sin bloquear la atención clínica.
Una segunda revisión de las adiciones finales y del ensayo de volumen no encontró
hallazgos materiales; confirmó los límites de medición descritos arriba.

Skills aplicadas: `brainstorming` para acotar el ensayo al diseño aprobado,
`playwright` para la comprobación del navegador y `pr-reviewer-github` para orientar
la revisión de contratos, permisos y límites. Se reutilizaron herramientas y fixtures
del proyecto; no se agregó otro framework de pruebas.

## Límites y continuidad

- No se repitieron la suite global ni el build/frontend completo: este incremento
  sólo agrega pruebas y documentación. La validación del código productivo anterior
  está en [seguimiento hospitalario](seguimiento-hospitalario.md).
- No se abrió el archivo en Microsoft Excel real. Se comprobaron XLSX con openpyxl,
  CSV con parser y descargas con Chromium; falta la aceptación en la herramienta
  habitual del equipo del piloto.
- El ensayo automatizado demuestra los contratos anteriores; la aceptación del
  recorrido por personal hospitalario y del financiador continúa pendiente. No se
  atribuye comprensión ni aceptación humana a una revisión de código o prueba verde.
- No hay una decisión de negocio bloqueante dentro del alcance aprobado. La demo
  permanece disponible y el PR sigue en borrador. Autorizaciones previas (L7) siguen
  fuera de esta primera entrega.

El análisis posterior del [resto del circuito](continuidad-del-circuito.md) identifica
además la integración pendiente del padrón/legado y Red/FHIR. El recorrido de este
ensayo no pretendía comprobar esos contratos; no los da por terminados.
