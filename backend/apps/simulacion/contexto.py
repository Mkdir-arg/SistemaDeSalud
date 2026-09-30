"""
Qué cuenta se simula en el pedido en curso y quién la está usando.

Durante una simulación, `request.user` es la cuenta de referencia: así cada
permiso, cada filtro por institución y cada servicio que recibe `usuario`
evalúan los límites reales del perfil sin que haya que tocarlos. El costo es que
esos mismos servicios guardan a `usuario` como autor. Acá se corrige eso.

**Autoría y estado operativo.** Al guardar, los campos de autoría (quién
registró, aprobó, firmó o consultó) que apunten a la cuenta simulada pasan al
superusuario que actuó. Los campos operativos (a quién está asignado un caso,
quién ocupa un box) conservan la cuenta: son el estado que el perfil necesita
para seguir el recorrido, no una firma.

Cada FK a `Usuario` tiene que figurar en una de las dos listas. Un test recorre
todos los modelos y falla si aparece una sin clasificar: un campo de autoría
nuevo no puede quedar a nombre de la cuenta por omisión.

`pre_save` no cubre `bulk_create` ni `QuerySet.update()`. Esos caminos llaman a
`autor_real()` de forma explícita.
"""
import contextvars
from dataclasses import dataclass

# (app_label.Modelo) → campos que registran quién hizo algo.
CAMPOS_AUTORIA = {
    "agenda.Turno": ("creado_por", "resuelto_por"),
    "auditoria.AccesoClinico": ("usuario",),
    "casos.EventoCaso": ("autor",),
    "farmacia.Movimiento": ("autor",),
    "farmacia.Pedido": ("creado_por",),
    "financiadores.AfiliacionCaso": ("registrado_por",),
    "financiadores.Afiliado": ("finalizado_por",),
    "financiadores.ArancelConvenio": ("creado_por",),
    "financiadores.ConsumoExterno": ("registrado_por",),
    "financiadores.Convenio": ("creado_por", "aceptado_por", "cerrado_por"),
    "financiadores.EventoAutorizacion": ("usuario",),
    "financiadores.EventoCobertura": ("usuario",),
    "financiadores.HistorialAfiliacion": ("registrado_por",),
    "financiadores.Importacion": ("creado_por",),
    "financiadores.ReglaCobertura": ("creado_por",),
    "financiadores.ReservaCobertura": ("creado_por", "cerrado_por"),
    "financiadores.ResolucionSaldo": ("registrado_por",),
    "financiadores.RevisionContexto": ("registrado_por",),
    "financiadores.SolicitudAutorizacion": ("creado_por", "resuelto_por"),
    "financiadores.VinculoCiudadano": ("verificado_por",),
    "finanzas.AccesoFinanciero": ("usuario",),
    "finanzas.AjusteCosto": ("registrado_por", "aprobado_por", "rechazado_por"),
    "finanzas.AjusteGasto": ("registrado_por", "aprobado_por", "rechazado_por"),
    "finanzas.AjusteObligacion": ("autor", "aprobado_por", "rechazado_por"),
    "finanzas.CoberturaActividadCosteable": ("registrado_por",),
    "finanzas.ConceptoGasto": ("registrado_por",),
    "finanzas.CorreccionSnapshotCosteo": ("registrado_por",),
    "finanzas.ExpectativaGasto": ("registrado_por",),
    "finanzas.Gasto": ("registrado_por", "aprobado_por", "rechazado_por"),
    "finanzas.HechoAtencionCosteable": ("autor",),
    "finanzas.IndicacionCargaGasto": ("registrado_por",),
    "finanzas.MovimientoDinero": ("autor", "aprobado_por", "rechazado_por"),
    "finanzas.ObligacionFinanciera": ("creado_por",),
    "finanzas.PendienteCobro": ("resuelto_por",),
    "finanzas.PoliticaCobro": ("registrado_por",),
    "finanzas.ReglaRepartoActividad": ("registrado_por",),
    "finanzas.ValorComponente": ("registrado_por",),
    "flujos.VersionFlujo": ("autor",),
    "instituciones.EstadiaCama": ("autor",),
    "red.Traslado": ("solicitado_por", "resuelto_por"),
    "registros.ArchivoClinico": ("subido_por",),
    "registros.ConsentimientoDatos": ("tomado_por",),
    "registros.EntradaHistoria": ("autor",),
    "registros.HistoriaClinica": ("antecedentes_por",),
    "registros.Receta": ("autor",),
}

# Campos que NO son autoría: pertenencia, asignación, destinatario, o los
# registros de la propia simulación. Durante una simulación quedan en la cuenta.
CAMPOS_OPERATIVOS = {
    "accounts.LegajoProfesional": ("usuario",),
    "accounts.Membresia": ("usuario",),
    "admin.LogEntry": ("user",),
    "agenda.Agenda": ("profesional",),
    "casos.Caso": ("asignado_a",),
    "casos.Notificacion": ("usuario",),
    "financiadores.MembresiaFinanciador": ("usuario",),
    "instituciones.Box": ("ocupado_por",),
    "instituciones.Grupo": ("miembros",),
    "simulacion.CuentaReferencia": ("usuario",),
    "simulacion.SesionSimulacion": ("superusuario", "cuenta"),
}


@dataclass(frozen=True)
class Contexto:
    sesion: object
    cuenta: object
    superusuario: object


_actual = contextvars.ContextVar("simulacion_actual", default=None)


def actual():
    """El `Contexto` del pedido simulado en curso, o None."""
    return _actual.get()


def activar(sesion, superusuario):
    _actual.set(Contexto(sesion=sesion, cuenta=sesion.cuenta, superusuario=superusuario))


def limpiar():
    _actual.set(None)


def autor_real(usuario):
    """Quién hizo de verdad lo que el código atribuye a `usuario`.

    Es el mismo `usuario` salvo que sea la cuenta simulada en este pedido.
    """
    ctx = _actual.get()
    if ctx is None or usuario is None or getattr(usuario, "pk", usuario) != ctx.cuenta.pk:
        return usuario
    return ctx.superusuario


def usuario_real(request):
    """El usuario autenticado del pedido, simule o no un perfil."""
    return getattr(request, "usuario_real", None) or request.user


def atribuir_autoria(sender, instance, raw=False, update_fields=None, **kwargs):
    """`pre_save`: la autoría de un pedido simulado es del superusuario."""
    ctx = _actual.get()
    if ctx is None or raw:
        return
    campos = CAMPOS_AUTORIA.get(sender._meta.concrete_model._meta.label)
    if not campos:
        return
    for nombre in campos:
        if update_fields is not None and nombre not in update_fields:
            continue
        if getattr(instance, f"{nombre}_id", None) == ctx.cuenta.pk:
            setattr(instance, nombre, ctx.superusuario)
