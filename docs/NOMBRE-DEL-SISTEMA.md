# Nombre del sistema

El nombre visible del producto se define por variable de entorno. Mientras se
elige la marca definitiva cambia seguido (Cauce → I-Core Salud → HEN → PLEXO), y
cada cambio no debería exigir tocar código.

**Valor por defecto: `PLEXO`** (desde el 13/10/2026).

## Cómo cambiarlo

Con docker compose, una sola variable en el `.env` de la raíz:

```bash
NOMBRE_SISTEMA=OtroNombre
docker compose up -d --build   # --build es obligatorio: el frontend lo incrusta al construirse
```

El compose la reparte a las dos partes:

| Parte | Variable | Cuándo se lee | Dónde se usa |
|---|---|---|---|
| Backend | `NOMBRE_SISTEMA` | Al arrancar | `settings.NOMBRE_SISTEMA`: título y descripción de `/api/docs/`, remitente por defecto de los correos (si `DEFAULT_FROM_EMAIL` no está definido) |
| Frontend | `VITE_NOMBRE_SISTEMA` | **Al construir** (Vite lo incrusta en el bundle) | `src/lib/marca.js`: inicial de la marca cuadrada, título por defecto de la barra superior, textos de la landing, portal del financiador, reporte PDF de finanzas, calendario `.ics` del portal; `vite.config.js`: `<title>` y favicon de `index.html` |

Fuera de compose (Railway, servidor propio) hay que definir las dos: `NOMBRE_SISTEMA`
en el servicio del backend y `VITE_NOMBRE_SISTEMA` como variable de **build** del
frontend (build arg del `frontend/Dockerfile`). Definirla sólo en tiempo de
ejecución del frontend no tiene efecto. En desarrollo local sin Docker van en
`backend/.env` y `frontend/.env`.

El logotipo de Plexo (`frontend/src/assets/marca/`, usado por `LogoFull` en
`frontend/src/components/Logo.jsx`) es **fijo y no sigue a la variable**: cambiar
`NOMBRE_SISTEMA` cambia títulos y textos, pero el logotipo sigue diciendo «plexo»
hasta que se reemplacen esos archivos. Se usa la versión color en tema claro y la
blanca en tema oscuro; el paquete original (blanco, negro, verdes, PNG) quedó fuera
del repositorio. El paquete no trae isotipo: la marca cuadrada (menú colapsado) y el
favicon muestran la inicial del nombre sobre el verde de la marca (`#079B9D`).

## Identificadores internos

El 13/10/2026 los identificadores técnicos que llevaban «HEN» se renombraron a
PLEXO. Están **escritos a mano, no salen de la variable**: son contratos entre
partes o claves de datos guardados, y que cambien con cada ajuste de marca
rompería sesiones, integraciones y cuentas. Un próximo cambio de nombre **no**
tiene que tocarlos; si se decide hacerlo, es un cambio aparte con los mismos
cuidados que este.

| Identificador | Antes | Ahora | Efecto del cambio al desplegar |
|---|---|---|---|
| Encabezado HTTP de la simulación | `X-HEN-Simulacion` | `X-PLEXO-Simulacion` (y `x-plexo-simulacion` en CORS) | Frontend y backend tienen que desplegarse juntos: con versiones cruzadas la simulación de perfiles responde 403 o ignora el encabezado |
| Sesión del portal del paciente | `hen.portal.access` / `hen.portal.refresh` (sessionStorage) | `plexo.portal.*` | Quien tenga el portal abierto tiene que volver a ingresar, una sola vez |
| Evento del portal | `hen:portal-vencido` | `plexo:portal-vencido` | Ninguno (interno de la pestaña) |
| Preferencia de tema | `salud.tema` (localStorage) | `plexo.tema` | Cada persona vuelve al tema del sistema operativo una vez |
| Clase CSS del botón de marca | `hen-cta` | `plexo-cta` | Ninguno |
| `UID` de los turnos en el `.ics` del portal | `turno-N@hen` | `turno-N@plexo` | Un turno ya importado a un calendario y vuelto a descargar aparece duplicado |
| Dominio de las cuentas de referencia | `referencia.hen.invalid` | `referencia.plexo.invalid` | La migración `simulacion.0003` reescribe los correos existentes (reversible) |
| Variables de las e2e del #111 | `HEN_111_REAL_*` | `PLEXO_111_REAL_*` | Ninguno |

Quedan con prefijo `salud.` las demás claves del navegador (`salud.access`,
`salud.institucion`, `salud.menu`): no llevaban el nombre del producto y
renombrarlas cerraría la sesión de todo el personal.

### URN de FHIR: estable a propósito

Los identificadores propios en FHIR usan **`urn:icore:id`** (antes
`urn:icore-salud:id`, y antes `urn:cauce:id`). Es el nombre de la institución que
corre el sistema, no del producto, y **no tiene que cambiar con la marca**: lo
guardan integradores externos, y la fachada responde a un namespace retirado con
un Bundle vacío (y un aviso en el log), no con la persona. Los anteriores están en
`SISTEMAS_RETIRADOS` (`backend/apps/fhir/views.py`). Antes de desplegar este cambio
hay que avisar a cualquier integrador que use `urn:icore-salud:id`.

El archivo de Figma «HEN» y su URL tampoco cambian: es el nombre del archivo de
diseño, no del producto.

`docs/historico/` y los planes ya cerrados conservan el nombre de su época.

## Documentación

Los documentos vigentes (`README.md`, `docs/*.md`, `docs/comercial`, `docs/entornos`,
`docs/funcionalidades`) nombran al producto con el valor actual, **PLEXO**, escrito
a mano: la documentación no lee variables. En el próximo cambio de nombre hay que
reemplazarlo ahí también:

```bash
git grep -nw PLEXO -- . ':!docs/historico'
```

En el código, en cambio, no debería aparecer el nombre literal salvo en los tres
valores por defecto: `backend/config/settings.py`, `frontend/src/lib/marca.js` y
`frontend/vite.config.js` (más los `.env.example`, el `frontend/Dockerfile`, el
`docker-compose*.yml` y `frontend/e2e/landing-ui.spec.js`). Los comentarios dicen
«el sistema» en lugar del nombre.
