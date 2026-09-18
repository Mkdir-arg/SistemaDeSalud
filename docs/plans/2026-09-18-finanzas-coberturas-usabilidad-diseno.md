# Finanzas y coberturas: usabilidad y ámbitos institucionales

## Decisiones aprobadas

- Las reservas se filtran en el servidor por texto, prestación, estado, saldo y antigüedad. Los filtros son combinables; los de texto esperan dos segundos y los selectores se aplican al cambiar.
- Atención permite encontrar un caso por paciente, documento o número. La evaluación muestra primero el estado, los importes y la siguiente acción.
- El estado de actividad para reparto es válido de forma implícita, incluso para períodos históricos. El control técnico de integridad se conserva en cada cálculo. Una excepción versionada puede bloquear o habilitar un área desde un mes.
- Un ámbito sin área es institucional. Un gasto institucional con regla institucional se reparte entre las atenciones elegibles de todas las áreas de la institución, en proporción a su cantidad durante el período.
- Los repartos ya materializados no se reescriben. La regla nueva afecta cálculos posteriores o reintentos.
- El rol Admin de institución hereda todas las acciones financieras, para todas las áreas e información sensible, sin crear concesiones duplicadas.
- Los formularios de Finanzas inician el campo Área como institucional cuando el dominio permite un ámbito sin área.
- El resumen incorpora la card Gastos mensuales pendientes, enlazada al Calendario con el mes, ámbito y estado correspondiente.
- El PDF de Reportes se ofrece en la barra superior sólo dentro de Reportes. Las referencias de casos visibles en Finanzas enlazan al detalle si el permiso clínico lo permite.

## Implementación

Se incorporará soporte de ámbito institucional y de excepción de actividad en el modelo y los servicios de reparto, preservando la versionación. Los filtros de cobertura se validarán en API y se reflejarán en URL; la interfaz aplicará debounce únicamente a texto. La herencia del administrador se resolverá en el verificador común de permisos.

## Validación

Pruebas focalizadas de backend cubrirán permisos de administración, reparto institucional, excepciones e historial, y filtros de reservas. Las pruebas de interfaz cubrirán búsqueda y evaluación de atención, filtros vivos, card de pendientes, PDF, editor de permisos y enlaces de caso. Se ejecutarán los comandos focales que admita el entorno y se informarán los que no puedan correr.
