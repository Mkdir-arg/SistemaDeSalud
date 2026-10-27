"""Los llamadores autorizan y bloquean el recurso dueño antes de guardar."""
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from .contrato import NIVELES, clave_manual, id_valido, nombre_valido
from .models import Lugar, Ubicacion


def ambito(institucion_id=None, financiador_id=None):
    if bool(institucion_id) == bool(financiador_id):
        raise ValidationError("La ubicación requiere una organización.")
    return {"institucion_id": institucion_id, "financiador_id": financiador_id}


def visibles(dueno):
    return Lugar.objects.filter(Q(origen="georef") | Q(origen="manual", **dueno))


@transaction.atomic
def resolver(entrada, *, dueno, anterior=None, textos=None):
    """Sólo crea sugerencias manuales si se confirma también el domicilio."""
    if not isinstance(entrada, dict) or set(entrada) - set(NIVELES):
        raise ValidationError("Ubicación inválida: informá provincia, partido y localidad.")
    textos = dict(textos or {})
    if anterior:
        textos.update(anterior.textos)
    lugares = {n: getattr(anterior, n) if anterior else None for n in NIVELES}
    origenes = dict(anterior.origenes if anterior else {})
    # Una edición sin cambio territorial conserva también relaciones históricas
    # retiradas o modificadas por la fuente desde que se guardó la instantánea.
    def intacto(nivel):
        if nivel not in entrada:
            return True
        dato, lugar, texto = entrada[nivel], lugares[nivel], textos.get(nivel, "")
        if lugar:
            return isinstance(dato, dict) and set(dato) == {"id"} and id_valido(dato["id"]) and dato["id"] == lugar.pk
        return dato is None and not texto or dato == {"nombre": texto, "origen": "legado"}

    if anterior and all(intacto(n) for n in NIVELES):
        return anterior
    for nivel in NIVELES:
        if nivel not in entrada:
            continue
        dato = entrada[nivel]
        previo = lugares[nivel]
        if dato is None:
            lugares[nivel], textos[nivel] = None, ""
            origenes[nivel] = "legado"
            continue
        if not isinstance(dato, dict):
            raise ValidationError({nivel: "Selección territorial inválida."})
        if dato.get("id") is not None:
            if not id_valido(dato["id"]):
                raise ValidationError({nivel: "Identificador inválido."})
            lugar = visibles(dueno).filter(pk=dato["id"], tipo=nivel).first()
            if not lugar or (not lugar.activo and (not previo or previo.pk != lugar.pk)):
                raise ValidationError({nivel: "El lugar no está disponible para esta organización."})
            lugares[nivel] = lugar
            origenes[nivel] = lugar.origen
            # La misma referencia conserva la instantánea aunque Georef la renombre.
            textos[nivel] = textos.get(nivel, "") if previo and previo.pk == lugar.pk else lugar.nombre
        elif dato.get("origen") == "legado" and dato.get("nombre", "") == textos.get(nivel, "") and not previo:
            lugares[nivel] = None
        elif "manual" in dato:
            try:
                nombre = nombre_valido(dato["manual"])
                prov, dep = lugares["provincia"], lugares["partido"]
                prov_id = prov.pk if prov and nivel != "provincia" else None
                dep_id = dep.pk if dep and nivel == "localidad" else None
                clave = clave_manual(nivel, nombre, **dueno, provincia_id=prov_id, partido_id=dep_id)
            except ValueError as exc:
                raise ValidationError({nivel: str(exc)}) from None
            lugar, _ = Lugar.objects.get_or_create(clave_manual=clave, origen="manual", defaults={
                "tipo": nivel, "nombre": nombre, "provincia_id": prov_id, "partido_id": dep_id, **dueno})
            lugares[nivel], textos[nivel] = lugar, lugar.nombre
            origenes[nivel] = "manual"
        else:
            raise ValidationError({nivel: "Elegí un lugar o confirmá su carga manual."})
    prov, dep, loc = (lugares[n] for n in NIVELES)
    if dep and dep.provincia_id and (not prov or dep.provincia_id != prov.pk):
        raise ValidationError({"partido": "Revisá el partido/departamento al cambiar la provincia."})
    if loc and ((loc.provincia_id and (not prov or loc.provincia_id != prov.pk))
                or (loc.partido_id and (not dep or loc.partido_id != dep.pk))):
        raise ValidationError({"localidad": "Revisá la localidad y sus unidades territoriales."})
    if anterior and all(getattr(anterior, n + "_id") == (lugares[n].pk if lugares[n] else None) for n in NIVELES) and anterior.textos == textos and anterior.origenes == origenes:
        return anterior
    return Ubicacion.objects.create(**lugares, textos=textos, origenes=origenes)


def presentacion(obj, campo="geografia"):
    ubicacion = getattr(obj, campo, None)
    return ubicacion.datos() if ubicacion else None


def texto_territorial(obj, campo="geografia"):
    datos = presentacion(obj, campo) or {}
    return " · ".join(f"{v['nombre']} ({'Manual · sin verificar' if v['origen'] == 'manual' else 'Georef' if v['origen'] == 'georef' else 'Sin homologar'})"
                      for v in datos.values() if v["nombre"])


def domicilio_completo(obj):
    texto = obj.direccion if obj._meta.model_name == "institucion" else obj.domicilio
    return " · ".join(v for v in (texto, texto_territorial(obj)) if v)


def para_traslado(ubicacion):
    """Copia procedencia sin compartir referencias manuales privadas entre dueños."""
    if not ubicacion:
        return None
    lugares = {n: getattr(ubicacion, n) for n in NIVELES}
    return Ubicacion.objects.create(textos=dict(ubicacion.textos),
        origenes={n: v["origen"] for n, v in ubicacion.datos().items()},
        **{n: lugar if lugar and lugar.origen == "georef" else None for n, lugar in lugares.items()})
