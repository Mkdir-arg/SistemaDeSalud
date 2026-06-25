"""
Carga el ESCENARIO DE GUARDIA completo (ver docs/ESCENARIO-GUARDIA.md):

  Hospital + áreas Guardia / Traumatología / Cardiología / Salud mental,
  staff (médico + administrativo por área), grupos por área, y los flujos:

    - Ingreso a Guardia: Inicio → Form → Decisión → Derivar a {Trauma|Cardio|SM}
    - Atención <especialidad>: Inicio → Form → Solicitud de estudios → Atención → Fin

  Los nodos de trabajo quedan asignados a los grupos responsables (quién hace qué),
  así el circuito de bandejas filtra por equipo.

Idempotente: se puede correr varias veces. Recrea los grafos de los flujos.

    python manage.py seed_guardia
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Membresia, Usuario
from apps.casos import motor
from apps.casos.models import Caso
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.formularios.models import Campo, Formulario
from apps.instituciones.models import Area, Box, Grupo


class Command(BaseCommand):
    help = "Carga el escenario de guardia (hospital, áreas, staff, grupos y flujos)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--si-vacio", action="store_true",
            help="Sembrar solo si no hay ninguna institución (no toca datos existentes).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from apps.instituciones.models import Institucion
        if options["si_vacio"] and Institucion.objects.exists():
            self.stdout.write("Ya hay datos cargados; se omite el sembrado.")
            return

        R = Membresia.Rol

        # --- Super admin (para poder entrar) -------------------------------
        admin, creado = Usuario.objects.get_or_create(
            email="admin@cauce.local",
            defaults={"nombre": "Super", "apellido": "Admin", "is_staff": True, "is_superuser": True},
        )
        admin.is_staff = admin.is_superuser = admin.is_active = True
        admin.set_password("admin1234")
        admin.save()

        # --- Institución y áreas -------------------------------------------
        inst, _ = Institucion.objects.get_or_create(
            nombre="Hospital Central", defaults={"tipo": "Hospital general", "cuit": "30-12345678-9"}
        )
        guardia, _ = Area.objects.get_or_create(institucion=inst, nombre="Guardia")
        trauma, _ = Area.objects.get_or_create(institucion=inst, nombre="Traumatología")
        cardio, _ = Area.objects.get_or_create(institucion=inst, nombre="Cardiología")
        salud_mental, _ = Area.objects.get_or_create(institucion=inst, nombre="Salud mental")
        imagenes, _ = Area.objects.get_or_create(institucion=inst, nombre="Diagnóstico por imágenes")

        # --- Staff: 1 médico + 1 administrativo por área -------------------
        def persona(email, nombre, apellido, rol, area):
            u, nuevo = Usuario.objects.get_or_create(email=email, defaults={"nombre": nombre, "apellido": apellido})
            if nuevo:
                u.set_password("demo1234")
                u.save()
            mem, _ = Membresia.objects.get_or_create(usuario=u, institucion=inst, rol=rol)
            mem.areas.add(area)
            return u

        med_guardia = persona("guardia.med@hospital.gob.ar", "Hernán", "Ruiz", R.MEDICO, guardia)
        adm_guardia = persona("guardia.adm@hospital.gob.ar", "Carla", "Ibáñez", R.ADMINISTRATIVO, guardia)
        med_trauma = persona("trauma.med@hospital.gob.ar", "Pablo", "Vega", R.MEDICO, trauma)
        adm_trauma = persona("trauma.adm@hospital.gob.ar", "Marta", "Ríos", R.ADMINISTRATIVO, trauma)
        med_cardio = persona("cardio.med@hospital.gob.ar", "Laura", "Méndez", R.MEDICO, cardio)
        adm_cardio = persona("cardio.adm@hospital.gob.ar", "Diego", "Salas", R.ADMINISTRATIVO, cardio)
        med_sm = persona("sm.med@hospital.gob.ar", "Sofía", "Bravo", R.MEDICO, salud_mental)
        adm_sm = persona("sm.adm@hospital.gob.ar", "Nadia", "Coll", R.ADMINISTRATIVO, salud_mental)
        med_img = persona("img.med@hospital.gob.ar", "Tomás", "Leiva", R.MEDICO, imagenes)

        # --- Grupos por área (equipos) -------------------------------------
        def grupo(area, nombre, *miembros):
            g, _ = Grupo.objects.get_or_create(area=area, nombre=nombre)
            g.miembros.set(miembros)
            return g

        g_med_guardia = grupo(guardia, "Médicos de guardia", med_guardia)
        g_adm_guardia = grupo(guardia, "Admin. de guardia", adm_guardia)
        g_med_trauma = grupo(trauma, "Médicos trauma", med_trauma)
        g_adm_trauma = grupo(trauma, "Admin. trauma", adm_trauma)
        g_med_cardio = grupo(cardio, "Médicos cardio", med_cardio)
        g_adm_cardio = grupo(cardio, "Admin. cardio", adm_cardio)
        g_med_sm = grupo(salud_mental, "Profesionales SM", med_sm)
        g_adm_sm = grupo(salud_mental, "Admin. SM", adm_sm)
        g_med_img = grupo(imagenes, "Técnicos de imágenes", med_img)

        # --- Boxes / consultorios por especialidad -------------------------
        for area in (trauma, cardio, salud_mental):
            for n in (1, 2):
                Box.objects.get_or_create(area=area, nombre=f"Box {n}")

        # --- Formularios ----------------------------------------------------
        def formulario(titulo, campos):
            form, nuevo = Formulario.objects.get_or_create(institucion=inst, titulo=titulo)
            if nuevo:
                for orden, (label, tipo, opciones, req) in enumerate(campos):
                    Campo.objects.create(formulario=form, label=label, tipo=tipo,
                                         opciones=opciones or [], requerido=req, orden=orden)
            return form

        T = Campo.Tipo
        form_ingreso = formulario("Datos de ingreso", [
            ("Nombre del paciente", T.TEXTO_CORTO, None, True),
            ("Motivo de consulta", T.TEXTO_LARGO, None, False),
            ("Especialidad", T.SELECCION_UNICA, ["Traumatología", "Cardiología", "Salud mental"], True),
        ])
        campo_esp = form_ingreso.campos.get(label="Especialidad")

        form_trauma = formulario("Evaluación traumatológica", [
            ("Zona afectada", T.TEXTO_CORTO, None, True),
            ("Mecanismo de lesión", T.TEXTO_LARGO, None, False),
            ("Dolor", T.SELECCION_UNICA, ["Leve", "Moderado", "Severo"], False),
        ])
        form_cardio = formulario("Evaluación cardiológica", [
            ("Síntoma principal", T.TEXTO_CORTO, None, True),
            ("Dolor torácico", T.SELECCION_UNICA, ["Sí", "No"], True),
            ("Antecedentes", T.TEXTO_LARGO, None, False),
        ])
        form_sm = formulario("Evaluación de salud mental", [
            ("Motivo", T.TEXTO_LARGO, None, True),
            ("Nivel de riesgo", T.SELECCION_UNICA, ["Bajo", "Medio", "Alto"], True),
        ])

        # --- Flujo de especialidad (Form → Solicitud estudios → Atención) ---
        def flujo_especialidad(area, titulo, form, g_adm, g_med):
            flujo, _ = Flujo.objects.get_or_create(institucion=inst, area=area, titulo=titulo)
            Caso.objects.filter(version__flujo=flujo).delete()
            flujo.versiones.all().delete()
            ver = VersionFlujo.objects.create(flujo=flujo, numero=1)
            # Los flujos de especialidad solo reciben casos por derivación.
            ini = Nodo.objects.create(version=ver, tipo=Nodo.Tipo.INICIO, titulo="Inicio", x=60, y=180, config={"origen": "derivado"})
            frm = Nodo.objects.create(version=ver, tipo=Nodo.Tipo.FORMULARIO, titulo=form.titulo, x=300, y=180, formulario=form)
            # Un solo nodo «Atención con fila»: el paciente espera, el médico lo llama
            # desde su box y lo atiende. Los estudios se piden dentro de la atención.
            ate = Nodo.objects.create(version=ver, tipo=Nodo.Tipo.ATENCION, titulo="Atención", x=560, y=180, config={"con_fila": True})
            fin = Nodo.objects.create(version=ver, tipo=Nodo.Tipo.FIN, titulo="Cierre", x=820, y=180)
            Conexion.objects.create(version=ver, origen=ini, destino=frm)
            Conexion.objects.create(version=ver, origen=frm, destino=ate)
            Conexion.objects.create(version=ver, origen=ate, destino=fin)
            # Quién hace qué: el form lo carga el administrativo; la fila/llamado y
            # la atención las maneja el médico (llama desde su box y atiende).
            frm.grupos.set([g_adm.id])
            ate.grupos.set([g_med.id])
            if motor.puede_publicar(ver):
                ver.estado = VersionFlujo.Estado.PUBLICADA
                ver.save()
            return flujo

        f_trauma = flujo_especialidad(trauma, "Atención traumatológica", form_trauma, g_adm_trauma, g_med_trauma)
        f_cardio = flujo_especialidad(cardio, "Atención cardiológica", form_cardio, g_adm_cardio, g_med_cardio)
        f_sm = flujo_especialidad(salud_mental, "Atención en salud mental", form_sm, g_adm_sm, g_med_sm)

        # --- Flujo de estudios (Imágenes): recibe la derivación y devuelve --
        f_img, _ = Flujo.objects.get_or_create(institucion=inst, area=imagenes, titulo="Realizar estudio")
        Caso.objects.filter(version__flujo=f_img).delete()
        f_img.versiones.all().delete()
        v_img = VersionFlujo.objects.create(flujo=f_img, numero=1)
        i_ini = Nodo.objects.create(version=v_img, tipo=Nodo.Tipo.INICIO, titulo="Inicio", x=60, y=180, config={"origen": "derivado"})
        i_ate = Nodo.objects.create(version=v_img, tipo=Nodo.Tipo.ATENCION, titulo="Informe del estudio", x=300, y=180)
        i_fin = Nodo.objects.create(version=v_img, tipo=Nodo.Tipo.FIN, titulo="Estudio realizado", x=560, y=180)
        Conexion.objects.create(version=v_img, origen=i_ini, destino=i_ate)
        Conexion.objects.create(version=v_img, origen=i_ate, destino=i_fin)
        i_ate.grupos.set([g_med_img.id])
        if motor.puede_publicar(v_img):
            v_img.estado = VersionFlujo.Estado.PUBLICADA
            v_img.save()

        # --- Flujo de ingreso a guardia (con la decisión + 3 derivaciones) --
        f_ing, _ = Flujo.objects.get_or_create(institucion=inst, area=guardia, titulo="Ingreso a Guardia")
        Caso.objects.filter(version__flujo=f_ing).delete()
        f_ing.versiones.all().delete()
        ver = VersionFlujo.objects.create(flujo=f_ing, numero=1)

        def N(tipo, titulo, x, y, **kw):
            return Nodo.objects.create(version=ver, tipo=tipo, titulo=titulo, x=x, y=y, **kw)

        n_ini = N(Nodo.Tipo.INICIO, "Inicio", 60, 240, config={"origen": "manual"})  # puerta de entrada manual
        n_form = N(Nodo.Tipo.FORMULARIO, "Datos de ingreso", 280, 240, formulario=form_ingreso)
        n_dec = N(Nodo.Tipo.DECISION, "¿Especialidad?", 520, 240)
        n_d_trauma = N(Nodo.Tipo.DERIVAR, "Derivar a Traumatología", 760, 80,
                       config={"area_destino_id": trauma.id, "flujo_destino_id": f_trauma.id})
        n_d_cardio = N(Nodo.Tipo.DERIVAR, "Derivar a Cardiología", 760, 240,
                       config={"area_destino_id": cardio.id, "flujo_destino_id": f_cardio.id})
        n_d_sm = N(Nodo.Tipo.DERIVAR, "Derivar a Salud mental", 760, 400,
                   config={"area_destino_id": salud_mental.id, "flujo_destino_id": f_sm.id})
        n_fin = N(Nodo.Tipo.FIN, "Ingreso cerrado", 1020, 240)

        def C(o, d, **kw):
            Conexion.objects.create(version=ver, origen=o, destino=d, **kw)

        C(n_ini, n_form)
        C(n_form, n_dec)
        C(n_dec, n_d_trauma, etiqueta="Traumatología",
          condicion={"campo": campo_esp.id, "operador": "=", "valor": "Traumatología"})
        C(n_dec, n_d_cardio, etiqueta="Cardiología",
          condicion={"campo": campo_esp.id, "operador": "=", "valor": "Cardiología"})
        C(n_dec, n_d_sm, etiqueta="Salud mental")  # rama por defecto
        C(n_d_trauma, n_fin)
        C(n_d_cardio, n_fin)
        C(n_d_sm, n_fin)

        # El triage de ingreso lo opera la guardia (médicos y administrativos).
        n_form.grupos.set([g_adm_guardia.id, g_med_guardia.id])

        if motor.puede_publicar(ver):
            ver.estado = VersionFlujo.Estado.PUBLICADA
            ver.save()

        self.stdout.write(self.style.SUCCESS(
            "Escenario de guardia cargado en «Hospital Central».\n"
            "  Áreas: Guardia, Traumatología, Cardiología, Salud mental (con staff y grupos).\n"
            "  Flujos publicados: Ingreso a Guardia + 3 de especialidad (con derivaciones).\n"
            "Accesos (contraseña demo1234, salvo el admin):\n"
            "  admin@cauce.local / admin1234   (super admin)\n"
            "  guardia.adm@hospital.gob.ar      (administrativo de guardia → arranca el ingreso)\n"
            "  trauma.med@hospital.gob.ar / cardio.med@... / sm.med@...  (médicos de cada especialidad)"
        ))
