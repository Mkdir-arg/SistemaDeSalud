# Reportería ejecutiva — issue #39

La pestaña **Reportes** permite comparar lo registrado, explicar sus variaciones y
abrir las fuentes. Se incorpora a Resumen, Evolución y Pagos y cobros; esas vistas
siguen disponibles. La implementación parte de `origin/main` `0c15551`, que ya
contiene los PR #40 y #41.

## Decisión de alcance

Recomendación técnica del agente, a quien el usuario delegó el estudio y las
decisiones de calidad: separar gasto económico de dinero efectivo y utilizar los
vínculos estructurados de cobertura para identificar cobros del financiador.
No atribuir gastos generales a obras sociales por coincidencia de nombres ni por
la afiliación de un paciente. Un copago es un cobro del paciente.

La alternativa de presentar un total que sume gastos, cargos y dinero duplicaría
partidas. Distribuir costos entre financiadores exigiría una regla de atribución
adicional; no se inventa en este incremento. El cruce de cobros usa **prestación**,
mientras que el de gastos y pagos usa **concepto de gasto**.

## Contrato de las cifras

| Lectura | Fuente, fecha y fórmula | Población y detalle |
| --- | --- | --- |
| Gastos aprobados | Gasto vigente + ajustes aprobados, por mes económico | Misma institución, área y sensibilidad del resumen; abre gastos aprobados, con o sin control mensual |
| Gastos por aprobar | Gasto pendiente; ajustes pendientes no alteran el aprobado | Listado con estado pendiente de aprobación |
| Cobros netos | Cobros aprobados − reintegros de cobros aprobados, por fecha efectiva | Movimientos de cuentas por cobrar, incluidos reintegros |
| Pagos netos | Pagos aprobados − reintegros de pagos aprobados, por fecha efectiva | Movimientos de cuentas por pagar, incluidos reintegros |
| Diferencia | Cobros netos − pagos netos | Todos los movimientos aprobados del período; no es disponibilidad ni rentabilidad |
| Variación | Actual − anterior; porcentaje = diferencia / anterior × 100 | Porcentaje sólo con base anterior positiva y registros en ambos períodos; sin inflación |
| Área × prestación × financiador | Obligación → distribución de cobertura o resolución → reserva → financiador/prestación | Relaciones 1:1 desde la obligación; nunca una unión con todas las reservas de la atención |

Se compara el mes elegido con el inmediato anterior o el mismo mes del año
anterior, y se ofrece una serie de 6/12 meses. Son meses calendario completos;
un mes abierto se señala como provisional, sin extrapolar ni prorratear.

La ausencia de registros no demuestra ausencia de actividad económica: las
tarjetas muestran **Sin registros**, la serie deja huecos y no calcula variaciones
contra una base ausente. Los valores cero registrados sí se conservan. Un neto
negativo por reintegros conserva su signo. La ausencia de configuración de
controles mensuales no se interpreta como carga completa.

Ambos períodos muestran cuántos controles conocidos siguen pendientes de carga,
reutilizando `calendario_mensual` y su alcance autorizado. El contador abre esos
controles en el mes y área correspondientes. Un mes con carga o aprobación
pendiente conserva una marca provisional aunque su mes calendario haya terminado.

Los pendientes se consultan aparte. Rechazados no participan del reporte de
dinero. El reparto sigue incluido en el aprobado, sin sumarlo dos veces, y se
mantiene desconocido mientras hay procesamiento pendiente. No se estima un
porcentaje de cobertura hospitalaria sin un universo verificable.

Los nombres de las dimensiones son etiquetas actuales del catálogo. Renombrar un
concepto no divide sus importes en grupos con un mismo enlace; el detalle conserva
los nombres históricos de cada registro.

## API y permisos

- `GET /api/reportes-finanzas/comparativa/`: requiere el alcance de `ver_gastos`.
- `GET /api/reportes-dinero/comparativa/`: requiere el alcance de `ver_dinero`.
- Ambos reciben `institucion`, `periodo_economico` (primer día del mes), `area` o
  `area_sin_asignar`, `comparar=mes_anterior|anio_anterior` y `meses=6|12`.
- `GET /api/movimientos-dinero/` admite filtros aditivos de detalle:
  `tipo_cuenta`, `reporte_pagador`, `reporte_financiador`, `reporte_prestacion` y
  `reporte_concepto`. `null` selecciona una dimensión sin identificar; omitir el
  parámetro no la filtra. Se combinan con fechas, área y estado.
- El reporte devuelve los filtros exactos de cada grupo. El listado aplica los
  mismos vínculos sobre su queryset autorizado; ningún filtro otorga permisos.
- La auditoría incluye las fuentes de todos los meses consultados y conserva el
  mes económico de la cuenta, aunque el dinero se haya movido en otro mes.
  Si falla la auditoría, no se devuelven los importes.
- Se reutiliza la aritmética de los endpoints operativos. El total de dinero
  actual y su desglose se calculan sobre las mismas filas agregadas de una sola
  consulta. Los importes se envían como decimales exactos en cadenas.

No hay nuevas tablas, migraciones, permisos, cachés ni dependencias. No se agrega
acceso del portal del financiador a las finanzas institucionales.

## Diseño y navegación

Recharts **3.10.1**, ya instalado; carga diferida de los gráficos. Tipografía Inter
y superficies, bordes, controles y foco del sistema existente.

- Petróleo `#287f92` para gasto/cobros, ocre `#ad7133` para pagos y gris azulado
  `#82949e` para el período anterior. No califican un aumento como bueno o malo.
- Líneas rectas, sin suavizado que invente trayectorias; pagos también llevan
  guiones. Meses provisionales con puntos huecos, ausencia sin unir huecos.
- Barras horizontales pareadas para comparar importes en una escala común;
  admiten negativos. Se muestran hasta ocho grupos por gasto actual, con todos
  los grupos disponibles en la tabla exacta.
- Ayudas con importes completos en ARS y tablas navegables con teclado. Los
  números de punto flotante sólo posicionan el dibujo; no calculan los importes
  mostrados. Estados de carga, vacío, error y fallo del módulo gráfico explícitos.
- La cifra actual y la anterior abren sus fuentes. El enlace del informe de
  gastos no activa el filtro de control mensual de Evolución. El dinero abre
  movimientos, luego la cuenta y su identificación de origen.
  Cada apertura reinicia la página del listado para no heredar una página inválida
  de una cifra anterior.
- Pantallas verificables en escritorio y a 390 px, usando las tablas adaptables
  del módulo. La etiqueta breve **Reportes** conserva el espacio de las vistas
  operativas.

## Verificación reproducible

### Iteración visual del 17/09/2026

La revisión solicitada por el usuario identificó un encabezado sobredimensionado,
títulos promocionales y explicaciones repetidas que desplazaban las cifras.
Se sustituyen por títulos directos, tarjetas y tamaños acordes al resumen existente.
Las aclaraciones se agrupan en `AyudaFinanzas`, el componente `(?)` del módulo,
con acceso por foco, clic y teclado. Se mantienen visibles fechas, restricciones,
mes abierto, actualizaciones y pendientes navegables de ambos períodos.

Validación de esta iteración: nueve e2e de reportería aprobados, incluidos foco y
Escape en escritorio y límites del panel de ayuda a 390 px; build correcto.
Inspección con Playwright en la demo aislada con API real, a 1440 y 390 px.
La auditoría CSS sigue señalando sólo los dos hallazgos previos de financiadores.
No se modificó backend ni se repitió su suite; los resultados posteriores describen
la validación de la implementación funcional anterior a este ajuste visual.

La skill interface-design guio la reutilización del sistema visual existente;
Playwright permitió contrastar el resultado visible y la interacción de las ayudas.

Backend aislado del entorno compartido:

```powershell
cd backend
$env:DJANGO_SETTINGS_MODULE = 'cauce.settings_financiadores_test'
python -m pytest apps/finanzas/ -q --tb=short
python manage.py check
python manage.py makemigrations --check --dry-run
```

Frontend con Vite en un puerto propio y API simulada, sin escrituras en la demo:

```powershell
cd frontend
npm ci --no-audit --no-fund
npm run dev -- --host 127.0.0.1 --port 5187 --strictPort
# En otra terminal, dentro de frontend:
$env:CAUCE_URL = 'http://127.0.0.1:5187'
npx playwright test --config=playwright.finanzas-ui.config.js
npm run build
npm run auditar
```

Las pruebas nuevas cubren comparativas, centavos, ajustes, ausencia/base cero,
base negativa, fechas, permisos, fallo de auditoría, reintegros, copagos, vínculos
de resoluciones, conceptos renombrados y conciliación con filtros de detalle.
Playwright cubre ambos períodos, navegación completa, estados, permisos y móvil.
Resultado final: 276 pruebas backend aprobadas, 24 omitidas por requerir
PostgreSQL y 60 subpruebas aprobadas al ejecutar `apps/finanzas/` junto con
`apps/financiadores/test_cobertura.py` y `apps/financiadores/test_recuperacion.py`.
Playwright: 127 pruebas aprobadas, incluidos nueve casos nuevos del reporte.
Build, comprobaciones de Django, ausencia de migraciones y validación de OpenAPI
correctos. La auditoría CSS conserva los dos hallazgos preexistentes descritos abajo.

Se aplicaron brainstorming para delimitar magnitudes, interface-design para la
jerarquía y navegación, Playwright para verificar escritorio/móvil y code-review
para revisar estándares y requisitos por separado. systematic-debugging orientó
el diagnóstico de dependencias de pruebas y regresiones de espacio en las pestañas.
Las comprobaciones usan el entorno Python temporal y un Vite propio; no modifican
los datos ni la configuración de la demo compartida.

### Standards

La revisión detectó paginación heredada al cambiar de cifra. Se corrigió y el e2e
verifica que el detalle comienza en la primera página. Sin hallazgos adicionales
concretos en la revisión estática de las correcciones.

### Spec

La revisión detectó la misma paginación y la falta de visibilidad de cargas
mensuales conocidas pendientes. Ambos hallazgos están corregidos y cubiertos por
pruebas; los controles conservan período, alcance y vigencia.

Hallazgos pendientes: Standards 0; Spec 0. Las revisiones son evidencia estática,
no aceptación funcional humana ni prueba de los escenarios pendientes de entorno.

## Límites y operación

- SQLite no valida los bloqueos concurrentes de PostgreSQL. Las pruebas que
  requieren ese motor se omiten explícitamente; no equivalen a una aprobación.
- Los e2e usan HTTP simulado. Sigue pendiente un recorrido autenticado con datos
  representativos, PostgreSQL y validación funcional de administración.
- Las consultas son lecturas vivas, no un cierre contable inmutable. Una carga o
  aprobación posterior puede cambiar el detalle al abrirlo. Se informa la fecha
  de consulta; no se promete una instantánea transaccional común entre meses ni
  entre el reporte de gastos y el de dinero.
- El cálculo recorre un máximo de 13 meses (12 de serie y uno de comparación).
  La cantidad de grupos no tiene un límite artificial que omita fuentes. No hay
  una prueba de volumen hospitalario ni un SLA de latencia en este incremento.
- Costos integrados por paciente/profesional, disponibilidad y donaciones siguen
  requiriendo fuentes y atribuciones válidas: este PR no cierra toda la épica #39.
- La auditoría CSS global detecta `text-2xl` y `max-w-sm` en
  `CoberturasHospital.jsx`, ya presentes en la base `0c15551`; quedan fuera del diff.
- Reversión: revertir el cambio de aplicación. No hay esquema ni datos de negocio
  que revertir; las lecturas sólo producen la auditoría existente.

El diseño y los riesgos están documentados para revisión. La delegación del
usuario permite ejecutar el trabajo; no demuestra aceptación visual ni comprensión
humana del diff, que continúan pendientes antes de incorporar el cambio.
