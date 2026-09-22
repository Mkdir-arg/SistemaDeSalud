# Configurar el sistema desde cero — qué apretar y dónde

Entorno **vacío**: <http://localhost:8081> · `admin@vacio.local` / `Configurar2026!`

Cada paso dice **dónde estás**, **qué botón apretás** y **cómo comprobás que salió**.
Todos los nombres de botones se tomaron de la app corriendo el 18/09/2026.

> **Dos reglas de oro.** El botón de acción está casi siempre **arriba a la
> derecha**, al lado del título. Y cada paso **se guarda solo**: no hay un
> «guardar todo» al final.

---

## Dónde estás hoy (Hospital Lepera)

| Bloque | Estado |
|---|---|
| Institución, 2 áreas, 6 usuarios | ✅ |
| 2 flujos publicados **con nodo de Atención** | ✅ |
| Prestaciones «Enfermeria» e «Imagen», 3 componentes con valor | ✅ |
| 3 conceptos de gasto · 2 gastos · 3 reglas de reparto | ✅ |
| 2 políticas de cobro | ✅ |
| 2 atenciones completadas, con costo ($500 y $1.700) | ✅ |
| Captura de cobros de esas 2 atenciones | ❌ falló: falta el vínculo al catálogo común |
| Reparto de los $100.000 | ❌ el gasto es institucional y las reglas son por área |
| Financiador OSDE con 3 planes, módulo de cobertura activado | ✅ |
| Catálogo común, reglas de cobertura, convenio aceptado, padrón | ❌ |

**Tus dos pendientes, en orden:** el bloque **6.4** (regla institucional, para que
el reparto reparta) y el bloque **10.1** (catálogo común, para recuperar los
cobros). Los bloques 1 a 5 quedan como referencia para la próxima institución.

---

## Lo primero: por qué el desplegable estaba vacío

No estaba roto.

**En «Configurar otra atención»**, el desplegable *Atención del flujo publicado*
sólo lista atenciones que **todavía no tienen prestación**. Vos ya configuraste
las dos que existen, así que no queda ninguna y el desplegable aparece vacío —
sin decirte por qué. Para que aparezca algo, primero tiene que existir **otro
nodo de Atención** en un flujo publicado.

**En la tabla de abajo** («Sin atenciones financieras visibles») es otra cosa: esa
tabla no lista lo que configuraste, lista **atenciones ya ocurridas**. Aparecen
recién cuando alguien completa el nodo de Atención en un caso real.

---

## 1. Crear la institución

**Dónde:** entrás con el superusuario y caés en el **Directorio**.

1. Apretá **«Nueva institución»** (arriba a la derecha).
2. Completá nombre, tipo y dirección. **«Crear»**.
3. En la fila de la institución, apretá **«Ingresar»**.

**Comprobás:** el encabezado de la izquierda pasa a decir el nombre de la
institución, y abajo aparece **«Volver al directorio»**.

## 2. Áreas

**Dónde:** menú lateral → **Estructura organizativa**.

Creá al menos dos áreas. El área es la unidad de alcance de todo lo demás:
permisos, gastos, repartos y cobertura se otorgan y se calculan **por área**.

## 3. Usuarios

**Dónde:** menú lateral → **Administración**.

1. **«Crear usuario»** (arriba a la derecha).
2. Email, nombre, contraseña.
3. En **Membresías**, elegí institución y rol, y apretá **«+ Agregar»**.

**Ojo:** un usuario puede tener **varias membresías** (por ejemplo Administrativo
y Médico). Eso importa en el bloque 7.

## 4. Formularios

**Dónde:** menú lateral → **Formularios**. Creá uno mínimo para la atención.

## 5. Flujos — acá está la trampa

**Dónde:** menú lateral → **Flujos** → abrí el flujo → editor.

El circuito mínimo es:

```
Inicio  →  Formulario  →  Atención  →  Cierre
```

**«Formulario» y «Atención» son nodos distintos y no se reemplazan.**

| Nodo | Qué hace |
|---|---|
| **Formulario** | Captura datos en un formulario |
| **Atención** | Registra la atención profesional, la firma y la **asienta sellada en la historia clínica** |

**Toda la cadena financiera cuelga del nodo «Atención».** La prestación se ata a
él, y completarlo es lo que crea el registro económico. Un flujo sin nodo de
Atención nunca va a generar un costo, y nada te lo avisa.

Cuando termines: **publicá la versión**. Un borrador no admite casos.

> **Republicar tiene costo.** La prestación se ata a un nodo **de una versión
> concreta**. Cada versión publicada crea nodos nuevos, así que **la
> configuración de costos no se hereda**: al publicar una versión nueva hay que
> volver a crear la prestación sobre su nodo. Es la causa típica de «configuré
> todo y las atenciones siguen sin costo».

> **Los casos abiertos se quedan en su versión.** Tu caso #1 corre sobre la v1,
> que no tiene nodo de Atención: por más que publiques la v2, **ese caso nunca va
> a llegar a una atención**. Para probar hay que abrir un caso nuevo.

## 6. Finanzas

**Dónde:** menú lateral → **Finanzas y costos**. Arriba tenés los filtros **Mes
económico** y **Área**, y siete pestañas:

`Resumen · Gastos registrados · Gastos mensuales · Repartos · Costos por atención · Pagos y cobros · Reportes`

**Los botones cambian según la pestaña.** Esto es lo que hay en cada una:

| Pestaña | Botones de acción |
|---|---|
| Gastos registrados | **Registrar gasto** · **Agregar gasto mensual** · **Nuevo concepto** |
| Gastos mensuales | **Agregar gasto mensual** · **Nuevo concepto** |
| Repartos | **Configurar repartos** · **Nuevo concepto** · **Ver historial** |
| Costos por atención | **Configurar costos por atención** |
| Pagos y cobros | **Configurar cobros por atención** · **Ver movimientos del período** |

### 6.1 Conceptos y gastos

1. Pestaña **Gastos registrados** → **«Nuevo concepto»**. Electricidad, limpieza,
   lo que sea. Crear un concepto no crea ninguna factura.
2. **«Registrar gasto»**: área, concepto, importe, mes.

En la fila del gasto tenés **Detalle**, **Ajustar**, **Crear cuenta por pagar** y,
si tenés permiso, **Aprobar** / **Rechazar** / **Reemplazar**.

### 6.2 Gastos mensuales

**«Agregar gasto mensual»**: área + concepto + vigencia + monto de referencia
(opcional). Es una lista de comprobación de lo que **se espera** cargar; sirve
para detectar lo que falta aunque nadie haya cargado nada.

La columna **Diferencia** es *referencia menos aprobado*. Que dé positivo no
significa ahorro: puede significar que falta una factura.

### 6.3 Costos por atención

**Dónde:** pestaña **Costos por atención** → **«Configurar costos por atención»**.

La pantalla tiene tres niveles, en este orden:

1. **Atención configurada** — desplegable arriba. Si todavía no creaste ninguna,
   apretá **«Configurar otra atención»**, elegí el nodo en *Atención del flujo
   publicado*, poné el nombre y **«Guardar este paso»**.
2. **Componentes de <atención>** — apretá **«Agregar componente»**. Uno por cada
   parte del costo directo (materiales, uso de la máquina, trabajo profesional).
3. **Valores y vigencias** — hacé clic en el **nombre del componente** y apretá
   **«Agregar intervalo de valor»**. Importe + desde cuándo.

Los valores **no se editan**: para cambiarlos usás **«Cambiar valor desde otra
fecha»**, que conserva el anterior. Por eso en diciembre podés explicar por qué
una atención de marzo costó lo que costó.

### 6.4 Repartos

Pestaña **Repartos** → **«Configurar repartos»**.

La **regla de reparto** dice qué concepto se distribuye, en qué **ámbito** y desde
cuándo. Desde el 18/09/2026 la actividad del área se considera válida de forma
implícita: ya **no** hace falta declarar la «cobertura de actividad verificada»
para que reparta. Sólo una **excepción explícita** puede deshabilitar un área
desde un mes.

**El ámbito de la regla tiene que coincidir con el del gasto.** Es el error más
fácil de cometer:

| Gasto | Regla que lo reparte |
|---|---|
| Cargado **con área** | Regla de **esa área** |
| Cargado **institucional** (sin área) | Regla **institucional** |

Un gasto institucional con reglas por área **no se reparte y nada te lo avisa**:
queda entero en *Sin distribuir*. Ojo que los formularios de Finanzas ahora
arrancan con el campo Área en **institucional**, así que es fácil cargar un gasto
institucional sin darte cuenta.

Una regla institucional reparte entre las atenciones elegibles de **todas** las
áreas de la institución, en proporción a la cantidad de cada una en el período.

El reparto **no agrega** un gasto: divide uno que ya está aprobado. Por eso
*distribuido + sin distribuir* explican el aprobado.

### 6.5 Cobros

Pestaña **Pagos y cobros** → **«Configurar cobros por atención»**. Por prestación:

- **¿Esta atención se cobra?** → *No: atención sin cobro* / *Sí: generar cuenta por cobrar*
- **Arancel en ARS** — no se toma del costo interno. Son cosas distintas.

**Quién debe pagar no se configura acá.** El pagador depende del paciente, no de la
prestación, así que se define **por atención** en **Cobros por completar**, o lo
determina la cobertura del paciente. El paciente **no** queda como pagador por
defecto.

Hasta que falte el arancel o el responsable, la atención cae en **Cobros por
completar**: no crea deuda ni le pregunta nada al profesional.

## 7. Permisos financieros

**Dónde:** **Administración** → clic en la **fila del usuario** → se abre *Editar
usuario* → abajo, **«Permisos financieros»** (clic para desplegar).

**Primero elegí «Membresía de los permisos financieros».** Si la persona es
Administrativo **y** Médico, los permisos se cuelgan de **una** de las dos. Es un
paso fácil de saltear, y si elegís la membresía equivocada el permiso no aplica
donde esperás.

Las casillas, con el nombre exacto que usa la app:

| Grupo | Casillas |
|---|---|
| Costos | Ver costos · Configurar componentes · Corregir costos · Aprobar ajustes de costos |
| Gastos | Ver gastos · Registrar gastos · Aprobar gastos · Corregir gastos · Configurar gastos mensuales |
| Reparto | Configurar repartos |
| Dinero | Ver pagos y cobros · Registrar pagos y cobros · Aprobar pagos, cobros y sus correcciones · Registrar devoluciones y reducciones |
| Cobros | Configurar cobros por atención · Registrar aceptación de copagos por prestación · Resolver saldos de cobertura con motivo |
| Auditoría | Auditar accesos financieros |

Terminá con **«Guardar permisos financieros»**. Es un botón **aparte** de
«Guardar datos personales»: guardar uno no guarda el otro.

**El rol no da permisos financieros** — con una excepción: desde el 18/09/2026 el
rol **Admin de institución** hereda **todas** las acciones financieras, en todas
las áreas e incluyendo información sensible. Aparecen como **Por rol** y no se
desmarcan desde estas casillas. Para el resto de los roles hay que concederlas una
por una: contaduría puede operar finanzas sin ver historias clínicas, y un jefe
médico puede no ver ningún importe.

---

## 8. Ver tu primera atención costeada ← **empezá por acá**

Esto es lo que te falta. Cinco clics.

1. Menú lateral → **Bandeja de tareas**.
2. **«+ Nuevo caso»** (arriba a la derecha).
3. En el modal:
   - **Flujo**: elegí **«Inicio de paciente (v2)»** o **«Inicio de Imagen (v3)»**.
     Fijate que diga **v2/v3**: son las versiones que tienen el nodo de Atención.
   - **Paciente**: *Paciente existente* → Juan Ignacio Portilla. (O *Nuevo
     paciente*.)
   - **«Crear e iniciar»**.
4. Se abre el caso. Vas a ver **PASO ACTUAL: Formulario**. Completá y apretá
   **«Completar y avanzar»**.
5. Ahora **PASO ACTUAL: Atención**. Completá el texto, marcá que se firma, y
   **«Completar y avanzar»** otra vez.

**Comprobás:** andá a **Finanzas y costos → Costos por atención**. Con lo que
tenés configurado hoy, el resultado tiene que ser **exactamente** esto:

| Si elegís el flujo | Costo directo conocido | En «Pagos y cobros» |
|---|---:|---|
| **Inicio de Imagen (v3)** → atención «Imagen» | **ARS 1.700** (Materiales 700 + Uso de la maquina 1.000) | En **Cobros por completar**: arancel **ARS 20.000** y responsable **sin definir** |
| **Inicio de paciente (v2)** → atención «Enfermeria» | **ARS 500** (Medicamentos) | Nada: su política está en *No se cobra* |

Hacé el de **Imagen**: te muestra las dos mitades de una vez, el costo interno
($1.700) y el arancel ($20.000), que son números que no tienen por qué parecerse.

Como ninguna política define **Quién debe pagar**, esa atención cae en **Cobros
por completar** en vez de generar deuda. Ahí la completás y recién entonces nace la
cuenta. Eso es lo correcto, y es justamente el comportamiento que conviene
entender: el sistema no le adjudica la deuda a nadie por su cuenta.

> Si la tabla sigue vacía, revisá el **Mes económico** del filtro: por defecto
> muestra el mes en curso.

## 9. Que el reparto reparta

Con al menos una atención completada:

1. **Repartos** → **«Configurar repartos»** → creá la regla, con el **mismo
   ámbito que el gasto** (institucional o del área).
2. Esperá hasta 2 minutos (el servicio `costos` procesa en ciclos) o mirá el
   cartel **«Repartos actualizados»** arriba.

**Comprobás:** en **Resumen**, *Distribuido entre atenciones* deja de ser $0. Hoy
tenés $80.000 aprobados y **$80.000 sin distribuir**, justamente porque todavía no
hay atenciones entre las cuales repartir.

---

## 10. Financiadores — lo que te falta

Ya tenés **OSDE** con 3 planes y el módulo activado en el hospital. Faltan cinco
cosas, **en este orden**, porque cada una depende de la anterior.

**Dónde:** menú lateral → **Financiadores**. El portal tiene su propio menú:
`Planes · Cobertura · Aranceles · Padrón · Consumos externos · Autorizaciones ·
Actividad en hospitales · Convenios · Usuarios · Catálogo común`.

### 10.1 Catálogo común ← **el que te va a trabar**

**Catálogo común** → **«Nueva prestación común»**: código, nombre, categoría.

Después hay que **vincular** tu prestación del hospital («Imagen»,
«Enfermeria») con esa prestación común. Sin el vínculo, la prestación existe para
el hospital pero es **invisible** para la cobertura, y en el paso siguiente no vas
a poder elegirla.

> Es el mismo patrón que te pasó con el nodo de Atención: un desplegable vacío
> porque falta el eslabón anterior, sin que nada lo explique.

### 10.2 Reglas de cobertura

**Cobertura** → **«Nueva regla de cobertura»**: plan + prestación común +
porcentaje + cupo (mensual o anual) + si **requiere autorización** + vigente desde.

### 10.3 Activar el convenio

**Convenios** → tu convenio con Hospital Lepera está en **propuesto**. Apretá
**«Aceptar convenio»**.

Mientras esté propuesto, **la cobertura no se aplica**.

### 10.4 Aranceles

**Aranceles** los carga **el hospital**, no el financiador: es el importe acordado
para una prestación. Sin acuerdo se usa el arancel general que pusiste en 6.5.

### 10.5 Padrón y usuarios

- **Padrón** → **«Registrar afiliación»** (o **«Importar Excel»**, que te muestra
  qué filas entran y cuáles se rechazan **antes** de aplicar).
- **Usuarios** → **«Dar acceso»**: el financiador necesita su propia gente.
  Roles: *admin*, *operador*, *auditor*. Hoy tenés **cero** usuarios en OSDE.

### 10.6 Permisos del lado del hospital

Volvé a **Administración → usuario → Permisos financieros** y marcá:

- **Registrar aceptación de copagos por prestación** → para quien admite.
- **Resolver saldos de cobertura con motivo** → para quien decide qué pasa con lo
  que la obra social no cubre.

### Comprobación final

```bash
docker compose -p salud-vacio --env-file .env.vacio \
  -f docker-compose.yml -f docker-compose.vacio.yml \
  exec backend python manage.py verificar_preparacion_financiadores --institucion 1
```

No modifica nada. Devuelve un JSON con lo que falta.

---

## Cuando algo aparece vacío

Casi siempre es el eslabón anterior, no un error.

| Lo que ves | Lo que falta |
|---|---|
| «Atención del flujo publicado» vacío | No hay nodos de Atención **sin prestación**. O no hay ninguno, o ya están todos configurados |
| «Sin atenciones financieras visibles» | Nadie completó un nodo de Atención todavía. O el filtro de **mes** está en otro mes |
| La atención no generó costo | Faltan componentes, o falta un valor **vigente a la fecha de la atención** (no a hoy) |
| Un componente sin importe | Mismo motivo: la vigencia empieza después de la atención |
| El gasto queda «por aprobar» | Quien lo cargó no tiene *Aprobar gastos* en esa área |
| «Sin distribuir» no baja | No hay regla, o **el ámbito de la regla no coincide con el del gasto** (institucional vs. área) |
| La atención cae en «Cobros por completar» | Falta el arancel o falta decir quién paga |
| No puedo elegir prestación en una regla de cobertura | Falta la prestación común y su vínculo (10.1) |
| La cobertura no se evalúa nunca | El convenio sigue en **propuesto** |
| Finanzas no aparece en el menú | Ese usuario no tiene ningún permiso financiero |
| Un permiso no aplica | Se guardó en la **otra membresía** de esa persona |

## Lo que el sistema no hace

- No emite facturación fiscal ni concilia bancos.
- No maneja cajas, anticipos ni sobrepagos.
- No genera cargos retroactivos al cambiar una configuración.
- El financiador **no** ve la historia clínica, y cada consulta suya queda
  auditada.

---

## Qué se verificó

Los bloques 1 a 8 y el 10 se recorrieron con un navegador contra este entorno el
18/09/2026: los nombres de botones, pestañas, campos y desplegables son los que
muestra la app, no una deducción del código. No se guardó ningún cambio en tu
entorno. El bloque 9 (que el reparto reparta) no se pudo comprobar porque
requiere una atención completada, que es justamente lo que falta.
