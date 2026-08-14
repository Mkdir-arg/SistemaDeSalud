"""
Aplica la política de retención (Ley 25.326).

**En seco por defecto.** Un borrado masivo que se dispara sin que nadie lo haya
mirado es peor que no purgar: lo segundo se arregla corriendo el comando, lo
primero no se arregla.

    python manage.py purgar_datos              # muestra qué haría
    python manage.py purgar_datos --aplicar    # lo hace

La política, con el motivo de cada plazo, está en `apps/auditoria/retencion.py`.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.auditoria import retencion


class Command(BaseCommand):
    help = "Borra los datos que cumplieron su plazo de retención."

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar", action="store_true",
            help="Borra de verdad. Sin esto sólo muestra qué haría.",
        )

    def handle(self, *args, **opciones):
        aplicar = opciones["aplicar"]
        total = 0

        for r in retencion.reglas():
            cuantos = r.vencidos().count()

            if r.protegido:
                # Se lista igual, para que la política se vea completa: alguien
                # que audita necesita ver que la historia clínica ESTÁ
                # contemplada y por qué no se toca, no que falte de la lista.
                self.stdout.write(
                    f"  {r.nombre:<24} {cuantos:>7} fuera de plazo · "
                    f"NO SE BORRA ({r.motivo.split(':')[0]})"
                )
                continue

            self.stdout.write(f"  {r.nombre:<24} {cuantos:>7} para borrar ({r.dias} días)")
            if aplicar and cuantos:
                with transaction.atomic():
                    # `delete()` sobre el queryset y no uno por uno: son miles de
                    # filas y el objetivo es que esto se pueda correr seguido.
                    r.vencidos().delete()
                total += cuantos

        if aplicar:
            self.stdout.write(self.style.SUCCESS(f"\n{total} registro(s) borrado(s)."))
        else:
            self.stdout.write(
                "\nEn seco: no se borró nada. Agregá --aplicar para hacerlo.\n"
                "La política y el motivo de cada plazo están en "
                "apps/auditoria/retencion.py"
            )
