# Guion de demo comercial

Entorno **demo**: <http://localhost:8082> · verificado el **17/09/2026**.

Recorrido completo de **45–50 minutos**. Los bloques son independientes: con 20
minutos, hacé el 1, el 4 y el 6.

> Todo lo que se muestra es **ficticio**: instituciones, personas, proveedores,
> obras sociales, importes y convenios. Decilo una vez al principio. No son
> precios de mercado ni datos de ningún hospital real.

---

## Lo que hay cargado

| Institución | Qué muestra |
|---|---|
| **Hospital General Los Aromos** | Finanzas maduras: un año de historia (oct/25 → sep/26), gastos, repartos, costos por atención, cobros y el circuito de obras sociales |
| **Hospital Central** | Operación clínica densa: guardia con triage, 547 casos, 28 camas, farmacia, agenda, historia clínica sellada |
| **Hospital Municipal de Villa Real** | El efector chico de la red que deriva al grande |

**Esa diferencia es el argumento, no un defecto.** Una plataforma provincial no
recibe hospitales parejos: recibe uno con la gestión económica ordenada y otro
que recién arranca. Mostrar los dos en la misma pantalla vale más que mostrar uno
perfecto.

| Módulo | Datos |
|---|---|
| Casos | 547 en Hospital Central · 196 en Los Aromos · 14 en Villa Real |
| Filas | ~25 esperando en la sala de guardia, urgentes al frente |
| Internación | 28 camas: libres, ocupadas, en higiene, bloqueadas |
| Agenda | 410 turnos con los 5 estados (reservado, confirmado, presente, ausente, cancelado) · 1 bloqueo con 4 turnos afectados |
| Farmacia | Los 6 estados de pedido · 2 lotes trazables hasta el paciente |
| Red | 1 red · 14 traslados (7 aceptados, 3 rechazados, 4 esperando) |
| Historia clínica | 617 entradas, selladas y encadenadas · 38 consentimientos |
| **Finanzas** | $750.000 aprobados en septiembre · 110 gastos · un año de evolución |
| **Financiadores** | 2 obras sociales · 12 afiliados · 20 atenciones con cobertura · $463.400 en cargos |

---

## Con qué usuario entrar

Para cambiar de usuario usá **otra ventana del navegador en modo privado**. Dos
pestañas normales comparten la sesión.

**Hospital General Los Aromos** — contraseña `LosAromos2026!`

| Perfil | Usuario |
|---|---|
| Administración + todos los permisos financieros | `elena.rivas@losaromos.test` |
| Administrativa: carga pero **no aprueba** | `paula.benitez@losaromos.test` |
| Configuración | `mateo.salvatierra@losaromos.test` |
| Médicos | `lucia.ferreyra@` · `andres.molina@` · `valeria.costa@` |

**Consultorios externos y financiadores** — contraseña `Financiadores2026!`

| Perfil | Usuario |
|---|---|
| Médica de consultorios externos | `irene.bustos@losaromos.test` |
| Mutual del Valle (portal) | `admin@mutualdelvalle.test` · `auditor@mutualdelvalle.test` |
| Obra Social Provincial (portal) | `admin@osprovincial.test` · `auditor@osprovincial.test` |

**Hospital Central y red** — contraseña `demo1234` (salvo el superusuario)

| Perfil | Usuario |
|---|---|
| Superusuario / plataforma completa | `admin@salud.local` / `admin1234` |
| Gobierno estatal: efectores y redes | `plataforma@salud.local` |
| Auditoría con alcance estatal | `auditor@salud.local` |
| Administración de la institución | `admin.central@hospital.gob.ar` |
| Diseño de flujos y formularios | `config.central@hospital.gob.ar` |
| Guardia | `guardia.jefe@` · `guardia.adm@` · `guardia.enf@` · `guardia.med@` |
| Especialidades y estudios | `cardio.med@` · `trauma.med@` · `lab.med@` · `img.med@` |
| Internación | `int.adm@` · `int.med@` |
| Villa Real | `villa.med@` · `villa.jefe@` · `villa.adm@` |

---

## 0. Antes de empezar · 3 minutos

```bash
curl -s http://localhost:8002/api/health/     # {"status": "ok", ...}
```

Abrí y dejá listas, en pestañas: Resumen de Finanzas, el portal de Mutual del
Valle y la sala de espera de guardia. Cerrá filtros que hayan quedado del ensayo.

**Apertura:** «Les voy a mostrar tres cosas que normalmente viven en tres sistemas
distintos: la atención, lo que cuesta y quién la paga. Y por qué tenerlas juntas
cambia las preguntas que pueden responder.»

---

## 1. La operación, primero · 8 minutos

Entrá con `guardia.adm@hospital.gob.ar` en **Hospital Central**.

1. **Filas**: ~25 personas esperando, los urgentes adelante. «Esto no es una lista
   de espera, es el orden clínico: el triage lo reordena.»
2. Abrí la **pantalla pública de sala de espera**:
   <http://localhost:8082/pantalla/lcH0m9kn5xlKogjL> — para el televisor de la
   sala, sin login. Las otras dos:
   [traumatología](http://localhost:8082/pantalla/_3j9MXW2ONUF2fj0) ·
   [cardiología](http://localhost:8082/pantalla/PsRTbCe7CUOBFuMg).
3. Con `guardia.enf@` mostrá el **triage**, y con `guardia.med@` la **conducta
   médica**: alta, internación, observación o derivación.
4. **Internación**: 28 camas con sus estados reales, incluida una en higiene y una
   bloqueada.
5. **Red**: 14 traslados entre Villa Real y Hospital Central, con 3 rechazados y 4
   esperando respuesta.

**Qué decir:** «Nada de esto está cableado. El circuito lo dibuja la institución
en el editor de flujos, y cambiarlo no requiere programar.»

Si te lo piden, mostrá el **editor de flujos** con `config.central@` — pero no te
quedes ahí: es lo que más impresiona y lo que menos se usa en el día a día.

---

## 2. Que el registro no se pueda falsear · 4 minutos

Con `guardia.med@`, abrí una **historia clínica**.

Cada entrada firmada queda **sellada y encadenada** con la anterior. Cambiar una
entrada vieja rompe la cadena y el sistema lo detecta. No es una bitácora que se
puede editar: es evidencia.

En **Accesos** (con `auditor@salud.local`) mostrá que cada consulta a una historia
queda registrada: quién, cuándo, a qué paciente.

**Qué decir:** «La pregunta de auditoría no es sólo “¿quién modificó esto?”, es
“¿quién lo *miró*?”. Las dos tienen respuesta acá.»

> Dato real que conviene tener a mano: intentamos mover atenciones de una fecha a
> otra al preparar este entorno y la base lo rechazó, porque habría dejado dos
> entradas encadenadas al mismo sello. La integridad no es una promesa del
> folleto; nos frenó a nosotros.

---

## 3. Dos hospitales, una plataforma · 3 minutos

Entrá con `plataforma@salud.local`. El **Directorio** muestra los tres efectores.

Cada uno tiene su estructura, sus flujos, sus usuarios y sus finanzas. La
plataforma da de alta efectores y redes; **no** opera adentro de ellos.

**Qué decir:** «Los Aromos tiene un año de gestión económica cargada. Hospital
Central tiene la operación clínica andando y las finanzas todavía sin configurar.
Es exactamente lo que pasa cuando se despliega en una provincia: conviven, y cada
uno avanza a su ritmo.»

---

## 4. Finanzas: cuatro preguntas que no son la misma · 12 minutos

Entrá con **`elena.rivas@losaromos.test`** en **Hospital General Los Aromos**.
Abrí [Finanzas · septiembre](http://localhost:8082/finanzas?mes=2026-09&tab=resumen),
**Todas las áreas e institucional**.

Poné esta tabla arriba de todo el bloque:

| Lo que mostramos | Qué significa | Qué **no** significa |
|---|---|---|
| Gasto aprobado | Gasto registrado más ajustes aprobados | Que ya esté pagado |
| Costo de atención | Componentes configurados + parte de gastos compartidos | Precio que paga el paciente |
| Arancel y cuenta | Obligación de pagar o cobrar | Dinero ya movido |
| Pago o cobro | Movimiento aprobado, con fecha efectiva | Saldo bancario ni rentabilidad |

### A. El resumen

**Gastos aprobados $750.000**, más **$45.000 por aprobar**, **$750.000
distribuidos** y **$0 sin distribuir**.

«Distribuido más sin distribuir explican el aprobado. El reparto **no agrega** un
gasto: divide uno que ya está.»

Tocá una barra: te lleva a los gastos que explican el número. Todo número es
navegable hasta su origen.

### B. Un año de evolución

**Evolución mensual → 12 meses.** Octubre 2025 a septiembre 2026, con
estacionalidad de electricidad, escalones de contrato en limpieza e
intervenciones irregulares de mantenimiento.

«Septiembre está abierto: que baje no demuestra ahorro. Los puntos provisionales
también pueden significar que falta cargar o aprobar. Y comparamos pesos
corrientes, sin ajustar por inflación.»

**Ese último renglón vende más que el gráfico.** Un sistema que te avisa que el
número todavía no es comparable es un sistema en el que se puede confiar.

### C. Un gasto y su historia

**Gastos registrados → Clínica médica →** gasto **#100**, electricidad de
septiembre: **$120.000 aprobados** y un ajuste de **−$10.000 pendiente de
aprobación**.

El importe vigente sigue siendo $120.000. «La corrección existe, está registrada,
tiene motivo y autor, y **todavía no cambió nada**. No se edita el original.»

### D. El costo de una atención concreta

**Costos por atención → Cardiología → caso 167** (Clara Benítez, 10/09). Abrí
**Ver composición**:

| | |
|---|---:|
| Componentes directos (profesional $22.000 + insumos $1.500) | **$23.500** |
| Gastos compartidos atribuidos (electricidad, limpieza, mantenimiento) | **$92.500** |

«El costo compartido no es un prorrateo inventado en una planilla: cada peso sale
de un gasto concreto, y desde acá se llega a la factura que lo originó.»

Mostrá el contraste con el **caso 170** (Beatriz Correa, imágenes): tiene un
componente **sin valor** y el responsable del cobro **sin definir**. Aparecen como
**pendientes**, no como cero.

«Cuando falta información, lo dice. No completa el hueco con un cero, que es lo
que hace una planilla y es como se toman decisiones equivocadas.»

### E. Deber no es haber pagado

**Pagos y cobros → septiembre.** Cuenta **#266** (electricidad, Cooperativa
Eléctrica del Bosque, del gasto #100):

| | |
|---|---:|
| Importe de la cuenta | $120.000 |
| Pagado confirmado | $60.000 |
| Pago **por aprobar** | $20.000 |
| Pendiente confirmado | $60.000 |
| Disponible para registrar otro pago | $40.000 |

«Debemos $60.000. Hay $20.000 cargados esperando aprobación: no los damos por
pagados, pero los reservamos para que nadie los cargue dos veces. Por eso puedo
registrar otros $40.000 y no $60.000.»

**Las dos fechas.** Cambiá el mes económico a agosto: la cuenta **#247** es de
agosto y tiene un pago hecho en **septiembre**. «Una cosa es a qué mes corresponde
el gasto; otra, cuándo salió la plata. Casi ningún sistema chico distingue las dos,
y es la diferencia entre cerrar un mes y no poder cerrarlo.»

---

## 5. Financiadores: quién paga cada parte · 12 minutos

El bloque que más preguntas genera, porque es donde se pierde plata de verdad.

### A. Lo mismo, con y sin obra social

**Finanzas → Costos por atención → Consultorios externos**, septiembre.

| Paciente | Cobertura | Paga el financiador | Paga la persona |
|---|---|---:|---:|
| Susana Barrios (12/09) | ninguna, es particular | $0 | **$28.000** |
| Rosa Maidana (03/09) | Mutual del Valle, 80% | $20.800 | **$5.200** |
| Fabián Leguizamón (04/09) | Obra Social Provincial, 70% | $19.600 | **$8.400** |

«Misma prestación, tres importes distintos para la persona. La diferencia no la
calcula nadie a mano ni se negocia en el mostrador: sale del convenio.»

Mostrá **por qué** Rosa paga menos que el 20% de $28.000: con Mutual del Valle hay
un **arancel de convenio de $26.000**, no el arancel general. El porcentaje se
aplica sobre lo acordado.

### B. El portal de la obra social

Ventana privada, `admin@mutualdelvalle.test`. Es **otra organización entrando al
mismo sistema**, no una exportación por correo.

- **Cobertura**: 80% en consultas con cupo de 6 al año; 70% en radiografía con
  cupo de 2 y **autorización previa**.
- **Padrón**: 7 afiliados. Uno **dado de baja** y otro **dado de baja y
  reactivado**, con motivo y fecha. «La afiliación es una identidad: cambiarle el
  número o el plan no le reinicia el cupo.»
- **Consumos externos**: prestaciones usadas en **otro** prestador. Gastan cupo.
- **Actividad en hospitales**: **12 registros, $211.700 asignados**, con filtros y
  descarga a CSV.

**Qué decir:** «La obra social ve actividad administrativa, no historia clínica. Y
cada consulta que hace queda en el registro de accesos del hospital. El acceso es
real, y es acotado.»

### C. Lo que no cubre no se convierte solo en deuda

Volvé a Elena, **Finanzas → Pagos y cobros**.

De las 20 atenciones con cobertura: **13 resueltas**, **6 pendientes** (las de
septiembre) y **1 esperando autorización** del financiador.

«Pendiente quiere decir que **nadie decidió todavía** quién se hace cargo. El
sistema no le inventa una deuda al paciente para cuadrar un número.»

Y mostrá el caso de Rosa Maidana del **04/08**: su saldo de $5.200 lo **asumió el
hospital**, con motivo registrado. Sólo existe la cuenta de la mutual; a Rosa no
se le generó ninguna.

«Resolver no quiere decir cobrarle a la persona. Puede ser que el hospital lo
absorba, y eso queda escrito con quién lo decidió y por qué.»

### D. Evaluar antes de hacer la prestación

Con `irene.bustos@losaromos.test`, abrí el **caso 195** (Gustavo Ramallo,
radiografía). **Evaluar la prestación**: aparece **sin cupo**, porque tiene dos
radiografías hechas en otro prestador.

Compará con el **caso 194** (Ernesto Bogado), que sí tiene cupo y ya tiene el
copago **aceptado** antes de la práctica.

«Consultar no crea deuda. Se le puede decir a la persona cuánto va a pagar
**antes**, no cuando llega la factura. Esa es la conversación que hoy no se puede
tener.»

### E. Lo que el financiador todavía debe

Todo septiembre está **sin liquidar**: julio y agosto se cobraron ($361.800),
septiembre no. «Esta es la plata que el hospital ya trabajó y todavía no cobró,
separada por obra social. Hoy, en la mayoría de los hospitales, este número no
existe o está en una planilla de alguien.»

---

## 6. Cierre · 5 minutos

Volvé al [Resumen de Finanzas](http://localhost:8082/finanzas?mes=2026-09&tab=resumen).

**Cierre:** «Pueden explicar cada gasto y sus pendientes, saber qué cuesta una
atención y de dónde sale cada peso, saber quién debe pagar cada parte y cuánto
falta cobrar, con historia completa y permisos por área. Y donde falta
información, el sistema lo muestra en vez de inventar una cifra.»

Preguntá: **«¿Cuál de estas preguntas no pueden responder hoy?»** — y callate.

---

## Preguntas que van a hacer

| Pregunta | Respuesta honesta |
|---|---|
| ¿Factura? | No. No emite facturación fiscal ni concilia bancos. Registra obligaciones y movimientos; la facturación es otro sistema. |
| ¿Se integra con lo que tenemos? | Expone API documentada y una fachada **FHIR** (`Patient`, `Encounter`, `Organization`). |
| ¿Firma digital? | La firma por rol está y sella la historia. La firma criptográfica con certificado (Ley 25.506) tiene el enganche, **no** el certificador. |
| ¿La obra social ve la historia clínica? | No. Ve actividad administrativa, y cada consulta suya queda auditada. |
| ¿Cuánto tarda configurarlo? | Depende de cuántas áreas y convenios. El circuito completo de una institución está en la [guía de configuración](guia-configuracion-desde-cero.md). |
| ¿Anda con un solo hospital? | Sí. Lo multicentro se agrega después; no es un requisito de arranque. |
| ¿Y si se cae? | Respaldo diario que **se restaura para verificarlo** en cada corrida. Un respaldo que nunca se restauró no es un respaldo. |

---

## Lo que conviene no mostrar

- **Rol `reportes`** (`reportes@salud.local`): la capacidad existe, las pantallas
  de indicadores agregados no. Entrar con ese usuario muestra una app casi vacía.
- **Hospital Central no tiene finanzas configuradas.** Si entrás a Finanzas con un
  usuario de Hospital Central vas a ver 427 atenciones con costeo pendiente y cero
  gastos. Úsalo **sólo** si vos elegiste el argumento del bloque 3; si aparece de
  sorpresa, parece un error.
- **El admin de Django** (`/admin/`) no funciona por http en este entorno.
- **Espera por tiempo**: se reactiva sola cada 2 minutos. Si la querés mostrar en
  vivo, hay que esperar ese ciclo.

---

## Antes de presentar

Comprobá que podés explicar estas cuatro sin mirar el guion. Si alguna no te sale,
esa es justamente la que te van a preguntar:

1. Por qué un pago pendiente **no** baja todavía la deuda.
2. Por qué el reparto **no** se suma al gasto original.
3. Por qué Rosa paga $5.200 y no $5.600 (el arancel de convenio, no el general).
4. Por qué un saldo «pendiente» **no** es una deuda del paciente.

Si algún número no coincide con este documento, revisá **mes, área, institución y
filtros** antes de pensar que el entorno está mal. Y si alguien registró o aprobó
algo durante un ensayo, dejá de presentar las cifras de acá como estado inicial:
[rehacé el entorno](README.md#rehacer-el-entorno-demo-desde-cero).

---

## Verificación de este guion

Todas las cifras se comprobaron contra la base el 17/09/2026, después de sembrar.
Las de Los Aromos (§4) coinciden exactamente con
[`guia-los-aromos.md`](../funcionalidades/finanzas-costos/guia-los-aromos.md), que
sigue siendo válida: el escenario de financiadores se montó en un área aparte
justamente para no alterarlas. Las de financiadores (§5) son nuevas y salen de
`seed_financiadores`, verificadas también por el portal y la API.
