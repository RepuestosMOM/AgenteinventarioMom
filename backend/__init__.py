from .odoo_client import (
    get_connection,
    search_products,
    search_oem,
    search_by_model,
    search_by_attribute,
    format_product,
    ATTR_OEM,
    ATTR_MODELO,
    ATTR_TIPO_VEH,
    ATTR_DIAM_INT,
    ATTR_DIAM_EXT,
    ATTR_ESPESOR,
)

# Inicializar conexión al cargar el paquete
get_connection()
