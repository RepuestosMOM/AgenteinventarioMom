import xmlrpc.client
import os

URL = 'https://www.repuestosmom.cl'
DB = 'repuestosmom-mom-main-25810633'
USERNAME = 'cio@repuestosmom.cl'
PASSWORD = '95512ac750d1fad3accc6b498a6490d9ef24f2f3'

def get_connection():
    try:
        common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(URL))
        uid = common.authenticate(DB, USERNAME, PASSWORD, {})
        if not uid:
            raise Exception("Credenciales incorrectas")
        models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(URL))
        return uid, models
    except Exception as e:
        print(f"Error conectando a Odoo: {e}")
        return None, None

def search_products(keyword: str, limit: int = 5):
    uid, models = get_connection()
    if not uid:
        return []
    
    # Buscamos coincidencias en nombre o código
    domain = ['|', ('name', 'ilike', keyword), ('default_code', 'ilike', keyword)]
    
    products = models.execute_kw(DB, uid, PASSWORD,
        'product.product', 'search_read',
        [domain],
        {'fields': ['name', 'default_code', 'qty_available', 'list_price'], 'limit': limit})
    
    return products
