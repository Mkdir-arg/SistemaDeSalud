# Issue #95 — V0 de documentación de facturas del financiador

Estado: alcance funcional confirmado por el usuario en entrevista (30/09/2026); pendiente implementación y validación.
Origen: [#95](https://github.com/Mkdir-arg/SistemaDeSalud/issues/95), derivado de #86. Relacionados: #19/#20 (facturación excluida del portal), #33–#39 (finanzas), #88 (guías comerciales).

## 1. Objetivo

Una v0 demostrable en el portal del financiador para registrar y consultar documentación de facturas recibidas y emitidas por el financiador: alta, listado filtrable y detalle. Es el primer paso de un futuro hub de facturas (estados aprobada/paga/rechazada, órdenes de pago, clasificador), que queda fuera de esta v0.

Términos: ver «Registro de factura», «Factura recibida», «Factura emitida por el financiador» y «Contraparte de la factura» en `CONTEXT.md`.

## 2. Decisiones confirmadas por el usuario

| # | Decisión |
|---|---|
| D1 | Ambas direcciones: facturas recibidas por el financiador y emitidas por él fuera de Salud. |
| D2 | Registros persistentes con adjunto opcional. La carga de adjuntos se habilita por variable de entorno; en demo queda deshabilitada porque no hay almacenamiento. |
| D3 | Interruptor apagado por defecto. Apagado: el formulario no muestra archivo, el detalle dice «Adjuntos no disponibles en este entorno» y la API rechaza archivos con error explícito. Encendido: un adjunto por registro, PDF/JPG/PNG/WebP, 10 MB, validación de firma existente, descarga autenticada, filtrada y auditada. |
| D4 | Contraparte: institución o afiliado (obligatorio). Vínculo opcional a institución con convenio con ese financiador (cualquier estado) o a afiliación de su propio padrón (incluso finalizada). Sin vínculo: nombre obligatorio, CUIT/documento opcional. |
| D5 | Campos: dirección, tipo (factura, nota de crédito, nota de débito, otro), letra opcional (A/B/C/M/ninguna), número texto libre, fecha no futura, importe ARS > 0, período/concepto y observaciones opcionales, autoría automática. Fuera: CAE, validación ARCA, detalle por prestación, moneda extranjera, relación con cargos/cobros. Se bloquea el duplicado exacto por financiador (dirección + contraparte + tipo + letra + número). |
| D6 | Sin estados ni flujo; se muestra «Registrada». Edición auditada (quién, qué campos). Sin borrado ni anulación. Adjunto: se agrega si no hay uno; no se reemplaza. |
| D7 | Roles existentes: admin y operador leen y escriben; auditor sólo lee y descarga; plataforma como admin. Ni la institución ni el afiliado contraparte ven los registros. Toda descarga queda auditada. |
| D8 | Glosario anterior; menú «Facturas», ruta `/financiadores/facturas`, título «Documentación de facturas» con etiqueta «Versión preliminar», filtro recibidas/emitidas. |
| D9 | Seed de demo: unos 8 registros por financiador de la demo (3 recibidas de Hospital Central vinculadas, 1 prestador externo sin vínculo, 1 reintegro de afiliado, 1 nota de crédito, 1 emitida a institución, 1 emitida a afiliado); números `DEMO-…`; sin CUIT reales ni adjuntos; idempotente. |
| D10 | Aviso fijo en listado y detalle: «Versión preliminar: registra documentación de facturas. No emite comprobantes fiscales, no los valida ante ARCA, no liquida, no concilia ni registra pagos». Bloque de recorrido en `guia-demo-financiadores.md`; matiz puntual en `guia-demo-comercial.md:356` y `PARA-VENTAS.md:80-81`, sin reestructurar lo que reescribe #88. |

## 3. Decisiones técnicas del plan (recomendación del agente, sujetas a aprobación del plan)

- **Modelo nuevo** `RegistroFactura` en `apps/financiadores`, con migración `0009` (renumerada al integrar `main`, que ya trae `0008` del #94). FK a `Financiador`, `Convenio` (null) y `Afiliado` (null); campos de D5; `creado_por`/`creado`/`actualizado`. Adjunto como metadatos propios (ruta, nombre original, content_type, tamaño, sha256, subido_por, fecha) en el mismo modelo o en uno 1:1; no reutilizar `ArchivoClinico` porque está atado a institución.
- **Clave de duplicado**: para contraparte vinculada, el id del convenio/afiliado; sin vínculo, nombre normalizado (minúsculas, espacios colapsados, sin tildes) más identificador. Implementado con una restricción o verificación en transacción; la condición de carrera se cubre con restricción única sobre un campo de clave derivada.
- **API** como acciones del `FinanciadorViewSet`: `GET/POST /api/financiadores/{pk}/facturas/`, `GET/PATCH …/facturas/{id}/`, `POST/GET …/facturas/{id}/adjunto/`. Permisos por `requerir_financiador` (`escritura=True` para escribir). Querysets siempre filtrados por financiador; vínculos validados contra el mismo financiador. `Cache-Control: private, no-store`.
- **Auditoría** con `services.auditar` (`EventoCobertura`): alta, edición (campos cambiados en `motivo`), alta de adjunto y cada descarga.
- **Interruptor** `SALUD_FACTURAS_ADJUNTOS` (booleano, por defecto falso) en `settings.py`. El API expone si está activo para que la UI oculte el campo.
- **Almacenamiento privado fuera de `MEDIA_ROOT`**: `frontend/nginx.conf:34-36` publica todo `/media/` sin control, así que ningún archivo de facturas puede quedar bajo `MEDIA_ROOT`. Directorio configurable `SALUD_FACTURAS_ADJUNTOS_DIR` (por defecto `BASE_DIR/privado/facturas`), nombres UUID, descarga sólo vía Django con `FileResponse` `as_attachment`. Guardado en transacción con borrado del archivo si falla la persistencia, como en la evidencia de consentimiento.
- **Validación de archivo** reutilizando `apps/common.py` (lista blanca, firma, tamaño), restringida a PDF e imágenes.
- **Frontend**: nueva sección en `SECCIONES` de `PortalFinanciadores.jsx`, componente de listado (reusando `ListaPortal`/tabla, filtro dirección), detalle con aviso y formulario de alta/edición; helpers en `api/financiadores.js`. Botón principal sólo para «Nueva factura» (criterio de #86 sobre CTAs).
- **Seed** en `seed_financiadores.py` (llamado por `seed_entorno_demo`), idempotente por la clave de duplicado.

## 4. Fuera de alcance

Emisión fiscal, CAE/ARCA, liquidación, conciliación, pagos, órdenes de pago, estados, anulación, borrado, varios adjuntos, reemplazo de adjunto, visibilidad para instituciones o afiliados, clasificador, retención de archivos, corrección del bloque `/media/` de nginx para otros adjuntos existentes (riesgo preexistente, se informa aparte) y cambios en Inicio del financiador (#92).

## 5. Criterios de aceptación y evidencia esperada

| Criterio del issue | Evidencia |
|---|---|
| Recorrido corto: alta, listado, detalle | Test API de alta→listado→detalle; verificación manual o e2e del portal con datos del seed. |
| Registro pertenece al financiador activo | Tests: otro financiador recibe 404 en detalle, edición y adjunto; vínculo a convenio/afiliado ajeno rechazado. |
| Sólo roles permitidos | Tests: auditor lee pero recibe 403 al escribir; usuario sin membresía no ve; membresía inactiva no ve. |
| Adjuntos: tipo, tamaño y acceso | Tests con interruptor encendido (`MEDIA_ROOT` y directorio temporales): tipo inválido, firma incoherente, >10 MB, segundo adjunto rechazado, descarga de otro financiador 404, descarga auditada, archivo fuera de `MEDIA_ROOT`. Con interruptor apagado: carga rechazada con error explícito. |
| Estado de demo visible | Aviso en listado y detalle; textos en guías (revisión manual). |
| Datos ficticios suficientes | Test del seed: 8 registros por financiador, idempotente, prefijo `DEMO-`, sin adjuntos. |
| Negativos adicionales | Duplicado exacto rechazado (vinculado y por nombre normalizado); fecha futura e importe ≤ 0 rechazados; edición auditada con campos cambiados. |

## 6. Riesgos

- **Exposición de archivos**: si alguien apunta el directorio de adjuntos dentro de `MEDIA_ROOT`, nginx lo publica. Mitigación: validar al arrancar que el directorio no esté dentro de `MEDIA_ROOT`, y test que lo cubra.
- **Pérdida de archivos**: al encender el interruptor sin volumen persistente, los archivos se pierden en el redespliegue. Mitigación: interruptor apagado por defecto; documentar en `DESPLIEGUE.md` que requiere volumen persistente no servido por nginx.
- **Retención sin regla**: los adjuntos se conservan indefinidamente; `auditoria/retencion.py` no cubre archivos. Deuda explícita para el hub.
- **Sensibilidad de reintegros**: comprobantes de afiliados pueden revelar prestaciones. Mitigación: sin visibilidad a terceros, descarga auditada, `no-store`.
- **Lectura fiscal errónea en la demo**: mitigada por el aviso fijo y ausencia de CAE/estados.
- **Conflicto con #88** en guías comerciales: cambios limitados a líneas puntuales.
- **Migración**: aditiva (tabla nueva); rollback con `migrate financiadores 0008`, que borra sólo los registros de factura.

## 7. Validación prevista

- Focalizada, sin Docker ni bases compartidas: `cd backend && python manage.py test apps.financiadores --settings=config.settings_financiadores_test` (SQLite en memoria), priorizando el módulo de tests nuevo.
- `python manage.py makemigrations --check --dry-run --settings=config.settings_financiadores_test`.
- Frontend: `npm run build` o lint focalizado del portal si es barato; e2e `financiadores-ui` sólo si se aprueba levantar el stack.
- No se usa Railway, datos reales ni credenciales.
