# Catálogo geográfico: tarea programada en Railway

## Decisión y alcance

El 27/10/2026 el usuario eligió una tarea programada para #136, en lugar de un
worker permanente. `cauce-geografia` usa el mismo código y Dockerfile del backend
de `main`, pero arranca, comprueba si corresponde actualizar y **termina**. No
comparte el bucle clínico de `cauce-reloj` ni ejecuta `--periodico`.

Entorno: proyecto `faithful-commitment`, ID
`5c9e06ca-364f-423f-9ef1-cd41c815b35b`, entorno Railway `production`
(`c0acf9b3-a608-441c-876c-cbcd5fed4860`). Es la demo compartida;
el nombre del entorno Railway no cambia `ENTORNO=demo` de Django.

La tarea sólo descarga el catálogo territorial público de Georef. No envía
domicilios, personas, instituciones, financiadores ni lugares manuales. Las
búsquedas de la UI siguen consultando el catálogo propio persistido en PostgreSQL.
No homologa datos antiguos ni altera coordenadas institucionales.

## Configuración efectiva

| Campo | Valor |
|---|---|
| Servicio | `cauce-geografia` |
| ID | `f14c805f-ba47-441c-ae3f-4880bb16692f` |
| Repositorio / rama | `Mkdir-arg/SistemaDeSalud` / `main` |
| Root directory | `/backend` |
| Dockerfile | `/backend/Dockerfile` |
| Cron | `0 6 * * *`, UTC: diariamente a las **03:00 Argentina** |
| Réplicas | 1 |
| Restart policy | `NEVER` |
| Healthcheck / pre-deploy command | Ninguno |
| Dominio público / volumen propio | Ninguno |

Start command exacto (una sola línea):

```text
/entrypoint.sh python manage.py shell -c "from django.core.management import call_command; from apps.geografia.models import Catalogo; from apps.geografia.sincronizacion import corresponde; pendiente=corresponde(Catalogo.objects.filter(pk=1).first()); print('Geografia cron: actualizar' if pendiente else 'Geografia cron: catalogo vigente o reintento pendiente'); call_command('sincronizar_geografia') if pendiente else None"
```

Se reutilizan `corresponde()` y el comando `sincronizar_geografia` existentes.
El pequeño envoltorio operativo sólo decide si invocarlo; no implementa otra
descarga/publicación ni requiere cambios de modelos, migraciones o dependencias.
Al cambiar el nombre o contrato de esas funciones, revisar también este comando
en Railway. No copiar el comando del servidor web: iniciaría Gunicorn sin salir.

Variables del servicio, sin valores secretos en el repositorio:

| Variable | Valor o referencia Railway |
|---|---|
| `DATABASE_URL` | `${{cauce-api.DATABASE_URL}}` |
| `DATABASE_SSL` | `${{cauce-api.DATABASE_SSL}}` |
| `DJANGO_SECRET_KEY` | `${{cauce-api.DJANGO_SECRET_KEY}}` |
| `ENTORNO` | `${{cauce-api.ENTORNO}}` |
| `DJANGO_DEBUG` | `0` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` |
| `EJECUTAR_MIGRACIONES` | `0` |
| `SEED_DEMO` | `0` |
| `SEED_GUARDIA` | `0` |
| `PYTHONUNBUFFERED` | `1` |

Las variables y el comando se configuraron **antes** de conectar el repositorio,
para impedir migraciones, seeds o un servidor web accidental en el primer arranque.
La API sigue siendo responsable de aplicar migraciones. La tarea requiere que
el esquema de #136 ya esté aplicado. No necesita credenciales de correo, RENAPER,
OSTEL ni almacenamiento de archivos. Las referencias siguen la configuración de
la API sin copiar sus secretos al disco.

## Frecuencia, errores y costo

- Sin catálogo: intenta la carga inicial en la primera ejecución.
- Con catálogo actualizado hace menos de 7 × 24 horas: termina sin llamar a Georef.
- Con catálogo vencido: actualiza si pasaron al menos 24 horas desde el último intento.
- Si la descarga falla: el comando sale con error, registra el fallo y conserva
  el último catálogo válido. No se publica una descarga parcial. No hay un bucle
  de reinicios; el próximo turno vuelve a evaluar la condición.
- Los intervalos son duraciones exactas, no fechas de calendario. Por la hora de
  la primera carga y las variaciones de arranque de Railway, una actualización
  puede ocurrir entre 7 y aproximadamente 8 días después de la anterior; un
  reintento fallido puede esperar hasta aproximadamente 48 horas. Una caída de
  plataforma puede alargar esos plazos. No se promete puntualidad al minuto.
- Railway omite un turno si el anterior sigue activo. El código limita tamaño,
  paginación y tiempos de descarga; no equivale a un límite total de ejecución
  de PostgreSQL. Si una ejecución queda activa, investigar antes de forzar otra.
- Publicación transaccional: conserva referencias históricas y lugares retirados;
  dos publicaciones concurrentes no deben reemplazarse con una versión vieja.

No queda un contenedor en espera entre ejecuciones. Esto reduce consumo frente
al worker 24/7, pero **no garantiza factura sin aumento**: arranques, CPU/RAM,
builds, transferencia y almacenamiento pueden consumir créditos o generar cargos.
Verificar consumo real en Railway; no se estableció aquí un presupuesto monetario.
La comprobación diaria tiene un pequeño costo aunque no descargue.

## Comprobar operación

Con Railway CLI autenticada, sin volcar variables ni credenciales:

```powershell
railway deployment list -p 5c9e06ca-364f-423f-9ef1-cd41c815b35b -e production -s cauce-geografia --limit 3 --json
railway logs -p 5c9e06ca-364f-423f-9ef1-cd41c815b35b -e production -s cauce-geografia --lines 30
```

En logs debe aparecer `EJECUTAR_MIGRACIONES=0`, nunca migraciones ni seeds.
Una carga muestra `Geografia cron: actualizar` y `Geografía: N entidades;
publicado=True.`. Un turno sin descarga muestra `catalogo vigente o reintento
pendiente` y termina normalmente. Revisar que el contenedor salga con código 0;
un cron terminado no debe interpretarse como un servidor caído. `SUCCESS` de un
build, por sí solo, no acredita publicación del catálogo ni salida del proceso.

Desde una sesión autorizada de la aplicación, comprobar
`GET /api/geografia/estado/`: versión positiva, `actualizado` reciente y `error`
vacío. `GET /api/estado/` incorpora la antigüedad/error del catálogo; requiere
autenticación y puede degradarse también por otros componentes.
`/api/health/` no comprueba la carga de Georef. Un 401 anónimo en los endpoints
de estado es esperado y no prueba que el catálogo esté cargado.

Para diagnóstico de DB, usar una consulta de **sólo lectura** dentro de `cauce-api`
con `railway ssh`, limitada a versión/fechas/error y conteos de lugares por tipo
y origen. No listar domicilios ni lugares manuales. No usar `railway run`, que
ejecuta código local con acceso a la base remota. Revisar el tablero de cron y
el catálogo después de cada actualización semanal; no se configuró alerta externa.

## Reejecución, suspensión y reversión

En el servicio `cauce-geografia` de Railway, usar **Run now** para una ejecución
manual. Un deploy/redeploy puede sólo construir la imagen de un cron
(`buildOnly`), sin ejecutar la tarea: no usarlo como prueba de carga inicial.
La ejecución manual usa la misma condición: si el catálogo está vigente termina
sin descargar. Con la CLI actual, el equivalente a Run now es:

```powershell
railway api 'mutation { deploymentInstanceExecutionCreate(input:{serviceInstanceId:"ac08a0d8-7dc0-4589-b3b7-9dc51f93f53e"}) }' --compact
```

Ese ID identifica la instancia de este servicio en este entorno; si se recrea,
obtener el nuevo ID con `railway status -p 5c9e06ca-364f-423f-9ef1-cd41c815b35b
-e production --json`, sin consultar variables. Verificar que corresponda a
`cauce-geografia` antes de ejecutar. Evitar
forzar `sincronizar_geografia` sin esa condición salvo intervención deliberada.
Nunca activar `--periodico` para un cron ni esconder errores con `|| true`.

Para suspender de forma reversible, **desconectar la fuente y retirar el cron
del servicio**, deteniendo además cualquier ejecución activa; comprobar que no
queden despliegues pendientes. No dejar un servicio sin cron conectado a `main`,
porque otro despliegue podría ejecutarlo. No modificar `cauce-api`, `cauce-reloj`
ni `cauce-respaldos`. Para reactivar, restaurar cron/configuración segura antes
de reconectar la fuente. La suspensión no borra el catálogo: UI y carga manual
siguen disponibles, aunque el catálogo envejece y el estado lo advierte.

Si una actualización da un resultado inesperado, suspender próximas ejecuciones
y revisar evidencia antes de intervenir datos. Detener/revertir código no deshace
una publicación ya confirmada. No borrar tablas, resetear versiones ni restaurar
la base completa para revertir únicamente este servicio.

## Evidencia y límites

La evidencia fechada de activación y primera carga está en el
[informe de #136](../plans/2026-10-22-issue136-avance.md). Una ejecución inicial
correcta no acredita por adelantado el próximo disparo automático ni estabilidad
de Georef; comprobar el turno siguiente y el consumo en Railway.

Referencias oficiales: [Cron jobs](https://docs.railway.com/cron-jobs) y
[planes y consumo](https://docs.railway.com/pricing/plans).
