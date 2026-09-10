# Completitud de costos directos

## Contexto

El primer incremento calcula sólo componentes directos configurados al completar
una atención. Gastos compartidos y otras fuentes siguen fuera de esta etapa.
Mostrar ese importe como costo total completo contradice el acuerdo de mantener
visibles los faltantes y el alcance conocido.

## Decisión

El detalle de un hecho de atención distingue tres conceptos:

1. `total_conocido`: suma disponible de los componentes directos calculados.
2. `total_directo_es_completo`: no faltan valores ni componentes dentro del
   snapshot directo congelado.
3. `total_es_completo`: `false` hasta que el módulo integre las demás fuentes
   necesarias para expresar el costo total del paciente.

También expone `alcance` y un faltante de alcance para declarar las fuentes no
integradas. Este faltante no es un error reintentable ni una fila financiera:
explica el límite de la versión actual.

## Alternativas descartadas

- Conservar `total_es_completo=true` con una aclaración textual: permite que
  clientes e informes interpreten un parcial como total.
- Ocultar `total_conocido` hasta tener todas las fuentes: pierde el costo
  directo útil que ya está disponible.

## Límites

No se agregan gastos, repartos, aranceles, cargos, cobros, obras sociales ni
pasos clínicos. La decisión se revisará cuando se integre una fuente adicional
que permita definir una completitud total verificable.

## Validación

Una atención con todos sus componentes directos valorizados debe devolver el
importe conocido y `total_directo_es_completo=true`, pero
`total_es_completo=false`, estado parcial y el alcance pendiente visible.
