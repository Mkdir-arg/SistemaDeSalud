"""Calendario relativo de las cargas ficticias: doce meses que terminan hoy.

Los escenarios se escriben con fechas *nominales* —un día y una hora dentro de un
mes que se nombra por su distancia al mes en curso— y este módulo las convierte en
instantes reales. Dos reglas:

- **Los meses anteriores al actual van tal cual.** El 25 de hace tres meses es
  el 25.
- **El mes en curso es el presente del escenario.** Su tramo nominal, del 1 a las
  00:00 al 15 a las 11:00, se estira o se comprime, en orden, sobre lo que va del
  mes hasta ahora. Cargado el 1° a las 9, todo cae entre las 0 y las 9; cargado
  el 30, se reparte en treinta días.

Así ninguna fecha queda en el futuro y lo que el escenario deja pendiente
—casos abiertos, gastos por aprobar, autorizaciones sin respuesta— es siempre de
las últimas horas. Además, el mes en curso nunca está vacío, y es el que las
pantallas de finanzas y de financiadores abren por defecto.

Comprimir conserva el orden de todos los instantes del mes, no sólo el de los
días. Eso importa: si un componente de costo se crea el 13 a las 7 y una atención
ocurre el 5 a las 10, la atención tiene que seguir siendo anterior aunque las dos
caigan el mismo día.
"""
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.utils import timezone

# Último instante nominal del mes en curso, contado desde el 1 a las 00:00.
PRESENTE_NOMINAL = timedelta(days=14, hours=11)


class Calendario:
    def __init__(self, ahora=None):
        self.ahora = timezone.localtime(ahora or timezone.now())
        self.hoy = self.ahora.date()
        self.mes_actual = self.hoy.replace(day=1)
        self._inicio_mes = self._aware(self.mes_actual, 0, 0)

    @staticmethod
    def _aware(fecha, hora, minuto):
        return timezone.make_aware(datetime.combine(fecha, time(hora, minuto)))

    def mes(self, desplazamiento):
        """Primer día del mes a `desplazamiento` meses del actual (0, -1, -11…)."""
        total = self.mes_actual.year * 12 + self.mes_actual.month - 1 + desplazamiento
        return date(total // 12, total % 12 + 1, 1)

    def meses(self, cantidad=12):
        """Los `cantidad` meses que terminan en el actual, del más viejo al actual."""
        return [self.mes(-i) for i in range(cantidad - 1, -1, -1)]

    def dia(self, desplazamiento, dia):
        """Fecha nominal: día `dia` del mes a `desplazamiento` del actual."""
        return self.mes(desplazamiento).replace(day=dia)

    def instante(self, fecha, hora=10, minuto=0):
        """Instante real de una fecha y hora nominales. Nunca posterior a ahora."""
        nominal = self._aware(fecha, hora, minuto)
        if fecha < self.mes_actual:
            return min(nominal, self.ahora)
        # Más allá del presente nominal todo caería en «ahora», empatado y fuera
        # de orden: es un escenario mal escrito, no algo que convenga disimular.
        if nominal - self._inicio_mes > PRESENTE_NOMINAL:
            raise ValueError(f"{fecha} {hora:02d}:{minuto:02d} es posterior al presente nominal del mes en curso.")
        escala = (self.ahora - self._inicio_mes) / PRESENTE_NOMINAL
        return min(self._inicio_mes + (nominal - self._inicio_mes) * escala, self.ahora)

    def fecha(self, fecha, hora=12):
        """Fecha real de una fecha nominal, para los campos que guardan sólo el día."""
        return timezone.localtime(self.instante(fecha, hora)).date()

    @contextmanager
    def sintetica(self, fecha, hora=10, minuto=0):
        """Ejecuta el bloque con el reloj en el instante real de esa fecha nominal.

        Sirve para ordenar datos históricos sin hacer backfills en los servicios:
        cada servicio sigue validando contra «ahora», que acá es el pasado del
        escenario.

        No alcanza a los campos con `default=timezone.now`: guardan la función
        original al definirse el modelo. Ahí la fecha se pasa explícita.
        """
        instante = self.instante(fecha, hora, minuto)
        with patch("django.utils.timezone.now", return_value=instante):
            yield instante
