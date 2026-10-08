"""
Validación de identidad contra RENAPER.

**El cotejo es nuestro.** El servicio contratado es una consulta: con DNI y sexo
devuelve los datos de la persona, incluido el número de trámite del ejemplar
vigente. La validación compara ese número con el que tipeó el paciente. Es lo
que la hace fuerte: el trámite está impreso sólo en el DNI físico y no figura en
ningún padrón, así que conocer el DNI, el sexo y el nombre de otra persona no
alcanza. El nombre no se pide: con el trámite no agrega seguridad y sí rechazos
falsos («Julián» contra «Julian Damian»). Se guarda el que devuelve RENAPER.

**Qué cuenta como intento.** Un DNI que no existe da lo mismo que un trámite
equivocado («no coincide») y cuenta para el bloqueo: si diera «no disponible»,
que no cuenta, el portal serviría para averiguar qué DNI existen. Sólo las
fallas técnicas (red, timeout, 5xx, respuesta ilegible o sin configurar) son
«no disponible».

**Selección del adaptador (falla cerrada).** El simulado se usa sólo si se lo
pide explícitamente con `RENAPER_MODO=simulado` *y* el `ENTORNO` es `demo` o
`desarrollo`. Se piden las dos cosas porque `ENTORNO` vale `desarrollo` cuando
falta la variable: un despliegue de producción que se olvidó de fijarla no
puede terminar validando identidades con el simulado. Cualquier otra
combinación usa el adaptador real, que sin URL ni credencial responde «no
disponible».

**La API** (documento «Uso de API», Coordinación de Infraestructura Digital de
Niñez, Adolescencia y Familia):
- `POST <RENAPER_URL>/auth/login` con `{username, password}` devuelve
  `{token, expiration}`;
- `GET <RENAPER_URL>/consultarenaper?dni=<documento>&sexo=<sexo>` con
  `Authorization: Bearer <token>`; vencido el token, hay que volver a pedirlo;
- si `isSuccess` es `false`, `message` dice el motivo y `result` viene vacío.

**Supuestos que la documentación no cubre** (acá y en ningún otro lado, para
corregirlos en un solo lugar):
- el sexo se manda como F, M o X (el ejemplo sólo muestra M);
- un DNI inexistente llega como `isSuccess: false` o como HTTP 404;
- un 401 o 403 en la consulta es un token vencido;
- el aviso de fallecimiento se reconoce porque falta «Sin Aviso de
  Fallecimiento» en `mensaf` o porque `fechaf` trae una fecha. Ante cualquier
  duda no se valida.
"""
import json
import logging
import re
import unicodedata
import threading
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

log = logging.getLogger(__name__)

ENTORNOS_CON_SIMULADO = ("demo", "desarrollo")
# La respuesta real ocupa ~1 KB. Un tope evita que una respuesta anómala se
# lea entera en memoria.
TOPE_RESPUESTA = 64 * 1024


@dataclass(frozen=True)
class DatosCotejo:
    documento: str
    sexo: str
    numero_tramite: str


@dataclass(frozen=True)
class Resultado:
    coincide: bool
    # Lo que devuelve RENAPER cuando coincide.
    nombre: str = ""
    apellido: str = ""
    fecha_nacimiento: Optional[date] = None
    # Por qué no coincidió, sólo para la auditoría: el paciente ve siempre lo
    # mismo. `no_encontrado`, `tramite_distinto` o `aviso_fallecimiento`.
    motivo: str = ""


class RenaperNoDisponible(Exception):
    """RENAPER no respondió, no está configurado o contestó algo ilegible.

    No cuenta como intento.
    """


def _numero(valor):
    texto = str(valor if valor is not None else "").strip()
    return int(texto) if texto.isascii() and texto.isdigit() else None


def _fecha(valor):
    try:
        return date.fromisoformat(str(valor or "").strip()[:10])
    except ValueError:
        return None


# UTF-8 leído como Latin-1 o Windows-1252: «Ã©» en vez de «é», «Ã‘» en vez de «Ñ».
_MARCAS_DE_DOBLE_ENCODING = ("Ã", "Â")
# Una palabra es una tira de letras: el apóstrofo y el guion la cortan, así
# «D'ANGELO» queda «D'Angelo» y «PÉREZ-GARCÍA», «Pérez-García». El carácter de
# reemplazo (una letra que se perdió) no corta: «GARC�A» queda «Garc�a».
_PALABRA = re.compile(r"(?:[^\W\d_]|\ufffd)+")


def _reparar_doble_encoding(texto):
    for _ in range(2):  # a veces viene codificado dos veces
        if not any(marca in texto for marca in _MARCAS_DE_DOBLE_ENCODING):
            break
        for codificacion in ("cp1252", "latin-1"):
            try:
                texto = texto.encode(codificacion).decode("utf-8")
                break
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        else:
            break  # no era doble encoding: una «Ã» legítima queda como está
    return texto


def formatear_nombre(valor):
    """Nombre o apellido de RENAPER en formato «Primera mayúscula».

    RENAPER los manda en mayúsculas, a veces con las tildes en minúscula
    («SáENZ»), con el UTF-8 leído como Latin-1 («PÃ‰REZ») o con la tilde como
    carácter aparte. Se reparan esas tres cosas antes de capitalizar: un
    `.title()` directo deja «PÃ©Rez» o «JoséE».
    """
    texto = _reparar_doble_encoding(str(valor or ""))
    # NFC junta «e» + tilde en «é»: si no, la tilde corta la palabra.
    texto = unicodedata.normalize("NFC", texto).replace("_", " ")
    texto = " ".join(texto.split())
    if "�" in texto:
        # La letra se perdió antes de llegar: no se puede adivinar cuál era.
        log.warning("portal: RENAPER devolvió un nombre con caracteres irrecuperables")
    return _PALABRA.sub(lambda palabra: palabra[0][:1].upper() + palabra[0][1:].lower(), texto)[:120]


def _sin_aviso_de_fallecimiento(datos):
    mensaje = str(datos.get("mensaf") or "").strip().lower()
    fecha = str(datos.get("fechaf") or "").strip()
    return mensaje.startswith("sin aviso de fallecimiento") and fecha in ("", "-")


def interpretar(respuesta, cotejo: DatosCotejo) -> Resultado:
    """Compara la respuesta de la consulta con lo que tipeó el paciente."""
    if not isinstance(respuesta, dict):
        raise RenaperNoDisponible("respuesta sin formato")
    datos = respuesta.get("result")
    if not respuesta.get("isSuccess") or not isinstance(datos, dict):
        return Resultado(coincide=False, motivo="no_encontrado")

    # El trámite del ejemplar vigente; si la tarjeta se reimprimió, el número
    # impreso puede ser el de la reimpresión. Se comparan como números porque
    # el DNI lo imprime con 11 dígitos y ceros adelante, y RENAPER sin ellos.
    vigentes = {_numero(datos.get("iD_TRAMITE_PRINCIPAL")), _numero(datos.get("iD_TRAMITE_TARJETA_REIMPRESA"))}
    vigentes -= {None, 0}
    if not vigentes:
        return Resultado(coincide=False, motivo="no_encontrado")
    if _numero(cotejo.numero_tramite) not in vigentes:
        return Resultado(coincide=False, motivo="tramite_distinto")
    if not _sin_aviso_de_fallecimiento(datos):
        return Resultado(coincide=False, motivo="aviso_fallecimiento")

    # Sólo esto sale de la respuesta: CUIL, domicilio y el resto no se guardan.
    return Resultado(
        coincide=True,
        nombre=formatear_nombre(datos.get("nombres")),
        apellido=formatear_nombre(datos.get("apellido")),
        fecha_nacimiento=_fecha(datos.get("fechaNacimiento")),
    )


class Simulado:
    """Para la demo y el desarrollo. Nunca en producción.

    Arma una respuesta con la forma de la real y la pasa por el mismo
    `interpretar`, así la demo recorre el mismo camino que producción:
    - trámite `00000000000`: el DNI no existe;
    - trámite `99999999999`: RENAPER no disponible;
    - trámite `11111111111`: tiene aviso de fallecimiento;
    - cualquier otro: coincide.
    """

    nombre = "simulado"

    def cotejar(self, datos: DatosCotejo) -> Resultado:
        if datos.numero_tramite == "99999999999":
            raise RenaperNoDisponible("simulado: no disponible")
        if datos.numero_tramite == "00000000000":
            return interpretar({"isSuccess": False, "message": "", "result": None}, datos)
        fallecida = datos.numero_tramite == "11111111111"
        respuesta = {
            "isSuccess": True,
            "result": {
                "iD_TRAMITE_PRINCIPAL": int(datos.numero_tramite),
                "iD_TRAMITE_TARJETA_REIMPRESA": 0,
                "apellido": "PÉREZ",
                "nombres": "Ana María",
                "fechaNacimiento": "1990-05-14",
                "mensaf": "Con Aviso de Fallecimiento" if fallecida else "Sin Aviso de Fallecimiento",
                "fechaf": "2020-01-01" if fallecida else "-",
            },
        }
        return interpretar(respuesta, datos)


class _TokenRechazado(Exception):
    """La consulta respondió 401/403: el token venció o lo revocaron."""


class _Sesion:
    """El token de la API, compartido por los pedidos de este proceso.

    Se pide con un login y se reusa hasta un minuto antes de que venza: un
    login por consulta duplicaría la latencia y la carga del servicio. Vive en
    memoria y no en la base: es una credencial, y cada worker sacar el suyo
    cuesta un login por worker, no por pedido.
    """

    MARGEN = timedelta(minutes=1)
    # Si el login no informa vencimiento, se renueva seguido por las dudas.
    VIDA_SIN_VENCIMIENTO = timedelta(minutes=5)

    def __init__(self):
        self._candado = threading.Lock()
        self._token = None
        self._vence = None

    def token(self, renovar=False):
        with self._candado:
            if renovar or self._token is None or timezone.now() >= self._vence - self.MARGEN:
                self._token, self._vence = _login()
            return self._token

    def olvidar(self):
        with self._candado:
            self._token = self._vence = None


_sesion = _Sesion()


def _pedir(pedido, que):
    """Hace el pedido y devuelve el JSON. Nada del pedido ni la respuesta va al log."""
    try:
        with urlopen(pedido, timeout=settings.RENAPER_TIMEOUT) as respuesta:
            cuerpo = respuesta.read(TOPE_RESPUESTA + 1)
    except HTTPError:
        raise
    except (URLError, TimeoutError, OSError) as exc:
        log.error("portal: RENAPER no respondió al %s (%s)", que, type(exc).__name__)
        raise RenaperNoDisponible(type(exc).__name__) from None
    if len(cuerpo) > TOPE_RESPUESTA:
        log.error("portal: la respuesta de RENAPER al %s supera el tope", que)
        raise RenaperNoDisponible("respuesta demasiado grande")
    try:
        return json.loads(cuerpo)
    except ValueError:
        log.error("portal: la respuesta de RENAPER al %s no es JSON", que)
        raise RenaperNoDisponible("respuesta ilegible") from None


def _login():
    cuerpo = json.dumps({"username": settings.RENAPER_USUARIO, "password": settings.RENAPER_CLAVE}).encode()
    pedido = Request(
        f"{settings.RENAPER_URL}/auth/login",
        data=cuerpo,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        respuesta = _pedir(pedido, "login")
    except HTTPError as exc:
        log.error("portal: el login de RENAPER respondió HTTP %s", exc.code)
        raise RenaperNoDisponible(f"login HTTP {exc.code}") from None
    token = respuesta.get("token") if isinstance(respuesta, dict) else None
    if not token:
        log.error("portal: el login de RENAPER no devolvió un token")
        raise RenaperNoDisponible("login sin token")
    vence = parse_datetime(str(respuesta.get("expiration") or ""))
    if vence is None or timezone.is_naive(vence):
        vence = timezone.now() + _Sesion.VIDA_SIN_VENCIMIENTO
    return token, vence


class Real:
    nombre = "real"

    def cotejar(self, datos: DatosCotejo) -> Resultado:
        if not (settings.RENAPER_URL and settings.RENAPER_USUARIO and settings.RENAPER_CLAVE):
            log.error("portal: RENAPER sin configurar (RENAPER_URL, RENAPER_USUARIO o RENAPER_CLAVE)")
            raise RenaperNoDisponible("sin configurar")
        if settings.ENTORNO == "produccion" and not settings.RENAPER_URL.lower().startswith("https://"):
            log.error("portal: RENAPER_URL tiene que ser https en producción; la validación está cerrada")
            raise RenaperNoDisponible("sin https")

        # Si el token se venció antes de lo informado, un login nuevo y un
        # solo reintento. Si el nuevo también se rechaza, es otra cosa.
        for renovar in (False, True):
            try:
                return self._consultar(_sesion.token(renovar=renovar), datos)
            except _TokenRechazado:
                _sesion.olvidar()
        log.error("portal: RENAPER rechazó un token recién emitido")
        raise RenaperNoDisponible("token rechazado")

    def _consultar(self, token, datos):
        # La URL lleva el DNI: nunca va al log.
        pedido = Request(
            f"{settings.RENAPER_URL}/consultarenaper?{urlencode({'dni': datos.documento, 'sexo': datos.sexo})}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        try:
            return interpretar(_pedir(pedido, "consulta"), datos)
        except HTTPError as exc:
            if exc.code in (401, 403):
                raise _TokenRechazado from None
            if exc.code == 404:
                return Resultado(coincide=False, motivo="no_encontrado")
            log.error("portal: la consulta a RENAPER respondió HTTP %s", exc.code)
            raise RenaperNoDisponible(f"HTTP {exc.code}") from None


def simulado_permitido():
    return settings.RENAPER_MODO == "simulado" and settings.ENTORNO in ENTORNOS_CON_SIMULADO


def adaptador():
    return Simulado() if simulado_permitido() else Real()
