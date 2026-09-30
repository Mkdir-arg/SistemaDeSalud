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
    manage.py preparar_cuentas_referencia --institucion 3 --financiador 2 --ancla-estatal 3
    manage.py preparar_cuentas_referencia --todas-las-instituciones --todos-los-financiadores
    manage.py preparar_cuentas_referencia --todas-las-instituciones --verificar

`--verificar` no escribe. Informa qué falta y, si falta algo, termina con error.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Membresia, Usuario
from apps.financiadores.models import Financiador, MembresiaFinanciador
from apps.financiadores.services import auditar
from apps.instituciones.models import Institucion
from apps.simulacion.models import Ambito, CuentaReferencia
from apps.simulacion.perfiles import alcance_de_pares, email_canonico, etiqueta, perfiles, problema_de_cuenta

ROL_QUE_RESUELVE_AUTORIZACIONES = "operador"


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
                            help="Prepara Autoridad estatal y Auditor estatal anclados a esa institución.")
        parser.add_argument("--verificar", action="store_true",
                            help="No escribe: informa el estado y termina con error si falta algo.")

    def handle(self, *args, **o):
        instituciones = self._elegir(Institucion, o["institucion"], o["todas_las_instituciones"], "activa")
        financiadores = self._elegir(Financiador, o["financiador"], o["todos_los_financiadores"], "activo")
        ancla = self._elegir(Institucion, [o["ancla_estatal"]] if o["ancla_estatal"] else [], False, "activa")
        if not (instituciones or financiadores or ancla):
            raise CommandError(
                "Indicá qué preparar: --institucion, --todas-las-instituciones, --financiador, "
                "--todos-los-financiadores o --ancla-estatal. No se modificó ningún dato."
            )
        pedidos = [(Ambito.PLATAFORMA, rol, ancla[0], None) for rol, _ in perfiles(Ambito.PLATAFORMA) if ancla]
        pedidos += [(Ambito.INSTITUCION, rol, inst, None) for inst in instituciones for rol, _ in perfiles(Ambito.INSTITUCION)]
        pedidos += [(Ambito.FINANCIADOR, rol, None, fin) for fin in financiadores for rol, _ in perfiles(Ambito.FINANCIADOR)]

        if o["verificar"]:
            self._verificar(pedidos)
            return
        with transaction.atomic():
            for ambito, rol, institucion, financiador in pedidos:
                estado, email, detalle = self._preparar(ambito, rol, institucion, financiador)
                self._linea(estado, ambito, rol, institucion or financiador, email, detalle)
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
                if not problema and ambito == Ambito.PLATAFORMA and ref.institucion_id != institucion.pk:
                    problema = f"está anclada a {ref.institucion}"
                estado, detalle = ("PROBLEMA", problema) if problema else ("OK", "")
            fallas += estado != "OK"
            self._linea(estado, ambito, rol, institucion or financiador, email, detalle)
        if fallas:
            raise CommandError(f"{fallas} de {len(pedidos)} cuentas de referencia no están listas.")
        self.stdout.write(self.style.SUCCESS(f"Las {len(pedidos)} cuentas de referencia están listas."))

    def _preparar(self, ambito, rol, institucion, financiador):
        filtros = {"ambito": ambito, "rol": rol}
        if ambito == Ambito.INSTITUCION:
            filtros["institucion"] = institucion
        elif ambito == Ambito.FINANCIADOR:
            filtros["financiador"] = financiador
        ref = CuentaReferencia.objects.select_related("usuario").filter(**filtros).first()
        email = email_canonico(ambito, rol, getattr(institucion, "pk", None), getattr(financiador, "pk", None))
        usuario = ref.usuario if ref else self._usuario_libre(email)
        nueva = usuario.pk is None
        cambios = self._cuenta(usuario, ambito, rol)

        if ref is None:
            CuentaReferencia.objects.create(
                usuario=usuario, ambito=ambito, rol=rol, institucion=institucion, financiador=financiador,
            )
        elif ambito == Ambito.PLATAFORMA and ref.institucion_id != institucion.pk:
            ref.institucion = institucion
            ref.save(update_fields=["institucion"])
            cambios.append(f"anclada a {institucion}")

        if ambito == Ambito.FINANCIADOR:
            cambios += self._membresia_financiador(usuario, financiador, rol)
        else:
            cambios += self._membresia_institucional(usuario, institucion, rol, espejo=ambito == Ambito.INSTITUCION)
        if nueva:
            return "creada", usuario.email, ""
        return ("actualizada" if cambios else "sin cambios"), usuario.email, ", ".join(cambios)

    @staticmethod
    def _usuario_libre(email):
        usuario = Usuario.objects.filter(email__iexact=email).first()
        if usuario is None:
            return Usuario(email=email)
        raise CommandError(f"{email} ya está en uso por otra cuenta. Revisalo antes de continuar; no se modificó ningún dato.")

    @staticmethod
    def _cuenta(usuario, ambito, rol):
        nueva = usuario.pk is None
        esperado = {
            "nombre": "Superusuario", "apellido": etiqueta(ambito, rol),
            "is_active": True, "is_staff": False, "is_superuser": False,
        }
        cambios = [campo for campo, valor in esperado.items() if getattr(usuario, campo) != valor]
        for campo in cambios:
            setattr(usuario, campo, esperado[campo])
        if nueva or usuario.has_usable_password():
            usuario.set_unusable_password()
            cambios.append("contraseña anulada")
        if cambios:
            usuario.save()
        return [] if nueva else cambios

    @staticmethod
    def _membresia_institucional(usuario, institucion, rol, espejo):
        cambios = []
        membresia, _ = Membresia.objects.get_or_create(
            usuario=usuario, institucion=institucion, rol=rol, defaults={"activo": True},
        )
        if not membresia.activo:
            membresia.activo = True
            membresia.save(update_fields=["activo"])
            cambios.append("membresía reactivada")
        if n := Membresia.objects.filter(usuario=usuario, activo=True).exclude(pk=membresia.pk).update(activo=False):
            cambios.append(f"{n} membresía(s) ajena(s) desactivada(s)")
        if n := MembresiaFinanciador.objects.filter(usuario=usuario, activo=True).update(activo=False):
            cambios.append(f"{n} membresía(s) de financiador desactivada(s)")
        if not espejo:
            return cambios
        # Espejo de pares: lo que tiene el personal real de ese rol en la institución.
        areas_pares, grupos_pares = alcance_de_pares(institucion, rol, usuario)
        areas = list(areas_pares.exclude(pk__in=membresia.areas.values("pk")))
        if areas:
            membresia.areas.add(*areas)
            cambios.append(f"{len(areas)} área(s) sumada(s)")
        grupos = list(grupos_pares.exclude(miembros=usuario))
        if grupos:
            usuario.grupos.add(*grupos)
            cambios.append(f"{len(grupos)} grupo(s) sumado(s)")
        return cambios

    @staticmethod
    def _membresia_financiador(usuario, financiador, rol):
        cambios = []
        esperado = {
            "rol": rol, "activo": True, "creo_cuenta": False,
            "resuelve_autorizaciones": rol == ROL_QUE_RESUELVE_AUTORIZACIONES,
        }
        membresia = MembresiaFinanciador.objects.filter(financiador=financiador, usuario=usuario).first()
        if membresia is None:
            membresia = MembresiaFinanciador.objects.create(financiador=financiador, usuario=usuario, **esperado)
            cambios.append("membresía creada")
        else:
            distintos = [campo for campo, valor in esperado.items() if getattr(membresia, campo) != valor]
            for campo in distintos:
                setattr(membresia, campo, esperado[campo])
            if distintos:
                membresia.save(update_fields=distintos)
                cambios.append("membresía restablecida")
        if cambios:
            # El financiador ve en su registro que una cuenta técnica entró a su organización.
            auditar(None, "membresia_financiador", membresia.pk, financiador=financiador,
                    motivo=f"cuenta de referencia; rol={membresia.rol}; resuelve_autorizaciones={membresia.resuelve_autorizaciones}")
        if n := MembresiaFinanciador.objects.filter(usuario=usuario, activo=True).exclude(pk=membresia.pk).update(activo=False):
            cambios.append(f"{n} membresía(s) de otro financiador desactivada(s)")
        if n := Membresia.objects.filter(usuario=usuario, activo=True).update(activo=False):
            cambios.append(f"{n} membresía(s) institucional(es) desactivada(s)")
        return cambios
