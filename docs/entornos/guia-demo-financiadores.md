# Financiadores en 8082 — qué tocar y dónde

Recorrido de **20 minutos** sobre <http://localhost:8082>, Hospital General Los Aromos.
Todo verificado contra la app el **18/09/2026**.

**Hacelo en este orden.** Los pasos 3 y 4 consumen los casos preparados: una vez
que los usás, no se repiten sin volver a sembrar.

## Usuarios

| Para | Usuario | Contraseña |
|---|---|---|
| Administrativa (admisión) | `paula.benitez@losaromos.test` | `LosAromos2026!` |
| Médica de Consultorios externos | `irene.bustos@losaromos.test` | `Financiadores2026!` |
| Administración y finanzas | `elena.rivas@losaromos.test` | `LosAromos2026!` |
| Portal de la obra social | `admin@mutualdelvalle.test` | `Financiadores2026!` |

Para cambiar de usuario usá **ventana privada**. Dos pestañas normales comparten sesión.

---

# 1. Dónde está configurado · 5 min

## 1.1 Lado obra social — ventana privada, `admin@mutualdelvalle.test`

Entrás y caés directo en el portal. Menú lateral propio.

| Tocá | Vas a ver |
|---|---|
| **Convenios** | Hospital General Los Aromos · 48 horas · **Activo** · Propuesto por Financiador · Aceptado 15/06/2026. Botones **Plazo de autorización** y **Cerrar convenio** |
| **Cobertura** | 2 reglas: *Consulta ambulatoria externa* **80%**, cupo **6 por año**, autorización *No requerida*; *Radiografía ambulatoria de tórax* **70%**, cupo **2 por año**, autorización **Requerida**. Botón **Nueva regla de cobertura** |
| **Padrón** | 7 afiliados, `MV00001` a `MV00007`. Botones **Registrar afiliación**, **Importar Excel**, y por fila **Corregir identidad** / **Finalizar afiliación** |
| **Aranceles** | CEX: general **ARS 28.000**, aplicable **ARS 26.000**, origen *Acordado con el financiador*. RXE: general **ARS 35.000**, aplicable **ARS 35.000**, origen *General del hospital* |

**El renglón que hay que señalar:** en Aranceles, la consulta tiene arancel general
28.000 pero aplicable 26.000. Ese 26.000 es el precio acordado, y el 80% se calcula
sobre él. Por eso el paciente paga 5.200 y no 5.600.

## 1.2 Lado hospital — `elena.rivas@losaromos.test`

Menú lateral → **Coberturas y copagos** → pestaña **Configuración**. Cuatro bloques:

1. **Circuito de cobertura** — casilla *Habilitar cobertura y distribución de cobros
   para este hospital* (tildada) + *Considerar antigua una reserva después de (días)*.
   Botón **Guardar configuración**.
2. **Vincular prestaciones al catálogo común** — dos desplegables (*Prestación del
   hospital* / *Prestación del catálogo común*) y botón **Guardar vínculo**.
3. **Convenios con financiadores** — *Financiador para el convenio* + **Proponer
   convenio**. Abajo, cada convenio con **Aceptar convenio** / **Cerrar convenio**.
4. **Aranceles** — *Excepción acordada*: convenio + prestación + importe + vigencia,
   botón **Guardar arancel acordado**.

**No toques nada acá.** Es para mostrar dónde vive la configuración.

---

# 2. El uso real: la administrativa en una atención · 6 min

Ventana privada, `paula.benitez@losaromos.test`.

**Cómo llegar a los casos, sin tipear URL:** menú lateral → **Casos** → en el
desplegable **Área** elegí **Consultorios externos**. Quedan los tres del
recorrido: **#0194**, **#0195** y **#0196**. Se abren haciendo clic en la fila.

## 2.1 Caso con cobertura — Andrea Paniagua

**Casos** → área *Consultorios externos* → fila **#0196**.

Bajá hasta el panel **Cobertura del caso**. Ya dice *Verificada · Afiliación
verificada contra el padrón al admitir*, con fecha y autor.

En **Prestaciones del paso actual** → apretá **«Consultar cobertura»**.

Aparece:

```
Cobertura según plan y cupo disponible
18/09/2026 · 1 unidad. 1 cubiertas al 70% · Cupo anual: 4; disponibles: 3.

Importe total              ARS 28.000,00
A cargo del financiador    ARS 19.600,00
A cargo del paciente       ARS  8.400,00
```

Debajo hay una casilla: *«El paciente aceptó expresamente ARS 8.400,00 por Consulta
ambulatoria externa (1 unidad)»*, y el botón **«Confirmar reserva de cobertura»**.

**Lo que hay que decir mientras lo mostrás:** «Consultar no ocupa cupo y no crea
deuda. Recién al confirmar se reserva.»

**Para el recorrido, tildá la casilla y apretá «Confirmar reserva de cobertura».**
Eso deja registrado que la persona aceptó pagar sus 8.400 **antes** de la práctica.

## 2.2 Caso sin cupo — Gustavo Ramallo

Volvé a **Casos** → fila **#0195** → **«Consultar cobertura»**.

```
No cubierta — cupo agotado
18/09/2026 · 1 unidad. 0 cubiertas al 70% · Cupo anual: 2; disponibles: 0.

Importe total              ARS 35.000,00
A cargo del financiador    ARS      0,00
A cargo del paciente       ARS 35.000,00
```

Fijate que acá aparece un botón que en el caso anterior no estaba:
**«Solicitar autorización»** (en el panel *Autorizaciones de este caso*), porque la
regla de radiografía la exige.

**El punto de venta:** el cupo se agotó con **dos radiografías hechas en otro
prestador**, cargadas por la obra social en *Consumos externos*. El hospital no
tiene forma de saberlo por su cuenta, y sin esto le diría al paciente que estaba
cubierto. Se lo podés decir **antes** de la práctica, no cuando llega la factura.

**No confirmes la reserva acá.** Dejalo como está.

## 2.3 Caso ya aceptado — Ernesto Bogado

Volvé a **Casos** → fila **#0194**.

En *Prestaciones del paso actual* dice **«Tiene una reserva abierta»** con el botón
**«Revisar importe»**, y abajo:

```
Coberturas registradas · 1
Consulta ambulatoria externa · Reservada · 15/09/2026 · 1 unidad
Financiador: ARS 20.800,00 · Paciente: ARS 5.200,00
Aceptación registrada: ARS 5.200,00 · 15/09/2026 · 09:00
```

Este es el que vas a completar en el paso siguiente.

---

# 3. El médico completa la atención · 2 min

Ventana privada, `irene.bustos@losaromos.test`.

Entra directo a **Mi trabajo** con sus tres casos listados. Apretá el de
**Ernesto Bogado**.

Bajá al bloque **ATENCIÓN** y completá:

1. **Título de la atención** → `Consulta ambulatoria`
2. **Evolución / observaciones** → cualquier texto
3. Tildá **«Firmar la entrada»**
4. Apretá **«Registrar atención y avanzar»**

**Lo que hay que decir:** «Al profesional no se le preguntó nada económico. Firmó
la atención y listo: el reparto entre obra social y paciente ya estaba resuelto en
admisión.»

---

# 4. Cómo se ve en Finanzas y costos · 5 min

Volvé a la ventana de `elena.rivas@losaromos.test`.

## 4.1 La cuenta por cobrar de la obra social

Barra del navegador:
**`localhost:8082/finanzas?mes=2026-09&tab=dinero&area=4`**

(`area=4` es Consultorios externos; también podés elegirla en el desplegable **Área**.)

Antes de tu atención había **5 cuentas por ARS 101.600** — 3 de Mutual del Valle
($20.800 c/u) y 2 de Obra Social Provincial ($19.600 c/u). Después de completar a
Ernesto son **6**, con la suya de **ARS 20.800** a nombre de *Mutual del Valle*.

Todas muestran **cobrado ARS 0,00** y el total como pendiente.

**El renglón de venta:** «Esto es lo que las obras sociales le deben al hospital
por septiembre, separado por obra social. Hoy, en la mayoría de los hospitales,
este número no existe o vive en la planilla de alguien.»

Fijate en la columna **A quién / de quién**: dice *Mutual del Valle ·
financiador:1*, no el nombre del paciente. La deuda es de la obra social.

## 4.2 Arancel y costo son dos configuraciones distintas

Cambiá a la pestaña **Costos por atención**, misma área y mes.

Las atenciones de Consultorios externos aparecen **sin costo directo y con un
pendiente**: a este servicio se le configuró el *cobro* (el arancel) pero todavía
no el *costo* (los componentes). El sistema lo muestra como pendiente en vez de
poner cero.

**Usalo a favor, no lo escondas:** «Cobrar y costear se configuran por separado.
Acá todavía no cargamos los componentes de costo de este servicio, y el sistema lo
dice en vez de inventar un cero.»

Y después mostrá un servicio que **sí** lo tiene configurado. Cambiá el **Área** a
**Cardiología** y buscá **167** en *Número de caso* (Clara Benítez, 10/09). Abrí
**«Ver composición»**:

| | |
|---|---:|
| Componentes directos (profesional 22.000 + insumos 1.500) | **ARS 23.500** |
| Gastos compartidos atribuidos (electricidad, limpieza, mantenimiento) | **ARS 92.500** |

Su arancel es **ARS 45.000**. Costo y arancel no tienen por qué parecerse, y el
sistema nunca deriva uno del otro.

## 4.3 El saldo del paciente no es una cuenta todavía

Menú lateral → **Coberturas y copagos** → pestaña **Reservas y saldos**.

Vas a ver la lista completa con su estado (*Realizada*, *Resuelta*, *Pendiente de
resolución administrativa*) y, en las que faltan decidir, el botón
**«Resolver saldo»**. Hoy hay **7 esperando decisión**.

Apretá **«Resolver saldo»** en cualquiera. Se abre *Resolver saldo administrativo*:

```
Saldo completo del paciente: ARS 5.200,00
Decisión:  ▾ Seleccioná una decisión
             El hospital asume el saldo
             El hospital rechaza asumirlo: continúa pendiente
             El paciente acepta pagar el saldo
             El financiador acepta pagar el saldo
Motivo:    [                    ]
                        [Cancelar] [Registrar decisión]
```

**Apretá «Cancelar».** No hace falta ejecutarlo para mostrar el punto:

> «Lo que la obra social no cubre **no se convierte solo en deuda del paciente**.
> Queda esperando que alguien decida, con motivo y autor. Y una de las opciones es
> que lo absorba el hospital.»

Filtros arriba: el desplegable de estado tiene *Todos · Autorización pendiente ·
Reservada · Realizada · Liberada · Pendiente de resolución administrativa ·
Resuelta · Arancel pendiente*.

---

# 5. Lo que ve la obra social · 2 min

Volvé a la ventana de `admin@mutualdelvalle.test` → **Actividad en hospitales**.

Abre en el **mes actual**: **5 registros**, **ARS 62.400** de importe original
asignado al financiador, 1 reservada y 4 realizadas. Apretá **«Limpiar filtros»**
para ver todo el período (12 registros, ARS 211.700).

Botón **«Exportar CSV»** — incluye todas las páginas con los filtros aplicados.

**Cerrá con esto:** «La obra social entra al mismo sistema y ve su actividad
administrativa. No ve la historia clínica. Y cada consulta que hace queda en el
registro de accesos del hospital.»

Si te lo piden, mostralo: ventana de Elena → menú lateral → **Registro de accesos**.

---

# Guion corto (5 minutos)

Si tenés poco tiempo, hacé solo esto:

1. Con Paula: **Casos** → área *Consultorios externos* → **#0196** →
   **Consultar cobertura** → los tres importes (28.000 / 19.600 / 8.400).
2. **Casos** → **#0195** → **Consultar cobertura** → *cupo agotado*, el paciente
   paga los 35.000 completos.
3. `localhost:8082/finanzas?mes=2026-09&tab=dinero&area=4` → las cuentas por cobrar
   a las obras sociales, todas sin cobrar.

Tres pantallas: lo que cubre, lo que no, y lo que falta cobrar.

---

# Si algo no coincide

| Síntoma | Causa |
|---|---|
| El panel de cobertura no aparece en el caso | Estás en un caso de otra área. Filtrá **Casos** por *Consultorios externos*: son el #0194, #0195 y #0196 |
| «Consultar cobertura» no está | El caso no tiene afiliación registrada, o el paso actual no tiene prestación vinculada al catálogo común |
| Los importes no son los de esta guía | Alguien ya confirmó la reserva o resolvió el saldo. [Rehacé el entorno](README.md#rehacer-el-entorno-demo-desde-cero) |
| «Actividad en hospitales» vacía | Está filtrando por mes actual. Apretá **Limpiar filtros** |
| La tabla de Pagos y cobros está vacía | Revisá **Mes económico** (septiembre 2026) y **Área** (Consultorios externos) |

# Lo que no hace, por si lo preguntan

No emite factura fiscal, no concilia bancos, no ejecuta transferencias, y la obra
social no accede a la historia clínica.
