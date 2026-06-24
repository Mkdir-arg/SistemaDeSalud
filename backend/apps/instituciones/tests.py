from django.test import TestCase

from apps.common import _coerce


class CoerceQueryParamTest(TestCase):
    """El mixin de filtrado debe convertir strings de query param a su tipo."""

    def test_booleanos(self):
        self.assertIs(_coerce("true"), True)
        self.assertIs(_coerce("false"), False)
        self.assertIs(_coerce("TRUE"), True)

    def test_null(self):
        self.assertIsNone(_coerce("null"))
        self.assertIsNone(_coerce("none"))

    def test_strings_normales(self):
        self.assertEqual(_coerce("recibido"), "recibido")
        self.assertEqual(_coerce("5"), "5")
