# Documentación cerrada

**Nada de lo que hay acá describe el estado actual del sistema.** Son documentos
que se escribieron para decidir algo, se ejecutaron, y se conservan por una sola
razón: explican **por qué** el sistema es como es. Para saber qué hace hoy,
[`docs/funcionalidades/`](../funcionalidades/README.md); para usarlo,
[`docs/entornos/`](../entornos/README.md).

Se archivó el 22/09/2026 al ordenar la documentación, junto con el
[índice funcional](../INDICE-FUNCIONAL.md).

## Qué hay

| Carpeta o documento | Qué es | Sirve para |
|---|---|---|
| [`plans/financiadores/`](plans/financiadores/README.md) | El diseño completo del circuito de obras sociales: arquitectura elegida y alternativas descartadas, invariantes de cálculo, identidad y privacidad, secuencia de lotes L0–L7, decisiones Q01–Q13 aprobadas | Entender **por qué** la cobertura se modeló así antes de cambiarla |
| [`plans/`](plans/) (raíz) | Diseño lote por lote de finanzas: reparto por actividad, unidad monetaria, aprobaciones, dinero, reportería, usabilidad | Lo mismo, para finanzas |
| [`auditorias/`](auditorias/) | Cuatro barridos de lógica, configuración y UI/UX del 18/08/2026, con los errores encontrados y cómo se resolvieron | Saber qué ya se revisó y qué se decidió no arreglar |
| [`PLAN-DESARROLLO.md`](PLAN-DESARROLLO.md) | Hoja de ruta técnica por fases 0–8, con el diagnóstico del frontend que la justificó | Entender el orden en que se construyó el sistema |
| [`PLAN-DE-VERSIONES.md`](PLAN-DE-VERSIONES.md) | Ruta comercial v1.0–v4.0. El propio documento se declaró superado el mismo día | Conserva el mapeo de paquetes comerciales contra lo construido y las respuestas para lo que no existe |
| [`estado-post-demo-2026-09-15.md`](estado-post-demo-2026-09-15.md) | Cierre de la demo de finanzas del 15/09: qué se entregó, qué no, y la prioridad que fijó el usuario | Registro de esa entrega. La prioridad que declara pendiente —obras sociales— ya se implementó |
| [`historico_demo.py`](historico_demo.py) | Herramienta manual que cargaba el escenario «Hospital Demo Finanzas», sustituido | No se usa. No es un inicializador |

## Cómo leer un documento de acá

Tienen fechas, cifras, puertos y rutas del momento en que se escribieron. Un
`localhost:8090`, un conteo de pruebas o un «está pendiente» de estos documentos
es una foto, no una afirmación sobre hoy. Las decisiones sí siguen valiendo
mientras nadie las revise: son las que explican el diseño actual.

## Qué no se archiva

Un documento sale de `docs/` y entra acá cuando describe un trabajo **terminado**.
Lo que describe **cómo funciona el sistema** se actualiza en su lugar o se borra;
no se deja envejecer.

Los planes de trabajo **en curso** viven en [`docs/plans/`](../plans/), no acá. La
diferencia es si la decisión ya se ejecutó:

| | Dónde | Qué es |
|---|---|---|
| `docs/plans/` | Fuera del archivo | Trabajo pendiente o en curso. Se mueve acá cuando termina |
| `docs/historico/plans/` | Acá | Decisiones ya ejecutadas. Explican el diseño actual |
