import json

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import (Product, Category, Oferta, CarruselImages, Pedido,
                     DetallePedido, OpcionEnvio, Cliente, ConfiguracionTienda,
                     MercadoPagoCuenta)
from .context_processors import subs_visibles
from . import tienda_cart
from .whatsapp import wa_url, mensaje_pedido
from .utils import MPCheckOut, CuentaMpTest
from .views import obtener_orden_configurado


PRODUCTOS_POR_PAGINA = 24


def _guardar_ref_vendedor(request):
    """Captura ?ref=<username> para atribuir la venta a un vendedor"""
    ref = request.GET.get('ref')
    if ref:
        request.session['vendedor_ref'] = ref


def _vendedor_de_sesion(request):
    ref = request.session.get('vendedor_ref')
    if not ref:
        return None
    return User.objects.filter(username=ref).first()


def _pedido_es_mio(request, pedido):
    """Un pedido guest solo lo puede ver quien lo creó (misma sesión) o staff"""
    if request.user.is_authenticated and (
            request.user.is_staff or pedido.user_id == request.user.id
            or pedido.vendedor_id == request.user.id):
        return True
    return pedido.id in request.session.get('pedidos_tienda', [])


@ensure_csrf_cookie
def tienda(request, tp=None, es_rubro=False):
    """Catálogo principal: buscador, categorías, ofertas y flyers.
    tp + es_rubro=True filtra por categoría principal; tp solo filtra
    por subcategoría."""
    _guardar_ref_vendedor(request)
    Oferta.desactivar_ofertas_expiradas()

    q = request.GET.get('q', '').strip()
    orden = obtener_orden_configurado()
    # Agrupa el catálogo por categoría y subcategoría
    orden_jerarquico = ('categoria__main__nombre', 'categoria__orden',
                        'categoria__nombre', orden)

    rubro_activo = None
    if q:
        products = Product.objects.filter(
            Q(nombre__icontains=q) | Q(marca__icontains=q)
        ).order_by(orden)
    elif tp == 'ofertas':
        products = Product.objects.filter(en_oferta__activa=True).order_by(orden)
    elif es_rubro:
        products = Product.objects.filter(
            categoria__main__nombre=tp).order_by(*orden_jerarquico)
        rubro_activo = tp
    elif tp:
        products = Product.objects.filter(categoria__nombre=tp).order_by(orden)
        cat = Category.objects.filter(nombre=tp).select_related('main').first()
        if cat and cat.main_id:
            rubro_activo = cat.main.nombre
    else:
        products = Product.objects.all().order_by(*orden_jerarquico)

    paginator = Paginator(products.select_related('en_oferta', 'categoria'),
                          PRODUCTOS_POR_PAGINA)
    page_obj = paginator.get_page(request.GET.get('page'))

    subs_activas = (subs_visibles().filter(main__nombre=rubro_activo)
                    if rubro_activo else [])

    context = {
        'products': page_obj,
        'ofertas': Oferta.objects.filter(activa=True).select_related('producto')[:12],
        'flyers': CarruselImages.objects.all(),
        'destacados': Product.objects.filter(destacado=True, stock__gt=0)[:8],
        'tp': tp,
        'es_rubro': es_rubro,
        'rubro_activo': rubro_activo,
        'subs_activas': subs_activas,
        'q': q,
    }
    return render(request, 'tienda/catalogo.html', context)


@ensure_csrf_cookie
def carrito(request):
    """Página de carrito del guest con resumen y opciones de envío"""
    items, total, cantidad = tienda_cart.detalle(request.session)
    context = {
        'items': items,
        'total': total,
        'cantidad': cantidad,
        'opciones_envio': OpcionEnvio.objects.filter(activo=True),
    }
    return render(request, 'tienda/carrito.html', context)


@require_POST
def api_carrito(request):
    """API del carrito de sesión: action=add|set, product_id, cantidad"""
    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
    except json.JSONDecodeError:
        data = request.POST

    product_id = data.get('product_id')
    accion = data.get('action', 'add')
    cantidad = data.get('cantidad', 1)

    product = get_object_or_404(Product, id=product_id)
    if accion == 'set':
        tienda_cart.establecer(request.session, product_id, cantidad)
    else:
        tienda_cart.agregar(request.session, product_id, cantidad)

    items, total, count = tienda_cart.detalle(request.session)
    cant_item = request.session.get(tienda_cart.CART_KEY, {}).get(str(product.id), 0)
    precio, _ = tienda_cart.precio_producto(product)

    return JsonResponse({
        'ok': True,
        'count': count,
        'total': float(total),
        'item_cantidad': cant_item,
        'item_subtotal': float(precio * cant_item),
    })


def api_producto(request, product_id):
    """Datos del producto para la previsualización rápida (modal)"""
    product = get_object_or_404(Product, id=product_id)
    precio, oferta = tienda_cart.precio_producto(product)

    oferta_data = None
    if oferta and oferta.activa:
        tipo = oferta.tipo_oferta
        if tipo == 'descuento':
            badge = f"-{oferta.descuento}% OFF"
        elif tipo == 'multiplicidad':
            badge = oferta.get_tipo_multiplicidad_display()
        else:
            badge = "COMBO"
        oferta_data = {
            'badge': badge,
            'precio_final': float(oferta.precio_final),
            'precio_anterior': float(product.precio),
            'descripcion': str(oferta),
        }

    imagen = product.imagenurl or (product.imagen1.url if product.imagen1 else '')

    return JsonResponse({
        'id': product.id,
        'nombre': product.nombre,
        'marca': product.marca or '',
        'pack': product.unidad_x_pack or 0,
        'descripcion': product.descripcion or '',
        'imagen': imagen,
        'precio': float(precio),
        'oferta': oferta_data,
        'stock': product.stock,
        'detalle_url': f'/producto/detalle/{product.id}/',
    })


def checkout(request):
    """Checkout rápido: nombre + teléfono + dirección, sin cuenta"""
    items, total, cantidad = tienda_cart.detalle(request.session)
    if not items:
        messages.info(request, "Tu carrito está vacío.")
        return redirect('tienda_carrito')

    cfg = ConfiguracionTienda.get()
    opciones_envio = OpcionEnvio.objects.filter(activo=True)
    mp_disponible = cfg.mp_habilitado and MercadoPagoCuenta.objects.filter(activa=True).exists()
    datos = request.session.get('checkout_data', {})

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        localidad = request.POST.get('localidad', '').strip()
        observaciones = request.POST.get('observaciones', '').strip()
        opcion_envio_id = request.POST.get('opcion_envio')
        metodo_pago = request.POST.get('metodo_pago', 'acordado')

        datos = {'nombre': nombre, 'telefono': telefono, 'direccion': direccion,
                 'localidad': localidad}
        request.session['checkout_data'] = datos

        errores = []
        if not nombre:
            errores.append("Ingresá tu nombre.")
        if not Cliente.normalizar_telefono(telefono):
            errores.append("Ingresá un teléfono válido.")
        if not opcion_envio_id:
            errores.append("Elegí una opción de envío o retiro.")
        if metodo_pago == 'mercadopago' and not mp_disponible:
            metodo_pago = 'acordado'

        opcion_envio = OpcionEnvio.objects.filter(id=opcion_envio_id, activo=True).first()
        if opcion_envio_id and not opcion_envio:
            errores.append("La opción de envío no es válida.")

        if errores:
            for e in errores:
                messages.error(request, e)
        else:
            with transaction.atomic():
                cliente = Cliente.obtener_o_crear(telefono, {
                    'nombre': nombre, 'direccion': direccion, 'localidad': localidad,
                })
                cliente.ultima_compra = timezone.now()
                if not cliente.vendedor_id:
                    cliente.vendedor = _vendedor_de_sesion(request)
                cliente.save()

                pedido = Pedido.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    cliente=cliente,
                    vendedor=cliente.vendedor,
                    opcion_envio=opcion_envio,
                    costo_envio=opcion_envio.costo,
                    metodo_pago=metodo_pago,
                    observaciones=observaciones,
                )
                for item in items:
                    DetallePedido.objects.create(
                        pedido=pedido,
                        producto=item['product'],
                        cantidad=item['cantidad'],
                        subtotal=item['subtotal'],
                    )
                pedido.actualizar_pedido()

            request.session.setdefault('pedidos_tienda', []).append(pedido.id)
            tienda_cart.limpiar(request.session)
            return redirect('pedido_confirmado', pedido_id=pedido.id)

    context = {
        'items': items,
        'total': total,
        'cantidad': cantidad,
        'opciones_envio': opciones_envio,
        'mp_disponible': mp_disponible,
        'datos': datos,
    }
    return render(request, 'tienda/checkout.html', context)


def pedido_confirmado(request, pedido_id):
    """Pantalla de confirmación con link de WhatsApp y opción de pago MP"""
    pedido = get_object_or_404(Pedido, id=pedido_id)
    if not _pedido_es_mio(request, pedido):
        messages.error(request, "No tenés acceso a ese pedido.")
        return redirect('index')

    cfg = ConfiguracionTienda.get()
    context = {
        'pedido': pedido,
        'wa_pedido_url': wa_url(cfg.whatsapp_numero, mensaje_pedido(pedido)),
        'mp_disponible': (pedido.metodo_pago == 'mercadopago' and not pedido.pagado),
    }
    return render(request, 'tienda/confirmado.html', context)


def pedido_pago_mp(request, pedido_id):
    """Genera el botón de MercadoPago para un pedido guest"""
    pedido = get_object_or_404(Pedido, id=pedido_id)
    if not _pedido_es_mio(request, pedido):
        messages.error(request, "No tenés acceso a ese pedido.")
        return redirect('index')
    if pedido.pagado:
        messages.info(request, "Este pedido ya fue pagado.")
        return redirect('pedido_confirmado', pedido_id=pedido.id)

    cuenta_mp = MercadoPagoCuenta.objects.filter(activa=True).first() or CuentaMpTest()
    try:
        mp_checkout = MPCheckOut(cuenta_mp)
        total_con_envio = float(pedido.total_precio) + float(pedido.costo_envio or 0)
        mp_checkout.config(
            titulo=f"PEDIDO N°:{pedido.id} - {pedido.contacto_nombre}",
            monto=total_con_envio,
            unidad=1,
            ID="service",
            external_reference=f"pedido-{pedido.id}",
        )
        webhook_url = request.build_absolute_uri('/webhook/mercadopago/')
        mp_checkout.respuestas_urls(
            exito=request.build_absolute_uri(f'/pago-exitoso/{pedido.id}/'),
            fallo=request.build_absolute_uri(f'/pago-fallido/{pedido.id}/'),
            pendiente=request.build_absolute_uri(f'/pago-pendiente/{pedido.id}/'),
            notification_url=webhook_url,
        )
        boton_mp = mp_checkout.boton(label='PAGAR PEDIDO')
        if boton_mp.startswith('Error:'):
            raise Exception(boton_mp)
    except Exception as e:
        messages.error(request, f"Error al generar el pago: {e}")
        return redirect('pedido_confirmado', pedido_id=pedido.id)

    return render(request, 'tienda/pago_mp.html', {
        'pedido': pedido, 'boton_mp': boton_mp,
    })


def mis_pedidos(request):
    """Consulta de pedidos por número de teléfono (identidad del cliente)"""
    pedidos, cliente, telefono = None, None, request.GET.get('telefono', '').strip()

    if telefono:
        tel = Cliente.normalizar_telefono(telefono)
        cliente = Cliente.objects.filter(telefono=tel).first()
        if cliente:
            pedidos = (cliente.pedidos
                       .select_related('opcion_envio')
                       .prefetch_related('detalles_pedido__producto')
                       .order_by('-fecha_pedido'))
        else:
            messages.info(request, "No encontramos pedidos para ese teléfono.")

    cfg = ConfiguracionTienda.get()
    context = {
        'pedidos': pedidos,
        'cliente': cliente,
        'telefono': telefono,
        'wa_consulta_numero': cfg.whatsapp_numero,
    }
    return render(request, 'tienda/mis_pedidos.html', context)
