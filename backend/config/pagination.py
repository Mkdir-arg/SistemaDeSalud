"""
Paginación por defecto de la API.

Vive en su propio módulo y no en `apps/common.py` a propósito: DRF resuelve
`DEFAULT_PAGINATION_CLASS` mientras todavía se está inicializando
`rest_framework.generics`, así que si la clase estuviera en un módulo que importa
`rest_framework.viewsets` se produce un import circular y el proyecto no arranca.
Acá solo se importa `rest_framework.pagination`, que no arrastra nada.
"""
from rest_framework.pagination import PageNumberPagination


class Paginacion(PageNumberPagination):
    """Paginación estándar, con el tamaño de página elegible desde el cliente.

    `PageNumberPagination` ignora `?page_size=` a menos que se declare
    `page_size_query_param`. Sin esto, el selector de «filas por página» de la
    tabla no haría nada: la API devolvería 25 igual.
    """

    page_size_query_param = "page_size"
    max_page_size = 200
