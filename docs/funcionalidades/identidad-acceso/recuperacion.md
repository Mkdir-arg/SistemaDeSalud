# Recuperación de acceso

La recuperación vigente se realiza mediante soporte o la administración de la institución. La pantalla de ingreso informa qué datos identificar (institución, nombre y correo de la cuenta) y advierte que no se envíen contraseñas, códigos ni datos clínicos. El contacto directo se muestra solo si el despliegue configura un correo o una URL HTTPS oficiales mediante `VITE_SOPORTE_EMAIL` o `VITE_SOPORTE_URL`.

La interfaz se bloquea tras 15 minutos sin interacción humana y avisa dos minutos antes. `VITE_IDLE_LOCK_MINUTES` permite ajustar ese plazo por instalación. Al bloquear se limpian los tokens del navegador y se exige la misma cuenta y el mismo ámbito para recuperar el formulario que sigue en memoria de esa pestaña. Recargarla descarta ese borrador. Este bloqueo no revoca anticipadamente JWT emitidos: el access token vence a los 60 minutos y el refresh a los 7 días según la configuración actual del servidor.

El personal autorizado verifica la identidad conforme al procedimiento institucional y establece una nueva contraseña mediante los mecanismos administrativos existentes. Comunica el resultado por un canal seguro. Este documento no reemplaza el procedimiento de verificación de cada institución; el contacto operativo y su responsable siguen pendientes de configuración.

## Tentativa futura: recuperación automática por correo

Se evaluará cuando existan un proveedor y remitente oficiales, una URL oficial, un procedimiento de verificación y un responsable operativo. La implementación necesitaría tokens de un solo uso y corta duración, respuestas que no revelen si existe una cuenta, límites de intentos, revocación de sesiones y pruebas de entrega y abuso. Hasta entonces, el sistema no envía correos de recuperación ni promete hacerlo desde la interfaz.
