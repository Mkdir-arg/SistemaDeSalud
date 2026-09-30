"""Prepara las cuentas de referencia que usa la simulación de perfiles.

Se puede correr en todos los entornos, producción incluida. No usa claves de
demo ni escribe contraseñas, y solo toca las cuentas de referencia y sus
membresías. Es idempotente: si se corre de nuevo, no cambia nada o restablece lo
que alguien haya modificado.

Estado en que queda cada cuenta
-------------------------------
- Tiene contraseña inutilizable y un correo en `referencia.hen.invalid`, un
  dominio que no recibe mensajes. No es staff ni superusuario. El login y el
  refresco de tokens la rechazan: solo funciona dentro de una simulación.
- Conserva únicamente la membresía de su perfil. Si alguien le agregó otra, el
  comando la desactiva.
- En los perfiles institucionales, recibe las áreas y los grupos activos donde ya
  trabaja personal activo con ese rol en la institución. El comando solo
  agrega; nunca quita, para respetar lo que haya configurado la institución.
- El operador de financiador queda designado para resolver autorizaciones. El
  admin y el auditor no, así cada perfil muestra la regla de designación expresa.
- No se crean permisos financieros institucionales. La simulación usa las
  concesiones que la institución le otorgue a la cuenta (el admin las hereda).

Uso
---
    manage.py preparar_cuentas_referencia --institucion 3 --financiador 2 --estatales
    manage.py preparar_cuentas_referencia --todas-las-instituciones --todos-los-financiadores --estatales
    manage.py preparar_cuentas_referencia --todas-las-instituciones --verificar

`--verificar` no escribe. Informa qué falta y, si falta algo, termina con error.
El uso habitual de «Ver como» prepara el perfil elegido automáticamente. Este
comando sirve para verificar o preparar cuentas por adelantado.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.financiadores.models import Financiador
from apps.instituciones.models import Institucion
from apps.simulacion.models import Ambito, CuentaReferencia
from apps.simulacion.perfiles import email_canonico, perfiles, problema_de_cuenta
from apps.simulacion.preparacion import ErrorPreparacion, preparar_cuenta

class Command(BaseCommand):
    help = "Crea o repara las cuentas de referencia para simular perfiles (apto para producción)."

    def add_arguments(self, parser):
        parser.add_argument("--institucion", type=int, action="append", default=[],
                            help="Prepara los perfiles institucionales de esa institución (repetible).")
        parser.add_argument("--todas-las-instituciones", action="store_true",
                            help="Prepara los perfiles institucionales de todas las instituciones activas.")
        parser.add_argument("--financiador", type=int, action="append", default=[],
                            help="Prepara los perfiles de ese financiador (repetible).")
        parser.add_argument("--todos-los-financiadores", action="store_true",
                            help="Prepara los perfiles de todos los financiadores activos.")
        parser.add_argument("--ancla-estatal", type=int, default=None,
                            help="Compatibilidad: prepara los perfiles estatales sin conservar el ancla.")
        parser.add_argument("--estatales", action="store_true",
                            help="Prepara Autoridad estatal y Auditor estatal sin institución.")
        parser.add_argument("--verificar", action="store_true",
                            help="No escribe: informa el estado y termina con error si falta algo.")

    def handle(self, *args, **o):
        instituciones = self._elegir(Institucion, o["institucion"], o["todas_las_instituciones"], "activa")
        financiadores = self._elegir(Financiador, o["financiador"], o["todos_los_financiadores"], "activo")
        ancla = self._elegir(Institucion, [o["ancla_estatal"]] if o["ancla_estatal"] else [], False, "activa")
        if not (instituciones or financiadores or ancla or o["estatales"]):
            raise CommandError(
                "Indicá qué preparar: --institucion, --todas-las-instituciones, --financiador, "
                "--todos-los-financiadores o --estatales. No se modificó ningún dato."
            )
        pedidos = [(Ambito.PLATAFORMA, rol, None, None) for rol, _ in perfiles(Ambito.PLATAFORMA) if ancla or o["estatales"]]
        pedidos += [(Ambito.INSTITUCION, rol, inst, None) for inst in instituciones for rol, _ in perfiles(Ambito.INSTITUCION)]
        pedidos += [(Ambito.FINANCIADOR, rol, None, fin) for fin in financiadores for rol, _ in perfiles(Ambito.FINANCIADOR)]

        if o["verificar"]:
            self._verificar(pedidos)
            return
        try:
            with transaction.atomic():
                for ambito, rol, institucion, financiador in pedidos:
                    estado, email, detalle = preparar_cuenta(ambito, rol, institucion, financiador)
                    self._linea(estado, ambito, rol, institucion or financiador or "Plataforma", email, detalle)
        except ErrorPreparacion as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f"{len(pedidos)} cuentas de referencia listas."))

    @staticmethod
    def _elegir(modelo, ids, todas, campo_activo):
        if todas:
            return list(modelo.objects.filter(**{campo_activo: True}).order_by("pk"))
        encontradas = {obj.pk: obj for obj in modelo.objects.filter(pk__in=ids)}
        faltan = [i for i in ids if i not in encontradas]
        if faltan:
            raise CommandError(f"No existe {modelo._meta.verbose_name} {faltan[0]}. No se modificó ningún dato.")
        return [encontradas[i] for i in dict.fromkeys(ids)]

    def _linea(self, estado, ambito, rol, lugar, email, detalle=""):
        estilo = {"FALTA": self.style.ERROR, "PROBLEMA": self.style.ERROR}.get(estado, lambda texto: texto)
        texto = f"  {estado:12} {ambito:12} {rol:15} {str(lugar):30.30} {email}"
        self.stdout.write(estilo(texto + (f" · {detalle}" if detalle else "")))

    def _verificar(self, pedidos):
        fallas = 0
        for ambito, rol, institucion, financiador in pedidos:
            filtros = {"ambito": ambito, "rol": rol}
            if ambito == Ambito.INSTITUCION:
                filtros["institucion"] = institucion
            elif ambito == Ambito.FINANCIADOR:
                filtros["financiador"] = financiador
            ref = CuentaReferencia.objects.select_related("usuario", "institucion", "financiador").filter(**filtros).first()
            email = email_canonico(ambito, rol, getattr(institucion, "pk", None), getattr(financiador, "pk", None))
            if ref is None:
                estado, detalle = "FALTA", "no está preparada"
            else:
                email = ref.usuario.email
                problema = problema_de_cuenta(ref)
                if not problema and ambito == Ambito.PLATAFORMA and ref.institucion_id is not None:
                    problema = f"está anclada a {ref.institucion}"
                estado, detalle = ("PROBLEMA", problema) if problema else ("OK", "")
            fallas += estado != "OK"
            self._linea(estado, ambito, rol, institucion or financiador or "Plataforma", email, detalle)
        if fallas:
            raise CommandError(f"{fallas} de {len(pedidos)} cuentas de referencia no están listas.")
        self.stdout.write(self.style.SUCCESS(f"Las {len(pedidos)} cuentas de referencia están listas."))
