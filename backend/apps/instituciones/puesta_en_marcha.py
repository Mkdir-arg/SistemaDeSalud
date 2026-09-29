"""Pasos de la puesta en marcha de una institución, verificados sobre sus datos.

Es lo que muestra la guía de Inicio mientras la institución está en alta, y lo
que el resumen de la carga de demo cuenta como trabajo pendiente de quien la
configura: un solo criterio para las dos cosas.
"""
from django.db.models import Q
from django.utils import timezone


def pasos(inst):
    """{paso: bool} con los seis pasos de la guía, en el orden de la pantalla."""
    from apps.accounts.models import Membresia
    from apps.agenda.models import Agenda, Disponibilidad
    from apps.flujos.models import VersionFlujo
    from apps.instituciones.models import Area

    miembros = Membresia.objects.filter(
        institucion=inst, activo=True, usuario__is_active=True,
    )
    horarios = Disponibilidad.objects.filter(
        agenda__institucion=inst, agenda__activa=True,
        agenda__area__activa=True, activa=True,
    ).filter(
        Q(vigente_desde__isnull=True) | Q(vigente_desde__lte=timezone.localdate()),
        Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=timezone.localdate()),
    )
    profesionales = horarios.filter(
        agenda__tipo=Agenda.Tipo.PROFESIONAL,
        agenda__profesional__is_active=True,
        agenda__profesional__membresias__institucion=inst,
        agenda__profesional__membresias__activo=True,
    )
    recursos = horarios.filter(agenda__tipo=Agenda.Tipo.RECURSO)
    publicados = VersionFlujo.objects.filter(
        flujo__institucion=inst, estado=VersionFlujo.Estado.PUBLICADA,
    )
    return {
        "areas": Area.objects.filter(institucion=inst, activa=True).exists(),
        "usuarios": miembros.exists(),
        "asignaciones": miembros.filter(areas__institucion=inst, areas__activa=True).exists(),
        "agenda_profesional": profesionales.exists(),
        "agenda_recurso": recursos.exists(),
        "flujo_operativo": publicados.exists(),
    }
