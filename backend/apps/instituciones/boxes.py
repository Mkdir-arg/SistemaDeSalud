"""Ocupaciones de box olvidadas (#172, AUD-048, decisión del dueño).

Un box ocupado sin actividad durante `UMBRAL` mientras hay pacientes sin
atender en su área probablemente quedó olvidado. Se avisa una sola vez por
ocupación al jefe del área y a los admins de la institución; liberarlo es una
decisión de ellos, confirmada. Nada se libera solo.

Actividad = la última llamada, rellamada o atención hecha desde ese box durante
la ocupación actual; sin ninguna, el momento en que se ocupó.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

UMBRAL = timedelta(hours=3)


def supervisa_box(usuario, box):
    """Jefe del área del box (o de toda la institución) o admin de la institución."""
    from apps.accounts.models import Membresia
    from apps.common import tiene_capacidad

    institucion_id = box.area.institucion_id
    if tiene_capacidad(usuario, "config_institucional", institucion_id):
        return True
    return Membresia.objects.filter(
        usuario=usuario, institucion_id=institucion_id, activo=True, rol=Membresia.Rol.JEFE_AREA,
    ).filter(Q(areas=box.area_id) | Q(areas__isnull=True)).exists()


def destinatarios(box):
    from apps.accounts.models import Membresia, Usuario

    institucion_id = box.area.institucion_id
    jefes = Q(rol=Membresia.Rol.JEFE_AREA) & (Q(areas=box.area_id) | Q(areas__isnull=True))
    admins = Q(rol=Membresia.Rol.ADMIN_INSTITUCION)
    ids = Membresia.objects.filter(institucion_id=institucion_id, activo=True).filter(jefes | admins) \
        .values_list("usuario_id", flat=True)
    return Usuario.objects.filter(pk__in=ids, is_active=True).exclude(pk=box.ocupado_por_id)


def ultima_actividad(box):
    from apps.casos.models import ItemFila

    marcas = ItemFila.objects.filter(box=box).aggregate(
        llamado=Max("llamado_at"), rellamado=Max("rellamado_at"), atendido=Max("atendido_at"),
    )
    hechas = [m for m in marcas.values() if m is not None and m >= box.ocupado_desde]
    return max([box.ocupado_desde, *hechas])


def hay_pacientes_esperando(box):
    from apps.casos.models import ItemFila

    return ItemFila.objects.filter(nodo__version__flujo__area_id=box.area_id, atendido=False).exists()


def revisar(ahora=None, *, seco=False):
    """Avisa las ocupaciones inactivas todavía no avisadas. Devuelve cuántas."""
    from apps.casos.models import Notificacion

    from .models import Box

    ahora = ahora or timezone.now()
    avisados = 0
    candidatos = Box.objects.filter(
        ocupado_por__isnull=False, ocupado_desde__lte=ahora - UMBRAL, aviso_inactividad_at__isnull=True,
    ).values_list("pk", flat=True)
    for pk in list(candidatos):
        with transaction.atomic():
            box = Box.objects.select_for_update(skip_locked=True, of=("self",)).select_related("area", "ocupado_por") \
                .filter(pk=pk, ocupado_por__isnull=False, aviso_inactividad_at__isnull=True).first()
            if box is None or ahora - ultima_actividad(box) < UMBRAL or not hay_pacientes_esperando(box):
                continue
            avisados += 1
            if seco:
                continue
            desde = timezone.localtime(ultima_actividad(box))
            quien = box.ocupado_por.nombre_completo or box.ocupado_por.email
            Notificacion.objects.bulk_create([
                Notificacion(
                    usuario=u, titulo=f"Box {box.nombre} ocupado sin actividad"[:200],
                    detalle=f"{quien} · sin actividad desde las {desde:%H:%M} y hay pacientes esperando en "
                            f"{box.area.nombre}. Podés liberarlo desde Mi trabajo."[:255],
                ) for u in destinatarios(box)
            ])
            box.aviso_inactividad_at = ahora
            box.save(update_fields=["aviso_inactividad_at"])
    return avisados
