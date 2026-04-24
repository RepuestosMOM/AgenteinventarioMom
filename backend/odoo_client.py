
import xmlrpc.client
import os
import logging

log = logging.getLogger(__name__)

URL      = os.environ.get('ODOO_URL')
DB       = os.environ.get('ODOO_DB')
USERNAME = os.environ.get('ODOO_USER')
PASSWORD = os.environ.get('ODOO_PASS')

_uid     = None
_models  = None


def _reset_connection():
    global _uid, _models
    _uid = None
    _models = None

# ─────────────────────────────────────────────────────────────────
# MAPEO TÉCNICO — Sprint 1 (verificado contra Odoo 19)
#
# Los campos técnicos existen como product.attribute (no como campos
# directos del modelo). Solo ~20 productos tienen atributos asignados;
# la mayoría de la data técnica vive en el nombre del producto.
#
# IDs de atributos confirmados:
ATTR_OEM         = 14   # "Código OEM"          → referencia fabricante original
ATTR_MODELO      = 15   # "Modelo"              → ej. "Aveo, Sail"
ATTR_TIPO_VEH    = 12   # "Tipo de vehículo"    → categoría de vehículo
ATTR_DIAM_INT    = 23   # "Diámetro interior"   → mm
ATTR_DIAM_EXT    = 24   # "Diámetro externo"    → mm
ATTR_ESPESOR     = 25   # "Espesor"             → mm

# Campos directos en product.template con data:
# - name              → nombre libre (contiene marca/modelo/motor en texto)
# - default_code      → referencia interna
# - meli_field_brand  → Marca (MeLi) — actualmente vacío en producción
# - meli_field_part_number → Nº de pieza (MeLi) — actualmente vacío
# ─────────────────────────────────────────────────────────────────

PRODUCT_FIELDS = [
    'name',
    'default_code',
    'qty_available',
    'list_price',
    'x_studio_precio_con_iva',
    'categ_id',
    'description_sale',
    'meli_field_brand',
    'meli_field_part_number',
]


def get_connection(retry: bool = True):
    global _uid, _models
    if _uid is not None:
        return _uid, _models
    if not all([URL, DB, USERNAME, PASSWORD]):
        log.error("Faltan variables de entorno ODOO_URL, ODOO_DB, ODOO_USER o ODOO_PASS")
        return None, None
    try:
        common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(URL))
        uid = common.authenticate(DB, USERNAME, PASSWORD, {})
        if not uid:
            raise Exception("Credenciales incorrectas")
        _uid = uid
        _models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(URL))
        log.info("Conectado a Odoo (UID: %s)", _uid)
        return _uid, _models
    except Exception as e:
        log.error("Error conectando a Odoo: %s", e)
        return None, None


def _execute_with_reconnect(models, uid, model, method, args, kwargs):
    """Ejecuta una llamada XML-RPC y reconecta automáticamente si la sesión expiró."""
    try:
        return models.execute_kw(DB, uid, PASSWORD, model, method, args, kwargs)
    except Exception as e:
        if 'session' in str(e).lower() or 'access' in str(e).lower() or 'auth' in str(e).lower():
            log.warning("Sesión Odoo expirada, reconectando...")
            _reset_connection()
            new_uid, new_models = get_connection()
            if new_uid:
                return new_models.execute_kw(DB, new_uid, PASSWORD, model, method, args, kwargs)
        raise


def _get_product_attributes(models, uid, product_ids: list) -> dict:
    """
    Dado una lista de product.product IDs, retorna sus atributos técnicos
    como dict {product_id: {attr_name: value, ...}}.
    """
    if not product_ids:
        return {}

    # Obtener los template IDs correspondientes
    products = _execute_with_reconnect(models, uid,
        'product.product', 'read',
        [product_ids],
        {'fields': ['product_tmpl_id']})
    tmpl_map = {p['id']: p['product_tmpl_id'][0] for p in products if p.get('product_tmpl_id')}
    tmpl_ids = list(set(tmpl_map.values()))

    # Buscar líneas de atributos para esos templates
    attr_lines = _execute_with_reconnect(models, uid,
        'product.template.attribute.line', 'search_read',
        [[('product_tmpl_id', 'in', tmpl_ids),
          ('attribute_id', 'in', [ATTR_OEM, ATTR_MODELO, ATTR_TIPO_VEH,
                                   ATTR_DIAM_INT, ATTR_DIAM_EXT, ATTR_ESPESOR])]],
        {'fields': ['product_tmpl_id', 'attribute_id', 'value_ids']})

    if not attr_lines:
        return {}

    # Obtener nombres de valores
    all_value_ids = [vid for line in attr_lines for vid in line['value_ids']]
    if not all_value_ids:
        return {}

    values = _execute_with_reconnect(models, uid,
        'product.attribute.value', 'read',
        [all_value_ids],
        {'fields': ['name', 'attribute_id']})
    value_map = {v['id']: v for v in values}

    # Construir resultado por template
    tmpl_attrs = {}
    for line in attr_lines:
        tmpl_id = line['product_tmpl_id'][0]
        attr_name = line['attribute_id'][1]
        names = [value_map[vid]['name'] for vid in line['value_ids'] if vid in value_map]
        tmpl_attrs.setdefault(tmpl_id, {})[attr_name] = ', '.join(names)

    # Mapear de vuelta a product IDs
    result = {}
    for prod_id, tmpl_id in tmpl_map.items():
        if tmpl_id in tmpl_attrs:
            result[prod_id] = tmpl_attrs[tmpl_id]

    return result


def search_products(keyword: str, limit: int = 10) -> list:
    """
    Búsqueda general por nombre o código interno.
    Retorna productos enriquecidos con atributos técnicos estructurados.
    """
    uid, models = get_connection()
    if not uid:
        return []

    domain = ['|', ('name', 'ilike', keyword), ('default_code', 'ilike', keyword)]

    products = _execute_with_reconnect(models, uid,
        'product.product', 'search_read',
        [domain],
        {'fields': PRODUCT_FIELDS, 'limit': limit})

    if not products:
        return []

    # Enriquecer con atributos técnicos
    prod_ids = [p['id'] for p in products]
    attrs_by_product = _get_product_attributes(models, uid, prod_ids)

    for p in products:
        p['_attrs'] = attrs_by_product.get(p['id'], {})

    return products


def search_by_attribute(attr_id: int, value_keyword: str, limit: int = 10) -> list:
    """
    Búsqueda estructurada por atributo técnico.
    Útil para buscar por OEM, Modelo, Diámetro, etc.

    Ejemplo:
        search_by_attribute(ATTR_OEM, "96445053")
        search_by_attribute(ATTR_MODELO, "Aveo")
    """
    uid, models = get_connection()
    if not uid:
        return []

    # Encontrar valores del atributo que coincidan
    attr_values = _execute_with_reconnect(models, uid,
        'product.attribute.value', 'search_read',
        [[('attribute_id', '=', attr_id), ('name', 'ilike', value_keyword)]],
        {'fields': ['name'], 'limit': 20})

    if not attr_values:
        return []

    value_ids = [v['id'] for v in attr_values]

    # Buscar líneas de atributos que contengan esos valores
    attr_lines = _execute_with_reconnect(models, uid,
        'product.template.attribute.line', 'search_read',
        [[('attribute_id', '=', attr_id), ('value_ids', 'in', value_ids)]],
        {'fields': ['product_tmpl_id']})

    if not attr_lines:
        return []

    tmpl_ids = list({line['product_tmpl_id'][0] for line in attr_lines})

    # Buscar product.product con esos templates
    products = _execute_with_reconnect(models, uid,
        'product.product', 'search_read',
        [[('product_tmpl_id', 'in', tmpl_ids)]],
        {'fields': PRODUCT_FIELDS, 'limit': limit})

    if not products:
        return []

    prod_ids = [p['id'] for p in products]
    attrs_by_product = _get_product_attributes(models, uid, prod_ids)
    for p in products:
        p['_attrs'] = attrs_by_product.get(p['id'], {})

    return products


def search_oem(oem_code: str, limit: int = 10) -> list:
    """Busca productos por código OEM."""
    return search_by_attribute(ATTR_OEM, oem_code, limit)


def search_by_model(model_name: str, limit: int = 10) -> list:
    """
    Búsqueda combinada por modelo de vehículo.
    Primero busca en atributos estructurados, luego complementa con nombre.
    """
    uid, models = get_connection()
    if not uid:
        return []

    structured = search_by_attribute(ATTR_MODELO, model_name, limit)
    structured_ids = {p['id'] for p in structured}

    # Complementar con búsqueda en nombre
    name_results = _execute_with_reconnect(models, uid,
        'product.product', 'search_read',
        [[('name', 'ilike', model_name), ('id', 'not in', list(structured_ids))]],
        {'fields': PRODUCT_FIELDS, 'limit': limit})

    prod_ids = [p['id'] for p in name_results]
    attrs_by_product = _get_product_attributes(models, uid, prod_ids)
    for p in name_results:
        p['_attrs'] = attrs_by_product.get(p['id'], {})

    combined = structured + name_results
    return combined[:limit]


def format_product(p: dict) -> str:
    """Formatea un producto para respuesta del agente."""
    code = p.get('default_code') or 'Sin código'
    name = p.get('name', 'Sin nombre')
    price = p.get('x_studio_precio_con_iva') or p.get('list_price', 0)
    stock = p.get('qty_available', 0)
    categ = p.get('categ_id', [None, ''])[1] if p.get('categ_id') else ''
    attrs = p.get('_attrs', {})

    lines = [f"**{name}** (Ref: `{code}`)"]
    lines.append(f"Stock: **{stock:.0f}** uds | Precio: **${price:,.0f} CLP**")

    if categ:
        lines.append(f"Categoría: {categ}")

    if attrs.get('Código OEM'):
        lines.append(f"OEM: {attrs['Código OEM']}")
    if attrs.get('Modelo'):
        lines.append(f"Modelo: {attrs['Modelo']}")
    if attrs.get('Tipo de vehículo'):
        lines.append(f"Vehículo: {attrs['Tipo de vehículo']}")
    if attrs.get('Diámetro interior'):
        lines.append(f"Ø interior: {attrs['Diámetro interior']}")
    if attrs.get('Diámetro externo'):
        lines.append(f"Ø externo: {attrs['Diámetro externo']}")
    if attrs.get('Espesor'):
        lines.append(f"Espesor: {attrs['Espesor']}")

    return '\n'.join(lines)
