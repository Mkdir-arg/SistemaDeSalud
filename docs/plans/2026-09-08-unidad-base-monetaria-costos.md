# Unidad, base y moneda del costo directo

## Decisión aprobada

El único componente integrado en este incremento representa un importe en
pesos argentinos por una atención completada. Su unidad es `atencion` y su
base de cálculo es `por_atencion`.

La moneda de V1 es exclusivamente `ARS`. No se incorpora conversión,
cotización ni multimoneda. Cada valor conserva `ARS` y la imputación congela
esa moneda junto con el valor aplicado.

## Alternativas descartadas

- Dejar unidad, base y moneda implícitas: hace que un importe histórico no
  tenga significado suficiente fuera del código actual.
- Admitir unidades, bases o monedas libres desde ahora: adelanta contratos de
  farmacia, internación y conversión que todavía no tienen una fuente ni una
  regla aprobada.

## Contrato mínimo

- `DefinicionComponente` declara unidad y base. Sólo se acepta la pareja
  `atencion` / `por_atencion` mientras la fuente sea atención directa.
- `ComponenteEsperadoHecho` congela unidad y base junto con la sensibilidad.
- `ValorComponente` declara la moneda ARS del importe vigente.
- `ImputacionCosto` congela la moneda del valor utilizado. Los ajustes se
  expresan en la moneda de su imputación y no pueden mezclar monedas.
- El detalle y el total exponen explícitamente `moneda: ARS`; `null` sigue
  significando desconocido, nunca cero.

## Límites

No cambia la atención clínica, no crea cargos ni responsables de pago, y no
resuelve consumos, personal, gastos compartidos, repartos o multimoneda.

## Validación prevista

- El catálogo acepta la única unidad/base habilitada y rechaza otra.
- Un hecho conserva unidad/base aunque luego cambie el catálogo.
- Una imputación y su total se identifican explícitamente como ARS.
- Los valores históricos siguen sin edición y las reglas de vigencia actuales
  permanecen vigentes.
