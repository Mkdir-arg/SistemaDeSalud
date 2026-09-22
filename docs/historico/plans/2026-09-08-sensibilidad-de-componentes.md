# Sensibilidad de componentes de costo

## Decisión

La sensibilidad se configura por componente y se congela junto con el
componente esperado de cada hecho de atención. No se recalcula desde el
catálogo vigente al consultar históricos.

Una concesión de lectura sin `permite_sensibles` puede ver un hecho sólo si
ninguno de sus componentes congelados es sensible. No se devuelven subtotales
ni listas parciales: un total parcial podría revelar el importe protegido por
diferencia. Una concesión sensible dentro de la misma institución y área sí
puede ver el hecho completo.

Los valores de componentes sensibles también se filtran de los listados y
altas para quien no tenga la habilitación sensible correspondiente.

## Consecuencias

- La delegación por área sigue disponible para costos no sensibles.
- Un hecho mixto se trata como sensible completo en V1.
- Cambiar después la sensibilidad de un componente no cambia el acceso a
  hechos ya congelados.

## Límites

No se implementan subtotales visibles, gastos, repartos, cargos, cobros ni
obras sociales. Si se necesita exposición parcial en el futuro, requerirá un
contrato propio que evite inferencias por agregados y faltantes.

## Validación

Se prueban hechos no sensibles visibles por área, hechos sensibles ocultos sin
habilitación y visibles con ella, y valores sensibles excluidos del catálogo
para una concesión no sensible.
