# Operación de continuidad: legado, preparación y suspensión

Implementación B1/B3 del [plan de continuidad](continuidad-del-circuito.md).
Los comandos de diagnóstico sólo leen. No habilitan hospitales, crean afiliaciones,
seleccionan cobertura, otorgan permisos ni generan cargos. Los ensayos descriptos
usan datos ficticios y bases descartables; no acreditan una migración del destino real.

## 1. Diagnosticar el texto histórico

Desde `backend`, con la configuración autorizada del entorno a revisar:

```text
python manage.py diagnosticar_coberturas_legacy --institucion 1 --lote 250
python manage.py diagnosticar_coberturas_legacy --institucion 1 --aliases /carpeta-privada/aliases.json --reporte /carpeta-privada/diagnostico-nuevo.jsonl
```

La institución es obligatoria. El lote admite 1–500 ciudadanos y recorre sus PK
en orden estable, hasta la mayor PK observada al iniciar. El resumen contiene
cantidades; ni stdout ni el reporte incluyen nombres, documentos, números de afiliado
o texto legado. Los IDs del reporte permiten revisar cada registro dentro del sistema.

Formato del mapeo **ya revisado**, con IDs existentes:

```json
{
  "obra social escrita de una manera acordada": {"financiador": 1, "plan": 2},
  "otro alias revisado": {"financiador": 1}
}
```

La normalización sólo unifica Unicode, mayúsculas y espacios. No se eliminan tildes
o signos ni se buscan nombres semejantes. Un plan indicado debe pertenecer al
financiador; no se crea un plan a partir del texto. Los alias normalizados repetidos
se rechazan, al igual que claves JSON repetidas.

| Clasificación | Interpretación |
| --- | --- |
| `sin_dato` | No hay texto legado que reconciliar. |
| `sin_documento` | Falta documento o contiene un identificador NN reconocido. |
| `identidad_en_conflicto` | Documento sin normalizar, corregido en el historial o distinto del vínculo anterior. Revisión de identidad necesaria. |
| `sin_padron_verificado` | No hay afiliación documental vigente para el financiador elegido, si hubo alias. |
| `ambiguo` | Quedan varias afiliaciones vigentes; no se elige una automáticamente. |
| `plan_desconocido` | Plan ausente, inactivo, ajeno o distinto del alias revisado. |
| `sin_convenio` | Falta convenio vigente del hospital con el candidato. |
| `candidato_unico` | Hay un candidato documental para revisar. No es una nueva verificación, selección ni autorización. |

Una afiliación sin plan puede ser válida en el circuito por reglas generales;
`plan_desconocido` del diagnóstico obliga a revisar qué significa el texto histórico,
sin inventar esa decisión. La coincidencia documental y el alias son criterios
separados. Sin alias, el texto no determina el financiador aunque exista un candidato.

El JSONL comienza con fecha, institución, criterio/versionado, PK límite y huella SHA256
del mapeo; termina con un resumen `completo: true`. Un archivo sin ese cierre no es un
diagnóstico terminado. La lectura no es una instantánea transaccional: si el padrón
cambia mientras se procesa, repetir y revalidar antes de actuar.

El destino debe estar fuera del repositorio y ser un archivo nuevo. Nunca se
sobrescribe. En POSIX se crea con modo `0600`; en Windows se debe preparar una carpeta
con ACL privada antes de ejecutar. El comando no modifica ACL ni pretende que `0600`
las sustituya. Aunque no incluya nombres/documentos, los IDs siguen requiriendo
custodia. Conservación y eliminación dependen de la política acordada del responsable;
no existe una purga programada ni un plazo supuesto.

## 2. Incorporar el padrón confirmado

Se reutiliza el importador del portal del financiador:

1. Seleccionar la organización correcta y descargar su plantilla personalizada.
2. Cargar documento, número, nombre, plan y vigencia confirmados por el financiador.
3. Previsualizar; revisar filas válidas/rechazadas y coincidencias.
4. Confirmar las válidas y descargar rechazos para corregirlos. Conservar la clave
   del lote y su resultado para reintentos.
5. Repetir el diagnóstico. Los nuevos ingresos eligen expresamente la afiliación
   vigente del caso mediante el circuito existente.

No hay un aplicador adicional del reporte de legado: el importador y la selección
explícita ya cubren estas operaciones. No crear números ficticios, fusionar personas,
seleccionar retrospectivamente casos ni generar deuda histórica para dejar el
diagnóstico sin pendientes. Corregir documentos exige revisar identidades y sus
antecedentes, no modificar un archivo hasta obtener una coincidencia.

## 3. Comprobar preparación sin activar

```text
python manage.py verificar_preparacion_financiadores --institucion 1
python manage.py verificar_preparacion_financiadores --institucion 1 --financiador 1 --financiador 2 --usuario 12 --usuario 13 --exigir-completa
```

Sin `--financiador`, se revisan los que tengan convenio activo/propuesto con ese
hospital. Sin `--usuario`, se consideran las designaciones explícitas existentes
del hospital. Repetir el parámetro restringe el ensayo a sus responsables concretos.
No se toman superusuarios como sustitutos de las concesiones operativas.

El reporte JSON usa códigos, explicaciones y referencias por ID, con hasta veinte
ejemplos por código y la cantidad total. Comprueba:

- Institución, catálogo hospitalario, nodo del hospital y equivalencias comunes activas.
- Convenios vigentes, organización activa y administrador activo del financiador.
- Padrón vigente y planes que pertenezcan al financiador y sigan activos.
- Regla aplicable por prestación/categoría y plan, usando la precedencia existente.
  Ausencia de regla se señala como advertencia: puede ser una prestación no cubierta
  intencional. El porcentaje predeterminado de convenio, incluido cero, se respeta.
- Política hospitalaria y precio mediante el mismo evaluador del circuito: arancel
  general por defecto y excepción explícita. No cobrar es una decisión distinta de
  carecer de precio. Una excepción no arregla el arancel de los otros convenios.
- Responsables activos con concesiones expresas para configurar, ver/cobrar/aprobar
  y corregir dinero, registrar aceptación y resolver cobertura. Se comprueba el área y el
  acceso sensible de la misma concesión, sin combinar ámbitos ajenos.
- Si una regla exige autorización, resolutor activo y designado expresamente por el
  financiador; un auditor de lectura no cubre esa responsabilidad.
- Reservas abiertas que deben conservarse durante la transición.

`configuracion_completa: true` significa que no se detectaron faltantes obligatorios
de esta revisión. **No equivale a aceptación del piloto, completitud del padrón real,
habilitación o certificación del despliegue.** Las advertencias requieren interpretación.
Que `circuito_activo` sea false es información normal antes de habilitar. El indicador
`requiere_revision_operativa` siempre permanece true. `--exigir-completa` produce
salida de error si faltan elementos obligatorios, después de imprimir el reporte.

## 4. Migración y restauración en aislamiento

El ensayo automatizado `EnsayoMigracionRestauracionTests` crea una base SQLite
exclusiva en un directorio temporal, sin usar archivos de la demo ni conexiones
existentes. Aplica el esquema anterior a financiadores (`finanzas.0024_aprobaciones`),
incorpora un hecho, una obligación y un cobro ficticios y toma respaldo mediante
la API de copia de SQLite. Luego aplica las migraciones actuales y comprueba:

- Mismas identidades de obligación, hecho asociado y movimiento; mismos importes,
  moneda y tipo de movimiento.
- Nuevo contexto de cobertura vacío para el hecho anterior: no se inventa un origen.
- Restauración del respaldo en **otra** base; integridad, claves foráneas, esquema
  anterior y dinero original. No se ejecuta una migración inversa destructiva.

El ensayo enruta el ORM histórico a su conexión temporal y prohíbe cualquier consulta
a `default`. Esto es necesario porque `registros/0008_normalizar_documentos` omite el
alias explícito de base. La migración histórica no se modificó; no se afirma soporte
de despliegue multibase a partir de este ensayo.

Esto ensaya mecánica y compatibilidad, no volumen ni restauración PostgreSQL real.
Para el destino operativo todavía deben identificarse la versión origen, motor,
base/copia autorizada, responsable y ventana. En esa copia se requiere:

1. Registrar revisión de código y migraciones aplicadas, sin publicar credenciales.
2. Respaldar con la herramienta del motor y verificar restauración en otra base.
3. Tomar conteos y una comparación privada de IDs, fuentes, moneda e importes de
   obligaciones/movimientos. Proteger esos artefactos como información financiera.
4. Revisar `manage.py migrate --plan`; migrar la copia, nunca la base de origen
   mientras se ensaya. Repetir invariantes y diagnóstico/preparación.
5. Ejecutar el recorrido ficticio con los roles y ámbitos definidos, y repetir una
   recuperación para comprobar que no duplica cargos.
6. Si aparece una diferencia no explicada, conservar ambos respaldos/evidencias y
   detener la incorporación. No borrar deuda o reservas para conseguir un resultado verde.

Restaurar una copia previa también elimina operaciones posteriores a ese respaldo;
no es un mecanismo rutinario para desactivar una función en producción. La continuidad
funcional se maneja con configuración y permisos, preservando las fuentes históricas.

## 5. Suspender nuevas operaciones y conservar compromisos

La configuración hospitalaria existente permite desactivar cobertura con el permiso
`configurar_cobros`; se conserva su auditoría. El servicio bloquea nuevas selecciones,
evaluaciones y reservas. Las reservas abiertas no se liberan automáticamente y una
atención ya comprometida puede registrarse y recuperarse con su contexto original.

**Desactivar cobertura no equivale a suspender todos los cobros.** Una atención nueva
sin reserva puede usar el circuito legado y sus políticas vigentes. No cambiar esas
políticas sin revisar qué se pretende suspender. Un hecho ya registrado como cobertura
conserva ese origen al recuperarlo, aunque el hospital esté desactivado o cambie el precio.

- Mantener responsables para lectura, recuperación y resolución de pendientes.
- Restringir accesos hospitalarios de escritura cuando corresponda, sin retirar a
  ciegas membresías del financiador que también opera con otros hospitales.
- Revisar reservas antiguas con el equipo asistencial. Liberar sólo al confirmar que
  la prestación no se realizó, dejando usuario, fecha y motivo por el servicio existente.
- Recuperar capturas pendientes; repetir conserva una sola deuda y los cobros registrados.
- No borrar historiales, reservas, obligaciones ni movimientos; no revertir migraciones
  para apagar el circuito.

## 6. Validación y límites

Comando focal reproducible desde `backend`:

```text
python manage.py test apps.financiadores.test_legado apps.financiadores.test_preparacion --settings=cauce.settings_financiadores_test --noinput
```

Las pruebas cubren SQL de diagnóstico exclusivamente de lectura, aislamiento,
configuración incompleta, ámbitos de permisos, precio general/excepción, reserva
abierta durante suspensión, recuperación repetida y conservación de dinero.
El [piloto integral](piloto-integral.md) aporta el recorrido existente con dos
hospitales, dos financiadores e importación real por API; no se sustituye por un
segundo importador. SQLite no prueba bloqueos concurrentes de PostgreSQL.

Ejecución del 16/09/2026: **33/33 pruebas aprobadas** con SQLite (8,715 s), incluidas las
18 de B1 y 15 de preparación/suspensión/restauración. La prueba de recuperación
inyecta un fallo de captura controlado; el log de ese fallo es parte del ensayo.
La base principal de pruebas y las bases auxiliares del pase final se eliminaron
al terminar. Del primer ensayo fallido de limpieza quedó el directorio ficticio
`%TEMP%/cauce-ensayo-migracion-ep3ghhql`; la revisión automática rechazó su eliminación.
No se reintentó por otro mecanismo. No contiene datos reales ni se utiliza después.
El ensayo de migración/restauración también pasó por separado (1/1, 7,765 s), sin
una base de pruebas `default` creada, demostrando su aislamiento del resto de fixtures.

Pendiente operativo: copia real autorizada, responsables definitivos, configuración
real de ámbitos sensibles, custodia/retención de archivos y aceptación del piloto.
No se ejecutaron migraciones, conversiones ni cargas sobre datos reales.
