"""
Segundo establecimiento y red, para poder mostrar los traslados.

Va aparte de `seed_guardia` a propósito: ese comando arma UN hospital completo y
es la base de todo lo demás. La red se apoya encima, y separarla deja claro que
el sistema funciona con una sola institución —que es como va a empezar
cualquier cliente— y que lo multicentro se agrega después.

El segundo establecimiento es deliberadamente distinto: un hospital chico de
localidad, con guardia y pocas camas, que deriva al grande. Dos hospitales
iguales no mostrarían para qué sirve una red.

    python manage.py seed_red
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Membresia, Usuario
from apps.casos import motor as motor_casos
from apps.casos.models import Caso
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.instituciones.models import Area, Box, Cama, Grupo, Institucion, Subarea
from apps.red import motor as motor_red
from apps.red.models import Red, Traslado
from apps.registros.models import Ciudadano

MOTIVOS = [
    (Traslado.Motivo.COMPLEJIDAD, "Requiere UTI, no disponible en el establecimiento."),
    (Traslado.Motivo.ESPECIALIDAD, "Sin traumatólogo de guardia."),
    (Traslado.Motivo.ESTUDIO, "Requiere tomografía; no hay equipo."),
    (Traslado.Motivo.CAMA, "Sin camas de internación disponibles."),
]


class Command(BaseCommand):
    help = "Agrega un segundo establecimiento y la red que lo une con el principal."

    def add_arguments(self, parser):
        parser.add_argument("--semilla", type=int, default=2026)

    @transaction.atomic
    def handle(self, *args, **opciones):
        random.seed(opciones["semilla"])

        principal = Institucion.objects.filter(nombre="Hospital Central").first()
        if principal is None:
            self.stderr.write("Falta el hospital principal. Corré `seed_guardia` primero.")
            return

        chico, _ = Institucion.objects.get_or_create(
            nombre="Hospital Municipal de Villa Real",
            defaults={"tipo": "Hospital de baja complejidad"},
        )
        guardia, _ = Area.objects.get_or_create(institucion=chico, nombre="Guardia")
        internacion, _ = Area.objects.get_or_create(institucion=chico, nombre="Internación")
        Box.objects.get_or_create(area=guardia, nombre="Consultorio 1")

        # Pocas camas: es la razón por la que deriva.
        sala, _ = Subarea.objects.get_or_create(area=internacion, nombre="Sala general")
        for i in range(1, 7):
            Cama.objects.get_or_create(
                area=internacion, nombre=f"S{i:02d}", defaults={"subarea": sala}
            )
        Cama.objects.filter(area=internacion).update(
            estado=Cama.Estado.LIBRE, caso=None, desde=None, motivo=""
        )

        def persona(email, nombre, apellido, rol, *areas):
            u, nuevo = Usuario.objects.get_or_create(
                email=email, defaults={"nombre": nombre, "apellido": apellido}
            )
            if nuevo:
                u.set_password("demo1234")
                u.save()
            m, _ = Membresia.objects.get_or_create(usuario=u, institucion=chico, rol=rol)
            m.activo = True
            m.save()
            if areas:
                m.areas.set(areas)
            return u

        med = persona("villa.med@hospital.gob.ar", "Silvina", "Roldán", Membresia.Rol.MEDICO, guardia)
        adm = persona("villa.adm@hospital.gob.ar", "Omar", "Britos",
                      Membresia.Rol.ADMINISTRATIVO, guardia)
        jefe = persona("villa.jefe@hospital.gob.ar", "Estela", "Vidal",
                       Membresia.Rol.JEFE_AREA, guardia, internacion)

        g, _ = Grupo.objects.get_or_create(area=guardia, nombre="Guardia de Villa Real")
        g.miembros.set([med, jefe])

        # Un flujo simple: la complejidad del diseñador ya se muestra en el
        # hospital grande; acá lo que importa es que pueda derivar.
        flujo, creado = Flujo.objects.get_or_create(
            institucion=chico, area=guardia, titulo="Atención en guardia",
            defaults={"descripcion": "Ingreso, atención y disposición."},
        )
        if creado or not flujo.versiones.exists():
            v = VersionFlujo.objects.create(
                flujo=flujo, numero=1, estado=VersionFlujo.Estado.PUBLICADA
            )
            ini = Nodo.objects.create(version=v, tipo=Nodo.Tipo.INICIO, titulo="Ingreso", x=60, y=180)
            at = Nodo.objects.create(version=v, tipo=Nodo.Tipo.ATENCION, titulo="Atención médica",
                                     x=300, y=180)
            fin = Nodo.objects.create(version=v, tipo=Nodo.Tipo.FIN, titulo="Alta", x=560, y=180)
            Conexion.objects.create(version=v, origen=ini, destino=at)
            Conexion.objects.create(version=v, origen=at, destino=fin)
            at.grupos.set([g])

        red, _ = Red.objects.get_or_create(
            nombre="Región Sanitaria VI",
            defaults={"descripcion": "Villa Real deriva al Hospital Central."},
        )
        red.instituciones.set([principal, chico])

        # --- Traslados: algunos resueltos y algunos esperando respuesta ------
        #
        # Los resueltos son los que dan los indicadores de la red —cuánto tarda
        # una respuesta, cuántos se rechazan—, y los pendientes son lo que hace
        # que la pantalla del hospital grande tenga algo que resolver. Con sólo
        # unos u otros, media pantalla queda vacía.
        Traslado.objects.filter(origen=chico).delete()
        version = flujo.versiones.filter(estado=VersionFlujo.Estado.PUBLICADA).first()
        area_destino = Area.objects.filter(institucion=principal, nombre="Internación").first()

        pacientes = list(Ciudadano.objects.filter(institucion=principal)[:14])
        hechos = {"pedidos": 0, "aceptados": 0, "rechazados": 0, "pendientes": 0}
        ahora = timezone.now()

        for i, ciud in enumerate(pacientes):
            # El paciente de Villa Real es la misma persona del padrón: en una
            # red el documento es lo que identifica, no el hospital.
            local, _ = Ciudadano.objects.get_or_create(
                institucion=chico, documento=ciud.documento or f"V{i:07d}",
                defaults={"nombre": ciud.nombre, "apellido": ciud.apellido},
            )
            caso = Caso.objects.create(institucion=chico, version=version, ciudadano=local,
                                       area_actual=guardia)
            motor_casos.iniciar(caso, autor=med)
            caso.refresh_from_db()

            motivo, detalle = random.choice(MOTIVOS)
            t = motor_red.solicitar(
                caso, principal, motivo, detalle=detalle,
                area_destino=area_destino, autor=med,
                urgente=random.random() < 0.3,
            )
            hechos["pedidos"] += 1

            # Los cuatro últimos quedan esperando respuesta.
            if i >= len(pacientes) - 4:
                hechos["pendientes"] += 1
                continue

            hace = ahora - timedelta(days=random.randint(1, 20), hours=random.randint(0, 20))
            Traslado.objects.filter(pk=t.pk).update(solicitado_at=hace)
            t.refresh_from_db()

            if random.random() < 0.78:
                motor_red.aceptar(t, autor=jefe, area_destino=area_destino)
                t.refresh_from_db()
                motor_red.marcar_en_camino(t, movil=f"Móvil {random.randint(1, 4)}", autor=adm)
                t.refresh_from_db()
                motor_red.marcar_recibido(t, autor=jefe)
                # Los tiempos se refechan para que los indicadores no salgan
                # todos en cero: el recorrido ocurre en segundos.
                Traslado.objects.filter(pk=t.pk).update(
                    resuelto_at=hace + timedelta(minutes=random.randint(8, 90)),
                    salida_at=hace + timedelta(minutes=random.randint(30, 120)),
                    llegada_at=hace + timedelta(minutes=random.randint(140, 260)),
                )
                hechos["aceptados"] += 1
            else:
                motor_red.rechazar(
                    t, random.choice([
                        "No hay camas de UTI disponibles.",
                        "El servicio está saturado; probar en otro efector.",
                    ]),
                    autor=jefe,
                )
                Traslado.objects.filter(pk=t.pk).update(
                    resuelto_at=hace + timedelta(minutes=random.randint(10, 120))
                )
                hechos["rechazados"] += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nRed «{red.nombre}» lista:\n"
            f"  {chico.nombre} (guardia + 6 camas) deriva a {principal.nombre}\n"
            f"  {hechos['pedidos']} traslados · {hechos['aceptados']} aceptados · "
            f"{hechos['rechazados']} rechazados · {hechos['pendientes']} esperando respuesta\n"
            f"  Entrar como: villa.med@hospital.gob.ar / villa.jefe@hospital.gob.ar (demo1234)\n"
        ))
