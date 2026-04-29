# ─────────────────────────────────────────────────────────────────
# IMPORTS Y CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────
from __future__ import annotations
import xmlrpc.client
import os
import logging

log = logging.getLogger(__name__)

URL      = os.environ.get('ODOO_URL')
DB       = os.environ.get('ODOO_DB')
USERNAME = os.environ.get('ODOO_USER')
PASSWORD = os.environ.get('ODOO_PASS')

_uid    = None
_models = None

# ─────────────────────────────────────────────────────────────────
# MAPEO TÉCNICO DE ATRIBUTOS (verificado contra Odoo 19)
#

# Claves normalizadas → IDs de product.attribute en la instancia.
# Solo ~20 productos tienen atributos asignados; la mayoría de la
# info técnica vive en el nombre del producto.
# ─────────────────────────────────────────────────────────────────
ATTRS = {
    'oem':       14,   # Código OEM — referencia del fabricante original
    'model':     15,   # Modelo de vehículo — ej. "Aveo, Sail"
    'type':      12,   # Tipo de vehículo — categoría general
    'diam_int':  23,   # Diámetro interior (mm)
    'diam_ext':  24,   # Diámetro externo (mm)
    'thickness': 25,   # Espesor (mm)
}

_ATTR_ID_TO_KEY = {v: k for k, v in ATTRS.items()}

# product_tmpl_id se incluye para evitar una llamada XML-RPC extra en _get_attrs
PRODUCT_FIELDS = [
    'name',
    'default_code',
    'product_tmpl_id',
    'qty_available',
    'list_price',
    'x_studio_precio_con_iva',
    'categ_id',
    'description_sale',
    'meli_field_brand',
    'meli_field_part_number',
]


# ─────────────────────────────────────────────────────────────────
# CONEXIÓN XML-RPC
# ─────────────────────────────────────────────────────────────────
def _reset_connection():
    global _uid, _models
    _uid = None
    _models = None


def get_connection():
    global _uid, _models
    if _uid is not None:
        return _uid, _models
    if not all([URL, DB, USERNAME, PASSWORD]):
        log.error("Faltan variables de entorno ODOO_URL, ODOO_DB, ODOO_USER o ODOO_PASS")
        return None, None
    try:
        common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
        uid = common.authenticate(DB, USERNAME, PASSWORD, {})
        if not uid:
            raise Exception("Credenciales incorrectas")
        _uid = uid
        _models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')
        log.info("Conectado a Odoo (UID: %s)", _uid)
        return _uid, _models
    except Exception as e:
        log.error("Error conectando a Odoo: %s", e)
        return None, None


def _execute(models, uid, model, method, args, kwargs=None):
    """Llama XML-RPC y reconecta automáticamente si la sesión expiró."""
    kwargs = kwargs or {}
    try:
        return models.execute_kw(DB, uid, PASSWORD, model, method, args, kwargs)
    except Exception as e:
        if any(k in str(e).lower() for k in ('session', 'access', 'auth')):
            log.warning("Sesión Odoo expirada, reconectando...")
            _reset_connection()
            new_uid, new_models = get_connection()
            if new_uid:
                return new_models.execute_kw(DB, new_uid, PASSWORD, model, method, args, kwargs)
        raise


# ─────────────────────────────────────────────────────────────────
# ATRIBUTOS TÉCNICOS
# ─────────────────────────────────────────────────────────────────
def _get_attrs(models, uid, products: list) -> dict:
    """
    Dado una lista de registros product.product (con product_tmpl_id ya cargado),
    retorna {product_id: {clave_normalizada: valor}} para los atributos de ATTRS.
    Omite silenciosamente atributos vacíos o sin valor.
    """
    if not products:
        return {}

    tmpl_map = {
        p['id']: p['product_tmpl_id'][0]
        for p in products
        if p.get('product_tmpl_id')
    }
    tmpl_ids = list(set(tmpl_map.values()))
    if not tmpl_ids:
        return {}

    attr_lines = _execute(models, uid,
        'product.template.attribute.line', 'search_read',
        [[('product_tmpl_id', 'in', tmpl_ids),
          ('attribute_id', 'in', list(ATTRS.values()))]],
        {'fields': ['product_tmpl_id', 'attribute_id', 'value_ids']})

    if not attr_lines:
        return {}

    all_value_ids = [vid for line in attr_lines for vid in line['value_ids']]
    if not all_value_ids:
        return {}

    values = _execute(models, uid,
        'product.attribute.value', 'read',
        [all_value_ids],
        {'fields': ['name', 'attribute_id']})
    value_map = {v['id']: v for v in values}

    tmpl_attrs: dict = {}
    for line in attr_lines:
        tmpl_id = line['product_tmpl_id'][0]
        attr_id = line['attribute_id'][0]
        key     = _ATTR_ID_TO_KEY.get(attr_id)
        if not key:
            continue
        names = [value_map[vid]['name'] for vid in line['value_ids'] if vid in value_map]
        if names:
            tmpl_attrs.setdefault(tmpl_id, {})[key] = ', '.join(names)

    return {
        prod_id: tmpl_attrs[tmpl_id]
        for prod_id, tmpl_id in tmpl_map.items()
        if tmpl_id in tmpl_attrs
    }


def _enrich(models, uid, products: list) -> list:
    """Agrega _attrs a cada producto y ordena por stock descendente."""
    if not products:
        return []
    attrs_map = _get_attrs(models, uid, products)
    for p in products:
        p['_attrs'] = attrs_map.get(p['id'], {})
    products.sort(key=lambda p: p.get('qty_available', 0), reverse=True)
    return products


# ─────────────────────────────────────────────────────────────────
# FUNCIONES DE BÚSQUEDA
# ─────────────────────────────────────────────────────────────────
def _search_by_attr(models, uid, attr_key: str, value: str, limit: int) -> list:
    """Busca product.product filtrando por un atributo técnico de ATTRS."""
    attr_id = ATTRS.get(attr_key)
    if not attr_id:
        return []

    attr_values = _execute(models, uid,
        'product.attribute.value', 'search_read',
        [[('attribute_id', '=', attr_id), ('name', 'ilike', value)]],
        {'fields': ['name'], 'limit': 20})

    if not attr_values:
        return []

    value_ids = [v['id'] for v in attr_values]
    attr_lines = _execute(models, uid,
        'product.template.attribute.line', 'search_read',
        [[('attribute_id', '=', attr_id), ('value_ids', 'in', value_ids)]],
        {'fields': ['product_tmpl_id']})

    if not attr_lines:
        return []

    tmpl_ids = list({line['product_tmpl_id'][0] for line in attr_lines})
    return _execute(models, uid,
        'product.product', 'search_read',
        [[('product_tmpl_id', 'in', tmpl_ids)]],
        {'fields': PRODUCT_FIELDS, 'limit': limit}) or []


def search_products(keyword: str, limit: int = 10) -> list:
    """
    Búsqueda general: nombre, código interno y código OEM.
    Combina las tres fuentes y deduplicada por ID.
    """
    uid, models = get_connection()
    if not uid:
        return []

    # Buscar template IDs que tengan ese OEM en atributos
    oem_tmpl_ids: list = []
    oem_values = _execute(models, uid,
        'product.attribute.value', 'search_read',
        [[('attribute_id', '=', ATTRS['oem']), ('name', 'ilike', keyword)]],
        {'fields': ['name'], 'limit': 20})
    if oem_values:
        oem_value_ids = [v['id'] for v in oem_values]
        oem_lines = _execute(models, uid,
            'product.template.attribute.line', 'search_read',
            [[('attribute_id', '=', ATTRS['oem']), ('value_ids', 'in', oem_value_ids)]],
            {'fields': ['product_tmpl_id']})
        oem_tmpl_ids = list({line['product_tmpl_id'][0] for line in oem_lines})

    if oem_tmpl_ids:
        domain = ['|', '|',
            ('name', 'ilike', keyword),
            ('default_code', 'ilike', keyword),
            ('product_tmpl_id', 'in', oem_tmpl_ids),
        ]
    else:
        domain = ['|',
            ('name', 'ilike', keyword),
            ('default_code', 'ilike', keyword),
        ]

    products = _execute(models, uid,
        'product.product', 'search_read',
        [domain],
        {'fields': PRODUCT_FIELDS, 'limit': limit}) or []

    return _enrich(models, uid, products)


def search_oem(oem_code: str, limit: int = 10) -> list:
    """
    Busca por código OEM en atributos estructurados.
    Si no encuentra nada, busca en default_code y name como fallback
    (cubre el caso en que el modelo enruta mal una referencia interna).
    """
    uid, models = get_connection()
    if not uid:
        return []

    products = _search_by_attr(models, uid, 'oem', oem_code, limit)
    if products:
        return _enrich(models, uid, products)

    # Fallback: buscar como referencia interna o nombre
    fallback = _execute(models, uid,
        'product.product', 'search_read',
        [['|', ('default_code', 'ilike', oem_code), ('name', 'ilike', oem_code)]],
        {'fields': PRODUCT_FIELDS, 'limit': limit}) or []
    return _enrich(models, uid, fallback)


def search_by_model(model_name: str, limit: int = 10) -> list:
    """
    Búsqueda combinada por modelo de vehículo.
    Primero atributos estructurados, luego complementa con búsqueda en nombre.
    """
    uid, models = get_connection()
    if not uid:
        return []

    structured    = _search_by_attr(models, uid, 'model', model_name, limit)
    structured_ids = {p['id'] for p in structured}

    name_results = _execute(models, uid,
        'product.product', 'search_read',
        [[('name', 'ilike', model_name), ('id', 'not in', list(structured_ids))]],
        {'fields': PRODUCT_FIELDS, 'limit': limit}) or []

    combined = structured + name_results
    return _enrich(models, uid, combined[:limit])


# ─────────────────────────────────────────────────────────────────
# DETALLE Y CATÁLOGO
# ─────────────────────────────────────────────────────────────────
def get_product_detail(product_id: int) -> dict | None:
    """Retorna ficha técnica completa de un producto."""
    uid, models = get_connection()
    if not uid:
        return None

    products = _execute(models, uid,
        'product.product', 'search_read',
        [[('id', '=', product_id)]],
        {'fields': PRODUCT_FIELDS + ['description_pickingin', 'barcode']})

    if not products:
        return None

    p     = _enrich(models, uid, products)[0]
    attrs = p.get('_attrs', {})

    return {
        'id':          p.get('id'),
        'name':        p.get('name', ''),
        'code':        p.get('default_code') or '',
        'barcode':     p.get('barcode') or '',
        'stock':       p.get('qty_available', 0),
        'price':       p.get('x_studio_precio_con_iva') or p.get('list_price', 0),
        'category':    p['categ_id'][1] if p.get('categ_id') else '',
        'description': p.get('description_sale') or '',
        'brand':       p.get('meli_field_brand') or '',
        'part_number': p.get('meli_field_part_number') or '',
        'attrs':       attrs,
    }


def serialize_catalog_row(p: dict) -> dict:
    """Convierte un producto raw de Odoo al formato que expone /api/catalog."""
    return {
        'id':       p.get('id'),
        'name':     p.get('name', ''),
        'code':     p.get('default_code') or '',
        'stock':    p.get('qty_available', 0),
        'price':    p.get('x_studio_precio_con_iva') or p.get('list_price', 0),
        'category': p['categ_id'][1] if p.get('categ_id') else '',
    }


def get_catalog(page: int = 1, limit: int = 50, solo_con_stock: bool = False) -> dict:
    """Retorna productos paginados para el catálogo."""
    uid, models = get_connection()
    if not uid:
        return {'products': [], 'total': 0}

    domain = [('qty_available', '>', 0)] if solo_con_stock else []
    offset = (page - 1) * limit

    total    = _execute(models, uid, 'product.product', 'search_count', [domain], {})
    products = _execute(models, uid,
        'product.product', 'search_read',
        [domain],
        {'fields': PRODUCT_FIELDS, 'limit': limit, 'offset': offset, 'order': 'name asc'}) or []

    products.sort(key=lambda p: p.get('qty_available', 0), reverse=True)
    return {'products': products, 'total': total or 0}


# ─────────────────────────────────────────────────────────────────
# FORMATEO DE RESPUESTA
# ─────────────────────────────────────────────────────────────────
def format_product(p: dict) -> str:
    """Formatea un producto para respuesta del agente."""
    code  = p.get('default_code') or 'Sin código'
    name  = p.get('name', 'Sin nombre')
    price = p.get('x_studio_precio_con_iva') or p.get('list_price', 0)
    stock = p.get('qty_available', 0)
    categ = p['categ_id'][1] if p.get('categ_id') else ''
    attrs = p.get('_attrs', {})

    lines = [f"**{name}** (Ref: `{code}`)"]
    lines.append(f"Stock: **{stock:.0f}** uds | Precio: **${price:,.0f} CLP**")

    if categ:
        lines.append(f"Categoría: {categ}")
    if attrs.get('oem'):
        lines.append(f"OEM: {attrs['oem']}")
    if attrs.get('model'):
        lines.append(f"Modelo: {attrs['model']}")
    if attrs.get('type'):
        lines.append(f"Vehículo: {attrs['type']}")
    if attrs.get('diam_int'):
        lines.append(f"Ø interior: {attrs['diam_int']}")
    if attrs.get('diam_ext'):
        lines.append(f"Ø externo: {attrs['diam_ext']}")
    if attrs.get('thickness'):
        lines.append(f"Espesor: {attrs['thickness']}")

    return '\n'.join(lines)
