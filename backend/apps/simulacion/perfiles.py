"""
Catálogo de perfiles simulables y verificación de sus cuentas.

Los perfiles salen de las fuentes de verdad de HEN: `Membresia.Rol` para
plataforma e institución y el rol de `MembresiaFinanciador` para el portal de
financiadores. Si mañana se agrega un rol, aparece acá sin cambiar este módulo.

Una cuenta solo sirve para simular si conserva exactamente la membresía de su
perfil. Si alguien le agregó un rol, otra institución o privilegios de
plataforma, la simulación se rechaza: mostraría más de lo que tiene el perfil.
"""
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Membresia, Usuario
from apps.financiadores.models import Financiador, MembresiaFinanciador
from apps.instituciones.models import Area, Grupo, Institucion

from .models import Ambito, CuentaReferencia, SesionSimulacion

# `plataforma` y `auditor` tienen membresía global y se ofrecen desde la vista
# de plataforma. El resto de `Membresia.Rol` es institucional.
PERFILES_ESTATALES = (Membresia.Rol.PLATAFORMA, Membresia.Rol.AUDITOR)
DOMINIO = "referencia.hen.invalid"
DURACION = timedelta(hours=8)


def perfiles(ambito):
    """`[(rol, etiqueta)]` que se pueden simular en el ámbito."""
    if ambito == Ambito.PLATAFORMA:
        return [(r.value, r.label) for r in Membresia.Rol if r in PERFILES_ESTATALES]
    if ambito == Ambito.INSTITUCION:
        return [(r.value, r.label) for r in Membresia.Rol if r not in PERFILES_ESTATALES]
    if ambito == Ambito.FINANCIADOR:
        return [(valor, f"{etiqueta} de financiador")
                for valor, etiqueta in MembresiaFinanciador._meta.get_field("rol").choices]
    return []


def etiqueta(ambito, rol):
    return dict(perfiles(ambito)).get(rol, rol)


def email_canonico(ambito, rol, institucion_id=None, financiador_id=None):
    """Correo de la cuenta. `.invalid` es un dominio reservado: nunca recibe mensajes."""
    if ambito == Ambito.PLATAFORMA:
        return f"{rol}@{DOMINIO}"
    if ambito == Ambito.INSTITUCION:
        return f"{rol}.i{institucion_id}@{DOMINIO}"
    return f"financiador-{rol}.f{financiador_id}@{DOMINIO}"


def es_cuenta_referencia(usuario):
    if not (usuario and getattr(usuario, "pk", None)):
        return False
    if (usuario.email or "").lower().endswith(f"@{DOMINIO}"):
        return True
    return CuentaReferencia.objects.filter(usuario_id=usuario.pk).exists()


def alcance_de_pares(institucion, rol, usuario):
    """Áreas y grupos activos de personal real del mismo perfil institucional."""
    pares = Membresia.objects.filter(
        institucion=institucion, rol=rol, activo=True,
        usuario__is_active=True, usuario__is_superuser=False, usuario__cuenta_referencia__isnull=True,
    ).exclude(usuario=usuario)
    areas = Area.objects.filter(institucion=institucion, activa=True, miembros__in=pares).distinct()
    grupos = Grupo.objects.filter(
        activo=True, area__institucion=institucion, area__activa=True,
        miembros__in=pares.values("usuario"),
    ).distinct()
    return areas, grupos


def problema_de_cuenta(ref):
    """Por qué la cuenta no sirve para simular su perfil, o None si sirve."""
    u = ref.usuario
    if not u.is_active:
        return "La cuenta de referencia está inactiva."
    if u.is_superuser or u.is_staff:
        return "La cuenta de referencia tiene privilegios de plataforma."
    if u.has_usable_password():
        return "La cuenta de referencia tiene contraseña propia."
    membresias = set(Membresia.objects.filter(usuario=u, activo=True).values_list("institucion_id", "rol"))
    financieras = set(MembresiaFinanciador.objects.filter(usuario=u, activo=True).values_list("financiador_id", "rol"))
    if ref.ambito == Ambito.FINANCIADOR:
        if membresias or financieras != {(ref.financiador_id, ref.rol)}:
            return "La cuenta de referencia no conserva solo la membresía de su perfil."
        if not ref.financiador.activo:
            return "El financiador está inactivo."
        return None
    if financieras or membresias != {(ref.institucion_id, ref.rol)}:
        return "La cuenta de referencia no conserva solo la membresía de su perfil."
    if ref.ambito == Ambito.INSTITUCION and not ref.institucion.activa:
        return "La institución está inactiva."
    if ref.ambito == Ambito.INSTITUCION:
        areas, grupos = alcance_de_pares(ref.institucion, ref.rol, u)
        membresia = Membresia.objects.get(usuario=u, institucion_id=ref.institucion_id, rol=ref.rol, activo=True)
        if areas.exclude(pk__in=membresia.areas.values("pk")).exists():
            return "La cuenta de referencia no tiene todas las áreas de sus pares. Volvé a prepararla."
        if grupos.exclude(miembros=u).exists():
            return "La cuenta de referencia no tiene todos los grupos de sus pares. Volvé a prepararla."
    return None


def cuentas_del_ambito(ambito, institucion_id=None, financiador_id=None):
    filtros = {"ambito": ambito}
    if ambito == Ambito.INSTITUCION:
        filtros["institucion_id"] = institucion_id
    elif ambito == Ambito.FINANCIADOR:
        filtros["financiador_id"] = financiador_id
    return CuentaReferencia.objects.filter(**filtros).select_related("usuario", "institucion", "financiador")


def catalogo(ambito, institucion_id=None, financiador_id=None):
    """Cada perfil del ámbito, con su cuenta y, si no se puede simular, el motivo."""
    cuentas = {c.rol: c for c in cuentas_del_ambito(ambito, institucion_id, financiador_id)}
    filas = []
    for rol, nombre in perfiles(ambito):
        ref = cuentas.get(rol)
        problema = "Falta preparar la cuenta de referencia." if ref is None else problema_de_cuenta(ref)
        filas.append({
            "rol": rol,
            "etiqueta": nombre,
            "disponible": problema is None,
            "motivo": problema or "",
            "cuenta": None if ref is None else {
                "id": ref.usuario_id, "nombre": ref.usuario.nombre_completo, "email": ref.usuario.email,
            },
        })
    return filas


@transaction.atomic
def iniciar(superusuario, ambito, rol, institucion_id=None, financiador_id=None, ip=None):
    """Abre una simulación y cierra la que el superusuario tuviera abierta."""
    if rol not in dict(perfiles(ambito)):
        raise ValidationError("Ese perfil no se puede simular en ese ámbito.")
    institucion = financiador = None
    if ambito == Ambito.INSTITUCION:
        institucion = Institucion.objects.select_for_update().filter(pk=institucion_id, activa=True).first()
        if institucion is None:
            raise ValidationError("La institución no existe o está inactiva.")
    elif ambito == Ambito.FINANCIADOR:
        financiador = Financiador.objects.select_for_update().filter(pk=financiador_id, activo=True).first()
        if financiador is None:
            raise ValidationError("El financiador no existe o está inactivo.")
    else:
        # Una fila compartida serializa el primer alta estatal entre superusuarios.
        Usuario.objects.filter(is_superuser=True).order_by("pk").select_for_update().first()
    # La preparación reutiliza el catálogo de este módulo; importar aquí evita
    # un ciclo de imports al cargar Django.
    from .preparacion import ErrorPreparacion, preparar_cuenta
    try:
        preparar_cuenta(ambito, rol, institucion, financiador)
    except ErrorPreparacion as error:
        raise ValidationError(str(error)) from error
    ref = cuentas_del_ambito(ambito, institucion_id, financiador_id).filter(rol=rol).first()
    if ref is None:
        raise ValidationError("No se pudo preparar la cuenta de referencia.")
    problema = problema_de_cuenta(ref)
    if problema:
        raise ValidationError(problema)
    Usuario.objects.select_for_update().get(pk=superusuario.pk)
    ahora = timezone.now()
    SesionSimulacion.objects.filter(superusuario=superusuario, finalizada__isnull=True).update(
        finalizada=ahora, fin=SesionSimulacion.Fin.REEMPLAZO,
    )
    return SesionSimulacion.objects.create(
        superusuario=superusuario, cuenta=ref.usuario, ambito=ambito, rol=rol,
        institucion=ref.institucion, financiador=ref.financiador, vence=ahora + DURACION, ip=ip,
    )


def problema_de_sesion(sesion):
    """Por qué una sesión abierta ya no puede usarse, o None si sigue vigente."""
    if sesion.vence <= timezone.now():
        return SesionSimulacion.Fin.VENCIMIENTO, "La simulación venció. Volvé a elegir un perfil."
    ref = CuentaReferencia.objects.select_related("usuario", "institucion", "financiador").filter(
        usuario_id=sesion.cuenta_id,
    ).first()
    clave = (sesion.ambito, sesion.rol, sesion.institucion_id, sesion.financiador_id)
    if ref is None or (ref.ambito, ref.rol, ref.institucion_id, ref.financiador_id) != clave:
        return SesionSimulacion.Fin.INVALIDA, "La cuenta de referencia ya no corresponde a ese perfil."
    problema = problema_de_cuenta(ref)
    if problema:
        return SesionSimulacion.Fin.INVALIDA, problema
    return None


def _ambito_json(obj):
    return None if obj is None else {"id": obj.pk, "nombre": obj.nombre, "tipo": getattr(obj, "tipo", "") or ""}


def datos_de_sesion(sesion):
    """Lo que el frontend necesita para mostrar y sostener la simulación."""
    return {
        "id": str(sesion.pk),
        "ambito": sesion.ambito,
        "rol": sesion.rol,
        "etiqueta": etiqueta(sesion.ambito, sesion.rol),
        "institucion": _ambito_json(sesion.institucion),
        "financiador": _ambito_json(sesion.financiador),
        "cuenta": {"id": sesion.cuenta_id, "nombre": sesion.cuenta.nombre_completo, "email": sesion.cuenta.email},
        "superusuario": {
            "id": sesion.superusuario_id,
            "nombre": sesion.superusuario.nombre_completo,
            "email": sesion.superusuario.email,
        },
        "iniciada": sesion.iniciada,
        "vence": sesion.vence,
        "finalizada": sesion.finalizada,
    }
