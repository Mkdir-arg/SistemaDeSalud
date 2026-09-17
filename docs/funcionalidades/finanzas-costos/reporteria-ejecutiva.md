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

### Interfaz y tablas del 17/09/2026

El estado de repartos acompaña la descripción del módulo. La comparación usa
controles compactos con nombres accesibles. Gastos y dinero forman dos columnas
independientes: cada una reúne sus indicadores, tendencia y desglose; el detalle
por área y concepto queda junto a su gráfico. Abrir una tabla mensual no desplaza
la otra columna. En móvil se apilan. Los controles de pagos y cobros comparten fila
cuando hay espacio y ya no dejan un hueco sobre su título.

Las tablas conservan filas y columnas a cualquier ancho; no se convierten en
fichas ni repiten el encabezado en cada registro. Los controles de orden y filtro
están siempre en el encabezado. Si falta ancho, se desplaza sólo el contenedor
de la tabla, también con teclado; no se ensancha el documento. En el desglose de
la demo a 1440 px entran las cuatro columnas. La densidad Compacta sigue disponible.

Todas las tablas del módulo ofrecen filtros y ordenamiento, reutilizando
`DataTable`, `useTablaUrl` y los controles financieros existentes:

- Los agregados completos usan `TablaAgregadaFinanzas`: filtros por columna,
  rangos de importes, orden exacto en centavos y paginación. Un desconocido no
  coincide con cero y queda al final al ordenar en ambos sentidos. Los filtros
  del listado no cambian gráficos ni indicadores.
- Los filtros aplicados indican su valor y permiten quitarlos individualmente
  o limpiar la tabla, incluidas las búsquedas de las listas remotas y el desglose.
  El período seleccionado/comparado y las fechas efectivas quedan sobre los
  importes; una versión histórica de reparto se identifica como tal y no suma
  al total vigente. Un mes pasado puede contener registros vigentes: no equivale
  a una versión reemplazada ni a un cierre contable.
- Al abrir otra cifra de dinero se retira la búsqueda previa del detalle para
  que su listado explique la cifra completa. Se conserva el filtro de período,
  área, estado y contraparte definido por el origen seleccionado.
- Cuentas, movimientos, pendientes, recuperables, historiales y atribuciones
  agregan búsqueda y orden sobre el queryset autorizado, antes de paginar.
  Cuentas ordena por tipo y contraparte; los saldos calculados conservan su fuente
  actual, sin duplicar sus reglas para ofrecer ordenamientos adicionales.
- Las búsquedas de atribuciones y recuperables usan referencias financieras;
  no permiten buscar información clínica no visible. El detalle de reparto
  comprueba todo su alcance antes de filtrar y conserva sus totales completos.
- Los títulos accesibles ocultos de tablas se posicionan dentro de su contenedor.
  Esto corrige el scroll invisible sin recortar contenido ni esconder overflow.

La validación cubre alineación, columnas independientes, teclado, móvil, filtros
reversibles con resultados vacíos, centavos grandes, valores desconocidos,
paginación y conservación del alcance. La demo aislada conserva sus 13 meses,
895 cuentas y 918 movimientos; se verificó además búsqueda, orden y paginación
contra su API real. El usuario identificó como riesgos los filtros poco visibles
y la confusión entre información histórica y vigente; las etiquetas y pruebas
anteriores responden a esos casos. La aceptación de esta presentación queda pendiente.

Skills: interface-design para reutilizar componentes y jerarquía del sistema;
Playwright para interacción y geometría en navegador; systematic-debugging para
identificar el caption fuera de su contenedor como causa del scroll sobrante.

Backend aislado del entorno compartido:

```powershell
cd backend
$env:DJANGO_SETTINGS_MODULE = 'config.settings_financiadores_test'
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
$env:SALUD_URL = 'http://127.0.0.1:5187'
npx playwright test --config=playwright.finanzas-ui.config.js
npm run build
npm run auditar
```

Las pruebas nuevas cubren comparativas, centavos, ajustes, ausencia/base cero,
base negativa, fechas, permisos, fallo de auditoría, reintegros, copagos, vínculos
de resoluciones, conceptos renombrados y conciliación con filtros de detalle.
Playwright cubre ambos períodos, navegación completa, estados, permisos y móvil.
Resultado final: 280 pruebas backend aprobadas, 24 omitidas por requerir
PostgreSQL y 60 subpruebas aprobadas al ejecutar `apps/finanzas/` junto con
`apps/financiadores/test_cobertura.py` y `apps/financiadores/test_recuperacion.py`.
Playwright: 132 pruebas aprobadas, incluidas filas tabulares, filtros visibles
y navegación sin búsquedas heredadas. La última corrección sólo cambia frontend;
no repite backend, cuya validación anterior corresponde a `006de0e`.
Una corrida previa sufrió una recarga durante el caso de error 403; el caso
aisladamente y la suite completa sin ediciones simultáneas pasaron después.
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
- Los e2e usan HTTP simulado y se complementaron con inspección autenticada en la
  demo ficticia SQLite. Sigue pendiente validación con PostgreSQL y aceptación
  funcional de administración.
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
