# ─────────────────────────────────────────────────────────────────
# SCRIPT DE PRUEBA — Conexión directa XML-RPC a Odoo
# Uso: python tests/odoo_test.py
# ─────────────────────────────────────────────────────────────────
import xmlrpc.client

# ─────────────────────────────────────────────────────────────────
# CREDENCIALES DE PRUEBA
# ─────────────────────────────────────────────────────────────────
url      = 'https://www.repuestosmom.cl'
db       = 'repuestosmom-mom-main-25810633'
username = 'cio@repuestosmom.cl'
password = '95512ac750d1fad3accc6b498a6490d9ef24f2f3'


# ─────────────────────────────────────────────────────────────────
# TEST DE CONEXIÓN Y CONSULTA BÁSICA
# ─────────────────────────────────────────────────────────────────
def test_connection():
    try:
        common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
        uid = common.authenticate(db, username, password, {})
        if uid:
            print(f"✅ Conexión exitosa. User ID: {uid}")

            models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))
            products = models.execute_kw(db, uid, password,
                'product.product', 'search_read',
                [[]],
                {'fields': ['name', 'default_code'], 'limit': 5})

            print("Algunos productos encontrados:")
            for p in products:
                print(f"- {p.get('default_code', 'N/A')}: {p.get('name', 'N/A')}")
        else:
            print("❌ Error de autenticación. Verifica las credenciales.")
    except Exception as e:
        print(f"❌ Error al conectar: {e}")


if __name__ == '__main__':
    test_connection()
