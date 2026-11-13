from .models import Product, Oferta

CART_KEY = 'tienda_cart'


def _cart(session):
    """Devuelve el dict {product_id: cantidad} guardado en sesión"""
    return session.setdefault(CART_KEY, {})


def agregar(session, product_id, cantidad=1):
    cart = _cart(session)
    pid = str(product_id)
    cart[pid] = cart.get(pid, 0) + int(cantidad)
    if cart[pid] <= 0:
        cart.pop(pid, None)
    session.modified = True


def establecer(session, product_id, cantidad):
    cart = _cart(session)
    pid = str(product_id)
    cantidad = int(cantidad)
    if cantidad <= 0:
        cart.pop(pid, None)
    else:
        cart[pid] = cantidad
    session.modified = True


def limpiar(session):
    session[CART_KEY] = {}
    session.modified = True


def cantidad_total(session):
    return sum(_cart(session).values())


def precio_producto(product):
    """Precio vigente: oferta activa con stock si existe, si no precio base"""
    oferta = getattr(product, 'en_oferta', None)
    if oferta and oferta.activa and oferta.tiene_stock_disponible():
        return oferta.precio_final, oferta
    return product.precio, oferta


def detalle(session):
    """Devuelve (items, total, cantidad) resolviendo productos de la sesión"""
    cart = _cart(session)
    productos = {p.id: p for p in Product.objects.filter(id__in=cart.keys())
                 .select_related('en_oferta')}
    items, total, cantidad = [], 0, 0
    for pid, qty in cart.items():
        product = productos.get(int(pid))
        if not product:
            continue
        precio, oferta = precio_producto(product)
        subtotal = precio * qty
        items.append({
            'product': product,
            'cantidad': qty,
            'precio': precio,
            'subtotal': subtotal,
            'en_oferta': bool(oferta and oferta.activa),
        })
        total += subtotal
        cantidad += qty
    return items, total, cantidad
