# Operación técnica del escenario OSTEL

## Estado

Preparación local validada en PostgreSQL 16 aislado. No implica que este código
esté desplegado ni que las cuentas estén disponibles en Railway. El PDF está
dirigido a OSTEL; el estado técnico se conserva únicamente en este documento.

## Carga

Comando nuevo: `python manage.py seed_ostel_demo`.

Requiere `ENTORNO=demo` y PostgreSQL migrado. Las cuentas usan la misma clave que
el resto de la demo: `DEMO_PASSWORD`, o `demo1234` si no está definida. La primera
carga agrega datos; una repetición devuelve el inventario actual y no cambia
contraseñas ni repara lo operado. No tiene opción de borrado.

Una transacción PostgreSQL y un advisory lock propio serializan dos cargas de
este escenario. El grupo `ostel-demo-v1` se crea únicamente al finalizar.
Antes de comenzar se rechazan colisiones de organizaciones, usuarios,
documentos, catálogo, red y cuenta de paciente reservados. No ejecutar a la
vez una reconstrucción general del entorno: usa otro bloqueo y borra la base.

No se alteran organizaciones anteriores, no se reutilizan usuarios ajenos y
no se ejecutan `seed_guardia`, `seed_financiadores` ni `seed_entorno_demo`.
El evaluador tiene roles sólo sobre las tres instituciones ficticias y OSTEL;
no es superusuario ni recibe membresías globales de plataforma.

## Railway: ejecutar sólo después de revisar y autorizar la publicación

Destino indicado por el usuario: https://cauce-web-production.up.railway.app/.
La CLI autenticada lista el proyecto `faithful-commitment`, con servicios
`cauce-web`, `cauce-api`, `cauce-reloj`, `cauce-respaldos` y `Postgres`.
El nombre del entorno de Railway es `production`; eso no demuestra el valor de
`ENTORNO` de Django. No cambiarlo para evitar una guarda de carga sin confirmar
previamente que el servicio es exclusivamente la demo indicada.

1. Confirmar proyecto, entorno, servicio backend y dominio publicado. Comparar
   la revisión desplegada con la revisión que contiene el comando y sus pruebas.
2. Confirmar base de demostración y que no corre una carga general. Revisar el
   mecanismo de respaldo existente y el impacto operativo del despliegue.
3. Publicar el código por el mecanismo acordado; no asumir que Railway recibe
   los archivos locales por ejecutar comandos dentro del contenedor.
4. En la consola del backend, ejecutar `python manage.py seed_ostel_demo`.
   No usar `railway run` contra una base remota: ejecuta código local con
   variables del servicio. No listar variables ni capturar claves en los logs.
5. Guardar el inventario sin secretos: IDs de OSTEL, instituciones y usuarios.
6. Verificar por navegación los tres convenios y el afiliado compartido, el
   saldo de cupo, los perfiles acotados, la cama ocupada y el turno del portal.
7. Comprobar que la demo anterior sigue existiendo. Actualizar el estado y fecha
   de la guía, y entregar la contraseña por un canal separado.

Si una carga falla antes del commit, se revierte su transacción. Si terminó
pero se perdió la salida, repetir no duplica datos. No borrar ni reconstruir la
base para corregir un conflicto o un marcador incompleto: investigar primero.

## Validación aislada

Con PostgreSQL exclusivo para esta tarea y sin conexiones productivas:

```text
python manage.py test apps.demo.test_ostel --noinput -v 2
```

La base de pruebas debe tener un nombre exclusivo. No apuntar las pruebas a la
base de Railway ni compartir `test_salud` con otros procesos.

Las pruebas cubren guardas, convivencia, roles acotados, tres convenios,
familias, cupo compartido, separación de fichas, repetición sin restablecimiento,
camas/estadía, colisión, rollback, clave compartida de la demo, ingreso real por
API, permisos protegidos, portal del paciente y dos cargas concurrentes con
conexiones PostgreSQL independientes. Su resultado
no sustituye la verificación del frontend y del despliegue publicado.

### Resultado local del 19/10/2026

Pasaron **15 pruebas**: las 14 de `apps.demo.test_ostel` y la regresión existente
`apps.demo.tests.EntornoTests.test_en_produccion_ningun_seed_escribe`.
Duración de la corrida final: 18,960 segundos, después de migrar la base aislada.
Comando ejecutado:

```text
python manage.py test apps.demo.test_ostel apps.demo.tests.EntornoTests.test_en_produccion_ningun_seed_escribe --noinput --keepdb -v 1
```

Se usó exclusivamente el contenedor temporal `salud-ostel-validation-20261019`,
PostgreSQL 16 con almacenamiento temporal, puerto aleatorio ligado a loopback y
base `test_ostel_validation`. No se consultó ni modificó una base de Railway.
Al finalizar se detuvo y eliminó el contenedor con su almacenamiento temporal.
Las respuestas 401, 403 y 404 de la salida corresponden a pruebas negativas.
El aviso de `staticfiles` corresponde al checkout local sin estáticos recolectados;
no se ejecutó `collectstatic`, un build ni una prueba de navegador. El checkout
no tiene `frontend/node_modules`.

La revisión corrigió tres problemas de la preparación: llamado desde un box
concreto, un único flujo receptor por área y eliminación del rol estatal
`auditor` del evaluador. La auditoría queda habilitada mediante administración
de las tres instituciones propias. No fue necesario cambiar permisos del sistema.

El PDF se regeneró con contenido dirigido al equipo de OSTEL y se verificó
visualmente después del cambio. No contiene estado de despliegue ni instrucciones
de carga, acceso al servidor o base de datos.

## Alcance y límites de los ejemplos

La carga simula el presente, no doce meses de evolución. No procesa la cola
global de repartos ni genera adjuntos en almacenamiento, que no se revierten
con una transacción de base de datos. Los estudios del portal tienen registro,
sin archivo descargable. No emite correos ni consulta RENAPER, ARCA, ANSES,
SSSalud o servicios bancarios.

Las solicitudes vencen a las 48/72 horas. La repetición no renueva fechas ni
repone stock. No se promete un reinicio automático del escenario. Los precios,
planes, prestadores y documentos son ilustrativos y no atribuibles a OSTEL real.
