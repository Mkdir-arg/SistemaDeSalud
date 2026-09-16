# Ensayo integral del piloto

## Alcance

Continuación del recorrido aprobado en el [plan](README.md): verificar contratos
existentes con datos ficticios, sin agregar funcionalidades ni modificar la demo.

1. Dos financiadores usan plantillas personalizadas del catálogo común; la carga
   de padrón conserva a los omitidos y la de consumos aplica válidas tras confirmar,
   entrega rechazos y admite reintentos sin duplicar usos.
2. Dos hospitales comparten el cupo de una misma persona dentro del financiador.
   El arancel general y la aceptación expresa del copago preceden a la realización.
3. La finalización clínica crea los cargos correspondientes una sola vez; Finanzas
   registra un cobro parcial y los reportes distinguen importe asignado de saldo.
4. Usuarios hospitalarios y de financiadores no acceden a organizaciones ajenas.
5. Las exportaciones entregan 5.000 filas completas y rechazan 5.001, con auditoría
   y sumas exactas. Medir tiempo, consultas y tamaño en PostgreSQL local; las cifras
   son una referencia de laboratorio, no una garantía de rendimiento en producción.

## Aislamiento y validación

- Prueba de integración HTTP en la base efímera del runner de Django; autenticación
  de usuarios reales del fixture, sin sustituir servicios de negocio por mocks.
- Ensayo de volumen optativo, fuera del descubrimiento normal `test*.py`. Las filas
  sintéticas preparan el volumen; la integración anterior valida cómo se originan.
- PostgreSQL 16 desechable, base `cauce_financiadores_test`, puerto local 55438.
  Conservar localhost:5188/8766 y cualquier otro entorno existente.
- Ejecutar las regresiones pertinentes si el ensayo descubre cambios necesarios.
  No incorporar dependencias, migraciones ni nuevas tablas para estas verificaciones.

## Evidencia

Pendiente de ejecutar. Registrar aquí comandos, resultados y límites observados.
