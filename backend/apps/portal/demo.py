"""
La paciente del portal en la demo (#122).

Una cuenta del portal YA validada, sin pasar por RENAPER, sobre una persona que
ya existe del lado del hospital. Así la demo muestra a la misma persona desde
el hospital, el financiador y su propio portal. Sólo para `ENTORNO` demo o
desarrollo: quien llama tiene que haber pasado por `exigir_entorno_de_prueba`.

Le agrega lo que la app necesita para tener algo que mostrar en cada pantalla:
un turno reservado a más de 24 horas (se puede confirmar y cancelar), un estudio
realizado con su archivo, uno solicitado sin resultado y, si se le pasa un flujo
con fila, un caso esperando en esa sala para llamarla desde un box. Repetirlo no
duplica nada.
"""
import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

from apps.agenda import motor as agenda_motor
from apps.agenda.models import Agenda, Turno
from apps.casos import motor
from apps.casos.models import Caso
from apps.registros.models import ArchivoClinico, Estudio, HistoriaClinica

from .models import CuentaPaciente

ESTUDIO_REALIZADO = "Hemograma completo"
ESTUDIO_PENDIENTE = "Radiografía de tórax"
# El turno tiene que poder cancelarse (R3: más de 24 horas) aunque la demo se
# muestre al día siguiente de la carga.
DESDE_DIAS = 3


@dataclass(frozen=True)
class PacienteDemo:
    """Lo que deja `preparar_paciente`: la carga que lo llama arma su salida con esto."""
    cuenta: CuentaPaciente
    turno: Turno  # reservado a más de 24 horas
    estudio: Estudio  # realizado, con su archivo
    pendiente: Estudio  # solicitado, sin resultado
    caso: Caso | None  # esperando en la sala; None si no se pasó `sala`


def preparar_paciente(ciudadano, *, email, password, agendas=None, sala=None, autor="") -> PacienteDemo:
    """Crea o pone al día la cuenta del portal de `ciudadano` y sus datos de muestra.

    `agendas`: dónde buscar lugar para el turno, en orden de preferencia. Por
    defecto, las activas de la institución de la persona.
    `sala`: un flujo cuyo primer paso es una atención con fila; la persona queda
    esperando ahí.
    """
    cuenta = _cuenta(ciudadano, email, password)
    turno = _turno(ciudadano, agendas)
    historia, _ = HistoriaClinica.objects.get_or_create(ciudadano=ciudadano)
    hoy = timezone.localdate()
    estudio = _estudio_con_archivo(historia, hoy - timedelta(days=12), autor)
    pendiente, _ = Estudio.objects.get_or_create(
        historia=historia, tipo=ESTUDIO_PENDIENTE,
        defaults={"fecha": hoy, "realizado": False, "autor": autor},
    )
    caso = en_sala_de_espera(ciudadano, sala) if sala else None
    return PacienteDemo(cuenta=cuenta, turno=turno, estudio=estudio, pendiente=pendiente, caso=caso)


def en_sala_de_espera(ciudadano, flujo):
    """Un caso de `flujo` esperando en su fila; si ya hay uno sin atender, ese.

    Rehacer la carga después de un ensayo la deja otra vez esperando:
    - si la llamaron y nadie la devolvió a la cola, vuelve a la cola (lo mismo
      que el botón «Volver a la cola» del hospital);
    - el portal deja de mostrar una espera de más de 24 horas (`ESPERA_VIGENTE`):
      si tiene más de 12, se renueva la hora de ingreso, así la carga se puede
      rehacer el día anterior a la demo.
    Si la dieron por ausente, ya salió de la cola: se le abre un caso nuevo.
    """
    caso = Caso.objects.filter(
        institucion=ciudadano.institucion, ciudadano=ciudadano, version__flujo=flujo, en_filas__atendido=False,
    ).first()
    if caso:
        if caso.en_filas.filter(atendido=False, box__isnull=False).exists():
            motor.devolver_a_la_cola(caso, motivo="Carga de la demo: vuelve a esperar.")
        caso.en_filas.filter(atendido=False, ingreso__lt=timezone.now() - timedelta(hours=12)).update(ingreso=timezone.now())
        return caso
    caso = Caso.objects.create(
        institucion=ciudadano.institucion, version=flujo.versiones.filter(estado="publicada").latest("id"),
        ciudadano=ciudadano, area_actual=flujo.area,
    )
    motor.iniciar(caso)
    if not caso.en_filas.filter(atendido=False).exists():
        raise ValueError(f"El caso no quedó en una fila de espera: «{flujo.titulo}» no empieza con una atención con fila.")
    return caso


def _cuenta(ciudadano, email, password):
    ahora = timezone.now()
    cuenta = CuentaPaciente.objects.filter(email=email).first() or CuentaPaciente(email=email)
    # Si otra cuenta ya tenía este documento validado, la constraint R2 lo
    # rechaza: es un error de la carga y tiene que verse, no taparse.
    cuenta.email_verificado_at = cuenta.email_verificado_at or ahora
    cuenta.activa = True
    cuenta.identidad = CuentaPaciente.Identidad.VALIDADA
    cuenta.identidad_via = ""  # sin RENAPER: la creó la carga de la demo
    cuenta.identidad_validada_at = cuenta.identidad_validada_at or ahora
    cuenta.documento = ciudadano.documento.lstrip("0")
    cuenta.sexo = cuenta.sexo or CuentaPaciente.Sexo.FEMENINO
    cuenta.nombre, cuenta.apellido = ciudadano.nombre, ciudadano.apellido
    cuenta.fecha_nacimiento = ciudadano.fecha_nacimiento
    cuenta.intentos_validacion, cuenta.validacion_bloqueada_hasta = 0, None
    cuenta.set_password(password)
    cuenta.save()
    return cuenta


def _turno(ciudadano, agendas):
    """Un turno reservado a más de 24 horas; si ya hay uno, ese."""
    ahora = timezone.now()
    vigente = Turno.objects.filter(
        ciudadano=ciudadano, estado=Turno.Estado.RESERVADO,
        inicio__gte=ahora + timedelta(days=DESDE_DIAS - 1),
    ).order_by("inicio").first()
    if vigente:
        return vigente
    if agendas is None:
        agendas = Agenda.objects.filter(institucion=ciudadano.institucion, activa=True).order_by("id")
    desde = timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=DESDE_DIAS), time.min))
    for agenda in agendas:
        # Un intento por día: si ese día ya tiene un turno en esta agenda (uno
        # confirmado en un ensayo), los demás horarios del día fallan igual.
        probados = set()
        for libre in agenda_motor.proximos_libres(agenda, desde=desde, dias=21, cuantos=500):
            dia = timezone.localtime(libre["inicio"]).date()
            if dia in probados:
                continue
            probados.add(dia)
            try:
                return agenda_motor.reservar(agenda, ciudadano, libre["inicio"], origen=Turno.Origen.TELEFONO)
            except agenda_motor.ErrorAgenda:
                continue
    raise ValueError(f"No hay lugar en las agendas de {ciudadano.institucion} para el turno de la demo.")


def _estudio_con_archivo(historia, fecha, autor):
    estudio = Estudio.objects.filter(historia=historia, tipo=ESTUDIO_REALIZADO).first()
    if estudio and estudio.archivo and default_storage.exists(estudio.archivo):
        return estudio
    if estudio is None:
        estudio = Estudio(historia=historia, tipo=ESTUDIO_REALIZADO)
    estudio.fecha, estudio.realizado, estudio.resultado, estudio.autor = fecha, True, Estudio.Resultado.NORMAL, autor
    estudio.save()

    ciudadano = historia.ciudadano
    contenido = informe_pdf(ciudadano, ESTUDIO_REALIZADO, fecha)
    # Nombre al azar, como las subidas reales (`common.SubirArchivoView`): uno
    # fijo chocaba con `ArchivoClinico.ruta` única si el archivo se había perdido
    # (una base restaurada sin el volumen de media) y se podía adivinar.
    ArchivoClinico.objects.filter(objeto_tipo="Estudio", objeto_id=estudio.pk).delete()
    ruta = default_storage.save(f"uploads/{ciudadano.institucion_id}/{uuid.uuid4().hex}.pdf", ContentFile(contenido))
    ArchivoClinico.objects.create(
        institucion_id=ciudadano.institucion_id, ruta=ruta,
        nombre_original=f"hemograma-{fecha:%Y-%m-%d}.pdf", content_type="application/pdf",
        tamano=len(contenido), sha256=hashlib.sha256(contenido).hexdigest(),
        proposito=ArchivoClinico.Proposito.ESTUDIO, objeto_tipo="Estudio", objeto_id=estudio.pk,
    )
    estudio.archivo = ruta
    estudio.save(update_fields=["archivo"])
    return estudio


def informe_pdf(ciudadano, tipo, fecha):
    """Un PDF de una página, armado a mano para no sumar dependencias.

    Dice en el propio documento que es ficticio: puede terminar impreso o
    reenviado fuera de la demo.
    """
    def texto(s):
        # Helvetica estándar con WinAnsi: alcanza para el español.
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("cp1252")

    lineas = [
        (18, f"Informe de {tipo.lower()}"),
        (11, f"Paciente: {ciudadano.nombre} {ciudadano.apellido} · Documento {ciudadano.documento}"),
        (11, f"{ciudadano.institucion.nombre} · {fecha:%d/%m/%Y}"),
        (11, "Resultado: dentro de los valores de referencia."),
        (11, "DOCUMENTO FICTICIO DE DEMOSTRACIÓN DE HEN. SIN VALIDEZ CLÍNICA."),
    ]
    flujo = b"BT /F1 11 Tf 56 780 Td 18 TL\n"
    for tam, linea in lineas:
        flujo += b"/F1 %d Tf (" % tam + texto(linea) + b") Tj T*\n"
    flujo += b"ET"
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length %d >>\nstream\n" % len(flujo) + flujo + b"\nendstream",
    ]
    pdf = b"%PDF-1.4\n"
    posiciones = []
    for n, objeto in enumerate(objetos, 1):
        posiciones.append(len(pdf))
        pdf += b"%d 0 obj\n" % n + objeto + b"\nendobj\n"
    xref = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % p for p in posiciones)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objetos) + 1, xref)
    return pdf
