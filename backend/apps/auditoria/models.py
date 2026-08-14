"""
Registro de accesos a datos clínicos (Ley 26.529, art. 14 y 15).

La ley le da al paciente el derecho a saber **quién consultó su historia
clínica**. Hasta acá el sistema registraba qué le pasó al caso —quién lo atendió,
qué se escribió— pero no quién lo MIRÓ, que es una pregunta distinta: leer una
historia no deja ninguna marca en ella.

Sin esto, un hospital no puede contestar «¿quién vio la historia de esta
persona?», y esa es la primera pregunta cuando alguien denuncia que su
información circuló.

**Qué se registra y qué no.** Se registra el acceso a datos clínicos: abrir la
historia de un paciente, su listado de estudios, sus recetas. No se registra la
navegación general del sistema —abrir la fila de espera, mirar el tablero— que
no expone la historia de nadie y llenaría el registro de ruido hasta volverlo
inútil.

**Este registro no se edita ni se borra.** Un registro de auditoría que se puede
reescribir no sirve para auditar: es exactamente lo que alguien querría tocar.
"""
from django.db import models


class AccesoClinico(models.Model):
    """
    Una consulta a datos clínicos de una persona.

    Se guarda el paciente y no sólo el objeto mirado porque la pregunta de la
    ley es sobre la PERSONA: «quién vio mi historia», no «quién vio la receta
    número 4812».
    """

    class Tipo(models.TextChoices):
        # Se abrió el registro de una persona concreta.
        DETALLE = "detalle", "Consulta de un registro"
        # Se listó un conjunto. Va como UNA fila con el filtro y la cantidad, no
        # una por resultado: un listado de 200 pacientes generaría 200 filas que
        # esconden los accesos que sí importan.
        LISTADO = "listado", "Consulta de un listado"
        EXPORTACION = "exportacion", "Exportación a archivo"

    usuario = models.ForeignKey(
        "accounts.Usuario", on_delete=models.PROTECT, related_name="accesos_clinicos",
        help_text="No se borra con el usuario: el registro tiene que sobrevivirlo.",
    )
    # A quién se consultó. Nulo en un listado, donde no hay una sola persona.
    ciudadano = models.ForeignKey(
        "registros.Ciudadano", on_delete=models.PROTECT, null=True, blank=True,
        related_name="accesos",
    )
    institucion = models.ForeignKey(
        "instituciones.Institucion", on_delete=models.PROTECT, null=True, blank=True,
        related_name="accesos_clinicos",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    # Qué se miró: «historias-clinicas», «recetas». Se guarda el nombre del
    # recurso y no una FK genérica porque el registro tiene que seguir siendo
    # legible aunque el objeto se borre.
    recurso = models.CharField(max_length=60)
    objeto_id = models.CharField(max_length=40, blank=True)
    # Con qué filtros, en un listado. Es lo que distingue «buscó a esta persona
    # por documento» de «abrió el padrón del área».
    detalle = models.CharField(max_length=300, blank=True)
    resultados = models.PositiveIntegerField(default=0)

    ip = models.GenericIPAddressField(null=True, blank=True)
    momento = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "acceso a datos clínicos"
        verbose_name_plural = "accesos a datos clínicos"
        ordering = ["-momento", "-id"]
        indexes = [
            models.Index(fields=["ciudadano", "-momento"]),
            models.Index(fields=["usuario", "-momento"]),
        ]

    def __str__(self):
        quien = self.usuario.nombre_completo if self.usuario_id else "?"
        return f"{quien} · {self.recurso} · {self.momento:%d/%m/%Y %H:%M}"


# El latido de los procesos periódicos vive en `latidos.py`, con su explicación.
# Se re-exporta acá para que Django lo descubra como modelo de esta app.
from .latidos import Latido  # noqa: E402,F401
