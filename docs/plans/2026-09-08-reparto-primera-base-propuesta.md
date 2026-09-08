# Primer reparto por actividad: condiciones aprobadas

Referencia: #37; módulo central #33, contratos #10/#12 y fuentes #36.
El responsable aprobó el 2026-09-08 las tres condiciones propuestas a continuación.
La fundamentación y las alternativas conservadas son recomendaciones del agente;
no se atribuye al responsable una explicación retrospectiva de esas alternativas.
La aprobación permite avanzar al diseño técnico concreto, no autoriza un esquema
todavía no presentado ni migraciones o infraestructura nuevas.

## Evidencia y límite actual

- `HechoAtencionCosteable` conserva atención completada, fecha, institución,
  paciente y área de origen. `registrar_atencion_completada` deduplica por el
  evento; firma y valorización no son condiciones para contar la actividad.
- `Gasto` conserva importe y período; sólo una fuente aprobada puede participar.
  `AjusteGasto` conserva correcciones aditivas. No existen todavía repartos.
- No hay una declaración durable de cobertura completa de la fuente de actividad
  por institución/período. Que una consulta devuelva cero hechos no prueba cero
  actividad real, especialmente para fechas anteriores al inicio del módulo.
- El filtro de lectura del usuario no puede definir el denominador económico:
  personas con permisos distintos deben consultar el mismo reparto, no calcular
  resultados distintos por ver menos filas.

## Tres condiciones aprobadas para continuar

### 1. Primera regla y fuente elegible

Recomiendo empezar sólo con gastos aprobados de un área y una regla mensual
explícita por cantidad de atenciones completadas en esa misma área e institución.
Se habilita por concepto, con vigencia. No se activa por tener un gasto ni se
aplica a todos los conceptos. Sin regla: pendiente de reparto, nunca costo cero.

Alternativas: empezar por gastos institucionales sobre todas las áreas, o
incorporar varias bases (ocupación, consumos, tiempos de referencia) juntas.
Cubren más fuentes, pero aumentan el riesgo de atribución incorrecta y exigen
contratos todavía no aprobados. Los gastos institucionales sin área y otras
bases quedarían visibles como pendientes en este primer corte, no redistribuidos
artificialmente. No confundir esta limitación del corte con excluirlos de V1.

### 2. Cuándo se puede afirmar que la actividad está completa

Recomiendo habilitación explícita de la fuente y fecha de inicio fiable por
institución, con conciliación técnica del recorrido completado antes de publicar
un reparto. Sin evidencia suficiente de cobertura para el mes/área, queda
pendiente de datos; no se reparte sobre una base posiblemente incompleta.
Sólo con cobertura acreditada y actividad realmente nula, el importe queda
como disponibilidad del mismo ámbito, sin trasladarse a otros pacientes.

La habilitación es administrativa y no agrega carga al profesional. No permite
que una declaración manual tape una inconsistencia técnica detectada. El
detalle persistente de esa evidencia deberá presentarse al aprobar este enfoque;
no se inventa un esquema aquí. Alternativa: repartir provisionalmente con los
hechos disponibles y mostrar que puede cambiar; ofrece resultados antes, pero
arriesga atribuciones aparentemente válidas sobre un denominador incompleto.

### 3. Centavos y correcciones posteriores

Recomiendo cálculo en centavos y residual determinista por ID estable del hecho:
ARS 100 entre tres atenciones produce 33,34 + 33,33 + 33,33. Conservar fuente,
regla, base utilizada, partes atribuidas y no atribuidas; la suma debe cerrar
exactamente. No sumar otra vez el gasto al consolidar vistas por área/paciente.

Si llega actividad, un gasto tardío o un ajuste, crear una versión trazable del
resultado, sin modificar la anterior. La versión vigente reemplaza a la previa
para el total; ambas quedan explicables y jamás se suman entre sí. Un reintento
con los mismos insumos no genera otra versión. Sin cierres mensuales obligatorios.
Alternativa: congelar el primer resultado y distribuir sólo diferencias; evita
revisar partes previas, pero exige más reglas para no sesgar los destinos.

## Plan siguiente a la aprobación

1. Precisar la evidencia de cobertura y el contrato de regla/versiones, con
   permisos de configuración y lectura separados. Presentar el mínimo esquema
   y las consecuencias de conservación antes de una migración.
2. Un gasto, un área y una base fiable: cálculo puro con igualdad exacta,
   denominador cero/desconocido, ajustes y exclusión de fuentes no aprobadas.
3. Persistencia idempotente/versionada y ejecución pesada fuera de la atención.
   Evaluar primero los comandos de recuperación existentes; no agregar colas,
   dependencias ni infraestructura sin una necesidad medida y aprobación.
4. API de explicación y pendientes con institución/área/sensibilidad; integrar
   al detalle del paciente sin cambiar costos directos ni generar cargos/pagos.
5. Pruebas de concurrencia, dato tardío, permisos y comparación clínica;
   medición con volumen representativo antes de fijar plazos o disponibilidad.

No comienza implementación de #37 en este checkpoint. La aprobación de las tres
condiciones queda registrada; no equivale a revisión del esquema aún pendiente,
aceptación del módulo completo ni comprobación de comprensión técnica.
Reconsiderar la regla inicial al incorporar bases que representen mejor el
consumo real de recursos.
