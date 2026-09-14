# Finanzas: correcciones de revisión y propuesta de resumen interactivo

Fecha: 14/09/2026. Autor de las recomendaciones: agente. No sustituye la definición aprobada del circuito económico.

## Estado y alcance

El usuario autorizó corregir los hallazgos y observaciones de la revisión técnica, y luego aprobó el rediseño descrito abajo y la activación acotada de los dos procesos financieros. Se implementaron el gráfico interactivo, los ajustes de disposición y el enlace clínico autorizado, sin ampliar permisos. Las secciones de propuesta conservan el razonamiento original del agente; el resultado de su ejecución se documenta al final.

Worktree: `C:\Users\Juanito\.codex\worktrees\sistemadesalud-finanzas-costos`, rama `codex/finanzas-costos-incremento-1`, HEAD `6cd2c1d71136809b354a81a72554296bbfd0d0b6` más trabajo local existente. Se preservó el checkout principal. Sin commit, push ni merge.

## Correcciones implementadas

| Hallazgo | Cambio de este pase | Evidencia |
| --- | --- | --- |
| Quitar sensibilidad permitía consultar valores protegidos | `views.py`, `DefinicionComponenteViewSet.perform_update`: exige configuración sensible sobre el componente original antes de desclasificar. No cambia el permiso para marcar un componente como más protegido. | Prueba API: PATCH sin permiso devuelve 403, lectura y alta de valores siguen denegadas; con autorización sensible permite el cambio. |
| A→B→A reutilizaba un reparto histórico | `services.py`, `_crear_reparto`: sólo reutiliza el último resultado si coincide; las nuevas huellas incluyen el predecesor. Conserva compatibilidad con huellas anteriores, unicidad e historial, sin migración. | Secuencia con eventos y registro financiero reales de prueba, sin mock del verificador: pendiente v1 → distribuido v2 → pendiente v3. Reporte final: 100,01 aprobado, 0 distribuido, 100,01 sin distribuir. Reintento no duplica versión. |
| Guía y UI tenían signos opuestos | README funcional mantiene la convención ya usada por API/UI: referencia menos aprobado, con ejemplos positivos y negativos. | Contraste de fórmula, texto y pruebas existentes de control mensual. |
| Configurador sin lectura quedaba bloqueado | `api_repartos.py`, `services.py`, `FormularioReparto.jsx`: verificación con `incluir_importes=false` permite controlar actividad con permiso de configuración, sin evaluar importes ni conceder lectura. | API sin lectura devuelve cantidades y montos nulos; pedir importes o consultar otra área sigue en 403. Navegador simulado registra regla sin consultar gastos. |
| Caché ocultaba errores del detalle | `Finanzas.jsx`, `DetalleGastoRemoto`: error tiene prioridad sobre datos anteriores. | Navegador: éxito→403 y éxito→503 retiran el monto anterior y muestran el estado de error correspondiente. |
| Auditoría agregada perdía el área | `api_reportes.py` y `auditoria.py`: agrupa evidencia según las fuentes ya autorizadas, por área y sensibilidad. | Consulta sin filtro explícito de área aparece para auditor limitado al área; no incorpora otras áreas. Se mantienen pruebas de fallo cerrado. |
| Saldo pendiente no era uniforme | `api_repartos.py`: lista y detalle derivan saldo menos atribuciones; filtros y orden usan esa misma expresión. No reescribe versiones previas. | Versiones antiguas con campo almacenado en cero muestran 200,02 y 100,01 pendientes, se ordenan y filtran por esos valores. |
| Recuperación de costos detenida | `backend/Dockerfile` normaliza CRLF del entrypoint al construir la imagen. Compose desactiva migraciones y siembras del worker de costos; el override de desarrollo monta el código actual. | Causa confirmada en log: `env: bash\r: No such file or directory`. Imagen reconstruida y servicio activado tras la aprobación posterior; ver evidencia operativa al final. |

El modo monetario de verificación conserva el contrato anterior por defecto: requiere configurar repartos y leer gastos dentro del mismo alcance, incluidos los permisos sensibles cuando corresponda. La opción sin importes es explícita; devuelve `incluye_importes=false` y montos nulos. Las claves de caché distinguen ambos modos.

No se actualizaron usuarios, pacientes, casos, gastos ni concesiones de demo. Los tests de backend usan SQLite en memoria; las pruebas de navegador interceptan todas las rutas de API. La aplicación de desarrollo tiene código montado y recarga automática; los procesos de fondo persistentes necesitan reinicio para tomar las correcciones.

## Validación de este pase

- 81 tests seleccionados de catálogo, motor, cola, reportes, auditoría, calendario y API de repartos: OK, SQLite en memoria. Se registró el fallo antes de corregir en cada escenario principal.
- 12 tests de `frontend/e2e/finanzas-ui.spec.js`: OK, Chromium con API simulada. Incluyen los 9 anteriores y 3 regresiones nuevas; validan también ancho móvil y navegación con filtros.
- `docker compose -f docker-compose.yml -f docker-compose.override.yml config --quiet`: OK, sólo lectura.
- Script de arranque normalizado y comprobado con `bash -n`: OK; no ejecuta migraciones ni procesamiento.
- `python manage.py makemigrations finanzas --check --dry-run`: sin cambios de esquema nuevos.
- `git -c core.safecrlf=false diff --check`: OK.
- No se ejecutaron suite completa del proyecto, CI, build de producción, reconstrucción de imagen ni pruebas de concurrencia PostgreSQL. SQLite no demuestra semántica de locks/NOTIFY de PostgreSQL. La corrección mantiene el bloqueo por gasto y el mecanismo de cola existentes.

Comandos reproducibles desde la raíz del worktree y desde `frontend`, respectivamente:

```powershell
docker exec -e DATABASE_URL=sqlite:///:memory: -e DATABASE_SSL=false sistemadesalud-finanzas-demo-backend-1 python manage.py test apps.finanzas.tests.CatalogoCostosApiTests apps.finanzas.tests.RepartoActividadTests apps.finanzas.test_procesamiento.TrabajoRepartoTests apps.finanzas.test_reportes apps.finanzas.test_auditoria apps.finanzas.test_calendario apps.finanzas.test_reparto_api --noinput
node node_modules/@playwright/test/cli.js test --config=playwright.finanzas-ui.config.js
```

Autorización operativa concedida y ejecutada: reiniciar únicamente el servicio de repartos para cargar el código corregido y recrear el servicio de costos con la imagen corregida, sin migrar, sembrar ni borrar volúmenes. El de costos puede procesar pendientes existentes; no es sólo un cambio visual. No se restauró ningún respaldo sobre la demo que el usuario está modificando.

## Análisis del feedback visual

### Intención y consistencia

Destinatario: administración/contabilidad hospitalaria, con necesidad de entender qué se cargó, qué falta aprobar y cuánto de lo aprobado pudo distribuirse, y pasar de una cifra a su evidencia.

Dominio: mes económico, área, concepto, aprobación, ajuste, atención, reparto e historial. La señal propia del módulo debe ser poder seguir un gasto desde el total hasta sus atribuciones sin contarlo dos veces.

Se conservan tipografía, espaciado, bordes y tokens existentes de `frontend/src/styles/tokens.css`: superficie clara de trabajo, gris de estructura, índigo de navegación, verde de resultado confirmado, ámbar de pendiente y rojo de error. No se inventa una segunda identidad visual ni se agrega color ornamental. Las superficies oscuras siguen los tokens semánticos actuales.

Tres opciones a evitar: torta con categorías que se superponen → vistas separadas; tarjetas altas con acciones en una tercera fila → métricas compactas con acción lateral; animación que agrega una librería de movimiento → transición CSS acotada al desplegable financiero.

### 1. Gráfico predeterminado y listado conservado

**Recomendación: barras horizontales como vista inicial**, una fila por combinación área/concepto. Permiten comparar importes cercanos, leer nombres largos y representar ajustes negativos. El dato actual es mensual, no una serie temporal: una línea de evolución requeriría otro reporte, fuera del alcance actual.

- Vista “Gastos”: aprobado y por aprobar, sin sumar la distribución nuevamente.
- Vista “Distribución del aprobado”: distribuido y sin distribuir, dejando explícito que explican el mismo aprobado.
- Clic en una barra/segmento lleva al listado de gastos o repartos con el mismo mes, área, concepto y estado. La ayuda muestra importe exacto en ARS y contexto, no sólo porcentaje.
- Mantener un selector de representación “Barras / Dona / Listado”, predeterminado en barras. La tabla conserva cifras exactas y todos sus enlaces.
- Dona como alternativa para la participación de áreas/conceptos en **una medida elegida**. Nunca poner “aprobado” y “distribuido” como porciones de un mismo total: distribuido ya está dentro de aprobado.
- Ejemplo: 100 aprobado y 80 distribuido significan 20 sin distribuir, no un total de 180. Por aprobar es otra etapa, no otra parte del aprobado.
- Si hay negativos, no dibujar una dona engañosa ni aplicar valores absolutos: explicar y ofrecer barras/listado. Si hay cambios pendientes, distribución desconocida no se dibuja como cero. Sin datos, estado vacío; sin permiso, no se consulta ni se expone información restringida.
- Con muchas categorías, altura acotada y desplazamiento/recorrido accesible; no esconder importes dentro de “Otros” sin un desglose. La tabla y acciones por teclado son una alternativa completa a la interacción con el dibujo.

**Biblioteca recomendada: Recharts**, por la integración declarativa con el React existente y porque cubre barras, tortas/donas, tooltips y eventos necesarios sin construir un motor propio. Se cargaría sólo al entrar al gráfico, manteniendo el listado disponible si la carga falla. No se decidió ni instaló una versión; antes de instalar se verificarán compatibilidad, dependencias transitivas y licencia de la versión elegida. Referencias oficiales: [Bar](https://recharts.github.io/en-US/api/Bar/), [Pie](https://recharts.github.io/en-US/api/Pie/) e [instalación](https://recharts.github.io/en-US/guide/installation/).

Alternativa: Apache ECharts, con importación modular y eventos de exploración. Es una opción válida si aparecen necesidades de visualización más avanzadas; requiere administrar la instancia y su ciclo de vida dentro de React. Para este alcance recomiendo la integración más directa de Recharts, no una capa genérica intercambiable. Referencias oficiales: [importación modular](https://echarts.apache.org/handbook/en/basics/import/) y [eventos](https://echarts.apache.org/handbook/en/concepts/event/).

Hacer gráficos propios en SVG evitaría una dependencia, pero trasladaría a este proyecto el mantenimiento de interacción, accesibilidad y escalas; no lo recomiendo para el motor de gráficos solicitado.

### 2. Estado de procesamiento dentro de la tarjeta de filtros

Mover `ProcesamientoFinanzas` debajo de mes y área, dentro de la misma tarjeta. Se mantiene una sola instancia y su consulta actual: la reubicación no debe duplicar sondeos ni alterar invalidaciones. Estado visible; explicación ampliada en el (?) existente. Sin permiso de lectura de gastos no se monta el estado financiero global.

### 3. Resumen más compacto

Mantener las cuatro cifras, pero reducir las tarjetas de tres niveles verticales a dos: título arriba; importe y acción compacta a la derecha debajo. Ajustar el número de columnas al ancho para no recortar cifras grandes. “Del gasto a su distribución” y su alcance pueden compartir una cabecera compacta; no hace falta una tarjeta introductoria alta ni contenido decorativo para rellenar espacio.

La relación aprobado = distribuido + sin distribuir seguirá visible en ayuda/contexto, para que las cuatro tarjetas no se interpreten como cantidades sumables entre sí. No agregar minigráficos o tendencias sin datos de comparación.

### 4. Abrir caso desde una atribución

Existe la ruta `/casos/:id`; está protegida en frontend por `casos_operar`. El serializador de atribuciones actualmente devuelve la referencia de atención, no el caso, aunque el hecho financiero conserva su relación/origen.

Propuesta: añadir a la atribución sólo una referencia navegable autorizada al caso existente y mostrar “Abrir caso” cuando corresponda. Reutilizar los controles institucionales/clínicos actuales; no conceder acceso clínico por tener permisos financieros, no devolver narrativa o datos de paciente para construir el enlace y no confundir el identificador de evento con el de caso. Caso eliminado/no disponible o acceso insuficiente: referencia financiera sin enlace, con explicación breve. La navegación conserva los filtros financieros al volver.

### 5. Apertura/cierre fluido de atenciones

Actualmente la fila de detalle se monta/desmonta de forma condicional en `tabla.jsx`, por eso el cierre desaparece inmediatamente. Propuesta: transición de altura/opacidad breve, acotada al desplegable financiero, conservando el contenido hasta terminar el cierre. Respetar `prefers-reduced-motion`, `aria-expanded`, teclado y foco; contenido cerrado no debe seguir accesible por Tab. No agregar dependencias de animación ni modificar por defecto el comportamiento de todas las tablas.

## Criterios propuestos para aprobar el rediseño

1. Al entrar a Resumen, se ve el gráfico de barras y se puede cambiar a dona o listado sin perder filtros.
2. El clic conserva área, concepto, mes y estado; dibujo, tooltip y listado concuerdan en el importe.
3. No se superponen cantidades ni se convierten desconocidos/restringidos en cero; negativos conservan signo.
4. El estado de procesamiento está dentro de la tarjeta de filtros y existe un solo sondeo.
5. Las métricas ocupan menos altura sin ocultar importes ni acciones en móvil.
6. Abrir caso respeta permisos y disponibilidad; el permiso financiero no amplía acceso clínico.
7. El desplegable abre y cierra fluidamente, sin salto al desmontar ni animación obligatoria con movimiento reducido.

## Skills y límites de comprensión

`systematic-debugging` y `tdd`: causa, prueba fallida en API/pantalla y corrección verificable; se reutilizaron los puntos de prueba del informe autorizado. `vercel-react-best-practices`: permisos/estado derivados y reutilización de la consulta, sin estados paralelos. `brainstorming` e `interface-design`: separaron el feedback todavía no aprobado de las correcciones, compararon opciones y conservaron la identidad hospitalaria existente. Se amplió la suite Playwright ya presente en el proyecto; no se creó otro flujo de automatización.

El usuario ya aportó los riesgos de confusión, duplicación y asignación incorrecta: los casos de regresión los conectan con pruebas concretas. El diseño y la activación local están aprobados; la aceptación de la implementación mediante el uso del propio circuito sigue siendo humana y está pendiente. Las pruebas no la sustituyen. No se recomienda merge ni despliegue de producción en este estado.

## Ejecución del diseño aprobado

### Segundo pase de UI aprobado por el usuario

El usuario aprobó: integrar tabs y filtros en la misma tarjeta y fila cuando el ancho lo permita; quitar el título introductorio y trasladar el límite de costo total a la ayuda superior; cabecera estable de gráficos con etiquetas accesibles sin fila extra; animación nativa breve de 350 ms; jerarquía en modales de gastos, costos, control e historiales; nombre de atención/flujo en enlaces con autorización clínica; permisos ya otorgados visualmente deshabilitados.

Se mantiene el Modal existente en lugar de cambiar a un panel lateral. No se agregan dependencias, migraciones ni permisos. El nombre procede del nodo de origen (no del paso actual) o del flujo del caso; no se usa el nombre del paciente. Se validarán filtros, importes exactos, protección del título clínico, cabecera estable, movimiento reducido y accesibilidad. El usuario ya aportó los riesgos de confusión y asignación incorrecta; esta ejecución reutiliza esos criterios, sin volver a pedir la definición.

Intento visual: administración hospitalaria debe poder seguir un gasto, su ajuste y sus atenciones sin confundir referencia con dinero aprobado. Se conservan tokens actuales, superficie neutra y separadores suaves, índigo de navegación, verde de confirmado y ámbar de pendiente. Los detalles muestran primero contexto/estado, después importe y desglose, luego historial. Tipografía y espaciado siguen el sistema existente; las cifras usan el token `cifra` y números tabulares.

### Cambios y decisiones

- `ResumenFinanzas.jsx`: barras iniciales, selectores Barras/Dona/Listado y de medida, cuatro métricas de dos niveles, carga diferida y respaldo visible ante fallo del gráfico. `Finanzas.jsx` mueve la única instancia de procesamiento dentro de la tarjeta de filtros.
- `GraficoFinanzas.jsx`: Recharts **3.10.1**, licencia MIT, compatible con React 18; `react-is` **18.3.1** alineado con React. El lockfile sólo agrega la dependencia y su árbol, sin actualizar paquetes anteriores. El motor queda en un chunk separado. Las coordenadas usan Number; no se suman importes en frontend y los tooltips/listados usan las cadenas decimales originales.
- Barras separadas para gastos y distribución, línea de cero para negativos, aviso sin dibujo para distribución incompleta. Dona de una medida, bloqueada con negativos o desconocidos. Todas las categorías siguen disponibles, sin agrupación artificial en “Otros”; scroll acotado y listado accesible por teclado.
- `api_repartos.py`: `caso_navegable` es un identificador nullable. Requiere `casos_operar` en la institución del gasto y un caso existente de esa misma institución. No usa el id histórico como respaldo, ni devuelve narrativa/paciente. La consulta relacionada evita una consulta adicional por atribución. No cambia los controles del recurso clínico.
- `Finanzas.jsx`: enlace a `/casos/:id`, ayuda ante caso no disponible y desplegable financiero con transición CSS de 200 ms, `inert` al cerrar, desmontaje posterior y respeto de movimiento reducido. `tabla.jsx` agrega sólo una opción de relleno; otras tablas mantienen su comportamiento por defecto.
- Guía hospitalaria y ayudas (?) actualizadas. Se conservan datos, configuraciones, worktree principal y PR sin operaciones Git de escritura.

### Activación operativa verificada

Proyecto Compose: `sistemadesalud-finanzas-demo`, con los mismos tres archivos de configuración del entorno existente (base, override de desarrollo y `finanzas-demo/compose.local.yml`). Se construyó la imagen de **costos**, se ejecutó `up -d --no-deps --no-build costos` y se reinició sólo `sistemadesalud-finanzas-demo-repartos-1`.

Antes de arrancar se comprobaron `SEED_DEMO=0`, `SEED_GUARDIA=0` y `EJECUTAR_MIGRACIONES=0`. El log confirma arranque sin migración y pasadas de costos con cero hechos pendientes. Consulta agregada de sólo lectura: ocho trabajos de reparto, cero pendientes, cero errores; latidos recientes de `repartos_eventos` y `procesar_costos`. Frontend 8090 y salud API 8010 responden HTTP 200. No se ejerció una nueva escritura sobre datos de demo para validar NOTIFY.

### Evidencia de aceptación técnica

| Criterio aprobado | Implementación / evidencia |
| --- | --- |
| Gráfico inicial y listado conservado | Pruebas UI de barras por defecto, cambio a dona/listado y fallo de descarga del gráfico con listado operativo. |
| Clic y centavos correctos | Pruebas UI de clic real en barra/porción, filtros mes/área/concepto/estado y tooltip con decimal negativo superior al rango entero seguro de JavaScript. |
| Sin doble conteo ni cero inventado | Vistas separadas; prueba de distribución pendiente sin dibujo ni cero; prueba API A→B→A conserva 100,01 sin duplicación; prueba de ajuste negativo y reporte. |
| Estado dentro de filtros | Una única instancia de `ProcesamientoFinanzas` en el código y captura de la tarjeta con el estado debajo de mes/área. |
| Compacto, móvil y tema oscuro | Capturas verificadas; prueba con 24 grupos mantiene las 48 barras y las 24 entradas de dona, scroll interno y sin desborde del documento en 390 px. |
| Enlace clínico limitado | API permite caso existente autorizado; niega enlace a lector financiero sin capacidad clínica, rol de otro hospital, caso sin relación viva o de otra institución. UI muestra sólo el enlace permitido y conserva filtros al volver. La prueba UI simula un 403 al llegar al caso: no pretende verificar una historia clínica real. |
| Animación accesible | Pruebas UI con movimiento normal/reducido, foco en control al cerrar y eliminación de enlaces del contenido cerrado. |

Resultado: **82 tests backend seleccionados OK** (SQLite en memoria), **20 tests UI OK** (Chromium/API simulada), build de producción y `git diff --check` OK. Chunk final de gráfico: 395,76 kB sin comprimir / 114,99 kB gzip, separado del módulo Finanzas. Sin escrituras de prueba en los datos de demo. Capturas en `%TEMP%/sistemadesalud-finanzas-ui-20260914`.

Fallos intermedios resueltos: contrato de campos actualizado para el identificador nullable; clic de prueba dirigido a la porción y no al hueco de la dona; navegación de prueba espera la pantalla destino antes de volver; selector del error clínico usa el alert real y no un heading inexistente. Una corrida fue afectada por recarga de Vite durante la edición; la corrida final se hizo sin editar el frontend durante su ejecución.

### Límites restantes

- `npm audit`: ocho avisos en dependencias **preexistentes** (cuatro moderados y cuatro altos); dos moderados pertenecen al árbol de producción de React Router. Ninguno corresponde al árbol nuevo de Recharts. No se aplicó `audit fix` ni una actualización ajena al alcance. Requieren una revisión de actualización separada; los enlaces nuevos se construyen con id numérico de servidor, no con destinos arbitrarios.
- No se ejecutan migraciones nuevas, suite completa del proyecto, CI, despliegue de producción ni pruebas de concurrencia PostgreSQL en este pase. Las pruebas de backend usan SQLite en memoria; no demuestran el comportamiento de locks bajo carga concurrente.
- Los servicios de tiempos, respaldos y guía estaban detenidos y no forman parte de los dos reinicios autorizados. No se presenta este trabajo como restauración completa de todo el hospital.
- Skills aplicadas: `interface-design` mantuvo tokens, jerarquía compacta y ayudas discretas; `vercel-react-best-practices` orientó la carga diferida sin estado financiero duplicado; `systematic-debugging` guió la lectura de fallos y su causa. `brainstorming` se retomó desde el diseño aprobado, sin volver a definirlo. `writing-plans` no estaba disponible; se continuó este plan existente.

## Cierre del segundo pase de UI · 14/09/2026

### Próximo pase aprobado: evolución, dos niveles y listas adaptables

El usuario aprobó reemplazar la dona simple por dos niveles, incorporar evolución mensual, quitar scroll horizontal de todas las listas financieras y trasladar el texto informativo de procesamiento a su ayuda. Aclaró que “gastos fijos” significa los gastos esperados configurados en Control mensual, no una nueva clasificación contable.

Plan de ejecución: (1) consulta histórica acotada a 6/12 meses reutilizando calendario_mensual, vigencias, permisos y auditoría existentes; (2) línea por concepto con aprobado y referencia opcional, meses sin control/sin carga como desconocidos y meses incompletos identificados; (3) dos anillos alineados por área/concepto, con aprobado/por aprobar o distribuido/sin distribuir, mismos filtros y centavos; (4) tablas con celdas multilínea y registros verticales en anchos pequeños, sin quitar datos, orden o filtros; (5) ayuda del procesamiento y pruebas de regresión/backend/UI.

Se mantiene la apariencia existente: superficies neutrales, separadores suaves, índigo para navegación/referencia, verde para aprobado, ámbar para carga incompleta, gris para contexto. La lectura de mes, concepto, área, aprobación y reparto prevalece sobre la decoración. No se agregan dependencias, modelos, migraciones ni permisos. Se reutilizan componentes y el plan; no se hace commit por la restricción del usuario. Skills: brainstorming (diseño aprobado), interface-design (jerarquía adaptable), vercel-react-best-practices (carga diferida e identidad estable). writing-plans no está disponible.

Implementados los siete puntos aprobados. Archivos de este pase: `Finanzas.jsx`, `ResumenFinanzas.jsx`, `GraficoFinanzas.jsx`, `CostosAtencion.jsx`, `ConcesionesFinancieras.jsx`, `api_repartos.py`, `test_reparto_api.py`, `finanzas-ui.spec.js`, la guía funcional y este plan. No se modificaron los componentes compartidos Modal/Tabs/Checkbox ni se agregaron dependencias, migraciones o concesiones en este pase.

- Filtros y tabs comparten fila en escritorio; en móvil la navegación tiene scroll propio. La prueba comprueba alineación y ausencia de desborde del documento en 390 px.
- Se eliminaron los dos textos redundantes. La ayuda superior distingue todos los gastos registrados de un costo integral hospitalario, que aún no está implementado.
- La cabecera mantiene altura y posición de controles al pasar entre Barras/Dona/Listado. La prueba compara sus coordenadas, con tolerancia de 2 px.
- Recharts usa animación nativa de 350 ms, sin espera inicial ni rebote. La prueba observa cambios reales de ancho con movimiento normal, ausencia de llenado progresivo con movimiento reducido y ausencia de reinicio tras una consulta con datos idénticos. La dona mantiene clic en la porción completa; su configuración reducida usa el mismo soporte nativo, sin prueba específica de fotogramas de dona.
- Los modales separan contexto/estado, importe destacado, desglose y seguimiento. Se comprobaron importe original 100,01, ajuste −20,00 y resultado 80,01; referencia 12.000,00, aprobado 10.000,01 y diferencia 1.999,99. No cambió el cálculo. Se inspeccionaron capturas de gastos y control en móvil, costos en escritorio y permisos deshabilitados.
- `caso_descripcion` sólo se devuelve cuando también se autoriza el enlace clínico. Se usa el nodo original, no el paso actual, y como respaldo el título del flujo. Pruebas API cubren origen, respaldo, falta de capacidad clínica, otra institución y ausencia de relación viva. No se incorporan datos de pacientes ni narrativa de eventos.
- “Ya otorgado” conserva el disabled nativo, con texto/control atenuados y cursor de bloqueo. Se prueba que un clic físico no lo selecciona ni escribe permisos.

Validación de este pase, separada de los resultados anteriores:

```text
docker exec -e DATABASE_URL=sqlite:///:memory: -e DATABASE_SSL=false sistemadesalud-finanzas-demo-backend-1 python manage.py test apps.finanzas.test_reparto_api --noinput
27 pruebas OK, base SQLite en memoria.

cd frontend
node node_modules/@playwright/test/cli.js test --config=playwright.finanzas-ui.config.js
25 pruebas OK, Chromium con API simulada, sin escrituras sobre la demo.

npm run build
OK. Chunk de gráfico: 395,94 kB / 115,03 kB gzip, cargado por separado.

git -c core.safecrlf=false diff --check
OK.
```

Los fallos intermedios estaban en las pruebas: un clic de alto nivel esperaba que se habilitara un checkbox intencionalmente deshabilitado; un selector omitía el área del nombre accesible; el observador del gráfico se instalaba antes de existir documentElement. Se corrigieron los experimentos y se repitió la suite completa. Las capturas de modales adelantan su animación CSS existente al estado final para inspeccionar contenido legible.

Frontend 8090 y `/api/health/` en 8010 respondieron HTTP 200 al cierre. Los procesos financieros siguen arriba; no se reiniciaron ni se sembraron datos en este pase. No se volvió a ejecutar la suite backend completa, CI ni una sesión clínica real de extremo a extremo. La validación visual usa datos controlados, no sustituye la aceptación del usuario con su propio circuito.

Se conservaron rama `codex/finanzas-costos-incremento-1`, HEAD `6cd2c1d71136809b354a81a72554296bbfd0d0b6`, PR #40 y cambios previos. Sin commit, push ni merge. Skills reutilizadas: `brainstorming` para continuar el diseño aprobado, `interface-design` para jerarquía y tokens existentes, `vercel-react-best-practices` para identidad estable del gráfico y `systematic-debugging` para diagnosticar las pruebas. No se crea un sistema de diseño paralelo.

## Tercer pase: dos niveles y evolución de Control mensual

Definición confirmada por el usuario: “gastos fijos” = gastos esperados incluidos en Control mensual. Se implementa el diseño aprobado sin agregar una clasificación ni cambiar la declaración manual de carga.

### Implementación

- `api_reportes.py`: acción GET `/reportes-finanzas/evolucion/`, con institución, mes final, área opcional, concepto opcional y rango de 6/12 meses. Reutiliza `calendario_mensual`, vigencias históricas, permisos institucionales/territoriales/sensibles y auditoría por área y mes. Si falla la auditoría, no entrega importes. Selecciona inicialmente el primer concepto visible en orden alfabético. Totales con Decimal; ninguna suma financiera usa float.
- `calendario.py` y `views.py`: filtro `control_mensual=true` para abrir exactamente las fuentes que integran el histórico. Usa EXISTS, concepto/área/mes y la versión vigente, sin multiplicar gastos por joins. Distingue el área NULL de otras áreas; no amplía permisos. `Finanzas.jsx` mantiene ese filtro visible y permite quitarlo.
- `ResumenFinanzas.jsx`: evolución por concepto, selector 6/12 meses, referencia opcional y listado de valores exactos con estado/cantidad de controles. Rechaza mostrar datos anteriores ante errores de acceso. El clic lleva al mes y concepto elegidos, gastos aprobados y sólo fuentes incluidas en Control mensual.
- `GraficoFinanzas.jsx`: dos anillos con los mismos pesos y orden; interior por área/concepto, exterior por comparación (aprobado/por aprobar o distribuido/sin distribuir). Etiquetas interiores cuando caben y lista lateral completa, también operable por teclado. Negativos y distribución desconocida no se dibujan como sectores válidos. Línea con meses completos conectados, provisionales como puntos separados y faltantes como huecos. Referencia discontinua, sin sumar al gasto. Se conserva animación reducida y carga diferida.
- `tabla.jsx`, `finanzas.css`, `Finanzas.jsx`, `CostosAtencion.jsx`: opción adaptable sólo para Finanzas. Tabla de ancho fijo y texto multilínea; registros verticales cuando falta ancho. Orden/filtros disponibles en un desplegable en la presentación vertical. No se recortan importes ni se ocultan columnas de datos. Incluye listados, atribuciones e historiales.
- `ProcesamientoFinanzas`: mensaje informativo y última ejecución en su ayuda. Estado corto permanece visible; fallos, pendientes y servicio sin actividad mantienen su aviso.
- Guía funcional y ayudas de la aplicación actualizadas. No se requiere leer una guía para distinguir referencia, gasto aprobado y mes incompleto.

### Evidencia y límites

Pruebas backend dirigidas: `python manage.py test apps.finanzas.test_evolucion apps.finanzas.test_reportes apps.finanzas.test_calendario apps.finanzas.test_reparto_api --noinput`, ejecutadas en el backend local con `DATABASE_URL=sqlite:///:memory:` y `DATABASE_SSL=false`: **59 pruebas OK**. Cubren versiones antes/después de una vigencia, centavos y ajustes múltiples, fuentes fuera de control, área institucional, referencia faltante, estados incompletos, período de cambio de año, permisos sensibles y auditoría caída. No son una prueba de concurrencia ni rendimiento PostgreSQL.

UI: `node node_modules/@playwright/test/cli.js test --config=playwright.finanzas-ui.config.js`, desde frontend: **30 pruebas OK** (58,5 s, corrida final sin edición concurrente del frontend). Los casos nuevos prueban huecos/provisionales, referencia, filtros de drill-down, pérdida de acceso, texto en ayuda, parentesco geométrico de anillos, clics de ambos niveles y listas sin scroll interno en 1440/1024/390 px, incluidos historiales y atribuciones. Capturas inspeccionadas de evolución, dos niveles y control móvil. API simulada: no se crean gastos, pacientes ni permisos en la demo. `git diff --check` también OK.

`npm run build`: OK; gráfico diferido de 418,06 kB / 120,50 kB gzip. No hay nuevas dependencias ni cambios de lockfile en este pase. Frontend 8090 y health 8010 respondieron HTTP 200. No se reiniciaron servicios ni se ejecutaron migraciones, semillas, commits o pushes.

Las advertencias de costos parciales se mantienen: el mes abierto no es una tendencia confirmada; cambiar áreas/vigencias cambia la cobertura comparada; los valores no están ajustados por inflación. El rango de consulta se limita a 6/12 meses, pero no se realizó una prueba de carga a gran escala. No se ejecutaron CI, suite completa del repositorio ni una nueva atención real del usuario. La aceptación funcional sigue pendiente del uso humano, no se infiere del resultado de las pruebas.

Skills usadas: brainstorming desde el diseño aprobado, interface-design para jerarquía y adaptación al ancho, vercel-react-best-practices para carga diferida y datos estables, systematic-debugging para separar fallos de selectores de fallos de la interfaz. Se inspeccionó la skill Playwright; se conservó la suite existente de regresión, aprobada en el plan, en lugar de introducir otro flujo CLI. writing-plans no disponible; se reutilizó este plan.

## Cuarto pase aprobado: espacio, participación y datos históricos

El usuario aprobó mover Evolución mensual junto a Barras / Dos niveles / Listado, ampliar los dibujos y reemplazar la lista lateral con scroll por conceptos debajo. Se descartó mantener la lista a un lado porque limita el diámetro disponible. El centro se utiliza completo, sin etiquetas internas; la identificación y los importes permanecen fuera. No se cambian tipografía, superficies ni controles comunes de la web.

### Implementación y decisiones visibles

- `ResumenFinanzas.jsx`: cuatro representaciones en una misma tarjeta, sin evolución duplicada debajo. La consulta histórica sólo se monta al abrir esa vista y queda accesible aunque no haya gastos en el mes seleccionado.
- `GraficoFinanzas.jsx`: interior completo hasta 70% del radio y exterior 72–96%; cada sector exterior conserva el intervalo angular de su concepto. Interior azul → violeta → rojo según participación relativa visible; exterior verde/ámbar/gris según el estado. Porcentaje aproximado junto a cada concepto, sin sumar dinero para mostrar importes. La ayuda aclara que rojo no equivale a error y que la escala cambia con los filtros.
- Se encontró y corrigió amplificación de ruido numérico: sumas gráficas equivalentes (80,01 + 20 frente a 50 + 50,01) podían terminar en extremos opuestos de una escala relativa casi nula. Una tolerancia acotada al error de representación binaria evita ese contraste falso. No cambia ningún importe contable.
- El resaltado por mouse/foco afecta los dos niveles mediante CSS. `GraficoCircular` y sus datos/celdas/callbacks estables aíslan ese cambio de la animación: en Recharts 3.10.1 la identidad de las props dispara un nuevo ciclo. La prueba reproduce el movimiento al enfocar y verifica geometría estable tras la corrección.
- `finanzas.css`: dimensiones adaptadas al viewport y al ancho real; el círculo no se estira ni desborda en móvil. Barras pueden crecer con su contenido; no se ocultan categorías. La leyenda inferior crece por filas sin desplazamiento interno.
- `finanzas-ui.spec.js`: se actualizaron coordenadas de clic del tamaño anterior; casos nuevos de vista histórica sin gastos del mes, consulta diferida, paletas separadas, pesos iguales, orden de colores, centro completo, foco y conservación geométrica.

### Carga histórica autorizada y acotada

Destino verificado: demo 8090, institución 2 **Hospital Demo Finanzas**, área 5 **Consultorio escuela**. Se usó esa área porque las concesiones actuales habilitan el circuito allí; no se otorgaron permisos nuevos ni se modificaron usuarios. La cuenta de carga/aprobación existente es usuario 8, y la carga pendiente usa la cuenta de admisión existente 6.

Script puntual: `docs/funcionalidades/finanzas-costos/historico_demo.py`. Inspección por defecto; aplicar requiere `FINANZAS_HISTORICO_DEMO=APLICAR_20260914`. No se agrega un comando al backend ni una semilla de arranque. Comprueba identidades/permisos, bloquea la institución durante la transacción, no sobrescribe un lote existente y compara las fuentes previas antes de confirmar.

Resultado: conceptos con prefijo `DEMO-HIST-20260914-`, nombres **Demo histórico · Electricidad / Limpieza / Mantenimiento**; 4 vigencias de control, 36 indicaciones mensuales y 37 gastos (IDs 11–47). Períodos octubre 2025 a septiembre 2026. Electricidad cambia referencia en abril (12.000 a 13.500); Mantenimiento agosto tiene 3.200 aprobado y 1.800 por aprobar. Septiembre es provisional por mes abierto. Las vigencias terminan el 01/10/2026; no se inventan expectativas futuras.

Las 37 solicitudes de cálculo quedaron procesadas, sin errores. Los 36 gastos aprobados producen resultados pendientes **sin_regla**, y el gasto pendiente **fuente_no_elegible**. No se crearon reglas ni actividad clínica para simular atribuciones. Estos importes sí afectan los totales históricos de la demo, identificados por sus conceptos.

Respaldo previo: `C:\Users\Juanito\AppData\Local\Temp\finanzas-antes-historico-20260914-v1.dump` (432.505 bytes), PostgreSQL custom; índice leído con pg_restore --list. No se ensayó restauración de este respaldo ni se restauró sobre la demo. El reintento del script no agregó ni modificó registros. No se recomienda restaurar la base para retirar ejemplos si el usuario siguió trabajando: requeriría una decisión específica sobre esos datos; las fuentes tienen historial inmutable.

### Evidencia del pase

- UI: `node node_modules/@playwright/test/cli.js test --config=playwright.finanzas-ui.config.js`: **32 pruebas OK**, aproximadamente un minuto, Chromium con API simulada. Después sólo se ajustó el encuadre de capturas del caso de participación; ese caso se repitió y pasó. Capturas inspeccionadas del círculo y conceptos móviles en `%TEMP%/finanzas-graficos-visual-20260914`.
- Backend: `docker exec -e DATABASE_URL=sqlite:///:memory: -e DATABASE_SSL=false sistemadesalud-finanzas-demo-backend-1 python manage.py test apps.finanzas.test_evolucion --noinput`: **8 pruebas OK**, base aislada. Los 403/400/503 del log son escenarios negativos previstos.
- Datos reales de demo: consulta de endpoints mediante APIClient de Django autenticado como usuario 8, con comprobación de permisos. Los 36 meses-concepto se conciliaron uno a uno con la fuente aprobada devuelta por `gastos?control_mensual=true`. Se verificaron referencia antes/después de abril y aprobación pendiente de agosto. No es una sesión de navegador autenticada ni una prueba del inicio de sesión.
- `npm run build`: OK, gráfico diferido 419,63 kB / 121,07 kB gzip, sin dependencias nuevas.
- `git -c core.safecrlf=false diff --check`: OK. Web 8090 y health 8010: HTTP 200.
- Worktree financiero conservado, HEAD `6cd2c1d71136809b354a81a72554296bbfd0d0b6`; checkout principal conserva sus cambios previos. Sin commit, push, merge, reinicios ni migraciones.

Riesgos ya señalados por el usuario: confusión sobre impacto, duplicación y asignación incorrecta. Mitigaciones comprobadas: leyendas separadas y ayuda de escala, reintento sin duplicados, conciliación mensual exacta y destino institucional/área explícito con permisos vigentes. Aún falta su aceptación del diseño y comprensión del recorrido; no se deduce de pruebas automáticas. No se ejecutaron CI, suite completa del repositorio, prueba de carga masiva ni una atención clínica nueva.

Skills: brainstorming reutilizó el diseño aprobado (sin reiniciar definición); interface-design guió espacio/jerarquía y leyenda externa; vercel-react-best-practices mantuvo consulta diferida y aisló renders de animación; systematic-debugging permitió reproducir y corregir el contraste numérico y distinguir coordenadas viejas de fallas reales. Playwright se inspeccionó y se conservaron las pruebas existentes autorizadas; writing-plans no está disponible y se reutilizó este plan.

## Quinto pase: correcciones autorizadas de la revisión técnica

Estado: implementado localmente, sin commit ni push. El feedback visual siguiente se planifica aparte y todavía no está implementado.

### Hallazgos, corrección y evidencia

1. **Sin distribuir abría un listado más amplio que el importe seleccionado.** El callback omitía el filtro de saldo: un grupo con 100 distribuidos y 50 pendientes podía abrir ambos. `GraficoFinanzas.jsx`, `ResumenFinanzas.jsx` y `Finanzas.jsx` ahora transmiten un filtro explícito desde gráfico, indicador y listado. `api_repartos.py` admite `sin_distribuir=true`: exige fuente aprobada no reemplazada y saldo calculado distinto de cero, conservando los filtros territoriales y permisos existentes. Incluye negativos por ajustes; no basta con exigir saldo positivo. El filtro activo es visible y removible. No cambian importes ni reglas de reparto.
2. **Cambiar el rango histórico podía cambiar el concepto silenciosamente.** `EvolucionMensual` borraba la selección al cambiar entre 6 y 12 meses, haciendo que el servidor eligiera su concepto inicial. `ResumenFinanzas.jsx` conserva tanto la selección explícita como la inicial devuelta por el servidor. Ante un concepto no disponible, muestra la explicación de la API y ofrece una acción explícita para consultar otro; no conserva un gráfico anterior bajo un error. Se mantiene el retiro de datos ante pérdida de acceso.

Pruebas de regresión nuevas en `frontend/e2e/finanzas-ui.spec.js` y `backend/apps/finanzas/test_reparto_api.py`: primero reprodujeron los fallos y después pasaron con las correcciones. Cubren conservación de área/concepto/mes, filtro removible, importes positivos/negativos/cero, fuentes pendientes excluidas, parámetro inválido, concepto conservado y recuperación explícita cuando no está disponible.

Validación final de este pase:

```text
cd frontend
node node_modules/@playwright/test/cli.js test --config=playwright.finanzas-ui.config.js
34 pruebas OK, Chromium con API simulada; sin escrituras sobre la demo.

docker exec -e DATABASE_URL=sqlite:///:memory: -e DATABASE_SSL=false sistemadesalud-finanzas-demo-backend-1 python manage.py test apps.finanzas.test_reparto_api apps.finanzas.test_evolucion --noinput
36 pruebas OK, SQLite aislada en memoria.

git -c core.safecrlf=false diff --check
OK.
```

Los errores de importación dinámica del log UI pertenecen al caso que simula la caída del gráfico y comprueba el acceso al listado. No se repitieron build de producción, CI, suite completa del repositorio ni pruebas de concurrencia PostgreSQL. No se modificaron datos de demo, dependencias, esquemas, permisos ni procesos. La aceptación visual humana sigue pendiente.

Skills: `systematic-debugging` guió reproducción y regresión antes/después; `vercel-react-best-practices` mantuvo selección y consulta en los componentes existentes. `brainstorming` e `interface-design` se usan para la propuesta siguiente, sin ejecutar el diseño antes de su aprobación.

## Propuesta siguiente: espacio útil, lectura y orden — aprobada

El usuario aprobó esta propuesta y pidió una revisión técnica y visual posterior. Resultado de implementación y revisión en el sexto pase, al final de este documento.

La aclaración del usuario reemplaza la interpretación del cuarto pase: **ocupar el espacio restante no significa imponer un gráfico más alto que ese espacio**. No cambia el modelo financiero ni requiere otra librería; se reutilizan Recharts, los controles y tokens actuales.

### 1. Tamaño y distribución

- Usar el espacio real restante después de cabecera, filtros, indicadores y controles. Priorizar flex/grid existentes; sólo medir altura disponible si el contenedor actual no permite resolverlo con CSS, sin reestructurar el layout global ni ligar el tamaño al desplazamiento del usuario.
- En escritorio, conceptos a la izquierda y gráfico de dos niveles a la derecha. Limitar el diámetro por ancho y alto disponibles; una leyenda extensa no debe agrandar artificialmente el círculo.
- Con contenido que cabe, evitar desplazamiento vertical innecesario. Si hay demasiadas categorías o poca altura, permitir que crezca la página para mantener legibilidad, sin scroll interno de categorías ni horizontal. En móvil, apilar.
- Mantener tarjeta y barra de controles estables entre Barras / Dos niveles / Evolución / Listado. Los listados largos seguirán necesitando desplazamiento natural.

### 2. Paleta y orden de los dos niveles

- Interior completo, sin texto dentro. Ordenar conceptos por participación descendente y reordenar conjuntamente sus sectores exteriores, para conservar alineación e interacción.
- Paleta propia discreta de fríos a cálidos: azul, violeta, magenta, naranja y rojo, seleccionando tonos separados según la cantidad necesaria. Con dos participaciones distintas, usar extremos; incorporar intermedios sólo cuando hagan falta. La posición relativa, no pequeñas diferencias numéricas, decide el escalón. Mayor participación, más cálido; menor, más frío.
- Participaciones iguales deben compartir tratamiento cromático y desempatar su orden por área/concepto; no insinuar diferencias de magnitud inexistentes. Porcentaje, nombre y resaltado siguen siendo necesarios: muchos conceptos no pueden distinguirse únicamente por color.
- **Alternativa recomendada, requiere aprobación:** exterior en tonos neutros y tramas (por ejemplo, sólido frente a rayado), con su leyenda. Esto separa estado de participación y permite ampliar la paleta interior. Mantener verde/ámbar afuera preservaría la convención actual, pero restringiría la paleta interior para evitar confusión. No cambiar los colores de estados del resto de la aplicación.
- Explicar en (?) que el color expresa participación relativa y puede cambiar con el filtro; rojo no significa error. Reutilizar foco/hover, contraste de tema claro/oscuro y movimiento reducido.

### 3. Orden de barras

- Selector compacto **Ordenar**: mayor importe primero (inicial), menor importe primero y área/concepto. Ordena todas las categorías de la representación, no sólo una serie.
- Comparación de gastos: aprobado + por aprobar. Comparación de distribución: distribuido + sin distribuir, equivalente al aprobado. Nunca sumar aprobado y distribuido entre sí.
- Comparar centavos exactos reutilizando el conversor existente, con desempate estable. No agregar consultas ni alterar totales; conservar negativos y estados de importe desconocido sin convertirlos a cero.

### 4. Simplificar Gastos registrados

- Retirar las columnas Importe original y Ajustes. Mantener visible el importe vigente; los valores originales, ajustes y reemplazos permanecen en el detalle con su historial actual.
- Conservar trazabilidad y acciones. Revisar enlaces guardados: ningún filtro previo sobre las columnas retiradas debe quedar oculto o imposible de quitar.

### 5. Control mensual

- Mostrar **-** cuando no hay referencia, con descripción accesible; no convertir ausencia en cero.
- Diferencia positiva verde, negativa roja y cero neutro, conservando el signo y el importe exacto. La fórmula sigue siendo **referencia menos aprobado**.
- Aclarar en su (?) que verde indica estar por debajo de la referencia, no ahorro confirmado ni carga completa; puede faltar carga o aprobación. No cambiar el estado ni automatizar cierres.

### Aceptación y secuencia de implementación propuesta

Implementar primero tamaño/layout, después paleta y orden conjunto, luego orden de barras y simplificación de listas. Validar los clics y filtros junto a cada cambio para evitar repetir el hallazgo corregido.

- Revisar 1366×768, 1440×900, 1920×1080 y móvil de 390 px, con 2/3/8/24 categorías. Para conjuntos pequeños, comprobar aprovechamiento del espacio sin crecimiento vertical arbitrario; para conjuntos grandes, todos los conceptos accesibles sin scroll interno ni recortes.
- Probar participaciones iguales, datos cero, negativos, referencia ausente, cambio de comparación y filtros; verificar que sectores interiores/exteriores, orden y navegación sigan correspondiéndose.
- Comparar orden por centavos y suma correcta de cada pareja de series. Verificar importe vigente visible y trazabilidad en detalle tras retirar columnas.
- Repetir la suite financiera UI y pruebas backend sólo si se modifica su contrato. Validación visual y aceptación del usuario separadas de los resultados automáticos.

No se agrega un sistema de diseño paralelo: dominio visual de gastos/control/aprobación/distribución, superficies y tipografía actuales, identificación por área/concepto y ayudas discretas. El cambio distintivo es la separación clara entre participación interior y estado exterior, no una decoración nueva.

## Sexto pase: implementación aprobada y revisión técnica/visual

### Cambios locales

- `frontend/src/pages/finanzas/Finanzas.jsx` y `ResumenFinanzas.jsx`: cadena flex desde el contenedor actual de la página hasta el gráfico. No se cambió Shell ni se agregó medición JavaScript del viewport. Se agruparon controles de evolución; Ver importes mensuales queda junto al selector y despliega la misma información exacta.
- `GraficoFinanzas.jsx` y `finanzas.css`: categorías a la izquierda en escritorio, círculo a la derecha y apilado móvil; no hay scroll interno de conceptos. El círculo se limita por el alto y ancho disponibles, y la lista larga puede extender la página sin hacerlo crecer ilimitadamente. Foco explícito y resaltado de ambas capas, sin reiniciar su animación.
- Paleta discreta por posición relativa, interpolada entre tonos fríos/cálidos separados. Se usan los extremos primero; pesos iguales comparten color. Se calcula el orden en centavos exactos, no sobre la aproximación gráfica. Exterior sólido/rayado neutro con identificador SVG por instancia y leyenda propia. Ambos niveles se reordenan juntos.
- Orden de barras mayor/menor/área y concepto. Suma sólo la pareja visible y no modifica los arrays de la respuesta. `frontend/src/api/finanzas.js` recibe el conversor de centavos ya existente, reutilizado por filtros y orden; no se añade otra implementación ni dependencia.
- Gastos: seis columnas, sin Original/Ajustes; detalle e historial intactos. Los filtros antiguos permanecen visibles/removibles y un orden guardado por columna retirada se explica con una acción para cambiarlo.
- Control mensual: referencia ausente como guion accesible; diferencia positiva verde con signo +, negativa roja y cero neutro. La ayuda explica referencia menos aprobado y advierte que verde no garantiza ahorro ni carga completa. No cambian cálculos, permisos ni estados del backend.
- `frontend/e2e/finanzas-ui.spec.js`: regresiones y capturas de este pase. `docs/funcionalidades/finanzas-costos/README.md`: uso y límites actualizados.

### Validación

- `node node_modules/@playwright/test/cli.js test --config=playwright.finanzas-ui.config.js`, desde frontend: **41 pruebas OK**, 1,2 minutos, Chromium con API simulada, sin escrituras a la demo. Se cubrieron montos grandes separados por un centavo, empates, negativos, desconocidos, ambos órdenes/comparaciones, filtros guardados, detalles, ausencia de referencia, signos, pérdida de acceso y carga diferida fallida. Después se ajustó sólo una fixture de control para que su aprobado y referencia conciliaran con la diferencia; se repitió su caso dirigido.
- `npm run build`, desde frontend: **OK**, Vite 5.4.21, 737 módulos. Gráfico diferido 421,72 kB / 121,90 kB gzip. Sin dependencias ni cambios de lockfile en este pase.
- Revisión de capturas: 1366×768, 1440×900, 1920×1080 y móvil 390×844; 2/3/8/24 categorías, tema claro/oscuro, gastos simplificados, diferencias, barras y evolución. En el escenario de tres categorías, 1440×900 ocupa 836–837 px del contenedor de 836 px (tolerancia de redondeo de 2 px); 1920×1080 ocupa 1016/1016 px. En 1366×768 queda scroll natural, aproximadamente 125–133 px, porque cabecera/controles y contenido legible exceden la altura restante. En móvil no se promete cero scroll: no hay recorte horizontal ni scroll interno de categorías.
- No se repitieron backend, CI, suite completa del repositorio, pruebas de carga ni navegador autenticado contra datos reales: no cambió el backend y las comprobaciones de UI están aisladas. Compilación y pruebas locales no prueban CI ni aceptación humana.

Los fallos intermedios se investigaron con `systematic-debugging`: una prueba esperaba los matices y el diámetro del diseño anterior, otra seleccionaba una clase de eje que no corresponde a la versión instalada de Recharts, y la primera comprobación de altura detectó filas redundantes que todavía forzaban scroll. Se ajustaron controles/layout y se repitió la suite. Los errores de importación dinámica del log final son el escenario intencional de fallo del gráfico, que comprueba que Listado sigue accesible.

### Revisión Standards

Sin hallazgos técnicos accionables en este pase. La revisión independiente comprobó centavos exactos, arrays no mutados, identidad estable de sectores, identificador de trama por instancia, permisos sin ampliar y reutilización del conversor. Se compararon los seis archivos del pase con su copia previa en `%TEMP%/finanzas-ux-base-20260914-162257`, no con todo el worktree sucio. HEAD continúa en `6cd2c1d71136809b354a81a72554296bbfd0d0b6`, sin nuevos commits.

### Revisión Spec

Sin requisitos implementados incorrectamente detectados por la revisión estática independiente. Se verificaron el orden de la suma correcta, el parentesco de sectores, el detalle conservado, los filtros antiguos y la separación entre ausencia y cero. No equivale a una validación de comprensión por usuarios hospitalarios.

### Revisión visual UX: observación detectada (corregida en el séptimo pase)

**UX-1 — legibilidad de Control mensual a ancho intermedio.** En 1440 px de pantalla, el listado dispone de unos 1146 px y conserva nueve columnas. El umbral adaptable actual de `finanzas.css` es 1050 px: todavía muestra la tabla, pero sus encabezados se parten excesivamente (por ejemplo, Concepto esperado y Referencia mensual). No hay desborde ni pérdida de datos, pero la lectura se vuelve incómoda. Es una limitación preexistente, expuesta por esta revisión, fuera del ajuste aprobado de color/guion.

Propuesta pendiente de autorización: activar antes la presentación adaptable **sólo para Control mensual**, o asignar anchos apropiados a sus columnas si eso permite conservar palabras completas. Reutilizar la tabla existente y mantener orden, filtros, importes y acciones, sin agregar scroll horizontal ni cambiar las demás listas. Agregar una prueba de legibilidad del encabezado, no sólo de ausencia de desborde. Evidencia: captura `control-diferencias.png` en el directorio temporal de la suite, caso gastos-simplificados.

Observación perceptual no bloqueante: con 24 categorías hay tonos vecinos; nombres, porcentajes, orden y resaltado siguen siendo indispensables. No se infiere que todos los tonos sean inequívocos para todas las condiciones de visión. No se ocultan ni se agrupan categorías.

Skills: `brainstorming` retomó el diseño ya aprobado sin reiniciar decisiones; `interface-design` guió jerarquía y la crítica visual; `vercel-react-best-practices` mantuvo memorización y consulta diferida; `systematic-debugging` separó defectos de layout de expectativas antiguas de pruebas; `code-review` produjo las dos revisiones independientes; `web-design-guidelines` contrastó foco, controles, contenido adaptable y movimiento reducido con su [fuente oficial](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md). Se inspeccionó Playwright y se mantuvo la suite ya aprobada, sin introducir otro flujo de automatización. No se añadió documentación de diseño paralela.

Se conservó el checkout principal con sus cambios previos. Sin commit, push, merge, reinicios, migraciones ni cargas de datos. Los riesgos humanos ya señalados (confusión, duplicación y área equivocada) se conectan con ayudas, orden exacto y pruebas de navegación; queda pendiente que el usuario confirme la claridad real y autorice, si corresponde, la corrección UX-1.

## Séptimo pase: corrección autorizada de UX-1

El usuario autorizó adaptar antes Control mensual. Se conserva su presentación existente: dos columnas de datos cuando falta ancho y una en móvil; tabla horizontal cuando hay espacio. No se agregan componentes ni dependencias.

- `Finanzas.jsx`: atributo `data-finance-tab` en el contenedor existente. No modifica filtros, cálculos ni consultas.
- `finanzas.css`: excepción entre 1050 y 1440 px de **ancho del contenedor**, sólo para la tabla principal de Control mensual. Las otras listas, historiales y modales conservan sus reglas anteriores; por debajo de 1050 px sigue aplicándose la regla común. No se reduce la tipografía ni se elimina información para hacerla caber. La prueba del límite detectó que 1280 px todavía dejaba palabras cortadas al aparecer la flecha de orden; el umbral final contempla también esos controles.
- `finanzas-ui.spec.js`: prueba de adaptación, palabras del encabezado sin cortes internos, apertura/cierre de controles, orden, filtros, importe y diferencia conservados, acceso al detalle y ausencia de efecto sobre Gastos registrados. El caso falla antes del cambio por no aparecer los controles adaptables y pasa después.
- Guía funcional actualizada para explicar dónde encontrar orden y filtros en esta presentación.

Revisión visual dirigida: etiquetas completas e importes legibles en escritorio intermedio y móvil; tabla conservada a 1920 px. Se acepta más altura por registro a cambio de lectura completa, usando la presentación ya existente. No se afirma que todas las filas quepan en un único viewport.

Skills: `systematic-debugging` para reproducir y verificar la causa; `interface-design` para reutilizar la jerarquía, superficies, tipografía y controles del módulo. No se requiere otra decisión de diseño ni una nueva revisión delegada para esta excepción localizada. Sin commit, push, reinicios ni modificación de datos. La claridad final sigue sujeta a la aceptación del usuario, no se deduce sólo de las pruebas.

Validación final del séptimo pase:

- `node node_modules/@playwright/test/cli.js test --config=playwright.finanzas-ui.config.js`: **42 pruebas OK**, 1,2 minutos, API simulada sin escrituras a la demo. El caso nuevo verifica todos los encabezados a 1366, 1440, 1578, 1734, 1738, 1920 y 390 px, incluidos ambos lados del umbral. Capturas inspeccionadas de 1440, 1738, 1920 y móvil. Se corrigió una expectativa anterior que no admitía el espacio entre separador y nombre en las etiquetas de barras; los importes y su orden eran correctos.
- `npm run build`: **OK**, CSS financiero 3,80 kB / 0,92 kB gzip; sin nuevas dependencias. `git -c core.safecrlf=false diff --check`: OK.
- Frontend 8090 y health 8010: HTTP 200. Checkout principal conservado. No se ejecutaron backend ni CI: este pase sólo cambia presentación y sus pruebas. No se validaron Firefox/Safari ni una sesión autenticada con datos reales.

UX-1 corregida, sin nuevos hallazgos accionables en la revisión localizada. Las pruebas y capturas comprueban lectura y acceso a controles, no sustituyen la aceptación del usuario.

## Evolución mensual multiconcepto — diseño aprobado

El usuario aprueba comparar conceptos simultáneamente y modifica el valor inicial: **todos los conceptos visibles seleccionados**, sin un límite artificial. Selector con búsqueda, casillas y selección total/vacía; etiquetas para quitar o destacar, color estable por identidad, escala común ARS y referencia de un solo concepto elegido. Meses incompletos: puntos huecos sin unir; sin carga/control no se inventa cero. Clic o teclado abre sólo mes/concepto/área/control mensual/aprobación correspondientes. Se mantiene el listado de importes.

Implementación: extender de forma aditiva la respuesta de evolución con todas las series en una consulta, reutilizando calendarios y auditoría; seleccionar localmente sin solicitudes por categoría; mantener selección explícita al cambiar 6/12 meses y señalar conceptos no disponibles. Sin dependencias, migraciones ni cambios de permisos/cálculos. Al cambiar institución/área/mes se conserva el reinicio existente a todos los conceptos del nuevo contexto.

Validación prevista: backend dirigido (series separadas, ajustes exactos, permisos, auditoría, referencia, número de consultas independiente de conceptos); navegador con API simulada (todos por defecto, selección/búsqueda, foco/color, referencia única, rango/ausencia, drilldown, 403, escritorio/móvil). No escribir datos de demo ni publicar cambios.

### Implementación y evidencia final

- `backend/apps/finanzas/api_reportes.py`: agrega `series` y agrupa por concepto en memoria sobre los mismos calendarios, conserva los campos anteriores. No cambia los importes, estados ni permisos.
- `frontend/src/pages/finanzas/ResumenFinanzas.jsx`: selección total inicial, búsqueda/casillas, selección local, referencia única, recuperación de selección al ampliar el rango y listado mensual por concepto.
- `frontend/src/pages/finanzas/GraficoFinanzas.jsx`: colores por identidad, leyenda para destacar/quitar, puntos llenos/huecos, consulta conjunta por mes y navegación exacta. Ayuda con portal soportado por Recharts 3.10.1, acotada al viewport, desplazable con muchas categorías y cerrable con Escape. El foco propio de cada punto no propaga al foco general del gráfico: se evita que éste reposicione la ayuda entre pointerdown y pointerup y capture el clic.
- `frontend/src/pages/finanzas/ControlesFinanzas.jsx`: reutiliza PanelFlotante con una etiqueta opcional; los filtros y ayudas existentes conservan su presentación.
- `backend/apps/finanzas/test_evolucion.py` y `frontend/e2e/finanzas-ui.spec.js`: regresiones dirigidas y nuevas comprobaciones multiconcepto.
- `docs/funcionalidades/finanzas-costos/README.md`: guía actualizada; la explicación de significado y límites también queda visible desde el (?) de la pantalla.

Validación ejecutada:

1. `docker exec -e DATABASE_URL=sqlite:///:memory: -e DATABASE_SSL=false sistemadesalud-finanzas-demo-backend-1 python manage.py test apps.finanzas.test_evolucion apps.finanzas.test_reportes --noinput`: **17 pruebas OK**, base de prueba aislada. Verifica ajustes exactos y no mezclados entre conceptos, permisos/áreas/sensibilidad, referencia incompleta, estados y auditoría. La cantidad de consultas es igual con uno y dos conceptos; no es una medición de latencia ni carga PostgreSQL.
2. `node node_modules/@playwright/test/cli.js test --config=playwright.finanzas-ui.config.js`: **44 pruebas OK**, 1,3 minutos, Chromium con contratos HTTP simulados. Incluye 24 conceptos seleccionados sin recorte, búsqueda/selección vacía/total, una sola petición al cambiar selección, color estable, referencia única, ayuda desplazable y Escape, rango/ausencias, clic móvil y teclado al concepto exacto, retiro de importes ante 403 y regresiones financieras anteriores. El error de carga dinámica del gráfico se provoca deliberadamente en la prueba de recuperación.
3. Capturas inspeccionadas de escritorio y móvil, incluida la ayuda completa: sin recorte ni scroll horizontal; se compactó la leyenda sin reducir el mínimo de 180 px del gráfico. El caso de viewport conserva ajuste a 1440×900 y 1920×1080. En pantallas bajas o con muchos conceptos puede haber scroll vertical natural.
4. `npm run build`: **OK**, 737 módulos; gráfico 424,83 kB / 122,79 kB gzip. Sin dependencias nuevas. `git -c core.safecrlf=false diff --check`: OK. Frontend 8090 y health 8010 responden HTTP 200.

Skills: brainstorming mantuvo el diseño aprobado y el nuevo valor inicial; interface-design reutilizó tokens y controles hospitalarios; vercel-react-best-practices evitó solicitudes por categoría y estado derivado redundante; systematic-debugging permitió reproducir y corregir el clic interceptado; playwright orientó la comprobación visual usando la suite existente ya autorizada.

No se ejecutaron CI, Firefox/Safari, pruebas de carga ni un flujo autenticado contra los datos de demo. No hubo seeds, migraciones, cambios en datos de demo, reinicios, commit ni push; checkout principal preservado. Riesgos señalados por el usuario —confundir una carga incompleta con ahorro, duplicar importes y abrir/asignar otra área o concepto— cubiertos por señales/listado exacto y las pruebas indicadas; la comprensión y aceptación visual del usuario siguen pendientes. No se propone incorporar ni desplegar este cambio.

## Checkpoint autorizado para continuar en otro chat — 2026-09-14

El usuario solicita guardar todos los cambios acumulados en la rama del PR #40 y retomar en un chat nuevo con un análisis actualizado del módulo, épicas e issues. La prioridad inmediata es preparar la demo del **15/09/2026**, preservando la simplicidad para usuarios hospitalarios y sin confundir el avance de reportes con la finalización de todo el circuito económico.

Los commits agrupan servidor, entorno, interfaz y documentación/pruebas; no reescriben el historial anterior ni constituyen aprobación de merge o despliegue. Al preparar la publicación se retiró una clave de demo fija de la prueba autenticada: ahora requiere `FINANZAS_DEMO_PASSWORD`. Se validó sintaxis con `node --check frontend/e2e/finanzas-feedback.spec.js`, sin iniciar sesión ni modificar usuarios.

El próximo pase debe rehacer el inventario código → pruebas → criterio de aceptación → issue/tarea, con evidencia fresca. La descripción del PR consultada en este checkpoint conserva afirmaciones históricas desactualizadas (por ejemplo reportería fuera del incremento y ausencia de dependencias nuevas); no usarla como estado actual ni actualizar/cerrar issues automáticamente. Revisar #33, #9–#12 y #34–#39, con sus comentarios, checklists y relaciones. Están abiertos en el inventario consultado.

El usuario anunció **nuevo feedback sobre Evolución mensual**, todavía no entregado. No considerar ese gráfico aceptado definitivamente ni adivinar el feedback. Incorporarlo antes de decidir los retoques de demo. La preparación de esta demo no implica implementar apresuradamente cajas, cobros/pagos/reintegros o costos de disponibilidad: contrastar alcance y pedir decisión si hace falta.
