# Ensayo del padrón ampliado — issue #130

Issue: https://github.com/Mkdir-arg/SistemaDeSalud/issues/130.

Estado al 12/10/2026: demo local iniciada y verificada con PostgreSQL y navegador.
Ver [accesos, recorridos y evidencia actual](guia-demo-padron-local.md).
La aceptación del usuario y la obra social sigue pendiente.

## Entorno exclusivo

Usar el worktree `issue-130-padron-demo`. El overlay `docker-compose.padron130.yml`
se combina únicamente con `docker-compose.yml`. Proyecto `salud-padron-130`, base
`padron130`, PostgreSQL 16 sin puerto al host; aplicación en
`http://127.0.0.1:8230`, API en `http://127.0.0.1:8130/api/`.

Los volúmenes y la red pertenecen al proyecto. No usar los proyectos `salud-demo`
o `salud-vacio`, sus archivos env, ni `seed_entorno_demo`: ese comando vacía la base.
No iniciar servicios de fondo para este ensayo. No usar datos de afiliados reales.

El overlay desactiva cargas automáticas, integraciones, HTTPS/HSTS local y correo
externo. RENAPER es simulado. No se agregan dependencias a las del repositorio.

**Autorizado y ejecutado:** construcción y arranque del proyecto, dependencias
del lockfile y Chromium, migraciones sólo en la base nueva, muestra ficticia,
pruebas focalizadas PostgreSQL, build y siete recorridos reales de navegador.

## Preparación de comandos (PowerShell)

Tras obtener esa autorización, comprobar que los puertos 8230 y 8130 están libres
y que no existe un proyecto previo con ese nombre. Si existe, inspeccionarlo;
no reutilizarlo, detenerlo ni borrar sus volúmenes automáticamente.

Crear claves aleatorias del ensayo en un archivo fuera del repo. No imprimir el
archivo, copiarlo a evidencia, incluirlo en trazas ni compartirlo como adjunto.
Guardar también `DEMO_PASSWORD` en ese archivo para el loader ficticio.

```powershell
$padron130Env = Join-Path $env:TEMP 'hen-padron130.env'
if (Test-Path -LiteralPath $padron130Env) { throw 'El archivo ya existe; revisar antes de continuar.' }
$padron130Keys = 1..3 | ForEach-Object {
    [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
}
@(
    "PADRON130_DB_PASSWORD=$($padron130Keys[0])"
    "PADRON130_DJANGO_SECRET_KEY=$($padron130Keys[1])"
    "DEMO_PASSWORD=$($padron130Keys[2])"
) | Set-Content -LiteralPath $padron130Env -Encoding utf8
$padron130Args = @('compose', '-p', 'salud-padron-130',
    '--env-file', $padron130Env,
    '-f', 'docker-compose.yml', '-f', 'docker-compose.padron130.yml')
docker @padron130Args config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose inválido; no iniciar.' }
docker @padron130Args up --build -d db backend frontend
if ($LASTEXITCODE -ne 0) { throw 'No se inició el entorno; revisar el error.' }
```

El entrypoint del backend aplica las migraciones. No hacerlo sobre otro proyecto
o con un `DATABASE_URL` del host. El loader y el manifiesto de cuentas/escenarios
se describen en [guia-demo-padron-datos.md](guia-demo-padron-datos.md).

## Pruebas del entorno aislado

Dentro de este mismo stack autorizado, Django usa la URL de tests del overlay,
con destino fijo y marcador de proyecto. El runner crea y destruye
`test_salud_financiadores_test`; no usa `padron130` para las pruebas. No usar
`--keepdb`, bases existentes o URLs de otros entornos para sortear las guardas.

```powershell
docker @padron130Args exec -T backend python manage.py check
docker @padron130Args exec -T backend python manage.py makemigrations --check --dry-run
docker @padron130Args exec -T backend python manage.py test apps.financiadores.test_padron130 apps.financiadores.test_concurrencia_padron130 apps.financiadores.test_importaciones.ImportacionesConcurrenciaTests apps.financiadores.tests_seed_padron_demo --settings=config.settings_financiadores_postgres_test --noinput
```

Para el ensayo del navegador, primero generar y copiar el manifiesto y XLSX
siguiendo la guía de datos. Desde `frontend`, con las dependencias del lockfile y
Chromium instalados únicamente después de la autorización:

```powershell
$env:PADRON130_MANIFEST = Join-Path $padron130Artifacts 'manifiesto.json'
$env:PADRON130_XLSX = Join-Path $padron130Artifacts 'muestra.xlsx'
$padron130PasswordLine = Get-Content -LiteralPath $padron130Env |
    Where-Object { $_.StartsWith('DEMO_PASSWORD=') }
if (@($padron130PasswordLine).Count -ne 1) { throw 'Falta una clave de ensayo única.' }
$env:PADRON130_PASSWORD = $padron130PasswordLine.Substring('DEMO_PASSWORD='.Length)
try {
    npx --no-install playwright test --config=playwright.issue130-real.config.js
    if ($LASTEXITCODE -ne 0) { throw 'El recorrido real falló; revisar evidencia.' }
} finally {
    Remove-Item Env:PADRON130_PASSWORD -ErrorAction SilentlyContinue
    $padron130PasswordLine = $null
}
```

La configuración no inicia otro servidor ni intercepta la API. Falta de archivos,
credenciales o health produce fallo, no omisión. Las pruebas operan sobre la
muestra ficticia: conservar evidencia y consultar el estado antes de repetirlas;
el loader no restaura los datos iniciales ni las contraseñas al volver a ejecutarlo.

## Recorrido observable

1. Buscar por documento, CUIL, apellido y número; filtrar por régimen, plan,
   estado administrativo, derecho actual y fechas; volver conservando el listado.
2. Editar domicilio/contacto con motivo; recargar y abrir otra sesión para
   demostrar persistencia. Mostrar autor y cambios en el historial paginado.
3. Navegar titular y familiares. Rechazar cruce de financiador, auto-vínculo,
   ciclos y familiar de otro familiar. La baja del titular no da bajas implícitas.
4. Revisar régimen/empleador/subsidio, legajo y vencimientos. La documentación es
   un registro de presentación **sin archivo adjunto**. La credencial se registra
   como emitida externamente; no se genera una credencial nueva.
5. Registrar baja administrativa o mora informada y comprobar que el derecho
   actual continúa gobernado por la finalización explícita existente.
6. Usar cuentas con salud solamente, cobranza solamente, ambas y ninguna:
   comprobar respuestas HTTP y no sólo controles ocultos. Auditor no escribe;
   financiador B no obtiene datos de A. Estos permisos no amplían historia clínica.
7. Descargar plantilla v2 de este servidor, completar muestra ficticia y ver
   errores de CUIL/familia/identidad antes de confirmar. Confirmar filas válidas,
   repetir sin duplicados y conservar afiliados omitidos. V1 sigue aceptada.
8. Intentar una edición con revisión antigua: esperar conflicto y recargar,
   sin sobrescribir silenciosamente el trabajo de otra persona.

## Límites que deben verse en la demo

La cobranza es información administrativa proporcionada por la obra social,
no una conciliación ni cálculo de deuda. No hay integración ARCA/ANSES/bancaria/
SSSalud, facturación de cuotas, cortes automáticos o cálculo de gracia legal.
CBU/CUIT y condiciones de salud se cargan en recursos protegidos; no entran en
la plantilla general. No presentar este ensayo como reemplazo completo de los
ocho módulos enumerados en los PDF.

## Evidencia y cierre

Registrar SHA/base, fecha real, proyecto, comandos y resultados, pruebas corridas
y pendientes. Separar pruebas con API simulada de pruebas con backend/PostgreSQL
real. Si falta entorno, cuentas, health o datos, el ensayo debe fallar; una omisión
de pruebas no constituye aprobación.

No guardar contraseñas, tokens, trazas de sesión ni datos sensibles en capturas.
Antes de incorporar, revisar el diff, recorrer el escenario y evaluar fallos.
La migración inversa elimina datos nuevos: no usarla para recuperar una base real.
Una vuelta al código anterior requiere plan de conservación de las columnas y
tablas agregadas; no ejecutar rollback destructivo como parte del ensayo.
