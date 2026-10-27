# Propuesta para completar #184

Fecha: 27/10/2026. Opción A y alcance aprobados por el usuario; implementación en PR #196.
Base revisada: main `2cb8464`, PR #196 `61eead0` (seis checks aprobados).

## Problema y persona

El operador del financiador necesita encontrar una afiliación, contrastar su
identidad, distinguir su situación administrativa de su cobertura, revisar
antecedentes y descargar exactamente la misma selección. Debe poder reconocer
los datos ausentes sin que la pantalla complete parentescos o derechos por inferencia.
Se conserva PadronTabla, navegación y configuración por URL; no se crea otra grilla.

Conceptos del dominio: padrón administrativo, afiliación, habilitación de cobertura,
estado del trámite, titular registrado, alta/baja administrativa y evidencia de origen.

Se conserva el sistema visual existente: superficies claras y texto oscuro,
acento violeta para acciones, verde para vigencia informada, ámbar para registro
administrativo, azul para futuro y gris para finalización. El texto sigue siendo
la evidencia del estado; el color no asigna derechos. No se rediseñan tokens,
tipografía, controles o navegación.

La distinción propia de esta vista es separar identidad individual, número de
origen y dos estados independientes en la misma fila. Se evitan tres defaults:
un único número ambiguo, un semáforo sin texto y datos desconocidos completados
por conveniencia. Se reemplazan por identificadores diferenciados, dos estados
textuales y faltantes explícitos, reutilizando los componentes actuales.

## Opciones

| Opción | Ganancia | Coste/límite |
| --- | --- | --- |
| A. Número individual principal, conservando número de afiliado (recomendada) | Distingue personas cuando NROAFI se comparte; evita renumerar y conserva la referencia conocida | Vista inicial de once columnas, con scroll horizontal; NUMERO faltante queda sin informar; requiere ampliar catálogo de lectura/XLSX |
| B. Conservar el número de afiliado como principal | Continuidad con la operación actual y vista inicial más compacta | NROAFI no identifica siempre a una persona; el número individual y el titular quedan en columnas opcionales |

Esta elección es operativa del usuario. No supone que OSTEL haya homologado el
significado de NROAFI o NROREF, ni convierte NUMERO en un criterio nuevo de fusión.

## Diseño recomendado (A)

### Identificadores

- **N.º individual**: `numero_interno`, que en OSTEL proviene de NUMERO. Es sólo
  presentación del valor guardado; no se genera ni se reescribe.
- **N.º de afiliado**: `numero`, que en OSTEL conserva NROAFI. Permanece visible y
  obligatorio como hoy. No se cambia su significado para otros financiadores.
- Si falta cualquiera, mostrar «Sin informar». No copiar uno sobre el otro.
- Documento continúa siendo visible para contrastar identidad; los identificadores
  se exportan como texto y mantienen ceros iniciales.

### Columnas iniciales

1. Afiliado (enlace a ficha).
2. N.º individual.
3. N.º de afiliado.
4. Documento.
5. Plan registrado.
6. Estado de cobertura (vigente / sólo administrativa / futura / finalizada).
7. Estado administrativo.
8. Alta administrativa.
9. Baja administrativa efectiva.
10. Motivo de baja administrativa.
11. Titular registrado.

Parentesco registrado, habilitación explícita, desde/finalización de afiliación,
contacto y demás columnas siguen disponibles en el selector. No se mezclan fecha
de baja administrativa y finalización de cobertura. Plan significa plan guardado
en Salud, no una equivalencia nueva del COD_PLAN original.

**Impacto que requiere aceptación:** los defaults de esta tabla son compartidos
por los financiadores. Esta vista inicial se aplicaría a consultas sin selección
explícita de columnas. Las URLs/configuraciones ya elegidas se conservan, al igual
que el número de afiliado obligatorio; no se crea un perfil por financiador ni un
nuevo almacenamiento de preferencias. La vista A es más ancha; B sería más compacta.

### Titular comprensible

Mostrar el nombre del titular y un enlace a su ficha sólo cuando exista un vínculo
registrado y autorizado dentro del mismo financiador. El ID técnico puede seguir
como columna opcional para conciliación; no reemplazarlo silenciosamente en archivos
ya existentes. Si no hay vínculo: «Sin informar», sin deducir que la persona sea titular.

Esto requiere una ampliación pequeña, pero explícita, de lectura/API y del catálogo
XLSX para el nombre del titular y el número individual. El servidor debe resolver
el nombre en la consulta, sin peticiones por fila, y proteger datos heredados que
pudieran referenciar un titular de otro financiador. No requiere modelo/migración,
servicio o permiso nuevo. No construye la familia OSTEL: esa relación sigue en #181.

### Comportamiento y validación

- Mantener búsquedas, paginación, filtros, orden y descarga de todas las filas
  filtradas. La pantalla y XLSX deben seleccionar los mismos registros y columnas.
- Mantener compatibles las URLs antiguas y sus columnas obligatorias; no agregar
  nuevas claves obligatorias que invaliden selecciones guardadas.
- Conservar el orden relativo de columnas anteriores y comprobar URLs previas,
  además de la nueva selección inicial, para evitar orden distinto en UI y XLSX.
- Seguir excluyendo salud/cobranza. Cubrir titular ausente, titular ajeno, NUMERO
  vacío, NROAFI compartido, estados contradictorios y configuraciones existentes.
- Teclado, foco, nombres accesibles e historial deben seguir funcionando con datos
  enteramente ficticios. No se prescribe un nuevo estándar WCAG o auditoría global.

## Auditoría previa a la aprobación de los cinco criterios originales

| Criterio de #184 | Estado comprobado | Qué falta para su aceptación |
| --- | --- | --- |
| Reutilizar PadronTabla y acordar columnas iniciales | La tabla se reutiliza; existe configuración por URL | Aprobar A/B y alcance global de los defaults |
| Número acordado, titular, plan, estado, alta, baja y motivo | Campos administrativos existentes seleccionables; NUMERO está en API, pero no en catálogo de tabla/XLSX; titular actual es ID | Aplicar elección de número/vista; titular comprensible; #181 aporta vínculo familiar OSTEL y #143/#183 la semántica pendiente de movimientos |
| Separar administrativo y derecho con texto | Cubierto por función común de #196 y regresiones | Aceptación humana; no cambia el backend de derechos |
| Igualdad de filtros/páginas/XLSX y permisos | Pruebas de consulta/exportación y contrastes; corregida localmente una diferencia de orden con URLs previas | Publicar/verificar la corrección e incluir los campos nuevos y sus negativas antes de aceptarlos |
| Histórico, desconocidos, accesibilidad y navegación | Navegación/foco probados; nueva prueba de historial con autor, motivo, desconocidos y dos páginas | Aceptación manual sobre el SHA final; no se acredita lector real |

Los cuerpos de #184/#181/#185 aún dicen que #186 está draft y que CUILTIT no llegó.
Eso está desactualizado: #186 ya se mergeó y conserva CUILTIT y el diccionario. El
bloqueo de familia es su implementación/aceptación en #181, no la ausencia de esa
columna. Las bajas no se aplican por #186; su conciliación sigue separada en #183.
No se actualizaron estados ni cuerpos de esos issues desde esta propuesta.

## Evidencia anterior a la implementación de A

- Se reprodujo una diferencia con una URL de columnas en orden distinto: la tabla
  usaba el orden de catálogo y la descarga enviaba el de la URL. La consulta se
  normaliza ahora al orden visible sólo si la selección es válida. Se preservan
  la URL guardada y los parámetros inválidos para que el backend siga rechazándolos,
  en vez de ocultar errores. Hay regresiones Node y de navegador. No cambia los
  defaults ni implementa las opciones A/B.
- Tres contrastes backend aprobados, frente a los dos anteriores: el nuevo compara
  número, titular registrado, plan, estados, alta, baja y motivo, ejecutando el
  formateador real con los planes de la API y el XLSX real. Una baja administrativa
  informada no convierte por sí sola la afiliación en finalizada.
- Dos recorridos focales de historial aprobados: uno existente y uno nuevo. El
  nuevo verifica autor, motivo, fecha, código desconocido, anterior/nuevo, origen,
  lote y paginación por teclado; navegar no altera el estado de cobertura.
- Datos ficticios, API simulada en navegador y SQLite en memoria en backend. Sin
  lectura de XLSX reales, cambios de reglas, migraciones reales ni nuevas dependencias.
- 33 pruebas del comando Node de contratos y nueve recorridos exclusivos #184 aprobados.
- La corrección, las ampliaciones de pruebas y este borrador están locales en el checkout de
  #196; todavía no forman parte del SHA `61eead0` ni de su CI verde.

## Decisión de alcance aprobada

Recomiendo que #184 se acepte como **vista operativa de datos registrados**, no como
implementación de identidad/familia o movimientos. Para darlo por terminado:
aprobar la vista y sus identificadores, implementar los campos de lectura acordados,
validar contra el SHA final y obtener aceptación manual. #181/#183 conservan la
responsabilidad de vincular familias y conciliar movimientos sin inventarlos.

**El usuario aprobó la opción A y esta precisión del alcance el 27/10/2026.**
La implementación y su evidencia vigente se describen en
[avance de #184](2026-10-22-issue184-avance.md). La aprobación de diseño no
acredita aceptación manual ni autoriza merge, deploy o cierre automático del issue.

Skills usadas: brainstorming para explorar opciones y dejar la decisión previa a
la implementación; interface-design para jerarquizar los datos de operación y
reutilizar la tabla y el sistema visual existentes. No se lanzaron agentes.
