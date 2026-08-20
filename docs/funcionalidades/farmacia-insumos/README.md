# Farmacia e insumos

## Proposito

Gestionar stock sanitario por institucion y deposito, con trazabilidad por lote cuando corresponde. El modulo cubre ingresos, consumos, transferencias, ajustes, bajas, pedidos y alertas de faltantes/vencimientos.

## Actores

- Farmacia central.
- Depositos de area.
- Enfermeria o equipo que consume insumos en un caso.
- Gestion estatal ante alertas, faltantes o retiros de lote.

## Alcance implementado

- Catalogo de insumos por institucion.
- Depositos centrales o de area.
- Lotes con vencimiento.
- Existencias acumuladas por deposito, insumo y lote.
- Movimientos inmutables de stock.
- Pedidos entre depositos.
- Preparacion/picking de pedidos antes del despacho.
- Entrega total o parcial.
- Rechazo de pedidos.
- Alertas de faltantes y proximos vencimientos.
- Trazabilidad de lote hacia pacientes/casos.

## Tipos de movimiento

- Ingreso.
- Consumo.
- Transferencia.
- Ajuste.
- Baja.

## Reglas de negocio

- La existencia es resultado de movimientos; los movimientos son la evidencia.
- El consumo puede imputarse a un caso para trazabilidad clinica y sanitaria.
- Los insumos con lote obligatorio deben operar con lote.
- Un lote vencido o proximo a vencer debe ser visible para resolucion operativa.
- La entrega de pedido puede ser parcial; lo pendiente queda visible.
- Un pedido puede marcarse como `preparado` solo si el deposito destino tiene stock usable para cubrir lo pendiente.
- Preparar no mueve stock ni cierra el pedido; la transferencia auditable ocurre al entregar.
- Los depositos y el insumo deben pertenecer a la misma institucion.

## Pantallas y rutas

- `/farmacia`
- Acciones de consumo desde el detalle de caso cuando aplica.

## Entidades y endpoints

- `insumos`, `depositos`, `lotes`, `stock`, `movimientos-stock`, `pedidos-stock`
- Acciones funcionales: `ingreso`, `consumo`, `transferencia`, `ajuste`, `baja`, `trazar-lote`, `preparar`, `entregar`, `rechazar`, `alertas`.

## Integraciones

- Casos: consumo asociado a paciente.
- Estructura: depositos por area.
- Auditoria sanitaria: retiro de lotes y trazabilidad.

## Puntos a validar

- Integracion con sistemas provinciales/nacionales de compras o farmacia.
- Nomencladores oficiales de medicamentos, insumos criticos y controlados.
