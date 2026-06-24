# Arquitectura, roles y navegación

## 1. Capas del sistema

```
Plataforma                         ← raíz; super admin
  └── Institución (autocontenida)  ← contexto; todo se filtra por la institución actual
        ├── Estructura organizativa
        │     Institución → Área → Sub-área   (jerarquía FIJA de 3 niveles)
        ├── Definición:  Flujos, Formularios   (pertenecen a un nivel organizativo)
        ├── Ejecución:   Casos, Bandejas, Filas
        └── Registros:   Historia clínica, Legajo profesional
```

**Reglas de la jerarquía organizativa:**
- Exactamente 3 niveles. Una **sub-área NO puede contener otra sub-área** (un área padre no puede a su vez tener padre).
- **Staff explícito por nivel** (sin herencia automática hacia abajo). El responsable del nivel superior supervisa pero no opera por defecto.
- Un **flujo pertenece a un nivel**: institución (transversal), área, o sub-área; un flujo de área puede declararse "del área y sus sub-áreas" (se comparte hacia abajo) o "solo de este nivel".
- Las **derivaciones apuntan a un nivel** (área o sub-área) → el caso cae en la bandeja correcta.
- **Nada se mezcla entre instituciones.**

## 2. Roles y permisos

| Capacidad | Configurador | Administrativo | Admin de institución | Super admin |
|---|---|---|---|---|
| Ver directorio de instituciones / dar de alta instituciones | — | — | — | ✅ |
| Ingresar a cualquier institución | — | — | solo la suya | ✅ |
| Crear / editar / publicar flujos | ✅ | — | ✅ | ✅ |
| Armar formularios y campos | ✅ | — | ✅ | ✅ |
| Definir reglas y estados de un flujo | ✅ | — | ✅ | ✅ |
| Iniciar y ejecutar casos | — | ✅ | ✅ | ✅ |
| Tomar casos de la bandeja de su área | — | ✅ | ✅ | ✅ |
| Operar filas (llamar / atender) | — | ✅ | ✅ | ✅ |
| Derivar y avanzar casos | — | ✅ | ✅ | ✅ |
| Consultar casos y trazabilidad | solo lectura | de su área | toda la institución | todas |
| Leer/escribir historia clínica | — | según credencial/área | ✅ | ✅ |
| Gestionar usuarios, roles y áreas | — | — | ✅ (su institución) | ✅ |

Notas:
- El **Configurador** entra y ve por defecto **Flujos / Formularios**. No ve la bandeja. Su mundo es **diseño**.
- El **Administrativo** entra y ve su **Bandeja**. No ve el diseñador. Su mundo es **ejecución**.
- El **Admin de institución** ve todo lo de su institución + Administración (usuarios, áreas, asignación de flujos por área). Reemplaza al antiguo "administrador del sistema", ahora acotado a una institución.
- El **Super admin** es global: directorio, alta de instituciones y sus admins, e ingresar a cualquiera.
- Un usuario puede tener más de un rol → ve ambos mundos y un selector de contexto.

**Áreas:** cada administrativo pertenece a una o más áreas. Las bandejas "sin asignar" se filtran por su área. Las derivaciones apuntan a un área/sub-área y por eso el caso aparece en su bandeja.

## 3. Navegación (barra lateral, agrupada)

Los grupos e ítems visibles dependen del rol y del contexto (dentro de una institución):

- **TRABAJO** — Bandeja de tareas · Filas de espera · Casos *(administrativo / admin)*
- **REGISTROS** — Historia clínica · Legajo profesional *(administrativo / admin)*
- **DISEÑO** — Flujos · Mapa de flujos · Formularios *(configurador / admin)*
- **SISTEMA** — Estructura organizativa · Administración *(admin de institución)*

**Header:** título de la sección actual · buscador global · selector de rol/contexto · avatar con rol.

**Fuera de una institución (super admin):** Directorio de instituciones (raíz) → Alta de institución → Ingresar → Panel de la institución.

## 4. Permisos y privacidad sobre la historia clínica

- El acceso a una HC está gobernado por el **legajo profesional** (rol / área / relación con el caso): solo profesionales habilitados la leen.
- Toda lectura y escritura queda **auditada** (quién, cuándo, en el marco de qué caso).
- Una entrada de HC, una vez asentada, es **inmutable** (se corrige con una entrada nueva). Igual que la timeline del caso.

## 5. Estados de un caso (configurables por flujo)

Cada flujo define su lista de estados y marca los de cierre. Ejemplo (Ingreso de paciente):

```
Recibido → En espera → En evaluación → Derivado → Atendido → Cerrado
```

Mapa de estado → color de badge: Recibido = neutro · En espera = ámbar · En evaluación = info · Derivado = ámbar · Atendido = verde · Cerrado = gris.
