"""
Carga datos de demo: institución, áreas, un flujo publicado realista y varios
casos en distintos estados (usando el motor). Idempotente: se puede correr
varias veces sin duplicar.

    python manage.py seed_demo
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Membresia, Usuario
from apps.casos import motor
from apps.casos.models import Caso
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.formularios.models import Campo, Formulario
from apps.instituciones.models import Area, Institucion
from apps.registros.models import Ciudadano, HistoriaClinica


class Command(BaseCommand):
    help = "Carga datos de demostración (institución, flujo publicado y casos)."

    @transaction.atomic
    def handle(self, *args, **options):
        # Super admin de plataforma (ve todas las instituciones). Idempotente.
        admin, creado_admin = Usuario.objects.get_or_create(
            email="admin@cauce.local",
            defaults={"nombre": "Super", "apellido": "Admin", "is_staff": True, "is_superuser": True},
        )
        if creado_admin:
            admin.set_password("admin1234")
            admin.save()

        inst, _ = Institucion.objects.get_or_create(
            nombre="Hospital Central", defaults={"cuit": "30-12345678-9", "tipo": "Hospital general"}
        )
        if not inst.tipo:
            inst.tipo = "Hospital general"
            inst.save(update_fields=["tipo"])
        admision, _ = Area.objects.get_or_create(institucion=inst, nombre="Admisión")
        cardio, _ = Area.objects.get_or_create(institucion=inst, nombre="Cardiología")
        Area.objects.get_or_create(institucion=inst, nombre="Asistencia social")
        # Datos de la ficha (responsable / descripción) + sub-áreas para el árbol.
        cardio.responsable = "Dra. Laura Méndez"
        cardio.descripcion = "Diagnóstico y tratamiento cardiovascular."
        cardio.save(update_fields=["responsable", "descripcion"])
        from apps.instituciones.models import Subarea
        Subarea.objects.get_or_create(area=cardio, nombre="Hemodinamia")
        Subarea.objects.get_or_create(area=cardio, nombre="Consultorios externos")

        # Otras instituciones del directorio (para el super admin).
        def inst_demo(nombre, tipo, n_areas, estado):
            i, _ = Institucion.objects.get_or_create(nombre=nombre)
            i.tipo, i.estado = tipo, estado
            i.save(update_fields=["tipo", "estado"])
            for n in range(n_areas):
                Area.objects.get_or_create(institucion=i, nombre=f"Área {n + 1}")
            return i

        inst_demo("Centro de Salud Norte", "Centro de salud", 4, Institucion.Estado.ACTIVA)
        inst_demo("Hospital Pediátrico San Juan", "Hospital pediátrico", 6, Institucion.Estado.ACTIVA)
        inst_demo("Centro de Atención Sur", "Centro de salud", 3, Institucion.Estado.EN_ALTA)

        # Usuario administrativo de demo.
        op, creado = Usuario.objects.get_or_create(
            email="operador@cauce.local",
            defaults={"nombre": "Carla", "apellido": "Ibáñez"},
        )
        if creado:
            op.set_password("demo1234")
            op.save()
        m_op, _ = Membresia.objects.get_or_create(
            usuario=op, institucion=inst, rol=Membresia.Rol.ADMINISTRATIVO
        )
        m_op.areas.add(admision)

        # Staff de demo (para Administración / Legajo / Estructura).
        asistencia = Area.objects.get(institucion=inst, nombre="Asistencia social")
        sistemas, _ = Area.objects.get_or_create(institucion=inst, nombre="Sistemas")
        R = Membresia.Rol

        def staff(email, nombre, apellido, roles, area, activo=True):
            u, creado = Usuario.objects.get_or_create(
                email=email, defaults={"nombre": nombre, "apellido": apellido}
            )
            if creado:
                u.set_password("demo1234")
            u.is_active = activo
            u.save()
            for rol in roles:
                mem, _ = Membresia.objects.get_or_create(usuario=u, institucion=inst, rol=rol)
                if area:
                    mem.areas.add(area)
            return u

        staff("m.diaz@hospital.gob.ar", "Martín", "Díaz", [R.CONFIGURADOR], admision)
        jperez = staff("j.perez@hospital.gob.ar", "Juan", "Pérez", [R.MEDICO], cardio)
        # Juan Pérez es médico también en Admisión (firma la atención del ingreso).
        Membresia.objects.get(usuario=jperez, institucion=inst, rol=R.MEDICO).areas.add(admision)
        # Limpia un eventual rol administrativo previo (en bases ya sembradas).
        Membresia.objects.filter(usuario=jperez, institucion=inst, rol=R.ADMINISTRATIVO).delete()
        staff("l.romero@hospital.gob.ar", "Lucía", "Romero", [R.ADMINISTRATIVO], asistencia)
        staff("a.gomez@hospital.gob.ar", "Ana", "Gómez", [R.ADMIN_INSTITUCION], sistemas)
        rsosa = staff("r.sosa@hospital.gob.ar", "Ricardo", "Sosa", [R.CONFIGURADOR, R.ADMINISTRATIVO], cardio)
        staff("s.funes@hospital.gob.ar", "Sofía", "Funes", [R.ADMINISTRATIVO], admision, activo=False)

        # Legajos profesionales (especialidad / matrícula).
        from apps.accounts.models import LegajoProfesional
        LegajoProfesional.objects.update_or_create(usuario=jperez, defaults={"especialidad": "Cardiología", "matricula": "98.214"})
        LegajoProfesional.objects.update_or_create(usuario=rsosa, defaults={"especialidad": "Clínica médica", "matricula": "72.330"})

        # Formulario de datos del paciente.
        form, creado = Formulario.objects.get_or_create(
            institucion=inst, titulo="Datos del paciente"
        )
        if creado:
            Campo.objects.create(formulario=form, label="Nombre", tipo=Campo.Tipo.TEXTO_CORTO, requerido=True, orden=0)
            Campo.objects.create(formulario=form, label="Obra social", tipo=Campo.Tipo.SELECCION_UNICA,
                                 opciones=["OSDE", "Swiss Medical", "PAMI", "Particular"], orden=1)
            Campo.objects.create(formulario=form, label="Prioridad", tipo=Campo.Tipo.SELECCION_UNICA,
                                 opciones=["Normal", "Alta"], requerido=True, orden=2)
            Campo.objects.create(formulario=form, label="Motivo de consulta", tipo=Campo.Tipo.TEXTO_LARGO, orden=3)
        campo_prioridad = form.campos.get(label="Prioridad")

        # Flujo "Atención cardiológica": destino de la derivación del ingreso.
        # Se crea primero para poder referenciarlo desde el nodo «Derivar».
        flujo_cardio, _ = Flujo.objects.get_or_create(institucion=inst, area=cardio, titulo="Atención cardiológica")
        Caso.objects.filter(version__flujo=flujo_cardio).delete()
        flujo_cardio.versiones.all().delete()
        ver_cardio = VersionFlujo.objects.create(flujo=flujo_cardio, numero=1)
        c_inicio = Nodo.objects.create(version=ver_cardio, tipo=Nodo.Tipo.INICIO, titulo="Inicio", x=60, y=160)
        c_aten = Nodo.objects.create(version=ver_cardio, tipo=Nodo.Tipo.ATENCION, titulo="Consulta cardiológica", x=300, y=160)
        c_fin = Nodo.objects.create(version=ver_cardio, tipo=Nodo.Tipo.FIN, titulo="Cierre", x=540, y=160)
        Conexion.objects.create(version=ver_cardio, origen=c_inicio, destino=c_aten)
        Conexion.objects.create(version=ver_cardio, origen=c_aten, destino=c_fin)
        if motor.puede_publicar(ver_cardio):
            ver_cardio.estado = VersionFlujo.Estado.PUBLICADA
            ver_cardio.save()

        # Flujo "Ingreso de paciente" (recreado limpio para que el seed sea estable).
        flujo, _ = Flujo.objects.get_or_create(institucion=inst, area=admision, titulo="Ingreso de paciente")
        # Los casos referencian la versión con on_delete=PROTECT: borrarlos primero.
        Caso.objects.filter(version__flujo=flujo).delete()
        flujo.versiones.all().delete()
        ver = VersionFlujo.objects.create(flujo=flujo, numero=1)

        def N(tipo, titulo, x, y, **kw):
            return Nodo.objects.create(version=ver, tipo=tipo, titulo=titulo, x=x, y=y, **kw)

        n_inicio = N(Nodo.Tipo.INICIO, "Inicio", 60, 200)
        n_form = N(Nodo.Tipo.FORMULARIO, "Datos del paciente", 280, 200, formulario=form)
        n_dec = N(Nodo.Tipo.DECISION, "¿prioridad?", 520, 200)
        n_derivar = N(Nodo.Tipo.DERIVAR, "Derivar a Cardiología", 760, 90,
                      config={"area_destino_id": cardio.id, "flujo_destino_id": flujo_cardio.id})
        n_espera = N(Nodo.Tipo.ESPERA_FILA, "Sala de admisión", 760, 320)
        n_atencion = N(Nodo.Tipo.ATENCION, "Evaluación inicial", 1000, 320)
        n_estado = N(Nodo.Tipo.ESTADO, "Atendido", 1000, 90, config={"estado": Caso.Estado.ATENDIDO})
        n_fin = N(Nodo.Tipo.FIN, "Cierre", 1240, 200)

        def C(o, d, **kw):
            Conexion.objects.create(version=ver, origen=o, destino=d, **kw)

        C(n_inicio, n_form)
        C(n_form, n_dec)
        C(n_dec, n_derivar, etiqueta="Alta", condicion={"campo": campo_prioridad.id, "operador": "=", "valor": "Alta"})
        C(n_dec, n_espera, etiqueta="Normal")
        C(n_derivar, n_estado)
        C(n_estado, n_fin)
        C(n_espera, n_atencion)
        C(n_atencion, n_fin)

        # Publicar la versión (valida primero).
        if motor.puede_publicar(ver):
            VersionFlujo.objects.filter(flujo=flujo, estado=VersionFlujo.Estado.PUBLICADA).exclude(pk=ver.pk).update(
                estado=VersionFlujo.Estado.REEMPLAZADA
            )
            ver.estado = VersionFlujo.Estado.PUBLICADA
            ver.save()

        # Ciudadanos.
        c1, _ = Ciudadano.objects.get_or_create(institucion=inst, documento="27418305",
                                                defaults={"nombre": "María", "apellido": "González", "obra_social": "OSDE"})
        c2, _ = Ciudadano.objects.get_or_create(institucion=inst, documento="18902551",
                                                defaults={"nombre": "Juan", "apellido": "Pérez", "obra_social": "PAMI"})
        c3, _ = Ciudadano.objects.get_or_create(institucion=inst, documento="33120778",
                                                defaults={"nombre": "Carlos", "apellido": "Vidal", "obra_social": "Swiss Medical"})

        def nuevo(ciud, prioridad=Caso.Prioridad.NORMAL, asignar=False):
            caso = Caso.objects.create(institucion=inst, version=ver, ciudadano=ciud, prioridad=prioridad)
            if asignar:
                caso.asignado_a = op
                caso.save(update_fields=["asignado_a"])
            return caso

        # Caso A: recién creado, sin asignar, sin iniciar.
        nuevo(c2)

        # Caso B: asignado al operador, parado en el formulario.
        cb = nuevo(c1, asignar=True)
        motor.iniciar(cb, autor=op)

        # Caso C: prioridad normal → quedó en la fila de espera.
        cc = nuevo(c3, asignar=True)
        motor.iniciar(cc, autor=op)
        motor.avanzar(cc, {"valores": {campo_prioridad.id: "Normal", form.campos.get(label="Nombre").id: "Carlos Vidal"}}, autor=op)

        # Caso D: recorrido completo (fila → atención → cierre) para poblar la HC.
        cd = nuevo(c1, asignar=True)
        motor.iniciar(cd, autor=op)
        motor.avanzar(cd, {"valores": {campo_prioridad.id: "Normal", form.campos.get(label="Nombre").id: "María González"}}, autor=op)
        motor.avanzar(cd, {}, autor=op)  # llamado desde la fila → Atención
        # La atención la firma un médico (Juan Pérez), no el administrativo.
        motor.avanzar(cd, {"titulo": "Evaluación inicial", "contenido": "Paciente estable, dolor torácico leve.", "firmada": True}, autor=jperez)

        # Antecedentes en la HC de María (para la tarjeta de solo lectura en ejecución).
        hc, _ = HistoriaClinica.objects.get_or_create(ciudadano=c1)
        hc.alergias = "Penicilina"
        hc.condiciones = "Hipertensión arterial (crónica)"
        hc.save(update_fields=["alergias", "condiciones"])

        self.stdout.write(self.style.SUCCESS(
            "Demo cargada: institución «Hospital Central», flujo «Ingreso de paciente» publicado y 3 casos.\n"
            "Super admin (ve todo): admin@cauce.local / admin1234\n"
            "Administrativo:         operador@cauce.local / demo1234"
        ))
