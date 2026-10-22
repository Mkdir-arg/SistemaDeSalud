# Corre en el contenedor de la demo con `manage.py shell`: imprime las cuentas que
# tienen que poder ingresar después de la carga. Sale de la base y no de la salida
# de los seeds, que es texto para personas y puede cambiar de formato.
import json

from apps.accounts.models import Usuario
from apps.portal.models import CuentaPaciente

institucionales = [u.email for u in Usuario.objects.filter(is_active=True).order_by("email") if u.has_usable_password()]
# Sin email confirmado la cuenta del portal no tiene clave usable (ver IngresarView).
portal = list(CuentaPaciente.objects.filter(activa=True, email_verificado_at__isnull=False)
              .order_by("email").values_list("email", flat=True))
print("CUENTAS=" + json.dumps({"institucionales": institucionales, "portal": portal}))
