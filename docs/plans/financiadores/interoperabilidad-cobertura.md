# Cobertura administrativa en Red y FHIR

## Contrato de esta entrega

Se conserva FHIR R4 **4.0.1**. El subconjunto implementado de
[Coverage](https://hl7.org/fhir/R4/coverage.html) describe la afiliación vigente;
no ofrece elegibilidad para una prestación, autorización ni garantía de pago.
No se anuncia conformidad con un perfil nacional o de un receptor aún no acordado.

- `GET /fhir/Coverage?beneficiary=Patient/<id>`: referencia local obligatoria,
  paginación `_count`/`_offset`, total y enlace siguiente. No busca por documento.
- `GET /fhir/Coverage/<ciudadano>-<afiliado>`: revalida la misma afiliación actual.
- Sólo lectura, autenticación y `padron_admision` en la institución de esa ficha.
  Una membresía de reportes en otra institución no concede lectura allí.
- Se reutiliza el resumen administrativo: módulo habilitado, documento identificado,
  padrón vigente y convenio vigente en ese hospital. Un plan inactivo no se exporta.
- Una ficha con varias afiliaciones produce varios recursos; no elige pagador.
- Un dato sólo declarado no produce Coverage. Se conserva la extensión textual de
  Patient para clientes existentes. El historial del caso no se exporta como actual.
- Cada lectura registra paciente, usuario, hospital y momento. Si falla esa evidencia,
  la consulta administrativa no entrega la cobertura.

## Campos

| Elemento R4 | Fuente / alcance |
| --- | --- |
| `id` | Par local ciudadano-afiliado; evita asignar la ficha de otro hospital. |
| `status` | `active`, únicamente mientras cumple las condiciones de lectura actual. |
| `identifier` | Número de afiliado bajo `urn:cauce:id:financiador:<id>:afiliado`. |
| `beneficiary` | Referencia al Patient del hospital consultado. |
| `period.start` | Fecha de inicio informada por el padrón. No inventa fecha final. |
| `payor` | Organization contenida, identificada por el ID local del financiador. |
| `class` | Plan si existe; valor = ID local, nombre = denominación del padrón. |

El pagador contenido evita publicar un catálogo transversal de financiadores bajo
Organization. No se emiten porcentajes, cupos, saldos, diagnósticos, contactos ni
consentimientos financieros. Los campos obligatorios se contrastaron con las
[definiciones oficiales R4](https://hl7.org/fhir/R4/coverage-definitions.html).
Las pruebas del contrato no sustituyen homologación con un consumidor externo.

## Traslados

El destino conserva su propia ficha. Un documento normalizado coincidente permite
reutilizarla, preservando ceros iniciales y su declaración previa. Los marcadores NN
no fusionan personas; dos fichas legadas conflictivas requieren revisión explícita.

El dato declarado puede viajar como antecedente. El nuevo caso no hereda afiliación
elegida, aceptación, reserva, autorización ni deuda del origen. La pantalla consulta
el padrón y convenio del destino al abrirse y pide selección expresa para su caso.
El afiliado estable sigue siendo el mismo: sus consumos del cupo se comparten según
las reglas existentes. Repetir la aceptación del traslado no crea otro caso.

No se enviaron datos a terceros. La prueba con un consumidor FHIR concreto y la
reconciliación de identidades reales pertenecen a la aceptación del entorno destino.
