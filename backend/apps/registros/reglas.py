"""
Quién puede escribir en la historia clínica, y qué no se puede deshacer.

La regla de firma nació dentro del motor de flujos (`_exigir_firmante` /
`_exigir_clinico`) porque hasta ahora la única forma de registrar una atención
era avanzar un caso. No lo era: el botón «Nueva atención» de la historia postea
directo a `/api/entradas-historia/`, que no pasaba por ninguna de las dos. El
resultado era que una administrativa de mesa de entradas podía dejar un «Alta
médica» firmado a nombre de una médica que nunca vio al paciente.

Acá se **reusa** la regla del motor —no se la reescribe— pasándole un contexto
mínimo con la institución del paciente. Dos reglas de firma en el mismo sistema
se desincronizan sin que nada avise, y la que quedaría vieja es justo la que
protege el registro legal.
"""
from rest_framework.exceptions import APIException


class ReglaClinica(APIException):
    """
    Una escritura que el rol de quien la pide no habilita.

    Sale con el mismo `{"detail": "<texto>"}` que devuelve el motor al avanzar un
    caso, porque la pantalla muestra ese texto tal cual: «Este paso lo puede
    registrar Médico» explica qué hacer; un error genérico manda a preguntar.
    """

    status_code = 400
    default_detail = "No se puede registrar esto."


class RegistroDuplicado(APIException):
    """
    Se intentó anotar dos veces al mismo paciente.

    Va con `detail` de texto y no como error de campo porque es el único lugar
    donde la pantalla lo lee: el cliente muestra `data.detail` tal cual, y un
    error keyeado por campo llega al usuario como «Error 400». El mensaje tiene
    que decir A QUIÉN corresponde ese documento —esa es la información que
    resuelve el problema—, así que tiene que llegar entero.
    """

    status_code = 400
    default_detail = "Ese paciente ya está registrado."


class RegistroInviolable(APIException):
    """
    Se intentó reescribir algo que ya se firmó.

    409 y no 403: el pedido es legítimo y el usuario puede escribir en esta
    historia; lo que no se puede es pisar un asiento firmado (Ley 26.529, art.
    15-16). La corrección de una atención firmada es una entrada NUEVA.
    """

    status_code = 409
    default_detail = "La entrada está firmada: no se puede modificar."


class _ContextoDirecto:
    """
    El mínimo que la regla del motor necesita cuando no hay caso.

    `_exigir_firmante` mira la institución y, si el caso está en un área, exige
    tenerla asignada. Una atención cargada desde la historia no viene de ningún
    área, así que ese chequeo no aplica: lo que sí aplica —rol y matrícula— es lo
    que se conserva.
    """

    def __init__(self, institucion):
        self.institucion = institucion
        self.area_actual_id = None
        self.area_actual = None


def exigir_firmante(institucion, autor):
    """
    Valida que `autor` pueda FIRMAR una atención y devuelve su matrícula.

    Sin esto, `firmada=True` es un booleano que manda cualquiera: la entrada sale
    con la chapa verde «Firmada» en pantalla y —al nacer sin sello— la
    verificación la clasifica como «anterior al sellado», o sea que una entrada
    fabricada hoy se disfraza de entrada vieja y la historia sigue diciendo que
    está intacta.
    """
    from apps.casos import motor

    try:
        return motor._exigir_firmante(_ContextoDirecto(institucion), None, autor)
    except motor.ErrorMotor as e:
        raise ReglaClinica(str(e))


def exigir_clinico(institucion, autor):
    """
    Valida que `autor` pueda emitir recetas o cargar estudios.

    Una receta de un psicofármaco atribuida a una profesional que no la
    prescribió no se puede desmentir: la receta no lleva sello ni matrícula.
    """
    from apps.casos import motor

    try:
        motor._exigir_clinico(_ContextoDirecto(institucion), autor)
    except motor.ErrorMotor as e:
        raise ReglaClinica(str(e))
