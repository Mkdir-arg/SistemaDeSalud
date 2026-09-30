"""Preparación idempotente de una cuenta técnica, compartida por API y comando."""

from django.db import transaction

from apps.accounts.models import Membresia, Usuario
from apps.financiadores.models import MembresiaFinanciador
from apps.financiadores.services import auditar

from .models import Ambito, CuentaReferencia
from .perfiles import alcance_de_pares, email_canonico, etiqueta


ROL_QUE_RESUELVE_AUTORIZACIONES = "operador"


class ErrorPreparacion(Exception):
    """No se puede preparar una cuenta sin intervenir sobre otra identidad."""


@transaction.atomic
def preparar_cuenta(ambito, rol, institucion=None, financiador=None):
    """Crea o restablece solo el perfil pedido, sin tocar cuentas ajenas."""
    filtros = {"ambito": ambito, "rol": rol}
    if ambito == Ambito.INSTITUCION:
        filtros["institucion"] = institucion
    elif ambito == Ambito.FINANCIADOR:
        filtros["financiador"] = financiador
    ref = CuentaReferencia.objects.select_related("usuario").filter(**filtros).first()
    email = email_canonico(ambito, rol, getattr(institucion, "pk", None), getattr(financiador, "pk", None))
    usuario = ref.usuario if ref else _usuario_libre(email)
    nueva = usuario.pk is None
    cambios = _cuenta(usuario, ambito, rol)

    if ref is None:
        CuentaReferencia.objects.create(
            usuario=usuario, ambito=ambito, rol=rol, institucion=institucion, financiador=financiador,
        )
    elif ambito == Ambito.PLATAFORMA and ref.institucion_id is not None:
        # Convierte una cuenta estatal antigua con ancla en una membresía global.
        ref.institucion = None
        ref.save(update_fields=["institucion"])
        cambios.append("ancla institucional quitada")

    if ambito == Ambito.FINANCIADOR:
        cambios += _membresia_financiador(usuario, financiador, rol)
    else:
        cambios += _membresia_institucional(usuario, institucion, rol, espejo=ambito == Ambito.INSTITUCION)
    if nueva:
        return "creada", usuario.email, ""
    return ("actualizada" if cambios else "sin cambios"), usuario.email, ", ".join(cambios)


def _usuario_libre(email):
    usuario = Usuario.objects.filter(email__iexact=email).first()
    if usuario is None:
        return Usuario(email=email)
    raise ErrorPreparacion(f"{email} ya está en uso por otra cuenta. Revisalo antes de continuar; no se modificó ningún dato.")


def _cuenta(usuario, ambito, rol):
    nueva = usuario.pk is None
    esperado = {
        "nombre": "Superusuario", "apellido": etiqueta(ambito, rol),
        "is_active": True, "is_staff": False, "is_superuser": False,
    }
    cambios = [campo for campo, valor in esperado.items() if getattr(usuario, campo) != valor]
    for campo in cambios:
        setattr(usuario, campo, esperado[campo])
    if nueva or usuario.has_usable_password():
        usuario.set_unusable_password()
        cambios.append("contraseña anulada")
    if cambios:
        usuario.save()
    return [] if nueva else cambios


def _membresia_institucional(usuario, institucion, rol, espejo):
    cambios = []
    membresia, _ = Membresia.objects.get_or_create(
        usuario=usuario, institucion=institucion, rol=rol, defaults={"activo": True},
    )
    if not membresia.activo:
        membresia.activo = True
        membresia.save(update_fields=["activo"])
        cambios.append("membresía reactivada")
    if n := Membresia.objects.filter(usuario=usuario, activo=True).exclude(pk=membresia.pk).update(activo=False):
        cambios.append(f"{n} membresía(s) ajena(s) desactivada(s)")
    if n := MembresiaFinanciador.objects.filter(usuario=usuario, activo=True).update(activo=False):
        cambios.append(f"{n} membresía(s) de financiador desactivada(s)")
    if not espejo:
        return cambios
    # Espejo de pares: lo que tiene el personal real de ese rol en la institución.
    areas_pares, grupos_pares = alcance_de_pares(institucion, rol, usuario)
    areas = list(areas_pares.exclude(pk__in=membresia.areas.values("pk")))
    if areas:
        membresia.areas.add(*areas)
        cambios.append(f"{len(areas)} área(s) sumada(s)")
    grupos = list(grupos_pares.exclude(miembros=usuario))
    if grupos:
        usuario.grupos.add(*grupos)
        cambios.append(f"{len(grupos)} grupo(s) sumado(s)")
    return cambios


def _membresia_financiador(usuario, financiador, rol):
    cambios = []
    esperado = {
        "rol": rol, "activo": True, "creo_cuenta": False,
        "resuelve_autorizaciones": rol == ROL_QUE_RESUELVE_AUTORIZACIONES,
    }
    membresia = MembresiaFinanciador.objects.filter(financiador=financiador, usuario=usuario).first()
    if membresia is None:
        membresia = MembresiaFinanciador.objects.create(financiador=financiador, usuario=usuario, **esperado)
        cambios.append("membresía creada")
    else:
        distintos = [campo for campo, valor in esperado.items() if getattr(membresia, campo) != valor]
        for campo in distintos:
            setattr(membresia, campo, esperado[campo])
        if distintos:
            membresia.save(update_fields=distintos)
            cambios.append("membresía restablecida")
    if cambios:
        # El financiador ve en su registro que una cuenta técnica entró a su organización.
        auditar(None, "membresia_financiador", membresia.pk, financiador=financiador,
                motivo=f"cuenta de referencia; rol={membresia.rol}; resuelve_autorizaciones={membresia.resuelve_autorizaciones}")
    if n := MembresiaFinanciador.objects.filter(usuario=usuario, activo=True).exclude(pk=membresia.pk).update(activo=False):
        cambios.append(f"{n} membresía(s) de otro financiador desactivada(s)")
    if n := Membresia.objects.filter(usuario=usuario, activo=True).update(activo=False):
        cambios.append(f"{n} membresía(s) institucional(es) desactivada(s)")
    return cambios
