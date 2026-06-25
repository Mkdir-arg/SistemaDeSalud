"""
Carga el ESCENARIO DE GUARDIA completo y realista (ver docs/ESCENARIO-GUARDIA.md).

Modela una guardia hospitalaria con triage tipo Manchester y los circuitos que
salen de ella: especialidades, estudios (laboratorio / imágenes) con ida y
vuelta, interconsultas e internación.

  Áreas:  Guardia · Traumatología · Cardiología · Salud mental · Neurología ·
          Diagnóstico por imágenes · Laboratorio · Internación (Clínica médica)

  Flujo central — «Ingreso a Guardia» (entrada manual):
    Inicio → Admisión administrativa → Triage de enfermería →
      ¿Nivel de triage?  ── Rojo ─────────────→ Shock Room (atención inmediata)
                         └─ resto ──→ Sala de espera (atención con fila)
    → Conducta médica → ¿Conducta?
        ├─ Alta ─────────────────→ Alta de guardia (fin)
        ├─ Internación ──────────→ deriva a Internación
        ├─ Observación ──────────→ espera y reevalúa (loop)
        └─ Derivar ─→ ¿Especialidad? → deriva a Trauma / Cardio / SM / Neuro

  Flujos de especialidad (reciben la derivación):
    Inicio → Atención con fila → Conducta → ¿Disposición? → {Alta | Internación}
    (durante la atención el médico pide estudios, recetas o interconsultas).

  Estudios (ida y vuelta):  Laboratorio e Imágenes reciben el sub-caso, cargan
    el resultado y lo devuelven al médico que lo pidió.

  Internación:  Inicio → Asignar cama → Evolución → Conducta →
    {Continúa internado (loop) | Alta médica}.

Los nodos de trabajo quedan asignados a los grupos responsables (quién hace qué),
así el circuito de bandejas y filas filtra por equipo.

Idempotente: borra los flujos/formularios/casos de la institución y los recrea.

    python manage.py seed_guardia
    python manage.py seed_guardia --si-vacio   # solo si no hay instituciones
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Membresia, Usuario
from apps.casos import motor
from apps.casos.models import Caso
from apps.flujos.models import Conexion, Flujo, Nodo, VersionFlujo
from apps.formularios.models import Campo, Formulario
from apps.instituciones.models import Area, Box, Grupo, Institucion


class Command(BaseCommand):
    help = "Carga el escenario de guardia realista (hospital, áreas, staff, grupos y flujos)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--si-vacio", action="store_true",
            help="Sembrar solo si no hay ninguna institución (no toca datos existentes).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["si_vacio"] and Institucion.objects.exists():
            self.stdout.write("Ya hay datos cargados; se omite el sembrado.")
            return

        R = Membresia.Rol
        T = Campo.Tipo
        NT = Nodo.Tipo

        # --- Super admin (para poder entrar) -------------------------------
        admin, _ = Usuario.objects.get_or_create(
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

        # Borrón y cuenta nueva de los FLUJOS (y lo que cuelga de ellos). Las
        # áreas, el staff, los grupos y los boxes se conservan (get_or_create).
        Caso.objects.filter(institucion=inst).delete()
        Flujo.objects.filter(institucion=inst).delete()
        Formulario.objects.filter(institucion=inst).delete()

        def area(nombre):
            a, _ = Area.objects.get_or_create(institucion=inst, nombre=nombre)
            return a

        guardia = area("Guardia")
        trauma = area("Traumatología")
        cardio = area("Cardiología")
        salud_mental = area("Salud mental")
        neuro = area("Neurología")
        imagenes = area("Diagnóstico por imágenes")
        laboratorio = area("Laboratorio")
        internacion = area("Internación")

        # --- Staff ----------------------------------------------------------
        def persona(email, nombre, apellido, rol, *areas):
            u, nuevo = Usuario.objects.get_or_create(
                email=email, defaults={"nombre": nombre, "apellido": apellido}
            )
            if nuevo:
                u.set_password("demo1234")
                u.save()
            mem, _ = Membresia.objects.get_or_create(usuario=u, institucion=inst, rol=rol)
            mem.areas.add(*areas)
            return u

        # Guardia: admisión, enfermería de triage y médicos.
        adm_guardia = persona("guardia.adm@hospital.gob.ar", "Carla", "Ibáñez", R.ADMINISTRATIVO, guardia)
        enf_guardia = persona("guardia.enf@hospital.gob.ar", "Roxana", "Páez", R.ADMINISTRATIVO, guardia)
        med_guardia = persona("guardia.med@hospital.gob.ar", "Hernán", "Ruiz", R.MEDICO, guardia)
        # Especialidades: 1 administrativo + 1 médico por área.
        adm_trauma = persona("trauma.adm@hospital.gob.ar", "Marta", "Ríos", R.ADMINISTRATIVO, trauma)
        med_trauma = persona("trauma.med@hospital.gob.ar", "Pablo", "Vega", R.MEDICO, trauma)
        adm_cardio = persona("cardio.adm@hospital.gob.ar", "Diego", "Salas", R.ADMINISTRATIVO, cardio)
        med_cardio = persona("cardio.med@hospital.gob.ar", "Laura", "Méndez", R.MEDICO, cardio)
        adm_sm = persona("sm.adm@hospital.gob.ar", "Nadia", "Coll", R.ADMINISTRATIVO, salud_mental)
        med_sm = persona("sm.med@hospital.gob.ar", "Sofía", "Bravo", R.MEDICO, salud_mental)
        med_neuro = persona("neuro.med@hospital.gob.ar", "Elena", "Castro", R.MEDICO, neuro)
        # Servicios de apoyo (estudios e internación).
        med_img = persona("img.med@hospital.gob.ar", "Tomás", "Leiva", R.MEDICO, imagenes)
        med_lab = persona("lab.med@hospital.gob.ar", "Andrés", "Sosa", R.MEDICO, laboratorio)
        adm_int = persona("int.adm@hospital.gob.ar", "Paula", "Núñez", R.ADMINISTRATIVO, internacion)
        med_int = persona("int.med@hospital.gob.ar", "Gabriel", "Ferro", R.MEDICO, internacion)

        # --- Grupos por área (equipos) -------------------------------------
        def grupo(area, nombre, *miembros):
            g, _ = Grupo.objects.get_or_create(area=area, nombre=nombre)
            g.miembros.set(miembros)
            return g

        g_adm_guardia = grupo(guardia, "Admisión de guardia", adm_guardia)
        g_enf_guardia = grupo(guardia, "Enfermería de triage", enf_guardia)
        g_med_guardia = grupo(guardia, "Médicos de guardia", med_guardia)
        g_adm_trauma = grupo(trauma, "Admin. trauma", adm_trauma)
        g_med_trauma = grupo(trauma, "Médicos trauma", med_trauma)
        g_adm_cardio = grupo(cardio, "Admin. cardio", adm_cardio)
        g_med_cardio = grupo(cardio, "Médicos cardio", med_cardio)
        g_adm_sm = grupo(salud_mental, "Admin. SM", adm_sm)
        g_med_sm = grupo(salud_mental, "Profesionales SM", med_sm)
        g_med_neuro = grupo(neuro, "Médicos neuro", med_neuro)
        g_med_img = grupo(imagenes, "Técnicos de imágenes", med_img)
        g_med_lab = grupo(laboratorio, "Bioquímicos", med_lab)
        g_adm_int = grupo(internacion, "Admisión internación", adm_int)
        g_med_int = grupo(internacion, "Médicos de planta", med_int)

        # --- Boxes / consultorios ------------------------------------------
        for nombre in ("Consultorio 1", "Consultorio 2"):
            Box.objects.get_or_create(area=guardia, nombre=nombre)
        for ar in (trauma, cardio, salud_mental, neuro):
            for n in (1, 2):
                Box.objects.get_or_create(area=ar, nombre=f"Box {n}")

        # --- Formularios ----------------------------------------------------
        def formulario(titulo, area, campos):
            form = Formulario.objects.create(institucion=inst, area=area, titulo=titulo)
            for orden, (label, tipo, opciones, req) in enumerate(campos):
                Campo.objects.create(formulario=form, label=label, tipo=tipo,
                                     opciones=opciones or [], requerido=req, orden=orden)
            return form

        NIVELES_TRIAGE = [
            "Rojo - Emergencia", "Naranja - Muy urgente", "Amarillo - Urgente",
            "Verde - Poco urgente", "Azul - No urgente",
        ]

        form_admision = formulario("Admisión administrativa", guardia, [
            ("Motivo de consulta", T.TEXTO_LARGO, None, True),
            ("Forma de llegada", T.SELECCION_UNICA, ["Ambulancia", "Por sus medios", "Derivado de otro centro"], False),
            ("Obra social / cobertura", T.TEXTO_CORTO, None, False),
            ("Acompañante", T.TEXTO_CORTO, None, False),
        ])
        form_triage = formulario("Triage de enfermería", guardia, [
            ("Tensión arterial", T.TEXTO_CORTO, None, False),
            ("Frecuencia cardíaca", T.TEXTO_CORTO, None, False),
            ("Temperatura", T.TEXTO_CORTO, None, False),
            ("Saturación de O₂", T.TEXTO_CORTO, None, False),
            ("Escala de dolor", T.SELECCION_UNICA, ["Sin dolor", "Leve", "Moderado", "Severo"], False),
            ("Nivel de triage", T.SELECCION_UNICA, NIVELES_TRIAGE, True),
            ("Observaciones de enfermería", T.TEXTO_LARGO, None, False),
        ])
        form_conducta_g = formulario("Conducta médica de guardia", guardia, [
            ("Diagnóstico presuntivo", T.TEXTO_LARGO, None, True),
            ("Conducta", T.SELECCION_UNICA,
             ["Alta", "Derivar a especialidad", "Internación", "Observación"], True),
            ("Especialidad de derivación", T.SELECCION_UNICA,
             ["Traumatología", "Cardiología", "Salud mental", "Neurología"], False),
        ])

        # Conducta por especialidad (diagnóstico + un dato clínico + disposición).
        def form_conducta_esp(titulo, area, campo_clinico):
            return formulario(titulo, area, [
                ("Diagnóstico", T.TEXTO_LARGO, None, True),
                campo_clinico,
                ("Disposición", T.SELECCION_UNICA, ["Alta", "Internación"], True),
            ])

        form_cond_trauma = form_conducta_esp(
            "Conducta traumatológica", trauma,
            ("¿Requiere cirugía?", T.SELECCION_UNICA, ["No", "Sí - programada", "Sí - urgente"], False))
        form_cond_cardio = form_conducta_esp(
            "Conducta cardiológica", cardio,
            ("Riesgo cardiovascular", T.SELECCION_UNICA, ["Bajo", "Moderado", "Alto"], False))
        form_cond_sm = form_conducta_esp(
            "Conducta en salud mental", salud_mental,
            ("Nivel de riesgo", T.SELECCION_UNICA, ["Bajo", "Medio", "Alto"], False))
        form_cond_neuro = form_conducta_esp(
            "Conducta neurológica", neuro,
            ("Déficit focal", T.SELECCION_UNICA, ["No", "Sí"], False))

        form_lab = formulario("Toma de muestra", laboratorio, [
            ("Tipo de muestra", T.SELECCION_UNICA, ["Sangre", "Orina", "Hisopado", "Otra"], True),
            ("Observaciones", T.TEXTO_LARGO, None, False),
        ])
        form_img = formulario("Recepción de imágenes", imagenes, [
            ("Estudio a realizar", T.TEXTO_CORTO, None, True),
            ("Preparación", T.SELECCION_UNICA, ["Ninguna", "Ayuno", "Contraste"], False),
        ])
        form_cama = formulario("Asignación de cama", internacion, [
            ("Sector", T.SELECCION_UNICA, ["Clínica médica", "Terapia intensiva", "Unidad coronaria"], True),
            ("Cama", T.TEXTO_CORTO, None, True),
            ("Médico de cabecera", T.TEXTO_CORTO, None, False),
        ])
        form_evol = formulario("Evolución diaria", internacion, [
            ("Evolución", T.TEXTO_LARGO, None, True),
            ("Decisión", T.SELECCION_UNICA, ["Continúa internado", "Alta médica"], True),
        ])

        # --- Utilidades de construcción de grafos --------------------------
        def nueva_version(area, titulo):
            flujo = Flujo.objects.create(institucion=inst, area=area, titulo=titulo)
            return VersionFlujo.objects.create(flujo=flujo, numero=1), flujo

        def publicar(ver):
            if motor.puede_publicar(ver):
                ver.estado = VersionFlujo.Estado.PUBLICADA
                ver.save()

        def campo_de(form, label):
            return form.campos.get(label=label)

        # =================================================================== #
        # INTERNACIÓN  (destino de internaciones; loop de evolución)
        # =================================================================== #
        v_int, f_internacion = nueva_version(internacion, "Internación")

        def N(v, tipo, titulo, x, y, **kw):
            return Nodo.objects.create(version=v, tipo=tipo, titulo=titulo, x=x, y=y, **kw)

        def C(v, o, d, **kw):
            Conexion.objects.create(version=v, origen=o, destino=d, **kw)

        i_ini = N(v_int, NT.INICIO, "Inicio", 60, 200, config={"origen": "derivado"})
        i_cama = N(v_int, NT.FORMULARIO, "Asignar cama", 280, 200, formulario=form_cama)
        i_evol = N(v_int, NT.ATENCION, "Evolución médica", 520, 200)
        i_cond = N(v_int, NT.FORMULARIO, "Conducta", 760, 200, formulario=form_evol)
        i_dec = N(v_int, NT.DECISION, "¿Continúa?", 1000, 200)
        i_alta = N(v_int, NT.FIN, "Alta médica", 1240, 200)
        C(v_int, i_ini, i_cama)
        C(v_int, i_cama, i_evol)
        C(v_int, i_evol, i_cond)
        C(v_int, i_cond, i_dec)
        c_dec_int = campo_de(form_evol, "Decisión")
        C(v_int, i_dec, i_alta, etiqueta="Alta médica",
          condicion={"campo": c_dec_int.id, "operador": "=", "valor": "Alta médica"})
        C(v_int, i_dec, i_evol, etiqueta="Continúa internado")  # rama por defecto: re-evoluciona
        i_cama.grupos.set([g_adm_int.id])
        i_evol.grupos.set([g_med_int.id])
        i_cond.grupos.set([g_med_int.id])
        publicar(v_int)

        # =================================================================== #
        # LABORATORIO  (ida y vuelta de estudios)
        # =================================================================== #
        v_lab, f_lab = nueva_version(laboratorio, "Procesamiento de laboratorio")
        l_ini = N(v_lab, NT.INICIO, "Inicio", 60, 200, config={"origen": "derivado"})
        l_toma = N(v_lab, NT.FORMULARIO, "Toma de muestra", 300, 200, formulario=form_lab)
        l_inf = N(v_lab, NT.ATENCION, "Procesamiento e informe", 560, 200)
        l_fin = N(v_lab, NT.FIN, "Informe disponible", 820, 200)
        C(v_lab, l_ini, l_toma)
        C(v_lab, l_toma, l_inf)
        C(v_lab, l_inf, l_fin)
        l_toma.grupos.set([g_med_lab.id])
        l_inf.grupos.set([g_med_lab.id])
        publicar(v_lab)

        # =================================================================== #
        # DIAGNÓSTICO POR IMÁGENES  (ida y vuelta de estudios)
        # =================================================================== #
        v_img, f_img = nueva_version(imagenes, "Realización de estudio por imágenes")
        m_ini = N(v_img, NT.INICIO, "Inicio", 60, 200, config={"origen": "derivado"})
        m_rec = N(v_img, NT.FORMULARIO, "Recepción y preparación", 300, 200, formulario=form_img)
        m_inf = N(v_img, NT.ATENCION, "Realización e informe", 560, 200)
        m_fin = N(v_img, NT.FIN, "Estudio informado", 820, 200)
        C(v_img, m_ini, m_rec)
        C(v_img, m_rec, m_inf)
        C(v_img, m_inf, m_fin)
        m_rec.grupos.set([g_med_img.id])
        m_inf.grupos.set([g_med_img.id])
        publicar(v_img)

        # =================================================================== #
        # ESPECIALIDADES  (Inicio → Atención con fila → Conducta → Disposición)
        # =================================================================== #
        def flujo_especialidad(area, titulo, form_cond, g_med):
            v, fl = nueva_version(area, titulo)
            e_ini = N(v, NT.INICIO, "Inicio", 60, 200, config={"origen": "derivado"})
            e_ate = N(v, NT.ATENCION, "Atención del especialista", 300, 200, config={"con_fila": True})
            e_cond = N(v, NT.FORMULARIO, "Conducta", 560, 200, formulario=form_cond)
            e_dec = N(v, NT.DECISION, "¿Disposición?", 800, 200)
            e_alta = N(v, NT.FIN, "Alta", 1040, 120)
            e_der = N(v, NT.DERIVAR, "Internar", 1040, 300,
                      config={"area_destino_id": internacion.id, "flujo_destino_id": f_internacion.id})
            e_fin = N(v, NT.FIN, "Internación gestionada", 1280, 300)
            C(v, e_ini, e_ate)
            C(v, e_ate, e_cond)
            C(v, e_cond, e_dec)
            c_disp = campo_de(form_cond, "Disposición")
            C(v, e_dec, e_der, etiqueta="Internación",
              condicion={"campo": c_disp.id, "operador": "=", "valor": "Internación"})
            C(v, e_dec, e_alta, etiqueta="Alta")  # rama por defecto
            C(v, e_der, e_fin)
            e_ate.grupos.set([g_med.id])
            e_cond.grupos.set([g_med.id])
            publicar(v)
            return fl

        f_trauma = flujo_especialidad(trauma, "Atención traumatológica", form_cond_trauma, g_med_trauma)
        f_cardio = flujo_especialidad(cardio, "Atención cardiológica", form_cond_cardio, g_med_cardio)
        f_sm = flujo_especialidad(salud_mental, "Atención en salud mental", form_cond_sm, g_med_sm)
        f_neuro = flujo_especialidad(neuro, "Atención neurológica", form_cond_neuro, g_med_neuro)

        # =================================================================== #
        # INGRESO A GUARDIA  (flujo central, entrada manual)
        # =================================================================== #
        v_g, f_ingreso = nueva_version(guardia, "Ingreso a Guardia")

        g_ini = N(v_g, NT.INICIO, "Inicio", 40, 320, config={"origen": "manual"})
        g_adm = N(v_g, NT.FORMULARIO, "Admisión administrativa", 220, 320, formulario=form_admision)
        g_tri = N(v_g, NT.FORMULARIO, "Triage de enfermería", 420, 320, formulario=form_triage)
        g_dec_t = N(v_g, NT.DECISION, "¿Nivel de triage?", 640, 320)
        g_shock = N(v_g, NT.ATENCION, "Shock Room", 860, 140)          # atención inmediata (sin fila)
        g_sala = N(v_g, NT.ATENCION, "Sala de espera", 860, 460, config={"con_fila": True})
        g_cond = N(v_g, NT.FORMULARIO, "Conducta médica", 1100, 320, formulario=form_conducta_g)
        g_dec_c = N(v_g, NT.DECISION, "¿Conducta?", 1320, 320)
        g_alta = N(v_g, NT.FIN, "Alta de guardia", 1540, 80)
        g_obs = N(v_g, NT.ESPERA_TIEMPO, "Observación en guardia", 1320, 540,
                  config={"duracion": "6 horas"})
        g_der_int = N(v_g, NT.DERIVAR, "Internar", 1540, 220,
                      config={"area_destino_id": internacion.id, "flujo_destino_id": f_internacion.id})
        g_dec_e = N(v_g, NT.DECISION, "¿Especialidad?", 1540, 360)
        g_d_tr = N(v_g, NT.DERIVAR, "Derivar a Traumatología", 1760, 200,
                   config={"area_destino_id": trauma.id, "flujo_destino_id": f_trauma.id})
        g_d_ca = N(v_g, NT.DERIVAR, "Derivar a Cardiología", 1760, 320,
                   config={"area_destino_id": cardio.id, "flujo_destino_id": f_cardio.id})
        g_d_sm = N(v_g, NT.DERIVAR, "Derivar a Salud mental", 1760, 440,
                   config={"area_destino_id": salud_mental.id, "flujo_destino_id": f_sm.id})
        g_d_ne = N(v_g, NT.DERIVAR, "Derivar a Neurología", 1760, 560,
                   config={"area_destino_id": neuro.id, "flujo_destino_id": f_neuro.id})
        g_egreso = N(v_g, NT.FIN, "Egreso de guardia", 2000, 380)

        C(v_g, g_ini, g_adm)
        C(v_g, g_adm, g_tri)
        C(v_g, g_tri, g_dec_t)
        # Triage: Rojo → Shock Room; el resto va a la sala de espera (rama por defecto).
        c_nivel = campo_de(form_triage, "Nivel de triage")
        C(v_g, g_dec_t, g_shock, etiqueta="Rojo - Emergencia",
          condicion={"campo": c_nivel.id, "operador": "=", "valor": "Rojo - Emergencia"})
        C(v_g, g_dec_t, g_sala, etiqueta="Naranja / Amarillo / Verde / Azul")
        # Ambas atenciones confluyen en la conducta médica.
        C(v_g, g_shock, g_cond)
        C(v_g, g_sala, g_cond)
        C(v_g, g_cond, g_dec_c)
        # Conducta: 4 ramas.
        c_cond = campo_de(form_conducta_g, "Conducta")
        C(v_g, g_dec_c, g_alta, etiqueta="Alta",
          condicion={"campo": c_cond.id, "operador": "=", "valor": "Alta"})
        C(v_g, g_dec_c, g_der_int, etiqueta="Internación",
          condicion={"campo": c_cond.id, "operador": "=", "valor": "Internación"})
        C(v_g, g_dec_c, g_obs, etiqueta="Observación",
          condicion={"campo": c_cond.id, "operador": "=", "valor": "Observación"})
        C(v_g, g_dec_c, g_dec_e, etiqueta="Derivar a especialidad")  # rama por defecto
        # Observación: espera y vuelve a reevaluarse (loop).
        C(v_g, g_obs, g_cond)
        # Internación: deriva y cierra el ingreso.
        C(v_g, g_der_int, g_egreso)
        # Decisión de especialidad.
        c_esp = campo_de(form_conducta_g, "Especialidad de derivación")
        C(v_g, g_dec_e, g_d_tr, etiqueta="Traumatología",
          condicion={"campo": c_esp.id, "operador": "=", "valor": "Traumatología"})
        C(v_g, g_dec_e, g_d_ca, etiqueta="Cardiología",
          condicion={"campo": c_esp.id, "operador": "=", "valor": "Cardiología"})
        C(v_g, g_dec_e, g_d_sm, etiqueta="Salud mental",
          condicion={"campo": c_esp.id, "operador": "=", "valor": "Salud mental"})
        C(v_g, g_dec_e, g_d_ne, etiqueta="Neurología")  # rama por defecto
        for nodo in (g_d_tr, g_d_ca, g_d_sm, g_d_ne):
            C(v_g, nodo, g_egreso)

        # Quién hace qué en la guardia.
        g_adm.grupos.set([g_adm_guardia.id])
        g_tri.grupos.set([g_enf_guardia.id])
        g_shock.grupos.set([g_med_guardia.id])
        g_sala.grupos.set([g_med_guardia.id])
        g_cond.grupos.set([g_med_guardia.id])
        publicar(v_g)

        # --- Resumen --------------------------------------------------------
        self.stdout.write(self.style.SUCCESS(
            "Escenario de guardia (realista) cargado en «Hospital Central».\n"
            "  Áreas: Guardia, Traumatología, Cardiología, Salud mental, Neurología,\n"
            "         Diagnóstico por imágenes, Laboratorio, Internación.\n"
            "  Flujos publicados:\n"
            "    · Ingreso a Guardia  (Admisión → Triage → Shock/Sala → Conducta → derivaciones)\n"
            "    · Atención traumatológica / cardiológica / salud mental / neurológica\n"
            "    · Procesamiento de laboratorio · Realización de estudio por imágenes\n"
            "    · Internación\n"
            "Accesos (contraseña demo1234, salvo el admin):\n"
            "  admin@cauce.local / admin1234       (super admin)\n"
            "  guardia.adm@hospital.gob.ar         (admisión → arranca el ingreso)\n"
            "  guardia.enf@hospital.gob.ar         (enfermería → triage)\n"
            "  guardia.med@hospital.gob.ar         (médico de guardia → atención y conducta)\n"
            "  trauma.med / cardio.med / sm.med / neuro.med   (médicos de especialidad)\n"
            "  lab.med / img.med                   (laboratorio / imágenes → estudios)\n"
            "  int.adm / int.med                   (internación)"
        ))
