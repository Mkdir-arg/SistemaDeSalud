"""
Límites de intentos de `/api/mi/*` (el primer throttling del proyecto).

Cada vista pública combina un límite por IP con otro por email o por cuenta. El
de IP frena a quien prueba muchos emails desde una máquina; el de email frena a
quien prueba un mismo email desde muchas IP, y evita que alguien llene de
correos la casilla de otra persona.

Los contadores viven en el cache `portal` (`DatabaseCache`, ver settings) y no
en el cache local por defecto: gunicorn corre con varios workers y cada uno
contaría por su lado.

La IP sale de `get_ident` de DRF, que respeta `NUM_PROXIES`. Detrás del nginx
del frontend hay un proxy: sin ese ajuste DRF tomaría el `X-Forwarded-For`
entero, que el cliente puede inventar para estrenar una IP en cada intento.
"""
import ipaddress

from django.core.cache import caches
from rest_framework.throttling import SimpleRateThrottle

from .tokens import hash_token


def origen(limite, request):
    """La IP del pedido, con IPv6 agrupado por /64.

    Una conexión IPv6 hogareña recibe un /64 entero: contar por dirección le
    daría a una sola máquina millones de IP para repartir los intentos.
    """
    ip = limite.get_ident(request)
    try:
        direccion = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if direccion.version == 4:
        return str(direccion)
    if direccion.ipv4_mapped is not None:
        return str(direccion.ipv4_mapped)
    return str(ipaddress.ip_network(f"{direccion}/64", strict=False))


class _LimitePortal(SimpleRateThrottle):
    # El cache se resuelve al usarlo y no al importar, para que las pruebas
    # puedan cambiar la configuración.
    @property
    def cache(self):
        return caches["portal"]


class PorIP(_LimitePortal):
    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": hash_token(origen(self, request))}


class PorEmail(_LimitePortal):
    """Por el email del cuerpo del pedido, exista o no la cuenta."""

    def identidad(self, request, email):
        return email

    def get_cache_key(self, request, view):
        datos = request.data if hasattr(request.data, "get") else {}
        email = str(datos.get("email", "") or "").strip().lower()
        if not email:
            return None
        # Hasheado: la tabla del cache no guarda emails y la clave no tiene
        # caracteres raros ni un largo que dependa de lo que mande el cliente.
        return self.cache_format % {"scope": self.scope, "ident": hash_token(self.identidad(request, email))}


class PorEmailEIP(PorEmail):
    """Por el par email e IP: un tercero que prueba claves desde su máquina no
    agota el cupo de la titular, que entra desde otra."""

    def identidad(self, request, email):
        return f"{email}|{origen(self, request)}"


class PorCuenta(_LimitePortal):
    def get_cache_key(self, request, view):
        cuenta = getattr(request, "user", None)
        if not getattr(cuenta, "pk", None):
            return None
        return self.cache_format % {"scope": self.scope, "ident": cuenta.pk}


def limites(**alcances):
    """Arma las clases de throttling de una vista.

    `limites(ip="portal_ingreso_ip", email="portal_ingreso_email")` devuelve
    una clase por alcance, cada una con su tasa de `DEFAULT_THROTTLE_RATES`.
    """
    base = {"ip": PorIP, "email": PorEmail, "email_ip": PorEmailEIP, "cuenta": PorCuenta}
    return [type(f"{base[tipo].__name__}_{alcance}", (base[tipo],), {"scope": alcance}) for tipo, alcance in alcances.items()]
