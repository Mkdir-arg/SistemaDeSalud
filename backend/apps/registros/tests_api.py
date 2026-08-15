"""
La historia clínica como registro legal, no como CRUD.

Lo que se prueba acá es lo que separa un expediente que se puede presentar ante
un reclamo de una tabla más: que quede claro QUIÉN firmó cada asiento, que lo
firmado no se pueda reescribir ni hacer desaparecer, y que el mismo paciente no
termine con dos historias paralelas.

Todo se prueba pegándole a la API con el rol que lo haría en la vida real —el
administrativo de mesa de entradas, que tiene capacidad `registros`—, porque lo
que importa no es que una función devuelva False sino que el pedido HTTP muera.
"""
from rest_framework.test import APITestCase

from apps.accounts.models import LegajoProfesional, Membresia, Usuario
from apps.instituciones.models import Area, Institucion
from apps.registros import integridad
from apps.registros.models import (
    Ciudadano, EntradaHistoria, Estudio, HistoriaClinica, Receta,
)


class RegistrosAPITestCase(APITestCase):
    def setUp(self):
        self.inst = Institucion.objects.create(nombre="Hospital Central")
        self.area = Area.objects.create(institucion=self.inst, nombre="Guardia")

        self.med = Usuario.objects.create_user("med@test.local", "x", nombre="Ana", apellido="Ruiz")
        m = Membresia.objects.create(
            usuario=self.med, institucion=self.inst, rol="medico", activo=True
        )
        m.areas.set([self.area])
        LegajoProfesional.objects.create(usuario=self.med, matricula="MP 12345")

        # Mesa de entradas: tiene capacidad `registros` y por eso llega a estos
        # endpoints. Es el usuario del que hablan estos tests.
        self.adm = Usuario.objects.create_user("adm@test.local", "x", nombre="Sofía", apellido="Gómez")
        ma = Membresia.objects.create(
            usuario=self.adm, institucion=self.inst, rol="administrativo", activo=True
        )
        ma.areas.set([self.area])

        self.paciente = Ciudadano.objects.create(
            institucion=self.inst, nombre="Juan", apellido="Pérez", documento="30111222"
        )
        self.hc = HistoriaClinica.objects.create(ciudadano=self.paciente)

    def como(self, usuario):
        self.client.force_authenticate(usuario)


class AutoriaDeLaAtencionTests(RegistrosAPITestCase):
    """
    Firmar es un acto profesional, no un booleano del cuerpo del pedido.

    Si esto falla, una administrativa puede dejar un «Alta médica» firmado a
    nombre de una médica que nunca vio al paciente, y la pantalla lo muestra con
    la chapa verde «Firmada» y el nombre de ella.
    """

    def test_un_administrativo_no_puede_firmar_una_atencion(self):
        self.como(self.adm)
        r = self.client.post("/api/entradas-historia/", {
            "historia": self.hc.id, "titulo": "Alta médica",
            "contenido": "Paciente en condiciones de alta.",
            "firmada": True, "autor": self.med.id,
        })
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("Médico", str(r.data["detail"]))
        self.assertFalse(EntradaHistoria.objects.exists())

    def test_no_se_puede_registrar_una_atencion_a_nombre_de_otro(self):
        """
        El `autor` sale de la sesión. Mandarlo en el cuerpo era la forma de
        atribuirle a una profesional una atención que no hizo.
        """
        self.como(self.adm)
        r = self.client.post("/api/entradas-historia/", {
            "historia": self.hc.id, "titulo": "Nota administrativa",
            "firmada": False, "autor": self.med.id,
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(EntradaHistoria.objects.get().autor_id, self.adm.id)

    def test_un_medico_firma_y_la_entrada_queda_sellada_con_su_matricula(self):
        """
        Sin sello, `verificar` la clasifica como «anterior al sellado» y la
        historia sigue diciendo que está intacta: una entrada fabricada hoy se
        disfraza de entrada vieja.
        """
        self.como(self.med)
        r = self.client.post("/api/entradas-historia/", {
            "historia": self.hc.id, "titulo": "Consulta",
            "contenido": "Paciente estable.", "firmada": True,
        })
        self.assertEqual(r.status_code, 201, r.data)
        e = EntradaHistoria.objects.get()
        self.assertEqual(e.autor_id, self.med.id)
        self.assertEqual(e.matricula, "MP 12345")
        self.assertTrue(e.sello, "la entrada firmada nació sin sello")
        self.assertTrue(integridad.verificar(e)["ok"])

    def test_sin_matricula_en_el_legajo_no_se_puede_firmar(self):
        """La matrícula es lo que convierte la firma en un acto registrable."""
        sin_mat = Usuario.objects.create_user("med2@test.local", "x", nombre="Luis")
        Membresia.objects.create(
            usuario=sin_mat, institucion=self.inst, rol="medico", activo=True
        )
        self.como(sin_mat)
        r = self.client.post("/api/entradas-historia/", {
            "historia": self.hc.id, "titulo": "Consulta", "firmada": True,
        })
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("matrícula", str(r.data["detail"]))

    def test_un_borrador_sin_firmar_lo_puede_dejar_cualquiera_del_equipo(self):
        """Anotar no es firmar: frenar el borrador sería frenar la atención."""
        self.como(self.adm)
        r = self.client.post("/api/entradas-historia/", {
            "historia": self.hc.id, "titulo": "Ingresó por guardia", "firmada": False,
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(EntradaHistoria.objects.get().sello, "")


class HistoriaInviolableTests(RegistrosAPITestCase):
    """
    Ley 26.529, art. 15-16: la historia clínica es inviolable y se conserva diez
    años. Si esto falla, cualquiera con capacidad `registros` la hace desaparecer
    con un DELETE, sin confirmación y sin dejar constancia de que existió.
    """

    def _firmada(self, titulo="Consulta", contenido="Todo normal."):
        e = EntradaHistoria.objects.create(
            historia=self.hc, titulo=titulo, contenido=contenido,
            autor=self.med, firmada=True, matricula="MP 12345",
        )
        return integridad.sellar(e)

    def test_una_entrada_firmada_no_se_puede_editar(self):
        e = self._firmada(contenido="Paciente estable.")
        self.como(self.adm)
        r = self.client.patch(f"/api/entradas-historia/{e.id}/", {"contenido": "Paciente descompensado."})
        self.assertEqual(r.status_code, 409, r.data)
        e.refresh_from_db()
        self.assertEqual(e.contenido, "Paciente estable.")

    def test_una_entrada_firmada_no_se_puede_borrar(self):
        """
        Borrar la ÚLTIMA entrada no rompe ninguna cadena de sellos y no deja
        rastro: era la forma más limpia de hacer desaparecer una atención.
        """
        e = self._firmada()
        self.como(self.adm)
        r = self.client.delete(f"/api/entradas-historia/{e.id}/")
        self.assertEqual(r.status_code, 405, r.data)
        self.assertTrue(EntradaHistoria.objects.filter(pk=e.pk).exists())

    def test_la_historia_clinica_no_se_puede_borrar(self):
        """Por cascade se llevaba entradas, estudios y recetas del paciente."""
        self._firmada()
        Estudio.objects.create(historia=self.hc, tipo="TAC", fecha="2026-07-01")
        self.como(self.adm)
        r = self.client.delete(f"/api/historias-clinicas/{self.hc.id}/")
        self.assertEqual(r.status_code, 405, r.data)
        self.assertTrue(HistoriaClinica.objects.filter(pk=self.hc.pk).exists())
        self.assertEqual(EntradaHistoria.objects.count(), 1)

    def test_el_paciente_tampoco_se_puede_borrar_porque_su_historia_va_con_el(self):
        """
        La puerta estaba trabada en la historia y abierta en el padre: como
        `historia_clinica` es CASCADE, un DELETE al paciente se llevaba la
        evolución firmada, los estudios y las recetas de una sola vez, sin dejar
        constancia de que existieron. Y el resultado dependía del azar: con
        `AccesoClinico.ciudadano` en PROTECT, el mismo pedido reventaba con 500 si
        alguien había abierto la ficha y borraba todo si nadie la había abierto.
        """
        self._firmada()
        Estudio.objects.create(historia=self.hc, tipo="TAC", fecha="2026-07-01")
        Receta.objects.create(historia=self.hc, detalle="Amoxicilina", autor=self.med)
        self.como(self.adm)
        r = self.client.delete(f"/api/ciudadanos/{self.paciente.id}/")
        self.assertEqual(r.status_code, 405, getattr(r, "data", r))
        self.assertTrue(Ciudadano.objects.filter(pk=self.paciente.pk).exists())
        self.assertEqual(EntradaHistoria.objects.count(), 1)
        self.assertEqual(Estudio.objects.count(), 1)
        self.assertEqual(Receta.objects.count(), 1)

    def test_una_historia_no_se_puede_pasar_a_otro_paciente(self):
        """
        Mudar la historia deja al paciente A sin nada y al B con atenciones
        ajenas —la alergia y la medicación crónica en la ficha equivocada—, y
        además rompe los sellos: el canónico incluye el ciudadano, así que
        `verificar_historia` pasa a denunciar entradas que nadie tocó. Ese falso
        positivo convierte la única prueba de integridad del hospital en una
        acusación contra sí mismo y no se puede deshacer.
        """
        self._firmada()
        otro = Ciudadano.objects.create(
            institucion=self.inst, nombre="María", apellido="Cabrera", documento="27418305"
        )
        self.como(self.adm)
        r = self.client.patch(f"/api/historias-clinicas/{self.hc.id}/", {"ciudadano": otro.id})
        self.assertEqual(r.status_code, 400, r.data)
        self.hc.refresh_from_db()
        self.assertEqual(self.hc.ciudadano_id, self.paciente.id)
        self.assertTrue(integridad.verificar_historia(self.hc)["ok"])

    def test_un_borrador_no_se_puede_mudar_a_la_historia_de_otro_paciente(self):
        """
        En un módulo donde nada se borra ni se mueve, la FK abierta era la puerta
        que quedaba: el asiento «Ingresó por guardia, dolor precordial» aparecía
        en la evolución de otra persona y, una vez firmado ahí, el sello
        certificaba esa ubicación equivocada como correcta.
        """
        otra_hc = HistoriaClinica.objects.create(
            ciudadano=Ciudadano.objects.create(
                institucion=self.inst, nombre="Elena", apellido="Ledesma", documento="27418305"
            )
        )
        e = EntradaHistoria.objects.create(
            historia=self.hc, titulo="Ingresó por guardia", autor=self.adm
        )
        self.como(self.adm)
        r = self.client.patch(f"/api/entradas-historia/{e.id}/", {"historia": otra_hc.id})
        self.assertEqual(r.status_code, 400, r.data)
        e.refresh_from_db()
        self.assertEqual(e.historia_id, self.hc.id)

    def test_un_borrador_sin_firmar_si_se_puede_corregir(self):
        """Corregir un borrador es lo esperable; trabarlo sería trabar el trabajo."""
        e = EntradaHistoria.objects.create(historia=self.hc, titulo="Nota", autor=self.adm)
        self.como(self.adm)
        r = self.client.patch(f"/api/entradas-historia/{e.id}/", {"contenido": "corregido"})
        self.assertEqual(r.status_code, 200, r.data)
        e.refresh_from_db()
        self.assertEqual(e.contenido, "corregido")

    def test_firmar_un_borrador_lo_sella_a_nombre_de_quien_firma(self):
        e = EntradaHistoria.objects.create(historia=self.hc, titulo="Consulta", autor=self.adm)
        self.como(self.med)
        r = self.client.patch(f"/api/entradas-historia/{e.id}/", {"firmada": True})
        self.assertEqual(r.status_code, 200, r.data)
        e.refresh_from_db()
        self.assertEqual(e.autor_id, self.med.id)
        self.assertEqual(e.matricula, "MP 12345")
        self.assertTrue(integridad.verificar(e)["ok"])


class AntecedentesTests(RegistrosAPITestCase):
    """
    Alergias y condiciones tienen que poder cargarse desde el sistema.

    Si esto falla, el único camino es el admin de Django: en la demo se ven
    completos porque los llena el seed, y en el hospital dicen «Sin alergias
    registradas» sobre un paciente alérgico a la penicilina.
    """

    def test_se_pueden_cargar_las_alergias_del_paciente(self):
        self.como(self.med)
        r = self.client.patch(f"/api/historias-clinicas/{self.hc.id}/", {
            "alergias": "Penicilina", "condiciones": "HTA",
        })
        self.assertEqual(r.status_code, 200, r.data)
        self.hc.refresh_from_db()
        self.assertEqual(self.hc.alergias, "Penicilina")
        self.assertEqual(self.hc.condiciones, "HTA")

    def test_queda_registrado_quien_los_cargo_y_cuando(self):
        """
        Es lo que distingue «se preguntó y no tiene» de «nunca se preguntó».
        Sin esta marca, la pantalla afirma lo primero cuando lo cierto es lo
        segundo, que es el peor estado vacío posible.
        """
        self.assertIsNone(self.hc.antecedentes_at)
        self.como(self.med)
        self.client.patch(f"/api/historias-clinicas/{self.hc.id}/", {"alergias": ""})
        self.hc.refresh_from_db()
        self.assertEqual(self.hc.antecedentes_por_id, self.med.id)
        self.assertIsNotNone(self.hc.antecedentes_at)

    def test_el_autor_de_los_antecedentes_no_se_puede_mandar_desde_afuera(self):
        self.como(self.adm)
        self.client.patch(f"/api/historias-clinicas/{self.hc.id}/", {
            "alergias": "Ninguna", "antecedentes_por": self.med.id,
        })
        self.hc.refresh_from_db()
        self.assertEqual(self.hc.antecedentes_por_id, self.adm.id)


class RecetasTests(RegistrosAPITestCase):
    """
    Prescribir y suspender son actos clínicos.

    Si la suspensión no existe, el estado sólo puede crecer: a los dos años el
    paciente crónico tiene veinte recetas «Activas» superpuestas y no hay manera
    de saber cuál es el tratamiento vigente.
    """

    def test_un_administrativo_no_puede_emitir_una_receta(self):
        self.como(self.adm)
        r = self.client.post("/api/recetas/", {
            "historia": self.hc.id, "detalle": "Clonazepam 2mg x 30", "autor": self.med.id,
        })
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("médico", str(r.data["detail"]).lower())
        self.assertFalse(Receta.objects.exists())

    def test_la_receta_queda_a_nombre_de_quien_la_emitio(self):
        self.como(self.med)
        r = self.client.post("/api/recetas/", {
            "historia": self.hc.id, "detalle": "Amoxicilina 500mg", "autor": self.adm.id,
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Receta.objects.get().autor_id, self.med.id)

    def test_se_puede_suspender_una_receta_vigente(self):
        receta = Receta.objects.create(historia=self.hc, detalle="Enoxaparina", autor=self.med)
        self.como(self.med)
        r = self.client.post(f"/api/recetas/{receta.id}/suspender/", {"motivo": "Cirugía programada"})
        self.assertEqual(r.status_code, 200, r.data)
        receta.refresh_from_db()
        self.assertFalse(receta.activa)

    def test_suspender_deja_el_asiento_en_la_evolucion(self):
        """
        Suspender una medicación es un acto que va a la historia: si sólo cambia
        un booleano, quien lea la evolución no se entera de que se cortó.
        """
        receta = Receta.objects.create(historia=self.hc, detalle="Enoxaparina", autor=self.med)
        self.como(self.med)
        self.client.post(f"/api/recetas/{receta.id}/suspender/", {"motivo": "Cirugía programada"})
        e = EntradaHistoria.objects.get()
        self.assertIn("Cirugía programada", e.contenido)
        self.assertIn("Enoxaparina", e.contenido)
        self.assertTrue(e.firmada)
        self.assertTrue(integridad.verificar(e)["ok"])

    def test_suspender_sin_motivo_no_se_acepta(self):
        """Sin motivo, el asiento no le contesta nada a quien retome el tratamiento."""
        receta = Receta.objects.create(historia=self.hc, detalle="Enoxaparina", autor=self.med)
        self.como(self.med)
        r = self.client.post(f"/api/recetas/{receta.id}/suspender/", {"motivo": "  "})
        self.assertEqual(r.status_code, 400, r.data)
        receta.refresh_from_db()
        self.assertTrue(receta.activa)

    def test_un_administrativo_no_puede_suspender_una_medicacion(self):
        receta = Receta.objects.create(historia=self.hc, detalle="Enoxaparina", autor=self.med)
        self.como(self.adm)
        r = self.client.post(f"/api/recetas/{receta.id}/suspender/", {"motivo": "porque sí"})
        self.assertEqual(r.status_code, 400, r.data)
        receta.refresh_from_db()
        self.assertTrue(receta.activa)


class EstudiosTests(RegistrosAPITestCase):
    def test_un_administrativo_no_puede_solicitar_un_estudio(self):
        self.como(self.adm)
        r = self.client.post("/api/estudios/", {
            "historia": self.hc.id, "tipo": "TAC de cerebro", "fecha": "2026-07-01",
        })
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(Estudio.objects.exists())

    def test_el_autor_del_estudio_sale_de_la_sesion(self):
        """`Estudio.autor` es texto libre: si viene del cuerpo, no lo verifica nadie."""
        self.como(self.med)
        r = self.client.post("/api/estudios/", {
            "historia": self.hc.id, "tipo": "TAC de cerebro", "fecha": "2026-07-01",
            "autor": "Quien sea",
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Estudio.objects.get().autor, self.med.nombre_completo)

    def _estudio(self):
        return Estudio.objects.create(
            historia=self.hc, tipo="Rx de tórax", resultado="alterado",
            autor=self.med.nombre_completo, fecha="2026-07-01",
        )

    def test_un_administrativo_no_puede_cambiar_el_resultado_de_un_estudio(self):
        """
        Informar es tan clínico como pedir, y sólo el alta lo exigía: mesa de
        entradas pasaba un «alterado» a «normal» y el registro seguía diciendo
        que lo pidió la médica. Ella no tiene con qué desmentirlo —el estudio no
        lleva sello ni matrícula—, que es el mismo argumento con el que se blindó
        el alta.
        """
        e = self._estudio()
        self.como(self.adm)
        r = self.client.patch(f"/api/estudios/{e.id}/", {"resultado": "normal", "tipo": "Rx normal"})
        self.assertEqual(r.status_code, 400, r.data)
        e.refresh_from_db()
        self.assertEqual(e.resultado, "alterado")
        self.assertEqual(e.tipo, "Rx de tórax")

    def test_un_estudio_no_se_puede_borrar(self):
        """Diez años de conservación obligatoria, y el estudio no lleva sello:
        borrado no queda nada que verificar. Se corrige con uno nuevo."""
        e = self._estudio()
        self.como(self.med)
        r = self.client.delete(f"/api/estudios/{e.id}/")
        self.assertEqual(r.status_code, 405, getattr(r, "data", r))
        self.assertTrue(Estudio.objects.filter(pk=e.pk).exists())

    def test_un_estudio_no_se_puede_mudar_a_la_ficha_de_otro_paciente(self):
        """El resultado de una persona en el expediente de otra se lee como suyo."""
        e = self._estudio()
        otra_hc = HistoriaClinica.objects.create(
            ciudadano=Ciudadano.objects.create(
                institucion=self.inst, nombre="Elena", apellido="Ledesma", documento="27418305"
            )
        )
        self.como(self.med)
        r = self.client.patch(f"/api/estudios/{e.id}/", {"historia": otra_hc.id})
        self.assertEqual(r.status_code, 400, r.data)
        e.refresh_from_db()
        self.assertEqual(e.historia_id, self.hc.id)

    def test_el_medico_si_puede_informar_el_resultado(self):
        """Trabar la edición entera dejaría el estudio pedido sin forma de informarse."""
        e = self._estudio()
        self.como(self.med)
        r = self.client.patch(f"/api/estudios/{e.id}/", {"resultado": "normal", "realizado": True})
        self.assertEqual(r.status_code, 200, r.data)
        e.refresh_from_db()
        self.assertEqual(e.resultado, "normal")
        self.assertTrue(e.realizado)


class PacienteDuplicadoTests(RegistrosAPITestCase):
    """
    Dos registros del mismo paciente son dos historias clínicas paralelas.

    Como `HistoriaClinica` es OneToOne con `Ciudadano`, cada copia arranca su
    propia evolución: el médico abre una de las dos al azar y la alergia puede
    estar en la otra.
    """

    def test_no_se_puede_cargar_dos_veces_el_mismo_documento(self):
        self.como(self.adm)
        r = self.client.post("/api/ciudadanos/", {
            "institucion": self.inst.id, "nombre": "Juan", "apellido": "Perez",
            "documento": "30111222",
        })
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(Ciudadano.objects.filter(documento="30111222").count(), 1)

    def test_el_error_dice_de_quien_es_ese_documento(self):
        """
        El caso real es el administrativo que no encontró al paciente por un
        error de tipeo del ingreso anterior. Un «documento duplicado» pelado lo
        deja igual de perdido; el nombre lo lleva a la historia que ya existe.
        """
        self.como(self.adm)
        r = self.client.post("/api/ciudadanos/", {
            "institucion": self.inst.id, "nombre": "J.", "documento": "30111222",
        })
        self.assertIn("Juan Pérez", str(r.data["detail"]))

    def test_el_mismo_documento_con_puntos_es_el_mismo_paciente(self):
        """
        En Argentina el DNI con puntos es como está impreso en el documento que
        el administrativo tiene en la mano: es el caso normal, no un error raro.
        Comparando la cadena cruda, «30.111.222» entraba como paciente nuevo y a
        partir de ahí había dos historias clínicas del mismo: el médico abre una
        al azar y la alergia puede estar en la otra. No se pueden fusionar, así
        que frenar el alta es toda la defensa que hay.
        """
        self.como(self.adm)
        r = self.client.post("/api/ciudadanos/", {
            "institucion": self.inst.id, "nombre": "Juan", "apellido": "Perez",
            "documento": "30.111.222",
        })
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("Juan Pérez", str(r.data["detail"]))
        self.assertEqual(Ciudadano.objects.filter(institucion=self.inst).count(), 1)

    def test_el_documento_queda_guardado_sin_puntos_ni_guiones(self):
        """
        Si se guardara como vino, el próximo alta compara contra la cadena
        punteada y el duplicado vuelve a entrar por el otro lado: la constraint
        de la base compara texto.
        """
        self.como(self.adm)
        r = self.client.post("/api/ciudadanos/", {
            "institucion": self.inst.id, "nombre": "Elena", "apellido": "Acosta",
            "documento": "27.418-305",
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Ciudadano.objects.get(nombre="Elena").documento, "27418305")

    def test_el_duplicado_tampoco_entra_por_el_alta_directa_del_modelo(self):
        """
        El alta del paciente también ocurre fuera del serializer —el motor al
        ingresar a alguien, un import—. Si la normalización viviera sólo en la
        API, esos caminos seguirían creando la segunda historia clínica.
        """
        from django.db import IntegrityError, transaction

        # El atomic propio es para que el error no deje inservible la transacción
        # del test: sin él, lo que falla es el desarme y no se entiende por qué.
        with self.assertRaises(IntegrityError), transaction.atomic():
            Ciudadano.objects.create(
                institucion=self.inst, nombre="Juan", apellido="Perez",
                documento="30.111.222",
            )

    def test_el_paciente_sin_documento_se_anota_igual_y_no_traba_al_siguiente(self):
        """
        El NN de guardia. Un unique pelado dejaría afuera justo el caso donde
        menos se puede frenar el ingreso.
        """
        self.como(self.adm)
        for nombre in ("NN 1", "NN 2"):
            r = self.client.post("/api/ciudadanos/", {
                "institucion": self.inst.id, "nombre": nombre, "documento": "",
            })
            self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Ciudadano.objects.filter(documento="").count(), 2)

    def test_el_mismo_documento_en_otra_institucion_no_molesta(self):
        """Cada institución tiene su padrón: el paciente puede estar en las dos."""
        otra = Institucion.objects.create(nombre="Hospital del Sur")
        Membresia.objects.create(usuario=self.adm, institucion=otra, rol="administrativo", activo=True)
        self.como(self.adm)
        r = self.client.post("/api/ciudadanos/", {
            "institucion": otra.id, "nombre": "Juan", "apellido": "Pérez",
            "documento": "30111222",
        })
        self.assertEqual(r.status_code, 201, r.data)
