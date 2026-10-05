# HEN: recorrido para evaluar la plataforma

**Demo del 01/10/2026.** Pantallas verificadas el 30/09/2026 sobre el entorno preparado para la
demo. **Todos los datos son ficticios:** instituciones, personas, obras sociales e importes.

HEN es una plataforma donde cada institución **dibuja su circuito de atención como un diagrama, y
ese diagrama pasa a ser el sistema que usa su personal**. Sobre ese circuito trabajan la guardia,
los turnos, la historia clínica, las coberturas, la red de establecimientos y la app para
pacientes.

Este documento sigue tres miradas: la de la **institución**, la del **paciente** y la del
**financiador**.

## Cómo entrar

El enlace y la clave se entregan con la demo.

| Para ver… | Cuenta |
|---|---|
| **Todo, con una sola cuenta** | `test@salud.local` |
| La jornada de una médica | `irene.bustos@hospital.gob.ar` |
| Admisión, coberturas y copagos | `guardia.adm@hospital.gob.ar` |
| El portal de una obra social | `admin@mutualdelvalle.test` |

`test@salud.local` es tu cuenta: tiene acceso a la red de instituciones, a todos los roles de
**Hospital Central**, al portal de **Mutual del Valle** y a **Hospital Piloto**, una institución
propia que queda a medio configurar para que la termines vos. Las otras cuentas muestran qué ve
cada rol. Para usar dos cuentas a la vez, abrí la segunda en una ventana privada.

![Instituciones de la red](capturas/01-instituciones.png)

Al entrar ves la red: qué instituciones están activas, cuáles están en configuración, la
ocupación de camas y la espera promedio de cada una. Con **Ingresar** entrás a una institución.

---

## 1. La institución: configurarla a su medida

### Puesta en marcha

Entrá a **Hospital Piloto**. El inicio muestra los pasos para empezar a operar: ya tiene áreas,
usuarios y personal asignado, y faltan tres.

![Puesta en marcha de Hospital Piloto](capturas/02-puesta-en-marcha.png)

1. **Agenda profesional con horarios:** un profesional y sus horarios de atención.
2. **Agenda de recurso con horarios:** una agenda que no depende de un profesional.
3. **Flujo publicado:** el circuito con el que van a empezar las atenciones.

Cada paso tiene un botón que lleva a la sección donde se completa. La institución queda **En
configuración** hasta terminarlos.

### El circuito como diagrama

En **Configuración → Flujos** está cada circuito de la institución. Este es el ingreso a la
guardia de Hospital Central: admisión, triage de enfermería, sala de espera y atención médica,
cada paso con el equipo que lo atiende.

![Circuito de ingreso a guardia](capturas/03-circuito-guardia.png)

Una versión publicada no se modifica, porque puede tener atenciones en curso. Para cambiar el
circuito se saca una versión nueva, y las atenciones que ya empezaron siguen con la anterior.

---

## 2. La institución: el trabajo de todos los días

### Guardia: fila por prioridad

La **fila de espera** ordena primero por urgencia y después por llegada. Cada consultorio llama
al siguiente desde esta misma pantalla.

![Fila de espera de guardia](capturas/04-fila-de-espera.png)

### Historia clínica firmada

Cada atención queda en la historia del paciente con el profesional que la **firmó** y su
matrícula. Están también sus estudios, recetas, alergias y antecedentes, y el consentimiento de
datos. **Quién la miró** muestra cada acceso, y **Verificar la historia** comprueba que ninguna
entrada firmada haya cambiado después.

![Historia clínica](capturas/05-historia-clinica.png)

### Turnos

La agenda de cada profesional o recurso, día por día, con cada turno reservado, confirmado o
libre.

![Agenda de turnos](capturas/06-turnos.png)

### Internación

El censo de camas por sector: ocupadas, libres, en higiene y fuera de servicio, con el tiempo de
internación de cada paciente.

![Censo de internación](capturas/07-internacion.png)

### Laboratorio e imágenes

Un estudio se pide desde la atención y vuelve al mismo recorrido. En este caso de laboratorio, el
hemograma pedido desde traumatología pasa por la toma de muestra y termina en un informe firmado
que queda en la historia clínica.

![Caso de laboratorio](capturas/08-laboratorio.png)

### Farmacia e insumos

**Qué resolver** junta lo urgente: insumos debajo del mínimo y lotes por vencer, en cada depósito.

![Farmacia: qué resolver](capturas/09-farmacia.png)

En **Movimientos**, cada consumo registra el lote y el paciente que lo recibió. Así se puede
seguir un lote hasta la persona.

![Farmacia: trazabilidad de lotes](capturas/10-farmacia-trazabilidad.png)

### Red de establecimientos

Las derivaciones entre instituciones: las que esperan respuesta, las que están en viaje y las que
ya llegaron a destino.

![Red de establecimientos](capturas/11-red.png)

### Finanzas y coberturas

**Finanzas y cobros** muestra los gastos del mes, cuánto está aprobado y cómo se reparte entre
las atenciones.

![Finanzas y cobros](capturas/12-finanzas.png)

**Coberturas y copagos** sigue cada prestación cubierta: el importe a cargo del paciente y si ya quedó resuelto.

![Coberturas y copagos](capturas/13-coberturas.png)

En el caso de una paciente se ve la cuenta completa **antes** de hacer la prestación. Su
afiliación está verificada contra el padrón de la obra social, y la consulta de cobertura separa
lo que paga el financiador de lo que paga el paciente, con el cupo que le queda.

![Cobertura en el caso de una paciente](capturas/14-cobertura-del-caso.png)

---

## 3. El paciente: la app en el celular

Abrí la app para pacientes desde la landing (**Ver la app**) o desde `/demo/app-clinica`, en el
celular. Para entrar usá el DNI ficticio **34521521** (Martina Sosa) y cualquier código de 6
dígitos.

| | |
|---|---|
| ![Inicio de la app](capturas/15-app-inicio.png) | ![Sacar turno](capturas/16-app-sacar-turno.png) |
| **Inicio:** el turno del día, cómo llegar y los resultados nuevos. | **Sacar turno:** especialidad, profesional y horario, con lo que va a pagar antes de confirmar. |
| ![En la fila](capturas/17-app-fila.png) | ![Resultados](capturas/18-app-resultados.png) |
| **Presente y fila:** avisa que llegó y ve su lugar en la fila y a qué consultorio la van a llamar. | **Resultados:** los estudios listos, para ver y descargar. |

La integración con la historia clínica y los turnos de tu institución se define en la
implementación.

---

## 4. El financiador: el portal de la obra social

Entrá con `admin@mutualdelvalle.test`, o con tu cuenta, en **Mutual del Valle**. El financiador
tiene su propio acceso y ve lo administrativo, no la historia clínica.

**Autorizaciones:** las solicitudes que mandan los hospitales, pendientes, observadas y resueltas.

![Autorizaciones del financiador](capturas/19-financiador-autorizaciones.png)

**Padrón de afiliados:** las afiliaciones con número, plan y vigencia. Se cargan de a una o
importando un Excel.

![Padrón de afiliados](capturas/20-financiador-padron.png)

**Actividad en hospitales:** el importe asignado en el mes, las prestaciones realizadas y las
reservas abiertas, con el detalle por afiliado.

![Actividad en hospitales](capturas/21-financiador-actividad.png)

---

## Qué se define en la implementación

- **Integración:** el conector con los sistemas que ya usa la institución y el acceso definitivo
  de los pacientes a la app. HEN ya ofrece una API completa y una fachada FHIR de lectura.
- **Firma digital con certificado:** la firma profesional con matrícula ya queda registrada en
  cada entrada. El certificado criptográfico y su proveedor se eligen para cada proyecto.
- **Facturación fiscal:** HEN registra prestaciones, cargos y cobros, y se integra con el
  facturador que ya use la institución.

El alcance y los plazos se definen al relevar el circuito de cada institución.
