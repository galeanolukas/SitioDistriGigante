from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Pedido, Product, MovimientoCaja, Category, Perfil


# ---------- Roles ----------

ROLES_PANEL = {'mostrador', 'deposito', 'caja', 'admin'}

ROL_LABELS = {
    'admin': 'Administrador',
    'mostrador': 'Mostrador',
    'deposito': 'Depósito',
    'caja': 'Caja',
    'vendedor': 'Vendedor',
    'cliente': 'Cliente',
}


def get_rol(user):
    """Rol operativo del usuario para el panel.
    Prioridad: superuser > perfil.tipo_usuario > staff sin perfil."""
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return 'admin'
    perfil = getattr(user, 'perfil', None)
    rol = getattr(perfil, 'tipo_usuario', None)
    if rol:
        return rol
    return 'admin' if user.is_staff else None


def puede(rol, *permitidos):
    return rol == 'admin' or rol in permitidos


def panel_access(view):
    """Decorador: solo usuarios con rol operativo acceden al panel"""
    @login_required
    def wrap(request, *args, **kwargs):
        rol = get_rol(request.user)
        if rol not in ROLES_PANEL:
            messages.error(request, "No tenés acceso al panel de gestión.")
            return redirect('index')
        request.rol = rol
        return view(request, *args, **kwargs)
    return wrap


# ---------- Transiciones de pedido ----------

# accion -> (estado_origen permitidos, estado_destino, roles permitidos)
ACCIONES = {
    'aprobar':    (('pendiente',),               'aprobado',   ('mostrador',)),
    'preparar':   (('aprobado',),                'preparando', ('deposito',)),
    'despachar':  (('aprobado', 'preparando'),   'despachado', ('deposito',)),
    'entregar':   (('aprobado', 'preparando', 'despachado'), 'entregado', ('deposito', 'caja')),
    'cancelar':   (('pendiente', 'aprobado'),    'cancelado',  ('mostrador',)),
    'pagar':      (None,                         None,         ('caja',)),  # solo marca pagado
}


@panel_access
@require_POST
def pedido_accion(request, pedido_id):
    """Ejecuta una transición de estado o marca de pago sobre un pedido"""
    pedido = get_object_or_404(Pedido, id=pedido_id)
    accion = request.POST.get('accion')
    origen = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'panel'

    if accion not in ACCIONES:
        messages.error(request, "Acción no válida.")
        return redirect(origen)

    estados_origen, destino, roles = ACCIONES[accion]
    if not puede(request.rol, *roles):
        messages.error(request, f"Tu rol ({ROL_LABELS.get(request.rol)}) no puede hacer eso.")
        return redirect(origen)

    if accion == 'pagar':
        pedido.pagado = True
        pedido.save()
        messages.success(request, f"Pedido #{pedido.id} marcado como pagado.")
        return redirect(origen)

    if pedido.estado not in estados_origen:
        messages.warning(request,
            f"El pedido #{pedido.id} está '{pedido.get_estado_display()}', no se puede {accion}.")
        return redirect(origen)

    pedido.estado = destino
    pedido.save()
    messages.success(request,
        f"Pedido #{pedido.id} → {pedido.get_estado_display()}. "
        f"Avisá al cliente por WhatsApp si hace falta.")
    return redirect(origen)


# ---------- Vistas por rol ----------

@panel_access
def home(request):
    hoy = timezone.now().date()
    pedidos_hoy = Pedido.objects.filter(fecha_pedido__date=hoy).exclude(estado='cancelado')

    context = {
        'rol': request.rol,
        'rol_label': ROL_LABELS.get(request.rol, request.rol),
        'pendientes': Pedido.objects.filter(estado='pendiente').count(),
        'a_preparar': Pedido.objects.filter(estado__in=['aprobado', 'preparando']).count(),
        'pedidos_hoy': pedidos_hoy.count(),
        'vendido_hoy': (pedidos_hoy.aggregate(t=Sum('total_precio'))['t'] or 0),
        'sin_pagar': pedidos_hoy.filter(pagado=False).count(),
    }
    return render(request, 'panel/home.html', context)


@panel_access
def mostrador(request):
    if not puede(request.rol, 'mostrador'):
        messages.error(request, "Esta sección es para Mostrador.")
        return redirect('panel')

    hoy = timezone.now().date()
    context = {
        'rol': request.rol,
        'nuevos': (Pedido.objects.filter(estado='pendiente')
                   .select_related('cliente', 'opcion_envio')
                   .prefetch_related('detalles_pedido__producto')
                   .order_by('fecha_pedido')),
        'gestionados': (Pedido.objects.filter(fecha_pedido__date=hoy)
                        .exclude(estado='pendiente')
                        .select_related('cliente').order_by('-fecha_pedido')[:20]),
    }
    return render(request, 'panel/mostrador.html', context)


@panel_access
def deposito(request):
    if not puede(request.rol, 'deposito'):
        messages.error(request, "Esta sección es para Depósito.")
        return redirect('panel')

    q = request.GET.get('q', '').strip()
    productos = None
    if q:
        productos = Product.objects.filter(
            Q(nombre__icontains=q) | Q(marca__icontains=q)
        ).order_by('stock')[:20]

    context = {
        'rol': request.rol,
        'a_preparar': (Pedido.objects.filter(estado__in=['aprobado', 'preparando'])
                       .select_related('cliente', 'opcion_envio')
                       .prefetch_related('detalles_pedido__producto')
                       .order_by('estado', 'fecha_pedido')),
        'despachados': (Pedido.objects.filter(estado__in=['despachado', 'entregado'],
                                              fecha_pedido__date=timezone.now().date())
                        .select_related('cliente').order_by('-fecha_pedido')[:15]),
        'q': q,
        'productos': productos,
        'sin_stock': Product.objects.filter(stock=0).order_by('nombre')[:15],
    }
    return render(request, 'panel/deposito.html', context)


@panel_access
@require_POST
def stock_update(request):
    """Actualización rápida de stock desde Depósito"""
    if not puede(request.rol, 'deposito'):
        messages.error(request, "Solo Depósito puede modificar stock.")
        return redirect('panel')

    product = get_object_or_404(Product, id=request.POST.get('product_id'))
    try:
        product.stock = max(0, int(request.POST.get('stock', 0)))
        product.save()
        messages.success(request, f"Stock de {product.nombre}: {product.stock}")
    except (ValueError, TypeError):
        messages.error(request, "Cantidad inválida.")

    return redirect(request.META.get('HTTP_REFERER') or 'panel_deposito')


@panel_access
def caja(request):
    if not puede(request.rol, 'caja'):
        messages.error(request, "Esta sección es para Caja.")
        return redirect('panel')

    hoy = timezone.now().date()

    if request.method == 'POST':
        tipo = request.POST.get('tipo')
        try:
            monto = int(request.POST.get('monto', 0))
        except (ValueError, TypeError):
            monto = 0
        descripcion = request.POST.get('descripcion', '').strip()
        if tipo in ('ingreso', 'egreso', 'retiro') and monto > 0 and descripcion:
            MovimientoCaja.objects.create(
                tipo=tipo, monto=monto, descripcion=descripcion, user=request.user)
            messages.success(request, "Movimiento registrado.")
        else:
            messages.error(request, "Completá tipo, monto y descripción.")
        return redirect('panel_caja')

    pedidos_hoy = (Pedido.objects.filter(fecha_pedido__date=hoy)
                   .exclude(estado='cancelado').select_related('cliente'))
    movimientos_hoy = MovimientoCaja.objects.filter(fecha__date=hoy)

    vendido = sum(p.total_precio + (p.costo_envio or 0) for p in pedidos_hoy)
    cobrado = sum(p.total_precio + (p.costo_envio or 0) for p in pedidos_hoy if p.pagado)
    movs = {t: movimientos_hoy.filter(tipo=t).aggregate(t=Sum('monto'))['t'] or 0
            for t in ('ingreso', 'egreso', 'retiro')}

    context = {
        'rol': request.rol,
        'vendido_hoy': vendido,
        'cobrado_hoy': cobrado,
        'por_cobrar': vendido - cobrado,
        'movs': movs,
        'caja_neta': cobrado + movs['ingreso'] - movs['egreso'] - movs['retiro'],
        'movimientos': movimientos_hoy.select_related('user'),
        'pedidos': pedidos_hoy.order_by('-fecha_pedido'),
    }
    return render(request, 'panel/caja.html', context)


@panel_access
def pedidos(request):
    """Listado completo de pedidos con filtros (todos los roles)"""
    estado = request.GET.get('estado', '')
    q = request.GET.get('q', '').strip()

    qs = (Pedido.objects.select_related('cliente', 'vendedor', 'opcion_envio')
          .order_by('-fecha_pedido'))
    if estado:
        qs = qs.filter(estado=estado)
    if q:
        qs = qs.filter(
            Q(id__icontains=q) |
            Q(cliente__nombre__icontains=q) |
            Q(cliente__telefono__icontains=q) |
            Q(user__username__icontains=q)
        )

    context = {
        'rol': request.rol,
        'pedidos': Paginator(qs, 25).get_page(request.GET.get('page')),
        'estado': estado,
        'estados': Pedido.ESTADO_CHOICES,
        'q': q,
    }
    return render(request, 'panel/pedidos.html', context)


# ---------- Gestión de contenido (solo admin) ----------

def _solo_admin(request):
    if request.rol != 'admin':
        messages.error(request, "Esta sección es solo para administradores.")
        return False
    return True


def _asignar_rol(user, rol, es_admin=False):
    """Sincroniza perfil.tipo_usuario, grupos y flags staff/superuser."""
    try:
        perfil = user.perfil  # misma instancia que la signal post_save vuelve a guardar
    except Perfil.DoesNotExist:
        perfil = Perfil(user=user)
    perfil.tipo_usuario = 'admin' if es_admin else rol
    perfil.save()

    user.is_superuser = es_admin
    user.is_staff = es_admin or rol != 'cliente'
    user.save()

    user.groups.clear()
    if es_admin:
        grupo, _ = Group.objects.get_or_create(name='admin')
    else:
        grupo, _ = Group.objects.get_or_create(name=rol)
    user.groups.add(grupo)


@panel_access
def categorias(request):
    """Gestión de categorías: orden y visibilidad en la tienda"""
    if not _solo_admin(request):
        return redirect('panel')

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        if nombre:
            ultimo = Category.objects.aggregate(m=Count('id'))['m'] or 0
            Category.objects.get_or_create(
                nombre=nombre,
                defaults={'orden': request.POST.get('orden') or ultimo},
            )
            messages.success(request, f"Categoría '{nombre}' creada.")
        else:
            messages.error(request, "Ingresá un nombre para la categoría.")
        return redirect('panel_categorias')

    context = {
        'rol': request.rol,
        'categorias': Category.objects.annotate(
            total_productos=Count('categoria')),
    }
    return render(request, 'panel/categorias.html', context)


@panel_access
@require_POST
def categoria_guardar(request, cat_id):
    if not _solo_admin(request):
        return redirect('panel')
    cat = get_object_or_404(Category, id=cat_id)
    nombre = request.POST.get('nombre', '').strip()
    if nombre:
        cat.nombre = nombre
    cat.orden = request.POST.get('orden') or 0
    cat.visible = request.POST.get('visible') == 'on'
    cat.save()
    messages.success(request, f"Categoría '{cat.nombre}' actualizada.")
    return redirect('panel_categorias')


@panel_access
@require_POST
def categoria_borrar(request, cat_id):
    if not _solo_admin(request):
        return redirect('panel')
    cat = get_object_or_404(Category, id=cat_id)
    if cat.categoria.exists():
        messages.error(request,
            f"'{cat.nombre}' tiene productos asignados. Reasignalos antes de borrarla.")
    else:
        cat.delete()
        messages.success(request, "Categoría eliminada.")
    return redirect('panel_categorias')


@panel_access
def usuarios(request):
    """Gestión de usuarios: crear, asignar roles, activar/desactivar"""
    if not _solo_admin(request):
        return redirect('panel')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        email = request.POST.get('email', '').strip()
        nombre = request.POST.get('nombre', '').strip()
        rol = request.POST.get('rol', 'cliente')
        es_admin = request.POST.get('es_admin') == 'on'

        if not username or not password:
            messages.error(request, "Usuario y contraseña son obligatorios.")
        elif User.objects.filter(username=username).exists():
            messages.error(request, f"El usuario '{username}' ya existe.")
        elif rol not in dict(Perfil.TIPOS_USUARIO):
            messages.error(request, "Rol no válido.")
        else:
            user = User.objects.create_user(
                username=username, email=email, password=password,
                first_name=nombre)
            _asignar_rol(user, rol, es_admin)
            messages.success(request, f"Usuario '{username}' creado.")
        return redirect('panel_usuarios')

    context = {
        'rol': request.rol,
        'usuarios': User.objects.select_related('perfil')
                    .prefetch_related('groups').order_by('username'),
        'roles': Perfil.TIPOS_USUARIO,
    }
    return render(request, 'panel/usuarios.html', context)


@panel_access
@require_POST
def usuario_guardar(request, user_id):
    if not _solo_admin(request):
        return redirect('panel')
    user = get_object_or_404(User, id=user_id)

    user.email = request.POST.get('email', '').strip()
    user.first_name = request.POST.get('nombre', '').strip()
    user.is_active = request.POST.get('is_active') == 'on'
    es_admin = request.POST.get('es_admin') == 'on'
    rol = request.POST.get('rol', 'cliente')

    if user == request.user and (not user.is_active or not es_admin):
        messages.error(request, "No podés quitarte el acceso a vos mismo.")
        return redirect('panel_usuarios')

    nueva_pass = request.POST.get('password', '').strip()
    if nueva_pass:
        user.set_password(nueva_pass)

    if rol in dict(Perfil.TIPOS_USUARIO):
        _asignar_rol(user, rol, es_admin)
    else:
        user.save()

    messages.success(request, f"Usuario '{user.username}' actualizado.")
    return redirect('panel_usuarios')


@panel_access
def flyers(request):
    """Gestión de flyers/carteles del carrusel de la tienda"""
    if not _solo_admin(request):
        return redirect('panel')
    from .models import CarruselImages

    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        imagen = request.FILES.get('imagen')
        if not titulo:
            messages.error(request, "El título es obligatorio.")
        elif not imagen:
            messages.error(request, "Subí una imagen para el flyer.")
        else:
            CarruselImages.objects.create(
                titulo=titulo,
                imagen=imagen,
                texto=request.POST.get('texto', '').strip(),
                color_texto=request.POST.get('color_texto') or '#FFFFFF',
                color_fondo=request.POST.get('color_fondo') or '#000000',
            )
            messages.success(request, f"Flyer '{titulo}' creado.")
        return redirect('panel_flyers')

    context = {
        'rol': request.rol,
        'flyers': CarruselImages.objects.all(),
    }
    return render(request, 'panel/flyers.html', context)


@panel_access
@require_POST
def flyer_guardar(request, flyer_id):
    if not _solo_admin(request):
        return redirect('panel')
    from .models import CarruselImages
    flyer = get_object_or_404(CarruselImages, id=flyer_id)

    titulo = request.POST.get('titulo', '').strip()
    if titulo:
        flyer.titulo = titulo
    flyer.texto = request.POST.get('texto', '').strip()
    flyer.color_texto = request.POST.get('color_texto') or '#FFFFFF'
    flyer.color_fondo = request.POST.get('color_fondo') or '#000000'
    if request.FILES.get('imagen'):
        flyer.imagen = request.FILES['imagen']
    flyer.save()
    messages.success(request, f"Flyer '{flyer.titulo}' actualizado.")
    return redirect('panel_flyers')


@panel_access
@require_POST
def flyer_borrar(request, flyer_id):
    if not _solo_admin(request):
        return redirect('panel')
    from .models import CarruselImages
    flyer = get_object_or_404(CarruselImages, id=flyer_id)
    flyer.delete()
    messages.success(request, "Flyer eliminado.")
    return redirect('panel_flyers')
