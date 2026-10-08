from django.urls import path

from . import views, views_datos

urlpatterns = [
    path("cuenta/", views.CuentaView.as_view(), name="portal_cuenta"),
    path("cuenta/registro/", views.RegistroView.as_view(), name="portal_registro"),
    path("cuenta/reenviar-verificacion/", views.ReenviarVerificacionView.as_view(), name="portal_reenviar"),
    path("cuenta/verificar-email/", views.VerificarEmailView.as_view(), name="portal_verificar_email"),
    path("cuenta/ingresar/", views.IngresarView.as_view(), name="portal_ingresar"),
    path("cuenta/renovar/", views.RenovarView.as_view(), name="portal_renovar"),
    path("cuenta/salir/", views.SalirView.as_view(), name="portal_salir"),
    path("cuenta/olvide/", views.OlvideView.as_view(), name="portal_olvide"),
    path("cuenta/restablecer/", views.RestablecerView.as_view(), name="portal_restablecer"),
    path("cuenta/cambiar-contrasena/", views.CambiarContrasenaView.as_view(), name="portal_cambiar_contrasena"),
    path("cuenta/validar-identidad/", views.ValidarIdentidadView.as_view(), name="portal_validar_identidad"),
    path("perfil/", views.PerfilView.as_view(), name="portal_perfil"),
    path("turnos/", views_datos.TurnosView.as_view(), name="portal_turnos"),
    path("turnos/<int:pk>/confirmar/", views_datos.ConfirmarTurnoView.as_view(), name="portal_turno_confirmar"),
    path("turnos/<int:pk>/cancelar/", views_datos.CancelarTurnoView.as_view(), name="portal_turno_cancelar"),
    path("llamado/", views_datos.LlamadoView.as_view(), name="portal_llamado"),
    path("resultados/", views_datos.ResultadosView.as_view(), name="portal_resultados"),
    path("resultados/<int:pk>/archivo/", views_datos.ArchivoResultadoView.as_view(), name="portal_resultado_archivo"),
    path("cobertura/", views_datos.CoberturaView.as_view(), name="portal_cobertura"),
]
