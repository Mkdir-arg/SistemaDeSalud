"""
Registros: lo que persiste más allá de un caso.

- Ciudadano: la persona/paciente, identificada a nivel institución.
- HistoriaClinica + EntradaHistoria / Estudio / Receta: el expediente clínico.
El legajo profesional (de los usuarios) vive en `apps.accounts`.
"""
import re

from django.db import models

_SEPARADORES = re.compile(r"[^0-9A-Za-z]")


def normalizar_documento(valor) -> str:
    """
    El documento como se COMPARA, no como lo escribió el administrativo.

    En Argentina el DNI se escribe con puntos: es lo que dice el documento
    físico que la persona tiene en la mano, o sea el caso normal y no el raro.
    Guardado tal cual, «30.111.222» y «30111222» son dos cadenas distintas para
    la base, la UniqueConstraint de abajo deja pasar la segunda y el paciente
    queda con dos historias clínicas paralelas: el médico abre una al azar y la
    alergia, la medicación crónica y la última internación pueden estar en la
    otra. No hay forma de fusionarlas, así que prevenir es toda la defensa.

    Se van puntos, espacios y guiones; las letras (pasaportes, LC/LE) quedan en
    mayúscula para que «ab123456» no sea un paciente distinto de «AB123456».
    """
    return _SEPARADORES.sub("", str(valor or "")).upper()


class Ciudadano(models.Model):
    """Persona registrada en una institución (paciente / ciudadano)."""

    institucion = models.ForeignKey(
        "instituciones.Institucion", on_delete=models.CASCADE, related_name="ciudadanos"
    )
    codigo = models.CharField("código (CIU)", max_length=40, blank=True)
    nombre = models.CharField(max_length=120)
    apellido = models.CharField(max_length=120, blank=True)
    documento = models.CharField("documento", max_length=30, blank=True)
    fecha_nacimiento = models.DateField("fecha de nacimiento", null=True, blank=True)
    obra_social = models.CharField("obra social", max_length=120, blank=True)
    domicilio = models.CharField(max_length=255, blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ciudadano"
        verbose_name_plural = "ciudadanos"
        ordering = ["apellido", "nombre"]
        constraints = [
            # El mismo documento no se puede anotar dos veces en la misma
            # institución: cada copia arranca su propia historia clínica (la HC
            # es OneToOne), y a partir de ahí el médico abre una de las dos al
            # azar mientras la alergia está en la otra.
            #
            # La condición es indispensable: el paciente sin documento —el NN
            # que entra a la guardia— tiene que poder anotarse igual, y varios a
            # la vez. Un unique pelado dejaría afuera exactamente el caso donde
            # menos se puede frenar el ingreso.
            models.UniqueConstraint(
                fields=["institucion", "documento"],
                condition=~models.Q(documento=""),
                name="ciudadano_documento_unico_por_institucion",
            ),
        ]

    def save(self, *args, **kwargs):
        # La normalización va acá y no sólo en el serializer porque la constraint
        # de arriba compara la cadena guardada: si un alta entra por otro camino
        # —el motor al ingresar un paciente, un import, el admin— con el DNI
        # punteado, la base acepta el duplicado igual y el módulo pierde su única
        # defensa contra las dos historias clínicas del mismo paciente.
        self.documento = normalizar_documento(self.documento)
        super().save(*args, **kwargs)

    def __str__(self):
        nombre = f"{self.nombre} {self.apellido}".strip()
        return f"{nombre} ({self.documento})" if self.documento else nombre


class ConsentimientoDatos(models.Model):
    """
    Consentimiento del paciente para tratar sus datos (Ley 25.326, art. 5).

    Se guarda **cada** consentimiento y cada revocación como una fila nueva, sin
    pisar la anterior: lo que importa ante un reclamo no es el estado de hoy sino
    qué se consintió y cuándo. Un booleano en el paciente no puede contestar «¿en
    qué momento dio el consentimiento?», que es justo la pregunta.

    La atención de urgencia NO depende de esto. La ley exceptúa expresamente los
    datos necesarios para una prestación de salud (art. 8), y un sistema que
    frene una guardia por un consentimiento faltante sería peligroso además de
    equivocado: se registra que falta, no se bloquea.
    """

    class Modo(models.TextChoices):
        ESCRITO = "escrito", "Escrito"
        VERBAL = "verbal", "Verbal"
        DIGITAL = "digital", "Digital"

    ciudadano = models.ForeignKey(
        "registros.Ciudadano", on_delete=models.CASCADE, related_name="consentimientos"
    )
    otorgado = models.BooleanField(
        default=True, help_text="False = revocación de un consentimiento anterior."
    )
    modo = models.CharField(max_length=20, choices=Modo.choices, default=Modo.ESCRITO)
    alcance = models.TextField(
        blank=True,
        help_text="Para qué se consintió: atención, docencia, investigación…",
    )
    # Quién lo tomó. Un consentimiento sin responsable no se puede verificar.
    tomado_por = models.ForeignKey(
        "accounts.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="consentimientos_tomados",
    )
    institucion = models.ForeignKey(
        "instituciones.Institucion", on_delete=models.CASCADE,
        related_name="consentimientos", null=True, blank=True,
    )
    momento = models.DateTimeField(auto_now_add=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "consentimiento de datos"
        verbose_name_plural = "consentimientos de datos"
        ordering = ["-momento", "-id"]

    def __str__(self):
        estado = "otorga" if self.otorgado else "revoca"
        return f"{self.ciudadano} {estado} · {self.momento:%d/%m/%Y}"


class HistoriaClinica(models.Model):
    """Expediente clínico de un ciudadano dentro de una institución."""

    ciudadano = models.OneToOneField(
        Ciudadano, on_delete=models.CASCADE, related_name="historia_clinica"
    )
    alergias = models.CharField(max_length=255, blank=True)
    condiciones = models.CharField("condiciones / antecedentes", max_length=255, blank=True)
    # Quién cargó los antecedentes por última vez y cuándo.
    #
    # Sin esta marca, `alergias=""` es ambiguo y la pantalla resuelve la
    # ambigüedad de la peor manera: dice «Sin alergias registradas» sobre un
    # paciente al que nunca se le preguntó. Con la marca se puede distinguir
    # «se preguntó y no tiene» de «no consta», que es la diferencia entre
    # indicar penicilina tranquilo y preguntar antes.
    antecedentes_por = models.ForeignKey(
        "accounts.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="antecedentes_cargados",
    )
    antecedentes_at = models.DateTimeField("antecedentes actualizados el", null=True, blank=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Orden explícito: sin él la paginación es inestable y un registro
        # puede salir en dos páginas o en ninguna.
        ordering = ["id"]
        verbose_name = "historia clínica"
        verbose_name_plural = "historias clínicas"

    def __str__(self):
        return f"HC de {self.ciudadano}"


class EntradaHistoria(models.Model):
    """Una entrada de evolución en la historia clínica (atención registrada)."""

    historia = models.ForeignKey(
        HistoriaClinica, on_delete=models.CASCADE, related_name="entradas"
    )
    titulo = models.CharField("título", max_length=200)
    contenido = models.TextField(blank=True)
    autor = models.ForeignKey(
        "accounts.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entradas_historia",
    )
    # Caso que originó la entrada (si vino del motor de ejecución).
    caso = models.ForeignKey(
        "casos.Caso",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entradas_historia",
    )
    firmada = models.BooleanField(default=False)
    # Matrícula del profesional al momento de firmar (snapshot: la matrícula del
    # legajo puede cambiar después). Vacía si la firmó el super admin.
    matricula = models.CharField("matrícula", max_length=60, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    # Sellado de integridad: prueba que la entrada no se tocó después de
    # firmarse. Hasta acá «firmada» era sólo un booleano y alguien con acceso a
    # la base podía editar una atención de hace dos años sin dejar rastro.
    # Ver `apps/registros/integridad.py` —incluido qué es y qué no es—.
    sello = models.CharField(max_length=64, blank=True, editable=False)
    # El sello de la entrada firmada anterior de esta historia: encadenarlas es
    # lo que hace que alterar una vieja no alcance con recalcular su resumen.
    sello_previo = models.CharField(max_length=64, blank=True, editable=False)
    firmada_at = models.DateTimeField("firmada el", null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "entrada de historia clínica"
        verbose_name_plural = "entradas de historia clínica"
        ordering = ["-fecha"]
        constraints = [
            # Un eslabón de la cadena tiene UN solo hijo. Si dos atenciones
            # simultáneas del mismo paciente leen la misma entrada previa —el
            # médico y la enfermera registrando a la vez—, las dos se encadenan
            # al mismo sello y `verificar_historia` denuncia una cadena rota que
            # nadie rompió. Ese falso positivo no se puede deshacer desde la
            # aplicación y queda pegado diez años: es preferible que la segunda
            # falle en el momento y se reintente.
            models.UniqueConstraint(
                fields=["historia", "sello_previo"],
                condition=~models.Q(sello_previo=""),
                name="entrada_un_solo_eslabon_siguiente",
            ),
        ]

    def __str__(self):
        return f"{self.titulo} · {self.historia.ciudadano}"


class Estudio(models.Model):
    """Estudio médico adjunto a una historia clínica."""

    class Resultado(models.TextChoices):
        NORMAL = "normal", "Normal"
        ALTERADO = "alterado", "Alterado"

    historia = models.ForeignKey(
        HistoriaClinica, on_delete=models.CASCADE, related_name="estudios"
    )
    tipo = models.CharField(max_length=150)
    resultado = models.CharField(max_length=20, choices=Resultado.choices, blank=True)
    realizado = models.BooleanField("realizado", default=False)
    archivo = models.CharField("archivo", max_length=255, blank=True)
    autor = models.CharField(max_length=150, blank=True)
    fecha = models.DateField()

    class Meta:
        verbose_name = "estudio"
        verbose_name_plural = "estudios"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.tipo} · {self.fecha}"


class ArchivoClinico(models.Model):
    """Metadata persistente de un archivo clinico guardado en storage privado."""

    class Proposito(models.TextChoices):
        ADJUNTO_CASO = "adjunto_caso", "Adjunto de caso"
        ESTUDIO = "estudio", "Estudio"
        OTRO = "otro", "Otro"

    institucion = models.ForeignKey(
        "instituciones.Institucion", on_delete=models.CASCADE, related_name="archivos_clinicos"
    )
    ruta = models.CharField(max_length=255, unique=True)
    nombre_original = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120)
    tamano = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    proposito = models.CharField(max_length=30, choices=Proposito.choices, default=Proposito.ADJUNTO_CASO)
    objeto_tipo = models.CharField(max_length=80, blank=True)
    objeto_id = models.PositiveIntegerField(null=True, blank=True)
    subido_por = models.ForeignKey(
        "accounts.Usuario", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="archivos_clinicos_subidos",
    )
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "archivo clinico"
        verbose_name_plural = "archivos clinicos"
        ordering = ["-creado", "-id"]
        indexes = [
            models.Index(fields=["institucion", "creado"]),
            models.Index(fields=["objeto_tipo", "objeto_id"]),
        ]

    def __str__(self):
        return f"{self.nombre_original} ({self.institucion})"


class Receta(models.Model):
    """Receta emitida en el marco de una historia clínica."""

    historia = models.ForeignKey(
        HistoriaClinica, on_delete=models.CASCADE, related_name="recetas"
    )
    detalle = models.TextField()
    activa = models.BooleanField(default=True)
    autor = models.ForeignKey(
        "accounts.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recetas",
    )
    fecha = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "receta"
        verbose_name_plural = "recetas"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Receta · {self.historia.ciudadano} · {self.fecha}"
