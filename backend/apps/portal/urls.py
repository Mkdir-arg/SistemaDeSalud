from django.urls import path

from . import views

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
]
