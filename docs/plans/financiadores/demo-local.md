# Demo local de financiadores

Preparada el 15/09/2026. Acceso en esta máquina: <http://127.0.0.1:5188>.

### Actividad y descarga — 16/09/2026

En «Actividad en hospitales», el financiador dispone de filtros, totales de todas las páginas y CSV. La pantalla abre el mes actual; «Limpiar filtros» permite consultar todo el período visible. El importe asignado suma cargos originales y acuerdos; no es el saldo pendiente de pago.

Se verificó el recorrido real con Obra Social Demo (3 prestaciones realizadas, $24.000 asignados) y Mutual Demo (2 realizadas, $17.500). La mutual conserva su operación pendiente del hospital cuyo convenio finalizó. Los resultados se contrastaron con los CSV y la base ficticia, sin registrar nuevos cobros ni modificar atenciones.

Scripts `verificar-actividad.cjs` y `verificar-datos-actividad.py`, capturas y CSV en `%LOCALAPPDATA%/Salud/demos/financiadores-main2/revision-actividad/`. Los scripts están en su directorio padre. Son artefactos locales de la demo; no contienen datos reales ni forman parte del PR.

## Cuentas

Contraseña de todas las cuentas ficticias: `SaludDemo2026!`.

| Cuenta | Uso |
| --- | --- |
| `financiador@demo.local` | Administración de Obra Social Demo; ingresa directamente al portal |
| `hospital@demo.local` | Hospital Demo; Finanzas y permisos clínicos para revisar las reservas de esta demo |
| `auditor@demo.local` | Portal de la obra social, sólo lectura |
| `mutual@demo.local` | Administración de Mutual Demo, con actividad en ambos hospitales |
| `admin@demo.local` | Administración de plataforma, para probar altas/configuración |

Para cambiar de rol, cerrar sesión antes de entrar con otra cuenta; también se puede usar una ventana privada independiente.

## Datos y recorrido

- Hospital Demo y Obra Social Demo, con convenio activo.
- Plan base: 80 % de cobertura, seis unidades por prestación y año calendario.
- Consulta: arancel general $10.000; parte financiador $8.000 y copago $2.000.
- Radiografía: arancel general $20.000; con cupo, financiador $16.000 y copago $4.000.

| Persona ficticia | Caso | Situación preparada |
| --- | --- | --- |
| Ana Paz, documento `00111222`, afiliación `00001` | 1 | Dos radiografías externas; quedan cuatro. Consulta realizada con copago aceptado: obligaciones de $8.000 y $2.000 |
| Luis Ruiz, documento `00222333`, afiliación `00002` | 2 | Seis radiografías externas; próxima radiografía no cubierta. Evaluar muestra $20.000 a cargo del paciente, sin crear deuda por consultar |
| Marta López, documento `00333444`, afiliación `00003` | 3 | Consulta realizada con $2.000 pendientes de resolución. Una radiografía reservada con copago aceptado, todavía sin realizar |

1. Como financiador, recorrer **Cobertura**, **Aranceles**, **Padrón**, **Consumos externos** y **Actividad en hospitales**. Se pueden descargar las plantillas personalizadas desde el importador.
2. Como hospital, abrir <http://127.0.0.1:5188/finanzas/coberturas>. La bandeja muestra la consulta resuelta, el saldo pendiente y la radiografía reservada.
3. En **Evaluar una prestación**, elegir a Luis (caso 2) y Radiografía para ver el cupo agotado; comparar con Ana (caso 1).
4. En **Finanzas y cobros**, consultar las tres obligaciones iniciales: $8.000, $2.000 y $8.000. El dinero cobrado inicial es cero.

Se puede modificar libremente esta información ficticia desde las pantallas; la base conserva los cambios entre reinicios. No se repone ni se borra automáticamente.

### Ampliación: vigencias y auditoría

Se agregaron **Hospital Norte Demo** y **Mutual Demo**, manteniendo los datos anteriores. La cuenta `hospital@demo.local` puede elegir cualquiera de los dos hospitales.

- Mutual Demo tiene el plan M70: 70 % y seis consultas por año compartidas entre hospitales.
- Lucía Demo (`00444555`, afiliación `M0001`) tiene los casos 4 y 5: una consulta de $10.000 en Hospital Demo y otra de $15.000 en Hospital Norte Demo. Las obligaciones de la mutual son $7.000 y $10.500; no se registraron cobros.
- Durante el recorrido se finalizó y reactivó su afiliación. Quedó vigente y conserva los dos usos del cupo.
- El convenio de Mutual Demo con Hospital Norte Demo quedó **finalizado**, con motivo. Su consulta sigue visible como **Histórico pendiente** porque la mutual aún debe su parte. El convenio con Hospital Demo continúa activo.
- En Padrón se pueden probar finalización/reactivación con motivo. En Planes se administra nombre/estado sin cambiar el código. En Convenios se puede proponer un acuerdo nuevo después de cerrar el anterior.
- Como hospital, abrir **Registro de accesos**, elegir **Consulta de un financiador** y filtrar por hospital. Se ven usuario, persona, momento y referencias de actividad consultada; no se otorgó historia clínica a la mutual.

Guion ejecutado con navegador y API reales: `verificar-vigencias.cjs`. Capturas y resultado en `revision-vigencias/`, dentro del directorio local de la demo. Existe un respaldo SQLite previo a la ampliación (`antes-vigencias-*.sqlite3`). La actualización `actualizar_vigencias.py` reconoce su marca de preparación y no repone los datos ya creados.

El portal ahora usa el sidebar y el encabezado compartidos de I-Core Salud. Las secciones se abren desde el menú lateral; el selector de financiador está en ese mismo menú. En móvil se accede con «Abrir menú». La sección y la organización elegida se conservan al recargar la URL. Para ver la corrección en una pestaña abierta, recargar la página.

## Ubicación y operación

Base, scripts, logs y capturas: `C:\Users\Juanito\AppData\Local\Salud\demos\financiadores-main2`.

- Backend: `127.0.0.1:8766`, SQLite exclusiva `demo.sqlite3`.
- Frontend: `127.0.0.1:5188`, proxy hacia ese backend.
- Los procesos quedan en segundo plano. La demo no usa la base de desarrollo ni envía correos.
- `demo.py` reutiliza la preparación mínima de pruebas y los servicios del módulo para cargar datos ficticios; no es un comando de carga para producción.

Para detener y volver a iniciar, desde PowerShell:

```powershell
& "$env:LOCALAPPDATA\Salud\demos\financiadores-main2\detener.ps1"
& "$env:LOCALAPPDATA\Salud\demos\financiadores-main2\iniciar.ps1"
```

El inicio reutiliza los datos existentes y rechaza ocupar puertos de otros procesos. El entorno Python está en `%TEMP%\cauce-financiadores-venv`; si se elimina ese entorno temporal habrá que recrearlo con las dependencias del proyecto.

## Verificación y continuidad

### Seguimiento hospitalario agregado el 16/09/2026

Ingresar con **`hospital@demo.local` / `SaludDemo2026!`** y abrir [Seguimiento de cobros](http://127.0.0.1:5188/finanzas/coberturas?tab=seguimiento). En Hospital Demo, buscar el caso **9**, de Valeria Seguimiento Demo:

- Cuenta del financiador: **$8.000** originales, **$3.000** cobrados y **$5.000** pendientes.
- Cuenta de la paciente: **$2.000** de copago aceptado, todavía sin cobro.
- «Ver cuenta» abre el detalle habitual de Finanzas. El cobro ficticio `DEMO-SEGUIMIENTO-PARCIAL` se registró desde ese modal y actualizó el seguimiento.
- En la vista «Pendientes administrativos», buscar el caso **8**: la evaluación sigue pendiente y el importe aparece **por determinar**, sin deuda generada.

La prestación nueva se preparó con los servicios existentes en la SQLite exclusiva, después de respaldarla; se conservaron los casos anteriores. El cobro sí se registró mediante navegador y API reales. Base, auditoría y pantalla coinciden, sin movimientos duplicados al repetir la verificación. Capturas y resultados en `revision-seguimiento`, dentro del directorio local de la demo. [Evidencia y límites](seguimiento-hospitalario.md).

El seguimiento ahora incluye **«Exportar CSV»**: aplicar los filtros y descargar la vista completa, hasta 5.000 filas. Se descargaron desde el navegador las dos cuentas del caso 9 y el pendiente del caso 8; los nueve importes monetarios de cada cuenta coinciden con JSON y base. El importe desconocido del caso 8 queda vacío. El archivo usa punto y coma, coma decimal y UTF-8; IDs y textos libres llevan un apóstrofo inicial para conservarlos como texto al abrirlos en una hoja de cálculo.

Archivos descargados, capturas y comprobación contra la base en `revision-exportacion`, dentro del directorio de la demo. Esta verificación sólo agregó auditorías de lectura: no cargó pacientes ni registró nuevos cobros. La vista de captura no tiene filas en esta demo; se verificó su archivo vacío por API y su botón deshabilitado. El contenido de capturas pendientes está cubierto por pruebas automatizadas.

### Circuito clínico agregado el 16/09/2026

En [la demo](http://127.0.0.1:5188), iniciar sesión con **`consulta@demo.local` / `SaludDemo2026!`**. «Mi trabajo» ofrece **Consulta con cobertura · demo**. Ingresar a Clara (`00888111`) o Diego (`00888222`) para crear otra consulta y probar la cobertura antes de atender.

Resultados ya disponibles: [Clara, caso 7](http://127.0.0.1:5188/casos/7), con $8.000 al financiador y $2.000 de copago aceptado; [Diego, caso 8](http://127.0.0.1:5188/casos/8), con atención completada y afiliación pendiente sin deuda generada. La [historia de Clara](http://127.0.0.1:5188/historia/6?tab=cobertura) muestra su selección por caso.

Se verificaron ambos recorridos completos mediante la interfaz real y se corroboraron sus estados en la SQLite exclusiva. Se preservaron todos los datos anteriores de la demo y se generó respaldo antes de agregar este recorrido. Detalles técnicos y límites: [circuito clínico](circuito-clinico.md).

### Evidencia inicial de la demo

Se verificaron los cuatro accesos por API; la skill `playwright` guio el inicio de sesión y la inspección de pantallas reales del portal y del hospital. El navegador mostró los aranceles, los tres estados de reserva esperados y «No cubierta — cupo agotado» para la radiografía de Luis, con $20.000 a cargo del paciente. El recurso legado `favicon.ico` responde 404 y hay avisos de desarrollo de React Router; no impidieron el recorrido.

No se repitió la batería completa de pruebas: este paso sólo creó la demo y su guía, sin cambios funcionales al módulo. SQLite permite explorar el producto; la concurrencia ya se probó en PostgreSQL en la entrega anterior.

No hay decisiones bloqueantes para continuar el alcance aprobado Q01–Q13. Para un piloto real siguen pendientes la revisión del resultado, la configuración del hospital y la política organizacional de conservación. Las autorizaciones previas pertenecen al incremento posterior L7.
