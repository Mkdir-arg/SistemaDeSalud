# Herencia financiera del admin de institución: hasta dónde llega

## Estado

Enmienda a `2026-09-18-finanzas-coberturas-usabilidad-diseno.md`, que sigue
vigente en todo lo demás.

**El fundamento de esta enmienda es una recomendación del agente, tomada por
delegación explícita del responsable del proyecto, no una decisión razonada por
una persona.** Queda escrito así a propósito: si mañana alguien la discute, no
va a encontrar un argumento humano detrás que no existió.

## Contexto

El documento del 18/09 decidió:

> El rol Admin de institución hereda todas las acciones financieras, para todas
> las áreas e información sensible, sin crear concesiones duplicadas.

El problema que resolvía es real: configurar un hospital no debería obligar a
duplicar a mano dieciocho concesiones para quien ya es su administrador.

`c4eefbb` lo implementó ampliando `ACCIONES_ADMIN` de dos acciones de lectura a
las dieciocho, y no tocó ninguna prueba. Dejó 51 en rojo, que se descubrieron
cuatro días después. La reparación de esas pruebas es el PR #53.

Al repararlas apareció algo que la decisión original no contemplaba: entre las
dieciocho estaban `aprobar_costos`, `aprobar_gastos`, `aprobar_dinero` y
`auditar_finanzas`.

## Decisión

Esas cuatro dejan de heredarse. Se conceden de forma explícita, a una persona
distinta, o no se tienen. El resto de la herencia queda como estaba: ver,
registrar, corregir y configurar en toda la institución, incluida la información
sensible.

En el código son `ACCIONES_SIN_HERENCIA`, en `apps/finanzas/permisos.py`.

## Por qué

Aprobar no es una acción más del conjunto. Es el control de cuatro ojos sobre el
dinero: si el mismo rol registra y aprueba, el control no existe. Con la
herencia completa, un admin de institución cargaba un pago y lo dejaba aprobado
en un solo paso, sin que ninguna otra persona interviniera.

Auditar los accesos propios tiene el mismo problema en otra forma: el registro
de accesos está para decir quién miró qué, y quien puede leer y auditar a la vez
se revisa a sí mismo.

Ninguna prueba lo detectó porque casi todas usaban una membresía con rol admin
como portador neutro, no como sujeto. Nadie estaba afirmando nada sobre el admin
real.

## Alternativa descartada

Dejar la herencia completa y confiar en el registro de auditoría como control
compensatorio. Se descarta porque el mismo rol hereda `auditar_finanzas`: el
control compensatorio queda en manos de la persona a controlar.

## Lo que esta enmienda NO resuelve

La herencia se aplica de forma despareja y eso sigue igual. `tiene_concesion_financiera`
consulta el alcance del admin, y por eso hereda dinero, cobros, coberturas y
aceptación; pero `registrar_gasto`, `PuedeConfigurarRepartos` y los tres reportes
(`reportes-finanzas`, `reportes-costos`, `reportes-dinero`) exigen concesión
explícita y no lo consultan.

Se deja como está a propósito: alinear hacia arriba ampliaría permisos sin que
nadie lo haya pedido, y hacerlo hacia abajo desharía lo que el documento del
18/09 sí decidió. Queda afirmado en `test_permisos_contables` para que un cambio
de criterio se decida y no se descubra.

## Cuándo revisarla

- Si aparece un hospital donde el admin es la única persona con acceso al
  módulo financiero: ahí la enmienda bloquea la operación en vez de protegerla,
  y la respuesta correcta es designar un segundo aprobador, no revertirla.
- Si se decide alinear la herencia dispareja en cualquiera de los dos sentidos.

## Verificación

`apps.finanzas.test_aprobaciones_dinero.test_el_admin_de_institucion_tampoco_aprueba_lo_que_registra`
encierra la garantía: un admin registra un movimiento y queda
`pendiente_aprobacion`, y pedirlo aprobado levanta `PermissionDenied`.
