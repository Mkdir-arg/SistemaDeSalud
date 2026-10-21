# Prueba local de OSTEL #180 / #185

Preparada el 21/10/2026. Todos los datos son ficticios. No importar aquí los archivos reales de OSTEL.

## Entrar

- Aplicación: http://127.0.0.1:5189/financiadores/padron
- Backend: http://127.0.0.1:8139
- Accesos: `C:/Users/Juanito/AppData/Local/Temp/salud-ostel-180-zd1jg1g3/accesos-locales.json`. Usar primero la cuenta `operador`; luego `auditor`. Las contraseñas no se copian al repositorio.
- Excel: `C:/Users/Juanito/AppData/Local/Temp/salud-ostel-180-zd1jg1g3/prueba-guiada`.
- Organización: **OSTEL - Prueba local ficticia**.

La base conserva algunos lotes del chequeo automático con personas 0201/0202. Los seis archivos de esta guía usan personas 0101–0107. La persona 0107 ya existe con habilitación de cobertura; el archivo 06 también se usó en el chequeo real de conflictos y puede repetirse sin duplicarla. Los otros cinco quedaron preparados para la prueba humana.

## Recorrido y resultados esperados

1. **Alta habitual.** Padrón → Registrar afiliación. Usar documento ficticio `99018801`, nombre `PRUEBA MANUAL CON COBERTURA`, número de afiliación `MANUAL-801`, fecha de hoy y el plan ficticio disponible. Completar los campos obligatorios. En Afiliación, **Habilitar cobertura junto con el registro** debe venir marcado; el resumen debe mostrarlo. Guardar: debe aparecer como vigente sin un paso adicional de habilitación. Esto no garantiza una prestación: siguen aplicando plan, fechas, convenio y reglas.

2. **Excepción administrativa.** Repetir con documento `99018802`, nombre `PRUEBA MANUAL ADMINISTRATIVA`, número `MANUAL-802`. Desmarcar la habilitación; se puede dejar sin plan. Guardar y elegir Estado → **Sólo registro administrativo**. Debe aparecer ahí y no en Vigentes. Abrir la ficha, editar la habilitación con motivo y asignar plan si corresponde; guardar y comprobar el cambio de estado. Volver a deshabilitar con otro motivo. Revisar el historial: ambos cambios deben ser trazables. No finaliza la afiliación ni borra a la persona.

3. **Base OSTEL.** Importar Excel → Formato **OSTEL** → desmarcar **Habilitar cobertura** para esta prueba administrativa. Elegir `01-base.xlsx` y Revisar archivo. Esperado: 2 listas, 0 pendientes. Aplicar. Cerrar y filtrar **Sólo registro administrativo**: personas 0101 y 0102, ambas con `FAMILIA-GUIA` como afiliación. Son dos personas; compartir NROAFI no las fusiona. No se debe inferir grupo familiar, plan ni cobertura.

4. **Aplicación parcial y corrección.** Mantener desmarcada **Habilitar cobertura**. Cargar `02-parcial.xlsx`: 1 válida y 1 pendiente. Aplicar la válida; la persona 0103 se incorpora y 0104 queda pendiente. Revisar fila → CUIL `27990186044` → motivo `Verificado contra dato ficticio de la guía` → Guardar y revalidar. Debe quedar lista; aplicar. Elegir Mostrar filas → Aplicadas → Ver detalle de 0104 → Historial de revisiones. Deben conservarse el valor original `123`, la corrección y su responsable. Guardar una corrección por sí solo no aplica la fila.

5. **Identidad contradictoria.** Cargar `03-identidad-conflictiva.xlsx`: las dos filas comparten NUMERO `GUIA-105`, por lo que ambas quedan en revisión y ninguna se incorpora. Corregir el Número interno de 0106 a `GUIA-106`, con motivo. Revalidar también 0105 si sigue pendiente: resolver un conflicto no aplica automáticamente su contraparte. Como alternativa, excluir una fila con motivo y comprobar que queda como Excluida con evidencia conservada. No debe haber una fusión silenciosa.

6. **Cambio entre fuentes.** Después del paso 3, cargar `04-cambio-administrativo.xlsx` manteniendo desmarcada **Habilitar cobertura**. La diferencia de nombre de 0101 requiere revisión. Abrir la fila: deben verse los valores actuales del padrón y los originales del archivo. Confirmar el cambio con motivo, revalidar y aplicar. El nombre cambia; la habilitación, plan y fechas existentes se conservan.

7. **Bajas como evidencia.** Cargar `05-bajas-evidencia.xlsx`. Ya no hay selector de contenido: la fecha de baja en la fila hace que se marque como evidencia, independientemente del checkbox de cobertura. No debe haber filas aplicables ni opción de forzar la baja mediante corrección. La persona 0101 continúa registrada. Excluir la fila tampoco elimina al afiliado. Las fechas y movimientos efectivos siguen pendientes de reglas de OSTEL.

8. **Conservación de cobertura.** Cargar `06-cobertura-existente.xlsx` con **Habilitar cobertura** desmarcado. La persona 0107 ya está habilitada: debe quedar como conflicto y no aplicarse aún. Revisar fila muestra el valor actual y el solicitado. Escribir un motivo, guardar/revalidar y aplicar; debe conservar su habilitación. Repetir con la plantilla del sistema: el conflicto muestra un campo de motivo para conservar la cobertura actual. Para nuevas personas, marcado habilita y desmarcado crea sólo el registro administrativo; las prestaciones siguen sujetas a reglas.

9. **Historial, repetición y exportación.** Cerrar/reabrir Importar Excel y seleccionar un lote previo desde Importaciones registradas; debe abrirse con su formato y detalle correctos. Las filas ya aplicadas no deben ofrecer una nueva aplicación. Volver a subir `01-base.xlsx` puede requerir revisión si el nombre fue cambiado en el paso 6; nunca debe duplicar las personas. Cambiar a Plantilla del sistema, descargarla y verificar que sigue disponible el circuito habitual. En el padrón, seleccionar Todos o Sólo registro administrativo, mostrar la columna Habilitación de cobertura y exportar XLSX; contrastar filas y filtro con la pantalla.

10. **Permisos y UX.** Salir y entrar como `auditor`: consultar padrón e historial disponible en sus pantallas, sin botones de alta/importación/edición. Volver como operador y abrir una corrección: el formato, archivo y cierre se bloquean mientras se edita; Cancelar permite salir sin guardar. Probar también ventana angosta y revisar legibilidad, scroll de la tabla, mensajes y foco. Cualquier incomodidad visual queda pendiente de la aceptación humana.

## Evidencia y límites

- Migración `0013_administrativa_cobertura` aplicada a la base SQLite ficticia, con respaldo anterior `ostel-antes-0013.sqlite3`.
- Chequeo real con navegador, API y SQLite: login operador, carga, aplicación parcial, subsanación, segunda aplicación, historial, filtro administrativo y auditor sin importación: OK.
- Las pruebas técnicas previas cubren alta predeterminada/excepcional, permisos, revisiones concurrentes, preservación de cobertura y consumidores clínicos/financieros. Este recorrido no configura un hospital ni demuestra prestaciones, reservas o liquidaciones completas mediante navegador.
- SQLite tuvo un bloqueo al cargar consultas simultáneas de Inicio. El servidor local usa `--nothreading` para esta demo; esto no prueba concurrencia PostgreSQL, rendimiento real ni producción.
- Hay trabajo paralelo de permisos/navegación en el mismo checkout, excluido de los commits OSTEL. La UI local también refleja esos archivos. Las verificaciones corresponden al estado observado, no a una copia inmutable del commit.
- No hubo push, despliegue ni uso de los Excel reales. No restaurar automáticamente una versión antigua: ignorar el nuevo indicador podría tratar registros administrativos como habilitados.

## Reiniciar si se cerró el entorno

En dos terminales, ejecutar respectivamente los scripts `iniciar-backend.ps1` e `iniciar-frontend.ps1` de la carpeta temporal indicada. No hacerlo si los puertos 8139 y 5189 ya están ocupados por esta demo. La base persiste; no hay que volver a migrar ni borrar datos para continuar la guía.

Al terminar, anotar qué pasos pasaron y dónde se apartó el resultado esperado. La aceptación visual y los escenarios de producción siguen separados de los checks técnicos.
