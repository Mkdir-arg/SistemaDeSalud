# Cumplimiento normativo

> Qué implementa el sistema respecto de la normativa sanitaria y de datos
> personales argentina, **con la evidencia en el código**, y qué queda por resolver
> con asesoría legal.
>
> Verificado contra el código el 22/09/2026.

**Esto no es una opinión legal.** Es el inventario técnico de lo que el sistema hace,
para que quien tenga que dar la opinión legal —del lado del hospital, del ministerio
o de la jurisdicción— sepa contra qué evaluarlo. La adecuación final depende de la
jurisdicción y de la ley aplicable, y **no está hecha**.

---

## Ley 26.529 — Derechos del paciente e historia clínica

### Historia clínica única y trazable

Cada ciudadano tiene una historia clínica por institución. Las entradas se firman con
autor y matrícula, y **no se borran ni se editan**: una corrección es otra entrada, y
las dos quedan.

### Integridad demostrable

Cada entrada firmada lleva un **sello encadenado** con la anterior. Si alguien
modificara una entrada vieja directamente en la base, la cadena deja de cerrar y la
verificación lo muestra en pantalla.

Es lo que permite sostener ante un tercero que la historia no fue alterada después
del hecho. Ver `backend/apps/registros/integridad.py`.

### Quién accedió a la historia

**Cada lectura de información clínica sensible queda registrada**: quién, qué
paciente, qué recurso, desde qué institución, con qué IP, cuántos resultados y
cuándo. Incluye las consultas que entran por la fachada FHIR.

Ese registro lo leen sólo los roles de conducción y control —administrador de
institución, jefe de área, auditor estatal y plataforma—, y **no se puede crear,
editar ni borrar desde la API**. Un profesional no audita a sus colegas.

Pantalla: `/accesos`. Ver [`funcionalidades/auditoria-consentimiento/`](funcionalidades/auditoria-consentimiento/README.md).

### Conservación por diez años

`ANIOS_HISTORIA_CLINICA = 10` en `backend/apps/auditoria/retencion.py`. La historia
clínica está marcada como **protegida**: el comando de purga **se niega a tocarla**
antes del plazo legal.

El registro de accesos se conserva al menos lo mismo que lo que audita: borrarlo
antes dejaría diez años de historia sin poder decir quién la miró.

### Firma

La firma implementada es **funcional**: queda registrado quién firmó, con qué
matrícula y cuándo, y qué rol lo habilitaba en ese paso.

**No es firma digital con certificado.** Ver la sección de la Ley 25.506.

---

## Ley 25.326 — Protección de datos personales

### Consentimiento (art. 5)

Se guarda **cada consentimiento y cada revocación como un registro nuevo**, sin pisar
el anterior, con su modo —escrito, verbal o digital—, su alcance, la institución y
quién lo tomó.

El motivo es concreto: ante un reclamo lo que importa no es el estado de hoy sino
**qué se consintió y cuándo**. Un campo de sí/no en la ficha del paciente no puede
contestar esa pregunta.

### La urgencia no se bloquea (art. 8)

**Una atención de urgencia no se frena por falta de consentimiento.** La ley exceptúa
expresamente los datos necesarios para una prestación de salud, y un sistema que
detuviera una guardia por un consentimiento faltante sería peligroso además de
equivocado.

Lo que hace el sistema es **registrar que falta**, no bloquear.

### Retención

`python manage.py purgar_datos` aplica la política de retención.

**Corre en seco por defecto**: muestra qué borraría y no borra. Hay que pasarle
`--aplicar` para que actúe. Un borrado masivo que se dispara sin que nadie lo haya
mirado es peor que no purgar: lo segundo se arregla corriendo el comando; lo primero
no se arregla.

Cada plazo tiene su motivo escrito al lado, en `backend/apps/auditoria/retencion.py`.
Los que tienen plazo legal mínimo están marcados como protegidos y el comando los
rechaza.

### Minimización en los accesos del financiador

Una obra social ve **prestación, fecha, cantidad e importe propio**. No accede a la
historia clínica. Y un financiador no puede consultar el padrón ni los consumos de
otro, ni siquiera para detectar un cambio de cobertura.

La auditoría del circuito de cobertura (`EventoCobertura`) registra la operación
administrativa **sin datos clínicos**.

### Aislamiento entre instituciones

Todo se acota a la institución donde la persona tiene membresía activa. Un 404 puede
significar «no existe para vos», y es deliberado: un 403 confirmaría que el
identificador es válido.

### Los archivos clínicos no son públicos

Las subidas clínicas **no se sirven por `/media`**. Salen por un endpoint que valida
permisos en cada descarga. Conocer la URL no alcanza.

---

## Ley 25.506 — Firma digital

**No está implementada.**

Lo que hay es la firma funcional por rol y matrícula descrita arriba, que identifica
autoría dentro del sistema. Lo que la ley pide para oponer una firma a un tercero es
otra cosa: **un certificado emitido por un certificador licenciado** y el dispositivo
donde vive la clave privada.

En `backend/apps/registros/integridad.py` está identificado el punto donde se
insertaría —guardar la firma y el certificado junto a la entrada, y sumar un chequeo
a la verificación— y por qué no se implementó: **elegir el certificador y el
dispositivo es una decisión del cliente**, no del producto.

> Al hablar con un cliente: no decir «está listo, sólo falta el certificado».

---

## Lo que falta y quién lo decide

Ninguna de estas cosas la puede resolver el equipo de desarrollo por su cuenta:

| Qué falta | Quién decide |
|---|---|
| **Adecuación jurídica final** según jurisdicción y ley aplicable | Asesoría legal del cliente |
| **Política de privacidad** publicada | Cliente |
| **Procedimiento ante una solicitud de acceso del paciente** a sus datos | Cliente + producto: hoy no hay una pantalla que exporte todo lo de una persona |
| **Exportación de datos del paciente** en formato portable | No está construido |
| **Certificador y dispositivo** para la firma digital | Cliente |
| **Perfiles FHIR** exigidos por la jurisdicción | Jurisdicción |
| **Autenticación exigida a clientes FHIR externos** en producción | Infraestructura del cliente |
| **Plazos de retención propios** si la jurisdicción pide otros | Asesoría legal, y después se ajusta la política |
| **Acuerdo de tratamiento de datos** entre hospital y financiador | Las dos partes |

## Antes de una auditoría o una licitación

Lo que conviene tener a mano, porque existe y se puede mostrar:

- [ ] `/accesos` funcionando, con una consulta por paciente.
- [ ] La verificación de integridad de una historia, en pantalla.
- [ ] El panel de consentimientos de un paciente, con su historial.
- [ ] `python manage.py purgar_datos` en seco, que muestra la política y sus motivos.
- [ ] `python manage.py respaldar`, que restaura y compara en cada corrida.
- [ ] `python manage.py check --deploy` limpio.
- [ ] La matriz de roles y permisos: [`ROLES-Y-PERMISOS.md`](ROLES-Y-PERMISOS.md).

Y lo que hay que decir sin que lo pregunten: **el sistema todavía no operó con datos
reales de pacientes**. Todo lo anterior está probado sobre escenarios ficticios.

## Referencias en el código

| Qué | Dónde |
|---|---|
| Sellado e integridad de la historia | `backend/apps/registros/integridad.py` |
| Política de retención, con el motivo de cada plazo | `backend/apps/auditoria/retencion.py` |
| Registro de accesos clínicos y quién puede leerlo | `backend/apps/auditoria/views.py` |
| Consentimiento y sus modos | `backend/apps/registros/models.py` |
| Permisos por institución, área y sensibilidad | `backend/apps/common.py`, `backend/apps/finanzas/permisos.py` |
| Alcance del financiador | `backend/apps/financiadores/permisos.py` |
