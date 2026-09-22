# Prompt — `main` en rojo: 53 tests fallando

Copiá todo lo que sigue como prompt.

---

## Tarea

La suite de backend en `main` está en rojo: **50 fallas y 3 errores** sobre 1030
tests. Averiguá por qué, decidí qué hacer con cada grupo y dejá la suite verde —
o, si algún test está mal escrito, arreglá el test y dejalo escrito por qué.

**Primero el diagnóstico. No arregles nada hasta haber agrupado las fallas por
causa raíz y habérmelas mostrado.**

## Está confirmado que es de `main`, no de tu rama

Lo verifiqué comparando dos corridas: el árbol de trabajo de ese momento y
`origin/main` limpio en un worktree aparte. Las dos dieron **exactamente las
mismas 53 fallas, con la misma lista de tests**. No las introdujo un cambio
reciente sin mergear.

El commit de referencia es `ccec515` (merge del PR #50).

## Cómo reproducirlo — leé esto antes de correr nada

```bash
DEMO="docker compose -p salud-demo --env-file .env.demo -f docker-compose.yml -f docker-compose.demo.yml"

# Los servicios de fondo compiten por Postgres y tumban la corrida.
$DEMO stop tiempos costos repartos respaldos frontend

$DEMO exec -T backend python manage.py test apps.finanzas apps.financiadores apps.casos --noinput
```

**Dos trampas que ya me costaron dos corridas inútiles:**

1. **El override `docker-compose.demo.yml` es obligatorio.** Sin él, `DEBUG=false`
   activa el redirect a HTTPS y **todos** los tests de API reciben 301. Da 419
   fallas y 358 errores, y ninguna es real. El síntoma es
   `AttributeError: 'HttpResponsePermanentRedirect' object has no attribute 'data'`.
2. **Dejá los servicios de fondo parados.** Con ellos corriendo, Postgres se queda
   sin conexiones a mitad de la suite: aparecen ~95 `ERROR: setUpClass` con
   tracebacks que terminan en `get_new_connection`. Son infraestructura, no código.

Si ves cualquiera de esas dos firmas, la corrida no sirve: arreglá el entorno y
repetila antes de sacar conclusiones.

## Dónde están las fallas

| Archivo | Fallas |
|---|---|
| `apps.finanzas.test_aprobaciones_dinero` | 10 |
| `apps.financiadores.test_seguimiento` | 7 |
| `apps.finanzas.test_cobros` | 6 |
| `apps.finanzas.tests` | 5 |
| `apps.finanzas.test_revision_circuito` | 3 |
| `apps.finanzas.test_dinero` | 3 |
| `apps.finanzas.test_aprobaciones_gastos` | 3 |
| `apps.financiadores.test_exportacion_seguimiento` | 3 |
| `apps.finanzas.test_reparto_api` · `test_editor_permisos` · `apps.financiadores.test_cobertura` | 2 c/u |
| `test_permisos_contables` · `test_calendario` · `test_auditoria` · `test_legado` · `test_api` · `apps.casos.test_permisos_barrida` | 1 c/u |

## Firmas de error, por frecuencia

| Veces | Mensaje |
|---|---|
| 22 | `AssertionError: N != N` (conteos o importes que no dan) |
| 5 | `AssertionError: PermissionDenied not raised` |
| 4 | `AssertionError: True is not false` |
| 4 | `AssertionError: Items in the first set but not the second` |
| 3 | `AssertionError: ValidationError not raised` |
| 3 | `AssertionError: N is not None` |
| 2 | `Tuples differ` en estados/motivos de `RepartoGasto` |

## Dos que ya identifiqué, empezá por acá

**1. `reportes-costos` queda abierto a cualquier miembro.** Es lo más urgente y es
un agujero de permisos, no un test caprichoso:

```
FAIL: apps.casos.test_permisos_barrida.BarridaDePermisosTests
      .test_no_hay_viewsets_sin_capacidad_declarada_sin_querer

'reportes-costos' : estos recursos no declaran `capacidad_requerida` y quedan
abiertos a cualquier miembro: declarala, o agregalos a SIN_CAPACIDAD_A_PROPOSITO
con el motivo escrito
```

Ese archivo de test existe exactamente para atrapar esto, y lo atrapó. El viewset
está en `backend/apps/finanzas/api_reportes_costos.py`, entró con el PR #48 y
verifica permisos por dentro, pero no declara la capacidad que la barrida exige.
Decidí cuál de las dos salidas corresponde y dejá escrito el motivo.

**2. `diagnosticar_coberturas_legacy` falla sólo dentro de Docker.** No es un bug
del producto:

```
CommandError: Elegí una ruta privada fuera del repositorio para el reporte.
```

El comando calcula `REPOSITORIO = Path(__file__).resolve().parents[5]`. En el
contenedor el código vive en `/app/apps/...`, un nivel más arriba que en el repo
(`repo/backend/apps/...`), así que `parents[5]` da `/` y **toda** ruta queda
"dentro del repositorio". En una checkout del host el test pasa. Hay que decidir
si se arregla el cálculo, si el test declara su dependencia del layout, o si se
documenta que esa suite no corre en contenedor.

## Ruido que NO es falla

`django.db.utils.DatabaseError: Lote interrumpido` aparece 12 veces en el log,
pero sale de `apps/financiadores/test_actividad.py:411`, en una función llamada
`fallar`: es **inyección de fallo deliberada** y esos tests pasan. No lo persigas.

## Lo que quiero de vuelta

**Paso 1 — Diagnóstico.** Agrupá las 53 por **causa raíz**, no por archivo. Para
cada grupo: qué cambió que las rompió (buscá el commit con `git log -S` o
`git bisect` si hace falta), y si lo que está mal es el código o el test.

Me interesa especialmente separar tres categorías, porque cada una se trata
distinto:

- **El código tiene un bug** → arreglar el código.
- **El comportamiento cambió a propósito y el test quedó viejo** → actualizar el
  test, y que el mensaje del commit diga qué decisión de producto lo justificó.
- **El test depende del entorno** → arreglar la dependencia, no el producto.

Las 5 de `PermissionDenied not raised` y las 3 de `ValidationError not raised`
miralas primero: un test de permisos que dejó de fallar cuando debía fallar
significa que **algo que antes se rechazaba ahora se acepta**. Si alguna resulta
ser un permiso realmente abierto, decímelo antes de seguir con el resto.

**Paso 2 — Plan.** Qué arreglás, en qué orden y por qué. Si algo merece quedar
rojo y documentado en vez de arreglarse ahora, proponelo con su razón.

**Paso 3 — Ejecución**, después de que apruebe. Un commit por causa raíz, no uno
gigante. Cada mensaje explica el porqué, no el qué.

## Cómo se valida

- La suite completa de las tres apps, con el entorno bien armado, en verde o con
  las excepciones que hayamos acordado explícitamente.
- Corré también `apps.flujos` si tocás validaciones de nodos.
- No declares verde nada que no hayas corrido. Si una falla no se pudo reproducir,
  decilo en vez de darla por arreglada.

## Lo que NO quiero

- Borrar o saltear tests (`skip`, `expectedFailure`) para poner la suite en verde.
  Si un test tiene que dejar de correr, quiero la razón escrita y tu recomendación
  antes de hacerlo.
- Aflojar una aserción de permisos para que pase. Ahí el test casi siempre tiene
  razón y el código no.
- Refactors de paso. Arreglá lo que rompe y nada más.
- Tocar migraciones para acomodar un test.
