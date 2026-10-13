# Demo local del padrón lista para probar

Preparada y verificada el 12/10/2026. URL: http://127.0.0.1:8230/financiadores/padron?financiador=1&estado=todos.

Entrar con `admin@padron130.example.test`. La contraseña y las seis cuentas están en el archivo local `C:\Users\Juanito\AppData\Local\Temp\hen-padron130-20261012\accesos.txt`. Es un archivo privado fuera del repositorio. Para comparar permisos, cerrar sesión y usar operador, salud, cobranza, auditor u organización B.

La aplicación queda encendida en el proyecto Docker `salud-padron-130`. Backend: http://127.0.0.1:8130/api/health/. Base PostgreSQL `padron130`, sin puerto expuesto al host. Los únicos servicios iniciados son db, backend y frontend; los puertos de la aplicación están ligados a 127.0.0.1. No se utilizaron otros proyectos ni bases compartidas.

## Qué probar

1. Buscar por DNI, CUIL, apellido o número; abrir «Filtros administrativos» para filtrar por régimen, trámite o fechas.
2. Abrir el titular P130-A-01, editar contacto con motivo, recargar y consultar la historia administrativa.
3. Navegar sus familiares; abrir P130-A-04 para legajo y vencimientos. El legajo registra presentaciones sin archivos adjuntos. Para observar un documento con trámite completo, pasar primero el trámite a «En revisión».
4. Comparar la baja administrativa y derechos actuales en P130-A-09; revisar mora informada en P130-A-06 con la cuenta de cobranza.
5. Usar los perfiles separados: operador no recibe salud/cobranza, auditor consulta sin escribir y B no accede a A.
6. Descargar plantilla v2 o importar `C:\Users\Juanito\AppData\Local\Temp\hen-padron130-20261012\muestra.xlsx`. La muestra tiene dos filas válidas y cuatro rechazadas. Ya se aplicó durante el ensayo: repetir conserva los datos y no agrega duplicados.

Se crearon trece afiliados ficticios iniciales (doce A y uno B), cuatro planes y seis cuentas. El recorrido de importación agregó dos afiliados A: quedan quince en total. Los ensayos de contacto y legajo restauran sus datos de partida y conservan el historial de prueba. El loader no resiembra ni restablece tus futuras ediciones.

## Validación realizada

- Construcción de las imágenes backend y frontend; build Vite pasó.
- Migraciones aplicadas sólo sobre la nueva base `padron130`; `check` y `makemigrations --check --dry-run` pasaron.
- 159 pruebas Django sobre PostgreSQL dedicado `test_salud_financiadores_test`: todas pasan, sin omisiones. El runner destruyó esa base de tests. Incluye carrera entre desactivación/asignación de plan, dos altas exclusivas del mismo documento, revisión concurrente, familia, importaciones, permisos, seed y compatibilidad.
- Siete recorridos Playwright contra el frontend/backend/PostgreSQL reales: todos pasan. Contacto persistente en sesión nueva, conflicto 409, roles/organizaciones, fechas y derechos, búsqueda/filtros, legajo/trámite e importación XLSX con repetición.
- Diez pruebas Node de campos, edición y navegación pasan; `git diff --check` pasa. La portada y ambos health HTTP responden 200 después del último ensayo.
- Los tres fallos iniciales de Playwright se debían a selectores de la prueba y nombre de descarga: se corrigieron abriendo los filtros, usando roles accesibles de desplegables y verificando el nombre real más la cabecera ZIP del XLSX. No se interceptó la API.
- Claude revisó el código y los ajustes finales en dos tareas supervisadas. Los hallazgos P2 quedaron atendidos, sin nuevos P1/P2. Ambos workers se liberaron al terminar. Run `run_5d0066141173`; informes privados sin claves en Temp: `padron130-claude-review-20261012.md` y `padron130-claude-recheck-20261012.md`.

La aceptación del usuario y la obra social está pendiente de su prueba. No se realizó validación integral de los otros módulos. La cobranza es información declarada; no calcula deuda ni ejecuta débitos o cortes. No hay integraciones ARCA/ANSES/bancarias, emisión de credenciales ni adjuntos binarios. En Excel, los valores de parentesco deben seguir las opciones de la plantilla; confirmar vuelve a validar y puede rechazar relaciones familiares que cambiaron desde el preview.

## Arrancar de nuevo conservando tus datos

Desde `C:\Users\Juanito\orca\workspaces\SistemaDeSalud\issue-130-padron-demo`, con Docker Desktop iniciado:

```powershell
$padron130Args = @('compose', '-p', 'salud-padron-130',
    '--env-file', (Join-Path $env:TEMP 'hen-padron130-20261012.env'),
    '-f', 'docker-compose.yml', '-f', 'docker-compose.padron130.yml')
docker @padron130Args up -d db backend frontend
```

Para detener la demo conservando la base, usar `docker @padron130Args stop`. No borrar volúmenes ni ejecutar seeds globales. El env temporal contiene claves exclusivas de este ensayo; conservarlo localmente para reiniciar.

## Cambios de esta continuación

Se aplicó el parche revisado: `services.py`, `padron.py`, `views.py`, `test_padron130.py` y `CrearAfiliadoPadron.jsx`. Alta exclusiva rechaza duplicados sin cambiar la afiliación y conserva el POST incremental legado; el alta básica conserva el motivo. La asignación de plan bloquea/revalida el plan y rechaza afiliaciones finalizadas.

Se añadieron dos pruebas PostgreSQL en `test_concurrencia_padron130.py` y tres regresiones adicionales en `test_padron130.py`. `LegajoPadron.jsx` explica el orden de revisión; `FichaPadronAdministrativa.jsx` deshabilita cambiar el plan finalizado; `FichaAfiliado.jsx` distingue fecha de afiliación e instantánea del plan. Se corrigieron los selectores/descarga en `issue130-padron-real.spec.js`. La guía y los datos documentan el runtime ejecutado.

El checkout es `juanikitro/issue-130-padron-demo`, base `29886cf26e668c67a224a30145260e0fc62ace81`, El PR y su historial Git registran los commits y la incorporación; el ensayo descrito aquí acredita el runtime local. La aceptación de negocio no se infiere de los checks.

## Compatibilidad del despliegue — PR #131

Las columnas nuevas no nulas mantienen defaults en PostgreSQL y en Python. La migración `0012_padron_legacy_db_defaults` actualiza las instalaciones que ya ensayaron 0010/0011, sin editar esas migraciones ni borrar datos. Para una instalación todavía en 0009, Django usa el reemplazo `0010_padron_expansion_compatible`: ejecuta las tres migraciones en una sola transacción. Así las columnas y sus defaults quedan visibles conjuntamente antes de promover el nuevo backend. Conservar todos los archivos originales y el reemplazo; no eliminar migraciones durante este despliegue.

Cinco pruebas usan los modelos históricos anteriores para insertar afiliados, planes, membresías, historial y lotes sobre el esquema nuevo. Verifican compatibilidad de escritores y defaults sin permisos sensibles implícitos. El ensayo PostgreSQL ampliado pasó 165 pruebas, sin omisiones.

La plataforma no administra las designaciones de salud/cobranza, incluso cuando tiene una membresía real. La designación de otro administrador del financiador conserva el acceso explícito; los administradores ordinarios mantienen su operatoria. Las pruebas cubren rechazo de autoconcesión y concesión a otra cuenta sin crear usuarios ni emitir activaciones, ausencia de efectos, revocación y designación independiente.

El esquema OpenAPI usa nombres distintos para los enums de sexo del padrón y del paciente; el enum previo del paciente conserva su nombre. La generación estricta sin avisos pasa. Las pruebas de UI actualizadas verifican la corrección parcial con revisión y la clasificación opcional del plan.
