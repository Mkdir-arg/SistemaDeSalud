"""
Sellado de integridad de la historia clínica.

**Qué es y qué no es esto, sin vueltas.** Esto NO es firma digital en el sentido
de la Ley 25.506: eso exige un certificado emitido por un certificador
licenciado y un dispositivo (token o HSM) que guarde la clave privada, y hasta
que el cliente diga cuál usa no se puede implementar sin inventar. Ver
`FIRMA_DIGITAL` al final del archivo para el enganche que queda preparado.

Lo que SÍ hace, que es lo que faltaba: permite **demostrar que una entrada no se
tocó después de firmarse**. Hasta acá «firmada» era un booleano; alguien con
acceso a la base podía editar el texto de una atención de hace dos años y no
quedaba ni rastro. Con esto, cualquier cambio se detecta.

Cómo: al firmar se calcula un resumen (SHA-256) del contenido y se encadena con
el de la entrada firmada anterior de esa misma historia. Encadenarlas es lo que
hace la diferencia entre «se puede verificar una entrada» y «se puede verificar
la historia»: sin la cadena, quien altera una entrada sólo tiene que recalcular
su propio resumen; con la cadena, tendría que recalcular todas las posteriores,
y eso deja la última en evidencia contra cualquier copia o respaldo.
"""
import hashlib
from datetime import timezone as tz

from django.db import transaction
from django.utils import timezone

# Versión del formato del resumen. Si algún día cambia cómo se arma, las
# entradas viejas se siguen verificando con su versión: un cambio de formato que
# invalide diez años de historia es peor que no tener sellado.
VERSION = "cauce-sha256-v1"


def _canonico(entrada) -> str:
    """
    El texto exacto sobre el que se calcula el resumen.

    Incluye todo lo que, si cambiara, cambiaría el sentido del registro: qué
    dice, de quién es, quién lo firmó y con qué matrícula. Dejar afuera
    cualquiera de esos permitiría alterarlo sin romper el sello.

    `fecha` va en ISO con zona: sin zona, el mismo instante da dos textos
    distintos según dónde corra la verificación.
    """
    campos = [
        VERSION,
        str(entrada.historia_id),
        str(entrada.historia.ciudadano_id),
        entrada.titulo or "",
        entrada.contenido or "",
        str(entrada.autor_id or ""),
        entrada.matricula or "",
        entrada.fecha.astimezone(tz.utc).isoformat() if entrada.fecha else "",
        entrada.sello_previo or "",
    ]
    # Separador que no puede aparecer en los campos: sin él, mover texto de un
    # campo al siguiente daría el mismo resumen.
    return "\x1f".join(campos)


def calcular(entrada) -> str:
    return hashlib.sha256(_canonico(entrada).encode("utf-8")).hexdigest()


def sellar(entrada):
    """
    Sella una entrada firmada, encadenándola con la anterior de su historia.

    Sólo se sella lo firmado: una evolución sin firmar es un borrador, y sellarla
    daría a entender que alguien se hizo responsable.
    """
    if not entrada.firmada:
        return entrada

    from .models import HistoriaClinica

    # El atomic propio garantiza que haya transacción donde tomar el candado
    # (adentro del de `motor.avanzar` es apenas un savepoint, no cuesta nada).
    with transaction.atomic():
        # Se serializan los sellados de UNA historia. Sin este candado, dos
        # atenciones simultáneas del mismo paciente leen la misma entrada previa
        # y las dos se encadenan a ella: después `verificar_historia` denuncia
        # «la cadena se rompió» sobre una historia que nadie tocó, y ese falso
        # positivo no se puede deshacer desde la aplicación. Es el peor error
        # posible acá: la única prueba que el hospital tiene para decir que la
        # historia está intacta pasa a acusarlo.
        HistoriaClinica.objects.select_for_update().filter(pk=entrada.historia_id).first()

        previa = (
            type(entrada).objects
            .filter(historia_id=entrada.historia_id, firmada=True, sello__gt="")
            .exclude(pk=entrada.pk)
            .order_by("-firmada_at", "-fecha", "-id")
            .first()
        )
        entrada.sello_previo = previa.sello if previa else ""
        entrada.firmada_at = entrada.firmada_at or timezone.now()
        entrada.sello = calcular(entrada)
        entrada.save(update_fields=["sello", "sello_previo", "firmada_at"])
    return entrada


def verificar(entrada) -> dict:
    """
    ¿La entrada dice hoy lo mismo que cuando se firmó?

    Devuelve `{ok, motivo}`. Una entrada sin firmar no es un error: es un
    borrador, y decir «inválida» de algo que nunca se firmó sería una alarma
    falsa que enseña a ignorar las verdaderas.
    """
    if not entrada.firmada:
        return {"ok": True, "motivo": "sin firmar"}
    if not entrada.sello:
        # Firmada antes de que existiera el sellado. Se dice, no se inventa un
        # resultado: no se puede afirmar que esté intacta ni que esté alterada.
        return {"ok": None, "motivo": "firmada antes del sellado: no verificable"}
    return (
        {"ok": True, "motivo": "intacta"}
        if calcular(entrada) == entrada.sello
        else {"ok": False, "motivo": "el contenido cambió después de firmarse"}
    )


def verificar_historia(historia) -> dict:
    """
    Verifica la historia completa: cada entrada y la cadena entre ellas.

    La cadena es lo que hace que alterar una entrada vieja no alcance con
    recalcular su resumen: la siguiente apunta al anterior, y si no coincide, la
    historia queda marcada aunque cada entrada por separado se verifique.
    """
    entradas = list(
        historia.entradas.filter(firmada=True).order_by("firmada_at", "fecha", "id")
    )
    problemas, previo = [], ""
    for e in entradas:
        r = verificar(e)
        if r["ok"] is False:
            problemas.append({"entrada": e.id, "titulo": e.titulo, "motivo": r["motivo"]})
        elif r["ok"] is None:
            continue  # anterior al sellado: no entra en la cadena
        elif e.sello_previo != previo:
            problemas.append({
                "entrada": e.id, "titulo": e.titulo,
                "motivo": "la cadena se rompió: falta o cambió una entrada anterior",
            })
        if e.sello:
            previo = e.sello

    return {
        "ok": not problemas,
        "firmadas": len(entradas),
        "selladas": sum(1 for e in entradas if e.sello),
        "problemas": problemas,
    }


# --------------------------------------------------------------------------- #
# Enganche para firma digital con certificado (Ley 25.506)
# --------------------------------------------------------------------------- #
# Lo de arriba prueba que el registro no cambió. Lo que NO prueba, con validez
# legal ante un tercero, es QUIÉN lo firmó: para eso hace falta un certificado
# de un certificador licenciado y el dispositivo donde vive la clave privada.
#
# El resumen que se calcula acá es exactamente lo que habría que firmar con esa
# clave, así que agregarlo no cambia nada de lo ya escrito: se guardaría la firma
# y el certificado junto a la entrada, y `verificar` sumaría un chequeo más.
#
# No se implementa ahora porque elegir el certificador y el dispositivo es una
# decisión del cliente, y hacerlo con una clave generada por el sistema daría
# una firma sin ningún valor legal —peor que no tenerla, porque parece que sí—.
FIRMA_DIGITAL_PENDIENTE = True
