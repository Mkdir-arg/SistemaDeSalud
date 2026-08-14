"""
Política de retención de datos (Ley 25.326, art. 4 inc. 7).

La ley dice que los datos personales se destruyen cuando dejan de ser necesarios
para el fin que los originó. Eso no significa borrar todo lo viejo: la Ley
26.529 obliga a conservar la historia clínica **diez años**, y ese es su fin.

Las dos leyes no se contradicen; lo que hay que hacer es distinguir, y esa
distinción es todo este archivo:

  · La HISTORIA CLÍNICA tiene un plazo legal mínimo. No se toca antes, ni aunque
    alguien lo pida: la obligación de conservarla es del hospital, no del
    paciente. Un comando que la borre «para cumplir con protección de datos»
    haría al hospital incumplir la otra ley.

  · El REGISTRO DE ACCESOS vive lo mismo que la historia que audita. Borrarlo
    antes dejaría diez años de historia sin poder decir quién la miró, que es
    exactamente lo que ese registro existe para evitar.

  · Lo OPERATIVO —quién estuvo en una cola, qué notificación se mostró— cumple su
    fin en semanas. Es lo que de verdad hay que purgar, y lo que hoy se acumula
    para siempre sin que nadie lo mire.

El comando `purgar_datos` aplica esto, en seco por defecto: un borrado masivo
que se dispara sin que nadie lo haya mirado es peor que no purgar.
"""
from datetime import timedelta

from django.utils import timezone

# Mínimo legal de la historia clínica (Ley 26.529, art. 18). No es configurable
# a la baja a propósito: bajarlo es incumplir, y una constante editable termina
# editada por alguien que necesitaba espacio en disco.
ANIOS_HISTORIA_CLINICA = 10


class Regla:
    """
    Una clase de dato con su plazo y el motivo de ese plazo.

    El motivo es parte de la regla, no un comentario: una política de retención
    sin el porqué de cada plazo no se puede defender ante nadie, y a los seis
    meses nadie recuerda si «90 días» salió de la ley o de una reunión.
    """

    def __init__(self, nombre, dias, motivo, queryset, campo_fecha, protegido=False):
        self.nombre = nombre
        self.dias = dias
        self.motivo = motivo
        self._queryset = queryset
        self.campo_fecha = campo_fecha
        # Protegido = tiene plazo legal mínimo; el comando se niega a tocarlo
        # aunque se lo pidan.
        self.protegido = protegido

    def vencidos(self):
        corte = timezone.now() - timedelta(days=self.dias)
        return self._queryset().filter(**{f"{self.campo_fecha}__lt": corte})


def reglas():
    """
    La política completa, en un solo lugar.

    Está como función y no como constante porque los modelos se importan tarde;
    tenerla junta es lo que permite mirarla entera y discutirla, que es la única
    forma de que una política de retención signifique algo.
    """
    from apps.agenda.models import Turno
    from apps.auditoria.models import AccesoClinico
    from apps.casos.models import ItemFila, Notificacion
    from apps.registros.models import EntradaHistoria

    diez_anios = ANIOS_HISTORIA_CLINICA * 365

    return [
        Regla(
            "historia clínica", diez_anios,
            "Ley 26.529 art. 18: se conserva 10 años. No se borra antes.",
            lambda: EntradaHistoria.objects.all(), "fecha", protegido=True,
        ),
        Regla(
            "registro de accesos", diez_anios,
            "Vive lo mismo que la historia que audita: borrarlo antes dejaría "
            "esos años sin poder decir quién los miró.",
            lambda: AccesoClinico.objects.all(), "momento", protegido=True,
        ),
        Regla(
            "ítems de fila", 180,
            "Cumplió su fin cuando el paciente fue atendido. Los tiempos que "
            "alimentan los indicadores ya se calcularon; el renglón en sí no "
            "aporta nada después de seis meses.",
            lambda: ItemFila.objects.filter(atendido=True), "ingreso",
        ),
        Regla(
            "notificaciones leídas", 90,
            "Un aviso ya leído de hace tres meses no le sirve a nadie y acumula "
            "el nombre del paciente en una tabla que nadie mira.",
            lambda: Notificacion.objects.filter(leida=True), "creada",
        ),
        Regla(
            "turnos cancelados", 365,
            "Un turno que se canceló no forma parte de la atención. Se conserva "
            "un año porque el ausentismo del período se sigue reportando.",
            lambda: Turno.objects.filter(estado=Turno.Estado.CANCELADO), "inicio",
        ),
    ]


def informe():
    """Qué hay para purgar hoy, sin tocar nada."""
    return [{
        "regla": r.nombre,
        "dias": r.dias,
        "motivo": r.motivo,
        "protegido": r.protegido,
        "vencidos": r.vencidos().count(),
    } for r in reglas()]
